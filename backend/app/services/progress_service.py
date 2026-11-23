import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.gis.hlb.boundary_checker import (
    BoundaryStatusEnum,
    check_point_in_hlb_boundary,
)
from app.models.census_house import CensusHouse, CensusHouseListingState
from app.models.enumerator_assignment import (
    EnumeratorAssignmentStatus,
    HlbEnumeratorAssignment,
)
from app.models.fieldwork import (
    FieldworkBuildingStatus,
    GpsTrack,
    HouseFieldworkStatus,
    HouseholdRecord,
    HouseholdReviewState,
    RevisitRecord,
    RevisitRecordStatus,
    SyncOperation,
)
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import BuildingFieldStatus, House
from app.models.layout import Layout
from app.models.person import Person
from app.models.supervisor_assignment import (
    LayoutSupervisorAssignment,
    SupervisorAssignmentStatus,
)

logger = logging.getLogger(__name__)


class AuthoritativeProgressService:
    """
    Authoritative centralized fieldwork progress service.
    Enforces strict Census domain separation:
      Building -> CensusHouse -> Household -> Person

    A building is fieldwork-resolved if and only if:
      1. Its listing is explicitly closed (listing_closed == True).
      2. It has at least one associated census house (empty buildings cannot complete).
      3. Every associated census house is in a resolved state (LISTED, VACANT, NON_RESIDENTIAL),
         with none LOCKED or NOT_VISITED.
      4. Building is not a FALSE_DETECTION (excluded from progress denominators).

    Legacy fallback:
      If a building has no CensusHouse records, existing HouseFieldworkStatus is respected
      to guarantee backward compatibility.
    """

    @staticmethod
    def calculate_authoritative_progress(buildings: list[dict]) -> dict:
        """
        Pure authoritative progress evaluation function.
        Consumed identically by backend service, tests, and shared JSON test vectors.
        """
        total_eligible_buildings = 0
        completed_buildings = 0
        resolved_census_houses = 0
        locked_census_houses = 0
        unresolved_census_houses = 0

        for b in buildings:
            f_status = str(b.get("field_status", "UNVERIFIED")).upper()
            if f_status == "FALSE_DETECTION":
                continue  # Excluded from progress denominators

            total_eligible_buildings += 1
            listing_closed = bool(b.get("listing_closed", False))
            c_houses = b.get("census_houses", [])

            b_has_locked = False
            b_all_resolved = len(c_houses) > 0  # Empty building cannot become complete

            for ch in c_houses:
                state = str(ch.get("listing_state", "NOT_VISITED")).upper()
                if state in ("LISTED", "VACANT", "NON_RESIDENTIAL"):
                    resolved_census_houses += 1
                elif state == "LOCKED":
                    locked_census_houses += 1
                    b_has_locked = True
                    b_all_resolved = False
                else:
                    unresolved_census_houses += 1
                    b_all_resolved = False

            if listing_closed and b_all_resolved:
                completed_buildings += 1

        pending_buildings = max(0, total_eligible_buildings - completed_buildings)
        completion_percentage = (
            round((completed_buildings / total_eligible_buildings) * 100.0, 2)
            if total_eligible_buildings > 0
            else 0.0
        )

        return {
            "total_eligible_buildings": total_eligible_buildings,
            "completed_buildings": completed_buildings,
            "pending_buildings": pending_buildings,
            "resolved_census_houses": resolved_census_houses,
            "locked_census_houses": locked_census_houses,
            "unresolved_census_houses": unresolved_census_houses,
            "completion_percentage": completion_percentage,
        }

    def calculate_hlb_progress(self, db: Session, hlb_id: UUID) -> dict:
        hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
        if not hlb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Houselisting Block '{hlb_id}' not found.",
            )

        # 1. Assigned Buildings
        houses = (
            db.query(House)
            .join(HlbHouse, HlbHouse.house_id == House.id)
            .filter(HlbHouse.hlb_id == hlb.id)
            .all()
        )

        total_buildings = len(houses) if houses else (hlb.actual_building_count or 0)

        # Retrieve legacy fieldwork statuses for this HLB
        legacy_status_rows = (
            db.query(HouseFieldworkStatus)
            .filter(HouseFieldworkStatus.hlb_id == hlb.id)
            .all()
        )
        legacy_status_map = {row.house_id: row for row in legacy_status_rows}

        # Initialize counters
        buildings_discovered = total_buildings
        buildings_visited = 0
        buildings_confirmed = 0
        buildings_listing_closed = 0
        buildings_false_detection = 0
        buildings_completed = 0
        buildings_locked = 0

        census_houses_total = 0
        census_houses_listed = 0
        census_houses_vacant = 0
        census_houses_non_residential = 0
        census_houses_locked = 0
        census_houses_not_visited = 0

        households_total = 0
        households_submitted = 0
        households_verified = 0
        households_rejected = 0
        persons_enumerated = 0

        for house in houses:
            # Field Status checks
            f_status = (
                house.field_status.value
                if hasattr(house.field_status, "value")
                else str(house.field_status)
            )
            if f_status == BuildingFieldStatus.CONFIRMED.value:
                buildings_confirmed += 1
            elif f_status == BuildingFieldStatus.FALSE_DETECTION.value:
                buildings_false_detection += 1

            if house.listing_closed:
                buildings_listing_closed += 1

            # Fetch associated census houses
            c_houses = (
                db.query(CensusHouse).filter(CensusHouse.building_id == house.id).all()
            )

            is_visited = False
            has_locked = False
            all_ch_resolved = True

            if c_houses:
                census_houses_total += len(c_houses)
                for ch in c_houses:
                    state = (
                        ch.listing_state.value
                        if hasattr(ch.listing_state, "value")
                        else str(ch.listing_state)
                    )
                    if (
                        ch.visited_at is not None
                        or state != CensusHouseListingState.NOT_VISITED.value
                    ):
                        is_visited = True

                    if state == CensusHouseListingState.LISTED.value:
                        census_houses_listed += 1
                        # Check associated households
                        hh_records = (
                            db.query(HouseholdRecord)
                            .filter(HouseholdRecord.census_house_id == ch.id)
                            .all()
                        )
                        if not hh_records:
                            all_ch_resolved = False
                        else:
                            households_total += len(hh_records)
                            for hh in hh_records:
                                r_state = (
                                    hh.review_state.value
                                    if hasattr(hh.review_state, "value")
                                    else str(hh.review_state)
                                )
                                if r_state in (
                                    HouseholdReviewState.SUBMITTED.value,
                                    "SUBMITTED",
                                ):
                                    households_submitted += 1
                                elif r_state in (
                                    HouseholdReviewState.SUPERVISOR_VERIFIED.value,
                                    HouseholdReviewState.ACCEPTED.value,
                                    "SUPERVISOR_VERIFIED",
                                    "ACCEPTED",
                                    "VERIFIED",
                                    "APPROVED",
                                ):
                                    households_submitted += 1
                                    households_verified += 1
                                elif r_state in (
                                    HouseholdReviewState.RETURNED_FOR_CORRECTION.value,
                                    "RETURNED_FOR_CORRECTION",
                                    "RETURNED",
                                    "REJECTED",
                                ):
                                    households_rejected += 1
                                    all_ch_resolved = False

                                p_count = (
                                    db.query(Person)
                                    .filter(Person.household_id == hh.id)
                                    .count()
                                )
                                persons_enumerated += p_count

                    elif state == CensusHouseListingState.VACANT.value:
                        census_houses_vacant += 1
                    elif state == CensusHouseListingState.NON_RESIDENTIAL.value:
                        census_houses_non_residential += 1
                    elif state == CensusHouseListingState.LOCKED.value:
                        census_houses_locked += 1
                        has_locked = True
                        all_ch_resolved = False
                    elif state == CensusHouseListingState.NOT_VISITED.value:
                        census_houses_not_visited += 1
                        all_ch_resolved = False

                # Building resolution rule:
                # 1. listing_closed == True
                # 2. Every census house resolved
                # 3. Non-empty (at least one census house)
                # 4. Not false detection
                if (
                    house.listing_closed
                    and all_ch_resolved
                    and len(c_houses) > 0
                    and f_status != BuildingFieldStatus.FALSE_DETECTION.value
                ):
                    buildings_completed += 1

                if has_locked:
                    buildings_locked += 1

            else:
                # Legacy fallback if no CensusHouse rows exist yet
                leg = legacy_status_map.get(house.id)
                if leg:
                    leg_status = (
                        leg.status.value
                        if hasattr(leg.status, "value")
                        else str(leg.status)
                    )
                    if leg_status != FieldworkBuildingStatus.PENDING.value:
                        is_visited = True
                    if leg_status == FieldworkBuildingStatus.COMPLETED.value:
                        buildings_completed += 1
                    elif leg_status == FieldworkBuildingStatus.LOCKED.value:
                        buildings_locked += 1

                # If house has no census houses, it must NOT automatically complete
                # even if listing_closed is true.

            if is_visited or f_status != BuildingFieldStatus.UNVERIFIED.value:
                buildings_visited += 1

        census_houses_resolved = (
            census_houses_listed + census_houses_vacant + census_houses_non_residential
        )

        total_eligible_buildings = max(0, total_buildings - buildings_false_detection)
        remaining_buildings = max(0, total_eligible_buildings - buildings_completed)
        progress_percentage = (
            round(min(100.0, (buildings_completed / total_eligible_buildings) * 100.0), 2)
            if total_eligible_buildings > 0
            else 0.0
        )

        # Revisits
        revisit_count = (
            db.query(RevisitRecord)
            .filter(
                RevisitRecord.hlb_id == hlb.id,
                RevisitRecord.status == RevisitRecordStatus.PENDING,
            )
            .count()
        )
        if census_houses_locked > 0 and revisit_count == 0:
            revisit_count = census_houses_locked

        # Assigned Enumerator
        assignment = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.hlb_id == hlb.id,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .first()
        )
        enum_user = (
            assignment.enumerator if (assignment and assignment.enumerator) else None
        )

        # Last sync
        last_sync = None
        if enum_user:
            last_op = (
                db.query(SyncOperation)
                .filter(SyncOperation.user_id == enum_user.id)
                .order_by(SyncOperation.server_timestamp.desc())
                .first()
            )
            if last_op:
                last_sync = last_op.server_timestamp
        if not last_sync:
            latest_status = (
                db.query(HouseFieldworkStatus.last_updated_at)
                .filter(HouseFieldworkStatus.hlb_id == hlb.id)
                .order_by(HouseFieldworkStatus.last_updated_at.desc())
                .first()
            )
            if latest_status:
                last_sync = latest_status[0]

        # GPS coverage & Boundary alerts
        houses_with_gps = (
            db.query(func.count(func.distinct(GpsTrack.house_id)))
            .filter(GpsTrack.hlb_id == hlb.id, GpsTrack.house_id.isnot(None))
            .scalar()
            or 0
        )
        total_gps_obs = db.query(GpsTrack).filter(GpsTrack.hlb_id == hlb.id).count()

        gps_coverage = None
        if total_buildings > 0 and houses_with_gps > 0:
            gps_coverage = round(
                min(100.0, (houses_with_gps / total_buildings) * 100.0), 1
            )
        elif total_buildings > 0 and total_gps_obs > 0:
            gps_coverage = round(
                min(100.0, (total_gps_obs / total_buildings) * 100.0), 1
            )

        boundary_alert_count = 0
        boundary_alerts = []
        if hlb.boundary is not None and total_gps_obs > 0:
            tracks = (
                db.query(GpsTrack)
                .filter(GpsTrack.hlb_id == hlb.id)
                .order_by(GpsTrack.timestamp.desc())
                .limit(100)
                .all()
            )
            for t in tracks:
                try:
                    status_res, dist, msg = check_point_in_hlb_boundary(
                        boundary_geom=hlb.boundary,
                        latitude=t.latitude,
                        longitude=t.longitude,
                        accuracy_meters=t.accuracy_meters,
                    )
                    if status_res == BoundaryStatusEnum.OUTSIDE:
                        boundary_alert_count += 1
                        boundary_alerts.append(
                            {
                                "track_id": t.id,
                                "timestamp": t.timestamp,
                                "latitude": t.latitude,
                                "longitude": t.longitude,
                                "distance_meters": dist,
                                "message": msg or "Outside assigned HLB boundary",
                            }
                        )
                except Exception as exc:
                    logger.debug(f"Boundary check exception for track {t.id}: {exc}")

        enumerator_info = None
        if enum_user:
            enumerator_info = {
                "id": enum_user.id,
                "name": enum_user.name,
                "username": enum_user.username,
                "phone": enum_user.phone,
                "assigned_hlb_id": hlb.id,
                "assigned_hlb_code": hlb.block_code,
                "progress_percentage": progress_percentage,
                "completed_houses": buildings_completed,
                "remaining_houses": remaining_buildings,
                "locked_houses": buildings_locked,
                "revisit_count": revisit_count,
                "last_sync": last_sync,
                "sync_status": "SYNCED" if last_sync else "OFFLINE",
            }

        return {
            "hlb_id": hlb.id,
            "block_code": hlb.block_code,
            "name": hlb.name,
            "enumerator": enumerator_info,
            # Legacy metrics
            "total_houses": total_buildings,
            "total_eligible_buildings": total_eligible_buildings,
            "completed_houses": buildings_completed,
            "remaining_houses": remaining_buildings,
            "locked_houses": buildings_locked,
            "revisit_count": revisit_count,
            "progress_percentage": progress_percentage,
            "last_sync": last_sync,
            "gps_coverage": gps_coverage,
            "boundary_alert_count": boundary_alert_count,
            "boundary_alerts": boundary_alerts,
            # Authoritative domain metrics
            "buildings_discovered": buildings_discovered,
            "buildings_visited": buildings_visited,
            "buildings_confirmed": buildings_confirmed,
            "buildings_listing_closed": buildings_listing_closed,
            "buildings_false_detection": buildings_false_detection,
            "buildings_completed": buildings_completed,
            "census_houses_total": census_houses_total,
            "census_houses_listed": census_houses_listed,
            "census_houses_vacant": census_houses_vacant,
            "census_houses_non_residential": census_houses_non_residential,
            "census_houses_locked": census_houses_locked,
            "census_houses_resolved": census_houses_resolved,
            "households_total": households_total,
            "households_submitted": households_submitted,
            "households_verified": households_verified,
            "households_rejected": households_rejected,
            "persons_enumerated": persons_enumerated,
            "pending_revisits": revisit_count,
        }

    def calculate_layout_progress(self, db: Session, layout_id: UUID) -> dict:
        layout = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )

        village_name = layout.area.name if layout.area else layout.name

        hlbs_query = db.query(HouselistingBlock).filter(
            HouselistingBlock.layout_id == layout_id
        )
        if layout.active_version_id:
            hlbs_query = hlbs_query.filter(
                HouselistingBlock.version_id == layout.active_version_id
            )
        hlb_records = hlbs_query.order_by(HouselistingBlock.block_code.asc()).all()

        hlb_progress_list = [
            self.calculate_hlb_progress(db, hlb.id) for hlb in hlb_records
        ]

        total_hlbs = len(hlb_progress_list)
        total_houses = sum(h["total_houses"] for h in hlb_progress_list)
        completed_houses = sum(h["completed_houses"] for h in hlb_progress_list)
        locked_houses = sum(h["locked_houses"] for h in hlb_progress_list)
        revisit_count = sum(h["revisit_count"] for h in hlb_progress_list)
        remaining_houses = max(0, total_houses - completed_houses)
        progress_percentage = (
            round(min(100.0, (completed_houses / total_houses) * 100.0), 2)
            if total_houses > 0
            else 0.0
        )

        return {
            "layout_id": layout.id,
            "layout_name": layout.name,
            "area_id": layout.area_id,
            "village_name": village_name,
            "total_hlbs": total_hlbs,
            "total_houses": total_houses,
            "completed_houses": completed_houses,
            "remaining_houses": remaining_houses,
            "locked_houses": locked_houses,
            "revisit_count": revisit_count,
            "progress_percentage": progress_percentage,
            "last_updated": datetime.now(UTC),
            "hlbs": hlb_progress_list,
            # Aggregated domain metrics
            "buildings_discovered": sum(
                h["buildings_discovered"] for h in hlb_progress_list
            ),
            "buildings_visited": sum(h["buildings_visited"] for h in hlb_progress_list),
            "buildings_confirmed": sum(
                h["buildings_confirmed"] for h in hlb_progress_list
            ),
            "buildings_listing_closed": sum(
                h["buildings_listing_closed"] for h in hlb_progress_list
            ),
            "buildings_false_detection": sum(
                h["buildings_false_detection"] for h in hlb_progress_list
            ),
            "census_houses_listed": sum(
                h["census_houses_listed"] for h in hlb_progress_list
            ),
            "census_houses_vacant": sum(
                h["census_houses_vacant"] for h in hlb_progress_list
            ),
            "census_houses_non_residential": sum(
                h["census_houses_non_residential"] for h in hlb_progress_list
            ),
            "census_houses_locked": sum(
                h["census_houses_locked"] for h in hlb_progress_list
            ),
            "census_houses_resolved": sum(
                h["census_houses_resolved"] for h in hlb_progress_list
            ),
            "households_submitted": sum(
                h["households_submitted"] for h in hlb_progress_list
            ),
            "households_verified": sum(
                h["households_verified"] for h in hlb_progress_list
            ),
            "pending_revisits": sum(h["pending_revisits"] for h in hlb_progress_list),
        }

    def calculate_supervisor_overall_progress(
        self, db: Session, supervisor_id: UUID
    ) -> dict:
        assignments = (
            db.query(LayoutSupervisorAssignment)
            .filter(
                LayoutSupervisorAssignment.supervisor_id == supervisor_id,
                LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE,
            )
            .all()
        )

        layout_ids = [a.layout_id for a in assignments]
        if not layout_ids:
            return {
                "layouts": [],
                "total_layouts": 0,
                "overall_total_houses": 0,
                "overall_completed_houses": 0,
                "overall_remaining_houses": 0,
                "overall_locked_houses": 0,
                "overall_revisit_count": 0,
                "overall_progress_percentage": 0.0,
                "last_updated": datetime.now(UTC),
            }

        layout_progress_list = [
            self.calculate_layout_progress(db, lid) for lid in layout_ids
        ]

        overall_total = sum(lp["total_houses"] for lp in layout_progress_list)
        overall_completed = sum(lp["completed_houses"] for lp in layout_progress_list)
        overall_remaining = max(0, overall_total - overall_completed)
        overall_locked = sum(lp["locked_houses"] for lp in layout_progress_list)
        overall_revisit = sum(lp["revisit_count"] for lp in layout_progress_list)
        overall_pct = (
            round(min(100.0, (overall_completed / overall_total) * 100.0), 2)
            if overall_total > 0
            else 0.0
        )

        return {
            "layouts": layout_progress_list,
            "total_layouts": len(layout_progress_list),
            "overall_total_houses": overall_total,
            "overall_completed_houses": overall_completed,
            "overall_remaining_houses": overall_remaining,
            "overall_locked_houses": overall_locked,
            "overall_revisit_count": overall_revisit,
            "overall_progress_percentage": overall_pct,
            "last_updated": datetime.now(UTC),
            "buildings_discovered": sum(
                lp["buildings_discovered"] for lp in layout_progress_list
            ),
            "buildings_visited": sum(
                lp["buildings_visited"] for lp in layout_progress_list
            ),
            "buildings_confirmed": sum(
                lp["buildings_confirmed"] for lp in layout_progress_list
            ),
            "buildings_listing_closed": sum(
                lp["buildings_listing_closed"] for lp in layout_progress_list
            ),
            "census_houses_listed": sum(
                lp["census_houses_listed"] for lp in layout_progress_list
            ),
            "census_houses_resolved": sum(
                lp["census_houses_resolved"] for lp in layout_progress_list
            ),
            "households_submitted": sum(
                lp["households_submitted"] for lp in layout_progress_list
            ),
            "households_verified": sum(
                lp["households_verified"] for lp in layout_progress_list
            ),
            "pending_revisits": sum(
                lp["pending_revisits"] for lp in layout_progress_list
            ),
        }


progress_service = AuthoritativeProgressService()
