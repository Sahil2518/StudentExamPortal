import os
from jose import jwt, JWTError
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load .env so this module works when imported directly
load_dotenv()

# Read the secret from the environment.
# A missing or empty secret means the application cannot safely sign tokens.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

if not SECRET_KEY:
    # Allow startup without crashing, but log a clear warning.
    # In production, set JWT_SECRET_KEY to a long random string.
    import warnings
    warnings.warn(
        "JWT_SECRET_KEY is not set in the environment. "
        "Token signing is insecure. Set this variable before deployment.",
        stacklevel=1
    )
    # Fall back to an unsafe default only to avoid import errors.
    # Never rely on this in production.
    SECRET_KEY = "UNSAFE_DEFAULT_CHANGE_BEFORE_DEPLOYMENT"

# Algorithm used for signing
ALGORITHM = "HS256"

# How long tokens stay valid (minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: dict) -> str:
    """
    Create a signed JWT token containing the given payload data.

    The token expires after ACCESS_TOKEN_EXPIRE_MINUTES minutes.
    """

    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    # Add expiry claim to the payload
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Raises JWTError if the token is invalid, expired, or tampered with.
    """

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
    except JWTError as exc:
        # Re-raise as the same type so callers can handle it uniformly
        raise exc

    return payload


def create_password_reset_token(email: str, expires_minutes: int = 15) -> str:
    """
    Create a short-lived cryptographically signed token specifically for password reset.
    Only issued after successful OTP verification.
    """
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = {
        "sub": email.lower().strip(),
        "purpose": "password_reset",
        "exp": expire
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_password_reset_token(token: str) -> dict:
    """
    Validate a password reset token.
    Ensures signature, expiry, and purpose == 'password_reset'.
    """
    payload = verify_token(token)
    if payload.get("purpose") != "password_reset":
        raise JWTError("Invalid token purpose; expected password_reset")
    if not payload.get("sub"):
        raise JWTError("Missing email identity in reset token")
    return payload
