import shutil
from pathlib import Path

BOUNDARIES_DIR = Path("app/data/boundaries")

villages = [
    ("achipatti", "644592"),
    ("anupperpalayam", "644535"),
    ("a. nagur", "644537"),
    ("a_nagur", "644537"),
    ("kittasoorampalayam", "644534"),
    ("bodipalayam", "644549"),
    ("chinnampalayam", "644501"),
    ("unjavelampatti", "644541"),
    ("zamin muthur", "644542"),
    ("zamin_muthur", "644542"),
    ("kolarpatti", "644556"),
    ("gomangalam", "644554"),
]

for name, code in villages:
    src = BOUNDARIES_DIR / f"vill_{code}_provisional_boundary.geojson"
    if src.exists():
        for alias in [f"vill-{code}", f"vill_{code}", code, name.replace(" ", "_"), name.replace(" ", "")]:
            dest = BOUNDARIES_DIR / f"{alias}_provisional_boundary.geojson"
            if not dest.exists():
                shutil.copyfile(src, dest)
                print(f"Copied {src.name} -> {dest.name}")

print("Aliases created successfully.")

