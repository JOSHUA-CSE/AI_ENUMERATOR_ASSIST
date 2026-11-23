import json
import logging
import os
import time
import urllib.request
import zlib
from datetime import UTC, datetime

import numpy as np
from pyproj import Transformer
from scipy.spatial import Voronoi
from shapely import wkt
from shapely.geometry import MultiPolygon, Point, Polygon, box, mapping
from shapely.ops import clip_by_rect, transform, unary_union
from shapely.validation import make_valid

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

transformer_to_32643 = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
transformer_to_4326 = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)


def project_to_utm(geom):
    return transform(transformer_to_32643.transform, geom)


def project_to_wgs84(geom):
    return transform(transformer_to_4326.transform, geom)


# 10 Verified Pollachi Revenue Villages
POLLACHI_VILLAGES = [
    # Layout A (Pollachi North Corridor)
    {
        "name": "Achipatti",
        "tamil_name": "ஆச்சிபட்டி",
        "census_code": "644592",
        "lgd_code": "644592",
        "firka": "Pollachi North",
        "taluk": "Pollachi",
        "district": "Coimbatore",
        "lat": 10.685,
        "lng": 77.015,
        "layout_group": "A",
    },
    {"name": "Anupperpalayam", "tamil_name": "அனுப்பர்பாளையம்", "census_code": "644535", "lgd_code": "644535", "firka": "Pollachi North", "taluk": "Pollachi", "district": "Coimbatore", "lat": 10.710, "lng": 77.025, "layout_group": "A"},
    {"name": "A. Nagur", "tamil_name": "ஏ. நாகூர்", "census_code": "644537", "lgd_code": "644537", "firka": "Pollachi North", "taluk": "Pollachi", "district": "Coimbatore", "lat": 10.720, "lng": 77.035, "layout_group": "A"},
    {"name": "Kittasoorampalayam", "tamil_name": "கிட்டசூரம்பாளையம்", "census_code": "644534", "lgd_code": "644534", "firka": "Pollachi North", "taluk": "Pollachi", "district": "Coimbatore", "lat": 10.712, "lng": 77.018, "layout_group": "A"},
    {"name": "Bodipalayam", "tamil_name": "போடிபாளையம்", "census_code": "644549", "lgd_code": "644549", "firka": "Pollachi North", "taluk": "Pollachi", "district": "Coimbatore", "lat": 10.735, "lng": 77.045, "layout_group": "A"},
    # Layout B (Pollachi South Corridor)
    {"name": "Chinnampalayam", "tamil_name": "சின்னம்பாளையம்", "census_code": "644501", "lgd_code": "644501", "firka": "Pollachi South", "taluk": "Pollachi", "district": "Coimbatore", "lat": 10.645, "lng": 77.002, "layout_group": "B"},
    {"name": "Unjavelampatti", "tamil_name": "ஊஞ்சவேலாம்பட்டி", "census_code": "644541", "lgd_code": "644541", "firka": "Pollachi South", "taluk": "Pollachi", "district": "Coimbatore", "lat": 10.642, "lng": 77.030, "layout_group": "B"},
    {"name": "Zamin Muthur", "tamil_name": "ஜமீன் முத்தூர்", "census_code": "644542", "lgd_code": "644542", "firka": "Pollachi South", "taluk": "Pollachi", "district": "Coimbatore", "lat": 10.648, "lng": 77.035, "layout_group": "B"},
    {"name": "Kolarpatti", "tamil_name": "கோலார்பட்டி", "census_code": "644556", "lgd_code": "644556", "firka": "Pollachi South", "taluk": "Pollachi", "district": "Coimbatore", "lat": 10.620, "lng": 77.060, "layout_group": "B"},
    {"name": "Gomangalam", "tamil_name": "கோமங்கலம்", "census_code": "644554", "lgd_code": "644554", "firka": "Pollachi South", "taluk": "Pollachi", "district": "Coimbatore", "lat": 10.615, "lng": 77.065, "layout_group": "B"},
]

SOURCE_URL = "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_6_gzip_no_header/3ba9_buildings.csv.gz"
OUTPUT_DIR = "app/data/open_buildings"
BOUNDARIES_DIR = "app/data/boundaries"


