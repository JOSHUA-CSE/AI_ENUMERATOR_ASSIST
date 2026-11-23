import json
import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon
from shapely.strtree import STRtree

from app.gis.spatial import (
    COIMBATORE_PROJECTED_CRS,
    DEFAULT_GEOGRAPHIC_CRS,
    calculate_projected_distance_meters,
    transform_geometry,
)

logger = logging.getLogger(__name__)

ROADS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "roads"
DEFAULT_ARASUR_ROADS_FILE = ROADS_DIR / "arasur_osm_roads.json"
DEFAULT_POLLACHI_ROADS_FILE = ROADS_DIR / "pollachi_osm_roads.json"

WALKABLE_HIGHWAY_TYPES = {
    "residential",
    "unclassified",
    "living_street",
    "pedestrian",
    "footway",
    "path",
    "service",
    "track",
    "steps",
    "tertiary",
    "secondary",
    "primary",
}

EXCLUDED_HIGHWAY_TYPES = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
}

# Highway classification walking speed multipliers (baseline 4.5 km/h = 1.0)
HIGHWAY_SPEED_FACTORS = {
    "pedestrian": 1.05,
    "footway": 1.05,
    "living_street": 1.0,
    "residential": 1.0,
    "service": 0.95,
    "unclassified": 0.95,
    "tertiary": 0.90,
    "secondary": 0.85,
    "primary": 0.80,
    "track": 0.85,
    "path": 0.90,
    "steps": 0.50,
}

# Surface walking speed factors
SURFACE_SPEED_FACTORS = {
    "asphalt": 1.0,
    "paved": 1.0,
    "concrete": 1.0,
    "cobblestone": 0.90,
    "unpaved": 0.85,
    "compacted": 0.85,
    "gravel": 0.80,
    "ground": 0.80,
    "dirt": 0.75,
    "earth": 0.75,
    "sand": 0.65,
    "steps": 0.50,
}

# Major roads requiring independent two-sided enumeration
TWO_SIDED_HIGHWAY_TYPES = {"primary", "secondary", "tertiary"}

AVERAGE_WALKING_SPEED_KMH = 4.5


def calculate_linestring_length_m(coords: list[tuple[float, float]]) -> float:
    """Calculate metric length of coordinate list [(lat, lon), ...] in meters using EPSG:32643."""
    if len(coords) < 2:
        return 0.0
    total = 0.0
    for i in range(len(coords) - 1):
        total += calculate_projected_distance_meters(coords[i], coords[i + 1])
    return total


@dataclass
class RoadSegment:
    segment_id: str
    osm_way_id: int | None
    osm_node_ids: list[int]
    coordinates: list[tuple[float, float]]  # [(lat, lon), ...]
    geometry: LineString
    length_m: float
    highway: str
    name: str | None = None
    foot: str | None = None
    access: str | None = None
    surface: str | None = None
    walking_speed_factor: float = 1.0
    walking_cost: float = 0.0  # Estimated walking time in minutes
    boundary_classification: str = "INTERNAL"  # INTERNAL or EXTERNAL_TRANSIT
    required_status: str = "REQUIRED"  # REQUIRED or TRANSIT
    coverage_status: str = "NOT_VISITED"  # NOT_VISITED, IN_PROGRESS, SURVEYED, NEEDS_REVISIT
    requires_two_sided: bool = False
    left_surveyed: bool = False
    right_surveyed: bool = False
    source: str = "OpenStreetMap"
    acquisition_date: str = "2026-11-11T09:42:04Z"
    network_version: str = "v1.0"

    def __post_init__(self):
        if self.walking_cost <= 0.0 and self.length_m > 0:
            effective_speed_kmh = AVERAGE_WALKING_SPEED_KMH * self.walking_speed_factor
            if effective_speed_kmh <= 0.1:
                effective_speed_kmh = 1.0
            self.walking_cost = round((self.length_m / 1000.0) / effective_speed_kmh * 60.0, 3)

        if self.highway in TWO_SIDED_HIGHWAY_TYPES:
            self.requires_two_sided = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "osm_way_id": self.osm_way_id,
            "osm_node_ids": self.osm_node_ids,
            "coordinates": [[c[0], c[1]] for c in self.coordinates],
            "length_m": round(self.length_m, 2),
            "walking_cost": round(self.walking_cost, 3),
            "highway": self.highway,
            "name": self.name,
            "foot": self.foot,
            "access": self.access,
            "surface": self.surface,
            "walking_speed_factor": self.walking_speed_factor,
            "boundary_classification": self.boundary_classification,
            "required_status": self.required_status,
            "coverage_status": self.coverage_status,
            "requires_two_sided": self.requires_two_sided,
            "left_surveyed": self.left_surveyed,
            "right_surveyed": self.right_surveyed,
            "source": self.source,
            "acquisition_date": self.acquisition_date,
            "network_version": self.network_version,
        }


