import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import time
import asyncio
import re
import unicodedata
from typing import Optional, Dict
from config import (
    COLOR_PRIMARY,
    COLOR_GOLD,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_ERROR,
    create_embed
)

# Bank of 25+ engaging Questions of the Day (QOTD)
QOTD_BANK = [
    "🚜 What is your all-time favorite tractor brand (John Deere, Fendt, Claas, New Holland, Case IH) and why?",
    "🌱 If you could own a 500-hectare farm anywhere in the world, which country and crops would you choose?",
    "🌾 What do you think is the biggest technological revolution coming to agriculture in the next 10 years?",
    "🌽 Organic vs Conventional Farming: Where do you stand on yield vs sustainability?",
    "🐂 Dairy farming, arable crop farming, or greenhouse horticulture: Which branch interests you most?",
    "☀️ Drought and extreme weather: What are the best strategies for modern farmers to adapt?",
    "🤖 Autonomous & Driverless Tractors: Would you trust an AI tractor to manage your entire field overnight?",
    "🥔 What is your favorite dish made from fresh farm-grown potatoes?",
    "🌿 Precision Agriculture & Drones: Have you seen drones used in crop spraying or field mapping in person?",
    "🚜 Horsepower debate: What is the most powerful agricultural machine you have ever driven or seen in action?",
    "🌾 Combine Harvester season is the best time of the year — agree or disagree?",
    "🌻 Solar panels on agricultural land vs pure crop production: How should farm land be prioritized?",
    "🍓 Vertical farming in cities: Can it realistically replace traditional field agriculture for vegetables?",
    "🚜 Old school mechanical tractors with zero electronics vs Modern tech-packed smart tractors: Which do you prefer to fix?",
    "💧 What is the most innovative irrigation system you have learned about or used?",
]

