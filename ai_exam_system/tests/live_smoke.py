"""
Live API smoke test - hits the real running server at http://127.0.0.1:8000.

This is different from the unit tests (which use TestClient in-process).
This script makes real HTTP requests to verify the full stack is working:
  server -> router -> service -> database -> response

Run after start_server.bat is running:
    python tests/live_smoke.py

Expected output: all checks print OK, script exits 0.
"""

import sys
import time
import uuid
import requests

BASE = "http://127.0.0.1:8000"
TIMEOUT = 10

# Unique suffix so this run does not collide with previous smoke test users
RUN_ID = str(uuid.uuid4())[:8]
EMAIL = f"smoke_{RUN_ID}@example.com"
PASSWORD = "SmokeTest123!"
NAME = f"Smoke User {RUN_ID}"

errors = []

def check(label, condition, detail=""):
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label}" + (f" -- {detail}" if detail else ""))
        errors.append(label)

def section(title):
    print(f"\n{title}")
    print("-" * 50)

# ---------------------------------------------------------------------------
# 1. Health
# ---------------------------------------------------------------------------
section("1. Health checks")
try:
    r = requests.get(f"{BASE}/", timeout=TIMEOUT)
    check("GET / returns 200", r.status_code == 200)
    check("Status field = running", r.json().get("status") == "running")

    r = requests.get(f"{BASE}/ready", timeout=TIMEOUT)
    check("GET /ready returns 200", r.status_code == 200)
    check("Database = connected", r.json().get("database") == "connected")
