"""
NathVerse Quiz Bot - Database Layer
Handles SQLite database connection, table initialization, progressive cooldowns,
scoring calculations, batch management, and leaderboard tracking.
"""

import os
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple

# Resolve data directory and DB path
DATA_DIR = os.environ.get("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "nathverse.db")

# Thread lock to prevent concurrent write collisions on SQLite
_DB_LOCK = threading.Lock()


def get_connection() -> sqlite3.Connection:
    """
    Creates and configures a SQLite connection with WAL mode and busy timeout
    to prevent database lock errors under concurrent async load.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """
    Initializes required database tables: users, attempts, and quizzes.
    Creates performance indexes for cooldown checks and leaderboard queries.
    """
    with _DB_LOCK:
        with get_connection() as conn:
            cursor = conn.cursor()

            # 1. Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    points INTEGER NOT NULL DEFAULT 0 CHECK(points >= 0),
                    questions_attempted INTEGER NOT NULL DEFAULT 0,
                    correct_answers INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Attempts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    is_correct INTEGER NOT NULL CHECK(is_correct IN (0, 1)),
                    points_awarded INTEGER NOT NULL,
                    attempt_time TIMESTAMP NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (question_id) REFERENCES quizzes(id)
                );
            """)

            # Index for fast progressive cooldown lookups (user_id + attempt_time)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_attempts_user_time
                ON attempts (user_id, attempt_time DESC);
            """)

            # Index for duplicate attempt checks
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_attempts_user_question
                ON attempts (user_id, question_id);
            """)

            # 3. Quizzes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quizzes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_number INTEGER NOT NULL,
                    batch_title TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    options TEXT NOT NULL,
                    correct_option TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    is_posted INTEGER NOT NULL DEFAULT 0 CHECK(is_posted IN (0, 1)),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Index for batch querying and posting status
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_quizzes_batch_posted
                ON quizzes (batch_number, is_posted);
            """)

            conn.commit()


def insert_quiz_batch(batch_number: int, batch_title: str, questions: List[Dict[str, Any]]) -> int:
    """
    Inserts a list of validated questions belonging to a batch.
    Options are stored as a serialized JSON list of strings.
    Returns the number of questions inserted.
    """
    if not questions:
        return 0

    inserted_count = 0
    with _DB_LOCK:
        with get_connection() as conn:
            cursor = conn.cursor()
            for q in questions:
                # Options can be list or already formatted
                raw_options = q.get("options", [])
                options_json = json.dumps(raw_options) if isinstance(raw_options, list) else str(raw_options)
                
                # Normalize correct answer (e.g. 'A' or the exact text)
                correct_option = str(q.get("answer", "")).strip().upper()
                explanation = str(q.get("explanation", "")).strip()
                question_text = str(q.get("text", "")).strip()

                cursor.execute("""
                    INSERT INTO quizzes (
                        batch_number, batch_title, question_text, options,
                        correct_option, explanation, is_posted
                    ) VALUES (?, ?, ?, ?, ?, ?, 0)
                """, (batch_number, batch_title, question_text, options_json, correct_option, explanation))
                inserted_count += 1
            
            conn.commit()
    return inserted_count


def get_next_unposted_batch() -> Optional[Dict[str, Any]]:
    """
    Retrieves the next unposted batch with the lowest batch_number.
    Returns a dictionary containing batch_number, title, and question records,
    or None if all batches have been posted.
    """
    with _DB_LOCK:
        with get_connection() as conn:
            cursor = conn.cursor()
            # Find lowest unposted batch number
            cursor.execute("""
                SELECT batch_number, batch_title
                FROM quizzes
                WHERE is_posted = 0
                ORDER BY batch_number ASC
                LIMIT 1
            """)
            batch_row = cursor.fetchone()
            if not batch_row:
                return None

            batch_number = batch_row["batch_number"]
            batch_title = batch_row["batch_title"]

            cursor.execute("""
                SELECT id, batch_number, batch_title, question_text, options, correct_option, explanation
                FROM quizzes
                WHERE batch_number = ? AND is_posted = 0
                ORDER BY id ASC
            """, (batch_number,))
            
            rows = cursor.fetchall()
            questions = []
            for r in rows:
                try:
                    options_list = json.loads(r["options"])
                except Exception:
                    options_list = []

                questions.append({
                    "id": r["id"],
                    "batch_number": r["batch_number"],
                    "batch_title": r["batch_title"],
                    "question_text": r["question_text"],
                    "options": options_list,
                    "correct_option": r["correct_option"],
                    "explanation": r["explanation"]
                })

            return {
                "batch_number": batch_number,
                "title": batch_title,
                "questions": questions
            }


def mark_batch_posted(batch_num: int) -> bool:
    """
    Marks all questions in the specified batch as posted.
    """
    with _DB_LOCK:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE quizzes
                SET is_posted = 1
                WHERE batch_number = ?
            """, (batch_num,))
            conn.commit()
            return cursor.rowcount > 0


