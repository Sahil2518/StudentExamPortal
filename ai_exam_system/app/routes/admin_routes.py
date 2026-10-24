"""
Admin user management routes.

All routes here require admin role.

Admins can:
  - List all users
  - Get a specific user by id
  - Change a user's role
  - Deactivate a user (not delete, to preserve history)

Password hashes are never returned by any of these routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from app.database.connection import get_db
from app.dependencies.current_user import require_admin
from app.models.user import User


router = APIRouter(prefix="/admin", tags=["Admin"])


class RoleUpdate(BaseModel):
    """Request body for changing a user's role."""
    role: str = Field(..., pattern="^(student|admin|reviewer)$")


def _safe_user(u: User) -> dict:
    """Return a user dict with the password hash excluded."""
    return {
        "id": str(u.id),
        "name": u.name,
        "email": u.email,
        "role": u.role,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


@router.get("/users", summary="List all users")
def list_users(
    role: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Return a paginated list of all user accounts."""

    query = db.query(User)

    if role:
        query = query.filter(User.role == role)

    total = query.count()
    users = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "users": [_safe_user(u) for u in users]
    }


@router.get("/users/{user_id}", summary="Get one user by id")
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Return one user account without the password hash."""

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return _safe_user(user)


@router.patch("/users/{user_id}/role", summary="Change a user's role")
def update_user_role(
    user_id: str,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Change the role of an existing user (student, admin, or reviewer)."""

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.role = body.role
    db.commit()
    db.refresh(user)

    return {
        "message": f"Role updated to '{body.role}'",
        "user": _safe_user(user)
    }
