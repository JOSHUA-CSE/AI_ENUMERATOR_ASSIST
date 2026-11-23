from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.gis.hlb.boundary_checker import BoundaryStatusEnum


class GpsObservationCreate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude")
    accuracy_meters: float | None = Field(
        default=None, ge=0.0, description="Horizontal accuracy radius in meters"
    )
    building_id: UUID | None = Field(
        default=None, description="Optional associated building UUID"
    )
    timestamp: datetime | None = Field(
        default=None, description="Device-recorded observation timestamp"
    )


class GpsObservationResponse(BaseModel):
    id: UUID
    hlb_id: UUID
    enumerator_id: UUID
    house_id: UUID | None = None
    latitude: float
    longitude: float
    accuracy_meters: float | None = None
    timestamp: datetime
    source: str = "OFFLINE"

    model_config = {"from_attributes": True}


class GpsBoundaryCheckRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: float | None = Field(default=None, ge=0.0)


class GpsBoundaryCheckResponse(BaseModel):
    status: BoundaryStatusEnum
    distance_to_boundary_meters: float | None = None
    accuracy_meters: float | None = None
    message: str | None = None


class GpsHlbStatusResponse(BaseModel):
    hlb_id: UUID
    total_observations: int
    latest_observation: GpsObservationResponse | None = None
    boundary_status: BoundaryStatusEnum | None = None
    distance_to_boundary_meters: float | None = None


class GpsBoundaryEventRequest(BaseModel):
    event_type: str = Field(default="EXIT", description="EXIT, ENTRY, ACCURACY_WARNING")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: float | None = Field(default=None, ge=0.0)
    distance_to_boundary_meters: float | None = None
    device_id: str | None = None
    timestamp: datetime | None = None


class GpsBoundaryEventResponse(BaseModel):
    event_id: UUID
    hlb_id: UUID
    enumerator_id: UUID
    event_type: str
    boundary_status: str
    distance_to_boundary_meters: float | None = None
    accuracy_meters: float | None = None
    supervisor_notified: bool = False
    message: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class EnumeratorLiveLocationItem(BaseModel):
    enumerator_id: UUID
    enumerator_name: str
    hlb_id: UUID
    block_code: str
    latitude: float | None = None
    longitude: float | None = None
    accuracy_meters: float | None = None
    boundary_status: str = "UNKNOWN"
    distance_to_boundary_meters: float | None = None
    last_timestamp: datetime | None = None
    is_live: bool = False
    road_coverage_percentage: float = 0.0
    unvisited_edges_count: int = 0
    recent_boundary_events_count: int = 0


class SupervisorEnumeratorMonitoringResponse(BaseModel):
    supervisor_id: UUID
    total_enumerators: int
    active_now_count: int
    outside_hlb_count: int
    uncertain_count: int
    enumerators: list[EnumeratorLiveLocationItem]

