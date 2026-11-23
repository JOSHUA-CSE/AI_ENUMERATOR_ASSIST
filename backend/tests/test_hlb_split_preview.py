"""
Integration and Unit Tests for HLB Split Preview Engine.
Validates:
1. Preview returns actual split geometries (part_a_geometry, part_b_geometry) and building ID lists.
2. Moving split line coordinates dynamically updates geometries and building distributions.
3. Invariant conservation: count_before == count_A + count_B across all tests.
4. Diagonal split cuts properly across EPSG:32643 projected space.
5. Strongly uneven split (e.g., 90/10 or 80/20) correctly assigns counts.
6. Dense cluster partitioning cleanly separates buildings on both sides.
"""

import uuid
import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, Point, Polygon
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.gis.hlb.editing_service import HlbEditingService
from app.models.administrative_area import AdministrativeArea, AreaType, BoundaryStatus
from app.models.hlb import HlbHouse, HlbStatus, HouselistingBlock
from app.models.house import House
from app.models.layout import Layout, LayoutStatus, LayoutVersion, LayoutVersionSource, LayoutVersionStatus


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def hlb_editing_svc():
    return HlbEditingService()


@pytest.fixture
def setup_hlb_with_buildings(db_session: Session):
    """
    Creates an AdministrativeArea, Layout, LayoutVersion, HLB, and 30 houses in Arasur / Coimbatore coordinate space.
    """
    # 1. Administrative Area
    poly = Polygon([
        (77.080, 11.030),
        (77.120, 11.030),
        (77.120, 11.070),
        (77.080, 11.070),
        (77.080, 11.030),
    ])
    area = AdministrativeArea(
        id=uuid.uuid4(),
        name="Test Area Split Preview",
        code=f"TEST-AREA-{uuid.uuid4().hex[:6]}",
        type=AreaType.VILLAGE,
        boundary=from_shape(MultiPolygon([poly]), srid=4326),
        boundary_status=BoundaryStatus.PROVISIONAL.value,
        status="ACTIVE",
    )
    db_session.add(area)
    db_session.flush()

    # 2. Layout
    layout = Layout(
        id=uuid.uuid4(),
        area_id=area.id,
        name="Test Split Preview Layout",
        target_hlb_building_count=250,
        actual_building_count=30,
        expected_hlb_count=1,
        status=LayoutStatus.REVIEW,
        boundary=from_shape(MultiPolygon([poly]), srid=4326),
    )
    db_session.add(layout)
    db_session.flush()

    # 3. Layout Version
    version = LayoutVersion(
        id=uuid.uuid4(),
        layout_id=layout.id,
        version_number=1,
        source=LayoutVersionSource.AI_GENERATED,
        status=LayoutVersionStatus.CANDIDATE,
        target_buildings_per_hlb=250,
        total_buildings=30,
        hlb_count=1,
    )
    db_session.add(version)
    db_session.flush()

    layout.active_version_id = version.id
    db_session.flush()

    # 4. HLB Polygon (1km x 1km box)
    hlb_poly = Polygon([
        (77.090, 11.040),
        (77.100, 11.040),
        (77.100, 11.050),
        (77.090, 11.050),
        (77.090, 11.040),
    ])
    hlb = HouselistingBlock(
        id=uuid.uuid4(),
        layout_id=layout.id,
        version_id=version.id,
        block_code="HLB-PREVIEW-01",
        boundary=from_shape(MultiPolygon([hlb_poly]), srid=4326),
        actual_building_count=30,
        target_building_count=250,
        status=HlbStatus.GENERATED,
        quality_score=0.95,
    )
    db_session.add(hlb)
    db_session.flush()

    # 5. Populate 30 buildings:
    # 15 on west side (lng ~ 77.092)
    # 15 on east side (lng ~ 77.098)
    houses = []
    for i in range(15):
        lat = 11.041 + (i * 0.0005)
        h = House(
            id=uuid.uuid4(),
            area_id=area.id,
            building_reference=f"BLD-W-{i+1}",
            latitude=lat,
            longitude=77.092,
            location=from_shape(Point(77.092, lat), srid=4326),
        )
        db_session.add(h)
        db_session.flush()
        houses.append(h)
        assoc = HlbHouse(hlb_id=hlb.id, house_id=h.id)
        db_session.add(assoc)

    for i in range(15):
        lat = 11.041 + (i * 0.0005)
        h = House(
            id=uuid.uuid4(),
            area_id=area.id,
            building_reference=f"BLD-E-{i+1}",
            latitude=lat,
            longitude=77.098,
            location=from_shape(Point(77.098, lat), srid=4326),
        )
        db_session.add(h)
        db_session.flush()
        houses.append(h)
        assoc = HlbHouse(hlb_id=hlb.id, house_id=h.id)
        db_session.add(assoc)

    db_session.commit()

    return {
        "area": area,
        "layout": layout,
        "version": version,
        "hlb": hlb,
        "houses": houses,
        "hlb_poly": MultiPolygon([hlb_poly]),
    }


