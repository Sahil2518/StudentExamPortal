from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.current_user import get_current_user

from app.models.user import User

from app.services.knowledge_state import (
    calculate_knowledge_state
)


router = APIRouter()


@router.get("/knowledge-state")
def get_knowledge_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    knowledge_state = calculate_knowledge_state(
        db=db,
        user_id=current_user.id
    )

    return {
        "student_id": current_user.id,
        "knowledge_state": knowledge_state
    }