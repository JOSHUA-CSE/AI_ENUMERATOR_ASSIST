# AI-Enumerator Assistant — Technical Requirement Document

## 1. Technical Goal

Build an **Android-first mobile application** with a shared backend and GIS/AI services to support census fieldwork.

The technical system must support the complete workflow:

```text
Village / Ward
      ↓
    Layout
      ↓
AI-assisted Block Generation
      ↓
Blocks of approximately 250 Houses/Buildings
      ↓
Supervisor Assignment
      ↓
Number of Blocks = Number of Enumerators Required
      ↓
One Enumerator → One Block
      ↓
Block-level Fieldwork
      ↓
GPS + House Coverage
      ↓
Offline Synchronization
      ↓
Supervisor Monitoring
```

The system must keep the three roles separate:

```text
DEPUTY TAHSILDAR
       ↓
Creates and approves layouts/blocks
       ↓
SUPERVISOR
       ↓
Manages blocks and Enumerators
       ↓
ENUMERATOR
       ↓
Works on one assigned block
```

The application is intended to support field staff and should not replace human approval for important operations.

---

# 2. Recommended Technology Stack

## 2.1 Mobile Application

### React Native with Expo + TypeScript

The mobile application is built with **React Native with Expo (Expo React Native)** and **TypeScript**.

Recommended mobile architecture:

```text
React Native with Expo
    │
    ├── React Navigation (Role-based Navigation)
    │     ├── Role Resolver
    │     ├── Deputy Navigator
    │     ├── Supervisor Navigator
    │     └── Enumerator Navigator
    │
    ├── Feature Modules (Authentication, Deputy, Supervisor, Enumerator)
    │
    ├── Zustand (Client State Management)
    │
    ├── API Client (Fetch / Axios with JWT interceptor)
    │
    ├── expo-sqlite (Offline Local Database & Sync Queue)
    │
    ├── expo-secure-store (Encrypted Token & Session Storage)
    │
    ├── expo-location (GPS, Accuracy & Boundary Checking)
    │
    ├── react-native-maps (Primary MVP Map Rendering)
    │
    └── Testing (Jest + React Native Testing Library)
```

### Core Libraries & Their Roles

1. **Expo (`expo`)**:
   - Acts as the primary mobile application framework and runtime.
   - Provides standardized SDK modules, unified configuration (`app.json`), fast development server (`npx expo start`), and modern asset pipeline.

2. **React Navigation (`@react-navigation/native`, `@react-navigation/native-stack`, `@react-navigation/bottom-tabs`)**:
   - Responsible for role-based navigation and screen routing.
   - Architecture:
     ```text
     Authenticated User
             ↓
        Role Resolver
             ↓
     ┌─────────────────┬────────────────────┬─────────────────────┐
     │ DeputyNavigator │ SupervisorNavigator │ EnumeratorNavigator │
     └─────────────────┴────────────────────┴─────────────────────┘
     ```
   - React Navigation manages UI flow; backend FastAPI remains the authoritative security boundary.

3. **Zustand (`zustand`)**:
   - Lightweight, hook-based state management.
   - Manages active user session, assigned HLB state, UI filters, network state, and sync progress without boilerplate.

4. **`expo-sqlite`**:
   - Embedded local SQL database providing offline-first persistence.
   - Stores downloaded HLB boundaries, houses, buildings, questionnaire records, revisits, and queued synchronization operations.
   - Offline flow: `React Native UI -> Repository -> expo-sqlite -> Local Data -> Sync Queue -> FastAPI`.

5. **`expo-secure-store`**:
   - Encrypted, hardware-backed key-value storage (Android Keystore / iOS Keychain).
   - Used strictly for authentication JWTs, refresh tokens, and session credentials.
   - **Rule:** Plain `AsyncStorage` MUST NOT be used for sensitive authentication tokens.

6. **`expo-location`**:
   - Native location API managing GPS services.
   - Supports:
     * Current device location retrieval
     * Foreground & background location permissions
     * GPS accuracy thresholds
     * Point-in-polygon HLB boundary checks
     * GPS tracking breadcrumbs
     * Offline GPS logging for supervisor audit

7. **`react-native-maps`**:
   - Primary MVP map rendering library.
   - Renders OpenStreetMap / Google Maps base tiles, HLB boundary polygons, house/building markers, Enumerator current position, and route visualization.
   - **Important:** The FastAPI backend (GeoPandas + Shapely) remains responsible for heavy GIS computations (clipping, spatial clustering, AI block generation). The mobile application renders boundaries and performs lightweight point-in-polygon checks without heavy client GIS processing.
   - *(Note: MapLibre remains documented as an optional alternative for advanced custom offline vector tile rendering if future requirements exceed `react-native-maps`).*

