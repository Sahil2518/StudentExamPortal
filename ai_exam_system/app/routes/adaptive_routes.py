from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.current_user import get_current_user

from app.models.user import User

from app.services.adaptive_engine import (
    select_next_question
)


router = APIRouter()


@router.get("/adaptive-question")
def get_adaptive_question(
    domain: str,
    skill: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    raise HTTPException(
        status_code=410,
        detail="This endpoint is deprecated. Use GET /exam-sessions/{session_id}/next-question instead."
    )