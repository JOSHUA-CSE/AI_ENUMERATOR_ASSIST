import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.administrative_area import AdministrativeArea, AreaType
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
from app.models.fieldwork import (
    HouseholdRecord,
    HouseholdRecordStatus,
    HouseholdReviewState,
    SupervisorCorrection,
    SyncEntityType,
    SyncOperation,
    SyncOperationStatus,
    SyncOperationType,
)
from app.models.hlb import HlbHouse, HlbStatus, HouselistingBlock
from app.models.hlb_counter import HlbCounter
from app.models.house import BuildingFieldStatus, House
from app.models.layout import (
    Layout,
    LayoutStatus,
    LayoutVersion,
    LayoutVersionSource,
    LayoutVersionStatus,
    WorkloadUnit,
)
from app.models.supervisor_assignment import (
    LayoutSupervisorAssignment,
    SupervisorAssignmentStatus,
)
from app.models.user import User, UserRole, UserStatus
from app.services.progress_service import AuthoritativeProgressService


def _get_auth_headers(client: TestClient, username: str, password: str = "password123"):
    res = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def domain_completeness_fixture(db: Session):
    suffix = uuid.uuid4().hex[:6]

    deputy = User(
        name="Deputy Completeness",
        username=f"dep_comp_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor = User(
        name="Supervisor Completeness",
        username=f"sup_comp_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enumerator = User(
        name="Enumerator Completeness",
        username=f"enum_comp_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all([deputy, supervisor, enumerator])
    db.commit()

    poly_wkt = "MULTIPOLYGON(((77.0 11.0, 77.01 11.0, 77.01 11.01, 77.0 11.01, 77.0 11.0)))"
    area = AdministrativeArea(
        name=f"Completeness Area {suffix}",
        type=AreaType.VILLAGE,
        code=f"COMP-{suffix}",
        boundary=WKTElement(poly_wkt, srid=4326),
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    layout = Layout(
        area_id=area.id,
        name=f"Layout Completeness {suffix}",
        status=LayoutStatus.APPROVED,
        boundary=WKTElement(poly_wkt, srid=4326),
    )
    db.add(layout)
    db.commit()
    db.refresh(layout)

    layout_version = LayoutVersion(
        layout_id=layout.id,
        version_number=1,
        source=LayoutVersionSource.APPROVED,
        status=LayoutVersionStatus.APPROVED,
        workload_unit=WorkloadUnit.CENSUS_HOUSES,
        target_workload=150,
        estimated_census_house_count=350,
        estimated_population=1350,
    )
    db.add(layout_version)
    db.commit()
    db.refresh(layout_version)

    hlb = HouselistingBlock(
        layout_id=layout.id,
        version_id=layout_version.id,
        block_code=f"HLB-COMP-{suffix}",
        name=f"Block Completeness {suffix}",
        boundary=WKTElement(poly_wkt, srid=4326),
        status=HlbStatus.ASSIGNED,
        target_building_count=150,
        estimated_census_house_count=150,
        estimated_population=600,
    )
    db.add(hlb)
    db.commit()
    db.refresh(hlb)

    assignment = HlbEnumeratorAssignment(
        hlb_id=hlb.id,
        layout_id=layout.id,
        enumerator_id=enumerator.id,
        supervisor_id=supervisor.id,
        status=EnumeratorAssignmentStatus.ACTIVE,
    )
    db.add(assignment)

    sup_assignment = LayoutSupervisorAssignment(
        layout_id=layout.id,
        supervisor_id=supervisor.id,
        assigned_by=deputy.id,
        status=SupervisorAssignmentStatus.ACTIVE,
    )
    db.add(sup_assignment)
    db.commit()

    house = House(
        area_id=area.id,
        building_reference=f"BLD-COMP-{suffix}",
        latitude=11.005,
        longitude=77.005,
        location=WKTElement("POINT(77.005 11.005)", srid=4326),
        field_status=BuildingFieldStatus.CONFIRMED,
    )
    db.add(house)
    db.commit()
    db.refresh(house)
    db.add(HlbHouse(hlb_id=hlb.id, house_id=house.id))
    db.commit()

    return {
        "deputy": deputy,
        "supervisor": supervisor,
        "enumerator": enumerator,
        "area": area,
        "layout": layout,
        "layout_version": layout_version,
        "hlb": hlb,
        "assignment": assignment,
        "house": house,
    }


def test_shared_progress_json_vectors():
    """Requirement A4: Verify all cases in progress_test_vectors.json against backend AuthoritativeProgressService."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "progress_test_vectors.json")
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    test_cases = data.get("test_cases", [])
    assert len(test_cases) == 7, f"Expected 7 test cases, got {len(test_cases)}"

    for tc in test_cases:
        tc_id = tc["id"]
        buildings = tc["buildings"]
        expected = tc["expected"]

        res = AuthoritativeProgressService.calculate_authoritative_progress(buildings)

        assert res["total_eligible_buildings"] == expected["total_eligible_buildings"], (
            f"Case {tc_id} failed on total_eligible_buildings"
        )
        assert res["completed_buildings"] == expected["completed_buildings"], (
            f"Case {tc_id} failed on completed_buildings"
        )
        assert res["pending_buildings"] == expected["pending_buildings"], (
            f"Case {tc_id} failed on pending_buildings"
        )
        assert res["resolved_census_houses"] == expected["resolved_census_houses"], (
            f"Case {tc_id} failed on resolved_census_houses"
        )
        assert res["locked_census_houses"] == expected["locked_census_houses"], (
            f"Case {tc_id} failed on locked_census_houses"
        )
        assert res["unresolved_census_houses"] == expected["unresolved_census_houses"], (
            f"Case {tc_id} failed on unresolved_census_houses"
        )
        assert pytest.approx(res["completion_percentage"], 0.01) == expected["completion_percentage"], (
            f"Case {tc_id} failed on completion_percentage"
        )


def test_sync_v2_duplicate_prevention(client: TestClient, db: Session, domain_completeness_fixture):
    """Requirement B1: Operations with identical (device_id, entity_type, local_entity_id) must not create duplicate entities."""
    data = domain_completeness_fixture
    headers = _get_auth_headers(client, data["enumerator"].username)
    hlb_id = str(data["hlb"].id)
    device_id = f"device-test-{uuid.uuid4().hex[:6]}"
    local_id = f"local-hh-{uuid.uuid4().hex[:6]}"

    payload_base = {
        "hlb_id": hlb_id,
        "building_id": str(data["house"].id),
        "census_house_id": str(uuid.uuid4()),
        "household_number": "HH-01",
        "head_name": "Test Household Head",
        "total_members": 4,
        "male_count": 2,
        "female_count": 2,
        "transgender_count": 0,
        "status": "COMPLETED",
    }

    # First sync push
    batch_1 = {
        "device_id": device_id,
        "operations": [
            {
                "idempotency_key": f"key-1-{uuid.uuid4().hex[:6]}",
                "local_entity_id": local_id,
                "entity_type": "HOUSEHOLD",
                "operation_type": "CREATE",
                "client_timestamp": datetime.now(UTC).isoformat(),
                "payload": payload_base,
            }
        ],
    }
    res1 = client.post("/api/v1/sync", json=batch_1, headers=headers)
    assert res1.status_code == 200, res1.text
    r1_json = res1.json()
    assert r1_json["success_count"] == 1
    op1_result = r1_json["results"][0]
    server_entity_id = op1_result["server_entity_id"]
    assert server_entity_id is not None

    # Second sync push (same device_id and local_entity_id, different idempotency_key e.g. double tap)
    batch_2 = {
        "device_id": device_id,
        "operations": [
            {
                "idempotency_key": f"key-2-{uuid.uuid4().hex[:6]}",
                "local_entity_id": local_id,
                "entity_type": "HOUSEHOLD",
                "operation_type": "CREATE",
                "client_timestamp": datetime.now(UTC).isoformat(),
                "payload": payload_base,
            }
        ],
    }
    res2 = client.post("/api/v1/sync", json=batch_2, headers=headers)
    assert res2.status_code == 200, res2.text
    r2_json = res2.json()
    op2_result = r2_json["results"][0]

    # Must return the existing entity and NOT insert duplicate row
    assert op2_result["server_entity_id"] == server_entity_id

    records = db.query(HouseholdRecord).filter(
        HouseholdRecord.hlb_id == data["hlb"].id,
        HouseholdRecord.household_number == "HH-01"
    ).all()
    assert len(records) == 1, f"Expected exactly 1 household record, found {len(records)}"


def test_sync_v2_unassignment_quarantine(client: TestClient, db: Session, domain_completeness_fixture):
    """Requirement B2: Client operations created after assignment deactivation must enter QUARANTINE."""
    data = domain_completeness_fixture
    headers = _get_auth_headers(client, data["enumerator"].username)
    hlb_id = str(data["hlb"].id)
    device_id = f"device-quarantine-{uuid.uuid4().hex[:6]}"

    # Deactivate enumerator assignment at reference time T
    t_unassign = datetime.now(UTC) - timedelta(minutes=10)
    assignment = data["assignment"]
    assignment.status = EnumeratorAssignmentStatus.CANCELLED
    assignment.updated_at = t_unassign
    db.commit()

    # Op 1: client_timestamp is 15 minutes before T (valid offline work before unassignment)
    t_valid = t_unassign - timedelta(minutes=15)
    # Op 2: client_timestamp is 5 minutes after T (work done after unassignment -> quarantine)
    t_invalid = t_unassign + timedelta(minutes=5)

    batch = {
        "device_id": device_id,
        "operations": [
            {
                "idempotency_key": f"key-valid-{uuid.uuid4().hex[:6]}",
                "local_entity_id": f"loc-val-{uuid.uuid4().hex[:6]}",
                "entity_type": "HOUSEHOLD",
                "operation_type": "CREATE",
                "client_timestamp": t_valid.isoformat(),
                "payload": {
                    "hlb_id": hlb_id,
                    "building_id": str(data["house"].id),
                    "census_house_id": str(uuid.uuid4()),
                    "household_number": "HH-VALID",
                    "head_name": "Valid Head",
                    "total_members": 2,
                    "male_count": 1,
                    "female_count": 1,
                    "transgender_count": 0,
                    "status": "COMPLETED",
                },
            },
            {
                "idempotency_key": f"key-invalid-{uuid.uuid4().hex[:6]}",
                "local_entity_id": f"loc-inval-{uuid.uuid4().hex[:6]}",
                "entity_type": "HOUSEHOLD",
                "operation_type": "CREATE",
                "client_timestamp": t_invalid.isoformat(),
                "payload": {
                    "hlb_id": hlb_id,
                    "building_id": str(data["house"].id),
                    "census_house_id": str(uuid.uuid4()),
                    "household_number": "HH-INVALID",
                    "head_name": "Invalid Head",
                    "total_members": 2,
                    "male_count": 1,
                    "female_count": 1,
                    "transgender_count": 0,
                    "status": "COMPLETED",
                },
            },
        ],
    }

    res = client.post("/api/v1/sync", json=batch, headers=headers)
    assert res.status_code == 200, res.text
    r_json = res.json()
    assert r_json["success_count"] == 1
    assert r_json["failed_count"] == 0

    results = {r["local_entity_id"]: r for r in r_json["results"]}
    val_op = results[batch["operations"][0]["local_entity_id"]]
    inval_op = results[batch["operations"][1]["local_entity_id"]]

    assert val_op["status"] == "SUCCESS"
    assert inval_op["status"] == "QUARANTINE"
    assert "after unassignment" in inval_op["error_message"].lower() or "unassigned" in inval_op["error_message"].lower()


def test_supervisor_quarantine_review_and_listing(client: TestClient, db: Session, domain_completeness_fixture):
    """Requirement B3: Supervisor can list and review (approve/reject) quarantined sync operations."""
    data = domain_completeness_fixture
    sup_headers = _get_auth_headers(client, data["supervisor"].username)

    # Insert a quarantined sync operation
    op = SyncOperation(
        device_id="dev-q-rev",
        user_id=data["enumerator"].id,
        idempotency_key=str(uuid.uuid4()),
        local_entity_id="loc-q-rev",
        entity_type=SyncEntityType.HOUSEHOLD,
        operation_type=SyncOperationType.CREATE,
        entity_id="loc-q-rev",
        client_timestamp=datetime.now(UTC),
        payload={
            "hlb_id": str(data["hlb"].id),
            "building_id": str(data["house"].id),
            "census_house_id": str(uuid.uuid4()),
            "household_number": "HH-Q-REV",
            "head_name": "Quarantine Head",
            "total_members": 2,
            "male_count": 1,
            "female_count": 1,
            "transgender_count": 0,
            "status": "COMPLETED",
        },
        status=SyncOperationStatus.QUARANTINE,
        error_message="ENUMERATOR_UNASSIGNED_PRIOR_TO_OPERATION",
    )
    db.add(op)
    db.commit()
    db.refresh(op)

    # Supervisor lists quarantined operations
    list_res = client.get("/api/v1/supervisor/quarantined-operations", headers=sup_headers)
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    found = [it for it in items if it["id"] == str(op.id)]
    assert len(found) == 1
    assert found[0]["status"] == "QUARANTINE"

    # Supervisor approves quarantined operation
    rev_res = client.post(
        f"/api/v1/supervisor/quarantined-operations/{op.id}/review",
        json={"approved": True, "reason": "Approved after field verification with enumerator"},
        headers=sup_headers,
    )
    assert rev_res.status_code == 200
    rev_json = rev_res.json()
    assert rev_json["status"] in ("SYNCED", "APPLIED")

    db.refresh(op)
    assert op.status == SyncOperationStatus.SYNCED


def test_supervisor_versioned_correction(client: TestClient, db: Session, domain_completeness_fixture):
    """Requirement D3: Supervisor corrections must be non-destructive and versioned."""
    data = domain_completeness_fixture
    sup_headers = _get_auth_headers(client, data["supervisor"].username)

    # Create original household record
    orig_record = HouseholdRecord(
        hlb_id=data["hlb"].id,
        house_id=data["house"].id,
        enumerator_id=data["enumerator"].id,
        census_house_id=uuid.uuid4(),
        household_number="HH-CORR-1",
        head_name="Original Head",
        total_members=4,
        male_count=2,
        female_count=2,
        status=HouseholdRecordStatus.COMPLETED,
        review_state=HouseholdReviewState.SUBMITTED,
    )
    db.add(orig_record)
    db.commit()
    db.refresh(orig_record)

    # Supervisor submits correction
    corr_payload = {
        "entity_type": "HOUSEHOLD",
        "entity_id": str(orig_record.id),
        "corrected_data": {
            "household_number": "HH-CORR-1",
            "total_members": 5,
            "male_count": 2,
            "female_count": 3,
        },
        "reason": "Found uncounted infant girl during verification sample",
    }
    res = client.post("/api/v1/supervisor/corrections", json=corr_payload, headers=sup_headers)
    assert res.status_code == 200, res.text
    corr_json = res.json()
    assert corr_json["id"] is not None

    # Verify original record remains intact and not overwritten
    db.refresh(orig_record)
    assert orig_record.total_members == 4, "Original record must remain unmodified"

    # Verify correction record exists in database
    correction = db.query(SupervisorCorrection).filter(
        SupervisorCorrection.entity_id == orig_record.id
    ).first()
    assert correction is not None
    assert correction.author_id == data["supervisor"].id
    assert correction.correction_reason == "Found uncounted infant girl during verification sample"
    assert correction.corrected_data["total_members"] == 5


def test_hlb_atomic_counter_allocation(client: TestClient, db: Session, domain_completeness_fixture):
    """Requirement C1: Atomic sequence allocator for building and census house numbering."""
    data = domain_completeness_fixture
    enum_headers = _get_auth_headers(client, data["enumerator"].username)
    hlb_id = str(data["hlb"].id)

    # Allocate batch 1: 5 buildings, 10 census houses
    req1 = {"hlb_id": hlb_id, "building_count": 5, "census_house_count": 10}
    res1 = client.post("/api/v1/counters/allocate", json=req1, headers=enum_headers)
    assert res1.status_code == 200, res1.text
    j1 = res1.json()
    assert j1["building_number_start"] == 1
    assert j1["building_number_end"] == 5
    assert j1["census_house_number_start"] == 1
    assert j1["census_house_number_end"] == 10

    # Allocate batch 2: 3 buildings, 5 census houses
    req2 = {"hlb_id": hlb_id, "building_count": 3, "census_house_count": 5}
    res2 = client.post("/api/v1/counters/allocate", json=req2, headers=enum_headers)
    assert res2.status_code == 200, res2.text
    j2 = res2.json()
    assert j2["building_number_start"] == 6
    assert j2["building_number_end"] == 8
    assert j2["census_house_number_start"] == 11
    assert j2["census_house_number_end"] == 15

    # Verify counter in database
    counter = db.query(HlbCounter).filter(HlbCounter.hlb_id == data["hlb"].id).first()
    assert counter is not None
    assert counter.next_building_no == 9
    assert counter.next_census_house_no == 16


def test_review_workflow_and_deputy_accepted_totals(client: TestClient, db: Session, domain_completeness_fixture):
    """Requirement D1 & D2: Review workflow transitions and deputy accepted census totals isolation."""
    data = domain_completeness_fixture
    deputy_headers = _get_auth_headers(client, data["deputy"].username)
    sup_headers = _get_auth_headers(client, data["supervisor"].username)
    area_id = str(data["area"].id)

    # Record 1: ACCEPTED (4 persons, 2 male, 2 female)
    rec1 = HouseholdRecord(
        hlb_id=data["hlb"].id,
        house_id=data["house"].id,
        enumerator_id=data["enumerator"].id,
        census_house_id=uuid.uuid4(),
        household_number="HH-ACC-1",
        head_name="Head Acc",
        total_members=4,
        male_count=2,
        female_count=2,
        status=HouseholdRecordStatus.COMPLETED,
        review_state=HouseholdReviewState.ACCEPTED,
    )
    # Record 2: SUBMITTED (3 persons) -> must be IGNORED by accepted totals
    rec2 = HouseholdRecord(
        hlb_id=data["hlb"].id,
        house_id=data["house"].id,
        enumerator_id=data["enumerator"].id,
        census_house_id=uuid.uuid4(),
        household_number="HH-SUB-2",
        head_name="Head Sub",
        total_members=3,
        male_count=1,
        female_count=2,
        status=HouseholdRecordStatus.COMPLETED,
        review_state=HouseholdReviewState.SUBMITTED,
    )
    # Record 3: SUPERVISOR_VERIFIED (5 persons) -> must be IGNORED by accepted totals until Deputy accepts
    rec3 = HouseholdRecord(
        hlb_id=data["hlb"].id,
        house_id=data["house"].id,
        enumerator_id=data["enumerator"].id,
        census_house_id=uuid.uuid4(),
        household_number="HH-VER-3",
        head_name="Head Ver",
        total_members=5,
        male_count=3,
        female_count=2,
        status=HouseholdRecordStatus.COMPLETED,
        review_state=HouseholdReviewState.SUPERVISOR_VERIFIED,
    )
    db.add_all([rec1, rec2, rec3])
    db.commit()

    # Deputy calls accepted census totals
    res_tot1 = client.get(f"/api/v1/deputy/accepted-census-totals?area_id={area_id}", headers=deputy_headers)
    assert res_tot1.status_code == 200, res_tot1.text
    j_tot1 = res_tot1.json()
    assert j_tot1["accepted_households"] == 1
    assert j_tot1["accepted_population"] == 4
    assert j_tot1["male_population"] == 2
    assert j_tot1["female_population"] == 2

    # Deputy accepts Record 3 (transition from SUPERVISOR_VERIFIED to ACCEPTED)
    accept_res = client.post(
        f"/api/v1/deputy/records/{rec3.id}/accept",
        headers=deputy_headers
    )
    assert accept_res.status_code == 200
    db.refresh(rec3)
    assert rec3.review_state == HouseholdReviewState.ACCEPTED

    # Deputy calls accepted census totals again -> now reflects rec1 + rec3 (1 + 1 = 2 households, 4 + 5 = 9 persons)
    res_tot2 = client.get(f"/api/v1/deputy/accepted-census-totals?area_id={area_id}", headers=deputy_headers)
    assert res_tot2.status_code == 200
    j_tot2 = res_tot2.json()
    assert j_tot2["accepted_households"] == 2
    assert j_tot2["accepted_population"] == 9
    assert j_tot2["male_population"] == 5
    assert j_tot2["female_population"] == 4


def test_change_request_execution_and_message_threads(client: TestClient, db: Session, domain_completeness_fixture):
    """Requirement D4 & D5: Change request resolution execution and threaded communication."""
    data = domain_completeness_fixture
    deputy_headers = _get_auth_headers(client, data["deputy"].username)
    sup_headers = _get_auth_headers(client, data["supervisor"].username)

    # Supervisor submits change request
    req_payload = {
        "layout_id": str(data["layout"].id),
        "hlb_id": str(data["hlb"].id),
        "request_type": "EXTRA_ENUMERATOR",
        "description": "High building count requires second enumerator to meet census deadline",
    }
    cr_res = client.post("/api/v1/supervisor/change-requests", json=req_payload, headers=sup_headers)
    assert cr_res.status_code == 200, cr_res.text
    cr_id = cr_res.json()["id"]

    # Deputy posts a message in the change request thread
    msg_res = client.post(
        f"/api/v1/deputy/change-requests/{cr_id}/messages",
        json={"message": "Please verify if the neighboring block enumerator is available."},
        headers=deputy_headers,
    )
    assert msg_res.status_code == 200, msg_res.text
    assert msg_res.json()["message"] == "Please verify if the neighboring block enumerator is available."

    # List messages
    list_msg = client.get(f"/api/v1/deputy/change-requests/{cr_id}/messages", headers=deputy_headers)
    assert list_msg.status_code == 200
    messages = list_msg.json()["items"]
    assert len(messages) == 1
    assert messages[0]["message"] == "Please verify if the neighboring block enumerator is available."

    # Deputy resolves the change request
    resolve_res = client.post(
        f"/api/v1/deputy/change-requests/{cr_id}/resolve",
        json={"status": "RESOLVED", "resolution_notes": "Approved additional enumerator assignment"},
        headers=deputy_headers,
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "RESOLVED"


def test_rbac_security_boundaries(client: TestClient, domain_completeness_fixture):
    """Requirement: Enforce strict role-based access control and reject unauthenticated / unauthorized calls."""
    data = domain_completeness_fixture
    enum_headers = _get_auth_headers(client, data["enumerator"].username)
    area_id = str(data["area"].id)

    # 1. Unauthenticated requests must receive 401
    unauth_tot = client.get(f"/api/v1/deputy/accepted-census-totals?area_id={area_id}")
    assert unauth_tot.status_code == 401

    unauth_quarantine = client.get("/api/v1/supervisor/quarantined-operations")
    assert unauth_quarantine.status_code == 401

    # 2. Enumerator attempting to access Deputy endpoints must receive 403 Forbidden
    enum_dep = client.get(f"/api/v1/deputy/accepted-census-totals?area_id={area_id}", headers=enum_headers)
    assert enum_dep.status_code == 403

    # 3. Enumerator attempting to access Supervisor quarantined operations must receive 403 Forbidden
    enum_sup = client.get("/api/v1/supervisor/quarantined-operations", headers=enum_headers)
    assert enum_sup.status_code == 403
