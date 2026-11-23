import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.administrative_area import AdministrativeArea, AreaType
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
    HouseholdRecord,
    HouseholdRecordStatus,
    HouseholdReviewState,
)
from app.models.hlb import HlbHouse, HlbStatus, HouselistingBlock
from app.models.house import BuildingFieldStatus, House
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


def _get_auth_headers(client: TestClient, username: str, password: str = "password123"):
    res = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def supervisor_test_env(db: Session):
    suffix = uuid.uuid4().hex[:6]

    deputy = User(
        name="Deputy Tahsildar",
        username=f"dep_rev_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor = User(
        name="Supervisor",
        username=f"sup_rev_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enumerator = User(
        name="Enumerator",
        username=f"enum_rev_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all([deputy, supervisor, enumerator])
    db.commit()

    poly_wkt = (
        "MULTIPOLYGON(((77.0 11.0, 77.02 11.0, 77.02 11.02, 77.0 11.02, 77.0 11.0)))"
    )
    area = AdministrativeArea(
        name=f"Rev Area {suffix}",
        type=AreaType.VILLAGE,
        code=f"RA-{suffix}",
        boundary=WKTElement(poly_wkt, srid=4326),
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    layout = Layout(
        area_id=area.id,
        name=f"Layout Rev {suffix}",
        target_hlb_building_count=200,
        actual_building_count=10,
        boundary=WKTElement(poly_wkt, srid=4326),
        status=LayoutStatus.ASSIGNED,
    )
    db.add(layout)
    db.commit()
    db.refresh(layout)

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

    db.add(
        LayoutSupervisorAssignment(
            layout_id=layout.id,
            supervisor_id=supervisor.id,
            assigned_by=deputy.id,
            assigned_at=datetime.now(UTC),
            status=SupervisorAssignmentStatus.ACTIVE,
        )
    )

    hlb = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code=f"B-{suffix}",
        name="Rev HLB",
        target_building_count=10,
        actual_building_count=2,
        boundary=WKTElement(poly_wkt, srid=4326),
        status=HlbStatus.APPROVED,
    )
    db.add(hlb)
    db.commit()
    db.refresh(hlb)

    db.add(
        HlbEnumeratorAssignment(
            hlb_id=hlb.id,
            layout_id=layout.id,
            enumerator_id=enumerator.id,
            supervisor_id=supervisor.id,
            assigned_at=datetime.now(UTC),
            status=EnumeratorAssignmentStatus.ACTIVE,
        )
    )

    house_1 = House(
        area_id=area.id,
        building_reference="BLD-01",
        latitude=11.001,
        longitude=77.001,
        location=WKTElement("POINT(77.001 11.001)", srid=4326),
        field_status=BuildingFieldStatus.CONFIRMED,
    )
    db.add(house_1)
    db.commit()
    db.refresh(house_1)
    db.add(HlbHouse(hlb_id=hlb.id, house_id=house_1.id))

    ch_1 = CensusHouse(
        building_id=house_1.id,
        hlb_id=hlb.id,
        census_house_number="CH-01",
        use_code=CensusHouseUseCode.RESIDENTIAL,
        listing_state=CensusHouseListingState.LISTED,
        visited_at=datetime.now(UTC),
    )
    db.add(ch_1)
    db.commit()
    db.refresh(ch_1)

    return {
        "area": area,
        "layout": layout,
        "hlb": hlb,
        "house_1": house_1,
        "ch_1": ch_1,
        "deputy": deputy,
        "supervisor": supervisor,
        "enumerator": enumerator,
    }


def test_supervisor_verify_and_return_submissions(
    client: TestClient, db: Session, supervisor_test_env
):
    supervisor = supervisor_test_env["supervisor"]
    enumerator = supervisor_test_env["enumerator"]
    hlb = supervisor_test_env["hlb"]
    house_1 = supervisor_test_env["house_1"]
    ch_1 = supervisor_test_env["ch_1"]

    # 1. Create two household submissions
    now = datetime.now(UTC)
    hh_to_verify = HouseholdRecord(
        house_id=house_1.id,
        census_house_id=ch_1.id,
        hlb_id=hlb.id,
        enumerator_id=enumerator.id,
        household_number="HH-01",
        head_name="Good Submission",
        total_members=2,
        male_count=1,
        female_count=1,
        status=HouseholdRecordStatus.COMPLETED,
        review_state=HouseholdReviewState.SUBMITTED,
        captured_at=now,
    )
    hh_to_return = HouseholdRecord(
        house_id=house_1.id,
        census_house_id=ch_1.id,
        hlb_id=hlb.id,
        enumerator_id=enumerator.id,
        household_number="HH-02",
        head_name="Missing Docs",
        total_members=1,
        male_count=1,
        status=HouseholdRecordStatus.COMPLETED,
        review_state=HouseholdReviewState.SUBMITTED,
        captured_at=now,
    )
    db.add_all([hh_to_verify, hh_to_return])
    db.commit()
    db.refresh(hh_to_verify)
    db.refresh(hh_to_return)

    headers = _get_auth_headers(client, supervisor.username)

    # 2. List submissions
    res_list = client.get("/api/v1/supervisor/submissions", headers=headers)
    assert res_list.status_code == 200
    assert res_list.json()["total"] >= 2

    # 3. Verify first submission
    res_v = client.post(
        f"/api/v1/supervisor/submissions/{hh_to_verify.id}/verify",
        json={"comment": "Audited in field, all documents verified"},
        headers=headers,
    )
    assert res_v.status_code == 200
    v_data = res_v.json()
    assert v_data["review_state"] == "SUPERVISOR_VERIFIED"
    assert v_data["verified_by"] == str(supervisor.id)
    assert v_data["supervisor_comment"] == "Audited in field, all documents verified"

    # 4. Return second submission for correction
    res_r = client.post(
        f"/api/v1/supervisor/submissions/{hh_to_return.id}/return",
        json={
            "rejection_reason": "Incomplete water source details",
            "supervisor_comment": "Please revisit and obtain exact drinking water source",
        },
        headers=headers,
    )
    assert res_r.status_code == 200
    r_data = res_r.json()
    assert r_data["review_state"] == "RETURNED_FOR_CORRECTION"
    assert r_data["rejection_reason"] == "Incomplete water source details"


def test_supervisor_review_building_edits(
    client: TestClient, db: Session, supervisor_test_env
):
    supervisor = supervisor_test_env["supervisor"]
    enumerator = supervisor_test_env["enumerator"]
    hlb = supervisor_test_env["hlb"]
    house_1 = supervisor_test_env["house_1"]

    headers = _get_auth_headers(client, supervisor.username)
    now = datetime.now(UTC)

    # 1. Create a building edit (MOVE)
    edit_move = BuildingEdit(
        hlb_id=hlb.id,
        building_id=house_1.id,
        requesting_user_id=enumerator.id,
        edit_type=BuildingEditType.MOVE,
        proposed_changes={"latitude": 11.0019, "longitude": 77.0019},
        reason="GPS offset correction by enumerator",
        review_status=BuildingEditReviewStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    db.add(edit_move)
    db.commit()
    db.refresh(edit_move)

    # 2. List building edits
    res_list = client.get("/api/v1/supervisor/building-edits", headers=headers)
    assert res_list.status_code == 200
    assert res_list.json()["total"] >= 1

    # 3. Approve the MOVE edit
    res_app = client.post(
        f"/api/v1/supervisor/building-edits/{edit_move.id}/review",
        json={"status": "APPROVED", "comment": "Approved coordinate shift"},
        headers=headers,
    )
    assert res_app.status_code == 200
    assert res_app.json()["review_status"] == "APPROVED"

    # Verify underlying building was updated!
    db.refresh(house_1)
    assert house_1.latitude == 11.0019
    assert house_1.longitude == 77.0019


def test_change_request_workflow_between_supervisor_and_deputy(
    client: TestClient, supervisor_test_env
):
    supervisor = supervisor_test_env["supervisor"]
    deputy = supervisor_test_env["deputy"]
    hlb = supervisor_test_env["hlb"]
    layout = supervisor_test_env["layout"]

    sup_headers = _get_auth_headers(client, supervisor.username)
    dep_headers = _get_auth_headers(client, deputy.username)

    # 1. Supervisor submits a change request (HLB_SPLIT)
    create_body = {
        "request_type": "HLB_SPLIT",
        "hlb_id": str(hlb.id),
        "layout_id": str(layout.id),
        "priority": "HIGH",
        "description": "Block exceeded 300 houses during listing, split required",
        "metadata_json": {"proposed_blocks": 2, "estimated_excess": 85},
    }
    res_cr = client.post(
        "/api/v1/supervisor/change-requests",
        json=create_body,
        headers=sup_headers,
    )
    assert res_cr.status_code == 200
    cr_data = res_cr.json()
    assert cr_data["request_type"] == "HLB_SPLIT"
    assert cr_data["status"] == "OPEN"
    cr_id = cr_data["id"]

    # 2. Supervisor lists change requests
    res_sup_list = client.get("/api/v1/supervisor/change-requests", headers=sup_headers)
    assert res_sup_list.status_code == 200
    assert res_sup_list.json()["total"] >= 1

    # 3. Deputy Tahsildar views pending/open change requests
    res_dep_list = client.get(
        "/api/v1/deputy/change-requests?status=OPEN",
        headers=dep_headers,
    )
    assert res_dep_list.status_code == 200
    assert any(item["id"] == cr_id for item in res_dep_list.json()["items"])

    # 4. Deputy resolves the change request
    res_res = client.post(
        f"/api/v1/deputy/change-requests/{cr_id}/resolve",
        json={
            "status": "RESOLVED",
            "resolution_notes": "Approved HLB split. Tahsil GIS team instructed to repartition.",
        },
        headers=dep_headers,
    )
    assert res_res.status_code == 200
    res_data = res_res.json()
    assert res_data["status"] == "RESOLVED"
    assert res_data["assigned_reviewer_id"] == str(deputy.id)
    assert res_data["resolved_at"] is not None
