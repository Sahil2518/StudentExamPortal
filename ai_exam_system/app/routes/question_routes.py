"""
Question bank management routes.

Public (authenticated) routes:
  GET /questions         - list active questions with optional filters
  GET /questions/{id}    - get one question (without correct answer)
  GET /questions/recommend - get a profile-based recommendation

Admin-only routes:
  POST /questions           - create a question
  PATCH /questions/{id}     - update a question
  DELETE /questions/{id}    - deactivate a question

The correct_answer field is NEVER returned to students in list/get
responses. It is only included in admin responses and in attempt
result responses after submission.
"""

import random

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

from app.database.connection import get_db
from app.models.student_profile import StudentProfile
from app.models.question import Question
from app.dependencies.current_user import get_current_user, require_admin
from app.models.user import User


router = APIRouter(tags=["Questions"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class QuestionCreate(BaseModel):
    """Input for creating a new question (admin only)."""

    question_text: str = Field(..., min_length=10)
    domain: str = Field(..., min_length=2, max_length=200)
    skill: str = Field(..., min_length=2, max_length=200)
    difficulty: int = Field(..., ge=1, le=5)
    minimum_level: int = Field(..., ge=1, le=5)
    maximum_level: int = Field(..., ge=1, le=5)
    options: List[str] = Field(..., min_length=2)
    correct_answer: str = Field(..., min_length=1)
    explanation: Optional[str] = None
    question_type: str = Field(default="multiple_choice")

    def model_post_init(self, __context):
        # Validate that difficulty sits within the stated level range
        if self.minimum_level > self.maximum_level:
            raise ValueError(
                "minimum_level cannot be greater than maximum_level"
            )
        if not (self.minimum_level <= self.difficulty <= self.maximum_level):
            raise ValueError(
                "difficulty must be between minimum_level and maximum_level"
            )


class QuestionUpdate(BaseModel):
    """Input for updating an existing question (admin only)."""

    question_text: Optional[str] = None
    domain: Optional[str] = None
    skill: Optional[str] = None
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)
    minimum_level: Optional[int] = Field(default=None, ge=1, le=5)
    maximum_level: Optional[int] = Field(default=None, ge=1, le=5)
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    is_active: Optional[bool] = None
    approval_status: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_question(q: Question, include_answer: bool = False) -> dict:
    """
    Convert a Question ORM object to a response dict.

    By default, the correct_answer is excluded to prevent leaking
    answers to students. Pass include_answer=True for admin responses
    or post-submission result responses.
    """

    data = {
        "id": str(q.id),
        "question_text": q.question_text,
        "domain": q.domain,
        "skill": q.skill,
        "difficulty": q.difficulty,
        "minimum_level": q.minimum_level,
        "maximum_level": q.maximum_level,
        "options": q.options,
        "question_type": q.question_type,
        "explanation": q.explanation if include_answer else None,
        "source": q.source,
        "approval_status": q.approval_status,
        "is_active": q.is_active,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }

    if include_answer:
        data["correct_answer"] = q.correct_answer

    return data


# ---------------------------------------------------------------------------
# Public routes (any authenticated user)
# ---------------------------------------------------------------------------

@router.get("/questions", summary="List active questions")
def get_questions(
    domain: Optional[str] = Query(default=None),
    skill: Optional[str] = Query(default=None),
    difficulty: Optional[int] = Query(default=None, ge=1, le=5),
    approval_status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List questions from the question bank.

    Students see active, approved questions without correct answers.
    Admins additionally see inactive and pending questions, with answers.
    """

    query = db.query(Question)

    is_admin = current_user.role == "admin"

    # Non-admins only see active, approved questions
    if not is_admin:
        query = query.filter(
            Question.is_active == True,
            Question.approval_status == "approved"
        )
    else:
        # Admins can filter by approval_status
        if approval_status:
            query = query.filter(
                Question.approval_status == approval_status
            )

    if domain:
        query = query.filter(Question.domain == domain)

    if skill:
        query = query.filter(Question.skill == skill)

    if difficulty:
        query = query.filter(
            Question.minimum_level <= difficulty,
            Question.maximum_level >= difficulty
        )

    total = query.count()
    questions = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "questions": [
            _safe_question(q, include_answer=is_admin)
            for q in questions
        ]
    }


@router.get("/questions/recommend", summary="Get a profile-based question recommendation")
def recommend_question(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Suggest a question based on the student's profile preferences.

    Requires the student to have a completed profile. Returns one
    randomly selected question matching the preferred domain and
    difficulty. Does not expose the correct answer.
    """

    profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found. Please complete your profile first."
        )

    difficulty_map = {
        "Easy": 1,
        "Medium": 3,
        "Hard": 5
    }

    difficulty = difficulty_map.get(profile.preferred_difficulty)

    if difficulty is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile has an invalid preferred_difficulty value"
        )

    questions = db.query(Question).filter(
        Question.domain == profile.preferred_domain,
        Question.minimum_level <= difficulty,
        Question.maximum_level >= difficulty,
        Question.is_active == True,
        Question.approval_status == "approved"
    ).all()

    if not questions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No suitable questions found for your profile"
        )

    selected = random.choice(questions)
    return _safe_question(selected, include_answer=False)


