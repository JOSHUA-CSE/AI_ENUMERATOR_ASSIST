# AI-Enumerator Assistant

AI-Enumerator Assistant is a mobile application designed to support census field staff in planning, assigning, conducting, and monitoring fieldwork.

The project focuses on reducing manual work during census field operations while keeping important decisions under the control of authorized officers.

The application is designed around three roles:

* **Deputy Tahsildar**
* **Supervisor**
* **Enumerator**

The main idea is to combine a simple census-style field application with GIS, satellite-assisted building estimation, offline support, GPS, route optimization, and AI-assisted planning.

---

## Project Overview

The basic workflow of the application is:

```text
Village / Ward
      ↓
Satellite Imagery + Boundary
      ↓
Building Detection / Estimation
      ↓
Estimated Building Count
      ↓
Layout Planning
      ↓
Houselisting Blocks (HLBs)
      ↓
≈250 Houses / Buildings per HLB
      ↓
   Supervisor
      ↓
One Enumerator per HLB
      ↓
Household Fieldwork & Verification
      ↓
Offline Sync
      ↓
Supervisor Monitoring
```

A Deputy Tahsildar selects a village or ward, loads the administrative boundary over satellite imagery, runs or loads satellite-assisted building detection to estimate visible buildings/structures, and uses the resulting building distribution for GIS layout planning. The layout is divided into Houselisting Blocks (HLBs), with approximately 250 houses/buildings per HLB by default.

> **Important Distinction:** Satellite-derived building estimates serve as **geographic planning data** to assess building concentration and generate balanced HLBs. They are **not** official census household records. Actual household numbers, multi-household structures, and occupancy are determined during on-the-ground Enumerator fieldwork.

After the layout is reviewed and approved, it is assigned to a Supervisor. The Supervisor assigns one Enumerator to each HLB.

The Enumerator then works within the assigned HLB, records household information, captures GPS information, handles locked houses and revisits, and synchronizes the data when connectivity is available.

---

## Main Objectives

The project aims to:

* Reduce manual work in census field planning
* Support satellite-imagery-assisted building estimation and spatial density analysis
* Assist in creating balanced Houselisting Blocks
* Make field assignments easier
* Help Enumerators work with their assigned HLB
* Support offline field data collection
* Improve field progress monitoring
* Detect possible missed areas
* Provide route assistance
* Provide Tamil and English voice assistance
* Maintain clear role-based access
* Keep important decisions under human control

---

## User Roles

### Deputy Tahsildar

The Deputy Tahsildar is responsible for spatial planning and approving the field layout.

Main responsibilities:

* Select Village/Ward
* View administrative boundary on satellite imagery
* Run/load building detection and estimation
* Inspect building density heatmaps and cluster counts
* View estimated building count
* Create Layout
* Generate HLBs
* Review generated HLBs
* Edit HLB boundaries
* Split or merge HLBs
* Validate HLBs
* Approve the Layout
* Assign the Layout to a Supervisor
* Monitor overall progress

The AI can suggest building estimates and HLBs, but the Deputy Tahsildar remains the final approver.

---

### Supervisor

The Supervisor manages the fieldwork within the assigned Layout.

Main responsibilities:

* View assigned Layouts
* View HLBs
* Assign Enumerators
* Monitor Enumerator progress
* View completed and remaining houses
* Monitor locked/revisit houses
* View GPS coverage
* View possible missed areas
* Monitor synchronization status

The main assignment rule is:

```text
1 HLB
 ↓
1 Primary Enumerator
```

Therefore:

```text
Number of HLBs
      =
Required Number of Enumerators
```

---

### Enumerator

The Enumerator performs the actual fieldwork.

Main responsibilities:

* View assigned HLB
* Download HLB data for offline use
* View houses/buildings
* View map
* Follow an optimized route
* Record household information
* Use voice assistance
* Mark houses as completed
* Mark houses as locked
* Create revisit records
* Capture GPS location
* Continue working without internet
* Synchronize data when connectivity returns

The Enumerator should only work with the HLB assigned to them.

