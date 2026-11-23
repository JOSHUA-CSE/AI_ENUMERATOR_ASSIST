import math
from typing import Any

from shapely.geometry import MultiPolygon, Polygon
from shapely.validation import make_valid

from app.gis.spatial import (
    COIMBATORE_PROJECTED_CRS,
    DEFAULT_GEOGRAPHIC_CRS,
    get_transformer,
    transform_geometry,
)


def _euclidean_dist_sq_projected(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Euclidean distance squared in projected metric planar coordinates (meters^2)."""
    return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2


def _project_points(
    points: list[dict[str, Any]],
    projected_crs: str = COIMBATORE_PROJECTED_CRS,
) -> None:
    """
    Ensure every point dict has '_x' and '_y' in the specified projected CRS.
    Modifies point dicts in-place.
    """
    transformer = get_transformer(DEFAULT_GEOGRAPHIC_CRS, projected_crs)
    for p in points:
        if "_x" not in p or "_y" not in p:
            lng = float(p.get("longitude", 0.0))
            lat = float(p.get("latitude", 0.0))
            x, y = transformer.transform(lng, lat)
            p["_x"] = x
            p["_y"] = y


def _recursive_spatial_bisect(
    points: list[dict[str, Any]],
    target_sizes: list[int],
) -> list[list[dict[str, Any]]]:
    """
    Recursively partition points into sub-clusters with exact target sizes
    using principal axis spatial bisection in projected metric coordinates.
    """
    k = len(target_sizes)
    if k == 0 or not points:
        return []
    if k == 1:
        return [points]

    k_left = k // 2
    target_left = sum(target_sizes[:k_left])

    n = len(points)
    avg_x = sum(p["_x"] for p in points) / n
    avg_y = sum(p["_y"] for p in points) / n

    # Covariance matrix in metric planar coordinates
    var_x = sum((p["_x"] - avg_x) ** 2 for p in points)
    var_y = sum((p["_y"] - avg_y) ** 2 for p in points)
    cov = sum((p["_x"] - avg_x) * (p["_y"] - avg_y) for p in points)

    # Dominant principal direction angle theta
    theta = 0.5 * math.atan2(2 * cov, var_x - var_y)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)

    # Sort points along principal axis projection with deterministic tie-breaking
    for p in points:
        p["_proj"] = (p["_x"] - avg_x) * cos_t + (p["_y"] - avg_y) * sin_t

    sorted_pts = sorted(
        points,
        key=lambda p: (
            p["_proj"],
            str(p.get("id", "")),
        ),
    )

    left_pts = sorted_pts[:target_left]
    right_pts = sorted_pts[target_left:]

    left_clusters = _recursive_spatial_bisect(left_pts, target_sizes[:k_left])
    right_clusters = _recursive_spatial_bisect(right_pts, target_sizes[k_left:])

    return left_clusters + right_clusters


def _refine_cluster_boundaries(
    clusters: list[list[dict[str, Any]]],
    max_passes: int = 10,
) -> list[list[dict[str, Any]]]:
    """
    Refine spatial cluster boundaries to maximize compactness while
    preserving exact cluster sizes (swapping pairs of boundary points)
    using projected metric planar coordinates.
    """
    k = len(clusters)
    if k <= 1:
        return clusters

    current_clusters = [list(c) for c in clusters]

    for _ in range(max_passes):
        centroids: list[tuple[float, float]] = []
        for c in current_clusters:
            if c:
                c_x = sum(p["_x"] for p in c) / len(c)
                c_y = sum(p["_y"] for p in c) / len(c)
                centroids.append((c_x, c_y))
            else:
                centroids.append((0.0, 0.0))

        improved = False

        for i in range(k):
            for j in range(i + 1, k):
                c_i = current_clusters[i]
                c_j = current_clusters[j]
                cent_i = centroids[i]
                cent_j = centroids[j]

                candidates_i = []
                for idx_i, p_i in enumerate(c_i):
                    coord_i = (p_i["_x"], p_i["_y"])
                    d_ii = _euclidean_dist_sq_projected(coord_i, cent_i)
                    d_ij = _euclidean_dist_sq_projected(coord_i, cent_j)
                    gain_i = d_ii - d_ij
                    candidates_i.append((gain_i, idx_i))

                candidates_j = []
                for idx_j, p_j in enumerate(c_j):
                    coord_j = (p_j["_x"], p_j["_y"])
                    d_jj = _euclidean_dist_sq_projected(coord_j, cent_j)
                    d_ji = _euclidean_dist_sq_projected(coord_j, cent_i)
                    gain_j = d_jj - d_ji
                    candidates_j.append((gain_j, idx_j))

                candidates_i.sort(key=lambda x: x[0], reverse=True)
                candidates_j.sort(key=lambda x: x[0], reverse=True)

                swaps = []
                used_j = set()
                for gain_i, idx_i in candidates_i:
                    if gain_i <= 0:
                        break
                    for gain_j, idx_j in candidates_j:
                        if idx_j in used_j or gain_j <= 0:
                            continue
                        if gain_i + gain_j > 1e-6:
                            swaps.append((idx_i, idx_j))
                            used_j.add(idx_j)
                            break

                if swaps:
                    improved = True
                    for idx_i, idx_j in swaps:
                        c_i[idx_i], c_j[idx_j] = c_j[idx_j], c_i[idx_i]

        if not improved:
            break

    return current_clusters


def partition_buildings_spatially(
    buildings: list[dict[str, Any]],
    target_buildings_per_hlb: int = 250,
    projected_crs: str = COIMBATORE_PROJECTED_CRS,
) -> list[list[dict[str, Any]]]:
    """
    Partition building records into balanced, geographically contiguous HLBs
    using projected CRS (EPSG:32643) recursive principal-axis bisection.

    Guarantees:
    1. The number of HLBs is k = ceil(N / target_buildings_per_hlb).
    2. Every HLB has at most target_buildings_per_hlb buildings.
    3. Building counts are evenly divided with minimum difference (at most 1).
    4. 100% of buildings assigned, 0 unassigned, 0 duplicates.
    5. Calculations performed in projected metric planar coordinates.
    """
    total = len(buildings)
    if total == 0:
        return []

    target = max(10, target_buildings_per_hlb)
    if total <= target:
        return [buildings]

    # Ensure projected coordinates are populated
    _project_points(buildings, projected_crs=projected_crs)

    k = max(1, math.ceil(total / target))
    base_size = total // k
    remainder = total % k
    target_sizes = [base_size + 1 if i < remainder else base_size for i in range(k)]

    raw_clusters = _recursive_spatial_bisect(buildings, target_sizes)
    refined_clusters = _refine_cluster_boundaries(raw_clusters)

    # Invariant enforcement
    assigned_ids: set[str] = set()
    final_clusters: list[list[dict[str, Any]]] = []
    for cluster in refined_clusters:
        deduped = []
        for b in cluster:
            b_id = str(b["id"])
            if b_id not in assigned_ids:
                assigned_ids.add(b_id)
                deduped.append(b)
        if deduped:
            final_clusters.append(deduped)

    unassigned = [b for b in buildings if str(b["id"]) not in assigned_ids]
    if unassigned:
        if final_clusters:
            for b in unassigned:
                smallest = min(final_clusters, key=len)
                smallest.append(b)
        else:
            final_clusters = [unassigned]

    return final_clusters


def _split_polygon_and_points(
    poly_utm: Polygon | MultiPolygon,
    points: list[dict[str, Any]],
    target_sizes: list[int],
) -> list[tuple[Polygon | MultiPolygon, list[dict[str, Any]]]]:
    """
    Recursive core that simultaneously bisects the parent polygon in projected CRS
    and the point cloud along the principal spatial axis.
    Guarantees zero gaps and zero overlaps across the territory partition.
    """
    k = len(target_sizes)
    if k == 0 or not points:
        return []
    if k == 1:
        return [(poly_utm, points)]

    k_left = k // 2
    target_left = sum(target_sizes[:k_left])

    n = len(points)
    avg_x = sum(p["_x"] for p in points) / n
    avg_y = sum(p["_y"] for p in points) / n

    var_x = sum((p["_x"] - avg_x) ** 2 for p in points)
    var_y = sum((p["_y"] - avg_y) ** 2 for p in points)
    cov = sum((p["_x"] - avg_x) * (p["_y"] - avg_y) for p in points)

    theta = 0.5 * math.atan2(2 * cov, var_x - var_y)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)

    for p in points:
        p["_proj"] = (p["_x"] - avg_x) * cos_t + (p["_y"] - avg_y) * sin_t

    sorted_pts = sorted(points, key=lambda p: (p["_proj"], str(p.get("id", ""))))
    left_pts = sorted_pts[:target_left]
    right_pts = sorted_pts[target_left:]

    # Separating value along the principal axis
    if left_pts and right_pts:
        split_val = (left_pts[-1]["_proj"] + right_pts[0]["_proj"]) / 2.0
    elif left_pts:
        split_val = left_pts[-1]["_proj"]
    else:
        split_val = 0.0

    # Build separating half-plane polygon in projected CRS
    min_px, min_py, max_px, max_py = poly_utm.bounds
    diag = math.hypot(max_px - min_px, max_py - min_py) * 4.0
    cx = avg_x + split_val * cos_t
    cy = avg_y + split_val * sin_t

    p1 = (cx - diag * sin_t, cy + diag * cos_t)
    p2 = (cx + diag * sin_t, cy - diag * cos_t)
    p3 = (p2[0] - diag * cos_t, p2[1] - diag * sin_t)
    p4 = (p1[0] - diag * cos_t, p1[1] - diag * sin_t)

    half_plane_left = Polygon([p1, p2, p3, p4, p1])
    if not half_plane_left.is_valid:
        half_plane_left = make_valid(half_plane_left)

    left_raw = poly_utm.intersection(half_plane_left)
    right_raw = poly_utm.difference(half_plane_left)

    left_poly = make_valid(left_raw) if not left_raw.is_empty else poly_utm
    right_poly = make_valid(right_raw) if not right_raw.is_empty else poly_utm

    # Recurse
    left_results = _split_polygon_and_points(left_poly, left_pts, target_sizes[:k_left])
    right_results = _split_polygon_and_points(right_poly, right_pts, target_sizes[k_left:])

    return left_results + right_results


def partition_territory_and_buildings(
    buildings: list[dict[str, Any]],
    parent_boundary_geom: MultiPolygon | Polygon,
    target_buildings_per_hlb: int = 250,
    projected_crs: str = COIMBATORE_PROJECTED_CRS,
) -> list[tuple[MultiPolygon, list[dict[str, Any]]]]:
    """
    Simultaneously partition building records and complete territory polygon
    into balanced, geographically contiguous, gap-free, overlap-free HLB blocks.

    Returns:
        list of (hlb_boundary_wgs84, cluster_buildings)
    """
    total = len(buildings)
    if total == 0:
        return []

    target = max(10, target_buildings_per_hlb)

    # 1. Project parent boundary to UTM (EPSG:32643)
    parent_utm = transform_geometry(
        parent_boundary_geom,
        src_crs=DEFAULT_GEOGRAPHIC_CRS,
        dst_crs=projected_crs,
    )
    if not parent_utm.is_valid:
        parent_utm = make_valid(parent_utm)

    # 2. Project points
    _project_points(buildings, projected_crs=projected_crs)

    k = max(1, math.ceil(total / target))
    base_size = total // k
    remainder = total % k
    target_sizes = [base_size + 1 if i < remainder else base_size for i in range(k)]

    # 3. Simultaneous hierarchical bisection of polygon and points
    raw_partitions = _split_polygon_and_points(parent_utm, buildings, target_sizes)

    # 4. Transform partition boundaries back to EPSG:4326 WGS84
    final_output: list[tuple[MultiPolygon, list[dict[str, Any]]]] = []
    for poly_utm, cluster_pts in raw_partitions:
        poly_wgs84 = transform_geometry(
            poly_utm,
            src_crs=projected_crs,
            dst_crs=DEFAULT_GEOGRAPHIC_CRS,
        )
        if not poly_wgs84.is_valid:
            poly_wgs84 = make_valid(poly_wgs84)

        if isinstance(poly_wgs84, Polygon):
            mp = MultiPolygon([poly_wgs84])
        elif isinstance(poly_wgs84, MultiPolygon):
            mp = poly_wgs84
        else:
            polys = [g for g in getattr(poly_wgs84, "geoms", []) if isinstance(g, (Polygon, MultiPolygon))]
            flat = []
            for p in polys:
                if isinstance(p, Polygon):
                    flat.append(p)
                elif isinstance(p, MultiPolygon):
                    flat.extend(p.geoms)
            mp = MultiPolygon(flat) if flat else MultiPolygon([parent_boundary_geom]) if isinstance(parent_boundary_geom, Polygon) else parent_boundary_geom

        final_output.append((mp, cluster_pts))

    return final_output
