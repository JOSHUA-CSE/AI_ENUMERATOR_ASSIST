import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import json
import time
from shapely.geometry import shape
from app.gis.route.road_network import get_road_network
from app.gis.route.rpp_solver import solve_undirected_rpp

def main():
    print("--- BENCHMARKING ARASUR RPP ---")
    t0 = time.time()
    net = get_road_network("app/data/roads/arasur_osm_roads.json")
    t1 = time.time()
    print(f"RoadNetwork loaded in {t1 - t0:.3f}s: {len(net.segments)} segments")

    with open("app/data/boundaries/arasur_provisional_boundary.geojson") as f:
        feat_coll = json.load(f)
    poly = shape(feat_coll["features"][0]["geometry"])
    print(f"Boundary loaded, valid={poly.is_valid}, area={poly.area:.8f}")

    t2 = time.time()
    req, trans = net.extract_required_and_transit_edges(poly, buffer_meters=30.0)
    t3 = time.time()
    print(f"Clipping in {t3 - t2:.3f}s: {len(req)} required edges, {len(trans)} transit edges")

    t4 = time.time()
    rpp_res = solve_undirected_rpp(
        hlb_id="arasur_provisional",
        required_edges=req,
        available_transit_edges=trans,
    )
    t5 = time.time()
    print(f"RPP solved in {t5 - t4:.3f}s:")
    print(f"  Total distance: {rpp_res.total_distance_km:.3f} km")
    required_km = rpp_res.total_distance_km - rpp_res.deadhead_distance_km
    print(f"  Required distance: {required_km:.3f} km")
    print(f"  Deadhead distance: {rpp_res.deadhead_distance_km:.3f} km")
    print(f"  Deadhead percentage: {rpp_res.deadhead_percentage:.2f}%")
    print(f"  Step count: {len(rpp_res.steps)}")
    print(f"  Polyline points: {len(rpp_res.continuous_polyline)}")
    print(f"  Disconnected components: {rpp_res.disconnected_components_count}")
    print(f"  Total solve time: {t5 - t4:.3f}s")
    print(f"  Total pipeline time: {t5 - t0:.3f}s")

if __name__ == "__main__":
    main()
