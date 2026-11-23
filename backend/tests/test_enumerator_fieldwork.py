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
def fieldwork_test_data(db: Session):
    suffix = uuid.uuid4().hex[:6]

    # Users
    deputy = User(
        name="Deputy Tahsildar",
        username=f"deputy_fw_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor = User(
        name="Supervisor FW",
        username=f"sup_fw_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enum_1 = User(
        name="Enumerator Assigned",
        username=f"enum_fw_1_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    enum_2 = User(
        name="Enumerator Other",
        username=f"enum_fw_2_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )

    db.add_all([deputy, supervisor, enum_1, enum_2])
    db.commit()

    # Administrative Area
    poly_wkt = "MULTIPOLYGON(((80.0 13.0, 80.1 13.0, 80.1 13.1, 80.0 13.1, 80.0 13.0)))"
    area = AdministrativeArea(
        name=f"Fieldwork Ward {suffix}",
        code=f"FW_{suffix.upper()}",
        type=AreaType.WARD,
        boundary=WKTElement(poly_wkt, srid=4326),
    )
    db.add(area)
    db.commit()

    # Layout & Version
    now = datetime.now(UTC)
    layout = Layout(
        area_id=area.id,
        name=f"Layout FW {suffix}",
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
    now = datetime.now(UTC)
    sup_assign = LayoutSupervisorAssignment(
        layout_id=layout.id,
        supervisor_id=supervisor.id,
        assigned_by=deputy.id,
        assigned_at=now,
        status=SupervisorAssignmentStatus.ACTIVE,
    )
    db.add(sup_assign)
    db.commit()

    # HLBs
    hlb_poly_1 = (
        "MULTIPOLYGON(((80.0 13.0, 80.05 13.0, 80.05 13.05, 80.0 13.05, 80.0 13.0)))"
    )
    hlb_1 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code="HLB-FW-001",
        name="Block FW 1",
        target_building_count=10,
        actual_building_count=3,
        boundary=WKTElement(hlb_poly_1, srid=4326),
    )

    hlb_poly_2 = (
        "MULTIPOLYGON(((80.05 13.0, 80.1 13.0, 80.1 13.05, 80.05 13.05, 80.05 13.0)))"
    )
    hlb_2 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code="HLB-FW-002",
        name="Block FW 2",
        target_building_count=10,
        actual_building_count=2,
        boundary=WKTElement(hlb_poly_2, srid=4326),
    )

    db.add_all([hlb_1, hlb_2])
    db.commit()

    # Houses for HLB 1
    houses_hlb1 = []
    for i in range(3):
        pt_wkt = f"POINT({80.02 + (i * 0.005)} {13.01 + (i * 0.005)})"
        h = House(
            area_id=area.id,
            building_reference=f"BLD-FW-10{i + 1}",
            house_number=f"10{i + 1}",
            latitude=13.01 + (i * 0.005),
            longitude=80.02 + (i * 0.005),
            location=WKTElement(pt_wkt, srid=4326),
            source_type=BuildingSourceType.SATELLITE_DETECTED,
        )
        houses_hlb1.append(h)
    db.add_all(houses_hlb1)
    db.commit()

    for h in houses_hlb1:
        db.add(HlbHouse(hlb_id=hlb_1.id, house_id=h.id, status="ASSIGNED"))
    db.commit()

    # Assign enum_1 to hlb_1
    enum_assign = HlbEnumeratorAssignment(
        hlb_id=hlb_1.id,
        layout_id=layout.id,
        enumerator_id=enum_1.id,
        supervisor_id=supervisor.id,
        assigned_at=now,
        status=EnumeratorAssignmentStatus.ACTIVE,
    )
    db.add(enum_assign)
    db.commit()

    return {
        "deputy": deputy,
        "supervisor": supervisor,
        "enum_1": enum_1,
        "enum_2": enum_2,
        "layout": layout,
        "hlb_1": hlb_1,
        "hlb_2": hlb_2,
        "houses_hlb1": houses_hlb1,
    }


def get_token(client: TestClient, username: str) -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


def test_enumerator_download_assigned_hlb_success(
    client: TestClient, fieldwork_test_data: dict
):
    """
    Assigned enumerator can download complete HLB dataset.
    """
    enum_1 = fieldwork_test_data["enum_1"]
    hlb_1 = fieldwork_test_data["hlb_1"]
    token = get_token(client, enum_1.username)

    res = client.get(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["hlb"]["id"] == str(hlb_1.id)
    assert data["hlb"]["block_code"] == "HLB-FW-001"
    assert data["hlb"]["boundary"] is not None
    assert data["total_buildings"] == 3
    assert len(data["buildings"]) == 3
    assert data["buildings"][0]["building_reference"] == "BLD-FW-101"
    assert data["buildings"][0]["latitude"] > 0
    assert data["buildings"][0]["longitude"] > 0
    assert data["buildings"][0]["status"] == "PENDING"
    assert "downloaded_at" in data


def test_enumerator_download_unassigned_hlb_forbidden(
    client: TestClient, fieldwork_test_data: dict
):
    """
    Enumerator cannot download an HLB they are not assigned to (403 Forbidden).
    """
    enum_1 = fieldwork_test_data["enum_1"]
    hlb_2 = fieldwork_test_data["hlb_2"]  # unassigned to enum_1
    token = get_token(client, enum_1.username)

    res = client.get(
        f"/api/v1/enumerator/hlbs/{hlb_2.id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert "not authorized" in res.json()["detail"].lower()


def test_unassigned_enumerator_cannot_download_other_hlb(
    client: TestClient, fieldwork_test_data: dict
):
    """
    Another enumerator (enum_2) cannot download enum_1's assigned HLB.
    """
    enum_2 = fieldwork_test_data["enum_2"]
    hlb_1 = fieldwork_test_data["hlb_1"]
    token = get_token(client, enum_2.username)

    res = client.get(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_supervisor_cannot_access_enumerator_download_endpoint(
    client: TestClient, fieldwork_test_data: dict
):
    """
    Supervisor role cannot use enumerator download endpoint (403 Forbidden).
    """
    supervisor = fieldwork_test_data["supervisor"]
    hlb_1 = fieldwork_test_data["hlb_1"]
    token = get_token(client, supervisor.username)

    res = client.get(
        f"/api/v1/enumerator/hlbs/{hlb_1.id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_unauthenticated_download_rejected(
    client: TestClient, fieldwork_test_data: dict
):
    """
    Unauthenticated download request is rejected (401 Unauthorized).
    """
    hlb_1 = fieldwork_test_data["hlb_1"]
    res = client.get(f"/api/v1/enumerator/hlbs/{hlb_1.id}/download")
    assert res.status_code == 401
