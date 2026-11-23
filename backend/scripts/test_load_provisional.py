import sys
from pathlib import Path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.gis.boundary_loader import load_provisional_boundary

for code in ["vill-644592", "vill-644501", "achipatti", "gomangalam"]:
    geom, meta = load_provisional_boundary(code)
    print(f"Loaded {code}: {meta['name']} (Area: {meta['area_sq_km']} sq km, status: {meta['boundary_status']})")
