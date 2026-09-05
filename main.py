import asyncio
import os
import sys
from pathlib import Path

# Ensure UTF-8 output encoding for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import discord
from discord.ext import commands

from config import (
    DISCORD_TOKEN,
    GUILD_ID,
    COLOR_PRIMARY,
    LOGO_PATH,
    create_embed,
    is_staff_or_private_channel
)
from database import Database

class AgriBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        # Disable all unwanted ghost pings / role / everyone / user mention notifications
        allowed_mentions = discord.AllowedMentions(
            everyone=False,
            roles=False,
            users=False,
            replied_user=False
        )

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            allowed_mentions=allowed_mentions
        )
        self.db = Database()

    async def setup_hook(self):
        """Initializes database, loads cogs, and synchronizes slash commands."""
        print("🌾 [1/3] Initializing SQLite database...")
        await self.db.init_db()

        print("🚜 [2/3] Loading feature cogs...")
        initial_extensions = [
            "cogs.general",
            "cogs.activity",
            "cogs.bump",
            "cogs.counting",
            "cogs.minigames",
            "cogs.engagement"
        ]

        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                print(f"  ✅ Loaded cog: {ext}")
            except Exception as e:
                print(f"  ❌ Error loading {ext}: {e}")

        print("⚡ [3/3] Synchronizing slash commands...")
        try:
            if GUILD_ID:
                guild = discord.Object(id=GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(f"  ⚡ {len(synced)} Slash commands synced directly to Guild ID: {GUILD_ID}")
            else:
                synced = await self.tree.sync()
                print(f"  ⚡ {len(synced)} Slash commands synced globally with Discord.")
        except Exception as e:
            print(f"  ❌ Error synchronizing commands: {e}")

    async def on_ready(self):
        print("=" * 60)
        print("🌾 AGRI SOLUTIONS GROUP BOT IS ONLINE!")
        print(f"🤖 Logged in as: {self.user.name} (ID: {self.user.id})")
        print(f"🌐 Connected to {len(self.guilds)} guild(s)")
        print("=" * 60)

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="over the fields of Agri Solutions Group | /help"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)

        # Clear any guild-specific duplicates so Discord only shows 1 clean command entry
        for guild in self.guilds:
            try:
                self.tree.clear_commands(guild=guild)
                await self.tree.sync(guild=guild)
            except Exception:
                pass

            if guild.me.guild_permissions.manage_roles:
                try:
                    from cogs.engagement import auto_setup_roles_for_guild
                    await auto_setup_roles_for_guild(guild, self.db)
                    print(f"  🛡️ Auto-configured roles for server: {guild.name}")
                except Exception as e:
                    print(f"  ❌ Error setting up roles for {guild.name}: {e}")

    async def on_guild_join(self, guild: discord.Guild):
        """Automatically create roles when invited to a new server."""
        print(f"🎉 Joined new server: {guild.name} (ID: {guild.id})")
        if guild.me.guild_permissions.manage_roles:
            try:
                from cogs.engagement import auto_setup_roles_for_guild
                await auto_setup_roles_for_guild(guild, self.db)
                print(f"  🛡️ Successfully auto-generated all roles for {guild.name}!")
            except Exception as e:
                print(f"  ❌ Error in auto_setup_roles_for_guild: {e}")

    async def on_member_join(self, member: discord.Member):
        """Sends a welcome message to newly joined members."""
        guild = member.guild
        settings = await self.db.get_server_settings(guild.id)
        channel_id = settings.get("welcome_channel_id")

        channel = guild.get_channel(channel_id) if channel_id else guild.system_channel
        if not channel or is_staff_or_private_channel(channel):
            channel = next(
                (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages and not is_staff_or_private_channel(c)),
                None
            )

        if channel and not is_staff_or_private_channel(channel):
            embed = discord.Embed(
                title=f"🌱 Welcome to Agri Solutions Group, {member.display_name}!",
                description=(
                    f"Welcome to the official server, {member.mention}! 🚜\n\n"
                    f"Connect with other farmers, discuss agriculture tech and machinery, "
                    f"or start building your own virtual farm empire!\n\n"
                    f"👉 **Getting Started:**\n"
                    f"• Type `/help` for all available commands\n"
                    f"• Type `/daily` to claim your daily bonus\n"
                    f"• Type `/farm` to manage your farmland"
                ),
                color=COLOR_PRIMARY
            )
            if member.display_avatar:
                embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Agri Solutions Group • Growing Together")

            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass


def main():
    if not DISCORD_TOKEN or DISCORD_TOKEN == "vul_hier_jouw_bot_token_in":
        print("=" * 60)
        print("❌ ERROR: No valid DISCORD_TOKEN found in .env file!")
        print("👉 Please open the '.env' file and insert your Discord Bot Token.")
        print("👉 Check README.md for step-by-step instructions.")
        print("=" * 60)
        sys.exit(1)

    bot = AgriBot()
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
