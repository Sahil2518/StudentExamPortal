import pytest
import uuid
from tests.conftest import client, register_and_login, TestingSessionLocal
from app.models.proctoring import ProctoringEvent

def test_proctoring_replay_protection():
    """Verify that proctoring events handle duplicates and invalid sequence numbers."""
    user = register_and_login("proctor_replay")
    
    # 1. Setup a valid session
    with TestingSessionLocal() as db:
        from app.models.exam_session import ExamSession
        from app.models.user import User
        
        db_user = db.query(User).filter_by(email=user["email"]).first()
        sess_id = uuid.uuid4()
        test_sess = ExamSession(
            id=sess_id, user_id=db_user.id, domain="science", skill="physics",
            status="active", max_questions=5, questions_answered=0, correct_count=0
        )
        db.add(test_sess)
        db.commit()
        
    client_event_id_1 = str(uuid.uuid4())
    
    # 2. Submit initial valid event
    payload1 = {
        "exam_session_id": str(sess_id),
        "client_event_id": client_event_id_1,
        "sequence_number": 1,
        "event_type": "tab_switch",
        "severity": "low",
        "confidence": 1.0
    }
    
    resp1 = client.post(
        "/proctoring-events",
        json=payload1,
        headers={"Authorization": f"Bearer {user['access_token']}"}
    )
    assert resp1.status_code == 201
    
    # 3. Submit exact duplicate (idempotency check)
    resp_dup = client.post(
        "/proctoring-events",
        json=payload1,
        headers={"Authorization": f"Bearer {user['access_token']}"}
    )
    # Should be 201 Created since it's an idempotent response for duplicates
    assert resp_dup.status_code == 201
    assert "already recorded" in resp_dup.json()["message"].lower()
    
    # Verify only one event was created in DB
    with TestingSessionLocal() as db:
        events = db.query(ProctoringEvent).filter_by(client_event_id=client_event_id_1).all()
        assert len(events) == 1
        
    # 4. Submit event with out-of-order/replayed sequence number
    client_event_id_2 = str(uuid.uuid4())
    payload2 = {
        "exam_session_id": str(sess_id),
        "client_event_id": client_event_id_2,
        "sequence_number": 1, # Replay of sequence number!
        "event_type": "focus_lost",
        "severity": "low",
        "confidence": 1.0
    }
    
    resp_replay = client.post(
        "/proctoring-events",
        json=payload2,
        headers={"Authorization": f"Bearer {user['access_token']}"}
    )
    assert resp_replay.status_code == 400
    assert "replay" in resp_replay.json()["detail"].lower()
    
    # Verify second event was NOT created
    with TestingSessionLocal() as db:
        event2 = db.query(ProctoringEvent).filter_by(client_event_id=client_event_id_2).first()
        assert event2 is None
        
    # 5. Submit valid subsequent event
    client_event_id_3 = str(uuid.uuid4())
    payload3 = {
        "exam_session_id": str(sess_id),
        "client_event_id": client_event_id_3,
        "sequence_number": 2, # Valid progression
        "event_type": "focus_lost",
        "severity": "low",
        "confidence": 1.0
    }
    
    resp3 = client.post(
        "/proctoring-events",
        json=payload3,
        headers={"Authorization": f"Bearer {user['access_token']}"}
    )
    assert resp3.status_code == 201
