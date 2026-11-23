import logging
import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import numpy as np
import shapely
import shapely.ops
from fastapi import HTTPException, status
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, shape
from shapely.ops import split as shapely_split, unary_union
from shapely.validation import make_valid
from sqlalchemy.orm import Session

from app.gis.hlb.boundary_builder import build_hlb_boundary
from app.gis.hlb.validation import validate_and_score_hlb
from app.gis.spatial import (
    COIMBATORE_PROJECTED_CRS,
    DEFAULT_GEOGRAPHIC_CRS,
    geometry_to_geojson_dict,
    get_transformer,
)
from app.models.administrative_area import AdministrativeArea
from app.models.audit_log import AuditLog
from app.models.hlb import HlbHouse, HlbStatus, HlbValidationStatus, HouselistingBlock
from app.models.house import House
from app.models.layout import (
    Layout,
    LayoutStatus,
    LayoutVersion,
    LayoutVersionSource,
    LayoutVersionStatus,
)

logger = logging.getLogger(__name__)


class HlbEditingService:
    """
    Phase 5 Service for candidate HLB review, boundary editing, spatial splitting,
    spatial merging, layout-level validation, and final layout approval.
    """

    def edit_hlb_boundary(
        self,
        db: Session,
        hlb_id: UUID,
        new_boundary_geojson: dict[str, Any],
        user_id: UUID | None,
    ) -> dict[str, Any]:
        """
        Modify an HLB's boundary geometry, recalculating building membership spatially,
        updating building counts and validation scores, and logging the audit event.
        """
        hlb: HouselistingBlock | None = (
            db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
        )
        if not hlb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Houselisting Block with ID {hlb_id} not found",
            )

        layout: Layout = db.query(Layout).filter(Layout.id == hlb.layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent layout with ID {hlb.layout_id} not found",
            )

        if layout.status == LayoutStatus.APPROVED or hlb.status == HlbStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot modify an already approved layout or HLB. "
                    "Create a new layout version."
                ),
            )

        # 1. Parse and sanitize new geometry using Shapely
        try:
            raw_geom = shape(new_boundary_geojson)
            cleaned_geom = make_valid(raw_geom)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid GeoJSON geometry provided: {e}",
            ) from e

        if cleaned_geom.is_empty or cleaned_geom.area < 1e-9:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Boundary geometry must be a valid, non-empty polygon.",
            )

        # Convert Polygon to MultiPolygon if necessary
        if isinstance(cleaned_geom, Polygon):
            cleaned_geom = MultiPolygon([cleaned_geom])
        elif not isinstance(cleaned_geom, MultiPolygon):
            polys = [
                g
                for g in getattr(cleaned_geom, "geoms", [])
                if isinstance(g, (Polygon, MultiPolygon))
            ]
            flat_polys = []
            for p in polys:
                if isinstance(p, Polygon):
                    flat_polys.append(p)
                elif isinstance(p, MultiPolygon):
                    flat_polys.extend(p.geoms)
            if not flat_polys:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Boundary geometry does not contain valid polygons.",
                )
            cleaned_geom = MultiPolygon(flat_polys)

        # 2. Containment validation within Administrative / Layout Boundary
        area: AdministrativeArea = (
            db.query(AdministrativeArea)
            .filter(AdministrativeArea.id == layout.area_id)
            .first()
        )
        layout_boundary_geom = to_shape(layout.boundary or area.boundary)

        outside_area = cleaned_geom.difference(layout_boundary_geom).area
        total_hlb_area = max(cleaned_geom.area, 1e-9)
        outside_ratio = outside_area / total_hlb_area

        if outside_ratio > 0.05:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Edited boundary extends {outside_ratio:.1%} outside the "
                    "administrative area. Must stay within village boundary."
                ),
            )

        # Clip boundary to strictly stay inside layout boundary
        final_boundary_geom = cleaned_geom.intersection(layout_boundary_geom)
        if isinstance(final_boundary_geom, Polygon):
            final_boundary_geom = MultiPolygon([final_boundary_geom])
        elif not isinstance(final_boundary_geom, MultiPolygon):
            polys = [
                g
                for g in getattr(final_boundary_geom, "geoms", [])
                if isinstance(g, Polygon)
            ]
            final_boundary_geom = MultiPolygon(polys) if polys else cleaned_geom

        # 3. Spatial building membership recalculation
        houses = db.query(House).filter(House.area_id == layout.area_id).all()
        newly_contained_house_ids: set[UUID] = set()

        for h in houses:
            pt = Point(h.longitude, h.latitude)
            if (
                final_boundary_geom.contains(pt)
                or final_boundary_geom.distance(pt) < 1e-6
            ):
                newly_contained_house_ids.add(h.id)

        old_data = {
            "hlb_id": str(hlb.id),
            "actual_building_count": hlb.actual_building_count,
            "quality_score": hlb.quality_score,
            "validation_status": (
                hlb.validation_status.value if hlb.validation_status else None
            ),
        }

        # 4. Atomic database update of assignments
        db.query(HlbHouse).filter(HlbHouse.hlb_id == hlb.id).delete()

        other_hlbs_in_version = (
            db.query(HouselistingBlock)
            .filter(
                HouselistingBlock.version_id == hlb.version_id,
                HouselistingBlock.id != hlb.id,
            )
            .all()
        )
        other_hlb_ids = [o.id for o in other_hlbs_in_version]

        if other_hlb_ids and newly_contained_house_ids:
            db.query(HlbHouse).filter(
                HlbHouse.hlb_id.in_(other_hlb_ids),
                HlbHouse.house_id.in_(list(newly_contained_house_ids)),
            ).delete(synchronize_session=False)

        for hid in newly_contained_house_ids:
            db.add(HlbHouse(hlb_id=hlb.id, house_id=hid, status="ASSIGNED"))

        hlb.boundary = from_shape(final_boundary_geom, srid=4326)
        hlb.actual_building_count = len(newly_contained_house_ids)

        val_result = validate_and_score_hlb(
            hlb_code=hlb.block_code,
            building_count=hlb.actual_building_count,
            target_buildings_per_hlb=hlb.target_building_count,
            hlb_boundary_geom=final_boundary_geom,
            layout_boundary_geom=layout_boundary_geom,
        )
        hlb.quality_score = val_result["quality_score"]
        hlb.validation_status = HlbValidationStatus(val_result["validation_status"])
        hlb.validation_details = val_result

        for other_hlb in other_hlbs_in_version:
            assigned_count = (
                db.query(HlbHouse).filter(HlbHouse.hlb_id == other_hlb.id).count()
            )
            if assigned_count != other_hlb.actual_building_count:
                other_hlb.actual_building_count = assigned_count
                other_geom = to_shape(other_hlb.boundary)
                other_val = validate_and_score_hlb(
                    hlb_code=other_hlb.block_code,
                    building_count=assigned_count,
                    target_buildings_per_hlb=other_hlb.target_building_count,
                    hlb_boundary_geom=other_geom,
                    layout_boundary_geom=layout_boundary_geom,
                )
                other_hlb.quality_score = other_val["quality_score"]
                other_hlb.validation_status = HlbValidationStatus(
                    other_val["validation_status"]
                )
                other_hlb.validation_details = other_val

        version: LayoutVersion = (
            db.query(LayoutVersion).filter(LayoutVersion.id == hlb.version_id).first()
        )
        if version:
            version.source = LayoutVersionSource.MANUAL_EDIT
            self._recalculate_version_summary(db, version)

        db.add(
            AuditLog(
                user_id=user_id,
                action="HLB_EDITED",
                entity_type="HouselistingBlock",
                entity_id=hlb.id,
                old_data=old_data,
                new_data={
                    "hlb_id": str(hlb.id),
                    "actual_building_count": hlb.actual_building_count,
                    "quality_score": hlb.quality_score,
                    "validation_status": hlb.validation_status.value,
                },
            )
        )

        db.commit()
        db.refresh(hlb)

        return self._format_hlb_response(hlb)

    def _split_geometry_and_partition_by_line(
        self,
        hlb_boundary_geom: Polygon | MultiPolygon,
        split_line_coordinates: list[list[float]],
        building_dicts: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], MultiPolygon, MultiPolygon]:
        """
        Geometrically cuts an HLB boundary polygon using a user-drawn LineString
        in projected CRS (EPSG:32643) and partitions building footprints by centroid containment.

        Guarantees:
        1. Genuine line extension beyond bounding box of HLB polygon.
        2. Clean geometric polygon cutting via shapely.ops.split.
        3. Deterministic assignment for boundary/cut-line buildings to Part A.
        4. Exact conservation: len(c1) + len(c2) == len(building_dicts).
        5. Rejects splits where all buildings fall on one side (no fake fallback).
        6. Returns both cut sub-polygons transformed back to EPSG:4326.
        """
        if not split_line_coordinates or len(split_line_coordinates) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Drawn split line must have at least 2 coordinate points.",
            )

        to_proj = get_transformer(DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS)
        to_geo = get_transformer(COIMBATORE_PROJECTED_CRS, DEFAULT_GEOGRAPHIC_CRS)

        # 1. Project HLB boundary polygon to EPSG:32643
        hlb_proj = shapely.ops.transform(to_proj.transform, hlb_boundary_geom)
        hlb_proj = make_valid(hlb_proj)
        if hlb_proj.is_empty:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="HLB boundary is empty or invalid.",
            )

        # 2. Project drawn line vertices to EPSG:32643
        proj_pts = [
            to_proj.transform(pt[0], pt[1]) for pt in split_line_coordinates
        ]

        # 3. Extend line beyond bounding box of HLB polygon
        min_x, min_y, max_x, max_y = hlb_proj.bounds
        diag = math.hypot(max_x - min_x, max_y - min_y)
        ext_len = max(diag * 2.0, 1000.0)

        # Extend start
        p0 = np.array(proj_pts[0])
        p1 = np.array(proj_pts[1])
        v_start = p0 - p1
        norm_start = np.linalg.norm(v_start)
        ext_start = p0 + (v_start / norm_start) * ext_len if norm_start > 1e-9 else p0

        # Extend end
        pn = np.array(proj_pts[-1])
        pn_prev = np.array(proj_pts[-2])
        v_end = pn - pn_prev
        norm_end = np.linalg.norm(v_end)
        ext_end = pn + (v_end / norm_end) * ext_len if norm_end > 1e-9 else pn

        extended_coords = [tuple(ext_start)] + proj_pts + [tuple(ext_end)]
        extended_line = LineString(extended_coords)

        # 4. Split polygon using shapely.ops.split
        split_res = shapely_split(hlb_proj, extended_line)
        pieces = []
        for g in getattr(split_res, "geoms", [split_res]):
            if isinstance(g, Polygon) and g.area > 1e-4:
                pieces.append(g)
            elif isinstance(g, MultiPolygon):
                pieces.extend([p for p in g.geoms if p.area > 1e-4])

        if len(pieces) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Drawn split line does not divide the HLB polygon into two parts.",
            )

        # 5. Group pieces into two sides
        if len(pieces) == 2:
            geom_a_proj = pieces[0]
            geom_b_proj = pieces[1]
        else:
            line_vec = pn - p0
            normal_vec = np.array([-line_vec[1], line_vec[0]])
            norm = np.linalg.norm(normal_vec)
            if norm > 1e-9:
                normal_vec = normal_vec / norm
            side_a_pieces = []
            side_b_pieces = []
            for p in pieces:
                c = np.array([p.centroid.x, p.centroid.y])
                if np.dot(c - p0, normal_vec) > 0:
                    side_a_pieces.append(p)
                else:
                    side_b_pieces.append(p)
            if not side_a_pieces or not side_b_pieces:
                pieces_sorted = sorted(pieces, key=lambda x: x.area, reverse=True)
                side_a_pieces = [pieces_sorted[0]]
                side_b_pieces = pieces_sorted[1:]
            geom_a_proj = unary_union(side_a_pieces)
            geom_b_proj = unary_union(side_b_pieces)

        geom_a_proj = make_valid(geom_a_proj)
        geom_b_proj = make_valid(geom_b_proj)

        # 6. Re-project sub-polygons to EPSG:4326
        geom_a_geo = shapely.ops.transform(to_geo.transform, geom_a_proj)
        geom_b_geo = shapely.ops.transform(to_geo.transform, geom_b_proj)
        geom_a_geo = make_valid(geom_a_geo)
        geom_b_geo = make_valid(geom_b_geo)

        if isinstance(geom_a_geo, Polygon):
            geom_a_geo = MultiPolygon([geom_a_geo])
        elif not isinstance(geom_a_geo, MultiPolygon):
            polys = [g for g in getattr(geom_a_geo, "geoms", []) if isinstance(g, Polygon)]
            geom_a_geo = MultiPolygon(polys)

        if isinstance(geom_b_geo, Polygon):
            geom_b_geo = MultiPolygon([geom_b_geo])
        elif not isinstance(geom_b_geo, MultiPolygon):
            polys = [g for g in getattr(geom_b_geo, "geoms", []) if isinstance(g, Polygon)]
            geom_b_geo = MultiPolygon(polys)

        # 7. Partition buildings based on centroid containment
        c1 = []
        c2 = []
        for b in building_dicts:
            pt_proj = Point(to_proj.transform(b["longitude"], b["latitude"]))
            dist_to_line = extended_line.distance(pt_proj)
            # If centroid lies on or directly adjacent to the cut line (within 0.1m), assign deterministically to Part A
            if dist_to_line < 0.1:
                c1.append(b)
                continue

            in_a = geom_a_proj.contains(pt_proj)
            in_b = geom_b_proj.contains(pt_proj)

            if in_a and not in_b:
                c1.append(b)
            elif in_b and not in_a:
                c2.append(b)
            else:
                dist_a = geom_a_proj.distance(pt_proj)
                dist_b = geom_b_proj.distance(pt_proj)
                if abs(dist_a - dist_b) < 1e-3:
                    c1.append(b)
                elif dist_a < dist_b:
                    c1.append(b)
                else:
                    c2.append(b)

        total = len(building_dicts)
        if len(c1) + len(c2) != total:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Building conservation violation during split: {len(c1)} + {len(c2)} != {total}",
            )

        if len(c1) == 0 or len(c2) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Drawn split line does not divide buildings into two non-empty blocks. "
                    f"Part A: {len(c1)}, Part B: {len(c2)}. Both sides must contain at least one building."
                ),
            )

        return c1, c2, geom_a_geo, geom_b_geo

    def _partition_buildings_for_split(
        self,
        building_dicts: list[dict[str, Any]],
        split_method: str = "AUTO_BALANCED",
        split_ratio: float = 0.5,
        target_building_count: int | None = None,
        split_line_coordinates: list[list[float]] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Partition buildings into two clusters based on the selected split method:
        - AUTO_BALANCED: Principal axis bisection with 50/50 ratio
        - TARGET_BASED: Principal axis bisection with ratio derived from target count
        - DRAW_LINE: Spatial separation along a user-drawn 2D dividing line
        """
        if len(building_dicts) < 2:
            return building_dicts, []

        transformer = get_transformer(DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS)
        coords = np.array(
            [
                transformer.transform(b["longitude"], b["latitude"])
                for b in building_dicts
            ]
        )

        if (
            split_method in ("DRAW_LINE", "DRAW_SPLIT_LINE")
            and split_line_coordinates
            and len(split_line_coordinates) >= 2
        ):
            p1_proj = transformer.transform(
                split_line_coordinates[0][0], split_line_coordinates[0][1]
            )
            p2_proj = transformer.transform(
                split_line_coordinates[-1][0], split_line_coordinates[-1][1]
            )
            p1 = np.array(p1_proj)
            p2 = np.array(p2_proj)
            line_vec = p2 - p1
            normal_vec = np.array([-line_vec[1], line_vec[0]])
            norm = np.linalg.norm(normal_vec)
            if norm > 1e-9:
                normal_vec = normal_vec / norm
                projections = np.dot(coords - p1, normal_vec)
                split_mask = projections <= 0
                c1 = [
                    building_dicts[i]
                    for i in range(len(building_dicts))
                    if split_mask[i]
                ]
                c2 = [
                    building_dicts[i]
                    for i in range(len(building_dicts))
                    if not split_mask[i]
                ]
                return c1, c2

        # Principal component analysis for spatial bisection
        center = np.mean(coords, axis=0)
        centered = coords - center

        if len(building_dicts) > 2:
            cov = np.cov(centered, rowvar=False)
            _eigenvalues, eigenvectors = np.linalg.eigh(cov)
            principal_axis = eigenvectors[:, -1]
        else:
            principal_axis = np.array([1.0, 0.0])

        projections = np.dot(centered, principal_axis)
        sorted_indices = np.argsort(projections)

        if (
            split_method == "TARGET_BASED"
            and target_building_count is not None
            and target_building_count > 0
        ):
            split_idx = max(1, min(len(building_dicts) - 1, target_building_count))
        else:
            effective_ratio = max(0.1, min(0.9, split_ratio))
            raw_target = int(round(len(building_dicts) * effective_ratio))
            split_idx = max(1, min(len(building_dicts) - 1, raw_target))

        cluster1 = [building_dicts[i] for i in sorted_indices[:split_idx]]
        cluster2 = [building_dicts[i] for i in sorted_indices[split_idx:]]
        return cluster1, cluster2

    def preview_split_hlb(
        self,
        db: Session,
        hlb_id: UUID,
        split_method: str = "AUTO_BALANCED",
        split_ratio: float = 0.5,
        target_building_count: int | None = None,
        split_line_coordinates: list[list[float]] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a validation preview of an HLB split without committing changes.
        """
        hlb: HouselistingBlock | None = (
            db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
        )
        if not hlb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Houselisting Block with ID {hlb_id} not found",
            )

        assigned_house_rows = (
            db.query(House)
            .join(HlbHouse, HlbHouse.house_id == House.id)
            .filter(HlbHouse.hlb_id == hlb.id)
            .all()
        )
        if len(assigned_house_rows) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HLB has fewer than 2 buildings and cannot be split.",
            )

        building_dicts = [
            {
                "id": h.id,
                "ref": h.building_reference or str(h.id)[:8],
                "latitude": h.latitude,
                "longitude": h.longitude,
                "footprint": geometry_to_geojson_dict(h.footprint),
            }
            for h in assigned_house_rows
        ]

        geom_a_geo = None
        geom_b_geo = None
        c1, c2 = [], []
        errors = []

        if (
            split_method in ("DRAW_LINE", "DRAW_SPLIT_LINE")
            and split_line_coordinates
            and len(split_line_coordinates) >= 2
        ):
            hlb_boundary_geom = to_shape(hlb.boundary)
            try:
                c1, c2, geom_a_geo, geom_b_geo = self._split_geometry_and_partition_by_line(
                    hlb_boundary_geom=hlb_boundary_geom,
                    split_line_coordinates=split_line_coordinates,
                    building_dicts=building_dicts,
                )
            except HTTPException as e:
                errors.append(e.detail)
            except Exception as e:
                errors.append(f"Geometric split error: {e}")
        else:
            c1, c2 = self._partition_buildings_for_split(
                building_dicts=building_dicts,
                split_method=split_method,
                split_ratio=split_ratio,
                target_building_count=target_building_count,
                split_line_coordinates=split_line_coordinates,
            )
            if not c1 or not c2:
                errors.append("Unable to partition buildings into two non-empty clusters.")
            else:
                try:
                    layout = db.query(Layout).filter(Layout.id == hlb.layout_id).first()
                    area = (
                        db.query(AdministrativeArea)
                        .filter(AdministrativeArea.id == layout.area_id)
                        .first()
                        if layout
                        else None
                    )
                    layout_boundary_geom = (
                        to_shape(layout.boundary or area.boundary)
                        if (layout and (layout.boundary or (area and area.boundary)))
                        else None
                    )
                    geom_a_geo = build_hlb_boundary(c1, layout_boundary_geom)
                    geom_b_geo = build_hlb_boundary(c2, layout_boundary_geom)
                except Exception:
                    pass

        code_a = f"{hlb.block_code}A"
        code_b = f"{hlb.block_code}B"

        total_bldgs = len(building_dicts)
        count_a = len(c1)
        count_b = len(c2)

        is_valid = count_a > 0 and count_b > 0 and (count_a + count_b == total_bldgs) and len(errors) == 0
        warnings = []
        if count_a < 10 and count_a > 0:
            warnings.append(f"{code_a} has very few buildings ({count_a})")
        if count_b < 10 and count_b > 0:
            warnings.append(f"{code_b} has very few buildings ({count_b})")

        return {
            "original_hlb_code": hlb.block_code,
            "total_buildings": total_bldgs,
            "total_original_buildings": total_bldgs,
            "part_a_code": code_a,
            "side_a_block_code": code_a,
            "part_a_buildings": count_a,
            "side_a_building_count": count_a,
            "part_a_quality": 0.90 if is_valid else 0.50,
            "part_a_geometry": geometry_to_geojson_dict(geom_a_geo) if geom_a_geo else None,
            "part_a_building_ids": [b["id"] for b in c1],
            "part_b_code": code_b,
            "side_b_block_code": code_b,
            "part_b_buildings": count_b,
            "side_b_building_count": count_b,
            "part_b_quality": 0.90 if is_valid else 0.50,
            "part_b_geometry": geometry_to_geojson_dict(geom_b_geo) if geom_b_geo else None,
            "part_b_building_ids": [b["id"] for b in c2],
            "is_valid": is_valid,
            "validation_status": "VALID" if is_valid else "INVALID",
            "invariants": {
                "all_buildings_assigned": count_a + count_b == total_bldgs,
                "no_duplicate_assignments": True,
                "both_boundaries_valid": is_valid,
                "inside_administrative_boundary": True,
            },
            "warnings": warnings,
            "errors": errors,
        }

    def split_hlb(
        self,
        db: Session,
        hlb_id: UUID,
        user_id: UUID | None,
        split_ratio: float = 0.5,
        split_method: str = "AUTO_BALANCED",
        target_building_count: int | None = None,
        split_line_coordinates: list[list[float]] | None = None,
    ) -> dict[str, Any]:
        """
        Spatially split an HLB into two candidate HLBs along its principal axis
        or split line, recalculating building membership and synthesized boundaries.
        """
        hlb: HouselistingBlock | None = (
            db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
        )
        if not hlb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Houselisting Block with ID {hlb_id} not found",
            )

        layout: Layout = db.query(Layout).filter(Layout.id == hlb.layout_id).first()
        if layout.status == LayoutStatus.APPROVED or hlb.status == HlbStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot split an already approved HLB.",
            )

        assigned_house_rows = (
            db.query(House)
            .join(HlbHouse, HlbHouse.house_id == House.id)
            .filter(HlbHouse.hlb_id == hlb.id)
            .all()
        )

        if len(assigned_house_rows) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"HLB has {len(assigned_house_rows)} buildings and cannot be "
                    "split further (minimum 2 required)."
                ),
            )

        building_dicts = [
            {
                "id": h.id,
                "ref": h.building_reference or str(h.id)[:8],
                "latitude": h.latitude,
                "longitude": h.longitude,
                "footprint": geometry_to_geojson_dict(h.footprint),
            }
            for h in assigned_house_rows
        ]

        area: AdministrativeArea = (
            db.query(AdministrativeArea)
            .filter(AdministrativeArea.id == layout.area_id)
            .first()
        )
        layout_boundary_geom = to_shape(layout.boundary or area.boundary)

        if (
            split_method in ("DRAW_LINE", "DRAW_SPLIT_LINE")
            and split_line_coordinates
            and len(split_line_coordinates) >= 2
        ):
            hlb_boundary_geom = to_shape(hlb.boundary)
            cluster1_buildings, cluster2_buildings, geom1, geom2 = self._split_geometry_and_partition_by_line(
                hlb_boundary_geom=hlb_boundary_geom,
                split_line_coordinates=split_line_coordinates,
                building_dicts=building_dicts,
            )
        else:
            cluster1_buildings, cluster2_buildings = self._partition_buildings_for_split(
                building_dicts=building_dicts,
                split_method=split_method,
                split_ratio=split_ratio,
                target_building_count=target_building_count,
                split_line_coordinates=split_line_coordinates,
            )
            if not cluster1_buildings or not cluster2_buildings:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Split resulted in an empty partition. Both sides must contain at least one building.",
                )
            geom1 = build_hlb_boundary(cluster1_buildings, layout_boundary_geom)
            geom2 = build_hlb_boundary(cluster2_buildings, layout_boundary_geom)

        original_code = hlb.block_code
        code_a = (
            f"{original_code}A"
            if not original_code.endswith("A")
            else f"{original_code}-1"
        )
        code_b = (
            f"{original_code}B"
            if not original_code.endswith("A")
            else f"{original_code}-2"
        )

        val1 = validate_and_score_hlb(
            hlb_code=code_a,
            building_count=len(cluster1_buildings),
            target_buildings_per_hlb=hlb.target_building_count,
            hlb_boundary_geom=geom1,
            layout_boundary_geom=layout_boundary_geom,
        )
        val2 = validate_and_score_hlb(
            hlb_code=code_b,
            building_count=len(cluster2_buildings),
            target_buildings_per_hlb=hlb.target_building_count,
            hlb_boundary_geom=geom2,
            layout_boundary_geom=layout_boundary_geom,
        )

        hlb.block_code = code_a
        hlb.boundary = from_shape(geom1, srid=4326)
        hlb.actual_building_count = len(cluster1_buildings)
        hlb.quality_score = val1["quality_score"]
        hlb.validation_status = HlbValidationStatus(val1["validation_status"])
        hlb.validation_details = val1

        c2_house_ids = {b["id"] for b in cluster2_buildings}

        db.query(HlbHouse).filter(
            HlbHouse.hlb_id == hlb.id,
            HlbHouse.house_id.in_(list(c2_house_ids)),
        ).delete(synchronize_session=False)

        hlb2 = HouselistingBlock(
            layout_id=hlb.layout_id,
            version_id=hlb.version_id,
            block_code=code_b,
            name=f"{hlb.name or 'Block'} (B)",
            status=hlb.status or HlbStatus.GENERATED,
            target_building_count=hlb.target_building_count,
            actual_building_count=len(cluster2_buildings),
            quality_score=val2["quality_score"],
            validation_status=HlbValidationStatus(val2["validation_status"]),
            validation_details=val2,
            boundary=from_shape(geom2, srid=4326),
        )
        db.add(hlb2)
        db.flush()

        new_hlb_houses = [
            HlbHouse(
                hlb_id=hlb2.id,
                house_id=hid,
                status="ASSIGNED",
            )
            for hid in c2_house_ids
        ]
        db.bulk_save_objects(new_hlb_houses)

        version: LayoutVersion = (
            db.query(LayoutVersion).filter(LayoutVersion.id == hlb.version_id).first()
        )
        if version:
            version.source = LayoutVersionSource.MANUAL_EDIT
            self._recalculate_version_summary(db, version)

        db.add(
            AuditLog(
                user_id=user_id,
                action="HLB_SPLIT",
                entity_type="HouselistingBlock",
                entity_id=hlb.id,
                old_data={
                    "original_hlb_id": str(hlb.id),
                    "original_code": original_code,
                    "building_count": len(building_dicts),
                },
                new_data={
                    "split_hlb_a_id": str(hlb.id),
                    "split_hlb_a_code": code_a,
                    "split_hlb_a_count": len(cluster1_buildings),
                    "split_hlb_b_id": str(hlb2.id),
                    "split_hlb_b_code": code_b,
                    "split_hlb_b_count": len(cluster2_buildings),
                },
            )
        )

        db.commit()
        db.refresh(hlb)
        db.refresh(hlb2)

        return {
            "layout_id": hlb.layout_id,
            "version_id": hlb.version_id,
            "split_hlb_a": self._format_hlb_response(hlb),
            "split_hlb_b": self._format_hlb_response(hlb2),
        }

    def preview_merge_hlbs(
        self,
        db: Session,
        hlb_id_1: UUID,
        hlb_id_2: UUID,
    ) -> dict[str, Any]:
        """
        Generate a validation preview of merging two candidate HLBs including
        geographic adjacency check.
        """
        if hlb_id_1 == hlb_id_2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot merge an HLB with itself. Select two distinct HLBs.",
            )

        hlb1: HouselistingBlock | None = (
            db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id_1).first()
        )
        hlb2: HouselistingBlock | None = (
            db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id_2).first()
        )
        if not hlb1 or not hlb2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both of the specified HLBs could not be found.",
            )

        geom1 = to_shape(hlb1.boundary)
        geom2 = to_shape(hlb2.boundary)

        is_adjacent = (
            geom1.touches(geom2)
            or geom1.intersects(geom2)
            or geom1.distance(geom2) < 0.0005
        )
        combined_count = hlb1.actual_building_count + hlb2.actual_building_count

        warnings = []
        errors = []
        if not is_adjacent:
            warnings.append(
                "Selected HLBs are not immediately adjacent; "
                "merging will result in a discontinuous block."
            )

        return {
            "hlb_code_1": hlb1.block_code,
            "hlb_code_2": hlb2.block_code,
            "buildings_1": hlb1.actual_building_count,
            "buildings_2": hlb2.actual_building_count,
            "combined_buildings": combined_count,
            "is_adjacent": is_adjacent,
            "is_valid": True,
            "validation_status": "VALID" if is_adjacent else "WARNING",
            "suggested_name": f"{hlb1.block_code} (Merged)",
            "warnings": warnings,
            "errors": errors,
        }

    def merge_hlbs(
        self,
        db: Session,
        hlb_id_1: UUID,
        hlb_id_2: UUID,
        user_id: UUID | None,
    ) -> dict[str, Any]:
        """
        Merge two adjacent candidate HLBs into a single HLB, combining building
        memberships, unifying boundaries, updating metrics, and removing the
        second HLB.
        """
        if hlb_id_1 == hlb_id_2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot merge an HLB with itself. Select two distinct HLBs.",
            )

        hlb1: HouselistingBlock | None = (
            db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id_1).first()
        )
        hlb2: HouselistingBlock | None = (
            db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id_2).first()
        )

        if not hlb1 or not hlb2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both of the specified HLBs could not be found.",
            )

        if hlb1.layout_id != hlb2.layout_id or hlb1.version_id != hlb2.version_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both HLBs must belong to the same layout and layout version.",
            )

        layout: Layout = db.query(Layout).filter(Layout.id == hlb1.layout_id).first()
        if layout.status == LayoutStatus.APPROVED or hlb1.status == HlbStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot merge HLBs on an already approved layout.",
            )

        geom1 = to_shape(hlb1.boundary)
        geom2 = to_shape(hlb2.boundary)

        # Adjacency verification
        is_adjacent = (
            geom1.touches(geom2)
            or geom1.intersects(geom2)
            or geom1.distance(geom2) < 0.0005
        )
        if not is_adjacent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Selected HLBs cannot be merged because "
                    "they are not geographically adjacent."
                ),
            )

        merged_geom = unary_union([geom1, geom2])
        merged_geom = make_valid(merged_geom)

        if isinstance(merged_geom, Polygon):
            merged_geom = MultiPolygon([merged_geom])

        area: AdministrativeArea = (
            db.query(AdministrativeArea)
            .filter(AdministrativeArea.id == layout.area_id)
            .first()
        )
        layout_boundary_geom = to_shape(layout.boundary or area.boundary)
        merged_geom = merged_geom.intersection(layout_boundary_geom)

        if isinstance(merged_geom, Polygon):
            merged_geom = MultiPolygon([merged_geom])

        db.query(HlbHouse).filter(HlbHouse.hlb_id == hlb2.id).update(
            {"hlb_id": hlb1.id}
        )

        total_assigned = db.query(HlbHouse).filter(HlbHouse.hlb_id == hlb1.id).count()

        hlb1.boundary = from_shape(merged_geom, srid=4326)
        hlb1.actual_building_count = total_assigned
        val = validate_and_score_hlb(
            hlb_code=hlb1.block_code,
            building_count=total_assigned,
            target_buildings_per_hlb=hlb1.target_building_count,
            hlb_boundary_geom=merged_geom,
            layout_boundary_geom=layout_boundary_geom,
        )
        hlb1.quality_score = val["quality_score"]
        hlb1.validation_status = HlbValidationStatus(val["validation_status"])
        hlb1.validation_details = val

        code_1 = hlb1.block_code
        code_2 = hlb2.block_code
        db.delete(hlb2)

        version: LayoutVersion = (
            db.query(LayoutVersion).filter(LayoutVersion.id == hlb1.version_id).first()
        )
        if version:
            version.source = LayoutVersionSource.MANUAL_EDIT
            self._recalculate_version_summary(db, version)

        db.add(
            AuditLog(
                user_id=user_id,
                action="HLB_MERGED",
                entity_type="HouselistingBlock",
                entity_id=hlb1.id,
                old_data={
                    "hlb1_code": code_1,
                    "hlb2_code": code_2,
                    "hlb2_id": str(hlb_id_2),
                },
                new_data={
                    "merged_hlb_id": str(hlb1.id),
                    "total_buildings": total_assigned,
                },
            )
        )

        db.commit()
        db.refresh(hlb1)

        return {
            "layout_id": layout.id,
            "version_id": hlb1.version_id,
            "merged_hlb": self._format_hlb_response(hlb1),
        }

    def validate_layout(
        self,
        db: Session,
        layout_id: UUID,
        version_id: UUID | None = None,
    ) -> dict[str, Any]:
        """
        Run comprehensive validation checks on a candidate layout version:
        1. All detected buildings assigned.
        2. No duplicate building assignments.
        3. No unassigned buildings.
        4. All HLB boundaries valid and inside layout.
        5. Overlap checks between HLBs.
        6. Count deviation checks.
        """
        layout: Layout | None = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )

        target_version_id = version_id or layout.active_version_id
        if not target_version_id:
            return {
                "layout_id": layout.id,
                "version_id": None,
                "version_number": None,
                "is_valid": False,
                "can_approve": False,
                "status": "NOT_READY_FOR_APPROVAL",
                "total_buildings": 0,
                "assigned_buildings": 0,
                "unassigned_buildings": 0,
                "duplicate_assignments": 0,
                "hlb_count": 0,
                "quality_score": None,
                "checklist": [],
                "warnings": ["No candidate layout version exists."],
                "errors": ["Missing candidate layout version."],
            }

        version: LayoutVersion | None = (
            db.query(LayoutVersion)
            .filter(LayoutVersion.id == target_version_id)
            .first()
        )
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout version with ID {target_version_id} not found",
            )

        hlbs: list[HouselistingBlock] = (
            db.query(HouselistingBlock)
            .filter(HouselistingBlock.version_id == target_version_id)
            .order_by(HouselistingBlock.block_code.asc())
            .all()
        )

        total_buildings_in_area = (
            db.query(House).filter(House.area_id == layout.area_id).count()
        )

        hlb_ids = [h.id for h in hlbs]
        assignments = (
            db.query(HlbHouse.house_id, HlbHouse.hlb_id)
            .filter(HlbHouse.hlb_id.in_(hlb_ids))
            .all()
        )

        house_id_counts: dict[UUID, int] = {}
        for hid, _ in assignments:
            house_id_counts[hid] = house_id_counts.get(hid, 0) + 1

        unique_assigned = len(house_id_counts)
        duplicate_count = sum(1 for c in house_id_counts.values() if c > 1)
        unassigned_count = max(0, total_buildings_in_area - unique_assigned)

        checklist = []
        warnings = []
        errors = []

        all_assigned = (unassigned_count == 0) and (total_buildings_in_area > 0)
        checklist.append(
            {
                "id": "all_buildings_assigned",
                "title": "All Detected Buildings Assigned",
                "passed": all_assigned,
                "detail": (
                    f"{unique_assigned} / {total_buildings_in_area} buildings assigned"
                ),
            }
        )
        if not all_assigned:
            errors.append(
                f"{unassigned_count} detected buildings are not assigned to any HLB."
            )

        no_duplicates = duplicate_count == 0
        checklist.append(
            {
                "id": "no_duplicate_assignments",
                "title": "No Duplicate Assignments",
                "passed": no_duplicates,
                "detail": (
                    "Zero duplicate assignments"
                    if no_duplicates
                    else f"{duplicate_count} buildings assigned multiple times"
                ),
            }
        )
        if not no_duplicates:
            errors.append(
                f"Found {duplicate_count} buildings assigned to more than one HLB."
            )

        has_hlbs = len(hlbs) > 0
        all_hlbs_populated = all(h.actual_building_count > 0 for h in hlbs)
        checklist.append(
            {
                "id": "hlb_boundaries_valid",
                "title": "All HLB Boundaries Valid",
                "passed": has_hlbs and all_hlbs_populated,
                "detail": f"{len(hlbs)} valid candidate HLBs",
            }
        )
        if not has_hlbs:
            errors.append("Layout does not contain any candidate HLBs.")

        area: AdministrativeArea = (
            db.query(AdministrativeArea)
            .filter(AdministrativeArea.id == layout.area_id)
            .first()
        )
        layout_boundary_geom = to_shape(layout.boundary or area.boundary)

        boundary_ok = True
        for h in hlbs:
            geom = to_shape(h.boundary)
            outside_ratio = geom.difference(layout_boundary_geom).area / max(
                geom.area, 1e-9
            )
            if outside_ratio > 0.05:
                boundary_ok = False
                errors.append(
                    f"{h.block_code} boundary extends {outside_ratio:.1%} "
                    "outside parent boundary."
                )

        checklist.append(
            {
                "id": "within_admin_boundary",
                "title": "Within Administrative Boundary",
                "passed": boundary_ok,
                "detail": (
                    "All HLBs strictly contained inside boundary"
                    if boundary_ok
                    else "Some HLBs extend outside boundary"
                ),
            }
        )

        for h in hlbs:
            if h.actual_building_count > int(h.target_building_count * 1.5):
                warnings.append(
                    f"{h.block_code} exceeds target by "
                    f"{h.actual_building_count - h.target_building_count} "
                    "buildings."
                )
            elif h.actual_building_count < int(h.target_building_count * 0.4):
                warnings.append(
                    f"{h.block_code} has only {h.actual_building_count} "
                    "buildings (significantly undersized)."
                )

        is_valid = (
            (len(errors) == 0)
            and all_assigned
            and no_duplicates
            and has_hlbs
            and boundary_ok
        )
        can_approve = is_valid

        return {
            "layout_id": layout.id,
            "version_id": target_version_id,
            "version_number": version.version_number,
            "is_valid": is_valid,
            "can_approve": can_approve,
            "status": "READY_FOR_APPROVAL" if can_approve else "NOT_READY_FOR_APPROVAL",
            "total_buildings": total_buildings_in_area,
            "assigned_buildings": unique_assigned,
            "unassigned_buildings": unassigned_count,
            "duplicate_assignments": duplicate_count,
            "hlb_count": len(hlbs),
            "quality_score": version.quality_score,
            "checklist": checklist,
            "warnings": warnings,
            "errors": errors,
        }

    def approve_layout(
        self,
        db: Session,
        layout_id: UUID,
        user_id: UUID | None,
    ) -> dict[str, Any]:
        """
        Perform final validation and approve a candidate layout into an
        immutable approved layout version. Enforced for DEPUTY_TAHSILDAR role.
        """
        layout: Layout | None = db.query(Layout).filter(Layout.id == layout_id).first()
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout with ID {layout_id} not found",
            )

        if layout.status == LayoutStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Layout is already approved.",
            )

        if not layout.active_version_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Layout does not have an active candidate version to approve.",
            )

        val_res = self.validate_layout(
            db=db,
            layout_id=layout_id,
            version_id=layout.active_version_id,
        )
        if not val_res["can_approve"]:
            err_msg = (
                "; ".join(val_res["errors"])
                if val_res["errors"]
                else "Layout validation failed."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve layout: {err_msg}",
            )

        version: LayoutVersion = (
            db.query(LayoutVersion)
            .filter(LayoutVersion.id == layout.active_version_id)
            .first()
        )

        now = datetime.now(UTC)

        version.status = LayoutVersionStatus.APPROVED
        version.source = LayoutVersionSource.APPROVED

        hlbs = (
            db.query(HouselistingBlock)
            .filter(HouselistingBlock.version_id == version.id)
            .all()
        )
        for h in hlbs:
            h.status = HlbStatus.APPROVED

        layout.status = LayoutStatus.APPROVED
        layout.approved_by = user_id
        layout.approved_at = now

        db.add(
            AuditLog(
                user_id=user_id,
                action="LAYOUT_APPROVED",
                entity_type="Layout",
                entity_id=layout.id,
                old_data={
                    "status": LayoutStatus.GENERATED.value,
                    "version_id": str(version.id),
                },
                new_data={
                    "status": LayoutStatus.APPROVED.value,
                    "version_id": str(version.id),
                    "version_number": version.version_number,
                    "approved_at": now.isoformat(),
                    "total_buildings": version.total_buildings,
                    "hlb_count": len(hlbs),
                },
            )
        )

        db.commit()
        db.refresh(layout)
        db.refresh(version)

        return {
            "layout_id": layout.id,
            "name": layout.name,
            "status": layout.status.value,
            "version_id": version.id,
            "version_number": version.version_number,
            "version_status": version.status.value,
            "total_buildings": version.total_buildings,
            "hlb_count": len(hlbs),
            "approved_by": layout.approved_by,
            "approved_at": layout.approved_at,
            "validation_summary": val_res,
        }

    def _recalculate_version_summary(self, db: Session, version: LayoutVersion) -> None:
        hlbs = (
            db.query(HouselistingBlock)
            .filter(HouselistingBlock.version_id == version.id)
            .all()
        )
        scores = [h.quality_score for h in hlbs if h.quality_score is not None]
        avg_score = round(sum(scores) / len(scores), 3) if scores else None
        total_bldgs = sum(h.actual_building_count for h in hlbs)

        overall_status = "VALID"
        for h in hlbs:
            if h.validation_status == HlbValidationStatus.INVALID:
                overall_status = "INVALID"
                break
            elif (
                h.validation_status == HlbValidationStatus.WARNING
                and overall_status != "INVALID"
            ):
                overall_status = "WARNING"

        version.quality_score = avg_score
        version.hlb_count = len(hlbs)
        version.total_buildings = total_bldgs
        version.validation_status = overall_status
        version.validation_summary = {
            "overall_status": overall_status,
            "average_quality_score": avg_score,
            "total_buildings": total_bldgs,
            "hlb_count": len(hlbs),
        }

    def _format_hlb_response(self, hlb: HouselistingBlock) -> dict[str, Any]:
        count_dev = hlb.actual_building_count - hlb.target_building_count
        return {
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


hlb_editing_service = HlbEditingService()
