import time
import uuid

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.gis.route.distance import (
    calculate_distance_matrix,
    calculate_path_distance_km,
    haversine_distance_meters,
)
from app.gis.route.optimizer import (
    optimize_building_route,
)
from app.gis.route.validation import RouteValidationError, validate_route
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.enumerator_assignment import (
    EnumeratorAssignmentStatus,
    HlbEnumeratorAssignment,
)
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import BuildingSourceType, House
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


@pytest.fixture
def route_test_data(db: Session):
    suffix = uuid.uuid4().hex[:6]

    # Users
    deputy = User(
        name="Deputy Tahsildar Route",
        username=f"deputy_route_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.DEPUTY_TAHSILDAR,
        status=UserStatus.ACTIVE,
    )
    supervisor = User(
        name="Supervisor Route",
        username=f"sup_route_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enum_1 = User(
        name="Enumerator Assigned",
        username=f"enum_route_1_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    enum_2 = User(
        name="Enumerator Unassigned",
        username=f"enum_route_2_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all([deputy, supervisor, enum_1, enum_2])
    db.commit()

    # Administrative Area
    area = AdministrativeArea(
        name=f"Salem North Route {suffix}",
        code=f"AREA-R-{suffix}",
        type=AreaType.VILLAGE,
        boundary=WKTElement(
            "MULTIPOLYGON(((78.14 11.66, 78.16 11.66, "
            "78.16 11.68, 78.14 11.68, 78.14 11.66)))",
            srid=4326,
        ),
    )
    db.add(area)
    db.commit()

    # Layout & Version
    layout = Layout(
        name=f"Layout Route {suffix}",
        area_id=area.id,
        boundary=area.boundary,
        status=LayoutStatus.APPROVED,
    )
    db.add(layout)
    db.commit()

    version = LayoutVersion(
        layout_id=layout.id,
        version_number=1,
        source=LayoutVersionSource.APPROVED,
        status=LayoutVersionStatus.APPROVED,
    )
    db.add(version)
    db.commit()
    layout.active_version_id = version.id
    db.commit()

    # Supervisor Assignment
    sup_assign = LayoutSupervisorAssignment(
        layout_id=layout.id,
        supervisor_id=supervisor.id,
        status=SupervisorAssignmentStatus.ACTIVE,
    )
    db.add(sup_assign)

    # HLB 1 (Assigned to enum_1)
    hlb_1 = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code=f"HLB-R-001-{suffix}",
        name="Block 1 Route",
        target_building_count=150,
        actual_building_count=5,
        boundary=WKTElement(
            "MULTIPOLYGON(((78.141 11.661, 78.149 11.661, "
            "78.149 11.669, 78.141 11.669, 78.141 11.661)))",
            srid=4326,
        ),
    )

    # HLB 2 (Empty HLB with 0 buildings, assigned to enum_1)
    hlb_empty = HouselistingBlock(
        layout_id=layout.id,
        version_id=version.id,
        block_code=f"HLB-R-EMPTY-{suffix}",
        name="Empty Block Route",
        target_building_count=50,
        actual_building_count=0,
        boundary=WKTElement(
            "MULTIPOLYGON(((78.151 11.671, 78.159 11.671, "
            "78.159 11.679, 78.151 11.679, 78.151 11.671)))",
            srid=4326,
        ),
    )

    db.add_all([hlb_1, hlb_empty])
    db.commit()

    # Enumerator Assignments
    enum_assign_1 = HlbEnumeratorAssignment(
        hlb_id=hlb_1.id,
        layout_id=layout.id,
        enumerator_id=enum_1.id,
        supervisor_id=supervisor.id,
        status=EnumeratorAssignmentStatus.ACTIVE,
    )
    enum_assign_empty = HlbEnumeratorAssignment(
        hlb_id=hlb_empty.id,
        layout_id=layout.id,
        enumerator_id=enum_1.id,
        supervisor_id=supervisor.id,
        status=EnumeratorAssignmentStatus.ACTIVE,
    )
    db.add_all([enum_assign_1, enum_assign_empty])
    db.commit()

    # 5 Real Buildings inside HLB 1 with varied coordinates
    building_coords = [
        (11.6620, 78.1420, "BLD-R-01", "101"),
        (11.6680, 78.1480, "BLD-R-02", "102"),
        (11.6630, 78.1430, "BLD-R-03", "103"),
        (11.6670, 78.1470, "BLD-R-04", "104"),
        (11.6650, 78.1450, "BLD-R-05", "105"),
    ]

    houses_hlb1 = []
    for lat, lon, ref, num in building_coords:
        house = House(
            area_id=area.id,
            building_reference=ref,
            house_number=num,
            latitude=lat,
            longitude=lon,
            location=WKTElement(f"POINT({lon} {lat})", srid=4326),
            source_type=BuildingSourceType.SATELLITE_DETECTED,
        )
        db.add(house)
        db.flush()
        houses_hlb1.append(house)

        hlb_house = HlbHouse(hlb_id=hlb_1.id, house_id=house.id)
        db.add(hlb_house)

    db.commit()

    return {
        "deputy": deputy,
        "supervisor": supervisor,
        "enum_1": enum_1,
        "enum_2": enum_2,
        "hlb_1": hlb_1,
        "hlb_empty": hlb_empty,
        "houses_hlb1": houses_hlb1,
        "area": area,
        "layout": layout,
    }


