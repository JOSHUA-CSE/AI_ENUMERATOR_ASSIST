import urllib.request
import urllib.parse
import json

# Try querying Overpass for "Achipatti" or "Pollachi"
query = """
[out:json][timeout:25];
(
  relation["name"~"Achipatti|Chinnampalayam|Unjavelampatti|Zamin Muthur|Singanallur|Gomangalam|Kolarpatti|Kanjampatti|Samathur|Anaimalai",i];
  way["name"~"Achipatti|Chinnampalayam|Unjavelampatti",i]["boundary"="administrative"];
);
out tags bb;
"""

url = "https://overpass-api.de/api/interpreter"
req = urllib.request.Request(url, data=query.encode("utf-8"), headers={"User-Agent": "AI-Enumerator/1.0"})
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"Elements found: {len(data.get('elements', []))}")
        for el in data.get("elements", []):
            print(el.get("type"), el.get("id"), el.get("tags"))
except Exception as e:
    print(f"Error: {e}")

