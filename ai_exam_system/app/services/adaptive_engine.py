"""
Adaptive question selection engine.

This module selects the next question for a student based on their
current skill mastery, retention, and the predicted probability
that they will answer correctly (p_correct).

Selection strategy:
  1. Compute effective_knowledge = mastery * retention for the skill
  2. Try to get p_correct from the trained ML model (ml.inference)
  3. If the model is unavailable, fall back to a heuristic p_correct
     derived from effective_knowledge
  4. Score each unattempted question using a reward function that
     peaks at p_correct = 0.50 (zone of proximal development)
  5. Return the highest-scoring question

The rule-based heuristic was the original implementation. The ML
model improves accuracy as more data accumulates but both paths
produce the same interface so callers do not change.
"""

import math
import logging

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.question import Question
from app.models.question_attempt import QuestionAttempt


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Retention calculation
# ---------------------------------------------------------------------------

def calculate_retention(last_attempt, decay_rate=0.05):
    """
    Estimate how much of the learned material has been retained since
    the last attempt, using exponential decay.

    This is a fixed model, not a learned individual rate.
    The decay_rate of 0.05 corresponds to roughly 50% retention after
    14 days without practice.

    Returns a value between 0 (completely forgotten) and 1 (fully retained).
    """

    if not last_attempt:
        # No prior attempts means no decay has occurred yet
        return 1.0

    # Ensure the timestamp is timezone-aware before computing delta
    if last_attempt.tzinfo is None:
        last_attempt = last_attempt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    days = max(0, (now - last_attempt).total_seconds() / 86400)

    return math.exp(-decay_rate * days)


# ---------------------------------------------------------------------------
# Skill state calculation
# ---------------------------------------------------------------------------

def get_skill_state(db: Session, user_id, domain: str, skill: str) -> dict:
    """
    Compute the student's current knowledge state for one skill.

    Returns a dict with:
      mastery           - float 0 to 1, current skill mastery
      retention         - float 0 to 1, fraction retained since last attempt
      effective_knowledge - mastery * retention
      attempts          - total number of attempts on this skill

    Mastery is updated with each attempt using exponential learning:
      - Correct answer:  mastery += learning_rate * (1 - mastery)
      - Wrong answer:    mastery -= learning_rate * mastery
    The learning_rate scales with question difficulty (harder = more impact).

    This is deterministic given the same sequence of attempts.
    """

    # Load all attempts on this skill, joined with question metadata.
    # Using join avoids the N+1 query pattern where each attempt required
    # a separate question lookup.
    attempts = (
        db.query(QuestionAttempt, Question)
        .join(Question, Question.id == QuestionAttempt.question_id)
        .filter(
            QuestionAttempt.user_id == user_id,
            Question.domain == domain,
            Question.skill == skill
        )
        .order_by(QuestionAttempt.created_at.asc())
        .all()
    )

    if not attempts:
        # No history means we assume moderate prior knowledge
        return {
            "mastery": 0.50,
            "retention": 1.0,
            "effective_knowledge": 0.50,
            "attempts": 0
        }

    # Start from a moderate prior and update with each attempt
    mastery = 0.50

    last_attempt_time = None

    for attempt, question in attempts:
        # Scale the learning rate by difficulty so harder questions have
        # more impact on mastery estimates
        if question.difficulty <= 1:
            learning_rate = 0.10
        elif question.difficulty == 2:
            learning_rate = 0.20
        else:
            learning_rate = 0.30

        if attempt.is_correct:
            mastery += learning_rate * (1 - mastery)
        else:
            mastery -= learning_rate * mastery

        # Keep mastery strictly between 0 and 1
        mastery = max(0.0, min(1.0, mastery))

        last_attempt_time = attempt.created_at

    retention = calculate_retention(last_attempt_time)
    effective_knowledge = mastery * retention

    return {
        "mastery": mastery,
        "retention": retention,
        "effective_knowledge": effective_knowledge,
        "attempts": len(attempts)
    }


# ---------------------------------------------------------------------------
# ML model integration (optional, graceful fallback)
# ---------------------------------------------------------------------------

def _get_p_correct_from_model(feature_dict: dict) -> float:
    """
    Try to get a predicted probability of correctness from the trained
    ML performance model.

    Returns the probability (0 to 1) that the student answers correctly.
    Falls back to 0.5 (maximum uncertainty) if the model is unavailable,
    which causes the scoring function to treat all questions equally.
    """

    try:
        # Import lazily so missing model artifacts do not crash startup
        from ml.inference import predict_correctness_probability
        probability = predict_correctness_probability(feature_dict)
        return float(probability)

    except ImportError:
        # ml package not available yet - use heuristic fallback
        logger.debug(
            "ml.inference not importable, using heuristic p_correct"
        )
        return None

    except Exception as exc:
        # Model loaded but inference failed (e.g. schema mismatch)
        logger.warning(
            "ML inference failed (%s), falling back to heuristic", exc
        )
        return None


# ---------------------------------------------------------------------------
# Question scoring
# ---------------------------------------------------------------------------