8. **Jest & React Native Testing Library (`@testing-library/react-native`)**:
   - Standard unit and component test suite covering authentication, RBAC navigation, form validation, offline store transactions, and sync queue logic.

---

### Expo Go vs Expo Development Build

The project embraces a two-tier Expo development strategy:

```text
┌───────────────────────────────────────────────────────────────┐
│                           Expo Go                             │
│  - Instant preview via QR code                                │
│  - No native compilation on developer PC                      │
│  - Works for Login, RBAC, Forms, expo-sqlite,                 │
│    expo-secure-store, expo-location                           │
└───────────────────────────────┬───────────────────────────────┘
                                │
                                ▼ (when native customization needed)
┌───────────────────────────────────────────────────────────────┐
│                 Expo Development Build                        │
│  - Built via `npx expo run:android` / `eas build`             │
│  - Embeds custom native modules / native map configs          │
│  - Retains full Expo tooling, Fast Refresh, & JS workflow     │
└───────────────────────────────────────────────────────────────┘
```

1. **Expo Go (Fastest Mobile Preview)**:
   - Prioritized for getting the login and role-based dashboard screens running on a physical Android device immediately.
   - Developers install the **Expo Go** app from Google Play Store, start `npx expo start`, scan the QR code, and preview the app over Wi-Fi.
   - **Supported in Expo Go:** Phase 1 Authentication, RBAC navigation, `expo-secure-store`, `expo-sqlite`, `expo-location`, forms, session management.

2. **Expo Development Build (`expo-dev-client`)**:
   - Used when a package or feature requires custom native Android configuration (such as custom native map keys or custom native background services) unavailable in standard Expo Go.
   - **Crucial Rule:** If native customization is required, create an Expo Development Build. **Do NOT abandon Expo** or revert to unmanaged workflows.

### Android-first requirements

The Expo React Native application must support:

* Android GPS/location permissions via `expo-location`
* Background/foreground location behavior as permitted by Android
* Offline operation with `expo-sqlite`
* Secure local credential storage via `expo-secure-store`
* Map rendering via `react-native-maps`
* Camera and microphone access where required
* Network state detection
* Large touch targets and low-end Android performance

The mobile application must not contain backend database credentials or trusted server secrets.

---

## 2.2 Backend

Use:

* Python
* FastAPI
* REST API

FastAPI will handle:

* Authentication
* User roles
* Administrative areas
* Layouts
* Blocks
* Houses/buildings
* Supervisor assignments
* Enumerator assignments
* Household records
* GPS data
* Coverage calculations
* Synchronization
* AI/GIS services

---

## 2.3 Database

Use:

**PostgreSQL + PostGIS**

PostGIS is important because the application needs to manage:

* Village/ward boundaries
* Layout boundaries
* Block boundaries
* House/building locations
* Roads
* Enumerator GPS locations
* GPS tracks
* Spatial queries
* Boundary-crossing detection
* Coverage calculations

---

## 2.4 AI/GIS & Building Detection Architecture

Recommended Python technologies:

* GeoPandas & Shapely (Geometry manipulation, boundary clipping, spatial validation)
* NetworkX (Graph-based routing optimization)
* scikit-learn (Spatial clustering & density analysis where required)

### Geographic Pipeline: Satellite-Assisted Building Estimation

The system implements a server-side geographic pipeline:

```text
Satellite Imagery (Esri World Imagery / Configurable Provider)
        ↓
Building Detection Service (Spatial Extractor / Pre-trained / Footprint Provider)
        ↓
Building Footprints / Centroids (GeoJSON / WKB, SRID 4326)
        ↓
PostGIS (Spatial storage & boundary-filtered indexing)
        ↓
FastAPI (REST APIs with caching & spatial aggregation)
        ↓
React Native Map (Zoom-dependent visualization)
```

### Key Technical Principles:
1. **Server-Side Processing**: Heavy image processing, raster tiling, building footprint extraction, and machine learning inference are performed **exclusively on the backend/GIS layer**. The mobile Android client strictly visualizes the processed results (boundaries, heatmaps, cluster counts, markers) without running heavy on-device ML models.
2. **Imagery Source Abstraction**: The system must not hard-code a single commercial satellite provider. The imagery layer is abstracted through a configurable provider interface supporting Esri World Imagery, OpenStreetMap, Mapbox, or standardized XYZ/WMS tile endpoints.
3. **Imagery & Detection Metadata**: Each detected structure record preserves:
   - `source_type`: `SATELLITE_DETECTED`, `MANUAL`, `GOVERNMENT_IMPORT`, `FIELD_VERIFIED`
   - `detection_confidence`: Confidence score (0.0 to 1.0) where available from the detection model
   - `detected_at`: Timestamp of detection execution
   - `imagery_source`: Identifier of imagery provider/satellite sensor
   - `imagery_date`: Capture date or acquisition year of the underlying imagery