def generate_group_voronoi(group_villages, buffer_deg=0.018):
    """
    Generate bounded Voronoi polygons for a group of adjoining villages.
    Produces clean, non-rectangular, contiguous polygons with zero gaps/overlaps.
    """
    pts = np.array([[v["lng"], v["lat"]] for v in group_villages])
    min_x, min_y = pts[:, 0].min() - buffer_deg, pts[:, 1].min() - buffer_deg
    max_x, max_y = pts[:, 0].max() + buffer_deg, pts[:, 1].max() + buffer_deg
    bounding_box = box(min_x, min_y, max_x, max_y)

    # Add 4 distant boundary dummy points to close the Voronoi cells
    dummy_dist = 0.5
    dummy_pts = np.array([
        [pts[:, 0].mean() - dummy_dist, pts[:, 1].mean() - dummy_dist],
        [pts[:, 0].mean() + dummy_dist, pts[:, 1].mean() - dummy_dist],
        [pts[:, 0].mean() + dummy_dist, pts[:, 1].mean() + dummy_dist],
        [pts[:, 0].mean() - dummy_dist, pts[:, 1].mean() + dummy_dist],
    ])
    all_pts = np.vstack([pts, dummy_pts])
    vor = Voronoi(all_pts)

    polygons = []
    for i in range(len(group_villages)):
        region_idx = vor.point_region[i]
        region = vor.regions[region_idx]
        if -1 in region or len(region) == 0:
            # Fallback
            poly = Point(pts[i]).buffer(0.015)
        else:
            vertices = vor.vertices[region]
            poly = Polygon(vertices)
        # Clip to envelope
        clipped = poly.intersection(bounding_box)
        if not clipped.is_valid:
            clipped = make_valid(clipped)
        if isinstance(clipped, Polygon):
            mp = MultiPolygon([clipped])
        elif isinstance(clipped, MultiPolygon):
            mp = clipped
        else:
            mp = MultiPolygon([poly.buffer(0)])
        polygons.append(mp)

    return polygons


