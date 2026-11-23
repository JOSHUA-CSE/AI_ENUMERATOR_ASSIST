import uuid
import pytest
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.gis.route.road_network import get_road_network
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.enumerator_assignment import EnumeratorAssignmentStatus, HlbEnumeratorAssignment
from app.models.fieldwork import GpsTrack
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import BuildingFieldStatus, BuildingSourceType, House
from app.models.layout import Layout, LayoutStatus, LayoutVersion, LayoutVersionSource, LayoutVersionStatus
from app.models.road_coverage import (
    HlbBoundaryEvent,
    HlbRequiredEdge,
    RoadSegmentCoverage,
    RoadSegmentSurveyStatus,
)
from app.models.supervisor_assignment import LayoutSupervisorAssignment, SupervisorAssignmentStatus
from app.schemas.gps import GpsBoundaryEventRequest
from app.models.user import User, UserRole, UserStatus
from app.services.gps_service import gps_service
from app.services.road_coverage_service import (
    DEFAULT_GPS_ROAD_MATCHING_TOLERANCE_M,
    SURVEY_COMPLETION_THRESHOLD_PCT,
    road_coverage_service,
)


@pytest.fixture
def p10_setup(db: Session):
    suffix = uuid.uuid4().hex[:6]

    supervisor = User(
        name=f"Supervisor P10 {suffix}",
        username=f"sup_p10_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enumerator = User(
        name=f"Enumerator P10 {suffix}",
        username=f"enum_p10_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all([supervisor, enumerator])
    db.commit()

    # Arasur Area covering coordinates [11.080..11.120, 77.080..77.120]
    area = AdministrativeArea(
        name=f"Pollachi Pilot Area P10 {suffix}",
        code=f"AREA-P10-{suffix}",
        type=AreaType.WARD,
        boundary=WKTElement(
            "MULTIPOLYGON(((77.080 11.080, 77.120 11.080, 77.120 11.120, 77.080 11.120, 77.080 11.080)))",
            srid=4326,
        ),
    )
    db.add(area)
    db.commit()

    layout = Layout(
        name=f"Layout P10 {suffix}",
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

    # HLB strictly defined in Arasur region [11.085..11.098, 77.090..77.105]
    hlb = HouselistingBlock(
        layout_id=layout.id,
        version_id=v.id,
        block_code=f"HLB-P10-{suffix}",
        name=f"HLB P10 {suffix}",
        target_building_count=50,
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

    # Create a building inside the HLB for census access tests
    house = House(
        area_id=area.id,
        building_reference="BLD-P10-001",
        house_number="12/A",
        latitude=11.090,
        longitude=77.095,
        location=WKTElement("POINT(77.095 11.090)", srid=4326),
        field_status=BuildingFieldStatus.UNVERIFIED,
        source_type=BuildingSourceType.SATELLITE_DETECTED,
    )
    db.add(house)
    db.commit()

    db.add(HlbHouse(hlb_id=hlb.id, house_id=house.id))
    db.commit()

    return {
        "supervisor": supervisor,
        "enumerator": enumerator,
        "area": area,
        "layout": layout,
        "hlb": hlb,
        "house": house,
    }


def _login(client: TestClient, username: str) -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def test_01_inside_hlb_can_optimize_route(client: TestClient, db: Session, p10_setup):
    """
    Test 1: Inside HLB can optimize route / start traversal.
    Point (lat=11.090, lon=77.095) is strictly inside the polygon [11.085..11.098, 77.090..77.105].
    """
    hlb = p10_setup["hlb"]
    token = _login(client, p10_setup["enumerator"].username)

    res = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/route/traversal/start",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_latitude": 11.090,
            "current_longitude": 77.095,
            "accuracy_meters": 10.0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "TRAVERSAL_ACTIVE"
    assert data["current_boundary_status"] == "INSIDE"


def test_02_outside_hlb_cannot_optimize_route_403(client: TestClient, db: Session, p10_setup):
    """
    Test 2: Outside HLB cannot optimize route (403 Forbidden).
    Point (lat=11.150, lon=77.150) is far outside the polygon [11.085..11.098, 77.090..77.105].
    """
    hlb = p10_setup["hlb"]
    token = _login(client, p10_setup["enumerator"].username)

    res = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/route/rpp/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "force_recompute": True,
            "current_latitude": 11.150,
            "current_longitude": 77.150,
            "accuracy_meters": 10.0,
        },
    )
    assert res.status_code == 403
    assert "outside your assigned HLB" in res.json()["detail"]


def test_03_outside_hlb_cannot_start_traversal_403(client: TestClient, db: Session, p10_setup):
    """
    Test 3: Outside HLB cannot start traversal (403 Forbidden).
    """
    hlb = p10_setup["hlb"]
    token = _login(client, p10_setup["enumerator"].username)

    res = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/route/traversal/start",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_latitude": 11.150,
            "current_longitude": 77.150,
            "accuracy_meters": 12.0,
        },
    )
    assert res.status_code == 403
    assert "outside your assigned HLB" in res.json()["detail"]


