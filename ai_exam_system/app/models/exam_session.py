import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.base import Base


class ExamSession(Base):
    """
    Represents one complete exam attempt for a student.

    An exam session is created when the student begins an exam and
    closed when they submit or the time limit expires. All question
    attempts and proctoring events during the exam are linked here.
    """

    __tablename__ = "exam_sessions"

    # Unique session identifier
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Which student is taking this exam
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Domain being examined, e.g. "AI/ML"
    domain = Column(
        String(200),
        nullable=False
    )

    # Skill being examined, e.g. "Machine Learning Fundamentals"
    skill = Column(
        String(200),
        nullable=True
    )

    # Exam type: "practice" (adaptive) or "live" (fixed entrance exam like JEE/NEET/CAT)
    exam_type = Column(
        String(20),
        nullable=False,
        default="practice"
    )

    # Marking scheme for live exams
    positive_mark = Column(
        Float,
        nullable=False,
        default=4.0
    )

    negative_mark = Column(
        Float,
        nullable=False,
        default=1.0
    )

    # Total negative penalty accrued in live exam
    negative_marks_total = Column(
        Float,
        nullable=False,
        default=0.0
    )

    # Raw score calculated with negative marking: (correct * positive_mark) - (incorrect * negative_mark)
    raw_score = Column(
        Float,
        nullable=True
    )

    # Optional paper title (e.g., "JEE Main Mock Test 1")
    exam_paper_title = Column(
        String(255),
        nullable=True
    )

    # Maximum number of questions allowed in this session
    max_questions = Column(
        Integer,
        nullable=False,
        default=10
    )

    # Time limit in seconds (None means no limit)
    time_limit_seconds = Column(
        Integer,
        nullable=True
    )

    # Current status: "active", "finished", "abandoned", "expired"
    status = Column(
        String(20),
        nullable=False,
        default="active"
    )

    # Total score out of total marks available
    total_score = Column(
        Float,
        nullable=True
    )

    # Number of questions answered
    questions_answered = Column(
        Integer,
        nullable=False,
        default=0
    )

    # Number of correct answers
    correct_count = Column(
        Integer,
        nullable=False,
        default=0
    )

    # Accuracy as a decimal (0 to 1) calculated at session finish
    accuracy = Column(
        Float,
        nullable=True
    )

    # JSON blob storing personalized recommendations generated at finish
    recommendations = Column(
        JSONB,
        nullable=True
    )

    # Risk score from proctoring system (0 to 1, higher means more suspicious)
    risk_score = Column(
        Float,
        nullable=True,
        default=0.0
    )

    # Whether a human reviewer has been assigned to this session
    flagged_for_review = Column(
        Boolean,
        nullable=False,
        default=False
    )

    # When the exam started
    started_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # When the exam ended (set on finish or expiry)
    finished_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # Back-reference to the user who owns this session
    user = relationship("User", back_populates="exam_sessions")

    # All question attempts made during this session
    attempts = relationship(
        "QuestionAttempt",
        back_populates="exam_session",
        cascade="all, delete-orphan"
    )

    # All proctoring events recorded during this session
    proctoring_events = relationship(
        "ProctoringEvent",
        back_populates="exam_session",
        cascade="all, delete-orphan"
    )

    # All questions issued to this session by the adaptive engine
    issued_questions = relationship(
        "ExamSessionQuestion",
        back_populates="exam_session",
        cascade="all, delete-orphan"
    )
