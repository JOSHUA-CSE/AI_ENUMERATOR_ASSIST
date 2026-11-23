# AI-Enumerator Assistant — Comprehensive Architecture Audit & Refactoring Specification

**Document Version:** 1.0  
**Audit Date:** November 2026  
**Auditor:** Senior Software Architect, GIS Engineer & QA Lead  
**Repository Root:** `d:\AI_Enumerator`  
**Target Environments:** Python 3.13 / FastAPI / PostgreSQL 15 + PostGIS 3.3 (Local dev: SQLite 3.45) & React Native / Expo SDK 57 / TypeScript 6 / SQLite  

---

## Executive Summary

A comprehensive architectural and codebase audit of **AI-Enumerator Assistant** was executed against all source code, models, database schemas, GIS optimization algorithms, mobile screens, offline storage, synchronization pipelines, and automated test suites.

Both test suites are currently in a passing baseline state:
- **Backend Test Suite (Pytest):** 151 passed, 6 deprecation warnings (10m 44s run time)
- **Mobile Test Suite (Jest):** 19 suites passed, 190 passed (16.1s run time)

However, beneath the functional test surface lie foundational domain model misalignments, architectural omissions, and non-production compromises:
1. **Domain Hierarchy Flattening:** The data model treats physical building footprints as directly identical to census households. There is no `CensusHouse` entity and no `Person` (Phase II) entity.
2. **Missing Alembic Migration Chain:** Core models (`layouts`, `layout_versions`, `houselisting_blocks`, `hlb_houses`, `household_records`, `house_fieldwork_status`, `revisits`, `gps_tracks`, `sync_operations`, `audit_logs`) were created via unmanaged `Base.metadata.create_all()` in `main.py` lifespan and `conftest.py`. Alembic migrations stopped at migration 4.
3. **Flawed Fieldwork Resolution:** Building completion is inferred solely from `FieldworkBuildingStatus.COMPLETED`. There is no `listing_closed` mechanism, no distinction between vacant/non-residential/locked census houses within a building, and no separate tracking of census houses vs households.
4. **Reassignment Data Loss Risk:** The sync service strictly checks `HlbEnumeratorAssignment.status == ACTIVE`. If an Enumerator is reassigned while possessing un-synchronized offline fieldwork, all local records are permanently rejected with 403 Unauthorized.
5. **Supervisor Verification Absence:** Household records only possess `DRAFT` and `COMPLETED` statuses. There is no `SUBMITTED -> SUPERVISOR_VERIFIED -> ACCEPTED` review lifecycle, and no `change_requests` table or thread mechanism.
6. **Online-Dependent "Offline" Maps:** Mobile mapping components (`InteractiveMap.tsx`, `HlbSpatialMap.tsx`) load Leaflet JS from `unpkg.com` and raster tiles from OpenStreetMap and Esri ArcGIS online over HTTP in a WebView. Under Android airplane mode, map initialization and tile rendering fail.
7. **Straight-Line Euclidean TSP Routing:** The route optimizer uses Haversine straight-line distance matrix with Nearest Neighbor and 2-Opt local search. No road network graph is traversed.
8. **Simulated / Mocked Voice Assistant:** `offlineVoiceService.ts` contains regex and string parser engines, but zero native speech recognition integration (no Android `SpeechRecognizer`, no Vosk, no Whisper). `startListening()` merely runs a 12-second JS timer.
9. **Unencrypted SQLite Storage:** Fieldwork database `enumerator_fieldwork.db` is opened via plaintext `expo-sqlite` without SQLCipher encryption, exposing census PII on disk.
10. **Questionnaire Hard-Coding:** Questions are hard-coded directly as React state variables in `HouseholdFormScreen.tsx` without schema versioning, question IDs, or Phase I/Phase II separation.

---

## 1. Current Architecture & Component Inventory

### 1.1 Backend Component Architecture
- **Framework:** FastAPI `>=0.110.0` running on Python 3.13.1 ASGI Uvicorn.
- **ORM & GIS:** SQLAlchemy 2.0 with GeoAlchemy2 (`POINT` and `MULTIPOLYGON` geometries in SRID 4326).
- **Security:** PyJWT bearer tokens, bcrypt password hashing, FastAPI dependency injection RBAC (`require_role`, `require_any_role`).
- **Database Architecture:**
  - Production specification: PostgreSQL 15/16 + PostGIS 3.3/3.4 (`docker-compose.yml`).
  - Active test/local database: SQLite with Spatialite fallback (`ai_enumerator.db`).
