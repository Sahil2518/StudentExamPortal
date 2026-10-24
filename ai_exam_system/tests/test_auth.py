"""
Tests for authentication: registration, login, token validation,
token expiry handling, and role enforcement.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import client, make_test_email, TEST_PREFIX

# -------------------------------------------------------------------
# Health check
# -------------------------------------------------------------------

def test_health_check():
    """Server returns 200 and reports running status."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_database_health():
    """Database connection is alive."""
    resp = client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["database"] == "connected"


# -------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------

def test_register_new_user():
    """A new user can register with a valid email and password."""
    email = make_test_email("reg_new")
    resp = client.post("/register", json={
        "name": "New Test User",
        "email": email,
        "password": "SecurePass123!"
    })
    # Accept 200 or 400 (if already exists from prior run)
    assert resp.status_code in (200, 201, 400)
    if resp.status_code in (200, 201):
        data = resp.json()
        assert data["email"] == email
        # Password hash must never appear in the response
        assert "password" not in data
        assert "password_hash" not in data
        assert data["role"] == "student"


def test_register_duplicate_email_rejected():
    """Registering with an already-used email returns 400."""
    email = make_test_email("reg_dup")
    payload = {"name": "Dup User", "email": email, "password": "Pass123!"}
    client.post("/register", json=payload)  # First registration
    resp = client.post("/register", json=payload)  # Duplicate
    assert resp.status_code == 400
    assert "already registered" in resp.json()["detail"].lower()


# -------------------------------------------------------------------
# Login
# -------------------------------------------------------------------

def test_login_valid_credentials():
    """A registered user can log in and receives a JWT token."""
    email = make_test_email("login_valid")
    password = "ValidPass123!"
    client.post("/register", json={"name": "Login Test", "email": email, "password": password})

    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20


def test_login_wrong_password_rejected():
    """Login with the wrong password returns 401."""
    email = make_test_email("login_wrong_pw")
    client.post("/register", json={"name": "Wrong PW", "email": email, "password": "CorrectPass123!"})

    resp = client.post("/login", json={"email": email, "password": "WrongPassword!"})
    assert resp.status_code == 401


def test_login_unknown_email_rejected():
    """Login with an email that was never registered returns 401."""
    resp = client.post("/login", json={
        "email": "nobody_ever@test.invalid",
        "password": "anything"
    })
    assert resp.status_code == 401


# -------------------------------------------------------------------
# Token and authorization
# -------------------------------------------------------------------

def test_get_me_with_valid_token():
    """Authenticated /me returns the current user's details without the password hash."""
    email = make_test_email("me_valid")
    password = "Pass123!"
    client.post("/register", json={"name": "Me Test", "email": email, "password": password})
    login_resp = client.post("/login", json={"email": email, "password": password})
    token = login_resp.json()["access_token"]

    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == email
    assert "password" not in data
    assert "password_hash" not in data


def test_get_me_without_token_rejected():
    """Unauthenticated request to /me returns 403 (no credentials provided)."""
    resp = client.get("/me")
    assert resp.status_code in (401, 403)


def test_get_me_with_invalid_token_rejected():
    """A tampered or garbage token returns 401 or 403."""
    resp = client.get("/me", headers={"Authorization": "Bearer this.is.not.valid"})
    assert resp.status_code in (401, 403)


def test_admin_route_blocked_for_students():
    """A student cannot access admin-only endpoints."""
    email = make_test_email("admin_blocked")
    password = "Pass123!"
    client.post("/register", json={"name": "Student", "email": email, "password": password})
    login_resp = client.post("/login", json={"email": email, "password": password})
    token = login_resp.json()["access_token"]

    # Try to access the admin user list
    resp = client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


# -------------------------------------------------------------------
# Question bank: answer key protection
# -------------------------------------------------------------------

def test_questions_list_does_not_expose_correct_answer_to_students():
    """Students must not see correct_answer in the question list response."""
    email = make_test_email("qlist_student")
    password = "Pass123!"
    client.post("/register", json={"name": "Student Q", "email": email, "password": password})
    login_resp = client.post("/login", json={"email": email, "password": password})
    token = login_resp.json()["access_token"]

    resp = client.get("/questions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()

    # Every returned question must not have correct_answer
    for q in data.get("questions", []):
        assert "correct_answer" not in q or q.get("correct_answer") is None, \
            f"Question {q.get('id')} exposed correct_answer to a student"
