import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.audit_log import AuditLog
from app.models.enumerator_assignment import (
    EnumeratorAssignmentStatus,
    HlbEnumeratorAssignment,
)
from app.models.hlb import HouselistingBlock
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
def test_users(db: Session):
    suffix = uuid.uuid4().hex[:6]
    deputy = User(
        name="Deputy Tahsildar",
        username=f"deputy_p7_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor_1 = User(
        name="Supervisor Alpha",
        username=f"sup_p7_1_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    supervisor_2 = User(
        name="Supervisor Beta",
        username=f"sup_p7_2_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enum_1 = User(
        name="Enumerator One",
        username=f"enum_p7_1_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    enum_2 = User(
        name="Enumerator Two",
        username=f"enum_p7_2_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    enum_inactive = User(
        name="Enumerator Inactive",
        username=f"enum_p7_in_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.INACTIVE,
    )

    db.add_all([deputy, supervisor_1, supervisor_2, enum_1, enum_2, enum_inactive])
    db.commit()

    return {
        "deputy": deputy,
        "supervisor_1": supervisor_1,
        "supervisor_2": supervisor_2,
        "enum_1": enum_1,
        "enum_2": enum_2,
        "enum_inactive": enum_inactive,
    }


@pytest.fixture
def test_layout_with_hlbs(db: Session, test_users: dict):
    suffix = uuid.uuid4().hex[:6]
    area = AdministrativeArea(
        name=f"Phase 7 Village {suffix}",
        type=AreaType.VILLAGE,
        code=f"P7-VILL-{suffix}",
        boundary=WKTElement(
            "MULTIPOLYGON(((77.0 11.0, 77.01 11.0, 77.01 11.01, "
            "77.0 11.01, 77.0 11.0)))",
            srid=4326,
        ),
    )
    db.add(area)
    db.commit()

    layout = Layout(
        area_id=area.id,
        name=f"Phase 7 Layout {suffix}",
        target_hlb_building_count=150,
        actual_building_count=300,
        expected_hlb_count=2,
        boundary=area.boundary,
        status=LayoutStatus.ASSIGNED,
        created_by=test_users["deputy"].id,
        approved_by=test_users["deputy"].id,
        approved_at=datetime.now(UTC),
    )
    db.add(layout)
    db.commit()

    version = LayoutVersion(
        layout_id=layout.id,
        version_number=1,
        source=LayoutVersionSource.APPROVED,
        status=LayoutVersionStatus.APPROVED,
        target_buildings_per_hlb=150,
        total_buildings=300,
        hlb_count=2,
        quality_score=95.0,
        validation_status="VALID",
        created_by=test_users["deputy"].id,
    )
    db.add(version)
    db.commit()

    layout.active_version_id = version.id
    db.commit()

    # Assign supervisor_1 to this layout
    sup_assign = LayoutSupervisorAssignment(
        layout_id=layout.id,
        supervisor_id=test_users["supervisor_1"].id,
        assigned_by=test_users["deputy"].id,
        status=SupervisorAssignmentStatus.ACTIVE,
    )
    db.add(sup_assign)
    db.commit()

    hlb_1 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code="HLB-001",
        name="Block 1",
        target_building_count=150,
        actual_building_count=145,
        boundary=WKTElement(
            "MULTIPOLYGON(((77.0 11.0, 77.005 11.0, 77.005 11.01, "
            "77.0 11.01, 77.0 11.0)))",
            srid=4326,
        ),
    )
    hlb_2 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code="HLB-002",
        name="Block 2",
        target_building_count=150,
        actual_building_count=155,
        boundary=WKTElement(
            "MULTIPOLYGON(((77.005 11.0, 77.01 11.0, 77.01 11.01, "
            "77.005 11.01, 77.005 11.0)))",
            srid=4326,
        ),
    )
    db.add_all([hlb_1, hlb_2])
    db.commit()

    return {
        "area": area,
        "layout": layout,
        "version": version,
        "hlb_1": hlb_1,
        "hlb_2": hlb_2,
    }


