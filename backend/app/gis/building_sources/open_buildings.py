import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shapely.geometry import Point, shape
from shapely.validation import make_valid

from app.gis.building_sources.base import (
    BuildingRecord,
    BuildingSourceBase,
    generate_deterministic_building_ref,
)
from app.gis.spatial import (
    COIMBATORE_PROJECTED_CRS,
    calculate_projected_area_sq_meters,
    calculate_projected_centroid,
)
from app.models.house import BuildingSourceType

logger = logging.getLogger(__name__)


class OpenBuildingsV3Source(BuildingSourceBase):
    """
    Google Open Buildings V3 Ingestion Source.
    Performs dynamic geographic querying, spatial containment filtering,
    EPSG:32643 projected CRS planar calculations, geometry repair,
    and footprint normalization with strict separation of authentic and synthetic data.
    """

    def __init__(self, data_directory: Path | None = None):
        env_dir = os.environ.get("OPEN_BUILDINGS_DATA_DIR")
        if data_directory is not None:
            self.data_directory = data_directory
        elif env_dir:
            self.data_directory = Path(env_dir)
        else:
            self.data_directory = (
                Path(__file__).resolve().parent.parent.parent
                / "data"
                / "open_buildings"
            )
        self._last_loaded_provenance: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "Google Open Buildings V3"

    @property
    def source_type(self) -> BuildingSourceType:
        return BuildingSourceType.SATELLITE_DETECTED

    @property
    def provenance(self) -> dict[str, Any]:
        return self._last_loaded_provenance

    def fetch_buildings(
        self,
        boundary_geojson: dict[str, Any],
        confidence_threshold: float | None = None,
        area_code: str | None = None,
    ) -> list[BuildingRecord]:
        """
        Dynamically query and ingest Google Open Buildings V3 records for the
        provided administrative boundary GeoJSON.
        Uses EPSG:32643 for planar metric area and centroid calculations.
        Prioritizes authentic real-world dataset files over synthetic test data.
        """
        _ = area_code
        boundary_poly = shape(boundary_geojson)
        if not boundary_poly.is_valid:
            boundary_poly = make_valid(boundary_poly)

        min_lng, min_lat, max_lng, max_lat = boundary_poly.bounds
        logger.info(
            f"Open Buildings query bounds: "
            f"[{min_lat:.4f}, {min_lng:.4f}] to [{max_lat:.4f}, {max_lng:.4f}]"
        )

        # 1. Discover files and prioritize genuine non-synthetic datasets
        candidate_files: list[tuple[Path, dict[str, Any]]] = []
        if self.data_directory.exists():
            for file_path in self.data_directory.glob("*.json"):
                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = json.load(f)
                        if isinstance(content, dict) and "buildings" in content:
                            candidate_files.append((file_path, content))
                        elif isinstance(content, list):
                            candidate_files.append((file_path, {"buildings": content}))
                except Exception as e:
                    logger.warning(
                        f"Failed reading Open Buildings candidate file {file_path}: {e}"
                    )

        # Prioritize real data files (is_synthetic is False) over synthetic files
        real_files = [
            (p, c) for p, c in candidate_files if c.get("is_synthetic") is False
        ]
        target_files = real_files if real_files else candidate_files

        raw_candidates: list[dict[str, Any]] = []
        acquisition_date = datetime(2023, 5, 15, tzinfo=UTC)
        is_synthetic = False
        licence = "Creative Commons Attribution (CC BY-4.0) and ODbL"

        for _, content in target_files:
            raw_candidates.extend(content.get("buildings", []))
            if content.get("is_synthetic"):
                is_synthetic = True
            if "acquisition_date" in content:
                try:
                    acquisition_date = datetime.fromisoformat(
                        content["acquisition_date"].replace("Z", "+00:00")
                    )
                except Exception:
                    pass
            if "licence" in content:
                licence = content["licence"]

        self._last_loaded_provenance = {
            "source": self.name,
            "dataset_version": "v3",
            "is_synthetic": is_synthetic,
            "acquisition_date": acquisition_date.isoformat(),
            "licence": licence,
            "projected_crs": COIMBATORE_PROJECTED_CRS,
            "total_candidates": len(raw_candidates),
        }

        # 2. Process, validate, and spatially filter candidates
        results: list[BuildingRecord] = []
        seen_keys: set[str] = set()

        for item in raw_candidates:
            # Extract confidence score
            conf = item.get("confidence")
            if conf is not None:
                conf = float(conf)
                if confidence_threshold is not None and conf < confidence_threshold:
                    continue

            # Geometry parsing & validation
            geom_data = item.get("geometry", {})
            valid_types = ("Polygon", "MultiPolygon")
            if not geom_data or geom_data.get("type") not in valid_types:
                continue

            try:
                geom_poly = shape(geom_data)
                if not geom_poly.is_valid:
                    geom_poly = make_valid(geom_poly)
                if geom_poly.is_empty:
                    continue
            except Exception as e:
                logger.debug(f"Invalid geometry skipped: {e}")
                continue

            # Determine centroid coordinates using projected CRS EPSG:32643 for accuracy
            try:
                lat, lng = calculate_projected_centroid(
                    geom_poly, crs=COIMBATORE_PROJECTED_CRS
                )
                centroid_pt = Point(lng, lat)
            except Exception:
                centroid_pt = geom_poly.centroid
                lat = centroid_pt.y
                lng = centroid_pt.x

            # Quick Bounding Box check
            if not (min_lng <= lng <= max_lng and min_lat <= lat <= max_lat):
                if not (
                    min_lng <= geom_poly.bounds[2]
                    and geom_poly.bounds[0] <= max_lng
                    and min_lat <= geom_poly.bounds[3]
                    and geom_poly.bounds[1] <= max_lat
                ):
                    continue

            # Exact Spatial boundary filtering (Centroid or Footprint intersection)
            is_inside = False
            if boundary_poly.contains(centroid_pt):
                is_inside = True
            elif boundary_poly.intersects(geom_poly):
                is_inside = True

            if not is_inside:
                continue

            # Normalized footprint GeoJSON
            footprint_geojson = geom_poly.__geo_interface__
            coords = footprint_geojson.get("coordinates", [])

            # Compute stable deterministic building identifier
            bld_ref = generate_deterministic_building_ref(lat, lng, coords)
            ext_id = (
                item.get("source_id")
                or item.get("id")
                or item.get("full_plus_code")
                or item.get("plus_code")
                or bld_ref
            )

            # Deduplication: Spatial reference and ID deduplication
            if bld_ref in seen_keys or ext_id in seen_keys:
                continue
            seen_keys.add(bld_ref)
            seen_keys.add(ext_id)

            # Exact Planar Area in square meters using EPSG:32643
            area_m2 = item.get("area_in_meters")
            if area_m2 is None:
                area_m2 = calculate_projected_area_sq_meters(
                    geom_poly, crs=COIMBATORE_PROJECTED_CRS
                )
            else:
                area_m2 = round(float(area_m2), 1)

            results.append(
                BuildingRecord(
                    external_id=str(ext_id),
                    latitude=round(lat, 6),
                    longitude=round(lng, 6),
                    footprint_geojson=footprint_geojson,
                    confidence=round(conf, 4) if conf is not None else None,
                    source_type=self.source_type,
                    imagery_source=self.name,
                    imagery_date=acquisition_date,
                    area_in_meters=area_m2,
                    building_reference=bld_ref,
                )
            )

        logger.info(
            f"Open Buildings V3: Ingested {len(results)} buildings for query area "
            f"(Synthetic: {is_synthetic}, CRS: {COIMBATORE_PROJECTED_CRS})"
        )
        return results
