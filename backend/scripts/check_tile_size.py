import urllib.request

url = "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_6_gzip_no_header/3ba9_buildings.csv.gz"
req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "AI-Enumerator/1.0"})

try:
    with urllib.request.urlopen(req) as resp:
        length = resp.headers.get("Content-Length")
        if length:
            print(f"Content-Length: {int(length) / 1024 / 1024:.2f} MB")
        else:
            print("No Content-Length")
except Exception as e:
    print("Error:", e)

