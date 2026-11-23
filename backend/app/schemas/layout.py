from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.layout import (
    LayoutStatus,
    LayoutVersionSource,
    LayoutVersionStatus,
)
from app.schemas.hlb import HlbResponse


class LayoutBase(BaseModel):
    area_id: UUID | None = Field(default=None, description="Administrative Area ID")
    administrative_area_id: UUID | None = Field(
        default=None, description="Administrative Area ID alias"
    )
    area_ids: list[UUID] | None = Field(
        default=None, description="List of Administrative Area IDs for multi-area layouts"
    )
    administrative_area_ids: list[UUID] | None = Field(
        default=None, description="Administrative Area IDs alias"
    )
    name: str = Field(..., min_length=1, max_length=255, description="Layout name")
    target_buildings_per_hlb: int = Field(
        default=250, ge=10, le=5000, description="Target buildings per HLB"
    )
    target_houses_per_hlb: int | None = Field(
        default=None, description="Legacy target houses alias"
    )
    workload_unit: str = Field(
        default="BUILDINGS", description="Workload unit: BUILDINGS, CENSUS_HOUSES, POPULATION"
    )
    target_workload: int = Field(
        default=250, description="Configured workload target"
    )
    estimated_census_house_count: int | None = Field(
        default=None, description="Estimated census-house count across layout"
    )
    estimated_population: int | None = Field(
        default=None, description="Estimated population across layout"
    )
    estimation_method: str | None = Field(
        default=None, description="Method used to calculate estimates"
    )
    estimation_provenance: str | None = Field(
        default=None, description="Data source and provenance for estimates"
    )
    boundary_status: str = Field(
        default="PROVISIONAL", description="Status of layout boundary: OFFICIAL, PROVISIONAL, ESTIMATED"
    )
    description: str | None = Field(default=None, description="Optional description")

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Resolve area IDs
            if not data.get("area_ids") and data.get("administrative_area_ids"):
                data["area_ids"] = data["administrative_area_ids"]
            # Resolve single area ID
            if not data.get("area_id") and data.get("administrative_area_id"):
                data["area_id"] = data["administrative_area_id"]
            if not data.get("area_id") and data.get("area_ids") and len(data["area_ids"]) > 0:
                data["area_id"] = data["area_ids"][0]
            if not data.get("area_ids") and data.get("area_id"):
                data["area_ids"] = [data["area_id"]]

            # Resolve target buildings per HLB
            if (
                "target_buildings_per_hlb" not in data
                and "target_houses_per_hlb" in data
            ):
                data["target_buildings_per_hlb"] = data["target_houses_per_hlb"]
        return data

    @property
    def target_hlb_house_count(self) -> int:
        return self.target_buildings_per_hlb

    @property
    def target_houses_per_hlb_prop(self) -> int:
        return self.target_buildings_per_hlb


class LayoutCreate(LayoutBase):
    pass


class LayoutUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    target_buildings_per_hlb: int | None = Field(default=None, ge=10, le=5000)
    target_houses_per_hlb: int | None = None
    target_workload: int | None = None
    workload_unit: str | None = None
    area_ids: list[UUID] | None = None
    administrative_area_ids: list[UUID] | None = None
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("area_ids") and data.get("administrative_area_ids"):
                data["area_ids"] = data["administrative_area_ids"]
            if (
                "target_buildings_per_hlb" not in data
                and "target_houses_per_hlb" in data
            ):
                data["target_buildings_per_hlb"] = data["target_houses_per_hlb"]
        return data


class LayoutVersionResponse(BaseModel):
    id: UUID
    layout_id: UUID
    version_number: int
    source: LayoutVersionSource
    status: LayoutVersionStatus
    target_buildings_per_hlb: int
    workload_unit: str = "BUILDINGS"
    target_workload: int = 250
    estimated_census_house_count: int | None = None
    estimated_population: int | None = None
    estimation_method: str | None = None
    estimation_provenance: str | None = None
    total_buildings: int
    hlb_count: int
    boundary_status: str = "PROVISIONAL"
    quality_score: float | None = None
    validation_status: str
    validation_summary: dict[str, Any] | None = None
    generation_metadata: dict[str, Any] | None = None
    created_by: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LayoutVersionListResponse(BaseModel):
    items: list[LayoutVersionResponse]
    total: int
    layout_id: UUID


class LayoutResponse(BaseModel):
    id: UUID
    area_id: UUID
    administrative_area_id: UUID | None = None
    area_ids: list[UUID] = Field(default_factory=list)
    area_names: list[str] = Field(default_factory=list)
    areas_count: int | None = None
    supervisor_id: UUID | None = None
    assigned_supervisor_name: str | None = None
    name: str
    target_buildings_per_hlb: int = 250
    target_houses_per_hlb: int = 250
    workload_unit: str = "BUILDINGS"
    target_workload: int = 250
    estimated_census_house_count: int | None = None
    estimated_population: int | None = None
    estimation_method: str | None = None
    estimation_provenance: str | None = None
    actual_building_count: int = 0
    total_buildings: int = 0
    expected_hlb_count: int = 0
    hlb_count: int = 0
    boundary_status: str = "PROVISIONAL"
    status: LayoutStatus
    boundary: dict[str, Any] | None = None
    active_version_id: UUID | None = None
    active_version: LayoutVersionResponse | None = None
    active_version_number: int | None = None
    active_version_status: str | None = None
    created_by: UUID | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def populate_area_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("administrative_area_id") and data.get("area_id"):
                data["administrative_area_id"] = data["area_id"]
            elif not data.get("area_id") and data.get("administrative_area_id"):
                data["area_id"] = data["administrative_area_id"]
            if not data.get("area_ids") and data.get("area_id"):
                data["area_ids"] = [data["area_id"]]
        elif hasattr(data, "area_id"):
            # When loaded from ORM model object
            pass
        return data

    @property
    def target_hlb_house_count(self) -> int:
        return self.target_buildings_per_hlb

    @property
    def actual_house_count(self) -> int:
        return self.actual_building_count

    model_config = ConfigDict(from_attributes=True)


class LayoutListResponse(BaseModel):
    items: list[LayoutResponse]
    total: int


class GenerateHlbsRequest(BaseModel):
    target_buildings_per_hlb: int = Field(
        default=250,
        ge=10,
        le=5000,
        description="Configurable target building count per HLB",
    )


class HlbGenerationResultResponse(BaseModel):
    layout_id: UUID
    layout_name: str
    version_id: UUID
    version_number: int
    total_buildings: int
    target_buildings_per_hlb: int
    hlb_count: int
    boundary_status: str = "PROVISIONAL"
    quality_score: float | None = None
    validation_status: str
    validation_summary: dict[str, Any]
    generation_metadata: dict[str, Any]
    hlbs: list[HlbResponse]


class LayoutValidationChecklistItem(BaseModel):
    id: str
    title: str
    passed: bool
    detail: str


class LayoutValidationResponse(BaseModel):
    layout_id: UUID
    version_id: UUID | None = None
    version_number: int | None = None
    is_valid: bool
    can_approve: bool
    status: str
    total_buildings: int
    assigned_buildings: int
    unassigned_buildings: int
    duplicate_assignments: int
    hlb_count: int
    quality_score: float | None = None
    checklist: list[LayoutValidationChecklistItem]
    warnings: list[str]
    errors: list[str]


class LayoutApprovalResponse(BaseModel):
    layout_id: UUID
    name: str
    status: str
    version_id: UUID
    version_number: int
    version_status: str
    total_buildings: int
    hlb_count: int
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    validation_summary: LayoutValidationResponse