class ClaimDropView(discord.ui.View):
    def __init__(self, db, coins: int, xp: int, max_claims: int = 3):
        super().__init__(timeout=120.0)
        self.db = db
        self.coins = coins
        self.xp = xp
        self.max_claims = max_claims
        self.claimed_users = []

    @discord.ui.button(label="🌾 Claim Supply Crate! (0/3)", style=discord.ButtonStyle.success, emoji="📦")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.claimed_users:
            await interaction.response.send_message("❌ You have already claimed your share from this crate!", ephemeral=True)
            return

        if len(self.claimed_users) >= self.max_claims:
            await interaction.response.send_message("❌ All spots for this supply crate have been claimed!", ephemeral=True)
            return

        self.claimed_users.append(interaction.user.id)
        claims_count = len(self.claimed_users)

        await self.db.add_coins(interaction.user.id, interaction.guild.id, self.coins)
        await self.db.add_xp(interaction.user.id, interaction.guild.id, self.xp)

        button.label = f"Claimed ({claims_count}/{self.max_claims})"
        if claims_count >= self.max_claims:
            button.disabled = True
            button.style = discord.ButtonStyle.secondary

        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed(title="📦 Mystery Supply Crate", color=COLOR_GOLD)
        claimers_text = "\n".join(f"• <@{uid}> (Prize: `+{self.coins}` 🪙 / `+{self.xp}` ⭐)" for uid in self.claimed_users)
        
        status_text = "🎉 **All rewards claimed!**" if claims_count >= self.max_claims else f"⚡ **{self.max_claims - claims_count} spot(s) remaining! Click fast!**"

        embed.description = (
            f"A high-value harvest supply crate dropped into the valley!\n\n"
            f"{status_text}\n\n"
            f"🏆 **Winners ({claims_count}/{self.max_claims}):**\n{claimers_text}"
        )
        embed.color = COLOR_SUCCESS if claims_count >= self.max_claims else COLOR_GOLD
        embed.set_footer(text="Agri Solutions Group • Fast finger farmers win rewards!")

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class Engagement(commands.Cog):
    """Engagement boosters: Random chat supply drops, QOTD, Quests, Voice XP, Stats Channels, and Broadcasts."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.channel_message_counts: Dict[int, int] = {}
        self.drop_thresholds: Dict[int, int] = {}
        self.voice_xp_loop.start()
        self.stats_updater_loop.start()
        self.periodic_airdrop_loop.start()

    def cog_unload(self):
        self.voice_xp_loop.cancel()
        self.stats_updater_loop.cancel()
        self.periodic_airdrop_loop.cancel()

    # --- 🌾 RANDOM MYSTERY CHAT DROPS ---

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Update Daily Quest message count
        await self.db.update_quest_progress(message.author.id, message.guild.id, "messages_count", 1)

        channel_id = message.channel.id
        current_count = self.channel_message_counts.get(channel_id, 0) + 1
        self.channel_message_counts[channel_id] = current_count

        # Target threshold between 15 and 25 messages
        threshold = self.drop_thresholds.get(channel_id)
        if not threshold:
            threshold = random.randint(15, 25)
            self.drop_thresholds[channel_id] = threshold

        if current_count >= threshold:
            self.channel_message_counts[channel_id] = 0
            self.drop_thresholds[channel_id] = random.randint(15, 25)

            settings = await self.db.get_server_settings(message.guild.id)
            if settings.get("drops_enabled", 1) == 1:
                # Never drop in staff, admin, or private channels
                ch_name = message.channel.name.lower()
                excluded = ["staff", "admin", "mod", "private", "bot-log", "log", "ticket", "rules", "audit"]
                if any(x in ch_name for x in excluded):
                    return

                # If a specific drop channel is configured, only drop there
                configured_drop_ch = settings.get("drops_channel_id")
                if configured_drop_ch and message.channel.id != configured_drop_ch:
                    return

                min_c = settings.get("drop_min_coins", 75)
                max_c = settings.get("drop_max_coins", 180)
                min_x = settings.get("drop_min_xp", 40)
                max_x = settings.get("drop_max_xp", 90)
                spots = settings.get("drop_spots", 3)

                coins = random.randint(min_c, max(min_c, max_c))
                xp = random.randint(min_x, max(min_x, max_x))
                view = ClaimDropView(self.db, coins, xp, max_claims=spots)

                embed = discord.Embed(
                    title="🌾 AIRDROP: Mystery Harvest Crate! 📦",
                    description=(
                        "A supply crate just dropped into the channel for active farmers!\n\n"
                        f"👉 **Click the button below fast to claim your reward ({spots} spots available)!**"
                    ),
                    color=COLOR_GOLD
                )
                embed.set_footer(text="Agri Solutions Group • Stay active to catch more drops!")

                try:
                    await message.channel.send(embed=embed, view=view)
                except discord.HTTPException:
                    pass

    # --- ⏰ PERIODIC AIRDROPS LOOP (Keeps chat moving even when quiet) ---

    @tasks.loop(minutes=5)
    async def periodic_airdrop_loop(self):
        """Periodically drops a loot crate into the configured drops channel (never staff channels)."""
        try:
            now = time.time()
            for guild in self.bot.guilds:
                settings = await self.db.get_server_settings(guild.id)
                if settings.get("drops_enabled", 1) != 1:
                    continue

                interval = settings.get("drop_interval_minutes", 60) * 60
                last_drop = getattr(self, f"_last_periodic_drop_{guild.id}", 0)
                if now - last_drop < interval:
                    continue
                setattr(self, f"_last_periodic_drop_{guild.id}", now)

                # 1. First priority: Configured drops channel
                target_channel = None
                configured_channel_id = settings.get("drops_channel_id")
                if configured_channel_id:
                    target_channel = guild.get_channel(configured_channel_id)

                # 2. Second priority: Find public chat, strictly excluding staff/admin/private channels
                if not target_channel:
                    excluded_keywords = ["staff", "admin", "mod", "private", "bot-log", "log", "announcement", "welcome", "ticket", "rules", "audit", "team", "management", "leiding", "owner"]
                    for ch in guild.text_channels:
                        ch_name = ch.name.lower()
                        # Check channel name
                        if any(k in ch_name for k in excluded_keywords):
                            continue
                        # Check category name if channel is in a category
                        if ch.category and any(k in ch.category.name.lower() for k in excluded_keywords):
                            continue
                        # Must have send messages permission and view channel permission
                        if ch.permissions_for(guild.me).send_messages:
                            if "general" in ch_name or "chat" in ch_name or "main" in ch_name or "lounge" in ch_name or "algemeen" in ch_name:
                                target_channel = ch
                                break

                    # Fallback to any public text channel that is not staff/admin
                    if not target_channel:
                        for ch in guild.text_channels:
                            ch_name = ch.name.lower()
                            if any(k in ch_name for k in excluded_keywords):
                                continue
                            if ch.category and any(k in ch.category.name.lower() for k in excluded_keywords):
                                continue
                            if ch.permissions_for(guild.me).send_messages:
                                target_channel = ch
                                break

                if target_channel:
                    min_c = settings.get("drop_min_coins", 100)
                    max_c = settings.get("drop_max_coins", 250)
                    min_x = settings.get("drop_min_xp", 50)
                    max_x = settings.get("drop_max_xp", 120)
                    spots = settings.get("drop_spots", 3)

                    coins = random.randint(min_c, max(min_c, max_c))
                    xp = random.randint(min_x, max(min_x, max_x))
                    view = ClaimDropView(self.db, coins, xp, max_claims=spots)

                    embed = discord.Embed(
                        title="🚜 HOURLY HARVEST SUPPLY DROP! 📦",
                        description=(
                            "The Agri Solutions Group logistics truck just dropped a bonus crate!\n\n"
                            f"🎁 **{spots} Lucky Farmers** can claim **+{coins} Coins & +{xp} XP** right now!\n"
                            "👉 *Click the button below before it runs out!*"
                        ),
                        color=COLOR_GOLD
                    )
                    embed.set_footer(text="Agri Solutions Group • Hourly Community Airdrop")
                    await target_channel.send(embed=embed, view=view)
        except Exception as e:
            print(f"[Periodic Airdrop Error]: {e}")

    @periodic_airdrop_loop.before_loop
    async def before_periodic_airdrop_loop(self):
        await self.bot.wait_until_ready()

    # --- 📊 LIVE SERVER STATS AUTO-UPDATER LOOP ---

    @tasks.loop(minutes=10)
    async def stats_updater_loop(self):
        """Updates live voice channel counters for total members and online status."""
        try:
            for guild in self.bot.guilds:
                if not guild.me.guild_permissions.manage_channels:
                    continue

                settings = await self.db.get_server_settings(guild.id)
                mem_ch_id = settings.get("stat_members_channel_id")
                onl_ch_id = settings.get("stat_online_channel_id")
                goal_ch_id = settings.get("stat_goal_channel_id")

                if not mem_ch_id and not onl_ch_id and not goal_ch_id:
                    continue

                total_members = guild.member_count
                online_members = len([m for m in guild.members if m.status != discord.Status.offline and not m.bot])

                if mem_ch_id:
                    ch = guild.get_channel(mem_ch_id)
                    if ch:
                        try:
                            await ch.edit(name=f"👥・Members: {total_members}")
                        except Exception:
                            pass

                if onl_ch_id:
                    ch = guild.get_channel(onl_ch_id)
                    if ch:
                        try:
                            await ch.edit(name=f"🌾・Online: {online_members}")
                        except Exception:
                            pass

                if goal_ch_id:
                    ch = guild.get_channel(goal_ch_id)
                    if ch:
                        try:
                            await ch.edit(name="🚜・Agri Status: 🟢 Live")
                        except Exception:
                            pass
        except Exception as e:
            print(f"[Stats Updater Loop Error]: {e}")

    @stats_updater_loop.before_loop
    async def before_stats_updater_loop(self):
        await self.bot.wait_until_ready()

    # --- 🎙️ VOICE CHANNEL PASSIVE XP ---

    @tasks.loop(minutes=5)
    async def voice_xp_loop(self):
        """Awards XP & Coins to members actively in Voice Channels every 5 minutes."""
        try:
            for guild in self.bot.guilds:
                for vc in guild.voice_channels:
                    # Require at least 2 non-bot members in voice to prevent solo AFK farming
                    active_members = [
                        m for m in vc.members 
                        if not m.bot and not m.voice.self_deaf and not m.voice.deaf
                    ]
                    if len(active_members) >= 2:
                        for member in active_members:
                            await self.db.add_xp(member.id, guild.id, 20)
                            await self.db.add_coins(member.id, guild.id, 10)
        except Exception as e:
            print(f"[Voice XP Loop Error]: {e}")

    @voice_xp_loop.before_loop
    async def before_voice_xp_loop(self):
        await self.bot.wait_until_ready()

    # --- 🎯 DAILY QUESTS ---

    @app_commands.command(name="quests", description="View your 3 daily quests and claim completion rewards.")
    async def quests_command(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        quests = await self.db.get_daily_quests(user_id, guild_id)

        msg_done = min(5, quests["messages_count"])
        trivia_done = min(1, quests["trivia_done"])
        farm_done = min(1, quests["farm_done"])

        msg_check = "✅" if msg_done >= 5 else "⏳"
        trivia_check = "✅" if trivia_done >= 1 else "⏳"
        farm_check = "✅" if farm_done >= 1 else "⏳"

        is_all_done = (msg_done >= 5 and trivia_done >= 1 and farm_done >= 1)
        claimed = quests["claimed"] == 1

        embed = discord.Embed(
            title=f"🎯 Daily Farming Quests — {interaction.user.display_name}",
            description="Complete all 3 missions daily to earn **+200 Agri-Coins** and **+150 XP**!\n*(Resets every midnight UTC)*",
            color=COLOR_PRIMARY
        )

        embed.add_field(
            name="1. 💬 Chat Activity",
            value=f"{msg_check} Send 5 messages in chat (`{msg_done}/5`)",
            inline=False
        )
        embed.add_field(
            name="2. 🧠 Agricultural Knowledge",
            value=f"{trivia_check} Play `/trivia` (`{trivia_done}/1`)",
            inline=False
        )
        embed.add_field(
            name="3. 🚜 Farm Management",
            value=f"{farm_check} Plant or harvest a crop with `/plant` or `/harvest` (`{farm_done}/1`)",
            inline=False
        )

        if claimed:
            embed.add_field(name="🎁 Reward Status", value="🟢 **Claimed for today!** Come back tomorrow for new quests.", inline=False)
        elif is_all_done:
            embed.add_field(name="🎁 Reward Status", value="⭐ **All Quests Complete!** Click `/claimquests` or the command below to claim!", inline=False)
        else:
            embed.add_field(name="🎁 Reward Status", value="⏳ In progress... Complete the tasks above!", inline=False)

        embed.set_footer(text="Agri Solutions Group • Keep our community active!")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="claimquests", description="Claim the reward after completing all 3 daily quests.")
    async def claimquests_command(self, interaction: discord.Interaction):
        result = await self.db.claim_daily_quests(interaction.user.id, interaction.guild.id)
        if not result["success"]:
            embed = create_embed(
                title="⏳ Quests Incomplete",
                description=result["message"],
                color=COLOR_WARNING
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = create_embed(
            title="🎉 Daily Quests Completed!",
            description=result["message"],
            color=COLOR_SUCCESS
        )
        if interaction.user.display_avatar:
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    # --- 💬 QUESTION OF THE DAY (QOTD) ---

    @app_commands.command(name="qotd", description="Post or view an engaging agricultural Question of the Day.")
    async def qotd_command(self, interaction: discord.Interaction):
        question = random.choice(QOTD_BANK)

        embed = discord.Embed(
            title="💬 Agri Solutions — Question of the Day! 🌾",
            description=f"### {question}\n\n👉 *Reply in the chat below with your thoughts and experience!*",
            color=COLOR_GOLD
        )
        embed.set_footer(text="Agri Solutions Group • Discussion & Community")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="testdrop", description="[Admin] Manually spawn a harvest supply crate in this channel.")
    @app_commands.default_permissions(administrator=True)
    async def testdrop_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can trigger test drops.", ephemeral=True)
            return

        coins = random.randint(100, 250)
        xp = random.randint(50, 120)
        view = ClaimDropView(self.db, coins, xp, max_claims=3)

        embed = discord.Embed(
            title="🌾 AIRDROP: Mystery Harvest Crate! 📦",
            description=(
                "A supply crate just dropped into the channel for active farmers!\n\n"
                "👉 **Click the button below fast to claim your reward (3 spots available)!**"
            ),
            color=COLOR_GOLD
        )
        embed.set_footer(text="Agri Solutions Group • Community Airdrop")
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="flashdrop", description="[Admin] Drop a high-value community reward crate with custom coins and spots.")
    @app_commands.describe(coins="Agri-Coins reward per winner", xp="XP reward per winner", spots="Number of winners (1-5)")
    @app_commands.default_permissions(administrator=True)
    async def flashdrop_command(self, interaction: discord.Interaction, coins: int = 250, xp: int = 150, spots: int = 3):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can trigger flash drops.", ephemeral=True)
            return

        spots = max(1, min(5, spots))
        view = ClaimDropView(self.db, coins, xp, max_claims=spots)

        embed = discord.Embed(
            title="⚡ SPECIAL HARVEST FLASH EVENT! 🎁",
            description=(
                f"🚨 **Attention Farmers!** The Agri Solutions Group logistics truck just dropped a **MEGA SUPPLY CRATE**!\n\n"
                f"💰 **Prize per Winner:** `+{coins:,}` Agri-Coins\n"
                f"⭐ **Experience:** `+{xp:,}` XP\n"
                f"👥 **Available Spots:** **{spots} Winners**\n\n"
                f"👉 **Click the button below immediately to claim your share!**"
            ),
            color=COLOR_GOLD
        )
        embed.set_footer(text="Agri Solutions Group • Community Flash Event")
        await interaction.response.send_message(embed=embed, view=view)

    # --- ⚙️ MINIGAME & AIRDROP CONFIGURATION COMMANDS ---

    @app_commands.command(name="setdropchannel", description="[Admin] Set the dedicated channel where harvest airdrops and supply crates will appear.")
    @app_commands.describe(channel="The channel for airdrops (leave empty to reset to automatic public chat)")
    @app_commands.default_permissions(administrator=True)
    async def setdropchannel_command(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can configure drop channels.", ephemeral=True)
            return

        ch_id = channel.id if channel else None
        await self.db.update_server_setting(interaction.guild.id, "drops_channel_id", ch_id)

        if channel:
            embed = create_embed(
                title="✅ Airdrop Channel Updated",
                description=f"All automatic harvest airdrops and chat crates will now appear exclusively in {channel.mention}!",
                color=COLOR_SUCCESS
            )
        else:
            embed = create_embed(
                title="🔄 Airdrop Channel Reset",
                description="Airdrops will now automatically appear in public general chat (staff channels are strictly excluded).",
                color=COLOR_SUCCESS
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setdropinterval", description="[Admin] Set how often automatic harvest airdrops appear (in minutes).")
    @app_commands.describe(minutes="Interval between drops (e.g. 15, 30, 45, 60, 120)")
    @app_commands.default_permissions(administrator=True)
    async def setdropinterval_command(self, interaction: discord.Interaction, minutes: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can configure drop intervals.", ephemeral=True)
            return

        minutes = max(10, min(720, minutes))
        await self.db.update_server_setting(interaction.guild.id, "drop_interval_minutes", minutes)

        embed = create_embed(
            title="⏱️ Drop Interval Updated",
            description=f"Automatic harvest airdrops will now drop every **{minutes} minutes**!",
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setdroprewards", description="[Admin] Customize the coin, XP rewards and winner spots for harvest drops.")
    @app_commands.describe(
        min_coins="Minimum coins per winner",
        max_coins="Maximum coins per winner",
        min_xp="Minimum XP per winner",
        max_xp="Maximum XP per winner",
        spots="Number of winners per crate (1-5)"
    )
    @app_commands.default_permissions(administrator=True)
    async def setdroprewards_command(
        self,
        interaction: discord.Interaction,
        min_coins: int = 100,
        max_coins: int = 250,
        min_xp: int = 50,
        max_xp: int = 120,
        spots: int = 3
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can configure drop rewards.", ephemeral=True)
            return

        spots = max(1, min(5, spots))
        min_coins = max(10, min_coins)
        max_coins = max(min_coins, max_coins)
        min_xp = max(5, min_xp)
        max_xp = max(min_xp, max_xp)

        await self.db.update_server_setting(interaction.guild.id, "drop_min_coins", min_coins)
        await self.db.update_server_setting(interaction.guild.id, "drop_max_coins", max_coins)
        await self.db.update_server_setting(interaction.guild.id, "drop_min_xp", min_xp)
        await self.db.update_server_setting(interaction.guild.id, "drop_max_xp", max_xp)
        await self.db.update_server_setting(interaction.guild.id, "drop_spots", spots)

        embed = create_embed(
            title="🎁 Airdrop Rewards Updated",
            description=(
                f"• **Coins per Winner:** `{min_coins}` – `{max_coins}` 🪙\n"
                f"• **XP per Winner:** `{min_xp}` – `{max_xp}` ⭐\n"
                f"• **Winner Spots:** `{spots}` Farmers 👥"
            ),
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="toggledrops", description="[Admin] Enable or disable automatic harvest airdrops.")
    @app_commands.describe(enabled="True to enable airdrops, False to disable")
    @app_commands.default_permissions(administrator=True)
    async def toggledrops_command(self, interaction: discord.Interaction, enabled: bool):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can toggle airdrops.", ephemeral=True)
            return

        val = 1 if enabled else 0
        await self.db.update_server_setting(interaction.guild.id, "drops_enabled", val)

        state = "Enabled 🟢" if enabled else "Disabled 🔴"
        embed = create_embed(
            title=f"📦 Airdrops {state}",
            description=f"Automatic harvest airdrops are now **{state}** for this server.",
            color=COLOR_SUCCESS if enabled else COLOR_WARNING
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setminigameschannel", description="[Admin] Restrict all minigames (/farm, /trivia, /tractor-race, etc.) to one channel.")
    @app_commands.describe(channel="The channel for minigames (leave empty to allow in all channels)")
    @app_commands.default_permissions(administrator=True)
    async def setminigameschannel_command(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can configure minigame channels.", ephemeral=True)
            return

        ch_id = channel.id if channel else None
        await self.db.update_server_setting(interaction.guild.id, "minigames_channel_id", ch_id)

        if channel:
            embed = create_embed(
                title="🎮 Minigames Channel Configured",
                description=f"All minigames (`/farm`, `/trivia`, `/tractor-race`, `/coinflip`, `/dice`) are now restricted to {channel.mention}!",
                color=COLOR_SUCCESS
            )
        else:
            embed = create_embed(
                title="🌐 Minigames Allowed Everywhere",
                description="Members can now play minigames in all text channels where the bot has permission.",
                color=COLOR_SUCCESS
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setminigamerewards", description="[Admin] Adjust payout and XP multipliers for trivia and tractor racing.")
    @app_commands.describe(
        trivia_coins="Coins awarded for correct trivia answer",
        trivia_xp="XP awarded for correct trivia answer",
        race_multiplier="Payout multiplier for winning tractor race (e.g. 2.5 or 3.0)"
    )
    @app_commands.default_permissions(administrator=True)
    async def setminigamerewards_command(
        self,
        interaction: discord.Interaction,
        trivia_coins: int = 50,
        trivia_xp: int = 35,
        race_multiplier: float = 3.0
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can adjust minigame rewards.", ephemeral=True)
            return

        race_multiplier = max(1.5, min(10.0, race_multiplier))
        await self.db.update_server_setting(interaction.guild.id, "trivia_coins", trivia_coins)
        await self.db.update_server_setting(interaction.guild.id, "trivia_xp", trivia_xp)
        await self.db.update_server_setting(interaction.guild.id, "race_multiplier", race_multiplier)

        embed = create_embed(
            title="🎮 Minigame Rewards Updated",
            description=(
                f"• **Trivia Win Prize:** `+{trivia_coins}` 🪙 & `+{trivia_xp}` ⭐\n"
                f"• **Tractor Race Multiplier:** `{race_multiplier}x` payout!"
            ),
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="minigamesettings", description="[Admin] View the full configuration dashboard for minigames and airdrops.")
    @app_commands.default_permissions(administrator=True)
    async def minigamesettings_command(self, interaction: discord.Interaction):
        settings = await self.db.get_server_settings(interaction.guild.id)

        # Drops channel
        drop_ch_id = settings.get("drops_channel_id")
        drop_ch_text = f"<#{drop_ch_id}>" if drop_ch_id else "*Auto (Public Chat, excluding Staff)*"

        # Minigames channel
        mg_ch_id = settings.get("minigames_channel_id")
        mg_ch_text = f"<#{mg_ch_id}>" if mg_ch_id else "*Allowed in all channels*"

        drops_enabled = "🟢 Enabled" if settings.get("drops_enabled", 1) == 1 else "🔴 Disabled"
        interval = settings.get("drop_interval_minutes", 60)
        min_c = settings.get("drop_min_coins", 100)
        max_c = settings.get("drop_max_coins", 250)
        min_x = settings.get("drop_min_xp", 50)
        max_x = settings.get("drop_max_xp", 120)
        spots = settings.get("drop_spots", 3)
        t_coins = settings.get("trivia_coins", 50)
        t_xp = settings.get("trivia_xp", 35)
        race_mult = settings.get("race_multiplier", 3.0)

        embed = discord.Embed(
            title="⚙️ Agri Bot — Minigames & Airdrops Control Panel",
            description="Manage and customize all community minigames and airdrop settings below:",
            color=COLOR_PRIMARY
        )

        embed.add_field(
            name="📦 Airdrop Settings",
            value=(
                f"• **Status:** {drops_enabled}\n"
                f"• **Channel:** {drop_ch_text}\n"
                f"• **Interval:** Every `{interval}` minutes\n"
                f"• **Reward Range:** `{min_c}` – `{max_c}` 🪙 | `{min_x}` – `{max_x}` ⭐\n"
                f"• **Winner Spots:** `{spots}` Farmers"
            ),
            inline=False
        )

        embed.add_field(
            name="🎮 Minigames Gameplay & Restrictions",
            value=(
                f"• **Minigames Channel:** {mg_ch_text}\n"
                f"• **Trivia Win Prize:** `+{t_coins}` 🪙 | `+{t_xp}` ⭐\n"
                f"• **Tractor Race Multiplier:** `{race_mult}x` Wager Payout"
            ),
            inline=False
        )

        embed.add_field(
            name="🛠️ Quick Configuration Commands",
            value=(
                "`/setdropchannel` • Set where airdrops drop\n"
                "`/setdropinterval` • Change how often drops appear\n"
                "`/setdroprewards` • Change coins/XP & winner spots\n"
                "`/toggledrops` • Enable or disable drops\n"
                "`/setminigameschannel` • Restrict minigames to a channel\n"
                "`/setminigamerewards` • Customize trivia & race prizes\n"
                "`/flashdrop` • Spawn instant test crate"
            ),
            inline=False
        )
        embed.set_footer(text="Agri Solutions Group • Admin Control Panel")
        await interaction.response.send_message(embed=embed)

    # --- 📊 AUTO-UPDATING SERVER STATS CHANNELS ---

    @app_commands.command(name="setupstats", description="[Admin] Create live, auto-updating member & activity counters at the top of the server.")
    @app_commands.default_permissions(administrator=True)
    async def setupstats_command(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except Exception:
            pass

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Only administrators can configure server stats.", ephemeral=True)
            return

        guild = interaction.guild
        if not guild.me.guild_permissions.manage_channels:
            await interaction.followup.send("❌ The bot requires **Manage Channels** permission to create stat counters!", ephemeral=True)
            return

        # Overwrite to make channels read-only voice channels (connect denied for @everyone)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True),
            guild.me: discord.PermissionOverwrite(connect=True, manage_channels=True, view_channel=True)
        }

        total_members = guild.member_count
        online_members = len([m for m in guild.members if m.status != discord.Status.offline and not m.bot])

        try:
            # 1. Create Category at the very top (position=0)
            category = await guild.create_category(
                name="📊 SERVER STATS 📊",
                position=0,
                reason="Agri Bot automated live stats setup"
            )

            # 2. Create locked stat voice channels
            ch_members = await guild.create_voice_channel(
                name=f"👥・Members: {total_members}",
                category=category,
                overwrites=overwrites,
                reason="Agri Bot live member counter"
            )

            ch_online = await guild.create_voice_channel(
                name=f"🌾・Online: {online_members}",
                category=category,
                overwrites=overwrites,
                reason="Agri Bot live online counter"
            )

            ch_status = await guild.create_voice_channel(
                name="🚜・Agri Status: 🟢 Live",
                category=category,
                overwrites=overwrites,
                reason="Agri Bot live status counter"
            )

            # Save channel IDs to database
            await self.db.update_server_setting(guild.id, "stat_category_id", category.id)
            await self.db.update_server_setting(guild.id, "stat_members_channel_id", ch_members.id)
            await self.db.update_server_setting(guild.id, "stat_online_channel_id", ch_online.id)
            await self.db.update_server_setting(guild.id, "stat_goal_channel_id", ch_status.id)

            embed = discord.Embed(
                title="📊 Live Server Stats Configured!",
                description=(
                    "The live counter channels have been generated at the top of your server!\n\n"
                    f"• {ch_members.mention} *(Total Members)*\n"
                    f"• {ch_online.mention} *(Online Farmers)*\n"
                    f"• {ch_status.mention} *(Agri Bot Status)*\n\n"
                    "🔄 *These counters will automatically update in real-time every 10 minutes!*"
                ),
                color=COLOR_SUCCESS
            )
            embed.set_footer(text="Agri Solutions Group • Live Activity Tracking")
            await interaction.followup.send(embed=embed)

        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Failed to create stat channels: {e}")

    # --- 📢 COMMUNITY POLLS & BROADCASTS ---

    @app_commands.command(name="agripoll", description="Create an official community poll with up to 4 options.")
    @app_commands.describe(
        question="The question to ask the community",
        option1="First option",
        option2="Second option",
        option3="Third option (optional)",
        option4="Fourth option (optional)"
    )
    async def agripoll_command(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: Optional[str] = None,
        option4: Optional[str] = None
    ):
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        options = [option1, option2]
        if option3:
            options.append(option3)
        if option4:
            options.append(option4)

        poll_lines = []
        for i, opt in enumerate(options):
            poll_lines.append(f"{emojis[i]} **{opt}**")

        embed = discord.Embed(
            title="📊 COMMUNITY POLL 🌾",
            description=f"### {question}\n\n" + "\n\n".join(poll_lines) + "\n\n👉 *React below to cast your vote!*",
            color=COLOR_GOLD
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
        embed.set_footer(text="Agri Solutions Group • Community Decision")

        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        for i in range(len(options)):
            try:
                await msg.add_reaction(emojis[i])
            except Exception:
                pass

    @app_commands.command(name="dailybroadcast", description="Publish today's Agricultural Weather, Crop Market Forecast & QOTD.")
    async def dailybroadcast_command(self, interaction: discord.Interaction):
        weather_conditions = [
            ("☀️ Golden Sunshine across the Valley", "All crops grow **+20% faster** today! Great day for harvesting."),
            ("🌧️ Gentle Spring Rains", "Fields are well-watered. Fertilizer efficiency boosted by **+15%**!"),
            ("🌤️ Mild Weather & Clear Skies", "Perfect conditions for tractor races and loonwerk contracts."),
            ("🌾 Warm Summer Breeze", "Wheat and Corn market sell prices are **surging +25%**!"),
        ]
        weather_title, weather_desc = random.choice(weather_conditions)
        qotd_text = random.choice(QOTD_BANK)

        view = ClaimDropView(self.db, 150, 75, max_claims=5)

        embed = discord.Embed(
            title="🚜 DAILY AGRI BULLETIN & MARKET FORECAST 🌾",
            description=(
                f"### {weather_title}\n{weather_desc}\n\n"
                f"**📈 Daily Crop Market Trends:**\n"
                f"• 🌾 **Wheat:** `15` 🪙 (+25% Surge!)\n"
                f"• 🥕 **Carrots:** `28` 🪙 (Stable)\n"
                f"• 🌽 **Corn:** `45` 🪙 (High Demand)\n"
                f"• 🥔 **Potatoes:** `70` 🪙 (Top Value)\n\n"
                f"**💬 Question of the Day:**\n"
                f"> *{qotd_text}*\n\n"
                f"🎁 **Early Bird Bonus:** The first 5 farmers to click the button below get **+150 Coins & +75 XP**!"
            ),
            color=COLOR_PRIMARY
        )
        embed.set_footer(text="Agri Solutions Group • Daily Agricultural Report")
        await interaction.response.send_message(embed=embed, view=view)

    # --- 🎭 LEVEL ROLES SETUP ---

    @app_commands.command(name="setlevelrole", description="[Admin] Automatically award a Discord role when members reach a level.")
    @app_commands.describe(level="The required level", role="The role to grant")
    @app_commands.default_permissions(administrator=True)
    async def setlevelrole_command(self, interaction: discord.Interaction, level: int, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can configure level roles.", ephemeral=True)
            return

        await self.db.set_level_role(interaction.guild.id, level, role.id)
        embed = create_embed(
            title="✅ Level Role Configured",
            description=f"Members who reach **Level {level}** will now automatically receive the {role.mention} role!",
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="listlevelroles", description="View all configured level role rewards.")
    async def listlevelroles_command(self, interaction: discord.Interaction):
        roles_data = await self.db.get_level_roles(interaction.guild.id)
        if not roles_data:
            await interaction.response.send_message("ℹ️ No level roles configured yet. Use `/setlevelrole` to add some!", ephemeral=True)
            return

        lines = []
        for r in roles_data:
            role = interaction.guild.get_role(r["role_id"])
            role_str = role.mention if role else f"Role ID: {r['role_id']}"
            lines.append(f"• **Level {r['level']}:** {role_str}")

        embed = discord.Embed(
            title="🎭 Level Role Rewards",
            description="\n".join(lines),
            color=COLOR_PRIMARY
        )
        embed.set_footer(text="Agri Solutions Group • Level up by chatting to unlock roles!")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setuproles", description="[Admin] Automatically create and configure all Staff, Member, and Level roles.")
    @app_commands.default_permissions(administrator=True)
    async def setuproles_command(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except Exception:
            pass

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Only administrators can run the server setup.", ephemeral=True)
            return

        guild = interaction.guild
        if not guild.me.guild_permissions.manage_roles:
            await interaction.followup.send(
                "❌ The bot is missing the **Manage Roles** permission! Please make sure the bot has Administrator/Manage Roles.",
                ephemeral=True
            )
            return

        created_staff, created_levels = await auto_setup_roles_for_guild(guild, self.db)

        embed = discord.Embed(
            title="🎉 Server Roles Successfully Configured!",
            description="The complete hierarchy for **Agri Solutions Group** has been generated and linked!",
            color=COLOR_SUCCESS
        )

        embed.add_field(
            name="🛡️ Staff & Management Hierarchy",
            value="\n".join(created_staff) if created_staff else "*None*",
            inline=False
        )

        embed.add_field(
            name="🌾 Auto-Level Rewards (Unlocked via Chat XP)",
            value="\n".join(created_levels) if created_levels else "*None*",
            inline=False
        )

        embed.set_footer(text="Agri Solutions Group • Members will automatically receive level roles as they chat!")
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="verifycurrent",
        description="[Admin] Give the Verified Member role to all current server members."
    )
    @app_commands.default_permissions(administrator=True)
    async def verifycurrent_command(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except Exception:
            pass

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Only administrators can run this command.", ephemeral=True)
            return

        guild = interaction.guild
        if not guild.me.guild_permissions.manage_roles:
            await interaction.followup.send(
                "❌ The bot requires the **Manage Roles** permission to assign roles!",
                ephemeral=True
            )
            return

        # 1. Find or create Verified Member role
        verified_role = discord.utils.get(guild.roles, name="🌾 Verified Member")
        if not verified_role:
            verified_role = discord.utils.get(guild.roles, name="Verified Member")
        if not verified_role:
            try:
                verified_role = await guild.create_role(
                    name="🌾 Verified Member",
                    color=discord.Color(0x95A5A6),
                    reason="Created by Agri Bot verifycurrent command"
                )
            except discord.HTTPException as e:
                await interaction.followup.send(f"❌ Failed to create Verified Member role: {e}")
                return

        # 2. Chunk guild to load all members
        if not guild.chunked:
            try:
                await guild.chunk()
            except Exception:
                pass

        verified_count = 0
        already_verified = 0
        non_bot_members = [m for m in guild.members if not m.bot]

        for member in non_bot_members:
            if verified_role not in member.roles:
                try:
                    await member.add_roles(verified_role, reason="Agri Bot: Mass verification for current members")
                    verified_count += 1
                    await asyncio.sleep(0.35)
                except discord.HTTPException:
                    pass
            else:
                already_verified += 1

        embed = discord.Embed(
            title="🌾 Current Members Verified!",
            description=(
                f"Successfully checked **{len(non_bot_members)}** current members in **{guild.name}**!\n\n"
                f"✅ **{verified_count}** member(s) newly received {verified_role.mention}.\n"
                f"ℹ️ **{already_verified}** member(s) already had the role.\n\n"
                f"⚠️ *Note: Newly joining members will NOT automatically receive this role.*"
            ),
            color=COLOR_SUCCESS
        )
        embed.set_footer(text="Agri Solutions Group • Member Verification")
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="setuppermissions",
        description="[Admin] Apply recommended permissions to all Staff, Management, and Member roles."
    )
    @app_commands.default_permissions(administrator=True)
    async def setuppermissions_command(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except Exception:
            pass

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Only administrators can run this setup.", ephemeral=True)
            return

        guild = interaction.guild
        if not guild.me.guild_permissions.manage_roles:
            await interaction.followup.send("❌ The bot requires the **Manage Roles** permission!", ephemeral=True)
            return

        updated_roles, skipped_roles = await apply_permissions_for_guild(guild)

        embed = discord.Embed(
            title="🛡️ Role Permissions Configured Successfully!",
            description="All staff, management, moderator, and member role permissions have been updated to industry standard best practices!",
            color=COLOR_SUCCESS
        )

        if updated_roles:
            embed.add_field(
                name="✅ Configured Roles",
                value="\n".join(updated_roles),
                inline=False
            )

        if skipped_roles:
            embed.add_field(
                name="⚠️ Hierarchy Skipped (Move bot role higher)",
                value="\n".join(skipped_roles),
                inline=False
            )

        embed.set_footer(text="Agri Solutions Group • Safe & Structured Server Permissions")
        await interaction.followup.send(embed=embed)


def get_role_permissions_map() -> dict:
    """Returns the standard permission presets for each staff/member role."""
    return {
        "👑 Owner": discord.Permissions(administrator=True),
        "💼 Management": discord.Permissions(administrator=True),
        "⚡ Senior Administrator": discord.Permissions(administrator=True),
        "🛡️ Administrator": discord.Permissions(
            manage_guild=True,
            manage_roles=True,
            manage_channels=True,
            view_audit_log=True,
            kick_members=True,
            ban_members=True,
            moderate_members=True,
            manage_messages=True,
            mute_members=True,
            deafen_members=True,
            move_members=True,
            mention_everyone=True,
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            use_external_emojis=True,
            connect=True,
            speak=True,
            use_voice_activation=True
        ),
        "🔰 Junior Administrator": discord.Permissions(
            manage_channels=True,
            view_audit_log=True,
            kick_members=True,
            ban_members=True,
            moderate_members=True,
            manage_messages=True,
            mute_members=True,
            deafen_members=True,
            move_members=True,
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            use_external_emojis=True,
            connect=True,
            speak=True,
            use_voice_activation=True
        ),
        "🛠️ Senior Moderator": discord.Permissions(
            view_audit_log=True,
            kick_members=True,
            ban_members=True,
            moderate_members=True,
            manage_messages=True,
            mute_members=True,
            deafen_members=True,
            move_members=True,
            priority_speaker=True,
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            use_external_emojis=True,
            connect=True,
            speak=True,
            use_voice_activation=True
        ),
        "🛡️ Moderator": discord.Permissions(
            kick_members=True,
            moderate_members=True,
            manage_messages=True,
            mute_members=True,
            deafen_members=True,
            move_members=True,
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            use_external_emojis=True,
            connect=True,
            speak=True,
            use_voice_activation=True
        ),
        "🔰 Junior Moderator": discord.Permissions(
            moderate_members=True,
            manage_messages=True,
            mute_members=True,
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            use_external_emojis=True,
            connect=True,
            speak=True,
            use_voice_activation=True
        ),
        "🌾 Verified Member": discord.Permissions(
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            use_external_emojis=True,
            use_external_stickers=True,
            connect=True,
            speak=True,
            use_voice_activation=True,
            create_public_threads=True,
            send_messages_in_threads=True,
            change_nickname=True
        ),
        "⏰ Bump Reminder": discord.Permissions(
            read_messages=True,
            send_messages=True,
            read_message_history=True
        )
    }


async def apply_permissions_for_guild(guild: discord.Guild) -> tuple:
    """Applies clean permission sets to matching staff and member roles in a guild."""
    perm_map = get_role_permissions_map()
    updated = []
    skipped = []
    bot_top_role = guild.me.top_role

    for role_name, perms in perm_map.items():
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            # Fallback search without emoji
            clean_name = role_name.split()[-1].lower()
            role = next((r for r in guild.roles if clean_name in r.name.lower()), None)

        if role:
            if role.position >= bot_top_role.position:
                skipped.append(f"• {role.mention} *(Above bot role in hierarchy)*")
                continue

            try:
                await role.edit(permissions=perms, reason="Agri Bot automated role permissions setup")
                updated.append(f"• {role.mention}")
            except discord.HTTPException as e:
                skipped.append(f"• {role.mention} *({e})*")

    return updated, skipped


async def auto_setup_roles_for_guild(guild: discord.Guild, db) -> tuple:
    """Helper function to automatically generate and register all staff and level roles for a guild."""
    perm_map = get_role_permissions_map()
    staff_roles_def = [
        {"name": "👑 Owner", "color": discord.Color(0xF1C40F), "hoist": True, "mentionable": False},
        {"name": "💼 Management", "color": discord.Color(0xD4AC0D), "hoist": True, "mentionable": False},
        {"name": "⚡ Senior Administrator", "color": discord.Color(0x922B21), "hoist": True, "mentionable": False},
        {"name": "🛡️ Administrator", "color": discord.Color(0xC0392B), "hoist": True, "mentionable": False},
        {"name": "🔰 Junior Administrator", "color": discord.Color(0xCD6155), "hoist": True, "mentionable": False},
        {"name": "🛠️ Senior Moderator", "color": discord.Color(0xD35400), "hoist": True, "mentionable": False},
        {"name": "🛡️ Moderator", "color": discord.Color(0xE67E22), "hoist": True, "mentionable": False},
        {"name": "🔰 Junior Moderator", "color": discord.Color(0xF39C12), "hoist": True, "mentionable": False},
        {"name": "⏰ Bump Reminder", "color": discord.Color(0x9B59B6), "hoist": False, "mentionable": True},
        {"name": "🌾 Verified Member", "color": discord.Color(0x95A5A6), "hoist": False, "mentionable": False},
    ]

    level_roles_def = [
        {"level": 1, "name": "Level 1 • 🌱 Novice Farmer", "color": discord.Color(0x58D68D), "hoist": False},
        {"level": 5, "name": "Level 5 • 🚜 Tractor Operator", "color": discord.Color(0x3498DB), "hoist": False},
        {"level": 10, "name": "Level 10 • 🌾 Master Harvester", "color": discord.Color(0x16A085), "hoist": False},
        {"level": 15, "name": "Level 15 • 🌿 Crop Specialist", "color": discord.Color(0x27AE60), "hoist": False},
        {"level": 20, "name": "Level 20 • 🐂 Agronomy Expert", "color": discord.Color(0x2ECC71), "hoist": False},
        {"level": 30, "name": "Level 30 • 🏗️ Agricultural Engineer", "color": discord.Color(0x1ABC9C), "hoist": True},
        {"level": 40, "name": "Level 40 • 🏆 Agri Executive", "color": discord.Color(0xE67E22), "hoist": True},
        {"level": 50, "name": "Level 50 • 👑 Agri Solutions Legend", "color": discord.Color(0xF1C40F), "hoist": True},
    ]

    created_staff = []
    created_levels = []
    existing_roles = {r.name: r for r in guild.roles}
    bot_top_role = guild.me.top_role

    # 1. Staff roles
    for s_def in staff_roles_def:
        role_name = s_def["name"]
        perms = perm_map.get(role_name, discord.Permissions.none())

        if role_name in existing_roles:
            role = existing_roles[role_name]
            # Edit permissions if below bot
            if role.position < bot_top_role.position:
                try:
                    await role.edit(permissions=perms, reason="Agri Bot automated permissions setup")
                except Exception:
                    pass
        else:
            try:
                role = await guild.create_role(
                    name=role_name,
                    color=s_def["color"],
                    hoist=s_def["hoist"],
                    mentionable=s_def["mentionable"],
                    permissions=perms,
                    reason="Agri Bot automated staff role setup"
                )
            except discord.HTTPException as e:
                print(f"Error creating role {role_name}: {e}")
                continue

        created_staff.append(f"• {role.mention}")
        if role_name == "⏰ Bump Reminder":
            await db.update_server_setting(guild.id, "bump_ping_role_id", role.id)

    # 2. Level roles
    for l_def in level_roles_def:
        role_name = l_def["name"]
        if role_name in existing_roles:
            role = existing_roles[role_name]
        else:
            try:
                role = await guild.create_role(
                    name=role_name,
                    color=l_def["color"],
                    hoist=l_def["hoist"],
                    reason="Agri Bot automated level role setup"
                )
            except discord.HTTPException as e:
                print(f"Error creating level role {role_name}: {e}")
                continue

        await db.set_level_role(guild.id, l_def["level"], role.id)
        created_levels.append(f"• **Level {l_def['level']}:** {role.mention}")

    return created_staff, created_levels


async def setup(bot):
    await bot.add_cog(Engagement(bot))