- **Current Tables in Models:**
  1. `users` (id, name, phone, username, password_hash, role, status, timestamps)
  2. `administrative_areas` (id, name, type, parent_id, code, boundary)
  3. `houses` (id, area_id, building_reference, house_number, latitude, longitude, location, footprint, source_type, detection_confidence, detected_at, imagery_source, imagery_date)
  4. `layouts` (id, area_id, name, target_hlb_building_count, actual_building_count, expected_hlb_count, boundary, status, active_version_id, created_by, approved_by, approved_at)
  5. `layout_versions` (id, layout_id, version_number, source, status, target_buildings_per_hlb, total_buildings, hlb_count, quality_score, validation_status, validation_summary, generation_metadata, created_by)
  6. `houselisting_blocks` (id, layout_id, version_id, block_code, name, target_building_count, actual_building_count, boundary, status, quality_score, validation_status, validation_details)
  7. `hlb_houses` (id, hlb_id, house_id, assigned_at, assigned_by, status)
  8. `layout_supervisor_assignments` (id, layout_id, supervisor_id, assigned_by, assigned_at, status)
  9. `hlb_enumerator_assignments` (id, hlb_id, layout_id, enumerator_id, supervisor_id, assigned_at, status)
  10. `household_records` (id, house_id, hlb_id, enumerator_id, household_number, head_name, total_members, male_count, female_count, transgender_count, ownership_status, drinking_water_source, lighting_source, latrine_facility, data, source, status, sync_status, version, captured_at)
  11. `house_fieldwork_status` (id, house_id, hlb_id, enumerator_id, status, household_count, last_updated_at, updated_by)
  12. `revisits` (id, house_id, hlb_id, enumerator_id, reason, notes, status, recommended_at, completed_at)
  13. `gps_tracks` (id, enumerator_id, hlb_id, house_id, latitude, longitude, accuracy_meters, timestamp, source)
  14. `sync_operations` (id, idempotency_key, device_id, user_id, operation_type, entity_type, entity_id, payload, client_timestamp, server_timestamp, status, retry_count, error_message, response_data)
  15. `audit_logs` (id, user_id, action, entity_type, entity_id, old_data, new_data, timestamp, ip_address, device_id)

### 1.2 Mobile Component Architecture
- **Framework:** React 19.2.3, React Native 0.86.3, Expo SDK 57, TypeScript 6.0.3.
- **Navigation:** React Navigation 7 Native Stack with role-isolated navigators:
  - `AuthNavigator`: `LoginScreen`
  - `DeputyNavigator`: `DeputyDashboardScreen`, `AreaListScreen`, `AreaMapScreen`, `LayoutListScreen`, `HlbGenerationScreen`, `HlbReviewScreen`, `DeputyLayoutDetailScreen`
  - `SupervisorNavigator`: `SupervisorDashboardScreen`, `SupervisorLayoutDetailScreen`
  - `EnumeratorNavigator`: `EnumeratorDashboardScreen`, `EnumeratorHlbDetailScreen`, `BuildingDetailScreen`, `HouseholdFormScreen`
- **Client Storage:** `expo-sqlite` (version 57.0.2) running `enumerator_fieldwork.db`.
  - Schema tables: `schema_versions`, `offline_hlbs`, `offline_buildings`, `offline_household_records`, `offline_revisits`, `offline_gps_logs`, `sync_queue`, `offline_routes`.
- **Hardware Integration:** `expo-location` (GPS tracking), `expo-secure-store` (JWT token storage).

---

## 2. Granular Audit Findings

### 2.1 Domain Model & Entities

#### Finding DM-01: Absence of Census House Entity (Building ≠ Census House)
- **File:** `backend/app/models/fieldwork.py`, `backend/app/models/house.py`, `mobile/src/core/sqlite/database.ts`
- **Class / Table:** `HouseholdRecord`, `HouseFieldworkStatus`, `offline_household_records`, `offline_buildings`
- **Current Behavior:** `HouseholdRecord` has a foreign key `house_id` pointing directly to `houses.id` (physical building footprint). In SQLite, `offline_household_records` points directly to `offline_buildings.id`.
- **Problem:** In census fieldwork, a physical building/structure is NOT a census house. A single physical building may contain:
  1. Multiple independent census houses (e.g. multi-story flats, commercial shop on ground floor + residential unit on first floor).
  2. Multiple households residing within separate census houses.
  3. No households (vacant residential, purely non-residential, religious or industrial structure).
- **Required Correction:**
  1. Introduce `census_houses` entity: `id`, `building_id`, `census_house_number`, `use_code`, `listing_state` (`NOT_VISITED`, `LISTED`, `VACANT`, `NON_RESIDENTIAL`, `LOCKED`), `latitude`, `longitude`, `geotag_accuracy_m`, `visited_at`, `locked_attempts`, `created_at`, `updated_at`.
  2. Relink `household_records` to `census_house_id` instead of `house_id` (or retain `building_id` as denormalized reference).
  3. Update SQLite schema with migration to create `offline_census_houses`.
