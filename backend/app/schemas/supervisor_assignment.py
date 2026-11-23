from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.layout import LayoutResponse


class SupervisorAssignmentRequest(BaseModel):
    supervisor_id: UUID = Field(
        ..., description="UUID of the Supervisor to assign to the layout"
    )


class SupervisorSummaryResponse(BaseModel):
    id: UUID
    name: str
    username: str
    phone: str | None = None
    role: str = "SUPERVISOR"
    status: str = "ACTIVE"
    assigned_layouts_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SupervisorListResponse(BaseModel):
    items: list[SupervisorSummaryResponse]
    total: int


class SupervisorAssignmentResponse(BaseModel):
    id: UUID
    layout_id: UUID
    layout_name: str | None = None
    supervisor_id: UUID
    supervisor_name: str | None = None
    supervisor_username: str | None = None
    assigned_by: UUID | None = None
    assigned_by_name: str | None = None
    assigned_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupervisorLayoutResponse(LayoutResponse):
    assignment: SupervisorAssignmentResponse | None = None
    supervisor_name: str | None = None


class SupervisorLayoutListResponse(BaseModel):
    items: list[SupervisorLayoutResponse]
    total: int
