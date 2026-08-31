# 🌾 Agri Solutions Group — Official Discord Bot

A custom-built, feature-rich Discord bot designed specifically for **Agri Solutions Group**. This bot maximizes community activity with agricultural minigames, an XP & Leveling system, an interactive Counting game, and an automated Disboard Bump Tracker & 2-Hour Reminder system.

---

## 🌟 Key Features

### 1. 🚜 Agri Minigames & Farmland Economy
* **`/farm`**: View your 6 plots of farmland, active crop timers, and machinery fleet.
* **`/plant`**: Sow crops (*Wheat*, *Carrots*, *Corn*, *Potatoes*) with distinct grow times, costs, and revenues.
* **`/harvest`**: Harvest all fully grown crops in one click for **Agri-Coins** and **XP**.
* **`/market`**: Live market prices for seeds and tractor upgrades.
* **`/upgrade`**: Upgrade your machinery (from *Old Hand Plow* to the *Agri-Titan Smart Harvester*) for up to **2.2x** harvest multiplier!
* **`/trivia`**: Interactive quiz with modern agriculture and precision farming questions with direct coin & XP rewards.
* **`/tractor-race`**: Wager on tractor brands (*John Deere*, *Claas*, *Fendt*, *New Holland*) in an animated race with 3x payout.
* **`/coinflip` & `/dice`**: Quick betting minigames.

### 2. 📈 Activity & Leveling System
* **XP per message**: Members earn XP automatically by chatting (protected by a 60-second anti-spam cooldown).
* **Agricultural Titles**: Titles that scale with level (from *🌱 Novice Farmer* to *👑 Agri Solutions Legend*).
* **`/rank`**: Visual farmer profile card with progress bars, coins, streaks, and statistics.
* **`/leaderboard`**: Live rankings for XP, Wealth (Coins), Disboard Bumps, and Counting Contributions.
* **`/daily`**: Daily login rewards with an increasing streak multiplier.
* **`/pay`**: Transfer Agri-Coins to other members.
* **Welcome Embeds**: Automatic welcome cards branded with the Agri Solutions Group logo for new members.

### 3. 🔢 Counting Minigame
* **Designated Counting Channel**: Members take turns counting upwards (`1, 2, 3...`).
* **Strict Validation**: Duplicate turns or wrong numbers reset the counter to 0 while keeping the server high score record.
* **Milestone Rewards**: Milestones (50, 100, 250, 500...) trigger bonus coins/XP and special star reactions (🌟).
* **`/setcounting`**: *(Admin)* Easily configure the counting channel.
* **`/countstats`**: View current progress and all-time record.

### 4. ⏰ Disboard Auto-Bump & Smart Reminder
* **Automatic Detection**: Detects when someone runs `/bump` with the Disboard bot.
* **Bumper Rewards**: Gives the promoter **+150 Agri-Coins** and **+100 XP** immediately.
* **2-Hour Timer**: Automatically starts a countdown and posts an attention-grabbing reminder ping (e.g. `@Bump Reminder`) after 2 hours.
* **`/bumpstatus`**: Check remaining cooldown.
* **`/bumpleaderboard`**: View top promoters.
* **`/setbumpchannel` & `/setbumprole`**: *(Admin)* Fully customizable reminder channel and ping role.

---

## 🚀 Setup & Hosting

### Step 1: Invite Bot
Invite the bot using this direct link:
👉 **[Click Here to Invite the Bot](https://discord.com/oauth2/authorize?client_id=1504039320904798258&permissions=8&scope=bot%20applications.commands)**

### Step 2: Configure `.env`
Ensure your `.env` contains your Discord Bot Token:
```env
DISCORD_TOKEN=your_token_here
```

### Step 3: Run the Bot
```bash
python main.py
```