4. **Spatial Boundary Filtering**: All building detection and estimation queries must be strictly filtered by the selected village/ward administrative boundary polygon in PostGIS (`ST_Contains` / `ST_Intersects`).

---

## 2.5 Maps & Mobile Visualization

Recommended:

* Leaflet / react-native-maps for interactive mobile map rendering
* High-resolution satellite tile base layer (default) with toggle to street map
* PostGIS for server-side spatial indexing (`GIST`) and aggregation

The map system should support:

* Administrative boundaries (high-contrast polygons with semi-transparent fills)
* **Zoom-Dependent Visualization**:
  - **Far Zoom (< 14)**: Village boundary polygon only + centered name badge (no marker clutter)
  - **Medium Zoom (14–16)**: Multi-tier building density heatmap (Green $\rightarrow$ Yellow $\rightarrow$ Orange $\rightarrow$ Red)
  - **Closer Zoom (16–18)**: Clustered building markers with counts (tap to zoom into cluster)
  - **High Zoom (> 18)**: Individual detected building footprint markers + detail popups (ID, Building Ref, Coordinates)
* Top layer controls (`Boundary`, `Buildings`, `Layers`)
* Floating map tools (Location, Zoom In/Out, Fit Boundary)
* Bottom information card with estimated building count, area ($km^2$), and status

---

# 3. System Architecture

The overall architecture should be:

```text
               React Native with Expo Mobile App
                               |
                        HTTPS / REST API
                               |
                            FastAPI
                               |
              +----------------+----------------+
              |                |                |
         PostgreSQL         GIS Engine      Auth Service
           + PostGIS             |
              |             AI Block Engine
              |                |
              |        +-------+-------+
              |        |       |       |
              |      Houses  Roads  Boundaries
              |
              +-------------------------------+
```

The Enumerator mobile application also contains a local offline layer:

```text
             React Native with Expo
                        |
                 Local Repository
                        |
                   expo-sqlite
                        |
                Offline Field Work
                        |
                 Local Sync Queue
                        |
                Internet Available
                        |
                     FastAPI
                        |
                   PostgreSQL
```

---

# 4. Role-Based Architecture

The backend must enforce permissions based on the user's role.

Roles:

```text
DEPUTY_TAHSILDAR
SUPERVISOR
ENUMERATOR
```

## 4.1 Deputy Tahsildar

Can:

* Select village/ward
* Create layout
* View houses/buildings
* Generate blocks
* Review blocks
* Edit blocks
* Split blocks
* Merge blocks
* Approve layout
* Assign layout to Supervisor
* View overall progress

## 4.2 Supervisor

Can:

* View assigned layouts
* View blocks
* View houses/buildings
* View block counts
* View required Enumerator count
* Assign Enumerators to blocks
* Monitor Enumerators
* View progress
* View GPS coverage
* View boundary-crossing events
* Review field completion

## 4.3 Enumerator

Can:

* View assigned layout
* View assigned block
* Download block for offline use
* View assigned houses/buildings
* Navigate using optimized route
* Record household information
* Mark houses/buildings
* Use voice assistant
* Record GPS
* Receive block-boundary warnings
* Work offline
* Synchronize data

---

# 5. Core Geographic Hierarchy

The system must maintain the following hierarchy:

```text
Administrative Area
       ↓
Village / Ward
       ↓
Layout
       ↓
Blocks
       ↓
Houses / Buildings
```

The important relationship is:

```text
One Village/Ward
       ↓
One Layout
       ↓
Multiple Blocks
       ↓
Each Block ≈ 250 Houses/Buildings
```

Example:

```text
Village A
Total Houses = 1,000

Layout: Village A

Block B001 → 250
Block B002 → 250
Block B003 → 250
Block B004 → 250
```

The actual count may not be exactly 250 because geographic continuity and practical boundaries must also be considered.

---

# 6. Layout and Block Generation

## 6.1 Input

The AI/GIS engine receives:

```text
Village/Ward
Administrative boundary
House/building locations
Road network
Target block size
```

Default:

```text
Target block size = 250 houses/buildings
```

The target must be configurable.

It must **not** be hard-coded into the system as an unchangeable value.

---

## 6.2 Processing

The system should:

