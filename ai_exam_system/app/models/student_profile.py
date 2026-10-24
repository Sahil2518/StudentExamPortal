import uuid

from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    DateTime
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.orm import relationship

from app.database.base import Base


class StudentProfile(Base):

    __tablename__ = "student_profiles"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        unique=True,
        nullable=False
    )

    qualification = Column(
        String,
        nullable=False
    )

    branch = Column(
        String,
        nullable=False
    )

    experience_level = Column(
        String,
        nullable=False
    )

    preferred_domain = Column(
        String,
        nullable=False
    )

    preferred_difficulty = Column(
        String,
        nullable=False
    )

    learning_goal = Column(
        String,
        nullable=False
    )

    profile_completion = Column(
        String,
        default="0%"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    user = relationship(
        "User",
        back_populates="student_profile"
    )