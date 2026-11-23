from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.user import User, UserRole
from app.schemas.gps import (
    GpsBoundaryCheckRequest,
    GpsBoundaryCheckResponse,
    GpsBoundaryEventRequest,
    GpsBoundaryEventResponse,
    GpsHlbStatusResponse,
    GpsObservationCreate,
    GpsObservationResponse,
)
from app.services.gps_service import gps_service

router = APIRouter()


@router.get(
    "/hlbs/{hlb_id}/gps/status",
    response_model=GpsHlbStatusResponse,
    summary="Retrieve GPS tracking and boundary status for assigned HLB",
)
def get_hlb_gps_status(
    hlb_id: UUID,
    latitude: float | None = Query(default=None, ge=-90.0, le=90.0),
    longitude: float | None = Query(default=None, ge=-180.0, le=180.0),
    accuracy: float | None = Query(default=None, ge=0.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
) -> GpsHlbStatusResponse:
    """
    Retrieve real-time GPS monitoring status for an assigned HLB.
    - If coordinates are provided, evaluates whether the point is INSIDE, OUTSIDE,
      or BOUNDARY_UNCERTAIN relative to the approved HLB boundary.
    - Authorized exclusively for the assigned ENUMERATOR.
    """
    return gps_service.get_hlb_gps_status(
        db=db,
        hlb_id=hlb_id,
        current_user=current_user,
        latitude=latitude,
        longitude=longitude,
        accuracy_meters=accuracy,
    )


@router.post(
    "/hlbs/{hlb_id}/gps/observation",
    response_model=GpsObservationResponse,
    summary="Record a GPS fieldwork observation",
)
def record_gps_observation(
    hlb_id: UUID,
    payload: GpsObservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
) -> GpsObservationResponse:
    """
    Persist an authentic GPS location observation from the field.
    - Validates assigned HLB ownership.
    - Validates building association if provided.
    - Enforces coordinate range and accuracy sanity checks.
    """
    return gps_service.create_gps_observation(
        db=db,
        hlb_id=hlb_id,
        current_user=current_user,
        payload=payload,
    )


@router.post(
    "/hlbs/{hlb_id}/gps/check-boundary",
    response_model=GpsBoundaryCheckResponse,
    summary="Evaluate GPS coordinate against assigned HLB boundary",
)
def check_hlb_boundary(
    hlb_id: UUID,
    payload: GpsBoundaryCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
) -> GpsBoundaryCheckResponse:
    """
    Check if a coordinate is inside, outside, or uncertain relative to HLB boundary.
    """
    return gps_service.check_hlb_boundary(
        db=db,
        hlb_id=hlb_id,
        current_user=current_user,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters,
    )


@router.post(
    "/hlbs/{hlb_id}/gps/boundary-event",
    response_model=GpsBoundaryEventResponse,
    summary="Record enumerator boundary transition event (EXIT, ENTRY, ACCURACY_WARNING)",
)
def record_boundary_event(
    hlb_id: UUID,
    payload: GpsBoundaryEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
) -> GpsBoundaryEventResponse:
    """
    Record an authentic boundary event when an enumerator crosses the HLB boundary.
    Automatically checks server-side polygon and alerts supervisor if assigned.
    """
    return gps_service.record_boundary_event(
        db=db,
        hlb_id=hlb_id,
        current_user=current_user,
        payload=payload,
    )


@router.get(
    "/hlbs/{hlb_id}/gps/boundary-events",
    response_model=list[GpsBoundaryEventResponse],
    summary="List boundary events history for an HLB",
)
def get_boundary_events(
    hlb_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ENUMERATOR)),
) -> list[GpsBoundaryEventResponse]:
    """
    Retrieve historical boundary events for the assigned HLB.
    """
    # Verify access
    gps_service.verify_enumerator_hlb_access(db, hlb_id, current_user)
    return gps_service.get_boundary_events(db=db, hlb_id=hlb_id, limit=limit)

