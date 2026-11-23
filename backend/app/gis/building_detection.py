import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.gis.building_sources import get_building_source
from app.gis.building_sources.development import DevelopmentSource
from app.gis.spatial import (
    geometry_to_geojson_dict,
    validate_and_convert_geojson_polygon,
    validate_and_convert_point,
)
from app.models.administrative_area import AdministrativeArea
from app.models.house import BuildingSourceType, House

logger = logging.getLogger(__name__)


class BuildingDetectionService:
    """
    Server-side GIS & Satellite Building Estimation Service.
    Handles building footprint/centroid estimation, spatial filtering against
    administrative boundaries, density cluster calculation, and source labeling.
    """

    def get_building_estimation_summary(
        self, db: Session, area: AdministrativeArea
    ) -> dict[str, Any]:
        """
        Calculate building estimation metrics, density heatmap clusters,
        and honest data source labeling for a given administrative area.
        """
        houses = db.query(House).filter(House.area_id == area.id).all()
        total_count = len(houses)

        if total_count == 0:
            return {
                "area_id": area.id,
                "area_name": area.name,
                "area_code": area.code,
                "total_buildings": 0,
                "source_type": BuildingSourceType.SATELLITE_DETECTED.value,
                "quality_label": "No buildings detected",
                "imagery_source": "Google Open Buildings V3",
                "imagery_date": None,
                "average_confidence": None,
                "density_clusters": [],
                "is_synthetic": False,
                "provenance": None,
                "licence": None,
                "projected_crs": "EPSG:32643",
            }

        # Check source types to determine primary data origin
        has_satellite = any(
            h.source_type == BuildingSourceType.SATELLITE_DETECTED for h in houses
        )
        has_development = any(
            h.source_type == BuildingSourceType.DEVELOPMENT_DATA for h in houses
        )

        if has_satellite and not has_development:
            source_type = BuildingSourceType.SATELLITE_DETECTED.value
            quality_label = "Satellite-derived estimate"
        elif has_development and not has_satellite:
            source_type = BuildingSourceType.DEVELOPMENT_DATA.value
            quality_label = "Development data"
        else:
            source_type = (
                BuildingSourceType.SATELLITE_DETECTED.value
                if has_satellite
                else BuildingSourceType.DEVELOPMENT_DATA.value
            )
            quality_label = (
                "Satellite-derived estimate" if has_satellite else "Development data"
            )

        # Average confidence from source (never invent accuracy percentage)
        confidences = [
            h.detection_confidence for h in houses if h.detection_confidence is not None
        ]
        avg_confidence = (
            round(sum(confidences) / len(confidences), 3) if confidences else None
        )

        imagery_sources = [h.imagery_source for h in houses if h.imagery_source]
        primary_imagery = (
            imagery_sources[0] if imagery_sources else "Google Open Buildings V3"
        )

        imagery_dates = [h.imagery_date for h in houses if h.imagery_date]
        primary_date = imagery_dates[0].strftime("%Y-%m-%d") if imagery_dates else None

        # Generate spatial density grid clusters for medium-zoom visualization
        density_clusters = self._compute_density_clusters(houses)

        return {
            "area_id": area.id,
            "area_name": area.name,
            "area_code": area.code,
            "total_buildings": total_count,
            "source_type": source_type,
            "quality_label": quality_label,
            "imagery_source": primary_imagery,
            "imagery_date": primary_date,
            "average_confidence": avg_confidence,
            "density_clusters": density_clusters,
            "is_synthetic": has_development and not has_satellite,
            "provenance": (
                "Synthetic development dataset"
                if has_development and not has_satellite
                else "Google Open Buildings V3 (S2 level 6 tile 3ba9, May 2023)"
            ),
            "licence": (
                "Internal development use only"
                if has_development and not has_satellite
                else "Creative Commons Attribution (CC BY-4.0) and ODbL"
            ),
            "projected_crs": "EPSG:32643",
        }

    def _compute_density_clusters(
        self, houses: list[House], grid_size: float = 0.003
    ) -> list[dict[str, Any]]:
        """
        Aggregate buildings into spatial grid clusters for lightweight
        density heatmap and cluster visualization at medium zoom levels.
        """
        grid: dict[str, dict[str, Any]] = {}

        for h in houses:
            grid_x = int(h.longitude / grid_size)
            grid_y = int(h.latitude / grid_size)
            key = f"{grid_x}_{grid_y}"

            if key not in grid:
                grid[key] = {
                    "lat_sum": 0.0,
                    "lng_sum": 0.0,
                    "count": 0,
                    "min_lat": h.latitude,
                    "max_lat": h.latitude,
                    "min_lng": h.longitude,
                    "max_lng": h.longitude,
                }

            grid[key]["lat_sum"] += h.latitude
            grid[key]["lng_sum"] += h.longitude
            grid[key]["count"] += 1
            grid[key]["min_lat"] = min(grid[key]["min_lat"], h.latitude)
            grid[key]["max_lat"] = max(grid[key]["max_lat"], h.latitude)
            grid[key]["min_lng"] = min(grid[key]["min_lng"], h.longitude)
            grid[key]["max_lng"] = max(grid[key]["max_lng"], h.longitude)

        clusters = []
        for cell in grid.values():
            count = cell["count"]
            centroid_lat = cell["lat_sum"] / count
            centroid_lng = cell["lng_sum"] / count

            clusters.append(
                {
                    "latitude": round(centroid_lat, 6),
                    "longitude": round(centroid_lng, 6),
                    "count": count,
                    "bounds": [
                        [cell["min_lat"], cell["min_lng"]],
                        [cell["max_lat"], cell["max_lng"]],
                    ],
                }
            )

        return clusters

    def run_building_detection(
        self,
        db: Session,
        area: AdministrativeArea,
        imagery_source: str = "Google Open Buildings V3",
        confidence_threshold: float | None = None,
        allow_development_fallback: bool = False,
    ) -> list[House]:
        """
        Execute building estimation pipeline for administrative area using
        modular building sources with genuine satellite-derived footprint ingestion.
        Safely replaces stale records from the same source within a transaction.
        """
        boundary_geojson = geometry_to_geojson_dict(area.boundary)
        if not boundary_geojson:
            raise ValueError("Administrative area does not have a valid boundary")

        # Select building source provider
        source_provider = get_building_source(imagery_source)
        try:
            records = source_provider.fetch_buildings(
                boundary_geojson=boundary_geojson,
                confidence_threshold=confidence_threshold,
                area_code=area.code,
            )
        except Exception as e:
            if allow_development_fallback:
                logger.warning(
                    f"Satellite source failed ({e}), falling back to DevelopmentSource"
                )
                source_provider = DevelopmentSource()
                records = source_provider.fetch_buildings(
                    boundary_geojson=boundary_geojson,
                    confidence_threshold=confidence_threshold,
                    area_code=area.code,
                )
            else:
                raise

        if not records and allow_development_fallback:
            logger.info(
                "No satellite records found; using explicit development fallback"
            )
            source_provider = DevelopmentSource()
            records = source_provider.fetch_buildings(
                boundary_geojson=boundary_geojson,
                confidence_threshold=confidence_threshold,
                area_code=area.code,
            )

        detected_houses = []
        now_utc = datetime.now(UTC)

        for idx, rec in enumerate(records, start=1):
            wkb_point = validate_and_convert_point(rec.latitude, rec.longitude)
            wkb_footprint = validate_and_convert_geojson_polygon(rec.footprint_geojson)

            bld_ref = rec.building_reference or f"BLD-{idx:03d}"
            house_num = f"1/{idx}"

            house_obj = House(
                area_id=area.id,
                building_reference=bld_ref,
                house_number=house_num,
                latitude=rec.latitude,
                longitude=rec.longitude,
                location=wkb_point,
                footprint=wkb_footprint,
                source_type=rec.source_type,
                detection_confidence=rec.confidence,
                detected_at=now_utc,
                imagery_source=rec.imagery_source,
                imagery_date=rec.imagery_date or now_utc,
            )
            detected_houses.append(house_obj)

        # Safe transactional replacement: only delete prior records from THIS source
        # Never delete field-verified, government-imported, or manual records
        db.query(House).filter(
            House.area_id == area.id,
            House.source_type == source_provider.source_type,
            House.imagery_source == source_provider.name,
        ).delete()

        db.add_all(detected_houses)
        db.commit()

        logger.info(
            f"Building detection: {len(detected_houses)} structures in "
            f"{area.name} via {source_provider.name}"
        )
        return detected_houses


building_detection_service = BuildingDetectionService()
