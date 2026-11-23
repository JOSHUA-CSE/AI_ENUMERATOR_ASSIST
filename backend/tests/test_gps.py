import uuid
from datetime import UTC, datetime

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
from app.models.fieldwork import GpsTrack
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


def _get_auth_headers(client: TestClient, username: str) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def gps_test_data(db: Session):
    suffix = uuid.uuid4().hex[:6]

    deputy = User(
        name="Deputy GPS",
        username=f"deputy_gps_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor = User(
        name="Supervisor GPS",
        username=f"sup_gps_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enum_1 = User(
        name="Enumerator 1",
        username=f"enum_gps_1_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    enum_2 = User(
        name="Enumerator 2",
        username=f"enum_gps_2_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all([deputy, supervisor, enum_1, enum_2])
    db.commit()

    area = AdministrativeArea(
        name=f"GPS Ward {suffix}",
        code=f"GPS_{suffix.upper()}",
        type=AreaType.WARD,
        boundary=WKTElement(
            "MULTIPOLYGON(((80.0 13.0, 80.1 13.0, 80.1 13.1, 80.0 13.1, 80.0 13.0)))",
            srid=4326,
        ),
    )
    db.add(area)
    db.commit()

    now = datetime.now(UTC)
    layout = Layout(
        area_id=area.id,
        name=f"Layout GPS {suffix}",
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

    sup_assign = LayoutSupervisorAssignment(
        layout_id=layout.id,
        supervisor_id=supervisor.id,
        assigned_by=deputy.id,
        assigned_at=now,
        status=SupervisorAssignmentStatus.ACTIVE,
    )
    db.add(sup_assign)
    db.commit()

    # HLB 1 (lon: 80.0..80.05, lat: 13.0..13.05) assigned to enum_1
    wkt_hlb1 = (
        "MULTIPOLYGON(((80.0 13.0, 80.05 13.0, 80.05 13.05, 80.0 13.05, 80.0 13.0)))"
    )
    hlb_1 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code=f"HLB-GPS-1-{suffix}",
        name="Block GPS 1",
        target_building_count=10,
        actual_building_count=2,
        boundary=WKTElement(wkt_hlb1, srid=4326),
    )
    # HLB 2 (lon: 80.05..80.1, lat: 13.0..13.05) assigned to enum_2
    wkt_hlb2 = (
        "MULTIPOLYGON(((80.05 13.0, 80.1 13.0, 80.1 13.05, 80.05 13.05, 80.05 13.0)))"
    )
    hlb_2 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code=f"HLB-GPS-2-{suffix}",
        name="Block GPS 2",
        target_building_count=10,
        actual_building_count=1,
        boundary=WKTElement(wkt_hlb2, srid=4326),
    )
    db.add_all([hlb_1, hlb_2])
    db.commit()

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

    house_1 = House(
        area_id=area.id,
        building_reference="BLD-GPS-01",
        latitude=13.021,
        longitude=80.021,
        location=WKTElement("POINT(80.021 13.021)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    house_3 = House(
        area_id=area.id,
        building_reference="BLD-GPS-03",
        latitude=13.022,
        longitude=80.075,
        location=WKTElement("POINT(80.075 13.022)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    db.add_all([house_1, house_3])
    db.commit()

    hlb_h1 = HlbHouse(hlb_id=hlb_1.id, house_id=house_1.id)
    hlb_h3 = HlbHouse(hlb_id=hlb_2.id, house_id=house_3.id)
    db.add_all([hlb_h1, hlb_h3])
    db.commit()

    return {
        "deputy": deputy,
        "supervisor": supervisor,
        "enum_1": enum_1,
        "enum_2": enum_2,
        "hlb_1": hlb_1,
        "hlb_2": hlb_2,
        "house_1": house_1,
        "house_3": house_3,
    }


def test_record_gps_observation_success(client: TestClient, db: Session, gps_test_data):
    enum_1 = gps_test_data["enum_1"]
    hlb_1 = gps_test_data["hlb_1"]
    headers = _get_auth_headers(client, enum_1.username)

    obs_time = "2026-09-29T10:15:30Z"
    payload = {
        "latitude": 13.025,
        "longitude": 80.025,
        "accuracy_meters": 8.5,
        "timestamp": obs_time,
    }

    res = client.post(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/observation",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["hlb_id"] == str(hlb_1.id)
    assert data["enumerator_id"] == str(enum_1.id)
    assert data["latitude"] == 13.025
    assert data["longitude"] == 80.025
    assert data["accuracy_meters"] == 8.5
    assert data["source"] == "API"

    track_id = uuid.UUID(data["id"])
    track_db = db.query(GpsTrack).filter(GpsTrack.id == track_id).first()
    assert track_db is not None
    assert track_db.latitude == 13.025
    assert track_db.longitude == 80.025
    assert track_db.accuracy_meters == 8.5


def test_record_gps_observation_invalid_coordinates_and_accuracy(
    client: TestClient, gps_test_data
):
    enum_1 = gps_test_data["enum_1"]
    hlb_1 = gps_test_data["hlb_1"]
    headers = _get_auth_headers(client, enum_1.username)

    res_lat = client.post(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/observation",
        json={"latitude": 95.0, "longitude": 80.0, "accuracy_meters": 5.0},
        headers=headers,
    )
    assert res_lat.status_code == 422

    res_lon = client.post(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/observation",
        json={"latitude": 13.0, "longitude": 185.0, "accuracy_meters": 5.0},
        headers=headers,
    )
    assert res_lon.status_code == 422

    res_acc = client.post(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/observation",
        json={"latitude": 13.0, "longitude": 80.0, "accuracy_meters": -4.0},
        headers=headers,
    )
    assert res_acc.status_code == 422


def test_gps_observation_cross_enumerator_rejected(client: TestClient, gps_test_data):
    enum_1 = gps_test_data["enum_1"]
    hlb_2 = gps_test_data["hlb_2"]
    headers = _get_auth_headers(client, enum_1.username)

    payload = {"latitude": 13.025, "longitude": 80.075, "accuracy_meters": 10.0}

    res = client.post(
        f"/api/v1/enumerator/hlbs/{hlb_2.id}/gps/observation",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 403
    assert "not actively assigned" in res.json()["detail"].lower()


def test_gps_unauthenticated_and_role_rejection(client: TestClient, gps_test_data):
    hlb_1 = gps_test_data["hlb_1"]
    supervisor = gps_test_data["supervisor"]

    payload = {"latitude": 13.025, "longitude": 80.025}

    res_no_auth = client.post(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/observation",
        json=payload,
    )
    assert res_no_auth.status_code == 401

    sup_headers = _get_auth_headers(client, supervisor.username)
    res_sup = client.post(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/observation",
        json=payload,
        headers=sup_headers,
    )
    assert res_sup.status_code == 403


def test_gps_building_association_valid_and_invalid(client: TestClient, gps_test_data):
    enum_1 = gps_test_data["enum_1"]
    hlb_1 = gps_test_data["hlb_1"]
    house_1 = gps_test_data["house_1"]
    house_3 = gps_test_data["house_3"]
    headers = _get_auth_headers(client, enum_1.username)

    res_valid = client.post(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/observation",
        json={
            "latitude": 13.021,
            "longitude": 80.021,
            "accuracy_meters": 5.0,
            "building_id": str(house_1.id),
        },
        headers=headers,
    )
    assert res_valid.status_code == 200
    data_valid = res_valid.json()
    assert data_valid["house_id"] == str(house_1.id)

    res_invalid = client.post(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/observation",
        json={
            "latitude": 13.021,
            "longitude": 80.021,
            "accuracy_meters": 5.0,
            "building_id": str(house_3.id),
        },
        headers=headers,
    )
    assert res_invalid.status_code == 400
    assert "does not belong" in res_invalid.json()["detail"].lower()


def test_get_hlb_gps_status_and_boundary_evaluation(client: TestClient, gps_test_data):
    enum_1 = gps_test_data["enum_1"]
    hlb_1 = gps_test_data["hlb_1"]
    headers = _get_auth_headers(client, enum_1.username)

    res_init = client.get(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/status",
        headers=headers,
    )
    assert res_init.status_code == 200
    assert res_init.json()["total_observations"] == 0

    client.post(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/observation",
        json={"latitude": 13.025, "longitude": 80.025, "accuracy_meters": 10.0},
        headers=headers,
    )

    # Coordinate inside HLB
    res_inside = client.get(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/status"
        "?latitude=13.025&longitude=80.025&accuracy=5.0",
        headers=headers,
    )
    assert res_inside.status_code == 200
    data_inside = res_inside.json()
    assert data_inside["total_observations"] == 1
    assert data_inside["boundary_status"] == "INSIDE"

    # Coordinate outside HLB
    res_outside = client.get(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/status"
        "?latitude=13.07&longitude=80.07&accuracy=5.0",
        headers=headers,
    )
    assert res_outside.status_code == 200
    assert res_outside.json()["boundary_status"] == "OUTSIDE"

    # Boundary uncertainty (near edge with ±25m accuracy)
    res_uncertain = client.get(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/status"
        "?latitude=13.0001&longitude=80.025&accuracy=25.0",
        headers=headers,
    )
    assert res_uncertain.status_code == 200
    assert res_uncertain.json()["boundary_status"] == "BOUNDARY_UNCERTAIN"


def test_gps_check_boundary_endpoint(client: TestClient, gps_test_data):
    enum_1 = gps_test_data["enum_1"]
    hlb_1 = gps_test_data["hlb_1"]
    headers = _get_auth_headers(client, enum_1.username)

    res = client.post(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/gps/check-boundary",
        json={"latitude": 13.025, "longitude": 80.025, "accuracy_meters": 8.0},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "INSIDE"
    assert data["distance_to_boundary_meters"] is not None


def test_gps_sync_validation_and_idempotency(
    client: TestClient, db: Session, gps_test_data
):
    enum_1 = gps_test_data["enum_1"]
    hlb_1 = gps_test_data["hlb_1"]
    headers = _get_auth_headers(client, enum_1.username)

    idem_key = f"gps-idem-{uuid.uuid4()}"
    now_iso = datetime.now(UTC).isoformat()

    # 1. Valid GPS sync operation
    sync_payload = {
        "operations": [
            {
                "idempotency_key": idem_key,
                "operation_type": "CREATE",
                "entity_type": "GPS_LOG",
                "local_entity_id": "gps-sync-loc-1",
                "client_timestamp": now_iso,
                "payload": {
                    "hlb_id": str(hlb_1.id),
                    "latitude": 13.022,
                    "longitude": 80.022,
                    "accuracy": 6.2,
                },
            }
        ]
    }

    res = client.post("/api/v1/sync", json=sync_payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success_count"] == 1
    assert data["results"][0]["status"] == "SUCCESS"
    assert data["results"][0]["server_entity_id"] is not None

    server_id = uuid.UUID(data["results"][0]["server_entity_id"])
    track = db.query(GpsTrack).filter(GpsTrack.id == server_id).first()
    assert track is not None
    assert track.latitude == 13.022
    assert track.longitude == 80.022

    # 2. Idempotent replay: sending same idempotency_key returns identical SUCCESS
    res_replay = client.post("/api/v1/sync", json=sync_payload, headers=headers)
    assert res_replay.status_code == 200
    data_replay = res_replay.json()
    assert data_replay["success_count"] == 1
    assert data_replay["results"][0]["server_entity_id"] == str(server_id)

    # 3. Invalid coordinates in sync operation -> returns status="FAILED" in result
    invalid_idem_key = f"gps-invalid-{uuid.uuid4()}"
    invalid_payload = {
        "operations": [
            {
                "idempotency_key": invalid_idem_key,
                "operation_type": "CREATE",
                "entity_type": "GPS_LOG",
                "local_entity_id": "gps-sync-invalid-1",
                "client_timestamp": now_iso,
                "payload": {
                    "hlb_id": str(hlb_1.id),
                    "latitude": 130.022,
                    "longitude": 80.022,
                    "accuracy": 6.2,
                },
            }
        ]
    }

    res_inv = client.post("/api/v1/sync", json=invalid_payload, headers=headers)
    assert res_inv.status_code == 200
    data_inv = res_inv.json()
    assert data_inv["failed_count"] == 1
    assert data_inv["results"][0]["status"] == "FAILED"
    assert "range" in data_inv["results"][0]["error_message"].lower()
