# PHASE 7 — ROUTE OPTIMIZATION FOR ENUMERATORS
**Implementation & Verification Report**
*AI-Enumerator Assistant — Indian Census Digital Enumeration Platform*
*Date: November 12, 2026*

---

## 1. Initial Routing Audit

Before modifying code, an audit of the existing routing infrastructure was conducted across backend and mobile repositories:

| Component | Status | Existing Implementation | Missing / Enhanced Functionality in Phase 7 |
|---|---|---|---|
| **Road Network** | PARTIAL | `arasur_osm_roads.json` in `backend/app/data/roads/` contains Overpass OSM roads; `distance.py` had basic graph construction without tag filtering. | Added pedestrian walkable OSM tag filtering (`WALKABLE_HIGHWAY_TYPES`: residential, living_street, footway, etc.; `UNSUITABLE_HIGHWAY_TYPES`: motorway, trunk, foot=no, access=private). Added automatic loader for Arasur extent; honest `MISSING_ROAD_NETWORK_DATA` for Pollachi (zero fabricated roads). |
| **Shortest Path** | PARTIAL | `nx.single_source_dijkstra_path_length` with basic node snapping. | Handled disconnected graph components gracefully with Haversine fallback; added return-to-start loop support; explicit distance metric attribution. |
| **Visit Ordering** | PARTIAL | `solve_tsp_nearest_neighbor` + `improve_tsp_2opt` in Python & TypeScript. | Enforced input determinism (sorting by building reference & ID); added `return_to_start` closed-loop option; added timeout guard for bounded execution on $\ge 500$ buildings. |
| **HLB Restriction** | PARTIAL | Basic SQL join on `HlbHouse` and active enumerator assignment check. | Excluded `FALSE_DETECTION` buildings; filtered out buildings with invalid/missing coordinates and reported them in `unroutable_buildings`. |
| **Route API** | PARTIAL | Endpoints `POST /hlbs/{id}/route/optimize` and `GET /hlbs/{id}/route`. | Added `return_to_start` request param; added `route_id`, `assignment_id`, `version`, `routing_method`, `end_point`, `warning`, and `unroutable_buildings` to response. |
| **Mobile Route Display** | PARTIAL | `EnumeratorHlbDetailScreen.tsx` had basic metrics and list. | Added routing method badge (`🚶 ROAD NETWORK` vs `⚠️ GEOMETRIC APPROXIMATION`); warning banner; return-to-start toggle; "Next Building" navigation button; Skip Building action with recorded reason. |
| **Offline Route Support** | PARTIAL | `offline_routes` SQLite table with local TSP calculation. | Excluded `FALSE_DETECTION` buildings from local optimization; added staleness detection against local building records; added return-to-start support in SQLite engine. |

---

## 2. Existing Functionality Reused

In accordance with Phase 7 instructions, no duplicate services were created. Existing modules were directly audited, extended, and strengthened:
- **`backend/app/services/route_service.py`**: Reused the single canonical `RouteService` class, extending `generate_optimized_route` with `return_to_start`, `unroutable_buildings` reporting, and honest road network discovery.
- **`backend/app/gis/route/distance.py`**: Reused existing NetworkX Dijkstra implementation and Haversine formula, adding tag-aware pedestrian filtering and caching.
- **`backend/app/gis/route/optimizer.py`**: Reused existing Nearest Neighbor + 2-Opt local search, extending with `OptimizationResult` (4-tuple subclass preserving 100% backward compatibility), deterministic sorting, and bounded computation.
- **`backend/app/gis/route/validation.py`**: Reused existing `validate_route` function to enforce strict building uniqueness and completeness invariants.
- **`mobile/src/core/routeService.ts`**: Reused `RouteService` and client-side TSP solver, adding `returnToStart` and `field_status !== 'FALSE_DETECTION'` filtering.
- **`mobile/src/components/HlbSpatialMap.tsx`**: Reused existing Level 5 Leaflet route rendering layer and waypoints.

---

## 3. Backend Changes

### 3.1 Schemas (`backend/app/schemas/route.py`)
- **`RouteStartingPointRequest`**: Added `return_to_start: bool = False`.
- **`UnroutableBuildingInfo`**: Model capturing `building_id`, `building_reference`, and `reason` (`FALSE_DETECTION`, `MISSING_COORDINATES`, `OUTSIDE_HLB`).
- **`RouteEndPointInfo`**: Model capturing `strategy` (`ENDS_AT_FINAL_BUILDING` or `RETURNS_TO_START`), `latitude`, and `longitude`.
- **`OptimizedRouteResponse`**: Added `route_id`, `assignment_id`, `version`, `return_to_start`, `end_point`, `routing_method`, `optimization_time_ms`, `warning`, `unroutable_buildings`, `ordered_building_ids`, and `ordered_coordinates`.

