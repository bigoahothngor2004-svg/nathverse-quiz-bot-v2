"""
Comprehensive test suite for NathVerse Quiz Bot
Tests database operations, cooldown timers, scoring edge cases, and JSON validation.
"""

import os
import shutil
import json
from datetime import datetime, timedelta, timezone

# Use clean temporary data folder
TEST_DIR = "test_run_data"
if os.path.exists(TEST_DIR):
    shutil.rmtree(TEST_DIR)
os.environ["DATA_DIR"] = TEST_DIR

import database
import bot


def run_tests():
    print("🚀 Starting NathVerse test suite...")

    # 1. Test database initialization
    database.init_db()
    assert os.path.exists(os.path.join(TEST_DIR, "nathverse.db")), "Database file was not created!"
    print("✅ Database tables created successfully.")

    # 2. Test JSON batch validation
    valid_data = {
        "batch_number": 1,
        "title": "Math: Mixed Practical Word Problems I",
        "questions": [
            {
                "text": "What is 10 + 20?",
                "options": ["25", "30", "35", "40"],
                "answer": "B",
                "explanation": "Because 10 + 20 = 30."
            }
        ]
    }
    is_valid, err = bot.validate_batch_data(valid_data)
    assert is_valid, f"Validation failed on valid data: {err}"

    invalid_data = {
        "batch_number": -1,
        "title": "",
        "questions": []
    }
    is_valid, err = bot.validate_batch_data(invalid_data)
    assert not is_valid, "Validation should fail on negative batch number or empty title."
    print("✅ JSON batch schema validator tested.")

    # 3. Test batch insertion & fetching
    count = database.insert_quiz_batch(valid_data["batch_number"], valid_data["title"], valid_data["questions"])
    assert count == 1, f"Expected 1 inserted, got {count}"

    batch = database.get_next_unposted_batch()
    assert batch is not None, "Failed to retrieve unposted batch"
    assert batch["batch_number"] == 1
    assert len(batch["questions"]) == 1
    q_id = batch["questions"][0]["id"]
    print("✅ Batch insertion and retrieval verified.")

    # 4. Test Scoring & Floor at 0
    # User answering wrong when score is 0
    user_id = 777
    res = database.record_answer(user_id, "test_user", q_id, "A")
    assert not res["is_correct"]
    assert res["points_awarded"] == -1
    assert res["new_points"] == 0, f"Expected floor 0, got {res['new_points']}"

    # Verify duplicate check
    assert database.has_user_attempted(user_id, q_id), "User should be marked as having attempted."
    print("✅ Scoring floor at 0 and attempt logging verified.")

    # 5. Progressive Cooldown tests:
    # After 1 attempt:
    is_cd, rem, fmt = database.check_cooldown(user_id)
    assert is_cd, "Expected cooldown active after 1 attempt"
    assert 3500 <= rem <= 3600, f"Expected ~3600s cooldown for 2nd attempt, got {rem}"
    print(f"✅ 1st attempt cooldown verified: {fmt}")

    # Simulate 2 attempts in past 24h:
    now = datetime.now(timezone.utc)
    with database._DB_LOCK:
        with database.get_connection() as conn:
            conn.execute("DELETE FROM attempts WHERE user_id = ?", (user_id,))
            t1 = (now - timedelta(hours=3)).isoformat()
            t2 = (now - timedelta(minutes=10)).isoformat()
            conn.execute("INSERT INTO attempts (user_id, question_id, is_correct, points_awarded, attempt_time) VALUES (?, ?, 1, 3, ?)", (user_id, q_id, t1))
            conn.execute("INSERT INTO attempts (user_id, question_id, is_correct, points_awarded, attempt_time) VALUES (?, ?, 1, 3, ?)", (user_id, q_id, t2))
            conn.commit()

    is_cd, rem, fmt = database.check_cooldown(user_id)
    assert is_cd, "Expected cooldown active after 2 attempts"
    # Cooldown for 3rd attempt is 6 hours (21600s) from t2 (10 mins ago -> ~21000s remaining)
    assert 20800 <= rem <= 21100, f"Expected ~21000s cooldown for 3rd attempt, got {rem}"
    print(f"✅ 2nd attempt cooldown verified: {fmt}")

    # Simulate 3+ attempts in past 24h:
    with database._DB_LOCK:
        with database.get_connection() as conn:
            t3 = (now - timedelta(minutes=5)).isoformat()
            conn.execute("INSERT INTO attempts (user_id, question_id, is_correct, points_awarded, attempt_time) VALUES (?, ?, 1, 3, ?)", (user_id, q_id, t3))
            conn.commit()

    is_cd, rem, fmt = database.check_cooldown(user_id)
    assert is_cd, "Expected cooldown active after 3+ attempts"
    # Cooldown for 4th+ attempt is 24 hours (86400s) from t3 (5 mins ago -> ~86100s remaining)
    assert 85900 <= rem <= 86200, f"Expected ~86100s cooldown for 4th+ attempt, got {rem}"
    print(f"✅ 3rd+ attempt cooldown verified: {fmt}")

    # 6. Test Leaderboard accuracy and ranking
    database.record_answer(888, "top_player", q_id, "B")
    leaderboard = database.get_leaderboard(5)
    assert len(leaderboard) > 0
    top = leaderboard[0]
    assert top["user_id"] == 888
    assert top["points"] == 3
    assert top["accuracy"] == 100.0
    print("✅ Leaderboard ranking & accuracy calculations verified.")

    # 7. Test Mark batch as posted
    marked = database.mark_batch_posted(1)
    assert marked, "Failed to mark batch as posted"
    assert database.get_next_unposted_batch() is None, "Expected no more unposted batches"
    print("✅ Mark batch posted verified.")

    # Cleanup
    shutil.rmtree(TEST_DIR)
    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! 100% SPEC COMPLIANT.")


if __name__ == "__main__":
    run_tests()
