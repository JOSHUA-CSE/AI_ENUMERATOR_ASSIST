import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shapely.geometry import Point
from app.gis.boundary_loader import load_provisional_boundary
from app.gis.hlb.boundary_builder import build_partitioned_hlb_boundaries
from app.gis.hlb.quality_metrics import (
    DEFAULT_QUALITY_THRESHOLDS,
    calculate_hlb_quality_metrics,
    get_osm_road_segments_tree,
)
from app.gis.hlb.validation import recalculate_exact_building_counts
from app.gis.spatial import COIMBATORE_PROJECTED_CRS

prov_boundary, _ = load_provisional_boundary("arasur")
with open("app/data/open_buildings/arasur_real_open_buildings_v3.json") as f:
    raw_bldgs = json.load(f)["buildings"]

clipped_bldgs = [b for b in raw_bldgs if prov_boundary.contains(Point(b["longitude"], b["latitude"]))]

partitions = build_partitioned_hlb_boundaries(clipped_bldgs, prov_boundary, 250, COIMBATORE_PROJECTED_CRS)
geoms = [p[0] for p in partitions]
exact = recalculate_exact_building_counts(geoms, clipped_bldgs, target_buildings_per_hlb=250)
road_tree = get_osm_road_segments_tree()[1]

hlb_metrics = []
for idx, g in enumerate(geoms):
    block_code = f"HLB-{idx+1:03d}"
    cluster = exact["assigned_clusters"][idx]
    qm = calculate_hlb_quality_metrics(g, cluster, road_tree=road_tree)
    hlb_metrics.append((block_code, qm))

print(f"Total HLBs evaluated: {len(hlb_metrics)}")
print(f"Configured thresholds: {json.dumps(DEFAULT_QUALITY_THRESHOLDS, indent=2)}")

# Check each threshold
threshold_stats = {
    "min_compactness": [],
    "max_longest_axis_meters": [],
    "max_boundary_intersecting_buildings": [],
    "max_road_segments_crossed": [],
    "max_walking_distance_km": [],
}

for code, qm in hlb_metrics:
    if qm["compactness"] < DEFAULT_QUALITY_THRESHOLDS["min_compactness"]:
        threshold_stats["min_compactness"].append((code, qm["compactness"]))
    if qm["longest_axis_meters"] > DEFAULT_QUALITY_THRESHOLDS["max_longest_axis_meters"]:
        threshold_stats["max_longest_axis_meters"].append((code, qm["longest_axis_meters"]))
    if qm["boundary_intersecting_buildings_count"] > DEFAULT_QUALITY_THRESHOLDS["max_boundary_intersecting_buildings"]:
        threshold_stats["max_boundary_intersecting_buildings"].append((code, qm["boundary_intersecting_buildings_count"]))
    if qm["road_segments_crossed_count"] > DEFAULT_QUALITY_THRESHOLDS["max_road_segments_crossed"]:
        threshold_stats["max_road_segments_crossed"].append((code, qm["road_segments_crossed_count"]))
    if qm["estimated_walking_distance_km"] > DEFAULT_QUALITY_THRESHOLDS["max_walking_distance_km"]:
        threshold_stats["max_walking_distance_km"].append((code, qm["estimated_walking_distance_km"]))

for k, flagged in threshold_stats.items():
    print(f"\nThreshold '{k}': {len(flagged)} HLBs exceeded ({len(flagged)/len(hlb_metrics)*100:.1f}%)")
    for code, val in flagged:
        print(f"  {code}: {val}")
