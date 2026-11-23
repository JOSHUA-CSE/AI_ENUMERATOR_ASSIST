from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ==============================================================================
# Phase 9: Full-Road-Coverage Rural Postman Problem (RPP) Schemas
# ==============================================================================


class GraphBuildRequest(BaseModel):
    buffer_meters: float = Field(default=30.0, ge=0.0, le=200.0, description="Buffer around HLB boundary in meters")
    force_rebuild: bool = Field(default=False, description="Whether to rebuild from OSM raw source")


class GraphStatisticsResponse(BaseModel):
    hlb_id: UUID
    graph_version: str = "v1.0"
    source: str = "OpenStreetMap"
    license: str = "ODbL"
    acquisition_date: str = "2026-11-11T09:42:04Z"
    node_count: int
    edge_count: int
    required_edge_count: int
    total_required_length_m: float
    disconnected_components_count: int
    two_sided_edges_count: int


class RppRouteGenerateRequest(BaseModel):
    start_latitude: float | None = Field(None, ge=-90.0, le=90.0)
    start_longitude: float | None = Field(None, ge=-180.0, le=180.0)
    current_latitude: float | None = Field(None, ge=-90.0, le=90.0)
    current_longitude: float | None = Field(None, ge=-180.0, le=180.0)
    accuracy_meters: float | None = Field(None, ge=0.0)
    end_latitude: float | None = Field(None, ge=-90.0, le=90.0)
    end_longitude: float | None = Field(None, ge=-180.0, le=180.0)
    return_to_start: bool = Field(default=False, description="Whether the walking route must return to start point")


class RppRouteReplanRequest(BaseModel):
    current_latitude: float = Field(..., ge=-90.0, le=90.0)
    current_longitude: float = Field(..., ge=-180.0, le=180.0)
    reason: str = Field(default="DEVIATION", description="Reason for replanning: DEVIATION, MISSING_ROAD_ADDED, REVISIT")


class RoadSegmentItem(BaseModel):
    segment_id: str
    osm_way_id: int | None = None
    osm_node_ids: list[int] = Field(default_factory=list)
    coordinates: list[list[float]] = Field(..., description="Ordered [[lat, lon], ...] coordinates")
    length_m: float = Field(..., ge=0.0)
    walking_cost: float = Field(default=0.0, description="Estimated walking duration in minutes")
    highway: str
    name: str | None = None
    foot: str | None = None
    access: str | None = None
    surface: str | None = None
    boundary_classification: str = "INTERNAL"
    required_status: str = "REQUIRED"
    coverage_status: str = "NOT_VISITED"
    requires_two_sided: bool = False
    left_surveyed: bool = False
    right_surveyed: bool = False
    is_surveyed: bool = False
    walking_speed_factor: float = 1.0


class RouteSectionSchema(BaseModel):
    section_index: int
    is_primary: bool
    segment_count: int
    total_distance_km: float
    estimated_walking_time_minutes: float
    ordered_coordinates: list[list[float]]
    traversed_segment_ids: list[str]
    is_disconnected: bool = False
    disconnection_distance_m: float = 0.0
    disconnection_note: str | None = None


class RouteStepSchema(BaseModel):
    step_index: int
    section_index: int
    edge_id: str
    osm_way_id: int | None = None
    highway_type: str
    road_name: str | None = None
    is_transit: bool = False
    is_deadhead: bool = False
    from_node: list[float]
    to_node: list[float]
    length_m: float
    walking_time_minutes: float
    cumulative_distance_m: float
    cumulative_walking_time_minutes: float
    coordinates: list[list[float]]
    nearby_building_ids: list[str] = Field(default_factory=list)


class BuildingEncounterSchema(BaseModel):
    building_id: str
    building_reference: str
    latitude: float
    longitude: float
    matched_edge_id: str
    distance_along_edge_m: float
    traversal_step_index: int
    encounter_order: int


class RppRouteResponse(BaseModel):
    route_id: str
    hlb_id: UUID
    route_version: int = 1
    graph_version: str = "v1.0"
    source: str = "OpenStreetMap"
    license: str = "ODbL"
    acquisition_date: str = "2026-11-11T09:42:04Z"
    total_distance_km: float
    estimated_walking_time_minutes: float
    total_required_edges_count: int
    surveyed_edges_count: int
    coverage_percentage: float
    deadhead_distance_km: float
    deadhead_percentage: float
    disconnected_components_count: int
    external_transit_count: int
    sections: list[RouteSectionSchema] = Field(default_factory=list)
    steps: list[RouteStepSchema] = Field(default_factory=list)
    continuous_polyline: list[list[float]] = Field(default_factory=list)
    all_road_segments: list[RoadSegmentItem] = Field(default_factory=list)
    building_encounter_order: list[BuildingEncounterSchema] = Field(default_factory=list)
    start_point: list[float] | None = None
    end_point: list[float] | None = None
    warnings: list[str] = Field(default_factory=list)
    routing_mode: str = "RURAL_POSTMAN_PROBLEM"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Alias for backward compatibility
RoadCoverageRouteResponse = RppRouteResponse


