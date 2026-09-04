import discord
from discord import app_commands
from discord.ext import commands
import random
import time
import asyncio
from typing import Optional, List
from config import (
    COLOR_PRIMARY,
    COLOR_GOLD,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_ERROR,
    CROPS,
    TRACTOR_UPGRADES,
    create_embed
)

# Agricultural trivia question bank in English
TRIVIA_QUESTIONS = [
    {
        "question": "Which crop is primarily cultivated in temperate regions for commercial sugar production?",
        "options": ["Sugar Cane", "Sugar Beet", "Sweet Corn", "Potato"],
        "correct": 1,
        "explanation": "Sugar beet accounts for roughly 20-30% of global sugar production and grows well in cooler temperate zones."
    },
    {
        "question": "What is 'precision agriculture'?",
        "options": [
            "Hand-measuring every single leaf",
            "Using GPS, IoT sensors, and data analytics to optimize field-level crop management",
            "Farming without any modern machinery",
            "Only using organic animal fertilizers"
        ],
        "correct": 1,
        "explanation": "Precision agriculture uses GPS, satellite imagery, and telemetry to maximize yields while minimizing input waste."
    },
    {
        "question": "Which gas is commonly enriched in commercial greenhouses to accelerate plant photosynthesis?",
        "options": ["Oxygen (O2)", "Nitrogen (N2)", "Carbon Dioxide (CO2)", "Helium (He)"],
        "correct": 2,
        "explanation": "Plants utilize CO2 during photosynthesis; enriching greenhouse air with CO2 can increase crop growth and yields."
    },
    {
        "question": "What primary functions does a modern Combine Harvester perform in one operation?",
        "options": [
            "Only mowing grass",
            "Reaping, threshing, and winnowing grain crops",
            "Plowing and fertilizing soil",
            "Forestry logging"
        ],
        "correct": 1,
        "explanation": "The combine harvester combines reaping (cutting), threshing (separating grain), and cleaning (winnowing) into one pass."
    },
    {
        "question": "Which type of soil has the highest water and nutrient retention capacity?",
        "options": ["Sandy soil", "Clay soil", "Gravel soil", "Coarse silt"],
        "correct": 1,
        "explanation": "Clay soil consists of very fine particles with high surface area that retain moisture and mineral nutrients effectively."
    },
    {
        "question": "Why do farmers practice crop rotation between seasons?",
        "options": [
            "Purely for visual variety",
            "To prevent soil nutrient depletion and disrupt crop-specific pests & diseases",
            "To change the color of the soil",
            "By random seasonal choice"
        ],
        "correct": 1,
        "explanation": "Crop rotation preserves soil health, improves organic matter, and breaks pest and weed lifecycles."
    },
    {
        "question": "What is silage (ensiling) in livestock farming?",
        "options": [
            "Fermenting high-moisture forage crops (like grass or corn) under airtight conditions for livestock feed",
            "Washing dairy cattle before milking",
            "Injecting liquid manure into the subsoil",
            "Shearing sheep wool"
        ],
        "correct": 0,
        "explanation": "Silage is preserved green forage fermented by lactic acid bacteria in an anaerobic environment (silo/bale wrap)."
    }
]

async def enforce_minigames_channel(interaction: discord.Interaction, db) -> bool:
    """Checks if minigames are restricted to a specific channel."""
    if not interaction.guild or interaction.user.guild_permissions.administrator:
        return True
    settings = await db.get_server_settings(interaction.guild.id)
    mg_ch_id = settings.get("minigames_channel_id")
    if mg_ch_id and interaction.channel_id != mg_ch_id:
        await interaction.response.send_message(
            f"❌ Minigames are restricted to <#{mg_ch_id}>! Please head over there to play.",
            ephemeral=True
        )
        return False
    return True