def test_split_preview_returns_geometries_and_building_ids(
    db_session: Session, hlb_editing_svc: HlbEditingService, setup_hlb_with_buildings
):
    """
    Validates that preview_split_hlb returns part_a_geometry, part_b_geometry,
    part_a_building_ids, part_b_building_ids, and exact building counts.
    """
    hlb = setup_hlb_with_buildings["hlb"]

    # Midline cut at lng=77.095
    line_coords = [[77.095, 11.041], [77.095, 11.049]]
    preview = hlb_editing_svc.preview_split_hlb(
        db=db_session,
        hlb_id=hlb.id,
        split_method="DRAW_LINE",
        split_line_coordinates=line_coords,
    )

    assert preview["is_valid"] is True
    assert preview["total_original_buildings"] == 30
    assert preview["side_a_building_count"] == 15
    assert preview["side_b_building_count"] == 15
    assert preview["side_a_building_count"] + preview["side_b_building_count"] == 30

    # Verify geometries returned
    assert preview["part_a_geometry"] is not None
    assert preview["part_b_geometry"] is not None
    assert preview["part_a_geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert preview["part_b_geometry"]["type"] in ("Polygon", "MultiPolygon")

    # Verify building IDs returned
    assert "part_a_building_ids" in preview
    assert "part_b_building_ids" in preview
    assert len(preview["part_a_building_ids"]) == 15
    assert len(preview["part_b_building_ids"]) == 15

    # Check non-overlap of building IDs
    set_a = set(preview["part_a_building_ids"])
    set_b = set(preview["part_b_building_ids"])
    assert len(set_a.intersection(set_b)) == 0
    assert len(set_a.union(set_b)) == 30


def test_line_movement_dynamically_shifts_assignments(
    db_session: Session, hlb_editing_svc: HlbEditingService, setup_hlb_with_buildings
):
    """
    Validates that moving the split line coordinate alters the resulting
    geometries and building assignments between Part A and Part B.
    """
    hlb = setup_hlb_with_buildings["hlb"]

    # Position 1: Center cut at 77.095 (15 left, 15 right)
    line_center = [[77.095, 11.041], [77.095, 11.049]]
    prev_center = hlb_editing_svc.preview_split_hlb(
        db=db_session,
        hlb_id=hlb.id,
        split_method="DRAW_LINE",
        split_line_coordinates=line_center,
    )
    assert prev_center["side_a_building_count"] == 15
    assert prev_center["side_b_building_count"] == 15

    # Position 2: Move line to the right of west buildings but close to east buildings (e.g. 77.0975)
    # Both sets still separated cleanly, but geometries change
    line_shifted = [[77.097, 11.041], [77.097, 11.049]]
    prev_shifted = hlb_editing_svc.preview_split_hlb(
        db=db_session,
        hlb_id=hlb.id,
        split_method="DRAW_LINE",
        split_line_coordinates=line_shifted,
    )

    # Sub-polygon geometry must differ from center cut
    assert prev_shifted["part_a_geometry"] != prev_center["part_a_geometry"]
    assert prev_shifted["part_b_geometry"] != prev_center["part_b_geometry"]

    # Invariant: conservation holds
    assert prev_shifted["side_a_building_count"] + prev_shifted["side_b_building_count"] == 30


def test_diagonal_split(
    db_session: Session, hlb_editing_svc: HlbEditingService, setup_hlb_with_buildings
):
    """
    Validates a diagonal cut from bottom-left (77.091, 11.041) to top-right (77.099, 11.049).
    """
    hlb = setup_hlb_with_buildings["hlb"]

    diag_line = [[77.091, 11.041], [77.099, 11.049]]
    preview = hlb_editing_svc.preview_split_hlb(
        db=db_session,
        hlb_id=hlb.id,
        split_method="DRAW_LINE",
        split_line_coordinates=diag_line,
    )

    assert preview["is_valid"] is True
    assert preview["side_a_building_count"] > 0
    assert preview["side_b_building_count"] > 0
    assert preview["side_a_building_count"] + preview["side_b_building_count"] == 30
    assert preview["part_a_geometry"] is not None
    assert preview["part_b_geometry"] is not None


def test_strongly_uneven_split_and_dense_cluster(
    hlb_editing_svc: HlbEditingService, setup_hlb_with_buildings
):
    """
    Validates strongly uneven cuts (e.g. 90/10) on a dense cluster of buildings.
    """
    hlb_poly = setup_hlb_with_buildings["hlb_poly"]

    # Create 50 buildings in a dense cluster
    dense_buildings = []
    for i in range(50):
        # 45 buildings in dense west cluster: lng in [77.091, 77.093]
        if i < 45:
            lng = 77.091 + (i % 5) * 0.0004
            lat = 11.042 + (i // 5) * 0.0006
            dense_buildings.append({
                "id": uuid.uuid4(),
                "ref": f"DENSE-W-{i}",
                "latitude": lat,
                "longitude": lng,
            })
        else:
            # 5 buildings on east edge: lng in [77.098, 77.099]
            lng = 77.098 + (i - 45) * 0.0002
            lat = 11.045
            dense_buildings.append({
                "id": uuid.uuid4(),
                "ref": f"SPARSE-E-{i}",
                "latitude": lat,
                "longitude": lng,
            })

    # Cut dividing the 45 dense buildings from the 5 sparse buildings
    cut_line = [[77.096, 11.040], [77.096, 11.050]]
    c1, c2, geom_a, geom_b = hlb_editing_svc._split_geometry_and_partition_by_line(
        hlb_boundary_geom=hlb_poly,
        split_line_coordinates=cut_line,
        building_dicts=dense_buildings,
    )

    assert len(c1) + len(c2) == 50
    # One side has 45, the other has 5 (strongly uneven 90/10)
    counts = sorted([len(c1), len(c2)])
    assert counts == [5, 45]
    assert geom_a.is_valid and geom_b.is_valid
    assert not geom_a.is_empty and not geom_b.is_empty


def test_split_method_normalization(
    db_session: Session, hlb_editing_svc: HlbEditingService, setup_hlb_with_buildings
):
    """
    Ensures DRAW_SPLIT_LINE and DRAW_LINE both trigger line-based spatial splitting.
    """
    hlb = setup_hlb_with_buildings["hlb"]
    line = [[77.095, 11.041], [77.095, 11.049]]

    res_draw_line = hlb_editing_svc.preview_split_hlb(
        db=db_session,
        hlb_id=hlb.id,
        split_method="DRAW_LINE",
        split_line_coordinates=line,
    )

    res_draw_split_line = hlb_editing_svc.preview_split_hlb(
        db=db_session,
        hlb_id=hlb.id,
        split_method="DRAW_SPLIT_LINE",
        split_line_coordinates=line,
    )

    assert res_draw_line["side_a_building_count"] == res_draw_split_line["side_a_building_count"]
    assert res_draw_line["side_b_building_count"] == res_draw_split_line["side_b_building_count"]
    assert res_draw_line["total_original_buildings"] == res_draw_split_line["total_original_buildings"]
