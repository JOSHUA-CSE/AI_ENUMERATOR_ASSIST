import urllib.request
import zlib
import time

SOURCE_URL = "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_6_gzip_no_header/3ba9_buildings.csv.gz"

MIN_LAT, MAX_LAT = 10.60, 10.75
MIN_LNG, MAX_LNG = 76.95, 77.10

print(f"Connecting to {SOURCE_URL}...")
req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "AI-Enumerator/1.0"})

decomp = zlib.decompressobj(16 + zlib.MAX_WBITS)
chunk_size = 512 * 1024
bytes_read = 0
text_buf = ""
matching_buildings = 0

start_time = time.time()

with urllib.request.urlopen(req) as resp:
    # Read first 10MB of compressed data to test
    for _ in range(20):
        chunk = resp.read(chunk_size)
        if not chunk:
            break
        bytes_read += len(chunk)
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
                    if MIN_LAT <= lat <= MAX_LAT and MIN_LNG <= lng <= MAX_LNG:
                        matching_buildings += 1
                except ValueError:
                    pass

print(f"Checked {bytes_read / 1024 / 1024:.1f} MB in {time.time() - start_time:.2f}s. Matching buildings so far: {matching_buildings}")