---

## Key Features

### 1. AI-Assisted HLB Generation

The Deputy Tahsildar provides:

* Village/Ward boundary
* House/building locations
* Road information
* Target house count

The system generates suggested HLBs.

The default target is approximately:

```text
250 Houses / Buildings per HLB
```

The target is configurable and is not hard-coded.

The generated result can be reviewed and edited before approval.

The initial implementation will focus on GIS and optimization algorithms rather than unnecessarily complex machine-learning models.

---

### 2. HLB Review and Approval

Generated HLBs can be:

* Reviewed
* Edited
* Split
* Merged
* Validated
* Approved

The system checks:

* House count
* Boundary containment
* Geographic continuity
* Unassigned houses
* Duplicate house assignments
* Very large or very small HLBs
* Geographic fragmentation

AI-generated HLBs are suggestions only.

Final approval belongs to the Deputy Tahsildar.

---

### 3. Enumerator Assignment

After a Layout is approved:

```text
Layout
   ↓
Supervisor
   ↓
HLBs
   ↓
Enumerators
```

Each HLB receives one primary Enumerator.

The backend enforces these assignments.

---

### 4. Offline Fieldwork

The Enumerator application is designed to work even when internet connectivity is unavailable.

Local data may include:

* Assigned HLB
* HLB boundary
* House/building list
* House status
* Household records
* Revisit records
* GPS data
* Pending synchronization operations

When connectivity returns, pending changes are synchronized with the server.

---

### 5. GPS and Boundary Monitoring [Phase 11]

The application captures authentic device GPS observations to determine whether the Enumerator is inside or outside the assigned HLB boundary, while providing non-blocking operational guidance and coverage metrics.

```text
Device GPS
    ↓
Validate coordinate + accuracy
    ↓
Point-in-HLB check (Ray-Casting) + Distance to Boundary
    ↓
Inside / Outside / Boundary Uncertain / Unknown
    ↓
Fieldwork UI indication & Leaflet Map Overlay

Fieldwork Coverage:
Assigned HLB Buildings → Fieldwork status (COMPLETED + LOCKED) → Coverage %
```

Key principles and implementation details:
* **Authentic Device GPS Source**: Captured exclusively via device APIs (`expo-location`); coordinates and horizontal accuracy are never fabricated.
* **Accuracy Tiers**: `GOOD` ($\le 25\text{ m}$), `POOR` ($> 25\text{ m}$), and `UNKNOWN` ($> 100\text{ m}$ or unavailable). UI displays `±X m`.
* **Point-in-Polygon & Uncertainty Handling**: Ray-casting containment test combined with geodesic/metric distance $D$ to boundary segments. When $D \le R$ (where $R$ is GPS accuracy radius), status is classified as `BOUNDARY_UNCERTAIN` instead of making a false claim.
* **Non-Blocking Outside Warning**: If an Enumerator is outside their assigned HLB, a clear warning banner (`⚠ Outside assigned HLB`) is displayed. The warning does not lock the application, delete data, or invalidate legitimate fieldwork recording.
* **Fieldwork Coverage Indicators**: Progress percentage is strictly calculated from building fieldwork statuses (`(completed + locked) / total * 100`).
* **Offline Storage & Phase 9 Synchronization**: Observations are persisted locally in SQLite (`offline_gps_logs`) and enqueued in `sync_queue` (`GPS_LOG`) for batch upload to `/api/v1/sync`.
* **Important Rule**: **"GPS observations indicate field location but do not prove household enumeration completion."** Physical presence inside an HLB does not automatically complete any building or submit household data.

---

### 6. Route Optimization

The Enumerator can receive an optimized route based on:

* Assigned HLB
* Pending houses
* House coordinates
* Current location
* Road/network information

Completed houses are excluded from the route.

Locked houses can be moved to the revisit list.

The route must remain within the assigned HLB.

---

### 7. Offline Voice Assistant

The initial voice assistant will support:

* Tamil
* English

Example:

