import urllib.request
import json

url = "https://nominatim.openstreetmap.org/details.php?osmtype=R&osmid=10315635&format=json&polygon_geojson=1"
req = urllib.request.Request(url, headers={"User-Agent": "AI-Enumerator/1.0 (contact: test@example.com)"})

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("Name:", data.get("local_name"))
        geom = data.get("geometry")
        print("Geometry type:", geom.get("type") if geom else None)
        if geom:
            print("Coords len:", len(geom.get("coordinates", [])))
            with open("pollachi_taluk_osm.geojson", "w") as f:
                json.dump({"type": "Feature", "geometry": geom, "properties": {"name": "Pollachi Taluk", "osm_id": 10315635}}, f)
            print("Saved pollachi_taluk_osm.geojson!")
except Exception as e:
    print(f"Error: {e}")