### 3.2 Road Network & Distance Engine (`backend/app/gis/route/distance.py`)
- Added `load_osm_pedestrian_network(roads_file)`:
  - Parses Overpass GeoJSON/JSON road segments.
  - Filters strictly for walkable paths:
    ```python
    WALKABLE_HIGHWAY_TYPES = {
        "residential", "unclassified", "living_street", "footway",
        "pedestrian", "path", "service", "track", "steps", "tertiary", "secondary", "primary"
    }
    UNSUITABLE_HIGHWAY_TYPES = {"motorway", "motorway_link", "trunk", "trunk_link"}
    ```
  - Excludes explicit restrictions: `access in ("private", "no")` or `foot == "no"`.
  - Caches the parsed NetworkX graph in memory (3,968 nodes and 4,165 edges for Arasur).
- Extended `calculate_path_distance_km(..., return_to_start=False)`: Computes return leg distance when `return_to_start=True`.
- Handled disconnected components in `calculate_road_aware_distance_matrix`: Snaps to closest node; if no Dijkstra path exists between two nodes in disjoint components, gracefully falls back to Haversine straight-line distance.

### 3.3 Optimizer Engine (`backend/app/gis/route/optimizer.py`)
- **Determinism**: Input buildings are sorted by `(building_reference, id, lat, lon)` before calculating distance matrix and TSP order, ensuring 100% deterministic results for identical inputs.
- **Return to Start**: Implemented closed-loop TSP option in `solve_tsp_nearest_neighbor` and `improve_tsp_2opt`.
- **Bounded Runtime**: Implemented iteration scaling ($N \le 100 \implies 100$; $100 < N \le 250 \implies 60$; $N > 250 \implies 30$) and a 1.5-second timeout guard.
- **`OptimizationResult`**: Subclassed `tuple` to yield `(ordered_buildings, opt_dist_km, baseline_dist_km, strategy_used)` while exposing `.optimization_time_ms`, `.routing_method`, `.fallback_used`, `.fallback_reason`, and `.return_to_start`.

### 3.4 API Endpoints (`backend/app/api/endpoints/route.py`)
- Updated `POST /hlbs/{hlb_id}/route/optimize` to accept `return_to_start` from payload.
- Updated `GET /hlbs/{hlb_id}/route` to accept optional query parameter `return_to_start: bool = False`.

---

## 4. Road-Network Data Sources and Coverage

1. **Arasur Pilot Extent (`11.055°N – 11.151°N, 77.045°E – 77.151°E`):**
   - Source: OpenStreetMap via Overpass API (`arasur_osm_roads.json`).
   - Node count: 3,968 nodes.
   - Edge count: 4,165 edges.
   - Walkable network includes residential streets, service paths, and tertiary roads. Expressways (`NH544` trunk road) and restricted ways are excluded unless explicit pedestrian access exists.
   - Routing Method: `ROAD_NETWORK_DIJKSTRA`.

2. **Pollachi Demonstration Extent (`10.65°N – 10.69°N, 76.98°E – 77.02°E`):**
   - Source: Honest evaluation — OSM road network data is **UNAVAILABLE** locally.
   - Policy: Zero fabricated road geometries.
   - Routing Method: `GEOMETRIC_APPROXIMATION`.
   - Routing Mode: `MISSING_ROAD_NETWORK_DATA`.
   - Warning Issued: `"Road network data unavailable for this area; route calculated using geometric Haversine approximation. Straight-line distances do not reflect actual pedestrian walking paths."`

---

## 5. Route Optimization Algorithm

The route optimization pipeline operates in four deterministic stages:

1. **Deterministic Ordering & Preprocessing:**
   Input buildings are filtered for eligibility and sorted by reference code and ID. Centroids are snapped to nearest road graph nodes if road graph is active.
2. **Cost Matrix Computation:**
   - When road graph is present: All-pairs shortest path via `nx.single_source_dijkstra_path_length` with edge weights in meters.
   - When road graph is absent: Pairwise Haversine distance matrix with precomputed trigonometric radians.
3. **Nearest-Neighbor (NN) Construction:**
   Constructs the initial Hamiltonian path from the starting point (GPS or HLB centroid) greedily selecting the nearest unvisited building stop.
