from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.database.connection import get_db

from app.dependencies.current_user import get_current_user

from app.models.user import User
from app.models.student_profile import StudentProfile

from app.schemas.student_profile_schema import (
    StudentProfileCreate,
    StudentProfileResponse,
    StudentProfileUpdate
)


router = APIRouter(
    tags=["Student Profile"]
)


@router.post(
    "/student-profile",
    response_model=StudentProfileResponse
)
def create_student_profile(

    profile: StudentProfileCreate,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )

):

    existing_profile = db.query(
        StudentProfile
    ).filter(
        StudentProfile.user_id == current_user.id
    ).first()

    if existing_profile:

        raise HTTPException(
            status_code=400,
            detail="Profile already exists"
        )

    new_profile = StudentProfile(

        user_id=current_user.id,

        qualification=profile.qualification,

        branch=profile.branch,

        experience_level=profile.experience_level,

        preferred_domain=profile.preferred_domain,

        preferred_difficulty=profile.preferred_difficulty,

        learning_goal=profile.learning_goal,

        profile_completion="100%"
    )

    db.add(new_profile)

    db.commit()

    db.refresh(new_profile)

    return new_profile


@router.get(
    "/student-profile",
    response_model=StudentProfileResponse
)
def get_student_profile(

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(get_db)

):

    profile = db.query(
        StudentProfile
    ).filter(
        StudentProfile.user_id == current_user.id
    ).first()

    if not profile:

        raise HTTPException(
            status_code=404,
            detail="Student profile not found"
        )

    return profile


@router.patch(
    "/student-profile",
    response_model=StudentProfileResponse
)
def update_student_profile(

    profile_data: StudentProfileUpdate,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(get_db)

):

    profile = db.query(
        StudentProfile
    ).filter(
        StudentProfile.user_id == current_user.id
    ).first()

    if not profile:

        raise HTTPException(
            status_code=404,
            detail="Student profile not found"
        )

    update_data = profile_data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():

        setattr(
            profile,
            field,
            value
        )

    db.commit()

    db.refresh(profile)

    return profile