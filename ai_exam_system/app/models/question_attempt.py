import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    DateTime,
    ForeignKey
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database.base import Base


class QuestionAttempt(Base):
    """
    Records one question answered by a student.

    Each attempt belongs to an exam session. The server calculates
    whether the answer is correct - the student never submits
    is_correct directly. The correct_answer is never returned
    in API responses before the student has submitted.
    """

    __tablename__ = "question_attempts"

    # Unique identifier
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Which user submitted this answer
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Which exam session this attempt belongs to.
    # Null means the attempt was made outside any formal session
    # (legacy or practice mode).
    exam_session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exam_sessions.id"),
        nullable=True,
        index=True
    )

    # Which question was answered
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("questions.id"),
        nullable=False
    )

    # The answer the student selected
    selected_answer = Column(
        String(500),
        nullable=False
    )

    # Whether the answer was correct - set by the server, not the client
    is_correct = Column(
        Boolean,
        nullable=False
    )

    # How many seconds the student spent on this question
    time_taken = Column(
        Integer,
        nullable=False
    )

    # When the answer was submitted
    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # The exam session this attempt is part of
    exam_session = relationship(
        "ExamSession",
        back_populates="attempts"
    )

    # The question that was answered
    question = relationship("Question")