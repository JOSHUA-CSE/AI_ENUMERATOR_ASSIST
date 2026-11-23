from app.gis.building_sources.base import BuildingRecord, BuildingSourceBase
from app.gis.building_sources.development import DevelopmentSource
from app.gis.building_sources.open_buildings import OpenBuildingsV3Source


def get_building_source(source_name: str | None = None) -> BuildingSourceBase:
    """
    Factory to retrieve configured building source provider.
    Defaults to Google Open Buildings V3.
    """
    if source_name and source_name.lower() in ("development", "dev", "mock"):
        return DevelopmentSource()
    return OpenBuildingsV3Source()


__all__ = [
    "BuildingRecord",
    "BuildingSourceBase",
    "DevelopmentSource",
    "OpenBuildingsV3Source",
    "get_building_source",
]