```text
Voice:
"இந்த வீட்டில் நான்கு பேர் இருக்கிறார்கள்."

Detected:

Household Members = 4
```

The Enumerator must confirm the extracted information before it is saved.

The intended processing flow is:

```text
Voice
  ↓
Speech Recognition
  ↓
Text
  ↓
Field Extraction
  ↓
Structured Data
  ↓
Enumerator Confirmation
  ↓
Save
```

---

### 8. Supervisor Monitoring

The Supervisor can monitor:

* HLB progress
* Enumerator progress
* Completed houses
* Remaining houses
* Locked houses
* Revisit records
* GPS coverage
* Boundary events
* Last synchronization time

Example:

```text
HLB-001   E001   100%
HLB-002   E002    80%
HLB-003   E003    60%
HLB-004   E004    30%
HLB-005   E005    90%
```

---

## UI/UX Approach

The application follows a simple, operational UI approach inspired by existing Census field applications.

The design prioritizes:

* Large readable controls
* Simple forms
* Clear labels
* Simple navigation
* Strong status indicators
* Offline visibility
* Map-based fieldwork
* Minimal unnecessary animation
* Tamil and English support

The application should feel like a practical government field application rather than a highly decorative consumer application.

### Enumerator UI

The Enumerator's main operations are centered around map-based navigation and structured form entry.

---

## Technology Stack

### Mobile (Android-First)

* React Native with Expo (Expo React Native)
* TypeScript
* React Navigation (Role-based navigation)
* expo-sqlite (Offline field records database)
* Zustand (State management)
* Axios / Fetch (REST API Client)
* expo-secure-store (Credentials/session tokens)
* expo-location (GPS tracking and boundary monitoring)
* react-native-maps (Map rendering)
* React Native Testing Library and Jest (UI/unit testing)

### Backend

* Python
* FastAPI
* REST API
* Poetry (Dependency management)

### Database

* PostgreSQL
* PostGIS

### GIS / AI

* Python
* GeoPandas, Shapely (Spatial analysis & geometry validation)
* Configurable satellite imagery source abstraction & tile services
* Building detection / structure footprint estimation services
* NetworkX (Graph routing optimization)
* scikit-learn where clustering is required

### Maps

* High-resolution Satellite Imagery (Esri World Imagery / configurable provider)
* OpenStreetMap-based street tile overlay
* Leaflet / react-native-maps for interactive mobile visualization
* PostGIS for server-side spatial filtering & spatial indexing

---

## System Architecture

```text
               React Native with Expo Mobile App
                            │
                            │ HTTPS / REST
                            ↓
                         FastAPI
                            │
              ┌─────────────┼─────────────┐
              ↓             ↓             ↓
         PostgreSQL      GIS Engine    Auth/RBAC
         + PostGIS           │
                             ↓
              ┌──────────────┴──────────────┐
              ↓                             ↓
     Satellite Imagery &          AI / Optimization
     Building Detection Service     HLB Engine


Enumerator Device
        │
        ↓
SQLite Local Database
        │
        ↓
Offline Fieldwork
        │
        ↓
Sync Queue
        │
        ↓
FastAPI Backend
```

---

## Database Structure

The main data hierarchy is:

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

Important supporting data includes:

```text
Users
Layout Assignments
HLB Assignments
GPS Tracks
Boundary Events
Routes
Revisits
Sync Operations
Audit Logs
```

PostGIS is used for:

* Boundaries
* House locations
* HLB polygons
* GPS points
* Spatial queries
* Coverage calculations

---

## Security

The backend will enforce:

* Role-based access control
* Secure password hashing
* Protected APIs
* Secure authentication tokens
* Input validation
* Audit logs
* Secure mobile token storage
* HTTPS
* HLB-level Enumerator access control

Passwords will never be stored as plain text.

An Enumerator cannot access another Enumerator's HLB through the API.

---

## Offline Synchronization

The synchronization system uses a local queue.

```text
Field Update
    ↓
Local Database
    ↓
Sync Queue
    ↓
Internet Available
    ↓
Upload
    ↓
Server Validation
    ↓
SYNCED
```

