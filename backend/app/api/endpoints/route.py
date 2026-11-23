from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.user import User, UserRole
from app.schemas.route import (
    BuildingDiscoveryRequest,
    BuildingDiscoveryResponse,
    DisconnectedComponentsResponse,
    GpsTraceMatchRequest,
    GpsTraceMatchResponse,
    GraphBuildRequest,
    GraphStatisticsResponse,
    HlbCoverageStatusResponse,
    MissedRoadsResponse,
    MissingPathReviewRequest,
    MissingPathReviewResponse,
    MissingPathSubmissionRequest,
    MissingPathSubmissionResponse,
    OfflineHlbRoutePackageResponse,
    RouteDeviationCheckRequest,
    RouteDeviationCheckResponse,
    RouteStartingPointRequest,
    RouteVersionResponse,
    RppRouteGenerateRequest,
    RppRouteReplanRequest,
    RppRouteResponse,
    TraversalStartRequest,
    TraversalStartResponse,
)
from app.services.building_discovery_service import building_discovery_service
from app.services.road_coverage_service import road_coverage_service
from app.services.route_service import route_service

router = APIRouter()


# ------------------------------------------------------------------------------
# 1. Build or Refresh HLB Pedestrian Graph
# ------------------------------------------------------------------------------
@router.post(
    "/hlbs/{hlb_id}/graph/build",
    response_model=GraphStatisticsResponse,
    summary="Build or refresh the walkable pedestrian road graph for an HLB",
)
def build_or_refresh_hlb_graph(
    hlb_id: UUID,
    payload: GraphBuildRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    buffer_m = payload.buffer_meters if payload else 30.0
    force = payload.force_rebuild if payload else False
    return route_service.build_or_refresh_graph(
        db=db,
        hlb_id=hlb_id,
        buffer_meters=buffer_m,
        force_rebuild=force,
    )


# ------------------------------------------------------------------------------
# 2. Inspect Graph Statistics and Provenance
# ------------------------------------------------------------------------------
@router.get(
    "/hlbs/{hlb_id}/graph",
    response_model=GraphStatisticsResponse,
    summary="Inspect graph statistics, edge counts, and OSM provenance",
)
def get_hlb_graph_statistics(
    hlb_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    return route_service.get_graph_statistics(db=db, hlb_id=hlb_id)


# ------------------------------------------------------------------------------
# 3. Generate Full-Road-Coverage RPP Route
# ------------------------------------------------------------------------------
@router.post(
    "/hlbs/{hlb_id}/route/rpp/generate",
    response_model=RppRouteResponse,
    summary="Generate Full-Road-Coverage Rural Postman Problem (RPP) route",
)
def generate_rpp_route_endpoint(
    hlb_id: UUID,
    payload: RppRouteGenerateRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    start_lat = (
        payload.current_latitude
        if payload and payload.current_latitude is not None
        else (payload.start_latitude if payload else None)
    )
    start_lon = (
        payload.current_longitude
        if payload and payload.current_longitude is not None
        else (payload.start_longitude if payload else None)
    )
    accuracy_meters = payload.accuracy_meters if payload else None
    end_lat = payload.end_latitude if payload else None
    end_lon = payload.end_longitude if payload else None
    ret = payload.return_to_start if payload else False

    res = route_service.generate_rpp_route(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=end_lat,
        end_lon=end_lon,
        return_to_start=ret,
        accuracy_meters=accuracy_meters,
    )
    if res.total_required_edges_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "MISSING_ROAD_NETWORK_DATA",
                "detail": "Walkable street network data is unavailable for this area.",
            },
        )
    return res


# ------------------------------------------------------------------------------
# 4. Retrieve Current Active RPP Route
# ------------------------------------------------------------------------------
@router.get(
    "/hlbs/{hlb_id}/route/rpp",
    response_model=RppRouteResponse,
    summary="Retrieve current active RPP route and ordered edge traversal",
)
def get_rpp_route_endpoint(
    hlb_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    res = route_service.get_rpp_route(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
    )
    if res.total_required_edges_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "MISSING_ROAD_NETWORK_DATA",
                "detail": "Walkable street network data is unavailable for this area.",
            },
        )
    return res


