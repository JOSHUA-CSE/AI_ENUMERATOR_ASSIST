import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from shapely.geometry import MultiPolygon, Polygon

from app.gis.route.road_network import (
    RoadNetwork,
    RoadSegment,
    calculate_linestring_length_m,
)
from app.gis.route.rpp_solver import (
    RouteSection,
    RouteStep,
    RppRouteResult,
    solve_undirected_rpp,
)

logger = logging.getLogger(__name__)


@dataclass
class RoadCoverageRouteResult:
    route_id: str
    hlb_id: str
    network_version: str
    acquisition_date: str
    total_distance_km: float
    estimated_walking_time_minutes: float
    total_segments_count: int
    surveyed_segments_count: int
    coverage_percentage: float
    sections: list[RouteSection]
    continuous_polyline: list[list[float]]  # Coordinates of primary section / connected traversal
    all_road_segments: list[dict[str, Any]]
    disconnected_components_count: int = 1
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "hlb_id": self.hlb_id,
            "network_version": self.network_version,
            "acquisition_date": self.acquisition_date,
            "total_distance_km": round(self.total_distance_km, 3),
            "estimated_walking_time_minutes": round(self.estimated_walking_time_minutes, 1),
            "total_segments_count": self.total_segments_count,
            "surveyed_segments_count": self.surveyed_segments_count,
            "coverage_percentage": round(self.coverage_percentage, 1),
            "sections": [s.to_dict() for s in self.sections],
            "continuous_polyline": self.continuous_polyline,
            "all_road_segments": self.all_road_segments,
            "disconnected_components_count": self.disconnected_components_count,
            "warnings": self.warnings,
        }


def generate_hlb_road_coverage_route(
    hlb_id: str,
    hlb_polygon: Polygon | MultiPolygon,
    road_network: RoadNetwork,
    start_location: tuple[float, float] | None = None,
    surveyed_segment_ids: set[str] | None = None,
    return_to_start: bool = False,
    buffer_meters: float = 20.0,
) -> RoadCoverageRouteResult:
    """
    Generate an authoritative Full-Road-Coverage Rural Postman Problem (RPP) route
    traversing every eligible walkable street and pathway within the assigned HLB boundary.
    """
    segments = road_network.query_segments_in_polygon(hlb_polygon, buffer_meters=buffer_meters)

    if not segments:
        return RoadCoverageRouteResult(
            route_id=str(uuid.uuid4()),
            hlb_id=str(hlb_id),
            network_version=road_network.network_version,
            acquisition_date=road_network.acquisition_date,
            total_distance_km=0.0,
            estimated_walking_time_minutes=0.0,
            total_segments_count=0,
            surveyed_segments_count=0,
            coverage_percentage=0.0,
            sections=[],
            continuous_polyline=[],
            all_road_segments=[],
            disconnected_components_count=0,
            warnings=["MISSING_ROAD_NETWORK_DATA: No walkable road segments found intersecting this HLB boundary."],
        )

    rpp_res = solve_undirected_rpp(
        hlb_id=str(hlb_id),
        required_edges=segments,
        start_location=start_location,
        surveyed_segment_ids=surveyed_segment_ids,
        return_to_start=return_to_start,
    )

    return RoadCoverageRouteResult(
        route_id=rpp_res.route_id,
        hlb_id=rpp_res.hlb_id,
        network_version=rpp_res.network_version,
        acquisition_date=rpp_res.acquisition_date,
        total_distance_km=rpp_res.total_distance_km,
        estimated_walking_time_minutes=rpp_res.estimated_walking_time_minutes,
        total_segments_count=rpp_res.total_required_edges_count,
        surveyed_segments_count=rpp_res.surveyed_edges_count,
        coverage_percentage=rpp_res.coverage_percentage,
        sections=rpp_res.sections,
        continuous_polyline=rpp_res.continuous_polyline,
        all_road_segments=rpp_res.all_required_edges,
        disconnected_components_count=rpp_res.disconnected_components_count,
        warnings=rpp_res.warnings,
    )
