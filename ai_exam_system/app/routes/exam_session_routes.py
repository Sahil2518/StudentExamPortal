import uuid
"""
Exam session routes.

Students use these routes to start, manage, and finish exam sessions.
Each session tracks which questions were answered, their correctness,
timing, and links all proctoring events together.

A student may only see their own sessions. The server calculates
all scores - the client never submits a correctness value.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database.connection import get_db
from app.dependencies.current_user import get_current_user, require_admin
from app.models.user import User
from app.models.exam_session import ExamSession
from app.models.question_attempt import QuestionAttempt
from app.models.question import Question
from app.services.adaptive_engine import get_skill_state


router = APIRouter(prefix="/exam-sessions", tags=["Exam Sessions"])


# ---------------------------------------------------------------------------
# Pydantic schemas for exam session requests and responses
# ---------------------------------------------------------------------------

class ExamSessionCreate(BaseModel):
    """Input to start a new exam session."""

    # Domain to be examined
    domain: str = Field(..., min_length=2, max_length=200)

    # Skill within the domain (optional - None means the whole domain)
    skill: Optional[str] = Field(default=None, max_length=200)

    # Maximum number of questions before the session auto-finishes
    max_questions: int = Field(default=10, ge=1, le=300)

    # Optional time limit in seconds (None means no limit)
    time_limit_seconds: Optional[int] = Field(default=None, ge=60, le=28800)

    # Exam mode: "practice" (adaptive, default) or "live" (fixed entrance exam like JEE/NEET/CAT)
    exam_type: Optional[str] = Field(default="practice", max_length=20)
    positive_mark: Optional[float] = Field(default=4.0, ge=0.0)
    negative_mark: Optional[float] = Field(default=1.0, ge=0.0)
    exam_paper_title: Optional[str] = Field(default=None, max_length=255)


class LiveExamAnswerInput(BaseModel):
    """Input body for live entrance exam question saving."""
    question_id: uuid.UUID
    selected_option: Optional[str] = None
    review_status: str = Field(default="answered")
    time_taken: Optional[int] = 0


class ExamSessionResponse(BaseModel):
    """Summary of an exam session returned to the student."""

    id: str
    domain: str
    skill: Optional[str]
    max_questions: int
    time_limit_seconds: Optional[int]
    status: str
    exam_type: str = "practice"
    positive_mark: float = 4.0
    negative_mark: float = 1.0
    negative_marks_total: float = 0.0
    raw_score: Optional[float] = None
    total_score: Optional[float] = None
    exam_paper_title: Optional[str] = None
    questions_answered: int
    correct_count: int
    accuracy: Optional[float]
    risk_score: Optional[float]
    started_at: str
    finished_at: Optional[str]

    # Allow this model to be constructed from ORM objects
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_session_ownership(session: ExamSession, user: User):
    """
    Raise 403 if the session does not belong to the requesting user.

    This prevents one student from accessing another student's session.
    """

    if session.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this exam session"
        )


def _build_session_response(session: ExamSession) -> dict:
    """Convert an ExamSession ORM object to a safe dict for the response."""

    return {
        "id": str(session.id),
        "domain": session.domain,
        "skill": session.skill,
        "max_questions": session.max_questions,
        "time_limit_seconds": session.time_limit_seconds,
        "status": session.status,
        "exam_type": getattr(session, "exam_type", "practice") or "practice",
        "positive_mark": getattr(session, "positive_mark", 4.0),
        "negative_mark": getattr(session, "negative_mark", 1.0),
        "negative_marks_total": getattr(session, "negative_marks_total", 0.0),
        "raw_score": getattr(session, "raw_score", None),
        "total_score": session.total_score,
        "exam_paper_title": getattr(session, "exam_paper_title", None),
        "questions_answered": session.questions_answered,
        "correct_count": session.correct_count,
        "accuracy": session.accuracy,
        "risk_score": session.risk_score,
        "flagged_for_review": session.flagged_for_review,
        "started_at": session.started_at.isoformat()
        if session.started_at else None,
        "finished_at": session.finished_at.isoformat()
        if session.finished_at else None,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Start a new exam session"
)
def start_exam_session(
    body: ExamSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new exam session for the authenticated student.

    Returns the session id which must be included in all subsequent
    question-attempt submissions for this exam.

    A student cannot start a new session in the same domain/skill
    while another session is still active.
    """

    # Check for an already-active session in this domain
    active = (
        db.query(ExamSession)
        .filter(
            ExamSession.user_id == current_user.id,
            ExamSession.domain == body.domain,
            ExamSession.status == "active"
        )
        .first()
    )

    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You already have an active session in domain "
                f"'{body.domain}'. Finish it before starting a new one."
            )
        )

    # Create the session
    session = ExamSession(
        user_id=current_user.id,
        domain=body.domain,
        skill=body.skill,
        max_questions=body.max_questions,
        time_limit_seconds=body.time_limit_seconds,
        exam_type=body.exam_type or "practice",
        positive_mark=body.positive_mark if body.positive_mark is not None else 4.0,
        negative_mark=body.negative_mark if body.negative_mark is not None else 1.0,
        exam_paper_title=body.exam_paper_title or f"{body.domain} Entrance Examination",
        status="active"
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    # If it is a LIVE entrance exam (JEE/NEET/CAT), issue all fixed questions immediately
    # so every student taking this exam receives the EXACT SAME questions!
    if session.exam_type == "live":
        from app.models.exam_session_question import ExamSessionQuestion
        query = db.query(Question).filter(
            Question.domain == session.domain,
            Question.is_active == True,
            Question.approval_status == "approved"
        )
        if session.skill:
            query = query.filter(Question.skill == session.skill)

        # Deterministic ordering so all students taking this live exam get identical questions
        fixed_questions = query.order_by(Question.id.asc()).limit(session.max_questions).all()

        # If database has fewer questions than requested for this entrance exam domain/skill,
        # dynamically synthesize and persist them calibrated to this specific exam!
        needed = session.max_questions - len(fixed_questions)
        if needed > 0:
            from app.services.llm_question_generator import generate_and_persist_batch
            new_qs = generate_and_persist_batch(
                db=db,
                domain=session.domain,
                skill=session.skill,
                count=needed,
                target_difficulty=0.2,
                exam_name=session.exam_paper_title
            )
            fixed_questions.extend(new_qs)

        # Deterministic ordering so all students taking this live exam get identical questions
        fixed_questions.sort(key=lambda x: (x.created_at or datetime.min, str(x.id)))

        for idx, q in enumerate(fixed_questions, start=1):
            issuance = ExamSessionQuestion(
                exam_session_id=session.id,
                question_id=q.id,
                sequence_number=idx,
                selection_policy="fixed_live_entrance",
                status="served",
                review_status="not_visited"
            )
            db.add(issuance)
        db.commit()

    return _build_session_response(session)


@router.get(
    "",
    summary="List the authenticated student's exam sessions"
)
def list_exam_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Return all exam sessions belonging to the authenticated student,
    ordered most recent first.
    """

    sessions = (
        db.query(ExamSession)
        .filter(ExamSession.user_id == current_user.id)
        .order_by(ExamSession.started_at.desc())
        .all()
    )

    return [_build_session_response(s) for s in sessions]


@router.get(
    "/{session_id}",
    summary="Get a specific exam session"
)
def get_exam_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Return one exam session. Raises 404 if not found, 403 if not owned
    by the authenticated user.
    """

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found"
        )

    _check_session_ownership(session, current_user)

    return _build_session_response(session)


