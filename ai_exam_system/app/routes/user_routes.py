from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.schemas.user_schema import UserCreate, UserResponse
from app.services.auth_service import hash_password
from app.services.email_service import validate_candidate_email, canonicalize_email, EMAIL_ALIASES

from app.dependencies.current_user import get_current_user

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse
)
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    # Verify that the email actually exists, has valid DNS MX records, and is not disposable
    clean_email = validate_candidate_email(user.email)
    canonical_email = canonicalize_email(clean_email)

    existing_user = db.query(User).filter(
        (User.email == canonical_email) | (User.email == clean_email)
    ).first()

    if existing_user:
        if clean_email in EMAIL_ALIASES or clean_email != canonical_email:
            raise HTTPException(
                status_code=400,
                detail=f"This email is linked to your existing account ({canonical_email}). Please sign in instead."
            )
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    hashed_password = hash_password(
        user.password
    )

    new_user = User(
        name=user.name.strip(),
        email=canonical_email,
        password_hash=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

@router.get("/me")
def get_my_profile(

    current_user: User = Depends(
        get_current_user
    )

):

    return {

        "id": str(current_user.id),

        "name": current_user.name,

        "email": current_user.email,

        "role": current_user.role

    }