4. **2-Opt Local Search Improvement:**
   Iteratively checks non-adjacent edge pairs $(u_1, u_2)$ and $(v_1, v_2)$ and performs 2-opt sub-path reversals whenever:
   $$\text{cost}(u_1, v_1) + \text{cost}(u_2, v_2) < \text{cost}(u_1, u_2) + \text{cost}(v_1, v_2)$$
   Enforces monotonic improvement: if the optimized tour length exceeds baseline traversal order, baseline order is strictly preserved.

---

## 6. HLB Restriction Evidence

Server-side enforcement guarantees no cross-HLB contamination:
1. **Assignment Authorization:** `RouteService` verifies that the requesting enumerator has an `ACTIVE` assignment in `hlb_enumerator_assignments` for that specific `hlb_id` (403 Forbidden on failure).
2. **Database Join Isolation:** Buildings are queried via `House` joined with `HlbHouse` filtered by `HlbHouse.hlb_id == hlb_id`.
3. **`FALSE_DETECTION` Exclusion:** Buildings flagged as `BuildingFieldStatus.FALSE_DETECTION` are completely excluded from the route and reported in `unroutable_buildings`.
4. **Validation Guard (`validate_route`):** Verifies that every building ID in the output belongs strictly to the input set, appears exactly once, and has valid coordinates.

---

## 7. Route Distance Calculation Method

1. **Road-Network Mode:**
   $$d(B_i, B_j) = \text{snap}(B_i, G) + \text{Dijkstra}_{G}(\text{node}_i, \text{node}_j) + \text{snap}(B_j, G)$$
   Calculates actual path walking meters along residential and pedestrian edges.
2. **Geometric Approximation Mode (Haversine):**
   $$d = 2 R \arcsin \left( \sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos \phi_1 \cos \phi_2 \sin^2\left(\frac{\Delta \lambda}{2}\right)} \right)$$
   Where $R = 6,371,000 \text{ m}$. Clearly marked as `GEOMETRIC_APPROXIMATION` and never reported as actual walking distance.
3. **Return-to-Start:**
   When enabled, adds $d(B_{\text{last}}, B_{\text{start}})$ to the total path length.

---

## 8. Mobile Screen Implementation

### 8.1 `EnumeratorHlbDetailScreen.tsx`
- **Routing Method Badge (`testID="routing-method-badge"`):**
  - Displays `🚶 ROAD NETWORK (OSM)` in emerald green when road network routing is used.
  - Displays `⚠️ GEOMETRIC APPROXIMATION` in amber when Haversine straight-line approximation is used.
- **Routing Warning Banner (`testID="routing-warning-banner"`):**
  - Displays explicit notice when geometric approximation is used or when road data is unavailable.
- **Unroutable Buildings Notice (`testID="unroutable-buildings-notice"`):**
  - Displays count of excluded buildings (false detections or missing coordinates).
- **Return-to-Start Toggle (`testID="toggle-return-to-start"`):**
  - Allows enumerator to toggle between open route (`Ends at Final Building`) and closed loop (`Returns to Start`), instantly triggering recomputation.
- **Navigate to Next Building (`testID="btn-navigate-next-building"`):**
  - Direct action button finding the first unvisited building in the sequence and navigating directly to `BuildingDetailScreen`.

### 8.2 `BuildingDetailScreen.tsx`
- **Skip Building Action (`testID="skip-building-btn"`):**
  - Provides instant skip action prompting for reason (`ACCESSIBILITY_BARRIER`, `TEMPORARY_OBSTRUCTION`, `SAFETY_HAZARD`, `OTHER`).
  - Records revisit entry with `[SKIPPED]` note prefix and sets building field status to `REVISIT_REQUIRED`.

---

## 9. Offline Route Persistence

1. **Storage Engine:** SQLite `offline_routes` table managed via Expo SQLite / Web SQL fallback.
2. **Schema Attributes:** `id`, `hlb_id`, `enumerator_id`, `strategy`, `start_lat`, `start_lon`, `total_distance_km`, `baseline_distance_km`, `building_count`, `ordered_buildings_json`, `generated_at`, `routing_method`.
3. **Offline Resilience:**
   - Enumerator can open downloaded routes with zero cellular or Wi-Fi connectivity.
   - Building sequence and step distances remain fully intact across application restarts.
4. **Stale Route Detection:**
   - Validates cached building count against local `offline_buildings` inventory. If buildings are added, merged, or flagged `FALSE_DETECTION`, route recalculation is triggered.

---

## 10. Performance Benchmarks