@router.get(
    "/{session_id}/next-question",
    summary="Get the next adaptive question for an active session"
)
def get_next_session_question(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the next question selected by the adaptive engine for this session.
    Verifies time limits and question limits.
    Does NOT include the correct_answer in the response.
    """
    
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found"
        )

    _check_session_ownership(session, current_user)

    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session is {session.status}, cannot get next question."
        )

    # Enforce time limit
    if session.time_limit_seconds and session.started_at:
        from datetime import datetime, timezone
        started = session.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        grace_seconds = 30
        if elapsed > (session.time_limit_seconds + grace_seconds):
            session.status = "expired"
            session.finished_at = datetime.now(timezone.utc)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail=f"Time limit exceeded. Session expired. Elapsed: {int(elapsed)}s, Limit: {session.time_limit_seconds}s"
            )

    # Check question limit
    if session.questions_answered >= session.max_questions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Maximum number of questions reached for this session."
        )

    # For LIVE entrance exams (JEE/NEET/CAT), serve from the pre-issued fixed question paper
    if session.exam_type == "live":
        from app.models.exam_session_question import ExamSessionQuestion
        unanswered_issuance = (
            db.query(ExamSessionQuestion)
            .filter(
                ExamSessionQuestion.exam_session_id == session.id,
                ExamSessionQuestion.status == "served"
            )
            .order_by(ExamSessionQuestion.sequence_number.asc())
            .first()
        )
        if not unanswered_issuance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="All questions in this live entrance paper have been served or answered."
            )
        q = db.query(Question).filter(Question.id == unanswered_issuance.question_id).first()
        return {
            "id": str(q.id),
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": q.options,
            "domain": q.domain,
            "skill": q.skill,
            "difficulty": q.difficulty,
            "sequence_number": unanswered_issuance.sequence_number,
        }

    # Get already answered question IDs
    from app.models.exam_session_question import ExamSessionQuestion
    answered = db.query(ExamSessionQuestion).filter(
        ExamSessionQuestion.exam_session_id == session.id
    ).all()
    answered_ids = {str(a.question_id) for a in answered if a.status in ("answered", "served")}

    # Call adaptive engine
    from app.services.adaptive_engine import select_next_question
    next_q = select_next_question(
        db=db,
        user_id=current_user.id,
        domain=session.domain,
        skill=session.skill,
        exam_session_id=str(session.id)
    )

    if not next_q:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No more eligible questions available for this domain/skill."
        )

    # Create issuance record
    seq = len(answered) + 1
    issuance = ExamSessionQuestion(
        exam_session_id=session.id,
        question_id=next_q.id,
        sequence_number=seq,
        status="served"
    )
    db.add(issuance)
    db.commit()
    db.refresh(next_q)

    # Return question safely (hide correct answer)
    return {
        "id": str(next_q.id),
        "question_text": next_q.question_text,
        "question_type": next_q.question_type,
        "options": next_q.options,
        "domain": next_q.domain,
        "skill": next_q.skill,
        "difficulty": next_q.difficulty,
        "sequence_number": seq,
    }


# ---------------------------------------------------------------------------
# Live Entrance Exam Endpoints (JEE / NEET / CAT Palette & Navigation)
# ---------------------------------------------------------------------------

@router.get(
    "/{session_id}/live-palette",
    summary="Get the full question palette for a live entrance exam session"
)
def get_live_palette(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the complete Question Palette for JEE/NEET/CAT live entrance exams.
    Lists every question sequence number and its current review/answer status:
    - not_visited
    - not_answered
    - answered
    - marked_for_review
    """
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
    _check_session_ownership(session, current_user)

    from app.models.exam_session_question import ExamSessionQuestion
    issued = (
        db.query(ExamSessionQuestion)
        .filter(ExamSessionQuestion.exam_session_id == session.id)
        .order_by(ExamSessionQuestion.sequence_number.asc())
        .all()
    )

    return {
        "session_id": str(session.id),
        "exam_type": session.exam_type,
        "exam_paper_title": session.exam_paper_title,
        "domain": session.domain,
        "positive_mark": session.positive_mark,
        "negative_mark": session.negative_mark,
        "max_questions": session.max_questions,
        "time_limit_seconds": session.time_limit_seconds,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "status": session.status,
        "palette": [
            {
                "sequence_number": item.sequence_number,
                "question_id": str(item.question_id),
                "review_status": item.review_status,
                "selected_option": item.selected_option,
                "status": item.status,
            }
            for item in issued
        ]
    }


@router.get(
    "/{session_id}/question-by-seq/{sequence_number}",
    summary="Get question by sequence number for live entrance exam"
)
def get_question_by_seq(
    session_id: uuid.UUID,
    sequence_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches a specific question from the question palette by sequence number.
    Does NOT return correct_answer or explanation to prevent exam leakage.
    """
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
    _check_session_ownership(session, current_user)

    from app.models.exam_session_question import ExamSessionQuestion
    issuance = (
        db.query(ExamSessionQuestion)
        .filter(
            ExamSessionQuestion.exam_session_id == session.id,
            ExamSessionQuestion.sequence_number == sequence_number
        )
        .first()
    )
    if not issuance:
        raise HTTPException(status_code=404, detail="Question number not found in this paper")

    # Mark as visited if it was not_visited
    if issuance.review_status == "not_visited":
        issuance.review_status = "not_answered"
        db.commit()

    q = db.query(Question).filter(Question.id == issuance.question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question content not found")

    return {
        "sequence_number": issuance.sequence_number,
        "question_id": str(q.id),
        "question_text": q.question_text,
        "options": q.options,
        "domain": q.domain,
        "skill": q.skill,
        "difficulty": q.difficulty,
        "selected_option": issuance.selected_option,
        "review_status": issuance.review_status
    }


@router.post(
    "/{session_id}/live-answer",
    summary="Save answer or update review status during a live entrance exam"
)
def save_live_answer(
    session_id: uuid.UUID,
    body: LiveExamAnswerInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Saves or clears an answer for a question in a live entrance exam.
    Enforces time limits, calculates correctness internally, and prevents answer leakage.
    Supports 'Save & Next', 'Mark for Review', and 'Clear Response'.
    """
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
    _check_session_ownership(session, current_user)

    if session.status != "active":
        raise HTTPException(status_code=409, detail=f"Session is {session.status}, cannot save answer")

    # Time limit check
    if session.time_limit_seconds and session.started_at:
        from datetime import datetime, timezone
        started = session.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        if elapsed > (session.time_limit_seconds + 30):
            session.status = "expired"
            session.finished_at = datetime.now(timezone.utc)
            db.commit()
            raise HTTPException(status_code=410, detail="Time limit exceeded. Session expired.")

    from app.models.exam_session_question import ExamSessionQuestion
    issuance = (
        db.query(ExamSessionQuestion)
        .filter(
            ExamSessionQuestion.exam_session_id == session.id,
            ExamSessionQuestion.question_id == body.question_id
        )
        .first()
    )
    if not issuance:
        raise HTTPException(status_code=403, detail="Question was not issued to this exam session")

    q = db.query(Question).filter(Question.id == body.question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    from datetime import datetime, timezone
    issuance.answered_at = datetime.now(timezone.utc)
    issuance.selected_option = body.selected_option
    issuance.review_status = body.review_status

    if body.selected_option:
        issuance.status = "answered"
        issuance.is_correct = (body.selected_option.strip().lower() == q.correct_answer.strip().lower())
    else:
        # Clear response
        issuance.status = "served"
        issuance.is_correct = None
        if body.review_status != "marked_for_review":
            issuance.review_status = "not_answered"

    # Upsert QuestionAttempt so attempts table stays synchronized
    attempt = (
        db.query(QuestionAttempt)
        .filter(
            QuestionAttempt.exam_session_id == session.id,
            QuestionAttempt.question_id == q.id
        )
        .first()
    )
    if body.selected_option:
        if attempt:
            attempt.selected_answer = body.selected_option
            attempt.is_correct = issuance.is_correct
            attempt.time_taken = body.time_taken or 0
        else:
            attempt = QuestionAttempt(
                user_id=current_user.id,
                exam_session_id=session.id,
                question_id=q.id,
                selected_answer=body.selected_option,
                is_correct=issuance.is_correct,
                time_taken=body.time_taken or 0
            )
            db.add(attempt)
    else:
        # If response was cleared, remove the attempt
        if attempt:
            db.delete(attempt)

    db.commit()

    return {
        "status": "saved",
        "sequence_number": issuance.sequence_number,
        "selected_option": issuance.selected_option,
        "review_status": issuance.review_status
    }


@router.post(
    "/{session_id}/finish",
    summary="Finish an active exam session"
)
def finish_exam_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark an active exam session as finished.

    Calculates final accuracy, generates personalized recommendations,
    and returns the full results.

    Once finished, no further question attempts can be linked to this
    session.
    """

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found"
        )

    _check_session_ownership(session, current_user)

    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session is already '{session.status}' and cannot be finished again"
        )

    # For LIVE entrance exams, compute JEE/NEET/CAT scorecard with negative marking
    if session.exam_type == "live":
        from app.models.exam_session_question import ExamSessionQuestion
        issued = (
            db.query(ExamSessionQuestion)
            .filter(ExamSessionQuestion.exam_session_id == session.id)
            .all()
        )
        answered_items = [i for i in issued if i.selected_option is not None]
        correct_count = sum(1 for i in answered_items if i.is_correct is True)
        incorrect_count = sum(1 for i in answered_items if i.is_correct is False)
        unattempted_count = len(issued) - len(answered_items)

        pos_mark = session.positive_mark if session.positive_mark is not None else 4.0
        neg_mark = session.negative_mark if session.negative_mark is not None else 1.0
        raw_score = (correct_count * pos_mark) - (incorrect_count * neg_mark)

        session.status = "finished"
        session.finished_at = datetime.now(timezone.utc)
        session.questions_answered = len(answered_items)
        session.correct_count = correct_count
        session.accuracy = round((correct_count / len(answered_items)), 4) if answered_items else 0.0
        session.raw_score = raw_score
        session.total_score = raw_score
        session.negative_marks_total = incorrect_count * neg_mark

        recommendations = _generate_recommendations(
            db=db,
            user_id=current_user.id,
            domain=session.domain,
            skill=session.skill
        )
        session.recommendations = recommendations

        db.commit()
        db.refresh(session)

        return {
            **_build_session_response(session),
            "scorecard": {
                "raw_score": raw_score,
                "positive_marks_earned": correct_count * pos_mark,
                "negative_marks_deducted": incorrect_count * neg_mark,
                "max_possible_marks": len(issued) * pos_mark,
                "correct_count": correct_count,
                "incorrect_count": incorrect_count,
                "unattempted_count": unattempted_count,
                "total_questions": len(issued),
            },
            "recommendations": recommendations
        }

    # Count attempts and correct answers in this session
    attempts = (
        db.query(QuestionAttempt)
        .filter(QuestionAttempt.exam_session_id == session.id)
        .all()
    )

    total = len(attempts)
    correct = sum(1 for a in attempts if a.is_correct)

    accuracy = (correct / total) if total > 0 else 0.0

    # Update session state
    session.status = "finished"
    session.finished_at = datetime.now(timezone.utc)
    session.questions_answered = total
    session.correct_count = correct
    session.accuracy = round(accuracy, 4)

    # Generate simple recommendations based on performance
    recommendations = _generate_recommendations(
        db=db,
        user_id=current_user.id,
        domain=session.domain,
        skill=session.skill
    )

    session.recommendations = recommendations

    db.commit()
    db.refresh(session)

    return {
        **_build_session_response(session),
        "recommendations": recommendations
    }


@router.get(
    "/{session_id}/results",
    summary="Get detailed results for a finished session"
)
def get_session_results(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Return full results for a finished exam session including:
    - Summary statistics
    - Per-question breakdown with explanations
    - Personalized recommendations
    - Skill mastery state after the exam
    """

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found"
        )

    _check_session_ownership(session, current_user)

    if session.status == "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam session is still active. Finish it first to see results."
        )

    # Load all attempts for this session with their questions
    attempts = (
        db.query(QuestionAttempt)
        .filter(QuestionAttempt.exam_session_id == session.id)
        .order_by(QuestionAttempt.created_at.asc())
        .all()
    )

    # Build per-question result entries.
    # The correct_answer is now safe to include because the session is finished.
    question_results = []

    for attempt in attempts:
        q = db.query(Question).filter(
            Question.id == attempt.question_id
        ).first()

        if not q:
            continue

        question_results.append({
            "question_id": str(q.id),
            "question_text": q.question_text,
            "domain": q.domain,
            "skill": q.skill,
            "difficulty": q.difficulty,
            "options": q.options,
            "selected_answer": attempt.selected_answer,
            "correct_answer": q.correct_answer,
            "is_correct": attempt.is_correct,
            "time_taken": attempt.time_taken,
            "explanation": q.explanation,
        })

    # Skill mastery after the exam
    mastery_state = get_skill_state(
        db=db,
        user_id=current_user.id,
        domain=session.domain,
        skill=session.skill or ""
    )

    scorecard = None
    if session.exam_type == "live":
        pos_mark = session.positive_mark or 4.0
        neg_mark = session.negative_mark or 1.0
        incorrect_count = max(0, session.questions_answered - session.correct_count)
        total_questions = session.max_questions
        unattempted_count = max(0, total_questions - session.questions_answered)
        scorecard = {
            "raw_score": session.raw_score if session.raw_score is not None else (session.correct_count * pos_mark - incorrect_count * neg_mark),
            "positive_marks_earned": session.correct_count * pos_mark,
            "negative_marks_deducted": session.negative_marks_total,
            "max_possible_marks": total_questions * pos_mark,
            "correct_count": session.correct_count,
            "incorrect_count": incorrect_count,
            "unattempted_count": unattempted_count,
            "total_questions": total_questions,
        }

    return {
        **_build_session_response(session),
        "question_results": question_results,
        "skill_mastery": mastery_state,
        "scorecard": scorecard,
        "recommendations": session.recommendations or []
    }


# ---------------------------------------------------------------------------
# Admin-only: list all sessions
# ---------------------------------------------------------------------------

@router.get(
    "/admin/all",
    summary="Admin: list all exam sessions across all students"
)
def admin_list_all_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Returns all exam sessions for all students.

    Requires admin role. Used for monitoring and review assignment.
    """

    sessions = (
        db.query(ExamSession)
        .order_by(ExamSession.started_at.desc())
        .limit(200)
        .all()
    )

    return [_build_session_response(s) for s in sessions]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _generate_recommendations(
    db: Session,
    user_id,
    domain: str,
    skill: Optional[str]
) -> list:
    """
    Generate a simple list of practice recommendations based on
    the student's current skill state.

    This function uses the current mastery and retention values
    to identify weak areas. It does not fabricate learning gains.
    """

    recommendations = []

    # Determine which skills to assess
    if skill:
        skills_to_check = [(domain, skill)]
    else:
        # Find all skills attempted by this student in this domain
        pairs = (
            db.query(Question.domain, Question.skill)
            .join(QuestionAttempt, QuestionAttempt.question_id == Question.id)
            .filter(
                QuestionAttempt.user_id == user_id,
                Question.domain == domain
            )
            .distinct()
            .all()
        )
        skills_to_check = [(p.domain, p.skill) for p in pairs]

    for d, s in skills_to_check:

        state = get_skill_state(db=db, user_id=user_id, domain=d, skill=s)

        mastery = state.get("mastery", 0.5)
        retention = state.get("retention", 1.0)
        effective = state.get("effective_knowledge", mastery)

        if effective < 0.50:
            priority = "high"
            suggestion = (
                f"Your effective knowledge of '{s}' is low "
                f"({round(effective * 100)}%). Practice easy questions "
                f"to rebuild confidence."
            )
        elif effective < 0.75:
            priority = "medium"
            suggestion = (
                f"'{s}' is at moderate level ({round(effective * 100)}%). "
                f"Try medium-difficulty questions to strengthen this skill."
            )
        else:
            priority = "low"
            suggestion = (
                f"'{s}' looks strong ({round(effective * 100)}%). "
                f"Challenge yourself with harder questions."
            )

        recommendations.append({
            "domain": d,
            "skill": s,
            "priority": priority,
            "mastery": round(mastery, 3),
            "retention": round(retention, 3),
            "effective_knowledge": round(effective, 3),
            "suggestion": suggestion
        })

    # Sort by priority: high first
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(
        key=lambda r: priority_order.get(r["priority"], 3)
    )

    return recommendations
import uuid