def _get_auth_token(client: TestClient, username: str) -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


# ==============================================================================
# 1. UNIT TESTS: GIS Distance, Optimizer & Validation
# ==============================================================================


def test_haversine_distance_calculation():
    # Known distance: Salem (11.6643, 78.1460) to nearby point ~ 1.11 km
    dist_m = haversine_distance_meters(11.6643, 78.1460, 11.6743, 78.1460)
    assert 1100.0 < dist_m < 1120.0

    # Distance to identical point is 0
    assert haversine_distance_meters(11.6643, 78.1460, 11.6643, 78.1460) == 0.0


def test_distance_matrix_and_path_calculation():
    coords = [(11.662, 78.142), (11.664, 78.144), (11.666, 78.146)]
    matrix = calculate_distance_matrix(coords)

    assert len(matrix) == 3
    assert matrix[0][0] == 0.0
    assert matrix[0][1] == matrix[1][0]
    assert matrix[0][1] > 0.0

    # Path 0 -> 1 -> 2
    path_dist_km = calculate_path_distance_km([0, 1, 2], matrix)
    assert path_dist_km > 0.0


def test_optimizer_nearest_neighbor_and_2opt():
    # Zig-zag building points where 2-opt uncrosses the path
    buildings = [
        {
            "id": "b1",
            "building_reference": "B1",
            "latitude": 11.660,
            "longitude": 78.140,
        },
        {
            "id": "b2",
            "building_reference": "B2",
            "latitude": 11.669,
            "longitude": 78.149,
        },
        {
            "id": "b3",
            "building_reference": "B3",
            "latitude": 11.661,
            "longitude": 78.141,
        },
        {
            "id": "b4",
            "building_reference": "B4",
            "latitude": 11.668,
            "longitude": 78.148,
        },
        {
            "id": "b5",
            "building_reference": "B5",
            "latitude": 11.663,
            "longitude": 78.143,
        },
    ]

    ordered, opt_dist, base_dist, strat = optimize_building_route(
        buildings, (11.659, 78.139)
    )

    assert len(ordered) == 5
    assert opt_dist <= base_dist
    assert strat == "CURRENT_GPS"

    # Verify every ID is preserved
    orig_ids = {b["id"] for b in buildings}
    opt_ids = {b["id"] for b in ordered}
    assert orig_ids == opt_ids


def test_validation_integrity_checks():
    buildings = [
        {"id": "b1", "sequence_order": 1, "latitude": 11.66, "longitude": 78.14},
        {"id": "b2", "sequence_order": 2, "latitude": 11.67, "longitude": 78.15},
    ]

    # Valid route
    validate_route(buildings, buildings, 1.2)

    # Missing building
    with pytest.raises(RouteValidationError):
        validate_route(buildings, [buildings[0]], 0.5)

    # Duplicate building
    dup = [buildings[0], dict(buildings[0], sequence_order=2)]
    with pytest.raises(RouteValidationError):
        validate_route(buildings, dup, 0.5)

    # Negative distance
    with pytest.raises(RouteValidationError):
        validate_route(buildings, buildings, -1.0)


# ==============================================================================
# 2. INTEGRATION TESTS: Route Optimization Endpoints
# ==============================================================================


