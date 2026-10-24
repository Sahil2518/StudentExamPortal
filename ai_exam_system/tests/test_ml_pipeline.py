import pytest
import pandas as pd
from datetime import datetime, timedelta

from ml.knowledge_tracing.sequence_builder import build_sequences_from_dataframe, validate_no_leakage
from ml.train_performance_model import preprocess
from ml.knowledge_tracing.bkt_model import BKTModel
from ml.contextual_bandit import ThompsonSamplingBandit

def test_no_leakage_in_sequence():
    """Verify that the sequence builder maintains chronological order and index."""
    df = pd.DataFrame({
        "student_id": ["u1", "u1", "u1"],
        "question_id": ["q1", "q2", "q3"],
        "skill": ["s1", "s1", "s1"],
        "difficulty": [1, 2, 3],
        "target_is_correct": [1, 0, 1],
        "time_taken": [10.0, 15.0, 20.0],
        "timestamp": [
            datetime.now() - timedelta(minutes=30),
            datetime.now() - timedelta(minutes=20),
            datetime.now() - timedelta(minutes=10)
        ]
    })
    
    sequences = build_sequences_from_dataframe(df)
    assert len(sequences) == 1
    
    # validate_no_leakage asserts that attempt_index matches the sequence index
    assert validate_no_leakage(sequences) == True

def test_imputer_fitted_only_on_train():
    """Verify that preprocess fits the imputer on train data and applies it to test data."""
    df_train = pd.DataFrame({
        "question_difficulty": [1, 2, 3],
        "target_is_correct": [1, 0, 1],
        "days_since_skill_attempt": [1.0, 2.0, 3.0] # Median is 2.0
    })
    
    X_train, y_train, imp_dict, _ = preprocess(df_train)
    assert imp_dict["days_since_skill_attempt"] == 2.0
    
    df_test = pd.DataFrame({
        "question_difficulty": [4, 5],
        "target_is_correct": [0, 1],
        "days_since_skill_attempt": [None, None]
    })
    
    X_test, _, _, _ = preprocess(df_test, imputation_dict=imp_dict)
    assert X_test["days_since_skill_attempt"].iloc[0] == 2.0

def test_bkt_probabilities():
    """Verify that BKT model predicts valid probabilities."""
    model = BKTModel()
    history = [1, 0, 1]
    skill = "math"
    
    mastery = model.predict_mastery(history, skill)
    assert 0.0 <= mastery <= 1.0
    
    p_next = model.predict_next_correct(history, skill)
    assert 0.0 <= p_next <= 1.0

def test_bandit_selects_eligible_question():
    """Verify bandit selects a valid eligible question respecting hard constraints."""
    class MockQuestion:
        def __init__(self, qid, skill, diff):
            self.id = qid
            self.skill = skill
            self.difficulty = diff

    q1 = MockQuestion("1", "math", 2)
    q2 = MockQuestion("2", "math", 4)
    q3 = MockQuestion("3", "science", 3)
    
    bandit = ThompsonSamplingBandit()
    ctx = {
        "p_correct_estimates": {"1": 0.5, "2": 0.2, "3": 0.9},
        "skill_attempt_counts": {"math": 5, "science": 0}
    }
    
    class MockQuery:
        def filter(self, *args):
            return self
        def first(self):
            return None
    class MockSession:
        def query(self, *args):
            return MockQuery()

    mock_db = MockSession()
    selected = bandit.select_question(mock_db, [q1, q2, q3], ctx, answered_question_ids={"1"})
    
    # 1 is answered, so must be 2 or 3
    assert selected is not None
    assert selected.id in ["2", "3"]
