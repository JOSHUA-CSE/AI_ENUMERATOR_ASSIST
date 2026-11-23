"""
Provisional Boundary Loader for Administrative Areas.
Loads validated provisional settlement and village boundaries from GeoJSON data.
Marks all outputs PROVISIONAL until authoritative/official Survey of India boundaries are loaded.
"""

import json
import logging
from pathlib import Path
from typing import Any

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.validation import make_valid
from sqlalchemy.orm import Session

from app.gis.spatial import (
    COIMBATORE_PROJECTED_CRS,
    DEFAULT_GEOGRAPHIC_CRS,
    transform_geometry,
)
from app.models.administrative_area import AdministrativeArea, BoundaryStatus

logger = logging.getLogger(__name__)

BOUNDARIES_DIR = Path(__file__).resolve().parent.parent / "data" / "boundaries"


def load_provisional_boundary(
    area_code: str = "arasur",
) -> tuple[Polygon | MultiPolygon, dict[str, Any]]:
    """
    Load provisional boundary GeoJSON for a given administrative area.
    Returns (shapely_geometry, metadata_dict).
    """
    normalized_code = area_code.lower().strip()
    boundary_file = BOUNDARIES_DIR / f"{normalized_code}_provisional_boundary.geojson"

    if not boundary_file.exists():
        # Fallback to arasur default if exists
        boundary_file = BOUNDARIES_DIR / "arasur_provisional_boundary.geojson"

    if not boundary_file.exists():
        raise FileNotFoundError(
            f"Provisional boundary file not found for area '{area_code}' in {BOUNDARIES_DIR}"
        )

    with open(boundary_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract geometry and properties
    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])
        if not features:
            raise ValueError(f"FeatureCollection in {boundary_file} is empty")
        feature = features[0]
        raw_geom = feature.get("geometry")
        properties = feature.get("properties", {})
    elif data.get("type") == "Feature":
        raw_geom = data.get("geometry")
        properties = data.get("properties", {})
    else:
        raw_geom = data
        properties = {}

    if not raw_geom:
        raise ValueError(f"No geometry found in {boundary_file}")

    parsed_geom = shape(raw_geom)
    if not parsed_geom.is_valid:
        parsed_geom = make_valid(parsed_geom)

    # Calculate metric area in EPSG:32643
    proj_geom = transform_geometry(parsed_geom, DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS)
    area_sq_m = proj_geom.area
    area_sq_km = round(area_sq_m / 1_000_000.0, 3)

    metadata: dict[str, Any] = {
        "name": properties.get("name", "Arasur Provisional Boundary"),
        "code": properties.get("code", area_code),
        "boundary_status": BoundaryStatus.PROVISIONAL.value,
        "source": properties.get("source", "OpenStreetMap & Survey of India Provisional"),
        "license": properties.get("license", "ODbL 1.0"),
        "area_sq_km": area_sq_km,
        "centroid": [parsed_geom.centroid.y, parsed_geom.centroid.x],
    }

    return parsed_geom, metadata


def ensure_provisional_boundary_for_area(
    db: Session,
    area: AdministrativeArea,
    area_code: str = "arasur",
) -> AdministrativeArea:
    """
    Ensure an administrative area has a verified boundary and boundary_status.
    If boundary is missing or status is UNVERIFIED/ESTIMATED, loads provisional boundary.
    """
    current_status = getattr(area, "boundary_status", None)
    if not area.boundary or current_status not in (BoundaryStatus.OFFICIAL.value, BoundaryStatus.PROVISIONAL.value):
        geom, meta = load_provisional_boundary(area_code)
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        area.boundary = from_shape(geom, srid=4326)
        area.boundary_status = BoundaryStatus.PROVISIONAL.value
        db.flush()
        logger.info(
            "Loaded provisional boundary for area '%s' (area_sq_km=%s, status=%s)",
            area.name,
            meta["area_sq_km"],
            area.boundary_status,
        )
    return area
