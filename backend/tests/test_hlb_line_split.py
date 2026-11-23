import uuid
import pytest
from fastapi import HTTPException
from shapely.geometry import MultiPolygon, Polygon

from app.gis.hlb.editing_service import HlbEditingService


@pytest.fixture
def editing_service() -> HlbEditingService:
    return HlbEditingService()


@pytest.fixture
def sample_hlb_polygon() -> MultiPolygon:
    # 1km x 1km box in Coimbatore area (EPSG:4326)
    poly = Polygon(
        [
            (77.090, 11.040),
            (77.100, 11.040),
            (77.100, 11.050),
            (77.090, 11.050),
            (77.090, 11.040),
        ]
    )
    return MultiPolygon([poly])


@pytest.fixture
def sample_buildings() -> list[dict]:
    buildings = []
    # 10 buildings on the west (left) side: lng ~ 77.092
    for i in range(10):
        lat = 11.041 + (i * 0.0008)
        buildings.append(
            {
                "id": uuid.uuid4(),
                "ref": f"BLD-W{i+1}",
                "latitude": lat,
                "longitude": 77.092,
            }
        )
    # 10 buildings on the east (right) side: lng ~ 77.098
    for i in range(10):
        lat = 11.041 + (i * 0.0008)
        buildings.append(
            {
                "id": uuid.uuid4(),
                "ref": f"BLD-E{i+1}",
                "latitude": lat,
                "longitude": 77.098,
            }
        )
    return buildings


def test_line_split_vertical(
    editing_service: HlbEditingService,
    sample_hlb_polygon: MultiPolygon,
    sample_buildings: list[dict],
):
    """Case 1: Vertical dividing line splits left and right halves."""
    # Line down the middle: lng = 77.095
    split_line = [[77.095, 11.042], [77.095, 11.048]]

    c1, c2, geom_a, geom_b = editing_service._split_geometry_and_partition_by_line(
        hlb_boundary_geom=sample_hlb_polygon,
        split_line_coordinates=split_line,
        building_dicts=sample_buildings,
    )

    assert len(c1) + len(c2) == len(sample_buildings)
    assert len(c1) == 10
    assert len(c2) == 10
    assert geom_a.is_valid and not geom_a.is_empty
    assert geom_b.is_valid and not geom_b.is_empty


def test_line_split_horizontal(
    editing_service: HlbEditingService,
    sample_hlb_polygon: MultiPolygon,
    sample_buildings: list[dict],
):
    """Case 2: Horizontal dividing line splits top and bottom halves."""
    # Line across the middle: lat = 11.045
    split_line = [[77.091, 11.045], [77.099, 11.045]]

    c1, c2, geom_a, geom_b = editing_service._split_geometry_and_partition_by_line(
        hlb_boundary_geom=sample_hlb_polygon,
        split_line_coordinates=split_line,
        building_dicts=sample_buildings,
    )

    assert len(c1) + len(c2) == len(sample_buildings)
    assert len(c1) > 0
    assert len(c2) > 0
    assert geom_a.is_valid
    assert geom_b.is_valid


def test_line_split_diagonal(
    editing_service: HlbEditingService,
    sample_hlb_polygon: MultiPolygon,
    sample_buildings: list[dict],
):
    """Case 3: Diagonal cut line cleanly partitions polygon."""
    split_line = [[77.091, 11.041], [77.099, 11.049]]

    c1, c2, geom_a, geom_b = editing_service._split_geometry_and_partition_by_line(
        hlb_boundary_geom=sample_hlb_polygon,
        split_line_coordinates=split_line,
        building_dicts=sample_buildings,
    )

    assert len(c1) + len(c2) == len(sample_buildings)
    assert len(c1) > 0
    assert len(c2) > 0
    assert geom_a.is_valid and geom_b.is_valid


def test_line_split_irregular(
    editing_service: HlbEditingService,
    sample_hlb_polygon: MultiPolygon,
    sample_buildings: list[dict],
):
    """Case 4: Irregular multi-vertex polyline cuts polygon."""
    split_line = [
        [77.095, 11.041],
        [77.096, 11.044],
        [77.094, 11.047],
        [77.095, 11.049],
    ]

    c1, c2, geom_a, geom_b = editing_service._split_geometry_and_partition_by_line(
        hlb_boundary_geom=sample_hlb_polygon,
        split_line_coordinates=split_line,
        building_dicts=sample_buildings,
    )

    assert len(c1) + len(c2) == len(sample_buildings)
    assert len(c1) == 10
    assert len(c2) == 10
    assert geom_a.is_valid and geom_b.is_valid


def test_line_split_left_bias(
    editing_service: HlbEditingService,
    sample_hlb_polygon: MultiPolygon,
):
    """Case 5: Line positioned near left boundary yields uneven partition."""
    buildings = [
        {"id": uuid.uuid4(), "ref": "B1", "latitude": 11.045, "longitude": 77.091},
        {"id": uuid.uuid4(), "ref": "B2", "latitude": 11.045, "longitude": 77.094},
        {"id": uuid.uuid4(), "ref": "B3", "latitude": 11.045, "longitude": 77.096},
        {"id": uuid.uuid4(), "ref": "B4", "latitude": 11.045, "longitude": 77.098},
    ]
    # Line at lng = 77.0925 (separates B1 from B2, B3, B4)
    split_line = [[77.0925, 11.041], [77.0925, 11.049]]

    c1, c2, geom_a, geom_b = editing_service._split_geometry_and_partition_by_line(
        hlb_boundary_geom=sample_hlb_polygon,
        split_line_coordinates=split_line,
        building_dicts=buildings,
    )

    assert len(c1) + len(c2) == 4
    sizes = sorted([len(c1), len(c2)])
    assert sizes == [1, 3]