Possible synchronization states:

```text
PENDING
SYNCED
FAILED
CONFLICT
```

Synchronization should be retryable and idempotent.

Local data should not be deleted simply because synchronization failed.

---

## Repository Structure

```text
AI_Enumerator/
├── Docs/                              # Project documentation
│   ├── 01_Project_Requirements.md
│   ├── 02_Technical_Requirements_React_Native.md
│   ├── 03_App_Flow.md
│   ├── 04_UI_UX_Design.md
│   ├── 05_Backend_Schema.md
│   └── 06_Implementation_Plan.md
├── backend/                           # FastAPI backend application
│   ├── app/                           # Main application package
│   │   ├── api/                       # API routers and endpoints
│   │   ├── core/                      # Configuration, security, logging
│   │   ├── models/                    # SQLAlchemy database models
│   │   ├── schemas/                   # Pydantic validation schemas
│   │   ├── services/                  # Business logic services
│   │   ├── repositories/              # Database operations
│   │   ├── gis/                       # Geographic services (GeoPandas, Shapely)
│   │   ├── ai/                        # HLB generation engine
│   │   └── sync/                      # Synchronization handlers
│   ├── migrations/                    # Alembic database migrations
│   ├── tests/                         # Backend test suite (pytest)
│   ├── pyproject.toml                 # Poetry dependencies and tools configuration
│   └── poetry.lock                    # Locked python dependencies
└── mobile/                            # React Native with Expo mobile client (Android-first)
    ├── src/                           # TypeScript source files
    │   ├── app/                       # Application entry and global providers
    │   ├── navigation/                # Role-based React Navigation configuration
    │   ├── core/                      # Reusable services, constants, and database helpers
    │   ├── components/                # Reusable UI components
    │   └── features/                  # Feature-specific modules
    │       ├── authentication/        # Login and session handling
    │       ├── deputy/                # Deputy Tahsildar screens and layouts
    │       ├── supervisor/            # Supervisor screens and assignment
    │       ├── enumerator/            # Enumerator maps, household data entry
    │       ├── maps/                  # react-native-maps modules
    │       ├── households/            # Questionnaire forms and validation
    │       ├── gps/                   # Location services and boundary checking (expo-location)
    │       ├── offline/               # Local expo-sqlite database configurations
    │       ├── sync/                  # Synchronization queue handlers
    │       └── voice/                 # Offline voice assistant logic
    ├── app.json                       # Expo configuration manifest
    ├── package.json                   # NPM dependencies and scripts
    ├── __tests__/                     # Unit and component tests (Jest, RNTL)
    └── tsconfig.json                  # TypeScript compiler settings
```

---

## Development Prerequisites

Before running the application, make sure you have the following installed:

* **Node.js (LTS)** (for Expo Metro bundler)
* **Java Development Kit (JDK 17)** (for Android builds)
* **Android Studio & Android SDK** or **Expo Go** on Android physical device
* **Python (>= 3.13)**
* **Poetry** (Python dependency management)
* **PostgreSQL (>= 15) with PostGIS extension**

---

## Installation Instructions

### 1. Repository Setup
Clone the repository and navigate to the project directory:
```bash
git clone <repository-url>
cd AI_Enumerator
```

### 2. Mobile Setup
Install the mobile npm dependencies:
```bash
cd mobile
npm install
```

### 3. Backend Setup
Install Python dependencies using Poetry:
```bash
cd backend
poetry install --with dev
```

### 4. Database Setup
Create a PostgreSQL database named `ai_enumerator` and enable the PostGIS extension:
```sql
CREATE DATABASE ai_enumerator;
\c ai_enumerator;
CREATE EXTENSION postgis;
```

Copy the example environment file and configure your database settings:
```bash
cp .env.example .env
```

Apply backend database migrations:
```bash
poetry run alembic upgrade head
```

### 5. Database Reset & Mock Data Seeding
To erase all existing data and seed mock data covering all user roles (Deputy Tahsildar, Supervisor, Enumerator) and fieldwork workflows:
```bash
poetry run python -m app.seed
```
*Note: To seed without resetting existing tables, run `poetry run python -m app.seed --no-reset`.*

