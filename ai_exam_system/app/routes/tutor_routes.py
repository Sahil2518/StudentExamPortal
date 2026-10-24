"""
LLM Tutor routes.

Provides a conversational AI tutor that helps students understand
why they got a question wrong, explains the correct answer, and
suggests study topics related to their weak skills.

The tutor uses the OpenAI API if OPENAI_API_KEY is set in .env.
If the key is missing, it falls back to a rule-based explanation
built from the question's stored explanation text. This means the
tutor always returns something useful regardless of API availability.

Security:
  - The student's token is required (authenticated endpoint)
  - The student can only ask about their own question attempts
  - Correct answers are only included in tutor responses AFTER submission
    (the route checks that an attempt record exists before responding)
  - API keys are read from environment variables, never from the request
"""

import os
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.current_user import get_current_user
from app.models.user import User
from app.models.question import Question
from app.models.question_attempt import QuestionAttempt


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tutor", tags=["LLM Tutor"])


# ---------------------------------------------------------------------------
# Request and response schemas
# ---------------------------------------------------------------------------

class TutorRequest(BaseModel):
    """
    Request a tutor explanation for a specific question attempt.

    The student must have already submitted an answer (question_attempt_id
    must exist and belong to the requesting student).
    """

    # The attempt the student wants explained
    question_attempt_id: str = Field(
        ..., description="ID of the question attempt to explain"
    )

    # Optional follow-up question from the student
    follow_up: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional follow-up question about the topic"
    )


class TutorResponse(BaseModel):
    """Tutor explanation response."""

    question_text: str
    student_answer: str
    correct_answer: str
    was_correct: bool
    explanation: str
    tutor_message: str
    related_topics: list[str]
    source: str  # "llm" or "rule_based"


# ---------------------------------------------------------------------------
# Rule-based fallback tutor
# ---------------------------------------------------------------------------

def _build_rule_based_response(
    question: Question,
    attempt: QuestionAttempt,
    follow_up: Optional[str]
) -> str:
    """
    Build a helpful explanation without the LLM API.

    Uses the question's stored explanation text and adds framing
    based on whether the student was correct or not.
    """

    if attempt.is_correct:
        opening = (
            f"You answered correctly. Here is why your answer is right:"
        )
    else:
        opening = (
            f"You selected '{attempt.selected_answer}', but the correct "
            f"answer is '{question.correct_answer}'. Here is the explanation:"
        )

    explanation = question.explanation or (
        "No detailed explanation is available for this question. "
        "Review your study materials on this topic."
    )

    body = f"{opening}\n\n{explanation}"

    if follow_up:
        body += (
            f"\n\nYou asked: '{follow_up}'\n"
            "For a more detailed answer to your follow-up question, "
            "review the relevant section of your study material on "
            f"'{question.skill}'."
        )

    return body


def _build_related_topics(question: Question) -> list[str]:
    """
    Return a list of study topics related to the question's skill and domain.
    These are generated from the question metadata without needing an LLM.
    """

    topics = [
        question.skill,
        question.domain,
        f"{question.skill} fundamentals",
        f"Practice more {question.skill} questions",
    ]

    # Add difficulty-appropriate advice
    if question.difficulty <= 2:
        topics.append(f"Beginner concepts in {question.domain}")
    elif question.difficulty >= 4:
        topics.append(f"Advanced {question.skill} applications")

    return topics[:4]


# ---------------------------------------------------------------------------
# LLM-powered tutor (optional, requires OPENAI_API_KEY)
# ---------------------------------------------------------------------------

