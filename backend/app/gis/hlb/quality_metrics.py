"""
Per-HLB Quality Metrics & Validation.
Computes comprehensive quality and spatial metrics for Houselisting Blocks:
1. Projected Area (sq meters in EPSG:32643)
2. Polsby-Popper Compactness (4 * pi * Area / Perimeter^2)
3. Longest Axis Length (meters, from minimum rotated bounding box)
4. Building footprints intersecting the HLB boundary
5. Count of OSM road segments crossed by the HLB boundary
6. Estimated walking distance (using TSP route optimizer over building coordinates)
7. Configurable limit validation and warning flags
"""

import json
import logging
import math
from pathlib import Path
from typing import Any

from shapely.geometry import LineString, MultiPolygon, Polygon, shape
from shapely.strtree import STRtree

from app.gis.route.optimizer import optimize_building_route
from app.gis.spatial import (
    COIMBATORE_PROJECTED_CRS,
    DEFAULT_GEOGRAPHIC_CRS,
    transform_geometry,
)

logger = logging.getLogger(__name__)

ROADS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "roads"
DEFAULT_ROADS_FILE = ROADS_DIR / "arasur_osm_roads.json"

DEFAULT_QUALITY_THRESHOLDS: dict[str, float | int] = {
    "min_compactness": 0.12,  # Below 0.12 is flagged as elongated/fragmented
    "max_longest_axis_meters": 3500.0,  # Max span across the block
    "max_boundary_intersecting_buildings": 5,  # Max buildings straddling the border
    "max_road_segments_crossed": 60,  # Road division complexity
    "max_walking_distance_km": 30.0,  # Max walking route per enumerator
}

_CACHED_ROADS_TREE: STRtree | None = None
_CACHED_ROAD_SEGMENTS: list[LineString] | None = None


def get_osm_road_segments_tree(
    roads_file: Path | str | None = None,
) -> tuple[list[LineString], STRtree] | None:
    """
    Load OSM road segments and build a spatial index (STRtree).
    Cached in memory for high-performance spatial intersection queries.
    """
    global _CACHED_ROADS_TREE, _CACHED_ROAD_SEGMENTS

    if _CACHED_ROADS_TREE is not None and _CACHED_ROAD_SEGMENTS is not None:
        return _CACHED_ROAD_SEGMENTS, _CACHED_ROADS_TREE

    target_file = Path(roads_file) if roads_file else DEFAULT_ROADS_FILE
    if not target_file.exists():
        logger.warning("OSM roads file not found: %s", target_file)
        return None

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        segments: list[LineString] = []
        for el in data.get("elements", []):
            coords = el.get("geometry", [])
            for i in range(len(coords) - 1):
                p1 = (coords[i]["lon"], coords[i]["lat"])
                p2 = (coords[i + 1]["lon"], coords[i + 1]["lat"])
                if p1 != p2:
                    segments.append(LineString([p1, p2]))

        if not segments:
            logger.warning("No road segments found in %s", target_file)
            return None

        tree = STRtree(segments)
        _CACHED_ROAD_SEGMENTS = segments
        _CACHED_ROADS_TREE = tree
        logger.info(
            "Loaded %d OSM road segments from %s into STRtree",
            len(segments),
            target_file.name,
        )
        return segments, tree
    except Exception as exc:
        logger.error("Failed to load OSM roads from %s: %s", target_file, exc)
        return None


def calculate_longest_axis_meters(
    proj_geom: Polygon | MultiPolygon,
) -> float:
    """
    Calculate the longest axis length of a geometry in meters
    using its minimum rotated bounding box.
    """
    try:
        min_rect = proj_geom.minimum_rotated_rectangle
        if isinstance(min_rect, Polygon):
            coords = list(min_rect.exterior.coords)
            if len(coords) >= 4:
                # 4 corner vertices: p0-p1 (side 1), p1-p2 (side 2)
                side1 = math.hypot(coords[1][0] - coords[0][0], coords[1][1] - coords[0][1])
                side2 = math.hypot(coords[2][0] - coords[1][0], coords[2][1] - coords[1][1])
                return round(max(side1, side2), 2)
        # Fallback to envelope bounds
        minx, miny, maxx, maxy = proj_geom.bounds
        return round(math.hypot(maxx - minx, maxy - miny), 2)
    except Exception:
        minx, miny, maxx, maxy = proj_geom.bounds
        return round(math.hypot(maxx - minx, maxy - miny), 2)