def get_headers(client: TestClient, username: str, password: str = "password123"):
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. ENUMERATOR LISTING & AVAILABILITY TESTS
# ==============================================================================


def test_list_enumerators_as_supervisor(client: TestClient, test_users: dict):
    headers = get_headers(client, test_users["supervisor_1"].username)
    res = client.get("/api/v1/enumerators", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data

    usernames = [u["username"] for u in data["items"]]
    assert test_users["enum_1"].username in usernames
    assert test_users["enum_2"].username in usernames
    assert test_users["enum_inactive"].username in usernames
    assert test_users["deputy"].username not in usernames
    assert test_users["supervisor_1"].username not in usernames

    # Inactive enumerator check
    inactive_item = next(
        it
        for it in data["items"]
        if it["username"] == test_users["enum_inactive"].username
    )
    assert inactive_item["availability"] == "INACTIVE"

    # Available enumerator check
    avail_item = next(
        it for it in data["items"] if it["username"] == test_users["enum_1"].username
    )
    assert avail_item["availability"] == "AVAILABLE"


def test_list_enumerators_as_deputy(client: TestClient, test_users: dict):
    headers = get_headers(client, test_users["deputy"].username)
    res = client.get("/api/v1/enumerators", headers=headers)
    assert res.status_code == 200


def test_list_enumerators_denied_for_enumerator(client: TestClient, test_users: dict):
    headers = get_headers(client, test_users["enum_1"].username)
    res = client.get("/api/v1/enumerators", headers=headers)
    assert res.status_code == 403


# ==============================================================================
# 2. ENUMERATOR ASSIGNMENT TESTS
# ==============================================================================


def test_assign_enumerator_success(
    client: TestClient, db: Session, test_users: dict, test_layout_with_hlbs: dict
):
    headers = get_headers(client, test_users["supervisor_1"].username)
    hlb_1 = test_layout_with_hlbs["hlb_1"]
    enum_1 = test_users["enum_1"]

    res = client.post(
        f"/api/v1/hlbs/{hlb_1.id}/assign-enumerator",
        headers=headers,
        json={"enumerator_id": str(enum_1.id)},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["hlb_id"] == str(hlb_1.id)
    assert data["enumerator_id"] == str(enum_1.id)
    assert data["status"] == "ACTIVE"

    # Verify database assignment record
    assign = (
        db.query(HlbEnumeratorAssignment)
        .filter(
            HlbEnumeratorAssignment.hlb_id == hlb_1.id,
            HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
        )
        .first()
    )
    assert assign is not None
    assert assign.enumerator_id == enum_1.id
    assert assign.supervisor_id == test_users["supervisor_1"].id

    # Verify audit log
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_id == hlb_1.id,
            AuditLog.action == "ENUMERATOR_ASSIGNED",
        )
        .first()
    )
    assert audit is not None
    assert audit.user_id == test_users["supervisor_1"].id


def test_assign_non_enumerator_rejected(
    client: TestClient, test_users: dict, test_layout_with_hlbs: dict
):
    headers = get_headers(client, test_users["supervisor_1"].username)
    hlb_1 = test_layout_with_hlbs["hlb_1"]
    other_sup = test_users["supervisor_2"]

    res = client.post(
        f"/api/v1/hlbs/{hlb_1.id}/assign-enumerator",
        headers=headers,
        json={"enumerator_id": str(other_sup.id)},
    )
    assert res.status_code == 422


def test_assign_inactive_enumerator_rejected(
    client: TestClient, test_users: dict, test_layout_with_hlbs: dict
):
    headers = get_headers(client, test_users["supervisor_1"].username)
    hlb_1 = test_layout_with_hlbs["hlb_1"]
    inactive_enum = test_users["enum_inactive"]

    res = client.post(
        f"/api/v1/hlbs/{hlb_1.id}/assign-enumerator",
        headers=headers,
        json={"enumerator_id": str(inactive_enum.id)},
    )
    assert res.status_code == 422


