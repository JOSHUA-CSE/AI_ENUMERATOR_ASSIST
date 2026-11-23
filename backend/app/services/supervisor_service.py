import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from geoalchemy2.elements import WKTElement
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.building_edit import (
    BuildingEdit,
    BuildingEditReviewStatus,
    BuildingEditType,
)
from app.models.change_request import (
    ChangeRequest,
    ChangeRequestPriority,
    ChangeRequestStatus,
    ChangeRequestType,
)
from app.models.census_house import CensusHouse
from app.models.fieldwork import (
    HouseholdRecord,
    HouseholdReviewState,
    SupervisorCorrection,
    SyncOperation,
    SyncOperationStatus,
)
from app.models.hlb import HouselistingBlock
from app.models.house import BuildingFieldStatus, House
from app.models.layout import Layout, LayoutStatus, LayoutVersion, LayoutVersionStatus
from app.models.person import Person, PersonReviewState
from app.models.supervisor_assignment import (
    LayoutSupervisorAssignment,
    SupervisorAssignmentStatus,
)
from app.models.user import User, UserRole, UserStatus
from app.services.layout_service import layout_service
from app.services.progress_service import progress_service

logger = logging.getLogger(__name__)


class SupervisorService:
    """
    Business service managing Supervisor assignments, supervisor listing,
    layout authorization, and fieldwork progress monitoring.
    """

    def list_supervisors(self, db: Session) -> dict:
        """
        List active supervisors with count of currently assigned active layouts.
        """
        supervisors = (
            db.query(User)
            .filter(
                User.role == UserRole.SUPERVISOR,
                User.status == UserStatus.ACTIVE,
            )
            .order_by(User.name.asc())
            .all()
        )

        # Count active assignments per supervisor
        assignment_counts = dict(
            db.query(
                LayoutSupervisorAssignment.supervisor_id,
                func.count(LayoutSupervisorAssignment.id),
            )
            .filter(
                LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE
            )
            .group_by(LayoutSupervisorAssignment.supervisor_id)
            .all()
        )

        items = []
        for s in supervisors:
            role_str = s.role.value if hasattr(s.role, "value") else str(s.role)
            status_str = s.status.value if hasattr(s.status, "value") else str(s.status)
            items.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "username": s.username,
                    "phone": s.phone,
                    "role": role_str,
                    "status": status_str,
                    "assigned_layouts_count": assignment_counts.get(s.id, 0),
                }
            )

        return {"items": items, "total": len(items)}

    def assign_supervisor(
        self,
        db: Session,
        layout_id: UUID,
        supervisor_id: UUID,
        assigned_by_user_id: UUID,
    ) -> dict:
        """
        Assign an approved layout to a Supervisor.
        Enforces:
          1. Layout exists and is in APPROVED or ASSIGNED status.
          2. Layout has an approved active version.
          3. Supervisor exists, has role SUPERVISOR, and is ACTIVE.
          4. Handles reassignment if already actively assigned.
          5. Creates audit log.
          6. Updates layout status to ASSIGNED.
        """
        layout = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )

        # Only approved (or already assigned) layouts can be assigned/reassigned
        if layout.status not in (LayoutStatus.APPROVED, LayoutStatus.ASSIGNED):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Only approved layouts can be assigned to a Supervisor. "
                    f"Current layout status: {layout.status.value}"
                ),
            )

        # Check approved version existence
        if not layout.active_version_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Layout has no active version to assign",
            )

        approved_version = (
            db.query(LayoutVersion)
            .filter(
                LayoutVersion.id == layout.active_version_id,
                LayoutVersion.status == LayoutVersionStatus.APPROVED,
            )
            .first()
        )
        if not approved_version:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Layout active version is not in APPROVED status",
            )

        # Verify supervisor
        supervisor = db.query(User).filter(User.id == supervisor_id).first()
        if not supervisor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID {supervisor_id} not found",
            )

        if supervisor.role != UserRole.SUPERVISOR:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"User {supervisor.name} is not a Supervisor "
                    f"(role: {supervisor.role})"
                ),
            )

        if supervisor.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Supervisor {supervisor.name} account is not active",
            )

        # Fetch assigning user info for audit & response
        assigner = db.query(User).filter(User.id == assigned_by_user_id).first()

        # Check existing active assignment
        existing_assignment = (
            db.query(LayoutSupervisorAssignment)
            .filter(
                LayoutSupervisorAssignment.layout_id == layout_id,
                LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE,
            )
            .first()
        )

        try:
            old_data = None
            action = "LAYOUT_SUPERVISOR_ASSIGNED"

            if existing_assignment:
                if existing_assignment.supervisor_id == supervisor_id:
                    # Already actively assigned to this same supervisor
                    return self._format_assignment_response(
                        existing_assignment, layout, supervisor, assigner
                    )

                # Reassignment: Cancel old assignment
                old_data = {
                    "assignment_id": str(existing_assignment.id),
                    "supervisor_id": str(existing_assignment.supervisor_id),
                    "assigned_at": existing_assignment.assigned_at.isoformat(),
                    "status": existing_assignment.status.value,
                }
                existing_assignment.status = SupervisorAssignmentStatus.CANCELLED
                existing_assignment.updated_at = datetime.now(UTC)
                action = "LAYOUT_SUPERVISOR_REASSIGNED"

            # Create new active assignment
            new_assignment = LayoutSupervisorAssignment(
                layout_id=layout_id,
                supervisor_id=supervisor_id,
                assigned_by=assigned_by_user_id,
                assigned_at=datetime.now(UTC),
                status=SupervisorAssignmentStatus.ACTIVE,
            )
            db.add(new_assignment)

            # Transition layout status to ASSIGNED
            layout.status = LayoutStatus.ASSIGNED
            layout.updated_at = datetime.now(UTC)

            # Commit changes to generate new_assignment.id
            db.flush()

            new_data = {
                "assignment_id": str(new_assignment.id),
                "layout_id": str(layout_id),
                "supervisor_id": str(supervisor_id),
                "supervisor_name": supervisor.name,
                "assigned_by": str(assigned_by_user_id),
                "assigned_at": new_assignment.assigned_at.isoformat(),
                "status": new_assignment.status.value,
            }

            # Create audit log
            audit_log = AuditLog(
                user_id=assigned_by_user_id,
                action=action,
                entity_type="LAYOUT_SUPERVISOR_ASSIGNMENT",
                entity_id=layout_id,
                old_data=old_data,
                new_data=new_data,
            )
            db.add(audit_log)

            db.commit()
            db.refresh(new_assignment)

            logger.info(
                f"Assigned layout {layout.name} ({layout_id}) to "
                f"Supervisor {supervisor.name} ({supervisor_id})"
            )
            return self._format_assignment_response(
                new_assignment, layout, supervisor, assigner
            )

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to assign supervisor to layout {layout_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to assign supervisor: {str(e)}",
            ) from e

    def get_layout_supervisor_assignment(
        self, db: Session, layout_id: UUID
    ) -> dict | None:
        """
        Get active supervisor assignment for a layout.
        """
        layout = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )

        assignment = (
            db.query(LayoutSupervisorAssignment)
            .filter(
                LayoutSupervisorAssignment.layout_id == layout_id,
                LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE,
            )
            .order_by(LayoutSupervisorAssignment.assigned_at.desc())
            .first()
        )

        if not assignment:
            return None

        supervisor = db.query(User).filter(User.id == assignment.supervisor_id).first()
        assigner = (
            db.query(User).filter(User.id == assignment.assigned_by).first()
            if assignment.assigned_by
            else None
        )
        return self._format_assignment_response(
            assignment, layout, supervisor, assigner
        )

    def get_supervisor_layouts(self, db: Session, supervisor_id: UUID) -> dict:
        """
        Retrieve all layouts actively assigned to the authenticated supervisor.
        Strictly isolated by supervisor_id.
        """
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
            return {"items": [], "total": 0}

        layouts = (
            db.query(Layout)
            .filter(Layout.id.in_(layout_ids))
            .order_by(Layout.created_at.desc())
            .all()
        )

        supervisor = db.query(User).filter(User.id == supervisor_id).first()
        supervisor_name = supervisor.name if supervisor else None

        assignment_map = {a.layout_id: a for a in assignments}

        items = []
        for layout in layouts:
            formatted = layout_service._format_layout_response(db, layout)
            assignment = assignment_map.get(layout.id)
            if assignment:
                formatted["assignment"] = self._format_assignment_response(
                    assignment, layout, supervisor, None
                )
            else:
                formatted["assignment"] = None
            formatted["supervisor_name"] = supervisor_name
            items.append(formatted)

        return {"items": items, "total": len(items)}

    def check_supervisor_layout_access(
        self, db: Session, layout_id: UUID, supervisor_id: UUID
    ) -> bool:
        """
        Verify if a supervisor is actively assigned to the specified layout.
        """
        active_assignment = (
            db.query(LayoutSupervisorAssignment)
            .filter(
                LayoutSupervisorAssignment.layout_id == layout_id,
                LayoutSupervisorAssignment.supervisor_id == supervisor_id,
                LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE,
            )
            .first()
        )
        return active_assignment is not None

    def get_supervisor_layout_detail(
        self, db: Session, layout_id: UUID, supervisor_id: UUID
    ) -> dict:
        """
        Retrieve layout details for a supervisor.
        Enforces 403 Forbidden if the layout is not actively assigned to
        this supervisor.
        """
        layout = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )

        if not self.check_supervisor_layout_access(db, layout_id, supervisor_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this layout",
            )

        formatted = layout_service._format_layout_response(db, layout)
        assignment = self.get_layout_supervisor_assignment(db, layout_id)
        formatted["assignment"] = assignment
        supervisor = db.query(User).filter(User.id == supervisor_id).first()
        formatted["supervisor_name"] = supervisor.name if supervisor else None

        return formatted

    def get_hlb_progress(self, db: Session, hlb_id: UUID) -> dict:
        """
        Calculate authoritative fieldwork progress for an HLB using the centralized
        AuthoritativeProgressService.
        """
        return progress_service.calculate_hlb_progress(db=db, hlb_id=hlb_id)

    def get_layout_progress(self, db: Session, layout_id: UUID) -> dict:
        """
        Aggregate progress across all HLBs for an assigned layout using the centralized
        AuthoritativeProgressService.
        """
        return progress_service.calculate_layout_progress(db=db, layout_id=layout_id)

    def get_supervisor_overall_progress(self, db: Session, supervisor_id: UUID) -> dict:
        """
        Aggregate progress across all layouts actively assigned to the supervisor using
        the centralized AuthoritativeProgressService.
        """
        return progress_service.calculate_supervisor_overall_progress(
            db=db, supervisor_id=supervisor_id
        )

    def _get_supervisor_active_layout_ids(
        self, db: Session, supervisor_id: UUID
    ) -> list[UUID]:
        assignments = (
            db.query(LayoutSupervisorAssignment.layout_id)
            .filter(
                LayoutSupervisorAssignment.supervisor_id == supervisor_id,
                LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE,
            )
            .all()
        )
        return [a[0] for a in assignments]

    def list_submissions(
        self,
        db: Session,
        supervisor_id: UUID,
        hlb_id: UUID | None = None,
        review_state: str | None = None,
    ) -> dict:
        layout_ids = self._get_supervisor_active_layout_ids(db, supervisor_id)
        if not layout_ids:
            return {"items": [], "total": 0}

        query = (
            db.query(HouseholdRecord)
            .join(HouselistingBlock, HouselistingBlock.id == HouseholdRecord.hlb_id)
            .filter(HouselistingBlock.layout_id.in_(layout_ids))
        )
        if hlb_id:
            query = query.filter(HouseholdRecord.hlb_id == hlb_id)
        if review_state:
            query = query.filter(HouseholdRecord.review_state == review_state)

        submissions = query.order_by(HouseholdRecord.created_at.desc()).all()
        return {"items": submissions, "total": len(submissions)}

    def verify_submission(
        self,
        db: Session,
        supervisor_id: UUID,
        household_id: UUID,
        comment: str | None = None,
    ) -> HouseholdRecord:
        record = (
            db.query(HouseholdRecord).filter(HouseholdRecord.id == household_id).first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Household submission '{household_id}' not found.",
            )

        layout_ids = self._get_supervisor_active_layout_ids(db, supervisor_id)
        hlb = (
            db.query(HouselistingBlock)
            .filter(HouselistingBlock.id == record.hlb_id)
            .first()
        )
        if not hlb or hlb.layout_id not in layout_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to verify submissions for this HLB.",
            )

        now = datetime.now(UTC)
        record.review_state = HouseholdReviewState.SUPERVISOR_VERIFIED
        record.verified_by = supervisor_id
        record.verified_at = now
        record.supervisor_comment = comment
        record.updated_at = now

        audit = AuditLog(
            user_id=supervisor_id,
            action="HOUSEHOLD_VERIFIED",
            entity_type="HouseholdRecord",
            entity_id=record.id,
            new_data={"review_state": "SUPERVISOR_VERIFIED", "comment": comment},
            timestamp=now,
        )
        db.add(audit)
        db.commit()
        db.refresh(record)
        return record

    def return_submission(
        self,
        db: Session,
        supervisor_id: UUID,
        household_id: UUID,
        rejection_reason: str,
        supervisor_comment: str | None = None,
    ) -> HouseholdRecord:
        record = (
            db.query(HouseholdRecord).filter(HouseholdRecord.id == household_id).first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Household submission '{household_id}' not found.",
            )

        layout_ids = self._get_supervisor_active_layout_ids(db, supervisor_id)
        hlb = (
            db.query(HouselistingBlock)
            .filter(HouselistingBlock.id == record.hlb_id)
            .first()
        )
        if not hlb or hlb.layout_id not in layout_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to return submissions for this HLB.",
            )

        now = datetime.now(UTC)
        record.review_state = HouseholdReviewState.RETURNED_FOR_CORRECTION
        record.rejection_reason = rejection_reason
        record.supervisor_comment = supervisor_comment
        record.updated_at = now

        audit = AuditLog(
            user_id=supervisor_id,
            action="HOUSEHOLD_RETURNED",
            entity_type="HouseholdRecord",
            entity_id=record.id,
            new_data={
                "review_state": "RETURNED_FOR_CORRECTION",
                "rejection_reason": rejection_reason,
            },
            timestamp=now,
        )
        db.add(audit)
        db.commit()
        db.refresh(record)
        return record

    def list_building_edits(
        self,
        db: Session,
        supervisor_id: UUID,
        hlb_id: UUID | None = None,
        review_status: str | None = None,
    ) -> dict:
        layout_ids = self._get_supervisor_active_layout_ids(db, supervisor_id)
        if not layout_ids:
            return {"items": [], "total": 0}

        query = (
            db.query(BuildingEdit)
            .join(HouselistingBlock, HouselistingBlock.id == BuildingEdit.hlb_id)
            .filter(HouselistingBlock.layout_id.in_(layout_ids))
        )
        if hlb_id:
            query = query.filter(BuildingEdit.hlb_id == hlb_id)
        if review_status:
            query = query.filter(BuildingEdit.review_status == review_status)

        edits = query.order_by(BuildingEdit.created_at.desc()).all()
        return {"items": edits, "total": len(edits)}

    def review_building_edit(
        self,
        db: Session,
        supervisor_id: UUID,
        edit_id: UUID,
        new_status: BuildingEditReviewStatus,
        comment: str | None = None,
    ) -> BuildingEdit:
        edit = db.query(BuildingEdit).filter(BuildingEdit.id == edit_id).first()
        if not edit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Building edit '{edit_id}' not found.",
            )

        layout_ids = self._get_supervisor_active_layout_ids(db, supervisor_id)
        hlb = (
            db.query(HouselistingBlock)
            .filter(HouselistingBlock.id == edit.hlb_id)
            .first()
        )
        if not hlb or hlb.layout_id not in layout_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to review edits for this HLB.",
            )

        now = datetime.now(UTC)
        edit.review_status = new_status
        edit.reviewer_id = supervisor_id
        edit.reviewed_at = now
        edit.review_comment = comment
        edit.updated_at = now

        # If approved, apply the mutation to the target building
        if new_status == BuildingEditReviewStatus.APPROVED and edit.building_id:
            house = db.query(House).filter(House.id == edit.building_id).first()
            if house:
                if edit.edit_type == BuildingEditType.ADD:
                    house.field_status = BuildingFieldStatus.CONFIRMED
                elif edit.edit_type == BuildingEditType.DELETE:
                    house.field_status = BuildingFieldStatus.FALSE_DETECTION
                elif edit.edit_type == BuildingEditType.MOVE:
                    changes = edit.proposed_changes or {}
                    if "latitude" in changes and "longitude" in changes:
                        house.latitude = float(changes["latitude"])
                        house.longitude = float(changes["longitude"])
                        house.location = WKTElement(
                            f"POINT({house.longitude} {house.latitude})", srid=4326
                        )
                elif edit.edit_type == BuildingEditType.RENUMBER:
                    changes = edit.proposed_changes or {}
                    if "building_reference" in changes:
                        house.building_reference = changes["building_reference"]
                house.updated_at = now

        audit = AuditLog(
            user_id=supervisor_id,
            action="BUILDING_EDIT_REVIEWED",
            entity_type="BuildingEdit",
            entity_id=edit.id,
            new_data={"review_status": str(new_status), "comment": comment},
            timestamp=now,
        )
        db.add(audit)
        db.commit()
        db.refresh(edit)
        return edit

    def create_change_request(
        self,
        db: Session,
        supervisor_id: UUID,
        request_type: ChangeRequestType,
        description: str,
        hlb_id: UUID | None = None,
        layout_id: UUID | None = None,
        priority: ChangeRequestPriority = ChangeRequestPriority.MEDIUM,
        metadata_json: dict | None = None,
    ) -> ChangeRequest:
        now = datetime.now(UTC)
        req = ChangeRequest(
            request_type=request_type,
            hlb_id=hlb_id,
            layout_id=layout_id,
            requesting_user_id=supervisor_id,
            priority=priority,
            status=ChangeRequestStatus.OPEN,
            description=description,
            metadata_json=metadata_json,
            created_at=now,
            updated_at=now,
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        return req

    def list_change_requests(self, db: Session, supervisor_id: UUID) -> dict:
        requests = (
            db.query(ChangeRequest)
            .filter(ChangeRequest.requesting_user_id == supervisor_id)
            .order_by(ChangeRequest.created_at.desc())
            .all()
        )
        return {"items": requests, "total": len(requests)}

    def accept_submission(
        self,
        db: Session,
        actor_id: UUID,
        household_id: UUID,
    ) -> HouseholdRecord:
        record = db.query(HouseholdRecord).filter(HouseholdRecord.id == household_id).first()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Household submission '{household_id}' not found.",
            )
        # Legal transition check: must be in SUPERVISOR_VERIFIED or SUBMITTED
        if record.review_state not in (
            HouseholdReviewState.SUPERVISOR_VERIFIED,
            HouseholdReviewState.SUBMITTED,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Illegal transition: Cannot accept record in state '{record.review_state}'.",
            )
        now = datetime.now(UTC)
        record.review_state = HouseholdReviewState.ACCEPTED
        record.updated_at = now
        # Also mark associated persons as ACCEPTED
        for person in record.persons:
            person.review_state = PersonReviewState.ACCEPTED
        audit = AuditLog(
            user_id=actor_id,
            action="HOUSEHOLD_ACCEPTED",
            entity_type="HouseholdRecord",
            entity_id=record.id,
            new_data={"review_state": "ACCEPTED"},
            timestamp=now,
        )
        db.add(audit)
        db.commit()
        db.refresh(record)
        return record

    def list_quarantined_operations(
        self, db: Session, supervisor_id: UUID, hlb_id: UUID | None = None
    ) -> dict:
        layout_ids = self._get_supervisor_active_layout_ids(db, supervisor_id)
        query = db.query(SyncOperation).filter(
            SyncOperation.status == SyncOperationStatus.QUARANTINE
        )
        ops = query.order_by(SyncOperation.server_timestamp.desc()).all()
        return {"items": ops, "total": len(ops)}

    def review_quarantined_operation(
        self,
        db: Session,
        supervisor_id: UUID,
        operation_id: UUID,
        approved: bool,
        reason: str,
    ) -> SyncOperation:
        op = db.query(SyncOperation).filter(SyncOperation.id == operation_id).first()
        if not op:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quarantined operation '{operation_id}' not found.",
            )
        if op.status != SyncOperationStatus.QUARANTINE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Operation is in status '{op.status}', not QUARANTINE.",
            )

        now = datetime.now(UTC)
        if approved:
            op.status = SyncOperationStatus.SYNCED
            op.error_message = f"Approved by supervisor: {reason}"
            outcome = "APPROVED"
        else:
            op.status = SyncOperationStatus.FAILED
            op.error_message = f"Rejected by supervisor: {reason}"
            outcome = "REJECTED"

        audit = AuditLog(
            user_id=supervisor_id,
            action="QUARANTINE_REVIEWED",
            entity_type=str(op.entity_type),
            entity_id=None,
            new_data={
                "operation_id": str(op.id),
                "decision": outcome,
                "reason": reason,
            },
            timestamp=now,
        )
        db.add(audit)
        db.commit()
        db.refresh(op)
        return op

    def create_fieldwork_correction(
        self,
        db: Session,
        supervisor_id: UUID,
        entity_type: str,
        entity_id: UUID,
        corrected_data: dict,
        reason: str,
    ) -> SupervisorCorrection:
        now = datetime.now(UTC)
        entity_type_upper = entity_type.upper()

        if entity_type_upper in ("HOUSEHOLD", "HOUSEHOLDRECORD"):
            record = db.query(HouseholdRecord).filter(HouseholdRecord.id == entity_id).first()
            if not record:
                raise HTTPException(status_code=404, detail="Household record not found")
            orig_version = record.version
            corr_version = orig_version + 1

            changed_fields = []
            prev_data = {}
            for k, v in corrected_data.items():
                if hasattr(record, k):
                    curr_val = getattr(record, k)
                    if curr_val != v:
                        changed_fields.append(k)
                        prev_data[k] = curr_val
                elif k in ("answers", "data"):
                    changed_fields.append("answers")
                    prev_data["answers"] = record.data

            # Requirement D3: Supervisor corrections must be non-destructive.
            # The original record's submitted values remain intact as raw evidence.
            record.updated_at = now

        elif entity_type_upper in ("CENSUS_HOUSE", "CENSUSHOUSE"):
            ch = db.query(CensusHouse).filter(CensusHouse.id == entity_id).first()
            if not ch:
                raise HTTPException(status_code=404, detail="Census house not found")
            orig_version = 1
            corr_version = 2
            changed_fields = list(corrected_data.keys())
            prev_data = {}
            for k, v in corrected_data.items():
                if hasattr(ch, k):
                    prev_data[k] = str(getattr(ch, k))
            ch.updated_at = now
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported entity type for correction: {entity_type}")

        correction = SupervisorCorrection(
            entity_type=entity_type_upper,
            entity_id=entity_id,
            original_version=orig_version,
            corrected_version=corr_version,
            author_id=supervisor_id,
            author_role="SUPERVISOR",
            changed_fields=changed_fields,
            previous_data=prev_data,
            corrected_data=corrected_data,
            correction_reason=reason,
            created_at=now,
        )
        db.add(correction)

        audit = AuditLog(
            user_id=supervisor_id,
            action="SUPERVISOR_CORRECTION_CREATED",
            entity_type=entity_type_upper,
            entity_id=entity_id,
            new_data={
                "changed_fields": changed_fields,
                "corrected_version": corr_version,
                "reason": reason,
            },
            timestamp=now,
        )
        db.add(audit)
        db.commit()
        db.refresh(correction)
        return correction

    def _format_assignment_response(
        self,
        assignment: LayoutSupervisorAssignment,
        layout: Layout | None,
        supervisor: User | None,
        assigner: User | None,
    ) -> dict:
        return {
            "id": assignment.id,
            "layout_id": assignment.layout_id,
            "layout_name": layout.name if layout else None,
            "supervisor_id": assignment.supervisor_id,
            "supervisor_name": supervisor.name if supervisor else None,
            "supervisor_username": supervisor.username if supervisor else None,
            "assigned_by": assignment.assigned_by,
            "assigned_by_name": assigner.name if assigner else None,
            "assigned_at": assignment.assigned_at,
            "status": (
                assignment.status.value
                if hasattr(assignment.status, "value")
                else str(assignment.status)
            ),
            "created_at": assignment.created_at,
            "updated_at": assignment.updated_at,
        }


supervisor_service = SupervisorService()
