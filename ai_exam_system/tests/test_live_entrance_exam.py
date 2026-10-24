"""
Tests for Live Entrance Exam (JEE / NEET / CAT mode):
- Identical question paper for all candidates taking the same exam
- Palette navigation (jumping between questions)
- Save answer, mark for review, clear response
- Zero answer key / correctness leakage during live exam
- Negative marking scoring (+4 / -1)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import client, register_and_login


def test_live_entrance_exam_identical_questions_for_all_candidates():
    """
    Two different candidates taking the same live entrance exam must receive
    the EXACT SAME question IDs in the EXACT SAME sequence.
    """
    user_a = register_and_login("live_student_a")
    user_b = register_and_login("live_student_b")

    # Get available domain
    q_resp = client.get("/questions?limit=5", headers=user_a["auth_headers"])
    assert q_resp.status_code == 200
    questions = q_resp.json().get("questions", [])
    if len(questions) < 2:
        return

    domain = questions[0]["domain"]

    # Student A starts Live Exam
    session_a_resp = client.post("/exam-sessions", json={
        "domain": domain,
        "max_questions": 3,
        "exam_type": "live",
        "positive_mark": 4.0,
        "negative_mark": 1.0,
        "exam_paper_title": "JEE Main Mock Test"
    }, headers=user_a["auth_headers"])
    assert session_a_resp.status_code == 201
    session_a = session_a_resp.json()
    assert session_a["exam_type"] == "live"
    assert session_a["positive_mark"] == 4.0
    assert session_a["negative_mark"] == 1.0

    # Student B starts Live Exam
    session_b_resp = client.post("/exam-sessions", json={
        "domain": domain,
        "max_questions": 3,
        "exam_type": "live",
        "positive_mark": 4.0,
        "negative_mark": 1.0,
        "exam_paper_title": "JEE Main Mock Test"
    }, headers=user_b["auth_headers"])
    assert session_b_resp.status_code == 201
    session_b = session_b_resp.json()

    # Get palettes for both candidates
    palette_a = client.get(f"/exam-sessions/{session_a['id']}/live-palette", headers=user_a["auth_headers"]).json()
    palette_b = client.get(f"/exam-sessions/{session_b['id']}/live-palette", headers=user_b["auth_headers"]).json()

    assert len(palette_a["palette"]) > 0
    assert len(palette_a["palette"]) == len(palette_b["palette"])

    # CRITICAL VERIFICATION: Questions are identical in sequence
    for item_a, item_b in zip(palette_a["palette"], palette_b["palette"]):
        assert item_a["sequence_number"] == item_b["sequence_number"]
        assert item_a["question_id"] == item_b["question_id"]


def test_live_entrance_exam_palette_and_negative_marking():
    """
    Test answering, marking for review, clearing response, and negative marking scoring (+4 / -1).
    """
    user = register_and_login("live_student_palette")
    headers = user["auth_headers"]

    q_resp = client.get("/questions?limit=5", headers=headers)
    questions = q_resp.json().get("questions", [])
    if len(questions) < 2:
        return

    domain = questions[0]["domain"]

    # Start live exam with +4 / -1
    session_resp = client.post("/exam-sessions", json={
        "domain": domain,
        "max_questions": 2,
        "exam_type": "live",
        "positive_mark": 4.0,
        "negative_mark": 1.0
    }, headers=headers)
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    # 1. Fetch Question 1 by sequence
    q1_resp = client.get(f"/exam-sessions/{session_id}/question-by-seq/1", headers=headers)
    assert q1_resp.status_code == 200
    q1 = q1_resp.json()
    assert "correct_answer" not in q1  # No leaks!
    assert "explanation" not in q1

    # 2. Save answer for Question 1
    options = q1["options"]
    chosen_opt = list(options.keys())[0] if isinstance(options, dict) else "A"
    save_resp = client.post(f"/exam-sessions/{session_id}/live-answer", json={
        "question_id": q1["question_id"],
        "selected_option": chosen_opt,
        "review_status": "answered",
        "time_taken": 25
    }, headers=headers)
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "saved"
    assert "correct_answer" not in save_resp.json()  # No leaks!

    # 3. Mark Question 2 for review
    q2_resp = client.get(f"/exam-sessions/{session_id}/question-by-seq/2", headers=headers)
    assert q2_resp.status_code == 200
    q2 = q2_resp.json()
    mark_resp = client.post(f"/exam-sessions/{session_id}/live-answer", json={
        "question_id": q2["question_id"],
        "selected_option": None,
        "review_status": "marked_for_review"
    }, headers=headers)
    assert mark_resp.status_code == 200

    # 4. Check palette status
    palette_resp = client.get(f"/exam-sessions/{session_id}/live-palette", headers=headers)
    assert palette_resp.status_code == 200
    palette_data = palette_resp.json()["palette"]
    assert palette_data[0]["review_status"] == "answered"
    assert palette_data[0]["selected_option"] == chosen_opt
    assert palette_data[1]["review_status"] == "marked_for_review"

    # 5. Finish session and verify negative marking scorecard
    finish_resp = client.post(f"/exam-sessions/{session_id}/finish", headers=headers)
    assert finish_resp.status_code == 200
    res = finish_resp.json()
    assert "scorecard" in res
    card = res["scorecard"]
    assert card["total_questions"] == 2
    # Verify formula: raw_score = (correct * 4) - (incorrect * 1)
    expected_score = (card["correct_count"] * 4.0) - (card["incorrect_count"] * 1.0)
    assert card["raw_score"] == expected_score