def test_unauthorized_supervisor_assignment_rejected(
    client: TestClient, test_users: dict, test_layout_with_hlbs: dict
):
    # supervisor_2 is not assigned to this layout
    headers = get_headers(client, test_users["supervisor_2"].username)
    hlb_1 = test_layout_with_hlbs["hlb_1"]
    enum_1 = test_users["enum_1"]

    res = client.post(
        f"/api/v1/hlbs/{hlb_1.id}/assign-enumerator",
        headers=headers,
        json={"enumerator_id": str(enum_1.id)},
    )
    assert res.status_code == 403


def test_duplicate_assignment_to_multiple_hlbs_rejected(
    client: TestClient, test_users: dict, test_layout_with_hlbs: dict
):
    headers = get_headers(client, test_users["supervisor_1"].username)
    hlb_1 = test_layout_with_hlbs["hlb_1"]
    hlb_2 = test_layout_with_hlbs["hlb_2"]
    enum_1 = test_users["enum_1"]

    # Assign enum_1 to HLB 1
    res1 = client.post(
        f"/api/v1/hlbs/{hlb_1.id}/assign-enumerator",
        headers=headers,
        json={"enumerator_id": str(enum_1.id)},
    )
    assert res1.status_code == 200

    # Attempt to assign enum_1 to HLB 2 as well
    res2 = client.post(
        f"/api/v1/hlbs/{hlb_2.id}/assign-enumerator",
        headers=headers,
        json={"enumerator_id": str(enum_1.id)},
    )
    assert res2.status_code == 409
    assert "already assigned" in res2.json()["detail"].lower()


def test_reassignment_preserves_history_and_cancels_old(
    client: TestClient, db: Session, test_users: dict, test_layout_with_hlbs: dict
):
    headers = get_headers(client, test_users["supervisor_1"].username)
    hlb_1 = test_layout_with_hlbs["hlb_1"]
    enum_1 = test_users["enum_1"]
    enum_2 = test_users["enum_2"]

    # Assign enum_1
    res1 = client.post(
        f"/api/v1/hlbs/{hlb_1.id}/assign-enumerator",
        headers=headers,
        json={"enumerator_id": str(enum_1.id)},
    )
    assert res1.status_code == 200

    # Reassign to enum_2
    res2 = client.post(
        f"/api/v1/hlbs/{hlb_1.id}/assign-enumerator",
        headers=headers,
        json={"enumerator_id": str(enum_2.id)},
    )
    assert res2.status_code == 200
    assert res2.json()["enumerator_id"] == str(enum_2.id)

    # Verify history in DB
    assignments = (
        db.query(HlbEnumeratorAssignment)
        .filter(HlbEnumeratorAssignment.hlb_id == hlb_1.id)
        .order_by(HlbEnumeratorAssignment.created_at.asc())
        .all()
    )
    assert len(assignments) == 2
    assert assignments[0].enumerator_id == enum_1.id
    assert assignments[0].status == EnumeratorAssignmentStatus.CANCELLED
    assert assignments[1].enumerator_id == enum_2.id
    assert assignments[1].status == EnumeratorAssignmentStatus.ACTIVE

    # Verify audit log
    reassign_audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_id == hlb_1.id,
            AuditLog.action == "ENUMERATOR_REASSIGNED",
        )
        .first()
    )
    assert reassign_audit is not None


# ==============================================================================
# 3. ASSIGNMENT COMPLETENESS & SUMMARY TESTS
# ==============================================================================


