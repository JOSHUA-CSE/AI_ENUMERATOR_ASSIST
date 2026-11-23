# AI-Enumerator Assistant — Backend Schema

## 1. Database

### Recommended Database

**PostgreSQL + PostGIS**

PostGIS is required because the application needs to manage:

* Administrative boundaries
* Village/Ward boundaries
* Layout polygons
* Houselisting Block boundaries
* House/building coordinates
* Enumerator GPS tracks
* Spatial queries
* Distance calculations
* Route calculations
* GPS coverage analysis
* Boundary checking

The database should be designed around the project's hierarchy:

```text
Administrative Area
       ↓
     Layout
       ↓
Houselisting Blocks
       ↓
Houses / Buildings
       ↓
Household Records
```

---

# 2. Users

All three roles should be stored in a single `users` table.

### Table: `users`

| Column        | Type      | Notes                                          |
| ------------- | --------- | ---------------------------------------------- |
| id            | UUID      | Primary key                                    |
| name          | VARCHAR   | User name                                      |
| phone         | VARCHAR   | Optional, unique if used                       |
| username      | VARCHAR   | Unique login ID                                |
| password_hash | TEXT      | Never store plain password                     |
| role          | ENUM      | `DEPUTY_TAHSILDAR`, `SUPERVISOR`, `ENUMERATOR` |
| status        | ENUM      | `ACTIVE`, `INACTIVE`                           |
| created_at    | TIMESTAMP | Creation time                                  |
| updated_at    | TIMESTAMP | Last update                                    |

### Role hierarchy

```text
DEPUTY_TAHSILDAR
        ↓
    SUPERVISOR
        ↓
    ENUMERATOR
```

The backend must enforce role permissions.

---

# 3. Administrative Areas

Administrative areas represent the geographical hierarchy used to select a village, ward, or other administrative unit.

### Table: `administrative_areas`

| Column     | Type                                 | Notes                       |
| ---------- | ------------------------------------ | --------------------------- |
| id         | UUID                                 | Primary key                 |
| name       | VARCHAR                              | Area name                   |
| type       | VARCHAR                              | Village / Ward / etc.       |
| parent_id  | UUID                                 | Parent administrative area  |
| code       | VARCHAR                              | Official/internal area code |
| boundary   | GEOMETRY(POLYGON/MULTIPOLYGON, 4326) | PostGIS boundary            |
| created_at | TIMESTAMP                            | Creation time               |
| updated_at | TIMESTAMP                            | Last update                 |

Relationship:

```text
Administrative Area
       |
       +---- Child Administrative Areas
```

---

# 4. Houses / Buildings

Houses/buildings are master geographical planning objects representing physical structures identified via satellite imagery, GIS imports, or manual field entry.

> **Crucial Architecture Rule: Building vs. Household Record**
> - **Building / Structure (`houses` table)**: Physical geographic object with coordinates/footprint used for GIS planning, density estimation, and HLB generation.
> - **Household Record (`household_records` table)**: Socio-demographic census data for individual families/households residing inside a building, captured during on-the-ground Enumerator fieldwork.
> - Satellite-detected buildings are strictly treated as **geographic planning entities**, never as verified household records.

### Table: `houses`

| Column               | Type                                 | Notes                                                              |
| -------------------- | ------------------------------------ | ------------------------------------------------------------------ |
| id                   | UUID                                 | Primary key                                                        |
| area_id              | UUID                                 | Administrative area (Village / Ward)                               |
| building_reference   | VARCHAR                              | External/internal reference (e.g. `BLD-001`, `H-638401-001`)       |
| house_number         | VARCHAR                              | Optional door/house number (e.g. `1/1`)                            |
| latitude             | DECIMAL                              | Centroid Latitude                                                  |
| longitude            | DECIMAL                              | Centroid Longitude                                                 |
| location             | GEOMETRY(POINT, 4326)                | PostGIS point location                                             |
| footprint            | GEOMETRY(POLYGON/MULTIPOLYGON, 4326) | Optional building polygon footprint                                |
| source_type          | ENUM                                 | `MANUAL`, `SATELLITE_DETECTED`, `GOVERNMENT_IMPORT`, `FIELD_VERIFIED` |
| detection_confidence | DECIMAL                              | Confidence score (0.0 to 1.0) for ML/satellite detections          |
| detected_at          | TIMESTAMP                            | Timestamp when building detection was performed                    |
| imagery_source       | VARCHAR                              | Satellite imagery provider (e.g., `esri_world_imagery`, `sentinel`) |
| imagery_date         | DATE                                 | Acquisition date of underlying satellite imagery                   |
| created_at           | TIMESTAMP                            | Creation time                                                      |
| updated_at           | TIMESTAMP                            | Last update                                                        |

