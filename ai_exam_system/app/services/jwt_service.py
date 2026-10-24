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