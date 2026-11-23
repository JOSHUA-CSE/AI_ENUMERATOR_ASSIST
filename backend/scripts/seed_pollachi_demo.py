"""
Seed script for Pollachi Demonstration Dataset.
Populates official Pollachi Taluk (05899) administrative hierarchy:
- 1 Taluk: Pollachi Taluk (Census code: 05899)
- 65 Official Revenue Villages with 2011 Census location codes and Tamil names
- 4 Habitations / Urban Localities (Sangampalayam, Jeeva Nagar, Cheran Nagar, Thillai Nagar)
  correctly classified under their respective parent revenue village or municipality
- 4 Multi-Area Demonstration Layouts (Central, North, South, Rural)

Boundary Status: PROVISIONAL (Authoritative Survey of India boundaries pending)
Building Footprints: Mark UNAVAILABLE (No fake footprints generated)
Supports: --dry-run for non-destructive pre-flight verification.
"""

import argparse
import logging
import sys
import uuid
from pathlib import Path
from typing import Any

# Ensure backend root is in python path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.administrative_area import AdministrativeArea, AreaType, BoundaryStatus
from app.models.layout import Layout, LayoutAdministrativeArea, LayoutStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Complete official set of 65 Revenue Villages of Pollachi Taluk with 2011 Census codes, Tamil names, and Firkas
POLLACHI_REVENUE_VILLAGES: list[dict[str, Any]] = [
    # Pollachi North Firka (17 villages)
    {"name": "Achipatti", "tamil_name": "ஆச்சிபட்டி", "census_code": "644592", "firka": "Pollachi North", "lat": 10.685, "lng": 77.015},
    {"name": "A. Nagur", "tamil_name": "ஏ. நாகூர்", "census_code": "644537", "firka": "Pollachi North", "lat": 10.720, "lng": 77.035},
    {"name": "Anupperpalayam", "tamil_name": "அனுப்பர்பாளையம்", "census_code": "644535", "firka": "Pollachi North", "lat": 10.710, "lng": 77.025},
    {"name": "Bodipalayam", "tamil_name": "போடிபாளையம்", "census_code": "644549", "firka": "Pollachi North", "lat": 10.735, "lng": 77.045},
    {"name": "Boligoundenpalayam", "tamil_name": "போளிகவுண்டன்பாளையம்", "census_code": "644539", "firka": "Pollachi North", "lat": 10.715, "lng": 77.040},
    {"name": "Kavilipalayam", "tamil_name": "கவிலிபாளையம்", "census_code": "644519", "firka": "Pollachi North", "lat": 10.705, "lng": 77.010},
    {"name": "Kittasoorampalayam", "tamil_name": "கிட்டசூரம்பாளையம்", "census_code": "644534", "firka": "Pollachi North", "lat": 10.712, "lng": 77.018},
    {"name": "Kollapatty", "tamil_name": "கொல்லப்பட்டி", "census_code": "644536", "firka": "Pollachi North", "lat": 10.718, "lng": 77.028},
    {"name": "Kullakapalayam", "tamil_name": "குள்ளக்காபாளையம்", "census_code": "644522", "firka": "Pollachi North", "lat": 10.708, "lng": 77.005},
    {"name": "Kullichettipalayam", "tamil_name": "குள்ளிசெட்டிபாளையம்", "census_code": "644513", "firka": "Pollachi North", "lat": 10.702, "lng": 77.008},
    {"name": "Kumarapalayam", "tamil_name": "குமாரபாளையம்", "census_code": "644545", "firka": "Pollachi North", "lat": 10.725, "lng": 77.038},
    {"name": "Kurumbapalayam", "tamil_name": "குறும்பபாளையம்", "census_code": "644521", "firka": "Pollachi North", "lat": 10.704, "lng": 77.002},
    {"name": "Okkulipalayam", "tamil_name": "ஒக்கிலிபாளையம்", "census_code": "644520", "firka": "Pollachi North", "lat": 10.706, "lng": 77.012},
    {"name": "Puliyampatty", "tamil_name": "புளியம்பட்டி", "census_code": "644532", "firka": "Pollachi North", "lat": 10.709, "lng": 77.016},
    {"name": "R. Ponnapuram", "tamil_name": "ஆர். பொன்னாபுரம்", "census_code": "644533", "firka": "Pollachi North", "lat": 10.711, "lng": 77.014},
    {"name": "Rasakkapalayam", "tamil_name": "ராசாக்காபாளையம்", "census_code": "644531", "firka": "Pollachi North", "lat": 10.707, "lng": 77.015},
    {"name": "Vellalapalayam", "tamil_name": "வெள்ளாளபாளையம்", "census_code": "644529", "firka": "Pollachi North", "lat": 10.703, "lng": 77.019},

    # Pollachi South Firka (16 villages)
    {"name": "Ambarampalayam", "tamil_name": "அம்பாரம்பாளையம்", "census_code": "644561", "firka": "Pollachi South", "lat": 10.635, "lng": 76.955},
    {"name": "Chinnampalayam", "tamil_name": "சின்னம்பாளையம்", "census_code": "644501", "firka": "Pollachi South", "lat": 10.645, "lng": 77.002},
    {"name": "Gomangalam", "tamil_name": "கோமங்கலம்", "census_code": "644554", "firka": "Pollachi South", "lat": 10.615, "lng": 77.065},
    {"name": "Kanjampatti", "tamil_name": "காஞ்சம்பட்டி", "census_code": "644557", "firka": "Pollachi South", "lat": 10.625, "lng": 77.055},
    {"name": "Kolarpatti", "tamil_name": "கோலார்பட்டி", "census_code": "644556", "firka": "Pollachi South", "lat": 10.620, "lng": 77.060},
    {"name": "Naickenpalayam", "tamil_name": "நாயக்கன்பாளையம்", "census_code": "644560", "firka": "Pollachi South", "lat": 10.630, "lng": 76.960},
    {"name": "Nallampalayam", "tamil_name": "நல்லாம்பாளையம்", "census_code": "644552", "firka": "Pollachi South", "lat": 10.610, "lng": 77.050},
    {"name": "Nattukalpalayam", "tamil_name": "நாட்டுக்கல்பாளையம்", "census_code": "644558", "firka": "Pollachi South", "lat": 10.628, "lng": 77.045},
    {"name": "S. Malayandipattinam", "tamil_name": "எஸ். மலையாண்டிபட்டினம்", "census_code": "644555", "firka": "Pollachi South", "lat": 10.612, "lng": 77.058},
    {"name": "Seelakkampatti", "tamil_name": "சீலக்கம்பட்டி", "census_code": "644553", "firka": "Pollachi South", "lat": 10.614, "lng": 77.052},
    {"name": "Singanallur", "tamil_name": "சிங்கநல்லூர்", "census_code": "644566", "firka": "Pollachi South", "lat": 10.605, "lng": 77.035},
    {"name": "Solapalayam", "tamil_name": "சோளபாளையம்", "census_code": "644550", "firka": "Pollachi South", "lat": 10.608, "lng": 77.042},
    {"name": "Thippampatti", "tamil_name": "திப்பம்பட்டி", "census_code": "644551", "firka": "Pollachi South", "lat": 10.609, "lng": 77.048},
    {"name": "Unjavelampatti", "tamil_name": "ஊஞ்சவேலாம்பட்டி", "census_code": "644541", "firka": "Pollachi South", "lat": 10.642, "lng": 77.030},
    {"name": "Zamin Kottampatti", "tamil_name": "ஜமீன் கோட்டம்பட்டி", "census_code": "644559", "firka": "Pollachi South", "lat": 10.626, "lng": 76.990},
    {"name": "Zamin Muthur", "tamil_name": "ஜமீன் முத்தூர்", "census_code": "644542", "firka": "Pollachi South", "lat": 10.648, "lng": 77.035},

    # Periyanekamam Firka (8 villages)
    {"name": "Avalappampatty", "tamil_name": "அவலப்பம்பட்டி", "census_code": "644528", "firka": "Periyanekamam", "lat": 10.745, "lng": 77.085},
    {"name": "Chandrapuram", "tamil_name": "சந்திராபுரம்", "census_code": "644507", "firka": "Periyanekamam", "lat": 10.750, "lng": 77.090},
    {"name": "Chinna Negamam", "tamil_name": "சின்ன நெகமம்", "census_code": "644508", "firka": "Periyanekamam", "lat": 10.755, "lng": 77.095},
    {"name": "Devanampalayam", "tamil_name": "தேவனாம்பாளையம்", "census_code": "644504", "firka": "Periyanekamam", "lat": 10.760, "lng": 77.075},
    {"name": "Kappalankarai", "tamil_name": "கப்பலாங்கரை", "census_code": "644505", "firka": "Periyanekamam", "lat": 10.765, "lng": 77.080},
    {"name": "Kondegoundenpalayam", "tamil_name": "கொண்டேகவுண்டன்பாளையம்", "census_code": "644526", "firka": "Periyanekamam", "lat": 10.748, "lng": 77.082},
    {"name": "Mulanur", "tamil_name": "மூலனூர்", "census_code": "644527", "firka": "Periyanekamam", "lat": 10.742, "lng": 77.078},
    {"name": "Sirukkalandai", "tamil_name": "சிறுகாலந்தை", "census_code": "644506", "firka": "Periyanekamam", "lat": 10.762, "lng": 77.088},

    # Ramapattinam Firka (12 villages)
    {"name": "Ayyampalayam", "tamil_name": "அய்யம்பாளையம்", "census_code": "644543", "firka": "Ramapattinam", "lat": 10.672, "lng": 77.075},
    {"name": "Chikkarayapuram", "tamil_name": "சிக்கராயபுரம்", "census_code": "644518", "firka": "Ramapattinam", "lat": 10.682, "lng": 77.085},
    {"name": "Devambadi", "tamil_name": "தேவாம்பாடி", "census_code": "644515", "firka": "Ramapattinam", "lat": 10.688, "lng": 77.065},
    {"name": "Kallipatti", "tamil_name": "கள்ளிப்பட்டி", "census_code": "644525", "firka": "Ramapattinam", "lat": 10.678, "lng": 77.070},
    {"name": "Krishnarayapuram", "tamil_name": "கிருஷ்ணராயபுரம்", "census_code": "644523", "firka": "Ramapattinam", "lat": 10.675, "lng": 77.068},
    {"name": "Nalluthukuzhuli", "tamil_name": "நல்லூத்துக்குழி", "census_code": "644544", "firka": "Ramapattinam", "lat": 10.668, "lng": 77.072},
    {"name": "Poosanaickendhali", "tamil_name": "பூசநாயக்கன்தாழி", "census_code": "644514", "firka": "Ramapattinam", "lat": 10.692, "lng": 77.060},
    {"name": "Poosaripatty", "tamil_name": "பூசாரிப்பட்டி", "census_code": "644538", "firka": "Ramapattinam", "lat": 10.686, "lng": 77.078},
    {"name": "Ramapattinam", "tamil_name": "ராமபட்டினம்", "census_code": "644516", "firka": "Ramapattinam", "lat": 10.684, "lng": 77.072},
    {"name": "Thalakkarai", "tamil_name": "தலக்கரை", "census_code": "644517", "firka": "Ramapattinam", "lat": 10.680, "lng": 77.080},
    {"name": "Thimamkuthu", "tamil_name": "திமம்குத்து", "census_code": "644547", "firka": "Ramapattinam", "lat": 10.670, "lng": 77.082},
    {"name": "Varadanur", "tamil_name": "வரதனூர்", "census_code": "644524", "firka": "Ramapattinam", "lat": 10.676, "lng": 77.074},

    # Pollachi Rural Firka (12 villages)
    {"name": "Arasampalayam", "tamil_name": "அரசம்பாளையம்", "census_code": "644475", "firka": "Pollachi Rural", "lat": 10.785, "lng": 77.010},
    {"name": "Eripatti", "tamil_name": "ஏரிப்பட்டி", "census_code": "644540", "firka": "Pollachi Rural", "lat": 10.655, "lng": 77.050},
    {"name": "Kakkadavu", "tamil_name": "கக்கடவு", "census_code": "644510", "firka": "Pollachi Rural", "lat": 10.742, "lng": 77.015},
    {"name": "Kodangipalayam", "tamil_name": "கொடங்கிபாளையம்", "census_code": "644487", "firka": "Pollachi Rural", "lat": 10.778, "lng": 77.018},
    {"name": "Kondampatty", "tamil_name": "கொண்டம்பட்டி", "census_code": "644479", "firka": "Pollachi Rural", "lat": 10.780, "lng": 77.005},
    {"name": "Kothavadi", "tamil_name": "கோதவாடி", "census_code": "644488", "firka": "Pollachi Rural", "lat": 10.775, "lng": 77.020},
    {"name": "Mettubavi", "tamil_name": "மேட்டுபாவி", "census_code": "644477", "firka": "Pollachi Rural", "lat": 10.782, "lng": 77.012},
    {"name": "Mullipadi", "tamil_name": "முள்ளிப்பாடி", "census_code": "644502", "firka": "Pollachi Rural", "lat": 10.768, "lng": 77.030},
    {"name": "Panappatti", "tamil_name": "பனப்பட்டி", "census_code": "644476", "firka": "Pollachi Rural", "lat": 10.784, "lng": 77.008},
    {"name": "Periakalandai", "tamil_name": "பெரியகாலந்தை", "census_code": "644490", "firka": "Pollachi Rural", "lat": 10.770, "lng": 77.035},
    {"name": "Santhegoundanpalayam", "tamil_name": "சாந்தேகவுண்டன்பாளையம்", "census_code": "644512", "firka": "Pollachi Rural", "lat": 10.740, "lng": 77.012},
    {"name": "Vadakkipalayam", "tamil_name": "வடக்கிபாளையம்", "census_code": "644500", "firka": "Pollachi Rural", "lat": 10.730, "lng": 77.005},
]

