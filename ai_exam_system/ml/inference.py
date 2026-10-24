"""
Model inference module.

Loads the trained performance model from disk and provides a single
function predict_correctness_probability() that returns the probability
that a student will answer a question correctly.

If no model artifact exists yet (before the first training run), the
function returns 0.5 (maximum uncertainty) with a logged warning.
This allows the adaptive engine to fall back to its heuristic scorer
without crashing.
"""

import json
import logging
import warnings
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Directory where artifacts are stored
_ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"

# Module-level cache so the model is only loaded from disk once per process
_model = None
_schema = None
_model_load_attempted = False


def _load_model():
    """
    Attempt to load the trained model and feature schema from disk.

    Sets module-level _model and _schema. If loading fails, logs a
    warning and leaves both as None so callers can fall back gracefully.
    """

    global _model, _schema, _model_load_attempted
    _model_load_attempted = True

    model_path = _ARTIFACTS_DIR / "performance_model.pkl"
    schema_path = _ARTIFACTS_DIR / "feature_schema.json"

    if not model_path.exists():
        logger.warning(
            "Model artifact not found at %s. "
            "Run 'D:\\python\\python.exe -m ml.run_training' to train the model. "
            "Returning 0.5 (maximum uncertainty) until model is available.",
            model_path
        )
        return

    try:
        import joblib
        _model = joblib.load(model_path)
        logger.info("Performance model loaded from %s", model_path)
    except Exception as exc:
        logger.warning("Failed to load model: %s. Will use fallback.", exc)
        _model = None

    if not schema_path.exists():
        logger.warning("Feature schema not found. Model may receive incorrect inputs.")
        return

    try:
        with open(schema_path, "r") as f:
            _schema = json.load(f)
    except Exception as exc:
        logger.warning("Failed to load feature schema: %s", exc)
        _schema = None


def predict_correctness_probability(feature_dict: Dict[str, float]) -> float:
    """
    Predict the probability that a student answers a question correctly.

    Parameters
    ----------
    feature_dict : dict
        A dictionary containing the student's current state features.
        Expected keys (all are pre-answer state, not post-answer):
          - question_difficulty       (int 1-5)
          - skill_attempts_before     (int >= 0)
          - skill_accuracy_before     (float 0-1)
          - overall_attempts_before   (int >= 0)
          - overall_accuracy_before   (float 0-1)
          - mastery_before            (float 0-1)
          - retention_before          (float 0-1)
          - effective_knowledge_before (float 0-1)
          - days_since_skill_attempt  (float >= 0)
          - previous_is_correct       (float: 0, 0.5, or 1)
          - previous_response_time    (float, seconds)

    Returns
    -------
    float
        Probability between 0.0 and 1.0 that the student answers correctly.
        Returns 0.5 if the model is not available or inference fails.

    Notes
    -----
    The returned probability reflects the model's uncertainty given the
    student's observable state. It is not a ground-truth assessment.
    Use it as one signal in the adaptive selection, not as a final verdict.
    """

    global _model, _schema, _model_load_attempted

    # Lazy-load on first call
    if not _model_load_attempted:
        _load_model()

    if _model is None:
        return 0.5

    try:
        import numpy as np

        # Determine which features the model expects
        if _schema and "feature_columns" in _schema:
            feature_cols = _schema["feature_columns"]
            imputation = _schema.get("imputation", {})
        else:
            # Fallback: use all standard feature names
            feature_cols = [
                "question_difficulty", "skill_attempts_before",
                "skill_accuracy_before", "overall_attempts_before",
                "overall_accuracy_before", "mastery_before",
                "retention_before", "effective_knowledge_before",
                "days_since_skill_attempt", "previous_is_correct",
                "previous_response_time",
            ]
            imputation = {}

        # Build the feature vector in the expected column order
        feature_values = []
        for col in feature_cols:
            val = feature_dict.get(col)
            if val is None:
                # Use the imputation value from training, or 0 as last resort
                val = imputation.get(col, 0.0)
            feature_values.append(float(val))

        X = np.array(feature_values).reshape(1, -1)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            proba = _model.predict_proba(X)[0][1]

        # Clamp to (0.01, 0.99) to avoid log(0) issues downstream
        return float(max(0.01, min(0.99, proba)))

    except Exception as exc:
        logger.warning(
            "Inference failed (%s). Returning 0.5 as fallback.", exc
        )
        return 0.5


def reset_model_cache():
    """
    Force the model to be reloaded from disk on the next inference call.

    Call this after running a new training job so the API picks up the
    updated model without requiring a server restart.
    """

    global _model, _schema, _model_load_attempted
    _model = None
    _schema = None
    _model_load_attempted = False
    logger.info("Model cache cleared. Will reload on next inference call.")
