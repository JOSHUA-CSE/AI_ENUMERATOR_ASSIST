import logging
import math
import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from geoalchemy2.shape import to_shape
from shapely.geometry import LineString, Point
from sqlalchemy.orm import Session

from app.gis.route.coverage_router import (
    RoadCoverageRouteResult,
    generate_hlb_road_coverage_route,
)
from app.gis.route.road_network import (
    RoadNetwork,
    RoadSegment,
    get_road_network,
)
from app.gis.spatial import (
    COIMBATORE_PROJECTED_CRS,
    DEFAULT_GEOGRAPHIC_CRS,
    calculate_projected_distance_meters,
    transform_geometry,
)
from app.models.enumerator_assignment import (
    EnumeratorAssignmentStatus,
    HlbEnumeratorAssignment,
)
from app.models.hlb import HouselistingBlock
from app.models.road_coverage import (
    RoadCoverageSyncStatus,
    RoadSegmentCoverage,
    RoadSegmentSurveyStatus,
)

logger = logging.getLogger(__name__)

DEFAULT_GPS_ROAD_MATCHING_TOLERANCE_M = 15.0  # Configurable GPS matching buffer (meters)
SURVEY_COMPLETION_THRESHOLD_PCT = 85.0  # Percentage of segment length required to mark SURVEYED
SURVEY_IN_PROGRESS_THRESHOLD_PCT = 10.0  # Threshold to mark IN_PROGRESS
ROUTE_DEVIATION_THRESHOLD_M = 35.0  # Distance from planned route to trigger deviation warning
STRICT_GPS_ACCURACY_THRESHOLD_M = 30.0  # Accuracy required for authoritative coverage


