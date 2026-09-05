import discord
from discord import app_commands
from discord.ext import commands
import random
import time
from typing import Optional
from config import COLOR_PRIMARY, COLOR_GOLD, COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING, XP_PER_MESSAGE, XP_COOLDOWN_SECONDS, LOGO_PATH, create_embed
from database import xp_for_level

# Agricultural ranks and titles based on level
AGRI_TITLES = [
    (1, "🌱 Novice Farmer"),
    (5, "🚜 Tractor Operator"),
    (10, "🌾 Master Harvester"),
    (15, "🌿 Crop Specialist"),
    (20, "🐂 Agronomy Expert"),
    (30, "🏗️ Agricultural Engineer"),
    (40, "🏆 Agri Executive"),
    (50, "👑 Agri Solutions Legend"),
]

def get_agri_title(level: int) -> str:
    current_title = AGRI_TITLES[0][1]
    for req_lvl, title in AGRI_TITLES:
        if level >= req_lvl:
            current_title = title
        else:
            break
    return current_title

def render_progress_bar(current: int, total: int, length: int = 10) -> str:
    if total <= 0:
        return "▓" * length
    percentage = max(0.0, min(1.0, current / total))
    filled = int(round(length * percentage))
    empty = length - filled
    return f"{'🟩' * filled}{'⬜' * empty} `{int(percentage * 100)}%`"

