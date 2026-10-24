from pydantic import BaseModel
from uuid import UUID
class QuestionAttemptCreate(BaseModel):
    question_id: UUID
    selected_answer: str
    time_taken: int