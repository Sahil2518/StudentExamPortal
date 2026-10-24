from sqlalchemy import Column, String, Float, DateTime
from datetime import datetime
from app.database.base import Base

class BanditState(Base):
    """
    Persists Contextual Bandit parameters (alpha, beta).
    arm_key format: "{skill}::{difficulty_bucket}"
    """
    __tablename__ = "bandit_states"

    arm_key = Column(String, primary_key=True)
    alpha = Column(Float, nullable=False, default=1.0)
    beta = Column(Float, nullable=False, default=1.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
