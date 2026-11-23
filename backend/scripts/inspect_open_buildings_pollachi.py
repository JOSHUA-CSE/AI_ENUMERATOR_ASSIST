import json
import urllib.request
import zlib
import time
from shapely.geometry import Point, Polygon
from pyproj import Transformer

transformer = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)

villages = [
    # North
    {"name": "Achipatti", "code": "644592", "lat": 10.685, "lng": 77.015},
    {"name": "Anupperpalayam", "code": "644535", "lat": 10.710, "lng": 77.025},
    {"name": "A. Nagur", "code": "644537", "lat": 10.720, "lng": 77.035},
    {"name": "Kittasoorampalayam", "code": "644534", "lat": 10.712, "lng": 77.018},
    {"name": "Bodipalayam", "code": "644549", "lat": 10.735, "lng": 77.045},
    # South
    {"name": "Chinnampalayam", "code": "644501", "lat": 10.645, "lng": 77.002},
    {"name": "Unjavelampatti", "code": "644541", "lat": 10.642, "lng": 77.030},
    {"name": "Zamin Muthur", "code": "644542", "lat": 10.648, "lng": 77.035},
    {"name": "Kolarpatti", "code": "644556", "lat": 10.620, "lng": 77.060},
    {"name": "Gomangalam", "code": "644554", "lat": 10.615, "lng": 77.065},
]

# Overall bounding box covering all 10 villages:
# Lat: 10.60 to 10.75
# Lng: 76.99 to 77.08
min_lat, max_lat = 10.60, 10.75
min_lng, max_lng = 76.99, 77.08

print(f"Bounding box: Lat [{min_lat}, {max_lat}], Lng [{min_lng}, {max_lng}]")
SOURCE_URL = "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_6_gzip_no_header/3ba9_buildings.csv.gz"
req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "AI-Enumerator/1.0"})

decomp = zlib.decompressobj(16 + zlib.MAX_WBITS)
chunk_size = 512 * 1024
text_buf = ""
total_extracted = 0

with urllib.request.urlopen(req) as resp:
    # Read first 30MB of compressed data to see footprint count
    for i in range(60):
        chunk = resp.read(chunk_size)
        if not chunk:
            break
        uncompressed = decomp.decompress(chunk).decode("utf-8", errors="ignore")
        text_buf += uncompressed
        lines = text_buf.split("\n")
        text_buf = lines[-1]
        for line in lines[:-1]:
            parts = line.split(",", 4)
            if len(parts) >= 4:
                try:
                    lat = float(parts[0])
                    lng = float(parts[1])
                    if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
                        total_extracted += 1
                except ValueError:
                    pass

print(f"Footprints found in bbox from first 30MB: {total_extracted}")

