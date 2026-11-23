import json
from typing import Any

import shapely.wkb
import shapely.wkt
from geoalchemy2 import WKBElement
from geoalchemy2.shape import from_shape, to_shape
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Point, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from shapely.validation import explain_validity, make_valid

COIMBATORE_PROJECTED_CRS = "EPSG:32643"  # WGS 84 / UTM zone 43N (Coimbatore & Western Tamil Nadu)
DEFAULT_GEOGRAPHIC_CRS = "EPSG:4326"

_transformer_cache: dict[tuple[str, str], Transformer] = {}


def get_transformer(src_crs: str, dst_crs: str) -> Transformer:
    """Retrieve or instantiate a cached pyproj Coordinate Transformer."""
    key = (src_crs.upper(), dst_crs.upper())
    if key not in _transformer_cache:
        _transformer_cache[key] = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    return _transformer_cache[key]


def transform_geometry(
    geom: BaseGeometry,
    src_crs: str = DEFAULT_GEOGRAPHIC_CRS,
    dst_crs: str = COIMBATORE_PROJECTED_CRS,
) -> BaseGeometry:
    """Transform Shapely geometry between coordinate reference systems."""
    src_str = f"EPSG:{src_crs}" if isinstance(src_crs, int) else str(src_crs)
    dst_str = f"EPSG:{dst_crs}" if isinstance(dst_crs, int) else str(dst_crs)
    if src_str.upper() == dst_str.upper():
        return geom
    transformer = get_transformer(src_str, dst_str)
    return transform(transformer.transform, geom)


def calculate_projected_area_sq_meters(
    geom: BaseGeometry,
    crs: str = COIMBATORE_PROJECTED_CRS,
) -> float:
    """Calculate exact planar area in square meters using projected metric coordinates."""
    geom_proj = transform_geometry(geom, src_crs=DEFAULT_GEOGRAPHIC_CRS, dst_crs=crs)
    return round(max(0.0, float(geom_proj.area)), 2)


def calculate_projected_distance_meters(
    pt1: tuple[float, float],
    pt2: tuple[float, float],
    crs: str = COIMBATORE_PROJECTED_CRS,
) -> float:
    """Calculate Euclidean distance in meters between two (lat, lon) coordinates in projected CRS."""
    p1 = Point(pt1[1], pt1[0])  # (lng, lat)
    p2 = Point(pt2[1], pt2[0])
    p1_proj = transform_geometry(p1, src_crs=DEFAULT_GEOGRAPHIC_CRS, dst_crs=crs)
    p2_proj = transform_geometry(p2, src_crs=DEFAULT_GEOGRAPHIC_CRS, dst_crs=crs)
    return round(float(p1_proj.distance(p2_proj)), 2)


def buffer_geometry_projected(
    geom: BaseGeometry,
    distance_meters: float,
    crs: str = COIMBATORE_PROJECTED_CRS,
) -> BaseGeometry:
    """
    Apply a metric buffer in projected coordinates and transform back to EPSG:4326.
    """
    geom_proj = transform_geometry(geom, src_crs=DEFAULT_GEOGRAPHIC_CRS, dst_crs=crs)
    buffered_proj = geom_proj.buffer(distance_meters)
    if not buffered_proj.is_valid:
        buffered_proj = make_valid(buffered_proj)
    return transform_geometry(buffered_proj, src_crs=crs, dst_crs=DEFAULT_GEOGRAPHIC_CRS)


def calculate_projected_centroid(
    geom: BaseGeometry,
    crs: str = COIMBATORE_PROJECTED_CRS,
) -> tuple[float, float]:
    """
    Calculate planar centroid in projected CRS and return as (latitude, longitude) in EPSG:4326.
    """
    geom_proj = transform_geometry(geom, src_crs=DEFAULT_GEOGRAPHIC_CRS, dst_crs=crs)
    centroid_proj = geom_proj.centroid
    centroid_wgs84 = transform_geometry(centroid_proj, src_crs=crs, dst_crs=DEFAULT_GEOGRAPHIC_CRS)
    return round(float(centroid_wgs84.y), 6), round(float(centroid_wgs84.x), 6)


class InvalidGeometryError(ValueError):
    """Raised when provided geometry is malformed, unclosed, or invalid."""