class RoadNetwork:
    """
    Manages walkable pedestrian and road networks derived from OpenStreetMap.
    Enforces walkability constraints, metric projections (EPSG:32643),
    junction-level topological segmentation, spatial indexing (STRtree),
    and boundary-constrained segment extraction.
    """

    def __init__(
        self,
        segments: list[RoadSegment] | None = None,
        source_name: str = "OpenStreetMap",
        acquisition_date: str = "2026-11-11T09:42:04Z",
    ):
        self.segments: list[RoadSegment] = segments or []
        self.segment_map: dict[str, RoadSegment] = {s.segment_id: s for s in self.segments}
        self.source_name = source_name
        self.acquisition_date = acquisition_date
        self.network_version = "v1.0"

        # Build spatial index
        self._tree: STRtree | None = None
        self._geometries: list[LineString] = []
        if self.segments:
            self._build_spatial_index()

    def _build_spatial_index(self) -> None:
        self._geometries = [s.geometry for s in self.segments]
        self._tree = STRtree(self._geometries)

    @classmethod
    def from_osm_json_file(cls, file_path: Path | str) -> "RoadNetwork":
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"OSM roads file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        osm_meta = data.get("osm3s", {})
        acq_date = osm_meta.get("timestamp_osm_base", "2026-11-11T09:42:04Z")

        elements = data.get("elements", [])

        # 1. First pass: Filter eligible walkable ways
        walkable_ways = []
        for el in elements:
            if el.get("type") != "way":
                continue
            tags = el.get("tags", {})
            highway = tags.get("highway", "")
            foot = tags.get("foot", "")
            access = tags.get("access", "")

            # Exclude explicit non-walkable or private access
            if access in ("private", "no") or foot in ("no", "private"):
                continue

            # Exclude motorways, trunk roads unless foot is explicitly designated/yes
            if highway in EXCLUDED_HIGHWAY_TYPES and foot not in ("yes", "designated"):
                continue

            if highway not in WALKABLE_HIGHWAY_TYPES and foot not in ("yes", "designated", "permissive"):
                continue

            if len(el.get("geometry", [])) >= 2:
                walkable_ways.append(el)

        # 2. Count node occurrences across walkable ways to identify true junction nodes
        node_counts = Counter()
        for el in walkable_ways:
            for nid in el.get("nodes", []):
                node_counts[nid] += 1

        junction_nids = {nid for nid, count in node_counts.items() if count > 1}

        # 3. Second pass: Segment ways at junctions to preserve complete graph connectivity
        segments: list[RoadSegment] = []

        for el in walkable_ways:
            way_id = el.get("id")
            tags = el.get("tags", {})
            highway = tags.get("highway", "")
            name = tags.get("name")
            foot = tags.get("foot")
            access = tags.get("access")
            surface = tags.get("surface")
            raw_geom = el.get("geometry", [])
            node_ids = el.get("nodes", [])

            # Calculate composite speed factor: highway factor * surface factor
            hw_factor = HIGHWAY_SPEED_FACTORS.get(highway, 1.0)
            surf_factor = SURFACE_SPEED_FACTORS.get(surface, 1.0) if surface else 1.0
            speed_factor = round(hw_factor * surf_factor, 2)

            # Find junction split points along this way
            split_indices = [0]
            for i in range(1, len(node_ids) - 1):
                if node_ids[i] in junction_nids:
                    split_indices.append(i)
            split_indices.append(len(node_ids) - 1)
            split_indices = sorted(list(set(split_indices)))

            for s_idx in range(len(split_indices) - 1):
                start_i = split_indices[s_idx]
                end_i = split_indices[s_idx + 1]
                sub_pts = raw_geom[start_i : end_i + 1]
                sub_nodes = node_ids[start_i : end_i + 1]
                coords = [(round(pt["lat"], 6), round(pt["lon"], 6)) for pt in sub_pts]

                # Construct LineString in (lon, lat) for Shapely spatial operations
                shapely_coords = [(c[1], c[0]) for c in coords]
                line_geom = LineString(shapely_coords)
                length_m = calculate_linestring_length_m(coords)

                if length_m < 1.0:
                    continue

                segment_id = f"way_{way_id}_s{s_idx}"
                segments.append(
                    RoadSegment(
                        segment_id=segment_id,
                        osm_way_id=way_id,
                        osm_node_ids=sub_nodes,
                        coordinates=coords,
                        geometry=line_geom,
                        length_m=length_m,
                        highway=highway,
                        name=name,
                        foot=foot,
                        access=access,
                        surface=surface,
                        walking_speed_factor=speed_factor,
                        source="OpenStreetMap",
                        acquisition_date=acq_date,
                        network_version="v1.0",
                    )
                )

        logger.info(
            "Loaded RoadNetwork from %s: %d topological segments from %d ways (Acquisition: %s)",
            path.name,
            len(segments),
            len(walkable_ways),
            acq_date,
        )
        return cls(segments, source_name="OpenStreetMap", acquisition_date=acq_date)

    def query_segments_in_polygon(
        self,
        polygon: Polygon | MultiPolygon,
        buffer_meters: float = 20.0,
    ) -> list[RoadSegment]:
        """
        Find and clip walkable road segments that intersect the given HLB polygon,
        including a buffer to capture boundary access connections.
        """
        if not self._tree or not self.segments:
            return []

        # Buffer in projected metric space (EPSG:32643) then transform back to EPSG:4326
        poly_proj = transform_geometry(polygon, DEFAULT_GEOGRAPHIC_CRS, COIMBATORE_PROJECTED_CRS)
        buffered_proj = poly_proj.buffer(buffer_meters)
        buffered_poly = transform_geometry(buffered_proj, COIMBATORE_PROJECTED_CRS, DEFAULT_GEOGRAPHIC_CRS)

        candidate_indices = self._tree.query(buffered_poly)
        result: list[RoadSegment] = []

        for idx in candidate_indices:
            seg = self.segments[idx]
            if seg.geometry.intersects(buffered_poly):
                intersection = seg.geometry.intersection(buffered_poly)
                if intersection.is_empty:
                    continue

                # Process intersection geometry (LineString or MultiLineString)
                if isinstance(intersection, LineString):
                    lines = [intersection]
                elif hasattr(intersection, "geoms"):
                    lines = [geom for geom in intersection.geoms if isinstance(geom, LineString)]
                else:
                    lines = []

                for sub_idx, line in enumerate(lines):
                    sub_coords = [(round(pt[1], 6), round(pt[0], 6)) for pt in line.coords]
                    if len(sub_coords) < 2:
                        continue
                    clipped_length_m = calculate_linestring_length_m(sub_coords)
                    if clipped_length_m < 1.0:
                        continue

                    # Check if centroid of this sub-line is strictly inside polygon
                    line_centroid = Point(line.centroid.x, line.centroid.y)
                    is_internal = polygon.contains(line_centroid) or polygon.intersects(line)

                    sub_id = f"{seg.segment_id}_c{sub_idx}" if len(lines) > 1 else seg.segment_id
                    result.append(
                        RoadSegment(
                            segment_id=sub_id,
                            osm_way_id=seg.osm_way_id,
                            osm_node_ids=seg.osm_node_ids,
                            coordinates=sub_coords,
                            geometry=line,
                            length_m=clipped_length_m,
                            highway=seg.highway,
                            name=seg.name,
                            foot=seg.foot,
                            access=seg.access,
                            surface=seg.surface,
                            walking_speed_factor=seg.walking_speed_factor,
                            boundary_classification="INTERNAL" if is_internal else "EXTERNAL_TRANSIT",
                            required_status="REQUIRED" if is_internal else "TRANSIT",
                            source=seg.source,
                            acquisition_date=seg.acquisition_date,
                            network_version=seg.network_version,
                        )
                    )

        # Deduplicate by segment_id
        seen = set()
        deduped = []
        for s in result:
            if s.segment_id not in seen:
                seen.add(s.segment_id)
                deduped.append(s)

        return deduped

    def extract_required_and_transit_edges(
        self,
        polygon: Polygon | MultiPolygon,
        buffer_meters: float = 30.0,
    ) -> tuple[list[RoadSegment], list[RoadSegment]]:
        """
        Extract required road edges (internal to HLB) and transit candidate edges (external buffer).
        Every eligible road edge inside the HLB is REQUIRED.
        """
        all_nearby = self.query_segments_in_polygon(polygon, buffer_meters=buffer_meters)
        required_edges = []
        transit_edges = []

        for seg in all_nearby:
            # Check overlap with polygon
            line_geom = seg.geometry
            if polygon.intersects(line_geom):
                # Cut edge at boundary
                internal_geom = line_geom.intersection(polygon)
                external_geom = line_geom.difference(polygon)

                if not internal_geom.is_empty:
                    if isinstance(internal_geom, LineString):
                        int_lines = [internal_geom]
                    elif hasattr(internal_geom, "geoms"):
                        int_lines = [g for g in internal_geom.geoms if isinstance(g, LineString)]
                    else:
                        int_lines = []

                    for idx, line in enumerate(int_lines):
                        coords = [(round(pt[1], 6), round(pt[0], 6)) for pt in line.coords]
                        if len(coords) >= 2:
                            seg_len = calculate_linestring_length_m(coords)
                            if seg_len >= 1.0:
                                required_edges.append(
                                    RoadSegment(
                                        segment_id=f"{seg.segment_id}_req{idx}" if len(int_lines) > 1 else seg.segment_id,
                                        osm_way_id=seg.osm_way_id,
                                        osm_node_ids=seg.osm_node_ids,
                                        coordinates=coords,
                                        geometry=line,
                                        length_m=seg_len,
                                        highway=seg.highway,
                                        name=seg.name,
                                        foot=seg.foot,
                                        access=seg.access,
                                        surface=seg.surface,
                                        walking_speed_factor=seg.walking_speed_factor,
                                        boundary_classification="INTERNAL",
                                        required_status="REQUIRED",
                                        source=seg.source,
                                        acquisition_date=seg.acquisition_date,
                                        network_version=seg.network_version,
                                    )
                                )

                if not external_geom.is_empty:
                    if isinstance(external_geom, LineString):
                        ext_lines = [external_geom]
                    elif hasattr(external_geom, "geoms"):
                        ext_lines = [g for g in external_geom.geoms if isinstance(g, LineString)]
                    else:
                        ext_lines = []

                    for idx, line in enumerate(ext_lines):
                        coords = [(round(pt[1], 6), round(pt[0], 6)) for pt in line.coords]
                        if len(coords) >= 2:
                            seg_len = calculate_linestring_length_m(coords)
                            if seg_len >= 1.0:
                                transit_edges.append(
                                    RoadSegment(
                                        segment_id=f"{seg.segment_id}_ext{idx}",
                                        osm_way_id=seg.osm_way_id,
                                        osm_node_ids=seg.osm_node_ids,
                                        coordinates=coords,
                                        geometry=line,
                                        length_m=seg_len,
                                        highway=seg.highway,
                                        name=seg.name,
                                        foot=seg.foot,
                                        access=seg.access,
                                        surface=seg.surface,
                                        walking_speed_factor=seg.walking_speed_factor,
                                        boundary_classification="EXTERNAL_TRANSIT",
                                        required_status="TRANSIT",
                                        source=seg.source,
                                        acquisition_date=seg.acquisition_date,
                                        network_version=seg.network_version,
                                    )
                                )
            else:
                # Fully outside HLB polygon, in buffer -> candidate transit edge
                transit_edges.append(seg)

        return required_edges, transit_edges


