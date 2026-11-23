import urllib.request
import zlib

SOURCE_URL = "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_6_gzip_no_header/3ba9_buildings.csv.gz"
req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "AI-Enumerator/1.0"})

decomp = zlib.decompressobj(16 + zlib.MAX_WBITS)
chunk_size = 512 * 1024
text_buf = ""
lats = []

with urllib.request.urlopen(req) as resp:
    for i in range(10):
        chunk = resp.read(chunk_size)
        if not chunk:
            break
        uncompressed = decomp.decompress(chunk).decode("utf-8", errors="ignore")
        text_buf += uncompressed
        lines = text_buf.split("\n")
        text_buf = lines[-1]
        for line in lines[:-1]:
            parts = line.split(",", 2)
            if len(parts) >= 2:
                try:
                    lats.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass

print(f"Sampled {len(lats)} buildings.")
print(f"First 5: {lats[:5]}")
print(f"Last 5: {lats[-5:]}")
print(f"Min lat: {min(x[0] for x in lats)}, Max lat: {max(x[0] for x in lats)}")
print(f"Min lng: {min(x[1] for x in lats)}, Max lng: {max(x[1] for x in lats)}")

