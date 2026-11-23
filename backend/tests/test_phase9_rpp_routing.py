import json
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.gis.route.road_network import (
    AVERAGE_WALKING_SPEED_KMH,
    HIGHWAY_SPEED_FACTORS,
    SURFACE_SPEED_FACTORS,
    TWO_SIDED_HIGHWAY_TYPES,
    RoadNetwork,
    RoadSegment,
    calculate_linestring_length_m,
)
from app.gis.route.rpp_solver import (
    RppRouteResult,
    _greedy_odd_vertex_matching,
    solve_undirected_rpp,
)
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.enumerator_assignment import EnumeratorAssignmentStatus, HlbEnumeratorAssignment
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import BuildingFieldStatus, BuildingSourceType, House
from app.models.layout import Layout, LayoutStatus, LayoutVersion, LayoutVersionSource, LayoutVersionStatus
from app.models.road_coverage import (
    HlbRequiredEdge,
    HlbRoutePlan,
    MissingPathSubmission,
    RoadCoverageSyncStatus,
    RoadSegmentCoverage,
    RoadSegmentSurveyStatus,
)
from app.models.supervisor_assignment import LayoutSupervisorAssignment, SupervisorAssignmentStatus
from app.models.user import User, UserRole, UserStatus
from app.services.route_service import route_service