1. Load the selected village/ward.
2. Load its administrative boundary.
3. Load houses/buildings.
4. Load road/network information.
5. Remove or flag invalid geographic data.
6. Group nearby houses/buildings.
7. Consider roads and geographic separation.
8. Create candidate blocks.
9. Try to keep each block close to the target count.
10. Check geographic continuity.
11. Check whether all houses are assigned.
12. Check whether any house is assigned twice.
13. Check block boundaries.
14. Rank possible block divisions.
15. Display the proposed result to the Deputy Tahsildar.

---

## 6.3 Output

The AI/GIS engine should return:

```text
Layout ID
Number of blocks
Block boundaries
House/building membership
House/building count per block
Validation warnings
Generation information
```

Example:

```text
LAYOUT: Village A

Total Houses/Buildings: 1,240

B001 → 248
B002 → 252
B003 → 251
B004 → 245
B005 → 244

Total Blocks: 5
```

---

## 6.4 Block Validation

Every generated block should be checked for:

### House Count

```text
Block Count ≈ Target
```

### Geographic Continuity

The block should preferably form one connected geographic area.

### Boundary

The block must remain inside the selected village/ward layout.

### House Assignment

Every house/building should belong to exactly one active block.

### Duplicate Assignment

A house/building must not belong to multiple active blocks.

### Unassigned Houses

The system must identify houses/buildings that were not assigned to any block.

### Practical Boundaries

Roads and other geographic features should be considered when creating boundaries.

---

# 7. Layout Approval

AI-generated blocks are only proposals.

The workflow is:

```text
Generate
   ↓
Review
   ↓
Edit if Required
   ↓
Validate
   ↓
Approve
```

Only an authorized Deputy Tahsildar can approve the layout.

Once approved:

```text
Generated Version
       ↓
Approved Version
```

The approved version should be stored separately so that later AI generation does not silently change an approved layout.

---

# 8. Supervisor Assignment

After the layout is approved:

```text
Approved Layout
      ↓
Identify Responsible Supervisor
      ↓
Assign Layout
      ↓
Supervisor receives complete layout
```

The Supervisor should be able to see:

```text
Village/Ward
Layout ID
Total Blocks
Total Houses/Buildings
Required Enumerators
Assignment Status
```

Example:

```text
Layout: Village A

Total Blocks:          6
Total Houses:       1,480
Enumerators Required:  6
Enumerators Assigned:  6

Status: Assignment Complete
```

---

# 9. Enumerator Assignment

The number of Enumerators required is directly related to the number of blocks.

```text
Number of Blocks
        =
Number of Enumerators Required
```

Example:

```text
6 Blocks
   ↓
6 Enumerators Required
```

Each block should have one primary Enumerator.

```text
B001 → E001
B002 → E002
B003 → E003
B004 → E004
B005 → E005
B006 → E006
```

The Supervisor is responsible for assigning the Enumerators.

---

## 9.1 Assignment Validation

The backend must validate:

```text
Blocks = Required Enumerators
```

The Supervisor should see:

```text
Total Blocks:             6
Required Enumerators:     6
Assigned Enumerators:     5

⚠ 1 Enumerator Required
```

The system should not mark the assignment as complete until all blocks have an Enumerator, unless an authorized exception process is introduced later.

---

# 10. API Requirements

## 10.1 Authentication

```text
POST /api/auth/login
POST /api/auth/refresh
POST /api/auth/logout
GET  /api/auth/me
```

---

## 10.2 Administrative Areas

```text
GET /api/areas
GET /api/areas/{id}
GET /api/areas/{id}/houses
GET /api/areas/{id}/map
```

---

## 10.3 Layouts

```text
POST /api/layouts
GET  /api/layouts
GET  /api/layouts/{id}
PUT  /api/layouts/{id}
POST /api/layouts/{id}/generate
POST /api/layouts/{id}/approve
```

---

## 10.4 Blocks

```text
GET  /api/layouts/{id}/blocks
GET  /api/blocks/{id}
POST /api/layouts/{id}/blocks/generate
PUT  /api/blocks/{id}
POST /api/blocks/{id}/split
POST /api/blocks/{id}/merge
POST /api/blocks/{id}/validate
```

---

## 10.5 Supervisor Assignment

```text
POST /api/layouts/{id}/assign-supervisor
GET  /api/layouts/{id}/supervisor
```

---

## 10.6 Enumerator Assignment

```text
POST /api/blocks/{id}/assign-enumerator
GET  /api/layouts/{id}/enumerators
GET  /api/blocks/{id}/enumerator
POST /api/blocks/{id}/reassign-enumerator
```

---

## 10.7 Houses / Buildings

```text
GET  /api/blocks/{id}/houses
GET  /api/houses/{id}
PUT  /api/houses/{id}/status
POST /api/houses/{id}/household
```

---

## 10.8 Route

