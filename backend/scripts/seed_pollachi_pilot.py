"""
Seed script for Pollachi Pilot Dataset.
Populates official Pollachi Taluk (05899) pilot environment:
- 13 Application Users (1 Deputy Tahsildar, 4 Supervisors, 8 Enumerators)
  with secure bcrypt password hashing (temporary password: Pollachi@2026)
- 1 Taluk: Pollachi Taluk (Census code: 05899, LGD: 5899)
- 10 Official Revenue Villages with verified Census 2011 & LGD codes
- Provisional non-rectangular territorial boundary polygons (boundary_status: PROVISIONAL)
- 5,000 Genuine Google Open Buildings V3 footprints (500 per village, is_synthetic=False)
- 2 Multi-Area Demonstration Layouts (Layout A: 5 North villages; Layout B: 5 South villages)
- Supervisor Assignments (supervisor01 -> Layout A, supervisor02 -> Layout B)
- AI HLB Generation & Approval (target 250 buildings per HLB)
- Enumerator Assignments (enumerators 01-04 -> Layout A HLBs, enumerators 05-08 -> Layout B HLBs)

Supports:
  --dry-run: Non-destructive execution without committing to database
"""

import argparse
import json
import logging
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure backend root is in python path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import MultiPolygon, Point, Polygon, shape
from shapely.ops import unary_union
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.gis.hlb.editing_service import hlb_editing_service
from app.gis.hlb.generator_service import hlb_generation_service
from app.models.administrative_area import AdministrativeArea, AreaType, BoundaryStatus
from app.models.enumerator_assignment import (
    EnumeratorAssignmentStatus,
    HlbEnumeratorAssignment,
)
from app.models.hlb import HlbStatus, HouselistingBlock
from app.models.house import BuildingFieldStatus, BuildingSourceType, House
from app.models.layout import (
    Layout,
    LayoutAdministrativeArea,
    LayoutStatus,
    LayoutVersion,
    LayoutVersionStatus,
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

POLLACHI_VILLAGES_SPEC = [
    # Layout A (Pollachi North Corridor)
    {
        "name": "Achipatti",
        "tamil_name": "ஆச்சிபட்டி",
        "census_code": "644592",
        "lgd_code": "644592",
        "firka": "Pollachi North",
        "taluk": "Pollachi",
        "district": "Coimbatore",
        "lat": 10.685,
        "lng": 77.015,
        "layout_group": "A",
    },
    {
        "name": "Anupperpalayam",
        "tamil_name": "அனுப்பர்பாளையம்",
        "census_code": "644535",
        "lgd_code": "644535",
        "firka": "Pollachi North",
        "taluk": "Pollachi",
        "district": "Coimbatore",
        "lat": 10.710,
        "lng": 77.025,
        "layout_group": "A",
    },
    {
        "name": "A. Nagur",
        "tamil_name": "ஏ. நாகூர்",
        "census_code": "644537",
        "lgd_code": "644537",
        "firka": "Pollachi North",
        "taluk": "Pollachi",
        "district": "Coimbatore",
        "lat": 10.720,
        "lng": 77.035,
        "layout_group": "A",
    },
    {
        "name": "Kittasoorampalayam",
        "tamil_name": "கிட்டசூரம்பாளையம்",
        "census_code": "644534",
        "lgd_code": "644534",
        "firka": "Pollachi North",
        "taluk": "Pollachi",
        "district": "Coimbatore",
        "lat": 10.712,
        "lng": 77.018,
        "layout_group": "A",
    },
    {
        "name": "Bodipalayam",
        "tamil_name": "போடிபாளையம்",
        "census_code": "644549",
        "lgd_code": "644549",
        "firka": "Pollachi North",
        "taluk": "Pollachi",
        "district": "Coimbatore",
        "lat": 10.735,
        "lng": 77.045,
        "layout_group": "A",
    },
    # Layout B (Pollachi South Corridor)
    {
        "name": "Chinnampalayam",
        "tamil_name": "சின்னம்பாளையம்",
        "census_code": "644501",
        "lgd_code": "644501",
        "firka": "Pollachi South",
        "taluk": "Pollachi",
        "district": "Coimbatore",
        "lat": 10.645,
        "lng": 77.002,
        "layout_group": "B",
    },
    {
        "name": "Unjavelampatti",
        "tamil_name": "ஊஞ்சவேலாம்பட்டி",
        "census_code": "644541",
        "lgd_code": "644541",
        "firka": "Pollachi South",
        "taluk": "Pollachi",
        "district": "Coimbatore",
        "lat": 10.642,
        "lng": 77.030,
        "layout_group": "B",
    },
    {
        "name": "Zamin Muthur",
        "tamil_name": "ஜமீன் முத்தூர்",
        "census_code": "644542",
        "lgd_code": "644542",
        "firka": "Pollachi South",
        "taluk": "Pollachi",
        "district": "Coimbatore",
        "lat": 10.648,
        "lng": 77.035,
        "layout_group": "B",
    },
    {
        "name": "Kolarpatti",
        "tamil_name": "கோலார்பட்டி",
        "census_code": "644556",
        "lgd_code": "644556",
        "firka": "Pollachi South",
        "taluk": "Pollachi",
        "district": "Coimbatore",
        "lat": 10.620,
        "lng": 77.060,
        "layout_group": "B",
    },
    {
        "name": "Gomangalam",
        "tamil_name": "கோமங்கலம்",
        "census_code": "644554",
        "lgd_code": "644554",
        "firka": "Pollachi South",
        "taluk": "Pollachi",
        "district": "Coimbatore",
        "lat": 10.615,
        "lng": 77.065,
        "layout_group": "B",
    },
]


def load_boundary_geojson(filename: str) -> MultiPolygon:
    path = backend_root / "app" / "data" / "boundaries" / filename
    if not path.exists():
        raise FileNotFoundError(f"Boundary file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("type") == "FeatureCollection":
        geom_data = data["features"][0]["geometry"]
    elif data.get("type") == "Feature":
        geom_data = data["geometry"]
    else:
        geom_data = data
    parsed = shape(geom_data)
    if isinstance(parsed, Polygon):
        return MultiPolygon([parsed])
    elif isinstance(parsed, MultiPolygon):
        return parsed
    raise ValueError(f"Unexpected geometry type: {type(parsed)}")


def seed_pollachi_pilot(dry_run: bool = False, generate_hlbs: bool = True) -> dict[str, Any]:
    db: Session = SessionLocal()
    summary: dict[str, Any] = {
        "users_created": 0,
        "users_existing": 0,
        "areas_created": 0,
        "areas_existing": 0,
        "buildings_imported": 0,
        "buildings_existing": 0,
        "layouts_created": 0,
        "layouts_existing": 0,
        "hlbs_generated": 0,
        "supervisor_assignments": 0,
        "enumerator_assignments": 0,
    }

    try:
        logger.info(f"=== Starting Pollachi Pilot Seeding (dry_run={dry_run}) ===")

        # -------------------------------------------------------------
        # 1. USER ACCOUNTS (13 Total: 1 Deputy, 4 Supervisors, 8 Enumerators)
        # -------------------------------------------------------------
        logger.info("Step 1: Provisioning 13 User Accounts...")
        user_map: dict[str, User] = {}
        password_hash = get_password_hash(TEMP_DEV_PASSWORD)

        for u_spec in USERS_SPEC:
            uname = u_spec["username"]
            existing_user = db.query(User).filter(User.username == uname).first()
            if not existing_user:
                new_user = User(
                    id=uuid.uuid4(),
                    name=u_spec["name"],
                    username=uname,
                    password_hash=password_hash,
                    role=u_spec["role"],
                    status=UserStatus.ACTIVE,
                    phone=f"919876{summary['users_created'] + summary['users_existing']:04d}",
                )
                if not dry_run:
                    db.add(new_user)
                    db.flush()
                user_map[uname] = new_user
                summary["users_created"] += 1
                logger.info(f"  + Created User: {uname} ({u_spec['role']})")
            else:
                # Update password hash if needed
                existing_user.password_hash = password_hash
                existing_user.role = u_spec["role"]
                existing_user.status = UserStatus.ACTIVE
                user_map[uname] = existing_user
                summary["users_existing"] += 1
                logger.info(f"  ~ Existing User: {uname} ({u_spec['role']})")

        # -------------------------------------------------------------
        # 2. ADMINISTRATIVE AREAS (Pollachi Taluk + 10 Revenue Villages)
        # -------------------------------------------------------------
        logger.info("Step 2: Provisioning Administrative Areas...")
        taluk_code = "TALUK-05899"
        taluk = db.query(AdministrativeArea).filter(AdministrativeArea.code == taluk_code).first()
        taluk_poly = load_boundary_geojson("pollachi_taluk.geojson")

        if not taluk:
            taluk = AdministrativeArea(
                id=uuid.uuid4(),
                name="Pollachi Taluk",
                type=AreaType.TALUK,
                code=taluk_code,
                parent_id=None,
                boundary=from_shape(taluk_poly, srid=4326),
                boundary_status=BoundaryStatus.PROVISIONAL.value,
                status="ACTIVE",
            )
            if not dry_run:
                db.add(taluk)
                db.flush()
            summary["areas_created"] += 1
            logger.info("  + Created Administrative Area: Pollachi Taluk (TALUK-05899)")
        else:
            summary["areas_existing"] += 1
            logger.info("  ~ Existing Administrative Area: Pollachi Taluk (TALUK-05899)")

        village_map: dict[str, AdministrativeArea] = {}
        for v_spec in POLLACHI_VILLAGES_SPEC:
            v_code = f"VILL-{v_spec['census_code']}"
            existing_v = db.query(AdministrativeArea).filter(AdministrativeArea.code == v_code).first()
            v_poly = load_boundary_geojson(f"vill_{v_spec['census_code']}_provisional_boundary.geojson")

            if not existing_v:
                new_v = AdministrativeArea(
                    id=uuid.uuid4(),
                    name=v_spec["name"],
                    type=AreaType.VILLAGE,
                    code=v_code,
                    parent_id=taluk.id,
                    boundary=from_shape(v_poly, srid=4326),
                    boundary_status=BoundaryStatus.PROVISIONAL.value,
                    status="ACTIVE",
                )
                if not dry_run:
                    db.add(new_v)
                    db.flush()
                village_map[v_spec["census_code"]] = new_v
                summary["areas_created"] += 1
                logger.info(f"  + Created Village: {v_spec['name']} ({v_code})")
            else:
                existing_v.boundary = from_shape(v_poly, srid=4326)
                existing_v.boundary_status = BoundaryStatus.PROVISIONAL.value
                existing_v.parent_id = taluk.id
                village_map[v_spec["census_code"]] = existing_v
                summary["areas_existing"] += 1
                logger.info(f"  ~ Existing Village: {v_spec['name']} ({v_code})")

        # -------------------------------------------------------------
        # 3. REAL BUILDING FOOTPRINTS (Google Open Buildings V3)
        # -------------------------------------------------------------
        logger.info("Step 3: Ingesting Real Building Footprints (Google Open Buildings V3)...")
        bldgs_file = backend_root / "app" / "data" / "open_buildings" / "pollachi_real_open_buildings_v3.json"
        if not bldgs_file.exists():
            raise FileNotFoundError(f"Open Buildings file missing: {bldgs_file}. Run extract_pollachi_buildings.py first.")

        with open(bldgs_file, "r", encoding="utf-8") as f:
            bldgs_data = json.load(f)

        raw_buildings = bldgs_data.get("buildings", [])
        logger.info(f"  Loaded {len(raw_buildings)} buildings from {bldgs_file.name}")

        existing_bldg_refs = {
            r[0]
            for r in db.query(House.building_reference).filter(House.building_reference.isnot(None)).all()
        }

        new_houses = []
        for b in raw_buildings:
            ref = b["source_building_id"]
            if ref in existing_bldg_refs:
                summary["buildings_existing"] += 1
                continue

            v_code = b["village_census_code"]
            area = village_map.get(v_code)
            if not area:
                continue

            geom = shape(b["geometry"])
            if isinstance(geom, Polygon):
                mp_geom = MultiPolygon([geom])
            elif isinstance(geom, MultiPolygon):
                mp_geom = geom
            else:
                continue

            h = House(
                id=uuid.uuid4(),
                area_id=area.id,
                building_reference=ref,
                house_number=ref,
                latitude=b["latitude"],
                longitude=b["longitude"],
                location=from_shape(Point(b["longitude"], b["latitude"]), srid=4326),
                footprint=from_shape(mp_geom, srid=4326),
                detection_confidence=b.get("confidence", 0.75),
                detected_at=datetime.now(UTC),
                imagery_source="Google Open Buildings V3",
                source_type=BuildingSourceType.SATELLITE_DETECTED,
                field_status=BuildingFieldStatus.UNVERIFIED,
                listing_closed=False,
            )
            new_houses.append(h)
            existing_bldg_refs.add(ref)

        if not dry_run and new_houses:
            db.bulk_save_objects(new_houses)
            db.flush()
        summary["buildings_imported"] = len(new_houses)
        logger.info(f"  Ingested {summary['buildings_imported']} new buildings ({summary['buildings_existing']} existed).")

        # -------------------------------------------------------------
        # 4. MULTI-AREA LAYOUTS (Layout A & Layout B)
        # -------------------------------------------------------------
        logger.info("Step 4: Creating Multi-Area Demonstration Layouts...")
        layouts_spec = [
            {
                "name": "Pollachi Pilot Layout A",
                "village_codes": ["644592", "644535", "644537", "644534", "644549"],
                "supervisor": "supervisor01",
                "enumerators": ["enumerator01", "enumerator02", "enumerator03", "enumerator04"],
            },
            {
                "name": "Pollachi Pilot Layout B",
                "village_codes": ["644501", "644541", "644542", "644556", "644554"],
                "supervisor": "supervisor02",
                "enumerators": ["enumerator05", "enumerator06", "enumerator07", "enumerator08"],
            },
        ]

        deputy_user = user_map.get("deputy01")

        for l_spec in layouts_spec:
            lname = l_spec["name"]
            existing_l = db.query(Layout).filter(Layout.name == lname).first()

            group_areas = [village_map[c] for c in l_spec["village_codes"]]
            primary_area = group_areas[0]

            # Union boundaries
            polys = [to_shape(a.boundary) for a in group_areas]
            u_poly = unary_union(polys)
            if isinstance(u_poly, Polygon):
                mp_layout = MultiPolygon([u_poly])
            elif isinstance(u_poly, MultiPolygon):
                mp_layout = u_poly
            else:
                mp_layout = MultiPolygon([u_poly.buffer(0)])

            # Building count
            area_ids = [a.id for a in group_areas]
            bldg_count = db.query(House).filter(House.area_id.in_(area_ids)).count() if not dry_run else 2500

            if not existing_l:
                layout = Layout(
                    id=uuid.uuid4(),
                    area_id=primary_area.id,
                    name=lname,
                    target_hlb_building_count=250,
                    actual_building_count=bldg_count,
                    expected_hlb_count=max(1, bldg_count // 250),
                    boundary=from_shape(mp_layout, srid=4326),
                    boundary_status=BoundaryStatus.PROVISIONAL.value,
                    status=LayoutStatus.DRAFT,
                    created_by=deputy_user.id if deputy_user else None,
                )
                if not dry_run:
                    db.add(layout)
                    db.flush()

                    # Add associations
                    for a in group_areas:
                        assoc = LayoutAdministrativeArea(
                            id=uuid.uuid4(),
                            layout_id=layout.id,
                            area_id=a.id,
                        )
                        db.add(assoc)
                    db.flush()
                summary["layouts_created"] += 1
                logger.info(f"  + Created Layout: {lname} ({bldg_count} buildings across {len(group_areas)} villages)")
            else:
                layout = existing_l
                layout.actual_building_count = bldg_count
                layout.boundary = from_shape(mp_layout, srid=4326)
                summary["layouts_existing"] += 1
                logger.info(f"  ~ Existing Layout: {lname} ({bldg_count} buildings)")

            # ---------------------------------------------------------
            # 5. SUPERVISOR ASSIGNMENT
            # ---------------------------------------------------------
            sup_username = l_spec["supervisor"]
            sup_user = user_map.get(sup_username)
            if sup_user and not dry_run:
                existing_sup_ass = (
                    db.query(LayoutSupervisorAssignment)
                    .filter(
                        LayoutSupervisorAssignment.layout_id == layout.id,
                        LayoutSupervisorAssignment.supervisor_id == sup_user.id,
                        LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE,
                    )
                    .first()
                )
                if not existing_sup_ass:
                    sup_ass = LayoutSupervisorAssignment(
                        id=uuid.uuid4(),
                        layout_id=layout.id,
                        supervisor_id=sup_user.id,
                        assigned_by=deputy_user.id if deputy_user else None,
                        status=SupervisorAssignmentStatus.ACTIVE,
                    )
                    db.add(sup_ass)
                    summary["supervisor_assignments"] += 1
                    logger.info(f"  + Assigned {sup_username} to {lname}")

            # ---------------------------------------------------------
            # 6. AI HLB GENERATION & ENUMERATOR ASSIGNMENTS
            # ---------------------------------------------------------
            if generate_hlbs and not dry_run:
                logger.info(f"  Running AI HLB generation for {lname} (Target: 250 buildings/HLB)...")
                try:
                    # Reset layout status if was approved to allow clean generation
                    if layout.status == LayoutStatus.APPROVED:
                        layout.status = LayoutStatus.DRAFT

                    hlb_gen_res = hlb_generation_service.generate_candidate_hlbs(
                        db=db,
                        layout=layout,
                        user_id=deputy_user.id if deputy_user else None,
                        target_buildings_per_hlb=250,
                    )
                    num_hlbs = hlb_gen_res.get("hlb_count", 0)
                    summary["hlbs_generated"] += num_hlbs
                    logger.info(f"  Generated {num_hlbs} HLBs for {lname} (Candidate version: {hlb_gen_res.get('version_number')})")

                    # Approve layout
                    appr_res = hlb_editing_service.approve_layout(
                        db=db,
                        layout_id=layout.id,
                        user_id=deputy_user.id if deputy_user else None,
                    )
                    logger.info(f"  Approved {lname} into active approved version (Status: {appr_res.get('status')})")

                    # Assign Enumerators round-robin to the approved HLBs
                    active_hlbs = (
                        db.query(HouselistingBlock)
                        .filter(
                            HouselistingBlock.layout_id == layout.id,
                            HouselistingBlock.version_id == layout.active_version_id,
                        )
                        .order_by(HouselistingBlock.block_code.asc())
                        .all()
                    )

                    enum_users = [user_map[u] for u in l_spec["enumerators"] if u in user_map]
                    for idx, hlb in enumerate(active_hlbs):
                        assigned_enum = enum_users[idx % len(enum_users)]
                        existing_enum_ass = (
                            db.query(HlbEnumeratorAssignment)
                            .filter(
                                HlbEnumeratorAssignment.hlb_id == hlb.id,
                                HlbEnumeratorAssignment.enumerator_id == assigned_enum.id,
                            )
                            .first()
                        )
                        if not existing_enum_ass:
                            enum_ass = HlbEnumeratorAssignment(
                                id=uuid.uuid4(),
                                hlb_id=hlb.id,
                                layout_id=layout.id,
                                enumerator_id=assigned_enum.id,
                                supervisor_id=sup_user.id if sup_user else None,
                                status=EnumeratorAssignmentStatus.ACTIVE,
                            )
                            db.add(enum_ass)
                            summary["enumerator_assignments"] += 1

                    logger.info(f"  Assigned {len(l_spec['enumerators'])} enumerators across {len(active_hlbs)} HLBs for {lname}")

                except Exception as e:
                    logger.warning(f"  HLB generation/approval note for {lname}: {e}", exc_info=True)

        if dry_run:
            logger.info("DRY RUN: Validated successfully. Rolling back database changes.")
            db.rollback()
        else:
            db.commit()
            logger.info("SEED COMMITTED: Successfully seeded Pollachi Pilot environment into database.")

    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Pollachi Pilot Dataset")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without committing database changes")
    parser.add_argument("--skip-hlbs", action="store_true", help="Skip AI HLB generation")
    args = parser.parse_args()

    res = seed_pollachi_pilot(dry_run=args.dry_run, generate_hlbs=not args.skip_hlbs)
    print("\n--- SEED EXECUTION SUMMARY ---")
    for k, v in res.items():
        print(f"  {k}: {v}")
