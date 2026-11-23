import argparse
import logging
import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine, is_sqlite
from app.core.security import get_password_hash
from app.gis.building_detection import building_detection_service
from app.gis.hlb.editing_service import hlb_editing_service
from app.gis.hlb.generator_service import hlb_generation_service
from app.gis.spatial import validate_and_convert_geojson_polygon
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.fieldwork import (
    FieldworkBuildingStatus,
    GpsTrack,
    HouseFieldworkStatus,
    HouseholdRecord,
    HouseholdRecordStatus,
    HouseholdSyncStatus,
    RevisitRecord,
    RevisitRecordStatus,
    SyncEntityType,
    SyncOperation,
    SyncOperationStatus,
    SyncOperationType,
)
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import House
from app.models.layout import Layout
from app.models.user import User, UserRole, UserStatus
from app.schemas.layout import LayoutCreate
from app.services.enumerator_service import enumerator_service
from app.services.layout_service import layout_service
from app.services.supervisor_service import supervisor_service

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# --- Seed Users ---
SEED_USERS = [
    {
        "name": "Ramaswamy (Deputy Tahsildar)",
        "username": "deputy",
        "password": "password123",
        "phone": "9876543210",
        "role": UserRole.DEPUTY_TAHSILDAR,
        "status": UserStatus.ACTIVE,
    },
    {
        "name": "Kavitha (Supervisor)",
        "username": "supervisor",
        "password": "password123",
        "phone": "9876543211",
        "role": UserRole.SUPERVISOR,
        "status": UserStatus.ACTIVE,
    },
    {
        "name": "Rajesh (Supervisor)",
        "username": "supervisor2",
        "password": "password123",
        "phone": "9876543215",
        "role": UserRole.SUPERVISOR,
        "status": UserStatus.ACTIVE,
    },
    {
        "name": "Murugan (Enumerator)",
        "username": "enumerator",
        "password": "password123",
        "phone": "9876543212",
        "role": UserRole.ENUMERATOR,
        "status": UserStatus.ACTIVE,
    },
    {
        "name": "Priya (Enumerator)",
        "username": "enumerator2",
        "password": "password123",
        "phone": "9876543213",
        "role": UserRole.ENUMERATOR,
        "status": UserStatus.ACTIVE,
    },
    {
        "name": "Senthil (Enumerator)",
        "username": "enumerator3",
        "password": "password123",
        "phone": "9876543214",
        "role": UserRole.ENUMERATOR,
        "status": UserStatus.ACTIVE,
    },
    {
        "name": "Anand (Enumerator)",
        "username": "enumerator4",
        "password": "password123",
        "phone": "9876543216",
        "role": UserRole.ENUMERATOR,
        "status": UserStatus.ACTIVE,
    },
]

# --- Seed Boundaries ---
ARASUR_VILLAGE_GEOJSON = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [
                [77.1100, 11.0700],
                [77.1350, 11.0700],
                [77.1380, 11.0820],
                [77.1350, 11.0950],
                [77.1100, 11.0950],
                [77.1080, 11.0820],
                [77.1100, 11.0700],
            ]
        ]
    ],
}

KANIYUR_VILLAGE_GEOJSON = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [
                [77.1400, 11.0600],
                [77.1650, 11.0600],
                [77.1680, 11.0720],
                [77.1650, 11.0850],
                [77.1400, 11.0850],
                [77.1380, 11.0720],
                [77.1400, 11.0600],
            ]
        ]
    ],
}

SAMPLE_HEAD_NAMES = [
    "K. Murugesan",
    "M. Palanisamy",
    "R. Lakshmi",
    "S. Arumugam",
    "P. Kannan",
    "V. Selvi",
    "T. Natarajan",
    "A. Subramanian",
    "G. Saraswathi",
    "D. Vijayakumar",
    "N. Meenakshi",
    "S. Muthukumar",
    "R. Kalimuthu",
    "C. Thangavel",
    "B. Parvathi",
    "K. Dhanalakshmi",
    "S. Ramesh",
    "M. Govindaraj",
    "P. Sangeetha",
    "J. Jayaraman",
    "R. Soundararajan",
    "T. Vasantha",
    "V. Marimuthu",
    "N. Gomathi",
    "A. Veerappan",
]

WATER_SOURCES = ["TAP_WATER", "HAND_PUMP", "TUBEWELL", "PROTECTED_WELL"]
OWNERSHIP_TYPES = ["OWNED", "OWNED", "OWNED", "RENTED"]
LATRINE_TYPES = ["FLUSH_LATRINE", "PIT_LATRINE", "FLUSH_LATRINE"]


