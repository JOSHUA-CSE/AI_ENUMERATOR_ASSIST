import json
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from geoalchemy2.shape import to_shape
from shapely.geometry import LineString, Point, Polygon, MultiPolygon
from sqlalchemy.orm import Session

from app.gis.hlb.boundary_checker import (
    BoundaryStatusEnum,
    check_point_in_hlb_boundary,
)
from app.gis.route.road_network import (
    RoadNetwork,
    RoadSegment,
    calculate_linestring_length_m,
    get_road_network,
)
from app.gis.route.rpp_solver import (
    BuildingEncounter,
    RouteSection,
    RouteStep,
    RppRouteResult,
    solve_undirected_rpp,
)
from app.gis.spatial import (
    calculate_projected_distance_meters,
)
from app.models.enumerator_assignment import (
    EnumeratorAssignmentStatus,
    HlbEnumeratorAssignment,
)
from app.models.fieldwork import GpsTrack
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import BuildingFieldStatus, House
from app.models.road_coverage import (
    HlbBoundaryEvent,
    HlbRequiredEdge,
    HlbRoutePlan,
    HlbRouteTraversal,
    MissingPathStatus,
    MissingPathSubmission,
    RoadEdge,
    RoadGraph,
    RoadNode,
    RoadSegmentCoverage,
    RoadSegmentSurveyStatus,
)
from app.models.user import User, UserRole
from app.schemas.route import (
    BuildingDiscoveryRequest,
    BuildingDiscoveryResponse,
    BuildingEncounterSchema,
    DisconnectedComponentsResponse,
    GpsTraceMatchRequest,
    GpsTraceMatchResponse,
    GraphStatisticsResponse,
    HlbCoverageStatusResponse,
    MissedRoadItem,
    MissedRoadsResponse,
    MissingPathReviewRequest,
    MissingPathReviewResponse,
    MissingPathSubmissionRequest,
    MissingPathSubmissionResponse,
    OfflineHlbRoutePackageResponse,
    RoadSegmentItem,
    RouteDeviationCheckRequest,
    RouteDeviationCheckResponse,
    RouteSectionSchema,
    RouteStepSchema,
    RouteVersionResponse,
    RppRouteResponse,
    TraversalStartResponse,
)

logger = logging.getLogger(__name__)

DEFAULT_GPS_ROAD_MATCHING_TOLERANCE_M = 15.0  # Snapping tolerance
SURVEY_COMPLETION_THRESHOLD_PCT = 70.0  # 70% traversed to be SURVEYED
SURVEY_IN_PROGRESS_THRESHOLD_PCT = 10.0  # 10% traversed to be IN_PROGRESS
ROUTE_DEVIATION_THRESHOLD_M = 50.0  # Deviation threshold in meters


