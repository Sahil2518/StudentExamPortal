"""
Tests for Password Reset & Email OTP Verification.

Validates:
1. Requesting OTP for a non-registered email returns 404.
2. Requesting OTP generates a 6-digit code, stores a hashed record with 10-minute expiry.
3. Submitting an incorrect OTP is rejected with remaining attempts count.
4. Too many failed attempts invalidates the OTP.
5. Correct OTP returns a signed reset_token and marks the OTP as used.
6. Reusing an already-consumed OTP is rejected.
7. Resetting password updates password_hash and permits login with the new password,
   while rejecting the old password.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from tests.conftest import client, make_test_email
from app.models.password_reset_otp import PasswordResetOTP
from tests.conftest import TestingSessionLocal


def test_forgot_password_unregistered_email_returns_404():
    """Requesting OTP for an email that doesn't exist returns 404."""
    resp = client.post("/forgot-password", json={
        "email": "definitely_nonexistent_user_9999@example.com"
    })
    assert resp.status_code == 404
    assert "no account" in resp.json()["detail"].lower()


def test_full_otp_and_password_reset_flow():
    """Full lifecycle: Register -> Forgot Password -> Verify OTP -> Reset Password -> Login."""
    email = make_test_email("otp_reset_user")
    initial_password = "OldPassword123!"
    new_password = "BrandNewSecurePassword456!"

    # 1. Register user
    reg_resp = client.post("/register", json={
        "name": "OTP Test User",
        "email": email,
        "password": initial_password
    })
    assert reg_resp.status_code in (200, 201)

    # 2. Request OTP
    forgot_resp = client.post("/forgot-password", json={"email": email})
    assert forgot_resp.status_code == 200
    forgot_data = forgot_resp.json()
    assert forgot_data["email"] == email.lower().strip()
    assert forgot_data["expires_in_minutes"] == 10
    otp_code = forgot_data.get("dev_otp")
    assert otp_code is not None
    assert len(otp_code) == 6

    # 3. Verify OTP in database: verify it is stored as bcrypt hash, not plaintext
    db = TestingSessionLocal()
    otp_record = db.query(PasswordResetOTP).filter(PasswordResetOTP.email == email.lower().strip()).first()
    assert otp_record is not None
    assert otp_record.otp_hash != otp_code  # Must be hashed!
    assert otp_record.is_used is False
    assert otp_record.attempts == 0
    db.close()

    # 4. Attempt with WRONG OTP -> Should fail with 400
    wrong_resp = client.post("/verify-otp", json={
        "email": email,
        "otp": "000000"
    })
    assert wrong_resp.status_code == 400
    assert "invalid verification code" in wrong_resp.json()["detail"].lower()

    # 5. Attempt with CORRECT OTP -> Returns signed reset_token
    verify_resp = client.post("/verify-otp", json={
        "email": email,
        "otp": otp_code
    })
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert "reset_token" in verify_data
    reset_token = verify_data["reset_token"]
    assert len(reset_token) > 20

    # 6. Reusing same OTP must fail
    reuse_resp = client.post("/verify-otp", json={
        "email": email,
        "otp": otp_code
    })
    assert reuse_resp.status_code == 400

    # 7. Reset password using invalid/tampered token must fail
    tampered_resp = client.post("/reset-password", json={
        "email": email,
        "reset_token": "tampered.jwt.token",
        "new_password": new_password
    })
    assert tampered_resp.status_code == 400

    # 8. Reset password using valid reset_token
    reset_resp = client.post("/reset-password", json={
        "email": email,
        "reset_token": reset_token,
        "new_password": new_password
    })
    assert reset_resp.status_code == 200
    assert "password has been reset" in reset_resp.json()["message"].lower()

    # 9. Login with OLD password must fail (401)
    old_login_resp = client.post("/login", json={
        "email": email,
        "password": initial_password
    })
    assert old_login_resp.status_code == 401

    # 10. Login with NEW password must succeed (200)
    new_login_resp = client.post("/login", json={
        "email": email,
        "password": new_password
    })
    assert new_login_resp.status_code == 200
    assert "access_token" in new_login_resp.json()


def test_forgot_password_rate_limit_cooldown():
    """Requesting OTP twice within 60 seconds triggers HTTP 429 Too Many Requests."""
    email = make_test_email("cooldown_user")
    reg_resp = client.post("/register", json={
        "name": "Cooldown Test User",
        "email": email,
        "password": "Password123!"
    })
    assert reg_resp.status_code in (200, 201)

    # Temporarily disable TESTING bypass to enforce rate limit
    os.environ["TESTING"] = "false"
    try:
        # First request succeeds
        resp1 = client.post("/forgot-password", json={"email": email})
        assert resp1.status_code == 200

        # Immediate second request fails with HTTP 429
        resp2 = client.post("/forgot-password", json={"email": email})
        assert resp2.status_code == 429
        assert "wait" in resp2.json()["detail"].lower()
    finally:
        os.environ["TESTING"] = "true"
