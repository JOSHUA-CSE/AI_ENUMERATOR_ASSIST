from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DeputySupervisorInfo(BaseModel):
    id: UUID | None = None
    name: str | None = None
    username: str | None = None
    phone: str | None = None
    status: str | None = None
    is_assigned: bool = False

    model_config = ConfigDict(from_attributes=True)


class DeputyHlbSummary(BaseModel):
    hlb_id: UUID
    block_code: str
    name: str | None = None
    status: str
    assigned_enumerator_id: UUID | None = None
    assigned_enumerator_name: str | None = None
    assigned_supervisor_name: str | None = None
    total_houses: int = 0
    completed_houses: int = 0
    remaining_houses: int = 0
    locked_houses: int = 0
    revisit_count: int = 0
    progress_percentage: float = 0.0
    is_completed: bool = False
    is_active: bool = False
    last_sync: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DeputyLayoutProgressItem(BaseModel):
    layout_id: UUID
    layout_name: str
    area_id: UUID | None = None
    village_name: str | None = None
    status: str
    supervisor: DeputySupervisorInfo | None = None
    total_hlbs: int = 0
    active_hlbs: int = 0
    completed_hlbs: int = 0
    remaining_hlbs: int = 0
    total_houses: int = 0
    completed_houses: int = 0
    remaining_houses: int = 0
    locked_houses: int = 0
    revisit_count: int = 0
    overall_progress_percentage: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class DeputyLayoutDetailProgressResponse(DeputyLayoutProgressItem):
    hlbs: list[DeputyHlbSummary] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class DeputyOverallProgressResponse(BaseModel):
    total_layouts: int = 0
    total_hlbs: int = 0
    active_hlbs: int = 0
    completed_hlbs: int = 0
    remaining_hlbs: int = 0
    total_houses: int = 0
    completed_houses: int = 0
    remaining_houses: int = 0
    locked_houses: int = 0
    revisit_count: int = 0
    overall_progress_percentage: float = 0.0
    layouts: list[DeputyLayoutProgressItem] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)
