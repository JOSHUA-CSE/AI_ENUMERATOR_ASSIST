from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.administrative_area import AreaType


class AdministrativeAreaBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Area name")
    type: AreaType = Field(default=AreaType.VILLAGE, description="Area type")
    code: str = Field(
        ..., min_length=1, max_length=100, description="Official area code"
    )
    parent_id: UUID | None = Field(
        default=None, description="Parent administrative area ID"
    )
    boundary_status: str = Field(
        default="PROVISIONAL", description="Status of boundary: OFFICIAL, PROVISIONAL, ESTIMATED"
    )


class AdministrativeAreaCreate(AdministrativeAreaBase):
    boundary: dict[str, Any] = Field(
        ..., description="GeoJSON Polygon or MultiPolygon geometry dictionary"
    )


class AdministrativeAreaUpdate(BaseModel):
    name: str | None = None
    type: AreaType | None = None
    code: str | None = None
    parent_id: UUID | None = None
    boundary: dict[str, Any] | None = None
    boundary_status: str | None = None
    status: str | None = None


class AdministrativeAreaResponse(AdministrativeAreaBase):
    id: UUID
    status: str
    boundary_status: str = "PROVISIONAL"
    house_count: int = 0
    boundary: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdministrativeAreaListResponse(BaseModel):
    items: list[AdministrativeAreaResponse]
    total: int
    skip: int
    limit: int


class AdministrativeAreaBoundaryResponse(BaseModel):
    id: UUID
    name: str
    code: str
    type: AreaType
    boundary_status: str = "PROVISIONAL"
    boundary: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
