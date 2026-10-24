"""
Proctoring event routes.

Students submit browser and camera monitoring signals here during exams.
Reviewers and admins use these routes to inspect flags and record decisions.

Each event is a risk signal, not proof of misconduct. Human review is
required before any action is taken against a student.

Security notes:
  - Students can only submit events for their own active sessions
  - Students cannot read their own proctoring events (to avoid gaming)
  - Only reviewers and admins can read events and make decisions
  - Evidence references are never exposed to students
"""

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database.connection import get_db
from app.dependencies.current_user import (
    get_current_user,
    require_reviewer,
    require_admin
)
from app.models.user import User
from app.models.exam_session import ExamSession
from app.models.proctoring import ProctoringEvent, ReviewDecision


router = APIRouter(tags=["Proctoring"])


# ---------------------------------------------------------------------------
# Risk weight configuration
# Each event type carries a weight used in the cumulative risk score.
# These weights are tunable by an admin. Treat them as signals only.
# ---------------------------------------------------------------------------

RISK_WEIGHTS = {
    "tab_switch": 0.10,
    "fullscreen_exit": 0.08,
    "focus_lost": 0.05,
    "clipboard_paste": 0.12,
    "camera_blocked": 0.15,
    "face_absent": 0.20,
    "multiple_faces": 0.25,
    "phone_detected": 0.30,
    "network_disconnect": 0.05,
    "unknown": 0.05,
}

# Sessions with risk score above this threshold are flagged for review
FLAG_THRESHOLD = 0.50


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

import uuid

class ProctoringEventCreate(BaseModel):
    """Request body for submitting a proctoring signal."""

    # Which active session this event relates to
    exam_session_id: uuid.UUID = Field(...)

    # Client-provided unique ID to prevent duplicates
    client_event_id: str = Field(..., max_length=100)

    # Monotonically increasing sequence number
    sequence_number: int = Field(..., ge=1)

    # Category - see RISK_WEIGHTS for known types
    event_type: str = Field(..., max_length=100)

    # "low", "medium", or "high"
    severity: str = Field(default="low", pattern="^(low|medium|high)$")

    # How confident the detector is (0 to 1)
    # For certain browser events use 1.0; for ML detections use model output
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # Optional extra data (e.g. how many seconds the tab was away)
    event_metadata: Optional[dict] = None


class ReviewDecisionCreate(BaseModel):
    """Request body for a reviewer recording their decision."""

    exam_session_id: str = Field(...)

    # "cleared", "warning_issued", "exam_invalidated", "escalated"
    decision: str = Field(
        ...,
        pattern="^(cleared|warning_issued|exam_invalidated|escalated)$"
    )

    notes: Optional[str] = Field(default=None, max_length=2000)


# ---------------------------------------------------------------------------
# Student routes: submit events only
# ---------------------------------------------------------------------------

