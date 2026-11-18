import pytest
import sys, os
import tempfile
import atexit

# Set up temp SQLite database for tests BEFORE any app imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

fd, temp_db_path = tempfile.mkstemp(suffix=".db")
os.close(fd)

def cleanup_temp_db():
    try:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)
    except:
        pass

atexit.register(cleanup_temp_db)

SQLALCHEMY_TEST_URL = f"sqlite:///{temp_db_path}"
# Override DATABASE_URL so app.database.connection and lifespan use the test SQLite DB
os.environ["DATABASE_URL"] = SQLALCHEMY_TEST_URL
os.environ["ENVIRONMENT"] = "development"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database.base import Base
from app.database.connection import get_db, engine as app_engine

from app.models.user import User
from app.models.student_profile import StudentProfile
from app.models.question import Question
from app.models.question_attempt import QuestionAttempt
from app.models.exam_session import ExamSession
from app.models.proctoring import ProctoringEvent, ReviewDecision
from app.models.exam_session_question import ExamSessionQuestion
from app.models.bandit_state import BanditState
from app.models.bandit_update import BanditUpdate
from app.models.password_reset_otp import PasswordResetOTP

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from app.main import app

test_engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)

client = TestClient(app)

TEST_PREFIX = "test_"

def make_test_email(label: str) -> str:
    import uuid
    return f"{TEST_PREFIX}{label}_{uuid.uuid4().hex[:8]}@example.com"

def register_and_login(suffix: str, role: str = "student"):
    email = make_test_email(suffix)
    password = "TestPassword123!"
    resp = client.post("/register", json={"name": f"Test {suffix}", "email": email, "password": password, "role": role})
    if resp.status_code not in (200, 201):
        if "already" not in resp.json().get("detail", "").lower():
            raise AssertionError(f"Registration failed: {resp.text}")
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"email": email, "password": password, "access_token": token, "auth_headers": {"Authorization": f"Bearer {token}"}}

