from pathlib import Path

from shapely.geometry import Point, Polygon

from app.gis.building_sources.open_buildings import OpenBuildingsV3Source
from app.gis.spatial import (
    COIMBATORE_PROJECTED_CRS,
    buffer_geometry_projected,
    calculate_projected_area_sq_meters,
    calculate_projected_centroid,
    calculate_projected_distance_meters,
)
from app.models.house import BuildingSourceType

DATA_DIR = Path(__file__).parent.parent / "app" / "data" / "open_buildings"


def test_projected_crs_calculations():
    """
    Test EPSG:32643 projected coordinate calculations for Coimbatore:
    1. Planar distance between known points.
    2. Area calculation for a known metric bounding box.
    3. Metric buffering.
    4. Centroid projection.
    """
    # 100m x 100m box in projected coordinates: approx 10,000 sq meters
    # At latitude 11.08, 100m in lat is approx 0.0009 degrees, in lon approx 0.000918 degrees
    test_poly = Polygon(
        [
            [77.120000, 11.080000],
            [77.120918, 11.080000],
            [77.120918, 11.080900],
            [77.120000, 11.080900],
            [77.120000, 11.080000],
        ]
    )

    area_m2 = calculate_projected_area_sq_meters(test_poly, crs=COIMBATORE_PROJECTED_CRS)
    # Expected area is roughly 10,000 m2 (+-5%)
    assert 9500 <= area_m2 <= 10500

    # Distance test: 2 points separated by roughly 100 meters
    p1 = (11.080000, 77.120000)
    p2 = (11.080900, 77.120000)
    dist = calculate_projected_distance_meters(p1, p2, crs=COIMBATORE_PROJECTED_CRS)
    assert 95.0 <= dist <= 105.0

    # Centroid test
    cent_lat, cent_lng = calculate_projected_centroid(test_poly, crs=COIMBATORE_PROJECTED_CRS)
    assert 11.0804 <= cent_lat <= 11.0806
    assert 77.1204 <= cent_lng <= 77.1206

    # Projected metric buffer test (15 meters buffer)
    point_geom = Point(77.120000, 11.080000)
    buffered = buffer_geometry_projected(point_geom, distance_meters=15.0, crs=COIMBATORE_PROJECTED_CRS)
    assert buffered.is_valid
    assert not buffered.is_empty
    buffered_area = calculate_projected_area_sq_meters(buffered, crs=COIMBATORE_PROJECTED_CRS)
    # Circle area for r=15m: pi * 15^2 = ~706.8 m2
    assert 650.0 <= buffered_area <= 750.0


def test_real_open_buildings_ingestion_and_provenance():
    """
    Verify that OpenBuildingsV3Source ingests genuine Google Open Buildings V3 footprints
    extracted from tile 3ba9, calculates projected metric areas and centroids, and preserves provenance.
    """
    source = OpenBuildingsV3Source(data_directory=DATA_DIR)
    assert source.name == "Google Open Buildings V3"
    assert source.source_type == BuildingSourceType.SATELLITE_DETECTED

    # Arasur core bounding polygon
    arasur_test_boundary = {
        "type": "Polygon",
        "coordinates": [
            [
                [77.110, 11.070],
                [77.135, 11.070],
                [77.135, 11.095],
                [77.110, 11.095],
                [77.110, 11.070],
            ]
        ],
    }

    records = source.fetch_buildings(
        boundary_geojson=arasur_test_boundary,
        confidence_threshold=0.75,
    )

    assert len(records) > 0
    prov = source.provenance
    assert prov["is_synthetic"] is False
    assert prov["source"] == "Google Open Buildings V3"
    assert prov["projected_crs"] == "EPSG:32643"
    assert "CC BY-4.0" in prov["licence"]

    # Invariants for each authentic building record
    for rec in records[:100]:
        assert rec.source_type == BuildingSourceType.SATELLITE_DETECTED
        assert rec.confidence >= 0.75
        assert rec.area_in_meters > 0.0
        assert rec.building_reference.startswith("BLD-")
        assert 11.065 <= rec.latitude <= 11.105
        assert 77.105 <= rec.longitude <= 77.145
        assert rec.footprint_geojson["type"] in ("Polygon", "MultiPolygon")


def test_confidence_filtering_on_real_dataset():
    """
    Ensure confidence threshold filtering operates monotonically on real data.
    """
    source = OpenBuildingsV3Source(data_directory=DATA_DIR)

    arasur_boundary = {
        "type": "Polygon",
        "coordinates": [
            [
                [77.115, 11.075],
                [77.130, 11.075],
                [77.130, 11.090],
                [77.115, 11.090],
                [77.115, 11.075],
            ]
        ],
    }

    records_65 = source.fetch_buildings(arasur_boundary, confidence_threshold=0.65)
    records_75 = source.fetch_buildings(arasur_boundary, confidence_threshold=0.75)
    records_85 = source.fetch_buildings(arasur_boundary, confidence_threshold=0.85)

    assert len(records_65) >= len(records_75) >= len(records_85)
    for r in records_85:
        assert r.confidence >= 0.85
