import logging
from typing import Any

from shapely.geometry import MultiPolygon, Point, Polygon, box, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

from app.gis.hlb.clustering import partition_territory_and_buildings
from app.gis.spatial import (
    COIMBATORE_PROJECTED_CRS,
    DEFAULT_GEOGRAPHIC_CRS,
    transform_geometry,
)

logger = logging.getLogger(__name__)


def build_partitioned_hlb_boundaries(
    buildings: list[dict[str, Any]],
    layout_boundary_geom: MultiPolygon | Polygon,
    target_buildings_per_hlb: int = 250,
    projected_crs: str = COIMBATORE_PROJECTED_CRS,
) -> list[tuple[MultiPolygon, list[dict[str, Any]]]]:
    """
    Partition the complete parent layout/village territory and building centroids
    into balanced, contiguous, interior-disjoint HLB blocks.

    Guarantees:
    - Zero gaps across the parent layout boundary.
    - Zero overlapping territory between HLBs.
    - Strict containment inside the parent layout polygon.
    - Balanced building distribution targeting `target_buildings_per_hlb`.

    Returns:
        List of tuples: (hlb_boundary_wgs84: MultiPolygon, cluster_buildings: list[dict])
    """
    if not buildings:
        return []

    return partition_territory_and_buildings(
        buildings=buildings,
        parent_boundary_geom=layout_boundary_geom,
        target_buildings_per_hlb=target_buildings_per_hlb,
        projected_crs=projected_crs,
    )


def build_hlb_boundary(
    cluster_buildings: list[dict[str, Any]],
    layout_boundary_geom: MultiPolygon | Polygon,
    projected_crs: str = COIMBATORE_PROJECTED_CRS,
) -> MultiPolygon:
    """
    Construct a clean, valid candidate HLB boundary polygon from cluster buildings
    and clip strictly to the parent layout boundary polygon.
    Uses metric buffer operations in projected CRS (EPSG:32643) for spatial fidelity.
    """
    if not cluster_buildings:
        centroid = layout_boundary_geom.centroid
        tiny_box = box(
            centroid.x - 0.0001,
            centroid.y - 0.0001,
            centroid.x + 0.0001,
            centroid.y + 0.0001,
        )
        return (
            MultiPolygon([tiny_box])
            if isinstance(tiny_box, Polygon)
            else MultiPolygon()
        )

    geoms_projected = []
    for b in cluster_buildings:
        footprint_raw = b.get("footprint")
        if footprint_raw:
            try:
                g = shape(footprint_raw)
                if not g.is_valid:
                    g = make_valid(g)
                if not g.is_empty:
                    # Buffer footprint in projected metric CRS (approx 25 meters)
                    g_utm = transform_geometry(
                        g,
                        src_crs=DEFAULT_GEOGRAPHIC_CRS,
                        dst_crs=projected_crs,
                    )
                    geoms_projected.append(g_utm.buffer(25.0))
                    continue
            except Exception:
                pass

        # If no footprint or parse failed, use metric buffered centroid Point (35 meters)
        pt = Point(b["longitude"], b["latitude"])
        pt_utm = transform_geometry(
            pt,
            src_crs=DEFAULT_GEOGRAPHIC_CRS,
            dst_crs=projected_crs,
        )
        geoms_projected.append(pt_utm.buffer(35.0))

    # Union all building components in projected planar space
    union_projected = unary_union(geoms_projected)
    if not union_projected.is_valid:
        union_projected = make_valid(union_projected)

    # Smooth the boundary: morphological closing (buffer +35m then -15m)
    if len(cluster_buildings) <= 3:
        candidate_utm = union_projected.convex_hull.buffer(20.0)
    else:
        closed = union_projected.buffer(35.0).buffer(-15.0)
        candidate_utm = (
            closed if not closed.is_empty else union_projected.convex_hull
        )

    if not candidate_utm.is_valid:
        candidate_utm = make_valid(candidate_utm)

    # Transform back to WGS84 for clipping with layout_boundary_geom
    candidate_wgs84 = transform_geometry(
        candidate_utm,
        src_crs=projected_crs,
        dst_crs=DEFAULT_GEOGRAPHIC_CRS,
    )
    if not candidate_wgs84.is_valid:
        candidate_wgs84 = make_valid(candidate_wgs84)

    # Strict containment clipping: Candidate HLB must remain inside Layout boundary
    clipped = candidate_wgs84.intersection(layout_boundary_geom)
    if not clipped.is_valid:
        clipped = make_valid(clipped)

    # If clipping produced empty or collection, fallback to convex hull intersection
    if clipped.is_empty:
        clipped = candidate_wgs84.convex_hull.intersection(layout_boundary_geom)

    # Normalize to MultiPolygon
    if isinstance(clipped, Polygon):
        final_poly = MultiPolygon([clipped])
    elif isinstance(clipped, MultiPolygon):
        final_poly = clipped
    else:
        polys = [p for p in getattr(clipped, "geoms", []) if isinstance(p, Polygon)]
        final_poly = MultiPolygon(polys) if polys else (
            MultiPolygon([layout_boundary_geom])
            if isinstance(layout_boundary_geom, Polygon)
            else layout_boundary_geom
        )

    return final_poly