def clear_database():
    """
    Erase all existing data and drop all tables.
    """
    logger.info("Erasing all existing data from database...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    if is_sqlite:
        with engine.connect() as conn:
            conn.execute(text("VACUUM"))
    logger.info("Successfully dropped and recreated clean database schema.")


def seed_database(reset: bool = True):
    """
    Seed comprehensive mock data covering all user roles and functionalities:
      1. Deputy Tahsildar (deputy / password123)
      2. Supervisors (supervisor, supervisor2 / password123)
      3. Enumerators (enumerator, enumerator2, enumerator3, enumerator4)
      4. Administrative Areas:
         - Arasur Village: Fully planned, approved, assigned layout
         - Kaniyur Village: Fresh area for testing layout generation
      5. Layout & HLB Partitioning (HLB-001, HLB-002, HLB-003)
      6. Supervisor Assignment & Enumerator Assignments
      7. Realistic fieldwork records (census forms, locked, revisits, GPS)
    """
    if reset:
        clear_database()
    else:
        Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1. Seed Users
        logger.info("Seeding authentication users...")
        user_map: dict[str, User] = {}
        for u_data in SEED_USERS:
            existing = (
                db.query(User).filter(User.username == u_data["username"]).first()
            )
            if existing:
                existing.name = u_data["name"]
                existing.password_hash = get_password_hash(u_data["password"])
                existing.role = u_data["role"]
                existing.status = u_data["status"]
                existing.phone = u_data["phone"]
                user_map[u_data["username"]] = existing
            else:
                user = User(
                    name=u_data["name"],
                    username=u_data["username"],
                    password_hash=get_password_hash(u_data["password"]),
                    phone=u_data["phone"],
                    role=u_data["role"],
                    status=u_data["status"],
                )
                db.add(user)
                user_map[u_data["username"]] = user

        db.commit()
        for u in user_map.values():
            db.refresh(u)
        logger.info(f"Seeded {len(user_map)} users across all 3 roles.")

        # 2. Seed Administrative Areas
        logger.info(
            "Seeding Administrative Areas (Arasur Village & Kaniyur Village)..."
        )
        # Area 1: Arasur Village
        area_code_arasur = "VILL-638401"
        arasur_boundary = validate_and_convert_geojson_polygon(ARASUR_VILLAGE_GEOJSON)
        arasur_area = (
            db.query(AdministrativeArea)
            .filter(AdministrativeArea.code == area_code_arasur)
            .first()
        )
        if arasur_area:
            arasur_area.name = "Arasur Village"
            arasur_area.boundary = arasur_boundary
            arasur_area.status = "ACTIVE"
        else:
            arasur_area = AdministrativeArea(
                name="Arasur Village",
                type=AreaType.VILLAGE,
                code=area_code_arasur,
                boundary=arasur_boundary,
                status="ACTIVE",
            )
            db.add(arasur_area)

        # Area 2: Kaniyur Village (unpartitioned, ready for Deputy testing)
        area_code_kaniyur = "VILL-638402"
        kaniyur_boundary = validate_and_convert_geojson_polygon(KANIYUR_VILLAGE_GEOJSON)
        kaniyur_area = (
            db.query(AdministrativeArea)
            .filter(AdministrativeArea.code == area_code_kaniyur)
            .first()
        )
        if kaniyur_area:
            kaniyur_area.name = "Kaniyur Village"
            kaniyur_area.boundary = kaniyur_boundary
            kaniyur_area.status = "ACTIVE"
        else:
            kaniyur_area = AdministrativeArea(
                name="Kaniyur Village",
                type=AreaType.VILLAGE,
                code=area_code_kaniyur,
                boundary=kaniyur_boundary,
                status="ACTIVE",
            )
            db.add(kaniyur_area)

        db.commit()
        db.refresh(arasur_area)
        db.refresh(kaniyur_area)
        logger.info(f"Seeded areas: {arasur_area.name} and {kaniyur_area.name}")

        # 3. Satellite-Assisted Building Detection Ingestion
        logger.info("Ingesting building detection footprints for Arasur Village...")
        detected_arasur = building_detection_service.run_building_detection(
            db=db,
            area=arasur_area,
            imagery_source="Google Open Buildings V3",
            confidence_threshold=None,
            allow_development_fallback=True,
        )
        logger.info(
            f"Ingested {len(detected_arasur)} building footprints for Arasur Village."
        )

        logger.info("Ingesting building detection footprints for Kaniyur Village...")
        detected_kaniyur = building_detection_service.run_building_detection(
            db=db,
            area=kaniyur_area,
            imagery_source="Google Open Buildings V3",
            confidence_threshold=None,
            allow_development_fallback=True,
        )
        logger.info(
            f"Ingested {len(detected_kaniyur)} building footprints for Kaniyur Village."
        )

        # 4. Create, Generate, Approve, and Assign Layout for Arasur Village
        logger.info("Creating Fieldwork Layout for Arasur Village...")
        deputy_user = user_map["deputy"]
        supervisor_user = user_map["supervisor"]

        layout_dict = layout_service.create_layout(
            db=db,
            data=LayoutCreate(
                area_id=arasur_area.id,
                name="Arasur Main Fieldwork Layout",
                target_buildings_per_hlb=80,
            ),
            user_id=deputy_user.id,
        )
        raw_layout_id = layout_dict["id"]
        layout_id = (
            raw_layout_id
            if isinstance(raw_layout_id, uuid.UUID)
            else uuid.UUID(str(raw_layout_id))
        )
        layout = db.query(Layout).filter(Layout.id == layout_id).first()

        # Run AI HLB generation
        logger.info("Generating candidate HLBs with spatial clustering...")
        candidate_res = hlb_generation_service.generate_candidate_hlbs(
            db=db,
            layout=layout,
            user_id=deputy_user.id,
            target_buildings_per_hlb=80,
        )
        logger.info(f"Generated {candidate_res['hlb_count']} candidate HLBs.")

        # Approve layout version
        logger.info("Approving layout version...")
        hlb_editing_service.approve_layout(
            db=db,
            layout_id=layout.id,
            user_id=deputy_user.id,
        )

        # Assign layout to Supervisor Kavitha
        logger.info("Assigning layout to Supervisor Kavitha...")
        supervisor_service.assign_supervisor(
            db=db,
            layout_id=layout.id,
            supervisor_id=supervisor_user.id,
            assigned_by_user_id=deputy_user.id,
        )

        # Retrieve active version HLBs
        hlbs = (
            db.query(HouselistingBlock)
            .filter(HouselistingBlock.version_id == layout.active_version_id)
            .order_by(HouselistingBlock.block_code.asc())
            .all()
        )
        logger.info(f"Layout has {len(hlbs)} active HLBs.")

        # 5. Assign Enumerators
        # Assign HLB-001 to Murugan (enumerator)
        if len(hlbs) >= 1:
            enumerator_service.assign_enumerator(
                db=db,
                hlb_id=hlbs[0].id,
                enumerator_id=user_map["enumerator"].id,
                supervisor_id=supervisor_user.id,
            )
            logger.info(f"Assigned {hlbs[0].block_code} to Murugan (enumerator)")

        # Assign HLB-002 to Priya (enumerator2)
        if len(hlbs) >= 2:
            enumerator_service.assign_enumerator(
                db=db,
                hlb_id=hlbs[1].id,
                enumerator_id=user_map["enumerator2"].id,
                supervisor_id=supervisor_user.id,
            )
            logger.info(f"Assigned {hlbs[1].block_code} to Priya (enumerator2)")

        # HLB-003 is left unassigned so Supervisor can demonstrate assignment in UI!
        if len(hlbs) >= 3:
            logger.info(
                f"{hlbs[2].block_code} left UNASSIGNED so supervisor can test "
                "the 'Assign Enumerator' feature with Senthil or Anand."
            )

        # 6. Seed Fieldwork Data for HLB-001 (Murugan)
        logger.info("Seeding mock fieldwork data for HLB-001 (Murugan)...")
        hlb1_houses = (
            db.query(House)
            .join(HlbHouse, HlbHouse.house_id == House.id)
            .filter(HlbHouse.hlb_id == hlbs[0].id)
            .order_by(House.house_number.asc())
            .all()
        )

        # 18 Completed houses with Census Household Questionnaire records
        for i in range(min(18, len(hlb1_houses))):
            house = hlb1_houses[i]
            st = HouseFieldworkStatus(
                house_id=house.id,
                hlb_id=hlbs[0].id,
                enumerator_id=user_map["enumerator"].id,
                status=FieldworkBuildingStatus.COMPLETED,
                household_count=1,
                last_updated_at=datetime.now(UTC) - timedelta(hours=i),
                updated_by=user_map["enumerator"].id,
            )
            db.add(st)

            head = SAMPLE_HEAD_NAMES[i % len(SAMPLE_HEAD_NAMES)]
            male = random.randint(1, 3)
            female = random.randint(1, 3)
            total = male + female
            rec = HouseholdRecord(
                house_id=house.id,
                hlb_id=hlbs[0].id,
                enumerator_id=user_map["enumerator"].id,
                household_number=f"HH-{i + 1:03d}",
                head_name=head,
                total_members=total,
                male_count=male,
                female_count=female,
                transgender_count=0,
                ownership_status=OWNERSHIP_TYPES[i % len(OWNERSHIP_TYPES)],
                drinking_water_source=WATER_SOURCES[i % len(WATER_SOURCES)],
                lighting_source="ELECTRICITY",
                latrine_facility=LATRINE_TYPES[i % len(LATRINE_TYPES)],
                data={
                    "phone": f"98421{i + 10000:05d}",
                    "income_bracket": "MIDDLE",
                    "occupation": "Agriculture / Industry",
                },
                source="FORM",
                status=HouseholdRecordStatus.COMPLETED,
                sync_status=HouseholdSyncStatus.SYNCED,
                version=1,
                captured_at=datetime.now(UTC) - timedelta(hours=i),
            )
            db.add(rec)

            track = GpsTrack(
                enumerator_id=user_map["enumerator"].id,
                hlb_id=hlbs[0].id,
                house_id=house.id,
                latitude=house.latitude,
                longitude=house.longitude,
                accuracy_meters=8.5,
                timestamp=datetime.now(UTC) - timedelta(hours=i),
                source="OFFLINE",
            )
            db.add(track)

        # 3 Locked houses with Revisit records
        locked_reasons = [
            (
                "DOOR_LOCKED",
                "Family away at work, neighbor said return after 6 PM. Ph: 9876543201",
            ),
            (
                "FAMILY_OUT_OF_TOWN",
                "Family gone to hometown for temple festival, expected back Sunday.",
            ),
            (
                "HOUSE_LOCKED",
                "Gate padlocked, no response. Neighbor confirmed occupancy.",
            ),
        ]
        for j in range(min(3, max(0, len(hlb1_houses) - 18))):
            house = hlb1_houses[18 + j]
            st = HouseFieldworkStatus(
                house_id=house.id,
                hlb_id=hlbs[0].id,
                enumerator_id=user_map["enumerator"].id,
                status=FieldworkBuildingStatus.LOCKED,
                household_count=0,
                last_updated_at=datetime.now(UTC) - timedelta(minutes=45 * (j + 1)),
                updated_by=user_map["enumerator"].id,
            )
            db.add(st)

            rev = RevisitRecord(
                house_id=house.id,
                hlb_id=hlbs[0].id,
                enumerator_id=user_map["enumerator"].id,
                reason=locked_reasons[j][0],
                notes=locked_reasons[j][1],
                status=RevisitRecordStatus.PENDING,
                recommended_at=datetime.now(UTC) - timedelta(minutes=45 * (j + 1)),
            )
            db.add(rev)

        # 1 In-Progress house
        if len(hlb1_houses) > 21:
            st_in_prog = HouseFieldworkStatus(
                house_id=hlb1_houses[21].id,
                hlb_id=hlbs[0].id,
                enumerator_id=user_map["enumerator"].id,
                status=FieldworkBuildingStatus.IN_PROGRESS,
                household_count=0,
                last_updated_at=datetime.now(UTC) - timedelta(minutes=10),
                updated_by=user_map["enumerator"].id,
            )
            db.add(st_in_prog)

        # GPS Track observation near boundary (for boundary monitoring)
        outside_track = GpsTrack(
            enumerator_id=user_map["enumerator"].id,
            hlb_id=hlbs[0].id,
            house_id=None,
            latitude=11.0965,
            longitude=77.1365,
            accuracy_meters=14.0,
            timestamp=datetime.now(UTC) - timedelta(hours=2),
            source="OFFLINE",
        )
        db.add(outside_track)

        # Sync operation record
        if hlb1_houses:
            sync_op = SyncOperation(
                idempotency_key=str(uuid.uuid4()),
                device_id="device-murugan-01",
                user_id=user_map["enumerator"].id,
                operation_type=SyncOperationType.STATUS_UPDATE,
                entity_type=SyncEntityType.BUILDING_STATUS,
                entity_id=str(hlb1_houses[0].id),
                client_timestamp=datetime.now(UTC) - timedelta(hours=1),
                server_timestamp=datetime.now(UTC) - timedelta(hours=1),
                status=SyncOperationStatus.SYNCED,
                retry_count=0,
            )
            db.add(sync_op)

        # 7. Seed Fieldwork Data for HLB-002 (Priya)
        logger.info("Seeding mock fieldwork data for HLB-002 (Priya)...")
        hlb2_houses = (
            db.query(House)
            .join(HlbHouse, HlbHouse.house_id == House.id)
            .filter(HlbHouse.hlb_id == hlbs[1].id)
            .order_by(House.house_number.asc())
            .all()
        )

        # 35 Completed houses for Priya
        for i in range(min(35, len(hlb2_houses))):
            house = hlb2_houses[i]
            st = HouseFieldworkStatus(
                house_id=house.id,
                hlb_id=hlbs[1].id,
                enumerator_id=user_map["enumerator2"].id,
                status=FieldworkBuildingStatus.COMPLETED,
                household_count=1,
                last_updated_at=datetime.now(UTC) - timedelta(hours=i),
                updated_by=user_map["enumerator2"].id,
            )
            db.add(st)

            head = SAMPLE_HEAD_NAMES[(i + 7) % len(SAMPLE_HEAD_NAMES)]
            male = random.randint(1, 3)
            female = random.randint(1, 3)
            total = male + female
            rec = HouseholdRecord(
                house_id=house.id,
                hlb_id=hlbs[1].id,
                enumerator_id=user_map["enumerator2"].id,
                household_number=f"HH2-{i + 1:03d}",
                head_name=head,
                total_members=total,
                male_count=male,
                female_count=female,
                transgender_count=0,
                ownership_status=OWNERSHIP_TYPES[i % len(OWNERSHIP_TYPES)],
                drinking_water_source=WATER_SOURCES[i % len(WATER_SOURCES)],
                lighting_source="ELECTRICITY",
                latrine_facility="FLUSH_LATRINE",
                source="FORM",
                status=HouseholdRecordStatus.COMPLETED,
                sync_status=HouseholdSyncStatus.SYNCED,
                version=1,
                captured_at=datetime.now(UTC) - timedelta(hours=i),
            )
            db.add(rec)

            track = GpsTrack(
                enumerator_id=user_map["enumerator2"].id,
                hlb_id=hlbs[1].id,
                house_id=house.id,
                latitude=house.latitude,
                longitude=house.longitude,
                accuracy_meters=7.0,
                timestamp=datetime.now(UTC) - timedelta(hours=i),
                source="OFFLINE",
            )
            db.add(track)

        # 2 Locked houses for Priya
        for j in range(min(2, max(0, len(hlb2_houses) - 35))):
            house = hlb2_houses[35 + j]
            st = HouseFieldworkStatus(
                house_id=house.id,
                hlb_id=hlbs[1].id,
                enumerator_id=user_map["enumerator2"].id,
                status=FieldworkBuildingStatus.LOCKED,
                household_count=0,
                last_updated_at=datetime.now(UTC) - timedelta(hours=1),
                updated_by=user_map["enumerator2"].id,
            )
            db.add(st)

            rev = RevisitRecord(
                house_id=house.id,
                hlb_id=hlbs[1].id,
                enumerator_id=user_map["enumerator2"].id,
                reason="DOOR_LOCKED",
                notes="Residents at spinning mill; evening revisit recommended.",
                status=RevisitRecordStatus.PENDING,
                recommended_at=datetime.now(UTC) - timedelta(hours=1),
            )
            db.add(rev)

        db.commit()
        logger.info("Successfully completed comprehensive database seeding!")
        logger.info(
            "\n"
            "===========================================================\n"
            "                  DEMO USERS & CREDENTIALS                 \n"
            "===========================================================\n"
            "  Deputy Tahsildar:  username: deputy       password: password123\n"
            "  Supervisor:        username: supervisor   password: password123\n"
            "  Supervisor 2:      username: supervisor2  password: password123\n"
            "  Enumerator 1:      username: enumerator   password: password123\n"
            "  Enumerator 2:      username: enumerator2  password: password123\n"
            "  Enumerator 3:      username: enumerator3  password: password123\n"
            "  Enumerator 4:      username: enumerator4  password: password123\n"
            "===========================================================\n"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed AI-Enumerator Assistant database."
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not erase existing database tables before seeding.",
    )
    args = parser.parse_args()
    seed_database(reset=not args.no_reset)
