import aiosqlite
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from config import DB_PATH, TRACTOR_UPGRADES, CROPS, DAILY_BASE_REWARD, DAILY_STREAK_BONUS

def xp_for_level(level: int) -> int:
    """Calculates the total XP required for a given level."""
    return int(100 * (level ** 1.5))

def level_from_xp(xp: int) -> int:
    """Calculates the current level based on total XP."""
    level = 1
    while xp >= xp_for_level(level + 1):
        level += 1
    return level

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)

    async def init_db(self):
        """Initializes all database tables."""
        async with aiosqlite.connect(self.db_path) as db:
            # User table for XP, activity, economy & stats
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER,
                    guild_id INTEGER,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    coins INTEGER DEFAULT 100,
                    last_daily TEXT,
                    daily_streak INTEGER DEFAULT 0,
                    last_message_ts INTEGER DEFAULT 0,
                    tractor_level INTEGER DEFAULT 1,
                    total_bumps INTEGER DEFAULT 0,
                    counting_contributions INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)

            # Farm crops table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS farms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    guild_id INTEGER,
                    crop_key TEXT,
                    planted_at INTEGER,
                    harvest_at INTEGER
                )
            """)

            # Server settings (counting, bumps, notification channels)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS server_settings (
                    guild_id INTEGER PRIMARY KEY,
                    counting_channel_id INTEGER DEFAULT NULL,
                    current_count INTEGER DEFAULT 0,
                    last_counter_id INTEGER DEFAULT NULL,
                    highest_count INTEGER DEFAULT 0,
                    bump_channel_id INTEGER DEFAULT NULL,
                    bump_ping_role_id INTEGER DEFAULT NULL,
                    next_bump_time INTEGER DEFAULT 0,
                    bump_reminder_sent INTEGER DEFAULT 1,
                    welcome_channel_id INTEGER DEFAULT NULL,
                    qotd_channel_id INTEGER DEFAULT NULL,
                    drops_enabled INTEGER DEFAULT 1
                )
            """)

            # Level Role Rewards
            await db.execute("""
                CREATE TABLE IF NOT EXISTS level_roles (
                    guild_id INTEGER,
                    level INTEGER,
                    role_id INTEGER,
                    PRIMARY KEY (guild_id, level)
                )
            """)

            # Daily Quests
            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_quests (
                    user_id INTEGER,
                    guild_id INTEGER,
                    date TEXT,
                    messages_count INTEGER DEFAULT 0,
                    trivia_done INTEGER DEFAULT 0,
                    farm_done INTEGER DEFAULT 0,
                    claimed INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id, date)
                )
            """)

            # Add stats, broadcast, and minigame customization columns if not present
            cols_to_add = [
                ("stat_category_id", "INTEGER DEFAULT NULL"),
                ("stat_members_channel_id", "INTEGER DEFAULT NULL"),
                ("stat_online_channel_id", "INTEGER DEFAULT NULL"),
                ("stat_goal_channel_id", "INTEGER DEFAULT NULL"),
                ("broadcast_channel_id", "INTEGER DEFAULT NULL"),
                ("drops_channel_id", "INTEGER DEFAULT NULL"),
                ("drop_interval_minutes", "INTEGER DEFAULT 60"),
                ("drop_min_coins", "INTEGER DEFAULT 75"),
                ("drop_max_coins", "INTEGER DEFAULT 200"),
                ("drop_min_xp", "INTEGER DEFAULT 40"),
                ("drop_max_xp", "INTEGER DEFAULT 100"),
                ("drop_spots", "INTEGER DEFAULT 3"),
                ("minigames_channel_id", "INTEGER DEFAULT NULL"),
                ("trivia_coins", "INTEGER DEFAULT 50"),
                ("trivia_xp", "INTEGER DEFAULT 35"),
                ("race_multiplier", "REAL DEFAULT 3.0"),
                ("levelup_channel_id", "INTEGER DEFAULT NULL"),
                ("levelup_enabled", "INTEGER DEFAULT 1"),
                ("last_drop_time", "INTEGER DEFAULT 0"),
            ]
            for col_name, col_type in cols_to_add:
                try:
                    await db.execute(f"ALTER TABLE server_settings ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass

            await db.commit()

    async def get_or_create_user(self, user_id: int, guild_id: int) -> Dict[str, Any]:
        """Retrieves a user profile or creates a new entry."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)

            # Create default new user
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, guild_id, coins) VALUES (?, ?, 100)",
                (user_id, guild_id)
            )
            await db.commit()

            async with db.execute(
                "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row)

    async def add_xp(self, user_id: int, guild_id: int, xp_amount: int) -> Tuple[int, int, bool]:
        """Adds XP and detects level-ups."""
        async with aiosqlite.connect(self.db_path) as db:
            await self.get_or_create_user(user_id, guild_id)
            async with db.execute(
                "SELECT xp, level FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                current_xp = row[0]
                current_lvl = row[1]

            new_xp = current_xp + xp_amount
            new_level = level_from_xp(new_xp)
            leveled_up = new_level > current_lvl

            now_ts = int(time.time())
            await db.execute(
                """
                UPDATE users 
                SET xp = ?, level = ?, last_message_ts = ? 
                WHERE user_id = ? AND guild_id = ?
                """,
                (new_xp, new_level, now_ts, user_id, guild_id)
            )
            await db.commit()
            return new_xp, new_level, leveled_up

    async def add_coins(self, user_id: int, guild_id: int, amount: int) -> int:
        """Adds/deducts coins and returns the updated balance."""
        async with aiosqlite.connect(self.db_path) as db:
            await self.get_or_create_user(user_id, guild_id)
            await db.execute(
                "UPDATE users SET coins = MAX(0, coins + ?) WHERE user_id = ? AND guild_id = ?",
                (amount, user_id, guild_id)
            )
            await db.commit()
            async with db.execute(
                "SELECT coins FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]

    async def claim_daily(self, user_id: int, guild_id: int) -> Dict[str, Any]:
        """Claims daily reward with streak tracking."""
        user = await self.get_or_create_user(user_id, guild_id)
        last_daily_str = user.get("last_daily")
        now = datetime.utcnow()
        today_date_str = now.strftime("%Y-%m-%d")

        if last_daily_str:
            last_date = datetime.strptime(last_daily_str, "%Y-%m-%d")
            diff_days = (now.date() - last_date.date()).days

            if diff_days == 0:
                midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                remaining = midnight - now
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                return {
                    "success": False,
                    "message": f"⏳ You have already claimed your daily reward today! Come back in **{hours}h {minutes}m**."
                }
            elif diff_days == 1:
                streak = user["daily_streak"] + 1
            else:
                streak = 1
        else:
            streak = 1

        coins_awarded = DAILY_BASE_REWARD + (streak * DAILY_STREAK_BONUS)
        xp_awarded = 50 + (streak * 10)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE users 
                SET coins = coins + ?, xp = xp + ?, daily_streak = ?, last_daily = ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (coins_awarded, xp_awarded, streak, today_date_str, user_id, guild_id)
            )
            await db.commit()

        return {
            "success": True,
            "streak": streak,
            "coins": coins_awarded,
            "xp": xp_awarded,
            "message": f"🎉 **Daily Reward Claimed!**\n\n🌾 **+{coins_awarded}** Agri-Coins\n⭐ **+{xp_awarded}** XP\n🔥 **Streak:** {streak} day(s)"
        }

    async def get_leaderboard(self, guild_id: int, sort_by: str = "xp", limit: int = 10) -> List[Dict[str, Any]]:
        """Fetches top users sorted by XP, coins, bumps, or counting."""
        valid_cols = {
            "xp": "xp DESC",
            "coins": "coins DESC",
            "bumps": "total_bumps DESC",
            "counting": "counting_contributions DESC"
        }
        order_clause = valid_cols.get(sort_by, "xp DESC")

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT user_id, xp, level, coins, total_bumps, counting_contributions FROM users WHERE guild_id = ? ORDER BY {order_clause} LIMIT ?",
                (guild_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    # --- Farm & Minigame Methods ---

    async def get_active_crops(self, user_id: int, guild_id: int) -> List[Dict[str, Any]]:
        """Retrieves active crops of a user."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM farms WHERE user_id = ? AND guild_id = ? ORDER BY harvest_at ASC",
                (user_id, guild_id)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def plant_crop(self, user_id: int, guild_id: int, crop_key: str) -> Tuple[bool, str]:
        """Plants a new crop on the user's field."""
        if crop_key not in CROPS:
            return False, "❌ Invalid crop selected."

        crop = CROPS[crop_key]
        user = await self.get_or_create_user(user_id, guild_id)

        active_crops = await self.get_active_crops(user_id, guild_id)
        if len(active_crops) >= 6:
            return False, "🚜 Your plots are full (maximum 6 active plots)! Harvest your ripe crops first with `/harvest`."

        if user["coins"] < crop["cost"]:
            return False, f"❌ You don't have enough Agri-Coins! {crop['name']} costs **{crop['cost']}** coins (your balance: {user['coins']})."

        now = int(time.time())
        harvest_at = now + crop["grow_time_seconds"]

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET coins = coins - ? WHERE user_id = ? AND guild_id = ?",
                (crop["cost"], user_id, guild_id)
            )
            await db.execute(
                """
                INSERT INTO farms (user_id, guild_id, crop_key, planted_at, harvest_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, guild_id, crop_key, now, harvest_at)
            )
            await db.commit()

        mins = crop["grow_time_seconds"] // 60
        secs = crop["grow_time_seconds"] % 60
        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        return True, f"🌱 You planted **{crop['name']}** for **{crop['cost']}** Agri-Coins!\n⏳ Growth time: **{time_str}**."

    async def harvest_crops(self, user_id: int, guild_id: int) -> Tuple[bool, str, int, int]:
        """Harvests all fully grown crops."""
        active_crops = await self.get_active_crops(user_id, guild_id)
        if not active_crops:
            return False, "🌾 You have no crops planted right now. Use `/plant` to start sowing!", 0, 0

        user = await self.get_or_create_user(user_id, guild_id)
        tractor_lvl = user.get("tractor_level", 1)
        multiplier = TRACTOR_UPGRADES.get(tractor_lvl, {"multiplier": 1.0})["multiplier"]

        now = int(time.time())
        ready_crops = [c for c in active_crops if c["harvest_at"] <= now]

        if not ready_crops:
            shortest_wait = min(c["harvest_at"] - now for c in active_crops)
            mins, secs = divmod(shortest_wait, 60)
            return False, f"⏳ Your crops are still growing! The next one will be ready in **{mins}m {secs}s**.", 0, 0

        total_coins = 0
        total_xp = 0
        harvest_summary = []
        ready_ids = []

        for crop_row in ready_crops:
            key = crop_row["crop_key"]
            crop_info = CROPS.get(key, {"name": key, "sell_price": 20, "xp": 10})
            earned_coins = int(crop_info["sell_price"] * multiplier)
            earned_xp = crop_info["xp"]

            total_coins += earned_coins
            total_xp += earned_xp
            harvest_summary.append(crop_info["name"])
            ready_ids.append(crop_row["id"])

        async with aiosqlite.connect(self.db_path) as db:
            placeholders = ",".join("?" for _ in ready_ids)
            await db.execute(f"DELETE FROM farms WHERE id IN ({placeholders})", ready_ids)
            await db.commit()

        await self.add_coins(user_id, guild_id, total_coins)
        await self.add_xp(user_id, guild_id, total_xp)

        msg = (
            f"🌾 **Harvest Successful!**\n\n"
            f"📦 **Harvested ({len(ready_crops)}x):** {', '.join(set(harvest_summary))}\n"
            f"💰 **Revenue:** +{total_coins} Agri-Coins (Machinery Bonus: x{multiplier})\n"
            f"⭐ **Experience:** +{total_xp} XP"
        )
        return True, msg, total_coins, total_xp

    async def upgrade_tractor(self, user_id: int, guild_id: int) -> Tuple[bool, str]:
        """Upgrades to the next tractor / harvester tier."""
        user = await self.get_or_create_user(user_id, guild_id)
        current_lvl = user.get("tractor_level", 1)
        next_lvl = current_lvl + 1

        if next_lvl not in TRACTOR_UPGRADES:
            return False, "🚜 You already own the ultimate machine of Agri Solutions Group! (**Agri-Titan Smart Harvester**)"

        upgrade_info = TRACTOR_UPGRADES[next_lvl]
        cost = upgrade_info["cost"]

        if user["coins"] < cost:
            return False, f"❌ You don't have enough coins! The **{upgrade_info['name']}** costs **{cost}** Agri-Coins (your balance: {user['coins']})."

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET coins = coins - ?, tractor_level = ? WHERE user_id = ? AND guild_id = ?",
                (cost, next_lvl, user_id, guild_id)
            )
            await db.commit()

        return True, f"🎉 **Upgrade Complete!**\nYou now own the **{upgrade_info['name']}**!\n🌾 New harvest bonus: **x{upgrade_info['multiplier']}** on all your crops!"

    # --- Server Settings / Counting / Bump Management ---

    async def get_server_settings(self, guild_id: int) -> Dict[str, Any]:
        """Retrieves server settings."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM server_settings WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)

            await db.execute(
                "INSERT INTO server_settings (guild_id) VALUES (?)",
                (guild_id,)
            )
            await db.commit()
            async with db.execute(
                "SELECT * FROM server_settings WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row)

    async def update_server_setting(self, guild_id: int, key: str, value: Any):
        """Updates a specific server_settings column."""
        async with aiosqlite.connect(self.db_path) as db:
            await self.get_server_settings(guild_id)
            await db.execute(
                f"UPDATE server_settings SET {key} = ? WHERE guild_id = ?",
                (value, guild_id)
            )
            await db.commit()

    async def process_count(self, guild_id: int, user_id: int, number: int) -> Dict[str, Any]:
        """Handles counting validation logic."""
        settings = await self.get_server_settings(guild_id)
        current = settings.get("current_count", 0)
        highest = settings.get("highest_count", 0)
        last_user = settings.get("last_counter_id")

        expected = current + 1

        # Check consecutive counting by same user
        if user_id == last_user and current > 0:
            new_highest = max(highest, current)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE server_settings SET current_count = 0, last_counter_id = NULL, highest_count = ? WHERE guild_id = ?",
                    (new_highest, guild_id)
                )
                await db.commit()
            return {
                "status": "DOUBLE_COUNT",
                "current_count": 0,
                "ruined_at": current,
                "highest_count": new_highest
            }

        # Check correct order
        if number != expected:
            new_highest = max(highest, current)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE server_settings SET current_count = 0, last_counter_id = NULL, highest_count = ? WHERE guild_id = ?",
                    (new_highest, guild_id)
                )
                await db.commit()
            return {
                "status": "WRONG_NUMBER",
                "expected": expected,
                "received": number,
                "ruined_at": current,
                "highest_count": new_highest
            }

        new_count = expected
        new_highest = max(highest, new_count)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE server_settings SET current_count = ?, last_counter_id = ?, highest_count = ? WHERE guild_id = ?",
                (new_count, user_id, new_highest, guild_id)
            )
            await db.execute(
                "UPDATE users SET counting_contributions = counting_contributions + 1, coins = coins + 2, xp = xp + 5 WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            await db.commit()

        milestone = new_count if (new_count % 50 == 0 or new_count in (10, 25, 69, 100, 420, 500, 1000)) else None

        return {
            "status": "CORRECT",
            "current_count": new_count,
            "highest_count": new_highest,
            "milestone": milestone
        }

    async def record_bump(self, user_id: int, guild_id: int, coins: int, xp: int) -> int:
        """Records a successful Disboard bump."""
        async with aiosqlite.connect(self.db_path) as db:
            await self.get_or_create_user(user_id, guild_id)
            await db.execute(
                """
                UPDATE users 
                SET total_bumps = total_bumps + 1, coins = coins + ?, xp = xp + ?
                WHERE user_id = ? AND guild_id = ?
                """,
                (coins, xp, user_id, guild_id)
            )
            await db.commit()

            async with db.execute(
                "SELECT total_bumps FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]

    async def get_due_bump_reminders(self) -> List[Dict[str, Any]]:
        """Fetches servers where the 2-hour bump cooldown has expired and no reminder was sent."""
        now = int(time.time())
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM server_settings WHERE next_bump_time > 0 AND next_bump_time <= ? AND bump_reminder_sent = 0",
                (now,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    # --- Level Roles & Daily Quests ---

    async def get_level_roles(self, guild_id: int) -> List[Dict[str, Any]]:
        """Gets all configured level-role rewards for a server."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM level_roles WHERE guild_id = ? ORDER BY level ASC",
                (guild_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def set_level_role(self, guild_id: int, level: int, role_id: int):
        """Maps a level requirement to a Discord role reward."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
                (guild_id, level, role_id)
            )
            await db.commit()

    async def delete_level_role(self, guild_id: int, level: int):
        """Removes a level role reward."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM level_roles WHERE guild_id = ? AND level = ?",
                (guild_id, level)
            )
            await db.commit()

    async def get_daily_quests(self, user_id: int, guild_id: int) -> Dict[str, Any]:
        """Gets or creates daily quests for a user."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM daily_quests WHERE user_id = ? AND guild_id = ? AND date = ?",
                (user_id, guild_id, today)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)

            # Insert default today
            await db.execute(
                "INSERT OR IGNORE INTO daily_quests (user_id, guild_id, date) VALUES (?, ?, ?)",
                (user_id, guild_id, today)
            )
            await db.commit()

            async with db.execute(
                "SELECT * FROM daily_quests WHERE user_id = ? AND guild_id = ? AND date = ?",
                (user_id, guild_id, today)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row)

    async def update_quest_progress(self, user_id: int, guild_id: int, quest_key: str, amount: int = 1):
        """Updates a specific daily quest counter."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        await self.get_daily_quests(user_id, guild_id)
        valid_keys = ["messages_count", "trivia_done", "farm_done"]
        if quest_key not in valid_keys:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE daily_quests SET {quest_key} = {quest_key} + ? WHERE user_id = ? AND guild_id = ? AND date = ?",
                (amount, user_id, guild_id, today)
            )
            await db.commit()

    async def claim_daily_quests(self, user_id: int, guild_id: int) -> Dict[str, Any]:
        """Claims bonus rewards for completing all 3 daily quests."""
        quests = await self.get_daily_quests(user_id, guild_id)
        if quests["claimed"] == 1:
            return {"success": False, "message": "❌ You have already claimed today's quest reward!"}

        is_complete = (
            quests["messages_count"] >= 5 and
            quests["trivia_done"] >= 1 and
            quests["farm_done"] >= 1
        )

        if not is_complete:
            return {
                "success": False,
                "message": (
                    "⏳ You haven't completed all daily quests yet!\n\n"
                    f"💬 **Chat in server:** `{min(5, quests['messages_count'])}/5`\n"
                    f"🧠 **Answer /trivia:** `{min(1, quests['trivia_done'])}/1`\n"
                    f"🌾 **Plant/Harvest /farm:** `{min(1, quests['farm_done'])}/1`"
                )
            }

        reward_coins = 200
        reward_xp = 150
        today = datetime.utcnow().strftime("%Y-%m-%d")

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE daily_quests SET claimed = 1 WHERE user_id = ? AND guild_id = ? AND date = ?",
                (user_id, guild_id, today)
            )
            await db.execute(
                "UPDATE users SET coins = coins + ?, xp = xp + ? WHERE user_id = ? AND guild_id = ?",
                (reward_coins, reward_xp, user_id, guild_id)
            )
            await db.commit()

        return {
            "success": True,
            "coins": reward_coins,
            "xp": reward_xp,
            "message": f"🎉 **Daily Quests Completed!**\n\n🌾 **+{reward_coins}** Agri-Coins\n⭐ **+{reward_xp}** XP"
        }
