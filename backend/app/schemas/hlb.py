from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.hlb import HlbStatus, HlbValidationStatus


class HlbBase(BaseModel):
    block_code: str = Field(..., description="HLB Code, e.g., HLB-001")
    name: str | None = Field(default=None, description="Optional block name")
    target_building_count: int = Field(default=250, description="Target building count")
    actual_building_count: int = Field(default=0, description="Assigned building count")
    count_deviation: int = Field(
        default=0, description="Deviation from target count (actual - target)"
    )
    estimated_census_house_count: int | None = Field(
        default=None, description="Estimated census houses in block"
    )
    estimated_population: int | None = Field(
        default=None, description="Estimated population in block"
    )
    boundary_status: str = Field(
        default="PROVISIONAL", description="Status of boundary: OFFICIAL, PROVISIONAL, ESTIMATED"
    )

    @property
    def target_house_count(self) -> int:
        return self.target_building_count

    @property
    def actual_house_count(self) -> int:
        return self.actual_building_count


class HlbResponse(HlbBase):
    id: UUID
    layout_id: UUID
    version_id: UUID
    status: HlbStatus
    quality_score: float | None = None
    validation_status: HlbValidationStatus
    validation_details: dict[str, Any] | None = None
    boundary: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HlbDetailResponse(HlbResponse):
    houses: list[dict[str, Any]] = Field(default_factory=list)


class HlbListResponse(BaseModel):
    items: list[HlbResponse]
    total: int
    layout_id: UUID
    version_id: UUID | None = None


class HlbBoundaryUpdateRequest(BaseModel):
    boundary: dict[str, Any] = Field(
        ..., description="GeoJSON Polygon or MultiPolygon geometry"
    )


class HlbSplitRequest(BaseModel):
    split_ratio: float = Field(
        default=0.5,
        ge=0.1,
        le=0.9,
        description="Split ratio between 0.1 and 0.9 (default 0.5)",
    )
    split_method: str = Field(
        default="AUTO_BALANCED",
        description="Split method: AUTO_BALANCED, TARGET_BASED, or DRAW_LINE",
    )
    target_building_count: int | None = Field(
        default=None,
        description="Target building count for Side A when using TARGET_BASED split",
    )
    split_line_coordinates: list[list[float]] | None = Field(
        default=None,
        description=(
            "LineString coordinates [[lng, lat], ...] when using DRAW_LINE split"
        ),
    )


class HlbSplitResponse(BaseModel):
    layout_id: UUID
    version_id: UUID
    split_hlb_a: HlbResponse
    split_hlb_b: HlbResponse


class HlbSplitPreviewResponse(BaseModel):
    original_hlb_code: str
    total_buildings: int
    total_original_buildings: int | None = None
    part_a_code: str
    side_a_block_code: str | None = None
    part_a_buildings: int
    side_a_building_count: int | None = None
    part_a_quality: float
    part_a_geometry: dict[str, Any] | None = None
    part_a_building_ids: list[UUID] = Field(default_factory=list)
    part_b_code: str
    side_b_block_code: str | None = None
    part_b_buildings: int
    side_b_building_count: int | None = None
    part_b_quality: float
    part_b_geometry: dict[str, Any] | None = None
    part_b_building_ids: list[UUID] = Field(default_factory=list)
    is_valid: bool
    validation_status: str
    invariants: dict[str, bool]
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class HlbMergeRequest(BaseModel):
    hlb_id_1: UUID = Field(..., description="First HLB ID to merge")
    hlb_id_2: UUID = Field(..., description="Second HLB ID to merge")


class HlbMergeResponse(BaseModel):
    layout_id: UUID
    version_id: UUID
    merged_hlb: HlbResponse


class HlbMergePreviewResponse(BaseModel):
    hlb_code_1: str
    hlb_code_2: str
    buildings_1: int
    buildings_2: int
    combined_buildings: int
    is_adjacent: bool
    is_valid: bool
    validation_status: str
    suggested_name: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
