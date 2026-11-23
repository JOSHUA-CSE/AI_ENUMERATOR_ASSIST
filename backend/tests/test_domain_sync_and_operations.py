import uuid
from datetime import UTC, datetime
from uuid import UUID

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
from app.models.person import Person
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
def sync_domain_fixture(db: Session):
    suffix = uuid.uuid4().hex[:6]

    deputy = User(
        name="Deputy Tahsildar",
        username=f"deputy_sync_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor = User(
        name="Supervisor",
        username=f"sup_sync_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enum_1 = User(
        name="Enumerator Active",
        username=f"enum_act_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    enum_reassigned = User(
        name="Enumerator Reassigned",
        username=f"enum_re_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all([deputy, supervisor, enum_1, enum_reassigned])
    db.commit()

    poly_wkt = (
        "MULTIPOLYGON(((77.0 11.0, 77.02 11.0, 77.02 11.02, 77.0 11.02, 77.0 11.0)))"
    )
    area = AdministrativeArea(
        name=f"Sync Area {suffix}",
        type=AreaType.VILLAGE,
        code=f"SA-{suffix}",
        boundary=WKTElement(poly_wkt, srid=4326),
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    layout = Layout(
        area_id=area.id,
        name=f"Layout Sync {suffix}",
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
        name="Sync HLB",
        target_building_count=10,
        actual_building_count=2,
        boundary=WKTElement(poly_wkt, srid=4326),
        status=HlbStatus.APPROVED,
    )
    db.add(hlb)
    db.commit()
    db.refresh(hlb)

    # Active assignment for enum_1
    db.add(
        HlbEnumeratorAssignment(
            hlb_id=hlb.id,
            layout_id=layout.id,
            enumerator_id=enum_1.id,
            supervisor_id=supervisor.id,
            assigned_at=datetime.now(UTC),
            status=EnumeratorAssignmentStatus.ACTIVE,
        )
    )

    # Historical completed assignment for enum_reassigned (reassigned/completed before sync)
    db.add(
        HlbEnumeratorAssignment(
            hlb_id=hlb.id,
            layout_id=layout.id,
            enumerator_id=enum_reassigned.id,
            supervisor_id=supervisor.id,
            assigned_at=datetime.now(UTC),
            status=EnumeratorAssignmentStatus.COMPLETED,
        )
    )

    # Building 1 in HLB
    house_1 = House(
        area_id=area.id,
        building_reference="BLD-01",
        latitude=11.001,
        longitude=77.001,
        location=WKTElement("POINT(77.001 11.001)", srid=4326),
        field_status=BuildingFieldStatus.UNVERIFIED,
    )
    db.add(house_1)
    db.commit()
    db.refresh(house_1)
    db.add(HlbHouse(hlb_id=hlb.id, house_id=house_1.id))
    db.commit()

    return {
        "area": area,
        "layout": layout,
        "hlb": hlb,
        "house_1": house_1,
        "enum_1": enum_1,
        "enum_reassigned": enum_reassigned,
    }


def test_sync_census_house_and_person(
    client: TestClient, db: Session, sync_domain_fixture
):
    enum_1 = sync_domain_fixture["enum_1"]
    hlb = sync_domain_fixture["hlb"]
    house_1 = sync_domain_fixture["house_1"]

    headers = _get_auth_headers(client, enum_1.username)
    now_iso = datetime.now(UTC).isoformat()

    ch_local_id = str(uuid.uuid4())
    hh_local_id = str(uuid.uuid4())
    p_local_id = str(uuid.uuid4())

    # Step 1: Sync a new CensusHouse for Building 1
    ch_op = {
        "idempotency_key": f"idem-ch-{uuid.uuid4()}",
        "operation_type": "CREATE",
        "entity_type": "CENSUS_HOUSE",
        "local_entity_id": ch_local_id,
        "client_timestamp": now_iso,
        "payload": {
            "hlb_id": str(hlb.id),
            "building_id": str(house_1.id),
            "census_house_number": "CH-01",
            "use_code": "RESIDENTIAL",
            "listing_state": "LISTED",
            "latitude": 11.0012,
            "longitude": 77.0012,
            "geotag_accuracy_m": 4.5,
        },
    }

    res = client.post(
        "/api/v1/sync",
        json={"device_id": "test-dev", "operations": [ch_op]},
        headers=headers,
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success_count"] == 1
    ch_server_id = UUID(res_data["results"][0]["server_entity_id"])

    db_ch = db.query(CensusHouse).filter(CensusHouse.id == ch_server_id).first()
    assert db_ch is not None
    assert db_ch.census_house_number == "CH-01"
    assert db_ch.use_code == CensusHouseUseCode.RESIDENTIAL
    assert db_ch.listing_state == CensusHouseListingState.LISTED

    # Step 2: Sync a Household linked to this CensusHouse
    hh_op = {
        "idempotency_key": f"idem-hh-{uuid.uuid4()}",
        "operation_type": "CREATE",
        "entity_type": "HOUSEHOLD",
        "local_entity_id": hh_local_id,
        "client_timestamp": now_iso,
        "payload": {
            "hlb_id": str(hlb.id),
            "building_id": str(house_1.id),
            "census_house_id": str(db_ch.id),
            "household_number": "HH-01",
            "head_name": "Ramesh",
            "total_members": 2,
            "male_count": 1,
            "female_count": 1,
            "transgender_count": 0,
            "status": "COMPLETED",
            "answers": {"water": "tap", "fuel": "lpg"},
        },
    }

    res_hh = client.post(
        "/api/v1/sync",
        json={"device_id": "test-dev", "operations": [hh_op]},
        headers=headers,
    )
    assert res_hh.status_code == 200
    hh_server_id = UUID(res_hh.json()["results"][0]["server_entity_id"])

    db_hh = db.query(HouseholdRecord).filter(HouseholdRecord.id == hh_server_id).first()
    assert db_hh is not None
    assert db_hh.census_house_id == db_ch.id
    assert db_hh.review_state == HouseholdReviewState.SUBMITTED
    assert db_hh.data == {"water": "tap", "fuel": "lpg"}

    # Step 3: Sync a Person linked to this Household
    p_op = {
        "idempotency_key": f"idem-p-{uuid.uuid4()}",
        "operation_type": "CREATE",
        "entity_type": "PERSON",
        "local_entity_id": p_local_id,
        "client_timestamp": now_iso,
        "payload": {
            "hlb_id": str(hlb.id),
            "household_id": str(db_hh.id),
            "person_number": 1,
            "answers": {
                "name": "Ramesh",
                "age": 42,
                "gender": "male",
                "literacy": "yes",
            },
            "review_state": "SUBMITTED",
        },
    }

    res_p = client.post(
        "/api/v1/sync",
        json={"device_id": "test-dev", "operations": [p_op]},
        headers=headers,
    )
    assert res_p.status_code == 200
    p_server_id = UUID(res_p.json()["results"][0]["server_entity_id"])

    db_person = db.query(Person).filter(Person.id == p_server_id).first()
    assert db_person is not None
    assert db_person.household_id == db_hh.id
    assert db_person.person_number == 1
    assert db_person.answers["age"] == 42


def test_sync_building_edit_add_and_close_listing(
    client: TestClient, db: Session, sync_domain_fixture
):
    enum_1 = sync_domain_fixture["enum_1"]
    hlb = sync_domain_fixture["hlb"]
    house_1 = sync_domain_fixture["house_1"]

    headers = _get_auth_headers(client, enum_1.username)
    now_iso = datetime.now(UTC).isoformat()

    # Step 1: Add a new building via BUILDING_EDIT
    add_edit_op = {
        "idempotency_key": f"idem-bld-add-{uuid.uuid4()}",
        "operation_type": "CREATE",
        "entity_type": "BUILDING_EDIT",
        "local_entity_id": str(uuid.uuid4()),
        "client_timestamp": now_iso,
        "payload": {
            "hlb_id": str(hlb.id),
            "edit_type": "ADD",
            "latitude": 11.0025,
            "longitude": 77.0025,
            "building_reference": "NEW-BLD-01",
            "request_reason": "Newly constructed house discovered in field",
            "proposed_changes": {"latitude": 11.0025, "longitude": 77.0025},
        },
    }

    res = client.post(
        "/api/v1/sync",
        json={"device_id": "test-dev", "operations": [add_edit_op]},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["success_count"] == 1
    edit_id = UUID(res.json()["results"][0]["server_entity_id"])

    db_edit = db.query(BuildingEdit).filter(BuildingEdit.id == edit_id).first()
    assert db_edit is not None
    assert db_edit.edit_type == BuildingEditType.ADD
    assert db_edit.review_status == BuildingEditReviewStatus.PENDING

    # Check newly created house
    new_house = db.query(House).filter(House.id == db_edit.building_id).first()
    assert new_house is not None
    assert new_house.building_reference == "NEW-BLD-01"
    assert new_house.field_status == BuildingFieldStatus.FIELD_ADDED

    # Step 2: Confirm existing house and close listing via BUILDING_STATUS
    status_op = {
        "idempotency_key": f"idem-status-{uuid.uuid4()}",
        "operation_type": "UPDATE",
        "entity_type": "BUILDING_STATUS",
        "local_entity_id": str(house_1.id),
        "client_timestamp": now_iso,
        "payload": {
            "hlb_id": str(hlb.id),
            "building_id": str(house_1.id),
            "status": "COMPLETED",
            "field_status": "CONFIRMED",
            "listing_closed": True,
        },
    }

    res_st = client.post(
        "/api/v1/sync",
        json={"device_id": "test-dev", "operations": [status_op]},
        headers=headers,
    )
    assert res_st.status_code == 200
    assert res_st.json()["success_count"] == 1

    db.refresh(house_1)
    assert house_1.field_status == BuildingFieldStatus.CONFIRMED
    assert house_1.listing_closed is True
    assert house_1.listing_closed_at is not None


def test_reassigned_enumerator_can_sync_offline_work(
    client: TestClient, db: Session, sync_domain_fixture
):
    """
    Critical verification:
    If an enumerator was reassigned before being able to connect and sync,
    their offline work must be accepted and NOT rejected!
    """
    enum_reassigned = sync_domain_fixture["enum_reassigned"]
    hlb = sync_domain_fixture["hlb"]
    house_1 = sync_domain_fixture["house_1"]

    headers = _get_auth_headers(client, enum_reassigned.username)
    now_iso = datetime.now(UTC).isoformat()

    op = {
        "idempotency_key": f"idem-reassigned-{uuid.uuid4()}",
        "operation_type": "CREATE",
        "entity_type": "HOUSEHOLD",
        "local_entity_id": str(uuid.uuid4()),
        "client_timestamp": now_iso,
        "payload": {
            "hlb_id": str(hlb.id),
            "building_id": str(house_1.id),
            "household_number": "HH-RE-1",
            "head_name": "Reassigned Collector",
            "total_members": 1,
            "male_count": 1,
            "female_count": 0,
            "transgender_count": 0,
            "status": "COMPLETED",
        },
    }

    res = client.post(
        "/api/v1/sync",
        json={"device_id": "test-dev", "operations": [op]},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    # Must succeed because historical assignment is honored!
    assert data["success_count"] == 1
    assert data["failed_count"] == 0

    record = (
        db.query(HouseholdRecord)
        .filter(HouseholdRecord.household_number == "HH-RE-1")
        .first()
    )
    assert record is not None
    assert record.enumerator_id == enum_reassigned.id