```text
POST /api/blocks/{id}/route
GET  /api/blocks/{id}/route
```

The route API must verify that the requesting Enumerator is assigned to the block.

---

## 10.9 GPS

```text
POST /api/gps/batch
GET  /api/blocks/{id}/gps
GET  /api/blocks/{id}/coverage
GET  /api/blocks/{id}/boundary-events
```

---

## 10.10 Synchronization

```text
POST /api/sync/upload
GET  /api/sync/changes
```

---

# 11. Route Optimization

Route optimization operates at the **block level**.

The system must never treat the entire village/ward layout as the Enumerator's route area.

## Input

```text
Enumerator
Assigned Block
Houses/Buildings in Block
House Coordinates
Road Network
Current GPS Location
Completed Houses
Locked Houses
```

## Constraints

* Route must remain within the assigned block.
* Only houses/buildings belonging to that block should be included.
* Completed houses can be excluded.
* Locked houses can be moved to the revisit list.
* Remaining houses should be prioritized.
* Road/network information should be considered.
* Route should minimize unnecessary travel.

Example:

```text
Enumerator E003
       ↓
Assigned Block B003
       ↓
Get houses in B003
       ↓
Remove completed houses
       ↓
Handle locked houses
       ↓
Generate route
       ↓
Display route
```

A graph-based approach using NetworkX can be used initially.

---

# 12. GPS and Boundary Monitoring

GPS is used for:

* Enumerator location
* Field movement
* Coverage indication
* Boundary monitoring
* Supervisor monitoring

## 12.1 GPS Data

Store:

```text
Enumerator ID
Layout ID
Block ID
Latitude
Longitude
Accuracy
Timestamp
```

---

## 12.2 Block Boundary Check

The Enumerator's GPS position should be compared with the assigned block polygon.

```text
GPS Location
      ↓
Point-in-Polygon Check
      ↓
Inside Block?
   /       \
 YES        NO
 ↓           ↓
Continue    Warning
             ↓
       Record Event
             ↓
      Notify/Display
        Supervisor
```

Example:

```text
⚠ BLOCK B003

You are outside your assigned block.

Please return to your assigned area.
```

The event should contain:

```text
Enumerator ID
Block ID
Location
Timestamp
Boundary event type
```

---

# 13. GPS Coverage

Coverage calculation should combine:

* Block boundary
* Expected houses/buildings
* Completed houses
* GPS movement
* GPS accuracy

The system should distinguish between:

```text
House Completion
GPS Movement
Possible Uncovered Area
Boundary Crossing
```

Example:

```text
BLOCK B003

Total Houses:       247
Completed:          225
Remaining:           22
Locked:               5

House Coverage:      91%
GPS Coverage:        94%

Possible missed area detected
```

GPS coverage is only an indicator.

GPS movement must **not** automatically be treated as proof that a household was interviewed.

---

# 14. Offline Architecture

The Enumerator application must support core fieldwork without internet.

The Enumerator should download the assigned block before starting fieldwork.

Local data should include:

```text
Assigned Layout
Assigned Block
Block Boundary
House/Building List
House Status
Household Records
Revisit Records
GPS Points
Route Data
Pending Synchronization Actions
```

The Enumerator should not need continuous internet access to:

* Open the assigned block
* View houses
* Record household information
* Mark a house completed
* Mark a house locked
* Create a revisit
* Record GPS
* View the previously downloaded route

---

# 15. Local Database

`expo-sqlite` must be used for local offline storage.

The offline architecture is structured as:

```text
React Native UI
      ↓
Repository
      ↓
expo-sqlite
      ↓
Local Data
      ↓
Sync Queue
      ↓
FastAPI
```

Important local entities:

```text
users
layouts
blocks
houses
household_records
revisits
gps_tracks
routes
sync_operations
```

Each local record should have a synchronization state where applicable:

```text
PENDING
SYNCED
FAILED
CONFLICT
```

---

# 16. Synchronization

When internet connectivity returns:

```text
Internet Available
       ↓
Authenticate
       ↓
Read Pending Operations
       ↓
Upload Batch
       ↓
Server Validation
       ↓
Success / Failure
       ↓
Update Local Status
```

## Synchronization Rules

1. Authenticate the user.
2. Collect pending local operations.
3. Upload operations in batches.
4. Server validates the user and block permissions.
5. Server validates the data.
6. Successful operations become `SYNCED`.
7. Temporary failures remain retryable.
8. Conflicts are marked `CONFLICT`.
9. The user should be informed about unresolved conflicts.

Synchronization must be **idempotent** so that retrying the same operation does not create duplicate records.

Do not delete local data immediately after a failed synchronization.

---