Benchmark tests executed on representative workloads with varying building counts ($N = 50, 100, 250, 500, 1000$):

| Workload ($N$ Buildings) | Road Nodes / Extent | Total Time (ms) | Opt Time (ms) | Baseline Dist (km) | Opt Dist (km) | Distance Saved |
|---|---|---|---|---|---|---|
| **50 Buildings** | Micro-cluster | 3.10 ms | 3.05 ms | 1.76 km | 1.61 km | 0.16 km (-9.1%) |
| **100 Buildings** | HLB standard cluster | 40.35 ms | 40.24 ms | 3.39 km | 3.39 km | Monotonic guarantee |
| **250 Buildings** | Large HLB cluster | 260.87 ms | 260.53 ms | 11.63 km | 11.63 km | Monotonic guarantee |
| **500 Buildings** | Multi-block sector | 655.23 ms | 652.51 ms | 26.68 km | 21.85 km | 4.83 km (-18.1%) |
| **1,000 Buildings** | Full village extent | 663.47 ms | 653.65 ms | 54.59 km | 34.27 km | 20.32 km (-37.2%) |

*Observations:*
- Execution time is strictly sub-second for all standard HLB sizes ($N \le 500$) and remains under 700 ms for $N = 1,000$ buildings due to bounded 2-opt iteration scaling and timeout guards.
- Monotonic improvement guarantee strictly holds across all tests: $\text{opt\_dist} \le \text{baseline\_dist}$.

---

## 11. Complete Test Results

### 11.1 Backend Test Suite (Pytest)
Command: `cd backend; poetry run pytest`
- **Total Tests Collected:** 228
- **Passed:** 228
- **Failed:** 0
- **Duration:** 847.48s (14:07)

```text
============================= test session starts =============================
platform win32 -- Python 3.13.1, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\AI_Enumerator\backend
configfile: pyproject.toml
plugins: anyio-4.14.2, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 228 items

tests\test_areas.py ...........                                          [  4%]
tests\test_auth.py ............                                          [ 10%]
tests\test_boundary_checker.py .......                                   [ 13%]
tests\test_building_sources.py ......                                    [ 15%]
tests\test_deputy_progress.py .....................                      [ 25%]
tests\test_domain_completeness.py .........                              [ 28%]
tests\test_domain_hierarchy.py ......                                    [ 31%]
tests\test_domain_sync_and_operations.py ...                             [ 32%]
tests\test_enumerator_assignment.py ...........                          [ 37%]
tests\test_enumerator_fieldwork.py .....                                 [ 39%]
tests\test_gps.py ........                                               [ 43%]
tests\test_health.py .                                                   [ 43%]
tests\test_hlb_editing.py ............                                   [ 49%]
tests\test_hlb_generation.py ................                            [ 56%]
tests\test_hlb_line_split.py ..........                                  [ 60%]
tests\test_hlb_split_preview.py .....                                    [ 62%]
tests\test_layout_workflow_and_hierarchy.py .....                        [ 64%]
tests\test_phase7_route_validation.py ...................                [ 73%]
tests\test_pollachi_seed.py .                                            [ 73%]
tests\test_progress_service.py .                                         [ 74%]
tests\test_real_open_buildings_ingestion.py ...                          [ 75%]
tests\test_road_network_routing.py ....                                  [ 77%]
tests\test_route.py ............                                         [ 82%]
tests\test_supervisor_assignment.py .........                            [ 86%]
tests\test_supervisor_progress.py ....................                   [ 95%]
tests\test_supervisor_verification_and_change_requests.py ...            [ 96%]
tests\test_sync.py ........                                              [100%]

================= 228 passed, 8 warnings in 847.48s (0:14:07) =================
```

### 11.2 Mobile Test Suite (Jest)
Command: `cd mobile; npm test -- --maxWorkers=4`
- **Total Test Suites:** 24 passed, 24 total
- **Total Tests:** 211 passed, 211 total
- **Snapshots:** 0 total
- **Duration:** 30.159 s

