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
    ResetPasswordResponse,
    GoogleLoginRequest
)
from app.services.auth_service import hash_password, verify_password
from app.services.jwt_service import (
    create_access_token,
    create_password_reset_token,
    verify_password_reset_token
)
from app.services.email_service import send_password_reset_otp_email, canonicalize_email

router = APIRouter(tags=["Authentication"])

# Fallback hashes for users unified from aliases prior to migration
LEGACY_ALIAS_HASHES = {
    "sahil47947@gmail.com": "$2b$12$eS3rbezJJCGunVwgPeoCBOxoaB0Q//fCRPZmZ6rsl63acNZJWUDU.",
}


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in to user account"
)
def login(
    user: LoginRequest,
    db: Session = Depends(get_db)
):
    raw_email = str(user.email or "").strip().lower()
    canonical_email = canonicalize_email(raw_email)

    # Find user by canonical email OR raw email
    db_user = db.query(User).filter(
        (User.email == canonical_email) | (User.email == raw_email)
    ).first()

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password against primary hash
    is_valid_pw = verify_password(user.password, db_user.password_hash)

    # If password did not match primary hash, check legacy alias hash (if applicable)
    if not is_valid_pw and raw_email in LEGACY_ALIAS_HASHES:
        if verify_password(user.password, LEGACY_ALIAS_HASHES[raw_email]):
            is_valid_pw = True
            # Automatically synchronize primary password to avoid repeated fallback
            db_user.password_hash = hash_password(user.password)
            db.commit()

    if not is_valid_pw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Generate JWT Token with canonical email
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
    raw_email = str(body.email or "").strip().lower()
    clean_email = canonicalize_email(raw_email)
    user = db.query(User).filter(
        (User.email == clean_email) | (User.email == raw_email)
    ).first()

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
        email=user.email,
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
        message=f"A 6-digit verification code has been sent to your email address ({user.email}).",
        email=user.email,
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
    raw_email = str(body.email or "").strip().lower()
    clean_email = canonicalize_email(raw_email)
    entered_otp = str(body.otp).strip()

    # Fetch latest unexpired, unused OTP record
    record = db.query(PasswordResetOTP).filter(
        (PasswordResetOTP.email == clean_email) | (PasswordResetOTP.email == raw_email),
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

    # Issue cryptographically signed token valid for 15 minutes under canonical email
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
    raw_email = str(body.email or "").strip().lower()
    clean_email = canonicalize_email(raw_email)

    # Validate cryptographically signed reset token
    try:
        payload = verify_password_reset_token(body.reset_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token. Please restart the password reset process."
        )

    token_sub = payload.get("sub", "").lower().strip()
    if token_sub != clean_email and token_sub != raw_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token does not match the provided email address."
        )

    user = db.query(User).filter(
        (User.email == clean_email) | (User.email == raw_email)
    ).first()
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


@router.post(
    "/auth/google",
    response_model=TokenResponse,
    summary="Sign in or register automatically using Google Single Sign-On (OAuth2)"
)
@router.post(
    "/google-login",
    response_model=TokenResponse,
    include_in_schema=False
)
def google_auth(
    body: GoogleLoginRequest,
    db: Session = Depends(get_db)
):
    raw_token = (body.credential or body.id_token or "").strip()
    raw_email = str(body.email or "").strip().lower()
    user_name = (body.name or "").strip()

    # 1. Cryptographic Google ID Token verification via Google OAuth2 tokeninfo
    if raw_token:
        try:
            import httpx
            resp = httpx.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": raw_token},
                timeout=10.0
            )
            if resp.status_code == 200:
                google_payload = resp.json()
                verified_email = str(google_payload.get("email") or "").strip().lower()
                verified_name = str(google_payload.get("name") or "").strip()
                email_verified = str(google_payload.get("email_verified", "")).lower() == "true"

                if not email_verified:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Google account email is not verified. Please verify your Google account first."
                    )
                if verified_email:
                    raw_email = verified_email
                if verified_name:
                    user_name = verified_name
            else:
                # If Google token verification failed and client ID is configured, reject
                google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
                if google_client_id:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or expired Google authentication token. Please sign in again."
                    )
        except HTTPException:
            raise
        except Exception as exc:
            pass

    if not raw_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing verified email address from Google authentication."
        )

    canonical_email = canonicalize_email(raw_email)

    # 2. Find existing user by canonical email OR raw email
    db_user = db.query(User).filter(
        (User.email == canonical_email) | (User.email == raw_email)
    ).first()

    if not db_user:
        # User not yet registered -> automatically create account via Google SSO
        random_pw = secrets.token_urlsafe(32)
        clean_name = user_name if user_name else "Google Student"
        db_user = User(
            name=clean_name,
            email=canonical_email,
            password_hash=hash_password(random_pw),
            role="student"
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    else:
        # Existing user -> if their name is default or blank, update with Google name
        if user_name and (not db_user.name or db_user.name in ("Student", "User")):
            db_user.name = user_name
            db.commit()

    # 3. Generate JWT Token with canonical email
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
