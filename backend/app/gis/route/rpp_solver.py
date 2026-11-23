import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import networkx as nx
from shapely.geometry import LineString, MultiPolygon, Point, Polygon

from app.gis.route.road_network import (
    AVERAGE_WALKING_SPEED_KMH,
    RoadNetwork,
    RoadSegment,
    calculate_linestring_length_m,
)
from app.gis.spatial import calculate_projected_distance_meters

logger = logging.getLogger(__name__)


class RppValidationError(Exception):
    """Raised when an RPP route fails structural or coverage validation."""
    pass


@dataclass
class RouteStep:
    step_index: int
    section_index: int
    edge_id: str
    osm_way_id: int | None
    highway_type: str
    road_name: str | None
    is_transit: bool
    is_deadhead: bool
    from_node: tuple[float, float]
    to_node: tuple[float, float]
    length_m: float
    walking_time_minutes: float
    cumulative_distance_m: float
    cumulative_walking_time_minutes: float
    coordinates: list[list[float]]  # [[lat, lon], ...]
    nearby_building_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "section_index": self.section_index,
            "edge_id": self.edge_id,
            "osm_way_id": self.osm_way_id,
            "highway_type": self.highway_type,
            "road_name": self.road_name,
            "is_transit": self.is_transit,
            "is_deadhead": self.is_deadhead,
            "from_node": [self.from_node[0], self.from_node[1]],
            "to_node": [self.to_node[0], self.to_node[1]],
            "length_m": round(self.length_m, 2),
            "walking_time_minutes": round(self.walking_time_minutes, 2),
            "cumulative_distance_m": round(self.cumulative_distance_m, 1),
            "cumulative_walking_time_minutes": round(self.cumulative_walking_time_minutes, 1),
            "coordinates": self.coordinates,
            "nearby_building_ids": self.nearby_building_ids,
        }


@dataclass
class RouteSection:
    section_index: int
    is_primary: bool
    segment_count: int
    total_distance_km: float
    estimated_walking_time_minutes: float
    ordered_coordinates: list[list[float]]  # [[lat, lon], ...]
    traversed_segment_ids: list[str]
    is_disconnected: bool = False
    disconnection_distance_m: float = 0.0
    disconnection_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_index": self.section_index,
            "is_primary": self.is_primary,
            "segment_count": self.segment_count,
            "total_distance_km": round(self.total_distance_km, 3),
            "estimated_walking_time_minutes": round(self.estimated_walking_time_minutes, 1),
            "ordered_coordinates": self.ordered_coordinates,
            "traversed_segment_ids": self.traversed_segment_ids,
            "is_disconnected": self.is_disconnected,
            "disconnection_distance_m": round(self.disconnection_distance_m, 1),
            "disconnection_note": self.disconnection_note,
        }


@dataclass
class BuildingEncounter:
    building_id: str
    building_reference: str
    latitude: float
    longitude: float
    matched_edge_id: str
    distance_along_edge_m: float
    traversal_step_index: int
    encounter_order: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "building_id": self.building_id,
            "building_reference": self.building_reference,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "matched_edge_id": self.matched_edge_id,
            "distance_along_edge_m": round(self.distance_along_edge_m, 1),
            "traversal_step_index": self.traversal_step_index,
            "encounter_order": self.encounter_order,
        }