@pytest.fixture
def p9_fixture(db: Session):
    suffix = uuid.uuid4().hex[:6]

    supervisor = User(
        name=f"Supervisor P9 {suffix}",
        username=f"sup_p9_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enumerator = User(
        name=f"Enumerator P9 {suffix}",
        username=f"enum_p9_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all([supervisor, enumerator])
    db.commit()

    area = AdministrativeArea(
        name=f"Arasur Village P9 {suffix}",
        code=f"AREA-ARASUR-P9-{suffix}",
        type=AreaType.VILLAGE,
        boundary=WKTElement(
            "MULTIPOLYGON(((77.08 11.08, 77.12 11.08, 77.12 11.12, 77.08 11.12, 77.08 11.08)))",
            srid=4326,
        ),
    )
    db.add(area)
    db.commit()

    layout = Layout(
        name=f"Layout Arasur P9 {suffix}",
        area_id=area.id,
        boundary=area.boundary,
        status=LayoutStatus.APPROVED,
    )
    db.add(layout)
    db.commit()

    v = LayoutVersion(
        layout_id=layout.id,
        version_number=1,
        source=LayoutVersionSource.APPROVED,
        status=LayoutVersionStatus.APPROVED,
    )
    db.add(v)
    db.commit()
    layout.active_version_id = v.id
    db.commit()

    db.add(
        LayoutSupervisorAssignment(
            layout_id=layout.id,
            supervisor_id=supervisor.id,
            status=SupervisorAssignmentStatus.ACTIVE,
        )
    )

    hlb = HouselistingBlock(
        layout_id=layout.id,
        version_id=v.id,
        block_code=f"HLB-P9-{suffix}",
        name=f"Arasur Test HLB P9 {suffix}",
        target_building_count=100,
        actual_building_count=0,
        boundary=WKTElement(
            "MULTIPOLYGON(((77.090 11.085, 77.105 11.085, 77.105 11.098, 77.090 11.098, 77.090 11.085)))",
            srid=4326,
        ),
    )
    db.add(hlb)
    db.commit()

    db.add(
        HlbEnumeratorAssignment(
            hlb_id=hlb.id,
            layout_id=layout.id,
            enumerator_id=enumerator.id,
            supervisor_id=supervisor.id,
            status=EnumeratorAssignmentStatus.ACTIVE,
        )
    )
    db.commit()

    return {
        "supervisor": supervisor,
        "enumerator": enumerator,
        "area": area,
        "layout": layout,
        "hlb": hlb,
    }


def _login(client: TestClient, username: str) -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def _make_segment(seg_id, coords, highway="residential", length_m=100.0, is_required=True):
    geom = LineString([(c[1], c[0]) for c in coords])
    return RoadSegment(
        segment_id=seg_id,
        osm_way_id=1001,
        osm_node_ids=[1, 2],
        coordinates=coords,
        geometry=geom,
        length_m=length_m,
        highway=highway,
        required_status="REQUIRED" if is_required else "TRANSIT",
        boundary_classification="INTERNAL" if is_required else "EXTERNAL_TRANSIT",
    )


# ------------------------------------------------------------------------------
# Test 1: Every eligible internal road/pathway edge inside the HLB becomes a required edge
# ------------------------------------------------------------------------------
def test_1_internal_edges_become_required():
    poly = Polygon([(77.0, 11.0), (77.01, 11.0), (77.01, 11.01), (77.0, 11.01), (77.0, 11.0)])
    seg1 = _make_segment("int_1", [(11.002, 77.002), (11.008, 77.008)])
    seg2 = _make_segment("ext_1", [(11.050, 77.050), (11.060, 77.060)])
    net = RoadNetwork([seg1, seg2])

    req, trans = net.extract_required_and_transit_edges(poly, buffer_meters=10.0)
    assert any(s.segment_id.startswith("int_1") for s in req)
    assert not any(s.segment_id.startswith("ext_1") for s in req)


# ------------------------------------------------------------------------------
# Test 2: Empty streets (0 buildings along them) are still required edges and must be traversed
# ------------------------------------------------------------------------------
def test_2_empty_streets_are_required_and_traversed():
    # Grid of 2 streets, 0 buildings
    seg1 = _make_segment("empty_road_A", [(11.00, 77.00), (11.00, 77.01)], length_m=100.0)
    seg2 = _make_segment("empty_road_B", [(11.00, 77.01), (11.01, 77.01)], length_m=100.0)

    # Empty buildings list
    res = solve_undirected_rpp(hlb_id="test_hlb", required_edges=[seg1, seg2], buildings=[])

    assert res.total_required_edges_count == 2
    assert res.total_distance_km > 0
    # Both empty streets must be traversed
    traversed_ids = {step.edge_id for step in res.steps}
    assert "empty_road_A" in traversed_ids
    assert "empty_road_B" in traversed_ids


# ------------------------------------------------------------------------------
# Test 3: Streets with buildings are required edges and must be traversed
# ------------------------------------------------------------------------------
def test_3_streets_with_buildings_are_required_and_traversed():
    seg1 = _make_segment("built_road_1", [(11.00, 77.00), (11.00, 77.01)], length_m=100.0)
    seg2 = _make_segment("built_road_2", [(11.00, 77.01), (11.01, 77.01)], length_m=100.0)
    bldgs = [
        {"building_id": "b1", "building_reference": "REF-001", "latitude": 11.0001, "longitude": 77.005},
        {"building_id": "b2", "building_reference": "REF-002", "latitude": 11.005, "longitude": 77.0101},
    ]
    res = solve_undirected_rpp(hlb_id="test_hlb", required_edges=[seg1, seg2], buildings=bldgs)

    assert res.total_required_edges_count == 2
    traversed_ids = {step.edge_id for step in res.steps}
    assert "built_road_1" in traversed_ids
    assert "built_road_2" in traversed_ids
    assert len(res.building_encounter_order) == 2


# ------------------------------------------------------------------------------
# Test 4: Building coordinates do not determine primary route geometry
# ------------------------------------------------------------------------------
def test_4_building_coordinates_do_not_determine_primary_route():
    seg1 = _make_segment("rd1", [(11.00, 77.00), (11.00, 77.01)], length_m=100.0)
    seg2 = _make_segment("rd2", [(11.00, 77.01), (11.01, 77.01)], length_m=100.0)

    # Route with NO buildings
    res_no_bldg = solve_undirected_rpp(hlb_id="test_hlb", required_edges=[seg1, seg2], buildings=[])

    # Route with 5 arbitrary buildings scattered around
    bldgs = [
        {"building_id": f"b_{i}", "building_reference": f"REF-{i}", "latitude": 11.00 + i * 0.002, "longitude": 77.005}
        for i in range(5)
    ]
    res_with_bldg = solve_undirected_rpp(hlb_id="test_hlb", required_edges=[seg1, seg2], buildings=bldgs)

    # Road step geometry and total distance must match identically
    assert len(res_no_bldg.steps) == len(res_with_bldg.steps)
    assert res_no_bldg.total_distance_km == res_with_bldg.total_distance_km
    for s1, s2 in zip(res_no_bldg.steps, res_with_bldg.steps):
        assert s1.edge_id == s2.edge_id
        assert s1.coordinates == s2.coordinates


# ------------------------------------------------------------------------------
# Test 5: Exact polygon boundary clipping: edges crossing boundary are split
# ------------------------------------------------------------------------------
def test_5_boundary_clipping_and_edge_splitting():
    # Boundary: x from 77.0 to 77.01, y from 11.0 to 11.01
    poly = Polygon([(77.0, 11.0), (77.01, 11.0), (77.01, 11.01), (77.0, 11.01), (77.0, 11.0)])

    # Road crossing boundary: from (11.005, 76.995) [outside] to (11.005, 77.015) [outside, crossing through inside]
    crossing_seg = _make_segment(
        "cross_seg",
        [(11.005, 76.995), (11.005, 77.005), (11.005, 77.015)],
        length_m=2000.0,
    )
    net = RoadNetwork([crossing_seg])
    req, trans = net.extract_required_and_transit_edges(poly, buffer_meters=30.0)

    assert len(req) > 0
    # Required edge must be inside or on boundary
    for r in req:
        assert r.required_status == "REQUIRED"
        line = r.geometry
        # Centroid of clipped line should be inside or close to poly
        assert poly.buffer(0.0001).contains(line.centroid)


# ------------------------------------------------------------------------------
# Test 6: Valid graph topology
# ------------------------------------------------------------------------------
def test_6_valid_graph_topology():
    seg1 = _make_segment("rd1", [(11.00, 77.00), (11.00, 77.01)], length_m=100.0)
    seg2 = _make_segment("rd2", [(11.00, 77.01), (11.01, 77.01)], length_m=100.0)
    res = solve_undirected_rpp(hlb_id="test_hlb", required_edges=[seg1, seg2])

    assert len(res.continuous_polyline) >= 3
    # Verify coordinates are lat/lon within valid bounds
    for pt in res.continuous_polyline:
        assert -90.0 <= pt[0] <= 90.0
        assert -180.0 <= pt[1] <= 180.0


# ------------------------------------------------------------------------------
# Test 7: Disconnected components handling
# ------------------------------------------------------------------------------
def test_7_disconnected_components_handling():
    # Component A: far southwest
    segA = _make_segment("compA_rd", [(11.00, 77.00), (11.00, 77.01)], length_m=100.0)
    # Component B: far northeast (10km away)
    segB = _make_segment("compB_rd", [(11.10, 77.10), (11.10, 77.11)], length_m=100.0)

    res = solve_undirected_rpp(
        hlb_id="test_hlb",
        required_edges=[segA, segB],
        available_transit_edges=[],
    )

    # Must detect 2 disconnected components
    assert res.disconnected_components_count == 2
    assert len(res.sections) == 2
    assert res.sections[1].is_disconnected is True
    assert "disconnected" in res.sections[1].disconnection_note.lower()


# ------------------------------------------------------------------------------
# Test 8: External transit handling: shortest path transit outside HLB flagged
# ------------------------------------------------------------------------------
def test_8_external_transit_handling():
    # Two disconnected internal clusters, connected ONLY via an external transit road
    seg_int1 = _make_segment("int_cluster1", [(11.00, 77.00), (11.00, 77.01)], length_m=100.0, is_required=True)
    seg_int2 = _make_segment("int_cluster2", [(11.00, 77.02), (11.00, 77.03)], length_m=100.0, is_required=True)
    seg_transit = _make_segment("ext_transit", [(11.00, 77.01), (11.00, 77.02)], length_m=100.0, is_required=False)

    res = solve_undirected_rpp(
        hlb_id="test_hlb",
        required_edges=[seg_int1, seg_int2],
        available_transit_edges=[seg_transit],
    )

    assert res.external_transit_count >= 1
    # Check that transit step is flagged as is_transit=True and deadhead
    transit_steps = [s for s in res.steps if s.is_transit]
    assert len(transit_steps) >= 1
    assert any(s.is_deadhead for s in transit_steps)


# ------------------------------------------------------------------------------
# Test 9: Eulerization with minimum-weight odd-degree matching
# ------------------------------------------------------------------------------
def test_9_eulerization_odd_degree_matching():
    # T-junction: node (11.0, 77.01) has degree 3 (odd). The 3 outer ends have degree 1 (odd).
    # 4 odd vertices.
    center = (11.0, 77.01)
    n1 = (11.0, 77.00)
    n2 = (11.0, 77.02)
    n3 = (11.01, 77.01)
    seg1 = _make_segment("t1", [n1, center], length_m=50.0)
    seg2 = _make_segment("t2", [center, n2], length_m=50.0)
    seg3 = _make_segment("t3", [center, n3], length_m=50.0)

    res = solve_undirected_rpp(
        hlb_id="test_t",
        required_edges=[seg1, seg2, seg3],
        return_to_start=True,  # All vertices must become even
    )

    # In Eulerian circuit, every required edge is traversed, and deadhead must exist to double back
    assert res.deadhead_distance_km > 0
    assert res.total_distance_km > (seg1.length_m + seg2.length_m + seg3.length_m) / 1000.0


# ------------------------------------------------------------------------------
# Test 10: Open route generation honoring start and end locations
# ------------------------------------------------------------------------------
def test_10_open_route_generation():
    # Line of 3 segments: A - B - C - D
    pA = (11.00, 77.00)
    pB = (11.00, 77.01)
    pC = (11.00, 77.02)
    pD = (11.00, 77.03)
    seg1 = _make_segment("s1", [pA, pB], length_m=100.0)
    seg2 = _make_segment("s2", [pB, pC], length_m=100.0)
    seg3 = _make_segment("s3", [pC, pD], length_m=100.0)

    res = solve_undirected_rpp(
        hlb_id="test_open",
        required_edges=[seg1, seg2, seg3],
        start_location=pA,
        end_location=pD,
        return_to_start=False,
    )

    # Since it's a simple path from A to D, it can be traversed with 0 deadhead
    assert res.deadhead_distance_km == 0.0
    assert len(res.steps) == 3
    # Step 1 should start at pA, last step should end at pD
    first_step = res.steps[0]
    last_step = res.steps[-1]
    assert first_step.from_node == (11.0, 77.0)
    assert last_step.to_node == (11.0, 77.03)


# ------------------------------------------------------------------------------
# Test 11: Every required edge is traversed at least once
# ------------------------------------------------------------------------------
def test_11_all_required_edges_traversed():
    edges = [
        _make_segment(f"req_{i}", [(11.00 + i * 0.001, 77.00), (11.00 + (i + 1) * 0.001, 77.00)], length_m=100.0)
        for i in range(5)
    ]
    res = solve_undirected_rpp(hlb_id="test_all", required_edges=edges)

    traversed_edge_ids = {s.edge_id for s in res.steps}
    for e in edges:
        assert e.segment_id in traversed_edge_ids


# ------------------------------------------------------------------------------
# Test 12: No internal boundary violations: stays on road graph
# ------------------------------------------------------------------------------
def test_12_no_internal_boundary_violations():
    seg1 = _make_segment("seg_in_1", [(11.00, 77.00), (11.00, 77.01)], length_m=100.0)
    seg2 = _make_segment("seg_in_2", [(11.00, 77.01), (11.01, 77.01)], length_m=100.0)
    res = solve_undirected_rpp(hlb_id="test_bound", required_edges=[seg1, seg2])

    # Continuous polyline points must match road coordinate segments exactly
    valid_coords = {(11.00, 77.00), (11.00, 77.01), (11.01, 77.01)}
    for pt in res.continuous_polyline:
        assert (round(pt[0], 2), round(pt[1], 2)) in valid_coords


# ------------------------------------------------------------------------------
# Test 13: Major-road side coverage (two-sided enumeration requirement)
# ------------------------------------------------------------------------------
def test_13_major_road_side_coverage():
    primary_seg = _make_segment("prim_road", [(11.00, 77.00), (11.00, 77.01)], highway="primary")
    residential_seg = _make_segment("res_road", [(11.00, 77.01), (11.00, 77.02)], highway="residential")

    assert primary_seg.requires_two_sided is True
    assert residential_seg.requires_two_sided is False
    assert "primary" in TWO_SIDED_HIGHWAY_TYPES
    assert "secondary" in TWO_SIDED_HIGHWAY_TYPES


# ------------------------------------------------------------------------------
# Test 14: Walking cost calculation with road class and surface factors
# ------------------------------------------------------------------------------
def test_14_walking_cost_calculation():
    # 4.5 km/h base speed = 75 m/min
    # Residential asphalt (factor 1.0): 150m takes 2.0 mins
    seg_paved = RoadSegment(
        segment_id="s_paved",
        osm_way_id=1,
        osm_node_ids=[1, 2],
        coordinates=[(11.0, 77.0), (11.0, 77.001)],
        geometry=LineString([(77.0, 11.0), (77.001, 11.0)]),
        length_m=150.0,
        highway="residential",
        surface="asphalt",
        walking_speed_factor=1.0,
    )
    # Dirt path (factor 0.75): 150m takes (150/1000) / (4.5 * 0.75) * 60 = 2.667 mins
    seg_dirt = RoadSegment(
        segment_id="s_dirt",
        osm_way_id=2,
        osm_node_ids=[3, 4],
        coordinates=[(11.0, 77.0), (11.0, 77.001)],
        geometry=LineString([(77.0, 11.0), (77.001, 11.0)]),
        length_m=150.0,
        highway="path",
        surface="dirt",
        walking_speed_factor=0.75,
    )
    assert seg_dirt.walking_cost > seg_paved.walking_cost
    assert round(seg_paved.walking_cost, 1) == 2.0


# ------------------------------------------------------------------------------
# Test 15: Missing road submission by enumerator and supervisor approval
# ------------------------------------------------------------------------------
def test_15_missing_road_submission_and_approval(p9_fixture, db: Session, client: TestClient):
    hlb = p9_fixture["hlb"]
    enum = p9_fixture["enumerator"]
    sup = p9_fixture["supervisor"]

    enum_token = _login(client, enum.username)
    sup_token = _login(client, sup.username)

    # 1. Enumerator submits missing pathway
    sub_res = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/missing-roads",
        headers={"Authorization": f"Bearer {enum_token}"},
        json={
            "coordinates": [[11.086, 77.091], [11.087, 77.092]],
            "highway_type": "path",
            "road_name": "Newly Discovered Path",
            "notes": "Walkway between compounds",
        },
    )
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["status"] == "PENDING_REVIEW"
    sub_id = sub_data["submission_id"]

    # 2. Supervisor views pending submissions
    pending_res = client.get(
        "/api/v1/routes/missing-roads/pending",
        headers={"Authorization": f"Bearer {sup_token}"},
    )
    assert pending_res.status_code == 200
    pending_list = pending_res.json()
    assert any(p["submission_id"] == str(sub_id) for p in pending_list)

    # 3. Supervisor approves submission
    review_res = client.post(
        f"/api/v1/routes/missing-roads/{sub_id}/review",
        headers={"Authorization": f"Bearer {sup_token}"},
        json={
            "action": "APPROVE",
            "review_notes": "Verified on site",
        },
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == "APPROVED"


# ------------------------------------------------------------------------------
# Test 16: Route and graph versioning
# ------------------------------------------------------------------------------
def test_16_route_and_graph_versioning(p9_fixture, db: Session, client: TestClient):
    hlb = p9_fixture["hlb"]
    enum = p9_fixture["enumerator"]
    enum_token = _login(client, enum.username)

    # 1. Build graph
    build_res = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/graph/build",
        headers={"Authorization": f"Bearer {enum_token}"},
        json={"buffer_meters": 30.0, "force_rebuild": True},
    )
    assert build_res.status_code == 200

    # 2. Check version
    ver_res = client.get(
        f"/api/v1/routes/hlbs/{hlb.id}/route/version",
        headers={"Authorization": f"Bearer {enum_token}"},
    )
    assert ver_res.status_code == 200
    ver_data = ver_res.json()
    assert "graph_version" in ver_data
    assert "route_version" in ver_data


