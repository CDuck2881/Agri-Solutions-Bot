import discord
from discord import app_commands
from discord.ext import commands
import time
from config import COLOR_PRIMARY, COLOR_GOLD, COLOR_SUCCESS, LOGO_PATH, create_embed

class General(commands.Cog):
    """General commands and information about Agri Solutions Group."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="View all available commands of the Agri Bot.")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌾 Agri Solutions Group — Bot Commands",
            description="Welcome to the official **Agri Solutions Group** Discord bot!\nBelow you will find an overview of all available modules and commands.",
            color=COLOR_PRIMARY
        )

        embed.add_field(
            name="🚜 **Agri Farming & Minigames**",
            value=(
                "• `/farm` — View your farm plots, growing crops & machinery\n"
                "• `/plant` — Sow crops (wheat, carrots, corn, potatoes)\n"
                "• `/harvest` — Harvest ripe crops for coins & XP\n"
                "• `/market` — Check crop market prices and tractor upgrades\n"
                "• `/upgrade` — Upgrade your tractor for higher harvest multipliers\n"
                "• `/trivia` — Play the agricultural trivia quiz\n"
                "• `/tractor-race` — Bet on high-speed tractor races\n"
                "• `/coinflip` & `/dice` — Quick betting minigames"
            ),
            inline=False
        )

        embed.add_field(
            name="📈 **Activity, XP & Economy**",
            value=(
                "• `/rank [member]` — View profile card, level, XP progress & badge\n"
                "• `/leaderboard` — Server leaderboards for XP, coins, bumps & counting\n"
                "• `/daily` — Claim your daily coins reward and build your streak\n"
                "• `/pay [member] [amount]` — Send Agri-Coins to another member"
            ),
            inline=False
        )

        embed.add_field(
            name="🔢 **Counting Minigame**",
            value=(
                "• `/countstats` — View current count and all-time server record\n"
                "• `/setcounting #channel` — *(Admin)* Configure the designated counting channel"
            ),
            inline=False
        )

        embed.add_field(
            name="⏰ **Disboard Auto-Bump & Reminders**",
            value=(
                "• `/bumpstatus` — See when the server can be bumped again\n"
                "• `/bumpleaderboard` — View the top server promoters\n"
                "• `/setbumpchannel #channel` — *(Admin)* Set the reminder channel\n"
                "• `/setbumprole @role` — *(Admin)* Set the role to ping when bump is ready"
            ),
            inline=False
        )

        embed.add_field(
            name="🎯 **Community Activity & Engagement**",
            value=(
                "• `/quests` — Complete 3 daily missions for **+200 Coins & +150 XP**\n"
                "• `/claimquests` — Claim completed daily quest rewards\n"
                "• `/qotd` — Post or view an agricultural Question of the Day\n"
                "• `📦 Random Supply Drops` — Click the mystery harvest crates in active chat!\n"
                "• `🎙️ Voice XP` — Earn passive XP and coins in voice channels\n"
                "• `/setlevelrole` & `/listlevelroles` — *(Admin)* Auto role rewards on level-up"
            ),
            inline=False
        )

        embed.add_field(
            name="ℹ️ **General Information**",
            value=(
                "• `/info` — Information and stats about Agri Solutions Group\n"
                "• `/ping` — Check the bot latency and response time"
            ),
            inline=False
        )

        file = None
        if LOGO_PATH.exists():
            file = discord.File(str(LOGO_PATH), filename="logo.png")
            embed.set_thumbnail(url="attachment://logo.png")

        embed.set_footer(text="Agri Solutions Group • Agricultural Innovation")
        
        if file:
            await interaction.response.send_message(embed=embed, file=file)
        else:
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="info", description="Information and statistics about Agri Solutions Group.")
    async def info_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌱 Agri Solutions Group",
            description=(
                "**Agri Solutions Group** stands for innovation, collaboration, and sustainable growth in modern agriculture.\n\n"
                "Our Discord community brings together farming professionals, students, and enthusiasts in agriculture, mechanization, and technology."
            ),
            color=COLOR_PRIMARY
        )

        guild = interaction.guild
        member_count = guild.member_count if guild else "Unknown"

        embed.add_field(name="👥 Community Members", value=f"**{member_count}** members", inline=True)
        embed.add_field(name="⚡ Bot Version", value="**v2.0 (Agri Suite)**", inline=True)
        embed.add_field(name="🤖 Bot Latency", value=f"**{round(self.bot.latency * 1000)}ms**", inline=True)

        embed.add_field(
            name="🌟 Our Core Pillars",
            value=(
                "🌾 **Knowledge Sharing:** Exchanging experiences and industry innovations.\n"
                "🚜 **Mechanization:** Discussions on machinery, precision agriculture, and tech.\n"
                "🤝 **Community:** A welcoming, active, and supportive environment."
            ),
            inline=False
        )

        file = None
        if LOGO_PATH.exists():
            file = discord.File(str(LOGO_PATH), filename="logo.png")
            embed.set_thumbnail(url="attachment://logo.png")

        embed.set_footer(text="Agri Solutions Group • Growing Together")
        
        if file:
            await interaction.response.send_message(embed=embed, file=file)
        else:
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Check bot latency and connectivity.")
    async def ping_command(self, interaction: discord.Interaction):
        start_time = time.time()
        await interaction.response.send_message("🌾 *Measuring latency...*")
        end_time = time.time()

        latency_api = round(self.bot.latency * 1000)
        latency_roundtrip = round((end_time - start_time) * 1000)

        embed = create_embed(
            title="🏓 Pong! Connection Status",
            description=(
                f"📡 **Discord Websocket:** `{latency_api}ms`\n"
                f"⚡ **API Roundtrip:** `{latency_roundtrip}ms`\n"
                f"🟢 **Status:** All systems operational!"
            ),
            color=COLOR_SUCCESS
        )
        await interaction.edit_original_response(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(General(bot))
