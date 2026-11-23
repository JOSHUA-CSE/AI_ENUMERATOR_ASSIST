import enum
import math
from typing import Any

from shapely.geometry import MultiPolygon, Point, Polygon, shape

from app.gis.spatial import geometry_to_geojson_dict


class BoundaryStatusEnum(enum.StrEnum):
    INSIDE = "INSIDE"
    OUTSIDE = "OUTSIDE"
    BOUNDARY_UNCERTAIN = "BOUNDARY_UNCERTAIN"
    UNKNOWN = "UNKNOWN"


def point_to_segment_distance_meters(
    px: float,
    py: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> float:
    """
    Calculate minimum distance from point (px, py) to segment (x1, y1)-(x2, y2)
    in Euclidean 2D space.
    """
    dx = x2 - x1
    dy = y2 - y1
    len_sq = dx * dx + dy * dy
    if len_sq == 0.0:
        ex = px - x1
        ey = py - y1
        return math.sqrt(ex * ex + ey * ey)

    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    ex = px - proj_x
    ey = py - proj_y
    return math.sqrt(ex * ex + ey * ey)


def calculate_min_distance_to_boundary_meters(
    geom: Polygon | MultiPolygon,
    latitude: float,
    longitude: float,
) -> float:
    """
    Calculate shortest straight-line distance in meters from (latitude, longitude)
    to the exterior rings of the polygon/multipolygon boundary.
    """
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(latitude))

    polygons: list[Polygon] = (
        list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    )
    min_dist = float("inf")

    for poly in polygons:
        coords = list(poly.exterior.coords)
        for i in range(len(coords) - 1):
            lon1, lat1 = coords[i]
            lon2, lat2 = coords[i + 1]

            x1 = (lon1 - longitude) * m_per_deg_lon
            y1 = (lat1 - latitude) * m_per_deg_lat
            x2 = (lon2 - longitude) * m_per_deg_lon
            y2 = (lat2 - latitude) * m_per_deg_lat

            d = point_to_segment_distance_meters(0.0, 0.0, x1, y1, x2, y2)
            if d < min_dist:
                min_dist = d

    return min_dist


def check_point_in_hlb_boundary(
    boundary_geom: Any,
    latitude: float,
    longitude: float,
    accuracy_meters: float | None = None,
    max_reliable_accuracy: float = 150.0,
) -> tuple[BoundaryStatusEnum, float | None, str | None]:
    """
    Evaluate whether a device GPS observation is INSIDE, OUTSIDE, or BOUNDARY_UNCERTAIN
    relative to an approved HLB boundary polygon.

    Parameters:
    - boundary_geom: WKBElement, GeoJSON dict/str, or Shapely geometry
    - latitude: float [-90.0, 90.0]
    - longitude: float [-180.0, 180.0]
    - accuracy_meters: device horizontal accuracy radius in meters
    - max_reliable_accuracy: accuracy threshold beyond which the measurement is UNKNOWN

    Returns:
    - (status, distance_to_boundary_meters, explanation_message)
    """
    # 1. Validate coordinate ranges
    if not (isinstance(latitude, (int, float)) and isinstance(longitude, (int, float))):
        return (
            BoundaryStatusEnum.UNKNOWN,
            None,
            "Coordinates must be numeric floating point numbers",
        )

    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        return (
            BoundaryStatusEnum.UNKNOWN,
            None,
            f"Coordinates ({latitude}, {longitude}) out of range [-90..90, -180..180]",
        )

    # 2. Validate accuracy if supplied
    if accuracy_meters is not None:
        if not isinstance(accuracy_meters, (int, float)):
            return (
                BoundaryStatusEnum.UNKNOWN,
                None,
                "Accuracy must be a numeric value",
            )
        if accuracy_meters < 0.0:
            return (
                BoundaryStatusEnum.UNKNOWN,
                None,
                f"Negative accuracy ({accuracy_meters}m) is invalid",
            )

    # 3. Parse and validate boundary geometry
    if boundary_geom is None:
        return (
            BoundaryStatusEnum.UNKNOWN,
            None,
            "HLB boundary geometry is missing or unavailable",
        )

    shapely_geom: Polygon | MultiPolygon | None = None
    try:
        if isinstance(boundary_geom, (Polygon, MultiPolygon)):
            shapely_geom = boundary_geom
        else:
            geojson_dict = geometry_to_geojson_dict(boundary_geom)
            if geojson_dict:
                parsed = shape(geojson_dict)
                if isinstance(parsed, (Polygon, MultiPolygon)):
                    shapely_geom = parsed
    except Exception as exc:
        return (
            BoundaryStatusEnum.UNKNOWN,
            None,
            f"Failed to parse boundary geometry: {exc}",
        )

    if shapely_geom is None or shapely_geom.is_empty or not shapely_geom.is_valid:
        return (
            BoundaryStatusEnum.UNKNOWN,
            None,
            "Boundary geometry is invalid or empty",
        )

    # 4. Calculate metric distance to boundary perimeter
    dist_meters = calculate_min_distance_to_boundary_meters(
        shapely_geom, latitude, longitude
    )

    # 5. Point in polygon containment
    point = Point(longitude, latitude)
    is_inside = shapely_geom.covers(point)

    # 6. Evaluate accuracy & uncertainty
    if accuracy_meters is not None and accuracy_meters > max_reliable_accuracy:
        return (
            BoundaryStatusEnum.UNKNOWN,
            round(dist_meters, 2),
            f"GPS accuracy (±{accuracy_meters:.1f}m) exceeds "
            f"reliable limit ({max_reliable_accuracy}m)",
        )

    if accuracy_meters is not None and dist_meters <= accuracy_meters:
        return (
            BoundaryStatusEnum.BOUNDARY_UNCERTAIN,
            round(dist_meters, 2),
            f"GPS accuracy circle (±{accuracy_meters:.1f}m) overlaps boundary "
            f"(distance: {dist_meters:.1f}m)",
        )

    if is_inside:
        return (
            BoundaryStatusEnum.INSIDE,
            round(dist_meters, 2),
            f"Location is inside the assigned HLB boundary ({dist_meters:.1f}m)",
        )
    else:
        return (
            BoundaryStatusEnum.OUTSIDE,
            round(dist_meters, 2),
            f"Location is outside the assigned HLB boundary ({dist_meters:.1f}m)",
        )