class TriviaView(discord.ui.View):
    def __init__(self, question_data: dict, user_id: int, db, guild_id: int):
        super().__init__(timeout=25.0)
        self.question_data = question_data
        self.user_id = user_id
        self.db = db
        self.guild_id = guild_id
        self.answered = False

        for i, option in enumerate(question_data["options"]):
            btn = discord.ui.Button(
                label=option[:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"trivia_{i}"
            )
            btn.callback = self.make_callback(i)
            self.add_item(btn)

    def make_callback(self, index: int):
        async def button_callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ This is not your quiz question!", ephemeral=True)
                return

            if self.answered:
                return
            self.answered = True

            correct_idx = self.question_data["correct"]
            is_correct = (index == correct_idx)

            for btn in self.children:
                btn.disabled = True
                btn_idx = int(btn.custom_id.split("_")[1])
                if btn_idx == correct_idx:
                    btn.style = discord.ButtonStyle.success
                elif btn_idx == index and not is_correct:
                    btn.style = discord.ButtonStyle.danger

            # Update daily quest progress
            await self.db.update_quest_progress(self.user_id, self.guild_id, "trivia_done", 1)

            if is_correct:
                settings = await self.db.get_server_settings(self.guild_id)
                reward_coins = settings.get("trivia_coins", 50)
                reward_xp = settings.get("trivia_xp", 35)
                await self.db.add_coins(self.user_id, self.guild_id, reward_coins)
                await self.db.add_xp(self.user_id, self.guild_id, reward_xp)

                embed = discord.Embed(
                    title="✅ Correct Answer!",
                    description=(
                        f"**Question:** {self.question_data['question']}\n\n"
                        f"💡 **Explanation:** {self.question_data['explanation']}\n\n"
                        f"🎁 **Reward:** `+{reward_coins}` Agri-Coins & `+{reward_xp}` XP!"
                    ),
                    color=COLOR_SUCCESS
                )
            else:
                embed = discord.Embed(
                    title="❌ Incorrect!",
                    description=(
                        f"**Question:** {self.question_data['question']}\n\n"
                        f"The correct answer was: **{self.question_data['options'][correct_idx]}**\n\n"
                        f"💡 **Explanation:** {self.question_data['explanation']}"
                    ),
                    color=COLOR_ERROR
                )

            embed.set_footer(text="Agri Solutions Group Quiz")
            await interaction.response.edit_message(embed=embed, view=self)

        return button_callback

    async def on_timeout(self):
        for btn in self.children:
            btn.disabled = True


class Minigames(commands.Cog):
    """Agri Minigames: Farm Tycoon, Trivia, Tractor Races & Betting."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    # --- 🌾 FARM TYCOON ---

    @app_commands.command(name="farm", description="View your farm plots, growing crops, and machinery fleet.")
    async def farm_command(self, interaction: discord.Interaction):
        if not await enforce_minigames_channel(interaction, self.db):
            return

        user_id = interaction.user.id
        guild_id = interaction.guild.id

        user = await self.db.get_or_create_user(user_id, guild_id)
        crops = await self.db.get_active_crops(user_id, guild_id)
        tractor_info = TRACTOR_UPGRADES.get(user.get("tractor_level", 1), TRACTOR_UPGRADES[1])

        embed = discord.Embed(
            title=f"🚜 The Farm of {interaction.user.display_name}",
            description="Welcome to your fields! Plant crops with `/plant` and harvest with `/harvest`.",
            color=COLOR_PRIMARY
        )

        embed.add_field(
            name="🚜 Machinery Fleet",
            value=f"**{tractor_info['name']}** (Yield Multiplier: `x{tractor_info['multiplier']}`)",
            inline=False
        )

        embed.add_field(
            name="💰 Coin Balance",
            value=f"**{user['coins']:,}** Agri-Coins",
            inline=True
        )

        now = int(time.time())
        plots_text = []

        if not crops:
            plots_text.append("*All 6 plots are empty! Use `/plant` to start sowing.*")
        else:
            for i, c in enumerate(crops, 1):
                crop_data = CROPS.get(c["crop_key"], {"name": c["crop_key"]})
                if c["harvest_at"] <= now:
                    plots_text.append(f"• **Plot {i}:** {crop_data['name']} — 🟢 **Ready to Harvest!** (`/harvest`)")
                else:
                    remaining = c["harvest_at"] - now
                    m, s = divmod(remaining, 60)
                    plots_text.append(f"• **Plot {i}:** {crop_data['name']} — ⏳ *Growing ({m}m {s}s)*")

        embed.add_field(
            name=f"🌾 Plots ({len(crops)}/6 Occupied)",
            value="\n".join(plots_text),
            inline=False
        )

        embed.set_footer(text="Agri Solutions Group • Upgrade your tractor with /upgrade")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="plant", description="Sow a crop on your farmland.")
    @app_commands.describe(crop="Choose the crop you want to plant")
    @app_commands.choices(crop=[
        app_commands.Choice(name="🌾 Wheat (Cost: 10 | Grow time: 1m | Value: 25)", value="wheat"),
        app_commands.Choice(name="🥕 Carrots (Cost: 25 | Grow time: 3m | Value: 60)", value="carrot"),
        app_commands.Choice(name="🌽 Corn (Cost: 60 | Grow time: 6m | Value: 160)", value="corn"),
        app_commands.Choice(name="🥔 Potatoes (Cost: 120 | Grow time: 10m | Value: 320)", value="potato")
    ])
    async def plant_command(self, interaction: discord.Interaction, crop: app_commands.Choice[str]):
        if not await enforce_minigames_channel(interaction, self.db):
            return

        success, message = await self.db.plant_crop(interaction.user.id, interaction.guild.id, crop.value)

        if success:
            await self.db.update_quest_progress(interaction.user.id, interaction.guild.id, "farm_done", 1)

        color = COLOR_SUCCESS if success else COLOR_ERROR
        embed = create_embed(
            title="🌱 Farmland Update",
            description=message,
            color=color
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="harvest", description="Harvest all ripe crops for Agri-Coins and XP.")
    async def harvest_command(self, interaction: discord.Interaction):
        if not await enforce_minigames_channel(interaction, self.db):
            return

        success, message, coins, xp = await self.db.harvest_crops(interaction.user.id, interaction.guild.id)

        if success:
            await self.db.update_quest_progress(interaction.user.id, interaction.guild.id, "farm_done", 1)

        color = COLOR_SUCCESS if success else COLOR_WARNING
        embed = create_embed(
            title="🌾 Harvest Time!",
            description=message,
            color=color
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="market", description="Check market prices for crops and machinery upgrades.")
    async def market_command(self, interaction: discord.Interaction):
        if not await enforce_minigames_channel(interaction, self.db):
            return

        embed = discord.Embed(
            title="🛒 Agri Solutions Group — Market & Prices",
            description="Overview of seed purchase costs, grow times, sell prices, and tractor upgrades.",
            color=COLOR_GOLD
        )

        crop_lines = []
        for key, info in CROPS.items():
            mins = info["grow_time_seconds"] // 60
            crop_lines.append(f"• **{info['name']}**\n  Cost: `{info['cost']}` 🪙 | Sell: `{info['sell_price']}` 🪙 | Time: `{mins}m` | XP: `+{info['xp']}`")

        embed.add_field(name="🌱 Available Crops", value="\n".join(crop_lines), inline=False)

        tractor_lines = []
        for lvl, info in TRACTOR_UPGRADES.items():
            cost_str = f"`{info['cost']}` 🪙" if info["cost"] > 0 else "*Starter model*"
            tractor_lines.append(f"• **Lvl {lvl} — {info['name']}**\n  Multiplier: `x{info['multiplier']}` | Cost: {cost_str}")

        embed.add_field(name="🚜 Machinery Upgrades", value="\n".join(tractor_lines), inline=False)
        embed.set_footer(text="Use /upgrade to purchase your next machine tier!")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="upgrade", description="Upgrade your tractor for higher harvest yield multipliers.")
    async def upgrade_command(self, interaction: discord.Interaction):
        if not await enforce_minigames_channel(interaction, self.db):
            return

        success, message = await self.db.upgrade_tractor(interaction.user.id, interaction.guild.id)

        color = COLOR_SUCCESS if success else COLOR_ERROR
        embed = create_embed(
            title="🚜 Machinery Upgrade",
            description=message,
            color=color
        )
        await interaction.response.send_message(embed=embed)

    # --- 🧠 TRIVIA ---

    @app_commands.command(name="trivia", description="Play the agricultural trivia quiz for coins and XP!")
    async def trivia_command(self, interaction: discord.Interaction):
        if not await enforce_minigames_channel(interaction, self.db):
            return

        q_data = random.choice(TRIVIA_QUESTIONS)
        view = TriviaView(q_data, interaction.user.id, self.db, interaction.guild.id)

        embed = discord.Embed(
            title="🧠 Agri Solutions Trivia Quiz",
            description=f"**Question:**\n### {q_data['question']}\n\n*Select the correct answer within 25 seconds:*",
            color=COLOR_PRIMARY
        )
        embed.set_footer(text="Agri Trivia • Test your agriculture knowledge!")
        await interaction.response.send_message(embed=embed, view=view)

    # --- 🚜 TRACTOR RACE ---

    @app_commands.command(name="tractor-race", description="Bet on an exhilarating tractor race!")
    @app_commands.describe(
        bet="Amount of Agri-Coins to wager",
        tractor="Choose your champion tractor brand"
    )
    @app_commands.choices(tractor=[
        app_commands.Choice(name="🟢 John Deere Green Machine", value="John Deere"),
        app_commands.Choice(name="⚪ Claas Lexion Turbo", value="Claas"),
        app_commands.Choice(name="🟤 Fendt Vario Power", value="Fendt"),
        app_commands.Choice(name="🔵 New Holland Blue Beast", value="New Holland")
    ])
    async def tractor_race_command(self, interaction: discord.Interaction, bet: int, tractor: app_commands.Choice[str]):
        if not await enforce_minigames_channel(interaction, self.db):
            return

        if bet <= 0:
            await interaction.response.send_message("❌ Bet amount must be at least 1 Agri-Coin.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user = await self.db.get_or_create_user(interaction.user.id, guild_id)

        if user["coins"] < bet:
            await interaction.response.send_message(f"❌ You only have **{user['coins']}** Agri-Coins.", ephemeral=True)
            return

        await self.db.add_coins(interaction.user.id, guild_id, -bet)

        racers = ["John Deere", "Claas", "Fendt", "New Holland"]
        chosen = tractor.value

        embed = discord.Embed(
            title="🏁 THE GREAT AGRI TRACTOR RACE! 🚜",
            description=(
                f"🚩 **Your Choice:** `{chosen}` (Wager: **{bet}** 🪙)\n\n"
                f"3... 2... 1... **GO!** 💨\n\n"
                f"🟢 John Deere: 🚜💨 `[░░░░░░░░░░]`\n"
                f"⚪ Claas:      🚜💨 `[░░░░░░░░░░]`\n"
                f"🟤 Fendt:      🚜💨 `[░░░░░░░░░░]`\n"
                f"🔵 New Holland:🚜💨 `[░░░░░░░░░░]`"
            ),
            color=COLOR_GOLD
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(2)

        winner = random.choice(racers)
        user_won = (winner == chosen)

        if user_won:
            settings = await self.db.get_server_settings(guild_id)
            race_mult = settings.get("race_multiplier", 3.0)
            winnings = int(bet * race_mult)
            await self.db.add_coins(interaction.user.id, guild_id, winnings)
            await self.db.add_xp(interaction.user.id, guild_id, 40)
            result_text = f"🏆 **VICTORY!** Your **{chosen}** crossed the finish line first!\n💰 Payout: **+{winnings:,}** Agri-Coins ({race_mult}x multiplier)!"
            result_color = COLOR_SUCCESS
        else:
            result_text = f"💥 **Defeat!** The winner is **{winner}**!\nYour **{chosen}** came up just short. Better luck next time!"
            result_color = COLOR_ERROR

        final_embed = discord.Embed(
            title="🏁 FINISH! — The Great Agri Tractor Race",
            description=(
                f"🥇 **Winner:** `{winner}` 🚜💨\n\n"
                f"{result_text}"
            ),
            color=result_color
        )
        await interaction.edit_original_response(embed=final_embed)

    # --- 🪙 COINFLIP & DICE ---

    @app_commands.command(name="coinflip", description="Flip a coin for heads or tails.")
    @app_commands.describe(bet="Amount of Agri-Coins", choice="Choose Heads or Tails")
    @app_commands.choices(choice=[
        app_commands.Choice(name="👑 Heads", value="heads"),
        app_commands.Choice(name="🪙 Tails", value="tails")
    ])
    async def coinflip_command(self, interaction: discord.Interaction, bet: int, choice: app_commands.Choice[str]):
        if not await enforce_minigames_channel(interaction, self.db):
            return

        if bet <= 0:
            await interaction.response.send_message("❌ Bet amount must be at least 1 Agri-Coin.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user = await self.db.get_or_create_user(interaction.user.id, guild_id)

        if user["coins"] < bet:
            await interaction.response.send_message(f"❌ You only have **{user['coins']}** Agri-Coins.", ephemeral=True)
            return

        outcome = random.choice(["heads", "tails"])
        won = (outcome == choice.value)

        if won:
            await self.db.add_coins(interaction.user.id, guild_id, bet)
            embed = create_embed(
                title="🪙 Coinflip — Winner!",
                description=f"The coin landed on **{outcome.upper()}**!\n🎉 You won **+{bet:,}** Agri-Coins!",
                color=COLOR_SUCCESS
            )
        else:
            await self.db.add_coins(interaction.user.id, guild_id, -bet)
            embed = create_embed(
                title="🪙 Coinflip — Lost!",
                description=f"The coin landed on **{outcome.upper()}**.\n😢 You lost **{bet:,}** Agri-Coins.",
                color=COLOR_ERROR
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dice", description="Roll a 6-sided die for 5x your bet!")
    @app_commands.describe(bet="Amount of Agri-Coins", number="Pick a number from 1 to 6")
    async def dice_command(self, interaction: discord.Interaction, bet: int, number: int):
        if not await enforce_minigames_channel(interaction, self.db):
            return
        if bet <= 0:
            await interaction.response.send_message("❌ Bet amount must be at least 1 Agri-Coin.", ephemeral=True)
            return
        if number < 1 or number > 6:
            await interaction.response.send_message("❌ Please choose a number between 1 and 6.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        user = await self.db.get_or_create_user(interaction.user.id, guild_id)

        if user["coins"] < bet:
            await interaction.response.send_message(f"❌ You only have **{user['coins']}** Agri-Coins.", ephemeral=True)
            return

        rolled = random.randint(1, 6)
        dice_emojis = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

        if rolled == number:
            winnings = bet * 5
            await self.db.add_coins(interaction.user.id, guild_id, winnings)
            embed = create_embed(
                title=f"🎲 Dice: {dice_emojis[rolled]} ({rolled}) — JACKPOT!",
                description=f"Incredible guess! The die rolled exact **{rolled}**!\n🎉 You won **+{winnings:,}** Agri-Coins (5x payout)!",
                color=COLOR_SUCCESS
            )
        else:
            await self.db.add_coins(interaction.user.id, guild_id, -bet)
            embed = create_embed(
                title=f"🎲 Dice: {dice_emojis[rolled]} ({rolled}) — Bad Luck!",
                description=f"You chose **{number}**, but the die rolled **{rolled}**.\n😢 You lost **{bet:,}** Agri-Coins.",
                color=COLOR_ERROR
            )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Minigames(bot))