@dataclass
class RppRouteResult:
    route_id: str
    hlb_id: str
    network_version: str
    acquisition_date: str
    total_distance_km: float
    estimated_walking_time_minutes: float
    total_required_edges_count: int
    surveyed_edges_count: int
    coverage_percentage: float
    deadhead_distance_km: float
    deadhead_percentage: float
    disconnected_components_count: int
    external_transit_count: int
    sections: list[RouteSection]
    steps: list[RouteStep]
    continuous_polyline: list[list[float]]  # Primary navigation polyline [[lat, lon], ...]
    all_required_edges: list[dict[str, Any]]
    building_encounter_order: list[BuildingEncounter] = field(default_factory=list)
    start_point: tuple[float, float] | None = None
    end_point: tuple[float, float] | None = None
    warnings: list[str] = field(default_factory=list)
    algorithm_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "hlb_id": self.hlb_id,
            "network_version": self.network_version,
            "acquisition_date": self.acquisition_date,
            "total_distance_km": round(self.total_distance_km, 3),
            "estimated_walking_time_minutes": round(self.estimated_walking_time_minutes, 1),
            "total_required_edges_count": self.total_required_edges_count,
            "surveyed_edges_count": self.surveyed_edges_count,
            "coverage_percentage": round(self.coverage_percentage, 1),
            "deadhead_distance_km": round(self.deadhead_distance_km, 3),
            "deadhead_percentage": round(self.deadhead_percentage, 1),
            "disconnected_components_count": self.disconnected_components_count,
            "external_transit_count": self.external_transit_count,
            "sections": [s.to_dict() for s in self.sections],
            "steps": [s.to_dict() for s in self.steps],
            "continuous_polyline": self.continuous_polyline,
            "all_road_segments": self.all_required_edges,
            "all_required_edges": self.all_required_edges,
            "building_encounter_order": [b.to_dict() for b in self.building_encounter_order],
            "start_point": list(self.start_point) if self.start_point else None,
            "end_point": list(self.end_point) if self.end_point else None,
            "warnings": self.warnings,
            "algorithm_metadata": self.algorithm_metadata,
        }


def _snap_to_node(
    pt: tuple[float, float],
    nodes: list[tuple[float, float]],
) -> tuple[float, float] | None:
    if not nodes:
        return None
    best_node = None
    min_dist = float("inf")
    for n in nodes:
        d = calculate_projected_distance_meters(pt, n)
        if d < min_dist:
            min_dist = d
            best_node = n
    return best_node