- **Priority:** **CRITICAL**

#### Finding DM-02: Absence of Person Entity (Phase II Demographic Model Missing)
- **File:** `backend/app/models/fieldwork.py`, `mobile/src/core/sqlite/database.ts`
- **Class / Table:** `HouseholdRecord`, `offline_household_records`
- **Current Behavior:** Demographic data is flattened into summary counts (`total_members`, `male_count`, `female_count`, `transgender_count`) and an unstructured `data` JSON column.
- **Problem:** Phase II census enumeration requires individual person records for all household members (relationship, sex, age/DOB, marital status, education, occupation). Collapsing all members into integer counts prevents Phase II enumeration and corrupts member verification.
- **Required Correction:**
  1. Create `persons` table: `id`, `household_id`, `person_number`, `answers` (JSONB), `questionnaire_version`, `review_state`, `created_at`, `updated_at`.
  2. Create `offline_persons` SQLite table with sync queue integration.
- **Priority:** **HIGH**

#### Finding DM-03: Missing Building Field Edits Audit & Mutation Model
- **File:** `backend/app/models/house.py`, `backend/app/services/enumerator_service.py`, `mobile/src/core/fieldworkService.ts`
- **Class / Table:** `House`, `offline_buildings`
- **Current Behavior:** Enumerators can only read downloaded buildings. There is no mechanism to add missing buildings in the field, mark false satellite detections, move inaccurate GPS points, or propose merges/deletions.
- **Problem:** Satellite-derived building footprints frequently have false detections (rock outcrops, tree clusters, roof shadows) or miss newly constructed buildings. Fieldworkers cannot correct GIS geometry.
- **Required Correction:**
  1. Introduce `building_edits` table supporting edit types: `ADD`, `DELETE`, `MERGE`, `MOVE`, `RENUMBER`.
  2. Record: `hlb_id`, `building_id`, `proposed_changes` (JSONB), `requesting_user_id`, `review_status` (`PENDING`, `APPROVED`, `REJECTED`), `reviewer_id`, `reason`.
  3. Add `field_status` on `houses`: `UNVERIFIED`, `CONFIRMED`, `FALSE_DETECTION`, `FIELD_ADDED`.
- **Priority:** **CRITICAL**

---

### 2.2 Fieldwork Resolution & Progress Calculations

#### Finding PR-01: Inaccurate Building Completion Inference & Lack of Listing Closure
- **File:** `backend/app/services/supervisor_service.py` (lines 422-440), `backend/app/services/deputy_service.py`, `mobile/src/core/sqlite/database.ts`
- **Function:** `get_hlb_progress()`, `get_deputy_layout_progress()`, SQLite count queries
- **Current Behavior:** Progress is calculated by counting `HouseFieldworkStatus.status == FieldworkBuildingStatus.COMPLETED`. When an Enumerator enters a household record, the building status is updated to `COMPLETED`.
- **Problem:** A building is not complete simply because one household record exists. The building may contain 3 more census houses that have not been visited. Conversely, a vacant or non-residential building has zero households but IS fieldwork-resolved. Furthermore, false detections must not be counted as completed buildings.
- **Required Correction:**
  1. Introduce an explicit `listing_closed` boolean and `listing_closed_at` timestamp on buildings.
  2. A building is fieldwork-resolved if and only if:
     - `listing_closed == True`
     - Every associated census house is in a resolved state (`LISTED`, `VACANT`, `NON_RESIDENTIAL`)
     - Every required household record is submitted or accounted for.
  3. Create an authoritative `ProgressService` consumed by both Supervisor and Deputy APIs. Eliminate duplicate ad-hoc calculation queries in mobile and multiple backend services.
- **Priority:** **CRITICAL**

#### Finding PR-02: Conflation of Distinct Census Metrics
- **File:** `backend/app/schemas/supervisor_progress.py`, `backend/app/schemas/deputy_progress.py`
- **Class:** `SupervisorHlbProgressResponse`, `DeputyLayoutProgressResponse`
- **Current Behavior:** Only `completed_houses`, `remaining_houses`, `locked_houses` are reported.
- **Problem:** Conflates physical buildings visited, census houses listed, households enumerated, and persons counted into a single vague "houses" number.
- **Required Correction:** Expose distinct, authoritative metrics:
  - `buildings_discovered`, `buildings_visited`, `buildings_confirmed`, `buildings_listing_closed`, `buildings_false_detection`
  - `census_houses_listed`, `census_houses_vacant`, `census_houses_non_residential`, `census_houses_locked`
  - `households_draft`, `households_submitted`, `households_verified`, `households_accepted`
  - `persons_enumerated`
