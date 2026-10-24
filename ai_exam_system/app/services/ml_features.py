from sqlalchemy.orm import Session
from app.models.question import Question
from app.models.question_attempt import QuestionAttempt


def build_student_features(
    db: Session,
    user_id
):
    """
    Build ML-ready features from a student's
    previous question attempts.
    """

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
        return []

    features = []

    total_attempts = 0
    total_correct = 0

    skill_stats = {}

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

        total_attempts += 1

        if attempt.is_correct:
            total_correct += 1

        # -----------------------------------------
        # Skill statistics
        # -----------------------------------------

        skill_key = (
            question.domain,
            question.skill
        )

        if skill_key not in skill_stats:
            skill_stats[skill_key] = {
                "attempts": 0,
                "correct": 0
            }

        skill_stats[skill_key]["attempts"] += 1

        if attempt.is_correct:
            skill_stats[skill_key]["correct"] += 1

        skill_attempts = skill_stats[
            skill_key
        ]["attempts"]

        skill_correct = skill_stats[
            skill_key
        ]["correct"]

        skill_accuracy = (
            skill_correct /
            skill_attempts
        )

        overall_accuracy = (
            total_correct /
            total_attempts
        )

        # -----------------------------------------
        # ML feature vector
        # -----------------------------------------

        feature_row = {
            "question_difficulty": question.difficulty,

            "time_taken": attempt.time_taken,

            "skill_attempts": skill_attempts,

            "skill_accuracy": skill_accuracy,

            "overall_attempts": total_attempts,

            "overall_accuracy": overall_accuracy,

            "is_correct": int(
                attempt.is_correct
            )
        }

        features.append(feature_row)

    return features