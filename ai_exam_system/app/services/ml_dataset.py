
from datetime import datetime, timezone
import math

from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_attempt import QuestionAttempt


DECAY_RATE = 0.05


def to_utc(value):
    """Convert a datetime to timezone-aware UTC."""
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def get_time_factor(time_taken):
    """Estimate the influence of response speed."""
    if time_taken is None:
        return 1.0
    if time_taken <= 10:
        return 1.20
    if time_taken <= 30:
        return 1.00
    if time_taken <= 60:
        return 0.85
    if time_taken <= 120:
        return 0.70
    return 0.55


def get_learning_rate(difficulty):
    """Assign a baseline learning rate by question difficulty."""
    if difficulty <= 1:
        return 0.10
    if difficulty == 2:
        return 0.20
    return 0.30


def build_ml_dataset(db: Session, user_id):
    """
    Build sequential training samples.

    Each sample uses only information available before the
    current answer. The current answer becomes the target.
    """

    records = (
        db.query(QuestionAttempt, Question)
        .join(
            Question,
            Question.id == QuestionAttempt.question_id
        )
        .filter(
            QuestionAttempt.user_id == user_id
        )
        .order_by(
            QuestionAttempt.created_at.asc(),
            QuestionAttempt.id.asc()
        )
        .all()
    )

    if not records:
        return []

    dataset = []

    total_attempts = 0
    total_correct = 0
    previous_attempt_time = None
    previous_response_time = None
    previous_is_correct = None

    skill_stats = {}

    for attempt, question in records:
        current_time = to_utc(attempt.created_at)

        skill_key = (
            question.domain,
            question.skill
        )

        if skill_key not in skill_stats:
            skill_stats[skill_key] = {
                "attempts": 0,
                "correct": 0,
                "mastery": 0.50,
                "last_attempt": None
            }

        stats = skill_stats[skill_key]

        # Calculate features using history BEFORE this answer.
        skill_attempts = stats["attempts"]
        skill_accuracy = (
            stats["correct"] / skill_attempts
            if skill_attempts > 0
            else 0.0
        )

        overall_accuracy = (
            total_correct / total_attempts
            if total_attempts > 0
            else 0.0
        )

        mastery_before = stats["mastery"]

        last_skill_attempt = stats["last_attempt"]

        if last_skill_attempt is None:
            retention_before = 1.0
            days_since_skill_attempt = None
        else:
            elapsed = (
                current_time - last_skill_attempt
            ).total_seconds()

            days_since_skill_attempt = max(
                0.0,
                elapsed / 86400
            )

            retention_before = math.exp(
                -DECAY_RATE * days_since_skill_attempt
            )

        effective_knowledge_before = (
            mastery_before * retention_before
        )

        if previous_attempt_time is None:
            seconds_since_previous_attempt = None
        else:
            seconds_since_previous_attempt = max(
                0.0,
                (
                    current_time - previous_attempt_time
                ).total_seconds()
            )

        # Predicting correctness BEFORE the current answer:
        # do not use attempt.time_taken or attempt.is_correct
        # as input features.
        feature_row = {
            "domain": question.domain,
            "skill": question.skill,
            "question_difficulty": question.difficulty,
            "skill_attempts_before": skill_attempts,
            "skill_accuracy_before": round(
                skill_accuracy, 4
            ),
            "overall_attempts_before": total_attempts,
            "overall_accuracy_before": round(
                overall_accuracy, 4
            ),
            "mastery_before": round(
                mastery_before, 4
            ),
            "retention_before": round(
                retention_before, 4
            ),
            "effective_knowledge_before": round(
                effective_knowledge_before, 4
            ),
            "days_since_skill_attempt": (
                round(days_since_skill_attempt, 4)
                if days_since_skill_attempt is not None
                else None
            ),
            "seconds_since_previous_attempt": (
                round(seconds_since_previous_attempt, 2)
                if seconds_since_previous_attempt is not None
                else None
            ),
            "previous_response_time": previous_response_time,
            "previous_is_correct": previous_is_correct,

            # Target: the outcome of the current answer.
            "target_is_correct": int(attempt.is_correct)
        }

        dataset.append(feature_row)

        # Update historical state AFTER recording the sample.
        # These values become available to later samples.
        total_attempts += 1

        if attempt.is_correct:
            total_correct += 1

        stats["attempts"] += 1

        if attempt.is_correct:
            stats["correct"] += 1

        learning_rate = (
            get_learning_rate(question.difficulty)
            * get_time_factor(attempt.time_taken)
        )

        if attempt.is_correct:
            stats["mastery"] += (
                learning_rate * (1 - stats["mastery"])
            )
        else:
            stats["mastery"] -= (
                learning_rate * stats["mastery"]
            )

        stats["mastery"] = max(
            0.0,
            min(1.0, stats["mastery"])
        )

        stats["last_attempt"] = current_time

        previous_attempt_time = current_time
        previous_response_time = attempt.time_taken
        previous_is_correct = int(attempt.is_correct)

    return dataset
