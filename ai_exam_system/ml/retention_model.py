"""
Retention model for the AI Adaptive Exam System.

Uses exponential decay to estimate how much of a learned skill
the student has retained since their last practice session.

This is a fixed population-level model, not a learned individual rate.
The decay parameter lambda=0.05 was chosen based on spaced repetition
research (roughly 50% retention after 14 days without practice).

To use a learned individual rate, you would need at least 5-10 spaced
practice sessions per student per skill, which most students will not
have at this stage. Document this clearly and do not pretend this is
personalized to the individual.
"""

import math
from datetime import datetime, timezone


# The decay constant used in R(t) = exp(-LAMBDA * t_days).
# Higher values mean faster forgetting.
# 0.05 gives approximately:
#   1 day   -> 95% retained
#   7 days  -> 70% retained
#   14 days -> 50% retained
#   30 days -> 22% retained
LAMBDA = 0.05


def estimate_retention(
    last_attempt_datetime: datetime,
    now_datetime: datetime = None
) -> float:
    """
    Estimate the fraction of learned material retained at the given time.

    Parameters
    ----------
    last_attempt_datetime : datetime
        When the student last practiced this skill.
        Can be naive (assumed UTC) or timezone-aware.

    now_datetime : datetime, optional
        The current time. Defaults to datetime.now(UTC).
        Pass an explicit value in tests for reproducibility.

    Returns
    -------
    float
        Retention value between 0.0 (completely forgotten) and 1.0
        (fully retained). Never returns exactly 0 because the model
        uses a pure exponential which approaches 0 asymptotically.

    Notes
    -----
    If last_attempt_datetime is in the future (e.g. due to clock skew),
    retention is clamped to 1.0 rather than returning a value > 1.
    """

    if now_datetime is None:
        now_datetime = datetime.now(timezone.utc)

    # Ensure both datetimes are timezone-aware
    if last_attempt_datetime.tzinfo is None:
        last_attempt_datetime = last_attempt_datetime.replace(
            tzinfo=timezone.utc
        )

    if now_datetime.tzinfo is None:
        now_datetime = now_datetime.replace(tzinfo=timezone.utc)

    # Compute elapsed time in days
    elapsed_seconds = (now_datetime - last_attempt_datetime).total_seconds()
    elapsed_days = elapsed_seconds / 86400.0

    # Clamp to zero in case of clock skew (future last_attempt)
    elapsed_days = max(0.0, elapsed_days)

    return math.exp(-LAMBDA * elapsed_days)


def effective_knowledge(mastery: float, retention: float) -> float:
    """
    Combine mastery and retention into a single effective knowledge score.

    Effective knowledge represents how much of the student's peak mastery
    they can currently access. A student with mastery=0.9 but retention=0.3
    can access 0.27 of the full skill — they knew it well but have forgotten
    most of it since last practicing.

    Parameters
    ----------
    mastery : float
        The student's peak skill level (0 to 1).

    retention : float
        The fraction retained since last practice (0 to 1).

    Returns
    -------
    float
        Effective knowledge value between 0 and 1.
    """

    # Clamp inputs to valid range before multiplying
    mastery = max(0.0, min(1.0, mastery))
    retention = max(0.0, min(1.0, retention))

    return mastery * retention


def no_prior_retention() -> float:
    """
    Return the retention value for a skill that has never been practiced.

    When a student has never attempted a skill, there is nothing to forget.
    Retention starts at 1.0 (100%), meaning whatever mastery prior they
    have is not decayed.
    """
    return 1.0
