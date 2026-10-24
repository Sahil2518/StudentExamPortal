from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError

from app.database.connection import get_db
from app.models.user import User
from app.services.jwt_service import verify_token


# HTTPBearer parses the Authorization: Bearer <token> header automatically
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Validate the Bearer token and return the authenticated User.

    Returns HTTP 401 if the token is missing, expired, or invalid.
    Returns HTTP 401 if the user in the token no longer exists.
    """

    token = credentials.credentials

    # Decode and validate the token
    try:
        payload = verify_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing user identity",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Look up the user in the database
    import uuid
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise credentials_exception

    user = db.query(User).filter(
        User.id == user_uuid
    ).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user


def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency that enforces admin-only access.

    Returns HTTP 403 if the authenticated user is not an admin.
    """

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires administrator privileges"
        )

    return current_user


def require_reviewer(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency that allows access to admin or reviewer roles.

    Returns HTTP 403 for regular student accounts.
    """

    if current_user.role not in ("admin", "reviewer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires reviewer or administrator privileges"
        )

    return current_user