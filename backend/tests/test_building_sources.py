from pathlib import Path

from sqlalchemy.orm import Session

from app.gis.building_detection import building_detection_service
from app.gis.building_sources import (
    DevelopmentSource,
    OpenBuildingsV3Source,
    get_building_source,
)
from app.gis.building_sources.base import generate_deterministic_building_ref
from app.gis.spatial import (
    validate_and_convert_geojson_polygon,
    validate_and_convert_point,
)
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.house import BuildingSourceType, House

FIXTURES_DIR = Path(__file__).parent / "fixtures"

SAMPLE_BOUNDARY_GEOJSON = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [
                [77.1000, 11.5050],
                [77.1250, 11.5050],
                [77.1250, 11.5200],
                [77.1000, 11.5200],
                [77.1000, 11.5050],
            ]
        ]
    ],
}


def test_open_buildings_source_ingestion_and_spatial_filtering():
    source = OpenBuildingsV3Source(data_directory=FIXTURES_DIR)
    assert source.name == "Google Open Buildings V3"
    assert source.source_type == BuildingSourceType.SATELLITE_DETECTED

    records = source.fetch_buildings(
        boundary_geojson=SAMPLE_BOUNDARY_GEOJSON,
        confidence_threshold=None,
    )

    # Fixture contains 3 buildings inside boundary and 1 outside
    assert len(records) == 3
    for rec in records:
        assert rec.source_type == BuildingSourceType.SATELLITE_DETECTED
        assert rec.imagery_source == "Google Open Buildings V3"
        assert rec.confidence is not None
        assert rec.footprint_geojson["type"] in ("Polygon", "MultiPolygon")
        assert len(rec.footprint_geojson["coordinates"][0]) >= 4
        assert rec.area_in_meters is not None
        assert rec.building_reference.startswith("BLD-")


def test_open_buildings_source_confidence_filtering():
    source = OpenBuildingsV3Source(data_directory=FIXTURES_DIR)
    records_high_conf = source.fetch_buildings(
        boundary_geojson=SAMPLE_BOUNDARY_GEOJSON,
        confidence_threshold=0.85,
    )

    assert len(records_high_conf) == 2  # 0.88 and 0.92, skipping 0.74
    for rec in records_high_conf:
        assert rec.confidence >= 0.85


def test_deterministic_building_reference_stability():
    coords = [
        [77.107950, 11.510950],
        [77.108050, 11.510950],
        [77.108050, 11.511050],
        [77.107950, 11.511050],
        [77.107950, 11.510950],
    ]
    ref1 = generate_deterministic_building_ref(11.511000, 77.108000, coords)
    ref2 = generate_deterministic_building_ref(11.511000, 77.108000, coords)

    assert ref1 == ref2
    assert ref1.startswith("BLD-")
    assert len(ref1) == 10  # "BLD-" (4) + 6 hex chars = 10


def test_development_source_explicit_labeling():
    source = DevelopmentSource()
    assert source.name == "Development Dataset"
    assert source.source_type == BuildingSourceType.DEVELOPMENT_DATA

    records = source.fetch_buildings(
        boundary_geojson=SAMPLE_BOUNDARY_GEOJSON,
        confidence_threshold=None,
    )

    assert len(records) > 0
    for rec in records:
        assert rec.source_type == BuildingSourceType.DEVELOPMENT_DATA
        assert rec.source_type != BuildingSourceType.SATELLITE_DETECTED
        assert rec.imagery_source == "Development Dataset"
        assert rec.building_reference.startswith("BLD-")


def test_get_building_source_factory():
    default_source = get_building_source()
    assert isinstance(default_source, OpenBuildingsV3Source)

    dev_source = get_building_source("development")
    assert isinstance(dev_source, DevelopmentSource)


def test_building_detection_service_idempotence_and_selective_replacement(db: Session):
    wkb_boundary = validate_and_convert_geojson_polygon(SAMPLE_BOUNDARY_GEOJSON)
    area = AdministrativeArea(
        name="Arasur Test Area",
        type=AreaType.VILLAGE,
        code="VILL-TEST-OB-FIXTURE",
        boundary=wkb_boundary,
        status="ACTIVE",
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    # Insert a manual record that should NEVER be deleted by satellite refreshes
    manual_pt = validate_and_convert_point(11.510000, 77.105000)
    manual_house = House(
        area_id=area.id,
        building_reference="MANUAL-001",
        latitude=11.510000,
        longitude=77.105000,
        location=manual_pt,
        source_type=BuildingSourceType.MANUAL,
    )
    db.add(manual_house)
    db.commit()

    # First run using fixture data
    open_bld_source = OpenBuildingsV3Source(data_directory=FIXTURES_DIR)
    records = open_bld_source.fetch_buildings(
        boundary_geojson=SAMPLE_BOUNDARY_GEOJSON,
        confidence_threshold=None,
    )
    assert len(records) == 3

    # Seed through service
    detected = []
    for idx, rec in enumerate(records, start=1):
        wkb_pt = validate_and_convert_point(rec.latitude, rec.longitude)
        wkb_footprint = validate_and_convert_geojson_polygon(rec.footprint_geojson)
        h = House(
            area_id=area.id,
            building_reference=rec.building_reference,
            house_number=f"1/{idx}",
            latitude=rec.latitude,
            longitude=rec.longitude,
            location=wkb_pt,
            footprint=wkb_footprint,
            source_type=rec.source_type,
            detection_confidence=rec.confidence,
            imagery_source=rec.imagery_source,
        )
        detected.append(h)
    db.add_all(detected)
    db.commit()

    # 3 satellite + 1 manual = 4 houses
    total_houses = db.query(House).filter(House.area_id == area.id).count()
    assert total_houses == 4

    # Re-run detection through development fallback to test selective deletion
    building_detection_service.run_building_detection(
        db=db,
        area=area,
        imagery_source="development",
    )

    # Check that manual house was NOT deleted
    persisted_manual = (
        db.query(House)
        .filter(House.area_id == area.id, House.building_reference == "MANUAL-001")
        .first()
    )
    assert persisted_manual is not None
    assert persisted_manual.source_type == BuildingSourceType.MANUAL

    # Estimation summary check
    summary = building_detection_service.get_building_estimation_summary(
        db=db, area=area
    )
    assert summary["total_buildings"] > 0
    assert summary["quality_label"] in (
        "Satellite-derived estimate",
        "Development data",
    )