def calculate_hlb_quality_metrics(
    hlb_boundary_geom: Polygon | MultiPolygon,
    cluster_buildings: list[dict[str, Any]],
    all_footprints_tree: STRtree | None = None,
    road_tree: STRtree | None = None,
    thresholds: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    """
    Compute comprehensive GIS quality metrics for an individual HLB.

    Metrics:
    - area_sq_meters: Projected area in m^2 (EPSG:32643)
    - compactness: Polsby-Popper score (4*pi*A / P^2)
    - longest_axis_meters: Longest axis of minimum rotated bounding rectangle
    - boundary_intersecting_buildings_count: Count of buildings whose footprint intersects boundary
    - road_segments_crossed_count: Count of OSM road segments intersected by boundary
    - estimated_walking_distance_km: TSP-optimized walking path across buildings
    - warnings: Warning messages if metrics exceed configurable thresholds
    """
    limits = dict(DEFAULT_QUALITY_THRESHOLDS)
    if thresholds:
        limits.update(thresholds)

    warnings: list[str] = []

    # 1. Projected CRS Geometry (EPSG:32643 for Coimbatore / Arasur)
    proj_geom = transform_geometry(
        hlb_boundary_geom,
        DEFAULT_GEOGRAPHIC_CRS,
        COIMBATORE_PROJECTED_CRS,
    )

    area_sq_m = round(float(proj_geom.area), 2)
    perimeter_m = round(float(proj_geom.length), 2)

    # 2. Polsby-Popper Compactness
    if perimeter_m > 0 and area_sq_m > 0:
        compactness = round((4.0 * math.pi * area_sq_m) / (perimeter_m**2), 4)
    else:
        compactness = 0.0

    if compactness < float(limits["min_compactness"]):
        warnings.append(
            f"Low compactness ({compactness:.3f} < {limits['min_compactness']}): block is elongated or irregular"
        )

    # 3. Longest Axis Length
    longest_axis_m = calculate_longest_axis_meters(proj_geom)
    if longest_axis_m > float(limits["max_longest_axis_meters"]):
        warnings.append(
            f"Longest axis ({longest_axis_m:.0f}m > {limits['max_longest_axis_meters']:.0f}m) exceeds limit"
        )

    # 4. Building Footprints Intersecting Boundary
    boundary_line = hlb_boundary_geom.boundary
    intersecting_buildings_count = 0

    if all_footprints_tree is not None:
        try:
            # Query candidate footprint shapes intersecting boundary line
            candidate_indices = all_footprints_tree.query(boundary_line, predicate="intersects")
            intersecting_buildings_count = len(candidate_indices)
        except Exception as exc:
            logger.debug("STRtree query failed for footprint intersection: %s", exc)

    if intersecting_buildings_count == 0 and cluster_buildings:
        # Fallback to direct inspection of cluster building footprints
        for b in cluster_buildings:
            fp = b.get("footprint")
            if fp:
                try:
                    fp_shape = shape(fp)
                    if fp_shape.intersects(boundary_line):
                        intersecting_buildings_count += 1
                except Exception:
                    pass

    if intersecting_buildings_count > int(limits["max_boundary_intersecting_buildings"]):
        warnings.append(
            f"{intersecting_buildings_count} building footprints intersect HLB boundary (limit: {limits['max_boundary_intersecting_buildings']})"
        )

    # 5. OSM Road Segments Crossed by Boundary
    road_crossed_count = 0
    if road_tree is not None:
        try:
            crossed_indices = road_tree.query(boundary_line, predicate="intersects")
            road_crossed_count = len(crossed_indices)
        except Exception as exc:
            logger.debug("Road tree query failed: %s", exc)

    if road_crossed_count > int(limits["max_road_segments_crossed"]):
        warnings.append(
            f"Boundary crosses {road_crossed_count} OSM road segments (limit: {limits['max_road_segments_crossed']})"
        )

    # 6. Estimated Walking Distance via Route Optimizer
    estimated_walking_distance_km = 0.0
    if len(cluster_buildings) > 1:
        try:
            # Prepare minimal building coordinate dicts for fast TSP calculation
            coords_dicts = [
                {"latitude": b["latitude"], "longitude": b["longitude"]}
                for b in cluster_buildings
            ]
            _, opt_km, _, _ = optimize_building_route(coords_dicts)
            estimated_walking_distance_km = round(opt_km, 3)
        except Exception as exc:
            logger.debug("Route optimization failed: %s", exc)
            estimated_walking_distance_km = 0.0

    if estimated_walking_distance_km > float(limits["max_walking_distance_km"]):
        warnings.append(
            f"Estimated walking distance ({estimated_walking_distance_km:.2f}km > {limits['max_walking_distance_km']}km) exceeds limit"
        )

    return {
        "area_sq_meters": area_sq_m,
        "perimeter_meters": perimeter_m,
        "compactness": compactness,
        "longest_axis_meters": longest_axis_m,
        "boundary_intersecting_buildings_count": intersecting_buildings_count,
        "road_segments_crossed_count": road_crossed_count,
        "estimated_walking_distance_km": estimated_walking_distance_km,
        "quality_warnings": warnings,
        "thresholds_applied": limits,
    }

