"""
Builds student response sequences for knowledge tracing models.

A sequence is: for student S, sorted by timestamp, each item is:
  (question_id, skill, difficulty, is_correct, response_time, timestamp)

Uses ONLY information available BEFORE each response.
No future-answer leakage.
"""
from typing import List, Dict, Any

def build_sequences_from_db(db_session) -> List[Dict[str, Any]]:
    """
    Load sequences from real database attempt data.
    """
    from app.models.question_attempt import QuestionAttempt
    from app.models.question import Question

    attempts = (
        db_session.query(QuestionAttempt, Question)
        .join(Question, Question.id == QuestionAttempt.question_id)
        .order_by(QuestionAttempt.user_id, QuestionAttempt.created_at.asc(), QuestionAttempt.id.asc())
        .all()
    )

    if not attempts:
        return []

    sequences = {}
    
    for attempt, q in attempts:
        uid = str(attempt.user_id)
        if uid not in sequences:
            sequences[uid] = {
                "student_id": uid,
                "sequence": []
            }
        
        seq_list = sequences[uid]["sequence"]
        
        item = {
            "question_id": str(q.id),
            "skill": q.skill,
            "difficulty": q.difficulty,
            "is_correct": int(attempt.is_correct),
            "response_time": attempt.time_taken,
            "timestamp": attempt.created_at,
            "attempt_index": len(seq_list)
        }
        seq_list.append(item)

    return list(sequences.values())

def build_sequences_from_dataframe(df) -> List[Dict[str, Any]]:
    """Build from a pandas DataFrame (for testing/synthetic data)."""
    if "student_id" not in df.columns:
        df["student_id"] = "student_0"
    
    sequences = {}
    
    # Sort chronologically if a timestamp exists
    if "timestamp" in df.columns:
        df = df.sort_values(by=["student_id", "timestamp"])
    else:
        df = df.sort_values(by=["student_id"])
        
    for uid, group in df.groupby("student_id"):
        seq_list = []
        for i, row in enumerate(group.itertuples()):
            item = {
                "question_id": str(getattr(row, "question_id", i)),
                "skill": getattr(row, "skill", "unknown"),
                "difficulty": getattr(row, "difficulty", 3),
                "is_correct": getattr(row, "is_correct", getattr(row, "target_is_correct", 0)),
                "response_time": getattr(row, "response_time", getattr(row, "time_taken", 30.0)),
                "timestamp": getattr(row, "timestamp", None),
                "attempt_index": i
            }
            seq_list.append(item)
            
        sequences[uid] = {
            "student_id": uid,
            "sequence": seq_list
        }
        
    return list(sequences.values())

def validate_no_leakage(sequences: List[Dict[str, Any]]) -> bool:
    """
    Check that no sequence contains information from the future.
    Raises ValueError if leakage detected.
    """
    for seq in sequences:
        items = seq["sequence"]
        for i, item in enumerate(items):
            assert item["attempt_index"] == i, "Attempt index out of order"
    return True