def _call_llm_tutor(
    question: Question,
    attempt: QuestionAttempt,
    follow_up: Optional[str]
) -> Optional[str]:
    """
    Call the OpenAI API to generate a personalized explanation.

    Returns the tutor's message string, or None if the call fails or
    the API key is not configured.
    """

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        import httpx

        correct_or_wrong = "correctly" if attempt.is_correct else "incorrectly"

        system_prompt = (
            "You are a patient, encouraging exam tutor helping a student "
            "understand a question they answered during an adaptive exam. "
            "Be concise (3-5 sentences), factual, and educational. "
            "Do not make up information. Use only the context provided."
        )

        user_message = (
            f"Question: {question.question_text}\n"
            f"Domain: {question.domain} | Skill: {question.skill} | "
            f"Difficulty: {question.difficulty}/5\n"
            f"Student answered: {attempt.selected_answer} ({correct_or_wrong})\n"
            f"Correct answer: {question.correct_answer}\n"
            f"Stored explanation: {question.explanation or 'Not available'}\n"
        )

        if follow_up:
            user_message += f"\nStudent's follow-up question: {follow_up}"
        else:
            user_message += (
                "\nPlease explain why the correct answer is right and "
                "what the student should study to strengthen this skill."
            )

        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": 300,
                "temperature": 0.4,
            },
            timeout=15.0,
        )

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            logger.warning(
                "OpenAI API returned %s: %s",
                response.status_code, response.text[:200]
            )
            return None

    except Exception as exc:
        logger.warning("LLM tutor call failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/explain",
    response_model=TutorResponse,
    summary="Get an AI tutor explanation for a question attempt"
)
def get_tutor_explanation(
    body: TutorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return a tutor explanation for a question the student has already answered.

    The student must have submitted an attempt for this question. This ensures
    the correct answer is only revealed after the student has committed to their
    own answer, which is required to prevent cheating.

    The tutor tries the LLM API first. If it is unavailable or not configured,
    it falls back to a rule-based explanation using the stored question text.
    Both paths return the same response structure.
    """

    # Look up the attempt and verify ownership
    attempt = db.query(QuestionAttempt).filter(
        QuestionAttempt.id == body.question_attempt_id
    ).first()

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question attempt not found."
        )

    # Students can only ask about their own attempts
    if str(attempt.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only request explanations for your own attempts."
        )

    # Load the question (the attempt already stores the ID)
    question = db.query(Question).filter(
        Question.id == attempt.question_id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found."
        )

    # Try the LLM first, fall back to rule-based
    llm_response = _call_llm_tutor(question, attempt, body.follow_up)

    if llm_response:
        tutor_message = llm_response
        source = "llm"
    else:
        tutor_message = _build_rule_based_response(
            question, attempt, body.follow_up
        )
        source = "rule_based"

    return TutorResponse(
        question_text=question.question_text,
        student_answer=attempt.selected_answer,
        correct_answer=question.correct_answer,
        was_correct=attempt.is_correct,
        explanation=question.explanation or "",
        tutor_message=tutor_message,
        related_topics=_build_related_topics(question),
        source=source,
    )


@router.get(
    "/weak-skills/{skill}",
    summary="Get study recommendations for a weak skill"
)
def get_skill_recommendations(
    skill: str,
    domain: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return a list of study recommendations for a specific skill the
    student is struggling with.

    This is a lightweight endpoint that does not call the LLM - it
    selects representative questions from the bank that cover the skill
    at appropriate difficulty levels, which the student can use as
    practice material.
    """

    # Find questions covering this skill, ordered from easiest to hardest
    query = db.query(Question).filter(
        Question.skill == skill,
        Question.is_active == True,
        Question.approval_status == "approved"
    )

    if domain:
        query = query.filter(Question.domain == domain)

    questions = query.order_by(Question.difficulty.asc()).limit(10).all()

    if not questions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active questions found for skill: {skill}"
        )

    # Count how many the student has already attempted
    attempted_ids = {
        str(a.question_id)
        for a in db.query(QuestionAttempt.question_id)
        .filter(QuestionAttempt.user_id == current_user.id)
        .all()
    }

    recommendations = []
    for q in questions:
        recommendations.append({
            "question_id": str(q.id),
            "difficulty": q.difficulty,
            "already_attempted": str(q.id) in attempted_ids,
            "domain": q.domain,
            "skill": q.skill,
        })

    return {
        "skill": skill,
        "domain": domain,
        "total_questions_available": len(questions),
        "recommendations": recommendations,
        "study_tip": (
            f"Focus on difficulty 1-2 questions in '{skill}' first to build "
            f"your foundation, then progress to harder questions as your "
            f"mastery improves."
        )
    }
