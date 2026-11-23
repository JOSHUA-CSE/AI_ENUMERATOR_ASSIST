import json
import logging
import math
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROADS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "roads"
DEFAULT_ARASUR_ROADS_FILE = ROADS_DIR / "arasur_osm_roads.json"

WALKABLE_HIGHWAY_TYPES = {
    "residential",
    "unclassified",
    "living_street",
    "footway",
    "pedestrian",
    "path",
    "service",
    "track",
    "steps",
    "tertiary",
    "secondary",
    "primary",
}

UNSUITABLE_HIGHWAY_TYPES = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
}

_CACHED_PEDESTRIAN_GRAPH: Any | None = None
_CACHED_GRAPH_METADATA: dict[str, Any] | None = None


def haversine_distance_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate geographic straight-line (great-circle) distance between two
    WGS84 coordinate pairs in meters using the Haversine formula.

    Note: This computes coordinate straight-line distance, not walking or road distance.
    """
    # Earth mean radius in meters (WGS84 spherical approximation)
    r = 6371000.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return r * c


def calculate_distance_matrix(coords: list[tuple[float, float]]) -> list[list[float]]:
    """
    Compute pairwise symmetric distance matrix in meters for
    a list of (lat, lon) coordinates with precomputed radians for high performance.
    """
    n = len(coords)
    matrix = [[0.0] * n for _ in range(n)]
    rad_coords = [
        (math.radians(lat), math.radians(lon), math.cos(math.radians(lat)))
        for lat, lon in coords
    ]
    r = 6371000.0

    for i in range(n):
        phi1, lon1, cos_phi1 = rad_coords[i]
        row_i = matrix[i]
        for j in range(i + 1, n):
            phi2, lon2, cos_phi2 = rad_coords[j]
            dphi_half = (phi2 - phi1) * 0.5
            dlon_half = (lon2 - lon1) * 0.5
            sin_dphi = math.sin(dphi_half)
            sin_dlon = math.sin(dlon_half)
            a = sin_dphi * sin_dphi + cos_phi1 * cos_phi2 * sin_dlon * sin_dlon
            if a > 1.0:
                a = 1.0
            dist = r * (2.0 * math.asin(math.sqrt(a)))
            row_i[j] = dist
            matrix[j][i] = dist

    return matrix


def calculate_path_distance_km(
    path: list[int],
    dist_matrix: list[list[float]],
    start_point: tuple[float, float] | None = None,
    coords: list[tuple[float, float]] | None = None,
    return_to_start: bool = False,
) -> float:
    """
    Calculate total path length in kilometers for an ordered sequence of node indices.
    If start_point is provided, includes distance from start_point to the first node.
    If return_to_start is True, includes return distance back to start_point (or first node).
    """
    if not path:
        return 0.0

    total_meters = 0.0

    if start_point is not None and coords is not None and len(path) > 0:
        first_idx = path[0]
        first_coord = coords[first_idx]
        total_meters += haversine_distance_meters(
            start_point[0], start_point[1], first_coord[0], first_coord[1]
        )

    for k in range(len(path) - 1):
        i = path[k]
        j = path[k + 1]
        total_meters += dist_matrix[i][j]

    if return_to_start and len(path) > 0:
        last_idx = path[-1]
        if start_point is not None:
            last_coord = coords[last_idx] if coords is not None else None
            if last_coord is not None:
                total_meters += haversine_distance_meters(
                    last_coord[0], last_coord[1], start_point[0], start_point[1]
                )
        elif len(path) > 1:
            # Return to initial building
            first_idx = path[0]
            total_meters += dist_matrix[last_idx][first_idx]

    return round(total_meters / 1000.0, 4)


def build_road_network_graph(
    road_segments: list[list[tuple[float, float]]],
) -> Any:
    """
    Build a NetworkX spatial road graph from polylines of coordinates (lat, lon).
    Nodes are coordinate tuples (lat, lon) rounded to 6 decimal places.
    Edges have weight equal to road segment distance in meters.
    """
    import networkx as nx

    g = nx.Graph()
    for line in road_segments:
        for i in range(len(line) - 1):
            u = (round(line[i][0], 6), round(line[i][1], 6))
            v = (round(line[i + 1][0], 6), round(line[i + 1][1], 6))
            if u != v:
                dist = haversine_distance_meters(u[0], u[1], v[0], v[1])
                g.add_edge(u, v, weight=dist)
    return g


def snap_to_nearest_graph_node(
    point: tuple[float, float],
    graph: Any,
) -> tuple[float, float] | None:
    """
    Find the closest node in the road network graph to a given (lat, lon) point.
    """
    if not graph or graph.number_of_nodes() == 0:
        return None
    best_node = None
    best_dist = float("inf")
    for node in graph.nodes:
        d = haversine_distance_meters(point[0], point[1], node[0], node[1])
        if d < best_dist:
            best_dist = d
            best_node = node
    return best_node


def calculate_road_aware_distance_matrix(
    coords: list[tuple[float, float]],
    road_graph: Any | None = None,
) -> list[list[float]]:
    """
    Compute pairwise distance matrix using road network graph shortest paths (Dijkstra),
    falling back to Haversine distance when no road graph is provided or between disconnected components.
    """
    if not road_graph or getattr(road_graph, "number_of_nodes", lambda: 0)() < 2:
        return calculate_distance_matrix(coords)

    import networkx as nx

    n = len(coords)
    snapped = [snap_to_nearest_graph_node(c, road_graph) for c in coords]
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        u_snap = snapped[i]
        lengths: dict = {}
        if u_snap and u_snap in road_graph:
            try:
                lengths = nx.single_source_dijkstra_path_length(
                    road_graph, u_snap, weight="weight"
                )
            except Exception:
                lengths = {}

        for j in range(i + 1, n):
            v_snap = snapped[j]
            dist = None
            if u_snap and v_snap and v_snap in lengths:
                snap_i = haversine_distance_meters(
                    coords[i][0], coords[i][1], u_snap[0], u_snap[1]
                )
                snap_j = haversine_distance_meters(
                    coords[j][0], coords[j][1], v_snap[0], v_snap[1]
                )
                dist = snap_i + lengths[v_snap] + snap_j

            if dist is None or dist <= 0.0:
                dist = haversine_distance_meters(
                    coords[i][0], coords[i][1], coords[j][0], coords[j][1]
                )

            matrix[i][j] = dist
            matrix[j][i] = dist

    return matrix


def load_osm_pedestrian_network(
    roads_file: Path | str | None = None,
) -> tuple[Any, dict[str, Any]] | None:
    """
    Load OSM road network from GeoJSON/Overpass export and build a NetworkX
    pedestrian-walkable spatial graph.
    Filters out motorways, motorways links, trunk roads (unless foot=yes),
    and roads explicitly marked private or non-walkable.
    """
    global _CACHED_PEDESTRIAN_GRAPH, _CACHED_GRAPH_METADATA

    if _CACHED_PEDESTRIAN_GRAPH is not None and _CACHED_GRAPH_METADATA is not None:
        return _CACHED_PEDESTRIAN_GRAPH, _CACHED_GRAPH_METADATA

    target_file = Path(roads_file) if roads_file else DEFAULT_ARASUR_ROADS_FILE
    if not target_file.exists():
        logger.info("OSM roads file not found: %s", target_file)
        return None

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        import networkx as nx

        g = nx.Graph()
        elements = data.get("elements", [])
        edge_count = 0
        min_lat, min_lon, max_lat, max_lon = 90.0, 180.0, -90.0, -180.0

        for el in elements:
            if el.get("type") != "way":
                continue

            tags = el.get("tags", {})
            highway = tags.get("highway", "")
            foot = tags.get("foot", "")
            access = tags.get("access", "")

            # Exclude explicit non-walkable or private access
            if access in ("private", "no") or foot == "no":
                continue

            # Exclude motorways, trunk roads unless foot is explicitly yes
            if highway in UNSUITABLE_HIGHWAY_TYPES and foot != "yes":
                continue

            # Check if highway type is in walkable set or generic highway
            if highway not in WALKABLE_HIGHWAY_TYPES and foot != "yes":
                continue

            geom = el.get("geometry", [])
            for i in range(len(geom) - 1):
                p1 = (round(geom[i]["lat"], 6), round(geom[i]["lon"], 6))
                p2 = (round(geom[i + 1]["lat"], 6), round(geom[i + 1]["lon"], 6))
                if p1 != p2:
                    dist = haversine_distance_meters(p1[0], p1[1], p2[0], p2[1])
                    g.add_edge(p1, p2, weight=dist, highway=highway)
                    edge_count += 1
                    min_lat = min(min_lat, p1[0], p2[0])
                    max_lat = max(max_lat, p1[0], p2[0])
                    min_lon = min(min_lon, p1[1], p2[1])
                    max_lon = max(max_lon, p1[1], p2[1])

        if g.number_of_nodes() == 0:
            return None

        metadata = {
            "source_file": target_file.name,
            "node_count": g.number_of_nodes(),
            "edge_count": g.number_of_edges(),
            "bounds": {
                "min_lat": min_lat,
                "min_lon": min_lon,
                "max_lat": max_lat,
                "max_lon": max_lon,
            },
        }

        _CACHED_PEDESTRIAN_GRAPH = g
        _CACHED_GRAPH_METADATA = metadata
        logger.info(
            "Built pedestrian road graph: %d nodes, %d edges from %s",
            g.number_of_nodes(),
            g.number_of_edges(),
            target_file.name,
        )
        return g, metadata
    except Exception as exc:
        logger.error("Failed to build pedestrian road graph from %s: %s", target_file, exc)
        return None