# 17. Offline Boundary Monitoring

The block boundary should be downloaded to the Enumerator's device.

This allows basic boundary checking even without internet.

```text
GPS
 ↓
Local Block Polygon
 ↓
Point-in-Polygon
 ↓
Inside / Outside
```

If outside:

```text
Show local warning
Record boundary event locally
Add event to sync queue
```

When internet returns:

```text
Local Boundary Event
       ↓
Server Synchronization
       ↓
Supervisor Dashboard
```

---

# 18. Offline Voice Assistant

The voice assistant should support the Enumerator during offline fieldwork.

Initial languages:

```text
Tamil
English
```

Pipeline:

```text
Microphone
    ↓
Offline Speech Recognition
    ↓
Text
    ↓
Field Extraction
    ↓
Structured Data
    ↓
Enumerator Confirmation
    ↓
Local Database
```

Example:

```text
Voice:
"இந்த வீட்டில் நான்கு பேர் இருக்கிறார்கள்."

↓

Structured Data:

household_members = 4
```

The system must show the extracted information before saving important fields.

Example:

```text
Detected:

Household Members: 4

[Confirm] [Edit]
```

Uncertain AI results must not be silently saved.

---

# 19. Household Data

The household questionnaire should be implemented separately from the core technical architecture.

The backend should support structured household data using a flexible format such as JSONB where appropriate.

Example:

```json
{
  "household_members": 4,
  "ownership": "RENTED"
}
```

The exact fields should be added only after the required official questionnaire/data structure is defined.

---

# 20. House / Building Status

The system should support at least:

```text
PENDING
COMPLETED
LOCKED
REVISIT
```

Typical flow:

```text
PENDING
   |
   +----> COMPLETED
   |
   +----> LOCKED
              |
              ↓
           REVISIT
              |
              ↓
          COMPLETED
```

The system should maintain a history of important status changes where required.

---

# 21. Security Requirements

The backend must enforce security.

Requirements:

* HTTPS
* Secure password hashing
* JWT/session protection
* Role-based authorization
* Input validation
* Authentication rate limiting
* Secure mobile token storage
* Minimal personal data exposure
* Audit logs
* Database access control
* No database credentials inside the mobile application

Most importantly:

**Role permissions must be enforced by the backend, not only by the React Native UI.**

For example, hiding a Deputy Tahsildar screen from an Enumerator is not sufficient. The API must also reject unauthorized requests.

---

# 22. Authorization Rules

## Deputy Tahsildar

Can access:

```text
Village/Ward
Layouts
Blocks
Houses
Layout Generation
Block Generation
Layout Approval
Supervisor Assignment
Overall Progress
```

## Supervisor

Can access:

```text
Assigned Layouts
Assigned Blocks
Assigned Houses
Enumerator Assignment
Enumerator Progress
GPS Coverage
Boundary Events
```

## Enumerator

Can access:

```text
Own Assigned Block
Houses in Own Block
Household Records
Route
GPS
Revisits
Voice Assistant
Synchronization
```

An Enumerator must not be able to retrieve another Enumerator's block data through the API.

---

# 23. Database Requirements

The main database entities should include:

```text
users
administrative_areas
layouts
blocks
houses
layout_houses
block_houses
layout_supervisor_assignments
enumerator_assignments
household_records
gps_tracks
revisits
sync_operations
audit_logs
boundary_events
routes
```

The key relationship is:

```text
Administrative Area
       ↓
Village/Ward
       ↓
Layout
       ↓
Blocks
       ↓
Houses/Buildings
       ↓
Enumerator
```

---

# 24. Performance Requirements

The application should remain usable on low-end Android devices.

Priorities:

1. Offline operation
2. Fast house-status updates
3. Efficient map rendering
4. Efficient block rendering
5. Small synchronization payloads
6. Batch GPS uploads
7. Pagination for large datasets
8. Efficient spatial queries
9. Minimal unnecessary network requests

The mobile application should not attempt to load every geographic object in a large administrative region at once.

---

# 25. GIS Performance

GIS operations can become expensive with large datasets.

The backend should:

* Use spatial indexes
* Use appropriate PostGIS geometry types
* Use bounding-box filtering where appropriate
* Avoid sending unnecessary geometry to the mobile app
* Simplify map geometry for display when possible
* Paginate large house/building datasets
* Cache frequently accessed layout/block data where appropriate

---

# 26. AI/GIS Processing Architecture

The AI/GIS engine should be separated from normal API logic where practical.

```text
FastAPI
   |
   +---- Authentication
   |
   +---- Layout API
   |
   +---- Block API
   |
   +---- Assignment API
   |
   +---- Household API
   |
   +---- GPS API
   |
   +---- Sync API
   |
   +---- AI/GIS Service
             |
             +---- Block Generation
             +---- Block Validation
             +---- Route Optimization
             +---- Coverage Analysis
```