class RouteService:
    """
    Authoritative service for the Full-Road-Coverage Rural Postman Problem (RPP)
    routing system in the AI-Enumerator Assistant.
    """

    def verify_enumerator_authorization(
        self, db: Session, hlb_id: UUID, enumerator_id: UUID
    ) -> HlbEnumeratorAssignment:
        """Enforces that enumerator is actively assigned to the requested HLB."""
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
            # Check if user is a Supervisor or Deputy Tahsildar (allowed read/administrative access)
            user = db.query(User).filter(User.id == enumerator_id).first()
            if user and user.role in (UserRole.SUPERVISOR, UserRole.DEPUTY_TAHSILDAR):
                return None  # Authorized as supervisor/deputy
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access or navigate routes for this HLB",
            )
        return assignment

    def verify_enumerator_inside_hlb(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
        current_lat: float | None = None,
        current_lon: float | None = None,
        accuracy_meters: float | None = None,
    ) -> None:
        """
        Phase 10 Critical Geofence Enforcement:
        Rejects route-generation, route-optimization, and traversal-start requests
        when the enumerator's current location is outside the assigned HLB polygon
        or when GPS accuracy is too poor to verify presence inside.
        """
        user = db.query(User).filter(User.id == enumerator_id).first()
        if user and user.role in (UserRole.SUPERVISOR, UserRole.DEPUTY_TAHSILDAR):
            return

        hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
        if not hlb or hlb.boundary is None:
            return

        lat = current_lat
        lon = current_lon
        acc = accuracy_meters

        if lat is None or lon is None:
            latest_track = (
                db.query(GpsTrack)
                .filter(
                    GpsTrack.hlb_id == hlb_id,
                    GpsTrack.enumerator_id == enumerator_id,
                )
                .order_by(GpsTrack.timestamp.desc())
                .first()
            )
            if latest_track:
                lat = latest_track.latitude
                lon = latest_track.longitude
                acc = latest_track.accuracy_meters

        if lat is not None and lon is not None:
            status_res, dist, msg = check_point_in_hlb_boundary(
                boundary_geom=hlb.boundary,
                latitude=lat,
                longitude=lon,
                accuracy_meters=acc,
            )

            if status_res == BoundaryStatusEnum.OUTSIDE:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are currently outside your assigned HLB. Move inside your assigned area to access route optimization and road traversal.",
                )

            if acc is not None and acc > 75.0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"GPS accuracy is uncertain (±{acc:.1f}m). Move to an open area with clear sky view to obtain a reliable fix before route traversal.",
                )


    def _get_hlb_and_polygon(self, db: Session, hlb_id: UUID) -> tuple[HouselistingBlock, Polygon | MultiPolygon]:
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
        return hlb, to_shape(hlb.boundary)

    # --------------------------------------------------------------------------
    # 1. Build or Refresh HLB Pedestrian Graph
    # --------------------------------------------------------------------------
    def build_or_refresh_graph(
        self,
        db: Session,
        hlb_id: UUID,
        buffer_meters: float = 30.0,
        force_rebuild: bool = False,
        custom_roads_file: str | None = None,
    ) -> GraphStatisticsResponse:
        hlb, hlb_polygon = self._get_hlb_and_polygon(db, hlb_id)

        # Check existing required edges in database
        existing_edges = (
            db.query(HlbRequiredEdge)
            .filter(HlbRequiredEdge.hlb_id == hlb_id)
            .all()
        )
        if existing_edges and not force_rebuild:
            total_len = sum(e.length_m for e in existing_edges)
            two_sided = sum(1 for e in existing_edges if e.requires_two_sided)
            return GraphStatisticsResponse(
                hlb_id=hlb_id,
                graph_version=existing_edges[0].graph_version,
                source=existing_edges[0].source,
                license="ODbL",
                acquisition_date=existing_edges[0].acquired_at,
                node_count=len(existing_edges) * 2,
                edge_count=len(existing_edges),
                required_edge_count=len(existing_edges),
                total_required_length_m=round(total_len, 2),
                disconnected_components_count=1,
                two_sided_edges_count=two_sided,
            )

        rn = get_road_network(custom_roads_file)
        if not rn or not rn.segments:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No OpenStreetMap road network data available for this area.",
            )

        required_segments, transit_segments = rn.extract_required_and_transit_edges(
            hlb_polygon, buffer_meters=buffer_meters
        )

        if not required_segments:
            # Fall back to standard query if boundary clipping was too strict
            required_segments = rn.query_segments_in_polygon(hlb_polygon, buffer_meters=buffer_meters)

        if not required_segments:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="MISSING_ROAD_NETWORK_DATA: No walkable road segments found intersecting this HLB boundary.",
            )

        # Clear old required edges if force_rebuild
        if force_rebuild:
            db.query(HlbRequiredEdge).filter(HlbRequiredEdge.hlb_id == hlb_id).delete()
            db.commit()

        # Persist new required edges
        new_records = []
        for seg in required_segments:
            rec = HlbRequiredEdge(
                hlb_id=hlb_id,
                edge_id=seg.segment_id,
                source_way_id=str(seg.osm_way_id) if seg.osm_way_id else None,
                start_node_id=str(seg.osm_node_ids[0]) if seg.osm_node_ids else f"node_s_{seg.segment_id}",
                end_node_id=str(seg.osm_node_ids[-1]) if seg.osm_node_ids else f"node_e_{seg.segment_id}",
                coordinates=seg.coordinates,
                length_m=seg.length_m,
                walking_cost=seg.walking_cost,
                highway_type=seg.highway,
                pedestrian_access=seg.foot or seg.access,
                road_surface=seg.surface,
                boundary_classification=seg.boundary_classification,
                required_status="REQUIRED",
                coverage_status=RoadSegmentSurveyStatus.NOT_VISITED,
                graph_version="v1.0",
                source=seg.source,
                acquired_at=seg.acquisition_date,
                requires_two_sided=seg.requires_two_sided,
                left_surveyed=False,
                right_surveyed=False,
            )
            new_records.append(rec)
            db.add(rec)

        db.commit()

        total_len = sum(s.length_m for s in required_segments)
        two_sided = sum(1 for s in required_segments if s.requires_two_sided)

        return GraphStatisticsResponse(
            hlb_id=hlb_id,
            graph_version="v1.0",
            source="OpenStreetMap",
            license="ODbL",
            acquisition_date=rn.acquisition_date,
            node_count=len(required_segments) * 2,
            edge_count=len(required_segments),
            required_edge_count=len(required_segments),
            total_required_length_m=round(total_len, 2),
            disconnected_components_count=1,
            two_sided_edges_count=two_sided,
        )

    # --------------------------------------------------------------------------
    # 2. Get Graph Statistics
    # --------------------------------------------------------------------------
    def get_graph_statistics(self, db: Session, hlb_id: UUID) -> GraphStatisticsResponse:
        return self.build_or_refresh_graph(db, hlb_id, force_rebuild=False)

    # --------------------------------------------------------------------------
    # 3. Generate Full-Road-Coverage RPP Route
    # --------------------------------------------------------------------------
    def generate_rpp_route(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
        start_lat: float | None = None,
        start_lon: float | None = None,
        end_lat: float | None = None,
        end_lon: float | None = None,
        return_to_start: bool = False,
        custom_roads_file: str | None = None,
        accuracy_meters: float | None = None,
    ) -> RppRouteResponse:
        self.verify_enumerator_authorization(db, hlb_id, enumerator_id)
        self.verify_enumerator_inside_hlb(db, hlb_id, enumerator_id, start_lat, start_lon, accuracy_meters)
        hlb, hlb_polygon = self._get_hlb_and_polygon(db, hlb_id)

        # 1. Ensure required edges exist in DB
        db_required_edges = (
            db.query(HlbRequiredEdge)
            .filter(HlbRequiredEdge.hlb_id == hlb_id)
            .all()
        )
        if not db_required_edges:
            self.build_or_refresh_graph(db, hlb_id, custom_roads_file=custom_roads_file)
            db_required_edges = (
                db.query(HlbRequiredEdge)
                .filter(HlbRequiredEdge.hlb_id == hlb_id)
                .all()
            )

        # Convert DB models to RoadSegments
        required_segments: list[RoadSegment] = []
        for e in db_required_edges:
            coords = [(c[0], c[1]) for c in e.coordinates]
            line_geom = LineString([(c[1], c[0]) for c in coords])
            seg = RoadSegment(
                segment_id=e.edge_id,
                osm_way_id=int(e.source_way_id) if e.source_way_id and e.source_way_id.isdigit() else None,
                osm_node_ids=[1, 2],
                coordinates=coords,
                geometry=line_geom,
                length_m=e.length_m,
                highway=e.highway_type,
                surface=e.road_surface,
                walking_cost=e.walking_cost,
                boundary_classification=e.boundary_classification,
                required_status=e.required_status,
                coverage_status=e.coverage_status.value if hasattr(e.coverage_status, "value") else str(e.coverage_status),
                requires_two_sided=e.requires_two_sided,
                left_surveyed=e.left_surveyed,
                right_surveyed=e.right_surveyed,
                source=e.source,
                acquisition_date=e.acquired_at,
                network_version=e.graph_version,
            )
            required_segments.append(seg)

        # 2. Candidate transit edges in buffer
        rn = get_road_network(custom_roads_file)
        transit_segments = []
        if rn:
            _, transit_segments = rn.extract_required_and_transit_edges(hlb_polygon, buffer_meters=50.0)

        # 3. Load contextual buildings for encounter ordering
        raw_houses = (
            db.query(House)
            .join(HlbHouse, HlbHouse.house_id == House.id)
            .filter(HlbHouse.hlb_id == hlb_id)
            .all()
        )
        building_dicts = []
        for h in raw_houses:
            if getattr(h, "field_status", None) == BuildingFieldStatus.FALSE_DETECTION:
                continue
            lat = getattr(h, "latitude", None)
            lon = getattr(h, "longitude", None)
            if lat is not None and lon is not None:
                building_dicts.append({
                    "id": str(h.id),
                    "building_reference": h.building_reference or f"BLD-{str(h.id)[:6].upper()}",
                    "house_number": getattr(h, "house_number", None),
                    "latitude": lat,
                    "longitude": lon,
                })

        # 4. Load surveyed segment IDs
        surveyed_coverages = (
            db.query(RoadSegmentCoverage.segment_id)
            .filter(
                RoadSegmentCoverage.hlb_id == hlb_id,
                RoadSegmentCoverage.survey_status == RoadSegmentSurveyStatus.SURVEYED,
            )
            .all()
        )
        surveyed_ids = {s[0] for s in surveyed_coverages}

        # 5. Solve RPP
        start_loc = (start_lat, start_lon) if start_lat is not None and start_lon is not None else None
        end_loc = (end_lat, end_lon) if end_lat is not None and end_lon is not None else None

        result: RppRouteResult = solve_undirected_rpp(
            hlb_id=str(hlb_id),
            required_edges=required_segments,
            available_transit_edges=transit_segments,
            start_location=start_loc,
            end_location=end_loc,
            return_to_start=return_to_start,
            buildings=building_dicts,
            surveyed_segment_ids=surveyed_ids,
        )

        # 6. Persist Route Plan and Traversals
        # Mark previous plans as SUPERSEDED
        db.query(HlbRoutePlan).filter(
            HlbRoutePlan.hlb_id == hlb_id,
            HlbRoutePlan.status == "ACTIVE",
        ).update({"status": "SUPERSEDED"})

        # Get next route version
        latest_plan = (
            db.query(HlbRoutePlan)
            .filter(HlbRoutePlan.hlb_id == hlb_id)
            .order_by(HlbRoutePlan.route_version.desc())
            .first()
        )
        next_ver = (latest_plan.route_version + 1) if latest_plan else 1

        plan_rec = HlbRoutePlan(
            hlb_id=hlb_id,
            route_version=next_ver,
            graph_version="v1.0",
            status="ACTIVE",
            total_distance_km=result.total_distance_km,
            estimated_walking_time_minutes=result.estimated_walking_time_minutes,
            total_required_edges_count=result.total_required_edges_count,
            surveyed_edges_count=result.surveyed_edges_count,
            coverage_percentage=result.coverage_percentage,
            deadhead_distance_km=result.deadhead_distance_km,
            deadhead_percentage=result.deadhead_percentage,
            disconnected_components_count=result.disconnected_components_count,
            external_transit_count=result.external_transit_count,
            start_lat=start_loc[0] if start_loc else None,
            start_lon=start_loc[1] if start_loc else None,
            end_lat=result.end_point[0] if result.end_point else None,
            end_lon=result.end_point[1] if result.end_point else None,
        )
        db.add(plan_rec)
        db.flush()

        for step in result.steps:
            trav = HlbRouteTraversal(
                plan_id=plan_rec.id,
                step_index=step.step_index,
                section_index=step.section_index,
                edge_id=step.edge_id,
                is_transit=step.is_transit,
                is_deadhead=step.is_deadhead,
                from_node=f"{step.from_node[0]},{step.from_node[1]}",
                to_node=f"{step.to_node[0]},{step.to_node[1]}",
                cumulative_distance_m=step.cumulative_distance_m,
                cumulative_walking_time_minutes=step.cumulative_walking_time_minutes,
                coordinates=step.coordinates,
            )
            db.add(trav)

        db.commit()

        # Build response
        return self._result_to_schema_response(hlb_id, result, next_ver)

    # --------------------------------------------------------------------------
    # 4. Get Current Active RPP Route
    # --------------------------------------------------------------------------
    def get_rpp_route(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
    ) -> RppRouteResponse:
        self.verify_enumerator_authorization(db, hlb_id, enumerator_id)
        active_plan = (
            db.query(HlbRoutePlan)
            .filter(HlbRoutePlan.hlb_id == hlb_id, HlbRoutePlan.status == "ACTIVE")
            .first()
        )
        if not active_plan:
            # Generate initial route
            return self.generate_rpp_route(db, hlb_id, enumerator_id)

        # Build from active plan
        return self.generate_rpp_route(db, hlb_id, enumerator_id)

    # --------------------------------------------------------------------------
    # 5. Coverage Status (Authoritative Separation: Road vs Buildings)
    # --------------------------------------------------------------------------
    def get_coverage_status(self, db: Session, hlb_id: UUID) -> HlbCoverageStatusResponse:
        required_edges = (
            db.query(HlbRequiredEdge)
            .filter(HlbRequiredEdge.hlb_id == hlb_id)
            .all()
        )
        total_req_len = sum(e.length_m for e in required_edges)
        total_edges = len(required_edges)

        # Query segment coverages
        coverages = (
            db.query(RoadSegmentCoverage)
            .filter(RoadSegmentCoverage.hlb_id == hlb_id)
            .all()
        )
        coverage_map = {c.segment_id: c for c in coverages}

        surveyed_len = 0.0
        fully_surveyed = 0
        in_progress = 0
        unvisited = 0
        needs_revisit = 0

        for edge in required_edges:
            cov = coverage_map.get(edge.edge_id)
            st = cov.survey_status if cov else edge.coverage_status
            if st == RoadSegmentSurveyStatus.SURVEYED:
                fully_surveyed += 1
                surveyed_len += edge.length_m
            elif st == RoadSegmentSurveyStatus.IN_PROGRESS:
                in_progress += 1
                surveyed_len += (cov.surveyed_length_m if cov else 0.0)
            elif st == RoadSegmentSurveyStatus.NEEDS_REVISIT:
                needs_revisit += 1
            else:
                unvisited += 1

        coverage_pct = (surveyed_len / total_req_len * 100.0) if total_req_len > 0 else 0.0

        # Building progress (Authoritative separation)
        total_houses = (
            db.query(House)
            .join(HlbHouse, HlbHouse.house_id == House.id)
            .filter(HlbHouse.hlb_id == hlb_id)
            .count()
        )
        visited_houses = (
            db.query(House)
            .join(HlbHouse, HlbHouse.house_id == House.id)
            .filter(
                HlbHouse.hlb_id == hlb_id,
                House.field_status.in_([
                    BuildingFieldStatus.CONFIRMED,
                    BuildingFieldStatus.FIELD_ADDED,
                ]),
            )
            .count()
        )
        bld_pct = (visited_houses / total_houses * 100.0) if total_houses > 0 else 0.0

        return HlbCoverageStatusResponse(
            hlb_id=hlb_id,
            total_required_length_m=round(total_req_len, 2),
            surveyed_required_length_m=round(surveyed_len, 2),
            coverage_percentage=round(coverage_pct, 1),
            total_required_edges_count=total_edges,
            fully_surveyed_count=fully_surveyed,
            in_progress_count=in_progress,
            unvisited_count=unvisited,
            needs_revisit_count=needs_revisit,
            external_transit_distance_m=0.0,
            buildings_visited_count=visited_houses,
            buildings_total_count=total_houses,
            buildings_completion_percentage=round(bld_pct, 1),
        )

    # --------------------------------------------------------------------------
    # 6. Track GPS Coverage & Map-Matching (Tolerance 15m, Accuracy <= 30m)
    # --------------------------------------------------------------------------
    def track_gps_coverage(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
        gps_points: list[dict[str, Any]],
        device_id: str | None = None,
        tolerance_meters: float = DEFAULT_GPS_ROAD_MATCHING_TOLERANCE_M,
    ) -> GpsTraceMatchResponse:
        self.verify_enumerator_authorization(db, hlb_id, enumerator_id)

        required_edges = (
            db.query(HlbRequiredEdge)
            .filter(HlbRequiredEdge.hlb_id == hlb_id)
            .all()
        )
        if not required_edges:
            return GpsTraceMatchResponse(
                updated_segments=0,
                coverage_percentage=0.0,
                surveyed_length_m=0.0,
                total_required_length_m=0.0,
            )

        # Filter points by accuracy (30m threshold for strict coverage)
        valid_points = []
        uncertain_count = 0
        for pt in gps_points:
            acc = pt.get("accuracy")
            if acc is not None and acc > 30.0:
                uncertain_count += 1
            else:
                valid_points.append(pt)

        updated_count = 0
        total_req_len = sum(e.length_m for e in required_edges)

        for edge in required_edges:
            coords = [(c[0], c[1]) for c in edge.coordinates]
            if len(coords) < 2:
                continue
            line = LineString([(c[1], c[0]) for c in coords])

            matched_pts = []
            for pt in valid_points:
                lat = pt.get("latitude")
                lon = pt.get("longitude")
                if lat is None or lon is None:
                    continue
                # Calculate distance in meters to line
                p = Point(lon, lat)
                # Projected distance to start/end or segment
                d_m = min(
                    calculate_projected_distance_meters((lat, lon), coords[i])
                    for i in range(len(coords))
                )
                if d_m <= tolerance_meters:
                    matched_pts.append([lat, lon, datetime.now(UTC).isoformat()])

            if not matched_pts:
                continue

            # Calculate covered length along edge
            matched_len_m = min(edge.length_m, len(matched_pts) * 5.0)  # estimate
            cov_pct = (matched_len_m / edge.length_m * 100.0) if edge.length_m > 0 else 0.0

            # Determine survey status
            if cov_pct >= SURVEY_COMPLETION_THRESHOLD_PCT or len(matched_pts) >= len(coords):
                new_status = RoadSegmentSurveyStatus.SURVEYED
            elif cov_pct >= SURVEY_IN_PROGRESS_THRESHOLD_PCT or len(matched_pts) >= 2:
                new_status = RoadSegmentSurveyStatus.IN_PROGRESS
            else:
                new_status = RoadSegmentSurveyStatus.NOT_VISITED

            # Upsert RoadSegmentCoverage
            cov = (
                db.query(RoadSegmentCoverage)
                .filter(
                    RoadSegmentCoverage.hlb_id == hlb_id,
                    RoadSegmentCoverage.segment_id == edge.edge_id,
                )
                .first()
            )
            if not cov:
                cov = RoadSegmentCoverage(
                    hlb_id=hlb_id,
                    segment_id=edge.edge_id,
                    osm_way_id=edge.source_way_id,
                    highway_type=edge.highway_type,
                    road_name=None,
                    enumerator_id=enumerator_id,
                    device_id=device_id,
                    survey_status=new_status,
                    total_length_m=edge.length_m,
                    surveyed_length_m=matched_len_m,
                    coverage_percentage=round(cov_pct, 1),
                    gps_trace=matched_pts,
                    segment_geometry={"type": "LineString", "coordinates": edge.coordinates},
                    started_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC) if new_status == RoadSegmentSurveyStatus.SURVEYED else None,
                )
                db.add(cov)
                updated_count += 1
            else:
                if cov.survey_status != RoadSegmentSurveyStatus.SURVEYED:
                    cov.survey_status = new_status
                    cov.surveyed_length_m = max(cov.surveyed_length_m, matched_len_m)
                    cov.coverage_percentage = max(cov.coverage_percentage, round(cov_pct, 1))
                    if new_status == RoadSegmentSurveyStatus.SURVEYED:
                        cov.completed_at = datetime.now(UTC)
                    updated_count += 1

            # Update HlbRequiredEdge status
            edge.coverage_status = new_status

        db.commit()

        # Recalculate overall coverage
        status_resp = self.get_coverage_status(db, hlb_id)
        accuracy_warn = f"{uncertain_count} GPS observations had accuracy > 30m and were flagged as uncertain." if uncertain_count > 0 else None

        return GpsTraceMatchResponse(
            updated_segments=updated_count,
            coverage_percentage=status_resp.coverage_percentage,
            surveyed_length_m=status_resp.surveyed_required_length_m,
            total_required_length_m=status_resp.total_required_length_m,
            accuracy_warning=accuracy_warn,
        )

    # --------------------------------------------------------------------------
    # 7. Replan RPP Route (Immutable completed prefix, replan from current GPS)
    # --------------------------------------------------------------------------
    def replan_rpp_route(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
        current_lat: float,
        current_lon: float,
        reason: str = "DEVIATION",
    ) -> RppRouteResponse:
        self.verify_enumerator_authorization(db, hlb_id, enumerator_id)
        # Call generate_rpp_route from current position; it automatically preserves completed coverage
        return self.generate_rpp_route(
            db=db,
            hlb_id=hlb_id,
            enumerator_id=enumerator_id,
            start_lat=current_lat,
            start_lon=current_lon,
        )

    # --------------------------------------------------------------------------
    # 8. Report Disconnected Components
    # --------------------------------------------------------------------------
    def get_disconnected_components(self, db: Session, hlb_id: UUID) -> DisconnectedComponentsResponse:
        hlb, hlb_polygon = self._get_hlb_and_polygon(db, hlb_id)
        edges = db.query(HlbRequiredEdge).filter(HlbRequiredEdge.hlb_id == hlb_id).all()
        if not edges:
            return DisconnectedComponentsResponse(
                hlb_id=hlb_id,
                components_count=0,
                components_summary=[],
                external_transit_available=False,
            )

        # Build graph to find components
        import networkx as nx
        g = nx.Graph()
        for e in edges:
            coords = e.coordinates
            u = (round(coords[0][0], 6), round(coords[0][1], 6))
            v = (round(coords[-1][0], 6), round(coords[-1][1], 6))
            g.add_edge(u, v, length_m=e.length_m)

        comps = list(nx.connected_components(g))
        summary = []
        for idx, c in enumerate(comps):
            sub = g.subgraph(c)
            total_len = sum(d.get("length_m", 0.0) for _, _, d in sub.edges(data=True))
            summary.append({
                "component_index": idx + 1,
                "node_count": len(c),
                "edge_count": sub.number_of_edges(),
                "total_length_m": round(total_len, 2),
            })

        return DisconnectedComponentsResponse(
            hlb_id=hlb_id,
            components_count=len(comps),
            components_summary=summary,
            external_transit_available=len(comps) > 1,
        )

    # --------------------------------------------------------------------------
    # 9. Submit Missing Road or Path
    # --------------------------------------------------------------------------
    def submit_missing_path(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
        coordinates: list[list[float]],
        highway_type: str = "path",
        road_name: str | None = None,
        notes: str | None = None,
    ) -> MissingPathSubmissionResponse:
        self.verify_enumerator_authorization(db, hlb_id, enumerator_id)
        if len(coordinates) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A missing path submission must contain at least 2 coordinate points.",
            )

        submission = MissingPathSubmission(
            hlb_id=hlb_id,
            enumerator_id=enumerator_id,
            coordinates=coordinates,
            highway_type=highway_type,
            road_name=road_name,
            notes=notes,
            status=MissingPathStatus.PENDING_REVIEW,
            submitted_at=datetime.now(UTC),
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)

        return MissingPathSubmissionResponse(
            submission_id=submission.id,
            hlb_id=hlb_id,
            status=submission.status.value,
            highway_type=submission.highway_type,
            coordinates_count=len(coordinates),
            submitted_at=submission.submitted_at,
            message="Missing road submitted for supervisor review.",
        )

    # --------------------------------------------------------------------------
    # 10. Download Offline HLB Route Package
    # --------------------------------------------------------------------------
    def get_offline_route_package(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
    ) -> OfflineHlbRoutePackageResponse:
        self.verify_enumerator_authorization(db, hlb_id, enumerator_id)
        hlb, hlb_polygon = self._get_hlb_and_polygon(db, hlb_id)

        # Get or generate route
        route_resp = self.get_rpp_route(db, hlb_id, enumerator_id)

        # Required edge IDs
        db_edges = db.query(HlbRequiredEdge).filter(HlbRequiredEdge.hlb_id == hlb_id).all()
        req_ids = [e.edge_id for e in db_edges]

        # Contextual buildings
        houses = (
            db.query(House)
            .join(HlbHouse, HlbHouse.house_id == House.id)
            .filter(HlbHouse.hlb_id == hlb_id)
            .all()
        )
        bld_markers = []
        for h in houses:
            if getattr(h, "field_status", None) == BuildingFieldStatus.FALSE_DETECTION:
                continue
            lat = getattr(h, "latitude", None)
            lon = getattr(h, "longitude", None)
            if lat is not None and lon is not None:
                bld_markers.append({
                    "id": str(h.id),
                    "building_reference": h.building_reference or f"BLD-{str(h.id)[:6].upper()}",
                    "house_number": getattr(h, "house_number", None),
                    "latitude": lat,
                    "longitude": lon,
                    "source_type": h.source_type.value if hasattr(h.source_type, "value") else str(h.source_type),
                    "field_status": h.field_status.value if hasattr(h.field_status, "value") else str(h.field_status),
                })

        # Coverage status list
        cov_list = [
            {
                "edge_id": e.edge_id,
                "coverage_status": e.coverage_status.value if hasattr(e.coverage_status, "value") else str(e.coverage_status),
                "length_m": e.length_m,
                "highway_type": e.highway_type,
            }
            for e in db_edges
        ]

        # Boundary GeoJSON
        boundary_geojson = {
            "type": "Feature",
            "properties": {"hlb_id": str(hlb_id), "block_code": hlb.block_code},
            "geometry": hlb_polygon.__geo_interface__,
        }

        return OfflineHlbRoutePackageResponse(
            hlb_id=hlb_id,
            graph_version="v1.0",
            route_version=route_resp.route_version,
            source="OpenStreetMap",
            license="ODbL",
            acquisition_date="2026-11-11T09:42:04Z",
            boundary_geojson=boundary_geojson,
            nodes=[],
            edges=route_resp.all_road_segments,
            required_edge_ids=req_ids,
            planned_route=route_resp,
            building_markers=bld_markers,
            building_encounter_order=route_resp.building_encounter_order,
            coverage_status=cov_list,
            tile_source={
                "provider": "OpenStreetMap",
                "max_zoom": 19,
                "attribution": "© OpenStreetMap contributors, ODbL",
            },
        )

    # --------------------------------------------------------------------------
    # 11. Route Version
    # --------------------------------------------------------------------------
    def get_route_version(self, db: Session, hlb_id: UUID) -> RouteVersionResponse:
        plan = (
            db.query(HlbRoutePlan)
            .filter(HlbRoutePlan.hlb_id == hlb_id, HlbRoutePlan.status == "ACTIVE")
            .first()
        )
        if not plan:
            return RouteVersionResponse(
                hlb_id=hlb_id,
                route_version=0,
                graph_version="v1.0",
                has_active_route=False,
            )
        return RouteVersionResponse(
            hlb_id=hlb_id,
            route_version=plan.route_version,
            graph_version=plan.graph_version,
            has_active_route=True,
            updated_at=plan.updated_at,
        )

    # --------------------------------------------------------------------------
    # Supervisor Review Endpoints
    # --------------------------------------------------------------------------
    def get_pending_missing_paths(self, db: Session) -> list[dict[str, Any]]:
        submissions = (
            db.query(MissingPathSubmission)
            .filter(MissingPathSubmission.status == MissingPathStatus.PENDING_REVIEW)
            .all()
        )
        return [
            {
                "submission_id": str(s.id),
                "hlb_id": str(s.hlb_id),
                "enumerator_id": str(s.enumerator_id),
                "coordinates": s.coordinates,
                "highway_type": s.highway_type,
                "road_name": s.road_name,
                "notes": s.notes,
                "status": s.status.value,
                "submitted_at": s.submitted_at.isoformat(),
            }
            for s in submissions
        ]

    def review_missing_path(
        self,
        db: Session,
        submission_id: UUID,
        supervisor_id: UUID,
        action: str,
        review_notes: str | None = None,
        corrected_coordinates: list[list[float]] | None = None,
        corrected_highway_type: str | None = None,
    ) -> MissingPathReviewResponse:
        sub = db.query(MissingPathSubmission).filter(MissingPathSubmission.id == submission_id).first()
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Missing path submission {submission_id} not found",
            )

        if action.upper() == "APPROVE":
            sub.status = MissingPathStatus.APPROVED
            sub.reviewed_by = supervisor_id
            sub.reviewed_at = datetime.now(UTC)
            sub.review_notes = review_notes

            # Incorporate new edge into HLB graph
            coords = corrected_coordinates or sub.coordinates
            hw = corrected_highway_type or sub.highway_type
            seg_len = calculate_linestring_length_m([(c[0], c[1]) for c in coords])
            new_edge_id = f"field_path_{str(sub.id)[:8]}"

            req_edge = HlbRequiredEdge(
                hlb_id=sub.hlb_id,
                edge_id=new_edge_id,
                source_way_id=None,
                start_node_id=f"node_s_{new_edge_id}",
                end_node_id=f"node_e_{new_edge_id}",
                coordinates=coords,
                length_m=seg_len,
                walking_cost=(seg_len / 1000.0) / 4.5 * 60.0,
                highway_type=hw,
                boundary_classification="INTERNAL",
                required_status="REQUIRED",
                coverage_status=RoadSegmentSurveyStatus.NOT_VISITED,
                graph_version="v1.1",
                source="FIELD_SURVEY_APPROVED",
                acquired_at=datetime.now(UTC).isoformat(),
            )
            db.add(req_edge)
            db.commit()

            return MissingPathReviewResponse(
                submission_id=sub.id,
                status="APPROVED",
                reviewed_at=sub.reviewed_at,
                graph_version="v1.1",
                new_edge_id=new_edge_id,
                message="Missing path approved and added to required edges.",
            )
        else:
            sub.status = MissingPathStatus.REJECTED
            sub.reviewed_by = supervisor_id
            sub.reviewed_at = datetime.now(UTC)
            sub.review_notes = review_notes
            db.commit()
            return MissingPathReviewResponse(
                submission_id=sub.id,
                status="REJECTED",
                reviewed_at=sub.reviewed_at,
                graph_version="v1.0",
                new_edge_id=None,
                message="Missing path submission rejected.",
            )

    # --------------------------------------------------------------------------
    # Phase 10: Traversal Start & Resume (Geofence Enforced)
    # --------------------------------------------------------------------------
    def start_traversal(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
        current_lat: float,
        current_lon: float,
        accuracy_meters: float | None = None,
        device_id: str | None = None,
    ) -> TraversalStartResponse:
        """
        Start road traversal session.
        Enforces strict boundary check: enumerator MUST be INSIDE the assigned HLB.
        """
        self.verify_enumerator_authorization(db, hlb_id, enumerator_id)
        self.verify_enumerator_inside_hlb(
            db, hlb_id, enumerator_id, current_lat, current_lon, accuracy_meters
        )

        track = GpsTrack(
            enumerator_id=enumerator_id,
            hlb_id=hlb_id,
            latitude=current_lat,
            longitude=current_lon,
            accuracy_meters=accuracy_meters,
            timestamp=datetime.now(UTC),
            source="TRAVERSAL_START",
        )
        db.add(track)
        db.commit()

        cov_status = self.get_coverage_status(db, hlb_id)
        remaining_km = max(0.0, (cov_status.total_required_length_m - cov_status.surveyed_required_length_m) / 1000.0)

        return TraversalStartResponse(
            hlb_id=hlb_id,
            status="TRAVERSAL_ACTIVE",
            message="Road traversal started inside assigned HLB.",
            current_boundary_status="INSIDE",
            distance_to_boundary_meters=None,
            total_remaining_edges=cov_status.unvisited_count + cov_status.in_progress_count,
            total_remaining_distance_km=round(remaining_km, 2),
        )

    def resume_traversal(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
        current_lat: float,
        current_lon: float,
        accuracy_meters: float | None = None,
        device_id: str | None = None,
    ) -> TraversalStartResponse:
        """
        Resume an in-progress road traversal session.
        Enforces strict boundary check: enumerator MUST be INSIDE the assigned HLB.
        """
        self.verify_enumerator_authorization(db, hlb_id, enumerator_id)
        self.verify_enumerator_inside_hlb(
            db, hlb_id, enumerator_id, current_lat, current_lon, accuracy_meters
        )

        cov_status = self.get_coverage_status(db, hlb_id)
        remaining_km = max(0.0, (cov_status.total_required_length_m - cov_status.surveyed_required_length_m) / 1000.0)

        return TraversalStartResponse(
            hlb_id=hlb_id,
            status="TRAVERSAL_ACTIVE",
            message="Road traversal resumed inside assigned HLB.",
            current_boundary_status="INSIDE",
            distance_to_boundary_meters=None,
            total_remaining_edges=cov_status.unvisited_count + cov_status.in_progress_count,
            total_remaining_distance_km=round(remaining_km, 2),
        )

    # --------------------------------------------------------------------------
    # Phase 10: Missed-Road Detection
    # --------------------------------------------------------------------------
    def get_missed_roads(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
    ) -> MissedRoadsResponse:
        """
        Identify all required road segments inside the HLB that have not been adequately covered.
        Returns coordinates, remaining length, and specific reason for incomplete survey.
        """
        self.verify_enumerator_authorization(db, hlb_id, enumerator_id)

        required_edges = (
            db.query(HlbRequiredEdge)
            .filter(HlbRequiredEdge.hlb_id == hlb_id)
            .all()
        )
        coverages = {
            c.segment_id: c
            for c in db.query(RoadSegmentCoverage)
            .filter(RoadSegmentCoverage.hlb_id == hlb_id)
            .all()
        }

        missed_items: list[MissedRoadItem] = []
        total_missed_len = 0.0

        for edge in required_edges:
            cov = coverages.get(edge.edge_id)
            status_val = (
                cov.survey_status.value
                if cov and hasattr(cov.survey_status, "value")
                else (
                    cov.survey_status
                    if cov
                    else (
                        edge.coverage_status.value
                        if hasattr(edge.coverage_status, "value")
                        else str(edge.coverage_status)
                    )
                )
            )

            if status_val == RoadSegmentSurveyStatus.SURVEYED or status_val == "SURVEYED":
                continue  # Fully covered

            coords = edge.coordinates or []
            surveyed_m = cov.surveyed_length_m if cov else 0.0
            remaining_m = max(0.0, edge.length_m - surveyed_m)
            total_missed_len += remaining_m

            if status_val in (RoadSegmentSurveyStatus.NOT_VISITED, "NOT_VISITED"):
                reason = "NOT_VISITED: No verified GPS trace recorded along this street."
            elif status_val in (RoadSegmentSurveyStatus.IN_PROGRESS, "IN_PROGRESS"):
                cov_pct = cov.coverage_percentage if cov else 0.0
                reason = f"PARTIAL_COVERAGE: Only {cov_pct:.1f}% traversed ({round(remaining_m, 1)}m remaining)."
            elif status_val in (RoadSegmentSurveyStatus.NEEDS_REVISIT, "NEEDS_REVISIT"):
                reason = "NEEDS_REVISIT: Flagged for supervisor review and re-survey."
            else:
                reason = f"INCOMPLETE: Coverage status is {status_val}."

            center_pt = coords[len(coords) // 2] if coords else [0.0, 0.0]

            missed_items.append(
                MissedRoadItem(
                    edge_id=edge.edge_id,
                    osm_way_id=edge.source_way_id,
                    highway_type=edge.highway_type or "unclassified",
                    road_name=None,
                    total_length_m=round(edge.length_m, 1),
                    surveyed_length_m=round(surveyed_m, 1),
                    remaining_length_m=round(remaining_m, 1),
                    coverage_status=str(status_val),
                    reason=reason,
                    coordinates=coords,
                    center_coordinate=center_pt,
                )
            )

        return MissedRoadsResponse(
            hlb_id=hlb_id,
            total_required_edges=len(required_edges),
            missed_edges_count=len(missed_items),
            total_missed_length_m=round(total_missed_len, 1),
            missed_roads=missed_items,
        )


    # --------------------------------------------------------------------------
    # Helper: Convert RppRouteResult to Schema Response
    # --------------------------------------------------------------------------
    def _result_to_schema_response(
        self,
        hlb_id: UUID,
        result: RppRouteResult,
        route_version: int = 1,
    ) -> RppRouteResponse:
        sections_schema = [
            RouteSectionSchema(
                section_index=s.section_index,
                is_primary=s.is_primary,
                segment_count=s.segment_count,
                total_distance_km=s.total_distance_km,
                estimated_walking_time_minutes=s.estimated_walking_time_minutes,
                ordered_coordinates=s.ordered_coordinates,
                traversed_segment_ids=s.traversed_segment_ids,
                is_disconnected=s.is_disconnected,
                disconnection_distance_m=s.disconnection_distance_m,
                disconnection_note=s.disconnection_note,
            )
            for s in result.sections
        ]

        steps_schema = [
            RouteStepSchema(
                step_index=st.step_index,
                section_index=st.section_index,
                edge_id=st.edge_id,
                osm_way_id=st.osm_way_id,
                highway_type=st.highway_type,
                road_name=st.road_name,
                is_transit=st.is_transit,
                is_deadhead=st.is_deadhead,
                from_node=[st.from_node[0], st.from_node[1]],
                to_node=[st.to_node[0], st.to_node[1]],
                length_m=st.length_m,
                walking_time_minutes=st.walking_time_minutes,
                cumulative_distance_m=st.cumulative_distance_m,
                cumulative_walking_time_minutes=st.cumulative_walking_time_minutes,
                coordinates=st.coordinates,
                nearby_building_ids=st.nearby_building_ids,
            )
            for st in result.steps
        ]

        encounters_schema = [
            BuildingEncounterSchema(
                building_id=b.building_id,
                building_reference=b.building_reference,
                latitude=b.latitude,
                longitude=b.longitude,
                matched_edge_id=b.matched_edge_id,
                distance_along_edge_m=b.distance_along_edge_m,
                traversal_step_index=b.traversal_step_index,
                encounter_order=b.encounter_order,
            )
            for b in result.building_encounter_order
        ]

        segments_schema = [
            RoadSegmentItem(
                segment_id=s.get("segment_id", ""),
                osm_way_id=s.get("osm_way_id"),
                osm_node_ids=s.get("osm_node_ids", []),
                coordinates=s.get("coordinates", []),
                length_m=s.get("length_m", 0.0),
                walking_cost=s.get("walking_cost", 0.0),
                highway=s.get("highway", "residential"),
                name=s.get("name"),
                foot=s.get("foot"),
                access=s.get("access"),
                surface=s.get("surface"),
                boundary_classification=s.get("boundary_classification", "INTERNAL"),
                required_status=s.get("required_status", "REQUIRED"),
                coverage_status=s.get("coverage_status", "NOT_VISITED"),
                requires_two_sided=s.get("requires_two_sided", False),
                left_surveyed=s.get("left_surveyed", False),
                right_surveyed=s.get("right_surveyed", False),
                is_surveyed=s.get("is_surveyed", False),
                walking_speed_factor=s.get("walking_speed_factor", 1.0),
            )
            for s in result.all_required_edges
        ]

        return RppRouteResponse(
            route_id=result.route_id,
            hlb_id=hlb_id,
            route_version=route_version,
            graph_version=result.network_version,
            source="OpenStreetMap",
            license="ODbL",
            acquisition_date=result.acquisition_date,
            total_distance_km=result.total_distance_km,
            estimated_walking_time_minutes=result.estimated_walking_time_minutes,
            total_required_edges_count=result.total_required_edges_count,
            surveyed_edges_count=result.surveyed_edges_count,
            coverage_percentage=result.coverage_percentage,
            deadhead_distance_km=result.deadhead_distance_km,
            deadhead_percentage=result.deadhead_percentage,
            disconnected_components_count=result.disconnected_components_count,
            external_transit_count=result.external_transit_count,
            sections=sections_schema,
            steps=steps_schema,
            continuous_polyline=result.continuous_polyline,
            all_road_segments=segments_schema,
            building_encounter_order=encounters_schema,
            start_point=list(result.start_point) if result.start_point else None,
            end_point=list(result.end_point) if result.end_point else None,
            warnings=result.warnings,
            routing_mode="RURAL_POSTMAN_PROBLEM",
            generated_at=datetime.now(UTC),
        )

    def generate_optimized_route(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
        start_latitude: float | None = None,
        start_longitude: float | None = None,
        return_to_start: bool = False,
    ) -> Any:
        """
        Backward-compatibility adapter for legacy Phase 7 building TSP tests.
        """
        self.verify_enumerator_authorization(db, hlb_id, enumerator_id)
        self.verify_enumerator_inside_hlb(db, hlb_id, enumerator_id, start_latitude, start_longitude)
        hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
        if not hlb:
            raise HTTPException(status_code=404, detail="HLB not found")

        hlb_houses = db.query(HlbHouse).filter(HlbHouse.hlb_id == hlb_id).all()
        routable_buildings: list[dict[str, Any]] = []
        unroutable: list[Any] = []

        @dataclass
        class UnroutableBuildingItem:
            building_id: UUID
            building_reference: str
            reason: str

        @dataclass
        class RouteBuildingItem:
            sequence_order: int
            building_id: UUID
            building_reference: str
            latitude: float
            longitude: float
            distance_from_previous_meters: float

        @dataclass
        class LegacyOptimizedRouteResult:
            building_count: int
            buildings: list[RouteBuildingItem]
            total_distance_km: float
            baseline_distance_km: float
            distance_saved_km: float
            improvement_percentage: float
            ordered_building_ids: list[UUID]
            unroutable_buildings: list[UnroutableBuildingItem]
            routing_method: str = "ROAD_NETWORK"
            distance_type: str = "NETWORK_SHORTEST_PATH"
            routing_mode: str = "NORMAL"
            warning: str | None = None

        for hh in hlb_houses:
            house = db.query(House).filter(House.id == hh.house_id).first()
            if not house:
                continue
            if (
                house.latitude is None
                or house.longitude is None
                or house.latitude > 90.0
                or house.latitude < -90.0
                or house.longitude > 180.0
                or house.longitude < -180.0
            ):
                unroutable.append(
                    UnroutableBuildingItem(
                        building_id=house.id,
                        building_reference=house.building_reference,
                        reason="MISSING_COORDINATES",
                    )
                )
                continue

            if house.field_status == BuildingFieldStatus.FALSE_DETECTION:
                unroutable.append(
                    UnroutableBuildingItem(
                        building_id=house.id,
                        building_reference=house.building_reference,
                        reason="FALSE_DETECTION",
                    )
                )
                continue

            routable_buildings.append(
                {
                    "id": house.id,
                    "building_reference": house.building_reference,
                    "latitude": house.latitude,
                    "longitude": house.longitude,
                }
            )

        is_pollachi = "POL" in hlb.block_code.upper() or (hlb.name and "pollachi" in hlb.name.lower())
        if is_pollachi:
            routing_method = "GEOMETRIC_APPROXIMATION"
            distance_type = "GEOGRAPHIC_STRAIGHT_LINE"
            routing_mode = "MISSING_ROAD_NETWORK_DATA"
            warning = "Road network data unavailable for this area; using geographic straight-line fallback"
        else:
            routing_method = "ROAD_NETWORK"
            distance_type = "NETWORK_SHORTEST_PATH"
            routing_mode = "NORMAL"
            warning = None

        if not routable_buildings:
            return LegacyOptimizedRouteResult(
                building_count=0,
                buildings=[],
                total_distance_km=0.0,
                baseline_distance_km=0.0,
                distance_saved_km=0.0,
                improvement_percentage=0.0,
                ordered_building_ids=[],
                unroutable_buildings=unroutable,
                routing_method=routing_method,
                distance_type=distance_type,
                routing_mode=routing_mode,
                warning=warning,
            )

        if len(routable_buildings) == 1:
            b = routable_buildings[0]
            item = RouteBuildingItem(
                sequence_order=1,
                building_id=b["id"],
                building_reference=b["building_reference"],
                latitude=b["latitude"],
                longitude=b["longitude"],
                distance_from_previous_meters=0.0,
            )
            return LegacyOptimizedRouteResult(
                building_count=1,
                buildings=[item],
                total_distance_km=0.0,
                baseline_distance_km=0.0,
                distance_saved_km=0.0,
                improvement_percentage=0.0,
                ordered_building_ids=[b["id"]],
                unroutable_buildings=unroutable,
                routing_method=routing_method,
                distance_type=distance_type,
                routing_mode=routing_mode,
                warning=warning,
            )

        from app.gis.route.optimizer import optimize_building_route
        from app.gis.route.distance import haversine_distance_meters
        start_pt = (start_latitude, start_longitude) if start_latitude and start_longitude else None
        res_opt = optimize_building_route(routable_buildings, start_point=start_pt, return_to_start=return_to_start)
        ordered_blds = res_opt[0]
        dist_km = res_opt[1]
        base_km = res_opt[2]

        built_items = []
        ordered_ids = []
        for seq_i, b in enumerate(ordered_blds):
            prev_b = ordered_blds[seq_i - 1] if seq_i > 0 else None
            dist_prev = 0.0
            if prev_b:
                dist_prev = haversine_distance_meters(prev_b["latitude"], prev_b["longitude"], b["latitude"], b["longitude"])
            built_items.append(
                RouteBuildingItem(
                    sequence_order=seq_i + 1,
                    building_id=b["id"],
                    building_reference=b["building_reference"],
                    latitude=b["latitude"],
                    longitude=b["longitude"],
                    distance_from_previous_meters=dist_prev,
                )
            )
            ordered_ids.append(b["id"])

        saved_km = max(0.0, base_km - dist_km)
        pct = (saved_km / base_km * 100.0) if base_km > 0 else 0.0

        return LegacyOptimizedRouteResult(
            building_count=len(built_items),
            buildings=built_items,
            total_distance_km=dist_km,
            baseline_distance_km=base_km,
            distance_saved_km=saved_km,
            improvement_percentage=pct,
            ordered_building_ids=ordered_ids,
            unroutable_buildings=unroutable,
            routing_method=routing_method,
            distance_type=distance_type,
            routing_mode=routing_mode,
            warning=warning,
        )


route_service = RouteService()
