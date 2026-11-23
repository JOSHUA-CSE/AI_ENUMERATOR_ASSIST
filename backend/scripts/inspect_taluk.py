import json
from shapely.geometry import shape

with open("app/data/boundaries/pollachi_taluk.geojson", "r") as f:
    d = json.load(f)

s = shape(d)
print("Type:", s.geom_type)
print("Bounds:", s.bounds)
print("Area:", s.area)