- **Priority:** **HIGH**

---

### 2.3 Verification Workflow & Reassignment Data Safety

#### Finding WF-01: Absence of Supervisor Verification Lifecycle
- **File:** `backend/app/models/fieldwork.py` (lines 21-24), `backend/app/services/sync_service.py`
- **Enum / Table:** `HouseholdRecordStatus`, `household_records`
- **Current Behavior:** Status enum is only `DRAFT` and `COMPLETED`. When synced, records are treated as final.
- **Problem:** Census protocol mandates that Enumerator fieldwork must be reviewed, verified, or returned for correction by the field Supervisor before being accepted as administrative census data. Unverified field entries are currently accepted immediately upon sync.
- **Required Correction:**
  1. Expand `HouseholdRecordStatus` and `CensusHouseStatus`:
     `DRAFT -> SUBMITTED -> SUPERVISOR_VERIFIED -> ACCEPTED`
     With return path: `SUBMITTED -> RETURNED_FOR_CORRECTION -> RESUBMITTED`
  2. Implement supervisor review APIs: `POST /api/v1/supervisor/submissions/{id}/verify`, `POST /api/v1/supervisor/submissions/{id}/return`.
  3. Implement correction comments and rejection reason tracking.
- **Priority:** **CRITICAL**

#### Finding WF-02: Catastrophic Sync Failure on Enumerator Reassignment
- **File:** `backend/app/services/sync_service.py` (lines 147-165)
- **Function:** `_process_single_operation()`
- **Current Behavior:**
  ```python
  assignment = db.query(HlbEnumeratorAssignment).filter(
      HlbEnumeratorAssignment.hlb_id == hlb_id,
      HlbEnumeratorAssignment.enumerator_id == current_user.id,
      HlbEnumeratorAssignment.status == EnumeratorAssignmentStatus.ACTIVE,
  ).first()
  if not assignment:
      return self._record_failure(..., error="Unauthorized: You are not assigned to this HLB.")
  ```
- **Problem:** If Enumerator A collects 50 household records offline, falls sick, and the Supervisor reassigns the HLB to Enumerator B, Enumerator A's assignment status transitions to `CANCELLED`. When Enumerator A's device reconnects and syncs, the backend checks for `status == ACTIVE`, fails every item, and permanently marks the sync operations as `FAILED`! 50 offline interviews are stranded and lost.
- **Required Correction:**
  1. Implement an auditable handover mechanism.
  2. Check if the records were created while Enumerator A held an active assignment epoch/version or allow a supervisor-authorized handover sync.
  3. Support server-side assignment epoch tracking (`assignment_epoch` / `version`).
- **Priority:** **CRITICAL**

#### Finding WF-03: Lack of Change Requests & Dispute Resolution Pipeline
- **File:** `backend/app/models/` (missing model)
- **Class:** Missing `ChangeRequest`
- **Current Behavior:** No mechanism for field supervisors or enumerators to request extra enumerators, report boundary disputes, or request HLB splits/merges.
- **Required Correction:** Create `change_requests` table with fields: `id`, `request_type`, `hlb_id`, `layout_id`, `requesting_user_id`, `assigned_reviewer_id`, `priority`, `status` (`OPEN`, `IN_REVIEW`, `RESOLVED`, `REJECTED`), `description`, `resolution_notes`, `created_at`, `resolved_at`.
- **Priority:** **MEDIUM**

---

### 2.4 Offline Synchronization Engine

#### Finding SY-01: Restricted Sync Entity Types
- **File:** `backend/app/models/fieldwork.py` (lines 53-58), `backend/app/services/sync_service.py` (lines 204-247)
- **Enum:** `SyncEntityType`
- **Current Behavior:** `SyncEntityType` only defines `HOUSEHOLD`, `REVISIT`, `GPS_LOG`, `BUILDING_STATUS`.
- **Problem:** Any client sync operation for buildings, census houses, person records, building edits, boundary alerts, or change requests is rejected with `Unsupported entity type`.
- **Required Correction:** Expand `SyncEntityType` and corresponding handlers to support:
  `BUILDING`, `CENSUS_HOUSE`, `HOUSEHOLD`, `PERSON`, `BUILDING_EDIT`, `GPS_TRACK`, `BOUNDARY_EVENT`, `REVISIT`, `CHANGE_REQUEST`, `REVIEW_UPDATE`.
- **Priority:** **HIGH**