def test_line_split_right_bias(
    editing_service: HlbEditingService,
    sample_hlb_polygon: MultiPolygon,
):
    """Case 6: Line positioned near right boundary yields uneven partition."""
    buildings = [
        {"id": uuid.uuid4(), "ref": "B1", "latitude": 11.045, "longitude": 77.091},
        {"id": uuid.uuid4(), "ref": "B2", "latitude": 11.045, "longitude": 77.094},
        {"id": uuid.uuid4(), "ref": "B3", "latitude": 11.045, "longitude": 77.096},
        {"id": uuid.uuid4(), "ref": "B4", "latitude": 11.045, "longitude": 77.099},
    ]
    # Line at lng = 77.098 (separates B1, B2, B3 from B4)
    split_line = [[77.098, 11.041], [77.098, 11.049]]

    c1, c2, geom_a, geom_b = editing_service._split_geometry_and_partition_by_line(
        hlb_boundary_geom=sample_hlb_polygon,
        split_line_coordinates=split_line,
        building_dicts=buildings,
    )

    assert len(c1) + len(c2) == 4
    sizes = sorted([len(c1), len(c2)])
    assert sizes == [1, 3]


def test_line_split_clustered_buildings(
    editing_service: HlbEditingService,
    sample_hlb_polygon: MultiPolygon,
):
    """Case 7: Two distinct building clusters split cleanly by dividing corridor."""
    # North-west cluster
    nw_cluster = [
        {"id": uuid.uuid4(), "ref": f"NW-{i}", "latitude": 11.048, "longitude": 77.092 + (i * 0.0005)}
        for i in range(5)
    ]
    # South-east cluster
    se_cluster = [
        {"id": uuid.uuid4(), "ref": f"SE-{i}", "latitude": 11.042, "longitude": 77.096 + (i * 0.0005)}
        for i in range(5)
    ]
    all_bldgs = nw_cluster + se_cluster

    # Diagonal corridor separating NW and SE
    split_line = [[77.0905, 11.045], [77.0995, 11.045]]

    c1, c2, geom_a, geom_b = editing_service._split_geometry_and_partition_by_line(
        hlb_boundary_geom=sample_hlb_polygon,
        split_line_coordinates=split_line,
        building_dicts=all_bldgs,
    )

    assert len(c1) == 5
    assert len(c2) == 5
    assert len(c1) + len(c2) == 10


def test_line_split_boundary_building(
    editing_service: HlbEditingService,
    sample_hlb_polygon: MultiPolygon,
):
    """Case 8: Building located directly on the cut line assigned deterministically to Part A."""
    buildings = [
        {"id": uuid.uuid4(), "ref": "B-LEFT", "latitude": 11.045, "longitude": 77.092},
        {"id": uuid.uuid4(), "ref": "B-EXACT", "latitude": 11.045, "longitude": 77.095},
        {"id": uuid.uuid4(), "ref": "B-RIGHT", "latitude": 11.045, "longitude": 77.098},
    ]
    # Cut line passes directly through B-EXACT at lng = 77.095
    split_line = [[77.095, 11.041], [77.095, 11.049]]

    c1, c2, geom_a, geom_b = editing_service._split_geometry_and_partition_by_line(
        hlb_boundary_geom=sample_hlb_polygon,
        split_line_coordinates=split_line,
        building_dicts=buildings,
    )

    # Exactly 3 buildings conserved
    assert len(c1) + len(c2) == 3
    # B-EXACT must be in c1 (deterministic assignment)
    exact_bldg = [b for b in buildings if b["ref"] == "B-EXACT"][0]
    c1_refs = {b["ref"] for b in c1}
    assert "B-EXACT" in c1_refs


def test_line_split_invalid_no_intersection(
    editing_service: HlbEditingService,
    sample_hlb_polygon: MultiPolygon,
    sample_buildings: list[dict],
):
    """Case 9: Line outside polygon or not dividing buildings raises 422."""
    # Line completely outside polygon
    outside_line = [[77.105, 11.041], [77.105, 11.049]]
    with pytest.raises(HTTPException) as exc_info:
        editing_service._split_geometry_and_partition_by_line(
            hlb_boundary_geom=sample_hlb_polygon,
            split_line_coordinates=outside_line,
            building_dicts=sample_buildings,
        )
    assert exc_info.value.status_code == 422

    # Line that leaves all buildings on one side
    edge_line = [[77.0905, 11.041], [77.0905, 11.049]]
    with pytest.raises(HTTPException) as exc_info2:
        editing_service._split_geometry_and_partition_by_line(
            hlb_boundary_geom=sample_hlb_polygon,
            split_line_coordinates=edge_line,
            building_dicts=sample_buildings,
        )
    assert exc_info2.value.status_code == 422
    assert "non-empty" in str(exc_info2.value.detail)


def test_line_split_exact_building_conservation(
    editing_service: HlbEditingService,
    sample_hlb_polygon: MultiPolygon,
    sample_buildings: list[dict],
):
    """Case 10: Strict conservation invariant holds: no dropped or duplicate buildings."""
    split_line = [[77.095, 11.041], [77.095, 11.049]]

    c1, c2, geom_a, geom_b = editing_service._split_geometry_and_partition_by_line(
        hlb_boundary_geom=sample_hlb_polygon,
        split_line_coordinates=split_line,
        building_dicts=sample_buildings,
    )

    c1_ids = {b["id"] for b in c1}
    c2_ids = {b["id"] for b in c2}
    total_ids = {b["id"] for b in sample_buildings}

    # No overlaps
    assert len(c1_ids.intersection(c2_ids)) == 0
    # Exact union
    assert c1_ids.union(c2_ids) == total_ids
    # Exact count
    assert len(c1) + len(c2) == len(sample_buildings)

