import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point, shape
from shapely.strtree import STRtree
from sqlalchemy.orm import Session

from app.gis.hlb.boundary_builder import build_partitioned_hlb_boundaries
from app.gis.hlb.quality_metrics import get_osm_road_segments_tree
from app.gis.hlb.validation import (
    recalculate_exact_building_counts,
    validate_and_score_hlb,
    validate_layout_partition_geometry,
)
from app.gis.spatial import COIMBATORE_PROJECTED_CRS, geometry_to_geojson_dict
from app.models.administrative_area import AdministrativeArea, BoundaryStatus
from app.models.hlb import HlbHouse, HlbStatus, HlbValidationStatus, HouselistingBlock
from app.models.house import House
from app.models.layout import (
    Layout,
    LayoutAdministrativeArea,
    LayoutStatus,
    LayoutVersion,
    LayoutVersionSource,
    LayoutVersionStatus,
)

logger = logging.getLogger(__name__)


class HlbGenerationService:
    """
    AI-Assisted GIS & Spatial Optimization HLB Generation Service.
    Orchestrates building loading, projected spatial clustering, territory partitioning,
    quality scoring, exact building counting, geometry validation, and candidate layout versioning.
    """

    def generate_candidate_hlbs(
        self,
        db: Session,
        layout: Layout,
        user_id: UUID | None,
        target_buildings_per_hlb: int = 250,
        workload_unit: str = "BUILDINGS",
    ) -> dict[str, Any]:
        """
        Generate candidate HLBs for a Layout using real building records
        and Deputy Tahsildar's requested target_buildings_per_hlb.
        Executed in an atomic database transaction.
        """
        # 1. Load Administrative Area & Boundary
        area: AdministrativeArea | None = (
            db.query(AdministrativeArea)
            .filter(AdministrativeArea.id == layout.area_id)
            .first()
        )
        if not area:
            raise ValueError(
                f"Administrative area {layout.area_id} not found for layout"
            )

        # Boundary Guard: HLB generation must refuse to run unless boundary_status is OFFICIAL or PROVISIONAL
        boundary_status = getattr(area, "boundary_status", None) or BoundaryStatus.PROVISIONAL.value
        allowed_statuses = {BoundaryStatus.OFFICIAL.value, BoundaryStatus.PROVISIONAL.value}
        if boundary_status not in allowed_statuses:
            raise ValueError(
                f"HLB generation rejected: Administrative area '{area.name}' has boundary status '{boundary_status}'. "
                "Boundary status must be OFFICIAL or PROVISIONAL before running AI HLB generation."
            )

        layout_boundary_geom = to_shape(layout.boundary or area.boundary)

        # 2. Load Real Building Records (supporting multi-area layouts)
        assoc_area_ids = [
            r[0]
            for r in db.query(LayoutAdministrativeArea.area_id)
            .filter(LayoutAdministrativeArea.layout_id == layout.id)
            .all()
        ]
        target_area_ids = assoc_area_ids if assoc_area_ids else [layout.area_id]

        house_rows = (
            db.query(
                House.id,
                House.building_reference,
                House.latitude,
                House.longitude,
                House.source_type,
                House.footprint,
            )
            .filter(House.area_id.in_(target_area_ids))
            .order_by(House.created_at.asc())
            .all()
        )

        if not house_rows:
            raise ValueError(
                f"No building records available for administrative area '{area.name}'. "
                "Run satellite building detection before generating HLBs."
            )

        raw_building_dicts = []
        for r in house_rows:
            raw_building_dicts.append(
                {
                    "id": r.id,
                    "ref": r.building_reference or str(r.id)[:8],
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "source_type": r.source_type,
                    "footprint": geometry_to_geojson_dict(r.footprint),
                }
            )

        raw_total_buildings = len(raw_building_dicts)

        # Clip building centroids to administrative boundary
        clipped_buildings = []
        for b in raw_building_dicts:
            pt = Point(b["longitude"], b["latitude"])
            if layout_boundary_geom.contains(pt) or layout_boundary_geom.touches(pt):
                clipped_buildings.append(b)

        total_buildings = len(clipped_buildings)
        clipped_out_count = raw_total_buildings - total_buildings

        logger.info(
            "Clipped building footprints for area '%s': %d inside boundary (%s), %d outside bbox discarded",
            area.name,
            total_buildings,
            boundary_status,
            clipped_out_count,
        )

        if not clipped_buildings:
            raise ValueError(
                f"No building centroids fall inside the boundary for '{area.name}' ({raw_total_buildings} evaluated)."
            )

        # Spatial indices for per-HLB quality metrics
        road_data = get_osm_road_segments_tree()
        road_tree = road_data[1] if road_data else None

        footprint_shapes = []
        for b in clipped_buildings:
            fp = b.get("footprint")
            if fp:
                try:
                    s = shape(fp)
                    if s.is_valid:
                        footprint_shapes.append(s)
                except Exception:
                    pass
        footprint_tree = STRtree(footprint_shapes) if footprint_shapes else None

        # 3. Territory and Spatial Partitioning in projected metric CRS
        partitions = build_partitioned_hlb_boundaries(
            buildings=clipped_buildings,
            layout_boundary_geom=layout_boundary_geom,
            target_buildings_per_hlb=target_buildings_per_hlb,
            projected_crs=COIMBATORE_PROJECTED_CRS,
        )

        hlb_boundaries = [p[0] for p in partitions]

        # 4. Exact Point-in-Polygon Building Assignment & Invariant Verification
        exact_counts = recalculate_exact_building_counts(
            hlb_boundaries=hlb_boundaries,
            buildings=clipped_buildings,
            target_buildings_per_hlb=target_buildings_per_hlb,
        )

        # 5. Comprehensive Territory Partition Geometry Validation
        geom_val = validate_layout_partition_geometry(
            hlb_boundaries=hlb_boundaries,
            layout_boundary_geom=layout_boundary_geom,
            projected_crs=COIMBATORE_PROJECTED_CRS,
        )

        # 6. Determine next version number
        last_version: LayoutVersion | None = (
            db.query(LayoutVersion)
            .filter(LayoutVersion.layout_id == layout.id)
            .order_by(LayoutVersion.version_number.desc())
            .first()
        )
        next_version_num = (last_version.version_number + 1) if last_version else 1

        # 7. Mark prior CANDIDATE versions as SUPERSEDED
        db.query(LayoutVersion).filter(
            LayoutVersion.layout_id == layout.id,
            LayoutVersion.status == LayoutVersionStatus.CANDIDATE,
        ).update({"status": LayoutVersionStatus.SUPERSEDED})

        # 8. Create LayoutVersion record with Deputy's target
        layout_version = LayoutVersion(
            layout_id=layout.id,
            version_number=next_version_num,
            source=LayoutVersionSource.AI_GENERATED,
            status=LayoutVersionStatus.CANDIDATE,
            target_buildings_per_hlb=target_buildings_per_hlb,
            workload_unit=workload_unit,
            target_workload=target_buildings_per_hlb,
            estimation_method="CENSUS_2011_PCA_RATIO",
            estimation_provenance="Census of India 2011 Primary Census Abstract (Arasur CT 644401): 3,306 HH / 10,583 footprints (0.312 HH/footprint, 3.48 persons/HH)",
            total_buildings=total_buildings,
            hlb_count=len(partitions),
            boundary_status=boundary_status,
            created_by=user_id,
            generation_metadata={
                "algorithm": "recursive_spatial_bisection_projected_v2",
                "projected_crs": COIMBATORE_PROJECTED_CRS,
                "generated_at": datetime.now(UTC).isoformat(),
                "boundary_status": boundary_status,
                "raw_bbox_building_count": raw_total_buildings,
                "inside_boundary_building_count": total_buildings,
                "clipped_outside_count": clipped_out_count,
                "building_dataset_count": total_buildings,
                "target_buildings_per_hlb": target_buildings_per_hlb,
                "exact_counts_summary": {
                    "total_input_buildings": exact_counts["total_input_buildings"],
                    "accepted_buildings": exact_counts["accepted_buildings"],
                    "rejected_buildings": exact_counts["rejected_buildings"],
                    "hlb_count": exact_counts["hlb_count"],
                    "average_count": exact_counts["average_count"],
                    "min_count": exact_counts["min_count"],
                    "max_count": exact_counts["max_count"],
                    "deviation_from_target": exact_counts["deviation_from_target"],
                    "unassigned_count": exact_counts["unassigned_count"],
                    "duplicate_count": exact_counts["duplicate_count"],
                },
                "partition_geometry_validation": geom_val,
            },
        )
        db.add(layout_version)
        db.flush()  # Generate layout_version.id

        # 9. Build Candidate HLBs, boundaries, and validation scores
        created_hlb_schemas = []
        hlb_quality_scores = []
        overall_validation_status = "VALID"
        k_count = len(partitions)
        total_est_ch = 0
        total_est_pop = 0

        for idx, (boundary_geom, _) in enumerate(partitions):
            block_code = f"HLB-{idx + 1:03d}"
            cluster = exact_counts["assigned_clusters"][idx]
            cluster_count = len(cluster)
            hlb_est_ch = int(round(cluster_count * 0.3124))
            hlb_est_pop = int(round(hlb_est_ch * 3.48))
            total_est_ch += hlb_est_ch
            total_est_pop += hlb_est_pop

            cluster_target = (
                (total_buildings + k_count - (idx + 1)) // k_count
                if k_count > 0
                else target_buildings_per_hlb
            )

            boundary_wkb = from_shape(boundary_geom, srid=4326)

            # Validate & Score against Deputy's target limit, balanced target size, and quality metrics
            val_result = validate_and_score_hlb(
                hlb_code=block_code,
                building_count=cluster_count,
                target_buildings_per_hlb=target_buildings_per_hlb,
                hlb_boundary_geom=boundary_geom,
                layout_boundary_geom=layout_boundary_geom,
                balanced_target_size=cluster_target,
                cluster_buildings=cluster,
                all_footprints_tree=footprint_tree,
                road_tree=road_tree,
            )

            val_status = HlbValidationStatus(val_result["validation_status"])
            if val_status == HlbValidationStatus.INVALID:
                overall_validation_status = "INVALID"
            elif (
                val_status == HlbValidationStatus.WARNING
                and overall_validation_status != "INVALID"
            ):
                overall_validation_status = "WARNING"

            hlb_record = HouselistingBlock(
                layout_id=layout.id,
                version_id=layout_version.id,
                block_code=block_code,
                name=f"{area.name} Block {idx + 1}",
                target_building_count=target_buildings_per_hlb,
                actual_building_count=cluster_count,
                estimated_census_house_count=hlb_est_ch,
                estimated_population=hlb_est_pop,
                boundary=boundary_wkb,
                boundary_status=boundary_status,
                status=HlbStatus.GENERATED,
                quality_score=val_result["quality_score"],
                validation_status=val_status,
                validation_details=val_result,
            )
            db.add(hlb_record)
            db.flush()  # Generate hlb_record.id

            hlb_quality_scores.append(val_result["quality_score"])

            # Add House memberships
            for b in cluster:
                mapping = HlbHouse(
                    hlb_id=hlb_record.id,
                    house_id=b["id"],
                    status="ASSIGNED",
                )
                db.add(mapping)

            created_hlb_schemas.append(
                {
                    "id": hlb_record.id,
                    "layout_id": layout.id,
                    "version_id": layout_version.id,
                    "block_code": block_code,
                    "name": hlb_record.name,
                    "target_building_count": target_buildings_per_hlb,
                    "actual_building_count": cluster_count,
                    "estimated_census_house_count": hlb_est_ch,
                    "estimated_population": hlb_est_pop,
                    "count_deviation": val_result["count_deviation"],
                    "boundary_status": boundary_status,
                    "status": hlb_record.status.value,
                    "quality_score": val_result["quality_score"],
                    "validation_status": val_status.value,
                    "validation_details": val_result,
                    "boundary": geometry_to_geojson_dict(boundary_geom),
                    "created_at": hlb_record.created_at,
                    "updated_at": hlb_record.updated_at,
                }
            )

        # 10. Update LayoutVersion overall score & summary
        avg_quality = (
            round(sum(hlb_quality_scores) / len(hlb_quality_scores), 3)
            if hlb_quality_scores
            else None
        )
        layout_version.quality_score = avg_quality
        layout_version.validation_status = overall_validation_status
        layout_version.estimated_census_house_count = total_est_ch
        layout_version.estimated_population = total_est_pop
        layout_version.validation_summary = {
            "overall_status": overall_validation_status,
            "average_quality_score": avg_quality,
            "boundary_status": boundary_status,
            "total_buildings": total_buildings,
            "raw_bbox_building_count": raw_total_buildings,
            "clipped_outside_count": clipped_out_count,
            "target_buildings_per_hlb": target_buildings_per_hlb,
            "hlb_count": len(partitions),
            "unassigned_count": exact_counts["unassigned_count"],
            "duplicate_count": exact_counts["duplicate_count"],
            "gap_ratio": geom_val["metrics"]["gap_ratio"],
            "overlap_ratio": geom_val["metrics"]["max_pairwise_overlap_ratio"],
            "geometry_valid": geom_val["is_valid"],
            "geometry_errors": geom_val["errors"],
            "geometry_warnings": geom_val["warnings"],
        }

        # 11. Update Layout active candidate status
        layout.actual_building_count = total_buildings
        layout.expected_hlb_count = len(partitions)
        layout.target_hlb_building_count = target_buildings_per_hlb
        layout.workload_unit = workload_unit
        layout.target_workload = target_buildings_per_hlb
        layout.estimated_census_house_count = total_est_ch
        layout.estimated_population = total_est_pop
        layout.estimation_method = "CENSUS_2011_PCA_RATIO"
        layout.estimation_provenance = "Census of India 2011 Primary Census Abstract (Arasur CT 644401): 3,306 HH / 10,583 footprints (0.312 HH/footprint, 3.48 persons/HH)"
        layout.boundary_status = boundary_status
        layout.active_version_id = layout_version.id
        if layout.status == LayoutStatus.DRAFT:
            layout.status = LayoutStatus.GENERATED

        db.commit()

        return {
            "layout_id": layout.id,
            "layout_name": layout.name,
            "version_id": layout_version.id,
            "version_number": next_version_num,
            "boundary_status": boundary_status,
            "total_buildings": total_buildings,
            "target_buildings_per_hlb": target_buildings_per_hlb,
            "hlb_count": len(partitions),
            "quality_score": avg_quality,
            "validation_status": overall_validation_status,
            "validation_summary": layout_version.validation_summary,
            "generation_metadata": layout_version.generation_metadata,
            "hlbs": created_hlb_schemas,
        }


hlb_generation_service = HlbGenerationService()