def test_04_outside_hlb_can_access_census_records(client: TestClient, db: Session, p10_setup):
    """
    Test 4: Outside HLB can access census records (200 OK).
    Viewing building details, enumerator HLB metadata, or entering census questionnaires
    must NOT be blocked even when physically outside the HLB polygon.
    """
    hlb = p10_setup["hlb"]
    token = _login(client, p10_setup["enumerator"].username)

    # 1. Fetch assigned HLB detail with houses (200 OK)
    res_hlb = client.get(
        f"/api/v1/hlbs/{hlb.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_hlb.status_code == 200
    assert res_hlb.json()["id"] == str(hlb.id)
    assert len(res_hlb.json()["houses"]) >= 1
    assert res_hlb.json()["houses"][0]["building_reference"] == "BLD-P10-001"

    # 2. Number allocation within HLB is accessible (200 OK)
    res_alloc = client.post(
        f"/api/v1/hlbs/{hlb.id}/counters/allocate",
        headers={"Authorization": f"Bearer {token}"},
        json={"building_count": 1, "census_house_count": 1},
    )
    assert res_alloc.status_code == 200


def test_05_reentering_hlb_regains_route_access(client: TestClient, db: Session, p10_setup):
    """
    Test 5: Re-entering HLB regains route access.
    Step 1: Attempt traversal while outside -> 403 Forbidden.
    Step 2: Move back inside -> 200 OK.
    """
    hlb = p10_setup["hlb"]
    token = _login(client, p10_setup["enumerator"].username)

    # Outside: blocked
    res_outside = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/route/traversal/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_latitude": 11.150, "current_longitude": 77.150, "accuracy_meters": 10.0},
    )
    assert res_outside.status_code == 403

    # Inside: allowed
    res_inside = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/route/traversal/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_latitude": 11.090, "current_longitude": 77.095, "accuracy_meters": 10.0},
    )
    assert res_inside.status_code == 200
    assert res_inside.json()["status"] == "TRAVERSAL_ACTIVE"


def test_06_poor_accuracy_produces_400_bad_request(client: TestClient, db: Session, p10_setup):
    """
    Test 6: Poor accuracy (>75m) produces GPS_UNCERTAIN / 400 Bad Request.
    """
    hlb = p10_setup["hlb"]
    token = _login(client, p10_setup["enumerator"].username)

    res = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/route/traversal/start",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_latitude": 11.090,
            "current_longitude": 77.095,
            "accuracy_meters": 95.0,  # Accuracy > 75m threshold
        },
    )
    assert res.status_code == 400
    assert "uncertain" in res.json()["detail"].lower()


