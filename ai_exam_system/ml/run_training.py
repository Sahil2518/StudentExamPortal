"""
ML training entry point.

Run this to train the correctness prediction model:

    cd ai_exam_system
    D:\\python\\python.exe -m ml.run_training

What this does:
  1. Loads real attempt data from the database
  2. Falls back to synthetic data if fewer than 50 real samples exist
  3. Trains LogReg, LightGBM, XGBoost, and CatBoost
  4. Picks the winner by validation ROC-AUC
  5. Calibrates the winner
  6. Saves model to ml/artifacts/performance_model.pkl
  7. Saves evaluation report to ml/artifacts/evaluation_report.json
  8. Saves training log to ml/artifacts/training_log.txt
"""

import sys
import time
import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    start_time = time.time()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"AI Adaptive Exam System - Model Training")
    print(f"Started: {timestamp}")
    print("-" * 50)

    from ml.train_performance_model import run_training

    try:
        report = run_training()
    except Exception as exc:
        print(f"\nTraining failed with error: {exc}")
        raise

    elapsed = time.time() - start_time

    print("\n" + "=" * 50)
    print("TRAINING SUMMARY")
    print("=" * 50)
    print(f"Winner model:    {report['winner_model']}")
    print(f"Data source:     {report['data_source']}")
    print(f"Total samples:   {report['sample_count']}")
    print(f"Train / Val / Test: {report['train_size']} / {report['val_size']} / {report['test_size']}")
    print(f"Test ROC-AUC:    {report['test_metrics']['roc_auc']}")
    print(f"Test PR-AUC:     {report['test_metrics']['pr_auc']}")
    print(f"Test Log-Loss:   {report['test_metrics']['log_loss']}")
    print(f"Test Brier:      {report['test_metrics']['brier_score']}")
    print(f"Training time:   {elapsed:.1f}s")
    print()
    print(report["important_caveat"])

    # Write log to file
    log_path = PROJECT_ROOT / "ml" / "artifacts" / "training_log.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w") as f:
        f.write(f"Training run: {timestamp}\n")
        f.write(f"Winner: {report['winner_model']}\n")
        f.write(f"Data source: {report['data_source']}\n")
        f.write(f"Samples: {report['sample_count']}\n")
        f.write(f"Test ROC-AUC: {report['test_metrics']['roc_auc']}\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n")
        f.write(f"Caveat: {report['important_caveat']}\n")

    print(f"\nLog saved: {log_path}")

    # Log to MLflow if installed
    try:
        import mlflow
        with mlflow.start_run(run_name=f"performance_model_{timestamp}"):
            mlflow.log_param("data_source", report["data_source"])
            mlflow.log_param("sample_count", report["sample_count"])
            mlflow.log_param("winner_model", report["winner_model"])
            mlflow.log_metric("test_roc_auc", report["test_metrics"]["roc_auc"])
            mlflow.log_metric("test_pr_auc", report["test_metrics"]["pr_auc"])
            mlflow.log_metric("test_log_loss", report["test_metrics"]["log_loss"])
            mlflow.log_metric("test_brier", report["test_metrics"]["brier_score"])
            mlflow.log_artifact(str(PROJECT_ROOT / "ml" / "artifacts" / "performance_model.pkl"))
        print("Experiment tracked with MLflow.")
    except ImportError:
        print("MLflow not installed. Skipping MLflow tracking.")

    # Clear the inference cache so the API picks up the new model
    try:
        from ml.inference import reset_model_cache
        reset_model_cache()
        print("Inference cache cleared - new model is active.")
    except Exception:
        print("Note: restart the API server to activate the new model.")


if __name__ == "__main__":
    main()
