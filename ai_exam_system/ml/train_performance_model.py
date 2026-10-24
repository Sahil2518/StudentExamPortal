"""
Correctness prediction model training pipeline.

Trains four classifiers to predict whether a student will answer a
question correctly, given their current knowledge state before seeing
the question. The target variable is binary: 1 = correct, 0 = wrong.

Models trained:
  1. Logistic Regression (interpretable baseline)
  2. LightGBM
  3. XGBoost
  4. CatBoost

Each model is tuned with Optuna (max 30 trials per model, 2 min timeout).
The winner is selected by ROC-AUC on the validation split and calibrated
with isotonic regression before saving.

Data source:
  - Primary: real attempt data from the database via build_ml_dataset()
  - Fallback: clearly labeled synthetic smoke-test data when fewer than
    50 real samples exist. Synthetic metrics are NOT reported as real.

Leakage policy:
  All features are computed from the student's state BEFORE they see the
  question and submit an answer. The target (is_correct) is what happened
  AFTER. This matches ml_dataset.py which is already leakage-safe.

Usage:
    D:\\python\\python.exe -m ml.run_training
"""

import os
import sys
import json
import time
import warnings
import logging
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path so app imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Suppress verbose output from ML libraries during training
warnings.filterwarnings("ignore", category=UserWarning)
logging.basicConfig(level=logging.WARNING)

# Feature column names - must match what ml_dataset.py produces
FEATURE_COLUMNS = [
    "question_difficulty",
    "skill_attempts_before",
    "skill_accuracy_before",
    "overall_attempts_before",
    "overall_accuracy_before",
    "mastery_before",
    "retention_before",
    "effective_knowledge_before",
    "days_since_skill_attempt",
    "previous_is_correct",
    "previous_response_time",
]

TARGET_COLUMN = "target_is_correct"

# Directory where model artifacts are saved
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"