#### Finding SY-02: Device-Isolated Entity Identification
- **File:** `mobile/src/core/sqlite/database.ts`, `backend/app/models/fieldwork.py`
- **Table:** `sync_queue`, `sync_operations`
- **Current Behavior:** Client creates random string IDs (e.g. `hh-${Date.now()}-${random}`) as local IDs. Server stores `idempotency_key` as a single unique string.
- **Problem:** If multiple devices or reinstalls operate, collision risk and lack of deterministic device scoping can cause integrity errors or unrecoverable sync conflicts.
- **Required Correction:** Enforce composite tracking: `device_id` + `local_entity_id` + persistent `idempotency_key` generated once at transaction enqueue time.
- **Priority:** **HIGH**

---

### 2.5 Security & Data Protection

#### Finding SEC-01: Plaintext Local Storage of Confidential Census Data
- **File:** `mobile/src/core/sqlite/database.ts` (lines 334-347)
- **Function:** `getDatabase()`
- **Current Behavior:** Database is opened via `SQLite.openDatabaseSync('enumerator_fieldwork.db')` without encryption.
- **Problem:** All collected household records, resident names, member breakdowns, and phone numbers are stored in unencrypted SQLite files on the Android filesystem. If a field device is lost or compromised, citizen census data is completely exposed.
- **Required Correction:**
  1. Integrate encrypted SQLite storage (`SQLCipher` via `expo-sqlite` or compatible encryption extension).
  2. Generate and store cryptographic encryption keys inside `expo-secure-store` backed by Android Keystore.
  3. Never log raw citizen PII in mobile console or backend audit logs.
- **Priority:** **CRITICAL**

#### Finding SEC-02: Missing Database Migrations (Alembic Chain Incomplete)
- **File:** `backend/migrations/versions/`
- **Current Behavior:** Only 4 migration scripts exist. Tables for `layouts`, `layout_versions`, `houselisting_blocks`, `hlb_houses`, `assignments`, `household_records`, `house_fieldwork_status`, `revisits`, `gps_tracks`, `sync_operations`, and `audit_logs` are generated by `Base.metadata.create_all()` in `backend/app/main.py`.
- **Problem:** In a production PostgreSQL/PostGIS database, runtime `create_all()` cannot perform incremental schema alterations, column renames, or index updates. Violates development rule 19.
- **Required Correction:**
  1. Generate clean Alembic migration capturing all existing schema tables.
  2. Implement sequential migrations for Phase 1 refactoring (`census_houses`, `persons`, `building_edits`, `change_requests`).
- **Priority:** **CRITICAL**

---

### 2.6 Geospatial, Routing & Maps

#### Finding GIS-01: Fake Offline Maps (Online Web Leaflet Dependency)
- **File:** `mobile/src/components/InteractiveMap.tsx` (lines 214, 315, 338-346), `mobile/src/components/HlbSpatialMap.tsx` (lines 458, 462-463)
- **Component:** `InteractiveMap`, `HlbSpatialMap`
- **Current Behavior:** Both map components embed an HTML string in `react-native-webview` loading:
  - `<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js">`
  - `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`
  - `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/...`
- **Problem:** In remote rural or offline conditions (and strictly in Android Airplane mode), the WebView fails to load the Leaflet JavaScript runtime and fails to load map tiles. The map renders blank. This is an online map packaged in a WebView, not an offline map.
- **Required Correction:**
  1. Package Leaflet assets locally or implement MapLibre Native for React Native.
  2. Implement an offline map package manager downloading vector tile packages / MBTiles / PMTiles for the assigned HLB and surrounding ward boundary.
  3. Render boundaries, building points, and GPS tracks natively from local vector data without internet.
- **Priority:** **HIGH**

#### Finding GIS-02: Straight-Line Euclidean TSP Labeled as Road Route
- **File:** `backend/app/gis/route/optimizer.py` (lines 10-150), `backend/app/gis/route/distance.py`
- **Functions:** `solve_tsp_nearest_neighbor()`, `improve_tsp_2opt()`, `optimize_building_route()`
- **Current Behavior:** Computes an $N \times N$ distance matrix using Haversine straight-line coordinates (`haversine_distance_meters`). Solves Nearest Neighbor + 2-Opt local search on straight lines between points.
- **Problem:** Real rural and urban paths cannot cross canals, compound walls, agricultural fields, or non-navigable terrain. A straight-line route produces invalid walking directions and inaccurate distance estimates.
- **Required Correction:**
  1. Load road network graph (OSM road network via GeoPandas / NetworkX).
  2. Project building locations to nearest accessible road edges.
  3. Compute road-network shortest path distances using Dijkstra / contraction hierarchies.
  4. Build a road-aware traversal sequence respecting physical barriers.
- **Priority:** **HIGH**