except Exception as exc:
    print(f"  FAIL Cannot reach server: {exc}")
    print("\nMake sure start_server.bat is running before running this script.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 2. Registration
# ---------------------------------------------------------------------------
section("2. Registration")
r = requests.post(f"{BASE}/register", json={
    "name": NAME, "email": EMAIL, "password": PASSWORD
}, timeout=TIMEOUT)
check("POST /register returns 200/201", r.status_code in (200, 201))
if r.status_code in (200, 201):
    data = r.json()
    check("Email matches", data.get("email") == EMAIL)
    check("Role = student", data.get("role") == "student")
    check("No password_hash in response", "password_hash" not in data)
    check("No password in response", "password" not in data)

# ---------------------------------------------------------------------------
# 3. Login
# ---------------------------------------------------------------------------
section("3. Login")
r = requests.post(f"{BASE}/login", json={
    "email": EMAIL, "password": PASSWORD
}, timeout=TIMEOUT)
check("POST /login returns 200", r.status_code == 200)
token = None
if r.status_code == 200:
    token = r.json().get("access_token")
    check("Token received", bool(token) and len(token) > 20)
    check("Token type = bearer", r.json().get("token_type") == "bearer")

HEADERS = {"Authorization": f"Bearer {token}"} if token else {}

# Wrong password
r = requests.post(f"{BASE}/login", json={"email": EMAIL, "password": "wrong"}, timeout=TIMEOUT)
check("Wrong password returns 401", r.status_code == 401)

# ---------------------------------------------------------------------------
# 4. /me endpoint
# ---------------------------------------------------------------------------
section("4. /me endpoint")
if token:
    r = requests.get(f"{BASE}/me", headers=HEADERS, timeout=TIMEOUT)
    check("GET /me returns 200", r.status_code == 200)
    check("Email matches", r.json().get("email") == EMAIL)
    check("No password_hash exposed", "password_hash" not in r.json())

    r = requests.get(f"{BASE}/me", timeout=TIMEOUT)
    check("GET /me without token returns 401/403", r.status_code in (401, 403))

# ---------------------------------------------------------------------------
# 5. Question bank
# ---------------------------------------------------------------------------
section("5. Question bank")
if token:
    r = requests.get(f"{BASE}/questions", headers=HEADERS, timeout=TIMEOUT)
    check("GET /questions returns 200", r.status_code == 200)
    questions = r.json().get("questions", [])
    check("Questions returned", len(questions) > 0, f"got {len(questions)}")
    if questions:
        q = questions[0]
        check("No correct_answer for student", "correct_answer" not in q or q.get("correct_answer") is None)
        check("Question has domain", bool(q.get("domain")))
        check("Question has skill", bool(q.get("skill")))

# ---------------------------------------------------------------------------
# 6. Exam session lifecycle
# ---------------------------------------------------------------------------
section("6. Exam session lifecycle")
session_id = None
if token and questions:
    domain = questions[0]["domain"]
    skill = questions[0]["skill"]

    # Start session
    r = requests.post(f"{BASE}/exam-sessions", json={
        "domain": domain, "skill": skill, "max_questions": 3
    }, headers=HEADERS, timeout=TIMEOUT)
    check("POST /exam-sessions returns 201", r.status_code == 201)
    if r.status_code == 201:
        session_id = r.json()["id"]
        check("Session status = active", r.json()["status"] == "active")

    # Cannot view results while active
    if session_id:
        r = requests.get(f"{BASE}/exam-sessions/{session_id}/results",
                         headers=HEADERS, timeout=TIMEOUT)
        check("Results blocked while active (400)", r.status_code == 400)

    # Submit one answer
    if session_id:
        skill_qs = [q for q in questions if q.get("skill") == skill]
        if skill_qs:
            q_id = skill_qs[0]["id"]
            opts = skill_qs[0].get("options", [])
            # Options can be a list ["A. ...", "B. ..."] or a dict {"A": "..."}
            if isinstance(opts, dict):
                chosen = list(opts.keys())[0] if opts else "A"
            elif isinstance(opts, list) and opts:
                # Pick first character of first option as the answer key
                chosen = opts[0][0] if opts[0] else "A"
            else:
                chosen = "A"
            r = requests.post(f"{BASE}/question-attempts", json={
                "question_id": q_id,
                "selected_answer": chosen,
                "time_taken": 12,
                "exam_session_id": session_id
            }, headers=HEADERS, timeout=TIMEOUT)
            check("POST /question-attempts returns 201", r.status_code == 201)
            if r.status_code == 201:
                data = r.json()
                check("correct_answer revealed after submit", "correct_answer" in data)
                check("is_correct field present", "is_correct" in data)
                check("explanation field present", "explanation" in data)

    # Finish session
    if session_id:
        r = requests.post(f"{BASE}/exam-sessions/{session_id}/finish",
                          headers=HEADERS, timeout=TIMEOUT)
        check("POST /finish returns 200", r.status_code == 200)
        check("Status = finished", r.json().get("status") == "finished")

    # View results after finish
    if session_id:
        r = requests.get(f"{BASE}/exam-sessions/{session_id}/results",
                         headers=HEADERS, timeout=TIMEOUT)
        check("GET /results returns 200 after finish", r.status_code == 200)
        data = r.json()
        check("question_results present", "question_results" in data)
        check("recommendations present", "recommendations" in data)

# ---------------------------------------------------------------------------
# 7. Performance endpoint
# ---------------------------------------------------------------------------
section("7. Performance analytics")
if token:
    r = requests.get(f"{BASE}/performance", headers=HEADERS, timeout=TIMEOUT)
    check("GET /performance returns 200", r.status_code == 200)
    check("total_attempts present", "total_attempts" in r.json())

# ---------------------------------------------------------------------------
# 8. Admin route blocked for students
# ---------------------------------------------------------------------------
section("8. Authorization enforcement")
if token:
    r = requests.get(f"{BASE}/admin/users", headers=HEADERS, timeout=TIMEOUT)
    check("Student blocked from /admin/users (403)", r.status_code == 403)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = 35
section("SUMMARY")
if errors:
    print(f"  {len(errors)} check(s) FAILED:")
    for e in errors:
        print(f"    - {e}")
    sys.exit(1)
else:
    print("  All checks passed.")
    print("  The full stack (server + database + auth + exam + analytics) is working.")
    sys.exit(0)