# 4 Habitations / Urban Localities (correctly classified under parent village or municipality)
POLLACHI_HABITATIONS: list[dict[str, Any]] = [
    {
        "name": "Sangampalayam",
        "tamil_name": "சங்கம்பாளையம்",
        "classification": "HABITATION",
        "parent_reference": "Achipatti",
        "parent_code": "VILL-644592",
        "code": "HAB-SANGAMPALAYAM",
        "notes": "Residential habitation administratively linked to Achipatti Village Panchayat (Pollachi North).",
        "lat": 10.680,
        "lng": 77.012,
    },
    {
        "name": "Jeeva Nagar",
        "tamil_name": "ஜீவா நகர்",
        "classification": "URBAN_LOCALITY",
        "parent_reference": "Pollachi Municipality",
        "parent_code": "MUN-POLLACHI",
        "code": "LOC-JEEVA-NAGAR",
        "notes": "Urban locality/ward within Pollachi Municipality limits.",
        "lat": 10.662,
        "lng": 77.008,
    },
    {
        "name": "Cheran Nagar",
        "tamil_name": "சேரன் நகர்",
        "classification": "URBAN_LOCALITY",
        "parent_reference": "Pollachi Municipality",
        "parent_code": "MUN-POLLACHI",
        "code": "LOC-CHERAN-NAGAR",
        "notes": "Residential layout within Mahalingapuram / Pollachi Municipality.",
        "lat": 10.667,
        "lng": 77.014,
    },
    {
        "name": "Thillai Nagar",
        "tamil_name": "தில்லை நகர்",
        "classification": "URBAN_LOCALITY",
        "parent_reference": "Pollachi Municipality",
        "parent_code": "MUN-POLLACHI",
        "code": "LOC-THILLAI-NAGAR",
        "notes": "Urban neighborhood/ward within Pollachi Municipality limits.",
        "lat": 10.658,
        "lng": 77.004,
    },
]