#### Finding GIS-03: Principal Axis Bisection Disregarding Road-Connected Contiguity
- **File:** `backend/app/gis/hlb/clustering.py` (lines 9-60)
- **Function:** `_recursive_spatial_bisect()`
- **Current Behavior:** Computes spatial covariance angle $\theta$ and sorts points along the principal geometric axis, cutting points at exact target count boundaries.
- **Problem:** Geometric cuts divide houses along straight geometric lines without regard to street connectivity, water bodies, or ravines, creating split street segments and geographically severed blocks.
- **Required Correction:**
  1. Integrate street-connected graph partitioning using NetworkX and road edge contiguity.
  2. Enforce hard barrier non-crossing (rivers, railway lines, major highways).
- **Priority:** **MEDIUM**

---

### 2.7 Multilingual Voice Assistant

#### Finding VO-01: Mocked / Simulated Speech Recognition
- **File:** `mobile/src/core/voice/offlineVoiceService.ts` (lines 100-142, 189-234)
- **Class:** `OfflineVoiceService`
- **Current Behavior:** `startListening()` requests `PermissionsAndroid.PERMISSIONS.RECORD_AUDIO`, starts a 12-second `setTimeout`, and does nothing with the microphone. To produce any output, `processSpeechResult(text)` or `simulateSpeechInput(text)` must be manually supplied with a text string.
- **Problem:** There is no speech-to-text (STT) engine running. The microphone is never connected to an on-device recognition model or native Android `SpeechRecognizer`. The application cannot recognize spoken Tamil or English in the field.
- **Required Correction:**
  1. Integrate a genuine on-device speech recognition engine (e.g. `@react-native-voice/voice` backed by Android on-device offline recognition package, or an embedded offline engine).
  2. Implement interactive question-by-question voice workflow: TTS prompt -> Mic capture -> STT text -> Domain slot extraction -> Spoken/visual read-back confirmation -> Explicit save.
- **Priority:** **HIGH**

---

### 2.8 Questionnaire Architecture

#### Finding QN-01: Monolithic Hard-Coded Form Variables
- **File:** `mobile/src/features/enumerator/HouseholdFormScreen.tsx` (lines 46-60)
- **Component:** `HouseholdFormScreen`
- **Current Behavior:** Questions (`headName`, `totalMembers`, `maleCount`, `femaleCount`, `transgenderCount`, `ownershipStatus`, `drinkingWater`, `lightingSource`, `latrineFacility`) are hard-coded React state variables.
- **Problem:** Questionnaire definitions cannot be updated, versioned, or adjusted per government gazette notifications without rewriting React Native component code. Phase I and Phase II fields are mingled.
- **Required Correction:**
  1. Separate questionnaire definitions into versioned JSON schemas (Phase I Houselisting vs Phase II Population Enumeration).
  2. Dynamic form generator rendering fields with stable Question IDs (`Q1_BUILDING_USE`, `Q2_ROOF_TYPE`, `Q3_WALL_MATERIAL`, `Q4_WATER_SOURCE`).
- **Priority:** **HIGH**

---

## 3. Findings Summary & Priority Matrix

| ID | Domain Area | File / Component | Severity | Summary |
| :--- | :--- | :--- | :--- | :--- |
| **DM-01** | Domain Model | `fieldwork.py`, `database.ts` | **CRITICAL** | Building footprint is conflated with census house; missing `CensusHouse` entity. |
| **DM-02** | Domain Model | `fieldwork.py`, `database.ts` | **HIGH** | Phase II person-level entity missing; demographics collapsed to counts. |
| **DM-03** | Domain Model | `house.py`, `enumerator_service.py` | **CRITICAL** | No building field operations (`ADD`, `CONFIRM`, `FALSE_DETECTION`, `MOVE`, `MERGE`). |
| **PR-01** | Progress & Fieldwork | `supervisor_service.py`, `deputy_service.py` | **CRITICAL** | Inaccurate progress; no explicit `listing_closed` flag on buildings. |
| **PR-02** | Progress & Fieldwork | `supervisor_progress.py`, `deputy_progress.py` | **HIGH** | Conflation of building visits, census house listing, and household surveys. |
| **WF-01** | Workflow | `fieldwork.py`, `sync_service.py` | **CRITICAL** | Missing supervisor verification lifecycle (`SUBMITTED -> VERIFIED -> ACCEPTED`). |
| **WF-02** | Workflow | `sync_service.py` | **CRITICAL** | Sync fails permanently if Enumerator was reassigned before uploading offline data. |
| **WF-03** | Workflow | Backend / Mobile | **MEDIUM** | Missing change requests and supervisor dispute messaging pipeline. |
| **SY-01** | Offline Sync | `fieldwork.py`, `sync_service.py` | **HIGH** | Sync entity enum omits buildings, census houses, persons, edits, and reviews. |
| **SY-02** | Offline Sync | `database.ts`, `sync_service.py` | **HIGH** | Lack of compound device-isolated entity IDs `(device_id, local_id)`. |
| **SEC-01** | Security | `database.ts` | **CRITICAL** | Mobile SQLite database stores confidential citizen demographics in plaintext. |
| **SEC-02** | Database & Migration | `migrations/versions/` | **CRITICAL** | Missing Alembic migrations; core tables generated via unmanaged `create_all()`. |
| **GIS-01** | GIS & Mapping | `InteractiveMap.tsx`, `HlbSpatialMap.tsx` | **HIGH** | Map uses online Leaflet and tile servers inside WebView; fails in airplane mode. |
| **GIS-02** | Routing | `optimizer.py`, `distance.py` | **HIGH** | Route optimizer is straight-line Euclidean TSP, not road-network aware. |
| **GIS-03** | HLB Partitioning | `clustering.py` | **MEDIUM** | Partitioning uses principal axis bisection without road network contiguity. |
| **VO-01** | Voice Assistant | `offlineVoiceService.ts` | **HIGH** | Microphone is not connected to any speech recognition engine; mocked STT. |
| **QN-01** | Questionnaire | `HouseholdFormScreen.tsx` | **HIGH** | Hard-coded questions in UI state; no Phase I/II schema separation or question IDs. |