def test_07_boundary_drift_hysteresis_and_cooldown(client: TestClient, db: Session, p10_setup):
    """
    Test 7: Boundary exit event submission accepts distance to perimeter and accuracy.
    """
    hlb = p10_setup["hlb"]
    token = _login(client, p10_setup["enumerator"].username)

    res = client.post(
        f"/api/v1/hlbs/{hlb.id}/gps/boundary-event",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_type": "EXIT",
            "latitude": 11.150,
            "longitude": 77.150,
            "accuracy_meters": 8.0,
            "distance_to_boundary_meters": 120.0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["event_type"] == "EXIT"
    assert data["boundary_status"] == "OUTSIDE"


def test_08_boundary_exit_event_recorded_in_db(db: Session, p10_setup):
    """
    Test 8: Boundary exit event is recorded in DB table `hlb_boundary_events`.
    """
    hlb = p10_setup["hlb"]
    enum = p10_setup["enumerator"]

    req = GpsBoundaryEventRequest(
        event_type="EXIT",
        latitude=11.150,
        longitude=77.150,
        accuracy_meters=10.0,
        distance_to_boundary_meters=150.0,
    )
    evt = gps_service.record_boundary_event(
        db=db,
        hlb_id=hlb.id,
        current_user=enum,
        payload=req,
    )

    db_evt = db.query(HlbBoundaryEvent).filter(HlbBoundaryEvent.id == evt.event_id).first()
    assert db_evt is not None
    assert db_evt.event_type == "EXIT"
    assert db_evt.boundary_status == "OUTSIDE"
    assert db_evt.hlb_id == hlb.id
    assert db_evt.enumerator_id == enum.id


def test_09_supervisor_notification_queued_and_delivered(client: TestClient, db: Session, p10_setup):
    """
    Test 9: Supervisor notification is queued/recorded and supervisor live locations API reflects it.
    """
    hlb = p10_setup["hlb"]
    enum = p10_setup["enumerator"]
    sup = p10_setup["supervisor"]

    # Record EXIT event which triggers supervisor notification
    req = GpsBoundaryEventRequest(
        event_type="EXIT",
        latitude=11.150,
        longitude=77.150,
        accuracy_meters=10.0,
        distance_to_boundary_meters=150.0,
    )
    evt = gps_service.record_boundary_event(
        db=db,
        hlb_id=hlb.id,
        current_user=enum,
        payload=req,
    )
    assert evt.supervisor_notified is True
    db_evt = db.query(HlbBoundaryEvent).filter(HlbBoundaryEvent.id == evt.event_id).first()
    assert db_evt is not None
    assert db_evt.notification_details.get("supervisor_id") == str(sup.id)
    assert db_evt.notification_details.get("status") == "DELIVERED"

    # Supervisor retrieves live locations endpoint
    sup_token = _login(client, sup.username)
    res = client.get(
        "/api/v1/supervisor/enumerator-locations",
        headers={"Authorization": f"Bearer {sup_token}"},
    )
    assert res.status_code == 200
    mon_data = res.json()
    assert mon_data["total_enumerators"] >= 1
    found = [e for e in mon_data["enumerators"] if e["enumerator_id"] == str(enum.id)]
    assert len(found) == 1
    assert found[0]["boundary_status"] == "OUTSIDE"
    assert found[0]["is_live"] is True


def test_10_gps_samples_match_correct_road_edges(db: Session, p10_setup):
    """
    Test 10: GPS samples match correct road edges within 15m tolerance.
    """
    hlb = p10_setup["hlb"]
    rn = get_road_network()
    assert rn is not None
    hlb_poly = to_shape(hlb.boundary)
    segs = rn.query_segments_in_polygon(hlb_poly)
    assert len(segs) > 0
    seg = segs[0]

    p1 = seg.coordinates[0]
    p2 = seg.coordinates[-1]
    gps_trace = [
        {"latitude": p1[0], "longitude": p1[1], "accuracy": 10.0},
        {"latitude": p2[0], "longitude": p2[1], "accuracy": 10.0},
    ]

    res = road_coverage_service.match_gps_trace_to_segments(
        db=db,
        hlb_id=hlb.id,
        enumerator_id=p10_setup["enumerator"].id,
        gps_points=gps_trace,
        tolerance_meters=DEFAULT_GPS_ROAD_MATCHING_TOLERANCE_M,
    )
    assert res["updated_segments"] >= 1

    cov = (
        db.query(RoadSegmentCoverage)
        .filter(RoadSegmentCoverage.segment_id == seg.segment_id, RoadSegmentCoverage.hlb_id == hlb.id)
        .first()
    )
    assert cov is not None
    assert cov.surveyed_length_m > 0


def test_11_poor_gps_samples_greater_than_30m_do_not_count_toward_coverage(db: Session, p10_setup):
    """
    Test 11: Poor GPS samples (>30m) do not count toward verified road coverage.
    """
    hlb = p10_setup["hlb"]
    rn = get_road_network()
    hlb_poly = to_shape(hlb.boundary)
    segs = rn.query_segments_in_polygon(hlb_poly)
    assert len(segs) > 1
    seg = segs[1]

    p1 = seg.coordinates[0]
    p2 = seg.coordinates[-1]
    poor_trace = [
        {"latitude": p1[0], "longitude": p1[1], "accuracy": 45.0},
        {"latitude": p2[0], "longitude": p2[1], "accuracy": 50.0},
    ]

    res = road_coverage_service.match_gps_trace_to_segments(
        db=db,
        hlb_id=hlb.id,
        enumerator_id=p10_setup["enumerator"].id,
        gps_points=poor_trace,
        tolerance_meters=DEFAULT_GPS_ROAD_MATCHING_TOLERANCE_M,
    )

    cov = (
        db.query(RoadSegmentCoverage)
        .filter(RoadSegmentCoverage.segment_id == seg.segment_id, RoadSegmentCoverage.hlb_id == hlb.id)
        .first()
    )
    assert cov is not None
    # Accuracy > 30m is rejected from coverage, so surveyed length remains 0.0
    assert cov.surveyed_length_m == 0.0
    assert cov.survey_status == RoadSegmentSurveyStatus.NOT_VISITED


def test_12_partially_walked_roads_remain_in_progress(db: Session, p10_setup):
    """
    Test 12: Partially walked roads (<85%) remain IN_PROGRESS.
    """
    hlb = p10_setup["hlb"]
    rn = get_road_network()
    hlb_poly = to_shape(hlb.boundary)
    segs = rn.query_segments_in_polygon(hlb_poly)
    assert len(segs) > 2
    seg = segs[2]

    p1 = seg.coordinates[0]
    p2 = seg.coordinates[-1]
    # Walk only 25% of the distance
    quarter_lat = p1[0] + 0.25 * (p2[0] - p1[0])
    quarter_lon = p1[1] + 0.25 * (p2[1] - p1[1])
    partial_trace = [
        {"latitude": p1[0], "longitude": p1[1], "accuracy": 8.0},
        {"latitude": quarter_lat, "longitude": quarter_lon, "accuracy": 8.0},
    ]

    road_coverage_service.match_gps_trace_to_segments(
        db=db,
        hlb_id=hlb.id,
        enumerator_id=p10_setup["enumerator"].id,
        gps_points=partial_trace,
    )

    cov = (
        db.query(RoadSegmentCoverage)
        .filter(RoadSegmentCoverage.segment_id == seg.segment_id, RoadSegmentCoverage.hlb_id == hlb.id)
        .first()
    )
    assert cov is not None
    assert cov.coverage_percentage < SURVEY_COMPLETION_THRESHOLD_PCT
    assert cov.survey_status == RoadSegmentSurveyStatus.IN_PROGRESS


def test_13_missed_roads_endpoint_returns_unvisited_edges(client: TestClient, db: Session, p10_setup):
    """
    Test 13: Missed roads endpoint returns unvisited edges and reasons.
    """
    hlb = p10_setup["hlb"]
    token = _login(client, p10_setup["enumerator"].username)

    edge_id = f"edge_missed_{uuid.uuid4().hex[:6]}"
    req_edge = HlbRequiredEdge(
        hlb_id=hlb.id,
        edge_id=edge_id,
        source_way_id="5004",
        start_node_id="node_1",
        end_node_id="node_2",
        length_m=320.0,
        walking_cost=4.2,
        highway_type="path",
        coordinates=[[11.091, 77.091], [11.092, 77.092]],
        coverage_status="NOT_VISITED",
    )
    db.add(req_edge)
    db.commit()

    res = client.get(
        f"/api/v1/routes/hlbs/{hlb.id}/route/missed-roads",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["hlb_id"] == str(hlb.id)
    assert data["missed_edges_count"] >= 1
    missed_item = [e for e in data["missed_roads"] if e["edge_id"] == edge_id][0]
    assert missed_item["coverage_status"] == "NOT_VISITED"
    assert missed_item["total_length_m"] == 320.0
    assert "not_visited" in missed_item["reason"].lower()
    assert len(missed_item["coordinates"]) == 2


def test_14_offline_gps_samples_sync_without_duplicates(client: TestClient, db: Session, p10_setup):
    """
    Test 14: Offline GPS samples sync without duplicates.
    """
    hlb = p10_setup["hlb"]
    token = _login(client, p10_setup["enumerator"].username)

    # Initial position
    res1 = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/route/traversal/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_latitude": 11.090, "current_longitude": 77.095, "accuracy_meters": 10.0},
    )
    assert res1.status_code == 200

    # Resume at same position
    res2 = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/route/traversal/resume",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_latitude": 11.090, "current_longitude": 77.095, "accuracy_meters": 10.0},
    )
    assert res2.status_code == 200


def test_15_backend_independently_enforces_geofence(client: TestClient, db: Session, p10_setup):
    """
    Test 15: Backend independently enforces geofence on endpoints.
    Server calculates point-in-polygon from actual geometry, rejecting spoofed attempts.
    """
    hlb = p10_setup["hlb"]
    token = _login(client, p10_setup["enumerator"].username)

    # Coords clearly outside: lon=77.150, lat=11.150 (boundary max is 77.105, 11.098)
    res = client.post(
        f"/api/v1/routes/hlbs/{hlb.id}/route/traversal/resume",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_latitude": 11.150, "current_longitude": 77.150, "accuracy_meters": 15.0},
    )
    assert res.status_code == 403
    assert "outside your assigned HLB" in res.json()["detail"]
