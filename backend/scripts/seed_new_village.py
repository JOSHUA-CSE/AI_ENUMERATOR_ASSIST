"""
Seed script to add a new village (Achipatti - VILL-644592) WITHOUT any layout.
Used for demonstration to show the jury the complete layout creation workflow from scratch:
1. Deputy opens Administrative Areas.
2. Selects Achipatti (500 real Google Open Buildings V3 detected structures).
3. Sees 'No layouts found' empty state.
4. Taps '+ Create Layout' to create a new layout live in front of the jury.
5. Proceeds to AI-assisted HLB generation live.
"""

import json
import logging
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Ensure backend root is in python path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, Point, Polygon, shape
from shapely.validation import make_valid
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.administrative_area import AdministrativeArea, AreaType, BoundaryStatus
from app.models.house import BuildingFieldStatus, BuildingSourceType, House

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def seed_achipatti_without_layout(db: Session) -> dict:
    """Seed Achipatti village and real building footprints without creating any layout."""
    # Check if Achipatti already exists
    existing = db.query(AdministrativeArea).filter(AdministrativeArea.code == "VILL-644592").first()
    if existing:
        logger.info("Achipatti already exists in database (ID: %s). Cleaning prior houses...", existing.id)
        db.query(House).filter(House.area_id == existing.id).delete()
        db.delete(existing)
        db.commit()

    # 1. Load Achipatti Provisional Boundary
    boundary_path = backend_root / "app" / "data" / "boundaries" / "achipatti_provisional_boundary.geojson"
    if not boundary_path.exists():
        raise FileNotFoundError(f"Achipatti boundary file missing: {boundary_path}")

    with open(boundary_path, "r", encoding="utf-8") as f:
        boundary_json = json.load(f)

    feature = boundary_json["features"][0]
    raw_geom = shape(feature["geometry"])
    if not raw_geom.is_valid:
        raw_geom = make_valid(raw_geom)

    if isinstance(raw_geom, Polygon):
        achipatti_multipolygon = MultiPolygon([raw_geom])
    elif isinstance(raw_geom, MultiPolygon):
        achipatti_multipolygon = raw_geom
    else:
        raise ValueError(f"Unexpected geometry type: {type(raw_geom)}")

    # 2. Create AdministrativeArea for Achipatti
    achipatti_area = AdministrativeArea(
        id=uuid.uuid4(),
        name="Achipatti",
        type=AreaType.VILLAGE,
        code="VILL-644592",
        boundary=from_shape(achipatti_multipolygon, srid=4326),
        boundary_status=BoundaryStatus.PROVISIONAL.value,
        status="ACTIVE",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(achipatti_area)
    db.flush()
    logger.info("Created Achipatti administrative area (ID: %s, Code: %s)", achipatti_area.id, achipatti_area.code)

    # 3. Load Real Google Open Buildings V3 Footprints for Achipatti
    buildings_path = backend_root / "app" / "data" / "open_buildings" / "pollachi_real_open_buildings_v3.json"
    if not buildings_path.exists():
        raise FileNotFoundError(f"Real buildings dataset missing: {buildings_path}")

    with open(buildings_path, "r", encoding="utf-8") as f:
        buildings_data = json.load(f)

    raw_buildings = buildings_data.get("buildings", [])
    logger.info("Filtering from %d total buildings in Pollachi dataset...", len(raw_buildings))

    included_houses = []
    for b in raw_buildings:
        pt = Point(b["longitude"], b["latitude"])
        if raw_geom.contains(pt) or raw_geom.touches(pt):
            fp_raw = b.get("footprint")
            fp_geom = None
            if fp_raw:
                try:
                    g = shape(fp_raw)
                    if not g.is_valid:
                        g = make_valid(g)
                    if isinstance(g, Polygon):
                        fp_geom = from_shape(MultiPolygon([g]), srid=4326)
                    elif isinstance(g, MultiPolygon):
                        fp_geom = from_shape(g, srid=4326)
                except Exception:
                    fp_geom = None

            house = House(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"achipatti-{b.get('building_reference', b.get('id', len(included_houses)))}"),
                area_id=achipatti_area.id,
                building_reference=b.get("building_reference") or b.get("source_id") or f"ACH-{len(included_houses)+1:04d}",
                house_number=None,
                latitude=float(b["latitude"]),
                longitude=float(b["longitude"]),
                location=from_shape(Point(float(b["longitude"]), float(b["latitude"])), srid=4326),
                footprint=fp_geom,
                source_type=BuildingSourceType.SATELLITE_DETECTED,
                detection_confidence=float(b.get("confidence", 0.92)),
                detected_at=datetime(2023, 5, 15, tzinfo=UTC),
                imagery_source="Google Open Buildings V3",
                imagery_date=datetime(2023, 5, 15, tzinfo=UTC),
                field_status=BuildingFieldStatus.UNVERIFIED,
                listing_closed=False,
            )
            included_houses.append(house)

    db.bulk_save_objects(included_houses)
    db.commit()
    logger.info("Successfully seeded %d real Google Open Buildings V3 footprints for Achipatti", len(included_houses))

    return {
        "status": "SUCCESS",
        "village_name": achipatti_area.name,
        "village_code": achipatti_area.code,
        "boundary_status": achipatti_area.boundary_status,
        "building_source": "Google Open Buildings V3 (Real Footprints)",
        "total_buildings_seeded": len(included_houses),
        "layouts_created": 0,
        "ready_for_jury_demo": True,
        "demonstration_instructions": [
            "1. Open Administrative Areas in the app.",
            "2. Tap 'Achipatti' (shows 500 detected buildings, NO layout).",
            "3. Tap '+ Create Layout' button live in front of jury.",
            "4. Enter layout name (e.g. 'Achipatti Demonstration Layout'), set target to 250, tap Confirm.",
            "5. UI automatically navigates into HLB Generation screen with the 500 building footprints.",
            "6. Tap 'GENERATE HLBs' to demonstrate live AI spatial partitioning (generates 2 balanced HLBs of 250 buildings each).",
            "7. Review and Approve the layout live!"
        ]
    }


if __name__ == "__main__":
    db = SessionLocal()
    try:
        res = seed_achipatti_without_layout(db)
        print("\n=== NEW VILLAGE SEEDED (NO LAYOUT) ===")
        print(json.dumps(res, indent=2))
    finally:
        db.close()

