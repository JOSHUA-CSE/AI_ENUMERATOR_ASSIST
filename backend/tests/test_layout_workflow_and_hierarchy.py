import uuid
import pytest
from fastapi import HTTPException
from shapely.geometry import MultiPolygon, Point, Polygon
from geoalchemy2.shape import from_shape

from app.models.administrative_area import AdministrativeArea, AreaType, BoundaryStatus
from app.models.house import House, BuildingSourceType
from app.models.layout import Layout, LayoutAdministrativeArea, LayoutStatus
from app.models.supervisor_assignment import (
    LayoutSupervisorAssignment,
    SupervisorAssignmentStatus,
)
from app.models.user import User, UserRole, UserStatus
from app.schemas.layout import LayoutCreate, LayoutUpdate
from app.services.layout_service import layout_service


@pytest.fixture
def test_user(db) -> User:
    user = User(
        username=f"deputy_{uuid.uuid4().hex[:6]}",
        password_hash="test_hash",
        name="Test Deputy",
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_supervisor(db) -> User:
    user = User(
        username=f"sup_{uuid.uuid4().hex[:6]}",
        password_hash="test_hash",
        name="Test Supervisor",
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def two_areas(db) -> tuple[AdministrativeArea, AdministrativeArea]:
    geom1 = from_shape(
        MultiPolygon([Polygon([(77.0, 11.0), (77.05, 11.0), (77.05, 11.05), (77.0, 11.05), (77.0, 11.0)])]),
        srid=4326,
    )
    geom2 = from_shape(
        MultiPolygon([Polygon([(77.05, 11.0), (77.10, 11.0), (77.10, 11.05), (77.05, 11.05), (77.05, 11.0)])]),
        srid=4326,
    )
    area1 = AdministrativeArea(
        name="Sangampalayam",
        code=f"TN-POL-01-{uuid.uuid4().hex[:4]}",
        type=AreaType.VILLAGE,
        boundary=geom1,
        boundary_status=BoundaryStatus.PROVISIONAL.value,
        status="ACTIVE",
    )
    area2 = AdministrativeArea(
        name="Jeeva Nagar",
        code=f"TN-POL-02-{uuid.uuid4().hex[:4]}",
        type=AreaType.WARD,
        boundary=geom2,
        boundary_status=BoundaryStatus.PROVISIONAL.value,
        status="ACTIVE",
    )
    db.add_all([area1, area2])
    db.commit()
    db.refresh(area1)
    db.refresh(area2)
    return area1, area2


def test_multi_area_layout_creation_and_aggregation(
    db, test_user, two_areas
):
    area1, area2 = two_areas
    # Add buildings to both areas
    h1 = House(
        area_id=area1.id,
        building_reference="BLD-S1",
        latitude=11.02,
        longitude=77.02,
        location=from_shape(Point(77.02, 11.02), srid=4326),
        footprint=area1.boundary,
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    h2 = House(
        area_id=area2.id,
        building_reference="BLD-J1",
        latitude=11.02,
        longitude=77.07,
        location=from_shape(Point(77.07, 11.02), srid=4326),
        footprint=area2.boundary,
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    db.add_all([h1, h2])
    db.commit()

    # Create layout covering both areas
    data = LayoutCreate(
        name="Pollachi Combined Sector",
        area_ids=[area1.id, area2.id],
        target_buildings_per_hlb=250,
    )
    res = layout_service.create_layout(db=db, data=data, user_id=test_user.id)

    assert res["name"] == "Pollachi Combined Sector"
    assert res["actual_building_count"] == 2
    assert set(res["area_ids"]) == {area1.id, area2.id}

    # Verify database associations
    assocs = db.query(LayoutAdministrativeArea).filter(
        LayoutAdministrativeArea.layout_id == res["id"]
    ).all()
    assert len(assocs) == 2


def test_duplicate_active_layout_prevented(
    db, test_user, two_areas
):
    area1, _ = two_areas
    # First layout
    data1 = LayoutCreate(
        name="Sangampalayam Master Layout",
        area_id=area1.id,
        target_buildings_per_hlb=250,
    )
    layout_service.create_layout(db=db, data=data1, user_id=test_user.id)

    # Attempting second active layout for same area must fail with 409
    data2 = LayoutCreate(
        name="Sangampalayam Duplicate Layout",
        area_id=area1.id,
        target_buildings_per_hlb=250,
    )
    with pytest.raises(HTTPException) as exc_info:
        layout_service.create_layout(db=db, data=data2, user_id=test_user.id)

    assert exc_info.value.status_code == 409
    assert "already belongs to active layout" in str(exc_info.value.detail)


def test_layout_response_includes_supervisor(
    db, test_user, test_supervisor, two_areas
):
    area1, _ = two_areas
    # Create layout
    layout_obj = Layout(
        name="Supervisor Test Layout",
        area_id=area1.id,
        boundary=area1.boundary,
        status=LayoutStatus.ASSIGNED,
        target_hlb_building_count=250,
        created_by=test_user.id,
    )
    db.add(layout_obj)
    db.flush()

    # Add active supervisor assignment
    assignment = LayoutSupervisorAssignment(
        layout_id=layout_obj.id,
        supervisor_id=test_supervisor.id,
        assigned_by=test_user.id,
        status=SupervisorAssignmentStatus.ACTIVE,
    )
    db.add(assignment)
    db.commit()

    # Fetch layout response
    resp = layout_service.get_layout_by_id(db=db, layout_id=layout_obj.id)
    assert resp["supervisor_id"] == test_supervisor.id
    assert resp["assigned_supervisor_name"] == test_supervisor.name


def test_update_layout_and_area_names_response(
    db, test_user, two_areas
):
    area1, area2 = two_areas
    # Create single-area layout
    data = LayoutCreate(
        name="Initial Single Area Layout",
        area_id=area1.id,
        target_buildings_per_hlb=200,
    )
    created = layout_service.create_layout(db=db, data=data, user_id=test_user.id)
    assert created["name"] == "Initial Single Area Layout"
    assert created["areas_count"] == 1
    assert area1.name in created["area_names"]

    # Update to multi-area layout and change target size
    update_data = LayoutUpdate(
        name="Updated Multi Area Layout",
        target_buildings_per_hlb=300,
        area_ids=[area1.id, area2.id],
    )
    updated = layout_service.update_layout(db=db, layout_id=created["id"], data=update_data)
    assert updated["name"] == "Updated Multi Area Layout"
    assert updated["target_buildings_per_hlb"] == 300
    assert updated["areas_count"] == 2
    assert area1.name in updated["area_names"]
    assert area2.name in updated["area_names"]

    # Verify associations updated in DB
    assocs = db.query(LayoutAdministrativeArea).filter(
        LayoutAdministrativeArea.layout_id == created["id"]
    ).all()
    assert len(assocs) == 2


def test_update_layout_conflict_prevented(
    db, test_user, two_areas
):
    area1, area2 = two_areas
    # Layout A has area1
    layout_a = layout_service.create_layout(
        db=db,
        data=LayoutCreate(name="Layout A", area_id=area1.id),
        user_id=test_user.id,
    )
    # Layout B has area2
    layout_b = layout_service.create_layout(
        db=db,
        data=LayoutCreate(name="Layout B", area_id=area2.id),
        user_id=test_user.id,
    )

    # Attempt to update Layout B to also include area1 (already active in Layout A)
    update_data = LayoutUpdate(area_ids=[area2.id, area1.id])
    with pytest.raises(HTTPException) as exc_info:
        layout_service.update_layout(db=db, layout_id=layout_b["id"], data=update_data)

    assert exc_info.value.status_code == 409
    assert "already belongs to active layout" in str(exc_info.value.detail)

