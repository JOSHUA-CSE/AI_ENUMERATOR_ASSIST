import json
import math
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shapely.geometry import box

from app.gis.hlb.boundary_builder import build_partitioned_hlb_boundaries
from app.gis.hlb.validation import (
    recalculate_exact_building_counts,
    validate_layout_partition_geometry,
)
from app.gis.spatial import COIMBATORE_PROJECTED_CRS


def generate_synthetic_grid_buildings(n: int) -> tuple[list[dict], Any]:
    """Generate n synthetic buildings uniformly distributed in an Arasur-sized extent."""
    side = math.ceil(math.sqrt(n))
    buildings = []
    lat_min, lat_max = 11.050, 11.110
    lon_min, lon_max = 77.080, 77.160
    lat_step = (lat_max - lat_min) / (side + 1)
    lon_step = (lon_max - lon_min) / (side + 1)

    for i in range(n):
        r = i // side
        c = i % side
        lat = lat_min + (r + 1) * lat_step
        lon = lon_min + (c + 1) * lon_step
        buildings.append({
            "id": f"syn-{i:06d}",
            "ref": f"BLD-{i:06d}",
            "latitude": lat,
            "longitude": lon,
        })

    boundary = box(lon_min, lat_min, lon_max, lat_max)
    return buildings, boundary


def run_benchmark(dataset_name: str, buildings: list[dict], boundary: Any, target: int = 250) -> dict:
    tracemalloc.start()
    t_start = time.perf_counter()

    # 1. Partitioning
    t0 = time.perf_counter()
    partitions = build_partitioned_hlb_boundaries(
        buildings=buildings,
        layout_boundary_geom=boundary,
        target_buildings_per_hlb=target,
        projected_crs=COIMBATORE_PROJECTED_CRS,
    )
    t_part = time.perf_counter() - t0

    hlb_geoms = [p[0] for p in partitions]
    k = len(hlb_geoms)

    # 2. Exact counting with STRtree
    t0 = time.perf_counter()
    exact_res = recalculate_exact_building_counts(
        hlb_boundaries=hlb_geoms,
        buildings=buildings,
        target_buildings_per_hlb=target,
    )
    t_count = time.perf_counter() - t0

    # 3. Geometry validation (containment, gaps, overlaps)
    t0 = time.perf_counter()
    geom_val = validate_layout_partition_geometry(
        hlb_boundaries=hlb_geoms,
        layout_boundary_geom=boundary,
        projected_crs=COIMBATORE_PROJECTED_CRS,
    )
    t_val = time.perf_counter() - t0

    total_time = time.perf_counter() - t_start
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    counts = exact_res["counts"]
    mean_count = sum(counts) / len(counts) if counts else 0.0
    variance = sum((c - mean_count) ** 2 for c in counts) / len(counts) if counts else 0.0
    std_dev = math.sqrt(variance)

    return {
        "dataset": dataset_name,
        "input_buildings": len(buildings),
        "target_per_hlb": target,
        "hlb_count": k,
        "partition_time_sec": round(t_part, 4),
        "counting_time_sec": round(t_count, 4),
        "validation_time_sec": round(t_val, 4),
        "total_time_sec": round(total_time, 4),
        "peak_memory_mb": round(peak_mem / (1024 * 1024), 2),
        "min_count": min(counts) if counts else 0,
        "max_count": max(counts) if counts else 0,
        "mean_count": round(mean_count, 1),
        "std_dev": round(std_dev, 2),
        "unassigned_count": exact_res["unassigned_count"],
        "duplicate_count": exact_res["duplicate_count"],
        "gap_ratio": geom_val["metrics"]["gap_ratio"],
        "overlap_ratio": geom_val["metrics"]["max_pairwise_overlap_ratio"],
        "is_valid": geom_val["is_valid"] and exact_res["is_valid"],
    }


