import json
import sys
import numpy as np
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

metrics_data = {
    "compactness": [],
    "longest_axis_meters": [],
    "boundary_intersecting_buildings_count": [],
    "road_segments_crossed_count": [],
    "estimated_walking_distance_km": [],
}

for idx, g in enumerate(geoms):
    block_code = f"HLB-{idx+1:03d}"
    cluster = exact["assigned_clusters"][idx]
    qm = calculate_hlb_quality_metrics(g, cluster, road_tree=road_tree)
    for k in metrics_data:
        metrics_data[k].append(qm[k])

for k, vals in metrics_data.items():
    arr = np.array(vals)
    print(f"{k}: Min={arr.min():.2f}, Mean={arr.mean():.2f}, Max={arr.max():.2f}, p90={np.percentile(arr, 90):.2f}")

