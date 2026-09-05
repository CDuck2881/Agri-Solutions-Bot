import os
from pathlib import Path
import discord
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"
DB_PATH = BASE_DIR / "agri_bot.db"

# Bot tokens & IDs
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None
DISBOARD_BOT_ID = int(os.getenv("DISBOARD_BOT_ID", "302050872383242240"))

# Brand Color Palette (Agri Solutions Group Green & Gold)
COLOR_PRIMARY = discord.Color(0x2D7E37)  # Agri Green
COLOR_GOLD = discord.Color(0xF4A81D)     # Harvest Gold
COLOR_SUCCESS = discord.Color(0x2ECC71)  # Success Green
COLOR_WARNING = discord.Color(0xE67E22)  # Warning Amber
COLOR_ERROR = discord.Color(0xE74C3C)    # Error Red

# Economy & Reward Settings
XP_PER_MESSAGE = (15, 25)         # Min / max XP per chat message
XP_COOLDOWN_SECONDS = 60          # 1 XP reward per minute to prevent spam
DAILY_BASE_REWARD = 100           # Base Agri-Coins for /daily
DAILY_STREAK_BONUS = 25           # Extra coins per daily streak day
BUMP_REWARD_COINS = 150           # Agri-Coins reward for bumping via Disboard
BUMP_REWARD_XP = 100              # XP reward for bumping via Disboard
BUMP_COOLDOWN_SECONDS = 7200      # 2 hours Disboard cooldown

# Crops for the /farm minigame
CROPS = {
    "wheat": {
        "name": "🌾 Wheat",
        "cost": 10,
        "sell_price": 25,
        "grow_time_seconds": 60,   # 1 minute for fast gameplay
        "xp": 15
    },
    "carrot": {
        "name": "🥕 Carrots",
        "cost": 25,
        "sell_price": 60,
        "grow_time_seconds": 180,  # 3 minutes
        "xp": 35
    },
    "corn": {
        "name": "🌽 Corn",
        "cost": 60,
        "sell_price": 160,
        "grow_time_seconds": 360,  # 6 minutes
        "xp": 80
    },
    "potato": {
        "name": "🥔 Potatoes",
        "cost": 120,
        "sell_price": 320,
        "grow_time_seconds": 600, # 10 minutes
        "xp": 160
    }
}

# Machinery & Tractor upgrades
TRACTOR_UPGRADES = {
    1: {"name": "🚜 Old Hand Plow", "multiplier": 1.0, "cost": 0},
    2: {"name": "🚜 Agri-Basic Tractor", "multiplier": 1.25, "cost": 500},
    3: {"name": "🚜 Agri-Pro Turbo Harvester", "multiplier": 1.6, "cost": 2000},
    4: {"name": "🚜 Agri-Titan Smart Harvester", "multiplier": 2.2, "cost": 7500},
}

def is_staff_or_private_channel(channel) -> bool:
    """Returns True if the channel or its parent category belongs to staff, admin, or private areas."""
    if not channel:
        return True
    
    name = getattr(channel, "name", "").lower()
    blocked = [
        "staff", "admin", "mod", "private", "bot-log", "log", "announcement",
        "welcome", "ticket", "rules", "audit", "team", "management", "leiding",
        "owner", "secret", "internal", "dev", "moderator", "cmd", "command", "hidden"
    ]
    if any(b in name for b in blocked):
        return True
        
    category = getattr(channel, "category", None)
    if category:
        cat_name = category.name.lower()
        if any(b in cat_name for b in blocked):
            return True
            
    return False

def create_embed(
    title: str,
    description: str = "",
    color: discord.Color = COLOR_PRIMARY,
    thumbnail: bool = False
) -> discord.Embed:
    """Creates a branded embed with Agri Solutions Group styling."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    embed.set_footer(text="Agri Solutions Group • Growing Together")
    if thumbnail and LOGO_PATH.exists():
        embed.set_thumbnail(url="attachment://logo.png")
    return embed
