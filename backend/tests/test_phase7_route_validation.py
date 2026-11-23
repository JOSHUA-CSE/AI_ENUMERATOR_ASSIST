import time
import uuid

import networkx as nx
import pytest
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.gis.route.distance import (
    build_road_network_graph,
    calculate_distance_matrix,
    calculate_path_distance_km,
    calculate_road_aware_distance_matrix,
    haversine_distance_meters,
    load_osm_pedestrian_network,
)
from app.gis.route.optimizer import (
    optimize_building_route,
    solve_tsp_nearest_neighbor,
)
from app.gis.route.validation import RouteValidationError, validate_route
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.enumerator_assignment import (
    EnumeratorAssignmentStatus,
    HlbEnumeratorAssignment,
)
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import BuildingFieldStatus, BuildingSourceType, House
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
from app.services.route_service import route_service


@pytest.fixture
def p7_test_fixture(db: Session):
    suffix = uuid.uuid4().hex[:6]

    # Users
    deputy = User(
        name="Deputy P7",
        username=f"deputy_p7_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor = User(
        name="Supervisor P7",
        username=f"sup_p7_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enum_1 = User(
        name="Enumerator P7-1",
        username=f"enum_p7_1_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    enum_2 = User(
        name="Enumerator P7-2",
        username=f"enum_p7_2_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all([deputy, supervisor, enum_1, enum_2])
    db.commit()

    # Arasur pilot area
    area_arasur = AdministrativeArea(
        name=f"Arasur P7 {suffix}",
        code=f"AREA-ARASUR-{suffix}",
        type=AreaType.VILLAGE,
        boundary=WKTElement(
            "MULTIPOLYGON(((77.08 11.08, 77.12 11.08, 77.12 11.12, 77.08 11.12, 77.08 11.08)))",
            srid=4326,
        ),
    )
    # Pollachi area (no OSM roads available)
    area_pollachi = AdministrativeArea(
        name=f"Achipatti Pollachi {suffix}",
        code=f"AREA-POL-{suffix}",
        type=AreaType.VILLAGE,
        boundary=WKTElement(
            "MULTIPOLYGON(((76.98 10.65, 77.02 10.65, 77.02 10.69, 76.98 10.69, 76.98 10.65)))",
            srid=4326,
        ),
    )
    db.add_all([area_arasur, area_pollachi])
    db.commit()

    # Layout for Arasur
    layout_arasur = Layout(
        name=f"Layout Arasur {suffix}",
        area_id=area_arasur.id,
        boundary=area_arasur.boundary,
        status=LayoutStatus.APPROVED,
    )
    layout_pollachi = Layout(
        name=f"Layout Pollachi {suffix}",
        area_id=area_pollachi.id,
        boundary=area_pollachi.boundary,
        status=LayoutStatus.APPROVED,
    )
    db.add_all([layout_arasur, layout_pollachi])
    db.commit()

    v_arasur = LayoutVersion(
        layout_id=layout_arasur.id,
        version_number=1,
        source=LayoutVersionSource.APPROVED,
        status=LayoutVersionStatus.APPROVED,
    )
    v_pollachi = LayoutVersion(
        layout_id=layout_pollachi.id,
        version_number=1,
        source=LayoutVersionSource.APPROVED,
        status=LayoutVersionStatus.APPROVED,
    )
    db.add_all([v_arasur, v_pollachi])
    db.commit()
    layout_arasur.active_version_id = v_arasur.id
    layout_pollachi.active_version_id = v_pollachi.id
    db.commit()

    # Supervisor assignments
    db.add(LayoutSupervisorAssignment(
        layout_id=layout_arasur.id,
        supervisor_id=supervisor.id,
        status=SupervisorAssignmentStatus.ACTIVE,
    ))
    db.add(LayoutSupervisorAssignment(
        layout_id=layout_pollachi.id,
        supervisor_id=supervisor.id,
        status=SupervisorAssignmentStatus.ACTIVE,
    ))
    db.commit()

    # HLB 1 in Arasur (assigned to enum_1)
    hlb_arasur = HouselistingBlock(
        layout_id=layout_arasur.id,
        version_id=v_arasur.id,
        block_code=f"HLB-ARASUR-{suffix}",
        name="Arasur Block 1",
        target_building_count=120,
        actual_building_count=5,
        boundary=WKTElement(
            "MULTIPOLYGON(((77.09 11.09, 77.11 11.09, 77.11 11.11, 77.09 11.11, 77.09 11.09)))",
            srid=4326,
        ),
    )
    # HLB 2 in Arasur (also in Arasur, assigned to enum_2)
    hlb_arasur_2 = HouselistingBlock(
        layout_id=layout_arasur.id,
        version_id=v_arasur.id,
        block_code=f"HLB-ARASUR-2-{suffix}",
        name="Arasur Block 2",
        target_building_count=120,
        actual_building_count=3,
        boundary=WKTElement(
            "MULTIPOLYGON(((77.11 11.09, 77.13 11.09, 77.13 11.11, 77.11 11.11, 77.11 11.09)))",
            srid=4326,
        ),
    )
    # HLB in Pollachi (assigned to enum_1)
    hlb_pollachi = HouselistingBlock(
        layout_id=layout_pollachi.id,
        version_id=v_pollachi.id,
        block_code=f"HLB-POL-{suffix}",
        name="Pollachi Block 1",
        target_building_count=120,
        actual_building_count=4,
        boundary=WKTElement(
            "MULTIPOLYGON(((76.99 10.66, 77.01 10.66, 77.01 10.68, 76.99 10.68, 76.99 10.66)))",
            srid=4326,
        ),
    )
    db.add_all([hlb_arasur, hlb_arasur_2, hlb_pollachi])
    db.commit()

    # Enumerator assignments
    db.add(HlbEnumeratorAssignment(
        hlb_id=hlb_arasur.id,
        layout_id=layout_arasur.id,
        enumerator_id=enum_1.id,
        supervisor_id=supervisor.id,
        status=EnumeratorAssignmentStatus.ACTIVE,
    ))
    db.add(HlbEnumeratorAssignment(
        hlb_id=hlb_arasur_2.id,
        layout_id=layout_arasur.id,
        enumerator_id=enum_2.id,
        supervisor_id=supervisor.id,
        status=EnumeratorAssignmentStatus.ACTIVE,
    ))
    db.add(HlbEnumeratorAssignment(
        hlb_id=hlb_pollachi.id,
        layout_id=layout_pollachi.id,
        enumerator_id=enum_1.id,
        supervisor_id=supervisor.id,
        status=EnumeratorAssignmentStatus.ACTIVE,
    ))
    db.commit()

    return {
        "deputy": deputy,
        "supervisor": supervisor,
        "enum_1": enum_1,
        "enum_2": enum_2,
        "hlb_arasur": hlb_arasur,
        "hlb_arasur_2": hlb_arasur_2,
        "hlb_pollachi": hlb_pollachi,
        "area_arasur": area_arasur,
        "area_pollachi": area_pollachi,
    }


def _login(client: TestClient, username: str) -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


# ==============================================================================
# SECTION 7: 15 SPECIFIC ROUTE VALIDATION TESTS
# ==============================================================================


def test_01_one_building(db: Session, p7_test_fixture):
    """1. Route validation with exactly one building."""
    data = p7_test_fixture
    hlb = data["hlb_arasur"]
    area = data["area_arasur"]

    house = House(
        area_id=area.id,
        building_reference="BLD-SOLO-1",
        latitude=11.095,
        longitude=77.095,
        location=WKTElement("POINT(77.095 11.095)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    db.add(house)
    db.flush()
    db.add(HlbHouse(hlb_id=hlb.id, house_id=house.id))
    db.commit()

    res = route_service.generate_optimized_route(
        db=db,
        hlb_id=hlb.id,
        enumerator_id=data["enum_1"].id,
    )

    assert res.building_count == 1
    assert len(res.buildings) == 1
    assert res.buildings[0].sequence_order == 1
    assert res.buildings[0].building_id == house.id
    assert res.total_distance_km >= 0.0
    assert len(res.ordered_building_ids) == 1


def test_02_two_buildings(db: Session, p7_test_fixture):
    """2. Route validation with two buildings."""
    data = p7_test_fixture
    hlb = data["hlb_arasur"]
    area = data["area_arasur"]

    # Clear previous buildings
    db.query(HlbHouse).filter(HlbHouse.hlb_id == hlb.id).delete()
    db.commit()

    h1 = House(
        area_id=area.id,
        building_reference="BLD-PAIR-1",
        latitude=11.0950,
        longitude=77.0950,
        location=WKTElement("POINT(77.0950 11.0950)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    h2 = House(
        area_id=area.id,
        building_reference="BLD-PAIR-2",
        latitude=11.0960,
        longitude=77.0960,
        location=WKTElement("POINT(77.0960 11.0960)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    db.add_all([h1, h2])
    db.flush()
    db.add_all([HlbHouse(hlb_id=hlb.id, house_id=h1.id), HlbHouse(hlb_id=hlb.id, house_id=h2.id)])
    db.commit()

    res = route_service.generate_optimized_route(
        db=db,
        hlb_id=hlb.id,
        enumerator_id=data["enum_1"].id,
    )

    assert res.building_count == 2
    assert len(res.buildings) == 2
    assert res.buildings[0].sequence_order == 1
    assert res.buildings[1].sequence_order == 2
    assert {res.buildings[0].building_id, res.buildings[1].building_id} == {h1.id, h2.id}
    assert res.total_distance_km > 0.0


def test_03_multiple_buildings():
    """3. Multiple buildings appear exactly once in sequence 1..N."""
    buildings = [
        {"id": f"b{i}", "building_reference": f"BLD-{i:03d}", "latitude": 11.090 + i * 0.001, "longitude": 77.090 + i * 0.001}
        for i in range(12)
    ]
    ordered, opt_km, base_km, _ = optimize_building_route(buildings)
    assert len(ordered) == 12
    assert [b["sequence_order"] for b in ordered] == list(range(1, 13))
    assert {b["id"] for b in ordered} == {b["id"] for b in buildings}
    assert opt_km <= base_km


def test_04_dense_building_clusters():
    """4. Dense cluster of buildings tightly grouped together."""
    # 25 buildings in a 50m x 50m micro-grid
    buildings = [
        {
            "id": f"dense_{i}",
            "building_reference": f"DENSE-{i}",
            "latitude": 11.09200 + (i // 5) * 0.0001,
            "longitude": 77.09200 + (i % 5) * 0.0001,
        }
        for i in range(25)
    ]
    ordered, opt_km, base_km, _ = optimize_building_route(buildings, starting_point=(11.09200, 77.09200))
    assert len(ordered) == 25
    assert opt_km <= base_km
    assert opt_km > 0.0


def test_05_irregularly_distributed_buildings():
    """5. Irregularly scattered buildings across geographic extents."""
    import random
    rng = random.Random(42)
    buildings = [
        {
            "id": f"irreg_{i}",
            "building_reference": f"IRREG-{i}",
            "latitude": 11.080 + rng.random() * 0.040,
            "longitude": 77.080 + rng.random() * 0.040,
        }
        for i in range(30)
    ]
    ordered, opt_km, base_km, _ = optimize_building_route(buildings)
    assert len(ordered) == 30
    assert opt_km <= base_km


def test_06_disconnected_road_network_components():
    """6. Disconnected road network components fallback to Haversine."""
    # Island A road: (11.0, 78.0) to (11.0, 78.01)
    # Island B road: (11.1, 78.1) to (11.1, 78.11)
    roads = [
        [(11.0, 78.0), (11.0, 78.01)],
        [(11.1, 78.1), (11.1, 78.11)],
    ]
    g = build_road_network_graph(roads)
    assert nx.number_connected_components(g) == 2

    coords = [(11.0, 78.005), (11.1, 78.105)]
    matrix = calculate_road_aware_distance_matrix(coords, g)

    # Matrix must successfully calculate distance via Haversine across components
    assert matrix[0][1] > 0.0
    straight_dist = haversine_distance_meters(coords[0][0], coords[0][1], coords[1][0], coords[1][1])
    assert abs(matrix[0][1] - straight_dist) < 1.0


def test_07_missing_building_coordinates(db: Session, p7_test_fixture):
    """7. Exclude buildings with missing coordinates and report them."""
    data = p7_test_fixture
    hlb = data["hlb_arasur"]
    area = data["area_arasur"]

    db.query(HlbHouse).filter(HlbHouse.hlb_id == hlb.id).delete()
    db.commit()

    # Valid building
    h_valid = House(
        area_id=area.id,
        building_reference="BLD-VALID-COORD",
        latitude=11.0950,
        longitude=77.0950,
        location=WKTElement("POINT(77.0950 11.0950)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    # Out of bounds / invalid coordinate building (simulating missing/corrupted GPS)
    h_missing = House(
        area_id=area.id,
        building_reference="BLD-MISSING-COORD",
        latitude=999.0,
        longitude=999.0,
        location=WKTElement("POINT(0 0)", srid=4326),
        source_type=BuildingSourceType.MANUAL,
    )
    db.add_all([h_valid, h_missing])
    db.flush()
    db.add_all([HlbHouse(hlb_id=hlb.id, house_id=h_valid.id), HlbHouse(hlb_id=hlb.id, house_id=h_missing.id)])
    db.commit()

    res = route_service.generate_optimized_route(
        db=db,
        hlb_id=hlb.id,
        enumerator_id=data["enum_1"].id,
    )

    assert res.building_count == 1
    assert res.buildings[0].building_id == h_valid.id
    # Unroutable building reported
    assert len(res.unroutable_buildings) == 1
    assert res.unroutable_buildings[0].building_id == h_missing.id
    assert res.unroutable_buildings[0].reason == "MISSING_COORDINATES"


def test_08_invalid_building_geometry():
    """8. Invalid building coordinates trigger validation error."""
    buildings = [
        {"id": "b1", "building_reference": "B1", "sequence_order": 1, "latitude": 11.0, "longitude": 78.0},
        {"id": "b2", "building_reference": "B2", "sequence_order": 2, "latitude": 999.0, "longitude": 78.0},
    ]
    with pytest.raises(RouteValidationError):
        validate_route(buildings, buildings, 1.0)


def test_09_buildings_belonging_to_different_hlbs(db: Session, p7_test_fixture):
    """9. Route strictly excludes buildings belonging to different HLBs."""
    data = p7_test_fixture
    hlb1 = data["hlb_arasur"]
    hlb2 = data["hlb_arasur_2"]
    area = data["area_arasur"]

    db.query(HlbHouse).filter(HlbHouse.hlb_id.in_([hlb1.id, hlb2.id])).delete()
    db.commit()

    h_in_1 = House(
        area_id=area.id,
        building_reference="BLD-HLB1-ONLY",
        latitude=11.095,
        longitude=77.095,
        location=WKTElement("POINT(77.095 11.095)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    h_in_2 = House(
        area_id=area.id,
        building_reference="BLD-HLB2-ONLY",
        latitude=11.115,
        longitude=77.115,
        location=WKTElement("POINT(77.115 11.115)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    db.add_all([h_in_1, h_in_2])
    db.flush()
    db.add(HlbHouse(hlb_id=hlb1.id, house_id=h_in_1.id))
    db.add(HlbHouse(hlb_id=hlb2.id, house_id=h_in_2.id))
    db.commit()

    res = route_service.generate_optimized_route(
        db=db,
        hlb_id=hlb1.id,
        enumerator_id=data["enum_1"].id,
    )

    assert res.building_count == 1
    assert res.buildings[0].building_id == h_in_1.id
    assert h_in_2.id not in res.ordered_building_ids


def test_10_false_detection_exclusion(db: Session, p7_test_fixture):
    """10. FALSE_DETECTION buildings excluded and reported."""
    data = p7_test_fixture
    hlb = data["hlb_arasur"]
    area = data["area_arasur"]

    db.query(HlbHouse).filter(HlbHouse.hlb_id == hlb.id).delete()
    db.commit()

    h_good = House(
        area_id=area.id,
        building_reference="BLD-CONFIRMED",
        latitude=11.095,
        longitude=77.095,
        field_status=BuildingFieldStatus.CONFIRMED,
        location=WKTElement("POINT(77.095 11.095)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    h_false = House(
        area_id=area.id,
        building_reference="BLD-FALSE-GHOST",
        latitude=11.096,
        longitude=77.096,
        field_status=BuildingFieldStatus.FALSE_DETECTION,
        location=WKTElement("POINT(77.096 11.096)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    db.add_all([h_good, h_false])
    db.flush()
    db.add_all([HlbHouse(hlb_id=hlb.id, house_id=h_good.id), HlbHouse(hlb_id=hlb.id, house_id=h_false.id)])
    db.commit()

    res = route_service.generate_optimized_route(
        db=db,
        hlb_id=hlb.id,
        enumerator_id=data["enum_1"].id,
    )

    assert res.building_count == 1
    assert res.buildings[0].building_id == h_good.id
    assert len(res.unroutable_buildings) == 1
    assert res.unroutable_buildings[0].building_id == h_false.id
    assert res.unroutable_buildings[0].reason == "FALSE_DETECTION"


def test_11_no_available_road_graph_pollachi(db: Session, p7_test_fixture):
    """11. No available road graph (Pollachi) triggers honest GEOMETRIC_APPROXIMATION."""
    data = p7_test_fixture
    hlb = data["hlb_pollachi"]
    area = data["area_pollachi"]

    h = House(
        area_id=area.id,
        building_reference="BLD-POL-1",
        latitude=10.665,
        longitude=76.995,
        location=WKTElement("POINT(76.995 10.665)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    db.add(h)
    db.flush()
    db.add(HlbHouse(hlb_id=hlb.id, house_id=h.id))
    db.commit()

    res = route_service.generate_optimized_route(
        db=db,
        hlb_id=hlb.id,
        enumerator_id=data["enum_1"].id,
    )

    assert res.routing_method == "GEOMETRIC_APPROXIMATION"
    assert res.distance_type == "GEOGRAPHIC_STRAIGHT_LINE"
    assert res.routing_mode == "MISSING_ROAD_NETWORK_DATA"
    assert res.warning is not None
    assert "Road network data unavailable" in res.warning


def test_12_haversine_fallback():
    """12. Haversine fallback calculations are non-negative and accurate."""
    # Distance between Coimbatore junction and Gandhipuram (~3.3 km)
    cbe_jn = (11.0003, 76.9634)
    gandhipuram = (11.0183, 76.9680)
    dist = haversine_distance_meters(cbe_jn[0], cbe_jn[1], gandhipuram[0], gandhipuram[1])
    assert 2000.0 < dist < 2500.0


def test_13_optional_return_to_start():
    """13. Optional return to start creates a closed loop traversal."""
    buildings = [
        {"id": "b1", "building_reference": "B1", "latitude": 11.0, "longitude": 78.0},
        {"id": "b2", "building_reference": "B2", "latitude": 11.01, "longitude": 78.0},
        {"id": "b3", "building_reference": "B3", "latitude": 11.01, "longitude": 78.01},
    ]
    start = (11.0, 78.0)

    # Open route
    ordered_open, dist_open, _, _ = optimize_building_route(buildings, start, return_to_start=False)
    # Closed loop
    ordered_closed, dist_closed, _, _ = optimize_building_route(buildings, start, return_to_start=True)

    assert len(ordered_open) == 3
    assert len(ordered_closed) == 3
    # Return leg adds positive distance back to origin
    assert dist_closed > dist_open


def test_14_deterministic_route_generation():
    """14. Route generation is 100% deterministic across multiple invocations."""
    import random
    rng = random.Random(99)
    buildings = [
        {
            "id": f"det_{i}",
            "building_reference": f"BLD-DET-{i:02d}",
            "latitude": 11.090 + rng.random() * 0.01,
            "longitude": 77.090 + rng.random() * 0.01,
        }
        for i in range(20)
    ]

    run1, d1, _, _ = optimize_building_route(buildings, (11.090, 77.090))
    # Shuffled input order
    shuffled = list(buildings)
    rng.shuffle(shuffled)
    run2, d2, _, _ = optimize_building_route(shuffled, (11.090, 77.090))

    ids1 = [b["id"] for b in run1]
    ids2 = [b["id"] for b in run2]
    assert ids1 == ids2
    assert d1 == d2


# ==============================================================================
# SECTION 8: PERFORMANCE BENCHMARKING (50, 100, 250, 500, 1000 BUILDINGS)
# ==============================================================================


@pytest.mark.parametrize("building_count", [50, 100, 250, 500, 1000])
def test_15_benchmark_representative_workloads(building_count):
    """
    15. Benchmarks representative workloads (50, 100, 250, 500, 1000 buildings).
    Measures route generation time, optimization time, and verifies improvement over NN baseline.
    """
    import random
    rng = random.Random(12345)

    synth_buildings = [
        {
            "id": f"bench_{i}",
            "building_reference": f"BLD-{i:04d}",
            "latitude": 11.080 + (i * 0.0001) % 0.030 + rng.random() * 0.0005,
            "longitude": 77.080 + (i * 0.00015) % 0.030 + rng.random() * 0.0005,
        }
        for i in range(building_count)
    ]

    t0 = time.perf_counter()
    res = optimize_building_route(
        synth_buildings,
        starting_point=(11.080, 77.080),
    )
    total_duration_ms = (time.perf_counter() - t0) * 1000.0

    ordered = res[0]
    opt_dist = res[1]
    base_dist = res[2]
    opt_time_ms = res.optimization_time_ms

    assert len(ordered) == building_count
    assert opt_dist <= base_dist
    assert opt_dist > 0.0

    # Ensure bounded execution time
    if building_count <= 250:
        assert total_duration_ms < 300.0
    elif building_count <= 500:
        assert total_duration_ms < 1000.0
    else:
        assert total_duration_ms < 2500.0

    print(
        f"\n[BENCHMARK] N={building_count:4d} | Total: {total_duration_ms:6.2f}ms | "
        f"OptTime: {opt_time_ms:6.2f}ms | BaseDist: {base_dist:7.2f}km | OptDist: {opt_dist:7.2f}km | "
        f"Saved: {base_dist - opt_dist:6.2f}km"
    )

