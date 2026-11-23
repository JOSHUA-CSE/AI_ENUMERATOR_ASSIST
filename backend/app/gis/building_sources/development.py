from datetime import UTC, datetime
from typing import Any

from shapely.geometry import Point, shape
from shapely.validation import make_valid

from app.gis.building_sources.base import BuildingRecord, BuildingSourceBase
from app.models.house import BuildingSourceType


class DevelopmentSource(BuildingSourceBase):
    """
    Explicit Development Data Fallback Source.
    Used for local testing or when external satellite datasets are unavailable.
    Outputs are ALWAYS marked with source_type = DEVELOPMENT_DATA.
    """

    @property
    def name(self) -> str:
        return "Development Dataset"

    @property
    def source_type(self) -> BuildingSourceType:
        return BuildingSourceType.DEVELOPMENT_DATA

    def fetch_buildings(
        self,
        boundary_geojson: dict[str, Any],
        confidence_threshold: float = 0.50,
        area_code: str | None = None,
    ) -> list[BuildingRecord]:
        _ = (confidence_threshold, area_code)
        boundary_poly = shape(boundary_geojson)
        if not boundary_poly.is_valid:
            boundary_poly = make_valid(boundary_poly)

        min_lng, min_lat, max_lng, max_lat = boundary_poly.bounds
        results: list[BuildingRecord] = []

        steps_lat = 16
        steps_lng = 18
        lat_step = (max_lat - min_lat) / steps_lat
        lng_step = (max_lng - min_lng) / steps_lng
        idx = 1
        now_utc = datetime.now(UTC)

        for r in range(steps_lat):
            for c in range(steps_lng):
                pt_lat = round(min_lat + (r + 0.5) * lat_step, 6)
                pt_lng = round(min_lng + (c + 0.5) * lng_step, 6)
                pt = Point(pt_lng, pt_lat)

                if boundary_poly.contains(pt):
                    half_side = 0.00010
                    footprint_geojson = {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [
                                    round(pt_lng - half_side, 6),
                                    round(pt_lat - half_side, 6),
                                ],
                                [
                                    round(pt_lng + half_side, 6),
                                    round(pt_lat - half_side, 6),
                                ],
                                [
                                    round(pt_lng + half_side, 6),
                                    round(pt_lat + half_side, 6),
                                ],
                                [
                                    round(pt_lng - half_side, 6),
                                    round(pt_lat + half_side, 6),
                                ],
                                [
                                    round(pt_lng - half_side, 6),
                                    round(pt_lat - half_side, 6),
                                ],
                            ]
                        ],
                    }
                    results.append(
                        BuildingRecord(
                            external_id=f"DEV-BLD-{idx:03d}",
                            latitude=pt_lat,
                            longitude=pt_lng,
                            footprint_geojson=footprint_geojson,
                            confidence=None,
                            source_type=self.source_type,
                            imagery_source=self.name,
                            imagery_date=now_utc,
                            area_in_meters=100.0,
                            building_reference=f"BLD-{idx:03d}",
                        )
                    )
                    idx += 1

        return results