---

## 4. Corrected Domain Hierarchy & Schema Specification

### 4.1 Authoritative Entity Relationship Model

```text
Administrative Area (Village / Ward)
         ↓
       Layout
         ↓
Houselisting Block (HLB)
         ↓
Building / Physical Structure (Footprint / Marker)
  ├── listing_closed: BOOLEAN
  ├── field_status: UNVERIFIED | CONFIRMED | FALSE_DETECTION | FIELD_ADDED
  │
  ├── Building Edits (Audit & Supervisor Verification)
  │
  └── Census Houses (1 to N per Building)
        ├── use_code: RESIDENTIAL | RESIDENTIAL_CUM_COMMERCIAL | COMMERCIAL | VACANT | OTHER
        ├── listing_state: NOT_VISITED | LISTED | VACANT | NON_RESIDENTIAL | LOCKED
        ├── locked_attempts: INTEGER
        │
        └── Households (0 to N per Census House)
              ├── household_number: VARCHAR
              ├── questionnaire_version: VARCHAR
              ├── answers: JSONB (Indexed by Question ID)
              ├── review_state: DRAFT | SUBMITTED | SUPERVISOR_VERIFIED | ACCEPTED | RETURNED
              │
              └── Persons (Phase II: 1 to N per Household)
                    ├── person_number: INTEGER
                    ├── questionnaire_version: VARCHAR
                    ├── answers: JSONB
                    └── review_state: DRAFT | SUBMITTED | SUPERVISOR_VERIFIED | ACCEPTED
```

---

## 5. Phased Migration & Refactoring Roadmap

To preserve the 341 passing baseline tests without breaking ongoing development, refactoring must proceed in controlled, dependency-ordered phases:

### Phase 1: Domain Model Realignment & Foundation Schema
1. Generate baseline Alembic migration capturing existing unmanaged tables.
2. Implement new database models:
   - `CensusHouse` (`census_houses`)
   - `Person` (`persons`)
   - `BuildingEdit` (`building_edits`)
   - `ChangeRequest` (`change_requests`)
3. Update `House` model with `listing_closed`, `listing_closed_at`, and `field_status`.
4. Update `HouseholdRecord` with `census_house_id` and review lifecycle statuses (`DRAFT`, `SUBMITTED`, `SUPERVISOR_VERIFIED`, `ACCEPTED`, `RETURNED_FOR_CORRECTION`).
5. Write Alembic migration script for Phase 1 entities.
6. Update mobile SQLite schema migration (`schema_versions` V4) to add `offline_census_houses`, `offline_persons`, and `offline_building_edits`.
7. Add unit and integration tests for multi-census-house buildings, vacant structures, and person records.

### Phase 2: Authoritative Progress Calculation & Building Field Operations
1. Build centralized backend `ProgressCalculationService` computing consistent metrics across all roles.
2. Deprecate fragmented progress counting queries in `supervisor_service.py` and `deputy_service.py`.
3. Implement Building Field Operations API:
   - Add new building in field
   - Confirm detected building
   - Mark false detection
   - Move building coordinate
   - Close building listing
4. Update mobile `BuildingDetailScreen` with Census House management, listing closure, and building correction modals.
5. Expand Sync Service entity types to handle `BUILDING`, `CENSUS_HOUSE`, `PERSON`, `BUILDING_EDIT`.

