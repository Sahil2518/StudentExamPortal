from pydantic import BaseModel, Field, model_validator
from typing import List


class QuestionCreate(BaseModel):

    question_text: str = Field(
        ...,
        min_length=10
    )

    domain: str = Field(
        ...,
        min_length=2
    )

    skill: str = Field(
        ...,
        min_length=2
    )

    difficulty: int = Field(
        ...,
        ge=1,
        le=5
    )

    minimum_level: int = Field(
        ...,
        ge=1,
        le=5
    )

    maximum_level: int = Field(
        ...,
        ge=1,
        le=5
    )

    options: List[str] = Field(
        ...,
        min_length=2
    )

    correct_answer: str = Field(
        ...,
        min_length=1
    )

    explanation: str | None = None

    @model_validator(mode="after")
    def validate_difficulty_range(self):

        if self.minimum_level > self.maximum_level:
            raise ValueError(
                "Minimum level cannot be greater than maximum level"
            )

        if not (
            self.minimum_level
            <= self.difficulty
            <= self.maximum_level
        ):
            raise ValueError(
                "Difficulty must be between minimum and maximum level"
            )

        return self