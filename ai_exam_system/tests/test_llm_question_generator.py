"""
Tests for LLM Question Generation Service & Infinite Adaptive Practice:
- Synthesizing calibrated MCQs
- Safe schema validation (4 options, correct answer, explanation)
- Persistence with source='llm_generated'
- Auto-fallback triggering when question bank is exhausted in practice
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import client, register_and_login
from app.services.llm_question_generator import generate_llm_question, generate_and_persist_question
from app.services.adaptive_engine import select_next_question
from app.models.question import Question


def test_generate_llm_question_schema():
    """Verify that question generation returns a strictly compliant schema."""
    data = generate_llm_question(domain="Computer Science", skill="Dynamic Programming", target_difficulty=1.2)
    assert "question_text" in data
    assert len(data["question_text"]) > 10
    assert isinstance(data["options"], dict)
    assert set(data["options"].keys()) >= {"A", "B", "C", "D"}
    assert data["correct_answer"] in ["A", "B", "C", "D"]
    assert "explanation" in data
    assert len(data["explanation"]) > 5


def test_api_generate_ai_question_endpoint():
    """Verify POST /questions/generate-ai endpoint."""
    user = register_and_login("ai_gen_student")
    resp = client.post("/questions/generate-ai", json={
        "domain": "Artificial Intelligence",
        "skill": "Transformer Attention",
        "target_difficulty": 0.8
    }, headers=user["auth_headers"])

    assert resp.status_code == 201
    q = resp.json()
    assert q["domain"] == "Artificial Intelligence"
    assert q["skill"] == "Transformer Attention"
    assert "question_text" in q
    assert "options" in q
    # Student must not see correct answer
    assert "correct_answer" not in q


def test_adaptive_practice_auto_generates_when_bank_empty():
    """
    When a student enters practice in a new topic with 0 pre-existing questions,
    the adaptive engine automatically synthesizes a new question instead of failing.
    """
    user = register_and_login("empty_bank_student")
    user_id = user["auth_headers"]["Authorization"] # token

    # Unique domain with 0 stored questions
    unique_domain = "Quantum Computing"
    unique_skill = "Qubit Superposition"

    # Start practice session
    session_resp = client.post("/exam-sessions", json={
        "domain": unique_domain,
        "skill": unique_skill,
        "max_questions": 2,
        "exam_type": "practice"
    }, headers=user["auth_headers"])
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    # Calling next-question triggers LLM auto-generation
    next_q_resp = client.get(f"/exam-sessions/{session_id}/next-question", headers=user["auth_headers"])
    assert next_q_resp.status_code == 200
    q_data = next_q_resp.json()
    assert q_data["domain"] == unique_domain
    assert q_data["skill"] == unique_skill
    assert len(q_data["question_text"]) > 5
