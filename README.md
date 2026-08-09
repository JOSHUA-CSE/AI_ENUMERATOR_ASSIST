# AI-Enumerator Assistant

AI-Enumerator Assistant is a mobile application designed to support census field staff in planning, assigning, conducting, and monitoring fieldwork.

The project focuses on reducing manual work during census field operations while keeping important decisions under the control of authorized officers.

The application is designed around three roles:

* **Deputy Tahsildar**
* **Supervisor**
* **Enumerator**

The main idea is to combine a simple census-style field application with GIS, offline support, GPS, route optimization, and AI-assisted features.

---

## Project Overview

The basic workflow of the application is:

```text
Village / Ward
      ↓
    Layout
      ↓
Houselisting Blocks (HLBs)
      ↓
≈250 Houses / Buildings per HLB
      ↓
   Supervisor
      ↓
One Enumerator per HLB
      ↓
Household Fieldwork
      ↓
Offline Sync
      ↓
Supervisor Monitoring
```

A Deputy Tahsildar selects a village or ward and creates a layout for it. The layout is divided into Houselisting Blocks (HLBs), with approximately 250 houses/buildings per HLB by default.

After the layout is reviewed and approved, it is assigned to a Supervisor. The Supervisor assigns one Enumerator to each HLB.

The Enumerator then works within the assigned HLB, records household information, captures GPS information, handles locked houses and revisits, and synchronizes the data when connectivity is available.

---

## Main Objectives

The project aims to:

* Reduce manual work in census field planning
* Assist in creating Houselisting Blocks
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

The Deputy Tahsildar is responsible for planning and approving the field layout.

Main responsibilities:

* Select Village/Ward
* Create Layout
* View houses/buildings
* Generate HLBs
* Review generated HLBs
* Edit HLB boundaries
* Split or merge HLBs
* Validate HLBs
* Approve the Layout
* Assign the Layout to a Supervisor
* Monitor overall progress

The AI can suggest HLBs, but the Deputy Tahsildar remains the final approver.

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

### 5. GPS and Boundary Monitoring

The application records Enumerator GPS movement.

The system can compare the Enumerator's location with the assigned HLB boundary.

Example:

```text
✓ INSIDE ASSIGNED HLB
```

or:

```text
⚠ OUTSIDE ASSIGNED HLB
```

Boundary events are recorded for Supervisor monitoring.

GPS is treated as a field coverage indicator and not as proof that a household was interviewed.

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

The Enumerator's main operations are centered around:

```text
Assigned HLB
     ↓
Map
     ↓
House
     ↓
Household Form
     ↓
Save
     ↓
Next House
```

---

## Technology Stack

### Mobile

* Flutter
* Dart
* Android-first
* SQLite/local database

### Backend

* Python
* FastAPI
* REST API

### Database

* PostgreSQL
* PostGIS

### GIS / AI

* Python
* GeoPandas
* Shapely
* NetworkX
* scikit-learn where required

### Maps

* OpenStreetMap-based map data
* MapLibre or another suitable Flutter map SDK

---

## System Architecture

```text
                    Flutter Mobile App
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
                      AI/GIS Services


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

## Development Approach

The project is being developed in phases.

```text
1. Project Setup
2. Authentication
3. Role Dashboards
4. Administrative Areas
5. Maps
6. Houses / Buildings
7. Layout Creation
8. HLB Generation
9. HLB Review / Approval
10. Supervisor Assignment
11. Enumerator Assignment
12. Offline Field Workflow
13. Household Records
14. Synchronization
15. GPS Boundary Monitoring
16. Supervisor Progress
17. Route Optimization
18. GPS Coverage
19. Voice Assistant
20. Testing
21. Security
22. Android Release
```

The core field workflow will be completed before adding advanced AI features.

---

## Development Philosophy

This project is being built as a real software project rather than a UI prototype.

The code should be:

* Readable
* Modular
* Maintainable
* Testable
* Consistent
* Properly structured

Generated code should follow normal human software development practices.

Avoid:

* Huge files
* Huge functions
* Repeated code
* Unnecessary abstractions
* Hard-coded business rules
* Fake implementations
* Unused dependencies
* Unused variables
* Excessive comments
* Unclear naming

The project should be understandable to another developer without needing to know that AI was used during development.

---

## Project Documentation

The project includes a knowledge base for the AI coding agent.

```text
knowledge-base/
│
├── 01_Project_Requirements.md
├── 02_Technical_Requirements.md
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
