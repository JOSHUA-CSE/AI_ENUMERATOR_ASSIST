import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.change_request import (
    ChangeRequest,
    ChangeRequestMessage,
    ChangeRequestStatus,
    ChangeRequestType,
)
from app.models.enumerator_assignment import (
    EnumeratorAssignmentStatus,
    HlbEnumeratorAssignment,
)
from app.models.fieldwork import HouseholdRecord, HouseholdReviewState
from app.models.hlb import HlbStatus, HlbValidationStatus, HouselistingBlock
from app.models.layout import Layout
from app.models.person import Person, PersonReviewState
from app.models.supervisor_assignment import (
    LayoutSupervisorAssignment,
    SupervisorAssignmentStatus,
)
from app.models.user import User
from app.schemas.deputy_progress import (
    DeputyHlbSummary,
    DeputyLayoutDetailProgressResponse,
    DeputyLayoutProgressItem,
    DeputyOverallProgressResponse,
    DeputySupervisorInfo,
)
from app.services.progress_service import progress_service
from app.services.supervisor_service import supervisor_service

logger = logging.getLogger(__name__)


class DeputyService:
    """
    Authoritative monitoring service for Deputy Tahsildar.
    Provides administrative aggregation over layouts, HLBs, supervisor assignments,
    and fieldwork progress across the Deputy's jurisdiction.
    """

    def get_layout_supervisor_info(
        self, db: Session, layout_id: UUID
    ) -> DeputySupervisorInfo:
        """
        Retrieve assigned supervisor details for a layout.
        Uses LayoutSupervisorAssignment model.
        """
        assignment = (
            db.query(LayoutSupervisorAssignment)
            .filter(
                LayoutSupervisorAssignment.layout_id == layout_id,
                LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE,
            )
            .order_by(LayoutSupervisorAssignment.assigned_at.desc())
            .first()
        )

        if not assignment or not assignment.supervisor_id:
            return DeputySupervisorInfo(
                id=None,
                name=None,
                username=None,
                phone=None,
                status="Not assigned",
                is_assigned=False,
            )

        supervisor = db.query(User).filter(User.id == assignment.supervisor_id).first()
        if not supervisor:
            return DeputySupervisorInfo(
                id=assignment.supervisor_id,
                name=None,
                username=None,
                phone=None,
                status="Active Assignment",
                is_assigned=True,
            )

        return DeputySupervisorInfo(
            id=supervisor.id,
            name=supervisor.name,
            username=supervisor.username,
            phone=supervisor.phone,
            status=assignment.status.value
            if hasattr(assignment.status, "value")
            else str(assignment.status),
            is_assigned=True,
        )

    def get_layout_progress_item(
        self, db: Session, layout: Layout
    ) -> tuple[DeputyLayoutProgressItem, list[DeputyHlbSummary]]:
        """
        Calculate aggregated progress metrics for a single layout.
        Reuses supervisor_service.get_hlb_progress to ensure 100% semantic consistency.
        """
        village_name = layout.area.name if layout.area else layout.name
        layout_status_str = (
            layout.status.value
            if hasattr(layout.status, "value")
            else str(layout.status)
        )

        # Get supervisor info
        supervisor_info = self.get_layout_supervisor_info(db, layout.id)

        # Fetch HLBs for active version (or layout)
        hlbs_query = db.query(HouselistingBlock).filter(
            HouselistingBlock.layout_id == layout.id
        )
        if layout.active_version_id:
            hlbs_query = hlbs_query.filter(
                HouselistingBlock.version_id == layout.active_version_id
            )
        hlb_records = hlbs_query.order_by(HouselistingBlock.block_code.asc()).all()

        hlb_summaries: list[DeputyHlbSummary] = []
        completed_hlbs = 0
        active_hlbs = 0

        for hlb in hlb_records:
            # Reuse supervisor_service authoritative fieldwork calculation
            hlb_data = supervisor_service.get_hlb_progress(db, hlb.id)

            t_houses = hlb_data["total_houses"]
            c_houses = hlb_data["completed_houses"]
            l_houses = hlb_data["locked_houses"]
            r_houses = hlb_data["remaining_houses"]
            rev_count = hlb_data["revisit_count"]
            prog_pct = hlb_data["progress_percentage"]

            # Fieldwork completion rule:
            # 1. Total houses > 0 and completed_houses >= total_houses, OR
            # 2. hlb.status explicitly marked COMPLETED
            is_completed = (t_houses > 0 and c_houses >= t_houses) or (
                hlb.status == HlbStatus.COMPLETED
            )

            # Active HLB rule:
            # Not completed, and (status is ACTIVE/ASSIGNED, or active enumerator
            # assigned, or fieldwork started)
            enum_assigned = hlb_data.get("enumerator") is not None
            if not enum_assigned:
                active_assign = (
                    db.query(HlbEnumeratorAssignment)
                    .filter(
                        HlbEnumeratorAssignment.hlb_id == hlb.id,
                        HlbEnumeratorAssignment.status
                        == EnumeratorAssignmentStatus.ACTIVE,
                    )
                    .first()
                )
                enum_assigned = active_assign is not None

            is_active = (not is_completed) and (
                hlb.status in (HlbStatus.ACTIVE, HlbStatus.ASSIGNED)
                or enum_assigned
                or c_houses > 0
                or l_houses > 0
                or rev_count > 0
            )

            if is_completed:
                completed_hlbs += 1
            elif is_active:
                active_hlbs += 1

            hlb_status_str = (
                hlb.status.value if hasattr(hlb.status, "value") else str(hlb.status)
            )

            enum_id = None
            enum_name = None
            if hlb_data.get("enumerator"):
                enum_id = hlb_data["enumerator"].get("id")
                enum_name = hlb_data["enumerator"].get("name")

            hlb_summaries.append(
                DeputyHlbSummary(
                    hlb_id=hlb.id,
                    block_code=hlb.block_code,
                    name=hlb.name,
                    status=hlb_status_str,
                    assigned_enumerator_id=enum_id,
                    assigned_enumerator_name=enum_name,
                    assigned_supervisor_name=supervisor_info.name
                    if supervisor_info.is_assigned
                    else None,
                    total_houses=t_houses,
                    completed_houses=c_houses,
                    remaining_houses=r_houses,
                    locked_houses=l_houses,
                    revisit_count=rev_count,
                    progress_percentage=prog_pct,
                    is_completed=is_completed,
                    is_active=is_active,
                    last_sync=hlb_data.get("last_sync"),
                )
            )

        total_hlbs = len(hlb_summaries)
        remaining_hlbs = max(0, total_hlbs - completed_hlbs)
        total_houses = sum(h.total_houses for h in hlb_summaries)
        completed_houses = sum(h.completed_houses for h in hlb_summaries)
        locked_houses = sum(h.locked_houses for h in hlb_summaries)
        revisit_count = sum(h.revisit_count for h in hlb_summaries)
        remaining_houses = max(0, total_houses - completed_houses)

        # Weighted calculation: (sum(completed) / sum(total)) * 100
        # Safe division by zero returns 0.0
        overall_progress_percentage = (
            round(min(100.0, (completed_houses / total_houses) * 100.0), 2)
            if total_houses > 0
            else 0.0
        )

        item = DeputyLayoutProgressItem(
            layout_id=layout.id,
            layout_name=layout.name,
            area_id=layout.area_id,
            village_name=village_name,
            status=layout_status_str,
            supervisor=supervisor_info,
            total_hlbs=total_hlbs,
            active_hlbs=active_hlbs,
            completed_hlbs=completed_hlbs,
            remaining_hlbs=remaining_hlbs,
            total_houses=total_houses,
            completed_houses=completed_houses,
            remaining_houses=remaining_houses,
            locked_houses=locked_houses,
            revisit_count=revisit_count,
            overall_progress_percentage=overall_progress_percentage,
        )

        return item, hlb_summaries

    def get_layout_progress_detail(
        self, db: Session, layout_id: UUID
    ) -> DeputyLayoutDetailProgressResponse:
        """
        Level 2 & Level 3: Layout detail and HLB summary within the selected layout.
        """
        layout = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )

        item, hlb_summaries = self.get_layout_progress_item(db, layout)

        return DeputyLayoutDetailProgressResponse(
            layout_id=item.layout_id,
            layout_name=item.layout_name,
            area_id=item.area_id,
            village_name=item.village_name,
            status=item.status,
            supervisor=item.supervisor,
            total_hlbs=item.total_hlbs,
            active_hlbs=item.active_hlbs,
            completed_hlbs=item.completed_hlbs,
            remaining_hlbs=item.remaining_hlbs,
            total_houses=item.total_houses,
            completed_houses=item.completed_houses,
            remaining_houses=item.remaining_houses,
            locked_houses=item.locked_houses,
            revisit_count=item.revisit_count,
            overall_progress_percentage=item.overall_progress_percentage,
            hlbs=hlb_summaries,
            last_updated=datetime.now(UTC),
        )

    def get_overall_progress(
        self, db: Session, area_id: UUID | None = None
    ) -> DeputyOverallProgressResponse:
        """
        Level 1: Overall administrative progress across layouts in Deputy jurisdiction.
        Aggregates weighted metrics across all layouts.
        """
        query = db.query(Layout)
        if area_id:
            query = query.filter(Layout.area_id == area_id)

        layouts = query.order_by(Layout.created_at.desc()).all()

        layout_items: list[DeputyLayoutProgressItem] = []
        for layout in layouts:
            item, _ = self.get_layout_progress_item(db, layout)
            layout_items.append(item)

        total_layouts = len(layout_items)
        total_hlbs = sum(layout_item.total_hlbs for layout_item in layout_items)
        active_hlbs = sum(layout_item.active_hlbs for layout_item in layout_items)
        completed_hlbs = sum(layout_item.completed_hlbs for layout_item in layout_items)
        remaining_hlbs = sum(layout_item.remaining_hlbs for layout_item in layout_items)

        total_houses = sum(layout_item.total_houses for layout_item in layout_items)
        completed_houses = sum(
            layout_item.completed_houses for layout_item in layout_items
        )
        locked_houses = sum(layout_item.locked_houses for layout_item in layout_items)
        revisit_count = sum(layout_item.revisit_count for layout_item in layout_items)
        remaining_houses = max(0, total_houses - completed_houses)

        overall_progress_percentage = (
            round(min(100.0, (completed_houses / total_houses) * 100.0), 2)
            if total_houses > 0
            else 0.0
        )

        return DeputyOverallProgressResponse(
            total_layouts=total_layouts,
            total_hlbs=total_hlbs,
            active_hlbs=active_hlbs,
            completed_hlbs=completed_hlbs,
            remaining_hlbs=remaining_hlbs,
            total_houses=total_houses,
            completed_houses=completed_houses,
            remaining_houses=remaining_houses,
            locked_houses=locked_houses,
            revisit_count=revisit_count,
            overall_progress_percentage=overall_progress_percentage,
            layouts=layout_items,
            last_updated=datetime.now(UTC),
        )

    def list_change_requests(
        self,
        db: Session,
        status_filter: ChangeRequestStatus | None = None,
        area_id: UUID | None = None,
    ) -> dict:
        query = db.query(ChangeRequest)
        if status_filter:
            query = query.filter(ChangeRequest.status == status_filter)
        if area_id:
            query = query.join(Layout, Layout.id == ChangeRequest.layout_id).filter(
                Layout.area_id == area_id
            )
        requests = query.order_by(ChangeRequest.created_at.desc()).all()
        return {"items": requests, "total": len(requests)}

    def resolve_change_request(
        self,
        db: Session,
        deputy_id: UUID,
        request_id: UUID,
        new_status: ChangeRequestStatus,
        resolution_notes: str,
    ) -> ChangeRequest:
        req = db.query(ChangeRequest).filter(ChangeRequest.id == request_id).first()
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Change request '{request_id}' not found.",
            )

        now = datetime.now(UTC)

        # Requirement D4: Approval must trigger the actual business operation
        if new_status == ChangeRequestStatus.RESOLVED:
            metadata = req.metadata_json or {}
            r_type = req.request_type

            if r_type in (ChangeRequestType.HLB_SPLIT, ChangeRequestType.SPLIT_HLB):
                # Trigger split operation if split parameters supplied
                split_line = metadata.get("split_line")
                if split_line and req.hlb_id:
                    from app.gis.hlb.editing_service import hlb_editing_service
                    from app.schemas.hlb import SplitHlbRequest
                    split_req = SplitHlbRequest(
                        split_line=split_line,
                        target_houses_per_hlb=metadata.get("target_houses_per_hlb", 250),
                    )
                    hlb_editing_service.split_hlb(db, req.hlb_id, split_req)

            elif r_type in (ChangeRequestType.ENUMERATOR_REASSIGNMENT, ChangeRequestType.REASSIGN):
                new_enum_id = metadata.get("new_enumerator_id")
                if new_enum_id and req.hlb_id:
                    # Deactivate prior active assignments for this HLB
                    old_assigns = (
                        db.query(HlbEnumeratorAssignment)
                        .filter(
                            HlbEnumeratorAssignment.hlb_id == req.hlb_id,
                            HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
                        )
                        .all()
                    )
                    for oa in old_assigns:
                        oa.status = EnumeratorAssignmentStatus.COMPLETED
                        oa.updated_at = now

                    new_assign = HlbEnumeratorAssignment(
                        hlb_id=req.hlb_id,
                        layout_id=req.layout_id,
                        enumerator_id=UUID(str(new_enum_id)),
                        status=EnumeratorAssignmentStatus.ACTIVE,
                        assigned_at=now,
                    )
                    db.add(new_assign)

            elif r_type in (ChangeRequestType.ADDITIONAL_ENUMERATOR, ChangeRequestType.EXTRA_ENUMERATOR):
                extra_id = metadata.get("extra_enumerator_id") or metadata.get("enumerator_id")
                if extra_id and req.hlb_id:
                    new_assign = HlbEnumeratorAssignment(
                        hlb_id=req.hlb_id,
                        layout_id=req.layout_id,
                        enumerator_id=UUID(str(extra_id)),
                        status=EnumeratorAssignmentStatus.ACTIVE,
                        assigned_at=now,
                    )
                    db.add(new_assign)

            elif r_type == ChangeRequestType.BOUNDARY_DISPUTE:
                if req.hlb_id:
                    hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == req.hlb_id).first()
                    if hlb:
                        hlb.validation_status = HlbValidationStatus.WARNING
                        details = hlb.validation_details or {}
                        details["boundary_dispute"] = {
                            "status": "DISPUTED",
                            "resolution_notes": resolution_notes,
                            "resolved_at": now.isoformat(),
                        }
                        hlb.validation_details = details

        req.status = new_status
        req.assigned_reviewer_id = deputy_id
        req.resolved_at = now
        req.resolution_notes = resolution_notes
        req.updated_at = now

        audit = AuditLog(
            user_id=deputy_id,
            action="CHANGE_REQUEST_RESOLVED",
            entity_type="ChangeRequest",
            entity_id=req.id,
            new_data={"status": str(new_status), "resolution_notes": resolution_notes},
            timestamp=now,
        )
        db.add(audit)
        db.commit()
        db.refresh(req)
        return req

    def list_request_messages(self, db: Session, request_id: UUID) -> list[ChangeRequestMessage]:
        req = db.query(ChangeRequest).filter(ChangeRequest.id == request_id).first()
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Change request '{request_id}' not found.",
            )
        return (
            db.query(ChangeRequestMessage)
            .filter(ChangeRequestMessage.change_request_id == request_id)
            .order_by(ChangeRequestMessage.created_at.asc())
            .all()
        )

    def add_request_message(
        self,
        db: Session,
        request_id: UUID,
        author_id: UUID,
        author_role: str,
        message: str,
        attachments: dict | None = None,
    ) -> ChangeRequestMessage:
        req = db.query(ChangeRequest).filter(ChangeRequest.id == request_id).first()
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Change request '{request_id}' not found.",
            )
        now = datetime.now(UTC)
        msg = ChangeRequestMessage(
            change_request_id=request_id,
            author_id=author_id,
            author_role=author_role,
            message=message,
            attachments=attachments,
            created_at=now,
        )
        db.add(msg)
        req.updated_at = now
        db.commit()
        db.refresh(msg)
        return msg

    def get_accepted_census_totals(
        self,
        db: Session,
        area_id: UUID | None = None,
        layout_id: UUID | None = None,
    ) -> dict:
        """
        Level 0 / Authoritative Census Totals:
        Strictly queries ONLY ACCEPTED household records and ACCEPTED persons.
        Isolates accepted census figures from in-flight/draft fieldwork progress.
        """
        query = db.query(HouseholdRecord).filter(
            HouseholdRecord.review_state == HouseholdReviewState.ACCEPTED
        )
        if layout_id:
            query = query.join(
                HouselistingBlock, HouselistingBlock.id == HouseholdRecord.hlb_id
            ).filter(HouselistingBlock.layout_id == layout_id)
        elif area_id:
            query = (
                query.join(
                    HouselistingBlock, HouselistingBlock.id == HouseholdRecord.hlb_id
                )
                .join(Layout, Layout.id == HouselistingBlock.layout_id)
                .filter(Layout.area_id == area_id)
            )

        accepted_hh = query.all()
        hh_ids = [h.id for h in accepted_hh]

        total_persons = 0
        males = 0
        females = 0
        transgender = 0

        if hh_ids:
            accepted_persons = (
                db.query(Person)
                .filter(
                    Person.household_id.in_(hh_ids),
                    Person.review_state == PersonReviewState.ACCEPTED,
                )
                .all()
            )
            if accepted_persons:
                total_persons = len(accepted_persons)
                for p in accepted_persons:
                    sex_str = str(p.sex).upper() if p.sex else ""
                    if sex_str == "MALE":
                        males += 1
                    elif sex_str == "FEMALE":
                        females += 1
                    else:
                        transgender += 1
            else:
                # If no individual Person rows are stored, aggregate from HouseholdRecord counts
                total_persons = sum(h.total_members or 0 for h in accepted_hh)
                males = sum(h.male_count or 0 for h in accepted_hh)
                females = sum(h.female_count or 0 for h in accepted_hh)

        return {
            "accepted_households": len(accepted_hh),
            "accepted_persons": total_persons,
            "accepted_population": total_persons,
            "male_count": males,
            "male_population": males,
            "female_count": females,
            "female_population": females,
            "transgender_count": transgender,
            "isolated_from_draft_progress": True,
            "source_workflow_state": "ACCEPTED",
        }

    def accept_record(
        self,
        db: Session,
        deputy_id: UUID,
        record_id: UUID,
    ) -> dict:
        """
        Deputy Tahsildar accepts a household record into the final authoritative figures.
        """
        record = db.query(HouseholdRecord).filter(HouseholdRecord.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Household record not found")
        record.review_state = HouseholdReviewState.ACCEPTED
        record.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(record)
        return {"status": "SUCCESS", "id": str(record.id), "review_state": record.review_state.value}


deputy_service = DeputyService()