Relationship:

```text
Administrative Area
        ↓
Houses / Buildings (Satellite Detected / Estimated)
        ↓
HLB Assignment
        ↓
Field Verification by Enumerator
        ↓
Household Records
```

---

# 5. Layouts

A **Layout represents the selected Village/Ward** for the project's field planning.

The Deputy Tahsildar selects an administrative area and creates its layout.

### Table: `layouts`

| Column                    | Type                                 | Notes                                                             |
| ------------------------- | ------------------------------------ | ----------------------------------------------------------------- |
| id                        | UUID                                 | Primary key                                                       |
| area_id                   | UUID                                 | Foreign key to `administrative_areas.id` (Selected Village/Ward)  |
| name                      | VARCHAR                              | Layout name                                                       |
| target_hlb_building_count | INTEGER                              | Default approximately 250 (configurable)                          |
| actual_building_count     | INTEGER                              | Count of buildings in this area                                   |
| expected_hlb_count        | INTEGER                              | Calculated expected block count                                   |
| boundary                  | GEOMETRY(POLYGON/MULTIPOLYGON, 4326) | Layout boundary (from administrative area)                        |
| status                    | ENUM                                 | `DRAFT`, `ASSIGNED`, `APPROVED`, `COMPLETED`, `ARCHIVED`          |
| active_version_id         | UUID                                 | Foreign key to active approved `layout_versions.id`               |
| created_by                | UUID                                 | Deputy Tahsildar user ID                                          |
| approved_by               | UUID                                 | Deputy Tahsildar approver ID                                      |
| approved_at               | TIMESTAMP                            | Approval timestamp                                                |
| created_at                | TIMESTAMP                            | Creation time                                                     |
| updated_at                | TIMESTAMP                            | Last update                                                       |

### Important rule

```text
One selected Village/Ward
          ↓
      One Layout
```

---

# 6. Layout Versions

Generated layouts must be separated from approved layouts.

This is important because the Deputy Tahsildar may:

* Generate candidate blocks
* Edit boundaries
* Split blocks
* Merge blocks
* Regenerate
* Approve the final version

### Table: `layout_versions`

| Column                   | Type      | Notes                                                      |
| ------------------------ | --------- | ---------------------------------------------------------- |
| id                       | UUID      | Primary key                                                |
| layout_id                | UUID      | Foreign key to `layouts.id`                                |
| version_number           | INTEGER   | Incremental version number ($1, 2, \dots$)                 |
| source                   | ENUM      | `AI_GENERATED`, `MANUAL_EDIT`, `IMPORT`                    |
| status                   | ENUM      | `CANDIDATE`, `APPROVED`, `SUPERSEDED`, `REJECTED`          |
| target_buildings_per_hlb | INTEGER   | Deputy's requested building target for this version        |
| total_buildings          | INTEGER   | Total structures partitioned                               |
| hlb_count                | INTEGER   | Number of HLBs generated                                   |
| quality_score            | FLOAT     | Composite validation quality score $Q \in [0.0, 100.0]$    |
| validation_status        | VARCHAR   | `VALID`, `WARNING`, or `INVALID`                           |
| validation_summary       | JSON      | Invariant checklist (coverage, balance, duplicates)        |
| generation_metadata      | JSON      | Algorithm details, clustering timestamps                   |
| created_by               | UUID      | User who triggered generation                              |
| created_at               | TIMESTAMP | Creation timestamp                                         |

Relationship:

```text
Layout
  |
  +---- Version 1 (SUPERSEDED)
  |
  +---- Version 2 (SUPERSEDED)
  |
  +---- Version 3 (APPROVED / Active)
```

The approved version must remain stable for fieldwork.

---

# 7. Houselisting Blocks

A layout is divided into **Houselisting Blocks (HLBs)**.

Each HLB should contain approximately the configured target number of houses/buildings ($\approx 250$).

