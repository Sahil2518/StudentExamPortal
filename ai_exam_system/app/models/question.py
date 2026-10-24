import uuid

from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.base import Base


class Question(Base):
    """
    A single exam question in the question bank.

    The correct_answer field is stored here but must never be exposed
    to students through any API response before they have submitted
    their answer. After submission the server compares server-side
    and returns the result.

    Questions start as active=True. Deactivated questions are not
    served to students but are kept in the database for historical
    records of past attempts.
    """

    __tablename__ = "questions"

    # Unique identifier
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Full question text shown to the student
    question_text = Column(
        Text,
        nullable=False
    )

    # Top-level subject area, e.g. "AI/ML", "Data Science"
    domain = Column(
        String(200),
        nullable=False,
        index=True
    )

    # Specific skill within the domain, e.g. "Machine Learning Fundamentals"
    skill = Column(
        String(200),
        nullable=False,
        index=True
    )

    # Numeric difficulty on a 1-5 scale
    difficulty = Column(
        Integer,
        nullable=False,
        index=True
    )

    # Lowest student level for which this question is appropriate (1-5)
    minimum_level = Column(
        Integer,
        nullable=False
    )

    # Highest student level for which this question is appropriate (1-5)
    maximum_level = Column(
        Integer,
        nullable=False
    )

    # List of answer options stored as a JSON array of strings
    # Example: ["Option A", "Option B", "Option C", "Option D"]
    options = Column(
        JSONB,
        nullable=False
    )

    # The correct option string - must match one of the values in options
    # This is NEVER returned in student-facing API calls before submission
    correct_answer = Column(
        String(500),
        nullable=False
    )

    # Explanation shown to the student AFTER they submit their answer
    explanation = Column(
        Text,
        nullable=True
    )

    # Type of question: "multiple_choice", "true_false", "multiple_select"
    question_type = Column(
        String(50),
        nullable=False,
        default="multiple_choice"
    )

    # Whether this question is currently available for exams
    # Set to False to deactivate without deleting historical records
    is_active = Column(
        Boolean,
        nullable=False,
        default=True
    )

    # Source of this question: "manual", "csv_import", "llm_generated"
    source = Column(
        String(50),
        nullable=False,
        default="manual"
    )

    # For LLM-generated questions: "pending_review", "approved", "rejected"
    approval_status = Column(
        String(20),
        nullable=False,
        default="approved"
    )

    # Who approved this question (user_id as string, or "system")
    approved_by = Column(
        String(100),
        nullable=True
    )

    # When the question was created
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # When the question was last modified
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # All attempts that have used this question
    attempts = relationship(
        "QuestionAttempt",
        back_populates="question"
    )