from shapely.geometry import MultiPolygon, Polygon

from app.gis.hlb.boundary_checker import (
    BoundaryStatusEnum,
    check_point_in_hlb_boundary,
    point_to_segment_distance_meters,
)


def test_point_to_segment_distance_meters():
    # Segment from (0, 0) to (10, 0)
    # Point at (5, 5) -> distance should be 5.0
    d = point_to_segment_distance_meters(5.0, 5.0, 0.0, 0.0, 10.0, 0.0)
    assert abs(d - 5.0) < 1e-5

    # Point past end of segment at (15, 0) -> distance should be 5.0
    d2 = point_to_segment_distance_meters(15.0, 0.0, 0.0, 0.0, 10.0, 0.0)
    assert abs(d2 - 5.0) < 1e-5

    # Degenerate segment (0, 0) to (0, 0)
    d3 = point_to_segment_distance_meters(3.0, 4.0, 0.0, 0.0, 0.0, 0.0)
    assert abs(d3 - 5.0) < 1e-5


def test_point_clearly_inside_hlb():
    # Square polygon: lon 80.0 to 80.1, lat 13.0 to 13.1
    coords = [(80.0, 13.0), (80.1, 13.0), (80.1, 13.1), (80.0, 13.1), (80.0, 13.0)]
    poly = Polygon(coords)
    # Center point (lat 13.05, lon 80.05) is ~5.5km from boundary
    status, dist, msg = check_point_in_hlb_boundary(
        boundary_geom=poly,
        latitude=13.05,
        longitude=80.05,
        accuracy_meters=10.0,
    )
    assert status == BoundaryStatusEnum.INSIDE
    assert dist is not None
    assert dist > 1000.0
    assert "inside" in msg.lower()


def test_point_clearly_outside_hlb():
    coords = [(80.0, 13.0), (80.1, 13.0), (80.1, 13.1), (80.0, 13.1), (80.0, 13.0)]
    poly = Polygon(coords)
    # Point well outside (lat 13.5, lon 80.5)
    status, dist, msg = check_point_in_hlb_boundary(
        boundary_geom=poly,
        latitude=13.5,
        longitude=80.5,
        accuracy_meters=10.0,
    )
    assert status == BoundaryStatusEnum.OUTSIDE
    assert dist is not None
    assert dist > 1000.0
    assert "outside" in msg.lower()


def test_point_near_boundary_uncertainty():
    coords = [(80.0, 13.0), (80.1, 13.0), (80.1, 13.1), (80.0, 13.1), (80.0, 13.0)]
    poly = Polygon(coords)

    # Point ~5.5m inside southern boundary (lat 13.00005, lon 80.05)
    # With accuracy ±15m, the uncertainty circle overlaps the boundary!
    status, dist, msg = check_point_in_hlb_boundary(
        boundary_geom=poly,
        latitude=13.00005,
        longitude=80.05,
        accuracy_meters=15.0,
    )
    assert status == BoundaryStatusEnum.BOUNDARY_UNCERTAIN
    assert dist is not None
    assert dist < 10.0
    assert "overlap" in msg.lower() or "boundary" in msg.lower()

    # With higher accuracy (±2m), dist (~5.5m) > 2m -> strictly INSIDE
    status_precise, _, _ = check_point_in_hlb_boundary(
        boundary_geom=poly,
        latitude=13.00005,
        longitude=80.05,
        accuracy_meters=2.0,
    )
    assert status_precise == BoundaryStatusEnum.INSIDE

    # Point ~5.5m outside southern boundary (lat 12.99995, lon 80.05)
    # With accuracy ±15m -> BOUNDARY_UNCERTAIN
    status_out_unc, _, _ = check_point_in_hlb_boundary(
        boundary_geom=poly,
        latitude=12.99995,
        longitude=80.05,
        accuracy_meters=15.0,
    )
    assert status_out_unc == BoundaryStatusEnum.BOUNDARY_UNCERTAIN

    # With higher accuracy (±2m) -> strictly OUTSIDE
    status_out_prec, _, _ = check_point_in_hlb_boundary(
        boundary_geom=poly,
        latitude=12.99995,
        longitude=80.05,
        accuracy_meters=2.0,
    )
    assert status_out_prec == BoundaryStatusEnum.OUTSIDE


def test_multipolygon_hlb():
    coords1 = [
        (80.0, 13.0),
        (80.05, 13.0),
        (80.05, 13.05),
        (80.0, 13.05),
        (80.0, 13.0),
    ]
    coords2 = [
        (80.06, 13.0),
        (80.1, 13.0),
        (80.1, 13.05),
        (80.06, 13.05),
        (80.06, 13.0),
    ]
    poly1 = Polygon(coords1)
    poly2 = Polygon(coords2)
    mp = MultiPolygon([poly1, poly2])

    # Point in poly1
    status1, _, _ = check_point_in_hlb_boundary(mp, 13.025, 80.025, 5.0)
    assert status1 == BoundaryStatusEnum.INSIDE

    # Point in poly2
    status2, _, _ = check_point_in_hlb_boundary(mp, 13.025, 80.08, 5.0)
    assert status2 == BoundaryStatusEnum.INSIDE

    # Point between the two islands
    status_between, _, _ = check_point_in_hlb_boundary(mp, 13.025, 80.055, 5.0)
    assert status_between == BoundaryStatusEnum.OUTSIDE


def test_invalid_and_missing_geometry():
    # None boundary
    status, dist, _ = check_point_in_hlb_boundary(None, 13.0, 80.0)
    assert status == BoundaryStatusEnum.UNKNOWN
    assert dist is None

    # Empty geometry
    status_empty, _, _ = check_point_in_hlb_boundary(Polygon(), 13.0, 80.0)
    assert status_empty == BoundaryStatusEnum.UNKNOWN


def test_invalid_coordinates_and_accuracy():
    coords = [(80.0, 13.0), (80.1, 13.0), (80.1, 13.1), (80.0, 13.1), (80.0, 13.0)]
    poly = Polygon(coords)

    # Latitude > 90
    s1, _, _ = check_point_in_hlb_boundary(poly, 95.0, 80.0)
    assert s1 == BoundaryStatusEnum.UNKNOWN

    # Longitude < -180
    s2, _, _ = check_point_in_hlb_boundary(poly, 13.0, -185.0)
    assert s2 == BoundaryStatusEnum.UNKNOWN

    # Negative accuracy
    s3, _, _ = check_point_in_hlb_boundary(poly, 13.05, 80.05, accuracy_meters=-5.0)
    assert s3 == BoundaryStatusEnum.UNKNOWN

    # Accuracy exceeding reliable threshold (> 150m)
    s4, _, msg = check_point_in_hlb_boundary(poly, 13.05, 80.05, accuracy_meters=200.0)
    assert s4 == BoundaryStatusEnum.UNKNOWN
    assert "reliable" in msg.lower()
