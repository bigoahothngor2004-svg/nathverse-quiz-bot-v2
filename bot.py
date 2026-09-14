"""
NathVerse Quiz Bot - Main Application Entry Point
Production-ready Telegram quiz bot built with python-telegram-bot (v20+ async),
APScheduler, and SQLite.

Features:
- Progressive 24h cooldown policy (Immediate -> 1h -> 6h -> 24h)
- Scoring (+3 for correct, -1 for wrong, floor at 0)
- Scheduled 720-minute batch channel broadcasts
- JSON quiz batch upload & validation for admins
- Interactive inline buttons with instant modal feedback
- Real-time Top 5 Leaderboard & personal stats
"""

import os
import json
import logging
import asyncio
from typing import Set, Tuple, Dict, Any, List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from telegram import (
        Update,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
    )
    from telegram.constants import ParseMode
    from telegram.ext import (
        Application,
        CommandHandler,
        CallbackQueryHandler,
        MessageHandler,
        ContextTypes,
        filters,
    )
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    Update = Any  # type: ignore
    class _ContextTypesMock:
        DEFAULT_TYPE = Any
    ContextTypes = _ContextTypesMock  # type: ignore
    Application = Any  # type: ignore
    ParseMode = Any  # type: ignore
    InlineKeyboardButton = Any  # type: ignore
    InlineKeyboardMarkup = Any  # type: ignore
    AsyncIOScheduler = Any  # type: ignore
    IntervalTrigger = Any  # type: ignore
    filters = Any  # type: ignore

import database

# Load environment variables
if "load_dotenv" in globals():
    load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("NathVerseBot")

# Environment configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
ADMIN_IDS_RAW = os.environ.get("ADMIN_IDS", "").strip()
BROADCAST_INTERVAL_MINUTES = int(os.environ.get("BROADCAST_INTERVAL_MINUTES", "720"))

# Parse admin IDs
ADMIN_IDS: Set[int] = set()
if ADMIN_IDS_RAW:
    for raw_id in ADMIN_IDS_RAW.split(","):
        clean_id = raw_id.strip()
        if clean_id.isdigit():
            ADMIN_IDS.add(int(clean_id))

# Initialize scheduler if apscheduler is present
scheduler = AsyncIOScheduler(timezone="UTC") if HAS_TELEGRAM else None


def is_admin(user_id: int) -> bool:
    """Checks whether a user ID belongs to the authorized admin list."""
    return user_id in ADMIN_IDS


