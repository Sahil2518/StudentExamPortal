"""
Question attempt submission route.

Students submit their answers here during an active exam session.
The server:
  1. Validates the session is active and belongs to the student
  2. Checks the question exists and is active
  3. Prevents duplicate submissions for the same question in the same session
  4. Calculates correctness server-side (never trusts client)
  5. Updates session counters atomically in one transaction
  6. Returns the result including the correct answer and explanation

The correct_answer is only returned AFTER the student submits,
not before.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from app.database.connection import get_db
from app.dependencies.current_user import get_current_user

from app.models.user import User
from app.models.question import Question
from app.models.question_attempt import QuestionAttempt
from app.models.exam_session import ExamSession


router = APIRouter(tags=["Question Attempts"])


import uuid

class QuestionAttemptCreate(BaseModel):
    """Request body for submitting a question answer."""

    # Which question is being answered
    question_id: uuid.UUID = Field(...)

    # The answer string the student chose
    selected_answer: str = Field(..., min_length=1, max_length=500)

    # How long (in seconds) the student spent on this question
    time_taken: int = Field(..., ge=0, le=3600)

    # The exam session this attempt belongs to.
    # Required for session-based exams; optional for standalone practice.
    exam_session_id: Optional[uuid.UUID] = Field(default=None)


@router.post("/question-attempts", status_code=status.HTTP_201_CREATED)
def submit_question_attempt(
    attempt: QuestionAttemptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit an answer to a question.

    Returns:
    - Whether the answer was correct
    - The correct answer
    - The explanation
    - Updated session progress if within a session
    """

    # Load the question from the database
    question = db.query(Question).filter(
        Question.id == attempt.question_id
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    if not question.is_active:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This question is no longer active"
        )

    # If a session id is provided, validate it
    exam_session = None

    if attempt.exam_session_id:

        exam_session = db.query(ExamSession).filter(
            ExamSession.id == attempt.exam_session_id
        ).first()

        if not exam_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exam session not found"
            )

        # Ensure the session belongs to this student
        if exam_session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This exam session does not belong to you"
            )

        # Ensure the session is still active
        if exam_session.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This exam session is no longer active"
            )

        # Server-side time limit enforcement
        if exam_session.time_limit_seconds and exam_session.started_at:
            from datetime import datetime, timezone
            started = exam_session.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            grace_seconds = 30
            if elapsed > (exam_session.time_limit_seconds + grace_seconds):
                exam_session.status = "expired"
                exam_session.finished_at = datetime.now(timezone.utc)
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail=f"Time limit exceeded. Session expired. Elapsed: {int(elapsed)}s, Limit: {exam_session.time_limit_seconds}s"
                )

        # Verify the question was actually issued to this session
        from app.models.exam_session_question import ExamSessionQuestion
        issuance_record = db.query(ExamSessionQuestion).filter(
            ExamSessionQuestion.exam_session_id == exam_session.id,
            ExamSessionQuestion.question_id == attempt.question_id
        ).first()

        if not issuance_record:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This question was not issued to your exam session"
            )

        if issuance_record.status != "served":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already answered this question in this session"
            )

        # Check if the session has reached its question limit
        if exam_session.questions_answered >= exam_session.max_questions:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This session has reached its maximum question limit. "
                    "Please finish the session."
                )
            )

    # Server-side correctness check - never trust the client
    is_correct = (
        attempt.selected_answer.strip().lower()
        == question.correct_answer.strip().lower()
    )

    # Create the attempt record
    new_attempt = QuestionAttempt(
        user_id=current_user.id,
        exam_session_id=exam_session.id if exam_session else None,
        question_id=attempt.question_id,
        selected_answer=attempt.selected_answer,
        is_correct=is_correct,
        time_taken=attempt.time_taken
    )

    db.add(new_attempt)

    # Update session counters if this attempt belongs to a session
    if exam_session:
        from datetime import datetime, timezone
        issuance_record.status = "answered"
        issuance_record.answered_at = datetime.now(timezone.utc)
        
        exam_session.questions_answered += 1

        if is_correct:
            exam_session.correct_count += 1

        # Auto-finish the session if the max question limit is reached
        if exam_session.questions_answered >= exam_session.max_questions:
            from datetime import datetime, timezone
            exam_session.status = "finished"
            exam_session.finished_at = datetime.now(timezone.utc)

            total = exam_session.questions_answered
            correct = exam_session.correct_count
            exam_session.accuracy = round(
                (correct / total) if total > 0 else 0.0,
                4
            )

    # We flush the attempt to get its ID generated without committing.
    db.flush()
    
    # PROBLEM 1: Feed actual outcome back into the contextual bandit in the SAME transaction.
    from ml.contextual_bandit import get_bandit
    bandit = get_bandit()
    bandit.update(
        db=db,
        skill=question.skill,
        difficulty=question.difficulty,
        was_correct=is_correct,
        attempt_id=new_attempt.id,
        auto_commit=False
    )
    
    # Commit both the attempt and the bandit update transactionally.
    db.commit()
    db.refresh(new_attempt)

    # Build the response.
    # The correct answer is now safe to return because the student has submitted.
    response = {
        "attempt_id": str(new_attempt.id),
        "question_id": str(question.id),
        "selected_answer": attempt.selected_answer,
        "is_correct": is_correct,
        "correct_answer": question.correct_answer,
        "explanation": question.explanation,
        "time_taken": attempt.time_taken,
    }

    # Include session progress if within a session
    if exam_session:
        db.refresh(exam_session)
        response["session"] = {
            "id": str(exam_session.id),
            "status": exam_session.status,
            "questions_answered": exam_session.questions_answered,
            "max_questions": exam_session.max_questions,
            "correct_count": exam_session.correct_count,
        }

    return response