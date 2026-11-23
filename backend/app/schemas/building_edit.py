from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.building_edit import BuildingEditReviewStatus, BuildingEditType


class BuildingEditCreate(BaseModel):
    hlb_id: UUID
    building_id: UUID | None = Field(
        default=None, description="Existing building ID, or null for ADD"
    )
    edit_type: BuildingEditType
    proposed_changes: dict[str, Any] = Field(
        ..., description="Proposed attributes: lat, lon, reference, etc."
    )
    reason: str = Field(..., min_length=3)


class BuildingEditReviewRequest(BaseModel):
    status: BuildingEditReviewStatus = Field(..., description="APPROVED or REJECTED")
    comment: str | None = None


class BuildingEditResponse(BaseModel):
    id: UUID
    hlb_id: UUID
    building_id: UUID | None = None
    edit_type: BuildingEditType
    proposed_changes: dict[str, Any]
    reason: str
    requesting_user_id: UUID
    review_status: BuildingEditReviewStatus
    reviewer_id: UUID | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BuildingEditListResponse(BaseModel):
    items: list[BuildingEditResponse]
    total: int