def format_seconds(seconds: int) -> str:
    """Formats seconds into human-readable hours, minutes, and seconds."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts) if parts else "0s"


# ==========================================
# USER COMMAND HANDLERS
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start command: Displays welcome overview, scoring rules, cooldown policies,
    and available commands.
    """
    if not update.effective_message:
        return

    user = update.effective_user
    username = user.first_name if user else "Learner"

    welcome_text = (
        f"👋 *Welcome to NathVerse, {username}!* 🌌\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Test your intellect in our scheduled quiz batches, compete on the leaderboard, "
        f"and earn points with precision!\n\n"
        f"🏆 *Scoring System:*\n"
        f"• ✅ *Correct Answer*: `+3 points`\n"
        f"• ❌ *Incorrect Answer*: `-1 point` (Floor: 0 points)\n\n"
        f"⏳ *Progressive Cooldown Policy (Past 24 Hours):*\n"
        f"To reward thoughtful answers and prevent spamming:\n"
        f"• 1st Attempt: *Immediate* (No wait)\n"
        f"• 2nd Attempt: *1-Hour Cooldown*\n"
        f"• 3rd Attempt: *6-Hour Cooldown*\n"
        f"• 4th+ Attempts: *24-Hour Cooldown*\n\n"
        f"📜 *Commands:*\n"
        f"• /leaderboard — View Top 5 ranked players\n"
        f"• /stats (or /me) — View your personal score & cooldown timer\n"
        f"• /help — Full rulebook and guidelines\n"
    )

    if user and is_admin(user.id):
        welcome_text += (
            f"\n🛡️ *Admin Commands:*\n"
            f"• /addquiz — Instructions for uploading new quiz JSON\n"
            f"• /postbatch — Broadcast the next queued batch immediately\n"
            f"• /status — View queue and database statistics\n"
        )

    await update.effective_message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /help command: Explains bot mechanics, progressive cooldowns, and channel broadcast schedules.
    """
    if not update.effective_message:
        return

    help_text = (
        f"📖 *NathVerse Quiz Guide & Rulebook*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"1. *Batch Broadcasts:*\n"
        f"Every *720 minutes* (12 hours), a new quiz batch is automatically broadcast to the official channel.\n\n"
        f"2. *How to Play:*\n"
        f"Tap any answer button directly under the question in the channel. An alert popup will reveal "
        f"if you are correct, show your point delta, and supply detailed explanations for wrong answers.\n\n"
        f"3. *Progressive Cooldown:*\n"
        f"Your attempts in the last 24 hours determine your wait time before your next answer:\n"
        f"• Attempt 1: Instant\n"
        f"• Attempt 2: 1h wait after attempt 1\n"
        f"• Attempt 3: 6h wait after attempt 2\n"
        f"• Attempt 4+: 24h wait\n\n"
        f"4. *Leaderboard:*\n"
        f"Rankings are decided by *Total Points*, then by *Correct Answers*, then by *Accuracy %*.\n"
    )
    await update.effective_message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /leaderboard command: Fetches and displays the top 5 users (Points, Questions Attempted, Accuracy %).
    """
    if not update.effective_message:
        return

    leaderboard = database.get_leaderboard(limit=5)
    if not leaderboard:
        await update.effective_message.reply_text(
            "🏆 *NathVerse Leaderboard*\n\n"
            "No recorded scores yet! Be the first to answer a question when the next batch drops.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = [
        "🏆 *NathVerse Leaderboard — Top 5*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]

    for idx, user in enumerate(leaderboard):
        medal = medals[idx] if idx < len(medals) else f"{idx + 1}."
        raw_name = user["username"]
        # Format username cleanly
        if raw_name.startswith("@"):
            clean_name = raw_name
        elif " " in raw_name or raw_name.startswith("User_") or raw_name.startswith("Player "):
            clean_name = raw_name
        else:
            clean_name = f"@{raw_name}"

        points = user["points"]
        attempted = user["questions_attempted"]
        accuracy = user["accuracy"]

        lines.append(
            f"{medal} *{clean_name}*\n"
            f"   ⭐ *Points:* `{points}` | 🎯 *Attempted:* `{attempted}` | 📈 *Accuracy:* `{accuracy}%`"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━\n_Answer accurately to climb the leaderboard!_")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /stats or /me command: Shows individual user profile stats, rank, and cooldown status.
    """
    if not update.effective_message or not update.effective_user:
        return

    user = update.effective_user
    user_id = user.id
    user_stats = database.get_user_stats(user_id)

    # Check cooldown status
    is_cd, rem_seconds, formatted_cd = database.check_cooldown(user_id)
    if is_cd:
        cd_status = f"⏳ *Cooldown Active* — Available in `{formatted_cd}`"
    else:
        cd_status = "🟢 *Ready* — You can answer immediately!"

    if not user_stats:
        text = (
            f"👤 *Your NathVerse Profile* ({user.first_name})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⭐ *Points:* `0`\n"
            f"🎯 *Questions Attempted:* `0`\n"
            f"✅ *Correct Answers:* `0`\n"
            f"📈 *Accuracy:* `0.0%`\n"
            f"🏅 *Current Rank:* `Unranked`\n\n"
            f"⚡ *Status:* {cd_status}\n\n"
            f"_Participate in the quiz broadcasts to earn points!_"
        )
    else:
        text = (
            f"👤 *Your NathVerse Profile* ({user_stats['username']})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⭐ *Points:* `{user_stats['points']}`\n"
            f"🎯 *Questions Attempted:* `{user_stats['questions_attempted']}`\n"
            f"✅ *Correct Answers:* `{user_stats['correct_answers']}`\n"
            f"📈 *Accuracy:* `{user_stats['accuracy']}%`\n"
            f"🏅 *Current Rank:* `#{user_stats['rank']}`\n\n"
            f"⚡ *Status:* {cd_status}"
        )

    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# ADMIN COMMANDS & QUIZ UPLOAD
# ==========================================

async def addquiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /addquiz command (Admin only): Guides the admin on how to upload a batch JSON file.
    """
    if not update.effective_message or not update.effective_user:
        return

    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("⛔ *Access Denied:* Only authorized administrators can add quiz batches.", parse_mode=ParseMode.MARKDOWN)
        return

    sample_json = json.dumps({
        "batch_number": 1,
        "title": "Math: Mixed Practical Word Problems I",
        "questions": [
            {
                "text": "If a car travels 60 miles in 1 hour and 30 minutes, what is its average speed in mph?",
                "options": ["30 mph", "40 mph", "45 mph", "50 mph"],
                "answer": "B",
                "explanation": "Average speed = Distance / Time = 60 miles / 1.5 hours = 40 mph."
            }
        ]
    }, indent=2)

    instructions = (
        f"🛠️ *Admin Quiz Batch Upload*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"To add a new quiz batch, simply *upload a `.json` document* directly to this chat.\n\n"
        f"📋 *Required JSON Format:*\n"
        f"```json\n{sample_json}\n```\n\n"
        f"💡 *Notes:*\n"
        f"• `batch_number`: Unique positive integer.\n"
        f"• `options`: List of choice strings (e.g. ['A', 'B', 'C', 'D'] or text choices).\n"
        f"• `answer`: The correct option (e.g. 'A', 'B', 'C', or 'D').\n"
        f"• `explanation`: Detailed walkthrough displayed if the user gets the question wrong.\n"
    )
    await update.effective_message.reply_text(instructions, parse_mode=ParseMode.MARKDOWN)


def validate_batch_data(data: Any) -> Tuple[bool, str]:
    """
    Validates the structure, types, and values of the uploaded quiz batch JSON.
    """
    if not isinstance(data, dict):
        return False, "Root JSON element must be an object with keys 'batch_number', 'title', and 'questions'."

    batch_number = data.get("batch_number")
    if not isinstance(batch_number, int) or batch_number <= 0:
        return False, "Field 'batch_number' must be a positive integer."

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return False, "Field 'title' must be a non-empty string."

    questions = data.get("questions")
    if not isinstance(questions, list) or len(questions) == 0:
        return False, "Field 'questions' must be a non-empty list of questions."

    for idx, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            return False, f"Question #{idx} must be a JSON object."

        text = q.get("text")
        if not isinstance(text, str) or not text.strip():
            return False, f"Question #{idx}: 'text' must be a non-empty string."

        options = q.get("options")
        if not isinstance(options, list) or len(options) < 2:
            return False, f"Question #{idx}: 'options' must be a list of at least 2 choices."

        for opt_idx, opt in enumerate(options, start=1):
            if not isinstance(opt, (str, int, float)):
                return False, f"Question #{idx}, Option #{opt_idx} must be a string or number."

        answer = q.get("answer")
        if not isinstance(answer, (str, int)) or not str(answer).strip():
            return False, f"Question #{idx}: 'answer' must specify the correct option."

        explanation = q.get("explanation")
        if not isinstance(explanation, str) or not explanation.strip():
            return False, f"Question #{idx}: 'explanation' must be a non-empty string."

    return True, "Valid"


async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles file uploads sent by administrators. Validates `.json` quiz batches
    and stores them into the SQLite database.
    """
    if not update.effective_message or not update.effective_user:
        return

    user_id = update.effective_user.id
    if not is_admin(user_id):
        # Ignore non-admin file uploads
        return

    doc = update.effective_message.document
    if not doc:
        return

    file_name = doc.file_name or ""
    if not file_name.lower().endswith(".json"):
        await update.effective_message.reply_text(
            "⚠️ *Invalid File Type:* Please upload a `.json` file.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Download file with error handling
    try:
        telegram_file = await context.bot.get_file(doc.file_id)
        byte_array = await telegram_file.download_as_bytearray()
        content_str = byte_array.decode("utf-8")
        json_data = json.loads(content_str)
    except json.JSONDecodeError as jde:
        logger.error(f"JSON decode failure: {jde}")
        await update.effective_message.reply_text(
            f"❌ *JSON Parsing Error:*\nYour file contains invalid JSON syntax:\n`{str(jde)[:200]}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    except Exception as e:
        logger.error(f"File download or decoding failure: {e}", exc_info=True)
        await update.effective_message.reply_text(
            f"❌ *Download Error:* Could not read the uploaded file: `{str(e)}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Validate JSON structure
    is_valid, err_msg = validate_batch_data(json_data)
    if not is_valid:
        await update.effective_message.reply_text(
            f"❌ *Validation Failed:*\n{err_msg}",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    batch_num = json_data["batch_number"]
    title = json_data["title"].strip()
    questions = json_data["questions"]

    # Insert into database
    try:
        inserted = database.insert_quiz_batch(batch_num, title, questions)
        await update.effective_message.reply_text(
            f"✅ *Quiz Batch #{batch_num} Successfully Saved!*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📚 *Title:* {title}\n"
            f"📝 *Questions Loaded:* `{inserted}`\n"
            f"📡 *Status:* Queued for scheduled broadcast (or trigger immediately using `/postbatch`).",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Database insertion error: {e}", exc_info=True)
        await update.effective_message.reply_text(
            f"❌ *Database Error:* Could not store quiz batch:\n`{str(e)}`",
            parse_mode=ParseMode.MARKDOWN
        )


async def postbatch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /postbatch command (Admin only): Manually triggers broadcasting the next queued batch.
    """
    if not update.effective_message or not update.effective_user:
        return

    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("⛔ *Access Denied:* Admin only.", parse_mode=ParseMode.MARKDOWN)
        return

    if not CHANNEL_ID:
        await update.effective_message.reply_text("⚠️ `CHANNEL_ID` is not configured in your `.env`.", parse_mode=ParseMode.MARKDOWN)
        return

    status_msg = await update.effective_message.reply_text("⏳ *Broadcasting next batch to channel...*", parse_mode=ParseMode.MARKDOWN)
    success, msg = await broadcast_next_batch(context.application)
    if success:
        await status_msg.edit_text(f"✅ *Broadcast Complete!*\n{msg}", parse_mode=ParseMode.MARKDOWN)
    else:
        await status_msg.edit_text(f"⚠️ *Broadcast Status:*\n{msg}", parse_mode=ParseMode.MARKDOWN)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /status command (Admin only): Displays queue, user, and attempt stats.
    """
    if not update.effective_message or not update.effective_user:
        return

    if not is_admin(update.effective_user.id):
        return

    stats = database.get_system_stats()
    text = (
        f"📊 *NathVerse System Status*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 *Total Registered Players:* `{stats['total_users']}`\n"
        f"🎯 *Total Attempts Logged:* `{stats['total_attempts']}`\n"
        f"📦 *Queued Unposted Batches:* `{stats['queued_batches']}`\n"
        f"📡 *Posted Batches:* `{stats['posted_batches']}`\n"
        f"❓ *Total Questions in Database:* `{stats['total_questions']}`\n"
        f"⏱ *Broadcast Frequency:* `Every {BROADCAST_INTERVAL_MINUTES} mins`\n"
        f"📢 *Target Channel:* `{CHANNEL_ID or 'Not Set'}`"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ==========================================
# SCHEDULED BROADCAST LOGIC
# ==========================================

def build_question_keyboard(q_id: int, options: List[Any]) -> InlineKeyboardMarkup:
    """
    Builds responsive inline keyboard buttons for question options.
    Callback data format: ans:<q_id>:<option_key>
    """
    option_letters = ["A", "B", "C", "D", "E", "F"]
    buttons: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for idx, opt in enumerate(options):
        letter = option_letters[idx] if idx < len(option_letters) else f"{idx + 1}"
        opt_str = str(opt).strip()
        
        # If the option string itself starts with "A", "B", etc.
        btn_text = f"{letter}. {opt_str}" if not opt_str.startswith(f"{letter}") else opt_str
        callback_data = f"ans:{q_id}:{letter}"

        row.append(InlineKeyboardButton(text=btn_text, callback_data=callback_data))

        # 2 buttons per row for neat mobile display
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)


async def broadcast_next_batch(application: Application) -> Tuple[bool, str]:
    """
    Fetches the next unposted batch from SQLite, posts the banner to the channel,
    posts all questions with inline option buttons, and marks the batch as posted.
    """
    if not CHANNEL_ID:
        logger.warning("Scheduled broadcast skipped: CHANNEL_ID is not configured.")
        return False, "CHANNEL_ID is not configured."

    batch = database.get_next_unposted_batch()
    if not batch:
        logger.info("No unposted quiz batches in queue.")
        return False, "No unposted quiz batches found in queue."

    batch_num = batch["batch_number"]
    title = batch["title"]
    questions = batch["questions"]

    logger.info(f"Broadcasting Batch #{batch_num}: '{title}' with {len(questions)} questions.")

    try:
        # 1. Post Batch Banner
        banner_text = (
            f"🌌 *NATHVERSE QUIZ CHALLENGE* 🌌\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 *Batch #{batch_num}*: {title}\n"
            f"📝 *Questions*: `{len(questions)}`\n"
            f"⚡ *Scoring*: `+3` for Correct | `-1` for Incorrect\n"
            f"⏳ *Cooldown Policy*: Progressive over past 24h\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 *Answer the questions below to earn points!*"
        )
        await application.bot.send_message(
            chat_id=CHANNEL_ID,
            text=banner_text,
            parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(1.0)

        # 2. Post Each Question Individually
        for idx, q in enumerate(questions, start=1):
            q_text = (
                f"🧩 *Question {idx}/{len(questions)}* (Batch #{batch_num})\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{q['question_text']}\n\n"
                f"Tap your answer below:"
            )
            keyboard = build_question_keyboard(q["id"], q["options"])
            await application.bot.send_message(
                chat_id=CHANNEL_ID,
                text=q_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            # Short sleep to prevent Telegram rate limit spikes
            await asyncio.sleep(1.2)

        # 3. Mark Batch as Posted
        database.mark_batch_posted(batch_num)
        logger.info(f"Successfully broadcast and marked Batch #{batch_num} as posted.")
        return True, f"Batch #{batch_num} ('{title}') successfully broadcast ({len(questions)} questions)."

    except Exception as e:
        logger.error(f"Failed during channel broadcast: {e}", exc_info=True)
        return False, f"Broadcast failed: {str(e)}"


# ==========================================
# CALLBACK ANSWER ROUTING & MODAL ALERTS
# ==========================================

async def handle_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles user tapping on an answer button (`ans:<q_id>:<option>`).
    Enforces progressive cooldown and sends show_alert popups with instant feedback.
    """
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    if not data.startswith("ans:"):
        return

    parts = data.split(":", 2)
    if len(parts) < 3:
        await query.answer("Invalid question choice.", show_alert=False)
        return

    try:
        q_id = int(parts[1])
    except ValueError:
        await query.answer("Invalid question ID.", show_alert=False)
        return

    selected_option = parts[2].strip().upper()
    user = query.from_user
    user_id = user.id
    username = user.username or user.first_name or f"Player {user_id}"

    # 1. Progressive Cooldown Check
    is_cd, rem_seconds, formatted_cd = database.check_cooldown(user_id)
    if is_cd:
        cd_alert = (
            f"⏳ Cooldown Active!\n\n"
            f"Please wait {formatted_cd} before your next attempt.\n\n"
            f"Cooldown policy: 1st immediate, 2nd 1h, 3rd 6h, 4th+ 24h."
        )
        # Telegram alert dialog limit is ~200 chars
        await query.answer(cd_alert[:195], show_alert=True)
        return

    # 2. Check if user already answered this exact question
    if database.has_user_attempted(user_id, q_id):
        await query.answer(
            "⚠️ You have already submitted an answer for this question!",
            show_alert=True
        )
        return

    # 3. Record Answer and Calculate Scoring
    result = database.record_answer(user_id, username, q_id, selected_option)
    if "error" in result:
        await query.answer("⚠️ Question not found or closed.", show_alert=True)
        return

    is_correct = result["is_correct"]
    correct_option = result["correct_option"]
    explanation = result["explanation"]

    if is_correct:
        # Prompt requirement:
        # If answer is Correct: Show alert: `✅ Correct! +3 points added.`
        alert_msg = "✅ Correct! +3 points added."
    else:
        # Prompt requirement:
        # If answer is Incorrect: Show alert: `❌ Incorrect! (Correct answer was {correct_option})\n\n💡 Explanation:\n{explanation}\n\n-1 point applied.`
        raw_msg = f"❌ Incorrect! (Correct answer was {correct_option})\n\n💡 Explanation:\n{explanation}\n\n-1 point applied."
        # Keep within Telegram's 200-char modal alert boundary
        if len(raw_msg) > 195:
            avail_len = 195 - len(f"❌ Incorrect! (Correct was {correct_option})\n\n💡 ...\n\n-1 point applied.")
            short_exp = explanation[:max(20, avail_len)] + "..."
            alert_msg = f"❌ Incorrect! (Correct was {correct_option})\n\n💡 {short_exp}\n\n-1 point applied."
        else:
            alert_msg = raw_msg

    await query.answer(alert_msg, show_alert=True)


# ==========================================
# APPLICATION LIFECYCLE & SCHEDULER SETUP
# ==========================================

async def post_init(application: Application) -> None:
    """
    Initializes database tables, configures APScheduler, and schedules
    the recurring 720-minute channel broadcast.
    """
    logger.info("Initializing NathVerse database...")
    database.init_db()

    logger.info(f"Setting up APScheduler (Interval: {BROADCAST_INTERVAL_MINUTES} minutes)...")
    scheduler.add_job(
        broadcast_next_batch,
        trigger=IntervalTrigger(minutes=BROADCAST_INTERVAL_MINUTES),
        id="quiz_batch_broadcaster",
        replace_existing=True,
        args=[application]
    )
    scheduler.start()
    logger.info("APScheduler started successfully.")


async def post_shutdown(application: Application) -> None:
    """Gracefully shuts down APScheduler on bot termination."""
    if scheduler.running:
        logger.info("Shutting down APScheduler...")
        scheduler.shutdown(wait=False)


def build_application() -> Application:
    """
    Configures handlers and builds the python-telegram-bot Application instance.
    """
    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN is not set in environment. Set it in .env to connect to Telegram.")

    app = (
        Application.builder()
        .token(BOT_TOKEN or "DUMMY_TOKEN_FOR_BUILD_CHECK")
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler(["leaderboard", "top"], leaderboard_command))
    app.add_handler(CommandHandler(["stats", "me"], stats_command))

    # Admin Handlers
    app.add_handler(CommandHandler("addquiz", addquiz_command))
    app.add_handler(CommandHandler("postbatch", postbatch_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document_upload))

    # Callback Query Answer Handler
    app.add_handler(CallbackQueryHandler(handle_answer_callback, pattern=r"^ans:"))

    return app


def main() -> None:
    """Bot entry point."""
    if not BOT_TOKEN:
        print("=" * 60)
        print("ERROR: BOT_TOKEN is not defined in your environment or .env file.")
        print("Please configure BOT_TOKEN, CHANNEL_ID, and ADMIN_IDS in .env.")
        print("=" * 60)
        return

    logger.info("Starting NathVerse Telegram Quiz Bot...")
    application = build_application()
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
