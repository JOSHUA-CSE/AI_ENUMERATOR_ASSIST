import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from geoalchemy2.elements import WKTElement
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.building_edit import (
    BuildingEdit,
    BuildingEditReviewStatus,
    BuildingEditType,
)
from app.models.census_house import (
    CensusHouse,
    CensusHouseListingState,
    CensusHouseUseCode,
)
from app.models.enumerator_assignment import (
    EnumeratorAssignmentStatus,
    HlbEnumeratorAssignment,
)
from app.models.fieldwork import (
    FieldworkBuildingStatus,
    GpsTrack,
    HouseFieldworkStatus,
    HouseholdRecord,
    HouseholdRecordStatus,
    HouseholdReviewState,
    HouseholdSyncStatus,
    RevisitRecord,
    RevisitRecordStatus,
    SyncEntityType,
    SyncOperation,
    SyncOperationStatus,
    SyncOperationType,
)
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import BuildingFieldStatus, House
from app.models.person import Person, PersonReviewState
from app.models.user import User, UserRole
from app.schemas.sync import (
    SyncBatchRequest,
    SyncBatchResponse,
    SyncOperationItem,
    SyncOperationResultItem,
)


class SyncService:
    def process_sync_batch(
        self,
        db: Session,
        request: SyncBatchRequest,
        current_user: User,
    ) -> SyncBatchResponse:
        """
        Process a batch of sync operations from an authenticated Enumerator.
        Enforces:
        1. Enumerator role authorization.
        2. Strict per-operation idempotency via idempotency_key.
        3. Ownership validation: Enumerator must be assigned to the referenced HLB.
        4. Relational integrity: Building must belong to the referenced HLB.
        5. Demographic arithmetic validation for household forms.
        6. Version/timestamp conflict detection for updates.
        7. Audit logging of all significant fieldwork state changes.
        """
        if current_user.role != UserRole.ENUMERATOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Only authenticated Enumerators are authorized to perform "
                    "fieldwork synchronization."
                ),
            )

        results: list[SyncOperationResultItem] = []
        now = datetime.now(UTC)

        for op in request.operations:
            result = self._process_single_operation(
                db=db,
                op=op,
                current_user=current_user,
                device_id=request.device_id,
                now=now,
            )
            results.append(result)

        success_count = sum(1 for r in results if r.status == "SUCCESS")
        failed_count = sum(1 for r in results if r.status == "FAILED")
        conflict_count = sum(1 for r in results if r.status == "CONFLICT")
        quarantine_count = sum(1 for r in results if r.status == "QUARANTINE")

        return SyncBatchResponse(
            results=results,
            processed_count=len(results),
            success_count=success_count,
            failed_count=failed_count,
            conflict_count=conflict_count,
            quarantine_count=quarantine_count,
            synced_at=now,
        )

    def _process_single_operation(
        self,
        db: Session,
        op: SyncOperationItem,
        current_user: User,
        device_id: str | None,
        now: datetime,
    ) -> SyncOperationResultItem:
        # 1. Check Idempotency Table
        existing_op = (
            db.query(SyncOperation)
            .filter(
                SyncOperation.idempotency_key == op.idempotency_key,
                SyncOperation.user_id == current_user.id,
            )
            .first()
        )
        if existing_op and existing_op.response_data:
            # Idempotent replay: return exact saved acknowledgement without re-executing
            data = existing_op.response_data
            server_id_raw = data.get("server_entity_id")
            server_id = UUID(server_id_raw) if server_id_raw else None
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status=data.get("status", "SUCCESS"),
                entity_type=op.entity_type,
                local_entity_id=op.local_entity_id,
                server_entity_id=server_id,
                version=data.get("version"),
                server_timestamp=existing_op.server_timestamp,
                error_message=data.get("error_message"),
                conflict_data=data.get("conflict_data"),
            )

        # 1b. Check (device_id, entity_type, local_entity_id) Duplicate Prevention (Requirement B2)
        # Double taps with different idempotency keys must return the existing record without duplicate creation
        if device_id and op.local_entity_id:
            duplicate_op = (
                db.query(SyncOperation)
                .filter(
                    SyncOperation.device_id == device_id,
                    SyncOperation.entity_type == op.entity_type,
                    SyncOperation.local_entity_id == op.local_entity_id,
                )
                .first()
            )
            if duplicate_op and duplicate_op.response_data:
                data = duplicate_op.response_data
                server_id_raw = data.get("server_entity_id")
                server_id = UUID(server_id_raw) if server_id_raw else None
                return SyncOperationResultItem(
                    idempotency_key=op.idempotency_key,
                    status=data.get("status", "SUCCESS"),
                    entity_type=op.entity_type,
                    local_entity_id=op.local_entity_id,
                    server_entity_id=server_id,
                    version=data.get("version"),
                    server_timestamp=duplicate_op.server_timestamp,
                    error_message=data.get("error_message"),
                    conflict_data=data.get("conflict_data"),
                )

        # 2. Extract & Validate HLB ID
        hlb_id_val = op.payload.get("hlb_id")
        if not hlb_id_val:
            return self._record_failure(
                db=db,
                op=op,
                current_user=current_user,
                device_id=device_id,
                now=now,
                error="Missing required 'hlb_id' in payload",
            )

        try:
            hlb_id = UUID(str(hlb_id_val))
        except ValueError:
            return self._record_failure(
                db=db,
                op=op,
                current_user=current_user,
                device_id=device_id,
                now=now,
                error=f"Invalid HLB UUID format: {hlb_id_val}",
            )

        # 3. Verify HLB Assignment for this Enumerator
        # Allows sync if active OR historical (prevents offline data loss upon reassignment/completion)
        assignment = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.hlb_id == hlb_id,
                HlbEnumeratorAssignment.enumerator_id == current_user.id,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .first()
        )
        is_historical = False
        if not assignment:
            # Fallback to historical assignment for this HLB
            assignment = (
                db.query(HlbEnumeratorAssignment)
                .filter(
                    HlbEnumeratorAssignment.hlb_id == hlb_id,
                    HlbEnumeratorAssignment.enumerator_id == current_user.id,
                )
                .order_by(HlbEnumeratorAssignment.assigned_at.desc())
                .first()
            )
            if assignment:
                is_historical = True

        if not assignment:
            return self._record_failure(
                db=db,
                op=op,
                current_user=current_user,
                device_id=device_id,
                now=now,
                error="Unauthorized: You are not assigned to this HLB.",
            )

        # Requirement B3: Quarantine handling for operations captured after unassignment
        if is_historical and assignment.status == EnumeratorAssignmentStatus.CANCELLED:
            unassignment_time = assignment.updated_at
            c_time = op.client_timestamp
            if c_time.tzinfo is None and unassignment_time.tzinfo is not None:
                c_time = c_time.replace(tzinfo=UTC)
            elif c_time.tzinfo is not None and unassignment_time.tzinfo is None:
                unassignment_time = unassignment_time.replace(tzinfo=UTC)

            if c_time > unassignment_time:
                return self._record_quarantine(
                    db=db,
                    op=op,
                    current_user=current_user,
                    device_id=device_id,
                    now=now,
                    reason=f"Operation client timestamp ({c_time}) is after unassignment timestamp ({unassignment_time})",
                )

        # 4. Extract & Validate Building ID if present
        building_id: UUID | None = None
        building_id_val = op.payload.get("building_id") or op.payload.get("house_id")
        is_add_building = op.entity_type in ("BUILDING_EDIT", "BUILDING") and (
            op.payload.get("edit_type") == "ADD" or op.operation_type == "CREATE"
        )
        if building_id_val:
            try:
                building_id = UUID(str(building_id_val))
            except ValueError:
                return self._record_failure(
                    db=db,
                    op=op,
                    current_user=current_user,
                    device_id=device_id,
                    now=now,
                    error=f"Invalid Building UUID format: {building_id_val}",
                )

            # Check that building belongs to the assigned HLB (unless creating a new building)
            if not is_add_building:
                hlb_house = (
                    db.query(HlbHouse)
                    .filter(
                        HlbHouse.hlb_id == hlb_id,
                        HlbHouse.house_id == building_id,
                    )
                    .first()
                )
                if not hlb_house:
                    return self._record_failure(
                        db=db,
                        op=op,
                        current_user=current_user,
                        device_id=device_id,
                        now=now,
                        error="Building does not belong to the specified HLB.",
                    )

        # 5. Route to Entity Processor
        try:
            if op.entity_type == "HOUSEHOLD":
                result = self._process_household(
                    db=db,
                    op=op,
                    hlb_id=hlb_id,
                    building_id=building_id,
                    current_user=current_user,
                    now=now,
                )
            elif op.entity_type == "CENSUS_HOUSE":
                result = self._process_census_house(
                    db=db,
                    op=op,
                    hlb_id=hlb_id,
                    building_id=building_id,
                    current_user=current_user,
                    now=now,
                )
            elif op.entity_type == "PERSON":
                result = self._process_person(
                    db=db,
                    op=op,
                    current_user=current_user,
                    now=now,
                )
            elif op.entity_type in ("BUILDING_EDIT", "BUILDING"):
                result = self._process_building_edit(
                    db=db,
                    op=op,
                    hlb_id=hlb_id,
                    building_id=building_id,
                    current_user=current_user,
                    now=now,
                )
            elif op.entity_type == "REVISIT":
                result = self._process_revisit(
                    db=db,
                    op=op,
                    hlb_id=hlb_id,
                    building_id=building_id,
                    current_user=current_user,
                    now=now,
                )
            elif op.entity_type in ("GPS_LOG", "GPS_BATCH"):
                result = self._process_gps_log(
                    db=db,
                    op=op,
                    hlb_id=hlb_id,
                    building_id=building_id,
                    current_user=current_user,
                    now=now,
                )
            elif op.entity_type in ("BUILDING_STATUS", "STATUS"):
                result = self._process_building_status(
                    db=db,
                    op=op,
                    hlb_id=hlb_id,
                    building_id=building_id,
                    current_user=current_user,
                    now=now,
                )
            else:
                result = SyncOperationResultItem(
                    idempotency_key=op.idempotency_key,
                    status="FAILED",
                    entity_type=op.entity_type,
                    local_entity_id=op.local_entity_id,
                    error_message=f"Unsupported entity type: {op.entity_type}",
                )

            # Persist SyncOperation log with response
            sync_op_record = SyncOperation(
                idempotency_key=op.idempotency_key,
                device_id=device_id,
                local_entity_id=op.local_entity_id,
                user_id=current_user.id,
                operation_type=SyncOperationType(op.operation_type)
                if op.operation_type in SyncOperationType.__members__
                else SyncOperationType.CREATE,
                entity_type=SyncEntityType(op.entity_type)
                if op.entity_type in SyncEntityType.__members__
                else SyncEntityType.HOUSEHOLD,
                entity_id=op.local_entity_id or "",
                payload=op.payload,
                client_timestamp=op.client_timestamp,
                server_timestamp=now,
                status=SyncOperationStatus(result.status)
                if result.status in SyncOperationStatus.__members__
                else SyncOperationStatus.SYNCED,
                error_message=result.error_message,
                response_data=result.model_dump(mode="json"),
            )
            try:
                db.add(sync_op_record)
                db.commit()
            except IntegrityError:
                db.rollback()
                # Unique constraint violation on (device_id, entity_type, local_entity_id) or idempotency_key
                # Return the existing successful result
                existing = (
                    db.query(SyncOperation)
                    .filter(
                        SyncOperation.device_id == device_id,
                        SyncOperation.entity_type == op.entity_type,
                        SyncOperation.local_entity_id == op.local_entity_id,
                    )
                    .first()
                )
                if existing and existing.response_data:
                    srv_id = existing.response_data.get("server_entity_id")
                    return SyncOperationResultItem(
                        idempotency_key=op.idempotency_key,
                        status=existing.response_data.get("status", "SUCCESS"),
                        entity_type=op.entity_type,
                        local_entity_id=op.local_entity_id,
                        server_entity_id=UUID(srv_id) if srv_id else None,
                        version=existing.response_data.get("version"),
                        server_timestamp=existing.server_timestamp,
                    )

            return result

        except Exception as e:
            db.rollback()
            return self._record_failure(
                db=db,
                op=op,
                current_user=current_user,
                device_id=device_id,
                now=now,
                error=f"Internal synchronization error: {str(e)}",
            )

    def _process_household(
        self,
        db: Session,
        op: SyncOperationItem,
        hlb_id: UUID,
        building_id: UUID | None,
        current_user: User,
        now: datetime,
    ) -> SyncOperationResultItem:
        if not building_id:
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="HOUSEHOLD",
                local_entity_id=op.local_entity_id,
                error_message="Missing required 'building_id' for household record.",
            )

        payload = op.payload
        head_name = (payload.get("head_name") or "").strip()
        if not head_name:
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="HOUSEHOLD",
                local_entity_id=op.local_entity_id,
                error_message="Head of household name is required.",
            )

        total_members = int(payload.get("total_members", 1))
        male_count = int(payload.get("male_count", 0))
        female_count = int(payload.get("female_count", 0))
        trans_count = int(payload.get("transgender_count", 0))

        if total_members <= 0:
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="HOUSEHOLD",
                local_entity_id=op.local_entity_id,
                error_message="Total members must be at least 1.",
            )

        if male_count + female_count + trans_count != total_members:
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="HOUSEHOLD",
                local_entity_id=op.local_entity_id,
                error_message=(
                    f"Sum of male ({male_count}), female ({female_count}), "
                    f"and transgender ({trans_count}) must equal "
                    f"total members ({total_members})."
                ),
            )

        hh_number = payload.get("household_number", "HH-1")
        ownership_status = payload.get("ownership_status", "OWNED")
        drinking_water = payload.get("drinking_water_source")
        lighting = payload.get("lighting_source")
        latrine = payload.get("latrine_facility")
        source = payload.get("source", "FORM")
        status_str = payload.get("status", "DRAFT")
        hh_status = (
            HouseholdRecordStatus.COMPLETED
            if status_str == "COMPLETED"
            else HouseholdRecordStatus.DRAFT
        )

        ch_id_val = payload.get("census_house_id")
        census_house_id = UUID(str(ch_id_val)) if ch_id_val else None
        answers = payload.get("answers") or payload.get("data")
        q_version = payload.get("questionnaire_version", "1.0")
        review_state = (
            HouseholdReviewState.SUBMITTED
            if hh_status == HouseholdRecordStatus.COMPLETED
            else HouseholdReviewState.DRAFT
        )

        if op.operation_type == "CREATE":
            record = HouseholdRecord(
                house_id=building_id,
                census_house_id=census_house_id,
                hlb_id=hlb_id,
                enumerator_id=current_user.id,
                household_number=hh_number,
                head_name=head_name,
                total_members=total_members,
                male_count=male_count,
                female_count=female_count,
                transgender_count=trans_count,
                ownership_status=ownership_status,
                drinking_water_source=drinking_water,
                lighting_source=lighting,
                latrine_facility=latrine,
                data=answers,
                questionnaire_version=q_version,
                review_state=review_state,
                source=source,
                status=hh_status,
                sync_status=HouseholdSyncStatus.SYNCED,
                version=1,
                captured_at=op.client_timestamp,
                created_at=now,
                updated_at=now,
            )
            db.add(record)
            db.flush()

            # Audit log
            audit = AuditLog(
                user_id=current_user.id,
                action="HOUSEHOLD_CREATED",
                entity_type="HouseholdRecord",
                entity_id=record.id,
                new_data={
                    "household_number": hh_number,
                    "status": str(hh_status),
                    "building_id": str(building_id),
                    "hlb_id": str(hlb_id),
                    "changed_fields": ["household_number", "head_name", "status"],
                },
                timestamp=now,
            )
            db.add(audit)

            # Update HouseFieldworkStatus if completed
            self._update_house_fieldwork_status(
                db=db,
                house_id=building_id,
                hlb_id=hlb_id,
                enumerator_id=current_user.id,
                now=now,
            )

            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="SUCCESS",
                entity_type="HOUSEHOLD",
                local_entity_id=op.local_entity_id,
                server_entity_id=record.id,
                version=1,
                server_timestamp=now,
            )

        elif op.operation_type == "UPDATE":
            existing = None
            if op.server_entity_id:
                existing = (
                    db.query(HouseholdRecord)
                    .filter(HouseholdRecord.id == op.server_entity_id)
                    .first()
                )

            if not existing:
                existing = (
                    db.query(HouseholdRecord)
                    .filter(
                        HouseholdRecord.house_id == building_id,
                        HouseholdRecord.hlb_id == hlb_id,
                        HouseholdRecord.household_number == hh_number,
                    )
                    .first()
                )

            if not existing:
                return SyncOperationResultItem(
                    idempotency_key=op.idempotency_key,
                    status="FAILED",
                    entity_type="HOUSEHOLD",
                    local_entity_id=op.local_entity_id,
                    error_message="Household record not found for update.",
                )

            # Conflict Detection: If server has higher version than client expected
            client_version = op.version or 1
            if existing.version > client_version:
                return SyncOperationResultItem(
                    idempotency_key=op.idempotency_key,
                    status="CONFLICT",
                    entity_type="HOUSEHOLD",
                    local_entity_id=op.local_entity_id,
                    server_entity_id=existing.id,
                    version=existing.version,
                    server_timestamp=existing.updated_at,
                    error_message="Conflict: Server record has a newer version.",
                    conflict_data={
                        "server_version": existing.version,
                        "server_head_name": existing.head_name,
                        "server_household_number": existing.household_number,
                        "server_total_members": existing.total_members,
                        "server_status": str(existing.status),
                        "server_updated_at": existing.updated_at.isoformat(),
                    },
                )

            # Apply update
            existing.head_name = head_name
            existing.household_number = hh_number
            existing.total_members = total_members
            existing.male_count = male_count
            existing.female_count = female_count
            existing.transgender_count = trans_count
            existing.ownership_status = ownership_status
            existing.drinking_water_source = drinking_water
            existing.lighting_source = lighting
            existing.latrine_facility = latrine
            existing.status = hh_status
            if census_house_id:
                existing.census_house_id = census_house_id
            if answers:
                existing.answers = answers
            if (
                hh_status == HouseholdRecordStatus.COMPLETED
                and existing.review_state
                in (
                    HouseholdReviewState.DRAFT,
                    HouseholdReviewState.RETURNED_FOR_CORRECTION,
                )
            ):
                existing.review_state = HouseholdReviewState.SUBMITTED
            existing.version += 1
            existing.updated_at = now

            audit = AuditLog(
                user_id=current_user.id,
                action="HOUSEHOLD_UPDATED",
                entity_type="HouseholdRecord",
                entity_id=existing.id,
                new_data={
                    "household_number": hh_number,
                    "version": existing.version,
                    "status": str(hh_status),
                    "changed_fields": ["household_number", "head_name", "status", "answers"],
                },
                timestamp=now,
            )
            db.add(audit)

            self._update_house_fieldwork_status(
                db=db,
                house_id=building_id,
                hlb_id=hlb_id,
                enumerator_id=current_user.id,
                now=now,
            )

            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="SUCCESS",
                entity_type="HOUSEHOLD",
                local_entity_id=op.local_entity_id,
                server_entity_id=existing.id,
                version=existing.version,
                server_timestamp=now,
            )

        else:
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="HOUSEHOLD",
                local_entity_id=op.local_entity_id,
                error_message=(
                    f"Unsupported operation type '{op.operation_type}' for HOUSEHOLD."
                ),
            )

    def _process_revisit(
        self,
        db: Session,
        op: SyncOperationItem,
        hlb_id: UUID,
        building_id: UUID | None,
        current_user: User,
        now: datetime,
    ) -> SyncOperationResultItem:
        if not building_id:
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="REVISIT",
                local_entity_id=op.local_entity_id,
                error_message="Missing required 'building_id' for revisit.",
            )

        payload = op.payload
        reason = payload.get("reason", "OTHER")
        notes = payload.get("notes")

        revisit = RevisitRecord(
            house_id=building_id,
            hlb_id=hlb_id,
            enumerator_id=current_user.id,
            reason=reason,
            notes=notes,
            status=RevisitRecordStatus.PENDING,
            recommended_at=op.client_timestamp,
        )
        db.add(revisit)
        db.flush()

        # Update HouseFieldworkStatus to REVISIT_REQUIRED
        status_rec = (
            db.query(HouseFieldworkStatus)
            .filter(
                HouseFieldworkStatus.house_id == building_id,
                HouseFieldworkStatus.hlb_id == hlb_id,
            )
            .first()
        )
        if not status_rec:
            status_rec = HouseFieldworkStatus(
                house_id=building_id,
                hlb_id=hlb_id,
                enumerator_id=current_user.id,
                status=FieldworkBuildingStatus.REVISIT_REQUIRED,
                last_updated_at=now,
                updated_by=current_user.id,
            )
            db.add(status_rec)
        else:
            status_rec.status = FieldworkBuildingStatus.REVISIT_REQUIRED
            status_rec.last_updated_at = now
            status_rec.updated_by = current_user.id

        audit = AuditLog(
            user_id=current_user.id,
            action="REVISIT_CREATED",
            entity_type="RevisitRecord",
            entity_id=revisit.id,
            new_data={
                "building_id": str(building_id),
                "hlb_id": str(hlb_id),
                "reason": reason,
            },
            timestamp=now,
        )
        db.add(audit)

        return SyncOperationResultItem(
            idempotency_key=op.idempotency_key,
            status="SUCCESS",
            entity_type="REVISIT",
            local_entity_id=op.local_entity_id,
            server_entity_id=revisit.id,
            server_timestamp=now,
        )

    def _process_gps_log(
        self,
        db: Session,
        op: SyncOperationItem,
        hlb_id: UUID,
        building_id: UUID | None,
        current_user: User,
        now: datetime,
    ) -> SyncOperationResultItem:
        payload = op.payload
        try:
            lat_raw = payload.get("latitude")
            lng_raw = payload.get("longitude")
            if lat_raw is None or lng_raw is None:
                raise ValueError("Missing latitude or longitude")
            lat = float(lat_raw)
            lng = float(lng_raw)
        except (TypeError, ValueError):
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="GPS_LOG",
                local_entity_id=op.local_entity_id,
                error_message="Invalid or missing GPS latitude/longitude in payload",
            )

        if not (-90.0 <= lat <= 90.0):
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="GPS_LOG",
                local_entity_id=op.local_entity_id,
                error_message=f"Latitude {lat} is out of valid range [-90.0, 90.0]",
            )

        if not (-180.0 <= lng <= 180.0):
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="GPS_LOG",
                local_entity_id=op.local_entity_id,
                error_message=f"Longitude {lng} is out of valid range [-180.0, 180.0]",
            )

        accuracy = (
            payload.get("accuracy")
            if "accuracy" in payload
            else payload.get("accuracy_meters")
        )
        acc_float = None
        if accuracy is not None:
            try:
                acc_float = float(accuracy)
                if acc_float < 0.0:
                    return SyncOperationResultItem(
                        idempotency_key=op.idempotency_key,
                        status="FAILED",
                        entity_type="GPS_LOG",
                        local_entity_id=op.local_entity_id,
                        error_message="Accuracy radius cannot be negative",
                    )
            except (TypeError, ValueError):
                return SyncOperationResultItem(
                    idempotency_key=op.idempotency_key,
                    status="FAILED",
                    entity_type="GPS_LOG",
                    local_entity_id=op.local_entity_id,
                    error_message=f"Invalid accuracy format: {accuracy}",
                )

        obs_time = op.client_timestamp or now

        track = GpsTrack(
            enumerator_id=current_user.id,
            hlb_id=hlb_id,
            house_id=building_id,
            latitude=lat,
            longitude=lng,
            accuracy_meters=acc_float,
            timestamp=obs_time,
            source="OFFLINE",
        )
        db.add(track)
        db.flush()

        return SyncOperationResultItem(
            idempotency_key=op.idempotency_key,
            status="SUCCESS",
            entity_type="GPS_LOG",
            local_entity_id=op.local_entity_id,
            server_entity_id=track.id,
            server_timestamp=now,
        )

    def _process_building_status(
        self,
        db: Session,
        op: SyncOperationItem,
        hlb_id: UUID,
        building_id: UUID | None,
        current_user: User,
        now: datetime,
    ) -> SyncOperationResultItem:
        if not building_id:
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="BUILDING_STATUS",
                local_entity_id=op.local_entity_id,
                error_message=(
                    "Missing required 'building_id' for building status update."
                ),
            )

        payload = op.payload
        status_str = payload.get("status", "IN_PROGRESS")
        bld_status = (
            FieldworkBuildingStatus(status_str)
            if status_str in FieldworkBuildingStatus.__members__
            else FieldworkBuildingStatus.IN_PROGRESS
        )
        hh_count = int(payload.get("household_count", 0))

        status_rec = (
            db.query(HouseFieldworkStatus)
            .filter(
                HouseFieldworkStatus.house_id == building_id,
                HouseFieldworkStatus.hlb_id == hlb_id,
            )
            .first()
        )
        if not status_rec:
            status_rec = HouseFieldworkStatus(
                house_id=building_id,
                hlb_id=hlb_id,
                enumerator_id=current_user.id,
                status=bld_status,
                household_count=hh_count,
                last_updated_at=now,
                updated_by=current_user.id,
            )
            db.add(status_rec)
        else:
            status_rec.status = bld_status
            status_rec.household_count = hh_count
            status_rec.last_updated_at = now
            status_rec.updated_by = current_user.id

        if bld_status == FieldworkBuildingStatus.LOCKED:
            audit = AuditLog(
                user_id=current_user.id,
                action="HOUSE_LOCKED",
                entity_type="House",
                entity_id=building_id,
                new_data={"hlb_id": str(hlb_id), "status": "LOCKED"},
                timestamp=now,
            )
            db.add(audit)

        # Update House domain attributes if present in payload
        house = db.query(House).filter(House.id == building_id).first()
        if house:
            if "listing_closed" in payload:
                house.listing_closed = bool(payload["listing_closed"])
                house.listing_closed_at = now if house.listing_closed else None
            if "field_status" in payload:
                f_status_str = payload["field_status"]
                if f_status_str in BuildingFieldStatus.__members__:
                    house.field_status = BuildingFieldStatus(f_status_str)
            if "latitude" in payload and "longitude" in payload:
                house.latitude = float(payload["latitude"])
                house.longitude = float(payload["longitude"])
                house.location = WKTElement(
                    f"POINT({house.longitude} {house.latitude})", srid=4326
                )
            house.updated_at = now

        return SyncOperationResultItem(
            idempotency_key=op.idempotency_key,
            status="SUCCESS",
            entity_type="BUILDING_STATUS",
            local_entity_id=op.local_entity_id,
            server_timestamp=now,
        )

    def _process_census_house(
        self,
        db: Session,
        op: SyncOperationItem,
        hlb_id: UUID,
        building_id: UUID | None,
        current_user: User,
        now: datetime,
    ) -> SyncOperationResultItem:
        if not building_id:
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="CENSUS_HOUSE",
                local_entity_id=op.local_entity_id,
                error_message="Missing required 'building_id' for census house record.",
            )

        payload = op.payload
        ch_num = payload.get("census_house_number", "CH-1")
        use_code_str = payload.get("use_code", "RESIDENTIAL")
        use_code = (
            CensusHouseUseCode(use_code_str)
            if use_code_str in CensusHouseUseCode.__members__
            else CensusHouseUseCode.RESIDENTIAL
        )
        listing_state_str = payload.get("listing_state", "NOT_VISITED")
        listing_state = (
            CensusHouseListingState(listing_state_str)
            if listing_state_str in CensusHouseListingState.__members__
            else CensusHouseListingState.NOT_VISITED
        )

        lat = payload.get("latitude")
        lon = payload.get("longitude")
        acc = payload.get("geotag_accuracy_m")
        visited_at = payload.get("visited_at")
        locked_attempts = int(payload.get("locked_attempts", 0))

        existing_ch = None
        if op.local_entity_id:
            try:
                existing_ch = (
                    db.query(CensusHouse)
                    .filter(CensusHouse.id == UUID(op.local_entity_id))
                    .first()
                )
            except ValueError:
                pass

        if op.operation_type == "CREATE" and not existing_ch:
            ch_id = UUID(op.local_entity_id) if op.local_entity_id else uuid.uuid4()
            ch = CensusHouse(
                id=ch_id,
                building_id=building_id,
                hlb_id=hlb_id,
                census_house_number=ch_num,
                use_code=use_code,
                listing_state=listing_state,
                latitude=float(lat) if lat is not None else None,
                longitude=float(lon) if lon is not None else None,
                geotag_accuracy_m=float(acc) if acc is not None else None,
                visited_at=now if visited_at else None,
                locked_attempts=locked_attempts,
                created_by=current_user.id,
                created_at=now,
                updated_at=now,
            )
            db.add(ch)
            db.flush()

            audit = AuditLog(
                user_id=current_user.id,
                action="CENSUS_HOUSE_CREATED",
                entity_type="CensusHouse",
                entity_id=ch.id,
                new_data={
                    "census_house_number": ch_num,
                    "listing_state": str(listing_state),
                    "building_id": str(building_id),
                },
                timestamp=now,
            )
            db.add(audit)
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="SUCCESS",
                entity_type="CENSUS_HOUSE",
                local_entity_id=op.local_entity_id,
                server_entity_id=ch.id,
                version=1,
                server_timestamp=now,
            )
        else:
            ch = existing_ch or (
                db.query(CensusHouse)
                .filter(
                    CensusHouse.building_id == building_id,
                    CensusHouse.census_house_number == ch_num,
                )
                .first()
            )
            if not ch:
                ch_id = UUID(op.local_entity_id) if op.local_entity_id else uuid.uuid4()
                ch = CensusHouse(
                    id=ch_id,
                    building_id=building_id,
                    hlb_id=hlb_id,
                    census_house_number=ch_num,
                    use_code=use_code,
                    listing_state=listing_state,
                    latitude=float(lat) if lat is not None else None,
                    longitude=float(lon) if lon is not None else None,
                    geotag_accuracy_m=float(acc) if acc is not None else None,
                    visited_at=now if visited_at else None,
                    locked_attempts=locked_attempts,
                    created_by=current_user.id,
                    created_at=now,
                    updated_at=now,
                )
                db.add(ch)
            else:
                ch.use_code = use_code
                ch.listing_state = listing_state
                if lat is not None:
                    ch.latitude = float(lat)
                if lon is not None:
                    ch.longitude = float(lon)
                if acc is not None:
                    ch.geotag_accuracy_m = float(acc)
                if visited_at:
                    ch.visited_at = now
                ch.locked_attempts = locked_attempts
                ch.updated_at = now

            db.flush()
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="SUCCESS",
                entity_type="CENSUS_HOUSE",
                local_entity_id=op.local_entity_id,
                server_entity_id=ch.id,
                server_timestamp=now,
            )

    def _process_person(
        self,
        db: Session,
        op: SyncOperationItem,
        current_user: User,
        now: datetime,
    ) -> SyncOperationResultItem:
        _ = current_user
        payload = op.payload
        hh_id_val = payload.get("household_id")
        if not hh_id_val:
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="PERSON",
                local_entity_id=op.local_entity_id,
                error_message="Missing required 'household_id' for person record.",
            )
        try:
            household_id = UUID(str(hh_id_val))
        except ValueError:
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="FAILED",
                entity_type="PERSON",
                local_entity_id=op.local_entity_id,
                error_message=f"Invalid household UUID: {hh_id_val}",
            )

        person_number = int(payload.get("person_number", 1))
        answers = payload.get("answers", {})
        q_version = payload.get("questionnaire_version", "1.0")
        r_state_str = payload.get("review_state", "SUBMITTED")
        review_state = (
            PersonReviewState(r_state_str)
            if r_state_str in PersonReviewState.__members__
            else PersonReviewState.SUBMITTED
        )
        name = payload.get("name") or answers.get("name") or f"Person-{person_number}"
        sex_raw = (
            payload.get("sex")
            or payload.get("gender")
            or answers.get("gender")
            or answers.get("sex")
            or "MALE"
        )
        sex = str(sex_raw).upper()
        rel = (
            payload.get("relationship_to_head")
            or answers.get("relationship_to_head")
            or "HEAD"
        )
        age_val = payload.get("age") or answers.get("age")
        age = int(age_val) if age_val is not None else None

        existing_person = None
        if op.local_entity_id:
            try:
                existing_person = (
                    db.query(Person)
                    .filter(Person.id == UUID(op.local_entity_id))
                    .first()
                )
            except ValueError:
                pass

        if op.operation_type == "CREATE" and not existing_person:
            p_id = UUID(op.local_entity_id) if op.local_entity_id else uuid.uuid4()
            person = Person(
                id=p_id,
                household_id=household_id,
                person_number=person_number,
                name=name,
                sex=sex,
                relationship_to_head=rel,
                age=age,
                answers=answers,
                questionnaire_version=q_version,
                review_state=review_state,
                created_at=now,
                updated_at=now,
            )
            db.add(person)
            db.flush()
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="SUCCESS",
                entity_type="PERSON",
                local_entity_id=op.local_entity_id,
                server_entity_id=person.id,
                version=1,
                server_timestamp=now,
            )
        else:
            person = existing_person or (
                db.query(Person)
                .filter(
                    Person.household_id == household_id,
                    Person.person_number == person_number,
                )
                .first()
            )
            if not person:
                p_id = UUID(op.local_entity_id) if op.local_entity_id else uuid.uuid4()
                person = Person(
                    id=p_id,
                    household_id=household_id,
                    person_number=person_number,
                    name=name,
                    sex=sex,
                    relationship_to_head=rel,
                    age=age,
                    answers=answers,
                    questionnaire_version=q_version,
                    review_state=review_state,
                    created_at=now,
                    updated_at=now,
                )
                db.add(person)
            else:
                person.name = name
                person.sex = sex
                person.relationship_to_head = rel
                if age is not None:
                    person.age = age
                person.answers = answers
                person.review_state = review_state
                person.questionnaire_version = q_version
                person.updated_at = now
            db.flush()
            return SyncOperationResultItem(
                idempotency_key=op.idempotency_key,
                status="SUCCESS",
                entity_type="PERSON",
                local_entity_id=op.local_entity_id,
                server_entity_id=person.id,
                server_timestamp=now,
            )

    def _process_building_edit(
        self,
        db: Session,
        op: SyncOperationItem,
        hlb_id: UUID,
        building_id: UUID | None,
        current_user: User,
        now: datetime,
    ) -> SyncOperationResultItem:
        payload = op.payload
        edit_type_str = payload.get("edit_type", "ADD")
        edit_type = (
            BuildingEditType(edit_type_str)
            if edit_type_str in BuildingEditType.__members__
            else BuildingEditType.ADD
        )
        proposed_changes = payload.get("proposed_changes", {})
        request_reason = payload.get(
            "request_reason", "Enumerator fieldwork observation"
        )

        target_building_id = building_id
        if edit_type == BuildingEditType.ADD and not target_building_id:
            lat = proposed_changes.get("latitude") or payload.get("latitude") or 0.0
            lon = proposed_changes.get("longitude") or payload.get("longitude") or 0.0
            b_ref = (
                proposed_changes.get("building_reference")
                or payload.get("building_reference")
                or f"ADD-{uuid.uuid4().hex[:6].upper()}"
            )
            hlb = (
                db.query(HouselistingBlock)
                .filter(HouselistingBlock.id == hlb_id)
                .first()
            )
            area_id = hlb.layout.area_id if (hlb and hlb.layout) else None

            new_house = House(
                id=uuid.uuid4(),
                area_id=area_id,
                building_reference=b_ref,
                latitude=float(lat),
                longitude=float(lon),
                location=WKTElement(f"POINT({lon} {lat})", srid=4326),
                field_status=BuildingFieldStatus.FIELD_ADDED,
                listing_closed=False,
                created_at=now,
                updated_at=now,
            )
            db.add(new_house)
            db.flush()
            db.add(HlbHouse(hlb_id=hlb_id, house_id=new_house.id))
            target_building_id = new_house.id

        edit_id = UUID(op.local_entity_id) if op.local_entity_id else uuid.uuid4()
        edit = BuildingEdit(
            id=edit_id,
            hlb_id=hlb_id,
            building_id=target_building_id,
            requesting_user_id=current_user.id,
            edit_type=edit_type,
            proposed_changes=proposed_changes,
            reason=request_reason,
            review_status=BuildingEditReviewStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        db.add(edit)
        db.flush()

        audit = AuditLog(
            user_id=current_user.id,
            action="BUILDING_EDIT_REQUESTED",
            entity_type="BuildingEdit",
            entity_id=edit.id,
            new_data={"edit_type": str(edit_type), "hlb_id": str(hlb_id)},
            timestamp=now,
        )
        db.add(audit)

        return SyncOperationResultItem(
            idempotency_key=op.idempotency_key,
            status="SUCCESS",
            entity_type="BUILDING_EDIT",
            local_entity_id=op.local_entity_id,
            server_entity_id=edit.id,
            server_timestamp=now,
        )

    def _update_house_fieldwork_status(
        self,
        db: Session,
        house_id: UUID,
        hlb_id: UUID,
        enumerator_id: UUID,
        now: datetime,
    ) -> None:
        households = (
            db.query(HouseholdRecord)
            .filter(
                HouseholdRecord.house_id == house_id,
                HouseholdRecord.hlb_id == hlb_id,
            )
            .all()
        )
        total_hh = len(households)
        completed_hh = sum(
            1 for h in households if h.status == HouseholdRecordStatus.COMPLETED
        )

        new_status = FieldworkBuildingStatus.IN_PROGRESS
        if total_hh > 0 and completed_hh == total_hh:
            new_status = FieldworkBuildingStatus.COMPLETED
        elif total_hh == 0:
            new_status = FieldworkBuildingStatus.PENDING

        status_rec = (
            db.query(HouseFieldworkStatus)
            .filter(
                HouseFieldworkStatus.house_id == house_id,
                HouseFieldworkStatus.hlb_id == hlb_id,
            )
            .first()
        )
        if not status_rec:
            status_rec = HouseFieldworkStatus(
                house_id=house_id,
                hlb_id=hlb_id,
                enumerator_id=enumerator_id,
                status=new_status,
                household_count=total_hh,
                last_updated_at=now,
                updated_by=enumerator_id,
            )
            db.add(status_rec)
        else:
            status_rec.status = new_status
            status_rec.household_count = total_hh
            status_rec.last_updated_at = now
            status_rec.updated_by = enumerator_id

    def _record_quarantine(
        self,
        db: Session,
        op: SyncOperationItem,
        current_user: User,
        device_id: str | None,
        now: datetime,
        reason: str,
    ) -> SyncOperationResultItem:
        """
        Record a quarantined operation when an offline operation is submitted
        with a timestamp after the enumerator was unassigned.
        Preserves the operation and audit trail for supervisor review.
        """
        res = SyncOperationResultItem(
            idempotency_key=op.idempotency_key,
            status="QUARANTINE",
            entity_type=op.entity_type,
            local_entity_id=op.local_entity_id,
            error_message=reason,
            server_timestamp=now,
        )
        sync_op_record = SyncOperation(
            idempotency_key=op.idempotency_key,
            device_id=device_id,
            local_entity_id=op.local_entity_id,
            user_id=current_user.id,
            operation_type=SyncOperationType(op.operation_type)
            if op.operation_type in SyncOperationType.__members__
            else SyncOperationType.CREATE,
            entity_type=SyncEntityType(op.entity_type)
            if op.entity_type in SyncEntityType.__members__
            else SyncEntityType.HOUSEHOLD,
            entity_id=op.local_entity_id or "",
            payload=op.payload,
            client_timestamp=op.client_timestamp,
            server_timestamp=now,
            status=SyncOperationStatus.QUARANTINE,
            error_message=reason,
            response_data=res.model_dump(mode="json"),
        )
        try:
            db.add(sync_op_record)
            # Non-PII audit record
            audit = AuditLog(
                user_id=current_user.id,
                action="SYNC_OPERATION_QUARANTINED",
                entity_type=op.entity_type,
                entity_id=None,
                new_data={
                    "operation_id": str(sync_op_record.id),
                    "local_entity_id": op.local_entity_id,
                    "reason": reason,
                    "outcome": "QUARANTINED",
                },
                timestamp=now,
            )
            db.add(audit)
            db.commit()
        except IntegrityError:
            db.rollback()

        return res

    def _record_failure(
        self,
        db: Session,
        op: SyncOperationItem,
        current_user: User,
        device_id: str | None,
        now: datetime,
        error: str,
    ) -> SyncOperationResultItem:
        res = SyncOperationResultItem(
            idempotency_key=op.idempotency_key,
            status="FAILED",
            entity_type=op.entity_type,
            local_entity_id=op.local_entity_id,
            error_message=error,
            server_timestamp=now,
        )
        sync_op_record = SyncOperation(
            idempotency_key=op.idempotency_key,
            device_id=device_id,
            local_entity_id=op.local_entity_id,
            user_id=current_user.id,
            operation_type=SyncOperationType.CREATE,
            entity_type=SyncEntityType.HOUSEHOLD,
            entity_id=op.local_entity_id or "",
            payload=op.payload,
            client_timestamp=op.client_timestamp,
            server_timestamp=now,
            status=SyncOperationStatus.FAILED,
            error_message=error,
            response_data=res.model_dump(mode="json"),
        )
        try:
            db.add(sync_op_record)
            db.commit()
        except IntegrityError:
            db.rollback()
        return res


sync_service = SyncService()