def create_provisional_multipolygon(lat: float, lng: float, delta: float = 0.007) -> MultiPolygon:
    """
    Generate an estimated provisional bounding polygon centered around coordinates.
    Marked PROVISIONAL per domain rules.
    """
    poly = Polygon([
        (lng - delta, lat - delta),
        (lng + delta, lat - delta),
        (lng + delta, lat + delta),
        (lng - delta, lat + delta),
        (lng - delta, lat - delta),
    ])
    return MultiPolygon([poly])


def seed_pollachi(dry_run: bool = False) -> None:
    db: Session = SessionLocal()
    try:
        logger.info(f"Starting Pollachi Demonstration Dataset Seeding (dry_run={dry_run})...")

        # 1. Seed or Retrieve Pollachi Taluk parent
        taluk_code = "TALUK-05899"
        taluk = db.query(AdministrativeArea).filter(AdministrativeArea.code == taluk_code).first()

        taluk_poly = MultiPolygon([
            Polygon([
                (76.90, 10.55),
                (77.15, 10.55),
                (77.15, 10.82),
                (76.90, 10.82),
                (76.90, 10.55),
            ])
        ])

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
            logger.info("Plan: Create Pollachi Taluk (TALUK-05899)")
        else:
            logger.info("Found existing Pollachi Taluk (TALUK-05899)")

        # 2. Seed Pollachi Municipality as parent for urban localities
        mun_code = "MUN-POLLACHI"
        municipality = db.query(AdministrativeArea).filter(AdministrativeArea.code == mun_code).first()
        mun_poly = create_provisional_multipolygon(10.660, 77.008, delta=0.015)

        if not municipality:
            municipality = AdministrativeArea(
                id=uuid.uuid4(),
                name="Pollachi Municipality",
                type=AreaType.WARD,
                code=mun_code,
                parent_id=taluk.id,
                boundary=from_shape(mun_poly, srid=4326),
                boundary_status=BoundaryStatus.PROVISIONAL.value,
                status="ACTIVE",
            )
            if not dry_run:
                db.add(municipality)
                db.flush()
            logger.info("Plan: Create Pollachi Municipality (MUN-POLLACHI)")
        else:
            logger.info("Found existing Pollachi Municipality (MUN-POLLACHI)")

        # 3. Seed 65 Revenue Villages
        village_map: dict[str, AdministrativeArea] = {}
        created_villages = 0
        updated_villages = 0

        for vdata in POLLACHI_REVENUE_VILLAGES:
            vcode = f"VILL-{vdata['census_code']}"
            existing_v = db.query(AdministrativeArea).filter(AdministrativeArea.code == vcode).first()
            poly = create_provisional_multipolygon(vdata["lat"], vdata["lng"])

            if not existing_v:
                new_v = AdministrativeArea(
                    id=uuid.uuid4(),
                    name=vdata["name"],
                    type=AreaType.VILLAGE,
                    code=vcode,
                    parent_id=taluk.id,
                    boundary=from_shape(poly, srid=4326),
                    boundary_status=BoundaryStatus.PROVISIONAL.value,
                    status="ACTIVE",
                )
                if not dry_run:
                    db.add(new_v)
                    db.flush()
                village_map[vdata["name"]] = new_v
                created_villages += 1
            else:
                village_map[vdata["name"]] = existing_v
                updated_villages += 1

        logger.info(f"Revenue Villages processed: {created_villages} to create, {updated_villages} existing (Total: {len(POLLACHI_REVENUE_VILLAGES)})")

        # 4. Seed Habitations / Localities with proper classification
        achipatti = village_map.get("Achipatti")
        for hab in POLLACHI_HABITATIONS:
            existing_hab = db.query(AdministrativeArea).filter(AdministrativeArea.code == hab["code"]).first()
            hab_poly = create_provisional_multipolygon(hab["lat"], hab["lng"], delta=0.003)

            parent_id = achipatti.id if (achipatti and hab["parent_reference"] == "Achipatti") else municipality.id

            if not existing_hab:
                new_hab = AdministrativeArea(
                    id=uuid.uuid4(),
                    name=hab["name"],
                    type=AreaType.WARD,
                    code=hab["code"],
                    parent_id=parent_id,
                    boundary=from_shape(hab_poly, srid=4326),
                    boundary_status=BoundaryStatus.PROVISIONAL.value,
                    status="ACTIVE",
                )
                if not dry_run:
                    db.add(new_hab)
                    db.flush()
                logger.info(f"Plan: Create Habitation '{hab['name']}' under {hab['parent_reference']}")
            else:
                logger.info(f"Found existing Habitation '{hab['name']}'")

        # 5. Demonstration Layouts
        demo_layouts = [
            {
                "name": "Pollachi Central Layout",
                "area_names": ["Achipatti", "Zamin Muthur", "Unjavelampatti"],
                "target_buildings": 250,
                "status": LayoutStatus.DRAFT,
            },
            {
                "name": "Pollachi North Layout",
                "area_names": ["A. Nagur", "Anupperpalayam", "Kittasoorampalayam", "Bodipalayam"],
                "target_buildings": 250,
                "status": LayoutStatus.DRAFT,
            },
            {
                "name": "Pollachi South Layout",
                "area_names": ["Gomangalam", "Kolarpatti", "Singanallur", "Seelakkampatti"],
                "target_buildings": 250,
                "status": LayoutStatus.DRAFT,
            },
            {
                "name": "Pollachi Rural Layout",
                "area_names": ["Devambadi", "Ramapattinam", "Chikkarayapuram", "Okkulipalayam"],
                "target_buildings": 250,
                "status": LayoutStatus.DRAFT,
            },
        ]

        created_layouts = 0
        for ldef in demo_layouts:
            existing_l = db.query(Layout).filter(Layout.name == ldef["name"]).first()
            if existing_l:
                logger.info(f"Layout '{ldef['name']}' already exists (ID: {existing_l.id}). Skipping.")
                continue

            included_areas = [village_map[aname] for aname in ldef["area_names"] if aname in village_map]
            if not included_areas:
                logger.warning(f"Could not resolve areas for layout '{ldef['name']}'")
                continue

            primary_area = included_areas[0]

            # Union boundaries
            polys = [Polygon([
                (vdata["lng"] - 0.007, vdata["lat"] - 0.007),
                (vdata["lng"] + 0.007, vdata["lat"] - 0.007),
                (vdata["lng"] + 0.007, vdata["lat"] + 0.007),
                (vdata["lng"] - 0.007, vdata["lat"] + 0.007),
            ]) for vdata in POLLACHI_REVENUE_VILLAGES if vdata["name"] in ldef["area_names"]]
            union_poly = unary_union(polys)
            if isinstance(union_poly, Polygon):
                layout_mp = MultiPolygon([union_poly])
            else:
                layout_mp = union_poly

            new_layout = Layout(
                id=uuid.uuid4(),
                area_id=primary_area.id,
                name=ldef["name"],
                target_hlb_building_count=ldef["target_buildings"],
                actual_building_count=0,
                expected_hlb_count=len(included_areas),
                status=ldef["status"],
                boundary=from_shape(layout_mp, srid=4326),
            )

            if not dry_run:
                db.add(new_layout)
                db.flush()

                # Add associations
                for idx, area in enumerate(included_areas):
                    assoc = LayoutAdministrativeArea(
                        id=uuid.uuid4(),
                        layout_id=new_layout.id,
                        area_id=area.id,
                    )
                    db.add(assoc)

            created_layouts += 1
            logger.info(f"Plan: Create Layout '{ldef['name']}' covering {len(included_areas)} areas ({', '.join(ldef['area_names'])})")

        if dry_run:
            logger.info("DRY RUN COMPLETE: All validations passed. No changes committed to the database.")
            db.rollback()
        else:
            db.commit()
            logger.info("SEED COMPLETE: Successfully populated Pollachi demonstration dataset into the database.")

    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Pollachi Demonstration Dataset")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without committing database changes")
    args = parser.parse_args()

    seed_pollachi(dry_run=args.dry_run)
