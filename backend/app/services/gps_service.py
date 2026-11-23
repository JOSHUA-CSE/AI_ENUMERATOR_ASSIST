from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.gis.hlb.boundary_checker import (
    BoundaryStatusEnum,
    check_point_in_hlb_boundary,
)
from app.models.enumerator_assignment import (
    EnumeratorAssignmentStatus,
    HlbEnumeratorAssignment,
)
from app.models.fieldwork import GpsTrack
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.road_coverage import (
    HlbBoundaryEvent,
    RoadSegmentCoverage,
    RoadSegmentSurveyStatus,
)
from app.models.supervisor_assignment import (
    LayoutSupervisorAssignment,
    SupervisorAssignmentStatus,
)
from app.models.user import User, UserRole
from app.schemas.gps import (
    EnumeratorLiveLocationItem,
    GpsBoundaryCheckResponse,
    GpsBoundaryEventRequest,
    GpsBoundaryEventResponse,
    GpsHlbStatusResponse,
    GpsObservationCreate,
    GpsObservationResponse,
    SupervisorEnumeratorMonitoringResponse,
)


class GpsService:
    def verify_enumerator_hlb_access(
        self,
        db: Session,
        hlb_id: UUID,
        current_user: User,
    ) -> HouselistingBlock:
        """
        Verify that:
        1. User has the ENUMERATOR role.
        2. HLB exists.
        3. Enumerator is actively assigned to this HLB.
        Raises 403 Forbidden on authorization failure.
        """
        if current_user.role != UserRole.ENUMERATOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Only authenticated Enumerators are authorized to access "
                    "HLB GPS services."
                ),
            )

        hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
        if not hlb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Houselisting Block '{hlb_id}' not found.",
            )

        assignment = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.hlb_id == hlb_id,
                HlbEnumeratorAssignment.enumerator_id == current_user.id,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .first()
        )
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: You are not actively assigned to this HLB.",
            )

        return hlb

    def create_gps_observation(
        self,
        db: Session,
        hlb_id: UUID,
        current_user: User,
        payload: GpsObservationCreate,
    ) -> GpsObservationResponse:
        """
        Persist an authentic GPS observation for the assigned Enumerator and HLB.
        Validates coordinate ranges, accuracy, and building association if present.
        """
        self.verify_enumerator_hlb_access(
            db=db, hlb_id=hlb_id, current_user=current_user
        )

        # Validate coordinate ranges
        if not (-90.0 <= payload.latitude <= 90.0):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Latitude {payload.latitude} is outside range [-90.0, 90.0].",
            )
        if not (-180.0 <= payload.longitude <= 180.0):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Longitude {payload.longitude} is outside range [-180, 180].",
            )
        if payload.accuracy_meters is not None and payload.accuracy_meters < 0.0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="GPS accuracy radius cannot be negative.",
            )

        # Validate building relationship if building_id is supplied
        if payload.building_id:
            hlb_house = (
                db.query(HlbHouse)
                .filter(
                    HlbHouse.hlb_id == hlb_id,
                    HlbHouse.house_id == payload.building_id,
                )
                .first()
            )
            if not hlb_house:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Referenced building does not belong to this HLB.",
                )

        obs_time = (
            payload.timestamp if payload.timestamp is not None else datetime.now(UTC)
        )

        track = GpsTrack(
            enumerator_id=current_user.id,
            hlb_id=hlb_id,
            house_id=payload.building_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy_meters=payload.accuracy_meters,
            timestamp=obs_time,
            source="API",
        )
        db.add(track)
        db.commit()
        db.refresh(track)

        return GpsObservationResponse.model_validate(track)

    def get_hlb_gps_status(
        self,
        db: Session,
        hlb_id: UUID,
        current_user: User,
        latitude: float | None = None,
        longitude: float | None = None,
        accuracy_meters: float | None = None,
    ) -> GpsHlbStatusResponse:
        """
        Retrieve GPS status for an HLB: total observation count, latest observation,
        and real-time boundary evaluation if coordinates are provided.
        """
        hlb = self.verify_enumerator_hlb_access(
            db=db, hlb_id=hlb_id, current_user=current_user
        )

        total_obs = (
            db.query(GpsTrack)
            .filter(
                GpsTrack.hlb_id == hlb_id,
                GpsTrack.enumerator_id == current_user.id,
            )
            .count()
        )

        latest = (
            db.query(GpsTrack)
            .filter(
                GpsTrack.hlb_id == hlb_id,
                GpsTrack.enumerator_id == current_user.id,
            )
            .order_by(GpsTrack.timestamp.desc())
            .first()
        )

        boundary_status: BoundaryStatusEnum | None = None
        dist_to_boundary: float | None = None

        if latitude is not None and longitude is not None:
            status_res, dist, _ = check_point_in_hlb_boundary(
                boundary_geom=hlb.boundary,
                latitude=latitude,
                longitude=longitude,
                accuracy_meters=accuracy_meters,
            )
            boundary_status = status_res
            dist_to_boundary = dist
        elif latest:
            status_res, dist, _ = check_point_in_hlb_boundary(
                boundary_geom=hlb.boundary,
                latitude=latest.latitude,
                longitude=latest.longitude,
                accuracy_meters=latest.accuracy_meters,
            )
            boundary_status = status_res
            dist_to_boundary = dist

        return GpsHlbStatusResponse(
            hlb_id=hlb_id,
            total_observations=total_obs,
            latest_observation=GpsObservationResponse.model_validate(latest)
            if latest
            else None,
            boundary_status=boundary_status,
            distance_to_boundary_meters=dist_to_boundary,
        )

    def check_hlb_boundary(
        self,
        db: Session,
        hlb_id: UUID,
        current_user: User,
        latitude: float,
        longitude: float,
        accuracy_meters: float | None = None,
    ) -> GpsBoundaryCheckResponse:
        """
        Evaluate a coordinate against the approved HLB boundary polygon.
        """
        hlb = self.verify_enumerator_hlb_access(
            db=db, hlb_id=hlb_id, current_user=current_user
        )

        status_res, dist, msg = check_point_in_hlb_boundary(
            boundary_geom=hlb.boundary,
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
        )

        return GpsBoundaryCheckResponse(
            status=status_res,
            distance_to_boundary_meters=dist,
            accuracy_meters=accuracy_meters,
            message=msg,
        )

    def record_boundary_event(
        self,
        db: Session,
        hlb_id: UUID,
        current_user: User,
        payload: GpsBoundaryEventRequest,
    ) -> GpsBoundaryEventResponse:
        """
        Record an enumerator boundary transition event (EXIT, ENTRY, ACCURACY_WARNING).
        Notifies assigned supervisor if supervisor is assigned to the layout.
        """
        hlb = self.verify_enumerator_hlb_access(
            db=db, hlb_id=hlb_id, current_user=current_user
        )

        status_res, dist, msg = check_point_in_hlb_boundary(
            boundary_geom=hlb.boundary,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy_meters=payload.accuracy_meters,
        )

        # Determine supervisor notification status
        supervisor_notified = False
        notification_info = None

        sup_assignment = (
            db.query(LayoutSupervisorAssignment)
            .filter(
                LayoutSupervisorAssignment.layout_id == hlb.layout_id,
                LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE,
            )
            .first()
        )

        if sup_assignment and sup_assignment.supervisor_id:
            supervisor_notified = True
            notification_info = {
                "supervisor_id": str(sup_assignment.supervisor_id),
                "status": "DELIVERED",
                "channel": "IN_APP_DASHBOARD",
                "delivered_at": datetime.now(UTC).isoformat(),
            }
        else:
            notification_info = {
                "status": "QUEUED_UNASSIGNED",
                "reason": "NO_SUPERVISOR_ASSIGNED",
            }

        evt_time = payload.timestamp if payload.timestamp is not None else datetime.now(UTC)

        event = HlbBoundaryEvent(
            hlb_id=hlb_id,
            enumerator_id=current_user.id,
            event_type=payload.event_type.upper(),
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy_meters=payload.accuracy_meters,
            distance_to_boundary_meters=dist,
            boundary_status=status_res.value if hasattr(status_res, "value") else str(status_res),
            device_id=payload.device_id,
            timestamp=evt_time,
            supervisor_notified=supervisor_notified,
            notification_details=notification_info,
        )
        db.add(event)

        # Also persist as GPS track for location history
        track = GpsTrack(
            enumerator_id=current_user.id,
            hlb_id=hlb_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy_meters=payload.accuracy_meters,
            timestamp=evt_time,
            source="BOUNDARY_EVENT",
        )
        db.add(track)
        db.commit()
        db.refresh(event)

        alert_msg = msg or f"Boundary {payload.event_type} event recorded ({status_res})."
        if status_res == BoundaryStatusEnum.OUTSIDE:
            alert_msg = (
                "HLB Boundary Alert: You have moved outside your assigned HLB. "
                "Please return to your assigned area. Road traversal and route optimization "
                "are unavailable until you re-enter."
            )
        elif status_res == BoundaryStatusEnum.INSIDE and payload.event_type == "ENTRY":
            alert_msg = "Re-entry confirmed. You are inside your assigned HLB."

        return GpsBoundaryEventResponse(
            event_id=event.id,
            hlb_id=event.hlb_id,
            enumerator_id=event.enumerator_id,
            event_type=event.event_type,
            boundary_status=event.boundary_status,
            distance_to_boundary_meters=event.distance_to_boundary_meters,
            accuracy_meters=event.accuracy_meters,
            supervisor_notified=event.supervisor_notified,
            message=alert_msg,
            timestamp=event.timestamp,
        )

    def get_boundary_events(
        self,
        db: Session,
        hlb_id: UUID,
        limit: int = 50,
    ) -> list[GpsBoundaryEventResponse]:
        """
        List boundary events for an HLB, ordered by most recent first.
        """
        events = (
            db.query(HlbBoundaryEvent)
            .filter(HlbBoundaryEvent.hlb_id == hlb_id)
            .order_by(HlbBoundaryEvent.timestamp.desc())
            .limit(limit)
            .all()
        )
        results = []
        for e in events:
            results.append(
                GpsBoundaryEventResponse(
                    event_id=e.id,
                    hlb_id=e.hlb_id,
                    enumerator_id=e.enumerator_id,
                    event_type=e.event_type,
                    boundary_status=e.boundary_status,
                    distance_to_boundary_meters=e.distance_to_boundary_meters,
                    accuracy_meters=e.accuracy_meters,
                    supervisor_notified=e.supervisor_notified,
                    message=f"Boundary {e.event_type} at {e.timestamp.isoformat()}",
                    timestamp=e.timestamp,
                )
            )
        return results

    def get_supervisor_enumerator_locations(
        self,
        db: Session,
        supervisor_id: UUID,
    ) -> SupervisorEnumeratorMonitoringResponse:
        """
        Real-time tracking view for Supervisor:
        Lists all assigned enumerators, their latest reported location,
        INSIDE/OUTSIDE boundary status, whether location is live (< 5 min old)
        or stale, road coverage percentage, and unvisited road segment count.
        """
        # Find layouts assigned to this supervisor
        layout_assignments = (
            db.query(LayoutSupervisorAssignment)
            .filter(
                LayoutSupervisorAssignment.supervisor_id == supervisor_id,
                LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE,
            )
            .all()
        )
        layout_ids = [la.layout_id for la in layout_assignments]

        # Find enumerator assignments in these layouts
        enum_assignments = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.layout_id.in_(layout_ids)
                if layout_ids
                else False,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .all()
        )

        now = datetime.now(UTC)
        items: list[EnumeratorLiveLocationItem] = []
        active_now = 0
        outside_count = 0
        uncertain_count = 0

        for ea in enum_assignments:
            hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == ea.hlb_id).first()
            user = db.query(User).filter(User.id == ea.enumerator_id).first()
            if not hlb or not user:
                continue

            # Latest location
            latest_track = (
                db.query(GpsTrack)
                .filter(
                    GpsTrack.hlb_id == ea.hlb_id,
                    GpsTrack.enumerator_id == ea.enumerator_id,
                )
                .order_by(GpsTrack.timestamp.desc())
                .first()
            )

            boundary_status = "UNKNOWN"
            dist_to_boundary = None
            is_live = False
            last_ts = None
            lat = None
            lon = None
            acc = None

            if latest_track:
                lat = latest_track.latitude
                lon = latest_track.longitude
                acc = latest_track.accuracy_meters
                last_ts = latest_track.timestamp

                # Check if timestamp is within last 5 minutes
                diff_sec = (now - last_ts.replace(tzinfo=UTC) if last_ts.tzinfo is None else now - last_ts).total_seconds()
                is_live = diff_sec <= 300

                status_res, dist, _ = check_point_in_hlb_boundary(
                    boundary_geom=hlb.boundary,
                    latitude=lat,
                    longitude=lon,
                    accuracy_meters=acc,
                )
                boundary_status = status_res.value if hasattr(status_res, "value") else str(status_res)
                dist_to_boundary = dist

            if is_live:
                active_now += 1

            if boundary_status == "OUTSIDE":
                outside_count += 1
            elif boundary_status in ("BOUNDARY_UNCERTAIN", "UNKNOWN"):
                uncertain_count += 1

            # Road coverage stats
            coverages = (
                db.query(RoadSegmentCoverage)
                .filter(RoadSegmentCoverage.hlb_id == ea.hlb_id)
                .all()
            )
            total_req_m = sum(c.total_length_m for c in coverages)
            surveyed_m = sum(c.surveyed_length_m for c in coverages if c.survey_status == RoadSegmentSurveyStatus.SURVEYED)
            cov_pct = round((surveyed_m / total_req_m * 100.0), 1) if total_req_m > 0 else 0.0
            unvisited_cnt = sum(1 for c in coverages if c.survey_status == RoadSegmentSurveyStatus.NOT_VISITED)

            # Recent boundary events
            recent_events = (
                db.query(HlbBoundaryEvent)
                .filter(
                    HlbBoundaryEvent.hlb_id == ea.hlb_id,
                    HlbBoundaryEvent.enumerator_id == ea.enumerator_id,
                )
                .count()
            )

            items.append(
                EnumeratorLiveLocationItem(
                    enumerator_id=user.id,
                    enumerator_name=user.name,
                    hlb_id=hlb.id,
                    block_code=hlb.block_code,
                    latitude=lat,
                    longitude=lon,
                    accuracy_meters=acc,
                    boundary_status=boundary_status,
                    distance_to_boundary_meters=dist_to_boundary,
                    last_timestamp=last_ts,
                    is_live=is_live,
                    road_coverage_percentage=cov_pct,
                    unvisited_edges_count=unvisited_cnt,
                    recent_boundary_events_count=recent_events,
                )
            )

        return SupervisorEnumeratorMonitoringResponse(
            supervisor_id=supervisor_id,
            total_enumerators=len(items),
            active_now_count=active_now,
            outside_hlb_count=outside_count,
            uncertain_count=uncertain_count,
            enumerators=items,
        )



gps_service = GpsService()
