from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.enumerator_assignment import (
    EnumeratorAssignmentStatus,
    HlbEnumeratorAssignment,
)
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import House
from app.models.layout import Layout
from app.models.supervisor_assignment import (
    LayoutSupervisorAssignment,
    SupervisorAssignmentStatus,
)
from app.models.user import User, UserRole, UserStatus
from app.schemas.enumerator_assignment import (
    EnumeratorAssignedHlbDetailResponse,
    EnumeratorAssignmentResponse,
    EnumeratorBuildingItem,
    EnumeratorHlbDownloadResponse,
    EnumeratorListResponse,
    EnumeratorSummaryResponse,
    HlbAssignmentStatusItem,
    LayoutEnumeratorAssignmentsResponse,
)


class EnumeratorService:
    def list_enumerators(
        self, db: Session, _supervisor_id: UUID | None = None
    ) -> EnumeratorListResponse:
        """
        List all enumerators and compute genuine real-time availability.
        - AVAILABLE: Active user with 0 active HLB assignments.
        - ASSIGNED: Active user currently assigned to an active HLB.
        - INACTIVE: User status is INACTIVE.
        """
        users = (
            db.query(User)
            .filter(User.role == UserRole.ENUMERATOR)
            .order_by(User.name.asc())
            .all()
        )

        active_assignments = (
            db.query(HlbEnumeratorAssignment)
            .filter(HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE)
            .all()
        )
        assignment_map = {a.enumerator_id: a for a in active_assignments}

        items: list[EnumeratorSummaryResponse] = []
        for u in users:
            active_assign = assignment_map.get(u.id)
            if u.status == UserStatus.INACTIVE:
                availability = "INACTIVE"
            elif active_assign is not None:
                availability = "ASSIGNED"
            else:
                availability = "AVAILABLE"

            assigned_hlb_id = active_assign.hlb_id if active_assign else None
            assigned_block_code = (
                active_assign.hlb.block_code
                if active_assign and active_assign.hlb
                else None
            )
            assigned_layout_name = (
                active_assign.layout.name
                if active_assign and active_assign.layout
                else None
            )

            items.append(
                EnumeratorSummaryResponse(
                    id=u.id,
                    name=u.name,
                    username=u.username,
                    phone=u.phone,
                    role=str(u.role),
                    status=str(u.status),
                    availability=availability,
                    assigned_hlb_id=assigned_hlb_id,
                    assigned_block_code=assigned_block_code,
                    assigned_layout_name=assigned_layout_name,
                )
            )

        return EnumeratorListResponse(items=items, total=len(items))

    def assign_enumerator(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
        supervisor_id: UUID,
    ) -> EnumeratorAssignmentResponse:
        """
        Assign an eligible Primary Enumerator to an approved HLB.
        Enforces:
        1. Supervisor authorization for the parent layout.
        2. HLB exists and layout is approved/assigned.
        3. Enumerator role and active status.
        4. 1 HLB -> 1 Primary Enumerator rule (reject duplicate active assignments).
        5. Atomic reassignment with history retention and audit log.
        """
        # 1. Load HLB and parent Layout
        hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
        if not hlb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Houselisting Block with ID {hlb_id} not found",
            )

        layout = db.query(Layout).filter(Layout.id == hlb.layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent layout for HLB {hlb.block_code} not found",
            )

        # 2. Verify requesting supervisor is authorized for this layout
        active_sup_assignment = (
            db.query(LayoutSupervisorAssignment)
            .filter(
                LayoutSupervisorAssignment.layout_id == layout.id,
                LayoutSupervisorAssignment.supervisor_id == supervisor_id,
                LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE,
            )
            .first()
        )
        if not active_sup_assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to assign Enumerators for this layout",
            )

        # 3. Verify target enumerator user
        enumerator = db.query(User).filter(User.id == enumerator_id).first()
        if not enumerator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Enumerator with ID {enumerator_id} not found",
            )

        if enumerator.role != UserRole.ENUMERATOR:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"User {enumerator.name} does not have the ENUMERATOR role",
            )

        if enumerator.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Enumerator {enumerator.name} is inactive and cannot be assigned"
                ),
            )

        # 4. Check if enumerator is already assigned to another active HLB
        other_assignment = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.enumerator_id == enumerator_id,
                HlbEnumeratorAssignment.hlb_id != hlb_id,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .first()
        )
        if other_assignment:
            other_hlb_code = (
                other_assignment.hlb.block_code
                if other_assignment.hlb
                else "another HLB"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Enumerator {enumerator.name} is already assigned to active "
                    f"block {other_hlb_code}"
                ),
            )

        # 5. Handle existing active assignment on this HLB (Reassignment)
        current_active = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.hlb_id == hlb_id,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .first()
        )

        now = datetime.now(UTC)
        is_reassignment = False
        old_enumerator_id = None

        if current_active:
            if current_active.enumerator_id == enumerator_id:
                # Already assigned to this exact enumerator
                return self._format_assignment_response(current_active)

            # Reassignment: Cancel old assignment
            is_reassignment = True
            old_enumerator_id = current_active.enumerator_id
            current_active.status = EnumeratorAssignmentStatus.CANCELLED
            current_active.updated_at = now

        # 6. Create new active assignment
        new_assignment = HlbEnumeratorAssignment(
            hlb_id=hlb_id,
            layout_id=layout.id,
            enumerator_id=enumerator_id,
            supervisor_id=supervisor_id,
            assigned_at=now,
            status=EnumeratorAssignmentStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        db.add(new_assignment)

        # 7. Record Audit Log
        action_name = (
            "ENUMERATOR_REASSIGNED" if is_reassignment else "ENUMERATOR_ASSIGNED"
        )
        old_data = (
            {"previous_enumerator_id": str(old_enumerator_id)}
            if is_reassignment
            else None
        )
        new_data = {
            "enumerator_id": str(enumerator_id),
            "enumerator_name": enumerator.name,
            "hlb_id": str(hlb_id),
            "block_code": hlb.block_code,
            "layout_id": str(layout.id),
            "supervisor_id": str(supervisor_id),
            "assigned_at": now.isoformat(),
        }

        audit_entry = AuditLog(
            user_id=supervisor_id,
            action=action_name,
            entity_type="hlb",
            entity_id=hlb_id,
            old_data=old_data,
            new_data=new_data,
            timestamp=now,
        )
        db.add(audit_entry)

        db.commit()
        db.refresh(new_assignment)

        return self._format_assignment_response(new_assignment)

    def get_hlb_assignment(
        self, db: Session, hlb_id: UUID
    ) -> EnumeratorAssignmentResponse | None:
        """
        Get active primary enumerator assignment for an HLB.
        """
        assign = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.hlb_id == hlb_id,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .first()
        )
        if not assign:
            return None
        return self._format_assignment_response(assign)

    def get_layout_assignment_summary(
        self, db: Session, layout_id: UUID, supervisor_id: UUID | None = None
    ) -> LayoutEnumeratorAssignmentsResponse:
        """
        Get layout-level enumerator assignment summary and list of HLBs with
        their assigned enumerator.
        """
        layout = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )

        if supervisor_id:
            active_sup = (
                db.query(LayoutSupervisorAssignment)
                .filter(
                    LayoutSupervisorAssignment.layout_id == layout_id,
                    LayoutSupervisorAssignment.supervisor_id == supervisor_id,
                    LayoutSupervisorAssignment.status
                    == SupervisorAssignmentStatus.ACTIVE,
                )
                .first()
            )
            if not active_sup:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to view assignments for this layout",
                )

        # Load HLBs for layout's active approved version or general layout HLBs
        hlb_query = db.query(HouselistingBlock).filter(
            HouselistingBlock.layout_id == layout_id
        )
        if layout.active_version_id:
            hlb_query = hlb_query.filter(
                HouselistingBlock.version_id == layout.active_version_id
            )
        hlbs = hlb_query.order_by(HouselistingBlock.block_code.asc()).all()

        active_assignments = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.layout_id == layout_id,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .all()
        )
        assignment_map = {a.hlb_id: a for a in active_assignments}

        items: list[HlbAssignmentStatusItem] = []
        assigned_count = 0

        for h in hlbs:
            assign = assignment_map.get(h.id)
            is_assigned = assign is not None
            if is_assigned:
                assigned_count += 1

            assign_resp = self._format_assignment_response(assign) if assign else None

            items.append(
                HlbAssignmentStatusItem(
                    hlb_id=h.id,
                    block_code=h.block_code,
                    name=h.name,
                    actual_building_count=h.actual_building_count,
                    target_building_count=h.target_building_count,
                    is_assigned=is_assigned,
                    assignment=assign_resp,
                )
            )

        total_hlbs = len(hlbs)
        remaining = max(0, total_hlbs - assigned_count)
        is_complete = remaining == 0 and total_hlbs > 0
        status_label = "COMPLETE" if is_complete else "INCOMPLETE"

        return LayoutEnumeratorAssignmentsResponse(
            layout_id=layout.id,
            layout_name=layout.name,
            total_hlbs=total_hlbs,
            required_enumerators=total_hlbs,
            assigned_enumerators=assigned_count,
            remaining_enumerators=remaining,
            status=status_label,
            is_complete=is_complete,
            items=items,
        )

    def get_enumerator_assigned_hlbs(
        self, db: Session, enumerator_id: UUID
    ) -> list[EnumeratorAssignedHlbDetailResponse]:
        """
        Retrieve all HLBs actively assigned to the authenticated enumerator.
        Derived directly from authenticated JWT.
        """
        assignments = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.enumerator_id == enumerator_id,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .all()
        )

        results: list[EnumeratorAssignedHlbDetailResponse] = []
        for a in assignments:
            hlb = a.hlb
            if not hlb:
                continue

            boundary_geojson = None
            if hlb.boundary is not None:
                shape = to_shape(hlb.boundary)
                boundary_geojson = mapping(shape)

            layout_name = a.layout.name if a.layout else None
            area_name = (
                a.layout.area.name if a.layout and a.layout.area else layout_name
            )

            results.append(
                EnumeratorAssignedHlbDetailResponse(
                    id=hlb.id,
                    layout_id=a.layout_id,
                    layout_name=layout_name,
                    area_name=area_name,
                    block_code=hlb.block_code,
                    name=hlb.name,
                    status=str(hlb.status),
                    target_building_count=hlb.target_building_count,
                    actual_building_count=hlb.actual_building_count,
                    boundary=boundary_geojson,
                    assignment=self._format_assignment_response(a),
                )
            )

        return results

    def get_enumerator_assigned_hlb_detail(
        self, db: Session, hlb_id: UUID, enumerator_id: UUID
    ) -> EnumeratorAssignedHlbDetailResponse:
        """
        Retrieve detail of a specific HLB for the authenticated enumerator.
        Enforces strict 403 Forbidden access control if not assigned.
        """
        assign = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.hlb_id == hlb_id,
                HlbEnumeratorAssignment.enumerator_id == enumerator_id,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .first()
        )
        if not assign:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this HLB",
            )

        hlb = assign.hlb
        if not hlb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Houselisting Block with ID {hlb_id} not found",
            )

        boundary_geojson = None
        if hlb.boundary is not None:
            shape = to_shape(hlb.boundary)
            boundary_geojson = mapping(shape)

        layout_name = assign.layout.name if assign.layout else None
        area_name = (
            assign.layout.area.name
            if assign.layout and assign.layout.area
            else layout_name
        )

        return EnumeratorAssignedHlbDetailResponse(
            id=hlb.id,
            layout_id=assign.layout_id,
            layout_name=layout_name,
            area_name=area_name,
            block_code=hlb.block_code,
            name=hlb.name,
            status=str(hlb.status),
            target_building_count=hlb.target_building_count,
            actual_building_count=hlb.actual_building_count,
            boundary=boundary_geojson,
            assignment=self._format_assignment_response(assign),
        )

    def check_enumerator_hlb_access(
        self, db: Session, hlb_id: UUID, enumerator_id: UUID
    ) -> bool:
        """
        Check if an enumerator has active primary access to an HLB.
        """
        count = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.hlb_id == hlb_id,
                HlbEnumeratorAssignment.enumerator_id == enumerator_id,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .count()
        )
        return count > 0

    def get_enumerator_hlb_download(
        self, db: Session, hlb_id: UUID, enumerator_id: UUID
    ) -> EnumeratorHlbDownloadResponse:
        """
        Download complete HLB dataset (boundary + buildings) for offline fieldwork.
        Enforces strict 403 Forbidden if not actively assigned to this enumerator.
        """
        # 1. Verify access & retrieve HLB detail (raises 403 if unassigned)
        hlb_detail = self.get_enumerator_assigned_hlb_detail(
            db=db, hlb_id=hlb_id, enumerator_id=enumerator_id
        )

        # 2. Query all buildings assigned to this HLB
        houses = (
            db.query(House)
            .join(HlbHouse, HlbHouse.house_id == House.id)
            .filter(HlbHouse.hlb_id == hlb_id)
            .order_by(House.building_reference.asc(), House.id.asc())
            .all()
        )

        building_items: list[EnumeratorBuildingItem] = []
        for h in houses:
            footprint_geojson = None
            if h.footprint is not None:
                shape = to_shape(h.footprint)
                footprint_geojson = mapping(shape)

            b_ref = h.building_reference or f"BLD-{str(h.id)[:6].upper()}"
            building_items.append(
                EnumeratorBuildingItem(
                    id=h.id,
                    building_reference=b_ref,
                    house_number=h.house_number,
                    latitude=h.latitude,
                    longitude=h.longitude,
                    footprint=footprint_geojson,
                    source_type=str(h.source_type) if h.source_type else None,
                    status="PENDING",
                )
            )

        now = datetime.now(UTC)
        return EnumeratorHlbDownloadResponse(
            hlb=hlb_detail,
            buildings=building_items,
            total_buildings=len(building_items),
            downloaded_at=now,
        )

    def _format_assignment_response(
        self, assign: HlbEnumeratorAssignment
    ) -> EnumeratorAssignmentResponse:
        block_code = assign.hlb.block_code if assign.hlb else None
        layout_name = assign.layout.name if assign.layout else None
        enumerator_name = assign.enumerator.name if assign.enumerator else None
        enumerator_username = assign.enumerator.username if assign.enumerator else None
        supervisor_name = assign.supervisor.name if assign.supervisor else None

        return EnumeratorAssignmentResponse(
            id=assign.id,
            hlb_id=assign.hlb_id,
            block_code=block_code,
            layout_id=assign.layout_id,
            layout_name=layout_name,
            enumerator_id=assign.enumerator_id,
            enumerator_name=enumerator_name,
            enumerator_username=enumerator_username,
            supervisor_id=assign.supervisor_id,
            supervisor_name=supervisor_name,
            assigned_at=assign.assigned_at,
            status=str(assign.status),
            created_at=assign.created_at,
            updated_at=assign.updated_at,
        )


enumerator_service = EnumeratorService()
