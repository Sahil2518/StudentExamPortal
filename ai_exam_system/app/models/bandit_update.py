from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database.base import Base

class BanditUpdate(Base):
    __tablename__ = "bandit_updates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    question_attempt_id = Column(UUID(as_uuid=True), ForeignKey("question_attempts.id"), unique=True, nullable=False, index=True)
    arm_key = Column(String, nullable=False)
    outcome = Column(String, nullable=False) # "correct" or "incorrect"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