### Table: `houselisting_blocks`

| Column                | Type                                 | Notes                                                                         |
| --------------------- | ------------------------------------ | ----------------------------------------------------------------------------- |
| id                    | UUID                                 | Primary key                                                                   |
| layout_id             | UUID                                 | Foreign key to `layouts.id`                                                   |
| version_id            | UUID                                 | Foreign key to `layout_versions.id`                                           |
| block_code            | VARCHAR                              | Example: `HLB-001`, `HLB-002`                                                 |
| name                  | VARCHAR                              | Display name (e.g. `Arasur Village Block 1`)                                  |
| target_building_count | INTEGER                              | Balanced target size for this block                                           |
| actual_building_count | INTEGER                              | Actual assigned structures count                                              |
| boundary              | GEOMETRY(POLYGON/MULTIPOLYGON, 4326) | Morphological synthesized polygon boundary                                    |
| status                | ENUM                                 | `DRAFT`, `GENERATED`, `APPROVED`, `ASSIGNED`, `ACTIVE`, `COMPLETED`, `ARCHIVED`|
| quality_score         | FLOAT                                | Individual block quality score                                                |
| validation_status     | ENUM                                 | `VALID`, `WARNING`, `INVALID`                                                 |
| validation_details    | JSON                                 | Balance, compactness, and containment details                                 |
| created_at            | TIMESTAMP                            | Creation time                                                                 |
| updated_at            | TIMESTAMP                            | Last update                                                                   |

Relationship:

```text
Layout
   |
   +---- HLB-001
   |
   +---- HLB-002
   |
   +---- HLB-003
   |
   +---- HLB-004
   |
   +---- HLB-005
```

---

# 8. HLB-House Mapping

A house/building belongs to an HLB for the approved layout version.

### Table: `hlb_houses`

| Column      | Type      | Notes                  |
| ----------- | --------- | ---------------------- |
| id          | UUID      | Primary key            |
| hlb_id      | UUID      | Houselisting Block     |
| house_id    | UUID      | House/building         |
| assigned_at | TIMESTAMP | Assignment time        |
| assigned_by | UUID      | System/authorized user |
| status      | ENUM      | `ASSIGNED`, `REMOVED`  |

Relationship:

```text
HLB
 |
 +---- House 001
 +---- House 002
 +---- House 003
 +---- ...
```

### Important constraint

A house should not belong to two **active HLBs within the same approved layout**.

---

# 9. Layout-House Mapping

The previous `layout_houses` table can still be retained because it provides a direct relationship between the layout and its houses.

### Table: `layout_houses`

| Column      | Type      | Notes           |
| ----------- | --------- | --------------- |
| id          | UUID      | Primary key     |
| layout_id   | UUID      | Layout          |
| house_id    | UUID      | House/building  |
| assigned_at | TIMESTAMP | Assignment time |

Relationship:

```text
Layout
   ↓
layout_houses
   ↓
Houses
```

However, the HLB mapping is the authoritative assignment for fieldwork:

```text
Layout
   ↓
HLB
   ↓
House
```

---

# 10. Layout-Supervisor Assignment

A Supervisor is responsible for a complete approved layout.

### Table: `layout_supervisor_assignments`

| Column        | Type      | Notes                              |
| ------------- | --------- | ---------------------------------- |
| id            | UUID      | Primary key                        |
| layout_id     | UUID      | Assigned layout                    |
| supervisor_id | UUID      | Supervisor                         |
| assigned_by   | UUID      | Deputy Tahsildar                   |
| assigned_at   | TIMESTAMP | Assignment time                    |
| status        | ENUM      | `ACTIVE`, `COMPLETED`, `CANCELLED` |

Relationship:

```text
Layout
   ↓
Supervisor
```

Only an authorized Deputy Tahsildar can create this assignment.

---

# 11. HLB-Enumerator Assignment

This is the primary Enumerator assignment table.

The previous schema assigned Enumerators using `layout_id`. That is not sufficient for the revised workflow.

An Enumerator must be assigned to a **specific HLB**.

### Table: `hlb_enumerator_assignments`

