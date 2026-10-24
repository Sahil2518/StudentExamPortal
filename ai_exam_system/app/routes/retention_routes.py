from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.current_user import get_current_user

from app.models.user import User

from app.services.retention_model import (
    calculate_retention_state
)


router = APIRouter()


@router.get("/retention")
def get_retention_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    state = calculate_retention_state(
        db=db,
        user_id=current_user.id
    )

    return {
        "student_id": current_user.id,
        "retention_state": state
    }