@router.post(
    "/proctoring-events",
    status_code=status.HTTP_201_CREATED,
    summary="Submit a proctoring event from the browser or camera monitor"
)
def submit_proctoring_event(
    body: ProctoringEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Record one proctoring signal during an active exam session.

    The student can submit signals from the browser (focus loss,
    fullscreen exit, etc.) or from the camera monitoring client.

    The correct_answer or any other exam content is never returned here.
    """

    # Validate the session
    session = db.query(ExamSession).filter(
        ExamSession.id == body.exam_session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found"
        )

    # Prevent students from injecting events into other students' sessions
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot submit events for another student's session"
        )

    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Events can only be submitted for active sessions"
        )

    # Check for exact duplicate client_event_id
    existing_event = db.query(ProctoringEvent).filter(
        ProctoringEvent.client_event_id == body.client_event_id
    ).first()
    
    if existing_event:
        return {
            "message": "Event already recorded",
            "event_type": existing_event.event_type,
            "session_flagged": session.flagged_for_review
        }
        
    # Check for replay/out-of-order sequence number
    last_event = db.query(ProctoringEvent).filter(
        ProctoringEvent.exam_session_id == session.id
    ).order_by(ProctoringEvent.sequence_number.desc()).first()
    
    if last_event and last_event.sequence_number is not None:
        if body.sequence_number <= last_event.sequence_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sequence number: possible replay detected"
            )

    # Determine severity from event type if not explicitly set to high
    severity = body.severity

    # Create the event record
    event = ProctoringEvent(
        exam_session_id=session.id,
        user_id=current_user.id,
        event_type=body.event_type,
        severity=severity,
        confidence=body.confidence,
        event_metadata=body.event_metadata,
        client_event_id=body.client_event_id,
        sequence_number=body.sequence_number,
        status="pending"
    )

    db.add(event)

    # Recalculate the session's cumulative risk score
    _update_risk_score(db, session)

    db.commit()

    return {
        "message": "Event recorded",
        "event_type": body.event_type,
        "session_flagged": session.flagged_for_review
    }


# ---------------------------------------------------------------------------
# Reviewer/admin routes: read events and record decisions
# ---------------------------------------------------------------------------

@router.get(
    "/proctoring-events",
    summary="Reviewer: list all proctoring events"
)
def list_proctoring_events(
    exam_session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_reviewer)
):
    """
    Return proctoring events filtered by session, type, or status.

    Requires reviewer or admin role.
    Evidence references are included so reviewers can inspect them.
    """

    query = db.query(ProctoringEvent)

    if exam_session_id:
        query = query.filter(
            ProctoringEvent.exam_session_id == exam_session_id
        )

    if event_type:
        query = query.filter(
            ProctoringEvent.event_type == event_type
        )

    if status_filter:
        query = query.filter(
            ProctoringEvent.status == status_filter
        )

    events = query.order_by(
        ProctoringEvent.occurred_at.desc()
    ).limit(500).all()

    return [
        {
            "id": str(e.id),
            "exam_session_id": str(e.exam_session_id),
            "user_id": str(e.user_id),
            "event_type": e.event_type,
            "severity": e.severity,
            "confidence": e.confidence,
            "evidence_ref": e.evidence_ref,
            "event_metadata": e.event_metadata,
            "status": e.status,
            "occurred_at": e.occurred_at.isoformat()
            if e.occurred_at else None,
        }
        for e in events
    ]


@router.get(
    "/proctoring-events/flagged-sessions",
    summary="Reviewer: list sessions flagged for review"
)
def list_flagged_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_reviewer)
):
    """
    Return all exam sessions currently flagged for human review,
    ordered by risk score descending (highest risk first).
    """

    sessions = (
        db.query(ExamSession)
        .filter(ExamSession.flagged_for_review == True)
        .order_by(ExamSession.risk_score.desc())
        .limit(200)
        .all()
    )

    return [
        {
            "session_id": str(s.id),
            "user_id": str(s.user_id),
            "domain": s.domain,
            "skill": s.skill,
            "risk_score": s.risk_score,
            "status": s.status,
            "questions_answered": s.questions_answered,
            "accuracy": s.accuracy,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "finished_at": s.finished_at.isoformat()
            if s.finished_at else None,
        }
        for s in sessions
    ]


@router.post(
    "/review-decisions",
    status_code=status.HTTP_201_CREATED,
    summary="Reviewer: record a decision on a flagged session"
)
def record_review_decision(
    body: ReviewDecisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_reviewer)
):
    """
    Record a human reviewer's decision about a flagged exam session.

    This creates an immutable audit record. The exam session's
    flagged_for_review remains true for transparency; the decision
    record shows it was reviewed.

    Valid decisions: cleared, warning_issued, exam_invalidated, escalated
    """

    session = db.query(ExamSession).filter(
        ExamSession.id == body.exam_session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found"
        )

    # Check no decision was already made on this session by this reviewer
    # (allow multiple reviewers to record independent decisions)

    decision = ReviewDecision(
        exam_session_id=session.id,
        reviewer_id=current_user.id,
        decision=body.decision,
        notes=body.notes
    )

    db.add(decision)
    db.commit()
    db.refresh(decision)

    return {
        "decision_id": str(decision.id),
        "exam_session_id": str(decision.exam_session_id),
        "reviewer_id": str(decision.reviewer_id),
        "decision": decision.decision,
        "notes": decision.notes,
        "decided_at": decision.decided_at.isoformat()
        if decision.decided_at else None,
    }


@router.get(
    "/review-decisions",
    summary="Reviewer: list review decisions"
)
def list_review_decisions(
    exam_session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_reviewer)
):
    """Return review decisions, optionally filtered by session."""

    query = db.query(ReviewDecision)

    if exam_session_id:
        query = query.filter(
            ReviewDecision.exam_session_id == exam_session_id
        )

    decisions = query.order_by(
        ReviewDecision.decided_at.desc()
    ).limit(500).all()

    return [
        {
            "decision_id": str(d.id),
            "exam_session_id": str(d.exam_session_id),
            "reviewer_id": str(d.reviewer_id),
            "decision": d.decision,
            "notes": d.notes,
            "decided_at": d.decided_at.isoformat()
            if d.decided_at else None,
        }
        for d in decisions
    ]


# ---------------------------------------------------------------------------
# Internal: risk score calculation
# ---------------------------------------------------------------------------

def _update_risk_score(db: Session, session: ExamSession):
    """
    Recalculate the cumulative risk score for an exam session.

    The score is a weighted sum of event confidence values, capped at 1.0.
    It is an estimate, not a determination of guilt.

    After updating, flag the session for review if the score exceeds
    the configured threshold.
    """

    # Load all events for this session
    events = (
        db.query(ProctoringEvent)
        .filter(ProctoringEvent.exam_session_id == session.id)
        .all()
    )

    total_risk = 0.0

    for event in events:
        weight = RISK_WEIGHTS.get(event.event_type, RISK_WEIGHTS["unknown"])
        # Scale by the detector confidence so uncertain signals count less
        total_risk += weight * event.confidence

    # Cap at 1.0
    session.risk_score = min(1.0, round(total_risk, 4))

    # Flag for human review if threshold exceeded
    if session.risk_score >= FLAG_THRESHOLD:
        session.flagged_for_review = True
