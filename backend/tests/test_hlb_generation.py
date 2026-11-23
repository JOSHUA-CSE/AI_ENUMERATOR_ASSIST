import uuid as _uuid

import pytest
from shapely.geometry import Polygon, box

from app.gis.hlb.boundary_builder import (
    build_hlb_boundary,
    build_partitioned_hlb_boundaries,
)
from app.gis.hlb.clustering import partition_buildings_spatially
from app.gis.hlb.validation import (
    recalculate_exact_building_counts,
    validate_and_score_hlb,
    validate_generation_invariants,
    validate_layout_partition_geometry,
)
from app.gis.spatial import (
    validate_and_convert_geojson_polygon,
    validate_and_convert_point,
)
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import BuildingSourceType, House
from app.models.layout import Layout, LayoutStatus, LayoutVersion, LayoutVersionStatus

SAMPLE_VILLAGE_BOUNDARY = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.1100, 11.0700],
            [77.1400, 11.0700],
            [77.1400, 11.1000],
            [77.1100, 11.1000],
            [77.1100, 11.0700],
        ]
    ],
}


def get_auth_headers(client, username, password="password123"):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_tables(db):
    db.query(HlbHouse).delete()
    db.query(HouselistingBlock).delete()
    db.query(LayoutVersion).delete()
    db.query(Layout).delete()
    db.query(House).delete()
    db.query(AdministrativeArea).delete()
    db.commit()


# ----------------------------------------------------------------------
# Unit Tests — Spatial Algorithm & Building-Count Balancing
# ----------------------------------------------------------------------


