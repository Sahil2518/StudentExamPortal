from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field


class StudentProfileCreate(BaseModel):

    qualification: str = Field(..., min_length=2, max_length=100)

    branch: str = Field(..., min_length=2, max_length=100)

    experience_level: str = Field(..., min_length=2, max_length=50)

    preferred_domain: str = Field(..., min_length=2, max_length=100)

    preferred_difficulty: str = Field(..., min_length=4, max_length=20)

    learning_goal: str = Field(..., min_length=5, max_length=200)


class StudentProfileResponse(BaseModel):

    id: UUID

    qualification: str

    branch: str

    experience_level: str

    preferred_domain: str

    preferred_difficulty: str

    learning_goal: str

    profile_completion: str

    created_at: datetime

    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class StudentProfileUpdate(BaseModel):

    qualification: str | None = None

    branch: str | None = None

    experience_level: str | None = None

    preferred_domain: str | None = None

    preferred_difficulty: str | None = None

    learning_goal: str | None = None