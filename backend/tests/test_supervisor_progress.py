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
from app.models.fieldwork import (
    FieldworkBuildingStatus,
    GpsTrack,
    HouseFieldworkStatus,
    RevisitRecord,
    RevisitRecordStatus,
    SyncEntityType,
    SyncOperation,
    SyncOperationStatus,
    SyncOperationType,
)
from app.models.hlb import HlbHouse, HlbStatus, HouselistingBlock
from app.models.house import House
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


def get_auth_headers(client: TestClient, username: str, password: str = "password123"):
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login_res.status_code == 200, (
        f"Login failed for {username}: {login_res.text}"
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def progress_test_data(db: Session):
    suffix = uuid.uuid4().hex[:6]

    # Users
    deputy = User(
        name="Deputy Officer",
        username=f"deputy_p13_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor_assigned = User(
        name="Supervisor Assigned",
        username=f"sup_assigned_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    supervisor_unassigned = User(
        name="Supervisor Unassigned",
        username=f"sup_unassigned_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enumerator_1 = User(
        name="Enumerator E1",
        username=f"enum_e1_{suffix}",
        phone="9876500001",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    enumerator_2 = User(
        name="Enumerator E2",
        username=f"enum_e2_{suffix}",
        phone="9876500002",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all(
        [
            deputy,
            supervisor_assigned,
            supervisor_unassigned,
            enumerator_1,
            enumerator_2,
        ]
    )
    db.commit()

    # Village Area
    poly_wkt = (
        "MULTIPOLYGON(((77.0 11.0, 77.02 11.0, 77.02 11.02, 77.0 11.02, 77.0 11.0)))"
    )
    area = AdministrativeArea(
        name=f"Progress Test Village {suffix}",
        type=AreaType.VILLAGE,
        code=f"P13-VILL-{suffix}",
        boundary=WKTElement(poly_wkt, srid=4326),
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    # Layout
    layout = Layout(
        area_id=area.id,
        name="Layout Progress 1",
        target_hlb_building_count=250,
        actual_building_count=500,
        expected_hlb_count=3,
        boundary=WKTElement(poly_wkt, srid=4326),
        status=LayoutStatus.ASSIGNED,
    )
    db.add(layout)
    db.commit()
    db.refresh(layout)

    # Version
    version = LayoutVersion(
        layout_id=layout.id,
        version_number=1,
        source=LayoutVersionSource.AI_GENERATED,
        status=LayoutVersionStatus.APPROVED,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    layout.active_version_id = version.id
    db.commit()

    # Supervisor Assignment
    sup_assignment = LayoutSupervisorAssignment(
        layout_id=layout.id,
        supervisor_id=supervisor_assigned.id,
        assigned_by=deputy.id,
        assigned_at=datetime.now(UTC),
        status=SupervisorAssignmentStatus.ACTIVE,
    )
    db.add(sup_assignment)
    db.commit()

    # HLB 1: Boundary coords: 77.000 to 77.010, 11.000 to 11.010
    hlb1_wkt = (
        "MULTIPOLYGON(((77.0 11.0, 77.01 11.0, 77.01 11.01, 77.0 11.01, 77.0 11.0)))"
    )
    hlb_1 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code="B001",
        name="Block 001",
        target_building_count=250,
        actual_building_count=200,
        boundary=WKTElement(hlb1_wkt, srid=4326),
        status=HlbStatus.APPROVED,
    )

    # HLB 2: Boundary coords: 77.010 to 77.020, 11.000 to 11.010
    hlb2_wkt = (
        "MULTIPOLYGON(((77.01 11.0, 77.02 11.0, 77.02 11.01, 77.01 11.01, 77.01 11.0)))"
    )
    hlb_2 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code="B002",
        name="Block 002",
        target_building_count=250,
        actual_building_count=100,
        boundary=WKTElement(hlb2_wkt, srid=4326),
        status=HlbStatus.APPROVED,
    )

    # HLB 3: Edge case with 0 houses
    hlb3_wkt = (
        "MULTIPOLYGON(((77.0 11.01, 77.01 11.01, 77.01 11.02, 77.0 11.02, 77.0 11.01)))"
    )
    hlb_3 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code="B003",
        name="Block 003 Empty",
        target_building_count=250,
        actual_building_count=0,
        boundary=WKTElement(hlb3_wkt, srid=4326),
        status=HlbStatus.APPROVED,
    )
    db.add_all([hlb_1, hlb_2, hlb_3])
    db.commit()
    for h in [hlb_1, hlb_2, hlb_3]:
        db.refresh(h)

    # Enumerator Assignments
    assign_1 = HlbEnumeratorAssignment(
        hlb_id=hlb_1.id,
        layout_id=layout.id,
        enumerator_id=enumerator_1.id,
        supervisor_id=supervisor_assigned.id,
        assigned_at=datetime.now(UTC),
        status=EnumeratorAssignmentStatus.ACTIVE,
    )
    assign_2 = HlbEnumeratorAssignment(
        hlb_id=hlb_2.id,
        layout_id=layout.id,
        enumerator_id=enumerator_2.id,
        supervisor_id=supervisor_assigned.id,
        assigned_at=datetime.now(UTC),
        status=EnumeratorAssignmentStatus.ACTIVE,
    )
    db.add_all([assign_1, assign_2])
    db.commit()

    # Create houses for HLB 1 (4 houses for exact math)
    houses_hlb1 = []
    for i in range(4):
        h = House(
            area_id=area.id,
            building_reference=f"H1-{i + 1}",
            latitude=11.005,
            longitude=77.005,
            location=WKTElement("POINT(77.005 11.005)", srid=4326),
        )
        houses_hlb1.append(h)
    db.add_all(houses_hlb1)
    db.commit()
    for h in houses_hlb1:
        db.refresh(h)
        db.add(HlbHouse(hlb_id=hlb_1.id, house_id=h.id))
    db.commit()

    # Fieldwork statuses for HLB 1:
    # 2 COMPLETED, 1 LOCKED, 1 IN_PROGRESS (so remaining = 2)
    st_comp_1 = HouseFieldworkStatus(
        house_id=houses_hlb1[0].id,
        hlb_id=hlb_1.id,
        enumerator_id=enumerator_1.id,
        status=FieldworkBuildingStatus.COMPLETED,
        household_count=1,
    )
    st_comp_2 = HouseFieldworkStatus(
        house_id=houses_hlb1[1].id,
        hlb_id=hlb_1.id,
        enumerator_id=enumerator_1.id,
        status=FieldworkBuildingStatus.COMPLETED,
        household_count=1,
    )
    st_locked = HouseFieldworkStatus(
        house_id=houses_hlb1[2].id,
        hlb_id=hlb_1.id,
        enumerator_id=enumerator_1.id,
        status=FieldworkBuildingStatus.LOCKED,
        household_count=0,
    )
    st_prog = HouseFieldworkStatus(
        house_id=houses_hlb1[3].id,
        hlb_id=hlb_1.id,
        enumerator_id=enumerator_1.id,
        status=FieldworkBuildingStatus.IN_PROGRESS,
        household_count=0,
    )
    db.add_all([st_comp_1, st_comp_2, st_locked, st_prog])

    # Revisit for locked house in HLB 1
    revisit = RevisitRecord(
        house_id=houses_hlb1[2].id,
        hlb_id=hlb_1.id,
        enumerator_id=enumerator_1.id,
        reason="LOCKED",
        status=RevisitRecordStatus.PENDING,
    )
    db.add(revisit)

    # Sync Operation for Enumerator 1
    sync_op = SyncOperation(
        idempotency_key=f"sync-op-{suffix}",
        user_id=enumerator_1.id,
        operation_type=SyncOperationType.STATUS_UPDATE,
        entity_type=SyncEntityType.BUILDING_STATUS,
        entity_id=str(houses_hlb1[0].id),
        client_timestamp=datetime.now(UTC),
        server_timestamp=datetime.now(UTC),
        status=SyncOperationStatus.SYNCED,
    )
    db.add(sync_op)

    # GPS Track inside HLB 1 (lat 11.005, lon 77.005 is INSIDE)
    gps_inside = GpsTrack(
        enumerator_id=enumerator_1.id,
        hlb_id=hlb_1.id,
        house_id=houses_hlb1[0].id,
        latitude=11.005,
        longitude=77.005,
        accuracy_meters=10.0,
        source="OFFLINE",
    )
    # GPS Track OUTSIDE HLB 1 (lat 11.05, lon 77.05 is well outside HLB 1)
    gps_outside = GpsTrack(
        enumerator_id=enumerator_1.id,
        hlb_id=hlb_1.id,
        house_id=None,
        latitude=11.05,
        longitude=77.05,
        accuracy_meters=10.0,
        source="OFFLINE",
    )
    db.add_all([gps_inside, gps_outside])
    db.commit()

    # Create houses for HLB 2 (2 houses: 1 completed, 1 pending)
    houses_hlb2 = []
    for i in range(2):
        h = House(
            area_id=area.id,
            building_reference=f"H2-{i + 1}",
            latitude=11.005,
            longitude=77.015,
            location=WKTElement("POINT(77.015 11.005)", srid=4326),
        )
        houses_hlb2.append(h)
    db.add_all(houses_hlb2)
    db.commit()
    for h in houses_hlb2:
        db.refresh(h)
        db.add(HlbHouse(hlb_id=hlb_2.id, house_id=h.id))
    db.commit()

    st_h2_comp = HouseFieldworkStatus(
        house_id=houses_hlb2[0].id,
        hlb_id=hlb_2.id,
        enumerator_id=enumerator_2.id,
        status=FieldworkBuildingStatus.COMPLETED,
        household_count=1,
    )
    db.add(st_h2_comp)
    db.commit()

    return {
        "layout": layout,
        "hlb_1": hlb_1,
        "hlb_2": hlb_2,
        "hlb_3": hlb_3,
        "supervisor_assigned": supervisor_assigned,
        "supervisor_unassigned": supervisor_unassigned,
        "enumerator_1": enumerator_1,
        "enumerator_2": enumerator_2,
        "deputy": deputy,
        "houses_hlb1": houses_hlb1,
        "houses_hlb2": houses_hlb2,
    }


def test_1_supervisor_can_retrieve_assigned_layout_progress(
    client: TestClient, progress_test_data
):
    """1. Supervisor can retrieve assigned layout progress."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    layout_id = progress_test_data["layout"].id
    url = f"/api/v1/supervisor/layouts/{layout_id}/progress"
    res = client.get(url, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["layout_id"] == str(layout_id)
    assert "total_hlbs" in data
    assert "completed_houses" in data


def test_2_supervisor_cannot_retrieve_unassigned_layout(
    client: TestClient, progress_test_data
):
    """2. Supervisor cannot retrieve another Supervisor's layout (403 Forbidden)."""
    user = progress_test_data["supervisor_unassigned"]
    headers = get_auth_headers(client, user.username)
    layout_id = progress_test_data["layout"].id
    url = f"/api/v1/supervisor/layouts/{layout_id}/progress"
    res = client.get(url, headers=headers)
    assert res.status_code == 403
    assert "not authorized" in res.json()["detail"].lower()


def test_3_enumerator_cannot_access_supervisor_progress(
    client: TestClient, progress_test_data
):
    """3. Enumerator cannot access Supervisor progress endpoint (403 Forbidden)."""
    user = progress_test_data["enumerator_1"]
    headers = get_auth_headers(client, user.username)
    layout_id = progress_test_data["layout"].id
    url = f"/api/v1/supervisor/layouts/{layout_id}/progress"
    res = client.get(url, headers=headers)
    assert res.status_code == 403


def test_4_unauthenticated_access_fails(client: TestClient, progress_test_data):
    """4. Unauthenticated access fails (401 Unauthorized)."""
    layout_id = progress_test_data["layout"].id
    res = client.get(f"/api/v1/supervisor/layouts/{layout_id}/progress")
    assert res.status_code == 401


def test_5_correct_hlb_count(client: TestClient, progress_test_data):
    """5. Correct HLB count."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    layout_id = progress_test_data["layout"].id
    url = f"/api/v1/supervisor/layouts/{layout_id}/progress"
    res = client.get(url, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_hlbs"] == 3
    assert len(data["hlbs"]) == 3


def test_6_correct_total_houses(client: TestClient, progress_test_data):
    """6. Correct total house/building count across HLBs."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    layout_id = progress_test_data["layout"].id
    url = f"/api/v1/supervisor/layouts/{layout_id}/progress"
    res = client.get(url, headers=headers)
    assert res.status_code == 200
    data = res.json()
    # HLB 1 has 4 houses, HLB 2 has 2 houses, HLB 3 has 0 houses -> total 6
    assert data["total_houses"] == 6


def test_7_correct_completed_count(client: TestClient, progress_test_data):
    """7. Correct completed count."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    layout_id = progress_test_data["layout"].id
    url = f"/api/v1/supervisor/layouts/{layout_id}/progress"
    res = client.get(url, headers=headers)
    assert res.status_code == 200
    data = res.json()
    # HLB 1 has 2 completed, HLB 2 has 1 completed -> total 3 completed
    assert data["completed_houses"] == 3


def test_8_correct_remaining_count(client: TestClient, progress_test_data):
    """8. Correct remaining count."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    layout_id = progress_test_data["layout"].id
    url = f"/api/v1/supervisor/layouts/{layout_id}/progress"
    res = client.get(url, headers=headers)
    assert res.status_code == 200
    data = res.json()
    # Total 6 - Completed 3 = 3 remaining
    assert data["remaining_houses"] == 3


def test_9_correct_locked_count(client: TestClient, progress_test_data):
    """9. Correct locked count."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    layout_id = progress_test_data["layout"].id
    url = f"/api/v1/supervisor/layouts/{layout_id}/progress"
    res = client.get(url, headers=headers)
    assert res.status_code == 200
    data = res.json()
    # HLB 1 has 1 locked house
    assert data["locked_houses"] == 1


def test_10_correct_revisit_count(client: TestClient, progress_test_data):
    """10. Correct revisit count."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    layout_id = progress_test_data["layout"].id
    url = f"/api/v1/supervisor/layouts/{layout_id}/progress"
    res = client.get(url, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["revisit_count"] == 1


def test_11_correct_percentage_calculation(client: TestClient, progress_test_data):
    """11. Correct percentage calculation."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    layout_id = progress_test_data["layout"].id
    url = f"/api/v1/supervisor/layouts/{layout_id}/progress"
    res = client.get(url, headers=headers)
    assert res.status_code == 200
    data = res.json()
    # 3 / 6 * 100 = 50.0%
    assert data["progress_percentage"] == 50.0


def test_12_zero_house_edge_case(client: TestClient, progress_test_data):
    """12. Zero-house edge case returns 0% without NaN/infinity."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    hlb_3_id = progress_test_data["hlb_3"].id
    res = client.get(f"/api/v1/supervisor/hlbs/{hlb_3_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_houses"] == 0
    assert data["progress_percentage"] == 0.0


def test_13_correct_enumerator_assignment(client: TestClient, progress_test_data):
    """13. Correct Enumerator assignment."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    hlb_1_id = progress_test_data["hlb_1"].id
    res = client.get(f"/api/v1/supervisor/hlbs/{hlb_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["enumerator"] is not None
    assert data["enumerator"]["name"] == "Enumerator E1"
    assert data["enumerator"]["assigned_hlb_code"] == "B001"


def test_14_correct_last_sync_value(client: TestClient, progress_test_data):
    """14. Correct last-sync value."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    hlb_1_id = progress_test_data["hlb_1"].id
    res = client.get(f"/api/v1/supervisor/hlbs/{hlb_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["last_sync"] is not None


def test_15_gps_coverage_representation(client: TestClient, progress_test_data):
    """15. GPS coverage is correctly represented."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    hlb_1_id = progress_test_data["hlb_1"].id
    res = client.get(f"/api/v1/supervisor/hlbs/{hlb_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    # 1 of 4 houses has GPS track -> 25.0%
    assert data["gps_coverage"] == 25.0


def test_16_boundary_alert_representation(client: TestClient, progress_test_data):
    """16. Boundary alert count and details are correctly represented."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    hlb_1_id = progress_test_data["hlb_1"].id
    res = client.get(f"/api/v1/supervisor/hlbs/{hlb_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    # 1 track is outside the HLB boundary
    assert data["boundary_alert_count"] == 1
    assert len(data["boundary_alerts"]) == 1
    assert "outside" in data["boundary_alerts"][0]["message"].lower()


def test_17_multiple_hlb_aggregation(client: TestClient, progress_test_data):
    """17. Multiple HLB aggregation is correct."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    res = client.get("/api/v1/supervisor/layouts/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_layouts"] == 1
    assert data["overall_total_houses"] == 6
    assert data["overall_completed_houses"] == 3
    assert data["overall_remaining_houses"] == 3
    assert data["overall_progress_percentage"] == 50.0


def test_18_layout_overall_progress(client: TestClient, progress_test_data):
    """18. Layout overall progress matches individual HLB sum."""
    user = progress_test_data["supervisor_assigned"]
    headers = get_auth_headers(client, user.username)
    layout_id = progress_test_data["layout"].id
    url = f"/api/v1/supervisor/layouts/{layout_id}/progress"
    res = client.get(url, headers=headers)
    assert res.status_code == 200
    data = res.json()
    hlbs = data["hlbs"]
    sum_completed = sum(h["completed_houses"] for h in hlbs)
    sum_total = sum(h["total_houses"] for h in hlbs)
    assert data["completed_houses"] == sum_completed
    assert data["total_houses"] == sum_total


def test_19_supervisor_cannot_access_unassigned_hlb_progress(
    client: TestClient, progress_test_data
):
    """19. Supervisor cannot retrieve an unassigned HLB's progress (403 Forbidden)."""
    user = progress_test_data["supervisor_unassigned"]
    headers = get_auth_headers(client, user.username)
    hlb_1_id = progress_test_data["hlb_1"].id
    res = client.get(f"/api/v1/supervisor/hlbs/{hlb_1_id}/progress", headers=headers)
    assert res.status_code == 403
    assert "not authorized" in res.json()["detail"].lower()


def test_20_deputy_tahsildar_can_access_layout_progress(
    client: TestClient, progress_test_data
):
    """20. Deputy Tahsildar can retrieve layout progress."""
    user = progress_test_data["deputy"]
    headers = get_auth_headers(client, user.username)
    layout_id = progress_test_data["layout"].id
    url = f"/api/v1/supervisor/layouts/{layout_id}/progress"
    res = client.get(url, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["layout_id"] == str(layout_id)
    assert data["total_hlbs"] == 3
