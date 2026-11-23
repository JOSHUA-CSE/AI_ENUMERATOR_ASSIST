from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EnumeratorSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    username: str
    phone: str | None = None
    role: str
    status: str
    availability: str  # "AVAILABLE", "ASSIGNED", "INACTIVE"
    assigned_hlb_id: UUID | None = None
    assigned_block_code: str | None = None
    assigned_layout_name: str | None = None


class EnumeratorListResponse(BaseModel):
    items: list[EnumeratorSummaryResponse]
    total: int


class EnumeratorAssignmentRequest(BaseModel):
    enumerator_id: UUID


class EnumeratorAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hlb_id: UUID
    block_code: str | None = None
    layout_id: UUID
    layout_name: str | None = None
    enumerator_id: UUID
    enumerator_name: str | None = None
    enumerator_username: str | None = None
    supervisor_id: UUID | None = None
    supervisor_name: str | None = None
    assigned_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime


class HlbAssignmentStatusItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hlb_id: UUID
    block_code: str
    name: str | None = None
    actual_building_count: int
    target_building_count: int
    is_assigned: bool
    assignment: EnumeratorAssignmentResponse | None = None


class LayoutEnumeratorAssignmentsResponse(BaseModel):
    layout_id: UUID
    layout_name: str
    total_hlbs: int
    required_enumerators: int
    assigned_enumerators: int
    remaining_enumerators: int
    status: str  # "COMPLETE" or "INCOMPLETE"
    is_complete: bool
    items: list[HlbAssignmentStatusItem]


class EnumeratorAssignedHlbDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    layout_id: UUID
    layout_name: str | None = None
    area_name: str | None = None
    block_code: str
    name: str | None = None
    status: str
    target_building_count: int
    actual_building_count: int
    boundary: dict | None = None
    assignment: EnumeratorAssignmentResponse | None = None


class EnumeratorBuildingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    building_reference: str | None = None
    house_number: str | None = None
    latitude: float
    longitude: float
    footprint: dict | None = None
    source_type: str | None = None
    status: str = "PENDING"


class EnumeratorHlbDownloadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hlb: EnumeratorAssignedHlbDetailResponse
    buildings: list[EnumeratorBuildingItem]
    total_buildings: int
    downloaded_at: datetime