| Column        | Type      | Notes                                          |
| ------------- | --------- | ---------------------------------------------- |
| id            | UUID      | Primary key                                    |
| hlb_id        | UUID      | Assigned HLB                                   |
| layout_id     | UUID      | Parent layout                                  |
| enumerator_id | UUID      | Enumerator                                     |
| supervisor_id | UUID      | Assigning Supervisor                           |
| assigned_at   | TIMESTAMP | Assignment time                                |
| status        | ENUM      | `ASSIGNED`, `ACTIVE`, `COMPLETED`, `CANCELLED` |

Relationship:

```text
HLB
 ↓
Enumerator
```

### Core project rule

```text
1 HLB
 ↓
1 Primary Enumerator
```

And:

```text
Number of HLBs
       =
Required Number of Enumerators
```

---

# 12. Enumerator Assignment Validation

Before an assignment is marked complete, the backend must check:

```text
Total HLBs = Required Enumerators
```

and:

```text
Every HLB has one primary Enumerator
```

Example:

```text
Layout: Village A

HLBs: 5

Required Enumerators: 5
Assigned Enumerators: 5

Status:
✓ Assignment Complete
```

If:

```text
HLBs: 5
Enumerators: 4
```

the system should report:

```text
⚠ 1 Enumerator Required
```

---

# 13. Household Records

Household information should be stored separately from the house/building master record.

### Table: `household_records`

| Column        | Type      | Notes                         |
| ------------- | --------- | ----------------------------- |
| id            | UUID      | Primary key                   |
| house_id      | UUID      | House/building                |
| hlb_id        | UUID      | HLB                           |
| enumerator_id | UUID      | Enumerator                    |
| data          | JSONB     | Questionnaire data            |
| source        | ENUM      | `FORM`, `VOICE`               |
| captured_at   | TIMESTAMP | Original capture              |
| updated_at    | TIMESTAMP | Last update                   |
| version       | INTEGER   | Record version                |
| sync_status   | ENUM      | `LOCAL`, `SYNCED`, `CONFLICT` |

The exact questionnaire should be defined separately.

---

# 14. House Fieldwork Status

Because houses are master geographical objects, fieldwork status should be tracked separately.

### Table: `house_fieldwork_status`

| Column          | Type      | Notes                                                      |
| --------------- | --------- | ---------------------------------------------------------- |
| id              | UUID      | Primary key                                                |
| house_id        | UUID      | House/building                                             |
| hlb_id          | UUID      | Assigned HLB                                               |
| enumerator_id   | UUID      | Responsible Enumerator                                     |
| status          | ENUM      | `PENDING`, `IN_PROGRESS`, `COMPLETED`, `LOCKED`, `REVISIT` |
| last_updated_at | TIMESTAMP | Last status update                                         |
| updated_by      | UUID      | User                                                       |

This prevents a global house status from being incorrectly shared between different layouts or historical fieldwork.

---

# 15. Revisit Records

### Table: `revisits`

| Column         | Type      | Notes                               |
| -------------- | --------- | ----------------------------------- |
| id             | UUID      | Primary key                         |
| house_id       | UUID      | House                               |
| hlb_id         | UUID      | HLB                                 |
| enumerator_id  | UUID      | Assigned Enumerator                 |
| reason         | TEXT      | Reason for revisit                  |
| recommended_at | TIMESTAMP | Revisit creation                    |
| completed_at   | TIMESTAMP | Completion time                     |
| status         | ENUM      | `PENDING`, `COMPLETED`, `CANCELLED` |
| notes          | TEXT      | Optional notes                      |

Example reasons:

```text
No one available
Locked
Need additional information
Other
```

---

# 16. GPS Tracks

GPS records are associated primarily with the Enumerator and assigned HLB.

### Table: `gps_tracks`

| Column          | Type                  | Notes               |
| --------------- | --------------------- | ------------------- |
| id              | UUID                  | Primary key         |
| enumerator_id   | UUID                  | Enumerator          |
| layout_id       | UUID                  | Layout              |
| hlb_id          | UUID                  | Assigned HLB        |
| location        | GEOMETRY(POINT, 4326) | GPS position        |
| accuracy_meters | DECIMAL               | GPS accuracy        |
| timestamp       | TIMESTAMP             | Capture time        |
| source          | ENUM                  | `ONLINE`, `OFFLINE` |

Relationship:

```text
Enumerator
    ↓
Layout
    ↓
HLB
    ↓
GPS Points
```

GPS data can become very large.

