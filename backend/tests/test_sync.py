import uuid
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.administrative_area import AdministrativeArea, AreaType
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
    RevisitRecord,
)
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import BuildingSourceType, House
from app.models.layout import (
    Layout,
    LayoutStatus,
    LayoutVersion,
    LayoutVersionSource,
    LayoutVersionStatus,
)
from app.models.supervisor_assignment import (
    LayoutSupervisorAssignment,
    SupervisorAssignmentStatus,
)
from app.models.user import User, UserRole, UserStatus


@pytest.fixture
def sync_test_data(db: Session):
    suffix = uuid.uuid4().hex[:6]

    # Users
    deputy = User(
        name="Deputy Sync",
        username=f"deputy_sync_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor = User(
        name="Supervisor Sync",
        username=f"sup_sync_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enum_1 = User(
        name="Enumerator 1",
        username=f"enum_sync_1_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    enum_2 = User(
        name="Enumerator 2",
        username=f"enum_sync_2_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )

    db.add_all([deputy, supervisor, enum_1, enum_2])
    db.commit()

    # Area & Layout
    poly_wkt = "MULTIPOLYGON(((80.0 13.0, 80.1 13.0, 80.1 13.1, 80.0 13.1, 80.0 13.0)))"
    area = AdministrativeArea(
        name=f"Sync Ward {suffix}",
        code=f"SYNC_{suffix.upper()}",
        type=AreaType.WARD,
        boundary=WKTElement(poly_wkt, srid=4326),
    )
    db.add(area)
    db.commit()

    now = datetime.now(UTC)
    layout = Layout(
        area_id=area.id,
        name=f"Layout Sync {suffix}",
        target_hlb_building_count=100,
        actual_building_count=20,
        expected_hlb_count=2,
        boundary=area.boundary,
        status=LayoutStatus.ASSIGNED,
        created_by=deputy.id,
        approved_by=deputy.id,
        approved_at=now,
    )
    db.add(layout)
    db.commit()

    version = LayoutVersion(
        layout_id=layout.id,
        version_number=1,
        source=LayoutVersionSource.APPROVED,
        status=LayoutVersionStatus.APPROVED,
        target_buildings_per_hlb=100,
        hlb_count=2,
        total_buildings=20,
        quality_score=95.0,
        validation_status="VALID",
        created_by=deputy.id,
    )
    db.add(version)
    db.commit()

    layout.active_version_id = version.id
    db.commit()

    # Supervisor Assignment
    sup_assign = LayoutSupervisorAssignment(
        layout_id=layout.id,
        supervisor_id=supervisor.id,
        assigned_by=deputy.id,
        assigned_at=now,
        status=SupervisorAssignmentStatus.ACTIVE,
    )
    db.add(sup_assign)
    db.commit()

    # HLB 1 (Assigned to enum_1)
    hlb_poly_1 = (
        "MULTIPOLYGON(((80.0 13.0, 80.05 13.0, 80.05 13.05, 80.0 13.05, 80.0 13.0)))"
    )
    hlb_1 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code="HLB-SYNC-001",
        name="Block Sync 1",
        target_building_count=10,
        actual_building_count=2,
        boundary=WKTElement(hlb_poly_1, srid=4326),
    )
    # HLB 2 (Assigned to enum_2)
    hlb_poly_2 = (
        "MULTIPOLYGON(((80.05 13.0, 80.1 13.0, 80.1 13.05, 80.05 13.05, 80.05 13.0)))"
    )
    hlb_2 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code="HLB-SYNC-002",
        name="Block Sync 2",
        target_building_count=10,
        actual_building_count=1,
        boundary=WKTElement(hlb_poly_2, srid=4326),
    )
    db.add_all([hlb_1, hlb_2])
    db.commit()

    # Enumerator Assignments
    assign_1 = HlbEnumeratorAssignment(
        hlb_id=hlb_1.id,
        layout_id=layout.id,
        enumerator_id=enum_1.id,
        supervisor_id=supervisor.id,
        assigned_at=now,
        status=EnumeratorAssignmentStatus.ACTIVE,
    )
    assign_2 = HlbEnumeratorAssignment(
        hlb_id=hlb_2.id,
        layout_id=layout.id,
        enumerator_id=enum_2.id,
        supervisor_id=supervisor.id,
        assigned_at=now,
        status=EnumeratorAssignmentStatus.ACTIVE,
    )
    db.add_all([assign_1, assign_2])
    db.commit()

    # Buildings
    house_1 = House(
        area_id=area.id,
        building_reference="BLD-S-101",
        house_number="101",
        latitude=13.01,
        longitude=80.01,
        location=WKTElement("POINT(80.01 13.01)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    house_2 = House(
        area_id=area.id,
        building_reference="BLD-S-102",
        house_number="102",
        latitude=13.02,
        longitude=80.02,
        location=WKTElement("POINT(80.02 13.02)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    house_3 = House(
        area_id=area.id,
        building_reference="BLD-S-201",
        house_number="201",
        latitude=13.06,
        longitude=80.06,
        location=WKTElement("POINT(80.06 13.06)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    db.add_all([house_1, house_2, house_3])
    db.commit()

    # Link Houses to HLBs
    db.add_all(
        [
            HlbHouse(hlb_id=hlb_1.id, house_id=house_1.id),
            HlbHouse(hlb_id=hlb_1.id, house_id=house_2.id),
            HlbHouse(hlb_id=hlb_2.id, house_id=house_3.id),
        ]
    )
    db.commit()

    return {
        "deputy": deputy,
        "supervisor": supervisor,
        "enum_1": enum_1,
        "enum_2": enum_2,
        "hlb_1": hlb_1,
        "hlb_2": hlb_2,
        "house_1": house_1,
        "house_2": house_2,
        "house_3": house_3,
    }


def _get_auth_headers(client: TestClient, username: str) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_sync_household_create_success(client: TestClient, db: Session, sync_test_data):
    enum_1 = sync_test_data["enum_1"]
    hlb_1 = sync_test_data["hlb_1"]
    house_1 = sync_test_data["house_1"]

    headers = _get_auth_headers(client, enum_1.username)

    idempotency_key = f"idem-{uuid.uuid4()}"
    now_iso = datetime.now(UTC).isoformat()

    payload = {
        "device_id": "test-device-123",
        "operations": [
            {
                "idempotency_key": idempotency_key,
                "operation_type": "CREATE",
                "entity_type": "HOUSEHOLD",
                "local_entity_id": "hh-local-1",
                "client_timestamp": now_iso,
                "version": 1,
                "payload": {
                    "hlb_id": str(hlb_1.id),
                    "building_id": str(house_1.id),
                    "household_number": "HH-1",
                    "head_name": "Ravi Kumar",
                    "total_members": 4,
                    "male_count": 2,
                    "female_count": 2,
                    "transgender_count": 0,
                    "ownership_status": "OWNED",
                    "drinking_water_source": "Tap Water",
                    "lighting_source": "Electricity",
                    "latrine_facility": "Yes",
                    "status": "COMPLETED",
                },
            }
        ],
    }

    res = client.post("/api/v1/sync", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["processed_count"] == 1
    assert data["success_count"] == 1
    assert data["failed_count"] == 0

    result = data["results"][0]
    assert result["idempotency_key"] == idempotency_key
    assert result["status"] == "SUCCESS"
    assert result["server_entity_id"] is not None

    server_hh_id = UUID(result["server_entity_id"])
    db_hh = db.query(HouseholdRecord).filter(HouseholdRecord.id == server_hh_id).first()
    assert db_hh is not None
    assert db_hh.head_name == "Ravi Kumar"
    assert db_hh.total_members == 4
    assert db_hh.status == HouseholdRecordStatus.COMPLETED

    # Verify building fieldwork status was created
    fw_status = (
        db.query(HouseFieldworkStatus)
        .filter(
            HouseFieldworkStatus.house_id == house_1.id,
            HouseFieldworkStatus.hlb_id == hlb_1.id,
        )
        .first()
    )
    assert fw_status is not None
    assert fw_status.status == FieldworkBuildingStatus.COMPLETED


def test_sync_idempotency_replay(client: TestClient, db: Session, sync_test_data):
    enum_1 = sync_test_data["enum_1"]
    hlb_1 = sync_test_data["hlb_1"]
    house_1 = sync_test_data["house_1"]

    headers = _get_auth_headers(client, enum_1.username)
    idempotency_key = f"idem-replay-{uuid.uuid4()}"
    now_iso = datetime.now(UTC).isoformat()

    payload = {
        "device_id": "test-device-123",
        "operations": [
            {
                "idempotency_key": idempotency_key,
                "operation_type": "CREATE",
                "entity_type": "HOUSEHOLD",
                "local_entity_id": "hh-local-replay",
                "client_timestamp": now_iso,
                "version": 1,
                "payload": {
                    "hlb_id": str(hlb_1.id),
                    "building_id": str(house_1.id),
                    "household_number": "HH-2",
                    "head_name": "Lakshmi Narayanan",
                    "total_members": 3,
                    "male_count": 1,
                    "female_count": 2,
                    "transgender_count": 0,
                    "ownership_status": "RENTED",
                    "status": "COMPLETED",
                },
            }
        ],
    }

    # Request 1
    res1 = client.post("/api/v1/sync", json=payload, headers=headers)
    assert res1.status_code == 200
    res1_data = res1.json()
    server_id_1 = res1_data["results"][0]["server_entity_id"]

    # Request 2 (Identical retry with same idempotency key)
    res2 = client.post("/api/v1/sync", json=payload, headers=headers)
    assert res2.status_code == 200
    res2_data = res2.json()
    server_id_2 = res2_data["results"][0]["server_entity_id"]

    assert server_id_1 == server_id_2

    # Verify ONLY 1 record exists in database
    records = (
        db.query(HouseholdRecord)
        .filter(
            HouseholdRecord.house_id == house_1.id,
            HouseholdRecord.household_number == "HH-2",
        )
        .all()
    )
    assert len(records) == 1


def test_sync_unauthorized_hlb_rejected(client: TestClient, sync_test_data):
    enum_1 = sync_test_data["enum_1"]
    hlb_2 = sync_test_data["hlb_2"]  # Assigned to enum_2, not enum_1
    house_3 = sync_test_data["house_3"]

    headers = _get_auth_headers(client, enum_1.username)
    idempotency_key = f"idem-unauth-{uuid.uuid4()}"

    payload = {
        "operations": [
            {
                "idempotency_key": idempotency_key,
                "operation_type": "CREATE",
                "entity_type": "HOUSEHOLD",
                "local_entity_id": "hh-unauth",
                "client_timestamp": datetime.now(UTC).isoformat(),
                "payload": {
                    "hlb_id": str(hlb_2.id),
                    "building_id": str(house_3.id),
                    "household_number": "HH-1",
                    "head_name": "Intruder Attempt",
                    "total_members": 1,
                    "male_count": 1,
                    "female_count": 0,
                    "transgender_count": 0,
                },
            }
        ],
    }

    res = client.post("/api/v1/sync", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["failed_count"] == 1
    assert data["results"][0]["status"] == "FAILED"
    assert "Unauthorized" in data["results"][0]["error_message"]


def test_sync_household_demographic_arithmetic_validation(
    client: TestClient, sync_test_data
):
    enum_1 = sync_test_data["enum_1"]
    hlb_1 = sync_test_data["hlb_1"]
    house_1 = sync_test_data["house_1"]

    headers = _get_auth_headers(client, enum_1.username)
    idempotency_key = f"idem-arith-{uuid.uuid4()}"

    payload = {
        "operations": [
            {
                "idempotency_key": idempotency_key,
                "operation_type": "CREATE",
                "entity_type": "HOUSEHOLD",
                "local_entity_id": "hh-arith-fail",
                "client_timestamp": datetime.now(UTC).isoformat(),
                "payload": {
                    "hlb_id": str(hlb_1.id),
                    "building_id": str(house_1.id),
                    "household_number": "HH-3",
                    "head_name": "Invalid Counts",
                    "total_members": 5,
                    "male_count": 2,
                    "female_count": 1,  # 2 + 1 = 3 != 5
                    "transgender_count": 0,
                },
            }
        ],
    }

    res = client.post("/api/v1/sync", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["failed_count"] == 1
    assert "Sum of male" in data["results"][0]["error_message"]


def test_sync_household_update_and_conflict(
    client: TestClient, db: Session, sync_test_data
):
    enum_1 = sync_test_data["enum_1"]
    hlb_1 = sync_test_data["hlb_1"]
    house_1 = sync_test_data["house_1"]

    headers = _get_auth_headers(client, enum_1.username)

    # 1. Create initial record
    create_key = f"idem-upd-create-{uuid.uuid4()}"
    client.post(
        "/api/v1/sync",
        json={
            "operations": [
                {
                    "idempotency_key": create_key,
                    "operation_type": "CREATE",
                    "entity_type": "HOUSEHOLD",
                    "local_entity_id": "hh-upd-1",
                    "client_timestamp": datetime.now(UTC).isoformat(),
                    "payload": {
                        "hlb_id": str(hlb_1.id),
                        "building_id": str(house_1.id),
                        "household_number": "HH-4",
                        "head_name": "Initial Name",
                        "total_members": 2,
                        "male_count": 1,
                        "female_count": 1,
                        "transgender_count": 0,
                    },
                }
            ]
        },
        headers=headers,
    )

    db_hh = (
        db.query(HouseholdRecord)
        .filter(
            HouseholdRecord.house_id == house_1.id,
            HouseholdRecord.household_number == "HH-4",
        )
        .first()
    )
    assert db_hh is not None
    assert db_hh.version == 1

    # 2. Update with version=1 -> should succeed and increment to version=2
    update_key_1 = f"idem-upd-1-{uuid.uuid4()}"
    res_upd = client.post(
        "/api/v1/sync",
        json={
            "operations": [
                {
                    "idempotency_key": update_key_1,
                    "operation_type": "UPDATE",
                    "entity_type": "HOUSEHOLD",
                    "local_entity_id": "hh-upd-1",
                    "server_entity_id": str(db_hh.id),
                    "version": 1,
                    "client_timestamp": datetime.now(UTC).isoformat(),
                    "payload": {
                        "hlb_id": str(hlb_1.id),
                        "building_id": str(house_1.id),
                        "household_number": "HH-4",
                        "head_name": "Updated Name V2",
                        "total_members": 2,
                        "male_count": 1,
                        "female_count": 1,
                        "transgender_count": 0,
                    },
                }
            ]
        },
        headers=headers,
    )
    assert res_upd.status_code == 200
    assert res_upd.json()["success_count"] == 1
    assert res_upd.json()["results"][0]["version"] == 2

    # 3. Another client sends update with outdated version=1 -> should report CONFLICT
    conflict_key = f"idem-conflict-{uuid.uuid4()}"
    res_conflict = client.post(
        "/api/v1/sync",
        json={
            "operations": [
                {
                    "idempotency_key": conflict_key,
                    "operation_type": "UPDATE",
                    "entity_type": "HOUSEHOLD",
                    "local_entity_id": "hh-upd-1",
                    "server_entity_id": str(db_hh.id),
                    "version": 1,  # Stale version
                    "client_timestamp": datetime.now(UTC).isoformat(),
                    "payload": {
                        "hlb_id": str(hlb_1.id),
                        "building_id": str(house_1.id),
                        "household_number": "HH-4",
                        "head_name": "Stale Attempt",
                        "total_members": 2,
                        "male_count": 1,
                        "female_count": 1,
                        "transgender_count": 0,
                    },
                }
            ]
        },
        headers=headers,
    )
    assert res_conflict.status_code == 200
    conf_data = res_conflict.json()
    assert conf_data["conflict_count"] == 1
    assert conf_data["results"][0]["status"] == "CONFLICT"
    assert conf_data["results"][0]["conflict_data"] is not None


def test_sync_revisit_and_gps_log(client: TestClient, db: Session, sync_test_data):
    enum_1 = sync_test_data["enum_1"]
    hlb_1 = sync_test_data["hlb_1"]
    house_2 = sync_test_data["house_2"]

    headers = _get_auth_headers(client, enum_1.username)

    rev_key = f"idem-rev-{uuid.uuid4()}"
    gps_key = f"idem-gps-{uuid.uuid4()}"
    bld_key = f"idem-bld-{uuid.uuid4()}"
    now_iso = datetime.now(UTC).isoformat()

    payload = {
        "operations": [
            {
                "idempotency_key": rev_key,
                "operation_type": "CREATE",
                "entity_type": "REVISIT",
                "local_entity_id": "rev-local-1",
                "client_timestamp": now_iso,
                "payload": {
                    "hlb_id": str(hlb_1.id),
                    "building_id": str(house_2.id),
                    "reason": "LOCKED",
                    "notes": "Door locked during morning visit",
                },
            },
            {
                "idempotency_key": gps_key,
                "operation_type": "CREATE",
                "entity_type": "GPS_LOG",
                "local_entity_id": "gps-local-1",
                "client_timestamp": now_iso,
                "payload": {
                    "hlb_id": str(hlb_1.id),
                    "building_id": str(house_2.id),
                    "latitude": 13.021,
                    "longitude": 80.021,
                    "accuracy": 4.5,
                },
            },
            {
                "idempotency_key": bld_key,
                "operation_type": "STATUS_UPDATE",
                "entity_type": "BUILDING_STATUS",
                "local_entity_id": "bld-status-1",
                "client_timestamp": now_iso,
                "payload": {
                    "hlb_id": str(hlb_1.id),
                    "building_id": str(house_2.id),
                    "status": "REVISIT_REQUIRED",
                    "household_count": 0,
                },
            },
        ],
    }

    res = client.post("/api/v1/sync", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["processed_count"] == 3
    assert data["success_count"] == 3

    # Check revisit created in DB
    rev_db = (
        db.query(RevisitRecord)
        .filter(
            RevisitRecord.house_id == house_2.id,
            RevisitRecord.reason == "LOCKED",
        )
        .first()
    )
    assert rev_db is not None

    # Check GPS log created in DB
    gps_db = (
        db.query(GpsTrack)
        .filter(
            GpsTrack.house_id == house_2.id,
            GpsTrack.latitude == 13.021,
        )
        .first()
    )
    assert gps_db is not None
    assert gps_db.accuracy_meters == 4.5


def test_sync_non_enumerator_forbidden(client: TestClient, sync_test_data):
    supervisor = sync_test_data["supervisor"]
    headers = _get_auth_headers(client, supervisor.username)

    res = client.post("/api/v1/sync", json={"operations": []}, headers=headers)
    assert res.status_code == 403
    assert "Only authenticated Enumerators" in res.json()["detail"]


def test_sync_unauthenticated_rejected(client: TestClient):
    res = client.post("/api/v1/sync", json={"operations": []})
    assert res.status_code == 401