```text
PASS __tests__/App.test.tsx
PASS __tests__/AreaScreens.test.tsx
PASS __tests__/SyncFlow.test.tsx
PASS __tests__/HlbScreens.test.tsx
PASS __tests__/FieldworkFlow.test.tsx
PASS __tests__/GeometryUtils.test.ts
PASS __tests__/LoginScreen.test.tsx
PASS __tests__/GpsBoundaryMonitoring.test.tsx
PASS __tests__/SupervisorFlow.test.tsx
PASS __tests__/Phase7MobileRouteOptimization.test.tsx (7.703 s)
PASS __tests__/SupervisorProgressDashboard.test.tsx (24.126 s)
PASS __tests__/DeputyProgressMonitoring.test.tsx (26.327 s)
PASS __tests__/RouteFlow.test.tsx
PASS __tests__/MultiAreaLayoutAndSplitPreview.test.tsx
PASS __tests__/HlbReviewScreen.test.tsx
PASS __tests__/LayoutWorkflowAndHierarchy.test.tsx
...
Test Suites: 24 passed, 24 total
Tests:       211 passed, 211 total
Snapshots:   0 total
Time:        30.159 s
Ran all test suites.
```

### 11.3 TypeScript Compilation Check
Command: `cd mobile; npx tsc --noEmit`
- **Output:** Exit code 0 (0 compilation errors).

---

## 12. Verification Status Matrix

| Scenario / Requirement | Verification Method | Status | Notes |
|---|---|---|---|
| Exactly 1 Building Route | Pytest `test_01_one_building` | **VERIFIED** | Sequence order 1, non-negative distance, ID preserved |
| Exactly 2 Buildings Route | Pytest `test_02_two_buildings` | **VERIFIED** | Sequence orders 1..2, valid distance |
| Multiple Buildings (12+) | Pytest `test_03_multiple_buildings` | **VERIFIED** | All visited exactly once in 1..N sequence |
| Dense Building Clusters | Pytest `test_04_dense_building_clusters` | **VERIFIED** | 2-opt uncrosses paths in 25-building micro-grid |
| Irregular Building Distribution | Pytest `test_05_irregularly_distributed_buildings` | **VERIFIED** | 30 randomly scattered coordinates |
| Disconnected Road Components | Pytest `test_06_disconnected_road_network_components` | **VERIFIED** | Disjoint road islands fallback gracefully to Haversine |
| Missing Building Coordinates | Pytest `test_07_missing_building_coordinates` | **VERIFIED** | Excluded from route, reported in `unroutable_buildings` |
| Invalid Building Geometry | Pytest `test_08_invalid_building_geometry` | **VERIFIED** | Coordinate out-of-bounds rejected by `validate_route` |
| Multi-HLB Contamination Guard | Pytest `test_09_buildings_belonging_to_different_hlbs` | **VERIFIED** | Foreign HLB buildings strictly excluded server-side |
| `FALSE_DETECTION` Exclusion | Pytest `test_10_false_detection_exclusion` | **VERIFIED** | Excluded and reported in `unroutable_buildings` |
| No Road Graph (Pollachi) | Pytest `test_11_no_available_road_graph_pollachi` | **VERIFIED** | Marked `GEOMETRIC_APPROXIMATION` with honest warning |
| Haversine Fallback Accuracy | Pytest `test_12_haversine_fallback` | **VERIFIED** | Verified against Coimbatore ground-truth distances |
| Return-to-Start Option | Pytest `test_13_optional_return_to_start` | **VERIFIED** | Closed-loop distance includes return leg |
| Route Determinism | Pytest `test_14_deterministic_route_generation` | **VERIFIED** | Shuffled inputs yield identical output sequence |
| Scalability Benchmarks | Pytest `test_15_benchmark_representative_workloads` | **VERIFIED** | 50, 100, 250, 500, 1,000 buildings all pass bounded time |
| Mobile Route Method Badge & Warning | Jest `Phase7MobileRouteOptimization.test.tsx` | **VERIFIED** | Verified badge text, toggle, and warning banner |
| Mobile Next Building Navigation | Jest `Phase7MobileRouteOptimization.test.tsx` | **VERIFIED** | Auto-navigates to first pending building |
| Mobile Skip Building Action | Jest `Phase7MobileRouteOptimization.test.tsx` | **VERIFIED** | Revisit modal with skip reason logging |
| Physical Android Device Execution | Hardware Test | **UNVERIFIED** | Verified under Jest/JSDOM mock environment; physical Android hardware unverified |

---

## 13. Known Limitations

1. **Elevation & Gradient Invariance:** Route cost calculation does not incorporate elevation changes (slopes/stairs) due to lack of high-resolution digital elevation models (DEM) in the OpenStreetMap export.
2. **Dynamic Turn Restrictions:** Temporary construction blocks or real-time traffic conditions are not reflected in static OSM exports.
3. **Physical Android Device Execution:** Tests executed in Node/JSDOM automated test environment; execution on physical Android mobile hardware remains marked **UNVERIFIED**.

---
*Phase 7 complete. All strict stop conditions observed. No Git operations were performed.*

