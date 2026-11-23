import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.house import BuildingSourceType


@dataclass
class BuildingRecord:
    """
    Standardized internal representation of a detected building or footprint.
    """

    external_id: str
    latitude: float
    longitude: float
    footprint_geojson: dict[str, Any]
    confidence: float | None
    source_type: BuildingSourceType
    imagery_source: str
    imagery_date: datetime | None
    area_in_meters: float | None = None
    building_reference: str | None = None


def generate_deterministic_building_ref(
    lat: float, lng: float, polygon_coords: list[Any] | None = None
) -> str:
    """
    Generate a deterministic building reference derived from spatial geometry.
    Ensures stable building identifiers across repeated imports and execution runs.
    Format: BLD-<6-character-hex-hash>
    """
    if polygon_coords:
        serialized = json.dumps(polygon_coords, sort_keys=True)
        raw_key = f"{round(lat, 6)}_{round(lng, 6)}_{serialized}"
    else:
        raw_key = f"{round(lat, 6)}_{round(lng, 6)}"

    hash_hex = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:6].upper()
    return f"BLD-{hash_hex}"


class BuildingSourceBase(ABC):
    """
    Abstract interface for building data acquisition sources.
    Decouples GIS ingestion from specific download/detection mechanisms.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the source provider."""
        ...

    @property
    @abstractmethod
    def source_type(self) -> BuildingSourceType:
        """Classification type of the source data."""
        ...

    @abstractmethod
    def fetch_buildings(
        self,
        boundary_geojson: dict[str, Any],
        confidence_threshold: float | None = None,
        area_code: str | None = None,
    ) -> list[BuildingRecord]:
        """
        Fetch, clip, validate, and normalize building footprints for the given boundary.
        """
        ...
