
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.current_user import get_current_user

from app.models.user import User
from app.services.ml_dataset import build_ml_dataset


router = APIRouter()


@router.get("/ml/dataset")
def get_ml_dataset(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dataset = build_ml_dataset(
        db=db,
        user_id=current_user.id
    )

    return {
        "student_id": str(current_user.id),
        "samples": len(dataset),
        "target": "target_is_correct",
        "features": dataset
    }
