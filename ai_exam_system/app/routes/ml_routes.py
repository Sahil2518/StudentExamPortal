"""
ML model management routes.

These routes allow an authorized model admin (admin role) to:
  - Trigger a training run
  - Check training status
  - Get the current evaluation report
  - Reload the model without restarting the server

The actual training runs in a background thread so the HTTP request
returns immediately with a status, and the caller polls for completion.
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.current_user import require_admin
from app.models.user import User


router = APIRouter(prefix="/ml", tags=["ML"])

# Path to the artifacts directory
ARTIFACTS_DIR = (
    Path(__file__).resolve().parent.parent / "ml" / "artifacts"
)

# Simple in-process training status tracker
# In production this would be a proper task queue
_training_status = {
    "is_running": False,
    "last_started": None,
    "last_finished": None,
    "last_result": None,
    "error": None,
}


def _run_training_in_background():
    """
    Execute the training pipeline in a background thread.
    Updates _training_status before and after.
    """

    global _training_status
    _training_status["is_running"] = True
    _training_status["last_started"] = datetime.utcnow().isoformat()
    _training_status["error"] = None

    try:
        import sys
        sys.path.insert(
            0,
            str(Path(__file__).resolve().parent.parent)
        )
        from ml.train_performance_model import run_training
        report = run_training()
        _training_status["last_result"] = report

        # Clear the inference cache so the new model is used immediately
        from ml.inference import reset_model_cache
        reset_model_cache()

    except Exception as exc:
        _training_status["error"] = str(exc)

    finally:
        _training_status["is_running"] = False
        _training_status["last_finished"] = datetime.utcnow().isoformat()


@router.post(
    "/train",
    summary="Admin: trigger a model training run"
)
def trigger_training(
    current_user: User = Depends(require_admin)
):
    """
    Start a training run in the background.

    Returns immediately with the current training status.
    Poll GET /ml/status to check when training completes.

    Only one training run can be active at a time.
    """

    if _training_status["is_running"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A training run is already in progress. "
                "Check GET /ml/status for updates."
            )
        )

    # Start training in a background thread
    thread = threading.Thread(
        target=_run_training_in_background,
        daemon=True,
        name="ml-training"
    )
    thread.start()

    return {
        "message": "Training started in background",
        "status": "running",
        "started_by": current_user.email,
        "poll_at": "/ml/status"
    }


@router.get(
    "/status",
    summary="Get current model training status"
)
def get_training_status(
    current_user: User = Depends(require_admin)
):
    """Return the current state of the training pipeline."""

    return {
        "is_running": _training_status["is_running"],
        "last_started": _training_status["last_started"],
        "last_finished": _training_status["last_finished"],
        "error": _training_status["error"],
        "last_result": _training_status["last_result"],
    }


@router.get(
    "/evaluation-report",
    summary="Get the most recent model evaluation report"
)
def get_evaluation_report(
    current_user: User = Depends(require_admin)
):
    """
    Return the evaluation metrics from the last completed training run.

    The report includes test set ROC-AUC, PR-AUC, log-loss, and Brier
    score, along with whether the data was real or synthetic.
    """

    import json
    report_path = ARTIFACTS_DIR / "evaluation_report.json"

    if not report_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No evaluation report found. "
                "Run POST /ml/train first to generate one."
            )
        )

    with open(report_path, "r") as f:
        report = json.load(f)

    return report


@router.post(
    "/reload-model",
    summary="Admin: reload the model artifact without restarting the server"
)
def reload_model(
    current_user: User = Depends(require_admin)
):
    """
    Clear the in-memory model cache so the next inference call loads
    the latest artifact from disk.

    Use this after manually replacing the model artifact file.
    For normal training runs, the cache is cleared automatically.
    """

    try:
        from ml.inference import reset_model_cache
        reset_model_cache()
        return {"message": "Model cache cleared. New model will load on next inference."}
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML inference module is not available."
        )