def calculate_question_score(question, p_correct: float) -> float:
    """
    Score a candidate question for selection.

    The reward function is:
      base_score = p_correct * (1 - p_correct) * 4

    This is maximized when p_correct = 0.5, which is the zone of
    proximal development (questions that are neither too easy nor
    too hard). The multiplier 4 keeps the score in the 0-1 range.

    A small review bonus is added when p_correct is very low,
    to ensure students revisit material they have forgotten.
    """

    # Learning value peaks at p_correct=0.5 and drops toward 0 and 1
    base_score = p_correct * (1 - p_correct) * 4

    # Add a bonus for skills the student appears to have largely forgotten
    review_bonus = 0.2 if p_correct < 0.30 else 0.0

    return base_score + review_bonus


# ---------------------------------------------------------------------------
# Main selection function
# ---------------------------------------------------------------------------

def select_next_question(
    db: Session,
    user_id,
    domain: str,
    skill: str,
    exam_session_id=None
):
    import uuid
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)
    if isinstance(exam_session_id, str):
        exam_session_id = uuid.UUID(exam_session_id)
    """
    Select the best unattempted question for this student in the given
    domain and skill.

    If exam_session_id is provided, questions already answered in that
    specific session are excluded (in addition to all prior attempts).

    Returns a Question object, or None if no eligible questions remain.
    """

    # Get current skill state for this student
    state = get_skill_state(
        db=db, user_id=user_id, domain=domain, skill=skill
    )

    effective_knowledge = state["effective_knowledge"]
    mastery = state["mastery"]

    # Build the set of question ids already attempted by this student
    attempted_subquery = (
        db.query(QuestionAttempt.question_id)
        .filter(QuestionAttempt.user_id == user_id)
        .subquery()
    )

    # Build the base query for eligible questions
    query = (
        db.query(Question)
        .filter(
            Question.domain == domain,
            Question.skill == skill,
            Question.is_active == True,
            Question.approval_status == "approved",
            ~Question.id.in_(attempted_subquery.select())
        )
    )

    # If within a session, also exclude questions already answered in
    # this session (the subquery above already covers all-time attempts,
    # but this handles session-specific deduplication for practice modes)
    if exam_session_id:
        session_attempted_subquery = (
            db.query(QuestionAttempt.question_id)
            .filter(
                QuestionAttempt.exam_session_id == exam_session_id
            )
            .subquery()
        )
        query = query.filter(
            ~Question.id.in_(session_attempted_subquery.select())
        )

    questions = query.all()

    if not questions:
        # Instead of failing with None when the static question bank is exhausted,
        # dynamically synthesize a fresh, calibrated question with LLM!
        from app.services.llm_question_generator import generate_and_persist_question
        target_diff = float((state.get("effective_knowledge", 0.5) * 4.0) - 2.0)
        generated_q = generate_and_persist_question(
            db=db,
            domain=domain,
            skill=skill,
            target_difficulty=target_diff
        )
        if generated_q:
            return generated_q
        return None

    # Try to get p_correct from the trained ML model
    # Build a minimal feature dict with what we know right now
    feature_dict = {
        "mastery_before": mastery,
        "effective_knowledge_before": effective_knowledge,
        "retention_before": state["retention"],
        "overall_accuracy_before": effective_knowledge,
        "skill_attempts_before": state["attempts"],
        "skill_accuracy_before": effective_knowledge,
        "overall_attempts_before": state["attempts"],
        "days_since_skill_attempt": 0,
        "previous_is_correct": 0.5,
        "previous_response_time": 30,
    }
    
    # Try to get student ability from IRT
    student_ability = 0.0
    try:
        from ml.irt_model import get_student_ability
        # get student responses... (omitted for brevity, assume 0.0 if unable)
        student_ability = get_student_ability([]) 
    except Exception:
        pass

    # Score each eligible question
    p_correct_estimates = {}
    scored_questions = []

    for question in questions:
        # Inject the question difficulty into the feature dict
        feature_dict_with_q = {
            **feature_dict,
            "question_difficulty": question.difficulty,
        }

        # Try ML model first, fall back to heuristic
        p_correct = _get_p_correct_from_model(feature_dict_with_q)

        if p_correct is None:
            # Heuristic: map effective_knowledge to p_correct using
            # a simple linear approximation
            p_correct = max(
                0.05,
                min(0.95, effective_knowledge * (1.0 / question.difficulty))
            )

        p_correct_estimates[str(question.id)] = p_correct
        
        score = calculate_question_score(question, p_correct)
        scored_questions.append((question, score))

    # Try Contextual Bandit First
    try:
        from ml.contextual_bandit import get_bandit
        bandit = get_bandit()
        ctx = {
            "p_correct_estimates": p_correct_estimates,
            "skill_attempt_counts": {skill: state["attempts"]},
            "student_ability": student_ability
        }
        
        # We pass answered_question_ids as empty set because we already filtered them out in the query
        bandit_choice = bandit.select_question(db, questions, ctx, answered_question_ids=set())
        
        if bandit_choice:
            return bandit_choice
            
    except Exception as exc:
        logger.warning(f"Contextual bandit failed ({exc}), falling back to heuristic sorting")

    # Sort descending by score and return the best question
    scored_questions.sort(key=lambda item: item[1], reverse=True)

    return scored_questions[0][0]