@router.get("/questions/{question_id}", summary="Get one question by id")
def get_question(
    question_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Return a single question.

    Students do not receive the correct answer.
    Admins receive the full question including the answer.
    """

    question = db.query(Question).filter(
        Question.id == question_id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    is_admin = current_user.role == "admin"

    # Non-admins cannot access inactive or unapproved questions
    if not is_admin and (
        not question.is_active or question.approval_status != "approved"
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    return _safe_question(question, include_answer=is_admin)


# ---------------------------------------------------------------------------
# Admin-only routes
# ---------------------------------------------------------------------------

@router.post(
    "/questions",
    status_code=status.HTTP_201_CREATED,
    summary="Admin: create a question"
)
def create_question(
    question: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new question in the question bank.

    Requires admin role. The question is immediately set to active
    and approved status.
    """

    new_question = Question(
        question_text=question.question_text,
        domain=question.domain,
        skill=question.skill,
        difficulty=question.difficulty,
        minimum_level=question.minimum_level,
        maximum_level=question.maximum_level,
        options=question.options,
        correct_answer=question.correct_answer,
        explanation=question.explanation,
        question_type=question.question_type,
        source="manual",
        approval_status="approved",
        approved_by=str(current_user.id),
        is_active=True
    )

    db.add(new_question)
    db.commit()
    db.refresh(new_question)

    # Return the full question (including answer) to the admin
    return _safe_question(new_question, include_answer=True)


@router.patch(
    "/questions/{question_id}",
    summary="Admin: update a question"
)
def update_question(
    question_id: str,
    updates: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update one or more fields of an existing question.

    Requires admin role. Only the fields provided in the request body
    are changed.
    """

    question = db.query(Question).filter(
        Question.id == question_id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    # Apply only the fields that were explicitly provided
    update_data = updates.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(question, field, value)

    db.commit()
    db.refresh(question)

    return _safe_question(question, include_answer=True)


@router.delete(
    "/questions/{question_id}",
    summary="Admin: deactivate a question"
)
def deactivate_question(
    question_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Deactivate a question so it is no longer served to students.

    The question record is kept in the database to preserve the
    historical record of past attempts. Use PATCH to reactivate.
    """

    question = db.query(Question).filter(
        Question.id == question_id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    if not question.is_active:
        return {"message": "Question was already inactive"}

    question.is_active = False
    db.commit()

    return {"message": "Question deactivated successfully"}


class QuestionAIGenerateRequest(BaseModel):
    domain: str = Field(..., min_length=2, max_length=200)
    skill: Optional[str] = Field(default=None, max_length=200)
    target_difficulty: Optional[float] = Field(default=0.0, ge=-3.0, le=3.0)


@router.post(
    "/questions/generate-ai",
    status_code=status.HTTP_201_CREATED,
    summary="Generate a novel calibrated practice question via LLM"
)
def generate_ai_question(
    body: QuestionAIGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Synthesize a calibrated multiple choice question via LLM (OpenAI gpt-4o-mini).
    Persists and returns the question directly.
    """
    from app.services.llm_question_generator import generate_and_persist_question
    q = generate_and_persist_question(
        db=db,
        domain=body.domain,
        skill=body.skill,
        target_difficulty=body.target_difficulty or 0.0
    )
    if not q:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to synthesize question with AI model."
        )
    return _safe_question(q, include_answer=current_user.role in ("admin", "reviewer"))
