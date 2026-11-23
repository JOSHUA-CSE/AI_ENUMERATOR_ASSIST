import urllib.request
import json

url = "https://api.github.com/repos/datameet/indian_village_boundaries/contents"
req = urllib.request.Request(url, headers={"User-Agent": "AI-Enumerator/1.0"})

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        for item in data:
            print(item["name"], item["type"], item.get("download_url"))
except Exception as e:
    print(f"Error: {e}")