_CACHED_ROAD_NETWORKS: dict[str, RoadNetwork] = {}


def get_road_network(roads_file: Path | str | None = None) -> RoadNetwork | None:
    """
    Get or load a cached RoadNetwork from the specified OSM roads JSON file,
    falling back to DEFAULT_ARASUR_ROADS_FILE if none specified.
    """
    global _CACHED_ROAD_NETWORKS
    target = Path(roads_file) if roads_file else DEFAULT_ARASUR_ROADS_FILE
    target_str = str(target.resolve()) if target.exists() else None

    if target_str and target_str in _CACHED_ROAD_NETWORKS:
        return _CACHED_ROAD_NETWORKS[target_str]

    if not target.exists():
        if DEFAULT_ARASUR_ROADS_FILE.exists():
            target = DEFAULT_ARASUR_ROADS_FILE
            target_str = str(target.resolve())
            if target_str in _CACHED_ROAD_NETWORKS:
                return _CACHED_ROAD_NETWORKS[target_str]
        else:
            logger.warning("No OSM road network file found at %s", target)
            return None

    try:
        rn = RoadNetwork.from_osm_json_file(target)
        if target_str:
            _CACHED_ROAD_NETWORKS[target_str] = rn
        return rn
    except Exception as exc:
        logger.error("Failed to load RoadNetwork from %s: %s", target, exc)
        return None