def get_question_details(q_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves question details including correct_option, explanation, text, and options.
    """
    with _DB_LOCK:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, batch_number, batch_title, question_text, options, correct_option, explanation, is_posted
                FROM quizzes
                WHERE id = ?
            """, (q_id,))
            row = cursor.fetchone()
            if not row:
                return None

            try:
                options_list = json.loads(row["options"])
            except Exception:
                options_list = []

            return {
                "id": row["id"],
                "batch_number": row["batch_number"],
                "batch_title": row["batch_title"],
                "question_text": row["question_text"],
                "options": options_list,
                "correct_option": row["correct_option"],
                "explanation": row["explanation"],
                "is_posted": bool(row["is_posted"])
            }


def check_cooldown(user_id: int) -> Tuple[bool, int, str]:
    """
    Evaluates progressive cooldown based on attempts within the past 24 hours:
      - 1st attempt: Immediate (0s)
      - 2nd attempt: 1-hour cooldown (3,600s) from 1st attempt
      - 3rd attempt: 6-hour cooldown (21,600s) from 2nd attempt
      - 4th+ attempt: 24-hour cooldown (86,400s) from 3rd+ attempt

    Returns:
      (is_on_cooldown: bool, remaining_seconds: int, formatted_remaining_time: str)
    """
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=24)).isoformat()

    with _DB_LOCK:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT attempt_time
                FROM attempts
                WHERE user_id = ? AND attempt_time >= ?
                ORDER BY attempt_time DESC
            """, (user_id, cutoff))
            rows = cursor.fetchall()

    if not rows:
        # No attempts in past 24h -> 1st attempt is immediate
        return False, 0, ""

    past_attempts_count = len(rows)

    # Parse timestamp of the most recent attempt
    most_recent_str = rows[0]["attempt_time"]
    try:
        most_recent_time = datetime.fromisoformat(most_recent_str)
        if most_recent_time.tzinfo is None:
            most_recent_time = most_recent_time.replace(tzinfo=timezone.utc)
    except Exception:
        # Fallback parsing
        most_recent_time = now

    elapsed_seconds = (now - most_recent_time).total_seconds()

    # Determine required cooldown based on number of prior attempts in 24h:
    # 1 prior attempt -> next is 2nd attempt -> 1 hour (3600s)
    # 2 prior attempts -> next is 3rd attempt -> 6 hours (21600s)
    # 3+ prior attempts -> next is 4th+ attempt -> 24 hours (86400s)
    if past_attempts_count == 1:
        required_cooldown = 1 * 3600  # 1 hour
    elif past_attempts_count == 2:
        required_cooldown = 6 * 3600  # 6 hours
    else:
        required_cooldown = 24 * 3600  # 24 hours

    if elapsed_seconds < required_cooldown:
        remaining = int(required_cooldown - elapsed_seconds)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        seconds = remaining % 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or hours > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        formatted = " ".join(parts)
        
        return True, remaining, formatted

    return False, 0, ""


def has_user_attempted(user_id: int, question_id: int) -> bool:
    """
    Checks if a user has already attempted this specific question.
    """
    with _DB_LOCK:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM attempts
                WHERE user_id = ? AND question_id = ?
                LIMIT 1
            """, (user_id, question_id))
            return cursor.fetchone() is not None