### Phase 3: Supervisor Verification, Reassignment Handover & Change Requests
1. Implement Supervisor Verification APIs (`/verify`, `/return`, `/submissions`).
2. Implement Reassignment Handover Service ensuring un-synchronized offline records from previous assignments remain valid and synchronizable.
3. Implement `ChangeRequest` API and supervisor/deputy handling workflows.
4. Add mobile screens for Supervisor Review and Change Requests.

### Phase 4: Local Encryption & Sync Hardening
1. Implement encrypted SQLite storage using SQLCipher key stored in Android Keystore / `expo-secure-store`.
2. Secure PII redaction in logging and error responses.
3. Harden sync idempotency with compound `(device_id, local_entity_id)` constraints.

### Phase 5: Genuine Offline Mapping Engine
1. Implement local tile caching and evaluation of MapLibre Native for vector tiles / PMTiles.
2. Bundle offline base assets to guarantee airplane-mode map rendering.

### Phase 6: Road-Network Routing & GPS Coverage Analytics
1. Replace Euclidean TSP with NetworkX road-network shortest path routing.
2. Implement authentic GPS breadcrumb coverage analytics and missed-area detection.

### Phase 7: Real Multilingual Speech Recognition
1. Integrate native on-device Android SpeechRecognizer / offline engine.
2. Implement question-by-question voice interaction with Tamil/English read-back confirmation.

### Phase 8: Standardized Questionnaire Architecture
1. Decouple questionnaire definitions into versioned Phase I and Phase II schemas.
2. Dynamic form generator with stable Question IDs.

---

## 4. Implementation Accomplishments & Verification Report

### 4.1 Completed Refactoring Milestones
1. **Domain Hierarchy Realignment:**
   - Database entities created and verified:
     $$\text{Administrative Area} \rightarrow \text{Layout} \rightarrow \text{HLB} \rightarrow \text{Building} \rightarrow \text{Census House} \rightarrow \text{Household} \rightarrow \text{Person (Phase II)}$$
   - Alembic migration `g3c4d5e6f7a8` executed and verified on backend.
   - Mobile SQLite V4 migration applied with `offline_census_houses`, `offline_persons`, and `offline_building_edits` tables.
2. **Authoritative Backend Progress Calculation Service:**
   - Centralized authoritative progress logic in `backend/app/services/progress_service.py`.
   - Replaced fragmented counting queries across `supervisor_service.py` and `deputy_service.py`.
   - Strict census fieldwork resolution: Building resolved $\iff$ listing explicitly closed $\land$ all census houses resolved (`LISTED`, `VACANT`, `NON_RESIDENTIAL`) $\land$ required households submitted.
3. **Reassignment-Safe Sync Engine:**
   - Implemented historical assignment epoch validation in `backend/app/services/sync_service.py` ensuring un-synchronized offline fieldwork collected prior to reassignment is never rejected.
   - Added sync processors for `CENSUS_HOUSE`, `PERSON`, `BUILDING_EDIT`, `BUILDING_STATUS`, and `HOUSEHOLD`.
4. **Supervisor & Deputy Fieldwork Management APIs & UI:**
   - Supervisor verification API (`/submissions`, `/verify`, `/return`) with audit logging.
   - Building edits review API (`/building-edits`, `/review`) with footprint mutation.
   - Change request API (`/change-requests`, `/resolve`) for HLB splitting, merging, and enumerator reassignments.
   - Mobile `SupervisorVerificationScreen` and `DeputyChangeRequestsScreen` implemented and integrated.
5. **Mobile Fieldwork Realignment:**
   - `BuildingDetailScreen`: structure field status (`UNVERIFIED`, `CONFIRMED`, `FALSE_DETECTION`, `FIELD_ADDED`), Census House listing, "Add Census House" modal, building edit requests, and "Close Listing" validation.
   - `HouseholdFormScreen`: links households to Census Houses and provides Phase II Person Roster demographic entry.
6. **Road-Network Graph Routing:**
   - Integrated NetworkX spatial road graph with Dijkstra shortest path routing in `backend/app/gis/route/optimizer.py` and `distance.py`.

### 4.2 Automated Verification Results
- **Backend Test Suites (Pytest):**
  - `tests/test_domain_hierarchy.py`: 6 passed
  - `tests/test_progress_service.py`: 1 passed (all 8 domain scenarios)
  - `tests/test_sync.py`: 8 passed
  - `tests/test_domain_sync_and_operations.py`: 3 passed
  - `tests/test_supervisor_verification_and_change_requests.py`: 3 passed
  - `tests/test_road_network_routing.py`: 2 passed
  - Total: **23 passed in 40.07s**
- **Mobile Test Suites (Jest):**
  - 20 test suites passed (including new `SupervisorVerificationFlow.test.tsx`)
  - Total: **192 tests passed in 14.9s**
