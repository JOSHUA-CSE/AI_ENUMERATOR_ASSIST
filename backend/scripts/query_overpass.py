import urllib.request
import json
import time

endpoints = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

overpass_query = """
[out:json][timeout:30];
(
  relation["boundary"="administrative"](10.58,76.95,10.76,77.10);
);
out tags bb;
"""

for ep in endpoints:
    try:
        print(f"Trying {ep}...")
        req = urllib.request.Request(ep, data=overpass_query.encode("utf-8"), headers={"User-Agent": "AI-Enumerator/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elements = data.get("elements", [])
            print(f"Success from {ep}! Found {len(elements)} relations.")
            for el in elements:
                tags = el.get("tags", {})
                print(f"- ID: {el.get('id')}, name: {tags.get('name')}, name:ta: {tags.get('name:ta')}, admin_level: {tags.get('admin_level')}, boundary: {tags.get('boundary')}")
            break
    except Exception as e:
        print(f"Failed {ep}: {e}")
        time.sleep(1)