Therefore:

* Sampling interval should be configurable.
* Retention period should be configurable.
* Batch upload should be supported.

---

# 17. HLB Boundary Events

Boundary events should be stored separately from normal GPS points.

### Table: `hlb_boundary_events`

| Column          | Type                  | Notes                           |
| --------------- | --------------------- | ------------------------------- |
| id              | UUID                  | Primary key                     |
| enumerator_id   | UUID                  | Enumerator                      |
| hlb_id          | UUID                  | Assigned HLB                    |
| location        | GEOMETRY(POINT, 4326) | Event location                  |
| event_type      | ENUM                  | `EXITED_HLB`, `RETURNED_TO_HLB` |
| timestamp       | TIMESTAMP             | Event time                      |
| accuracy_meters | DECIMAL               | GPS accuracy                    |
| resolved_at     | TIMESTAMP             | Optional                        |
| created_at      | TIMESTAMP             | Creation time                   |

This allows the Supervisor to see:

```text
Enumerator left HLB
        ↓
GPS location
        ↓
Time
        ↓
Returned to HLB
```

---

# 18. Route Records

If route optimization is persisted, store the generated route.

### Table: `routes`

| Column                | Type                  | Notes                              |
| --------------------- | --------------------- | ---------------------------------- |
| id                    | UUID                  | Primary key                        |
| hlb_id                | UUID                  | HLB                                |
| enumerator_id         | UUID                  | Enumerator                         |
| generated_at          | TIMESTAMP             | Creation time                      |
| start_location        | GEOMETRY(POINT, 4326) | Starting position                  |
| total_distance_meters | DECIMAL               | Estimated distance                 |
| status                | ENUM                  | `ACTIVE`, `COMPLETED`, `CANCELLED` |

---

# 19. Route Stops

### Table: `route_stops`

| Column          | Type      | Notes                                     |
| --------------- | --------- | ----------------------------------------- |
| id              | UUID      | Primary key                               |
| route_id        | UUID      | Route                                     |
| house_id        | UUID      | House/building                            |
| sequence_number | INTEGER   | Visit order                               |
| status          | ENUM      | `PENDING`, `VISITED`, `SKIPPED`, `LOCKED` |
| visited_at      | TIMESTAMP | Visit time                                |

Important constraint:

```text
Route
  ↓
Only houses belonging to assigned HLB
```

---

# 20. Sync Operations

Offline operation requires a synchronization queue.

### Table: `sync_operations`

| Column           | Type      | Notes                                     |
| ---------------- | --------- | ----------------------------------------- |
| id               | UUID      | Primary key                               |
| device_id        | VARCHAR   | Mobile device                             |
| user_id          | UUID      | User                                      |
| operation_type   | VARCHAR   | CREATE / UPDATE / DELETE                  |
| entity_type      | VARCHAR   | Entity name                               |
| entity_id        | UUID      | Entity                                    |
| payload          | JSONB     | Operation data                            |
| client_timestamp | TIMESTAMP | Device time                               |
| server_timestamp | TIMESTAMP | Server time                               |
| status           | ENUM      | `PENDING`, `SYNCED`, `FAILED`, `CONFLICT` |
| retry_count      | INTEGER   | Retry count                               |
| error_message    | TEXT      | Failure details                           |

---

# 21. Sync Rules

The synchronization system must be:

* Retryable
* Idempotent
* Offline-first
* Conflict-aware

Flow:

```text
Local Change
     ↓
PENDING
     ↓
Sync
     ↓
Server Validation
     ↓
+--------------------+
|                    |
SUCCESS           CONFLICT/ERROR
 |                    |
 ↓                    ↓
SYNCED            Retry/Resolve
```

Never delete a local record simply because synchronization failed.

---

# 22. Devices

Since the Enumerator application is offline-first, device information should be tracked.

### Table: `devices`

| Column            | Type      | Notes                |
| ----------------- | --------- | -------------------- |
| id                | UUID      | Primary key          |
| device_identifier | VARCHAR   | Device identifier    |
| user_id           | UUID      | Assigned user        |
| app_version       | VARCHAR   | App version          |
| last_sync_at      | TIMESTAMP | Last successful sync |
| status            | ENUM      | `ACTIVE`, `REVOKED`  |
| created_at        | TIMESTAMP | Registration time    |

