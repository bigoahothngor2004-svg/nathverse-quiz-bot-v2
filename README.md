# NathVerse Telegram Quiz Bot 🌌

A production-ready Telegram quiz bot built with Python, `python-telegram-bot` (v20+ async), `APScheduler`, and `sqlite3`.

---

## 🌟 Key Features

1. **Scheduled Batch Broadcasts:**
   - Automatically checks for queued unposted quiz batches every **720 minutes** (12 hours) via `AsyncIOScheduler`.
   - Posts a batch banner to your channel, followed by each question individually with interactive inline answer buttons (`ans:<q_id>:<option>`).
   - Automatically marks batches as posted to prevent duplicate broadcasts.

2. **Progressive 24-Hour Cooldown Engine:**
   - Evaluates all attempts made by the user within the rolling past 24 hours:
     - **1st Attempt:** Immediate (0s wait)
     - **2nd Attempt:** 1-Hour Cooldown (3,600s after 1st attempt)
     - **3rd Attempt:** 6-Hour Cooldown (21,600s after 2nd attempt)
     - **4th+ Attempts:** 24-Hour Cooldown (86,400s after previous attempts)
   - When cooldown is active, the bot displays an instant Telegram modal alert (`show_alert=True`) showing exact remaining hours, minutes, and seconds.

3. **Robust Scoring System:**
   - **Correct Answer:** `+3 points` (Alert: `✅ Correct! +3 points added.`)
   - **Incorrect Answer:** `-1 point` with points floored at `0` (Alert: `❌ Incorrect! (Correct answer was {correct_option})\n\n💡 Explanation:\n{explanation}\n\n-1 point applied.`)
   - Prevents duplicate answers on the same question.

4. **Admin JSON Quiz Batch Upload:**
   - Restricted to Telegram User IDs configured in `ADMIN_IDS`.
   - Upload any `.json` file containing question batches. The bot validates schema, types, and values, then imports into SQLite.
   - Includes `/postbatch` command to immediately broadcast queued batches without waiting 720 minutes.

5. **Live Top 5 Leaderboard & Player Stats:**
   - `/leaderboard`: Displays top 5 players ranked by Points, Questions Attempted, and Accuracy %.
   - `/stats` (or `/me`): Shows individual user score, rank, attempted questions, accuracy, and live cooldown readiness.

---

## 📁 Project Structure

```text
├── bot.py             # Telegram handlers, APScheduler, callback router, entry point
├── database.py        # SQLite schema, WAL mode, lock handling, progressive cooldowns, scoring
├── requirements.txt   # python-telegram-bot>=20.8, apscheduler>=3.10.4, python-dotenv>=1.0.1
├── Dockerfile         # python:3.11-slim container with persistent volume at /app/data
├── .env.example       # Configuration template (BOT_TOKEN, CHANNEL_ID, ADMIN_IDS, DATA_DIR)
├── sample_batch.json  # Ready-to-upload example quiz batch
└── test_suite.py      # Complete automated test suite
```

---

## 🚀 Quick Start with Docker (Recommended)

1. **Clone repository and configure `.env`:**
   ```bash
   cp .env.example .env
   ```
   Fill in your parameters:
   - `BOT_TOKEN`: From [@BotFather](https://t.me/BotFather)
   - `CHANNEL_ID`: Channel username (e.g. `@my_quiz_channel`) or numeric ID
   - `ADMIN_IDS`: Comma-separated user IDs (e.g. `12345678,98765432`)
   - `DATA_DIR`: Defaults to `data`

2. **Build and run the container:**
   ```bash
   # Build the image
   docker build -t nathverse-bot .

   # Run with persistent volume mount for SQLite
   docker run -d \
     --name nathverse-bot \
     --restart unless-stopped \
     --env-file .env \
     -v $(pwd)/data:/app/data \
     nathverse-bot
   ```

3. **Check logs:**
   ```bash
   docker logs -f nathverse-bot
   ```

---

## 💻 Manual Setup (Virtualenv)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the test suite
python3 test_suite.py

# Launch the bot
python3 bot.py
```

---

## 📋 Quiz Batch JSON Schema

Admins can upload `.json` files directly to the bot chat:

```json
{
  "batch_number": 1,
  "title": "Math: Mixed Practical Word Problems I",
  "questions": [
    {
      "text": "If 6 shirts and 5 pants cost $120, and 5 shirts and 5 pants cost $90, how much does 1 shirt cost?",
      "options": ["$15", "$30", "$25", "$20"],
      "answer": "B",
      "explanation": "Because 6 shirts - 5 shirts = 1 shirt, and $120 - $90 = $30."
    }
  ]
}
```

---

## 🤖 Telegram Commands

### User Commands
- `/start` - Introduction, point system, cooldown rules, command list.
- `/leaderboard` - Top 5 ranked players (Points, Attempted, Accuracy %).
- `/stats` (or `/me`) - Personal score, accuracy, rank, and cooldown countdown.
- `/help` - Rules and gameplay walkthrough.

### Admin Commands (Restricted to `ADMIN_IDS`)
- `/addquiz` - Upload guidelines and JSON schema template.
- `/postbatch` - Immediately broadcast the next queued batch to the channel.
- `/status` - Current statistics (registered players, attempts, queued batches).