def test_optimize_route_assigned_enumerator_success(
    client: TestClient, route_test_data
):
    data = route_test_data
    token = _get_auth_token(client, data["enum_1"].username)

    # Call POST /api/v1/enumerator/hlbs/{hlb_id}/route/optimize
    resp = client.post(
        f"/api/v1/enumerator/hlbs/{data['hlb_1'].id}/route/optimize",
        headers={"Authorization": f"Bearer {token}"},
        json={"latitude": 11.6610, "longitude": 78.1410},
    )

    assert resp.status_code == 200, resp.text
    res_data = resp.json()

    assert res_data["hlb_id"] == str(data["hlb_1"].id)
    assert res_data["building_count"] == 5
    assert len(res_data["buildings"]) == 5
    assert res_data["total_distance_km"] > 0.0
    assert res_data["total_distance_km"] <= res_data["baseline_distance_km"]
    assert res_data["starting_point"]["strategy"] == "CURRENT_GPS"
    assert res_data["starting_point"]["latitude"] == 11.6610

    # Verify sequence order 1..5
    sequences = [b["sequence_order"] for b in res_data["buildings"]]
    assert sequences == [1, 2, 3, 4, 5]

    # Verify building IDs match exactly without duplicates
    retrieved_ids = {b["building_id"] for b in res_data["buildings"]}
    expected_ids = {str(h.id) for h in data["houses_hlb1"]}
    assert retrieved_ids == expected_ids


def test_optimize_route_zero_buildings_graceful(client: TestClient, route_test_data):
    data = route_test_data
    token = _get_auth_token(client, data["enum_1"].username)

    # HLB with 0 buildings
    resp = client.post(
        f"/api/v1/enumerator/hlbs/{data['hlb_empty'].id}/route/optimize",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200, resp.text
    res_data = resp.json()

    assert res_data["building_count"] == 0
    assert res_data["total_distance_km"] == 0.0
    assert len(res_data["buildings"]) == 0


def test_get_route_endpoint(client: TestClient, route_test_data):
    data = route_test_data
    token = _get_auth_token(client, data["enum_1"].username)

    # GET /api/v1/enumerator/hlbs/{hlb_id}/route
    resp = client.get(
        f"/api/v1/enumerator/hlbs/{data['hlb_1'].id}/route",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200, resp.text
    res_data = resp.json()
    assert res_data["building_count"] == 5
    assert res_data["starting_point"]["strategy"] in ("HLB_CENTROID", "FIRST_BUILDING")


def test_unassigned_enumerator_forbidden(client: TestClient, route_test_data):
    data = route_test_data
    # enum_2 is not assigned to hlb_1
    token = _get_auth_token(client, data["enum_2"].username)

    resp = client.post(
        f"/api/v1/enumerator/hlbs/{data['hlb_1'].id}/route/optimize",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"].lower()


def test_supervisor_forbidden(client: TestClient, route_test_data):
    data = route_test_data
    # Supervisor attempting to access enumerator route endpoint
    token = _get_auth_token(client, data["supervisor"].username)

    resp = client.post(
        f"/api/v1/enumerator/hlbs/{data['hlb_1'].id}/route/optimize",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 403


def test_unauthenticated_rejected(client: TestClient, route_test_data):
    data = route_test_data

    resp = client.post(
        f"/api/v1/enumerator/hlbs/{data['hlb_1'].id}/route/optimize",
    )

    assert resp.status_code in (401, 403)


def test_invalid_coordinates_rejected(client: TestClient, route_test_data):
    data = route_test_data
    token = _get_auth_token(client, data["enum_1"].username)

    # Latitude 999.0 is invalid
    resp = client.post(
        f"/api/v1/enumerator/hlbs/{data['hlb_1'].id}/route/optimize",
        headers={"Authorization": f"Bearer {token}"},
        json={"latitude": 999.0, "longitude": 78.14},
    )

    assert resp.status_code == 422


def test_performance_at_scale():
    # Test optimizer performance with 100 and 250 synthetic building coordinates
    for count in (100, 250):
        synth_buildings = [
            {
                "id": str(uuid.uuid4()),
                "building_reference": f"BLD-{i:03d}",
                "house_number": str(i),
                "latitude": 11.660 + (i * 0.0001) % 0.02,
                "longitude": 78.140 + (i * 0.00015) % 0.02,
            }
            for i in range(count)
        ]

        t0 = time.perf_counter()
        ordered, opt_dist, base_dist, _ = optimize_building_route(
            synth_buildings, (11.660, 78.140)
        )
        duration_ms = (time.perf_counter() - t0) * 1000.0

        assert len(ordered) == count
        assert opt_dist <= base_dist
        # Must execute in under 200 ms
        assert duration_ms < 200.0
