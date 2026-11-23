import math
from typing import Any

from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely.validation import make_valid

from app.gis.hlb.quality_metrics import (
    calculate_hlb_quality_metrics,
    get_osm_road_segments_tree,
)
from app.gis.spatial import (
    COIMBATORE_PROJECTED_CRS,
    DEFAULT_GEOGRAPHIC_CRS,
    transform_geometry,
)


def validate_and_score_hlb(
    hlb_code: str,
    building_count: int,
    target_buildings_per_hlb: int,
    hlb_boundary_geom: MultiPolygon | Polygon,
    layout_boundary_geom: MultiPolygon | Polygon,
    balanced_target_size: int | None = None,
    cluster_buildings: list[dict[str, Any]] | None = None,
    all_footprints_tree: STRtree | None = None,
    road_tree: STRtree | None = None,
    quality_thresholds: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    """
    Validate an individual candidate HLB and compute its multi-factor quality score
    against the Deputy Tahsildar's target and the balanced partition target.
    Includes comprehensive spatial quality metrics (area, Polsby-Popper compactness,
    longest axis length, intersecting building footprints, OSM road crossings, and walking distance).
    """
    warnings: list[str] = []
    errors: list[str] = []

    target_limit = max(10, target_buildings_per_hlb)
    ideal_target = (
        balanced_target_size if balanced_target_size is not None else target_limit
    )

    # Count deviation from the balanced target
    count_deviation = building_count - ideal_target
    count_dev_ratio = abs(count_deviation) / max(1, ideal_target)

    # Count score: 1.0 at ideal balanced target, decays only with significant deviation
    count_score = max(0.0, 1.0 - (count_dev_ratio * 0.50))

    if building_count > target_limit:
        warnings.append(
            f"Building count ({building_count}) exceeds target "
            f"({target_limit}) by {building_count - target_limit} buildings"
        )
        count_score = max(0.0, count_score - 0.25)
    elif building_count < int(ideal_target * 0.5):
        warnings.append(
            f"Building count ({building_count}) is significantly below balanced target "
            f"({ideal_target}) by {abs(count_deviation)} buildings"
        )

    # 2. Boundary containment validation
    area_outside = hlb_boundary_geom.difference(layout_boundary_geom).area
    hlb_area = max(hlb_boundary_geom.area, 1e-9)
    outside_ratio = area_outside / hlb_area

    if outside_ratio > 0.02:
        errors.append(f"Boundary extends {outside_ratio:.1%} outside parent layout")
        boundary_score = max(0.0, 1.0 - (outside_ratio * 5.0))
    else:
        boundary_score = 1.0

    # 3. Continuity / Fragmentation check
    num_parts = (
        len(hlb_boundary_geom.geoms)
        if isinstance(hlb_boundary_geom, MultiPolygon)
        else 1
    )
    if num_parts > 3:
        warnings.append(
            f"Geographic fragmentation: boundary contains {num_parts} "
            "disconnected parts"
        )
        continuity_score = max(0.4, 1.0 - ((num_parts - 1) * 0.12))
    elif num_parts > 1:
        continuity_score = 0.88
    else:
        continuity_score = 1.0

    # 4. Compute comprehensive quality metrics in projected CRS
    quality_metrics = calculate_hlb_quality_metrics(
        hlb_boundary_geom=hlb_boundary_geom,
        cluster_buildings=cluster_buildings or [],
        all_footprints_tree=all_footprints_tree,
        road_tree=road_tree,
        thresholds=quality_thresholds,
    )

    if quality_metrics.get("quality_warnings"):
        warnings.extend(quality_metrics["quality_warnings"])

    # Polsby-Popper compactness score (0.0 to 1.0)
    compactness_raw = quality_metrics.get("compactness", 0.0)
    compactness_score = min(1.0, max(0.2, compactness_raw * 3.5))

    # Overall Composite Quality Score (0.0 to 1.0)
    composite_score = round(
        (0.40 * count_score)
        + (0.30 * continuity_score)
        + (0.20 * boundary_score)
        + (0.10 * compactness_score),
        3,
    )

    if errors:
        validation_status = "INVALID"
    elif warnings or count_score < 0.70:
        validation_status = "WARNING"
    else:
        validation_status = "VALID"

    return {
        "block_code": hlb_code,
        "building_count": building_count,
        "target_buildings_per_hlb": ideal_target,
        "target_size": ideal_target,
        "count_deviation": count_deviation,
        "validation_status": validation_status,
        "quality_score": composite_score,
        "quality_metrics": quality_metrics,
        "scores": {
            "count_score": round(count_score, 3),
            "continuity_score": round(continuity_score, 3),
            "boundary_score": round(boundary_score, 3),
            "compactness_score": round(compactness_score, 3),
        },
        "warnings": warnings,
        "errors": errors,
    }


def validate_generation_invariants(
    total_input_buildings: int,
    candidate_clusters: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    """
    Verify global invariants across all generated candidate HLBs:
    1. Total input buildings == Total assigned buildings
    2. Duplicate assignments == 0
    3. Unassigned buildings == 0
    """
    assigned_ids: set[str] = set()
    duplicates: list[str] = []
    total_assigned = 0

    for cluster in candidate_clusters:
        for b in cluster:
            b_id = str(b["id"])
            total_assigned += 1
            if b_id in assigned_ids:
                duplicates.append(b_id)
            else:
                assigned_ids.add(b_id)

    unassigned_count = max(0, total_input_buildings - len(assigned_ids))
    duplicate_count = len(duplicates)

    is_valid = (
        (unassigned_count == 0)
        and (duplicate_count == 0)
        and (total_assigned == total_input_buildings)
    )

    warnings = []
    errors = []
    if duplicate_count > 0:
        errors.append(f"Found {duplicate_count} duplicate building assignments")
    if unassigned_count > 0:
        errors.append(f"Found {unassigned_count} unassigned buildings")

    return {
        "is_valid": is_valid,
        "total_input": total_input_buildings,
        "total_assigned": total_assigned,
        "unique_assigned": len(assigned_ids),
        "unassigned_count": unassigned_count,
        "duplicate_count": duplicate_count,
        "warnings": warnings,
        "errors": errors,
    }


def recalculate_exact_building_counts(
    hlb_boundaries: list[Polygon | MultiPolygon],
    buildings: list[dict[str, Any]],
    hlb_codes: list[str] | None = None,
    target_buildings_per_hlb: int = 250,
) -> dict[str, Any]:
    """
    Perform exact Point-in-Polygon building assignment from final HLB boundaries
    using Shapely STRtree spatial indexing.

    Deterministic Shared Boundary Tie-breaking:
    If a building centroid falls on a shared edge between multiple HLB polygons,
    it is assigned to the HLB with the lowest index/code.

    Guarantees:
    - 0 unassigned buildings
    - 0 duplicate assignments
    - Exact building count per HLB
    """
    total_buildings = len(buildings)
    k = len(hlb_boundaries)

    if k == 0 or total_buildings == 0:
        return {
            "is_valid": total_buildings == 0,
            "total_input_buildings": total_buildings,
            "accepted_buildings": 0,
            "rejected_buildings": 0,
            "hlb_count": k,
            "target_buildings_per_hlb": target_buildings_per_hlb,
            "counts": [],
            "average_count": 0.0,
            "min_count": 0,
            "max_count": 0,
            "deviation_from_target": 0,
            "unassigned_count": total_buildings,
            "duplicate_count": 0,
            "assigned_clusters": [],
            "building_assignments": {},
        }

    tree = STRtree(hlb_boundaries)
    assigned_clusters: list[list[dict[str, Any]]] = [[] for _ in range(k)]
    building_assignments: dict[str, int | str] = {}

    for b in buildings:
        b_id = str(b.get("id", ""))
        pt = Point(b["longitude"], b["latitude"])
        matches = tree.query(pt, predicate="intersects")

        if len(matches) > 0:
            # Deterministic tie-breaking: assign to the minimum index
            chosen_idx = int(min(matches))
        else:
            # Floating point boundary margin: assign to nearest polygon
            chosen_idx = int(tree.nearest(pt))

        assigned_clusters[chosen_idx].append(b)
        code = (
            hlb_codes[chosen_idx]
            if hlb_codes and chosen_idx < len(hlb_codes)
            else chosen_idx
        )
        building_assignments[b_id] = code

    counts = [len(c) for c in assigned_clusters]
    avg_count = round(sum(counts) / len(counts), 2) if counts else 0.0
    min_count = min(counts) if counts else 0
    max_count = max(counts) if counts else 0
    max_dev = max(abs(c - target_buildings_per_hlb) for c in counts) if counts else 0

    assigned_total = sum(counts)
    unassigned_count = max(0, total_buildings - len(building_assignments))
    duplicate_count = max(0, assigned_total - len(building_assignments))

    is_valid = (
        (assigned_total == total_buildings)
        and (unassigned_count == 0)
        and (duplicate_count == 0)
    )

    return {
        "is_valid": is_valid,
        "total_input_buildings": total_buildings,
        "accepted_buildings": total_buildings,
        "rejected_buildings": 0,
        "hlb_count": k,
        "target_buildings_per_hlb": target_buildings_per_hlb,
        "counts": counts,
        "average_count": avg_count,
        "min_count": min_count,
        "max_count": max_count,
        "deviation_from_target": max_dev,
        "unassigned_count": unassigned_count,
        "duplicate_count": duplicate_count,
        "assigned_clusters": assigned_clusters,
        "building_assignments": building_assignments,
    }


def validate_layout_partition_geometry(
    hlb_boundaries: list[Polygon | MultiPolygon],
    layout_boundary_geom: MultiPolygon | Polygon,
    projected_crs: str = COIMBATORE_PROJECTED_CRS,
) -> dict[str, Any]:
    """
    Validate geometric consistency and completeness of a layout partition:
    1. Polygon validity (`is_valid`)
    2. Strict parent boundary containment (outside area ratio < 0.01)
    3. Complete territory coverage / gap check (gap area ratio < 0.01)
    4. Interior-disjointness / overlap check (pairwise overlap ratio < 0.005)
    5. Fragmentation / contiguity (parts <= 3)

    Metric areas are calculated in `projected_crs` (EPSG:32643).
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Project to metric CRS
    parent_utm = transform_geometry(
        layout_boundary_geom,
        src_crs=DEFAULT_GEOGRAPHIC_CRS,
        dst_crs=projected_crs,
    )
    if not parent_utm.is_valid:
        parent_utm = make_valid(parent_utm)

    parent_area = max(parent_utm.area, 1e-9)

    geoms_utm: list[Polygon | MultiPolygon] = []
    invalid_geoms = 0
    total_hlb_area = 0.0
    fragmented_count = 0

    for idx, g in enumerate(hlb_boundaries):
        if not g.is_valid:
            invalid_geoms += 1
            errors.append(f"HLB index {idx} has invalid geometry")
            g = make_valid(g)

        g_utm = transform_geometry(
            g,
            src_crs=DEFAULT_GEOGRAPHIC_CRS,
            dst_crs=projected_crs,
        )
        if not g_utm.is_valid:
            g_utm = make_valid(g_utm)

        geoms_utm.append(g_utm)
        total_hlb_area += g_utm.area

        # Containment check
        diff = g_utm.difference(parent_utm)
        outside_area = diff.area if not diff.is_empty else 0.0
        outside_ratio = outside_area / max(g_utm.area, 1e-9)
        if outside_ratio > 0.01:
            errors.append(
                f"HLB index {idx} extends {outside_ratio:.2%} outside layout boundary"
            )
        elif outside_ratio > 0.0001:
            warnings.append(
                f"HLB index {idx} has minor border protrusion ({outside_ratio:.4%})"
            )

        # Fragmentation check
        parts = len(g.geoms) if isinstance(g, MultiPolygon) else 1
        if parts > 3:
            fragmented_count += 1
            warnings.append(
                f"HLB index {idx} contains {parts} disconnected components"
            )

    # Gap / Coverage Check: Union of HLBs vs Parent
    if geoms_utm:
        union_hlbs = unary_union(geoms_utm)
        gap_geom = parent_utm.difference(union_hlbs)
        gap_area = gap_geom.area if not gap_geom.is_empty else 0.0
        gap_ratio = gap_area / parent_area
    else:
        gap_area = parent_area
        gap_ratio = 1.0

    if gap_ratio > 0.01:
        errors.append(
            f"Territory partitioning has {gap_ratio:.2%} unallocated gap area ({gap_area:,.1f} m²)"
        )
    elif gap_ratio > 0.0001:
        warnings.append(
            f"Minor unallocated gap area: {gap_ratio:.4%} ({gap_area:,.1f} m²)"
        )

    # Overlap Check: Pairwise intersections using STRtree
    tree_utm = STRtree(geoms_utm) if geoms_utm else None
    max_overlap_area = 0.0
    max_overlap_ratio = 0.0

    if tree_utm:
        for i, g in enumerate(geoms_utm):
            candidates = tree_utm.query(g, predicate="overlaps")
            for j in candidates:
                if i < j:
                    inter = g.intersection(geoms_utm[j])
                    if not inter.is_empty and inter.area > 0.0:
                        o_area = inter.area
                        o_ratio = o_area / min(g.area, geoms_utm[j].area)
                        if o_area > max_overlap_area:
                            max_overlap_area = o_area
                            max_overlap_ratio = o_ratio

    if max_overlap_ratio > 0.005:
        errors.append(
            f"HLB boundaries overlap significantly: max overlap ratio {max_overlap_ratio:.2%} ({max_overlap_area:,.1f} m²)"
        )
    elif max_overlap_ratio > 0.0001:
        warnings.append(
            f"Minor boundary overlap: max overlap ratio {max_overlap_ratio:.4%} ({max_overlap_area:,.1f} m²)"
        )

    is_valid = (len(errors) == 0) and (invalid_geoms == 0)

    return {
        "is_valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "parent_area_sq_meters": round(parent_area, 2),
            "total_hlb_area_sq_meters": round(total_hlb_area, 2),
            "gap_area_sq_meters": round(gap_area, 4),
            "gap_ratio": round(gap_ratio, 6),
            "max_pairwise_overlap_sq_meters": round(max_overlap_area, 4),
            "max_pairwise_overlap_ratio": round(max_overlap_ratio, 6),
            "hlb_count": len(hlb_boundaries),
            "invalid_geometry_count": invalid_geoms,
            "fragmented_hlb_count": fragmented_count,
            "containment_passed": all("extends" not in e for e in errors),
            "gap_passed": gap_ratio <= 0.01,
            "overlap_passed": max_overlap_ratio <= 0.005,
        },
    }
