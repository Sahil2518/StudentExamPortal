import os
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.models.password_reset_otp import PasswordResetOTP
from app.schemas.auth_schema import (
    LoginRequest,
    TokenResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
    ResetPasswordRequest,
    ResetPasswordResponse
)
from app.services.auth_service import hash_password, verify_password
from app.services.jwt_service import (
    create_access_token,
    create_password_reset_token,
    verify_password_reset_token
)
from app.services.email_service import send_password_reset_otp_email

router = APIRouter(tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in to user account"
)
def login(
    user: LoginRequest,
    db: Session = Depends(get_db)
):
    # Find user by email
    db_user = db.query(User).filter(
        User.email == user.email.lower().strip()
    ).first()

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password
    if not verify_password(
        user.password,
        db_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Generate JWT Token
    token = create_access_token(
        {
            "user_id": str(db_user.id),
            "email": db_user.email,
            "role": db_user.role
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(db_user.id),
            "name": db_user.name,
            "email": db_user.email,
            "role": db_user.role
        }
    }


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request a 6-digit OTP verification code via email for password reset"
)
def forgot_password(
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    clean_email = str(body.email).lower().strip()
    user = db.query(User).filter(User.email == clean_email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account registered with this email address."
        )

    # Invalidate any previously issued, active OTPs for this user
    db.query(PasswordResetOTP).filter(
        PasswordResetOTP.user_id == user.id,
        PasswordResetOTP.is_used == False
    ).update({"is_used": True})

    # Generate cryptographically secure 6-digit OTP
    otp_code = f"{secrets.randbelow(900000) + 100000}"
    otp_hashed = hash_password(otp_code)

    # 10-minute validity
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    otp_record = PasswordResetOTP(
        user_id=user.id,
        email=clean_email,
        otp_hash=otp_hashed,
        expires_at=expires_at,
        is_used=False,
        attempts=0
    )
    db.add(otp_record)
    db.commit()

    # Dispatch email
    delivery_result = send_password_reset_otp_email(
        to_email=user.email,
        otp_code=otp_code,
        user_name=user.name
    )

    # In simulated / non-production mode, expose dev_otp so tests & local testing work effortlessly
    dev_otp = None
    if delivery_result.get("mode") == "simulated" or os.getenv("ENVIRONMENT") == "development":
        dev_otp = otp_code

    return ForgotPasswordResponse(
        message="A 6-digit verification code has been sent to your email address.",
        email=clean_email,
        expires_in_minutes=10,
        delivery_status=delivery_result.get("mode", "unknown"),
        dev_otp=dev_otp
    )


@router.post(
    "/verify-otp",
    response_model=VerifyOTPResponse,
    summary="Verify the 6-digit OTP code and obtain a signed password-reset token"
)
def verify_otp(
    body: VerifyOTPRequest,
    db: Session = Depends(get_db)
):
    clean_email = str(body.email).lower().strip()
    entered_otp = str(body.otp).strip()

    # Fetch latest unexpired, unused OTP record
    record = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == clean_email,
        PasswordResetOTP.is_used == False
    ).order_by(PasswordResetOTP.created_at.desc()).first()

    if not record or record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired or is invalid. Please request a new code."
        )

    # Max attempt brute-force mitigation
    if record.attempts >= 5:
        record.is_used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many incorrect attempts. This code has been invalidated. Please request a new code."
        )

    # Verify bcrypt OTP hash
    if not verify_password(entered_otp, record.otp_hash):
        record.attempts += 1
        db.commit()
        remaining = max(0, 5 - record.attempts)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. {remaining} attempt(s) remaining."
        )

    # Mark OTP as used (prevents replay)
    record.is_used = True
    db.commit()

    # Issue cryptographically signed token valid for 15 minutes
    reset_token = create_password_reset_token(email=clean_email, expires_minutes=15)

    return VerifyOTPResponse(
        message="Verification code confirmed successfully.",
        reset_token=reset_token
    )


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Update account password using verified reset token"
)
def reset_password(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    clean_email = str(body.email).lower().strip()

    # Validate cryptographically signed reset token
    try:
        payload = verify_password_reset_token(body.reset_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token. Please restart the password reset process."
        )

    if payload.get("sub", "").lower().strip() != clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token does not match the provided email address."
        )

    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found."
        )

    if len(body.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long."
        )

    # Update password hash with bcrypt
    user.password_hash = hash_password(body.new_password)

    # Invalidate all remaining OTP records for this user
    db.query(PasswordResetOTP).filter(
        PasswordResetOTP.user_id == user.id
    ).update({"is_used": True})

    db.commit()

    return ResetPasswordResponse(
        message="Your password has been reset successfully. You can now sign in with your new password."
    )
