from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.person import PersonReviewState


class PersonBase(BaseModel):
    person_number: int = Field(
        ..., ge=1, description="Sequence number of person inside household"
    )
    name: str = Field(..., min_length=1)
    relationship_to_head: str = Field(default="HEAD")
    sex: str = Field(..., description="MALE, FEMALE, TRANSGENDER")
    age: int | None = Field(default=None, ge=0, le=130)
    date_of_birth: datetime | None = None
    marital_status: str | None = None
    answers: dict[str, Any] | None = None
    questionnaire_version: str = Field(default="2.0")


class PersonCreate(PersonBase):
    household_id: UUID


class PersonUpdate(BaseModel):
    name: str | None = None
    relationship_to_head: str | None = None
    sex: str | None = None
    age: int | None = None
    date_of_birth: datetime | None = None
    marital_status: str | None = None
    answers: dict[str, Any] | None = None
    review_state: PersonReviewState | None = None


class PersonResponse(PersonBase):
    id: UUID
    household_id: UUID
    review_state: PersonReviewState
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PersonListResponse(BaseModel):
    items: list[PersonResponse]
    total: int
