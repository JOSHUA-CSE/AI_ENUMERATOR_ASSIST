import urllib.request
import json
import time
from pathlib import Path

OUT_FILE = Path("backend/app/data/roads/pollachi_osm_roads.json")
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Try Overpass servers
endpoints = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Query walkable road segments around Pollachi pilot area (Achipatti / Chinnampalayam)
# bbox: 10.60 to 10.72 N, 76.99 to 77.06 E
query = """[out:json][timeout:25];
(
  way["highway"~"^(residential|unclassified|living_street|pedestrian|footway|path|service|track|tertiary|secondary)$"](10.62,76.99,10.72,77.06);
);
out body geom;
"""

success = False
for ep in endpoints:
    try:
        print(f"Trying {ep}...", flush=True)
        req = urllib.request.Request(
            ep,
            data=query.encode("utf-8"),
            headers={"User-Agent": "AI-Enumerator/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elements = data.get("elements", [])
            print(f"Success from {ep}: {len(elements)} walkable road ways downloaded.", flush=True)
            with open(OUT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"Saved {OUT_FILE} ({OUT_FILE.stat().st_size / 1024:.1f} KB)", flush=True)
            success = True
            break
    except Exception as exc:
        print(f"Failed {ep}: {exc}", flush=True)
        time.sleep(1)

if not success:
    print("Could not fetch Pollachi roads from Overpass directly.", flush=True)
