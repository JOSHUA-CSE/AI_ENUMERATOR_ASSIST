import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shapely.geometry import LineString, Point, shape
from shapely.ops import unary_union
from app.gis.spatial import transform_geometry, DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS
from app.gis.boundary_loader import load_provisional_boundary
from app.gis.hlb.boundary_builder import build_partitioned_hlb_boundaries

t0 = time.time()
prov_boundary, _ = load_provisional_boundary('arasur')
with open('app/data/open_buildings/arasur_real_open_buildings_v3.json') as f:
    data = json.load(f)
raw_bldgs = data['buildings']
clipped_bldgs = [b for b in raw_bldgs if prov_boundary.contains(Point(b['longitude'], b['latitude']))]

print(f"Loaded {len(clipped_bldgs)} clipped buildings in {round((time.time()-t0)*1000, 1)}ms")

t1 = time.time()
partitions = build_partitioned_hlb_boundaries(clipped_bldgs, prov_boundary, 250)
geoms = [p[0] for p in partitions]
print(f"Generated {len(geoms)} HLBs in {round((time.time()-t1)*1000, 1)}ms")

proj_geoms = [transform_geometry(g, DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS) for g in geoms]
boundary_network = unary_union([g.boundary for g in proj_geoms])
total_len = boundary_network.length

with open('app/data/roads/arasur_osm_roads.json') as f:
    rd = json.load(f)
road_lines = []
for el in rd.get('elements', []):
    c = el.get('geometry', [])
    if len(c) >= 2:
        pts = [(p['lon'], p['lat']) for p in c]
        road_lines.append(transform_geometry(LineString(pts), DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS))

road_network = unary_union(road_lines)
road_buf = road_network.buffer(10.0)

coincident = boundary_network.intersection(road_buf)
print(f"Total unique boundary length: {total_len:.1f}m")
print(f"Coincident length with roads (10m tolerance): {coincident.length:.1f}m ({coincident.length / total_len * 100:.2f}%)")