def run_extraction(target_buildings_per_village=600):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(BOUNDARIES_DIR, exist_ok=True)

    # 1. Delineate provisional boundaries for both groups
    group_A = [v for v in POLLACHI_VILLAGES if v["layout_group"] == "A"]
    group_B = [v for v in POLLACHI_VILLAGES if v["layout_group"] == "B"]

    polys_A = generate_group_voronoi(group_A)
    polys_B = generate_group_voronoi(group_B)

    for v, poly in zip(group_A, polys_A):
        v["polygon"] = poly
    for v, poly in zip(group_B, polys_B):
        v["polygon"] = poly

    # Save provisional boundary GeoJSONs
    for v in POLLACHI_VILLAGES:
        code_str = v["census_code"]
        geojson_data = {
            "type": "FeatureCollection",
            "properties": {
                "name": f"{v['name']} (Provisional Boundary)",
                "official_name": v["name"],
                "tamil_name": v["tamil_name"],
                "census_code": v["census_code"],
                "lgd_code": v["lgd_code"],
                "firka": v["firka"],
                "taluk": v["taluk"],
                "district": v["district"],
                "boundary_status": "PROVISIONAL",
                "source": "Provisional territorial delineation based on Census 2011 revenue village coordinates and Voronoi settlement partitioning within Pollachi Taluk",
                "licence": "ODbL 1.0 / CC-BY-4.0",
                "is_official": False,
                "is_provisional": True,
                "verification_date": "2026-11-12",
                "source_url": "https://coimbatore.nic.in/revenue-administration/",
            },
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "name": v["name"],
                        "boundary_status": "PROVISIONAL",
                        "census_code": v["census_code"],
                    },
                    "geometry": mapping(v["polygon"]),
                }
            ],
        }
        filename = f"{BOUNDARIES_DIR}/vill_{code_str}_provisional_boundary.geojson"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(geojson_data, f, indent=2)
        logger.info(f"Saved provisional boundary: {filename}")

    # Envelope for streaming Open Buildings
    all_polys = [v["polygon"] for v in POLLACHI_VILLAGES]
    combined_union = unary_union(all_polys)
    min_lng, min_lat, max_lng, max_lat = combined_union.bounds
    logger.info(f"Extraction bounding box: Lat [{min_lat:.4f}, {max_lat:.4f}], Lng [{min_lng:.4f}, {max_lng:.4f}]")

    # 2. Stream Open Buildings V3
    logger.info(f"Streaming from Google Cloud Storage: {SOURCE_URL}...")
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "AI-Enumerator/1.0"})

    decomp = zlib.decompressobj(16 + zlib.MAX_WBITS)
    chunk_size = 512 * 1024
    bytes_read = 0
    text_buf = ""
    seen_hashes = set()

    village_buildings = {v["census_code"]: [] for v in POLLACHI_VILLAGES}
    village_lookup = {v["census_code"]: v for v in POLLACHI_VILLAGES}

    start_time = time.time()
    total_processed = 0

    with urllib.request.urlopen(req) as resp:
        while True:
            # Check if all villages have enough buildings
            all_filled = all(len(b) >= target_buildings_per_village for b in village_buildings.values())
            if all_filled:
                logger.info("All 10 villages reached target building count!")
                break

            chunk = resp.read(chunk_size)
            if not chunk:
                break
            bytes_read += len(chunk)
            try:
                uncompressed = decomp.decompress(chunk).decode("utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Decompress error at {bytes_read} bytes: {e}")
                continue

            text_buf += uncompressed
            if "\n" in text_buf:
                lines = text_buf.split("\n")
                text_buf = lines[-1]

                for line in lines[:-1]:
                    if not line:
                        continue
                    parts = line.split(",", 4)
                    if len(parts) < 5:
                        continue

                    try:
                        lat = float(parts[0])
                        lng = float(parts[1])
                        area_raw = float(parts[2])
                        confidence = float(parts[3])
                        rest = parts[4]
                    except ValueError:
                        continue

                    # Bounding box filter
                    if not (min_lat <= lat <= max_lat and min_lng <= lng <= max_lng):
                        continue

                    # Confidence filter (documented >= 0.65 threshold)
                    if confidence < 0.65:
                        continue

                    pt = Point(lng, lat)
                    if not combined_union.contains(pt):
                        continue

                    # Parse polygon WKT and plus code
                    geom_wkt = None
                    plus_code = None
                    if rest.startswith('"POLYGON') or rest.startswith('"MULTIPOLYGON'):
                        end_quote = rest.find('"', 1)
                        if end_quote != -1:
                            geom_wkt = rest[1:end_quote]
                            code_part = rest[end_quote + 1 :].strip(",")
                            plus_code = code_part.strip().strip('"')
                    elif rest.startswith("POLYGON") or rest.startswith("MULTIPOLYGON"):
                        comma_idx = rest.rfind(",")
                        if comma_idx != -1:
                            geom_wkt = rest[:comma_idx]
                            plus_code = rest[comma_idx + 1 :].strip().strip('"')

                    if not geom_wkt:
                        continue

                    # Validate geometry
                    try:
                        poly_geom = wkt.loads(geom_wkt)
                        if not poly_geom.is_valid:
                            poly_geom = make_valid(poly_geom)
                        if poly_geom.is_empty:
                            continue
                    except Exception:
                        continue

                    # Spatial deduplication hash
                    spatial_key = f"{round(lat, 5)}_{round(lng, 5)}"
                    if spatial_key in seen_hashes:
                        continue
                    seen_hashes.add(spatial_key)

                    # Determine which village contains this centroid
                    assigned_vcode = None
                    for v in POLLACHI_VILLAGES:
                        if v["polygon"].contains(pt):
                            assigned_vcode = v["census_code"]
                            break

                    if not assigned_vcode:
                        continue

                    if len(village_buildings[assigned_vcode]) >= target_buildings_per_village:
                        continue

                    # Metric projected area
                    try:
                        poly_utm = project_to_utm(poly_geom)
                        area_m2 = round(poly_utm.area, 1)
                        centroid_utm = poly_utm.centroid
                        centroid_wgs84 = project_to_wgs84(centroid_utm)
                        centroid_lat = round(centroid_wgs84.y, 6)
                        centroid_lng = round(centroid_wgs84.x, 6)
                    except Exception:
                        area_m2 = round(area_raw, 1)
                        centroid_lat = round(lat, 6)
                        centroid_lng = round(lng, 6)

                    vdata = village_lookup[assigned_vcode]
                    bldg_record = {
                        "source_building_id": plus_code or f"GOB3_{round(lat, 5)}_{round(lng, 5)}",
                        "source_dataset": "Google Open Buildings V3",
                        "latitude": centroid_lat,
                        "longitude": centroid_lng,
                        "area_in_meters": area_m2,
                        "confidence": round(confidence, 3),
                        "geometry": mapping(poly_geom),
                        "village_census_code": assigned_vcode,
                        "village_name": vdata["name"],
                        "taluk": vdata["taluk"],
                        "district": vdata["district"],
                        "is_synthetic": False,
                        "extraction_timestamp": datetime.now(UTC).isoformat(),
                        "licence": "CC-BY-4.0",
                    }
                    village_buildings[assigned_vcode].append(bldg_record)
                    total_processed += 1

            if bytes_read % (50 * 1024 * 1024) == 0:
                elapsed = time.time() - start_time
                counts_str = ", ".join(f"{v['name'][:6]}:{len(village_buildings[v['census_code']])}" for v in POLLACHI_VILLAGES)
                logger.info(f"Processed {bytes_read / 1024 / 1024:.0f} MB in {elapsed:.1f}s | {counts_str}")

    elapsed = time.time() - start_time
    logger.info(f"Extraction completed in {elapsed:.1f}s. Total buildings extracted: {total_processed}")
    for v in POLLACHI_VILLAGES:
        logger.info(f"- {v['name']} ({v['census_code']}): {len(village_buildings[v['census_code']])} buildings")

    # Save to disk
    all_bldgs = []
    for b_list in village_buildings.values():
        all_bldgs.extend(b_list)

    final_payload = {
        "metadata": {
            "source": "Google Research Open Buildings V3",
            "source_url": SOURCE_URL,
            "region": "Pollachi Taluk, Coimbatore District, Tamil Nadu, India",
            "crs": "EPSG:4326 (projected calculations in EPSG:32643)",
            "extraction_date": datetime.now(UTC).isoformat(),
            "licence": "CC-BY-4.0",
            "is_synthetic": False,
            "total_buildings": len(all_bldgs),
            "villages_covered": len(POLLACHI_VILLAGES),
        },
        "buildings": all_bldgs,
    }

    out_file = f"{OUTPUT_DIR}/pollachi_real_open_buildings_v3.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_payload, f)
    logger.info(f"Saved complete dataset to {out_file} ({len(all_bldgs)} buildings)")


if __name__ == "__main__":
    run_extraction(target_buildings_per_village=500)