This makes it easier to improve the AI/GIS algorithms without rewriting the entire backend.

---

# 27. Block Generation Validation Metrics

The block generator should produce measurable validation information.

Possible metrics:

```text
Total Houses
Number of Blocks
Target Houses per Block
Actual Houses per Block
Average Block Size
Minimum Block Size
Maximum Block Size
Unassigned Houses
Duplicate Assignments
Disconnected Blocks
Boundary Violations
```

Example:

```text
Total Houses:          1,240
Target:                  250
Blocks:                    5

Average Block Size:      248
Minimum:                 244
Maximum:                 252

Unassigned:                0
Duplicate:                 0
Boundary Violations:      0
```

These values should be visible to the Deputy Tahsildar during review.

---

# 28. Block Versioning

The system should maintain block versions.

Example:

```text
Layout V1
   ↓
AI Generated
   ↓
Deputy Edited
   ↓
Layout V2
   ↓
Approved
```

After approval, changes should create a new version or follow an explicit controlled modification process.

The system must not silently modify an approved layout.

---

# 29. Audit Requirements

Important operations should be recorded.

Examples:

```text
Layout Generated
Block Generated
Block Edited
Block Split
Block Merged
Layout Approved
Supervisor Assigned
Enumerator Assigned
Enumerator Reassigned
House Completed
House Locked
Revisit Created
Boundary Crossed
Data Synchronized
```

Audit records should include:

```text
User
Action
Entity
Timestamp
Old Value
New Value
```

---

# 30. Error Handling

The application should provide clear errors.

Examples:

### No Houses Found

```text
No houses/buildings were found in the selected area.
Please verify the geographic data.
```

### Block Generation Failure

```text
Block generation could not be completed.
Please check the selected area and house data.
```

### Missing Enumerator

```text
6 blocks require 6 Enumerators.
Only 5 are assigned.
```

### Boundary Crossing

```text
You are outside your assigned block.
Please return to your assigned area.
```

### Synchronization Failure

```text
Some changes could not be synchronized.
Your data is saved locally and will be retried.
```

---

# 31. Deployment

## Initial Development

```text
React Native with Expo + TypeScript
FastAPI
PostgreSQL
PostGIS
expo-sqlite
Local development environment
```

## Production

Production can later use:

* Managed PostgreSQL/PostGIS
* Containerized FastAPI
* HTTPS
* Object storage for large GIS files
* Monitoring
* Logging
* Database backup
* Application performance monitoring

---

# 32. Recommended Development Architecture

The project should be divided into the following modules:

```text
mobile/
│
├── src/
│   ├── app/
│   ├── navigation/
│   ├── core/
│   ├── components/
│   ├── features/
│   │   ├── authentication/
│   │   ├── deputy/
│   │   │   ├── areas/
│   │   │   ├── layouts/
│   │   │   ├── blocks/
│   │   │   └── assignments/
│   │   ├── supervisor/
│   │   │   ├── layouts/
│   │   │   ├── blocks/
│   │   │   ├── enumerators/
│   │   │   └── monitoring/
│   │   ├── enumerator/
│   │   │   ├── dashboard/
│   │   │   ├── map/
│   │   │   ├── houses/
│   │   │   ├── route/
│   │   │   ├── household/
│   │   │   ├── voice/
│   │   │   ├── revisit/
│   │   │   └── sync/
│   │   ├── gps/
│   │   ├── offline/
│   │   └── settings/
│   └── main.tsx
├── app.json
├── package.json
└── __tests__/

backend/
│
├── auth/
├── users/
├── areas/
├── layouts/
├── blocks/
├── houses/
├── assignments/
├── households/
├── gps/
├── coverage/
├── routes/
├── sync/
├── ai/
├── gis/
└── audit/
```

---


# 33. React Native with Expo Implementation Rules

The mobile implementation must follow these rules.

## 33.1 TypeScript

All application code should use TypeScript.

Avoid untyped JavaScript for core business logic.

Use:

* Typed API models
* Typed navigation parameters
* Typed local database models (`expo-sqlite`)
* Typed sync operations
* Typed component props
* Shared enums/constants for domain statuses

---

## 33.2 Feature-Based Architecture

Organize React Native with Expo code by feature rather than placing all screens, hooks, and services in large global folders.

Example:

```text
src/features/enumerator/
├── screens/
├── components/
├── hooks/
├── services/
├── store/
├── models/
└── index.ts
```

Shared functionality belongs under `src/core` or `src/components`.

