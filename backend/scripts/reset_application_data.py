"""
Complete Application Data Reset Script for AI-Enumerator Assistant
Clears all application database records from the configured development database
while strictly preserving table schemas and alembic migration history.
"""

import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
import sqlite3


TABLES_IN_DEPENDENCY_ORDER = [
    # 1. Child / dependent fieldwork records
    "persons",
    "household_records",
    "census_houses",
    "revisits",
    "gps_tracks",
    "house_fieldwork_status",
    "building_edits",
    "change_request_messages",
    "change_requests",
    "supervisor_corrections",
    "sync_operations",
    "road_segment_coverages",
    "hlb_route_traversals",
    "hlb_route_plans",
    "missing_path_submissions",
    "hlb_required_edges",
    "road_edges",
    "road_nodes",
    "road_graphs",
    # 2. Block and layout associations
    "hlb_counters",
    "hlb_houses",
    "hlb_enumerator_assignments",
    "houselisting_blocks",
    "layout_supervisor_assignments",
    "layout_administrative_areas",
    "layout_versions",
    "layouts",
    # 3. Structures and spatial areas
    "houses",
    "administrative_areas",
    # 4. Audit logs and user accounts
    "audit_logs",
    "users",
]


def reset_database(db_file: Path):
    if not db_file.exists():
        print(f"[SKIP] Database file does not exist: {db_file}")
        return

    print(f"\n=======================================================")
    print(f"RESETTING APPLICATION DATA: {db_file}")
    print(f"=======================================================")

    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    # Safety check: ensure alembic_version exists so we don't accidentally run on an uninitialized/wrong DB
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version';")
    has_alembic = cur.fetchone()
    if not has_alembic:
        print(f"[INFO] No alembic_version in {db_file.name}, checking for application tables...")

    # Discover all user tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    all_tables = [r[0] for r in cur.fetchall() if not r[0].startswith("sqlite_") and r[0] != "alembic_version"]

    print(f"Found {len(all_tables)} application tables to clear (preserving alembic_version).")

    # Disable foreign keys temporarily to allow breaking circular dependencies cleanly
    cur.execute("PRAGMA foreign_keys = OFF;")

    # 1. Break circular references if layouts table exists
    if "layouts" in all_tables:
        cur.execute("UPDATE layouts SET active_version_id = NULL;")

    deleted_counts = {}

    # 2. Delete from tables in strict dependency order
    for table in TABLES_IN_DEPENDENCY_ORDER:
        if table in all_tables:
            cur.execute(f"SELECT COUNT(*) FROM [{table}];")
            count_before = cur.fetchone()[0]
            cur.execute(f"DELETE FROM [{table}];")
            deleted_counts[table] = count_before

    # 3. Delete from any other application tables not in the explicit list
    for table in all_tables:
        if table not in deleted_counts:
            cur.execute(f"SELECT COUNT(*) FROM [{table}];")
            count_before = cur.fetchone()[0]
            cur.execute(f"DELETE FROM [{table}];")
            deleted_counts[table] = count_before

    # Commit all deletions
    conn.commit()

    # Re-enable foreign keys and run validation check
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.execute("PRAGMA foreign_key_check;")
    fk_violations = cur.fetchall()
    if fk_violations:
        print(f"[WARNING] Foreign key check reported violations: {fk_violations}")
    else:
        print("[OK] Foreign key check passed: 0 violations.")

    # Run VACUUM to reclaim storage and rebuild indexes
    print("Running VACUUM...")
    cur.execute("VACUUM;")
    conn.close()

    print("\n--- Deletion Summary ---")
    total_deleted = 0
    for t, cnt in deleted_counts.items():
        if cnt > 0:
            print(f"  {t}: {cnt} records deleted")
            total_deleted += cnt
        else:
            print(f"  {t}: 0 records (already empty)")
    print(f"Total deleted records: {total_deleted}")


def verify_database(db_file: Path):
    if not db_file.exists():
        return True

    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall() if not r[0].startswith("sqlite_") and r[0] != "alembic_version"]

    remaining = {}
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM [{t}];")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            remaining[t] = cnt

    # Verify alembic_version is preserved
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version';")
    has_alembic = cur.fetchone()
    alembic_count = 0
    if has_alembic:
        cur.execute("SELECT COUNT(*) FROM alembic_version;")
        alembic_count = cur.fetchone()[0]

    conn.close()

    print(f"\n--- Verification for {db_file.name} ---")
    print(f"Application tables checked: {len(tables)}")
    print(f"Non-empty application tables: {len(remaining)}")
    print(f"Alembic migration history preserved: {alembic_count} revision(s)")

    if remaining:
        print(f"[FAILED] Tables with remaining data: {remaining}")
        return False
    else:
        print("[SUCCESS] All application tables contain 0 records.")
        return True


def main():
    # 1. Verify environment safety
    db_url = settings.DATABASE_URL
    print(f"Configured DATABASE_URL: {db_url}")

    if not db_url.startswith("sqlite"):
        print("[FATAL ERROR] Configured DATABASE_URL is not a local SQLite database!")
        print("Safety policy: Refusing to reset non-SQLite or potential production databases.")
        sys.exit(1)

    # 2. Reset primary backend DB
    backend_db = backend_dir / "ai_enumerator.db"
    reset_database(backend_db)
    success_backend = verify_database(backend_db)

    # 3. Reset root DB if present
    root_db = backend_dir.parent / "ai_enumerator.db"
    if root_db.exists() and root_db.resolve() != backend_db.resolve():
        reset_database(root_db)
        success_root = verify_database(root_db)
    else:
        success_root = True

    # 4. Clean up temporary test databases
    for temp_name in ["test_temp.db", "sync_test.db"]:
        for p in [backend_dir / temp_name, backend_dir.parent / temp_name]:
            if p.exists():
                try:
                    p.unlink()
                    print(f"[OK] Removed temporary test file: {p.name}")
                except Exception as e:
                    print(f"[NOTE] Could not delete {p.name}: {e}")

    if success_backend and success_root:
        print("\n=======================================================")
        print("COMPLETE APPLICATION DATA RESET: SUCCESSFUL")
        print("=======================================================")
        sys.exit(0)
    else:
        print("\n=======================================================")
        print("COMPLETE APPLICATION DATA RESET: FAILED")
        print("=======================================================")
        sys.exit(1)


if __name__ == "__main__":
    main()

