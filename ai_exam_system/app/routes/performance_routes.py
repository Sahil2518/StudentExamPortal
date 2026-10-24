from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.connection import get_db
from app.dependencies.current_user import get_current_user

from app.models.user import User
from app.models.question_attempt import QuestionAttempt


router = APIRouter()


@router.get("/performance")
def get_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    total_attempts = db.query(
        QuestionAttempt
    ).filter(
        QuestionAttempt.user_id == current_user.id
    ).count()

    correct_answers = db.query(
        QuestionAttempt
    ).filter(
        QuestionAttempt.user_id == current_user.id,
        QuestionAttempt.is_correct == True
    ).count()

    wrong_answers = total_attempts - correct_answers

    if total_attempts > 0:
        accuracy = (
            correct_answers / total_attempts
        ) * 100
    else:
        accuracy = 0

    average_time = db.query(
        func.avg(QuestionAttempt.time_taken)
    ).filter(
        QuestionAttempt.user_id == current_user.id
    ).scalar()

    return {
        "total_attempts": total_attempts,
        "correct_answers": correct_answers,
        "wrong_answers": wrong_answers,
        "accuracy": round(accuracy, 2),
        "average_time": round(float(average_time), 2)
        if average_time is not None
        else 0
    }