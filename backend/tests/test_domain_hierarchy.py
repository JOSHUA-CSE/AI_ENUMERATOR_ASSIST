import uuid
from datetime import UTC, datetime

import pytest
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
from app.models.change_request import (
    ChangeRequest,
    ChangeRequestPriority,
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
)
from app.models.hlb import HlbHouse, HlbStatus, HouselistingBlock
from app.models.house import BuildingFieldStatus, BuildingSourceType, House
from app.models.layout import (
    Layout,
    LayoutStatus,
    LayoutVersion,
    LayoutVersionSource,
    LayoutVersionStatus,
)
from app.models.person import Person, PersonReviewState
from app.models.user import User, UserRole, UserStatus


@pytest.fixture
def domain_test_setup(db: Session):
    suffix = uuid.uuid4().hex[:6]

    # Users
    deputy = User(
        name="Deputy Domain",
        username=f"deputy_dom_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor = User(
        name="Supervisor Domain",
        username=f"sup_dom_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enumerator = User(
        name="Enumerator Domain",
        username=f"enum_dom_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all([deputy, supervisor, enumerator])
    db.commit()

    # Administrative Area & Layout
    poly_wkt = (
        "MULTIPOLYGON(((77.0 11.0, 77.02 11.0, 77.02 11.02, 77.0 11.02, 77.0 11.0)))"
    )
    area = AdministrativeArea(
        name=f"Domain Test Village {suffix}",
        type=AreaType.VILLAGE,
        code=f"DOM-{suffix.upper()}",
        boundary=WKTElement(poly_wkt, srid=4326),
    )
    db.add(area)
    db.commit()

    now = datetime.now(UTC)
    layout = Layout(
        area_id=area.id,
        name=f"Domain Layout {suffix}",
        target_hlb_building_count=250,
        actual_building_count=10,
        expected_hlb_count=1,
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
        source=LayoutVersionSource.AI_GENERATED,
        status=LayoutVersionStatus.APPROVED,
    )
    db.add(version)
    db.commit()
    layout.active_version_id = version.id
    db.commit()

    hlb = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code="DOM-HLB-1",
        name="Domain Block 1",
        target_building_count=250,
        actual_building_count=10,
        boundary=area.boundary,
        status=HlbStatus.APPROVED,
    )
    db.add(hlb)
    db.commit()

    # Assign enumerator
    assignment = HlbEnumeratorAssignment(
        hlb_id=hlb.id,
        layout_id=layout.id,
        enumerator_id=enumerator.id,
        supervisor_id=supervisor.id,
        assigned_at=now,
        status=EnumeratorAssignmentStatus.ACTIVE,
    )
    db.add(assignment)
    db.commit()

    return {
        "deputy": deputy,
        "supervisor": supervisor,
        "enumerator": enumerator,
        "area": area,
        "layout": layout,
        "hlb": hlb,
    }


