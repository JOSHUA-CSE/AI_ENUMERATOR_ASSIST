import urllib.request
import urllib.parse
import json

villages = ["Achipatti", "Chinnampalayam", "Unjavelampatti", "Zamin Muthur", "Singanallur", "Gomangalam", "Kolarpatti", "Kanjampatti", "Nallampalayam", "Samathur"]

for v in villages:
    q = urllib.parse.quote(f"{v}, Coimbatore, Tamil Nadu, India")
    url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&polygon_geojson=1"
    req = urllib.request.Request(url, headers={"User-Agent": "AI-Enumerator-Census-App/1.0 (contact: info@ai-enumerator.org)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data:
                res = data[0]
                geojson_type = res.get("geojson", {}).get("type")
                osm_type = res.get("osm_type")
                osm_id = res.get("osm_id")
                display_name = res.get("display_name")
                print(f"{v}: found! osm_type={osm_type}, osm_id={osm_id}, geojson_type={geojson_type}, display_name={display_name[:50]}")
            else:
                print(f"{v}: not found")
    except Exception as e:
        print(f"{v}: error {e}")

