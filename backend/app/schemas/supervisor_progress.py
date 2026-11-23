from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SupervisorEnumeratorProgress(BaseModel):
    id: UUID
    name: str
    username: str | None = None
    phone: str | None = None
    assigned_hlb_id: UUID | None = None
    assigned_hlb_code: str | None = None
    progress_percentage: float = 0.0
    completed_houses: int = 0
    remaining_houses: int = 0
    locked_houses: int = 0
    revisit_count: int = 0
    last_sync: datetime | None = None
    sync_status: str | None = "SYNCED"

    model_config = ConfigDict(from_attributes=True)


class BoundaryAlertItem(BaseModel):
    track_id: UUID
    timestamp: datetime
    latitude: float
    longitude: float
    distance_meters: float | None = None
    message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SupervisorHlbProgressResponse(BaseModel):
    hlb_id: UUID
    block_code: str
    name: str | None = None
    enumerator: SupervisorEnumeratorProgress | None = None
    total_houses: int = 0
    completed_houses: int = 0
    remaining_houses: int = 0
    locked_houses: int = 0
    revisit_count: int = 0
    progress_percentage: float = 0.0
    last_sync: datetime | None = None
    gps_coverage: float | None = None
    boundary_alert_count: int = 0
    boundary_alerts: list[BoundaryAlertItem] = Field(default_factory=list)

    # Domain metrics
    buildings_discovered: int = 0
    buildings_visited: int = 0
    buildings_confirmed: int = 0
    buildings_listing_closed: int = 0
    buildings_false_detection: int = 0
    buildings_completed: int = 0
    census_houses_total: int = 0
    census_houses_listed: int = 0
    census_houses_vacant: int = 0
    census_houses_non_residential: int = 0
    census_houses_locked: int = 0
    census_houses_resolved: int = 0
    households_total: int = 0
    households_submitted: int = 0
    households_verified: int = 0
    households_rejected: int = 0
    persons_enumerated: int = 0
    pending_revisits: int = 0

    model_config = ConfigDict(from_attributes=True)


class SupervisorLayoutProgressResponse(BaseModel):
    layout_id: UUID
    layout_name: str
    area_id: UUID | None = None
    village_name: str | None = None
    total_hlbs: int = 0
    total_houses: int = 0
    completed_houses: int = 0
    remaining_houses: int = 0
    locked_houses: int = 0
    revisit_count: int = 0
    progress_percentage: float = 0.0
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    hlbs: list[SupervisorHlbProgressResponse] = Field(default_factory=list)

    # Domain metrics
    buildings_discovered: int = 0
    buildings_visited: int = 0
    buildings_confirmed: int = 0
    buildings_listing_closed: int = 0
    buildings_false_detection: int = 0
    census_houses_listed: int = 0
    census_houses_vacant: int = 0
    census_houses_non_residential: int = 0
    census_houses_locked: int = 0
    census_houses_resolved: int = 0
    households_submitted: int = 0
    households_verified: int = 0
    pending_revisits: int = 0

    model_config = ConfigDict(from_attributes=True)


class SupervisorOverallProgressResponse(BaseModel):
    layouts: list[SupervisorLayoutProgressResponse] = Field(default_factory=list)
    total_layouts: int = 0
    overall_total_houses: int = 0
    overall_completed_houses: int = 0
    overall_remaining_houses: int = 0
    overall_locked_houses: int = 0
    overall_revisit_count: int = 0
    overall_progress_percentage: float = 0.0
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    # Domain metrics
    buildings_discovered: int = 0
    buildings_visited: int = 0
    buildings_confirmed: int = 0
    buildings_listing_closed: int = 0
    census_houses_listed: int = 0
    census_houses_resolved: int = 0
    households_submitted: int = 0
    households_verified: int = 0
    pending_revisits: int = 0

    model_config = ConfigDict(from_attributes=True)
