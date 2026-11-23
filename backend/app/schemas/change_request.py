from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.change_request import (
    ChangeRequestPriority,
    ChangeRequestStatus,
    ChangeRequestType,
)


class ChangeRequestCreate(BaseModel):
    request_type: ChangeRequestType
    hlb_id: UUID | None = None
    layout_id: UUID | None = None
    priority: ChangeRequestPriority = Field(default=ChangeRequestPriority.MEDIUM)
    description: str = Field(..., min_length=5)
    metadata_json: dict[str, Any] | None = None


class ChangeRequestResolutionRequest(BaseModel):
    status: ChangeRequestStatus = Field(..., description="RESOLVED or REJECTED")
    resolution_notes: str = Field(..., min_length=3)


class ChangeRequestResponse(BaseModel):
    id: UUID
    request_type: ChangeRequestType
    hlb_id: UUID | None = None
    layout_id: UUID | None = None
    requesting_user_id: UUID
    assigned_reviewer_id: UUID | None = None
    priority: ChangeRequestPriority
    status: ChangeRequestStatus
    description: str
    resolution_notes: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChangeRequestListResponse(BaseModel):
    items: list[ChangeRequestResponse]
    total: int


class ChangeRequestMessageCreate(BaseModel):
    message: str = Field(..., min_length=1)
    attachments: dict[str, Any] | None = None


class ChangeRequestMessageResponse(BaseModel):
    id: UUID
    change_request_id: UUID
    author_id: UUID
    author_role: str
    message: str
    attachments: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChangeRequestMessageListResponse(BaseModel):
    items: list[ChangeRequestMessageResponse]
    total: int
