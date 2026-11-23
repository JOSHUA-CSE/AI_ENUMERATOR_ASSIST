from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.fieldwork import HouseholdRecordStatus, HouseholdReviewState


class HouseholdVerificationRequest(BaseModel):
    comment: str | None = Field(
        default=None, description="Optional supervisor note on verification"
    )


class HouseholdReturnRequest(BaseModel):
    rejection_reason: str = Field(
        ...,
        min_length=3,
        description="Specific reason for returning the record for correction",
    )
    supervisor_comment: str | None = Field(
        default=None, description="Detailed instructions for the enumerator"
    )


class HouseholdSubmissionResponse(BaseModel):
    id: UUID
    house_id: UUID
    census_house_id: UUID | None = None
    hlb_id: UUID
    enumerator_id: UUID
    household_number: str
    head_name: str
    total_members: int
    male_count: int
    female_count: int
    transgender_count: int
    ownership_status: str
    drinking_water_source: str | None = None
    lighting_source: str | None = None
    latrine_facility: str | None = None
    data: dict[str, Any] | None = None
    status: HouseholdRecordStatus
    review_state: HouseholdReviewState
    rejection_reason: str | None = None
    supervisor_comment: str | None = None
    verified_by: UUID | None = None
    verified_at: datetime | None = None
    captured_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HouseholdSubmissionListResponse(BaseModel):
    items: list[HouseholdSubmissionResponse]
    total: int


class QuarantinedOperationReviewRequest(BaseModel):
    approved: bool
    reason: str = Field(..., min_length=3)


class SupervisorCorrectionCreate(BaseModel):
    entity_type: str = Field(..., description="HOUSEHOLD or CENSUS_HOUSE")
    entity_id: UUID
    corrected_data: dict[str, Any]
    reason: str = Field(..., min_length=3)


class SupervisorCorrectionResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    original_version: int
    corrected_version: int
    author_id: UUID | None = None
    author_role: str
    changed_fields: Any
    corrected_data: dict[str, Any]
    correction_reason: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
