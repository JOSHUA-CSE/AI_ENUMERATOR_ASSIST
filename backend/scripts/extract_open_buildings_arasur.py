import json
import logging
import os
import time
import urllib.request
import zlib
from datetime import UTC, datetime

from pyproj import Transformer
from shapely import wkt
from shapely.geometry import mapping
from shapely.ops import transform
from shapely.validation import make_valid

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Coordinate transformations: WGS84 (EPSG:4326) <-> UTM 43N (EPSG:32643)
transformer_to_32643 = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
transformer_to_4326 = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)


def project_to_utm(geom):
    return transform(transformer_to_32643.transform, geom)


def project_to_wgs84(geom):
    return transform(transformer_to_4326.transform, geom)


# Geographic bounding box for Arasur Village & vicinity:
# Latitude: 11.065 to 11.105 N
# Longitude: 77.105 to 77.145 E
MIN_LAT, MAX_LAT = 11.065, 11.105
MIN_LNG, MAX_LNG = 77.105, 77.145

SOURCE_URL = "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_6_gzip_no_header/3ba9_buildings.csv.gz"
OUTPUT_PATH = "backend/app/data/open_buildings/arasur_real_open_buildings_v3.json"


def extract_genuine_open_buildings():
    logger.info(f"Connecting to Google Cloud Storage: {SOURCE_URL}")
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "AI-Enumerator/1.0"})

    decomp = zlib.decompressobj(16 + zlib.MAX_WBITS)
    chunk_size = 512 * 1024
    bytes_read = 0
    text_buf = ""
    total_rows = 0

    valid_buildings = []
    rejected_stats = {
        "out_of_bounds": 0,
        "invalid_geometry": 0,
        "low_confidence": 0,
        "duplicate_or_overlap": 0,
    }
    seen_hashes = set()

    start_time = time.time()
    last_log_time = start_time

    with urllib.request.urlopen(req) as resp:
        while True:
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
                total_rows += len(lines) - 1

                for line in lines[:-1]:
                    if not line:
                        continue
                    # Format: lat, lng, area, confidence, geometry_wkt, full_plus_code
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
                    if not (MIN_LAT <= lat <= MAX_LAT and MIN_LNG <= lng <= MAX_LNG):
                        continue

                    # Parse geometry and plus code
                    # The rest string contains "POLYGON(...)",plus_code
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
                            rejected_stats["invalid_geometry"] += 1
                            continue
                    except Exception:
                        rejected_stats["invalid_geometry"] += 1
                        continue

                    # Projected calculations using EPSG:32643
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

                    # Deduplication via spatial hash
                    spatial_key = f"{round(centroid_lat, 5)}_{round(centroid_lng, 5)}"
                    if spatial_key in seen_hashes:
                        rejected_stats["duplicate_or_overlap"] += 1
                        continue
                    seen_hashes.add(spatial_key)

                    building_id = f"OB-V3-IND-TN-{len(valid_buildings)+1:05d}"

                    valid_buildings.append(
                        {
                            "id": building_id,
                            "source_id": plus_code or building_id,
                            "latitude": centroid_lat,
                            "longitude": centroid_lng,
                            "area_in_meters": area_m2,
                            "confidence": round(confidence, 4),
                            "full_plus_code": plus_code,
                            "geometry": mapping(poly_geom),
                        }
                    )

            now = time.time()
            if now - last_log_time >= 15:
                mb_read = bytes_read / (1024 * 1024)
                rate = mb_read / (now - start_time)
                logger.info(
                    f"Progress: {mb_read:.1f} MB streamed ({rate:.2f} MB/s) | "
                    f"{total_rows:,} rows scanned | {len(valid_buildings)} Arasur buildings extracted"
                )
                last_log_time = now

    logger.info(
        f"Stream completed. Total MB: {bytes_read / (1024*1024):.1f} MB | "
        f"Total rows: {total_rows:,} | Valid Arasur buildings: {len(valid_buildings)}"
    )

    dataset_payload = {
        "source": "Google Open Buildings V3",
        "imagery_source": "Google Open Buildings V3",
        "dataset_version": "v3",
        "acquisition_date": "2023-05-15T00:00:00Z",
        "import_timestamp": datetime.now(UTC).isoformat(),
        "licence": "Creative Commons Attribution (CC BY-4.0) and Open Data Commons Open Database License (ODbL)",
        "attribution": "Google Open Buildings Dataset V3, Google Research",
        "region": "Arasur Village, Sulur Taluk, Coimbatore District, Tamil Nadu, India",
        "boundary_code": "VILL-638401",
        "tile_id": "3ba9",
        "tile_url": SOURCE_URL,
        "projected_crs": "EPSG:32643",
        "bounds": [MIN_LNG, MIN_LAT, MAX_LNG, MAX_LAT],
        "is_synthetic": False,
        "total_detected_buildings": len(valid_buildings),
        "extraction_summary": {
            "source_stream_mb": round(bytes_read / (1024 * 1024), 2),
            "total_rows_scanned": total_rows,
            "valid_buildings_extracted": len(valid_buildings),
            "rejected_duplicates": rejected_stats["duplicate_or_overlap"],
            "rejected_invalid_geometry": rejected_stats["invalid_geometry"],
        },
        "buildings": valid_buildings,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset_payload, f)

    logger.info(f"Saved genuine dataset ({len(valid_buildings)} buildings) to {OUTPUT_PATH}")
    return dataset_payload


if __name__ == "__main__":
    extract_genuine_open_buildings()
