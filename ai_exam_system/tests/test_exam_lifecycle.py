"""
Tests for the full exam lifecycle:
  - Start a session
  - Submit answers
  - Finish the session
  - Retrieve results
  - Ownership enforcement (one student cannot access another's session)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import client, register_and_login, TEST_PREFIX


def test_full_exam_lifecycle():
    """
    End-to-end test: register, start session, submit an answer,
    finish session, read results.
    """

    # Create a student
    user = register_and_login("lifecycle_a")
    headers = user["auth_headers"]

    # Find an available question domain/skill from the question bank
    q_resp = client.get("/questions?limit=1", headers=headers)
    assert q_resp.status_code == 200
    questions = q_resp.json().get("questions", [])

    if not questions:
        # No questions in the bank yet - skip this test with a note
        print("WARNING: No questions found in question bank. Skipping lifecycle test.")
        return

    first_q = questions[0]
    domain = first_q["domain"]
    skill = first_q["skill"]

    # Start an exam session
    session_resp = client.post("/exam-sessions", json={
        "domain": domain,
        "skill": skill,
        "max_questions": 2
    }, headers=headers)

    assert session_resp.status_code == 201, f"Session start failed: {session_resp.text}"
    session = session_resp.json()
    session_id = session["id"]
    assert session["status"] == "active"
    assert session["domain"] == domain

    # Get next question from the adaptive engine
    next_q_resp = client.get(f"/exam-sessions/{session_id}/next-question", headers=headers)
    
    if next_q_resp.status_code == 404:
        print("WARNING: No eligible questions found. Skipping answer submission.")
        client.post(f"/exam-sessions/{session_id}/finish", headers=headers)
        return

    assert next_q_resp.status_code == 200, f"Next question failed: {next_q_resp.text}"
    q = next_q_resp.json()
    
    options = q.get("options", ["A"])
    if isinstance(options, dict):
        selected = list(options.keys())[0] if options else "A"
    else:
        selected = options[0] if options else "A"

    attempt_resp = client.post("/question-attempts", json={
        "question_id": q["id"],
        "selected_answer": selected,
        "time_taken": 15,
        "exam_session_id": session_id
    }, headers=headers)

    assert attempt_resp.status_code == 201, f"Attempt failed: {attempt_resp.text}"
    attempt = attempt_resp.json()

    # After submission, correct_answer must be revealed (the session is still active
    # but the student already submitted this question so it is safe to show the answer)
    assert "correct_answer" in attempt
    assert "is_correct" in attempt
    assert "explanation" in attempt
    assert "session" in attempt

    # Finish the session
    finish_resp = client.post(f"/exam-sessions/{session_id}/finish", headers=headers)
    assert finish_resp.status_code == 200, f"Finish failed: {finish_resp.text}"
    finished = finish_resp.json()
    assert finished["status"] == "finished"
    assert finished["questions_answered"] == 1

    # Read results
    results_resp = client.get(f"/exam-sessions/{session_id}/results", headers=headers)
    assert results_resp.status_code == 200
    results = results_resp.json()
    assert "question_results" in results
    assert len(results["question_results"]) == 1
    assert "recommendations" in results


def test_cannot_start_duplicate_active_session():
    """Starting a second session in the same domain while one is active returns 409."""

    user = register_and_login("lifecycle_dup")
    headers = user["auth_headers"]

    q_resp = client.get("/questions?limit=1", headers=headers)
    questions = q_resp.json().get("questions", [])
    if not questions:
        return

    domain = questions[0]["domain"]
    skill = questions[0]["skill"]

    # First session
    r1 = client.post("/exam-sessions", json={"domain": domain, "skill": skill, "max_questions": 5}, headers=headers)
    assert r1.status_code == 201
    session_id = r1.json()["id"]

    # Second session in the same domain - must fail
    r2 = client.post("/exam-sessions", json={"domain": domain, "skill": skill, "max_questions": 5}, headers=headers)
    assert r2.status_code == 409

    # Cleanup: finish the first session
    client.post(f"/exam-sessions/{session_id}/finish", headers=headers)


def test_cannot_access_another_students_session():
    """Student B cannot read or finish Student A's exam session."""

    user_a = register_and_login("lifecycle_ownership_a")
    user_b = register_and_login("lifecycle_ownership_b")

    q_resp = client.get("/questions?limit=1", headers=user_a["auth_headers"])
    questions = q_resp.json().get("questions", [])
    if not questions:
        return

    domain = questions[0]["domain"]
    skill = questions[0]["skill"]

    # Student A starts a session
    r = client.post("/exam-sessions", json={"domain": domain, "skill": skill, "max_questions": 2},
                    headers=user_a["auth_headers"])
    assert r.status_code == 201
    session_id = r.json()["id"]

    # Student B tries to read it - must be forbidden
    read_resp = client.get(f"/exam-sessions/{session_id}", headers=user_b["auth_headers"])
    assert read_resp.status_code == 403

    # Student B tries to finish it - must be forbidden
    finish_resp = client.post(f"/exam-sessions/{session_id}/finish", headers=user_b["auth_headers"])
    assert finish_resp.status_code == 403

    # Cleanup
    client.post(f"/exam-sessions/{session_id}/finish", headers=user_a["auth_headers"])


def test_cannot_answer_finished_session():
    """Submitting an answer to a finished session returns 409."""

    user = register_and_login("lifecycle_finished")
    headers = user["auth_headers"]

    q_resp = client.get("/questions?limit=2", headers=headers)
    questions = q_resp.json().get("questions", [])
    if len(questions) < 1:
        return

    domain = questions[0]["domain"]
    skill = questions[0]["skill"]

    # Start and immediately finish a session
    r = client.post("/exam-sessions", json={"domain": domain, "skill": skill, "max_questions": 2}, headers=headers)
    assert r.status_code == 201
    session_id = r.json()["id"]

    # Get next question while session is still active
    next_q_resp = client.get(f"/exam-sessions/{session_id}/next-question", headers=headers)
    if next_q_resp.status_code == 404:
        return
    q = next_q_resp.json()

    # Finish the session
    client.post(f"/exam-sessions/{session_id}/finish", headers=headers)

    # Try to submit an answer to the finished session
    attempt_resp = client.post("/question-attempts", json={
        "question_id": q["id"],
        "selected_answer": "anything",
        "time_taken": 5,
        "exam_session_id": session_id
    }, headers=headers)

    assert attempt_resp.status_code == 409


def test_results_not_available_during_active_session():
    """Cannot view results while the session is still active."""

    user = register_and_login("lifecycle_active_results")
    headers = user["auth_headers"]

    q_resp = client.get("/questions?limit=1", headers=headers)
    questions = q_resp.json().get("questions", [])
    if not questions:
        return

    domain = questions[0]["domain"]
    skill = questions[0]["skill"]

    r = client.post("/exam-sessions", json={"domain": domain, "skill": skill, "max_questions": 5}, headers=headers)
    assert r.status_code == 201
    session_id = r.json()["id"]

    # Try to read results on an active session
    results_resp = client.get(f"/exam-sessions/{session_id}/results", headers=headers)
    assert results_resp.status_code == 400

    # Cleanup
    client.post(f"/exam-sessions/{session_id}/finish", headers=headers)


def test_performance_endpoint():
    """Performance endpoint returns valid statistics for authenticated user."""

    user = register_and_login("lifecycle_perf")
    headers = user["auth_headers"]

    resp = client.get("/performance", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "total_attempts" in data
    assert "correct_answers" in data
    assert "accuracy" in data
    assert isinstance(data["accuracy"], (int, float))