A user may have more than one registered device over time, depending on the deployment policy.

---

# 23. Audit Logs

Important administrative actions must be recorded.

### Table: `audit_logs`

| Column      | Type      | Notes           |
| ----------- | --------- | --------------- |
| id          | UUID      | Primary key     |
| user_id     | UUID      | Performing user |
| action      | VARCHAR   | Action          |
| entity_type | VARCHAR   | Entity          |
| entity_id   | UUID      | Entity ID       |
| old_data    | JSONB     | Previous data   |
| new_data    | JSONB     | New data        |
| timestamp   | TIMESTAMP | Action time     |
| ip_address  | VARCHAR   | Optional        |
| device_id   | UUID      | Optional        |

Important actions include:

```text
LOGIN
LAYOUT_CREATED
HLBS_GENERATED
HLB_EDITED
HLB_SPLIT
HLB_MERGED
LAYOUT_APPROVED
SUPERVISOR_ASSIGNED
ENUMERATOR_ASSIGNED
HOUSE_COMPLETED
HOUSE_LOCKED
REVISIT_CREATED
LAYOUT_COMPLETED
```

---

# 24. Layout Generation Jobs

AI/GIS block generation may take time for large areas.

Therefore, generation should be represented as a background job.

### Table: `layout_generation_jobs`

| Column             | Type      | Notes                                         |
| ------------------ | --------- | --------------------------------------------- |
| id                 | UUID      | Primary key                                   |
| layout_id          | UUID      | Layout                                        |
| requested_by       | UUID      | Deputy Tahsildar                              |
| target_house_count | INTEGER   | Target                                        |
| status             | ENUM      | `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED` |
| progress           | INTEGER   | 0–100                                         |
| result_version_id  | UUID      | Generated layout version                      |
| error_message      | TEXT      | Failure details                               |
| started_at         | TIMESTAMP | Start time                                    |
| completed_at       | TIMESTAMP | Completion time                               |
| created_at         | TIMESTAMP | Creation time                                 |

UI can then display:

```text
Generating HLBs...

80%
```

---

# 25. Coverage Analysis

Coverage results can be calculated dynamically or stored for reporting.

### Table: `coverage_reports`

| Column                   | Type                         | Notes                 |
| ------------------------ | ---------------------------- | --------------------- |
| id                       | UUID                         | Primary key           |
| layout_id                | UUID                         | Layout                |
| hlb_id                   | UUID                         | HLB                   |
| enumerator_id            | UUID                         | Enumerator            |
| house_completion_percent | DECIMAL                      | House completion      |
| gps_coverage_percent     | DECIMAL                      | GPS-based indicator   |
| possible_missed_area     | GEOMETRY(MULTIPOLYGON, 4326) | Possible missed areas |
| generated_at             | TIMESTAMP                    | Calculation time      |

Important:

GPS coverage must remain an **indicator**, not proof of household completion.

---

# 26. Relationships

The main relationship structure is:

```text
users
 |
 +----< layout_supervisor_assignments >---- layouts
 |                                               |
 |                                               +----< houselisting_blocks
 |                                                          |
 |                                                          +----< hlb_houses >---- houses
 |                                                          |
 |                                                          +----< hlb_enumerator_assignments >---- users
 |                                                          |
 |                                                          +----< house_fieldwork_status
 |                                                          |
 |                                                          +----< revisits
 |                                                          |
 |                                                          +----< gps_tracks
 |                                                          |
 |                                                          +----< hlb_boundary_events
 |                                                          |
 |                                                          +----< routes
 |
 +----< household_records >---- houses
 |
 +----< audit_logs
 |
 +----< sync_operations
 |
 +----< devices

administrative_areas
 |
 +----< layouts
 |
 +----< houses
```

---

# 27. Simplified ER Structure

The AI coding agent should understand the core structure as:

```text
┌───────────────────────┐
│ Administrative Area   │
│ Village / Ward        │
└───────────┬───────────┘
            │
            ↓
┌───────────────────────┐
│ Layout                │
│ Village/Ward Layout   │
└───────────┬───────────┘
            │
            ↓
┌───────────────────────┐
│ Houselisting Block    │
│ HLB                   │
│ ≈250 Houses           │
└───────────┬───────────┘
            │
       ┌────┴────┐
       ↓         ↓
    Houses    Enumerator
       │         │
       ↓         ↓
 Household    GPS / Route
 Records
```