---

## 33.3 Navigation

Navigation must be role-aware and powered by **React Navigation**.

```text
Authenticated User
        ↓
Role Resolver
        ↓
┌──────────────┬──────────────┬──────────────┐
│ Deputy       │ Supervisor   │ Enumerator   │
│ Navigator    │ Navigator    │ Navigator    │
└──────────────┴──────────────┴──────────────┘
```

The mobile navigator must not be treated as the security boundary. Backend authorization remains authoritative.

---

## 33.4 Offline-First State

The Enumerator experience should follow:

```text
React Native UI
      ↓
Repository
      ↓
expo-sqlite
      ↓
Local Data
      ↓
Sync Queue
      ↓
FastAPI
```

Do not make every field entry depend directly on an API request.

A successful local save in `expo-sqlite` should allow the Enumerator to continue working even when connectivity is unavailable.

---

## 33.5 React Native Performance

The application should:

* Use virtualized lists for large house datasets.
* Avoid unnecessary re-renders.
* Keep map markers efficient.
* Batch GPS records via `expo-location`.
* Paginate large server responses.
* Avoid loading an entire village into React state when only one HLB is required.
* Keep heavy GIS processing on the backend.
* Keep offline database operations transactional with `expo-sqlite`.
* Avoid blocking the JS thread with expensive processing.

---

## 33.6 Native Capabilities & Expo Modules

Use Expo SDK modules and native libraries only where required.

Examples:

```text
expo-location (GPS / Location tracking)
expo-secure-store (Session & Token storage)
expo-sqlite (Offline local database)
react-native-maps (Map rendering)
expo-camera / expo-av (Camera / Audio where required)
NetInfo (Network State)
```

Native capabilities must be wrapped behind small application services in `src/core` so the rest of the codebase does not depend directly on platform-specific APIs.

---

## 33.7 Environment Configuration

Use separate configuration for:

```text
development
testing
production
```

Do not hard-code:

* API URLs
* Secret keys
* Database credentials
* Authentication secrets
* Private map service credentials

Only public/client-safe configuration may be bundled into the mobile application.

---

## 33.8 Testing

React Native tests (using Jest and React Native Testing Library) should cover:

* Login and role routing
* Enumerator HLB access restrictions
* Form validation
* Offline saves with `expo-sqlite`
* Sync queue behavior
* GPS status UI
* Boundary warning UI
* Revisit creation
* Navigation
* Error states

Critical business rules should also be tested independently of the UI.

# 34. Technical Core Rules

The AI coding system must always follow these rules.

### Rule 1

```text
One Village/Ward → One Layout
```

### Rule 2

```text
One Layout → Multiple Blocks
```

### Rule 3

```text
Each Block → Approximately 250 Houses/Buildings
```

### Rule 4

```text
Number of Blocks
        =
Number of Enumerators Required
```

### Rule 5

```text
One Block → One Primary Enumerator
```

### Rule 6

```text
Enumerator Route → Only Assigned Block
```

### Rule 7

```text
Enumerator GPS → Must Be Checked Against Assigned Block Boundary
```

### Rule 8

```text
Boundary Crossing → Warning + Event Recording
```

### Rule 9

```text
AI Generated Block → Deputy Tahsildar Review → Approval
```

### Rule 10

```text
Enumerator Fieldwork → Must Work Offline
```

### Rule 11

```text
Offline Changes → Local Storage → Sync Queue → Server
```

### Rule 12

```text
Backend Must Enforce All Role Permissions
```

---

# 35. Technical Success Criteria

The technical implementation can be considered successful when the following complete workflow works:

```text
Deputy Tahsildar Login
        ↓
Select Village/Ward
        ↓
View Houses/Buildings
        ↓
Generate Blocks
        ↓
Approximately 250 Houses/Buildings per Block
        ↓
Review / Edit
        ↓
Approve
        ↓
Assign Layout to Supervisor
        ↓
Supervisor Login
        ↓
View Blocks
        ↓
Required Enumerators = Number of Blocks
        ↓
Assign One Enumerator to Each Block
        ↓
Enumerator Login
        ↓
View Assigned Block
        ↓
Download for Offline Use
        ↓
View Houses
        ↓
Generate Route
        ↓
Visit Houses
        ↓
Record Household
        ↓
Mark Completed / Locked
        ↓
GPS Tracking
        ↓
Boundary Warning if Enumerator Leaves Block
        ↓
Continue Offline
        ↓
Internet Returns
        ↓
Synchronize
        ↓
Supervisor Sees Updated Progress
```

This workflow is the **technical backbone of AI-Enumerator Assistant**. All future modules should fit into this architecture rather than creating a separate workflow.