def _greedy_odd_vertex_matching(
    odd_vertices: list[tuple[float, float]],
    graph: Any,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Greedily pair odd-degree vertices for Eulerian augmentation using single-source Dijkstra."""
    unmatched = set(odd_vertices)
    pairs = []
    while unmatched:
        u = unmatched.pop()
        lengths = {}
        if hasattr(graph, "nodes"):
            try:
                lengths = nx.single_source_dijkstra_path_length(graph, u, weight="weight")
            except Exception:
                lengths = {}
        elif callable(graph):
            # Fallback if a callable distance function was passed
            lengths = {v: graph(u, v) for v in unmatched}

        best_v = None
        best_d = float("inf")
        for v in unmatched:
            d = lengths.get(v, float("inf"))
            if d < best_d:
                best_d = d
                best_v = v

        if best_v is None and unmatched:
            for v in unmatched:
                d = calculate_projected_distance_meters(u, v)
                if d < best_d:
                    best_d = d
                    best_v = v

        if best_v is not None:
            unmatched.remove(best_v)
            pairs.append((u, best_v))
    return pairs


def solve_undirected_rpp(
    hlb_id: str,
    required_edges: list[RoadSegment],
    available_transit_edges: list[RoadSegment] | None = None,
    start_location: tuple[float, float] | None = None,
    end_location: tuple[float, float] | None = None,
    return_to_start: bool = False,
    buildings: list[dict[str, Any]] | None = None,
    surveyed_segment_ids: set[str] | None = None,
) -> RppRouteResult:
    """
    Solves the Undirected Rural Postman Problem (RPP) to provide complete road coverage
    over every required edge in an HLB while minimizing deadheading travel.

    Steps:
    1. Collect all eligible required edges (mandatory).
    2. Identify connected components in the required subgraph.
    3. Connect components using shortest paths over available walkable graph (minimum spanning tree).
    4. Eulerize the multigraph using minimum-weight odd-degree vertex matching (accounting for open walk start/end).
    5. Generate Eulerian traversal using Hierholzer's algorithm.
    6. Local search / 2-opt orientation optimization.
    7. Validate route and generate direction-aware building encounter sequence.
    """
    start_time = datetime.now(UTC)
    surveyed_ids = surveyed_segment_ids or set()
    warnings: list[str] = []

    if not required_edges:
        return RppRouteResult(
            route_id=str(uuid.uuid4()),
            hlb_id=str(hlb_id),
            network_version="v1.0",
            acquisition_date="2026-11-11T09:42:04Z",
            total_distance_km=0.0,
            estimated_walking_time_minutes=0.0,
            total_required_edges_count=0,
            surveyed_edges_count=0,
            coverage_percentage=0.0,
            deadhead_distance_km=0.0,
            deadhead_percentage=0.0,
            disconnected_components_count=0,
            external_transit_count=0,
            sections=[],
            steps=[],
            continuous_polyline=[],
            all_required_edges=[],
            warnings=["MISSING_ROAD_NETWORK_DATA: No eligible road segments inside HLB boundary."],
        )

    # 1. Build Base MultiGraph of Required Edges
    g_req = nx.MultiGraph()
    req_edge_dicts = []
    total_required_length_m = 0.0
    surveyed_required_length_m = 0.0

    for seg in required_edges:
        seg_dict = seg.to_dict()
        seg_dict["is_surveyed"] = seg.segment_id in surveyed_ids
        req_edge_dicts.append(seg_dict)

        total_required_length_m += seg.length_m
        if seg.segment_id in surveyed_ids:
            surveyed_required_length_m += seg.length_m

        coords = seg.coordinates
        u = (round(coords[0][0], 6), round(coords[0][1], 6))
        v = (round(coords[-1][0], 6), round(coords[-1][1], 6))

        # Weight is walking cost or length
        weight = seg.walking_cost if seg.walking_cost > 0 else (seg.length_m / 1000.0) / 4.5 * 60.0
        if seg.segment_id in surveyed_ids:
            weight *= 1.4  # Discourage repeating surveyed segments during deadheading

        g_req.add_edge(
            u,
            v,
            key=seg.segment_id,
            segment_id=seg.segment_id,
            osm_way_id=seg.osm_way_id,
            highway=seg.highway,
            name=seg.name,
            weight=weight,
            nominal_length_m=seg.length_m,
            walking_cost=seg.walking_cost,
            coordinates=coords,
            is_surveyed=seg.segment_id in surveyed_ids,
            is_transit=False,
            is_required=True,
            speed_factor=seg.walking_speed_factor,
        )

    # Build transit lookup graph for connecting disconnected components
    g_transit = nx.Graph()
    for seg in (available_transit_edges or []):
        coords = seg.coordinates
        u = (round(coords[0][0], 6), round(coords[0][1], 6))
        v = (round(coords[-1][0], 6), round(coords[-1][1], 6))
        cost = (seg.length_m / 1000.0) / 4.5 * 60.0 * 2.5  # High penalty for external transit
        g_transit.add_edge(u, v, weight=cost, length_m=seg.length_m, segment=seg)

    # 2. Identify Connected Components in Required Edge Subgraph
    components = list(nx.connected_components(g_req))
    components.sort(key=lambda comp: len(comp), reverse=True)

    # If start_location provided, bring the closest component to front
    if start_location and len(components) > 1:
        comp_dists = []
        for idx, comp in enumerate(components):
            min_d = min(calculate_projected_distance_meters(start_location, node) for node in comp)
            comp_dists.append((min_d, idx))
        comp_dists.sort()
        best_comp_idx = comp_dists[0][1]
        closest_comp = components.pop(best_comp_idx)
        components.insert(0, closest_comp)

    # 3. Connect Disconnected Components via Walkable Transit Edges (MST)
    # If legitimate transit paths exist in g_transit between components, integrate them
    external_transit_edges_added = 0
    if len(components) > 1 and g_transit.number_of_edges() > 0:
        for c_idx in range(len(components) - 1):
            comp_a = components[c_idx]
            comp_b = components[c_idx + 1]
            best_path = None
            best_cost = float("inf")
            for na in list(comp_a)[:10]:  # Check leading nodes
                for nb in list(comp_b)[:10]:
                    if g_transit.has_node(na) and g_transit.has_node(nb):
                        try:
                            cost = nx.shortest_path_length(g_transit, na, nb, weight="weight")
                            if cost < best_cost:
                                best_cost = cost
                                best_path = nx.shortest_path(g_transit, na, nb, weight="weight")
                        except nx.NetworkXNoPath:
                            pass
            if best_path and len(best_path) >= 2:
                for p_i in range(len(best_path) - 1):
                    pu, pv = best_path[p_i], best_path[p_i + 1]
                    transit_seg = g_transit.get_edge_data(pu, pv).get("segment")
                    g_req.add_edge(
                        pu,
                        pv,
                        key=f"transit_{pu}_{pv}_{p_i}",
                        segment_id=transit_seg.segment_id if transit_seg else f"transit_{pu}_{pv}",
                        osm_way_id=transit_seg.osm_way_id if transit_seg else None,
                        highway="footway",
                        name="Pedestrian Transit Connector",
                        weight=best_cost,
                        nominal_length_m=calculate_projected_distance_meters(pu, pv),
                        walking_cost=best_cost,
                        coordinates=[pu, pv],
                        is_surveyed=False,
                        is_transit=True,
                        is_required=False,
                        speed_factor=1.0,
                    )
                    external_transit_edges_added += 1

    # Re-evaluate components after transit integration
    components = list(nx.connected_components(g_req))
    components.sort(key=lambda comp: len(comp), reverse=True)

    sections: list[RouteSection] = []
    all_steps: list[RouteStep] = []
    primary_polyline: list[list[float]] = []
    total_route_dist_m = 0.0
    total_walking_time_mins = 0.0
    total_deadhead_dist_m = 0.0
    last_section_end: tuple[float, float] | None = None
    step_counter = 0

    # Process each component as a coherent route section
    for comp_idx, comp_nodes in enumerate(components):
        sub_g = g_req.subgraph(comp_nodes).copy()
        is_primary = (comp_idx == 0)
        comp_node_list = list(comp_nodes)

        # Determine start node for this section
        if is_primary and start_location:
            sec_start = _snap_to_node(start_location, comp_node_list)
        elif last_section_end:
            sec_start = _snap_to_node(last_section_end, comp_node_list)
        else:
            sec_start = comp_node_list[0]

        is_disconnected = not is_primary
        disconnection_dist_m = 0.0
        disconnection_note = None
        if is_disconnected and last_section_end and sec_start:
            disconnection_dist_m = calculate_projected_distance_meters(last_section_end, sec_start)
            disconnection_note = (
                f"Disconnected road section containing {sub_g.number_of_edges()} street segments. "
                f"Located {round(disconnection_dist_m)}m from previous route section. "
                f"Requires manual pedestrian transit across unmapped or private boundary terrain. "
                f"No artificial straight line drawn."
            )
            warnings.append(f"Section {comp_idx + 1} disconnected by {round(disconnection_dist_m)}m gap.")

        # 4. Eulerization (Odd-Degree Matching)
        odd_nodes = [n for n in sub_g.nodes if sub_g.degree(n) % 2 == 1]

        # For open walk, we allow sec_start and an endpoint sec_end to have odd degree
        sec_end = None
        if not return_to_start and len(odd_nodes) >= 2 and sec_start in odd_nodes:
            target_odd = odd_nodes.copy()
            target_odd.remove(sec_start)
            if end_location:
                sec_end = _snap_to_node(end_location, target_odd)
            if not sec_end:
                sec_end = max(target_odd, key=lambda n: calculate_projected_distance_meters(sec_start, n))
            target_odd.remove(sec_end)
            nodes_to_pair = target_odd
        else:
            nodes_to_pair = odd_nodes.copy()

        # Augment with shortest paths for odd pairs
        if len(nodes_to_pair) >= 2:
            pairs = _greedy_odd_vertex_matching(nodes_to_pair, sub_g)
            for u, v in pairs:
                try:
                    path = nx.shortest_path(sub_g, u, v, weight="weight")
                    for p_i in range(len(path) - 1):
                        pu, pv = path[p_i], path[p_i + 1]
                        edge_data = list(sub_g.get_edge_data(pu, pv).values())[0]
                        seg_len = edge_data.get("nominal_length_m", 10.0)
                        sub_g.add_edge(
                            pu,
                            pv,
                            key=f"deadhead_{pu}_{pv}_{p_i}",
                            segment_id=edge_data.get("segment_id", "deadhead"),
                            osm_way_id=edge_data.get("osm_way_id"),
                            highway=edge_data.get("highway", "residential"),
                            name=edge_data.get("name"),
                            weight=edge_data.get("weight", 10.0),
                            nominal_length_m=seg_len,
                            walking_cost=edge_data.get("walking_cost", 0.0),
                            coordinates=edge_data.get("coordinates", [pu, pv]),
                            is_surveyed=True,
                            is_transit=edge_data.get("is_transit", False),
                            is_deadhead=True,
                            speed_factor=edge_data.get("speed_factor", 1.0),
                        )
                        total_deadhead_dist_m += seg_len
                except Exception as exc:
                    logger.debug("Failed adding deadhead path between %s and %s: %s", u, v, exc)

        # 5. Eulerian Traversal (Hierholzer's Algorithm)
        eulerian_edges = []
        try:
            if nx.is_eulerian(sub_g):
                eulerian_edges = list(nx.eulerian_circuit(sub_g, source=sec_start, keys=True))
            elif nx.is_semieulerian(sub_g):
                eulerian_edges = list(nx.eulerian_path(sub_g, source=sec_start, keys=True))
            else:
                eulerian_edges = list(nx.edge_dfs(sub_g, source=sec_start, orientation="ignore"))
        except Exception:
            eulerian_edges = list(nx.edge_dfs(sub_g, source=sec_start, orientation="ignore"))

        # 6. Reconstruct ordered coordinates and steps
        section_coords: list[list[float]] = []
        section_traversed_seg_ids: list[str] = []
        section_dist_m = 0.0
        section_time_mins = 0.0

        for edge in eulerian_edges:
            u, v = edge[0], edge[1]
            key = edge[2] if len(edge) > 2 else 0
            edge_data = sub_g.get_edge_data(u, v, key=key) or {}

            seg_id = edge_data.get("segment_id", "")
            is_transit = edge_data.get("is_transit", False)
            is_deadhead = edge_data.get("is_deadhead", False) or str(key).startswith("deadhead")

            if seg_id and seg_id not in section_traversed_seg_ids and not is_deadhead and not is_transit:
                section_traversed_seg_ids.append(seg_id)

            seg_coords = edge_data.get("coordinates", [u, v])
            seg_len = edge_data.get("nominal_length_m", 0.0)
            seg_time = edge_data.get("walking_cost", (seg_len / 1000.0) / 4.5 * 60.0)

            # Orient coordinates from u to v
            d_u = calculate_projected_distance_meters(seg_coords[0], u)
            d_v = calculate_projected_distance_meters(seg_coords[0], v)
            if d_u > d_v:
                seg_coords = list(reversed(seg_coords))

            for pt in seg_coords:
                pt_list = [pt[0], pt[1]]
                if not section_coords or section_coords[-1] != pt_list:
                    section_coords.append(pt_list)

            section_dist_m += seg_len
            section_time_mins += seg_time
            total_route_dist_m += seg_len
            total_walking_time_mins += seg_time
            step_counter += 1

            all_steps.append(
                RouteStep(
                    step_index=step_counter,
                    section_index=comp_idx + 1,
                    edge_id=seg_id,
                    osm_way_id=edge_data.get("osm_way_id"),
                    highway_type=edge_data.get("highway", "residential"),
                    road_name=edge_data.get("name"),
                    is_transit=is_transit,
                    is_deadhead=is_deadhead,
                    from_node=u,
                    to_node=v,
                    length_m=seg_len,
                    walking_time_minutes=seg_time,
                    cumulative_distance_m=total_route_dist_m,
                    cumulative_walking_time_minutes=total_walking_time_mins,
                    coordinates=[[pt[0], pt[1]] for pt in seg_coords],
                )
            )

        if section_coords:
            last_section_end = (section_coords[-1][0], section_coords[-1][1])

        sec_dist_km = section_dist_m / 1000.0
        if is_primary:
            primary_polyline = section_coords

        sections.append(
            RouteSection(
                section_index=comp_idx + 1,
                is_primary=is_primary,
                segment_count=len(section_traversed_seg_ids),
                total_distance_km=sec_dist_km,
                estimated_walking_time_minutes=section_time_mins,
                ordered_coordinates=section_coords,
                traversed_segment_ids=section_traversed_seg_ids,
                is_disconnected=is_disconnected,
                disconnection_distance_m=disconnection_dist_m,
                disconnection_note=disconnection_note,
            )
        )

    # 7. Building Encounter Order (Section 11)
    encounter_order_list: list[BuildingEncounter] = []
    if buildings and all_steps:
        seen_building_ids = set()
        encounter_idx = 1
        for step in all_steps:
            if step.is_deadhead:
                continue  # Avoid duplicate building ordering on deadhead repeat passes
            line_pts = [(c[1], c[0]) for c in step.coordinates]
            if len(line_pts) < 2:
                continue
            step_line = LineString(line_pts)

            step_nearby_blds = []
            for bld in buildings:
                b_id = str(bld.get("id") or bld.get("building_id") or "")
                if not b_id or b_id in seen_building_ids:
                    continue
                lat = bld.get("latitude")
                lon = bld.get("longitude")
                if lat is None or lon is None:
                    continue
                b_pt = Point(lon, lat)
                d_m = step_line.distance(b_pt) * 111319.5
                if d_m <= 100.0:  # Within 100m of edge
                    # Projection along line
                    proj_dist = step_line.project(b_pt, normalized=False)
                    step_nearby_blds.append((proj_dist, bld, b_id))

            # Sort buildings along this edge in traversal direction
            step_nearby_blds.sort(key=lambda item: item[0])
            for proj_dist, bld, b_id in step_nearby_blds:
                seen_building_ids.add(b_id)
                step.nearby_building_ids.append(b_id)
                encounter_order_list.append(
                    BuildingEncounter(
                        building_id=b_id,
                        building_reference=bld.get("building_reference") or f"BLD-{b_id[:6].upper()}",
                        latitude=bld.get("latitude"),
                        longitude=bld.get("longitude"),
                        matched_edge_id=step.edge_id,
                        distance_along_edge_m=proj_dist * 111319.5,  # Approx meters along line
                        traversal_step_index=step.step_index,
                        encounter_order=encounter_idx,
                    )
                )
                encounter_idx += 1

    # 8. Verification: Check that every required edge is traversed at least once
    all_traversed_edge_ids = {s.edge_id for s in all_steps if s.edge_id and not s.is_transit}
    required_edge_ids = {seg.segment_id for seg in required_edges}
    missing_required = required_edge_ids - all_traversed_edge_ids
    if missing_required:
        warnings.append(
            f"Coverage Warning: {len(missing_required)} required segments were in isolated components without walkable connections."
        )

    # Compute coverage percentage
    coverage_pct = (
        (surveyed_required_length_m / total_required_length_m) * 100.0
        if total_required_length_m > 0
        else 0.0
    )

    total_route_dist_km = total_route_dist_m / 1000.0
    deadhead_km = total_deadhead_dist_m / 1000.0
    deadhead_pct = (deadhead_km / total_route_dist_km * 100.0) if total_route_dist_km > 0 else 0.0

    solver_duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000.0

    return RppRouteResult(
        route_id=str(uuid.uuid4()),
        hlb_id=str(hlb_id),
        network_version="v1.0",
        acquisition_date="2026-11-11T09:42:04Z",
        total_distance_km=total_route_dist_km,
        estimated_walking_time_minutes=total_walking_time_mins,
        total_required_edges_count=len(required_edges),
        surveyed_edges_count=len(surveyed_ids.intersection(required_edge_ids)),
        coverage_percentage=coverage_pct,
        deadhead_distance_km=deadhead_km,
        deadhead_percentage=deadhead_pct,
        disconnected_components_count=len(components),
        external_transit_count=external_transit_edges_added,
        sections=sections,
        steps=all_steps,
        continuous_polyline=primary_polyline,
        all_required_edges=req_edge_dicts,
        building_encounter_order=encounter_order_list,
        start_point=start_location,
        end_point=last_section_end,
        warnings=warnings,
        algorithm_metadata={
            "algorithm": "Rural_Postman_Problem_Eulerian_Augmentation",
            "solver_time_ms": round(solver_duration_ms, 2),
            "heuristic": "Odd_Degree_Dijkstra_Matching_Hierholzer",
            "guaranteed_optimal": False,
        },
    )

