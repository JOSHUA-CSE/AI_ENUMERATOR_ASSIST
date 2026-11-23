import logging
import math
from uuid import UUID

from fastapi import HTTPException, status
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
from sqlalchemy.orm import Session

from app.gis.hlb.generator_service import hlb_generation_service
from app.gis.spatial import geometry_to_geojson_dict
from app.models.administrative_area import AdministrativeArea
from app.models.hlb import HouselistingBlock
from app.models.house import House
from app.models.layout import (
    Layout,
    LayoutAdministrativeArea,
    LayoutStatus,
    LayoutVersion,
)
from app.models.supervisor_assignment import (
    LayoutSupervisorAssignment,
    SupervisorAssignmentStatus,
)
from app.schemas.layout import LayoutCreate, LayoutUpdate

logger = logging.getLogger(__name__)

ACTIVE_LAYOUT_STATUSES = (
    LayoutStatus.DRAFT,
    LayoutStatus.GENERATED,
    LayoutStatus.REVIEW,
    LayoutStatus.APPROVED,
    LayoutStatus.ASSIGNED,
    LayoutStatus.ACTIVE,
)


class LayoutService:
    """
    Business service for Layout and Houselisting Block lifecycle management.
    """

    def list_layouts(
        self,
        db: Session,
        area_id: UUID | None = None,
        status_filter: LayoutStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> dict:
        query = db.query(Layout)
        if area_id:
            matching_layout_ids = (
                db.query(LayoutAdministrativeArea.layout_id)
                .filter(LayoutAdministrativeArea.area_id == area_id)
            )
            query = query.filter(
                (Layout.area_id == area_id) | (Layout.id.in_(matching_layout_ids))
            )
        if status_filter:
            query = query.filter(Layout.status == status_filter)

        total = query.count()
        layouts = (
            query.order_by(Layout.created_at.desc()).offset(skip).limit(limit).all()
        )

        items = []
        for layout in layouts:
            items.append(self._format_layout_response(db, layout))

        return {"items": items, "total": total}

    def get_layout_by_id(self, db: Session, layout_id: UUID) -> dict:
        layout = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )
        return self._format_layout_response(db, layout)

    def create_layout(
        self, db: Session, data: LayoutCreate, user_id: UUID | None
    ) -> dict:
        area_ids = data.area_ids or []
        if not area_ids and data.area_id:
            area_ids = [data.area_id]
        elif not area_ids and data.administrative_area_id:
            area_ids = [data.administrative_area_id]

        if not area_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At least one administrative area ID must be provided",
            )

        # 1. Verify all administrative areas exist
        areas = (
            db.query(AdministrativeArea)
            .filter(AdministrativeArea.id.in_(area_ids))
            .all()
        )
        if len(areas) != len(area_ids):
            found_ids = {a.id for a in areas}
            missing = [str(aid) for aid in area_ids if aid not in found_ids]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Administrative area(s) not found: {', '.join(missing)}",
            )

        # 2. Invariant Check: A village/ward can belong to only one active Layout at a time.
        # Check association table for active layouts
        conflicting_assoc = (
            db.query(LayoutAdministrativeArea, Layout, AdministrativeArea)
            .join(Layout, Layout.id == LayoutAdministrativeArea.layout_id)
            .join(AdministrativeArea, AdministrativeArea.id == LayoutAdministrativeArea.area_id)
            .filter(
                LayoutAdministrativeArea.area_id.in_(area_ids),
                Layout.status.in_(ACTIVE_LAYOUT_STATUSES),
            )
            .first()
        )
        if conflicting_assoc:
            _assoc, conf_layout, conf_area = conflicting_assoc
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Administrative area '{conf_area.name}' already belongs to active layout "
                    f"'{conf_layout.name}' ({conf_layout.status.value}). A village or ward "
                    "can belong to only one active layout at a time."
                ),
            )

        # Check primary area_id on Layout table directly as fallback
        conflicting_direct = (
            db.query(Layout, AdministrativeArea)
            .join(AdministrativeArea, AdministrativeArea.id == Layout.area_id)
            .filter(
                Layout.area_id.in_(area_ids),
                Layout.status.in_(ACTIVE_LAYOUT_STATUSES),
            )
            .first()
        )
        if conflicting_direct:
            conf_layout, conf_area = conflicting_direct
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Administrative area '{conf_area.name}' already belongs to active layout "
                    f"'{conf_layout.name}' ({conf_layout.status.value}). A village or ward "
                    "can belong to only one active layout at a time."
                ),
            )

        target_buildings = data.target_buildings_per_hlb
        if target_buildings <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="target_buildings_per_hlb must be greater than 0",
            )

        # Count buildings across all associated areas
        building_count = db.query(House).filter(House.area_id.in_(area_ids)).count()
        expected_hlbs = (
            max(1, math.ceil(building_count / target_buildings))
            if building_count > 0
            else 0
        )

        # Combine boundaries if multiple areas, else use single boundary
        if len(areas) == 1:
            combined_boundary = areas[0].boundary
        else:
            shapely_polys = []
            for a in areas:
                s_geom = to_shape(a.boundary)
                if isinstance(s_geom, Polygon):
                    shapely_polys.append(s_geom)
                elif isinstance(s_geom, MultiPolygon):
                    shapely_polys.extend(s_geom.geoms)
            union_geom = unary_union(shapely_polys)
            if isinstance(union_geom, Polygon):
                union_geom = MultiPolygon([union_geom])
            combined_boundary = from_shape(union_geom, srid=4326)

        primary_area_id = area_ids[0]
        layout = Layout(
            area_id=primary_area_id,
            name=data.name,
            target_hlb_building_count=target_buildings,
            actual_building_count=building_count,
            expected_hlb_count=expected_hlbs,
            boundary=combined_boundary,
            status=LayoutStatus.DRAFT,
            created_by=user_id,
        )
        db.add(layout)
        db.flush()

        # Add records to layout_administrative_areas
        for aid in area_ids:
            db.add(LayoutAdministrativeArea(layout_id=layout.id, area_id=aid))

        db.commit()
        db.refresh(layout)

        return self._format_layout_response(db, layout)

    def update_layout(
        self, db: Session, layout_id: UUID, data: LayoutUpdate
    ) -> dict:
        layout = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )

        if data.name:
            layout.name = data.name.strip()

        if data.target_buildings_per_hlb is not None:
            if data.target_buildings_per_hlb <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="target_buildings_per_hlb must be greater than 0",
                )
            layout.target_hlb_building_count = data.target_buildings_per_hlb

        if data.description is not None:
            layout.description = data.description

        new_area_ids = data.area_ids
        if new_area_ids is not None:
            if len(new_area_ids) == 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="At least one administrative area ID must be provided",
                )

            # Verify all areas exist
            areas = (
                db.query(AdministrativeArea)
                .filter(AdministrativeArea.id.in_(new_area_ids))
                .all()
            )
            if len(areas) != len(new_area_ids):
                found_ids = {a.id for a in areas}
                missing = [str(aid) for aid in new_area_ids if aid not in found_ids]
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Administrative area(s) not found: {', '.join(missing)}",
                )

            # Invariant check: cannot assign area that belongs to ANOTHER active layout
            conflicting_assoc = (
                db.query(LayoutAdministrativeArea, Layout, AdministrativeArea)
                .join(Layout, Layout.id == LayoutAdministrativeArea.layout_id)
                .join(AdministrativeArea, AdministrativeArea.id == LayoutAdministrativeArea.area_id)
                .filter(
                    LayoutAdministrativeArea.area_id.in_(new_area_ids),
                    Layout.id != layout.id,
                    Layout.status.in_(ACTIVE_LAYOUT_STATUSES),
                )
                .first()
            )
            if conflicting_assoc:
                _assoc, conf_layout, conf_area = conflicting_assoc
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Administrative area '{conf_area.name}' already belongs to active layout "
                        f"'{conf_layout.name}' ({conf_layout.status.value}). A village or ward "
                        "can belong to only one active layout at a time."
                    ),
                )

            # Check direct fallback
            conflicting_direct = (
                db.query(Layout, AdministrativeArea)
                .join(AdministrativeArea, AdministrativeArea.id == Layout.area_id)
                .filter(
                    Layout.area_id.in_(new_area_ids),
                    Layout.id != layout.id,
                    Layout.status.in_(ACTIVE_LAYOUT_STATUSES),
                )
                .first()
            )
            if conflicting_direct:
                conf_layout, conf_area = conflicting_direct
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Administrative area '{conf_area.name}' already belongs to active layout "
                        f"'{conf_layout.name}' ({conf_layout.status.value}). A village or ward "
                        "can belong to only one active layout at a time."
                    ),
                )

            # Update area associations
            db.query(LayoutAdministrativeArea).filter(
                LayoutAdministrativeArea.layout_id == layout.id
            ).delete()
            for aid in new_area_ids:
                db.add(LayoutAdministrativeArea(layout_id=layout.id, area_id=aid))
            layout.area_id = new_area_ids[0]

            # Recompute aggregated building count
            building_count = (
                db.query(House).filter(House.area_id.in_(new_area_ids)).count()
            )
            layout.actual_building_count = building_count
            target_buildings = layout.target_hlb_building_count or 250
            layout.expected_hlb_count = (
                max(1, math.ceil(building_count / target_buildings))
                if building_count > 0
                else 0
            )

            # Recompute boundary union
            if len(areas) == 1:
                layout.boundary = areas[0].boundary
            else:
                shapely_polys = []
                for a in areas:
                    if a.boundary:
                        s_geom = to_shape(a.boundary)
                        if isinstance(s_geom, Polygon):
                            shapely_polys.append(s_geom)
                        elif isinstance(s_geom, MultiPolygon):
                            shapely_polys.extend(s_geom.geoms)
                if shapely_polys:
                    union_geom = unary_union(shapely_polys)
                    if isinstance(union_geom, Polygon):
                        union_geom = MultiPolygon([union_geom])
                    layout.boundary = from_shape(union_geom, srid=4326)

        db.commit()
        db.refresh(layout)
        return self._format_layout_response(db, layout)

    def generate_hlbs(
        self,
        db: Session,
        layout_id: UUID,
        user_id: UUID | None,
        target_buildings_per_hlb: int = 250,
    ) -> dict:
        if target_buildings_per_hlb <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="target_buildings_per_hlb must be greater than 0",
            )

        layout = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )

        if layout.status == LayoutStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot regenerate HLBs for an already approved layout. "
                    "Create a new layout version."
                ),
            )

        try:
            result = hlb_generation_service.generate_candidate_hlbs(
                db=db,
                layout=layout,
                user_id=user_id,
                target_buildings_per_hlb=target_buildings_per_hlb,
            )
            return result
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        except Exception as e:
            logger.exception("HLB generation failed unexpectedly")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"HLB generation failed: {e}",
            ) from e

    def get_layout_hlbs(
        self, db: Session, layout_id: UUID, version_id: UUID | None = None
    ) -> dict:
        layout = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )

        target_version_id = version_id or layout.active_version_id
        if not target_version_id:
            # If no active version, return empty list
            return {
                "items": [],
                "total": 0,
                "layout_id": layout.id,
                "version_id": None,
            }

        hlbs = (
            db.query(HouselistingBlock)
            .filter(
                HouselistingBlock.layout_id == layout_id,
                HouselistingBlock.version_id == target_version_id,
            )
            .order_by(HouselistingBlock.block_code.asc())
            .all()
        )

        items = []
        for hlb in hlbs:
            count_dev = hlb.actual_building_count - hlb.target_building_count
            items.append(
                {
                    "id": hlb.id,
                    "layout_id": hlb.layout_id,
                    "version_id": hlb.version_id,
                    "block_code": hlb.block_code,
                    "name": hlb.name,
                    "target_building_count": hlb.target_building_count,
                    "actual_building_count": hlb.actual_building_count,
                    "count_deviation": count_dev,
                    "status": hlb.status.value,
                    "quality_score": hlb.quality_score,
                    "validation_status": hlb.validation_status.value,
                    "validation_details": hlb.validation_details,
                    "boundary": geometry_to_geojson_dict(hlb.boundary),
                    "created_at": hlb.created_at,
                    "updated_at": hlb.updated_at,
                }
            )

        return {
            "items": items,
            "total": len(items),
            "layout_id": layout.id,
            "version_id": target_version_id,
        }

    def get_layout_versions(self, db: Session, layout_id: UUID) -> dict:
        layout = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )

        versions = (
            db.query(LayoutVersion)
            .filter(LayoutVersion.layout_id == layout_id)
            .order_by(LayoutVersion.version_number.desc())
            .all()
        )

        items = []
        for version in versions:
            items.append(
                {
                    "id": version.id,
                    "layout_id": version.layout_id,
                    "version_number": version.version_number,
                    "source": version.source.value,
                    "status": version.status.value,
                    "target_buildings_per_hlb": version.target_buildings_per_hlb,
                    "total_buildings": version.total_buildings,
                    "hlb_count": version.hlb_count,
                    "quality_score": version.quality_score,
                    "validation_status": version.validation_status,
                    "validation_summary": version.validation_summary,
                    "generation_metadata": version.generation_metadata,
                    "created_by": version.created_by,
                    "created_at": version.created_at,
                }
            )

        return {"items": items, "total": len(items), "layout_id": layout.id}

    def _format_layout_response(self, db: Session, layout: Layout) -> dict:
        active_version_dict = None
        if layout.active_version_id:
            version = (
                db.query(LayoutVersion)
                .filter(LayoutVersion.id == layout.active_version_id)
                .first()
            )
            if version:
                active_version_dict = {
                    "id": version.id,
                    "layout_id": version.layout_id,
                    "version_number": version.version_number,
                    "source": version.source.value,
                    "status": version.status.value,
                    "target_buildings_per_hlb": version.target_buildings_per_hlb,
                    "total_buildings": version.total_buildings,
                    "hlb_count": version.hlb_count,
                    "quality_score": version.quality_score,
                    "validation_status": version.validation_status,
                    "validation_summary": version.validation_summary,
                    "generation_metadata": version.generation_metadata,
                    "created_by": version.created_by,
                    "created_at": version.created_at,
                }

        # Query active supervisor assignment
        active_assignment = (
            db.query(LayoutSupervisorAssignment)
            .filter(
                LayoutSupervisorAssignment.layout_id == layout.id,
                LayoutSupervisorAssignment.status == SupervisorAssignmentStatus.ACTIVE,
            )
            .first()
        )
        supervisor_id = active_assignment.supervisor_id if active_assignment else None
        supervisor_name = (
            active_assignment.supervisor.name
            if (active_assignment and active_assignment.supervisor)
            else None
        )

        # Query associated administrative areas
        area_assocs = (
            db.query(LayoutAdministrativeArea.area_id)
            .filter(LayoutAdministrativeArea.layout_id == layout.id)
            .all()
        )
        area_ids = [r[0] for r in area_assocs]
        if not area_ids and layout.area_id:
            area_ids = [layout.area_id]

        area_records = (
            db.query(AdministrativeArea.id, AdministrativeArea.name)
            .filter(AdministrativeArea.id.in_(area_ids))
            .all()
        ) if area_ids else []
        area_name_map = {r[0]: r[1] for r in area_records}
        area_names = [area_name_map[aid] for aid in area_ids if aid in area_name_map]

        return {
            "id": layout.id,
            "area_id": layout.area_id,
            "administrative_area_id": layout.area_id,
            "area_ids": area_ids,
            "area_names": area_names,
            "areas_count": len(area_ids),
            "supervisor_id": supervisor_id,
            "assigned_supervisor_name": supervisor_name,
            "name": layout.name,
            "target_buildings_per_hlb": layout.target_hlb_building_count,
            "target_houses_per_hlb": layout.target_hlb_building_count,
            "actual_building_count": layout.actual_building_count,
            "total_buildings": layout.actual_building_count,
            "expected_hlb_count": layout.expected_hlb_count,
            "hlb_count": layout.expected_hlb_count,
            "status": layout.status.value,
            "boundary": geometry_to_geojson_dict(layout.boundary),
            "active_version_id": layout.active_version_id,
            "active_version": active_version_dict,
            "active_version_number": (
                active_version_dict["version_number"] if active_version_dict else None
            ),
            "active_version_status": (
                active_version_dict["status"] if active_version_dict else None
            ),
            "created_by": layout.created_by,
            "approved_by": layout.approved_by,
            "approved_at": layout.approved_at,
            "created_at": layout.created_at,
            "updated_at": layout.updated_at,
        }


layout_service = LayoutService()
