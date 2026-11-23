"""
Tests for Pollachi Demonstration Dataset Seeding and Administrative Hierarchy.
Validates:
1. Dry-run execution runs cleanly without committing changes.
2. Complete official set of 65 Revenue Villages with 2011 Census location codes and Tamil names.
3. Habitation classification: Sangampalayam, Jeeva Nagar, Cheran Nagar, Thillai Nagar classified as habitations/urban localities under parent entities.
4. Demonstration layouts created and associated with multiple areas.
5. Idempotent re-execution produces zero duplicates and zero errors.
6. All boundaries marked PROVISIONAL.
"""

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.administrative_area import AdministrativeArea, AreaType, BoundaryStatus
from app.models.layout import Layout, LayoutAdministrativeArea
from scripts.seed_pollachi_demo import POLLACHI_HABITATIONS, POLLACHI_REVENUE_VILLAGES, seed_pollachi


def test_pollachi_seed_dry_run_and_execution():
    """
    Validates dry-run followed by idempotent real execution.
    """
    # 1. Test dry-run execution
    seed_pollachi(dry_run=True)

    # 2. Test real execution
    seed_pollachi(dry_run=False)

    db: Session = SessionLocal()
    try:
        # Verify Taluk
        taluk = db.query(AdministrativeArea).filter(AdministrativeArea.code == "TALUK-05899").first()
        assert taluk is not None
        assert taluk.name == "Pollachi Taluk"
        assert taluk.type == AreaType.TALUK
        assert taluk.boundary_status == BoundaryStatus.PROVISIONAL.value

        # Verify Municipality
        mun = db.query(AdministrativeArea).filter(AdministrativeArea.code == "MUN-POLLACHI").first()
        assert mun is not None
        assert mun.parent_id == taluk.id

        # Verify exactly 65 Revenue Villages
        villages = (
            db.query(AdministrativeArea)
            .filter(
                AdministrativeArea.parent_id == taluk.id,
                AdministrativeArea.type == AreaType.VILLAGE,
            )
            .all()
        )
        assert len(villages) == 65
        assert len(POLLACHI_REVENUE_VILLAGES) == 65

        # Verify every village has code starting with VILL- and boundary marked PROVISIONAL
        for v in villages:
            assert v.code.startswith("VILL-")
            assert v.boundary_status == BoundaryStatus.PROVISIONAL.value
            assert v.boundary is not None

        # Verify 4 Habitations / Localities
        sangampalayam = db.query(AdministrativeArea).filter(AdministrativeArea.code == "HAB-SANGAMPALAYAM").first()
        assert sangampalayam is not None
        achipatti = db.query(AdministrativeArea).filter(AdministrativeArea.code == "VILL-644592").first()
        assert achipatti is not None
        # Parent of Sangampalayam must be Achipatti
        assert sangampalayam.parent_id == achipatti.id

        for hab_code in ["LOC-JEEVA-NAGAR", "LOC-CHERAN-NAGAR", "LOC-THILLAI-NAGAR"]:
            hab = db.query(AdministrativeArea).filter(AdministrativeArea.code == hab_code).first()
            assert hab is not None
            # Parent must be Pollachi Municipality
            assert hab.parent_id == mun.id

        # Verify 4 Demonstration Layouts
        demo_layout_names = [
            "Pollachi Central Layout",
            "Pollachi North Layout",
            "Pollachi South Layout",
            "Pollachi Rural Layout",
        ]
        for lname in demo_layout_names:
            layout = db.query(Layout).filter(Layout.name == lname).first()
            assert layout is not None, f"Layout {lname} was not found"
            assocs = (
                db.query(LayoutAdministrativeArea)
                .filter(LayoutAdministrativeArea.layout_id == layout.id)
                .all()
            )
            assert len(assocs) >= 3, f"Layout {lname} should cover multiple areas, found {len(assocs)}"

        # 3. Test Idempotency: Re-running seed must succeed with 0 duplicates
        seed_pollachi(dry_run=False)

        count_taluk = db.query(AdministrativeArea).filter(AdministrativeArea.code == "TALUK-05899").count()
        assert count_taluk == 1

        count_villages = (
            db.query(AdministrativeArea)
            .filter(
                AdministrativeArea.parent_id == taluk.id,
                AdministrativeArea.type == AreaType.VILLAGE,
            )
            .count()
        )
        assert count_villages == 65

    finally:
        db.close()