class HlbCoverageStatusResponse(BaseModel):
    hlb_id: UUID
    total_required_length_m: float
    surveyed_required_length_m: float
    coverage_percentage: float
    total_required_edges_count: int
    fully_surveyed_count: int
    in_progress_count: int
    unvisited_count: int
    needs_revisit_count: int
    external_transit_distance_m: float
    # Building enumeration progress (authoritative separation)
    buildings_visited_count: int
    buildings_total_count: int
    buildings_completion_percentage: float


class GpsTracePoint(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    timestamp: datetime | None = None
    accuracy: float | None = Field(None, description="GPS horizontal accuracy in meters")


class GpsTraceMatchRequest(BaseModel):
    gps_points: list[GpsTracePoint]
    device_id: str | None = None
    tolerance_meters: float = Field(default=15.0, ge=1.0, le=100.0, description="Snapping tolerance in meters")


class GpsTraceMatchResponse(BaseModel):
    updated_segments: int
    coverage_percentage: float
    surveyed_length_m: float
    total_required_length_m: float
    accuracy_warning: str | None = None


class RouteDeviationCheckRequest(BaseModel):
    current_latitude: float = Field(..., ge=-90.0, le=90.0)
    current_longitude: float = Field(..., ge=-180.0, le=180.0)
    route_polyline: list[list[float]]
    threshold_meters: float = Field(default=50.0, ge=5.0, le=500.0)


class RouteDeviationCheckResponse(BaseModel):
    is_deviated: bool
    deviation_distance_m: float
    threshold_meters: float
    message: str


class MissingPathSubmissionRequest(BaseModel):
    coordinates: list[list[float]] = Field(..., description="Ordered [[lat, lon], ...] coordinates of the missing path")
    highway_type: str = Field(default="path", description="Proposed highway class: path, footway, residential, etc.")
    road_name: str | None = None
    notes: str | None = None


class MissingPathSubmissionResponse(BaseModel):
    submission_id: UUID
    hlb_id: UUID
    status: str
    highway_type: str
    coordinates_count: int
    submitted_at: datetime
    message: str


class MissingPathReviewRequest(BaseModel):
    action: str = Field(..., description="APPROVE or REJECT")
    review_notes: str | None = None
    corrected_coordinates: list[list[float]] | None = None
    corrected_highway_type: str | None = None


class MissingPathReviewResponse(BaseModel):
    submission_id: UUID
    status: str
    reviewed_at: datetime
    graph_version: str
    new_edge_id: str | None = None
    message: str


class OfflineHlbRoutePackageResponse(BaseModel):
    hlb_id: UUID
    graph_version: str
    route_version: int
    source: str = "OpenStreetMap"
    license: str = "ODbL"
    acquisition_date: str = "2026-11-11T09:42:04Z"
    boundary_geojson: dict[str, Any]
    nodes: list[dict[str, Any]]
    edges: list[RoadSegmentItem]
    required_edge_ids: list[str]
    planned_route: RppRouteResponse
    building_markers: list[dict[str, Any]]
    building_encounter_order: list[BuildingEncounterSchema]
    coverage_status: list[dict[str, Any]]
    tile_source: dict[str, Any]


class RouteVersionResponse(BaseModel):
    hlb_id: UUID
    route_version: int
    graph_version: str
    has_active_route: bool
    updated_at: datetime | None = None


class DisconnectedComponentsResponse(BaseModel):
    hlb_id: UUID
    components_count: int
    components_summary: list[dict[str, Any]]
    external_transit_available: bool


# Field Building Discovery
class BuildingDiscoveryRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    building_reference: str | None = None
    house_number: str | None = None
    notes: str | None = None
    placement_mode: str = Field(default="CURRENT_GPS", description="CURRENT_GPS or MANUAL_MAP")


class BuildingDiscoveryResponse(BaseModel):
    building_id: UUID | str
    building_reference: str
    house_number: str | None = None
    latitude: float
    longitude: float
    source_type: str
    field_status: str
    edit_id: UUID | str
    review_status: str
    message: str


# Legacy & Compatibility Request Schemas
class RouteStartingPointRequest(BaseModel):
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    road_segments: list[Any] | None = None


# Phase 10: Missed Road & Traversal Schemas
class MissedRoadItem(BaseModel):
    edge_id: str
    osm_way_id: str | None = None
    highway_type: str
    road_name: str | None = None
    total_length_m: float
    surveyed_length_m: float
    remaining_length_m: float
    coverage_status: str
    reason: str
    coordinates: list[list[float]] = Field(..., description="[[lat, lon], ...]")
    center_coordinate: list[float] = Field(..., description="[lat, lon]")


class MissedRoadsResponse(BaseModel):
    hlb_id: UUID
    total_required_edges: int
    missed_edges_count: int
    total_missed_length_m: float
    missed_roads: list[MissedRoadItem]


class TraversalStartRequest(BaseModel):
    current_latitude: float = Field(..., ge=-90.0, le=90.0)
    current_longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: float | None = Field(default=None, ge=0.0)
    device_id: str | None = None


class TraversalStartResponse(BaseModel):
    hlb_id: UUID
    status: str  # "TRAVERSAL_ACTIVE", "BLOCKED_OUTSIDE_HLB", "BLOCKED_UNCERTAIN_GPS"
    message: str
    current_boundary_status: str
    distance_to_boundary_meters: float | None = None
    route_id: str | None = None
    total_remaining_edges: int = 0
    total_remaining_distance_km: float = 0.0