---

# 28. Core Assignment Relationship

The most important assignment relationship is:

```text
Deputy Tahsildar
       ↓
    Layout
       ↓
   Supervisor
       ↓
     HLB
       ↓
  Enumerator
       ↓
 Houses/Buildings
```

Therefore:

```text
1 Layout → 1 Supervisor
1 Layout → N HLBs
1 HLB → 1 Primary Enumerator
1 HLB → N Houses/Buildings
```

---

# 29. Enumerator Access Constraints

An Enumerator must only be able to access:

```text
Their assigned HLB
        ↓
Its houses/buildings
        ↓
Its household records
        ↓
Its route
        ↓
Its GPS/fieldwork data
```

The backend must reject requests for another Enumerator's HLB.

Example:

```text
Enumerator E001
Assigned HLB: B001

Request:
GET /api/hlbs/B002

Result:

403 FORBIDDEN
```

The UI restriction alone is not sufficient.

---

# 30. Supervisor Access Constraints

A Supervisor can only access layouts assigned to them.

Within an assigned layout, the Supervisor can access:

```text
All HLBs
All assigned Enumerators
House progress
Revisit information
GPS coverage
Boundary events
```

The Supervisor cannot approve the layout unless that permission is explicitly granted by the system design.

---

# 31. Deputy Tahsildar Access Constraints

The Deputy Tahsildar can:

* Create layouts
* Generate HLBs
* Review HLBs
* Edit HLBs
* Split HLBs
* Merge HLBs
* Approve layouts
* Assign Supervisors
* View overall progress

Only authorized Deputy Tahsildars can approve layouts.

---

# 32. Important Database Constraints

The backend must enforce the following.

### Constraint 1 — One Village/Ward Layout

```text
One selected Village/Ward
        ↓
One active Layout
```

---

### Constraint 2 — HLB Membership

A house cannot belong to two active HLBs within the same layout.

```text
House 102
   ↓
HLB B003 ✓
```

Not:

```text
House 102
   ↓
HLB B003
HLB B004
```

---

### Constraint 3 — Enumerator Assignment

Each active HLB should have one primary Enumerator.

```text
HLB B003
    ↓
E003
```

---

### Constraint 4 — Enumerator Scope

An Enumerator can only operate on their assigned HLB.

---

### Constraint 5 — Supervisor Scope

A Supervisor can only manage authorized layouts and their HLBs.

---

### Constraint 6 — Layout Approval

Only an authorized Deputy Tahsildar can approve a layout.

---

### Constraint 7 — Approved Version

Once approved, the fieldwork version of the layout/HLBs should remain stable.

If changes are required later:

```text
Approved Version
       ↓
Create New Version
       ↓
Review
       ↓
Approve
```

Do not silently modify historical approved data.

---

### Constraint 8 — Approximately 250 Houses

The target is configurable.

Default:

```text
250 Houses/Buildings per HLB
```

The system should validate the actual count and report deviations.

It should not blindly reject geographically necessary variations.

---

### Constraint 9 — Enumerator Count

```text
Required Enumerators
        =
Number of Active HLBs
```

The Supervisor assignment screen should clearly display this calculation.

---

### Constraint 10 — Route Scope

An Enumerator route must only contain houses belonging to the assigned HLB.

---

### Constraint 11 — GPS Scope

Enumerator GPS analysis should be evaluated against the assigned HLB boundary.

---

### Constraint 12 — Auditability

Important actions must create audit records.

---

# 33. Status Definitions

## Layout

```text
DRAFT
GENERATED
REVIEW
APPROVED
ACTIVE
COMPLETED
```

## HLB

```text
DRAFT
GENERATED
REVIEW
APPROVED
ASSIGNED
ACTIVE
COMPLETED
```

## House

```text
PENDING
IN_PROGRESS
COMPLETED
LOCKED
REVISIT
```

## Assignment

```text
ASSIGNED
ACTIVE
COMPLETED
CANCELLED
```

## Sync

```text
PENDING
SYNCED
FAILED
CONFLICT
```

---

# 34. Backend API Mapping

The schema should support APIs such as:

### Authentication

```text
POST /api/auth/login
POST /api/auth/refresh
POST /api/auth/logout
GET  /api/auth/me
```

