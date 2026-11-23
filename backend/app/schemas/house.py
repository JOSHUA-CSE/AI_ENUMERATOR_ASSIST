from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.house import BuildingFieldStatus, BuildingSourceType


class HouseBase(BaseModel):
    area_id: UUID | None = Field(default=None, description="Administrative area ID")
    building_reference: str | None = Field(default=None, max_length=100)
    house_number: str | None = Field(default=None, max_length=100)
    latitude: float = Field(
        ..., ge=-90.0, le=90.0, description="Latitude in decimal degrees"
    )
    longitude: float = Field(
        ..., ge=-180.0, le=180.0, description="Longitude in decimal degrees"
    )
    source_type: BuildingSourceType = Field(
        default=BuildingSourceType.SATELLITE_DETECTED,
        description="Origin of building data",
    )
    field_status: BuildingFieldStatus = Field(
        default=BuildingFieldStatus.UNVERIFIED,
        description="Ground survey verification status",
    )
    listing_closed: bool = Field(
        default=False,
        description="Whether census house listing is explicitly closed for this building",
    )
    listing_closed_at: datetime | None = None
    detection_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Detection confidence"
    )
    imagery_source: str | None = Field(
        default=None, description="Satellite imagery provider name"
    )
    imagery_date: datetime | date | None = Field(
        default=None, description="Date of imagery acquisition"
    )


class HouseCreate(HouseBase):
    pass


class HouseResponse(BaseModel):
    id: UUID
    area_id: UUID
    building_reference: str | None = None
    house_number: str | None = None
    latitude: float
    longitude: float
    source_type: BuildingSourceType | str = BuildingSourceType.SATELLITE_DETECTED
    field_status: BuildingFieldStatus | str = BuildingFieldStatus.UNVERIFIED
    listing_closed: bool = False
    listing_closed_at: datetime | None = None
    detection_confidence: float | None = None
    detected_at: datetime | None = None
    imagery_source: str | None = None
    imagery_date: datetime | None = None
    footprint: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HouseListResponse(BaseModel):
    items: list[HouseResponse]
    total: int
    skip: int
    limit: int


class BuildingDensityCluster(BaseModel):
    latitude: float
    longitude: float
    count: int
    bounds: list[list[float]]


class BuildingEstimationResponse(BaseModel):
    area_id: UUID
    area_name: str
    area_code: str
    total_buildings: int
    source_type: str
    quality_label: str
    imagery_source: str | None = None
    imagery_date: str | None = None
    average_confidence: float | None = None
    density_clusters: list[BuildingDensityCluster] = []
    is_synthetic: bool = False
    provenance: str | None = None
    licence: str | None = None
    projected_crs: str | None = "EPSG:32643"