class Activity(commands.Cog):
    """XP, Leveling, Daily rewards, and Community Engagement."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.xp_cooldowns = {} # (user_id, guild_id) -> last_timestamp
        self.last_announced_levels = {} # (user_id, guild_id) -> last_announced_level

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        guild_id = message.guild.id
        now = time.time()

        # Cooldown check (max 1x XP gain per minute to avoid chat spamming)
        last_xp = self.xp_cooldowns.get((user_id, guild_id), 0)
        if now - last_xp >= XP_COOLDOWN_SECONDS:
            self.xp_cooldowns[(user_id, guild_id)] = now
            xp_gain = random.randint(*XP_PER_MESSAGE)
            new_xp, new_lvl, leveled_up = await self.db.add_xp(user_id, guild_id, xp_gain)

            # Auto-assign any earned level roles (including Level 1) if missing
            level_roles = await self.db.get_level_roles(guild_id)
            for lr in level_roles:
                if lr["level"] <= new_lvl:
                    role = message.guild.get_role(lr["role_id"])
                    if role and isinstance(message.author, discord.Member) and role not in message.author.roles:
                        if role.position < message.guild.me.top_role.position:
                            try:
                                await message.author.add_roles(role, reason=f"Agri Bot: Level {lr['level']} Reward")
                            except discord.HTTPException:
                                pass

            # Prevent duplicate / spam announcements: Only announce each level ONCE
            last_announced = self.last_announced_levels.get((user_id, guild_id), 0)
            if leveled_up and new_lvl > last_announced:
                self.last_announced_levels[(user_id, guild_id)] = new_lvl

                bonus_coins = new_lvl * 50
                await self.db.add_coins(user_id, guild_id, bonus_coins)
                title = get_agri_title(new_lvl)

                # Check if level-up announcements are enabled
                settings = await self.db.get_server_settings(guild_id)
                if settings.get("levelup_enabled", 1) == 1:
                    # Check if a dedicated level-up channel is configured
                    target_ch = message.channel
                    configured_ch_id = settings.get("levelup_channel_id")
                    if configured_ch_id:
                        ch = message.guild.get_channel(configured_ch_id)
                        if ch and ch.permissions_for(message.guild.me).send_messages:
                            target_ch = ch

                    # Check if this specific level unlocked a new role
                    role_awarded_text = ""
                    for lr in level_roles:
                        if lr["level"] == new_lvl:
                            role = message.guild.get_role(lr["role_id"])
                            if role:
                                role_awarded_text = f"\n🎭 **Unlocked Role:** {role.mention}"

                    embed = discord.Embed(
                        title="🎉 LEVEL UP! 🎉",
                        description=(
                            f"Congratulations **{message.author.display_name}**! You reached **Level {new_lvl}**!\n\n"
                            f"🏷️ **New Title:** `{title}`\n"
                            f"💰 **Level-up Bonus:** `+{bonus_coins}` Agri-Coins{role_awarded_text}"
                        ),
                        color=COLOR_GOLD
                    )
                    if message.author.display_avatar:
                        embed.set_thumbnail(url=message.author.display_avatar.url)
                    embed.set_footer(text="Agri Solutions Group • Stay active to earn more rewards!")

                    try:
                        await target_ch.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                    except discord.HTTPException:
                        pass

    @app_commands.command(name="rank", description="View your rank, level, XP progression, and statistics.")
    @app_commands.describe(member="The member whose profile you want to view (defaults to yourself)")
    async def rank_command(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        if target.bot:
            await interaction.response.send_message("❌ Bots do not participate in the ranking system!", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user_data = await self.db.get_or_create_user(target.id, guild_id)

        xp = user_data["xp"]
        level = user_data["level"]
        coins = user_data["coins"]
        streak = user_data["daily_streak"]
        bumps = user_data["total_bumps"]
        counting = user_data["counting_contributions"]

        cur_lvl_xp = xp_for_level(level)
        next_lvl_xp = xp_for_level(level + 1)
        xp_in_level = max(0, xp - cur_lvl_xp)
        xp_needed = max(1, next_lvl_xp - cur_lvl_xp)

        progress_bar = render_progress_bar(xp_in_level, xp_needed, length=8)
        title = get_agri_title(level)

        embed = discord.Embed(
            title=f"🌾 Farmer Profile: {target.display_name}",
            color=COLOR_PRIMARY
        )
        if target.display_avatar:
            embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(name="🏷️ Agricultural Title", value=f"**{title}**", inline=False)
        embed.add_field(name="⭐ Level & XP", value=f"**Level {level}** ({xp:,} total XP)\n{progress_bar}\n`{xp_in_level:,} / {xp_needed:,} XP`", inline=False)
        embed.add_field(name="💰 Agri-Coins", value=f"**{coins:,}** 🪙", inline=True)
        embed.add_field(name="🔥 Daily Streak", value=f"**{streak}** day(s)", inline=True)
        embed.add_field(name="⏰ Disboard Bumps", value=f"**{bumps}** times", inline=True)
        embed.add_field(name="🔢 Count Contributions", value=f"**{counting}** numbers", inline=True)

        embed.set_footer(text="Agri Solutions Group • Earn XP by chatting and playing minigames")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Claim your daily Agri-Coins and XP bonus!")
    async def daily_command(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        result = await self.db.claim_daily(interaction.user.id, guild_id)

        if not result["success"]:
            embed = create_embed(
                title="⏳ Please Wait!",
                description=result["message"],
                color=COLOR_WARNING
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = create_embed(
            title="🎁 Daily Harvest Bonus!",
            description=result["message"],
            color=COLOR_SUCCESS
        )
        if interaction.user.display_avatar:
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="View the top farmers on the server.")
    @app_commands.describe(category="Choose which leaderboard to display")
    @app_commands.choices(category=[
        app_commands.Choice(name="⭐ Experience (XP / Level)", value="xp"),
        app_commands.Choice(name="💰 Wealthiest Farmers (Agri-Coins)", value="coins"),
        app_commands.Choice(name="⏰ Top Promoters (Disboard Bumps)", value="bumps"),
        app_commands.Choice(name="🔢 Master Counters (Counting Contributions)", value="counting")
    ])
    async def leaderboard_command(self, interaction: discord.Interaction, category: Optional[app_commands.Choice[str]] = None):
        cat_key = category.value if category else "xp"
        rows = await self.db.get_leaderboard(interaction.guild.id, sort_by=cat_key, limit=10)

        cat_titles = {
            "xp": "⭐ Top Farmers — Most Experience (XP)",
            "coins": "💰 Wealthiest Farmers — Agri-Coins",
            "bumps": "⏰ Top Promoters — Most Disboard Bumps",
            "counting": "🔢 Counting Champions — Most Numbers Counted"
        }

        embed = discord.Embed(
            title=f"🌾 {cat_titles[cat_key]}",
            color=COLOR_GOLD
        )

        if not rows:
            embed.description = "No data recorded on this server yet. Start chatting to join the leaderboard!"
            await interaction.response.send_message(embed=embed)
            return

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        lines = []

        for idx, row in enumerate(rows):
            medal = medals[idx] if idx < len(medals) else f"`#{idx+1}`"
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"Member ID: {row['user_id']}"

            if cat_key == "xp":
                val = f"**Level {row['level']}** (`{row['xp']:,} XP`)"
            elif cat_key == "coins":
                val = f"**{row['coins']:,}** 🪙"
            elif cat_key == "bumps":
                val = f"**{row['total_bumps']}** bumps"
            else:
                val = f"**{row['counting_contributions']}** numbers"

            lines.append(f"{medal} **{name}** — {val}")

        embed.description = "\n".join(lines)
        embed.set_footer(text="Agri Solutions Group Leaderboard")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pay", description="Transfer Agri-Coins to another member.")
    @app_commands.describe(member="The member to send coins to", amount="The amount of Agri-Coins")
    async def pay_command(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.id == interaction.user.id:
            await interaction.response.send_message("❌ You cannot send coins to yourself!", ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message("❌ You cannot send coins to a bot!", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be at least 1 Agri-Coin.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        sender = await self.db.get_or_create_user(interaction.user.id, guild_id)

        if sender["coins"] < amount:
            await interaction.response.send_message(
                f"❌ Insufficient funds! Your current balance is **{sender['coins']}** Agri-Coins.",
                ephemeral=True
            )
            return

        await self.db.add_coins(interaction.user.id, guild_id, -amount)
        await self.db.add_coins(member.id, guild_id, amount)

        embed = create_embed(
            title="💸 Transfer Successful!",
            description=f"🤝 {interaction.user.mention} sent **{amount:,}** Agri-Coins to {member.mention}!",
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="syncroles", description="Synchronize your earned Level Roles based on your current level.")
    async def syncroles_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user_data = await self.db.get_or_create_user(interaction.user.id, guild.id)
        user_lvl = user_data["level"]
        level_roles = await self.db.get_level_roles(guild.id)

        added = []
        bot_top_role = guild.me.top_role

        for lr in level_roles:
            if lr["level"] <= user_lvl:
                role = guild.get_role(lr["role_id"])
                if role and isinstance(interaction.user, discord.Member) and role not in interaction.user.roles:
                    if role.position < bot_top_role.position:
                        try:
                            await interaction.user.add_roles(role, reason="Agri Bot /syncroles manual sync")
                            added.append(role.mention)
                        except discord.HTTPException:
                            pass

        if added:
            embed = create_embed(
                title="✅ Level Roles Synchronized!",
                description=f"You have been granted your missing Level Roles:\n" + "\n".join(f"• {r}" for r in added),
                color=COLOR_SUCCESS
            )
        else:
            embed = create_embed(
                title="✅ Up to Date!",
                description=f"Your roles are already fully synchronized for **Level {user_lvl}**!",
                color=COLOR_SUCCESS
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="setlevelupchannel", description="[Admin] Set a specific channel where level-up messages are posted.")
    @app_commands.describe(channel="The channel for level-up announcements (leave empty to post in the active chat)")
    @app_commands.default_permissions(administrator=True)
    async def setlevelupchannel_command(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can configure level-up channels.", ephemeral=True)
            return

        ch_id = channel.id if channel else None
        await self.db.update_server_setting(interaction.guild.id, "levelup_channel_id", ch_id)

        if channel:
            embed = create_embed(
                title="✅ Level-Up Channel Configured",
                description=f"Level-up celebration cards will now be posted in {channel.mention}!",
                color=COLOR_SUCCESS
            )
        else:
            embed = create_embed(
                title="🔄 Level-Up Channel Reset",
                description="Level-up cards will now be posted in whichever channel the member reaches their new level.",
                color=COLOR_SUCCESS
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="togglelevelup", description="[Admin] Enable or disable level-up announcement messages.")
    @app_commands.describe(enabled="True to show level-up messages, False to silence them (roles still granted)")
    @app_commands.default_permissions(administrator=True)
    async def togglelevelup_command(self, interaction: discord.Interaction, enabled: bool):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can toggle level-up announcements.", ephemeral=True)
            return

        val = 1 if enabled else 0
        await self.db.update_server_setting(interaction.guild.id, "levelup_enabled", val)

        state = "Enabled 🟢" if enabled else "Silenced 🔴"
        embed = create_embed(
            title=f"🎉 Level-Up Messages {state}",
            description=f"Level-up celebration messages are now **{state}** (level roles & coins are always granted).",
            color=COLOR_SUCCESS if enabled else COLOR_WARNING
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Activity(bot))
