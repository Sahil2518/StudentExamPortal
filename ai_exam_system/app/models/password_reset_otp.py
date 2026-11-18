from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database.base import Base

import uuid
from datetime import datetime


class PasswordResetOTP(Base):
    """
    Stores 6-digit one-time passwords (hashed) for email-verified password resets.
    """
    __tablename__ = "password_reset_otps"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    email = Column(
        String(320),
        nullable=False,
        index=True
    )
    otp_hash = Column(
        String(255),
        nullable=False
    )
    expires_at = Column(
        DateTime,
        nullable=False
    )
    is_used = Column(
        Boolean,
        default=False,
        nullable=False
    )
    attempts = Column(
        Integer,
        default=0,
        nullable=False
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = relationship("User", backref="password_reset_otps")