def validate_coordinates_range(coords: list | tuple) -> None:
    """
    Recursively validate that all coordinates are within valid geographic bounds:
    Longitude in [-180, 180], Latitude in [-90, 90].
    """
    if not coords:
        raise InvalidGeometryError("Coordinates array cannot be empty")

    if isinstance(coords[0], (int, float)):
        # It's a [lon, lat] coordinate pair
        if len(coords) < 2:
            raise InvalidGeometryError(
                f"Coordinate pair must have at least 2 numbers [lon, lat], got {coords}"
            )
        lon, lat = coords[0], coords[1]
        if not (-180.0 <= lon <= 180.0):
            raise InvalidGeometryError(
                f"Longitude {lon} is out of valid range [-180.0, 180.0]"
            )
        if not (-90.0 <= lat <= 90.0):
            raise InvalidGeometryError(
                f"Latitude {lat} is out of valid range [-90.0, 90.0]"
            )
    else:
        for sub_coords in coords:
            validate_coordinates_range(sub_coords)


def validate_and_convert_geojson_polygon(geojson_data: dict[str, Any]) -> WKBElement:
    """
    Validate GeoJSON Polygon/MultiPolygon and convert to GeoAlchemy2 WKBElement.
    """
    if not isinstance(geojson_data, dict):
        raise InvalidGeometryError("GeoJSON geometry must be a dictionary")

    geom_type = geojson_data.get("type")
    if geom_type not in ("Polygon", "MultiPolygon"):
        raise InvalidGeometryError(
            f"Expected geometry type 'Polygon' or 'MultiPolygon', got '{geom_type}'"
        )

    coords = geojson_data.get("coordinates")
    if not coords:
        raise InvalidGeometryError("Geometry must contain 'coordinates' array")

    # Validate coordinate ranges
    validate_coordinates_range(coords)

    try:
        geom = shape(geojson_data)
    except Exception as e:
        raise InvalidGeometryError(f"Failed to parse GeoJSON geometry: {e}") from e

    if geom.is_empty:
        raise InvalidGeometryError("Geometry cannot be empty")

    if not geom.is_valid:
        # Try to repair geometry or raise error
        geom = make_valid(geom)
        if not geom.is_valid:
            reason = explain_validity(geom)
            raise InvalidGeometryError(f"Invalid polygon geometry: {reason}")

    # Normalize to MultiPolygon for consistent database storage
    if isinstance(geom, Polygon):
        geom = MultiPolygon([geom])
    elif not isinstance(geom, MultiPolygon):
        raise InvalidGeometryError(
            f"Expected Polygon/MultiPolygon resolution, got {geom.geom_type}"
        )

    return from_shape(geom, srid=4326)


def validate_and_convert_point(latitude: float, longitude: float) -> WKBElement:
    """
    Validate lat/lon and convert to GeoAlchemy2 Point WKBElement (SRID 4326).
    """

    if not (-90.0 <= latitude <= 90.0):
        raise InvalidGeometryError(
            f"Latitude {latitude} is out of valid range [-90.0, 90.0]"
        )
    if not (-180.0 <= longitude <= 180.0):
        raise InvalidGeometryError(
            f"Longitude {longitude} is out of valid range [-180.0, 180.0]"
        )

    point = Point(longitude, latitude)
    return from_shape(point, srid=4326)


def geometry_to_geojson_dict(geom_element: Any) -> dict[str, Any] | None:
    """
    Convert GeoAlchemy2 WKBElement, Shapely geometry, bytes, or string
    to standard GeoJSON dictionary.
    """

    if geom_element is None:
        return None

    if isinstance(geom_element, dict):
        return geom_element

    if isinstance(geom_element, BaseGeometry):
        return mapping(geom_element)

    if isinstance(geom_element, bytes):
        try:
            return mapping(shapely.wkb.loads(geom_element))
        except Exception:
            pass

    if isinstance(geom_element, str):
        try:
            return json.loads(geom_element)
        except json.JSONDecodeError:
            pass

        try:
            # Try hex WKB
            return mapping(shapely.wkb.loads(bytes.fromhex(geom_element)))
        except Exception:
            pass

        try:
            # Try EWKT / WKT
            wkt_str = (
                geom_element.split(";")[-1] if ";" in geom_element else geom_element
            )
            return mapping(shapely.wkt.loads(wkt_str))
        except Exception:
            pass

    try:
        shapely_geom = to_shape(geom_element)
        return mapping(shapely_geom)
    except Exception:
        pass

    return None