# ------------------------------------------------------------------------------
# 5. Retrieve Required-Edge Coverage Status (Authoritative Progress Separation)
# ------------------------------------------------------------------------------
@router.get(
    "/hlbs/{hlb_id}/route/coverage/status",
    response_model=HlbCoverageStatusResponse,
    summary="Retrieve required-edge coverage status and progress",
)
def get_coverage_status_endpoint(
    hlb_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    return route_service.get_coverage_status(db=db, hlb_id=hlb_id)


# ------------------------------------------------------------------------------
# 6. Update Edge Coverage via GPS Traces
# ------------------------------------------------------------------------------
@router.post(
    "/hlbs/{hlb_id}/route/coverage/track",
    response_model=GpsTraceMatchResponse,
    summary="Match recorded GPS points to required edges and update coverage status",
)
def track_gps_coverage_endpoint(
    hlb_id: UUID,
    payload: GpsTraceMatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    pts = [p.model_dump() for p in payload.gps_points]
    return route_service.track_gps_coverage(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
        gps_points=pts,
        device_id=payload.device_id,
        tolerance_meters=payload.tolerance_meters,
    )


# ------------------------------------------------------------------------------
# 7. Recalculate / Replan Remaining Route from Current GPS Position
# ------------------------------------------------------------------------------
@router.post(
    "/hlbs/{hlb_id}/route/rpp/replan",
    response_model=RppRouteResponse,
    summary="Replan remaining route from current GPS position",
)
def replan_rpp_route_endpoint(
    hlb_id: UUID,
    payload: RppRouteReplanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    return route_service.replan_rpp_route(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
        current_lat=payload.current_latitude,
        current_lon=payload.current_longitude,
        reason=payload.reason,
    )


# ------------------------------------------------------------------------------
# 8. Report Disconnected Components
# ------------------------------------------------------------------------------
@router.get(
    "/hlbs/{hlb_id}/graph/disconnected",
    response_model=DisconnectedComponentsResponse,
    summary="Report disconnected road network components in an HLB",
)
def get_disconnected_components_endpoint(
    hlb_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    return route_service.get_disconnected_components(db=db, hlb_id=hlb_id)


# ------------------------------------------------------------------------------
# 9. Submit Missing Road or Path Geometry
# ------------------------------------------------------------------------------
@router.post(
    "/hlbs/{hlb_id}/missing-roads",
    response_model=MissingPathSubmissionResponse,
    summary="Submit newly discovered road/pathway geometry for supervisor review",
)
def submit_missing_path_endpoint(
    hlb_id: UUID,
    payload: MissingPathSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    return route_service.submit_missing_path(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
        coordinates=payload.coordinates,
        highway_type=payload.highway_type,
        road_name=payload.road_name,
        notes=payload.notes,
    )


# Supervisor: View pending missing paths
@router.get(
    "/missing-roads/pending",
    summary="List pending missing road submissions for supervisor review",
)
def get_pending_missing_paths_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    return route_service.get_pending_missing_paths(db=db)


# Supervisor: Review (Approve/Reject) missing path
@router.post(
    "/missing-roads/{submission_id}/review",
    response_model=MissingPathReviewResponse,
    summary="Review (Approve or Reject) a missing road submission",
)
def review_missing_path_endpoint(
    submission_id: UUID,
    payload: MissingPathReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPERVISOR)),
):
    return route_service.review_missing_path(
        db=db,
        submission_id=submission_id,
        supervisor_id=current_user.id,
        action=payload.action,
        review_notes=payload.review_notes,
        corrected_coordinates=payload.corrected_coordinates,
        corrected_highway_type=payload.corrected_highway_type,
    )


# ------------------------------------------------------------------------------
# 10. Download Offline HLB Route Package
# ------------------------------------------------------------------------------
@router.get(
    "/hlbs/{hlb_id}/route/offline-package",
    response_model=OfflineHlbRoutePackageResponse,
    summary="Download complete offline HLB road network and route navigation package",
)
def get_offline_route_package_endpoint(
    hlb_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    return route_service.get_offline_route_package(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
    )


# ------------------------------------------------------------------------------
# 11. Retrieve Route Version and Graph Version
# ------------------------------------------------------------------------------
@router.get(
    "/hlbs/{hlb_id}/route/version",
    response_model=RouteVersionResponse,
    summary="Retrieve current route and graph versions for an HLB",
)
def get_route_version_endpoint(
    hlb_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    return route_service.get_route_version(db=db, hlb_id=hlb_id)


# ------------------------------------------------------------------------------
# Field Building Discovery & Route Deviation Endpoints
# ------------------------------------------------------------------------------
@router.post(
    "/hlbs/{hlb_id}/buildings/discover",
    response_model=BuildingDiscoveryResponse,
    summary="Record newly discovered building found during road traversal",
)
def discover_building_endpoint(
    hlb_id: UUID,
    payload: BuildingDiscoveryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    return building_discovery_service.discover_building(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        building_reference=payload.building_reference,
        house_number=payload.house_number,
        notes=payload.notes,
        placement_mode=payload.placement_mode,
    )


@router.post(
    "/hlbs/{hlb_id}/route/deviation",
    response_model=RouteDeviationCheckResponse,
    summary="Check current GPS coordinate against active planned route polyline",
)
def check_route_deviation_endpoint(
    hlb_id: UUID,
    payload: RouteDeviationCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    route_service.verify_enumerator_authorization(db, hlb_id, current_user.id)
    return road_coverage_service.detect_route_deviation(
        current_lat=payload.current_latitude,
        current_lon=payload.current_longitude,
        route_polyline=payload.route_polyline,
        threshold_meters=payload.threshold_meters,
    )


# ------------------------------------------------------------------------------
# Backward Compatibility: /hlbs/{hlb_id}/route/coverage forwards to RPP
# ------------------------------------------------------------------------------
@router.post(
    "/hlbs/{hlb_id}/route/coverage",
    response_model=RppRouteResponse,
    summary="Generate road-network coverage walking route (forwards to RPP)",
)
def generate_hlb_road_coverage_route_endpoint(
    hlb_id: UUID,
    payload: RppRouteGenerateRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    start_lat = (
        payload.current_latitude
        if payload and payload.current_latitude is not None
        else (payload.start_latitude if payload else None)
    )
    start_lon = (
        payload.current_longitude
        if payload and payload.current_longitude is not None
        else (payload.start_longitude if payload else None)
    )
    accuracy_meters = payload.accuracy_meters if payload else None
    end_lat = payload.end_latitude if payload else None
    end_lon = payload.end_longitude if payload else None
    ret = payload.return_to_start if payload else False

    res = route_service.generate_rpp_route(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=end_lat,
        end_lon=end_lon,
        return_to_start=ret,
        accuracy_meters=accuracy_meters,
    )
    if res.total_required_edges_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "MISSING_ROAD_NETWORK_DATA",
                "detail": "Walkable street network data is unavailable for this area.",
            },
        )
    return res


@router.get(
    "/hlbs/{hlb_id}/route/coverage",
    response_model=RppRouteResponse,
    summary="Retrieve current road-network coverage route (forwards to RPP)",
)
def get_hlb_road_coverage_route_endpoint(
    hlb_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    res = route_service.get_rpp_route(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
    )
    if res.total_required_edges_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "MISSING_ROAD_NETWORK_DATA",
                "detail": "Walkable street network data is unavailable for this area.",
            },
        )
    return res


# ------------------------------------------------------------------------------
# Legacy / Backward-Compatible Endpoints
# ------------------------------------------------------------------------------
@router.post(
    "/hlbs/{hlb_id}/route/optimize",
    summary="Legacy building route optimization endpoint (backward-compatible adapter)",
)
def optimize_hlb_route_legacy(
    hlb_id: UUID,
    payload: RouteStartingPointRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    start_lat = payload.latitude if payload else None
    start_lon = payload.longitude if payload else None
    res = route_service.generate_optimized_route(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
        start_latitude=start_lat,
        start_longitude=start_lon,
    )
    strat = "CURRENT_GPS" if (start_lat is not None and start_lon is not None) else "DEFAULT_ORIGIN"
    return {
        "hlb_id": str(hlb_id),
        "building_count": res.building_count,
        "buildings": [
            {
                "sequence_order": b.sequence_order,
                "building_id": str(b.building_id),
                "building_reference": b.building_reference,
                "latitude": b.latitude,
                "longitude": b.longitude,
                "distance_from_previous_meters": b.distance_from_previous_meters,
            }
            for b in res.buildings
        ],
        "total_distance_km": res.total_distance_km,
        "baseline_distance_km": res.baseline_distance_km,
        "distance_saved_km": res.distance_saved_km,
        "improvement_percentage": res.improvement_percentage,
        "starting_point": {
            "strategy": strat,
            "latitude": start_lat,
            "longitude": start_lon,
        },
        "unroutable_buildings": [
            {
                "building_id": str(ub.building_id),
                "building_reference": ub.building_reference,
                "reason": ub.reason,
            }
            for ub in res.unroutable_buildings
        ],
        "routing_method": res.routing_method,
        "distance_type": res.distance_type,
        "routing_mode": res.routing_mode,
        "warning": res.warning,
    }


@router.get(
    "/hlbs/{hlb_id}/route",
    summary="Legacy get active building route endpoint (backward-compatible adapter)",
)
def get_hlb_route_legacy(
    hlb_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    res = route_service.generate_optimized_route(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
    )
    return {
        "hlb_id": str(hlb_id),
        "building_count": res.building_count,
        "buildings": [
            {
                "sequence_order": b.sequence_order,
                "building_id": str(b.building_id),
                "building_reference": b.building_reference,
                "latitude": b.latitude,
                "longitude": b.longitude,
                "distance_from_previous_meters": b.distance_from_previous_meters,
            }
            for b in res.buildings
        ],
        "total_distance_km": res.total_distance_km,
        "baseline_distance_km": res.baseline_distance_km,
        "distance_saved_km": res.distance_saved_km,
        "improvement_percentage": res.improvement_percentage,
        "starting_point": {
            "strategy": "HLB_CENTROID",
            "latitude": None,
            "longitude": None,
        },
        "unroutable_buildings": [
            {
                "building_id": str(ub.building_id),
                "building_reference": ub.building_reference,
                "reason": ub.reason,
            }
            for ub in res.unroutable_buildings
        ],
        "routing_method": res.routing_method,
        "distance_type": res.distance_type,
        "routing_mode": res.routing_mode,
        "warning": res.warning,
    }


# ------------------------------------------------------------------------------
# Phase 10: Missed-Road & Geofenced Traversal Endpoints
# ------------------------------------------------------------------------------
@router.get(
    "/hlbs/{hlb_id}/route/missed-roads",
    response_model=MissedRoadsResponse,
    summary="List all unvisited or incompletely surveyed road segments inside the HLB",
)
def get_missed_roads_endpoint(
    hlb_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    """
    Retrieve missed road segments inside the assigned HLB with geometry,
    remaining lengths, and explanation of incomplete coverage.
    """
    return route_service.get_missed_roads(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
    )


@router.post(
    "/hlbs/{hlb_id}/route/traversal/start",
    response_model=TraversalStartResponse,
    summary="Start road traversal session (geofence verified)",
)
def start_traversal_endpoint(
    hlb_id: UUID,
    payload: TraversalStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    """
    Start field road traversal. Enforces strict HLB geofence:
    Rejects with 403 Forbidden if the enumerator is currently outside the assigned HLB.
    """
    return route_service.start_traversal(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
        current_lat=payload.current_latitude,
        current_lon=payload.current_longitude,
        accuracy_meters=payload.accuracy_meters,
        device_id=payload.device_id,
    )


@router.post(
    "/hlbs/{hlb_id}/route/traversal/resume",
    response_model=TraversalStartResponse,
    summary="Resume road traversal session (geofence verified)",
)
def resume_traversal_endpoint(
    hlb_id: UUID,
    payload: TraversalStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
):
    """
    Resume field road traversal. Enforces strict HLB geofence:
    Rejects with 403 Forbidden if the enumerator is currently outside the assigned HLB.
    """
    return route_service.resume_traversal(
        db=db,
        hlb_id=hlb_id,
        enumerator_id=current_user.id,
        current_lat=payload.current_latitude,
        current_lon=payload.current_longitude,
        accuracy_meters=payload.accuracy_meters,
        device_id=payload.device_id,
    )

