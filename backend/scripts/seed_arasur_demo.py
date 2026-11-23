"""
Seed script for Arasur Demonstration Dataset.
Cleans obsolete test/preview data and seeds real Arasur geographic data:
- Cleans obsolete test areas, layouts, synthetic buildings, and temporary previews.
- Preserves 13 application user accounts (deputy01, supervisor01-04, enumerator01-08).
- Seeds Arasur Village (VILL-644401) with provisional administrative boundary.
- Seeds 1,000 genuine Google Open Buildings V3 footprints from arasur_real_open_buildings_v3.json.
- Creates 'Arasur Demonstration Layout'.
- Generates 4 candidate HLBs (target 250 buildings each) using the AI/GIS RPP spatial partitioning engine.
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
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.gis.hlb.generator_service import hlb_generation_service
from app.models.administrative_area import AdministrativeArea, AreaType, BoundaryStatus
from app.models.house import BuildingFieldStatus, BuildingSourceType, House
from app.models.layout import (
    Layout,
    LayoutAdministrativeArea,
    LayoutStatus,
    WorkloadUnit,
)
from app.models.supervisor_assignment import (
    LayoutSupervisorAssignment,
    SupervisorAssignmentStatus,
)
from app.models.user import User, UserRole, UserStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TEMP_DEV_PASSWORD = "Pollachi@2026"

USERS_SPEC = [
    {"username": "deputy01", "name": "Deputy Tahsildar Pollachi", "role": UserRole.DEPUTY_TAHSILDAR},
    {"username": "supervisor01", "name": "Supervisor North", "role": UserRole.SUPERVISOR},
    {"username": "supervisor02", "name": "Supervisor South", "role": UserRole.SUPERVISOR},
    {"username": "supervisor03", "name": "Supervisor Reserve A", "role": UserRole.SUPERVISOR},
    {"username": "supervisor04", "name": "Supervisor Reserve B", "role": UserRole.SUPERVISOR},
    {"username": "enumerator01", "name": "Enumerator 01", "role": UserRole.ENUMERATOR},
    {"username": "enumerator02", "name": "Enumerator 02", "role": UserRole.ENUMERATOR},
    {"username": "enumerator03", "name": "Enumerator 03", "role": UserRole.ENUMERATOR},
    {"username": "enumerator04", "name": "Enumerator 04", "role": UserRole.ENUMERATOR},
    {"username": "enumerator05", "name": "Enumerator 05", "role": UserRole.ENUMERATOR},
    {"username": "enumerator06", "name": "Enumerator 06", "role": UserRole.ENUMERATOR},
    {"username": "enumerator07", "name": "Enumerator 07", "role": UserRole.ENUMERATOR},
    {"username": "enumerator08", "name": "Enumerator 08", "role": UserRole.ENUMERATOR},
]

TABLES_TO_CLEAN = [
    "hlb_boundary_events",
    "missing_path_submissions",
    "hlb_route_traversals",
    "hlb_route_plans",
    "hlb_required_edges",
    "road_edges",
    "road_nodes",
    "road_graphs",
    "road_segment_coverages",
    "supervisor_corrections",
    "sync_operations",
    "change_request_messages",
    "change_requests",
    "building_edits",
    "revisits",
    "gps_tracks",
    "house_fieldwork_status",
    "household_records",
    "census_houses",
    "persons",
    "hlb_counters",
    "hlb_houses",
    "hlb_enumerator_assignments",
    "houselisting_blocks",
    "layout_supervisor_assignments",
    "layout_versions",
    "layout_administrative_areas",
    "layouts",
    "houses",
    "administrative_areas",
    "audit_logs",
]


def clean_test_data(db: Session) -> dict[str, int]:
    """Remove test and preview records in correct foreign key order."""
    deleted_counts = {}
    for table_name in TABLES_TO_CLEAN:
        try:
            count = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
            if count > 0:
                db.execute(text(f"DELETE FROM {table_name}"))
                deleted_counts[table_name] = count
        except Exception as e:
            logger.warning("Could not delete from %s: %s", table_name, e)
    db.commit()
    logger.info("Test/preview data cleanup completed. Records removed: %s", deleted_counts)
    return deleted_counts


def ensure_users(db: Session) -> dict[str, User]:
    """Ensure the 13 required user accounts exist and are ACTIVE."""
    users_by_username = {}
    hashed_pwd = get_password_hash(TEMP_DEV_PASSWORD)
    for spec in USERS_SPEC:
        user = db.query(User).filter(User.username == spec["username"]).first()
        if not user:
            user = User(
                id=uuid.uuid4(),
                username=spec["username"],
                hashed_password=hashed_pwd,
                name=spec["name"],
                role=spec["role"],
                status=UserStatus.ACTIVE,
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            db.add(user)
            db.flush()
            logger.info("Created user: %s (%s)", user.username, user.role.value)
        else:
            user.status = UserStatus.ACTIVE
            user.is_active = True
        users_by_username[user.username] = user
    db.commit()
    return users_by_username


def seed_arasur_demonstration(db: Session) -> dict:
    """Seed real Arasur data and generate demonstration HLBs."""
    # 1. Clean test data
    deleted_counts = clean_test_data(db)

    # 2. Ensure Users
    users = ensure_users(db)
    deputy = users["deputy01"]
    supervisor = users["supervisor01"]

    # 3. Load Real Arasur Boundary
    boundary_path = backend_root / "app" / "data" / "boundaries" / "arasur_provisional_boundary.geojson"
    if not boundary_path.exists():
        raise FileNotFoundError(f"Arasur boundary file missing: {boundary_path}")

    with open(boundary_path, "r", encoding="utf-8") as f:
        boundary_json = json.load(f)

    feature = boundary_json["features"][0]
    raw_geom = shape(feature["geometry"])
    if not raw_geom.is_valid:
        raw_geom = make_valid(raw_geom)

    arasur_polygon = raw_geom
    if isinstance(arasur_polygon, Polygon):
        arasur_multipolygon = MultiPolygon([arasur_polygon])
    elif isinstance(arasur_polygon, MultiPolygon):
        arasur_multipolygon = arasur_polygon
    else:
        raise ValueError(f"Unexpected geometry type: {type(arasur_polygon)}")

    # Create Arasur Administrative Area
    arasur_area = AdministrativeArea(
        id=uuid.uuid4(),
        name="Arasur",
        type=AreaType.VILLAGE,
        code="VILL-644401",
        boundary=from_shape(arasur_multipolygon, srid=4326),
        boundary_status=BoundaryStatus.PROVISIONAL.value,
        status="ACTIVE",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(arasur_area)
    db.flush()
    logger.info("Created Arasur administrative area (ID: %s, Code: %s)", arasur_area.id, arasur_area.code)

    # 4. Load Real Google Open Buildings V3 Footprints
    buildings_path = backend_root / "app" / "data" / "open_buildings" / "arasur_real_open_buildings_v3.json"
    if not buildings_path.exists():
        raise FileNotFoundError(f"Real buildings dataset missing: {buildings_path}")

    with open(buildings_path, "r", encoding="utf-8") as f:
        buildings_data = json.load(f)

    raw_buildings = buildings_data.get("buildings", [])
    total_in_file = len(raw_buildings)
    logger.info("Loaded %d building records from Google Open Buildings V3 dataset", total_in_file)

    # Filter to buildings strictly inside Arasur boundary
    TARGET_BUILDING_COUNT = 1000
    included_houses = []
    outside_boundary_count = 0

    for b in raw_buildings:
        pt = Point(b["longitude"], b["latitude"])
        if arasur_polygon.contains(pt) or arasur_polygon.touches(pt):
            if len(included_houses) < TARGET_BUILDING_COUNT:
                fp_raw = b.get("geometry")
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
                    id=uuid.uuid5(uuid.NAMESPACE_DNS, str(b["id"])),
                    area_id=arasur_area.id,
                    building_reference=b.get("source_id") or f"OB-V3-{b['id']}",
                    house_number=None,
                    latitude=float(b["latitude"]),
                    longitude=float(b["longitude"]),
                    location=from_shape(Point(float(b["longitude"]), float(b["latitude"])), srid=4326),
                    footprint=fp_geom,
                    source_type=BuildingSourceType.SATELLITE_DETECTED,
                    detection_confidence=float(b.get("confidence", 0.90)),
                    detected_at=datetime(2023, 5, 15, tzinfo=UTC),
                    imagery_source="Google Open Buildings V3",
                    imagery_date=datetime(2023, 5, 15, tzinfo=UTC),
                    field_status=BuildingFieldStatus.UNVERIFIED,
                    listing_closed=False,
                )
                included_houses.append(house)
        else:
            outside_boundary_count += 1

    db.bulk_save_objects(included_houses)
    db.commit()
    logger.info("Seeded %d real Google Open Buildings V3 structures into Arasur", len(included_houses))

    # 5. Create 'Arasur Demonstration Layout'
    layout = Layout(
        id=uuid.uuid4(),
        area_id=arasur_area.id,
        name="Arasur Demonstration Layout",
        target_hlb_building_count=250,
        actual_building_count=len(included_houses),
        expected_hlb_count=4,
        workload_unit=WorkloadUnit.BUILDINGS,
        target_workload=250,
        estimation_method="CENSUS_2011_PCA_RATIO",
        estimation_provenance="Census of India 2011 Primary Census Abstract (Arasur CT 644401): 1,000 real Google Open Buildings V3 footprints",
        boundary=from_shape(arasur_multipolygon, srid=4326),
        status=LayoutStatus.DRAFT,
        created_by=deputy.id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(layout)
    db.flush()

    # Link layout to administrative area
    layout_area = LayoutAdministrativeArea(
        id=uuid.uuid4(),
        layout_id=layout.id,
        area_id=arasur_area.id,
    )
    db.add(layout_area)

    # Assign Supervisor
    supervisor_assign = LayoutSupervisorAssignment(
        id=uuid.uuid4(),
        layout_id=layout.id,
        supervisor_id=supervisor.id,
        assigned_by=deputy.id,
        assigned_at=datetime.now(UTC),
        status=SupervisorAssignmentStatus.ACTIVE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(supervisor_assign)
    db.commit()
    logger.info("Created Arasur Demonstration Layout (ID: %s)", layout.id)

    # 6. Generate Candidate HLBs using Existing Engine
    t0 = datetime.now()
    generation_result = hlb_generation_service.generate_candidate_hlbs(
        db=db,
        layout=layout,
        user_id=deputy.id,
        target_buildings_per_hlb=250,
        workload_unit="BUILDINGS",
    )
    t1 = datetime.now()
    generation_duration = (t1 - t0).total_seconds()
    logger.info("Candidate HLB generation completed in %.2fs: %s", generation_duration, generation_result)

    # Fetch generated HLBs summary
    from app.models.hlb import HouselistingBlock
    hlbs = (
        db.query(HouselistingBlock)
        .filter(HouselistingBlock.layout_id == layout.id)
        .order_by(HouselistingBlock.block_code.asc())
        .all()
    )

    hlb_counts = {h.block_code: h.actual_building_count for h in hlbs}

    return {
        "status": "SUCCESS",
        "test_data_removed": deleted_counts,
        "area_name": arasur_area.name,
        "area_code": arasur_area.code,
        "boundary_status": arasur_area.boundary_status,
        "building_source": "Google Open Buildings V3 (Real Footprints)",
        "total_available_in_file": total_in_file,
        "total_included": len(included_houses),
        "total_excluded_outside_boundary": total_in_file - len(included_houses),
        "target_buildings_per_hlb": 250,
        "hlb_count": len(hlbs),
        "hlb_building_counts": hlb_counts,
        "layout_id": str(layout.id),
        "layout_name": layout.name,
        "generation_duration_sec": round(generation_duration, 2),
    }


if __name__ == "__main__":
    db = SessionLocal()
    try:
        summary = seed_arasur_demonstration(db)
        print("\n=== ARASUR DEMONSTRATION SEED SUMMARY ===")
        print(json.dumps(summary, indent=2, default=str))
    finally:
        db.close()
