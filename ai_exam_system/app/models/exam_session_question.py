"""
ExamSessionQuestion — tracks which questions were issued to which exam session.

When the adaptive engine selects a question, it records that selection here.
On answer submission, the server verifies the question was actually issued
to this session. This prevents clients from submitting answers to questions
they were never shown.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, UniqueConstraint, Boolean

class ExamSessionQuestion(Base):
    __tablename__ = "exam_session_questions"
    
    __table_args__ = (
        UniqueConstraint('exam_session_id', 'question_id', name='uq_session_question'),
        UniqueConstraint('exam_session_id', 'sequence_number', name='uq_session_sequence'),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_session_id = Column(UUID(as_uuid=True), ForeignKey("exam_sessions.id"), nullable=False, index=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    sequence_number = Column(Integer, nullable=False)
    served_at = Column(DateTime(timezone=True), server_default=func.now())
    answered_at = Column(DateTime(timezone=True), nullable=True)
    selection_policy = Column(String(50), nullable=True)
    model_version = Column(String(50), nullable=True)
    predicted_probability = Column(Float, nullable=True)
    selection_reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="served")
    # Live exam palette status: not_visited, not_answered, answered, marked_for_review, answered_and_marked
    review_status = Column(String(30), nullable=False, default="not_visited")
    selected_option = Column(String(500), nullable=True)
    is_correct = Column(Boolean, nullable=True)
    
    exam_session = relationship("ExamSession", back_populates="issued_questions")
    question = relationship("Question")
