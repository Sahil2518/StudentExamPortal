from datetime import datetime, timezone
import math

from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_attempt import QuestionAttempt


def calculate_retention(
    mastery: float,
    last_attempt,
    decay_rate: float = 0.05
):
    """
    Estimate how much of the student's knowledge
    is currently retained.

    mastery:
        Current estimated mastery (0 to 1)

    last_attempt:
        Timestamp of the student's latest attempt

    decay_rate:
        Controls forgetting speed.
    """

    if not last_attempt:
        return mastery

    # Make datetime timezone-safe
    if last_attempt.tzinfo is None:
        last_attempt = last_attempt.replace(
            tzinfo=timezone.utc
        )

    now = datetime.now(timezone.utc)

    elapsed_seconds = (
        now - last_attempt
    ).total_seconds()

    elapsed_days = max(
        0,
        elapsed_seconds / 86400
    )

    # Exponential forgetting
    retention = math.exp(
        -decay_rate * elapsed_days
    )

    effective_knowledge = (
        mastery * retention
    )

    return max(
        0.0,
        min(1.0, effective_knowledge)
    )


def calculate_retention_state(
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

    # ---------------------------------------------
    # Build skill-level history
    # ---------------------------------------------

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

        if domain not in skills:
            skills[domain] = {}

        if skill not in skills[domain]:

            skills[domain][skill] = {
                "mastery": 0.50,
                "attempts": 0,
                "correct": 0,
                "wrong": 0,
                "last_attempt": None
            }

        data = skills[domain][skill]

        data["attempts"] += 1

        # -----------------------------------------
        # Difficulty-based learning rate
        # -----------------------------------------

        if question.difficulty <= 1:
            learning_rate = 0.10

        elif question.difficulty == 2:
            learning_rate = 0.20

        else:
            learning_rate = 0.30

        # -----------------------------------------
        # Correct / incorrect update
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
        # Save latest attempt
        # -----------------------------------------

        data["last_attempt"] = (
            attempt.created_at
        )

    # ---------------------------------------------
    # Calculate current retention
    # ---------------------------------------------

    for domain in skills:

        for skill in skills[domain]:

            data = skills[domain][skill]

            retention = calculate_retention(
                mastery=data["mastery"],
                last_attempt=data["last_attempt"]
            )

            data["mastery_percentage"] = round(
                data["mastery"] * 100,
                2
            )

            # retention here is already effective_knowledge = mastery * retention
            # from calculate_retention(). Split them for clear reporting.
            raw_retention = math.exp(-0.05 * max(0, (
                (datetime.now(timezone.utc) - (
                    data["last_attempt"].replace(tzinfo=timezone.utc)
                    if data["last_attempt"] and hasattr(data["last_attempt"], "tzinfo")
                    and data["last_attempt"].tzinfo is None
                    else data["last_attempt"]
                )).total_seconds() / 86400
            ) if data["last_attempt"] else 0))

            data["retention_percentage"] = round(raw_retention * 100, 2)

            # effective_knowledge = mastery * retention (both in [0,1])
            # This is the correct combined measure of what the student
            # can currently recall and apply.
            data["effective_knowledge_percentage"] = round(
                data["mastery"] * raw_retention * 100,
                2
            )

            if data["retention_percentage"] >= 80:
                data["retention_status"] = "Strong"

            elif data["retention_percentage"] >= 50:
                data["retention_status"] = "Moderate"

            else:
                data["retention_status"] = "Weak"

            # Datetime isn't ideal for JSON responses
            if data["last_attempt"]:
                data["last_attempt"] = (
                    data["last_attempt"].isoformat()
                )

    return skills