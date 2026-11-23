"""
Benchmark comparing HLB spatial partition engine against two baselines on identical Arasur data:
1. Baseline A: Previous Bisection without Territory Splitting (buffered convex hulls around clusters)
2. Baseline B: Standard K-Means Spatial Clustering (unconstrained Voronoi/convex partitions)
3. Proposed Engine: Projected Recursive Spatial Bisection with Balanced Centroids & Complete Territory Partitioning

Data: 10,583 real building footprints clipped to Arasur provisional village boundary.
"""

import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from shapely.geometry import MultiPolygon, Point, Polygon, box, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely.validation import make_valid

from app.gis.boundary_loader import load_provisional_boundary
from app.gis.hlb.boundary_builder import build_partitioned_hlb_boundaries
from app.gis.hlb.clustering import partition_buildings_spatially
from app.gis.hlb.quality_metrics import (
    calculate_hlb_quality_metrics,
    get_osm_road_segments_tree,
)
from app.gis.hlb.validation import (
    recalculate_exact_building_counts,
    validate_layout_partition_geometry,
)
from app.gis.spatial import (
    COIMBATORE_PROJECTED_CRS,
    DEFAULT_GEOGRAPHIC_CRS,
    transform_geometry,
)


def run_benchmark():
    # 1. Load provisional boundary and real buildings
    prov_boundary, meta = load_provisional_boundary("arasur")

    raw_path = Path("app/data/open_buildings/arasur_real_open_buildings_v3.json")
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    raw_bldgs = raw_data["buildings"]

    # Centroid-in-polygon clip to provisional Arasur
    clipped_bldgs = [
        b
        for b in raw_bldgs
        if prov_boundary.contains(Point(b["longitude"], b["latitude"]))
        or prov_boundary.touches(Point(b["longitude"], b["latitude"]))
    ]
    n_bldgs = len(clipped_bldgs)
    target = 250
    expected_k = math.ceil(n_bldgs / target)  # 10583 / 250 = 43

    # Load OSM road tree
    road_data = get_osm_road_segments_tree()
    road_tree = road_data[1] if road_data else None

    # Load footprint tree
    footprint_shapes = []
    for b in clipped_bldgs:
        fp = b.get("footprint")
        if fp:
            try:
                s = shape(fp)
                if s.is_valid:
                    footprint_shapes.append(s)
            except Exception:
                pass
    footprint_tree = STRtree(footprint_shapes) if footprint_shapes else None

    coords = np.array([[b["longitude"], b["latitude"]] for b in clipped_bldgs])

    results = {}

    # -------------------------------------------------------------
    # Method A: Previous Bisection Without Territory Splitting
    # (Buffered convex hull around each bisection cluster)
    # -------------------------------------------------------------
    t0 = time.time()
    clusters_a = partition_buildings_spatially(
        clipped_bldgs,
        target_buildings_per_hlb=target,
        projected_crs=COIMBATORE_PROJECTED_CRS,
    )
    # Build buffered convex hulls around each cluster (Phase 1 approach)
    hlb_boundaries_a = []
    for c in clusters_a:
        pts = [Point(b["longitude"], b["latitude"]) for b in c]
        if len(pts) >= 3:
            hull = MultiPolygon([Polygon([(p.x, p.y) for p in pts]).convex_hull]) if Polygon([(p.x, p.y) for p in pts]).convex_hull.geom_type == "MultiPolygon" else Polygon([(p.x, p.y) for p in pts]).convex_hull
            # Add small buffer in degrees (~30m)
            buf = hull.buffer(0.0003)
            hlb_boundaries_a.append(buf)
        else:
            hlb_boundaries_a.append(Point(c[0]["longitude"], c[0]["latitude"]).buffer(0.0005))
    time_a_ms = round((time.time() - t0) * 1000, 1)

    # -------------------------------------------------------------
    # Method B: Standard K-Means Spatial Clustering
    # -------------------------------------------------------------
    t0 = time.time()
    # Simple scikit-learn or Lloyd's algorithm K-Means
    from scipy.cluster.vq import kmeans2
    # Run K-Means on projected metric coordinates
    proj_coords = []
    for b in clipped_bldgs:
        pt = transform_geometry(Point(b["longitude"], b["latitude"]), DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS)
        proj_coords.append([pt.x, pt.y])
    proj_coords = np.array(proj_coords)

    np.random.seed(42)
    centroids, labels = kmeans2(proj_coords, expected_k, minit="points", iter=25)

    clusters_b = [[] for _ in range(expected_k)]
    for idx, label in enumerate(labels):
        clusters_b[label].append(clipped_bldgs[idx])

    # Build Voronoi / bounded cells for K-Means centroids clipped to village boundary
    from scipy.spatial import Voronoi
    vor = Voronoi(centroids)
    # Create Voronoi polygons in projected CRS
    hlb_boundaries_b = []
    parent_proj = transform_geometry(prov_boundary, DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS)

    for i in range(len(centroids)):
        region_idx = vor.point_region[i]
        region = vor.regions[region_idx]
        if -1 not in region and len(region) > 0:
            poly_proj = Polygon([vor.vertices[v] for v in region])
            poly_clipped = poly_proj.intersection(parent_proj)
        else:
            # Fallback to buffer around points in this cluster
            if clusters_b[i]:
                c_pts = [Point(p[0], p[1]) for p in proj_coords[labels == i]]
                poly_proj = unary_union([p.buffer(100.0) for p in c_pts]).convex_hull
                poly_clipped = poly_proj.intersection(parent_proj)
            else:
                poly_clipped = Point(centroids[i][0], centroids[i][1]).buffer(10.0)

        poly_wgs84 = transform_geometry(poly_clipped, COIMBATORE_PROJECTED_CRS, DEFAULT_GEOGRAPHIC_CRS)
        if not poly_wgs84.is_valid:
            poly_wgs84 = make_valid(poly_wgs84)
        hlb_boundaries_b.append(poly_wgs84)
    time_b_ms = round((time.time() - t0) * 1000, 1)

    # -------------------------------------------------------------
    # Method C: Current Engine (Recursive Bisection + Complete Partitioning)
    # -------------------------------------------------------------
    t0 = time.time()
    partitions_c = build_partitioned_hlb_boundaries(
        buildings=clipped_bldgs,
        layout_boundary_geom=prov_boundary,
        target_buildings_per_hlb=target,
        projected_crs=COIMBATORE_PROJECTED_CRS,
    )
    hlb_boundaries_c = [p[0] for p in partitions_c]
    time_c_ms = round((time.time() - t0) * 1000, 1)

    # Evaluate all 3 methods with exact counting and geometry validation
    methods = [
        ("Baseline A (Bisection + Buffered Hulls)", hlb_boundaries_a, clusters_a, time_a_ms),
        ("Baseline B (K-Means Voronoi)", hlb_boundaries_b, clusters_b, time_b_ms),
        ("Current Engine (Projected Bisection + Partitioning)", hlb_boundaries_c, None, time_c_ms),
    ]

    summary_table = []

    for name, hlb_geoms, clusters, runtime in methods:
        exact_counts = recalculate_exact_building_counts(
            hlb_boundaries=hlb_geoms,
            buildings=clipped_bldgs,
            target_buildings_per_hlb=target,
        )
        counts = exact_counts["counts"]
        mean_c = statistics.mean(counts)
        stdev_c = statistics.stdev(counts) if len(counts) > 1 else 0.0
        min_c = min(counts)
        max_c = max(counts)

        geom_val = validate_layout_partition_geometry(
            hlb_boundaries=hlb_geoms,
            layout_boundary_geom=prov_boundary,
            projected_crs=COIMBATORE_PROJECTED_CRS,
        )
        gap_ratio = geom_val["metrics"]["gap_ratio"]
        overlap_ratio = geom_val["metrics"]["max_pairwise_overlap_ratio"]

        # Sample 5 HLBs for quality metrics (Polsby-Popper, road crosses, walk dist, intersecting buildings)
        compactness_list = []
        road_crosses_total = 0
        footprint_intersects_total = 0
        walk_distances = []

        assigned_clusters = exact_counts["assigned_clusters"]
        for idx, g in enumerate(hlb_geoms):
            c_bldgs = assigned_clusters[idx]
            qm = calculate_hlb_quality_metrics(
                hlb_boundary_geom=g,
                cluster_buildings=c_bldgs,
                all_footprints_tree=footprint_tree,
                road_tree=road_tree,
            )
            compactness_list.append(qm["compactness"])
            road_crosses_total += qm["road_segments_crossed_count"]
            footprint_intersects_total += qm["boundary_intersecting_buildings_count"]
            if qm["estimated_walking_distance_km"] > 0:
                walk_distances.append(qm["estimated_walking_distance_km"])

        avg_compactness = round(statistics.mean(compactness_list), 4) if compactness_list else 0.0
        avg_walk_dist = round(statistics.mean(walk_distances), 2) if walk_distances else 0.0

        summary_table.append({
            "Method": name,
            "HLB Count": len(hlb_geoms),
            "Assigned Bldgs": exact_counts["accepted_buildings"],
            "Unassigned": exact_counts["unassigned_count"],
            "Mean Count": round(mean_c, 1),
            "StdDev Count": round(stdev_c, 1),
            "Min / Max Count": f"{min_c} / {max_c}",
            "Gap Ratio (%)": f"{gap_ratio * 100:.2f}%",
            "Overlap Ratio (%)": f"{overlap_ratio * 100:.2f}%",
            "Avg Polsby-Popper": avg_compactness,
            "Total Road Crossings": road_crosses_total,
            "Total Footprint Intersections": footprint_intersects_total,
            "Avg Walking Dist (km)": avg_walk_dist,
            "Runtime (ms)": runtime,
        })

    print(json.dumps(summary_table, indent=2))
    return summary_table


if __name__ == "__main__":
    run_benchmark()