def test_spatial_clustering_multiple_deputy_targets():
    """
    Test 1,240 detected buildings against various Deputy targets:
    Target = 200 -> ~7 HLBs (ceil(1240/200) = 7)
    Target = 250 -> ~5 HLBs (ceil(1240/250) = 5)
    Target = 100 -> ~13 HLBs (ceil(1240/100) = 13)
    Target = 300 -> ~5 HLBs (ceil(1240/300) = 5)
    """
    buildings = []
    for i in range(1240):
        lat = 11.070 + (i % 35) * 0.0008
        lon = 77.110 + (i // 35) * 0.0008
        buildings.append(
            {
                "id": f"bld-{i}",
                "ref": f"BLD-{i:04d}",
                "latitude": lat,
                "longitude": lon,
            }
        )

    # 1. Target = 200
    clusters_200 = partition_buildings_spatially(
        buildings, target_buildings_per_hlb=200
    )
    assert 6 <= len(clusters_200) <= 8
    inv_200 = validate_generation_invariants(1240, clusters_200)
    assert inv_200["is_valid"] is True
    assert inv_200["total_assigned"] == 1240
    assert inv_200["duplicate_count"] == 0
    assert inv_200["unassigned_count"] == 0

    # 2. Target = 250
    clusters_250 = partition_buildings_spatially(
        buildings, target_buildings_per_hlb=250
    )
    assert 4 <= len(clusters_250) <= 6
    inv_250 = validate_generation_invariants(1240, clusters_250)
    assert inv_250["is_valid"] is True

    # 3. Target = 100
    clusters_100 = partition_buildings_spatially(
        buildings, target_buildings_per_hlb=100
    )
    assert 11 <= len(clusters_100) <= 15
    inv_100 = validate_generation_invariants(1240, clusters_100)
    assert inv_100["is_valid"] is True

    # 4. Target = 300
    clusters_300 = partition_buildings_spatially(
        buildings, target_buildings_per_hlb=300
    )
    assert 4 <= len(clusters_300) <= 6
    inv_300 = validate_generation_invariants(1240, clusters_300)
    assert inv_300["is_valid"] is True


def test_spatial_clustering_edge_cases():
    """
    Edge cases:
    - 0 buildings -> 0 clusters
    - 1 building -> 1 cluster
    - 50 buildings with target 200 -> 1 cluster without artificial division
    """
    assert partition_buildings_spatially([], target_buildings_per_hlb=200) == []

    single = [{"id": "b1", "latitude": 11.08, "longitude": 77.12}]
    res_single = partition_buildings_spatially(single, target_buildings_per_hlb=200)
    assert len(res_single) == 1
    assert len(res_single[0]) == 1

    small = [
        {"id": f"b{i}", "latitude": 11.08 + i * 0.0001, "longitude": 77.12}
        for i in range(50)
    ]
    res_small = partition_buildings_spatially(small, target_buildings_per_hlb=200)
    assert len(res_small) == 1
    assert len(res_small[0]) == 50


def test_boundary_builder_and_containment():
    """
    HLB boundaries must remain strictly inside the parent layout boundary.
    """
    layout_polygon = box(77.110, 11.070, 77.140, 11.100)

    cluster_buildings = [
        {"latitude": 11.075, "longitude": 77.115, "footprint": None},
        {"latitude": 11.078, "longitude": 77.118, "footprint": None},
        {"latitude": 11.079, "longitude": 77.120, "footprint": None},
        {"latitude": 11.076, "longitude": 77.119, "footprint": None},
    ]

    boundary = build_hlb_boundary(cluster_buildings, layout_polygon)
    assert boundary.is_valid
    assert not boundary.is_empty
    assert layout_polygon.contains(boundary) or layout_polygon.covers(boundary)


def test_validation_and_scoring_against_deputy_target():
    """
    Quality scoring and count deviation must be computed against the
    Deputy's target_buildings_per_hlb (e.g. target 200 with 198 buildings
    yielding deviation -2).
    """
    layout_polygon = box(77.110, 11.070, 77.140, 11.100)
    hlb_poly = Polygon(
        [
            [77.112, 11.072],
            [77.125, 11.072],
            [77.125, 11.085],
            [77.112, 11.085],
            [77.112, 11.072],
        ]
    )

    result = validate_and_score_hlb(
        hlb_code="HLB-001",
        building_count=198,
        target_buildings_per_hlb=200,
        hlb_boundary_geom=hlb_poly,
        layout_boundary_geom=layout_polygon,
    )

    assert result["block_code"] == "HLB-001"
    assert result["building_count"] == 198
    assert result["target_buildings_per_hlb"] == 200
    assert result["count_deviation"] == -2
    assert result["validation_status"] == "VALID"
    assert result["quality_score"] >= 0.90
    assert result["scores"]["boundary_score"] == 1.0


# ----------------------------------------------------------------------
# API Integration Tests
# ----------------------------------------------------------------------


def test_create_layout_and_generate_hlbs_success(client, db):
    """
    Test creating a Layout and generating Candidate HLBs with
    target_buildings_per_hlb=200.
    """
    headers = get_auth_headers(client, "deputy")

    # 1. Create Area
    area = AdministrativeArea(
        name="Arasur Village",
        type=AreaType.VILLAGE,
        code="VILL-638401",
        boundary=validate_and_convert_geojson_polygon(SAMPLE_VILLAGE_BOUNDARY),
        status="ACTIVE",
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    # 2. Add 500 building records
    houses = []
    for i in range(500):
        lat = 11.075 + (i % 25) * 0.0008
        lon = 77.115 + (i // 25) * 0.0008
        h = House(
            area_id=area.id,
            building_reference=f"BLD-{i:04d}",
            latitude=lat,
            longitude=lon,
            location=validate_and_convert_point(lat, lon),
            source_type=BuildingSourceType.SATELLITE_DETECTED,
            detection_confidence=0.88,
            imagery_source="Google Open Buildings V3",
        )
        houses.append(h)
    db.add_all(houses)
    db.commit()

    # 3. Create Layout
    create_layout_payload = {
        "area_id": str(area.id),
        "name": "Arasur Village Layout",
        "target_buildings_per_hlb": 200,
    }
    resp_create = client.post(
        "/api/v1/layouts", json=create_layout_payload, headers=headers
    )
    assert resp_create.status_code == 201
    layout_data = resp_create.json()
    layout_id = layout_data["id"]
    assert layout_data["status"] == "DRAFT"
    assert layout_data["actual_building_count"] == 500

    # 4. Generate Candidate HLBs with target 200
    resp_gen = client.post(
        f"/api/v1/layouts/{layout_id}/generate-hlbs",
        json={"target_buildings_per_hlb": 200},
        headers=headers,
    )
    assert resp_gen.status_code == 200
    gen_data = resp_gen.json()
    assert gen_data["layout_id"] == layout_id
    assert gen_data["version_number"] == 1
    assert gen_data["target_buildings_per_hlb"] == 200
    assert gen_data["total_buildings"] == 500
    assert 2 <= gen_data["hlb_count"] <= 4

    for hlb in gen_data["hlbs"]:
        assert hlb["actual_building_count"] > 0
        assert hlb["target_building_count"] == 200
        assert "count_deviation" in hlb
        assert hlb["boundary"]["type"] in ("Polygon", "MultiPolygon")
        assert hlb["validation_status"] in ("VALID", "WARNING")

    # 5. Verify GET /layouts/{id}/hlbs
    resp_hlbs = client.get(f"/api/v1/layouts/{layout_id}/hlbs", headers=headers)
    assert resp_hlbs.status_code == 200
    hlb_list = resp_hlbs.json()
    assert len(hlb_list["items"]) == gen_data["hlb_count"]


def test_regeneration_creates_new_version_and_records_target(client, db):
    """
    Regeneration with different target (200 -> 100) must create Version 2,
    record target 100, and mark Version 1 as SUPERSEDED.
    """
    headers = get_auth_headers(client, "deputy")

    area = AdministrativeArea(
        name="Arasur Village",
        type=AreaType.VILLAGE,
        code="VILL-638401",
        boundary=validate_and_convert_geojson_polygon(SAMPLE_VILLAGE_BOUNDARY),
        status="ACTIVE",
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    houses = []
    for i in range(250):
        lat = 11.075 + (i % 15) * 0.001
        lon = 77.115 + (i // 15) * 0.001
        h = House(
            area_id=area.id,
            building_reference=f"BLD-{i:04d}",
            latitude=lat,
            longitude=lon,
            location=validate_and_convert_point(lat, lon),
            source_type=BuildingSourceType.SATELLITE_DETECTED,
            detection_confidence=0.88,
            imagery_source="Google Open Buildings V3",
        )
        houses.append(h)
    db.add_all(houses)
    db.commit()

    create_resp = client.post(
        "/api/v1/layouts",
        json={
            "area_id": str(area.id),
            "name": "Arasur Village Layout",
            "target_buildings_per_hlb": 200,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    layout_id = create_resp.json()["id"]

    # Run Generation 1 (Target = 200)
    resp1 = client.post(
        f"/api/v1/layouts/{layout_id}/generate-hlbs",
        json={"target_buildings_per_hlb": 200},
        headers=headers,
    )
    assert resp1.status_code == 200
    v1_id = resp1.json()["version_id"]

    # Run Generation 2 (Target = 100)
    resp2 = client.post(
        f"/api/v1/layouts/{layout_id}/generate-hlbs",
        json={"target_buildings_per_hlb": 100},
        headers=headers,
    )
    assert resp2.status_code == 200
    v2_data = resp2.json()
    assert v2_data["version_number"] == 2
    assert v2_data["target_buildings_per_hlb"] == 100
    assert 2 <= v2_data["hlb_count"] <= 4

    # Check that Version 1 is SUPERSEDED and Version 2 is CANDIDATE
    v1 = db.query(LayoutVersion).filter(LayoutVersion.id == _uuid.UUID(v1_id)).first()
    assert v1.status == LayoutVersionStatus.SUPERSEDED
    assert v1.target_buildings_per_hlb == 200


def test_generate_hlbs_rejects_non_positive_target(client, db):
    """
    Validate that target_buildings_per_hlb <= 0 is rejected with 422.
    """
    headers = get_auth_headers(client, "deputy")

    area = AdministrativeArea(
        name="Arasur Village",
        type=AreaType.VILLAGE,
        code="VILL-638401",
        boundary=validate_and_convert_geojson_polygon(SAMPLE_VILLAGE_BOUNDARY),
        status="ACTIVE",
    )
    db.add(area)
    db.commit()

    layout = Layout(
        area_id=area.id,
        name="Arasur Layout",
        target_hlb_building_count=200,
        boundary=area.boundary,
        status=LayoutStatus.DRAFT,
    )
    db.add(layout)
    db.commit()

    resp_zero = client.post(
        f"/api/v1/layouts/{layout.id}/generate-hlbs",
        json={"target_buildings_per_hlb": 0},
        headers=headers,
    )
    assert resp_zero.status_code in (400, 422)

    resp_neg = client.post(
        f"/api/v1/layouts/{layout.id}/generate-hlbs",
        json={"target_buildings_per_hlb": -50},
        headers=headers,
    )
    assert resp_neg.status_code in (400, 422)


def test_rbac_authorization_for_hlb_generation(client, db):
    """
    Verify Deputy can generate (200), while Supervisor and Enumerator receive 403.
    """
    area = AdministrativeArea(
        name="Arasur Village",
        type=AreaType.VILLAGE,
        code="VILL-638401",
        boundary=validate_and_convert_geojson_polygon(SAMPLE_VILLAGE_BOUNDARY),
        status="ACTIVE",
    )
    db.add(area)
    db.commit()

    h = House(
        area_id=area.id,
        building_reference="BLD-0001",
        latitude=11.080,
        longitude=77.120,
        location=validate_and_convert_point(11.080, 77.120),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    db.add(h)
    db.commit()

    layout = Layout(
        area_id=area.id,
        name="Arasur Layout",
        target_hlb_building_count=250,
        boundary=area.boundary,
        status=LayoutStatus.DRAFT,
    )
    db.add(layout)
    db.commit()

    deputy_headers = get_auth_headers(client, "deputy")
    supervisor_headers = get_auth_headers(client, "supervisor")
    enumerator_headers = get_auth_headers(client, "enumerator")

    # Supervisor -> 403
    resp_sup = client.post(
        f"/api/v1/layouts/{layout.id}/generate-hlbs",
        json={"target_buildings_per_hlb": 250},
        headers=supervisor_headers,
    )
    assert resp_sup.status_code == 403

    # Enumerator -> 403
    resp_enum = client.post(
        f"/api/v1/layouts/{layout.id}/generate-hlbs",
        json={"target_buildings_per_hlb": 250},
        headers=enumerator_headers,
    )
    assert resp_enum.status_code == 403

    # Deputy -> 200
    resp_dep = client.post(
        f"/api/v1/layouts/{layout.id}/generate-hlbs",
        json={"target_buildings_per_hlb": 250},
        headers=deputy_headers,
    )
    assert resp_dep.status_code == 200


def test_build_partitioned_hlb_boundaries_zero_gaps_zero_overlaps():
    """
    Territory partitioning must completely partition parent layout polygon:
    - Gap ratio == 0.0
    - Max overlap ratio == 0.0
    - Total buildings preserved across partitions
    """
    layout_polygon = box(77.110, 11.070, 77.140, 11.100)
    buildings = [
        {"id": f"b-{i}", "latitude": 11.071 + (i % 20) * 0.0014, "longitude": 77.111 + (i // 20) * 0.0014}
        for i in range(500)
    ]

    partitions = build_partitioned_hlb_boundaries(
        buildings=buildings,
        layout_boundary_geom=layout_polygon,
        target_buildings_per_hlb=125,
    )

    assert len(partitions) == 4
    hlb_geoms = [p[0] for p in partitions]

    geom_val = validate_layout_partition_geometry(
        hlb_boundaries=hlb_geoms,
        layout_boundary_geom=layout_polygon,
    )

    assert geom_val["is_valid"] is True
    assert geom_val["metrics"]["gap_ratio"] < 0.0001
    assert geom_val["metrics"]["max_pairwise_overlap_ratio"] < 0.0001
    assert geom_val["metrics"]["gap_passed"] is True
    assert geom_val["metrics"]["overlap_passed"] is True


def test_recalculate_exact_building_counts_shared_boundary_tie_breaking():
    """
    Building points lying on the exact shared border of adjacent HLBs must be
    assigned deterministically to exactly one HLB (zero duplicates, zero unassigned).
    """
    # Create two adjacent unit boxes sharing edge x=10.0
    poly1 = box(0.0, 0.0, 10.0, 10.0)
    poly2 = box(10.0, 0.0, 20.0, 10.0)

    # 3 points: inside poly1, on shared edge x=10.0, inside poly2
    buildings = [
        {"id": "b-left", "latitude": 5.0, "longitude": 5.0},
        {"id": "b-shared", "latitude": 5.0, "longitude": 10.0},
        {"id": "b-right", "latitude": 5.0, "longitude": 15.0},
    ]

    result = recalculate_exact_building_counts(
        hlb_boundaries=[poly1, poly2],
        buildings=buildings,
        target_buildings_per_hlb=2,
    )

    assert result["is_valid"] is True
    assert result["total_input_buildings"] == 3
    assert result["unassigned_count"] == 0
    assert result["duplicate_count"] == 0
    # Shared point deterministically assigned to first polygon (index 0)
    assert result["building_assignments"]["b-shared"] == 0
    assert result["counts"] == [2, 1]


def test_validate_layout_partition_geometry_detects_gap_and_overlap():
    """
    Validation service must flag significant gap or overlap as invalid.
    """
    parent = box(77.110, 11.070, 77.140, 11.100)

    # Incomplete coverage (only half the box -> gap ratio 0.50)
    half_hlb = box(77.110, 11.070, 77.125, 11.100)
    val_gap = validate_layout_partition_geometry(
        hlb_boundaries=[half_hlb],
        layout_boundary_geom=parent,
    )
    assert val_gap["is_valid"] is False
    assert val_gap["metrics"]["gap_passed"] is False
    assert any("unallocated gap area" in err for err in val_gap["errors"])

    # Overlapping HLBs
    poly1 = box(77.110, 11.070, 77.130, 11.100)
    poly2 = box(77.120, 11.070, 77.140, 11.100)
    val_overlap = validate_layout_partition_geometry(
        hlb_boundaries=[poly1, poly2],
        layout_boundary_geom=parent,
    )
    assert val_overlap["is_valid"] is False
    assert val_overlap["metrics"]["overlap_passed"] is False
    assert any("overlap significantly" in err for err in val_overlap["errors"])


def test_real_arasur_16374_exact_partition_and_counting():
    """
    Verify engine on the 16,374 real Google Open Buildings V3 footprints:
    - Balanced K = 66 blocks (target 250)
    - Zero gaps (<0.0001)
    - Zero overlaps (<0.0001)
    - Total buildings = 16,374 with 0 unassigned and 0 duplicates
    """
    import json
    from pathlib import Path

    json_path = Path("app/data/open_buildings/arasur_real_open_buildings_v3.json")
    if not json_path.exists():
        pytest.skip("Real dataset not present in local test environment")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    bldgs = data["buildings"]
    assert len(bldgs) == 16374

    lats = [b["latitude"] for b in bldgs]
    lons = [b["longitude"] for b in bldgs]
    envelope = box(min(lons) - 0.001, min(lats) - 0.001, max(lons) + 0.001, max(lats) + 0.001)

    partitions = build_partitioned_hlb_boundaries(
        buildings=bldgs,
        layout_boundary_geom=envelope,
        target_buildings_per_hlb=250,
    )
    assert len(partitions) == 66

    hlb_geoms = [p[0] for p in partitions]

    exact_res = recalculate_exact_building_counts(
        hlb_boundaries=hlb_geoms,
        buildings=bldgs,
        target_buildings_per_hlb=250,
    )
    assert exact_res["is_valid"] is True
    assert exact_res["total_input_buildings"] == 16374
    assert exact_res["unassigned_count"] == 0
    assert exact_res["duplicate_count"] == 0
    assert min(exact_res["counts"]) >= 245
    assert max(exact_res["counts"]) <= 255


def test_boundary_guard_refuses_unverified_boundary(client, db):
    """
    HLB generation must refuse to run if boundary_status is not OFFICIAL or PROVISIONAL.
    """
    area = AdministrativeArea(
        name="Unverified Area",
        type=AreaType.VILLAGE,
        code="VILL-UNVERIFIED",
        boundary=validate_and_convert_geojson_polygon(SAMPLE_VILLAGE_BOUNDARY),
        boundary_status="ESTIMATED",
        status="ACTIVE",
    )
    db.add(area)
    db.commit()

    h = House(
        area_id=area.id,
        building_reference="BLD-UNV-1",
        latitude=11.080,
        longitude=77.120,
        location=validate_and_convert_point(11.080, 77.120),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    db.add(h)
    db.commit()

    layout = Layout(
        area_id=area.id,
        name="Unverified Layout",
        target_hlb_building_count=250,
        boundary=area.boundary,
        boundary_status="ESTIMATED",
        status=LayoutStatus.DRAFT,
    )
    db.add(layout)
    db.commit()

    deputy_headers = get_auth_headers(client, "deputy")
    resp = client.post(
        f"/api/v1/layouts/{layout.id}/generate-hlbs",
        json={"target_buildings_per_hlb": 250},
        headers=deputy_headers,
    )
    assert resp.status_code == 400
    assert "boundary status" in resp.json()["detail"].lower()


def test_provisional_boundary_loader():
    """
    Verify loading provisional boundary GeoJSON for Arasur.
    """
    from app.gis.boundary_loader import load_provisional_boundary

    geom, meta = load_provisional_boundary("arasur")
    assert geom.is_valid is True
    assert meta["boundary_status"] == "PROVISIONAL"
    assert "area_sq_km" in meta
    assert meta["area_sq_km"] > 0.0


def test_per_hlb_quality_metrics_structure():
    """
    Verify calculation of individual HLB quality metrics including Polsby-Popper compactness,
    longest axis, road crossings, and estimated walking distance.
    """
    from app.gis.hlb.quality_metrics import (
        calculate_hlb_quality_metrics,
        get_osm_road_segments_tree,
    )

    test_box = box(77.110, 11.080, 77.120, 11.090)
    buildings = [
        {"latitude": 11.082, "longitude": 77.112},
        {"latitude": 11.085, "longitude": 77.115},
        {"latitude": 11.088, "longitude": 77.118},
    ]

    road_data = get_osm_road_segments_tree()
    road_tree = road_data[1] if road_data else None

    metrics = calculate_hlb_quality_metrics(
        hlb_boundary_geom=test_box,
        cluster_buildings=buildings,
        road_tree=road_tree,
    )

    assert "area_sq_meters" in metrics
    assert metrics["area_sq_meters"] > 0
    assert "compactness" in metrics
    assert 0.0 <= metrics["compactness"] <= 1.0
    assert "longest_axis_meters" in metrics
    assert metrics["longest_axis_meters"] > 0
    assert "boundary_intersecting_buildings_count" in metrics
    assert "road_segments_crossed_count" in metrics
    assert "estimated_walking_distance_km" in metrics
    assert isinstance(metrics["quality_warnings"], list)


def test_centroid_in_polygon_clipping_arasur():
    """
    Centroid clipping must filter out raw bounding-box buildings that fall outside
    the provisional Arasur village boundary.
    """
    import json
    from pathlib import Path
    from shapely.geometry import Point
    from app.gis.boundary_loader import load_provisional_boundary

    prov_boundary, meta = load_provisional_boundary("arasur")

    raw_path = Path("app/data/open_buildings/arasur_real_open_buildings_v3.json")
    if not raw_path.exists():
        pytest.skip("arasur_real_open_buildings_v3.json not found")

    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    raw_bldgs = raw_data["buildings"]
    assert len(raw_bldgs) == 16374

    inside = [
        b for b in raw_bldgs
        if prov_boundary.contains(Point(b["longitude"], b["latitude"]))
        or prov_boundary.touches(Point(b["longitude"], b["latitude"]))
    ]

    # Exactly 10,583 building centroids are inside provisional Arasur
    assert len(inside) == 10583
    assert len(raw_bldgs) - len(inside) == 5791


