import urllib.request
import json

url = "https://polygons.openstreetmap.fr/get_geojson.py?id=10315635"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode("utf-8")
        if content.startswith("{"):
            data = json.loads(content)
            print("Polygons OSM FR success! Type:", data.get("type"))
            with open("app/data/boundaries/pollachi_taluk.geojson", "w") as f:
                f.write(content)
            print("Saved app/data/boundaries/pollachi_taluk.geojson")
        else:
            print("Response:", content[:200])
except Exception as e:
    print(f"Error: {e}")