def test_layout_assignment_summary_completeness(
    client: TestClient, test_users: dict, test_layout_with_hlbs: dict
):
    headers = get_headers(client, test_users["supervisor_1"].username)
    layout = test_layout_with_hlbs["layout"]
    hlb_1 = test_layout_with_hlbs["hlb_1"]
    hlb_2 = test_layout_with_hlbs["hlb_2"]
    enum_1 = test_users["enum_1"]
    enum_2 = test_users["enum_2"]

    # 0/2 assigned -> INCOMPLETE
    res = client.get(
        f"/api/v1/layouts/{layout.id}/enumerator-assignments",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_hlbs"] == 2
    assert data["required_enumerators"] == 2
    assert data["assigned_enumerators"] == 0
    assert data["remaining_enumerators"] == 2
    assert data["status"] == "INCOMPLETE"
    assert data["is_complete"] is False

    # 1/2 assigned -> INCOMPLETE
    client.post(
        f"/api/v1/hlbs/{hlb_1.id}/assign-enumerator",
        headers=headers,
        json={"enumerator_id": str(enum_1.id)},
    )
    res2 = client.get(
        f"/api/v1/layouts/{layout.id}/enumerator-assignments",
        headers=headers,
    )
    data2 = res2.json()
    assert data2["assigned_enumerators"] == 1
    assert data2["remaining_enumerators"] == 1
    assert data2["status"] == "INCOMPLETE"
    assert data2["is_complete"] is False

    # 2/2 assigned -> COMPLETE
    client.post(
        f"/api/v1/hlbs/{hlb_2.id}/assign-enumerator",
        headers=headers,
        json={"enumerator_id": str(enum_2.id)},
    )
    res3 = client.get(
        f"/api/v1/layouts/{layout.id}/enumerator-assignments",
        headers=headers,
    )
    data3 = res3.json()
    assert data3["assigned_enumerators"] == 2
    assert data3["remaining_enumerators"] == 0
    assert data3["status"] == "COMPLETE"
    assert data3["is_complete"] is True


# ==============================================================================
# 4. ENUMERATOR ACCESS ISOLATION TESTS
# ==============================================================================


def test_enumerator_access_isolation(
    client: TestClient, test_users: dict, test_layout_with_hlbs: dict
):
    """
    CRITICAL SECURITY TEST:
    Enum 1 -> HLB 1 (200 OK)
    Enum 1 -> HLB 2 (403 Forbidden)
    Enum 2 -> HLB 2 (200 OK)
    Enum 2 -> HLB 1 (403 Forbidden)
    """
    sup_headers = get_headers(client, test_users["supervisor_1"].username)
    hlb_1 = test_layout_with_hlbs["hlb_1"]
    hlb_2 = test_layout_with_hlbs["hlb_2"]
    enum_1 = test_users["enum_1"]
    enum_2 = test_users["enum_2"]

    # Assign Enum 1 -> HLB 1, Enum 2 -> HLB 2
    client.post(
        f"/api/v1/hlbs/{hlb_1.id}/assign-enumerator",
        headers=sup_headers,
        json={"enumerator_id": str(enum_1.id)},
    )
    client.post(
        f"/api/v1/hlbs/{hlb_2.id}/assign-enumerator",
        headers=sup_headers,
        json={"enumerator_id": str(enum_2.id)},
    )

    enum_1_headers = get_headers(client, enum_1.username)
    enum_2_headers = get_headers(client, enum_2.username)

    # Enum 1 -> HLB 1 (Allowed)
    res_e1_1 = client.get(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}",
        headers=enum_1_headers,
    )
    assert res_e1_1.status_code == 200
    assert res_e1_1.json()["id"] == str(hlb_1.id)

    # Enum 1 -> HLB 2 (Forbidden)
    res_e1_2 = client.get(
        f"/api/v1/enumerator/hlbs/{hlb_2.id}",
        headers=enum_1_headers,
    )
    assert res_e1_2.status_code == 403

    # Enum 2 -> HLB 2 (Allowed)
    res_e2_2 = client.get(
        f"/api/v1/enumerator/hlbs/{hlb_2.id}",
        headers=enum_2_headers,
    )
    assert res_e2_2.status_code == 200
    assert res_e2_2.json()["id"] == str(hlb_2.id)

    # Enum 2 -> HLB 1 (Forbidden)
    res_e2_1 = client.get(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}",
        headers=enum_2_headers,
    )
    assert res_e2_1.status_code == 403

    # Also test GET /api/v1/hlbs/{id} endpoint
    res_direct_e1_hlb1 = client.get(f"/api/v1/hlbs/{hlb_1.id}", headers=enum_1_headers)
    assert res_direct_e1_hlb1.status_code == 200

    res_direct_e1_hlb2 = client.get(f"/api/v1/hlbs/{hlb_2.id}", headers=enum_1_headers)
    assert res_direct_e1_hlb2.status_code == 403
