import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.audit_log import AuditLog
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
def supervisor_users(db: Session):
    """Create test users for testing supervisor assignment."""
    suffix = uuid.uuid4().hex[:6]
    # Deputy Tahsildar
    deputy = User(
        name="Test Deputy",
        username=f"deputy_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    # Supervisor 1
    supervisor_1 = User(
        name="Supervisor Alpha",
        username=f"sup_alpha_{suffix}",
        phone=f"98765{suffix[:5]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    # Supervisor 2
    supervisor_2 = User(
        name="Supervisor Beta",
        username=f"sup_beta_{suffix}",
        phone=f"98766{suffix[:5]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    # Enumerator
    enumerator = User(
        name="Enumerator Charlie",
        username=f"enum_charlie_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )

    db.add_all([deputy, supervisor_1, supervisor_2, enumerator])
    db.commit()
    for u in [deputy, supervisor_1, supervisor_2, enumerator]:
        db.refresh(u)

    return {
        "deputy": deputy,
        "supervisor_1": supervisor_1,
        "supervisor_2": supervisor_2,
        "enumerator": enumerator,
    }


@pytest.fixture
def test_approved_layout(db: Session, supervisor_users):
    """Create an approved layout with an approved version and HLBs."""
    suffix = uuid.uuid4().hex[:6]
    poly_wkt = (
        "MULTIPOLYGON(((77.0 11.0, 77.01 11.0, 77.01 11.01, 77.0 11.01, 77.0 11.0)))"
    )
    area = AdministrativeArea(
        name=f"Phase 6 Test Village {suffix}",
        type=AreaType.VILLAGE,
        code=f"P6-VILL-{suffix}",
        boundary=WKTElement(poly_wkt, srid=4326),
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    layout = Layout(
        area_id=area.id,
        name="Approved Test Layout 1",
        target_hlb_building_count=250,
        actual_building_count=500,
        expected_hlb_count=2,
        boundary=area.boundary,
        status=LayoutStatus.APPROVED,
        created_by=supervisor_users["deputy"].id,
        approved_by=supervisor_users["deputy"].id,
        approved_at=datetime.now(UTC),
    )
    db.add(layout)
    db.commit()
    db.refresh(layout)

    version = LayoutVersion(
        layout_id=layout.id,
        version_number=1,
        source=LayoutVersionSource.APPROVED,
        status=LayoutVersionStatus.APPROVED,
        target_buildings_per_hlb=250,
        total_buildings=500,
        hlb_count=2,
        quality_score=95.0,
        validation_status="VALID",
        created_by=supervisor_users["deputy"].id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    layout.active_version_id = version.id
    db.commit()

    hlb1_wkt = (
        "MULTIPOLYGON(((77.0 11.0, 77.005 11.0, 77.005 11.01, 77.0 11.01, 77.0 11.0)))"
    )
    hlb2_wkt = (
        "MULTIPOLYGON(((77.005 11.0, 77.01 11.0, 77.01 11.01, "
        "77.005 11.01, 77.005 11.0)))"
    )

    hlb_1 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code="HLB-001",
        name="Block 1",
        target_building_count=250,
        actual_building_count=245,
        boundary=WKTElement(hlb1_wkt, srid=4326),
    )
    hlb_2 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code="HLB-002",
        name="Block 2",
        target_building_count=250,
        actual_building_count=255,
        boundary=WKTElement(hlb2_wkt, srid=4326),
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


def get_auth_headers(client: TestClient, username: str, password: str = "password123"):
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. SUPERVISOR LISTING TESTS
# ==============================================================================


def test_list_supervisors_as_deputy(client: TestClient, supervisor_users: dict):
    headers = get_auth_headers(client, supervisor_users["deputy"].username)
    response = client.get("/api/v1/supervisors", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data

    supervisor_usernames = [s["username"] for s in data["items"]]
    assert supervisor_users["supervisor_1"].username in supervisor_usernames
    assert supervisor_users["supervisor_2"].username in supervisor_usernames
    assert supervisor_users["deputy"].username not in supervisor_usernames
    assert supervisor_users["enumerator"].username not in supervisor_usernames


def test_list_supervisors_rbac_denied_for_others(
    client: TestClient, supervisor_users: dict
):
    # Supervisor cannot list all supervisors
    sup_headers = get_auth_headers(client, supervisor_users["supervisor_1"].username)
    response = client.get("/api/v1/supervisors", headers=sup_headers)
    assert response.status_code == 403

    # Enumerator cannot list supervisors
    enum_headers = get_auth_headers(client, supervisor_users["enumerator"].username)
    response = client.get("/api/v1/supervisors", headers=enum_headers)
    assert response.status_code == 403


# ==============================================================================
# 2. ASSIGN SUPERVISOR TESTS
# ==============================================================================


def test_assign_supervisor_success(
    client: TestClient, db: Session, supervisor_users: dict, test_approved_layout: dict
):
    deputy_headers = get_auth_headers(client, supervisor_users["deputy"].username)
    layout = test_approved_layout["layout"]
    supervisor = supervisor_users["supervisor_1"]

    response = client.post(
        f"/api/v1/layouts/{layout.id}/assign-supervisor",
        headers=deputy_headers,
        json={"supervisor_id": str(supervisor.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["layout_id"] == str(layout.id)
    assert data["supervisor_id"] == str(supervisor.id)
    assert data["supervisor_name"] == supervisor.name
    assert data["status"] == "ACTIVE"

    # Verify DB state
    db.refresh(layout)
    assert layout.status == LayoutStatus.ASSIGNED

    assignment = (
        db.query(LayoutSupervisorAssignment)
        .filter(
            LayoutSupervisorAssignment.layout_id == layout.id,
            LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE,
        )
        .first()
    )
    assert assignment is not None
    assert assignment.supervisor_id == supervisor.id
    assert assignment.assigned_by == supervisor_users["deputy"].id

    # Verify Audit Log
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_id == layout.id,
            AuditLog.action == "LAYOUT_SUPERVISOR_ASSIGNED",
        )
        .first()
    )
    assert audit is not None
    assert audit.user_id == supervisor_users["deputy"].id


def test_assign_supervisor_unapproved_layout_rejected(
    client: TestClient, db: Session, supervisor_users: dict
):
    deputy_headers = get_auth_headers(client, supervisor_users["deputy"].username)

    suffix = uuid.uuid4().hex[:6]
    poly_wkt = (
        "MULTIPOLYGON(((77.0 11.0, 77.01 11.0, 77.01 11.01, 77.0 11.01, 77.0 11.0)))"
    )
    # Create a draft layout
    area = AdministrativeArea(
        name=f"Draft Village {suffix}",
        type=AreaType.VILLAGE,
        code=f"DRAFT-VILL-{suffix}",
        boundary=WKTElement(poly_wkt, srid=4326),
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    draft_layout = Layout(
        area_id=area.id,
        name="Draft Layout",
        target_hlb_building_count=250,
        actual_building_count=100,
        boundary=area.boundary,
        status=LayoutStatus.DRAFT,
    )
    db.add(draft_layout)
    db.commit()
    db.refresh(draft_layout)

    response = client.post(
        f"/api/v1/layouts/{draft_layout.id}/assign-supervisor",
        headers=deputy_headers,
        json={"supervisor_id": str(supervisor_users["supervisor_1"].id)},
    )
    assert response.status_code == 422
    assert "Only approved layouts" in response.json()["detail"]


def test_assign_non_supervisor_rejected(
    client: TestClient, supervisor_users: dict, test_approved_layout: dict
):
    deputy_headers = get_auth_headers(client, supervisor_users["deputy"].username)
    layout = test_approved_layout["layout"]

    # Attempt to assign an enumerator
    response = client.post(
        f"/api/v1/layouts/{layout.id}/assign-supervisor",
        headers=deputy_headers,
        json={"supervisor_id": str(supervisor_users["enumerator"].id)},
    )
    assert response.status_code == 422
    assert "not a Supervisor" in response.json()["detail"]


def test_assign_supervisor_rbac_forbidden(
    client: TestClient, supervisor_users: dict, test_approved_layout: dict
):
    layout = test_approved_layout["layout"]

    # Supervisor attempting assignment
    sup_headers = get_auth_headers(client, supervisor_users["supervisor_1"].username)
    response = client.post(
        f"/api/v1/layouts/{layout.id}/assign-supervisor",
        headers=sup_headers,
        json={"supervisor_id": str(supervisor_users["supervisor_1"].id)},
    )
    assert response.status_code == 403

    # Enumerator attempting assignment
    enum_headers = get_auth_headers(client, supervisor_users["enumerator"].username)
    response = client.post(
        f"/api/v1/layouts/{layout.id}/assign-supervisor",
        headers=enum_headers,
        json={"supervisor_id": str(supervisor_users["supervisor_1"].id)},
    )
    assert response.status_code == 403


# ==============================================================================
# 3. REASSIGNMENT TESTS
# ==============================================================================


def test_reassign_supervisor_transaction(
    client: TestClient, db: Session, supervisor_users: dict, test_approved_layout: dict
):
    deputy_headers = get_auth_headers(client, supervisor_users["deputy"].username)
    layout = test_approved_layout["layout"]
    sup1 = supervisor_users["supervisor_1"]
    sup2 = supervisor_users["supervisor_2"]

    # 1. First assignment to Supervisor 1
    res1 = client.post(
        f"/api/v1/layouts/{layout.id}/assign-supervisor",
        headers=deputy_headers,
        json={"supervisor_id": str(sup1.id)},
    )
    assert res1.status_code == 200

    # 2. Reassign to Supervisor 2
    res2 = client.post(
        f"/api/v1/layouts/{layout.id}/assign-supervisor",
        headers=deputy_headers,
        json={"supervisor_id": str(sup2.id)},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["supervisor_id"] == str(sup2.id)
    assert data2["supervisor_name"] == sup2.name

    # Verify assignments in DB
    assignments = (
        db.query(LayoutSupervisorAssignment)
        .filter(LayoutSupervisorAssignment.layout_id == layout.id)
        .all()
    )
    assert len(assignments) == 2

    active_assignments = [
        a for a in assignments if a.status == SupervisorAssignmentStatus.ACTIVE
    ]
    cancelled_assignments = [
        a for a in assignments if a.status == SupervisorAssignmentStatus.CANCELLED
    ]

    assert len(active_assignments) == 1
    assert active_assignments[0].supervisor_id == sup2.id

    assert len(cancelled_assignments) == 1
    assert cancelled_assignments[0].supervisor_id == sup1.id

    # Verify Reassigned Audit Log
    reassigned_audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_id == layout.id,
            AuditLog.action == "LAYOUT_SUPERVISOR_REASSIGNED",
        )
        .first()
    )
    assert reassigned_audit is not None


# ==============================================================================
# 4. SUPERVISOR ISOLATION & ACCESS CONTROL TESTS
# ==============================================================================


def test_supervisor_layout_isolation(
    client: TestClient, db: Session, supervisor_users: dict
):
    deputy = supervisor_users["deputy"]
    sup_a = supervisor_users["supervisor_1"]
    sup_b = supervisor_users["supervisor_2"]

    sfx = uuid.uuid4().hex[:6]
    poly_wkt_a = (
        "MULTIPOLYGON(((77.0 11.0, 77.01 11.0, 77.01 11.01, 77.0 11.01, 77.0 11.0)))"
    )
    # Create Area A & Approved Layout A
    area_a = AdministrativeArea(
        name=f"Village A {sfx}",
        type=AreaType.VILLAGE,
        code=f"VILL-A-{sfx}",
        boundary=WKTElement(poly_wkt_a, srid=4326),
    )
    db.add(area_a)
    db.commit()
    db.refresh(area_a)

    layout_a = Layout(
        area_id=area_a.id,
        name="Layout A",
        target_hlb_building_count=250,
        actual_building_count=200,
        boundary=area_a.boundary,
        status=LayoutStatus.APPROVED,
        created_by=deputy.id,
    )
    db.add(layout_a)
    db.commit()
    db.refresh(layout_a)

    ver_a = LayoutVersion(
        layout_id=layout_a.id,
        version_number=1,
        source=LayoutVersionSource.APPROVED,
        status=LayoutVersionStatus.APPROVED,
        target_buildings_per_hlb=250,
        total_buildings=200,
        hlb_count=1,
        validation_status="VALID",
        created_by=deputy.id,
    )
    db.add(ver_a)
    db.commit()
    db.refresh(ver_a)
    layout_a.active_version_id = ver_a.id
    db.commit()

    # Create Area B & Approved Layout B
    poly_wkt_b = (
        "MULTIPOLYGON(((77.1 11.0, 77.11 11.0, 77.11 11.01, 77.1 11.01, 77.1 11.0)))"
    )
    area_b = AdministrativeArea(
        name=f"Village B {sfx}",
        type=AreaType.VILLAGE,
        code=f"VILL-B-{sfx}",
        boundary=WKTElement(poly_wkt_b, srid=4326),
    )
    db.add(area_b)
    db.commit()
    db.refresh(area_b)

    layout_b = Layout(
        area_id=area_b.id,
        name="Layout B",
        target_hlb_building_count=250,
        actual_building_count=300,
        boundary=area_b.boundary,
        status=LayoutStatus.APPROVED,
        created_by=deputy.id,
    )
    db.add(layout_b)
    db.commit()
    db.refresh(layout_b)

    ver_b = LayoutVersion(
        layout_id=layout_b.id,
        version_number=1,
        source=LayoutVersionSource.APPROVED,
        status=LayoutVersionStatus.APPROVED,
        target_buildings_per_hlb=250,
        total_buildings=300,
        hlb_count=1,
        validation_status="VALID",
        created_by=deputy.id,
    )
    db.add(ver_b)
    db.commit()
    db.refresh(ver_b)
    layout_b.active_version_id = ver_b.id
    db.commit()

    # Assign Layout A -> Supervisor A
    deputy_headers = get_auth_headers(client, deputy.username)
    client.post(
        f"/api/v1/layouts/{layout_a.id}/assign-supervisor",
        headers=deputy_headers,
        json={"supervisor_id": str(sup_a.id)},
    )

    # Assign Layout B -> Supervisor B
    client.post(
        f"/api/v1/layouts/{layout_b.id}/assign-supervisor",
        headers=deputy_headers,
        json={"supervisor_id": str(sup_b.id)},
    )

    # --- Test Supervisor A Access ---
    sup_a_headers = get_auth_headers(client, sup_a.username)

    # 1. GET /api/v1/supervisor/layouts for Supervisor A
    res_a_layouts = client.get("/api/v1/supervisor/layouts", headers=sup_a_headers)
    assert res_a_layouts.status_code == 200
    a_layout_ids = [item["id"] for item in res_a_layouts.json()["items"]]
    assert str(layout_a.id) in a_layout_ids
    assert str(layout_b.id) not in a_layout_ids

    # 2. Supervisor A accesses Layout A -> Allowed
    res_a_detail = client.get(
        f"/api/v1/supervisor/layouts/{layout_a.id}", headers=sup_a_headers
    )
    assert res_a_detail.status_code == 200
    assert res_a_detail.json()["id"] == str(layout_a.id)

    # 3. Supervisor A accesses Layout B -> Forbidden 403
    res_a_unauth = client.get(
        f"/api/v1/supervisor/layouts/{layout_b.id}", headers=sup_a_headers
    )
    assert res_a_unauth.status_code == 403

    # 4. Supervisor A calls generic layout endpoint for Layout B -> Forbidden 403
    res_a_generic = client.get(f"/api/v1/layouts/{layout_b.id}", headers=sup_a_headers)
    assert res_a_generic.status_code == 403

    # --- Test Supervisor B Access ---
    sup_b_headers = get_auth_headers(client, sup_b.username)

    # 1. GET /api/v1/supervisor/layouts for Supervisor B
    res_b_layouts = client.get("/api/v1/supervisor/layouts", headers=sup_b_headers)
    assert res_b_layouts.status_code == 200
    b_layout_ids = [item["id"] for item in res_b_layouts.json()["items"]]
    assert str(layout_b.id) in b_layout_ids
    assert str(layout_a.id) not in b_layout_ids

    # 2. Supervisor B accesses Layout B -> Allowed
    res_b_detail = client.get(
        f"/api/v1/supervisor/layouts/{layout_b.id}", headers=sup_b_headers
    )
    assert res_b_detail.status_code == 200

    # 3. Supervisor B accesses Layout A -> Forbidden 403
    res_b_unauth = client.get(
        f"/api/v1/supervisor/layouts/{layout_a.id}", headers=sup_b_headers
    )
    assert res_b_unauth.status_code == 403


# ==============================================================================
# 5. APPROVED LAYOUT IMMUTABILITY UNDER SUPERVISOR
# ==============================================================================


def test_supervisor_cannot_modify_layout_or_hlb(
    client: TestClient, supervisor_users: dict, test_approved_layout: dict
):
    layout = test_approved_layout["layout"]
    hlb1 = test_approved_layout["hlb_1"]
    hlb2 = test_approved_layout["hlb_2"]
    sup = supervisor_users["supervisor_1"]
    deputy = supervisor_users["deputy"]

    # Assign layout to Supervisor
    deputy_headers = get_auth_headers(client, deputy.username)
    client.post(
        f"/api/v1/layouts/{layout.id}/assign-supervisor",
        headers=deputy_headers,
        json={"supervisor_id": str(sup.id)},
    )

    sup_headers = get_auth_headers(client, sup.username)

    # 1. Supervisor cannot edit HLB boundary
    poly_coords = [
        [[77.0, 11.0], [77.005, 11.0], [77.005, 11.01], [77.0, 11.01], [77.0, 11.0]]
    ]
    res_edit = client.patch(
        f"/api/v1/hlbs/{hlb1.id}/boundary",
        headers=sup_headers,
        json={"boundary": {"type": "Polygon", "coordinates": poly_coords}},
    )
    assert res_edit.status_code == 403

    # 2. Supervisor cannot split HLB
    res_split = client.post(
        f"/api/v1/hlbs/{hlb1.id}/split",
        headers=sup_headers,
        json={"split_ratio": 0.5},
    )
    assert res_split.status_code == 403

    # 3. Supervisor cannot merge HLBs
    res_merge = client.post(
        "/api/v1/hlbs/merge",
        headers=sup_headers,
        json={"hlb_id_1": str(hlb1.id), "hlb_id_2": str(hlb2.id)},
    )
    assert res_merge.status_code == 403

    # 4. Supervisor cannot approve layout
    res_app = client.post(
        f"/api/v1/layouts/{layout.id}/approve",
        headers=sup_headers,
        json={},
    )
    assert res_app.status_code == 403
