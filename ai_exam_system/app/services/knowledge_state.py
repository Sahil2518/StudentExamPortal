from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_attempt import QuestionAttempt


def get_time_factor(time_taken: int):
    """
    Convert response time into a factor.

    Faster answers give stronger evidence of mastery.
    Very slow answers give weaker evidence.
    """

    if time_taken <= 10:
        return 1.20

    elif time_taken <= 30:
        return 1.00

    elif time_taken <= 60:
        return 0.85

    elif time_taken <= 120:
        return 0.70

    else:
        return 0.55


def calculate_knowledge_state(
    db: Session,
    user_id
):

    attempts = (
        db.query(QuestionAttempt)
        .join(
            Question,
            Question.id == QuestionAttempt.question_id
        )
        .filter(
            QuestionAttempt.user_id == user_id
        )
        .order_by(
            QuestionAttempt.created_at.asc()
        )
        .all()
    )

    if not attempts:
        return {}

    skills = {}

    for attempt in attempts:

        question = (
            db.query(Question)
            .filter(
                Question.id == attempt.question_id
            )
            .first()
        )

        if not question:
            continue

        domain = question.domain
        skill = question.skill

        # -----------------------------------------
        # Create skill if it doesn't exist
        # -----------------------------------------

        if domain not in skills:
            skills[domain] = {}

        if skill not in skills[domain]:

            skills[domain][skill] = {
                "attempts": 0,
                "correct": 0,
                "wrong": 0,
                "mastery": 0.50
            }

        data = skills[domain][skill]

        data["attempts"] += 1

        # -----------------------------------------
        # Difficulty factor
        # -----------------------------------------

        difficulty = question.difficulty

        if difficulty <= 1:
            difficulty_factor = 0.10

        elif difficulty == 2:
            difficulty_factor = 0.20

        else:
            difficulty_factor = 0.30

        # -----------------------------------------
        # Time factor
        # -----------------------------------------

        time_factor = get_time_factor(
            attempt.time_taken
        )

        # -----------------------------------------
        # Final learning impact
        # -----------------------------------------

        learning_rate = (
            difficulty_factor *
            time_factor
        )

        # -----------------------------------------
        # Update mastery
        # -----------------------------------------

        if attempt.is_correct:

            data["correct"] += 1

            data["mastery"] += (
                learning_rate *
                (1 - data["mastery"])
            )

        else:

            data["wrong"] += 1

            data["mastery"] -= (
                learning_rate *
                data["mastery"]
            )

        # -----------------------------------------
        # Keep mastery between 0 and 1
        # -----------------------------------------

        data["mastery"] = max(
            0.0,
            min(1.0, data["mastery"])
        )

    # -----------------------------------------
    # Add percentages
    # -----------------------------------------

    for domain in skills:

        for skill in skills[domain]:

            data = skills[domain][skill]

            data["mastery_percentage"] = round(
                data["mastery"] * 100,
                2
            )

    return skills