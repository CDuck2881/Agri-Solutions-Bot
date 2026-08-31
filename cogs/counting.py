import discord
from discord import app_commands
from discord.ext import commands
import re
from typing import Optional
from config import COLOR_PRIMARY, COLOR_GOLD, COLOR_SUCCESS, COLOR_ERROR, create_embed

class Counting(commands.Cog):
    """Counting minigame with automated validation, highscore records, and milestone rewards."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        settings = await self.db.get_server_settings(message.guild.id)
        counting_channel_id = settings.get("counting_channel_id")

        if not counting_channel_id or message.channel.id != counting_channel_id:
            return

        content = message.content.strip()
        match = re.match(r"^(\d+)", content)
        if not match:
            return

        number = int(match.group(1))
        result = await self.db.process_count(message.guild.id, message.author.id, number)
        status = result["status"]

        if status == "CORRECT":
            if result.get("milestone"):
                await message.add_reaction("🌟")
                milestone_val = result["milestone"]
                bonus_coins = 50 + (milestone_val // 2)
                bonus_xp = 30 + (milestone_val // 4)
                await self.db.add_coins(message.author.id, message.guild.id, bonus_coins)
                await self.db.add_xp(message.author.id, message.guild.id, bonus_xp)

                embed = discord.Embed(
                    title=f"🏆 MILESTONE REACHED: {milestone_val}!",
                    description=(
                        f"Amazing teamwork! {message.author.mention} reached the milestone of **{milestone_val}**!\n\n"
                        f"🎁 **Milestone Bonus:** `+{bonus_coins}` Agri-Coins & `+{bonus_xp}` XP!\n"
                        f"👉 Next number is **{milestone_val + 1}**!"
                    ),
                    color=COLOR_GOLD
                )
                await message.channel.send(embed=embed)
            else:
                await message.add_reaction("✅")

        elif status == "DOUBLE_COUNT":
            await message.add_reaction("❌")
            ruined = result["ruined_at"]
            highest = result["highest_count"]

            embed = discord.Embed(
                title="💥 Oops! You cannot count twice in a row!",
                description=(
                    f"{message.author.mention} ruined the count at **{ruined}** by counting twice!\n\n"
                    f"🏆 **Server Highscore:** `{highest}`\n\n"
                    f"🌱 **Starting over!** The next number is **1**."
                ),
                color=COLOR_ERROR
            )
            embed.set_footer(text="Agri Solutions Group • Take turns with other farmers!")
            await message.channel.send(embed=embed)

        elif status == "WRONG_NUMBER":
            await message.add_reaction("❌")
            expected = result["expected"]
            received = result["received"]
            ruined = result["ruined_at"]
            highest = result["highest_count"]

            embed = discord.Embed(
                title="💥 Oops! Wrong Number!",
                description=(
                    f"{message.author.mention} typed **{received}**, but we needed **{expected}**!\n\n"
                    f"📉 **Count ruined at:** `{ruined}`\n"
                    f"🏆 **Server Highscore:** `{highest}`\n\n"
                    f"🌱 **Starting over!** The next number is **1**."
                ),
                color=COLOR_ERROR
            )
            embed.set_footer(text="Agri Solutions Group • Stay focused!")
            await message.channel.send(embed=embed)

    @app_commands.command(name="countstats", description="View the current counting status and all-time record.")
    async def countstats_command(self, interaction: discord.Interaction):
        settings = await self.db.get_server_settings(interaction.guild.id)
        channel_id = settings.get("counting_channel_id")
        current = settings.get("current_count", 0)
        highest = settings.get("highest_count", 0)
        last_user_id = settings.get("last_counter_id")

        channel_mention = f"<#{channel_id}>" if channel_id else "*Not configured yet (use /setcounting)*"
        last_counter = f"<@{last_user_id}>" if last_user_id else "*Nobody yet*"

        embed = discord.Embed(
            title="🔢 Counting Statistics",
            color=COLOR_PRIMARY
        )
        embed.add_field(name="📍 Counting Channel", value=channel_mention, inline=False)
        embed.add_field(name="🎯 Current Count", value=f"**{current}** (Next number: **{current + 1}**)", inline=True)
        embed.add_field(name="🏆 All-Time Highscore", value=f"**{highest}**", inline=True)
        embed.add_field(name="👤 Last Counter", value=last_counter, inline=True)

        embed.set_footer(text="Agri Solutions Group • Earn coins and XP with every valid number!")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setcounting", description="[Admin] Configure the official counting channel.")
    @app_commands.describe(channel="The text channel where counting takes place")
    @app_commands.default_permissions(administrator=True)
    async def setcounting_command(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can configure this setting.", ephemeral=True)
            return

        await self.db.update_server_setting(interaction.guild.id, "counting_channel_id", channel.id)
        embed = create_embed(
            title="✅ Counting Channel Configured",
            description=(
                f"The official counting channel is set to {channel.mention}!\n\n"
                f"📜 **Rules:**\n"
                f"1. Start at **1** and count upwards.\n"
                f"2. You **cannot** count twice in a row.\n"
                f"3. Any mistake resets the counter to **1**.\n"
                f"4. Every correct number awards **Agri-Coins & XP**!"
            ),
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Counting(bot))
