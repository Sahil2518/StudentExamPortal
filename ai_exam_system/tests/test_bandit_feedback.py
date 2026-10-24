import pytest
from app.models.bandit_state import BanditState
from app.models.bandit_update import BanditUpdate
from ml.contextual_bandit import get_bandit
from tests.conftest import client, register_and_login, TestingSessionLocal
import uuid

def test_bandit_persisted_updates():
    """Verify that a completed attempt updates the bandit state and persists to DB."""
    bandit = get_bandit()
    arm_key = bandit._arm_key("algebra", 2)
    
    with TestingSessionLocal() as db_session:
        # Clean up any existing state
        db_session.query(BanditState).filter_by(arm_key=arm_key).delete()
        db_session.query(BanditUpdate).delete()
        db_session.commit()
        
        attempt_1 = str(uuid.uuid4())
        # 1. Correct attempt updates bandit
        bandit.update(db=db_session, skill="algebra", difficulty=2, was_correct=True, attempt_id=attempt_1)
        state_after_correct = db_session.query(BanditState).filter_by(arm_key=arm_key).first()
        assert state_after_correct is not None
        assert state_after_correct.alpha == 2.0
        assert state_after_correct.beta == 1.0
        
        attempt_2 = str(uuid.uuid4())
        # 2. Incorrect attempt updates bandit appropriately
        bandit.update(db=db_session, skill="algebra", difficulty=2, was_correct=False, attempt_id=attempt_2)
        state_after_incorrect = db_session.query(BanditState).filter_by(arm_key=arm_key).first()
        assert state_after_incorrect.alpha == 2.0
        assert state_after_incorrect.beta == 2.0
        
        # 3. Idempotency test: Re-submitting the same attempt should NOT update params
        bandit.update(db=db_session, skill="algebra", difficulty=2, was_correct=False, attempt_id=attempt_2)
        state_after_duplicate = db_session.query(BanditState).filter_by(arm_key=arm_key).first()
        assert state_after_duplicate.beta == 2.0  # Still 2.0
        
def test_idempotency_of_attempt():
    """Verify duplicate submission doesn't double-update the bandit for a session."""
    user = register_and_login("bandit_idem")
    
    # Need to create a real question and session to submit an attempt
    with TestingSessionLocal() as db:
        from app.models.question import Question
        from app.models.exam_session import ExamSession
        from app.models.exam_session_question import ExamSessionQuestion
        from app.models.user import User
        
        db_user = db.query(User).filter_by(email=user["email"]).first()
        
        q_id = uuid.uuid4()
        test_q = Question(
            id=q_id, domain="math", skill="calculus", difficulty=3,
            question_text="Q?", correct_answer="A", options={"A": "A"},
            is_active=True, approval_status="approved",
            minimum_level=1, maximum_level=10
        )
        sess_id = uuid.uuid4()
        test_sess = ExamSession(
            id=sess_id, user_id=db_user.id, domain="math", skill="calculus",
            status="active", max_questions=10, questions_answered=0, correct_count=0
        )
        issuance = ExamSessionQuestion(
            exam_session_id=sess_id, question_id=q_id, status="served", sequence_number=1
        )
        db.add(test_q)
        db.add(test_sess)
        db.add(issuance)
        db.commit()
        
    payload = {
        "question_id": str(q_id),
        "selected_answer": "A",
        "time_taken": 10,
        "exam_session_id": str(sess_id)
    }
    
    # First submission
    resp1 = client.post(
        "/question-attempts",
        json=payload,
        headers={"Authorization": f"Bearer {user['access_token']}"}
    )
    assert resp1.status_code == 201
    
    # Second submission
    resp2 = client.post(
        "/question-attempts",
        json=payload,
        headers={"Authorization": f"Bearer {user['access_token']}"}
    )
    assert resp2.status_code == 409
    
    with TestingSessionLocal() as db:
        bandit = get_bandit()
        arm_key = bandit._arm_key("calculus", 3)
        state = db.query(BanditState).filter_by(arm_key=arm_key).first()
        assert state is not None
        assert state.alpha == 2.0  # Prior is 1.0, updated once to 2.0

def test_bandit_failure_rolls_back_attempt(monkeypatch):
    """Verify that if bandit update fails, the attempt is not persisted."""
    user = register_and_login("bandit_fail")
    
    with TestingSessionLocal() as db:
        from app.models.question import Question
        from app.models.exam_session import ExamSession
        from app.models.exam_session_question import ExamSessionQuestion
        from app.models.user import User
        from app.models.question_attempt import QuestionAttempt
        
        db_user = db.query(User).filter_by(email=user["email"]).first()
        
        q_id = uuid.uuid4()
        test_q = Question(
            id=q_id, domain="math", skill="calculus", difficulty=3,
            question_text="Q2?", correct_answer="A", options={"A": "A"},
            is_active=True, approval_status="approved",
            minimum_level=1, maximum_level=10
        )
        sess_id = uuid.uuid4()
        test_sess = ExamSession(
            id=sess_id, user_id=db_user.id, domain="math", skill="calculus",
            status="active", max_questions=10, questions_answered=0, correct_count=0
        )
        issuance = ExamSessionQuestion(
            exam_session_id=sess_id, question_id=q_id, status="served", sequence_number=1
        )
        db.add(test_q)
        db.add(test_sess)
        db.add(issuance)
        db.commit()

    # Monkeypatch bandit update to raise exception
    import ml.contextual_bandit
    def mock_update(*args, **kwargs):
        raise ValueError("Simulated bandit failure")
    
    monkeypatch.setattr(ml.contextual_bandit.ThompsonSamplingBandit, "update", mock_update)
    
    payload = {
        "question_id": str(q_id),
        "selected_answer": "A",
        "time_taken": 10,
        "exam_session_id": str(sess_id)
    }
    
    import pytest
    with pytest.raises(Exception):
        resp = client.post(
            "/question-attempts",
            json=payload,
            headers={"Authorization": f"Bearer {user['access_token']}"}
        )
    
    # Verify the attempt was rolled back
    with TestingSessionLocal() as db:
        from app.models.question_attempt import QuestionAttempt
        attempt = db.query(QuestionAttempt).filter_by(exam_session_id=sess_id).first()
        assert attempt is None
