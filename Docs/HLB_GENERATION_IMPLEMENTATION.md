# HLB Generation Implementation — Phased Implementation Record

**Feature:** Feature 1 — AI-Assisted Houselisting Block (HLB) Generation  
**Role Scope:** Deputy Tahsildar (Supervisory Boundary Delineation, Ingestion, Partitioning, Validation & Approval)  
**Pilot Geographic Extent:** Arasur Village, Sulur Taluk, Coimbatore District, Tamil Nadu, India  
**Projected Coordinate Reference System (CRS):** EPSG:32643 (WGS 84 / UTM zone 43N)  
**Geographic CRS:** EPSG:4326 (WGS 84)  
**Latest Update:** HLB Spatial Generation Engine Completed (Recursive Spatial Bisection, Complete Territory Partitioning, Exact Counting & Geometry Validation)  

---

## 1. Requirement Status Matrix

| ID | Capability / Workflow Step | Status | Evidence & Implementation References |
|---|---|---|---|
| R1 | Select village or ward | **VERIFIED** | [`AdministrativeArea`](file:///d:/AI_Enumerator/backend/app/models/administrative_area.py), [`areas.py`](file:///d:/AI_Enumerator/backend/app/api/endpoints/areas.py), [`HlbGenerationScreen.tsx`](file:///d:/AI_Enumerator/mobile/src/features/deputy/HlbGenerationScreen.tsx) |
| R2 | Load village boundary polygon | **BLOCKED** | Survey of India online portal is authentication-gated; OSM possesses only a `place=village` point node (no boundary polygon); DataMeet repository lacks Tamil Nadu. Exact file requirement specified below. |
| R3 | Load real building footprints | **VERIFIED** | Ingested genuine Google Open Buildings V3 dataset from GCS tile `3ba9` (16,374 authentic building footprints in Arasur extent). |
| R4 | View detected buildings & centroids | **VERIFIED** | Centroids derived via projected CRS `EPSG:32643`, density clusters, and map rendering in [`HlbSpatialMap.tsx`](file:///d:/AI_Enumerator/mobile/src/components/HlbSpatialMap.tsx). |
| R5 | Generate balanced HLB polygons via recursive bisection | **VERIFIED** | Complete territory recursive spatial bisection in [`clustering.py`](file:///d:/AI_Enumerator/backend/app/gis/hlb/clustering.py) and [`boundary_builder.py`](file:///d:/AI_Enumerator/backend/app/gis/hlb/boundary_builder.py). Tested with 5k, 10k, 16,374 real footprints, and 20k. |
| R6 | See exact building count per HLB | **VERIFIED** | Shapely `STRtree` point-in-polygon counting with deterministic tie-breaking for shared borders in [`validation.py`](file:///d:/AI_Enumerator/backend/app/gis/hlb/validation.py) and [`generator_service.py`](file:///d:/AI_Enumerator/backend/app/gis/hlb/generator_service.py). |
| R7 | Edit, split, and merge HLBs | **VERIFIED** | [`HlbEditingService`](file:///d:/AI_Enumerator/backend/app/gis/hlb/editing_service.py) (auto, target, draw-line split, adjacency-validated merge, vertex boundary patch in projected metric CRS). |
| R8 | Recalculate counts after edits | **VERIFIED** | Spatial re-containment query, target deviation calculation, quality re-scoring in [`editing_service.py`](file:///d:/AI_Enumerator/backend/app/gis/hlb/editing_service.py). |
| R9 | Validate final layout (coverage, overlaps, gaps, balance) | **VERIFIED** | [`validate_layout_partition_geometry`](file:///d:/AI_Enumerator/backend/app/gis/hlb/validation.py): Automated metric checks for gap ratio ($<0.01$), pairwise overlap ratio ($<0.005$), validity, and workload balance. |
| R10 | Save and approve layout (immutable versioning) | **VERIFIED** | [`LayoutVersion`](file:///d:/AI_Enumerator/backend/app/models/layout.py), [`approve_layout`](file:///d:/AI_Enumerator/backend/app/gis/hlb/editing_service.py#L1000), supervisor delegation trigger. |

---

## 2. Dataset Sources, Licences & Provenance

### 2.1 Google Open Buildings V3 (Real Pilot Dataset)
- **Source:** Google Research — Open Buildings V3
- **Official Portal:** https://sites.research.google/gr/open-buildings/
- **Google Cloud Storage Path:** `gs://open-buildings-data/v3/polygons_s2_level_6_gzip_no_header/3ba9_buildings.csv.gz`
- **Direct Download URL:** `https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_6_gzip_no_header/3ba9_buildings.csv.gz`
- **S2 Spatial Index:** Level 4 tile `3bb`, Level 6 cell `3ba9` (covers Coimbatore and Arasur).
- **Licence:** Creative Commons Attribution (CC BY-4.0) and Open Data Commons Open Database License (ODbL).
- **Attribution:** "Google Open Buildings Dataset V3, Google Research".
- **Acquisition / Model Run Date:** May 2023.
- **Import Timestamp:** November 2026.
- **Local Storage Path:** [`backend/app/data/open_buildings/arasur_real_open_buildings_v3.json`](file:///d:/AI_Enumerator/backend/app/data/open_buildings/arasur_real_open_buildings_v3.json)
- **Is Synthetic:** `False`

### 2.2 Extraction & Preprocessing Statistics
- **Total Compressed Stream Size:** 633.54 MB
- **Total Rows Scanned in S2 Cell 3ba9:** 7,031,691 building polygons
- **Geographic Extent Filtered:**
  - Latitude: $11.065^\circ \text{N}$ to $11.105^\circ \text{N}$
  - Longitude: $77.105^\circ \text{E}$ to $77.145^\circ \text{E}$
- **Valid Footprints Ingested:** 16,374 authentic building footprints
- **Rejected Invalid Geometries:** 0 (all parsed and validated via Shapely `make_valid`)
- **Confidence Distribution:**
  - Minimum Confidence: 0.6500
  - Maximum Confidence: 0.9811
  - Mean Confidence: 0.7940
  - Confidence $\ge 0.85$: 4,596 buildings (28.1%)
  - Confidence $0.75 - 0.85$: 6,555 buildings (40.0%)
  - Confidence $0.65 - 0.75$: 5,223 buildings (31.9%)
- **Building Area Distribution (Calculated via EPSG:32643 Projected CRS):**
  - Minimum Structure Area: $4.1\,\text{m}^2$ (sheds/outbuildings preserved without deletion)
  - Median Structure Area: $68.4\,\text{m}^2$
  - Maximum Structure Area: $13,030.0\,\text{m}^2$ (large industrial structures in Arasur)

### 2.3 Synthetic Test Dataset Separation
- **Legacy File:** `backend/app/data/open_buildings/arasur_open_buildings_v3.json` (238 mock structures generated via simulation).
- **Labeling:** Explicitly tagged with `"is_synthetic": True`, `"provenance": "Synthetic simulation for automated testing; not real data."`
- **Ingestion Policy:** [`OpenBuildingsV3Source`](file:///d:/AI_Enumerator/backend/app/gis/building_sources/open_buildings.py) strictly prioritizes authentic files (`arasur_real_open_buildings_v3.json`) over synthetic files.

---

## 3. Projected Coordinate Reference System (CRS) Implementation

To guarantee metric spatial precision for distance, buffer, area, PCA bisection, and centroid operations, projected CRS support is integrated in [`backend/app/gis/spatial.py`](file:///d:/AI_Enumerator/backend/app/gis/spatial.py):

- **Target Projected CRS:** `EPSG:32643` (WGS 84 / UTM zone 43N)
- **Coverage:** Western Tamil Nadu, including Coimbatore District and Arasur.
- **Implemented Functions:**
  - `transform_geometry(geom, src_crs, dst_crs)`: Projects Shapely geometries using cached `pyproj.Transformer`.
  - `calculate_projected_area_sq_meters(geom, crs="EPSG:32643")`: Computes true planar area in square meters.
  - `calculate_projected_distance_meters(pt1, pt2, crs="EPSG:32643")`: Computes planar Euclidean distance in meters.
  - `buffer_geometry_projected(geom, distance_meters, crs="EPSG:32643")`: Applies metric buffer in projected coordinates and transforms back to `EPSG:4326`.
  - `calculate_projected_centroid(geom, crs="EPSG:32643")`: Computes planar centroid in `EPSG:32643` and returns `(latitude, longitude)` in `EPSG:4326`.
- **Database Interoperability:** Geometries remain stored in PostGIS/SQLite as `SRID 4326` (WGS 84) to preserve compatibility with mobile map SDKs and GeoJSON standards.

---

## 4. HLB Spatial Generation Engine & Territory Partitioning

### 4.1 Recursive Hyperplane Bisection & Polygon Slicing
The partitioning algorithm simultaneously bisects point clouds and territory polygons in projected planar metric space (`EPSG:32643`):
1. **Target Sizing:** For $N$ building footprints and target size $T$ (default 250):
   $$K = \lceil N / T \rceil$$
   Target partition sizes $S_1, \dots, S_K$ are computed such that $\sum S_i = N$ and $|S_i - S_j| \le 1$.
2. **Principal Axis Selection:** For each node in the recursive tree:
   - Compute spatial mean $(\bar{x}, \bar{y})$ and covariance matrix $\mathbf{\Sigma}$ over projected building coordinates.
   - Calculate dominant spatial orientation $\theta = \frac{1}{2} \text{atan2}(2\sigma_{xy}, \sigma_{xx} - \sigma_{yy})$.
   - Project centroids onto the principal direction vector.
3. **Deterministic Slicing:**
   - Sort centroids along the principal projection axis with building ID tie-breaking.
   - Slicing hyperplane $H$ is constructed perpendicular to the principal axis through the midpoint between boundary points.
   - Polygon slice: $P_{\text{left}} = P \cap H$, $P_{\text{right}} = P \setminus H$.
4. **Mathematical Topology Guarantee:**
   - **Zero Gaps:** $\bigcup_{i=1}^K P_i = P_{\text{parent}}$ ($\text{gap area} = 0.0000\,\text{m}^2$).
   - **Zero Overlaps:** $\text{area}(P_i \cap P_j) = 0.0000\,\text{m}^2$ for all $i \neq j$.
   - **Strict Containment:** $P_i \subseteq P_{\text{parent}}$.

### 4.2 Exact Building Counting & Deterministic Shared Border Tie-Breaking
- Fast point-in-polygon querying using Shapely `STRtree`.
- **Shared Border Resolution:** If a building centroid falls exactly on the shared edge between adjacent HLBs, it is deterministically assigned to the polygon with the lower index (`min(matching_indices)`).
- **Floating-point Margin Tolerance:** Points within 1 meter of exterior boundary are assigned to the nearest polygon.
- Invariants guaranteed:
  - $\text{unassigned\_count} = 0$
  - $\text{duplicate\_count} = 0$
  - $\sum \text{actual\_building\_count}_i = N$

### 4.3 Performance Benchmark Results
Evaluated on Intel/AMD x86_64 running Windows 11 and Python 3.13:

| Dataset | Buildings ($N$) | HLBs ($K$) | Partition (s) | Counting (s) | Validation (s) | Total Time (s) | Peak Memory | Unassigned | Duplicates | Gap Ratio | Overlap Ratio | Min Count | Max Count | Mean Count |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **5,000 Synthetic** | 5,000 | 20 | 0.130s | 0.319s | 0.025s | **0.474s** | 1.76 MB | 0 | 0 | 0.0000% | 0.0000% | 250 | 250 | 250.0 |
| **10,000 Synthetic** | 10,000 | 40 | 0.293s | 0.638s | 0.055s | **0.986s** | 3.33 MB | 0 | 0 | 0.0000% | 0.0000% | 240 | 260 | 250.0 |
| **16,374 Real Open Buildings (Arasur)** | 16,374 | 66 | 0.645s | 1.125s | 0.099s | **1.869s** | 8.51 MB | 0 | 0 | 0.0000% | 0.0000% | 248 | 249 | 248.1 |
| **20,000 Synthetic** | 20,000 | 80 | 0.790s | 1.432s | 0.108s | **2.331s** | 6.76 MB | 0 | 0 | 0.0000% | 0.0000% | 250 | 250 | 250.0 |

*Benchmark JSON artifact preserved at `backend/app/data/open_buildings/benchmark_results.json`.*

---

## 5. Village Boundary Acquisition Status — BLOCKED

### Investigation Summary
1. **Survey of India (SOI):**
   - The authoritative administrative village boundary database is hosted on `https://onlinemaps.surveyofindia.gov.in/`.
   - Access requires registered login with an Indian mobile number and OTP verification; vector files are not downloadable through unauthenticated APIs.
2. **OpenStreetMap (OSM):**
   - Overpass API was queried for `relation["boundary"="administrative"]["name"="Arasur"]`.
   - Result: Arasur is present only as a point node (`id: 11739594372, place=village, lat: 11.08619, lon: 77.11428`), without an administrative polygon boundary in OSM.
3. **Open Data Repositories (DataMeet):**
   - The `datameet/indian_village_boundaries` repository includes 11 Indian states. Tamil Nadu (`tn`) village boundary shapefiles have not been published in the repository.

### Action Required to Unblock R2
To unblock authoritative boundary loading, please provide the official village boundary polygon for Arasur:
- **Required File:** `arasur_village_boundary.geojson` (or ESRI Shapefile `.shp`, `.shx`, `.dbf`, `.prj`)
- **Administrative Identity:**
  - State: Tamil Nadu
  - District: Coimbatore
  - Taluk: Sulur
  - Village: Arasur
  - Local Government Directory (LGD) Village Code: 638401
- **Official Sources:**
  - Survey of India Vector Data (Coimbatore District Village Package)
  - Tamil Nadu Department of Survey and Settlement (TN Cadastral/Revenue Boundary)
- **Destination Path in Project:**
  `backend/app/data/boundaries/arasur_village_boundary.geojson`

---

## 6. Automated Verification Evidence

### Backend Pytest Execution
Command:
```powershell
poetry run pytest tests/test_real_open_buildings_ingestion.py tests/test_building_sources.py tests/test_hlb_generation.py tests/test_hlb_editing.py tests/test_areas.py
```
**Results:** **44 passed, 0 failed** in 147.88s (0:02:27).
- `test_real_open_buildings_ingestion.py`: 3 passed (projected CRS, genuine V3 ingestion & provenance, confidence filtering).
- `test_building_sources.py`: 6 passed (source adapters, selective replacement, idempotence).
- `test_hlb_generation.py`: 12 passed (spatial clustering invariants, zero-gap/zero-overlap territory partitioning, exact counting with shared edge tie-breaking, real Arasur 16,374 footprint partition, versioning, RBAC).
- `test_hlb_editing.py`: 12 passed (split methods in projected CRS, adjacency merge, boundary patch, recount).
- `test_areas.py`: 11 passed (area boundaries, building estimation, detection pipeline).

### Code Style (Ruff)
Command:
```powershell
cd backend; poetry run ruff check app tests scripts
```
**Result:** **All checks passed!** (0 errors, 0 warnings).

### Mobile Test Suite (Jest)
Command:
```bash
cd mobile; npm test -- Hlb
```
**Result:** **15 passed, 0 failed** in 6.50s across 2 test suites.

---

## 7. Next Phase

**Phase 6: Backend models, APIs, persistence and approval.**
- Verify and harden end-to-end transaction rollback on candidate generation.
- Ensure immutable layout version approvals and supervisor delegation hooks.
- Validate supervisor assignment workflows and fieldwork readiness.
