import urllib.request
import json

url = "https://api.github.com/repos/ramSeraph/indian_admin_boundaries/releases"
req = urllib.request.Request(url, headers={"User-Agent": "AI-Enumerator/1.0"})

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        releases = json.loads(resp.read().decode("utf-8"))
        for r in releases[:5]:
            print(f"Release: {r.get('tag_name')}")
            for a in r.get("assets", []):
                name = a.get("name")
                if "village" in name.lower() or "tamil" in name.lower() or "tngis" in name.lower():
                    print(f"  Asset: {name} ({a.get('size')} bytes)")
except Exception as e:
    print(f"Error: {e}")

