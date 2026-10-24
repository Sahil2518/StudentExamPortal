from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database.base import Base

import uuid
from datetime import datetime


class User(Base):
    """
    Core user account table.

    Stores credentials, role, and links to all user-owned data.
    Password hashes are stored using bcrypt; plain passwords
    are never stored or returned by any API response.
    """

    __tablename__ = "users"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Display name
    name = Column(
        String(200),
        nullable=False
    )

    # Login email - must be unique across all accounts
    email = Column(
        String(320),
        unique=True,
        nullable=False,
        index=True
    )

    # bcrypt hash of the user's password
    # Never return this in any API response
    password_hash = Column(
        String(255),
        nullable=False
    )

    # Role controls what the user can access.
    # Valid values: "student", "admin", "reviewer"
    role = Column(
        String(20),
        default="student"
    )

    # Account creation timestamp
    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # One-to-one relationship with the student's extended profile
    student_profile = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False
    )

    # All exam sessions belonging to this user
    exam_sessions = relationship(
        "ExamSession",
        back_populates="user",
        cascade="all, delete-orphan"
    )