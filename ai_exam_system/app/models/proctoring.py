import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Integer
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.base import Base


class ProctoringEvent(Base):
    """
    Records a single proctoring signal during an exam session.

    Events are submitted by the browser or camera monitoring code
    and stored for later risk scoring and human review. Each event
    has a type, severity, optional evidence reference, and a
    confidence value between 0 and 1.

    These are risk signals, not conclusive proof of misconduct.
    A human reviewer must inspect flagged sessions before any
    action is taken.
    """

    __tablename__ = "proctoring_events"

    # Unique identifier for this event
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Which exam session this event belongs to
    exam_session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exam_sessions.id"),
        nullable=False,
        index=True
    )

    # Which student triggered this event
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Category of event.
    # Examples: "tab_switch", "fullscreen_exit", "face_absent",
    # "multiple_faces", "phone_detected", "clipboard_paste",
    # "camera_blocked", "focus_lost", "network_disconnect"
    event_type = Column(
        String(100),
        nullable=False
    )

    # Client-generated unique ID to prevent duplicate submissions
    client_event_id = Column(
        String(100),
        nullable=True,
        unique=True
    )

    # Monotonically increasing sequence number from the client for this session
    # Used to detect replayed or out-of-order events
    sequence_number = Column(
        Integer,
        nullable=True
    )

    # Severity level: "low", "medium", "high"
    severity = Column(
        String(20),
        nullable=False,
        default="low"
    )

    # Model or sensor confidence that this event is genuine (0.0 to 1.0).
    # For browser events that are definitely real, use 1.0.
    # For ML detections, use the model output probability.
    confidence = Column(
        Float,
        nullable=False,
        default=1.0
    )

    # Optional path or identifier for stored evidence such as a frame snapshot.
    # This is never exposed to students.
    evidence_ref = Column(
        Text,
        nullable=True
    )

    # Extra structured data relevant to this event type.
    # For example, tab-switch events might include the URL the student went to.
    # Column is named event_metadata to avoid conflict with SQLAlchemy's
    # reserved 'metadata' attribute on all mapped classes.
    event_metadata = Column(
        "event_metadata",
        JSONB,
        nullable=True
    )

    # Current processing state: "pending", "reviewed", "dismissed"
    status = Column(
        String(20),
        nullable=False,
        default="pending"
    )

    # When the event occurred
    occurred_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Exam session this event is linked to
    exam_session = relationship(
        "ExamSession",
        back_populates="proctoring_events"
    )

    # Student who was being monitored
    user = relationship("User")


class ReviewDecision(Base):
    """
    Records a human reviewer's decision about a flagged exam session.

    This provides an audit trail that shows who reviewed what, when,
    and what conclusion was reached. No automatic penalty is applied
    based solely on the proctoring risk score.
    """

    __tablename__ = "review_decisions"

    # Unique identifier
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Which exam session was reviewed
    exam_session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exam_sessions.id"),
        nullable=False,
        index=True
    )

    # Which admin or reviewer made this decision
    reviewer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )

    # Outcome: "cleared", "warning_issued", "exam_invalidated", "escalated"
    decision = Column(
        String(50),
        nullable=False
    )

    # Free-text notes explaining the decision
    notes = Column(
        Text,
        nullable=True
    )

    # When the decision was recorded
    decided_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # The reviewer who made this decision
    reviewer = relationship(
        "User",
        foreign_keys=[reviewer_id]
    )