#### Preconfigured Demo Accounts:
* **Deputy Tahsildar**: `username: deputy` | `password: password123`
* **Supervisor**: `username: supervisor` | `password: password123`
* **Supervisor 2**: `username: supervisor2` | `password: password123`
* **Enumerator 1**: `username: enumerator` | `password: password123` *(Assigned to Arasur HLB-001)*
* **Enumerator 2**: `username: enumerator2` | `password: password123` *(Assigned to Arasur HLB-002)*
* **Enumerator 3 & 4**: `username: enumerator3` / `enumerator4` | `password: password123` *(Available for assignment)*

---

## Running the Application

### 1. Running the Backend
Start the FastAPI development server:
```bash
cd backend
poetry run uvicorn app.main:app --reload
```
The API documentation will be available at `http://localhost:8000/docs`.

### 2. Running the Mobile Application
Start the Expo development server:
```bash
cd mobile
npx expo start
```

You can open the app by:
- Scanning the QR code with **Expo Go** on an Android device.
- Pressing `a` to open in an Android Emulator.
- Pressing `w` or running `npm run web` to open the Web preview.

---

## Testing Instructions

### Backend Tests
Run the Python test suite using pytest:
```bash
cd backend
poetry run pytest
```

### Mobile Tests
Run mobile tests using Jest and React Native Testing Library:
```bash
cd mobile
npm test
```

---

## Development Workflow

1. **Local Database Configuration**: Ensure that the database connection string in `backend/.env` is configured correctly.
2. **Offline Mode Testing**: To test the offline-first capability, run the application, sign in as an Enumerator, download the assigned HLB block, and disconnect the internet connection. Completed/locked houses are recorded locally in `expo-sqlite` and synchronized later.
3. **Linting and Formatting**:
   - Backend: Run `poetry run ruff check .` and `poetry run ruff format .`.
   - Mobile: Run `npm run lint`.

---

## Project Documentation

The project includes a knowledge base for the AI coding agent.

```text
Docs/
│
├── 01_Project_Requirements.md
├── 02_Technical_Requirements_React_Native.md
├── 03_App_Flow.md
├── 04_UI_UX_Design.md
├── 05_Backend_Schema.md
└── 06_Implementation_Plan.md
```

Recommended reading order:

```text
Project Requirements
        ↓
Technical Requirements
        ↓
App Flow
        ↓
UI/UX Design
        ↓
Backend Schema
        ↓
Implementation Plan
```

These documents define the current baseline architecture and requirements.

Government-specific rules, questionnaire fields, administrative hierarchy, and other official requirements should be added only after verification from authoritative sources.

---

## Current Development Status

This project is currently under development.

The initial focus is on building the core workflow:

```text
Deputy Tahsildar
      ↓
Village/Ward
      ↓
Layout
      ↓
HLBs
      ↓
Supervisor
      ↓
Enumerator
      ↓
Household Fieldwork
      ↓
Offline Sync
      ↓
Progress Monitoring
```

Advanced AI capabilities will be integrated progressively after the core workflow is stable.

---

## Project Goal

The long-term goal is to create a practical field assistant that combines:

```text
Census-style Field UX
        +
GIS
        +
AI-assisted HLB Planning
        +
Offline-first Mobile App
        +
GPS Monitoring
        +
Route Optimization
        +
Voice Assistance
        +
Supervisor Monitoring
```

The system is intended to **assist census field staff**, not replace authorized human decision-making.

In particular, layout generation remains subject to Deputy Tahsildar review and approval.

---

## Disclaimer

This is a project under development and is not an official Government of India Census application.

The application is intended as a technology project/prototype for exploring how AI, GIS, offline mobile applications, and field-work tools can support census-related operations.

Official census procedures, data fields, rules, terminology, and administrative requirements should always be verified against authoritative government sources before being used in a real deployment.

---

## License

Add the project's license here when the licensing decision has been finalized.