def record_answer(user_id: int, username: Optional[str], question_id: int, selected_option: str) -> Dict[str, Any]:
    """
    Evaluates the user's selected answer, updates scoring, logs attempt,
    and updates the user's points (floored at 0).
    
    Scoring:
      - Correct: +3 points
      - Incorrect: -1 point (floor at 0)

    Returns a dict with:
      - is_correct (bool)
      - points_awarded (int)
      - new_points (int)
      - correct_option (str)
      - explanation (str)
      - already_attempted (bool)
    """
    # 1. Fetch question details
    q = get_question_details(question_id)
    if not q:
        return {
            "error": "Question not found",
            "is_correct": False,
            "points_awarded": 0,
            "new_points": 0,
            "correct_option": "",
            "explanation": "Question does not exist."
        }

    correct_option = q["correct_option"].strip().upper()
    selected_clean = selected_option.strip().upper()

    # Match selected option: check if selected option letter matches (e.g. 'A' == 'A')
    # Or matches exact text of option
    is_correct = (selected_clean == correct_option)
    points_delta = 3 if is_correct else -1
    now_iso = datetime.now(timezone.utc).isoformat()

    display_name = username or f"User_{user_id}"

    with _DB_LOCK:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Check if user already exists
            cursor.execute("SELECT points, questions_attempted, correct_answers FROM users WHERE user_id = ?", (user_id,))
            user_row = cursor.fetchone()

            if user_row:
                current_points = user_row["points"]
                new_points = max(0, current_points + points_delta)
                new_attempted = user_row["questions_attempted"] + 1
                new_correct = user_row["correct_answers"] + (1 if is_correct else 0)

                cursor.execute("""
                    UPDATE users
                    SET username = ?,
                        points = ?,
                        questions_attempted = ?,
                        correct_answers = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (display_name, new_points, new_attempted, new_correct, user_id))
            else:
                new_points = max(0, points_delta)
                new_attempted = 1
                new_correct = 1 if is_correct else 0

                cursor.execute("""
                    INSERT INTO users (user_id, username, points, questions_attempted, correct_answers)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, display_name, new_points, new_attempted, new_correct))

            # Record in attempts table
            cursor.execute("""
                INSERT INTO attempts (user_id, question_id, is_correct, points_awarded, attempt_time)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, question_id, 1 if is_correct else 0, points_delta, now_iso))

            conn.commit()

    return {
        "is_correct": is_correct,
        "points_awarded": points_delta,
        "new_points": new_points,
        "correct_option": correct_option,
        "explanation": q["explanation"]
    }


def get_leaderboard(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieves the top users ranked by points descending.
    Computes Accuracy % = (correct_answers / questions_attempted) * 100.
    """
    with _DB_LOCK:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, points, questions_attempted, correct_answers
                FROM users
                WHERE questions_attempted > 0
                ORDER BY points DESC, correct_answers DESC, questions_attempted ASC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()

            leaderboard = []
            for r in rows:
                attempted = r["questions_attempted"]
                correct = r["correct_answers"]
                accuracy = round((correct / attempted * 100.0), 1) if attempted > 0 else 0.0

                leaderboard.append({
                    "user_id": r["user_id"],
                    "username": r["username"] or f"Player {r['user_id']}",
                    "points": r["points"],
                    "questions_attempted": attempted,
                    "correct_answers": correct,
                    "accuracy": accuracy
                })

            return leaderboard


def get_user_stats(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves individual user profile stats and current rank.
    """
    with _DB_LOCK:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, points, questions_attempted, correct_answers
                FROM users
                WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return None

            # Calculate rank
            cursor.execute("""
                SELECT COUNT(*) + 1 AS rank
                FROM users
                WHERE points > ? OR (points = ? AND correct_answers > ?)
            """, (row["points"], row["points"], row["correct_answers"]))
            rank_row = cursor.fetchone()
            rank = rank_row["rank"] if rank_row else 1

            attempted = row["questions_attempted"]
            correct = row["correct_answers"]
            accuracy = round((correct / attempted * 100.0), 1) if attempted > 0 else 0.0

            return {
                "user_id": row["user_id"],
                "username": row["username"],
                "points": row["points"],
                "questions_attempted": attempted,
                "correct_answers": correct,
                "accuracy": accuracy,
                "rank": rank
            }


def get_system_stats() -> Dict[str, Any]:
    """
    Retrieves administrative statistics: total users, total attempts,
    posted batches, and queued unposted batches.
    """
    with _DB_LOCK:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM attempts")
            total_attempts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT batch_number) FROM quizzes WHERE is_posted = 1")
            posted_batches = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT batch_number) FROM quizzes WHERE is_posted = 0")
            queued_batches = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM quizzes")
            total_questions = cursor.fetchone()[0]

            return {
                "total_users": total_users,
                "total_attempts": total_attempts,
                "posted_batches": posted_batches,
                "queued_batches": queued_batches,
                "total_questions": total_questions
            }


# Auto-initialize database tables on module import
init_db()