def ensure_artifacts_dir():
    """Create the artifacts directory if it does not exist."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def load_real_data() -> pd.DataFrame:
    """
    Load training data from the database by calling build_ml_dataset()
    for every student who has attempt history.

    Returns an empty DataFrame if the database is unreachable or empty.
    """

    try:
        # Import init_db first to ensure ALL models are registered with
        # SQLAlchemy's mapper. Without this, relationship() calls on User
        # fail because StudentProfile hasn't been imported yet.
        from app.database.init_db import init_db  # noqa: F401 - side effect import
        from app.database.connection import SessionLocal
        from app.models.user import User
        from app.services.ml_dataset import build_ml_dataset

        db = SessionLocal()
        rows = []

        try:
            users = db.query(User).all()
            for user in users:
                user_rows = build_ml_dataset(db=db, user_id=user.id)
                for r in user_rows:
                    r["student_id"] = str(user.id)
                rows.extend(user_rows)
        finally:
            db.close()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        print(f"Loaded {len(df)} real samples from {len(users)} users.")
        return df

    except Exception as exc:
        print(f"Could not load real data: {exc}")
        return pd.DataFrame()


def generate_synthetic_data(n_samples: int = 500) -> pd.DataFrame:
    """
    Generate clearly labeled synthetic training data for smoke-testing
    the pipeline when real data is insufficient.

    THIS DATA IS SYNTHETIC. Any metrics computed from it are not valid
    indicators of real-world model performance. They are only used to
    confirm the training pipeline runs without errors.

    The synthetic data follows a simple rule: students with higher
    mastery and lower question difficulty are more likely to be correct.
    """

    rng = np.random.RandomState(42)
    n = n_samples

    mastery = rng.uniform(0.0, 1.0, n)
    difficulty = rng.randint(1, 6, n).astype(float)
    retention = rng.uniform(0.3, 1.0, n)
    skill_accuracy = rng.uniform(0.0, 1.0, n)
    previous_correct = rng.choice([0.0, 0.5, 1.0], n)

    # Simple synthetic rule: higher mastery - higher difficulty -> more correct
    p_correct = np.clip(mastery - (difficulty - 3) * 0.15 + rng.normal(0, 0.1, n), 0.05, 0.95)
    target = (rng.uniform(0, 1, n) < p_correct).astype(int)

    student_ids = [f"student_{i}" for i in rng.randint(0, 50, n)]

    df = pd.DataFrame({
        "student_id": student_ids,
        "question_difficulty": difficulty,
        "skill_attempts_before": rng.randint(0, 20, n).astype(float),
        "skill_accuracy_before": skill_accuracy,
        "overall_attempts_before": rng.randint(0, 50, n).astype(float),
        "overall_accuracy_before": skill_accuracy * rng.uniform(0.8, 1.2, n),
        "mastery_before": mastery,
        "retention_before": retention,
        "effective_knowledge_before": mastery * retention,
        "days_since_skill_attempt": rng.exponential(3, n),
        "previous_is_correct": previous_correct,
        "previous_response_time": rng.uniform(5, 120, n),
        TARGET_COLUMN: target,
    })

    df["overall_accuracy_before"] = df["overall_accuracy_before"].clip(0, 1)
    return df


def preprocess(df: pd.DataFrame, imputation_dict=None):
    """
    Prepare features and target for training/inference.
    
    If imputation_dict is None (e.g. for training set), computes medians.
    If provided (e.g. for val/test), applies the provided medians to prevent leakage.
    """
    df = df.dropna(subset=[TARGET_COLUMN]).copy()

    available_features = [c for c in FEATURE_COLUMNS if c in df.columns]
    X = df[available_features].copy()
    y = df[TARGET_COLUMN].astype(int)

    if imputation_dict is None:
        imputation_dict = {}
        for col in available_features:
            if col == "previous_is_correct":
                imputation_dict[col] = 0.5
            else:
                imputation_dict[col] = float(X[col].median())

    for col, val in imputation_dict.items():
        if col in X.columns:
            X[col] = X[col].fillna(val)

    return X, y, imputation_dict, available_features


def train_and_evaluate(X_train, X_val, X_test, y_train, y_val, y_test, use_synthetic: bool):
    """
    Train all four model types, tune with Optuna, pick the winner,
    calibrate, and return results.

    Returns a dict with model objects and evaluation metrics.
    """

    from sklearn.linear_model import LogisticRegression
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.metrics import roc_auc_score, average_precision_score, log_loss, brier_score_loss
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    results = {}

    # -----------------------------------------------------------------------
    # Model 1: Logistic Regression (baseline)
    # -----------------------------------------------------------------------
    print("  Training Logistic Regression...")

    def lr_objective(trial):
        C = trial.suggest_float("C", 1e-3, 10.0, log=True)
        clf = LogisticRegression(C=C, max_iter=500, random_state=42)
        clf.fit(X_train, y_train)
        return roc_auc_score(y_val, clf.predict_proba(X_val)[:, 1])

    lr_study = optuna.create_study(direction="maximize")
    lr_study.optimize(lr_objective, n_trials=20, timeout=60, show_progress_bar=False)

    best_lr = LogisticRegression(
        C=lr_study.best_params["C"], max_iter=500, random_state=42
    )
    best_lr.fit(X_train, y_train)
    lr_val_auc = roc_auc_score(y_val, best_lr.predict_proba(X_val)[:, 1])
    results["logistic_regression"] = {"model": best_lr, "val_auc": lr_val_auc}
    print(f"     Val ROC-AUC: {lr_val_auc:.4f}")

    # -----------------------------------------------------------------------
    # Model 2: LightGBM
    # -----------------------------------------------------------------------
    try:
        import lightgbm as lgb
        print("  Training LightGBM...")

        def lgb_objective(trial):
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 50, 400),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "max_depth": trial.suggest_int("max_depth", 3, 8),
                "num_leaves": trial.suggest_int("num_leaves", 15, 63),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "random_state": 42,
                "verbose": -1,
            }
            clf = lgb.LGBMClassifier(**params)
            clf.fit(X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    callbacks=[lgb.early_stopping(10, verbose=False), lgb.log_evaluation(-1)])
            return roc_auc_score(y_val, clf.predict_proba(X_val)[:, 1])

        lgb_study = optuna.create_study(direction="maximize")
        lgb_study.optimize(lgb_objective, n_trials=30, timeout=120, show_progress_bar=False)

        best_lgb = lgb.LGBMClassifier(**lgb_study.best_params, random_state=42, verbose=-1)
        best_lgb.fit(X_train, y_train)
        lgb_val_auc = roc_auc_score(y_val, best_lgb.predict_proba(X_val)[:, 1])
        results["lightgbm"] = {"model": best_lgb, "val_auc": lgb_val_auc}
        print(f"     Val ROC-AUC: {lgb_val_auc:.4f}")

    except ImportError:
        print("  LightGBM not installed, skipping.")

    # -----------------------------------------------------------------------
    # Model 3: XGBoost
    # -----------------------------------------------------------------------
    try:
        import xgboost as xgb
        print("  Training XGBoost...")

        def xgb_objective(trial):
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 50, 400),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "max_depth": trial.suggest_int("max_depth", 3, 8),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "gamma": trial.suggest_float("gamma", 0, 1.0),
                # early_stopping_rounds is a constructor param in XGBoost 2.x
                "early_stopping_rounds": 10,
                "eval_metric": "logloss",
                "random_state": 42,
                "verbosity": 0,
            }
            clf = xgb.XGBClassifier(**params)
            clf.fit(X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    verbose=False)
            return roc_auc_score(y_val, clf.predict_proba(X_val)[:, 1])

        xgb_study = optuna.create_study(direction="maximize")
        xgb_study.optimize(xgb_objective, n_trials=30, timeout=120, show_progress_bar=False)

        best_xgb = xgb.XGBClassifier(
            **{k: v for k, v in xgb_study.best_params.items()},
            eval_metric="logloss", random_state=42, verbosity=0
        )
        best_xgb.fit(X_train, y_train)
        xgb_val_auc = roc_auc_score(y_val, best_xgb.predict_proba(X_val)[:, 1])
        results["xgboost"] = {"model": best_xgb, "val_auc": xgb_val_auc}
        print(f"     Val ROC-AUC: {xgb_val_auc:.4f}")

    except ImportError:
        print("  XGBoost not installed, skipping.")

    # -----------------------------------------------------------------------
    # Model 4: CatBoost
    # -----------------------------------------------------------------------
    try:
        from catboost import CatBoostClassifier
        print("  Training CatBoost...")

        def cat_objective(trial):
            params = {
                "iterations": trial.suggest_int("iterations", 50, 400),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "depth": trial.suggest_int("depth", 3, 8),
                "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
                "random_seed": 42,
                "verbose": False,
                "allow_writing_files": False,
            }
            clf = CatBoostClassifier(**params)
            clf.fit(X_train, y_train, eval_set=(X_val, y_val),
                    early_stopping_rounds=10, verbose=False)
            return roc_auc_score(y_val, clf.predict_proba(X_val)[:, 1])

        cat_study = optuna.create_study(direction="maximize")
        cat_study.optimize(cat_objective, n_trials=30, timeout=120, show_progress_bar=False)

        best_cat = CatBoostClassifier(
            **cat_study.best_params, random_seed=42, verbose=False, allow_writing_files=False
        )
        best_cat.fit(X_train, y_train)
        cat_val_auc = roc_auc_score(y_val, best_cat.predict_proba(X_val)[:, 1])
        results["catboost"] = {"model": best_cat, "val_auc": cat_val_auc}
        print(f"     Val ROC-AUC: {cat_val_auc:.4f}")

    except ImportError:
        print("  CatBoost not installed, skipping.")

    # -----------------------------------------------------------------------
    # Pick winner by validation ROC-AUC
    # -----------------------------------------------------------------------
    winner_name = max(results, key=lambda k: results[k]["val_auc"])
    winner_model = results[winner_name]["model"]
    print(f"\n  Winner: {winner_name} (val AUC = {results[winner_name]['val_auc']:.4f})")

    # Calibrate the winner if enough validation data exists
    if len(X_val) >= 20:
        print("  Calibrating winner with isotonic regression...")
        winner_model = CalibratedClassifierCV(
            winner_model, method="isotonic", cv="prefit"
        )
        winner_model.fit(X_val, y_val)

    # Evaluate on test set
    y_test_proba = winner_model.predict_proba(X_test)[:, 1]

    test_metrics = {
        "roc_auc": round(float(roc_auc_score(y_test, y_test_proba)), 4),
        "pr_auc": round(float(average_precision_score(y_test, y_test_proba)), 4),
        "log_loss": round(float(log_loss(y_test, y_test_proba)), 4),
        "brier_score": round(float(brier_score_loss(y_test, y_test_proba)), 4),
    }

    return winner_name, winner_model, test_metrics


def run_training() -> dict:
    """
    Full training pipeline.

    Returns a summary dict with the result, winner, and test metrics.
    """

    import joblib
    from sklearn.model_selection import train_test_split

    ensure_artifacts_dir()

    print("Loading data...")
    df = load_real_data()

    use_synthetic = False
    if len(df) < 50:
        print(
            f"Only {len(df)} real samples found (need at least 50). "
            "Falling back to SYNTHETIC data for smoke-test. "
            "Metrics from synthetic data are NOT valid real-world estimates."
        )
        df = generate_synthetic_data(n_samples=500)
        use_synthetic = True

    print(f"Total samples: {len(df)}")
    print(f"Data source: {'SYNTHETIC (smoke-test only)' if use_synthetic else 'REAL database records'}")
    print(f"Class balance: {df[TARGET_COLUMN].mean():.1%} correct answers\n")

    from sklearn.model_selection import GroupShuffleSplit
    
    # 80/10/10 student-grouped split to prevent temporal/student leakage
    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
    train_idx, temp_idx = next(gss1.split(df, groups=df["student_id"]))
    
    df_train = df.iloc[train_idx]
    df_temp = df.iloc[temp_idx]
    
    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=42)
    val_idx, test_idx = next(gss2.split(df_temp, groups=df_temp["student_id"]))
    
    df_val = df_temp.iloc[val_idx]
    df_test = df_temp.iloc[test_idx]

    # Preprocess: fit imputation on train only, transform val/test
    X_train, y_train, imputation, feature_cols = preprocess(df_train, imputation_dict=None)
    X_val, y_val, _, _ = preprocess(df_val, imputation_dict=imputation)
    X_test, y_test, _, _ = preprocess(df_test, imputation_dict=imputation)

    print(f"Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}\n")

    print("Training models...")
    winner_name, winner_model, test_metrics = train_and_evaluate(
        X_train, X_val, X_test, y_train, y_val, y_test, use_synthetic
    )

    # Save the winner model
    model_path = ARTIFACTS_DIR / "performance_model.pkl"
    joblib.dump(winner_model, model_path)
    print(f"\nModel saved: {model_path}")

    # Save feature schema so inference can validate inputs
    schema = {
        "feature_columns": feature_cols,
        "imputation": imputation,
        "target": TARGET_COLUMN,
    }
    schema_path = ARTIFACTS_DIR / "feature_schema.json"
    with open(schema_path, "w") as f:
        json.dump(schema, f, indent=2)
    print(f"Schema saved: {schema_path}")

    # Save evaluation report
    report = {
        "winner_model": winner_name,
        "data_source": "synthetic" if use_synthetic else "real",
        "sample_count": len(df),
        "train_size": len(X_train),
        "val_size": len(X_val),
        "test_size": len(X_test),
        "test_metrics": test_metrics,
        "important_caveat": (
            "Metrics are from SYNTHETIC data and do not represent real performance."
            if use_synthetic
            else "Metrics computed on held-out real student data."
        ),
    }
    report_path = ARTIFACTS_DIR / "evaluation_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    report = run_training()
    print("\n--- Training Complete ---")
    print(f"Winner: {report['winner_model']}")
    print(f"Data: {report['data_source']} ({report['sample_count']} samples)")
    print(f"Test ROC-AUC: {report['test_metrics']['roc_auc']}")
    if report["data_source"] == "synthetic":
        print("\nNOTE: These metrics are from synthetic data. Run again after")
        print("students complete real exam sessions to get meaningful scores.")