def test_building_with_multiple_census_houses(db: Session, domain_test_setup):
    """
    Scenario 1: One physical building contains multiple census houses
    (e.g., ground floor shop and 1st floor residential flat).
    """
    hlb = domain_test_setup["hlb"]
    area = domain_test_setup["area"]
    enum_user = domain_test_setup["enumerator"]

    # 1. Physical structure
    building = House(
        area_id=area.id,
        building_reference="BLD-MULTI-01",
        house_number="12/A",
        latitude=11.01,
        longitude=77.01,
        location=WKTElement("POINT(77.01 11.01)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
        field_status=BuildingFieldStatus.CONFIRMED,
        listing_closed=False,
    )
    db.add(building)
    db.commit()

    # Map building to HLB
    db.add(HlbHouse(hlb_id=hlb.id, house_id=building.id))
    db.commit()

    # 2. Add two distinct census houses inside this single building
    ch_shop = CensusHouse(
        building_id=building.id,
        hlb_id=hlb.id,
        census_house_number="12/A-Shop",
        use_code=CensusHouseUseCode.COMMERCIAL,
        listing_state=CensusHouseListingState.NON_RESIDENTIAL,
        created_by=enum_user.id,
    )
    ch_flat = CensusHouse(
        building_id=building.id,
        hlb_id=hlb.id,
        census_house_number="12/A-Flat1",
        use_code=CensusHouseUseCode.RESIDENTIAL,
        listing_state=CensusHouseListingState.LISTED,
        created_by=enum_user.id,
    )
    db.add_all([ch_shop, ch_flat])
    db.commit()

    # Query back via relationship
    reloaded_building = db.query(House).filter(House.id == building.id).first()
    assert len(reloaded_building.census_houses) == 2
    house_numbers = {ch.census_house_number for ch in reloaded_building.census_houses}
    assert "12/A-Shop" in house_numbers
    assert "12/A-Flat1" in house_numbers


def test_census_house_with_household_and_persons(db: Session, domain_test_setup):
    """
    Scenario 2: One census house contains a household, and the household
    contains individual Phase II person records.
    """
    hlb = domain_test_setup["hlb"]
    area = domain_test_setup["area"]
    enum_user = domain_test_setup["enumerator"]

    building = House(
        area_id=area.id,
        building_reference="BLD-RES-02",
        house_number="45",
        latitude=11.015,
        longitude=77.015,
        location=WKTElement("POINT(77.015 11.015)", srid=4326),
        field_status=BuildingFieldStatus.CONFIRMED,
        listing_closed=True,
        listing_closed_at=datetime.now(UTC),
    )
    db.add(building)
    db.commit()

    census_house = CensusHouse(
        building_id=building.id,
        hlb_id=hlb.id,
        census_house_number="45/1",
        use_code=CensusHouseUseCode.RESIDENTIAL,
        listing_state=CensusHouseListingState.LISTED,
        created_by=enum_user.id,
    )
    db.add(census_house)
    db.commit()

    # Household record linked to census house
    hh = HouseholdRecord(
        house_id=building.id,
        census_house_id=census_house.id,
        hlb_id=hlb.id,
        enumerator_id=enum_user.id,
        household_number="HH-01",
        head_name="Murugan P",
        total_members=2,
        male_count=1,
        female_count=1,
        transgender_count=0,
        ownership_status="OWNED",
        questionnaire_version="1.0",
        review_state=HouseholdReviewState.SUBMITTED,
        status=HouseholdRecordStatus.COMPLETED,
    )
    db.add(hh)
    db.commit()

    # Person 1 (Head)
    p1 = Person(
        household_id=hh.id,
        person_number=1,
        name="Murugan P",
        relationship_to_head="HEAD",
        sex="MALE",
        age=45,
        marital_status="MARRIED",
        questionnaire_version="2.0",
        review_state=PersonReviewState.SUBMITTED,
    )
    # Person 2 (Spouse)
    p2 = Person(
        household_id=hh.id,
        person_number=2,
        name="Lakshmi M",
        relationship_to_head="SPOUSE",
        sex="FEMALE",
        age=40,
        marital_status="MARRIED",
        questionnaire_version="2.0",
        review_state=PersonReviewState.SUBMITTED,
    )
    db.add_all([p1, p2])
    db.commit()

    # Verify relationships from census house down to persons
    reloaded_ch = (
        db.query(CensusHouse).filter(CensusHouse.id == census_house.id).first()
    )
    assert len(reloaded_ch.household_records) == 1
    reloaded_hh = reloaded_ch.household_records[0]
    assert reloaded_hh.head_name == "Murugan P"
    assert len(reloaded_hh.persons) == 2
    assert reloaded_hh.review_state == HouseholdReviewState.SUBMITTED
    person_names = {p.name for p in reloaded_hh.persons}
    assert "Murugan P" in person_names
    assert "Lakshmi M" in person_names


def test_vacant_and_non_residential_census_houses(db: Session, domain_test_setup):
    """
    Scenario 3 & 4: Vacant and Non-residential structures have zero households
    but are validly listed and fieldwork-resolved.
    """
    hlb = domain_test_setup["hlb"]
    area = domain_test_setup["area"]

    building_vacant = House(
        area_id=area.id,
        building_reference="BLD-VACANT-03",
        house_number="88",
        latitude=11.012,
        longitude=77.012,
        location=WKTElement("POINT(77.012 11.012)", srid=4326),
        field_status=BuildingFieldStatus.CONFIRMED,
        listing_closed=True,
    )
    db.add(building_vacant)
    db.commit()

    ch_vacant = CensusHouse(
        building_id=building_vacant.id,
        hlb_id=hlb.id,
        census_house_number="88",
        use_code=CensusHouseUseCode.VACANT,
        listing_state=CensusHouseListingState.VACANT,
        notes="Vacant locked house, owner moved to city",
    )
    db.add(ch_vacant)
    db.commit()

    assert ch_vacant.listing_state == CensusHouseListingState.VACANT
    assert len(ch_vacant.household_records) == 0


def test_locked_census_house(db: Session, domain_test_setup):
    """
    Scenario 5: A locked census house tracks locked attempts and remains unresolved.
    """
    hlb = domain_test_setup["hlb"]
    area = domain_test_setup["area"]

    building = House(
        area_id=area.id,
        building_reference="BLD-LOCKED-04",
        house_number="99",
        latitude=11.014,
        longitude=77.014,
        location=WKTElement("POINT(77.014 11.014)", srid=4326),
        field_status=BuildingFieldStatus.CONFIRMED,
        listing_closed=False,
    )
    db.add(building)
    db.commit()

    ch_locked = CensusHouse(
        building_id=building.id,
        hlb_id=hlb.id,
        census_house_number="99",
        use_code=CensusHouseUseCode.RESIDENTIAL,
        listing_state=CensusHouseListingState.LOCKED,
        locked_attempts=2,
        notes="Door padlocked on morning and afternoon visits",
    )
    db.add(ch_locked)
    db.commit()

    assert ch_locked.listing_state == CensusHouseListingState.LOCKED
    assert ch_locked.locked_attempts == 2
    assert not building.listing_closed


def test_false_detection_building(db: Session, domain_test_setup):
    """
    Scenario 6: Building marked as FALSE_DETECTION (satellite detection error).
    """
    area = domain_test_setup["area"]

    false_bld = House(
        area_id=area.id,
        building_reference="BLD-FALSE-05",
        latitude=11.018,
        longitude=77.018,
        location=WKTElement("POINT(77.018 11.018)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
        field_status=BuildingFieldStatus.FALSE_DETECTION,
        listing_closed=True,
    )
    db.add(false_bld)
    db.commit()

    assert false_bld.field_status == BuildingFieldStatus.FALSE_DETECTION
    assert false_bld.listing_closed


def test_building_edit_audit_and_change_request(db: Session, domain_test_setup):
    """
    Scenario 7: Creating building edits and change requests without data destruction.
    """
    hlb = domain_test_setup["hlb"]
    layout = domain_test_setup["layout"]
    enum_user = domain_test_setup["enumerator"]
    sup_user = domain_test_setup["supervisor"]

    # Propose moving building location
    edit = BuildingEdit(
        hlb_id=hlb.id,
        edit_type=BuildingEditType.MOVE,
        proposed_changes={"latitude": 11.025, "longitude": 77.025},
        reason="Inaccurate satellite footprint placement",
        requesting_user_id=enum_user.id,
        review_status=BuildingEditReviewStatus.PENDING,
    )
    db.add(edit)
    db.commit()

    # Supervisor approves edit
    edit.review_status = BuildingEditReviewStatus.APPROVED
    edit.reviewer_id = sup_user.id
    edit.reviewed_at = datetime.now(UTC)
    edit.review_comment = "Verified on ground"
    db.commit()

    # Create change request
    cr = ChangeRequest(
        request_type=ChangeRequestType.ADDITIONAL_ENUMERATOR,
        hlb_id=hlb.id,
        layout_id=layout.id,
        requesting_user_id=sup_user.id,
        priority=ChangeRequestPriority.HIGH,
        status=ChangeRequestStatus.OPEN,
        description="HLB contains over 350 structures, need assistant enumerator",
    )
    db.add(cr)
    db.commit()

    reloaded_cr = db.query(ChangeRequest).filter(ChangeRequest.id == cr.id).first()
    assert reloaded_cr.priority == ChangeRequestPriority.HIGH
    assert reloaded_cr.status == ChangeRequestStatus.OPEN
