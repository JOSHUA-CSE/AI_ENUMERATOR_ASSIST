import json
import time
import uuid
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from shapely.geometry import Point, Polygon, LineString
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.gis.route.road_network import RoadNetwork, RoadSegment
from app.gis.route.coverage_router import generate_hlb_road_coverage_route
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.building_edit import BuildingEdit, BuildingEditReviewStatus, BuildingEditType
from app.models.enumerator_assignment import EnumeratorAssignmentStatus, HlbEnumeratorAssignment
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import BuildingFieldStatus, BuildingSourceType, House
from app.models.layout import Layout, LayoutStatus, LayoutVersion, LayoutVersionSource, LayoutVersionStatus
from app.models.road_coverage import RoadCoverageSyncStatus, RoadSegmentCoverage, RoadSegmentSurveyStatus
from app.models.supervisor_assignment import LayoutSupervisorAssignment, SupervisorAssignmentStatus
from app.models.user import User, UserRole, UserStatus
from app.services.building_discovery_service import building_discovery_service
from app.services.road_coverage_service import road_coverage_service


@pytest.fixture
def p8_fixture(db: Session):
    suffix = uuid.uuid4().hex[:6]

    supervisor = User(
        name="Supervisor P8",
        username=f"sup_p8_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPERVISOR,
        status=UserStatus.ACTIVE,
    )
    enumerator = User(
        name="Enumerator P8",
        username=f"enum_p8_{suffix}",
        password_hash=get_password_hash("password123"),
        role=UserRole.ENUMERATOR,
        status=UserStatus.ACTIVE,
    )
    db.add_all([supervisor, enumerator])
    db.commit()

    # Arasur area covering known OSM roads
    area = AdministrativeArea(
        name=f"Arasur Village P8 {suffix}",
        code=f"AREA-ARASUR-P8-{suffix}",
        type=AreaType.VILLAGE,
        boundary=WKTElement(
            "MULTIPOLYGON(((77.08 11.08, 77.12 11.08, 77.12 11.12, 77.08 11.12, 77.08 11.08)))",
            srid=4326,
        ),
    )
    db.add(area)
    db.commit()

    layout = Layout(
        name=f"Layout Arasur P8 {suffix}",
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

    # HLB 1 with verified OSM road coverage in Arasur
    hlb = HouselistingBlock(
        layout_id=layout.id,
        version_id=v.id,
        block_code=f"HLB-P8-{suffix}",
        name="Arasur Road Coverage Block 1",
        target_building_count=120,
        actual_building_count=0,
        boundary=WKTElement(
            "MULTIPOLYGON(((77.090 11.085, 77.105 11.085, 77.105 11.098, 77.090 11.098, 77.090 11.085)))",
            srid=4326,
        ),
    )
    # HLB 2 in empty area without OSM roads
    hlb_no_roads = HouselistingBlock(
        layout_id=layout.id,
        version_id=v.id,
        block_code=f"HLB-EMPTY-P8-{suffix}",
        name="Empty Remote Block",
        target_building_count=100,
        actual_building_count=0,
        boundary=WKTElement(
            "MULTIPOLYGON(((76.500 10.100, 76.505 10.100, 76.505 10.105, 76.500 10.105, 76.500 10.100)))",
            srid=4326,
        ),
    )
    db.add_all([hlb, hlb_no_roads])
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
    db.add(
        HlbEnumeratorAssignment(
            hlb_id=hlb_no_roads.id,
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
        "hlb_no_roads": hlb_no_roads,
    }


def _login(client: TestClient, username: str) -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def _make_seg(seg_id, way_id, node_ids, coords, length_m, highway="residential"):
    geom = LineString([(c[1], c[0]) for c in coords])
    return RoadSegment(
        segment_id=seg_id,
        osm_way_id=way_id,
        osm_node_ids=node_ids,
        coordinates=coords,
        geometry=geom,
        length_m=length_m,
        highway=highway,
    )


# 1. Route follows actual road geometry
def test_route_follows_actual_road_geometry(p8_fixture, db: Session):
    hlb = p8_fixture["hlb"]
    enum = p8_fixture["enumerator"]
    route = road_coverage_service.generate_coverage_route(
        db, hlb.id, enumerator_id=enum.id, return_to_start=False
    )

    assert route.total_distance_km > 0
    assert len(route.continuous_polyline) >= 2

    # Every polyline vertex must have valid [lat, lon] coordinates within the bounding box
    for pt in route.continuous_polyline:
        lat, lon = pt
        assert 11.080 <= lat <= 11.105
        assert 77.085 <= lon <= 77.110

    # Segments returned must have non-zero lengths and valid road highway tags
    for seg in route.all_road_segments:
        assert seg["length_m"] > 0
        assert seg["highway"] in [
            "residential",
            "unclassified",
            "living_street",
            "pedestrian",
            "footway",
            "path",
            "service",
            "track",
            "steps",
            "tertiary",
            "secondary",
            "primary",
        ]


# 2. Primary route does not depend on building coordinates
def test_primary_route_independent_of_building_coordinates(p8_fixture, db: Session):
    hlb = p8_fixture["hlb"]
    enum = p8_fixture["enumerator"]
    area = p8_fixture["area"]

    # Route with 0 buildings
    route_0_buildings = road_coverage_service.generate_coverage_route(
        db, hlb.id, enumerator_id=enum.id, return_to_start=False
    )

    # Add 5 buildings in the HLB
    bldgs = []
    for i in range(5):
        lat = 11.088 + (i * 0.001)
        lon = 77.095 + (i * 0.001)
        b = House(
            area_id=area.id,
            building_reference=f"BLD-P8-TEST-{i}-{uuid.uuid4().hex[:4]}",
            latitude=lat,
            longitude=lon,
            location=WKTElement(f"POINT({lon} {lat})", srid=4326),
            source_type=BuildingSourceType.SATELLITE_DETECTED,
            field_status=BuildingFieldStatus.UNVERIFIED,
        )
        db.add(b)
        db.flush()
        bldgs.append(b)
        db.add(HlbHouse(hlb_id=hlb.id, house_id=b.id))
    hlb.actual_building_count = 5
    db.commit()

    # Route with 5 buildings
    route_5_buildings = road_coverage_service.generate_coverage_route(
        db, hlb.id, enumerator_id=enum.id, return_to_start=False
    )

    # Road network geometry and distance must be EXACTLY identical regardless of buildings
    assert route_0_buildings.total_distance_km == route_5_buildings.total_distance_km
    assert len(route_0_buildings.continuous_polyline) == len(route_5_buildings.continuous_polyline)
    assert route_0_buildings.continuous_polyline == route_5_buildings.continuous_polyline
    assert route_0_buildings.total_segments_count == route_5_buildings.total_segments_count


# 3. HLB boundary restrictions (clipping/filtering)
def test_hlb_boundary_restrictions(p8_fixture, db: Session):
    hlb = p8_fixture["hlb"]
    enum = p8_fixture["enumerator"]
    boundary_poly = Polygon([(77.090, 11.085), (77.105, 11.085), (77.105, 11.098), (77.090, 11.098)])

    route = road_coverage_service.generate_coverage_route(
        db, hlb.id, enumerator_id=enum.id, return_to_start=False
    )
    assert route.total_segments_count > 0

    # Ensure all segments are within or intersect the HLB boundary polygon (expanded by small buffer for tolerance)
    buffered_poly = boundary_poly.buffer(0.002)
    for seg in route.all_road_segments:
        seg_coords = [(c[1], c[0]) for c in seg["coordinates"]]  # (lon, lat)
        seg_line = LineString(seg_coords)
        assert buffered_poly.intersects(seg_line), f"Segment {seg['segment_id']} is outside the HLB boundary!"


# 4. Road network connectivity and Eulerian path generation
def test_road_network_connectivity_and_eulerian_path():
    # Construct a small synthetic road network with 4 nodes forming a ring + cross
    # Nodes: (11.0, 77.0), (11.0, 77.1), (11.1, 77.1), (11.1, 77.0)
    segs = [
        _make_seg("s1", 1, [1, 2], [(11.0, 77.0), (11.0, 77.1)], 100.0, "residential"),
        _make_seg("s2", 2, [2, 3], [(11.0, 77.1), (11.1, 77.1)], 100.0, "residential"),
        _make_seg("s3", 3, [3, 4], [(11.1, 77.1), (11.1, 77.0)], 100.0, "residential"),
        _make_seg("s4", 4, [4, 1], [(11.1, 77.0), (11.0, 77.0)], 100.0, "residential"),
    ]
    poly = Polygon([(76.9, 10.9), (77.2, 10.9), (77.2, 11.2), (76.9, 11.2)])
    rn = RoadNetwork(segments=segs)
    route = generate_hlb_road_coverage_route(
        hlb_id="test-hlb-1",
        hlb_polygon=poly,
        road_network=rn,
        return_to_start=True,
    )

    assert route.total_segments_count == 4
    assert len(route.sections) == 1
    assert route.disconnected_components_count == 1
    # Check that Eulerian traversal visits all 4 segments
    assert len(route.continuous_polyline) >= 5


# 5. Disconnected network handling without fake straight lines
def test_disconnected_network_handling():
    # Two disconnected roads far apart:
    # Road 1: (11.0, 77.0) to (11.0, 77.01)
    # Road 2: (11.05, 77.05) to (11.05, 77.06)
    segs = [
        _make_seg("s_c1", 1, [1, 2], [(11.0, 77.0), (11.0, 77.01)], 110.0, "residential"),
        _make_seg("s_c2", 2, [3, 4], [(11.05, 77.05), (11.05, 77.06)], 110.0, "residential"),
    ]
    poly = Polygon([(76.9, 10.9), (77.2, 10.9), (77.2, 11.2), (76.9, 11.2)])
    rn = RoadNetwork(segments=segs)
    route = generate_hlb_road_coverage_route(
        hlb_id="test-hlb-disc",
        hlb_polygon=poly,
        road_network=rn,
        return_to_start=False,
    )

    assert route.disconnected_components_count == 2
    assert len(route.sections) == 2
    # Section 1 is primary
    assert route.sections[0].is_primary is True
    assert route.sections[0].is_disconnected is False
    # Section 2 is secondary disconnected with disconnection distance note
    assert route.sections[1].is_primary is False
    assert route.sections[1].is_disconnected is True
    assert route.sections[1].disconnection_distance_m > 5000.0
    assert "road section" in route.sections[1].disconnection_note.lower()


# 6. Surveyed vs unsurveyed segment tracking and prioritization
def test_surveyed_vs_unsurveyed_tracking(p8_fixture, db: Session):
    hlb = p8_fixture["hlb"]
    enum = p8_fixture["enumerator"]
    route = road_coverage_service.generate_coverage_route(
        db, hlb.id, enumerator_id=enum.id
    )

    # Initial state: 0% surveyed
    assert route.surveyed_segments_count == 0
    assert route.coverage_percentage == 0.0

    # Mark first segment as SURVEYED in DB
    first_seg = route.all_road_segments[0]
    rec = (
        db.query(RoadSegmentCoverage)
        .filter(
            RoadSegmentCoverage.hlb_id == hlb.id,
            RoadSegmentCoverage.segment_id == first_seg["segment_id"],
        )
        .first()
    )
    if not rec:
        rec = RoadSegmentCoverage(
            hlb_id=hlb.id,
            segment_id=first_seg["segment_id"],
            enumerator_id=enum.id,
            survey_status=RoadSegmentSurveyStatus.SURVEYED,
            total_length_m=first_seg["length_m"],
            surveyed_length_m=first_seg["length_m"],
            coverage_percentage=100.0,
            segment_geometry=first_seg["coordinates"],
        )
        db.add(rec)
    else:
        rec.survey_status = RoadSegmentSurveyStatus.SURVEYED
        rec.surveyed_length_m = first_seg["length_m"]
        rec.coverage_percentage = 100.0
    db.commit()

    # Re-fetch route
    updated_route = road_coverage_service.generate_coverage_route(
        db, hlb.id, enumerator_id=enum.id
    )
    assert updated_route.surveyed_segments_count == 1
    assert updated_route.coverage_percentage > 0.0


# 7. GPS trace-to-road matching with 20m tolerance and 70% threshold
def test_gps_trace_matching(p8_fixture, db: Session):
    hlb = p8_fixture["hlb"]
    enum = p8_fixture["enumerator"]

    route = road_coverage_service.generate_coverage_route(
        db, hlb.id, enumerator_id=enum.id
    )
    assert len(route.all_road_segments) > 0
    seg = route.all_road_segments[0]
    coords = seg["coordinates"]
    p1_lat, p1_lon = coords[0]
    p2_lat, p2_lon = coords[-1]

    # Submitting GPS points along 80% of the segment length
    mid_lat = (p1_lat + p2_lat) / 2.0
    mid_lon = (p1_lon + p2_lon) / 2.0
    gps_trace = [
        {"latitude": p1_lat, "longitude": p1_lon, "accuracy": 5.0},
        {"latitude": mid_lat, "longitude": mid_lon, "accuracy": 5.0},
        {"latitude": p2_lat, "longitude": p2_lon, "accuracy": 5.0},
    ]

    res = road_coverage_service.match_gps_trace_to_segments(
        db=db,
        hlb_id=hlb.id,
        enumerator_id=enum.id,
        gps_points=gps_trace,
        tolerance_meters=20.0,
    )

    assert res["coverage_summary"]["total_segments"] > 0
    assert res["updated_segments"] >= 1

    # Verify record in DB
    cov = (
        db.query(RoadSegmentCoverage)
        .filter(
            RoadSegmentCoverage.hlb_id == hlb.id,
            RoadSegmentCoverage.segment_id == seg["segment_id"],
        )
        .first()
    )
    assert cov is not None
    assert cov.survey_status in [RoadSegmentSurveyStatus.IN_PROGRESS, RoadSegmentSurveyStatus.SURVEYED]


# 8. Route resumption after pause/interruption
def test_route_resumption(p8_fixture, db: Session):
    hlb = p8_fixture["hlb"]
    enum = p8_fixture["enumerator"]

    route = road_coverage_service.generate_coverage_route(db, hlb.id, enumerator_id=enum.id)
    half = max(1, len(route.all_road_segments) // 2)
    for seg in route.all_road_segments[:half]:
        cov = (
            db.query(RoadSegmentCoverage)
            .filter(
                RoadSegmentCoverage.hlb_id == hlb.id,
                RoadSegmentCoverage.segment_id == seg["segment_id"],
            )
            .first()
        )
        if not cov:
            cov = RoadSegmentCoverage(
                hlb_id=hlb.id,
                segment_id=seg["segment_id"],
                enumerator_id=enum.id,
                survey_status=RoadSegmentSurveyStatus.SURVEYED,
                total_length_m=seg["length_m"],
                surveyed_length_m=seg["length_m"],
                coverage_percentage=100.0,
                segment_geometry=seg["coordinates"],
            )
            db.add(cov)
        else:
            cov.survey_status = RoadSegmentSurveyStatus.SURVEYED
            cov.surveyed_length_m = seg["length_m"]
            cov.coverage_percentage = 100.0
    db.commit()

    # Generate route with starting coordinate near the surveyed part
    resumed_route = road_coverage_service.generate_coverage_route(
        db, hlb.id, enumerator_id=enum.id, current_lat=11.090, current_lon=77.095
    )
    assert resumed_route.surveyed_segments_count >= half
    assert resumed_route.coverage_percentage > 0


# 9. Building discovery during traversal (independent of route)
def test_building_discovery_during_traversal(p8_fixture, db: Session):
    hlb = p8_fixture["hlb"]
    enum = p8_fixture["enumerator"]

    disc_lat = 11.0895
    disc_lon = 77.0935
    result = building_discovery_service.discover_building(
        db=db,
        hlb_id=hlb.id,
        enumerator_id=enum.id,
        latitude=disc_lat,
        longitude=disc_lon,
        building_reference="BLD-DISC-001",
        house_number="42-A",
        notes="New construction discovered during road sweep",
    )

    assert result["source_type"] == BuildingSourceType.FIELD_DISCOVERED.value
    assert result["field_status"] == BuildingFieldStatus.FIELD_ADDED.value
    assert result["building_reference"] == "BLD-DISC-001"
    assert result["building_edit_id"] is not None

    # Verify building exists in DB
    house_id = uuid.UUID(result["building_id"]) if isinstance(result["building_id"], str) else result["building_id"]
    house = db.query(House).filter(House.id == house_id).first()
    assert house is not None
    assert house.source_type == BuildingSourceType.FIELD_DISCOVERED
    assert house.field_status == BuildingFieldStatus.FIELD_ADDED

    # Verify BuildingEdit audit record was created
    edit_id = uuid.UUID(result["building_edit_id"]) if isinstance(result["building_edit_id"], str) else result["building_edit_id"]
    edit = db.query(BuildingEdit).filter(BuildingEdit.id == edit_id).first()
    assert edit is not None
    assert edit.edit_type == BuildingEditType.ADD
    assert edit.review_status == BuildingEditReviewStatus.PENDING


# 10. Duplicate building prevention (proximity < 5m and reference collision)
def test_duplicate_building_prevention(p8_fixture, db: Session):
    hlb = p8_fixture["hlb"]
    enum = p8_fixture["enumerator"]
    area = p8_fixture["area"]

    # Existing building
    lat0 = 11.092000
    lon0 = 77.095000
    b0 = House(
        area_id=area.id,
        building_reference="BLD-ORIGINAL-001",
        latitude=lat0,
        longitude=lon0,
        location=WKTElement(f"POINT({lon0} {lat0})", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
        field_status=BuildingFieldStatus.UNVERIFIED,
    )
    db.add(b0)
    db.flush()
    db.add(HlbHouse(hlb_id=hlb.id, house_id=b0.id))
    db.commit()

    # 1. Proximity collision: < 5m away (~2m difference in latitude)
    lat_too_close = 11.092020
    lon_too_close = 77.095000
    with pytest.raises(HTTPException) as excinfo:
        building_discovery_service.discover_building(
            db=db,
            hlb_id=hlb.id,
            enumerator_id=enum.id,
            latitude=lat_too_close,
            longitude=lon_too_close,
            building_reference="BLD-TOO-CLOSE",
        )
    assert excinfo.value.status_code == 409
    assert "DUPLICATE_BUILDING_PROXIMITY" in str(excinfo.value.detail)

    # 2. Reference code collision
    lat_valid = 11.094000
    lon_valid = 77.095000
    with pytest.raises(HTTPException) as excinfo2:
        building_discovery_service.discover_building(
            db=db,
            hlb_id=hlb.id,
            enumerator_id=enum.id,
            latitude=lat_valid,
            longitude=lon_valid,
            building_reference="BLD-ORIGINAL-001",  # duplicate reference
        )
    assert excinfo2.value.status_code == 409
    assert "DUPLICATE_BUILDING_REFERENCE" in str(excinfo2.value.detail)

    # 3. Valid discovery (distance ~220m, unique reference)
    res = building_discovery_service.discover_building(
        db=db,
        hlb_id=hlb.id,
        enumerator_id=enum.id,
        latitude=lat_valid,
        longitude=lon_valid,
        building_reference="BLD-VALID-002",
    )
    assert res["building_id"] is not None


# 11. GPS deviation detection (>50m)
def test_gps_deviation_detection():
    # Route along a north-south line: lon=77.100, lat from 11.080 to 11.090
    polyline = [[11.080, 77.100], [11.085, 77.100], [11.090, 77.100]]

    # Case A: GPS location directly on route
    on_track = road_coverage_service.detect_route_deviation(
        current_lat=11.083, current_lon=77.100, route_polyline=polyline, threshold_meters=50.0
    )
    assert on_track["is_deviated"] is False
    assert on_track["deviation_distance_m"] < 10.0

    # Case B: GPS location 150 meters away (lon=77.1015, ~163m east)
    off_track = road_coverage_service.detect_route_deviation(
        current_lat=11.083, current_lon=77.1015, route_polyline=polyline, threshold_meters=50.0
    )
    assert off_track["is_deviated"] is True
    assert off_track["deviation_distance_m"] > 50.0
    assert "Off route" in off_track["message"]


# 12. Offline route persistence and missing road network warning
def test_offline_route_and_missing_road_data(p8_fixture, db: Session, client: TestClient):
    hlb_no_roads = p8_fixture["hlb_no_roads"]
    enum = p8_fixture["enumerator"]
    token = _login(client, enum.username)

    # Test HLB in area with 0 OSM roads
    res = client.post(
        f"/api/v1/hlbs/{hlb_no_roads.id}/route/coverage",
        headers={"Authorization": f"Bearer {token}"},
        json={"return_to_start": False},
    )
    assert res.status_code == 404
    body = res.json()
    err_text = json.dumps(body)
    assert "MISSING_ROAD_NETWORK_DATA" in err_text


# 13. Large network performance (bounded execution time)
def test_large_network_performance(p8_fixture, db: Session):
    hlb = p8_fixture["hlb"]
    enum = p8_fixture["enumerator"]
    start_time = time.time()
    route = road_coverage_service.generate_coverage_route(
        db, hlb.id, enumerator_id=enum.id, return_to_start=True
    )
    elapsed = time.time() - start_time

    # Performance must be bounded: under 2.5 seconds for complete network extraction & Eulerian tour
    assert elapsed < 2.5, f"Coverage routing took too long: {elapsed:.2f}s"
    assert route.total_distance_km > 0


# 14. Road coverage progress vs building progress separation
def test_road_coverage_vs_building_progress_separation(p8_fixture, db: Session):
    hlb = p8_fixture["hlb"]
    enum = p8_fixture["enumerator"]
    area = p8_fixture["area"]

    # Create 4 buildings, 3 completed
    b_completed = []
    for i in range(3):
        lat = 11.088 + (i * 0.001)
        lon = 77.095
        b = House(
            area_id=area.id,
            building_reference=f"BLD-COMP-{i}-{uuid.uuid4().hex[:4]}",
            latitude=lat,
            longitude=lon,
            location=WKTElement(f"POINT({lon} {lat})", srid=4326),
            source_type=BuildingSourceType.SATELLITE_DETECTED,
            field_status=BuildingFieldStatus.CONFIRMED,
        )
        db.add(b)
        db.flush()
        db.add(HlbHouse(hlb_id=hlb.id, house_id=b.id))
        b_completed.append(b)

    b_pending = House(
        area_id=area.id,
        building_reference=f"BLD-PEND-{uuid.uuid4().hex[:4]}",
        latitude=11.091,
        longitude=77.095,
        location=WKTElement("POINT(77.095 11.091)", srid=4326),
        source_type=BuildingSourceType.SATELLITE_DETECTED,
        field_status=BuildingFieldStatus.UNVERIFIED,
    )
    db.add(b_pending)
    db.flush()
    db.add(HlbHouse(hlb_id=hlb.id, house_id=b_pending.id))
    hlb.actual_building_count = 4
    db.commit()

    # Route road coverage check
    route = road_coverage_service.generate_coverage_route(
        db, hlb.id, enumerator_id=enum.id
    )

    # Road coverage is strictly 0% because no road segments have been surveyed yet,
    # even though building progress is 75% (3/4 buildings completed).
    assert route.coverage_percentage == 0.0
    assert route.surveyed_segments_count == 0

    # Mark all road segments as surveyed
    for seg in route.all_road_segments:
        rec = RoadSegmentCoverage(
            hlb_id=hlb.id,
            segment_id=seg["segment_id"],
            enumerator_id=enum.id,
            survey_status=RoadSegmentSurveyStatus.SURVEYED,
            total_length_m=seg["length_m"],
            surveyed_length_m=seg["length_m"],
            coverage_percentage=100.0,
            segment_geometry=seg["coordinates"],
        )
        db.add(rec)
    db.commit()

    # Now road coverage is 100%, but building completion remains untouched (still 3/4)
    route_full_roads = road_coverage_service.generate_coverage_route(
        db, hlb.id, enumerator_id=enum.id
    )
    assert route_full_roads.coverage_percentage == 100.0
    assert route_full_roads.surveyed_segments_count == len(route.all_road_segments)

    # Re-verify houses in DB: still 3 confirmed, 1 unverified
    houses_in_hlb = (
        db.query(House)
        .join(HlbHouse, HlbHouse.house_id == House.id)
        .filter(HlbHouse.hlb_id == hlb.id)
        .all()
    )
    confirmed_count = sum(1 for h in houses_in_hlb if h.field_status == BuildingFieldStatus.CONFIRMED)
    assert confirmed_count == 3
    assert len(houses_in_hlb) == 4
