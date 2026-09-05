import discord
from discord import app_commands
from discord.ext import commands, tasks
import time
import re
from typing import Optional
from config import (
    DISBOARD_BOT_ID,
    COLOR_PRIMARY,
    COLOR_GOLD,
    COLOR_SUCCESS,
    COLOR_WARNING,
    BUMP_REWARD_COINS,
    BUMP_REWARD_XP,
    BUMP_COOLDOWN_SECONDS,
    create_embed,
    is_staff_or_private_channel
)

class Bump(commands.Cog):
    """Disboard Bump Tracker, Rewards, and Automated 2-Hour Reminders."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.bump_checker.start()

    def cog_unload(self):
        self.bump_checker.cancel()

    @tasks.loop(seconds=20)
    async def bump_checker(self):
        """Checks every 20 seconds whether a bump reminder is due."""
        try:
            due_servers = await self.db.get_due_bump_reminders()
            for server_data in due_servers:
                guild_id = server_data["guild_id"]
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue

                channel_id = server_data.get("bump_channel_id")
                channel = guild.get_channel(channel_id) if channel_id else None

                # Fallback to public channel (never staff channels)
                if not channel or is_staff_or_private_channel(channel):
                    channel = next(
                        (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages and not is_staff_or_private_channel(c)),
                        None
                    )

                if channel:
                    role_id = server_data.get("bump_ping_role_id")
                    ping_text = f"<@&{role_id}>" if role_id else ""

                    embed = discord.Embed(
                        title="⏰ TIME TO BUMP! 🌾",
                        description=(
                            "The **2-hour** cooldown has expired!\n\n"
                            "👉 Type **`/bump`** in the chat to push **Agri Solutions Group** back to the top of Disboard!\n\n"
                            f"🎁 *Bumper Reward:* **+{BUMP_REWARD_COINS} Agri-Coins** & **+{BUMP_REWARD_XP} XP**!"
                        ),
                        color=COLOR_GOLD
                    )
                    embed.set_footer(text="Agri Solutions Group • Help our community grow!")

                    try:
                        await channel.send(content=ping_text if ping_text else None, embed=embed)
                    except discord.HTTPException:
                        pass

                # Mark reminder as sent
                await self.db.update_server_setting(guild_id, "bump_reminder_sent", 1)
        except Exception as e:
            print(f"[Bump Loop Error]: {e}")

    @bump_checker.before_loop
    async def before_bump_checker(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listens for messages from the Disboard bot to detect successful bumps."""
        if not message.guild:
            return

        if message.author.id == DISBOARD_BOT_ID:
            is_bump = False
            bump_user = None

            # 1. Modern slash command interaction
            if message.interaction and message.interaction.user:
                bump_user = message.interaction.user
                is_bump = True
            
            # 2. Check embed text for 'Bump done' or thumbsup
            if message.embeds:
                for embed in message.embeds:
                    desc = (embed.description or "").lower()
                    title = (embed.title or "").lower()
                    
                    if "bump done" in desc or "bump done" in title or "👍" in desc or "thumbsup" in desc:
                        is_bump = True
                        if not bump_user:
                            match = re.search(r"<@!?(\d+)>", embed.description or "")
                            if match:
                                bump_user = message.guild.get_member(int(match.group(1)))

            if is_bump:
                guild_id = message.guild.id
                now = int(time.time())
                next_time = now + BUMP_COOLDOWN_SECONDS

                # Update database
                await self.db.update_server_setting(guild_id, "next_bump_time", next_time)
                await self.db.update_server_setting(guild_id, "bump_reminder_sent", 0)
                await self.db.update_server_setting(guild_id, "bump_channel_id", message.channel.id)

                user_reward_text = ""
                if bump_user and not bump_user.bot:
                    total_bumps = await self.db.record_bump(
                        bump_user.id,
                        guild_id,
                        coins=BUMP_REWARD_COINS,
                        xp=BUMP_REWARD_XP
                    )
                    user_reward_text = (
                        f"\n\n👏 Thank you {bump_user.mention} for bumping!\n"
                        f"💰 **+{BUMP_REWARD_COINS}** Agri-Coins\n"
                        f"⭐ **+{BUMP_REWARD_XP}** XP\n"
                        f"🏆 Total bumps: **{total_bumps}**"
                    )

                confirm_embed = discord.Embed(
                    title="🌾 Server Successfully Bumped!",
                    description=(
                        f"Thank you for supporting **Agri Solutions Group**! 🚜"
                        f"{user_reward_text}\n\n"
                        f"⏳ **Next bump available:** <t:{next_time}:R> (<t:{next_time}:t>)\n"
                        f"🔔 I will automatically send a reminder when it's time!"
                    ),
                    color=COLOR_SUCCESS
                )
                confirm_embed.set_footer(text="Agri Solutions Group • Auto-Reminder Enabled")

                try:
                    await message.channel.send(embed=confirm_embed)
                except discord.HTTPException:
                    pass

    @app_commands.command(name="bumpstatus", description="Check the current status of the Disboard bump cooldown.")
    async def bumpstatus_command(self, interaction: discord.Interaction):
        settings = await self.db.get_server_settings(interaction.guild.id)
        next_bump = settings.get("next_bump_time", 0)
        now = int(time.time())

        if next_bump <= now or next_bump == 0:
            embed = create_embed(
                title="⏰ Server Ready to Bump!",
                description=(
                    "There is currently **no cooldown**!\n\n"
                    "👉 Type **`/bump`** now to promote the server on Disboard!\n"
                    f"🎁 Reward: **+{BUMP_REWARD_COINS} Agri-Coins** & **+{BUMP_REWARD_XP} XP**."
                ),
                color=COLOR_SUCCESS
            )
        else:
            embed = create_embed(
                title="⏳ Bump Cooldown Active",
                description=(
                    f"The server has been bumped recently.\n\n"
                    f"🌾 **Next bump available:** <t:{next_bump}:R> (<t:{next_bump}:t>)\n"
                    f"🔔 The bot will automatically notify this server when the timer expires!"
                ),
                color=COLOR_WARNING
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="bumpleaderboard", description="View the top Disboard bumpers in the server.")
    async def bumpleaderboard_command(self, interaction: discord.Interaction):
        rows = await self.db.get_leaderboard(interaction.guild.id, sort_by="bumps", limit=10)

        embed = discord.Embed(
            title="⏰ Disboard Bump Champions",
            description="The most dedicated promoters of **Agri Solutions Group**:",
            color=COLOR_GOLD
        )

        active_rows = [r for r in rows if r.get("total_bumps", 0) > 0]
        if not active_rows:
            embed.description = "No bumps recorded yet since the bot joined. Be the first with `/bump`!"
            await interaction.response.send_message(embed=embed)
            return

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        lines = []

        for idx, row in enumerate(active_rows):
            medal = medals[idx] if idx < len(medals) else f"`#{idx+1}`"
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"Member ID: {row['user_id']}"
            bumps = row["total_bumps"]
            lines.append(f"{medal} **{name}** — **{bumps}** bumps")

        embed.description = "\n".join(lines)
        embed.set_footer(text="Agri Solutions Group • Bump every 2 hours for extra coins & XP")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setbumpchannel", description="[Admin] Set the channel for Disboard bump reminders.")
    @app_commands.describe(channel="The text channel where the bot should send bump reminders")
    @app_commands.default_permissions(administrator=True)
    async def setbumpchannel_command(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can configure this setting.", ephemeral=True)
            return

        await self.db.update_server_setting(interaction.guild.id, "bump_channel_id", channel.id)
        embed = create_embed(
            title="✅ Bump Channel Configured",
            description=f"Bump reminders will now be sent to {channel.mention}!",
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setbumprole", description="[Admin] Set a role to ping when the 2-hour bump timer expires.")
    @app_commands.describe(role="The role to mention (e.g. @Bump Reminder)")
    @app_commands.default_permissions(administrator=True)
    async def setbumprole_command(self, interaction: discord.Interaction, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can configure this setting.", ephemeral=True)
            return

        await self.db.update_server_setting(interaction.guild.id, "bump_ping_role_id", role.id)
        embed = create_embed(
            title="✅ Bump Ping Role Configured",
            description=f"The role {role.mention} will be notified when the 2 hours are up!",
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Bump(bot))
