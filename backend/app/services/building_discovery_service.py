import logging
import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.gis.spatial import (
    COIMBATORE_PROJECTED_CRS,
    DEFAULT_GEOGRAPHIC_CRS,
    calculate_projected_distance_meters,
    transform_geometry,
)
from app.models.building_edit import (
    BuildingEdit,
    BuildingEditReviewStatus,
    BuildingEditType,
)
from app.models.enumerator_assignment import (
    EnumeratorAssignmentStatus,
    HlbEnumeratorAssignment,
)
from app.models.hlb import HlbHouse, HouselistingBlock
from app.models.house import BuildingFieldStatus, BuildingSourceType, House

logger = logging.getLogger(__name__)

DUPLICATE_PROXIMITY_THRESHOLD_METERS = 5.0  # Proximity buffer for duplicate structure detection


class BuildingDiscoveryService:
    def discover_building(
        self,
        db: Session,
        hlb_id: UUID,
        enumerator_id: UUID,
        latitude: float,
        longitude: float,
        building_reference: str | None = None,
        house_number: str | None = None,
        notes: str | None = None,
        placement_mode: str = "CURRENT_GPS",  # "CURRENT_GPS" or "MANUAL_MAP"
    ) -> dict:
        """
        Record a newly discovered building found during road traversal fieldwork.
        Enforces:
        - Strict Enumerator assignment authorization (403 Forbidden).
        - Spatial validation against HLB boundary.
        - Strict duplicate prevention (proximity < 5m check and reference collision).
        - Preserves field-discovery provenance (source_type=FIELD_DISCOVERED, FIELD_ADDED).
        - Automatic submission into BuildingEdit supervisor review workflow.
        """
        # 1. Enforce Enumerator Authorization
        assignment = (
            db.query(HlbEnumeratorAssignment)
            .filter(
                HlbEnumeratorAssignment.hlb_id == hlb_id,
                HlbEnumeratorAssignment.enumerator_id == enumerator_id,
                HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
            )
            .first()
        )
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to discover or add buildings for this HLB",
            )

        hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
        if not hlb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Houselisting Block with ID {hlb_id} not found",
            )

        # 2. Coordinate Range Validation
        if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid geographic coordinates: lat={latitude}, lon={longitude}",
            )

        # 3. Spatial Boundary Check
        pt_geo = Point(longitude, latitude)
        if hlb.boundary is not None:
            hlb_poly = to_shape(hlb.boundary)
            # Allow up to 10m tolerance around HLB boundary for edge/boundary structures
            poly_proj = transform_geometry(hlb_poly, DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS)
            pt_proj = transform_geometry(pt_geo, DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS)
            buffered_poly = poly_proj.buffer(10.0)

            if not buffered_poly.contains(pt_proj):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Building location is outside the assigned HLB boundary.",
                )

        # 4. Duplicate Prevention Checks
        # Query existing buildings in this HLB
        existing_houses = (
            db.query(House)
            .join(HlbHouse, HlbHouse.house_id == House.id)
            .filter(HlbHouse.hlb_id == hlb_id)
            .all()
        )

        target_ref = building_reference.strip().upper() if building_reference else None

        for eh in existing_houses:
            # Check reference code uniqueness if provided
            if target_ref and eh.building_reference and eh.building_reference.upper() == target_ref:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"DUPLICATE_BUILDING_REFERENCE: Duplicate building reference '{target_ref}' already exists in this HLB (Building ID: {eh.id}).",
                )

            # Check spatial proximity
            d_meters = calculate_projected_distance_meters(
                (latitude, longitude), (eh.latitude, eh.longitude)
            )
            if d_meters < DUPLICATE_PROXIMITY_THRESHOLD_METERS:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"DUPLICATE_BUILDING_PROXIMITY: Potential duplicate structure detected: existing building '{eh.building_reference}' "
                        f"is only {round(d_meters, 1)}m away (threshold is {DUPLICATE_PROXIMITY_THRESHOLD_METERS}m)."
                    ),
                )

        # 5. Generate Reference Code if not provided
        ref_code = target_ref or f"DISC-{str(uuid.uuid4())[:6].upper()}"

        # Determine administrative area from layout
        area_id = None
        if hlb.layout and hlb.layout.area_id:
            area_id = hlb.layout.area_id
        elif hlb.layout_id:
            layout_rec = db.query(Layout).filter(Layout.id == hlb.layout_id).first()
            if layout_rec:
                area_id = layout_rec.area_id

        if not area_id:
            # Fallback to first existing house's area_id in HLB
            if existing_houses:
                area_id = existing_houses[0].area_id
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Cannot determine administrative area for newly discovered building.",
                )

        # 6. Create House Record
        house = House(
            area_id=area_id,
            building_reference=ref_code,
            house_number=house_number,
            latitude=latitude,
            longitude=longitude,
            location=from_shape(pt_geo, srid=4326),
            source_type=BuildingSourceType.FIELD_DISCOVERED,
            field_status=BuildingFieldStatus.FIELD_ADDED,
            imagery_source=f"Field Discovery ({placement_mode})",
            detection_confidence=1.0,
        )
        db.add(house)
        db.flush()

        # 7. Associate to HLB
        hlb_house = HlbHouse(
            hlb_id=hlb_id,
            house_id=house.id,
        )
        db.add(hlb_house)

        # 8. Submit BuildingEdit Record for Supervisor Review
        building_edit = BuildingEdit(
            hlb_id=hlb_id,
            building_id=house.id,
            edit_type=BuildingEditType.ADD,
            proposed_changes={
                "latitude": latitude,
                "longitude": longitude,
                "building_reference": ref_code,
                "house_number": house_number,
                "placement_mode": placement_mode,
                "notes": notes,
                "discovery_timestamp": datetime.now(UTC).isoformat(),
            },
            reason="Newly discovered unmapped structure during road traversal",
            requesting_user_id=enumerator_id,
            review_status=BuildingEditReviewStatus.PENDING,
        )
        db.add(building_edit)
        db.commit()

        logger.info(
            "Enumerator %s discovered building %s (%s) at (%f, %f) in HLB %s",
            enumerator_id,
            house.id,
            ref_code,
            latitude,
            longitude,
            hlb_id,
        )

        return {
            "building_id": str(house.id),
            "building_reference": ref_code,
            "house_number": house.house_number,
            "latitude": house.latitude,
            "longitude": house.longitude,
            "source_type": house.source_type,
            "field_status": house.field_status,
            "edit_id": str(building_edit.id),
            "building_edit_id": str(building_edit.id),
            "review_status": building_edit.review_status,
            "message": "Building discovered and added successfully. Submitted for supervisor review.",
        }


building_discovery_service = BuildingDiscoveryService()
