"""
routes/ai_assistant_routes.py
Omnipresent AI Assistant, Doubt Solver & Exam Malpractice Monitor Routes.

Endpoints:
- POST /ai-assistant/chat:
    Dual-mode conversational AI.
    * Live Exam Mode: Enforces Academic Integrity Shield. Prohibits direct answer leakage
      and logs malpractice attempts to session telemetry.
    * Practice & Review Mode: Pedagogical doubt solver. Step-by-step math derivations with KaTeX.
- GET /ai-assistant/telemetry-status:
    Returns the real-time malpractice audit and integrity trust score (0-100%) for an active session.
- POST /ai-assistant/log-malpractice:
    Direct client beacon for proctoring incidents (tab switches, focus loss, paste, camera blockage).
"""

import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.current_user import get_current_user
from app.models.user import User
from app.models.exam_session import ExamSession
from app.models.proctoring import ProctoringEvent
from app.services.ai_assistant_service import (
    generate_ai_response,
    calculate_integrity_score
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-assistant", tags=["AI Assistant & Proctor Monitor"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="The user's query or doubt")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Current navigation route, active question, and exam metadata")
    history: Optional[List[Dict[str, str]]] = Field(default=None, description="Previous messages in the chat session")


class ChatResponse(BaseModel):
    response: str
    mode: str
    integrity_flag: bool
    proactive_tip: Optional[str] = None
    provider: str


class MalpracticeBeaconInput(BaseModel):
    exam_session_id: str
    event_type: str = Field(..., pattern="^(tab_switch|focus_lost|camera_blocked|clipboard_paste|rapid_guess)$")
    severity: Optional[str] = "medium"
    metadata: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with Aura: Omnipresent Doubt Solver & Exam Integrity Guide"
)
def chat_with_assistant(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Primary conversational endpoint.

    Dynamically monitors context:
    - If user is in a live entrance exam, blocks answer cheating, issues malpractice warnings,
      and records the incident into proctoring telemetry.
    - If user is on dashboard, setup, practice, or results page, operates as a comprehensive
      academic doubt solver with rich LaTeX math derivations ($...$ and $$...$$).
    """
    ctx = body.context or {}
    session_id_str = ctx.get("exam_session_id")
    is_live = ctx.get("exam_type") == "live" or "/exam/session" in str(ctx.get("route", ""))

    ai_result = generate_ai_response(
        user_message=body.message,
        context=ctx,
        history=body.history,
    )

    # If the user attempted to elicit answers during a live entrance exam, log a proctoring incident!
    if ai_result.get("integrity_flag") and session_id_str and is_live:
        try:
            s_uuid = uuid.UUID(session_id_str)
            incident = ProctoringEvent(
                exam_session_id=s_uuid,
                event_type="assistant_cheat_attempt",
                severity="high",
                confidence=1.0,
                occurred_at=datetime.now(timezone.utc),
                event_metadata={
                    "flagged_message": body.message[:200],
                    "route": ctx.get("route"),
                    "question_id": ctx.get("question_id")
                }
            )
            db.add(incident)
            db.commit()
            logger.info("Logged assistant_cheat_attempt proctoring incident for session=%s", session_id_str)
        except Exception as exc:
            logger.warning("Could not persist cheat attempt proctoring event: %s", exc)

    return ChatResponse(**ai_result)


@router.get(
    "/telemetry-status",
    summary="Retrieve live exam integrity trust score and malpractice audit"
)
def get_telemetry_status(
    session_id: Optional[str] = Query(default=None, description="Target exam session UUID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the real-time integrity status of an exam session:
    - Trust score (0-100%)
    - Malpractice incident breakdown (tab switches, focus loss, camera drops, cheat attempts)
    - Verdict (Clean, Caution, Flagged for Human Review)
    - Recent incident timeline
    """
    target_session = None

    if session_id:
        try:
            s_uuid = uuid.UUID(session_id)
            target_session = (
                db.query(ExamSession)
                .filter(ExamSession.id == s_uuid, ExamSession.user_id == current_user.id)
                .first()
            )
        except Exception:
            pass

    # If no session ID provided, pick user's most recent active or finished session
    if not target_session:
        target_session = (
            db.query(ExamSession)
            .filter(ExamSession.user_id == current_user.id)
            .order_by(ExamSession.started_at.desc())
            .first()
        )

    if not target_session:
        return {
            "session_id": None,
            "integrity_score": 100,
            "verdict": "clean",
            "status_label": "No active session",
            "status_color": "green",
            "breakdown": {
                "tab_switches": 0,
                "focus_losses": 0,
                "camera_blocked": 0,
                "cheat_attempts": 0,
                "clipboard_pastes": 0,
                "total_incidents": 0
            },
            "recent_incidents": []
        }

    events = (
        db.query(ProctoringEvent)
        .filter(ProctoringEvent.exam_session_id == target_session.id)
        .order_by(ProctoringEvent.occurred_at.asc())
        .all()
    )

    event_dicts = [
        {
            "event_type": ev.event_type,
            "severity": ev.severity,
            "occurred_at": ev.occurred_at,
            "metadata": getattr(ev, "event_metadata", {})
        }
        for ev in events
    ]

    summary = calculate_integrity_score(event_dicts)
    summary["session_id"] = str(target_session.id)
    summary["exam_type"] = target_session.exam_type
    summary["exam_title"] = target_session.exam_paper_title or target_session.domain

    return summary


@router.post(
    "/log-malpractice",
    summary="Record a client-side proctoring malpractice beacon"
)
def log_malpractice_beacon(
    body: MalpracticeBeaconInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Direct beacon endpoint for browser integrity hooks (tab switch, focus lost, paste).
    Automatically saves event and returns the updated integrity trust score.
    """
    try:
        s_uuid = uuid.UUID(body.exam_session_id)
        session = (
            db.query(ExamSession)
            .filter(ExamSession.id == s_uuid, ExamSession.user_id == current_user.id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Exam session not found or unauthorized")

        event = ProctoringEvent(
            exam_session_id=s_uuid,
            event_type=body.event_type,
            severity=body.severity or "medium",
            confidence=1.0,
            occurred_at=datetime.now(timezone.utc),
            event_metadata=body.metadata or {}
        )
        db.add(event)
        db.commit()

        # Query all events to compute updated score
        all_events = (
            db.query(ProctoringEvent)
            .filter(ProctoringEvent.exam_session_id == s_uuid)
            .all()
        )
        event_dicts = [
            {"event_type": e.event_type, "occurred_at": e.occurred_at}
            for e in all_events
        ]
        return calculate_integrity_score(event_dicts)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to log malpractice beacon: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid session format or payload")