def main():
    print("=" * 80)
    print("HLB SPATIAL ENGINE BENCHMARK SUITE")
    print("Target: 250 buildings/HLB | CRS: EPSG:32643")
    print("=" * 80)

    results = []

    # 1. 5,000 synthetic footprints
    b5k, bdry5k = generate_synthetic_grid_buildings(5000)
    res5k = run_benchmark("5,000 Synthetic", b5k, bdry5k)
    results.append(res5k)
    print(f"5k:   Total {res5k['total_time_sec']}s | Part: {res5k['partition_time_sec']}s | Count: {res5k['counting_time_sec']}s | HLBs: {res5k['hlb_count']} | Mem: {res5k['peak_memory_mb']} MB")

    # 2. 10,000 synthetic footprints
    b10k, bdry10k = generate_synthetic_grid_buildings(10000)
    res10k = run_benchmark("10,000 Synthetic", b10k, bdry10k)
    results.append(res10k)
    print(f"10k:  Total {res10k['total_time_sec']}s | Part: {res10k['partition_time_sec']}s | Count: {res10k['counting_time_sec']}s | HLBs: {res10k['hlb_count']} | Mem: {res10k['peak_memory_mb']} MB")

    # 3. 16,374 Real Arasur Google Open Buildings V3 footprints
    real_path = Path("app/data/open_buildings/arasur_real_open_buildings_v3.json")
    if real_path.exists():
        with open(real_path, encoding="utf-8") as f:
            data = json.load(f)
        real_bldgs = data["buildings"]
        lats = [b["latitude"] for b in real_bldgs]
        lons = [b["longitude"] for b in real_bldgs]
        real_bdry = box(min(lons) - 0.001, min(lats) - 0.001, max(lons) + 0.001, max(lats) + 0.001)

        res_real = run_benchmark("16,374 Real Open Buildings (Arasur)", real_bldgs, real_bdry)
        results.append(res_real)
        print(f"16.3k (Real): Total {res_real['total_time_sec']}s | Part: {res_real['partition_time_sec']}s | Count: {res_real['counting_time_sec']}s | HLBs: {res_real['hlb_count']} | Mem: {res_real['peak_memory_mb']} MB")

    # 4. 20,000 synthetic footprints
    b20k, bdry20k = generate_synthetic_grid_buildings(20000)
    res20k = run_benchmark("20,000 Synthetic", b20k, bdry20k)
    results.append(res20k)
    print(f"20k:  Total {res20k['total_time_sec']}s | Part: {res20k['partition_time_sec']}s | Count: {res20k['counting_time_sec']}s | HLBs: {res20k['hlb_count']} | Mem: {res20k['peak_memory_mb']} MB")

    print("\n" + "=" * 80)
    print("SUMMARY BENCHMARK TABLE")
    print("=" * 80)
    header = f"{'Dataset':<32} | {'Count':<6} | {'HLBs':<5} | {'Part(s)':<8} | {'Count(s)':<8} | {'Val(s)':<8} | {'Total(s)':<8} | {'Mem(MB)':<7}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r['dataset']:<32} | {r['input_buildings']:<6} | {r['hlb_count']:<5} | {r['partition_time_sec']:<8.3f} | {r['counting_time_sec']:<8.3f} | {r['validation_time_sec']:<8.3f} | {r['total_time_sec']:<8.3f} | {r['peak_memory_mb']:<7.2f}")

    print("\n" + "=" * 80)
    print("INVARIANT & TOPOLOGY VERIFICATION")
    print("=" * 80)
    for r in results:
        print(f"{r['dataset']}: Unassigned={r['unassigned_count']}, Dups={r['duplicate_count']}, Gap={r['gap_ratio']:.6%}, Overlap={r['overlap_ratio']:.6%}, Min={r['min_count']}, Max={r['max_count']}, Mean={r['mean_count']}, Valid={r['is_valid']}")

    # Save to JSON artifact
    out_file = Path("app/data/open_buildings/benchmark_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved benchmark results to {out_file}")


if __name__ == "__main__":
    main()
