import uuid
from datetime import UTC, datetime

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.administrative_area import AdministrativeArea, AreaType
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
from app.services.progress_service import progress_service


@pytest.fixture
def progress_domain_setup(db: Session):
    suffix = uuid.uuid4().hex[:6]

    deputy = User(
        name="Deputy Progress",
        username=f"dep_prog_{suffix}",
        password_hash=get_password_hash("pass123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor = User(
        name="Sup Progress",
        username=f"sup_prog_{suffix}",
        password_hash=get_password_hash("pass123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enumerator = User(
        name="Enum Progress",
        username=f"enum_prog_{suffix}",
        password_hash=get_password_hash("pass123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all([deputy, supervisor, enumerator])
    db.commit()

    poly_wkt = (
        "MULTIPOLYGON(((77.0 11.0, 77.02 11.0, 77.02 11.02, 77.0 11.02, 77.0 11.0)))"
    )
    area = AdministrativeArea(
        name=f"Progress Domain Area {suffix}",
        type=AreaType.VILLAGE,
        code=f"PDA-{suffix}",
        boundary=WKTElement(poly_wkt, srid=4326),
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    layout = Layout(
        area_id=area.id,
        name=f"Layout Progress Domain {suffix}",
        target_hlb_building_count=200,
        actual_building_count=8,
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

    sup_assign = LayoutSupervisorAssignment(
        layout_id=layout.id,
        supervisor_id=supervisor.id,
        assigned_by=deputy.id,
        assigned_at=datetime.now(UTC),
        status=SupervisorAssignmentStatus.ACTIVE,
    )
    db.add(sup_assign)
    db.commit()

    hlb = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code=f"B-{suffix}",
        name="Domain Test HLB",
        target_building_count=10,
        actual_building_count=8,
        boundary=WKTElement(poly_wkt, srid=4326),
        status=HlbStatus.APPROVED,
    )
    db.add(hlb)
    db.commit()
    db.refresh(hlb)

    enum_assign = HlbEnumeratorAssignment(
        hlb_id=hlb.id,
        layout_id=layout.id,
        enumerator_id=enumerator.id,
        supervisor_id=supervisor.id,
        assigned_at=datetime.now(UTC),
        status=EnumeratorAssignmentStatus.ACTIVE,
    )
    db.add(enum_assign)
    db.commit()

    return {
        "area": area,
        "layout": layout,
        "hlb": hlb,
        "supervisor": supervisor,
        "enumerator": enumerator,
    }


def test_progress_scenarios(db: Session, progress_domain_setup):
    """
    Validates the 8 mandatory domain scenarios from Part 5 of the prompt:
      1. One building with two census houses.
      2. One building containing multiple households.
      3. A vacant building.
      4. A non-residential building.
      5. A locked census house.
      6. A building with no census houses yet.
      7. A false building detection.
      8. An explicitly closed building listing.
    """
    hlb = progress_domain_setup["hlb"]
    area = progress_domain_setup["area"]
    enumerator = progress_domain_setup["enumerator"]

    # --- Scenario 1: One building with two census houses ---
    b1 = House(
        area_id=area.id,
        building_reference="BLD-S1",
        field_status=BuildingFieldStatus.CONFIRMED,
        listing_closed=True,
        listing_closed_at=datetime.now(UTC),
        latitude=11.001,
        longitude=77.001,
        location=WKTElement("POINT(77.001 11.001)", srid=4326),
    )
    db.add(b1)
    db.flush()
    db.add(HlbHouse(hlb_id=hlb.id, house_id=b1.id))

    ch1_1 = CensusHouse(
        building_id=b1.id,
        hlb_id=hlb.id,
        census_house_number="CH-101",
        use_code=CensusHouseUseCode.RESIDENTIAL,
        listing_state=CensusHouseListingState.LISTED,
        visited_at=datetime.now(UTC),
    )
    ch1_2 = CensusHouse(
        building_id=b1.id,
        hlb_id=hlb.id,
        census_house_number="CH-102",
        use_code=CensusHouseUseCode.RESIDENTIAL,
        listing_state=CensusHouseListingState.LISTED,
        visited_at=datetime.now(UTC),
    )
    db.add_all([ch1_1, ch1_2])
    db.flush()

    hh1_1 = HouseholdRecord(
        house_id=b1.id,
        census_house_id=ch1_1.id,
        hlb_id=hlb.id,
        enumerator_id=enumerator.id,
        household_number="HH-01",
        head_name="Alice Head",
        total_members=2,
        male_count=1,
        female_count=1,
        status=HouseholdRecordStatus.COMPLETED,
        review_state=HouseholdReviewState.SUBMITTED,
    )
    hh1_2 = HouseholdRecord(
        house_id=b1.id,
        census_house_id=ch1_2.id,
        hlb_id=hlb.id,
        enumerator_id=enumerator.id,
        household_number="HH-02",
        head_name="Bob Head",
        total_members=1,
        male_count=1,
        status=HouseholdRecordStatus.COMPLETED,
        review_state=HouseholdReviewState.SUPERVISOR_VERIFIED,
    )
    db.add_all([hh1_1, hh1_2])

    # --- Scenario 2: One building containing multiple households in one census house ---
    b2 = House(
        area_id=area.id,
        building_reference="BLD-S2",
        field_status=BuildingFieldStatus.CONFIRMED,
        listing_closed=True,
        listing_closed_at=datetime.now(UTC),
        latitude=11.002,
        longitude=77.002,
        location=WKTElement("POINT(77.002 11.002)", srid=4326),
    )
    db.add(b2)
    db.flush()
    db.add(HlbHouse(hlb_id=hlb.id, house_id=b2.id))

    ch2 = CensusHouse(
        building_id=b2.id,
        hlb_id=hlb.id,
        census_house_number="CH-201",
        use_code=CensusHouseUseCode.RESIDENTIAL,
        listing_state=CensusHouseListingState.LISTED,
        visited_at=datetime.now(UTC),
    )
    db.add(ch2)
    db.flush()

    hh2_1 = HouseholdRecord(
        house_id=b2.id,
        census_house_id=ch2.id,
        hlb_id=hlb.id,
        enumerator_id=enumerator.id,
        household_number="HH-201-A",
        head_name="Charlie Head",
        total_members=3,
        male_count=2,
        female_count=1,
        status=HouseholdRecordStatus.COMPLETED,
        review_state=HouseholdReviewState.SUBMITTED,
    )
    hh2_2 = HouseholdRecord(
        house_id=b2.id,
        census_house_id=ch2.id,
        hlb_id=hlb.id,
        enumerator_id=enumerator.id,
        household_number="HH-201-B",
        head_name="David Head",
        total_members=2,
        male_count=1,
        female_count=1,
        status=HouseholdRecordStatus.COMPLETED,
        review_state=HouseholdReviewState.SUBMITTED,
    )
    db.add_all([hh2_1, hh2_2])

    # --- Scenario 3: Vacant building ---
    b3 = House(
        area_id=area.id,
        building_reference="BLD-S3",
        field_status=BuildingFieldStatus.CONFIRMED,
        listing_closed=True,
        listing_closed_at=datetime.now(UTC),
        latitude=11.003,
        longitude=77.003,
        location=WKTElement("POINT(77.003 11.003)", srid=4326),
    )
    db.add(b3)
    db.flush()
    db.add(HlbHouse(hlb_id=hlb.id, house_id=b3.id))

    ch3 = CensusHouse(
        building_id=b3.id,
        hlb_id=hlb.id,
        census_house_number="CH-301",
        use_code=CensusHouseUseCode.RESIDENTIAL,
        listing_state=CensusHouseListingState.VACANT,
        visited_at=datetime.now(UTC),
    )
    db.add(ch3)

    # --- Scenario 4: Non-residential building ---
    b4 = House(
        area_id=area.id,
        building_reference="BLD-S4",
        field_status=BuildingFieldStatus.CONFIRMED,
        listing_closed=True,
        listing_closed_at=datetime.now(UTC),
        latitude=11.004,
        longitude=77.004,
        location=WKTElement("POINT(77.004 11.004)", srid=4326),
    )
    db.add(b4)
    db.flush()
    db.add(HlbHouse(hlb_id=hlb.id, house_id=b4.id))

    ch4 = CensusHouse(
        building_id=b4.id,
        hlb_id=hlb.id,
        census_house_number="CH-401",
        use_code=CensusHouseUseCode.COMMERCIAL,
        listing_state=CensusHouseListingState.NON_RESIDENTIAL,
        visited_at=datetime.now(UTC),
    )
    db.add(ch4)

    # --- Scenario 5: Locked census house ---
    b5 = House(
        area_id=area.id,
        building_reference="BLD-S5",
        field_status=BuildingFieldStatus.CONFIRMED,
        listing_closed=True,
        listing_closed_at=datetime.now(UTC),
        latitude=11.005,
        longitude=77.005,
        location=WKTElement("POINT(77.005 11.005)", srid=4326),
    )
    db.add(b5)
    db.flush()
    db.add(HlbHouse(hlb_id=hlb.id, house_id=b5.id))

    ch5 = CensusHouse(
        building_id=b5.id,
        hlb_id=hlb.id,
        census_house_number="CH-501",
        use_code=CensusHouseUseCode.RESIDENTIAL,
        listing_state=CensusHouseListingState.LOCKED,
        locked_attempts=2,
        visited_at=datetime.now(UTC),
    )
    db.add(ch5)

    # --- Scenario 6: Building with no census houses yet (unvisited) ---
    b6 = House(
        area_id=area.id,
        building_reference="BLD-S6",
        field_status=BuildingFieldStatus.UNVERIFIED,
        listing_closed=False,
        latitude=11.006,
        longitude=77.006,
        location=WKTElement("POINT(77.006 11.006)", srid=4326),
    )
    db.add(b6)
    db.flush()
    db.add(HlbHouse(hlb_id=hlb.id, house_id=b6.id))

    # --- Scenario 7: False building detection ---
    b7 = House(
        area_id=area.id,
        building_reference="BLD-S7",
        field_status=BuildingFieldStatus.FALSE_DETECTION,
        listing_closed=True,
        latitude=11.007,
        longitude=77.007,
        location=WKTElement("POINT(77.007 11.007)", srid=4326),
    )
    db.add(b7)
    db.flush()
    db.add(HlbHouse(hlb_id=hlb.id, house_id=b7.id))

    # --- Scenario 8: Building with open listing (listing_closed=False) vs closed listing ---
    b8 = House(
        area_id=area.id,
        building_reference="BLD-S8",
        field_status=BuildingFieldStatus.CONFIRMED,
        listing_closed=False,  # Still open!
        latitude=11.008,
        longitude=77.008,
        location=WKTElement("POINT(77.008 11.008)", srid=4326),
    )
    db.add(b8)
    db.flush()
    db.add(HlbHouse(hlb_id=hlb.id, house_id=b8.id))

    ch8 = CensusHouse(
        building_id=b8.id,
        hlb_id=hlb.id,
        census_house_number="CH-801",
        use_code=CensusHouseUseCode.RESIDENTIAL,
        listing_state=CensusHouseListingState.LISTED,
        visited_at=datetime.now(UTC),
    )
    db.add(ch8)
    db.flush()

    hh8 = HouseholdRecord(
        house_id=b8.id,
        census_house_id=ch8.id,
        hlb_id=hlb.id,
        enumerator_id=enumerator.id,
        household_number="HH-801",
        head_name="Emily Head",
        total_members=1,
        female_count=1,
        status=HouseholdRecordStatus.COMPLETED,
        review_state=HouseholdReviewState.SUBMITTED,
    )
    db.add(hh8)
    db.commit()

    # Now calculate progress with AuthoritativeProgressService
    progress = progress_service.calculate_hlb_progress(db, hlb.id)

    # Verification:
    # Total buildings = 8 (b1 to b8)
    assert progress["total_houses"] == 8
    assert progress["buildings_discovered"] == 8

    # Buildings visited:
    # b1, b2, b3, b4, b5, b7 (CONFIRMED/FALSE_DETECTION), b8 visited. b6 is UNVERIFIED and has no visits -> visited = 7
    assert progress["buildings_visited"] == 7
    assert progress["buildings_confirmed"] == 6  # b1, b2, b3, b4, b5, b8
    assert progress["buildings_false_detection"] == 1  # b7
    assert progress["buildings_listing_closed"] == 6  # b1, b2, b3, b4, b5, b7

    # Resolved Buildings:
    # b1: closed, 2 CHs listed, both HH submitted -> RESOLVED
    # b2: closed, 1 CH listed, 2 HH submitted -> RESOLVED
    # b3: closed, 1 CH vacant -> RESOLVED
    # b4: closed, 1 CH non-res -> RESOLVED
    # b5: closed, 1 CH locked -> UNRESOLVED (locked)
    # b6: open, no CH -> UNRESOLVED
    # b7: false detection -> UNRESOLVED (cannot count as completed building)
    # b8: open listing (listing_closed=False) -> UNRESOLVED (must be explicitly closed)
    # Total completed buildings = 4 (b1, b2, b3, b4)
    assert progress["completed_houses"] == 4
    assert progress["buildings_completed"] == 4
    # Phase 6 Requirement A1: FALSE_DETECTION is excluded from progress denominator
    # Total eligible buildings = 8 - 1 (false detection) = 7
    # Remaining eligible buildings = 7 - 4 = 3
    assert progress["total_eligible_buildings"] == 7
    assert progress["remaining_houses"] == 3  # 7 eligible - 4 completed
    assert progress["locked_houses"] == 1  # b5 has locked census house
    assert progress["pending_revisits"] == 1  # b5

    # Census Houses metrics:
    # Total CH: ch1_1, ch1_2, ch2, ch3, ch4, ch5, ch8 = 7
    assert progress["census_houses_total"] == 7
    assert progress["census_houses_listed"] == 4  # ch1_1, ch1_2, ch2, ch8
    assert progress["census_houses_vacant"] == 1  # ch3
    assert progress["census_houses_non_residential"] == 1  # ch4
    assert progress["census_houses_locked"] == 1  # ch5
    assert progress["census_houses_resolved"] == 6  # 4 listed + 1 vacant + 1 non-res

    # Households metrics:
    # hh1_1, hh1_2, hh2_1, hh2_2, hh8 = 5 households
    assert progress["households_total"] == 5
    assert progress["households_submitted"] == 5
    assert progress["households_verified"] == 1  # hh1_2

    # Percentage: 4 / 7 * 100 = 57.14% (excluding FALSE_DETECTION from denominator per Phase 6 domain invariant)
    assert progress["progress_percentage"] == 57.14

    # Now close b8 listing:
    b8.listing_closed = True
    b8.listing_closed_at = datetime.now(UTC)
    db.commit()

    updated_progress = progress_service.calculate_hlb_progress(db, hlb.id)
    # b8 is now RESOLVED! completed increases to 5!
    assert updated_progress["completed_houses"] == 5
    assert updated_progress["buildings_completed"] == 5
    assert updated_progress["progress_percentage"] == 71.43
