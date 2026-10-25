"""
Tests for Advanced EdTech Industry Features:
1. KaTeX LaTeX Math delimiters & prompts
2. Cognitive Fatigue & Rapid-Guess Detection Engine
3. Multidimensional IRT (MIRT) 3D Ability Vector
4. Human-in-the-Loop Review Pipeline
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import client, register_and_login, TestingSessionLocal
from app.models.user import User
from app.models.question import Question
from ml.irt_model import MultidimensionalIRT


def test_reviewer_pipeline_permissions_and_certification():
    """
    Test Human-in-the-Loop review queue:
    - Students blocked with 403
    - Reviewers allowed
    - Approving and rejecting pending questions
    """
    student = register_and_login("rev_student")
    reviewer = register_and_login("rev_reviewer")

    # Elevate reviewer user to role='reviewer' in DB
    db = TestingSessionLocal()
    db_user = db.query(User).filter(User.email == reviewer["email"]).first()
    assert db_user is not None
    db_user.role = "reviewer"
    reviewer_user_id = str(db_user.id)

    # Insert a dummy question with approval_status='pending_review'
    pending_q = Question(
        question_text="What is the value of $\\int_0^1 x^2\\,dx$?",
        domain="Mathematics",
        skill="Definite Integrals",
        difficulty=3,
        minimum_level=2,
        maximum_level=4,
        options={"A": "1/3", "B": "1/2", "C": "1/4", "D": "1"},
        correct_answer="A",
        explanation="The antiderivative is $x^3/3$, evaluating from 0 to 1 gives $1/3$.",
        question_type="multiple_choice",
        is_active=True,
        source="llm_generated",
        approval_status="pending_review"
    )
    db.add(pending_q)
    db.commit()
    db.refresh(pending_q)
    qid = str(pending_q.id)
    db.close()

    # 1. Student access blocked
    res_student = client.get("/questions/pending-review", headers=student["auth_headers"])
    assert res_student.status_code == 403

    cert_student = client.post(
        f"/questions/{qid}/certify",
        json={"action": "approve"},
        headers=student["auth_headers"]
    )
    assert cert_student.status_code == 403

    # 2. Reviewer can view queue and see correct_answer
    res_reviewer = client.get("/questions/pending-review", headers=reviewer["auth_headers"])
    assert res_reviewer.status_code == 200
    queue = res_reviewer.json()
    assert any(q["id"] == qid for q in queue)
    target_q = next(q for q in queue if q["id"] == qid)
    assert target_q["correct_answer"] == "A"
    assert "$\\int_0^1" in target_q["question_text"]

    # 3. Reviewer certifies / approves question
    approve_res = client.post(
        f"/questions/{qid}/certify",
        json={"action": "approve", "reviewer_note": "Accurate calculus item with valid KaTeX notation"},
        headers=reviewer["auth_headers"]
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["new_status"] == "approved"

    # Verify updated in DB
    db = TestingSessionLocal()
    updated_q = db.query(Question).filter(Question.id == pending_q.id).first()
    assert updated_q.approval_status == "approved"
    assert updated_q.approved_by == reviewer_user_id
    assert updated_q.is_active is True

    # 4. Now test rejection flow on a second pending question
    reject_q = Question(
        question_text="Flawed question with incorrect math $\\frac{1}{0}$",
        domain="Mathematics",
        skill="Arithmetic",
        difficulty=1,
        minimum_level=1,
        maximum_level=2,
        options={"A": "0", "B": "Infinity"},
        correct_answer="A",
        question_type="multiple_choice",
        is_active=True,
        source="llm_generated",
        approval_status="pending_review"
    )
    db.add(reject_q)
    db.commit()
    db.refresh(reject_q)
    reject_qid = str(reject_q.id)
    db.close()

    reject_res = client.post(
        f"/questions/{reject_qid}/certify",
        json={"action": "reject", "reviewer_note": "Mathematically undefined distractor"},
        headers=reviewer["auth_headers"]
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["new_status"] == "rejected"

    db = TestingSessionLocal()
    check_rej = db.query(Question).filter(Question.id == reject_q.id).first()
    assert check_rej.approval_status == "rejected"
    assert check_rej.is_active is False
    db.close()


def test_mirt_multidimensional_irt_unit():
    """
    Unit test for MultidimensionalIRT model:
    - Verifies cognitive classification (conceptual, numerical, analytical)
    - Verifies 3D ability estimation vector
    """
    mirt = MultidimensionalIRT()

    # Classification tests
    assert mirt._classify_question("Define Newton's first law of motion", "Physics Laws") == "conceptual"
    assert mirt._classify_question("Calculate the velocity given distance 100m and time 5s", "Kinematics") == "numerical"
    assert mirt._classify_question("Analyze the effect of temperature on reaction rate and infer the consequence", "Thermodynamics") == "analytical"

    # Ability estimation test
    sample_results = [
        # Conceptual items (correct)
        {"question_text": "Define the concept of entropy", "skill": "Theory", "difficulty": 3, "is_correct": True},
        {"question_text": "State the principle of conservation of energy", "skill": "Laws", "difficulty": 2, "is_correct": True},
        # Numerical items (incorrect)
        {"question_text": "Calculate the integral value", "skill": "Calculus", "difficulty": 4, "is_correct": False},
        {"question_text": "Compute the molar mass", "skill": "Stoichiometry", "difficulty": 3, "is_correct": False},
        # Analytical items (correct)
        {"question_text": "Analyze and compare the circuit response", "skill": "Circuits", "difficulty": 3, "is_correct": True},
    ]

    vector = mirt.estimate_theta(sample_results)

    assert "theta_conceptual" in vector
    assert "theta_numerical" in vector
    assert "theta_analytical" in vector
    assert "composite_theta" in vector

    # Conceptual should be higher than numerical since conceptual questions were answered correctly
    assert vector["theta_conceptual"] > vector["theta_numerical"]
    assert vector["n_conceptual"] == 2
    assert vector["n_numerical"] == 2
    assert vector["n_analytical"] == 1


def test_cognitive_fatigue_and_mirt_in_session_results():
    """
    End-to-end integration test verifying that finished exam sessions return:
    1. Cognitive Fatigue Analytics with rapid-guess flags
    2. Multidimensional IRT theta vector
    """
    user = register_and_login("fatigue_student")
    headers = user["auth_headers"]

    # Start live exam
    q_resp = client.get("/questions?limit=5", headers=headers)
    questions = q_resp.json().get("questions", [])
    domain = questions[0]["domain"] if questions else "Physics"

    session_resp = client.post("/exam-sessions", json={
        "domain": domain,
        "max_questions": 3,
        "exam_type": "live",
        "positive_mark": 4.0,
        "negative_mark": 1.0,
        "exam_paper_title": "JEE Main Mock KaTeX & Fatigue Test"
    }, headers=headers)
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    # Answer question 1 very quickly (2 seconds) -> triggers rapid-guess flag
    q1 = client.get(f"/exam-sessions/{session_id}/question-by-seq/1", headers=headers).json()
    opt1 = list(q1["options"].keys())[0] if isinstance(q1["options"], dict) else "A"
    client.post(f"/exam-sessions/{session_id}/live-answer", json={
        "question_id": q1["question_id"],
        "selected_option": opt1,
        "review_status": "answered",
        "time_taken": 2  # rapid guess (< threshold of 5-8 seconds)
    }, headers=headers)

    # Answer question 2 with normal time (45 seconds)
    q2 = client.get(f"/exam-sessions/{session_id}/question-by-seq/2", headers=headers).json()
    opt2 = list(q2["options"].keys())[0] if isinstance(q2["options"], dict) else "A"
    client.post(f"/exam-sessions/{session_id}/live-answer", json={
        "question_id": q2["question_id"],
        "selected_option": opt2,
        "review_status": "answered",
        "time_taken": 45
    }, headers=headers)

    # Finish session
    finish_res = client.post(f"/exam-sessions/{session_id}/finish", headers=headers)
    assert finish_res.status_code == 200

    # Fetch results
    results_res = client.get(f"/exam-sessions/{session_id}/results", headers=headers)
    assert results_res.status_code == 200
    res_data = results_res.json()

    # 1. Verify Fatigue Analytics
    assert "fatigue_analytics" in res_data
    fatigue = res_data["fatigue_analytics"]
    assert "rapid_guess_count" in fatigue
    assert "rapid_guess_flags" in fatigue
    assert "fatigue_detected" in fatigue
    assert "fatigue_buckets" in fatigue
    assert "total_exam_time_seconds" in fatigue

    # Rapid guess was detected for question 1 (time_taken = 2s)
    assert fatigue["rapid_guess_count"] >= 1
    flagged_ids = [f["question_id"] for f in fatigue["rapid_guess_flags"]]
    assert q1["question_id"] in flagged_ids

    # 2. Verify Multidimensional IRT Vector
    assert "theta_vector" in res_data
    theta_vec = res_data["theta_vector"]
    assert theta_vec is not None
    assert "theta_conceptual" in theta_vec
    assert "theta_numerical" in theta_vec
    assert "theta_analytical" in theta_vec
    assert "composite_theta" in theta_vec
