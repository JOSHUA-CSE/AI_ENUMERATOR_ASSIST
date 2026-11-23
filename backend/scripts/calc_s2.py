import s2sphere

# Pollachi center ~ 10.66, 77.01
points = [
    ("Pollachi Center", 10.66, 77.01),
    ("Achipatti", 10.685, 77.015),
    ("Gomangalam", 10.615, 77.065),
    ("Arasur", 11.08, 77.12),
]

for name, lat, lng in points:
    ll = s2sphere.LatLng.from_degrees(lat, lng)
    cell = s2sphere.CellId.from_lat_lng(ll).parent(6)
    print(f"{name} ({lat}, {lng}) -> S2 level 6 token: {cell.to_token()}")

