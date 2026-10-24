from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.current_user import get_current_user

from app.models.user import User
from app.models.question import Question
from app.models.question_attempt import QuestionAttempt


router = APIRouter()


@router.get("/performance/skills")
def get_skill_performance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    attempts = db.query(
        QuestionAttempt
    ).filter(
        QuestionAttempt.user_id == current_user.id
    ).all()

    skill_data = {}

    for attempt in attempts:

        question = db.query(
            Question
        ).filter(
            Question.id == attempt.question_id
        ).first()

        if not question:
            continue

        domain = question.domain
        skill = question.skill

        if domain not in skill_data:
            skill_data[domain] = {}

        if skill not in skill_data[domain]:
            skill_data[domain][skill] = {
                "attempts": 0,
                "correct": 0,
                "wrong": 0
            }

        skill_data[domain][skill]["attempts"] += 1

        if attempt.is_correct:
            skill_data[domain][skill]["correct"] += 1
        else:
            skill_data[domain][skill]["wrong"] += 1

    for domain in skill_data:

        for skill in skill_data[domain]:

            data = skill_data[domain][skill]

            data["accuracy"] = round(
                (data["correct"] / data["attempts"]) * 100,
                2
            )

    return skill_data