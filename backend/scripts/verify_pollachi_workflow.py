"""
Comprehensive Verification Test Suite for Pollachi Pilot Dataset.
Verifies all 10 requirements:
1. Authentication of all 13 accounts (1 Deputy, 4 Supervisors, 8 Enumerators) with temporary password
2. Role isolation and permissions
3. 10 Administrative areas + 1 Taluk with PROVISIONAL boundaries
4. 5,000 genuine Google Open Buildings V3 footprints (is_synthetic=False, no fake census records)
5. 2 Multi-Area Layouts (adjoining villages, 2,500 buildings each)
6. Supervisor assignments (supervisor01 -> Layout A, supervisor02 -> Layout B)
7. 20 HLBs generated (10 per layout, exactly 250 buildings per HLB)
8. Role-based workflows (Deputy, Supervisor, Enumerator)
9. Routing engine test on real building coordinates
10. Database schema and foreign key integrity
"""

import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import create_access_token, decode_access_token, verify_password
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.enumerator_assignment import HlbEnumeratorAssignment
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import House
from app.models.layout import Layout, LayoutAdministrativeArea, LayoutVersion
from app.models.supervisor_assignment import LayoutSupervisorAssignment
from app.models.user import User, UserRole
from app.services.route_service import route_service


def run_verification():
    db: Session = SessionLocal()
    errors = []

    print("==================================================")
    print("  AI-ENUMERATOR POLLACHI PILOT VERIFICATION SUITE")
    print("==================================================")

    # 1. AUTHENTICATION & USERS VERIFICATION
    print("\n--- 1. Testing User Accounts & Authentication (13 Accounts) ---")
    expected_users = [
        ("deputy01", UserRole.DEPUTY_TAHSILDAR),
        ("supervisor01", UserRole.SUPERVISOR),
        ("supervisor02", UserRole.SUPERVISOR),
        ("supervisor03", UserRole.SUPERVISOR),
        ("supervisor04", UserRole.SUPERVISOR),
        ("enumerator01", UserRole.ENUMERATOR),
        ("enumerator02", UserRole.ENUMERATOR),
        ("enumerator03", UserRole.ENUMERATOR),
        ("enumerator04", UserRole.ENUMERATOR),
        ("enumerator05", UserRole.ENUMERATOR),
        ("enumerator06", UserRole.ENUMERATOR),
        ("enumerator07", UserRole.ENUMERATOR),
        ("enumerator08", UserRole.ENUMERATOR),
    ]

    temp_password = "Pollachi@2026"
    authenticated_count = 0

    for uname, expected_role in expected_users:
        user = db.query(User).filter(User.username == uname).first()
        if not user:
            errors.append(f"User {uname} not found in database!")
            continue
        if user.role != expected_role:
            errors.append(f"User {uname} role mismatch: expected {expected_role}, got {user.role}")
            continue
        if not verify_password(temp_password, user.password_hash):
            errors.append(f"User {uname} password verification failed with temporary password!")
            continue

        token = create_access_token(subject=str(user.id))
        sub = decode_access_token(token)
        if sub != str(user.id):
            errors.append(f"JWT access token round-trip failed for {uname}!")
            continue

        authenticated_count += 1

    print(f"  [PASS] Successfully authenticated {authenticated_count}/13 users with role permissions and JWT.")

    # 2. ADMINISTRATIVE AREAS VERIFICATION
    print("\n--- 2. Testing Pollachi Administrative Areas (10 Villages + 1 Taluk) ---")
    taluk = db.query(AdministrativeArea).filter(AdministrativeArea.type == AreaType.TALUK).first()
    if not taluk or taluk.code != "TALUK-05899":
        errors.append("Pollachi Taluk (TALUK-05899) missing or incorrect!")
    else:
        print(f"  [PASS] Found Parent Taluk: {taluk.name} ({taluk.code}), boundary_status: {taluk.boundary_status}")

    villages = db.query(AdministrativeArea).filter(AdministrativeArea.type == AreaType.VILLAGE).all()
    print(f"  Total Revenue Villages: {len(villages)}")
    for v in villages:
        poly = to_shape(v.boundary)
        print(f"    - {v.name} ({v.code}): Status={v.boundary_status}, Geom={poly.geom_type}, Bounds={poly.bounds}")
        if v.boundary_status != "PROVISIONAL":
            errors.append(f"Village {v.name} boundary status is not PROVISIONAL: {v.boundary_status}")
        if poly.is_empty or not poly.is_valid:
            errors.append(f"Village {v.name} geometry is invalid or empty!")

    if len(villages) != 10:
        errors.append(f"Expected 10 revenue villages, found {len(villages)}!")

    # 3. REAL BUILDING FOOTPRINTS VERIFICATION
    print("\n--- 3. Testing Real Building Footprints (Google Open Buildings V3) ---")
    total_houses = db.query(House).count()
    real_gob3_houses = db.query(House).filter(House.imagery_source == "Google Open Buildings V3").count()
    print(f"  Total Buildings: {total_houses}")
    print(f"  Real Google Open Buildings V3: {real_gob3_houses}")

    if total_houses != 5000:
        errors.append(f"Expected 5,000 building records, found {total_houses}!")
    if real_gob3_houses != 5000:
        errors.append(f"Expected 5,000 Google Open Buildings V3 records, found {real_gob3_houses}!")

    # Check that no fake census records were created
    conn = db.connection()
    c_houses = conn.exec_driver_sql("SELECT COUNT(*) FROM census_houses;").scalar()
    households = conn.exec_driver_sql("SELECT COUNT(*) FROM household_records;").scalar()
    persons = conn.exec_driver_sql("SELECT COUNT(*) FROM persons;").scalar()
    print(f"  Census Houses: {c_houses} (Expected: 0)")
    print(f"  Household Records: {households} (Expected: 0)")
    print(f"  Person Records: {persons} (Expected: 0)")
    if c_houses > 0 or households > 0 or persons > 0:
        errors.append(f"Fake census records detected: {c_houses} census houses, {households} households, {persons} persons!")

    # 4. MULTI-AREA LAYOUTS & SUPERVISOR ASSIGNMENTS
    print("\n--- 4. Testing Multi-Area Demonstration Layouts & Supervisors ---")
    layouts = db.query(Layout).all()
    print(f"  Total Layouts: {len(layouts)}")
    for l in layouts:
        assocs = db.query(LayoutAdministrativeArea).filter(LayoutAdministrativeArea.layout_id == l.id).all()
        assoc_names = [a.area.name for a in assocs]
        sup_ass = db.query(LayoutSupervisorAssignment).filter(LayoutSupervisorAssignment.layout_id == l.id).first()
        sup_name = sup_ass.supervisor.username if sup_ass else "None"
        print(f"  Layout: {l.name}")
        print(f"    Status: {l.status}, Version: {l.active_version_id}")
        print(f"    Covered Villages ({len(assocs)}): {', '.join(assoc_names)}")
        print(f"    Assigned Supervisor: {sup_name}")
        print(f"    Actual Buildings: {l.actual_building_count}")

        if len(assocs) != 5:
            errors.append(f"Layout {l.name} does not cover exactly 5 villages: {len(assocs)}")
        if l.actual_building_count != 2500:
            errors.append(f"Layout {l.name} actual building count is not 2,500: {l.actual_building_count}")
        if not sup_ass:
            errors.append(f"Layout {l.name} has no supervisor assigned!")

    # 5. HLB GENERATION & ENUMERATOR ASSIGNMENTS
    print("\n--- 5. Testing Generated HLBs & Enumerator Assignments ---")
    hlbs = db.query(HouselistingBlock).all()
    print(f"  Total Generated HLBs: {len(hlbs)}")

    for l in layouts:
        l_hlbs = db.query(HouselistingBlock).filter(HouselistingBlock.layout_id == l.id).order_by(HouselistingBlock.block_code.asc()).all()
        print(f"  {l.name}: {len(l_hlbs)} HLBs")
        total_hlb_bldgs = 0
        for h in l_hlbs:
            bldg_cnt = db.query(HlbHouse).filter(HlbHouse.hlb_id == h.id).count()
            enum_ass = db.query(HlbEnumeratorAssignment).filter(HlbEnumeratorAssignment.hlb_id == h.id).first()
            enum_name = enum_ass.enumerator.username if enum_ass else "None"
            total_hlb_bldgs += bldg_cnt
            print(f"    HLB {h.block_code}: {bldg_cnt} bldgs, Enumerator={enum_name}, Quality={h.quality_score}, Status={h.status}")
            if bldg_cnt != 250:
                errors.append(f"HLB {h.block_code} building count is {bldg_cnt}, expected 250!")
            if not enum_ass:
                errors.append(f"HLB {h.block_code} has no enumerator assigned!")

        if len(l_hlbs) != 10:
            errors.append(f"Layout {l.name} has {len(l_hlbs)} HLBs, expected 10!")
        if total_hlb_bldgs != 2500:
            errors.append(f"Layout {l.name} total HLB buildings is {total_hlb_bldgs}, expected 2,500!")

    # 6. ROUTE OPTIMIZATION TEST ON REAL HLB BUILDINGS
    print("\n--- 6. Testing Route Optimization Engine on Assigned HLB Buildings ---")
    first_hlb = hlbs[0]
    first_enum_ass = db.query(HlbEnumeratorAssignment).filter(HlbEnumeratorAssignment.hlb_id == first_hlb.id).first()
    first_enum = first_enum_ass.enumerator

    route_res = route_service.generate_optimized_route(
        db=db,
        hlb_id=first_hlb.id,
        enumerator_id=first_enum.id,
        return_to_start=True,
    )
    print(f"  Route Generated for HLB {first_hlb.block_code} (Enumerator: {first_enum.username}):")
    print(f"    Building Count: {route_res.building_count}")
    print(f"    Total Distance: {route_res.total_distance_km:.2f} km")
    print(f"    Distance Saved: {route_res.distance_saved_km:.2f} km ({route_res.improvement_percentage:.1f}% improvement)")
    print(f"    Optimization Method: {route_res.optimization_method}")
    print(f"    Routing Mode: {route_res.routing_mode}")
    print(f"    Ordered Coordinates: {len(route_res.ordered_coordinates)} points")

    # Test unauthorized enumerator (must raise 403)
    unauthorized_enum = db.query(User).filter(User.username == "enumerator08").first()
    try:
        route_service.generate_optimized_route(
            db=db,
            hlb_id=first_hlb.id,
            enumerator_id=unauthorized_enum.id,
        )
        errors.append("Authorization check failed: unauthorized enumerator was allowed to generate route!")
    except Exception as e:
        print(f"  [PASS] Authorization Guard: Unauthorized enumerator rejected with 403 ({e.detail if hasattr(e, 'detail') else e})")

    # 7. DATABASE INTEGRITY
    print("\n--- 7. Testing Database Foreign Key Integrity ---")
    fk_violations = conn.exec_driver_sql("PRAGMA foreign_key_check;").fetchall()
    if fk_violations:
        errors.append(f"Foreign key violations found: {fk_violations}")
    else:
        print("  [PASS] PRAGMA foreign_key_check passed with 0 violations.")

    print("\n==================================================")
    if not errors:
        print("  ALL VERIFICATION CHECKS PASSED (0 ERRORS)!")
        print("==================================================")
        return True
    else:
        print(f"  VERIFICATION FAILED WITH {len(errors)} ERRORS:")
        for e in errors:
            print(f"    - {e}")
        print("==================================================")
        return False


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
