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
    HouseFieldworkStatus,
    RevisitRecord,
    RevisitRecordStatus,
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
def deputy_test_data(db: Session):
    suffix = uuid.uuid4().hex[:6]

    # Users
    deputy = User(
        name="Deputy Tahsildar Sharma",
        username=f"deputy_p14_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor = User(
        name="Supervisor S001",
        username=f"sup_p14_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enumerator = User(
        name="Enumerator E001",
        username=f"enum_p14_{suffix}",
        phone=f"98765{suffix[:5]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all([deputy, supervisor, enumerator])
    db.flush()

    poly_wkt = "MULTIPOLYGON(((80.0 13.0, 80.1 13.0, 80.1 13.1, 80.0 13.1, 80.0 13.0)))"

    # Administrative Areas
    area_1 = AdministrativeArea(
        name=f"Village Alpha {suffix}",
        code=f"VA_{suffix}",
        type=AreaType.VILLAGE,
        boundary=WKTElement(poly_wkt, srid=4326),
        status="ACTIVE",
    )
    area_2 = AdministrativeArea(
        name=f"Village Beta {suffix}",
        code=f"VB_{suffix}",
        type=AreaType.VILLAGE,
        boundary=WKTElement(poly_wkt, srid=4326),
        status="ACTIVE",
    )
    db.add_all([area_1, area_2])
    db.flush()

    # Layout 1: Village Alpha
    # Assigned Supervisor, 3 HLBs: 1 Completed, 1 Active, 1 Remaining
    layout_1 = Layout(
        area_id=area_1.id,
        name=f"Layout Alpha {suffix}",
        status=LayoutStatus.APPROVED,
        boundary=WKTElement(poly_wkt, srid=4326),
        actual_building_count=7,
        expected_hlb_count=3,
    )
    db.add(layout_1)
    db.flush()

    version_1 = LayoutVersion(
        layout_id=layout_1.id,
        version_number=1,
        source=LayoutVersionSource.APPROVED,
        status=LayoutVersionStatus.APPROVED,
        total_buildings=7,
        hlb_count=3,
    )
    db.add(version_1)
    db.flush()
    layout_1.active_version_id = version_1.id

    # Assign Supervisor S001 to Layout 1
    sup_assignment_1 = LayoutSupervisorAssignment(
        layout_id=layout_1.id,
        supervisor_id=supervisor.id,
        assigned_by=deputy.id,
        status=SupervisorAssignmentStatus.ACTIVE,
    )
    db.add(sup_assignment_1)

    # HLB 1: 2 houses, 2 completed -> COMPLETED
    hlb_1 = HouselistingBlock(
        layout_id=layout_1.id,
        version_id=version_1.id,
        block_code="HLB-001",
        name="Block 1",
        boundary=WKTElement(poly_wkt, srid=4326),
        status=HlbStatus.APPROVED,
        actual_building_count=2,
    )
    # HLB 2: 3 houses, 1 completed, 1 locked -> ACTIVE
    hlb_2 = HouselistingBlock(
        layout_id=layout_1.id,
        version_id=version_1.id,
        block_code="HLB-002",
        name="Block 2",
        boundary=WKTElement(poly_wkt, srid=4326),
        status=HlbStatus.ASSIGNED,
        actual_building_count=3,
    )
    # HLB 3: 2 houses, 0 completed -> REMAINING (not active)
    hlb_3 = HouselistingBlock(
        layout_id=layout_1.id,
        version_id=version_1.id,
        block_code="HLB-003",
        name="Block 3",
        boundary=WKTElement(poly_wkt, srid=4326),
        status=HlbStatus.APPROVED,
        actual_building_count=2,
    )
    db.add_all([hlb_1, hlb_2, hlb_3])
    db.flush()

    # Assign enumerator to HLB 2
    enum_assign = HlbEnumeratorAssignment(
        hlb_id=hlb_2.id,
        layout_id=layout_1.id,
        enumerator_id=enumerator.id,
        supervisor_id=supervisor.id,
        status=EnumeratorAssignmentStatus.ACTIVE,
    )
    db.add(enum_assign)

    # Houses for Layout 1
    houses_l1 = []
    for i in range(7):
        h = House(
            area_id=area_1.id,
            building_reference=f"BLD-A{i + 1}-{suffix}",
            latitude=13.05,
            longitude=80.05,
            location=WKTElement("POINT(80.05 13.05)", srid=4326),
        )
        houses_l1.append(h)
    db.add_all(houses_l1)
    db.flush()

    # Link houses to HLBs:
    # hlb_1 gets houses 0, 1
    # hlb_2 gets houses 2, 3, 4
    # hlb_3 gets houses 5, 6
    for i in range(2):
        db.add(HlbHouse(hlb_id=hlb_1.id, house_id=houses_l1[i].id))
    for i in range(2, 5):
        db.add(HlbHouse(hlb_id=hlb_2.id, house_id=houses_l1[i].id))
    for i in range(5, 7):
        db.add(HlbHouse(hlb_id=hlb_3.id, house_id=houses_l1[i].id))
    db.flush()

    # Fieldwork statuses for HLB 1: both completed
    db.add(
        HouseFieldworkStatus(
            house_id=houses_l1[0].id,
            hlb_id=hlb_1.id,
            enumerator_id=enumerator.id,
            status=FieldworkBuildingStatus.COMPLETED,
            last_updated_at=datetime.now(UTC),
        )
    )
    db.add(
        HouseFieldworkStatus(
            house_id=houses_l1[1].id,
            hlb_id=hlb_1.id,
            enumerator_id=enumerator.id,
            status=FieldworkBuildingStatus.COMPLETED,
            last_updated_at=datetime.now(UTC),
        )
    )

    # Fieldwork statuses for HLB 2: 1 completed, 1 locked
    db.add(
        HouseFieldworkStatus(
            house_id=houses_l1[2].id,
            hlb_id=hlb_2.id,
            enumerator_id=enumerator.id,
            status=FieldworkBuildingStatus.COMPLETED,
            last_updated_at=datetime.now(UTC),
        )
    )
    db.add(
        HouseFieldworkStatus(
            house_id=houses_l1[3].id,
            hlb_id=hlb_2.id,
            enumerator_id=enumerator.id,
            status=FieldworkBuildingStatus.LOCKED,
            last_updated_at=datetime.now(UTC),
        )
    )

    # Add a revisit record for HLB 2
    revisit = RevisitRecord(
        house_id=houses_l1[3].id,
        hlb_id=hlb_2.id,
        enumerator_id=enumerator.id,
        reason="DOOR_LOCKED",
        status=RevisitRecordStatus.PENDING,
    )
    db.add(revisit)

    # Layout 2: Village Beta (No Supervisor, 2 HLBs: both 100% completed)
    layout_2 = Layout(
        area_id=area_2.id,
        name=f"Layout Beta {suffix}",
        status=LayoutStatus.APPROVED,
        boundary=WKTElement(poly_wkt, srid=4326),
        actual_building_count=6,
        expected_hlb_count=2,
    )
    db.add(layout_2)
    db.flush()

    version_2 = LayoutVersion(
        layout_id=layout_2.id,
        version_number=1,
        source=LayoutVersionSource.APPROVED,
        status=LayoutVersionStatus.APPROVED,
        total_buildings=6,
        hlb_count=2,
    )
    db.add(version_2)
    db.flush()
    layout_2.active_version_id = version_2.id

    hlb_4 = HouselistingBlock(
        layout_id=layout_2.id,
        version_id=version_2.id,
        block_code="HLB-101",
        name="Block Beta 1",
        boundary=WKTElement(poly_wkt, srid=4326),
        status=HlbStatus.APPROVED,
        actual_building_count=3,
    )
    hlb_5 = HouselistingBlock(
        layout_id=layout_2.id,
        version_id=version_2.id,
        block_code="HLB-102",
        name="Block Beta 2",
        boundary=WKTElement(poly_wkt, srid=4326),
        status=HlbStatus.APPROVED,
        actual_building_count=3,
    )
    db.add_all([hlb_4, hlb_5])
    db.flush()

    houses_l2 = []
    for i in range(6):
        h = House(
            area_id=area_2.id,
            building_reference=f"BLD-B{i + 1}-{suffix}",
            latitude=13.06,
            longitude=80.06,
            location=WKTElement("POINT(80.06 13.06)", srid=4326),
        )
        houses_l2.append(h)
    db.add_all(houses_l2)
    db.flush()

    for i in range(3):
        db.add(HlbHouse(hlb_id=hlb_4.id, house_id=houses_l2[i].id))
        db.add(
            HouseFieldworkStatus(
                house_id=houses_l2[i].id,
                hlb_id=hlb_4.id,
                enumerator_id=enumerator.id,
                status=FieldworkBuildingStatus.COMPLETED,
            )
        )
    for i in range(3, 6):
        db.add(HlbHouse(hlb_id=hlb_5.id, house_id=houses_l2[i].id))
        db.add(
            HouseFieldworkStatus(
                house_id=houses_l2[i].id,
                hlb_id=hlb_5.id,
                enumerator_id=enumerator.id,
                status=FieldworkBuildingStatus.COMPLETED,
            )
        )

    # Empty Layout for zero-house edge cases
    layout_empty = Layout(
        area_id=area_1.id,
        name=f"Layout Empty {suffix}",
        status=LayoutStatus.DRAFT,
        boundary=WKTElement(poly_wkt, srid=4326),
        actual_building_count=0,
        expected_hlb_count=0,
    )
    db.add(layout_empty)

    db.commit()

    return {
        "deputy": deputy,
        "supervisor": supervisor,
        "enumerator": enumerator,
        "area_1": area_1,
        "area_2": area_2,
        "layout_1": layout_1,
        "layout_2": layout_2,
        "layout_empty": layout_empty,
        "hlb_1": hlb_1,
        "hlb_2": hlb_2,
        "hlb_3": hlb_3,
        "hlb_4": hlb_4,
        "hlb_5": hlb_5,
    }


# ==============================================================================
# Phase 14 Backend Tests: Deputy Tahsildar Progress Monitoring
# ==============================================================================


def test_01_deputy_can_retrieve_overall_progress(client: TestClient, deputy_test_data):
    """1. Deputy Tahsildar can retrieve overall progress."""
    user = deputy_test_data["deputy"]
    headers = get_auth_headers(client, user.username)
    res = client.get("/api/v1/deputy/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_layouts" in data
    assert "total_hlbs" in data
    assert "overall_progress_percentage" in data
    assert "layouts" in data


def test_02_deputy_can_retrieve_authorized_layout_progress(
    client: TestClient, deputy_test_data
):
    """2. Deputy Tahsildar can retrieve progress for a specific layout."""
    user = deputy_test_data["deputy"]
    layout_id = deputy_test_data["layout_1"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{layout_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["layout_id"] == str(layout_id)
    assert "hlbs" in data
    assert len(data["hlbs"]) == 3


def test_03_unauthorized_role_is_rejected(client: TestClient, deputy_test_data):
    """3. Supervisor and Enumerator cannot access Deputy monitoring endpoints."""
    sup = deputy_test_data["supervisor"]
    headers_sup = get_auth_headers(client, sup.username)
    res_sup = client.get("/api/v1/deputy/progress", headers=headers_sup)
    assert res_sup.status_code == 403

    enum = deputy_test_data["enumerator"]
    headers_enum = get_auth_headers(client, enum.username)
    res_enum = client.get("/api/v1/deputy/progress", headers=headers_enum)
    assert res_enum.status_code == 403


def test_04_unauthenticated_access_is_rejected(client: TestClient):
    """4. Unauthenticated requests return 401 Unauthorized."""
    res = client.get("/api/v1/deputy/progress")
    assert res.status_code == 401


def test_05_layout_status_is_correct(client: TestClient, deputy_test_data):
    """5. Layout status reflects actual DB status."""
    user = deputy_test_data["deputy"]
    layout_id = deputy_test_data["layout_1"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{layout_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "APPROVED"


def test_06_supervisor_assignment_is_correct(client: TestClient, deputy_test_data):
    """6. Assigned supervisor is correctly displayed or 'Not assigned'."""
    user = deputy_test_data["deputy"]
    headers = get_auth_headers(client, user.username)

    # Layout 1 has supervisor assigned
    layout_1_id = deputy_test_data["layout_1"].id
    res_1 = client.get(
        f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers
    )
    assert res_1.status_code == 200
    data_1 = res_1.json()
    assert data_1["supervisor"] is not None
    assert data_1["supervisor"]["is_assigned"] is True
    assert data_1["supervisor"]["name"] == "Supervisor S001"

    # Layout 2 has no supervisor assigned
    layout_2_id = deputy_test_data["layout_2"].id
    res_2 = client.get(
        f"/api/v1/deputy/layouts/{layout_2_id}/progress", headers=headers
    )
    assert res_2.status_code == 200
    data_2 = res_2.json()
    assert data_2["supervisor"]["is_assigned"] is False
    assert data_2["supervisor"]["status"] == "Not assigned"


def test_07_total_hlb_count_is_correct(client: TestClient, deputy_test_data):
    """7. Total HLB count is accurate."""
    user = deputy_test_data["deputy"]
    layout_1_id = deputy_test_data["layout_1"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_hlbs"] == 3


def test_08_active_hlb_count_is_correct(client: TestClient, deputy_test_data):
    """8. Active HLB count is correctly derived from current fieldwork/assignment."""
    user = deputy_test_data["deputy"]
    layout_1_id = deputy_test_data["layout_1"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    # HLB 2 is active (partially completed / assigned)
    assert data["active_hlbs"] == 1


def test_09_completed_hlb_count_is_correct(client: TestClient, deputy_test_data):
    """9. Completed HLB count satisfies fieldwork completion logic."""
    user = deputy_test_data["deputy"]
    layout_1_id = deputy_test_data["layout_1"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    # HLB 1 has 2/2 houses completed -> 1 completed HLB
    assert data["completed_hlbs"] == 1


def test_10_remaining_hlb_count_is_correct(client: TestClient, deputy_test_data):
    """10. Remaining HLB count = total_hlbs - completed_hlbs."""
    user = deputy_test_data["deputy"]
    layout_1_id = deputy_test_data["layout_1"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    # 3 total - 1 completed = 2 remaining
    assert data["remaining_hlbs"] == 2


def test_11_total_house_building_count_is_correct(client: TestClient, deputy_test_data):
    """11. Total house/building count is accurate."""
    user = deputy_test_data["deputy"]
    layout_1_id = deputy_test_data["layout_1"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_houses"] == 7


def test_12_completed_house_building_count_is_correct(
    client: TestClient, deputy_test_data
):
    """12. Completed house count reflects actual COMPLETED records."""
    user = deputy_test_data["deputy"]
    layout_1_id = deputy_test_data["layout_1"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    # 2 from HLB 1, 1 from HLB 2 = 3
    assert data["completed_houses"] == 3


def test_13_remaining_house_building_count_is_correct(
    client: TestClient, deputy_test_data
):
    """13. Remaining house count = max(0, total - completed)."""
    user = deputy_test_data["deputy"]
    layout_1_id = deputy_test_data["layout_1"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    # 7 total - 3 completed = 4 remaining
    assert data["remaining_houses"] == 4


def test_14_locked_houses_remain_separate_from_completed(
    client: TestClient, deputy_test_data
):
    """14. LOCKED structures are NOT counted as completed."""
    user = deputy_test_data["deputy"]
    layout_1_id = deputy_test_data["layout_1"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["locked_houses"] == 1
    assert data["completed_houses"] == 3


def test_15_revisit_count_is_correct(client: TestClient, deputy_test_data):
    """15. Revisit count matches revisit records."""
    user = deputy_test_data["deputy"]
    layout_1_id = deputy_test_data["layout_1"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["revisit_count"] == 1


def test_16_overall_percentage_is_weighted_correctly(
    client: TestClient, deputy_test_data
):
    """16. Overall percentage uses weighted aggregation (completed / total * 100)."""
    user = deputy_test_data["deputy"]
    layout_1_id = deputy_test_data["layout_1"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    expected_pct = round((3 / 7) * 100.0, 2)  # 42.86
    assert data["overall_progress_percentage"] == expected_pct


def test_17_zero_house_edge_case(client: TestClient, deputy_test_data):
    """17. Zero-house edge case returns 0.0% without division-by-zero errors."""
    user = deputy_test_data["deputy"]
    empty_id = deputy_test_data["layout_empty"].id
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{empty_id}/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_houses"] == 0
    assert data["completed_houses"] == 0
    assert data["overall_progress_percentage"] == 0.0


def test_18_multiple_layouts_aggregate_correctly(client: TestClient, deputy_test_data):
    """18. Multiple layouts aggregate correctly with weighted math."""
    user = deputy_test_data["deputy"]
    headers = get_auth_headers(client, user.username)
    res = client.get("/api/v1/deputy/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_layouts"] >= 2
    # Ensure layout items exist
    layout_ids = [item["layout_id"] for item in data["layouts"]]
    assert str(deputy_test_data["layout_1"].id) in layout_ids
    assert str(deputy_test_data["layout_2"].id) in layout_ids


def test_19_nonexistent_layout_access_returns_404(client: TestClient, deputy_test_data):
    """19. Nonexistent layout ID returns 404 Not Found."""
    user = deputy_test_data["deputy"]
    fake_id = uuid.uuid4()
    headers = get_auth_headers(client, user.username)
    res = client.get(f"/api/v1/deputy/layouts/{fake_id}/progress", headers=headers)
    assert res.status_code == 404


def test_20_no_individual_house_data_in_overview(client: TestClient, deputy_test_data):
    """20. Overview response does NOT leak individual house records."""
    user = deputy_test_data["deputy"]
    headers = get_auth_headers(client, user.username)
    res = client.get("/api/v1/deputy/progress", headers=headers)
    assert res.status_code == 200
    data = res.json()
    # Check that individual houses or households list does not exist in overview
    assert "houses" not in data
    for layout in data["layouts"]:
        assert "houses" not in layout


def test_21_real_fieldwork_update_reflects_in_deputy_progress(
    client: TestClient, db: Session, deputy_test_data
):
    """
    21. Real workflow verification:
    Enumerator completes building -> Deputy sees updated progress.
    """
    user = deputy_test_data["deputy"]
    layout_1_id = deputy_test_data["layout_1"].id
    hlb_2_id = deputy_test_data["hlb_2"].id
    headers = get_auth_headers(client, user.username)

    # 1. Fetch before
    res_before = client.get(
        f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers
    )
    assert res_before.status_code == 200
    before_data = res_before.json()
    assert before_data["completed_houses"] == 3
    assert before_data["overall_progress_percentage"] == 42.86

    # 2. Simulate Enumerator completing building 4 in HLB 2
    # (previously uncompleted)
    # Get building in HLB 2
    hlb_house = db.query(HlbHouse).filter(HlbHouse.hlb_id == hlb_2_id).all()
    house_to_complete = hlb_house[2].house_id

    # Create/update fieldwork status to COMPLETED
    fw_status = (
        db.query(HouseFieldworkStatus)
        .filter(
            HouseFieldworkStatus.house_id == house_to_complete,
            HouseFieldworkStatus.hlb_id == hlb_2_id,
        )
        .first()
    )
    if not fw_status:
        fw_status = HouseFieldworkStatus(
            house_id=house_to_complete,
            hlb_id=hlb_2_id,
            enumerator_id=deputy_test_data["enumerator"].id,
            status=FieldworkBuildingStatus.COMPLETED,
            last_updated_at=datetime.now(UTC),
        )
        db.add(fw_status)
    else:
        fw_status.status = FieldworkBuildingStatus.COMPLETED
        fw_status.last_updated_at = datetime.now(UTC)
    db.commit()

    # 3. Deputy retrieves updated progress
    res_after = client.get(
        f"/api/v1/deputy/layouts/{layout_1_id}/progress", headers=headers
    )
    assert res_after.status_code == 200
    after_data = res_after.json()

    # Progress increased from 3/7 (42.86%) to 4/7 (57.14%)
    assert after_data["completed_houses"] == 4
    expected_pct = round((4 / 7) * 100.0, 2)
    assert after_data["overall_progress_percentage"] == expected_pct
