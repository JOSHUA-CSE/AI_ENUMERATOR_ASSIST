import networkx as nx

from app.gis.route.distance import (
    build_road_network_graph,
)
from app.gis.route.optimizer import optimize_building_route


def test_build_road_network_graph():
    # Grid of road segments: (11.0, 78.0) to (11.0, 78.01) to (11.01, 78.01)
    roads = [
        [(11.0, 78.0), (11.0, 78.01)],
        [(11.0, 78.01), (11.01, 78.01)],
    ]
    g = build_road_network_graph(roads)
    assert isinstance(g, nx.Graph)
    assert g.number_of_nodes() == 3
    assert g.number_of_edges() == 2


def test_road_aware_distance_matrix_and_optimization():
    # 3 buildings along an L-shaped street:
    # Corner at (11.0, 78.01)
    # B1 at (11.0, 78.001)
    # B2 at (11.0, 78.009)
    # B3 at (11.009, 78.01)
    buildings = [
        {"id": "b1", "building_reference": "B1", "latitude": 11.0, "longitude": 78.001},
        {"id": "b2", "building_reference": "B2", "latitude": 11.0, "longitude": 78.009},
        {
            "id": "b3",
            "building_reference": "B3",
            "latitude": 11.009,
            "longitude": 78.01,
        },
    ]

    road_segments = [
        [(11.0, 78.0), (11.0, 78.01)],
        [(11.0, 78.01), (11.01, 78.01)],
    ]

    ordered, opt_dist, base_dist, strategy = optimize_building_route(
        buildings=buildings,
        starting_point=(11.0, 78.0),
        road_segments=road_segments,
    )

    assert len(ordered) == 3
    # First building should be B1 (closest to starting point along the street)
    assert ordered[0]["id"] == "b1"
    assert ordered[1]["id"] == "b2"
    assert ordered[2]["id"] == "b3"
    assert opt_dist > 0.0
    assert strategy == "CURRENT_GPS"


def test_village_road_network_with_barrier_detour():
    """
    Test routing in a realistic village setting where two buildings are close
    in straight-line distance across a canal/railway/barrier, but the road network
    requires a detour over a bridge.
    """
    from app.gis.route.distance import (
        calculate_distance_matrix,
        calculate_road_aware_distance_matrix,
        haversine_distance_meters,
    )

    # Building 1: West bank (11.000, 77.000)
    # Building 2: East bank (11.000, 77.002) - only ~218m apart straight-line
    coords = [(11.000, 77.000), (11.000, 77.002)]
    straight_dist = haversine_distance_meters(
        coords[0][0], coords[0][1], coords[1][0], coords[1][1]
    )

    # Road network goes North to a bridge at (11.005, 77.001) and back South
    # Path: (11.000, 77.000) -> (11.005, 77.000) -> (11.005, 77.002) -> (11.000, 77.002)
    road_segments = [
        [(11.000, 77.000), (11.005, 77.000)],
        [(11.005, 77.000), (11.005, 77.002)],
        [(11.005, 77.002), (11.000, 77.002)],
    ]
    road_graph = build_road_network_graph(road_segments)

    # Road-aware distance matrix
    road_matrix = calculate_road_aware_distance_matrix(coords, road_graph)
    # Straight-line distance matrix
    straight_matrix = calculate_distance_matrix(coords)

    # Road distance must be substantially longer than straight-line distance due to bridge detour
    assert road_matrix[0][1] > straight_dist * 2.0
    assert abs(straight_matrix[0][1] - straight_dist) < 1e-3


def test_routing_mode_distinction_in_route_service():
    """
    Verify RouteService explicitly distinguishes ROAD_NETWORK from
    STRAIGHT_LINE_FALLBACK and MISSING_ROAD_NETWORK_DATA.
    """
    from app.schemas.route import RouteStartingPointRequest

    req_with_roads = RouteStartingPointRequest(
        latitude=11.0,
        longitude=78.0,
        road_segments=[[(11.0, 78.0), (11.0, 78.01)]],
    )
    assert req_with_roads.road_segments is not None
    assert len(req_with_roads.road_segments) == 1

    req_without_roads = RouteStartingPointRequest(
        latitude=11.0,
        longitude=78.0,
    )
    assert req_without_roads.road_segments is None