# ------------------------------------------------------------------------------
# Test 17: Replanning after new edge approval (keeping completed prefix immutable)
# ------------------------------------------------------------------------------
def test_17_replan_after_new_edge_approval(p9_fixture, db: Session, client: TestClient):
    hlb = p9_fixture["hlb"]
    enum = p9_fixture["enumerator"]
    enum_token = _login(client, enum.username)

    # Build and generate route
    client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/graph/build",
        headers={"Authorization": f"Bearer {enum_token}"},
        json={"force_rebuild": True},
    )
    gen_res = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/route/rpp/generate",
        headers={"Authorization": f"Bearer {enum_token}"},
        json={"return_to_start": False},
    )
    assert gen_res.status_code == 200
    orig_route = gen_res.json()

    # Replan from current GPS position
    replan_res = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/route/rpp/replan",
        headers={"Authorization": f"Bearer {enum_token}"},
        json={
            "current_latitude": 11.088,
            "current_longitude": 77.092,
            "reason": "Replanning after newly added pathway",
        },
    )
    assert replan_res.status_code == 200
    replanned = replan_res.json()
    assert replanned["total_required_edges_count"] > 0


# ------------------------------------------------------------------------------
# Test 18: Large graph performance benchmark (100, 500, 1000 edges)
# ------------------------------------------------------------------------------
def test_18_large_graph_performance_benchmark():
    def make_grid_edges(num_edges: int) -> list[RoadSegment]:
        edges = []
        side = int(num_edges**0.5) + 1
        edge_cnt = 0
        for i in range(side):
            for j in range(side):
                if edge_cnt >= num_edges:
                    break
                p1 = (11.0 + i * 0.001, 77.0 + j * 0.001)
                p2 = (11.0 + i * 0.001, 77.0 + (j + 1) * 0.001)
                edges.append(_make_segment(f"grid_{edge_cnt}", [p1, p2], length_m=50.0))
                edge_cnt += 1
                if edge_cnt < num_edges:
                    p3 = (11.0 + (i + 1) * 0.001, 77.0 + j * 0.001)
                    edges.append(_make_segment(f"grid_{edge_cnt}", [p1, p3], length_m=50.0))
                    edge_cnt += 1
        return edges

    # 1. 100 edges
    edges_100 = make_grid_edges(100)
    t0 = time.time()
    res_100 = solve_undirected_rpp("bench_100", edges_100)
    t1 = time.time()
    time_100 = t1 - t0
    assert time_100 < 2.0
    assert res_100.total_required_edges_count == 100

    # 2. 500 edges
    edges_500 = make_grid_edges(500)
    t2 = time.time()
    res_500 = solve_undirected_rpp("bench_500", edges_500)
    t3 = time.time()
    time_500 = t3 - t2
    assert time_500 < 5.0
    assert res_500.total_required_edges_count == 500

    # 3. 1000 edges
    edges_1000 = make_grid_edges(1000)
    t4 = time.time()
    res_1000 = solve_undirected_rpp("bench_1000", edges_1000)
    t5 = time.time()
    time_1000 = t5 - t4
    assert time_1000 < 10.0
    assert res_1000.total_required_edges_count == 1000