class RoadCoverageService:
    def verify_enumerator_authorization(
        self, db: Session, hlb_id: UUID, enumerator_id: UUID
    ) -> HlbEnumeratorAssignment:
        """Enforce strict assignment check: 403 Forbidden for unauthorized enumerators."""
        assignment = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.hlb_id == hlb_id,
                HlbEnumeratorAssignment.enumerator_id == enumerator_id,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .first()
        )
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access or navigate routes for this HLB",
            )
        return assignment

    def generate_coverage_route(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
        current_lat: float | None = None,
        current_lon: float | None = None,
        return_to_start: bool = False,
        custom_roads_file: str | None = None,
    ) -> RoadCoverageRouteResult:
        """
        Generate a street-coverage walking route following real road geometry
        within the assigned HLB boundary.
        """
        self.verify_enumerator_authorization(db, hlb_id, enumerator_id)

        hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
        if not hlb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Houselisting Block with ID {hlb_id} not found",
            )

        if hlb.boundary is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="HLB has no valid polygon boundary geometry.",
            )

        hlb_polygon = to_shape(hlb.boundary)

        # Load road network (OSM)
        rn = get_road_network(custom_roads_file)
        if not rn:
            return RoadCoverageRouteResult(
                route_id=str(uuid.uuid4()),
                hlb_id=str(hlb_id),
                network_version="v1.0",
                acquisition_date=datetime.now(UTC).isoformat(),
                total_distance_km=0.0,
                estimated_walking_time_minutes=0.0,
                total_segments_count=0,
                surveyed_segments_count=0,
                coverage_percentage=0.0,
                sections=[],
                continuous_polyline=[],
                all_road_segments=[],
                disconnected_components_count=0,
                warnings=["MISSING_ROAD_NETWORK_DATA: No road network data file available for this area."],
            )

        # Load existing surveyed segments from DB
        existing_coverages = (
            db.query(RoadSegmentCoverage)
            .filter(
                RoadSegmentCoverage.hlb_id == hlb_id,
                RoadSegmentCoverage.survey_status == RoadSegmentSurveyStatus.SURVEYED,
            )
            .all()
        )
        surveyed_ids = {c.segment_id for c in existing_coverages}

        start_location = None
        if current_lat is not None and current_lon is not None:
            start_location = (current_lat, current_lon)

        return generate_hlb_road_coverage_route(
            hlb_id=str(hlb_id),
            hlb_polygon=hlb_polygon,
            road_network=rn,
            start_location=start_location,
            surveyed_segment_ids=surveyed_ids,
            return_to_start=return_to_start,
        )

    def match_gps_trace_to_segments(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
        gps_points: list[dict],  # [{latitude, longitude, timestamp?, accuracy?}, ...]
        device_id: str | None = None,
        tolerance_meters: float = DEFAULT_GPS_ROAD_MATCHING_TOLERANCE_M,
        custom_roads_file: str | None = None,
    ) -> dict:
        """
        Match recorded GPS trace to HLB road segments, update segment survey status
        (NOT_VISITED -> IN_PROGRESS -> SURVEYED) based on projected coverage span,
        and persist coverage state in DB.
        """
        self.verify_enumerator_authorization(db, hlb_id, enumerator_id)

        if not gps_points:
            return {"updated_segments": 0, "coverage_summary": {}}

        hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
        if not hlb or hlb.boundary is None:
            raise HTTPException(status_code=404, detail="HLB or boundary not found")

        hlb_polygon = to_shape(hlb.boundary)
        rn = get_road_network(custom_roads_file)
        if not rn:
            raise HTTPException(status_code=404, detail="MISSING_ROAD_NETWORK_DATA")

        hlb_segments = rn.query_segments_in_polygon(hlb_polygon)
        if not hlb_segments:
            return {"updated_segments": 0, "coverage_summary": {}}

        # Load or create DB records for these segments
        existing_map = {
            cov.segment_id: cov
            for cov in db.query(RoadSegmentCoverage)
            .filter(RoadSegmentCoverage.hlb_id == hlb_id)
            .all()
        }

        updated_count = 0
        now_dt = datetime.now(UTC)

        for seg in hlb_segments:
            seg_id = seg.segment_id
            cov = existing_map.get(seg_id)
            if not cov:
                cov = RoadSegmentCoverage(
                    hlb_id=hlb_id,
                    segment_id=seg_id,
                    osm_way_id=str(seg.osm_way_id) if seg.osm_way_id else None,
                    highway_type=seg.highway,
                    road_name=seg.name,
                    enumerator_id=enumerator_id,
                    device_id=device_id,
                    survey_status=RoadSegmentSurveyStatus.NOT_VISITED,
                    total_length_m=seg.length_m,
                    surveyed_length_m=0.0,
                    coverage_percentage=0.0,
                    gps_trace=[],
                    segment_geometry=[[c[0], c[1]] for c in seg.coordinates],
                    sync_status=RoadCoverageSyncStatus.SYNCED,
                )
                db.add(cov)
                existing_map[seg_id] = cov

            # Transform segment line to metric EPSG:32643
            line_proj = transform_geometry(seg.geometry, DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS)
            line_len_m = max(1.0, float(line_proj.length))
            buffered_line = line_proj.buffer(tolerance_meters)

            matched_pts_proj: list[float] = []
            matched_pts_raw: list[dict] = []

            for pt in gps_points:
                acc = pt.get("accuracy") or pt.get("accuracy_meters")
                if acc is not None and acc > STRICT_GPS_ACCURACY_THRESHOLD_M:
                    continue  # Strict accuracy threshold <= 30m required for coverage verification
                lat = pt["latitude"]
                lon = pt["longitude"]
                p_geo = Point(lon, lat)
                p_proj = transform_geometry(p_geo, DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS)
                if buffered_line.contains(p_proj):
                    proj_dist = line_proj.project(p_proj)
                    matched_pts_proj.append(proj_dist)
                    matched_pts_raw.append(pt)

            if matched_pts_proj:
                min_p = min(matched_pts_proj)
                max_p = max(matched_pts_proj)
                new_covered_m = max_p - min_p

                # Cumulative update: preserve existing covered distance if higher
                current_covered = max(cov.surveyed_length_m or 0.0, new_covered_m)
                cov.surveyed_length_m = round(min(line_len_m, current_covered), 2)
                cov.coverage_percentage = round((cov.surveyed_length_m / line_len_m) * 100.0, 1)

                # Append GPS points to trace
                existing_trace = cov.gps_trace or []
                existing_trace.extend(matched_pts_raw[:20])  # Cap trace size for storage efficiency
                cov.gps_trace = existing_trace

                if not cov.started_at:
                    cov.started_at = now_dt

                # Update status based on strict thresholds
                if cov.coverage_percentage >= SURVEY_COMPLETION_THRESHOLD_PCT:
                    cov.survey_status = RoadSegmentSurveyStatus.SURVEYED
                    if not cov.completed_at:
                        cov.completed_at = now_dt
                elif cov.coverage_percentage >= SURVEY_IN_PROGRESS_THRESHOLD_PCT:
                    if cov.survey_status == RoadSegmentSurveyStatus.NOT_VISITED:
                        cov.survey_status = RoadSegmentSurveyStatus.IN_PROGRESS

                cov.updated_at = now_dt
                updated_count += 1

        db.commit()

        # Compute summary
        all_covs = list(existing_map.values())
        total_segs = len(all_covs)
        surveyed_segs = sum(1 for c in all_covs if c.survey_status == RoadSegmentSurveyStatus.SURVEYED)
        in_prog_segs = sum(1 for c in all_covs if c.survey_status == RoadSegmentSurveyStatus.IN_PROGRESS)
        total_len = sum(c.total_length_m for c in all_covs)
        surveyed_len = sum(c.surveyed_length_m for c in all_covs)
        overall_pct = (surveyed_len / total_len * 100.0) if total_len > 0 else 0.0

        return {
            "updated_segments": updated_count,
            "coverage_summary": {
                "total_segments": total_segs,
                "surveyed_segments": surveyed_segs,
                "in_progress_segments": in_prog_segs,
                "not_visited_segments": total_segs - surveyed_segs - in_prog_segs,
                "total_length_km": round(total_len / 1000.0, 3),
                "surveyed_length_km": round(surveyed_len / 1000.0, 3),
                "coverage_percentage": round(overall_pct, 1),
            },
        }

    def detect_route_deviation(
        self,
        current_lat: float,
        current_lon: float,
        route_polyline: list[list[float]],
        threshold_meters: float = ROUTE_DEVIATION_THRESHOLD_M,
    ) -> dict:
        """
        Check if current GPS coordinate deviates from the active planned route polyline.
        Returns deviation distance and boolean warning flag.
        """
        if not route_polyline or len(route_polyline) < 2:
            return {"is_deviated": False, "deviation_distance_m": 0.0}

        p_geo = Point(current_lon, current_lat)
        p_proj = transform_geometry(p_geo, DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS)

        shapely_coords = [(pt[1], pt[0]) for pt in route_polyline]
        line_geo = LineString(shapely_coords)
        line_proj = transform_geometry(line_geo, DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS)

        dist_m = float(line_proj.distance(p_proj))
        is_deviated = dist_m > threshold_meters

        return {
            "is_deviated": is_deviated,
            "deviation_distance_m": round(dist_m, 1),
            "threshold_meters": threshold_meters,
            "message": (
                f"Off route by {round(dist_m)}m! Planned road is {round(dist_m)}m away."
                if is_deviated
                else "On track"
            ),
        }


road_coverage_service = RoadCoverageService()