### Administrative Areas

```text
GET /api/areas
GET /api/areas/{id}
```

### Layouts

```text
POST /api/layouts
GET  /api/layouts
GET  /api/layouts/{id}
PUT  /api/layouts/{id}
POST /api/layouts/{id}/generate
POST /api/layouts/{id}/approve
```

### HLBs

```text
GET  /api/layouts/{layout_id}/hlbs
GET  /api/hlbs/{id}
PUT  /api/hlbs/{id}
POST /api/hlbs/{id}/split
POST /api/hlbs/{id}/merge
POST /api/hlbs/{id}/validate
```

### Supervisor Assignment

```text
POST /api/layouts/{id}/supervisor
GET  /api/layouts/{id}/supervisor
```

### Enumerator Assignment

```text
POST /api/hlbs/{id}/enumerator
GET  /api/hlbs/{id}/enumerator
GET  /api/assignments/my
```

### Houses

```text
GET  /api/hlbs/{id}/houses
GET  /api/houses/{id}
PUT  /api/houses/{id}/status
POST /api/houses/{id}/household
```

### GPS

```text
POST /api/gps/batch
GET  /api/hlbs/{id}/coverage
GET  /api/hlbs/{id}/boundary-events
```

### Routes

```text
POST /api/hlbs/{id}/route
GET  /api/hlbs/{id}/route
```

### Revisits

```text
GET  /api/hlbs/{id}/revisits
POST /api/houses/{id}/revisit
PUT  /api/revisits/{id}
```

### Synchronization

```text
POST /api/sync/upload
GET  /api/sync/changes
```

---

# 35. Security Requirements

The backend must enforce:

* HTTPS
* Password hashing
* Access-token/session security
* Role-based authorization
* HLB-level Enumerator authorization
* Supervisor-level layout authorization
* Input validation
* Authentication rate limiting
* Secure mobile token storage
* Audit logging
* Minimal exposure of household information
* No database credentials in the mobile application

---

# 36. Final Backend Architecture

The complete database model should follow:

```text
                    USERS
                      │
       ┌──────────────┼───────────────┐
       ↓              ↓               ↓
Deputy Tahsildar  Supervisor      Enumerator
       │              │               │
       ↓              ↓               ↓
Administrative     Layout         HLB Assignment
Area                 │               │
       │             ↓               ↓
       └────────→   HLB ←──────── Enumerator
                     │
              ┌──────┼──────┐
              ↓      ↓      ↓
           Houses  Routes  GPS
              │
              ↓
        Household Records
              │
              ↓
          Revisit Data
```

---

# 37. Final Core Rules for the AI Coding Agent

The backend implementation must always preserve these rules:

```text
Rule 1
Village/Ward → Layout

Rule 2
Layout → Multiple HLBs

Rule 3
HLB → Approximately 250 Houses/Buildings

Rule 4
Number of HLBs = Required Enumerators

Rule 5
One HLB → One Primary Enumerator

Rule 6
Enumerator → Only Assigned HLB

Rule 7
Route → Only Houses in Assigned HLB

Rule 8
GPS → Compared with Assigned HLB Boundary

Rule 9
Deputy Tahsildar → Approves Layout

Rule 10
Supervisor → Manages Assigned Layout

Rule 11
Enumerator → Performs Fieldwork

Rule 12
Offline Changes → Sync Queue

Rule 13
Synchronization → Idempotent

Rule 14
Important Actions → Audit Log

Rule 15
Approved Layout → Stable Version
```

---

# 38. Final Data Hierarchy

The AI coding agent should consider this the authoritative project hierarchy:

```text
ADMINISTRATIVE AREA
       │
       │ Village / Ward
       ↓
LAYOUT
       │
       │ Complete Village/Ward field layout
       ↓
HOUSELISTING BLOCKS (HLBs)
       │
       │ Approximately 250 houses/buildings each
       ↓
HOUSES / BUILDINGS
       │
       ├───────────────┐
       ↓               ↓
HOUSEHOLD         FIELDWORK
RECORDS           STATUS
                       │
             ┌─────────┼─────────┐
             ↓         ↓         ↓
           GPS       ROUTE     REVISIT
```

This structure should be treated as the **base database architecture** for the AI-Enumerator Assistant.
