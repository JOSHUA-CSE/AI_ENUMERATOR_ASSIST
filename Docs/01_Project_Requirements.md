# AI-Enumerator Assistant — Project Requirement Document

## 1. Project Overview

**Project Name:** AI-Enumerator Assistant

AI-Enumerator Assistant is a **mobile application** designed to help three levels of census field staff plan, assign, perform, and monitor census fieldwork:

* Deputy Tahsildar
* Supervisor
* Enumerator

The application is not intended to replace the official census system. Its purpose is to reduce manual work, improve field coordination, reduce missed households, and make field progress easier to monitor.

The core workflow is:

```text
Village / Ward
      ↓
     Layout
      ↓
Divide into Blocks
      ↓
Each Block ≈ 250 Houses / Buildings
      ↓
Supervisor
      ↓
Number of Enumerators = Number of Blocks
      ↓
One Enumerator → One Block
```

---

# 2. Problem Statement

Census field staff need to:

* Select a village/ward for fieldwork
* Create a layout for the selected village/ward
* Divide the layout into blocks
* Ensure each block contains approximately 250 houses/buildings
* Assign the complete layout to the Supervisor responsible for that area
* Assign one Enumerator to each block
* Locate and visit houses/buildings
* Handle locked houses and revisits
* Track completed and remaining houses
* Check whether the assigned block has been fully covered
* Monitor Enumerator progress
* Prepare progress information

The application combines these activities into one role-based mobile application.

---

# 3. User Roles

## 3.1 Deputy Tahsildar

### Primary responsibility

**Select a village/ward, create its layout, divide it into blocks, and assign the layout to the responsible Supervisor.**

The Deputy Tahsildar can:

* Securely login
* Select a village/ward
* View the village/ward on a map
* View buildings/houses
* Set the target block size
* Generate blocks automatically
* Ensure each block contains approximately **250 houses/buildings**
* Review generated blocks
* Edit block boundaries
* Split a block
* Merge blocks
* Add/remove houses from a block when required
* View house/building count in each block
* Approve the final block division
* Identify the Supervisor responsible for the selected village/ward
* Assign the complete layout to that Supervisor
* View the required number of Enumerators
* View overall progress

### Important Layout Rule

A **village/ward is treated as one layout**.

For example:

```text
Village A
Total Houses/Buildings = 1,000

        ↓

Layout: Village A

        ↓

Block 1 → 250
Block 2 → 250
Block 3 → 250
Block 4 → 250

        ↓

4 Blocks

        ↓

Supervisor

        ↓

4 Enumerators

        ↓

Enumerator 1 → Block 1
Enumerator 2 → Block 2
Enumerator 3 → Block 3
Enumerator 4 → Block 4
```

The target is approximately 250 houses/buildings per block. The system should allow the authorized Deputy Tahsildar to review and adjust blocks when geographic boundaries, roads, buildings, or other field conditions make an exact 250 count impractical.

---

## 3.2 Supervisor

### Primary responsibility

**Manage the Enumerators assigned to the blocks of the Supervisor's layout and monitor their fieldwork.**

The Supervisor can:

* Securely login
* View assigned village/ward layout
* View all blocks in the layout
* View houses/buildings in each block
* View the number of blocks
* View the required number of Enumerators
* Assign one Enumerator to each block
* View Enumerator status
* View completed and remaining houses/buildings
* View locked houses
* View revisit requirements
* View GPS coverage
* Identify possible missed areas
* Monitor Enumerator progress
* Review completed fieldwork

### Enumerator Assignment Rule

The number of Enumerators required for a layout is determined by the number of blocks.

```text
Number of Blocks
       =
Number of Enumerators Required
```

Example:

```text
Village/Ward
     ↓
8 Blocks
     ↓
Supervisor
     ↓
8 Enumerators required
```

Each Enumerator must be assigned to one specific block.

```text
Enumerator 1 → Block 1
Enumerator 2 → Block 2
Enumerator 3 → Block 3
Enumerator 4 → Block 4
Enumerator 5 → Block 5
Enumerator 6 → Block 6
Enumerator 7 → Block 7
Enumerator 8 → Block 8
```

The system should prevent assigning two Enumerators to the same block unless the Supervisor explicitly performs a supported reassignment.

---

## 3.3 Enumerator

### Primary responsibility

**Complete the fieldwork for the block assigned to the Enumerator.**

The Enumerator can:

* Securely login
* View assigned village/ward
* View assigned block
* Download assigned block for offline use
* View houses/buildings on a map
* Get an optimized route within the assigned block
* Record household information
* Use voice assistance
* Mark houses/buildings as completed
* Mark houses/buildings as locked
* Record/recommend revisit
* Record GPS location
* Receive a warning when approaching or crossing the block boundary
* Work offline
* Synchronize data when internet returns

### Enumerator Boundary Rule

An Enumerator should normally work **only inside the assigned block**.

If the Enumerator moves outside the assigned block:

```text
Enumerator GPS
       ↓
Outside assigned block?
       ↓
YES
       ↓
Show warning
```

Example:

> **You are outside your assigned block. Please return to your assigned area.**

The Supervisor should also be able to see such boundary-crossing events.

---

# 4. Core Features

## FR-01 — AI-Assisted Layout and Block Generation

### User

Deputy Tahsildar

### Input

* Village/ward
* Administrative boundary
* Building/house locations
* Road information
* Target block size

### Default Target

**250 houses/buildings per block**

The target should be configurable by an authorized user, but the default project requirement is **250**.

### Process

```text
Select Village/Ward
        ↓
Load Houses/Buildings
        ↓
Load Roads
        ↓
Identify Geographic Boundary
        ↓
AI/GIS Block Generation
        ↓
Create Blocks
        ↓
Target ≈ 250 Houses/Buildings per Block
        ↓
Validate Blocks
        ↓
Deputy Tahsildar Review
        ↓
Edit if Required
        ↓
Approve
```

### Output

The system should generate:

* Number of blocks
* Block boundaries
* Houses/buildings belonging to each block
* House/building count per block
* Block ID
* Layout ID
* Validation warnings

Example:

```text
LAYOUT: Village A

Total Houses/Buildings: 1,240

Block 01 → 248
Block 02 → 252
Block 03 → 251
Block 04 → 245
Block 05 → 244

Total Blocks → 5
```

The system should prioritize geographic continuity and practical field boundaries rather than blindly forcing every block to exactly 250.

---

# 5. FR-02 — Supervisor and Enumerator Assignment

After the Deputy Tahsildar approves the layout:

```text
Approved Village/Ward Layout
            ↓
Identify Responsible Supervisor
            ↓
Assign Layout to Supervisor
            ↓
Count Blocks
            ↓
Required Enumerators = Block Count
            ↓
Supervisor assigns Enumerators
            ↓
One Enumerator per Block
```

Example:

```text
Layout: Village A

Blocks:
B001
B002
B003
B004
B005
B006

Total Blocks = 6

Supervisor:
S001

Required Enumerators = 6

E001 → B001
E002 → B002
E003 → B003
E004 → B004
E005 → B005
E006 → B006
```

The system should clearly show:

```text
Total Blocks:              6
Enumerators Required:      6
Enumerators Assigned:      6
Assignment Status:         Complete
```

If only 5 Enumerators are assigned:

```text
Total Blocks:              6
Enumerators Required:      6
Enumerators Assigned:      5

⚠ 1 Enumerator Required
```

The Supervisor should not be able to mark the assignment as complete until every block has an Enumerator, unless an authorized exception mechanism is introduced.

---

# 6. FR-03 — Route Optimization

### User

Enumerator

The route is optimized **only inside the Enumerator's assigned block**.

The system should consider:

* Houses/buildings in the block
* Current Enumerator location
* Road/network information
* Completed houses
* Locked houses
* Remaining houses

The goal is to:

* Reduce walking/travel distance
* Reduce backtracking
* Ensure all assigned houses/buildings are covered
* Avoid unnecessary movement

Example:

```text
Block B001

Start
 ↓
House 001
 ↓
House 002
 ↓
House 008
 ↓
House 009
 ↓
House 015
 ↓
...
 ↓
Last Assigned House
```

If a house is locked:

```text
House 008
    ↓
LOCKED
    ↓
Revisit List
    ↓
Continue Route
```

The route must not intentionally include houses from another Enumerator's block.

---

# 7. FR-04 — GPS Coverage Verification

The system records Enumerator GPS movement and compares:

* Assigned block boundary
* Expected houses/buildings
* Completed houses/buildings
* Enumerator GPS movement
* Enumerator boundary crossings

### Boundary Monitoring

If the Enumerator crosses the assigned block boundary:

```text
GPS Location
     ↓
Outside Assigned Block
     ↓
Enumerator Warning
     +
Supervisor Event
```

Example:

```text
⚠ BLOCK B003

You have moved outside your
assigned block.

Please return to Block B003.
```

### Coverage

The system should identify:

* Completed houses
* Remaining houses
* Locked houses
* Revisit houses
* Possible uncovered areas
* GPS movement outside the block

Example:

```text
BLOCK B003

Total Houses       247
Completed          225
Remaining           22
Locked               5

House Coverage      91%
GPS Coverage        94%

Possible missed area detected
```

GPS coverage is an indicator of field movement and must not automatically be treated as proof that a household interview was completed.

---

# 8. FR-05 — Offline Multilingual Voice Assistant

The Enumerator must be able to use voice assistance without continuous internet connectivity.

Initial prototype languages:

* Tamil
* English

Example:

Voice:

> "இந்த வீட்டில் நான்கு பேர் இருக்கிறார்கள்."

Structured result:

```text
Household members = 4
```

Voice:

> "இந்த வீடு வாடகைக்கு உள்ளது."

Structured result:

```text
Ownership = Rented
```

The initial prototype should focus on Tamil and English.

The extracted information must be shown to the Enumerator for confirmation before important information is saved.

---

# 9. FR-06 — Supervisor Live Dashboard

The Supervisor dashboard should show the complete layout and individual block progress.

Example:

```text
VILLAGE A

Total Blocks: 5
Total Houses: 1,240

B001  ██████████ 100% ✓
B002  ████████░░  80%
B003  ██████░░░░  60%
B004  ███░░░░░░░  30%
B005  █████████░  90%
```

Enumerator status:

```text
E001 → B001 → 🟢 Active → 100%
E002 → B002 → 🟢 Active →  80%
E003 → B003 → 🟢 Active →  60%
E004 → B004 → 🟡 Offline → 30%
E005 → B005 → 🟢 Active →  90%
```

The Supervisor should be able to open a block and see its detailed progress.

---

# 10. End-to-End Workflow

```text
                    DEPUTY TAHSILDAR
                           │
                           ▼
                  Select Village / Ward
                           │
                           ▼
                     Create Layout
                           │
                           ▼
                 Load Houses/Buildings
                           │
                           ▼
                  AI Block Generation
                           │
                           ▼
               Target ≈ 250 per Block
                           │
                           ▼
                    Review / Edit
                           │
                           ▼
                       Approve
                           │
                           ▼
               Identify Responsible
                    Supervisor
                           │
                           ▼
                 Assign Layout
                    to Supervisor
                           │
                           ▼
                      SUPERVISOR
                           │
                           ▼
                    View Blocks
                           │
                           ▼
             Number of Blocks = N
                           │
                           ▼
          Required Enumerators = N
                           │
                           ▼
              Assign One Enumerator
                    to Each Block
                           │
                           ▼
                     ENUMERATOR
                           │
                           ▼
                 Download Block
                           │
                           ▼
                  View Block Map
                           │
                           ▼
                  Optimize Route
                           │
                           ▼
                  Visit Houses
                           │
                  ┌────────┴────────┐
                  ▼                 ▼
              Completed          Locked
                  │                 │
                  │                 ▼
                  │              Revisit
                  │                 │
                  └────────┬────────┘
                           ▼
                     GPS Tracking
                           │
                           ▼
               Boundary Monitoring
                           │
                           ▼
                 Offline Data Sync
                           │
                           ▼
                      SUPERVISOR
                           │
                           ▼
                 Review Block Status
                           │
                           ▼
                 Review Layout Status
```

---

# 11. MVP Requirements

## Deputy Tahsildar

* Login
* Select village/ward
* View map
* View houses/buildings
* Generate blocks
* Target approximately 250 houses/buildings per block
* Review block division
* Edit blocks
* Approve layout
* Assign layout to responsible Supervisor

## Supervisor

* Login
* View assigned village/ward layout
* View blocks
* View block house/building counts
* See required Enumerator count
* Assign one Enumerator to each block
* View Enumerator status
* View block progress
* View GPS coverage
* View boundary-crossing events

## Enumerator

* Login
* View assigned block
* View map
* View houses/buildings
* GPS tracking
* Boundary-crossing warning
* Mark completed/locked
* Revisit list
* Offline local storage
* Sync

The voice assistant and advanced route optimization can be added after the core workflow is working.

---

# 12. Important Business Rules

These rules are central to the application.

### Rule 1 — Village/Ward is the Layout

```text
One Village/Ward
       ↓
One Layout
```

### Rule 2 — Layout is Divided into Blocks

```text
Layout
 ↓
Block 1
Block 2
Block 3
...
Block N
```

### Rule 3 — Block Target

```text
Target ≈ 250 Houses/Buildings per Block
```

250 is the default target, not an unchangeable technical constant.

### Rule 4 — Enumerator Count

```text
Number of Blocks
       =
Number of Enumerators Required
```

### Rule 5 — One Enumerator per Block

```text
Block 1 → Enumerator 1
Block 2 → Enumerator 2
Block 3 → Enumerator 3
...
Block N → Enumerator N
```

### Rule 6 — Enumerator Boundary

An Enumerator is responsible only for the assigned block.

### Rule 7 — Boundary Warning

If the Enumerator's GPS position moves outside the assigned block, the application must warn the Enumerator and record the event for Supervisor monitoring.

### Rule 8 — Complete Coverage

The system should track whether all houses/buildings assigned to the block have been:

* Completed
* Locked and scheduled for revisit
* Otherwise accounted for

### Rule 9 — Human Approval

AI-generated blocks are **suggestions**. The Deputy Tahsildar has final authority to review, edit, and approve them.

### Rule 10 — Offline Fieldwork

The Enumerator must be able to continue core fieldwork without internet and synchronize later.

---

# 13. Non-Functional Requirements

* Role-based access control
* Secure authentication
* Offline-first Enumerator workflow
* Reliable synchronization
* Clear error messages
* Low-bandwidth operation
* Location permission handling
* Data validation
* Audit-friendly status changes
* Maintainable architecture
* Accurate block-to-Enumerator assignment
* Reliable GPS boundary monitoring
* Efficient map rendering

---

# 14. Product Principle

The application should assist census staff rather than remove human approval.

The central operating model is:

```text
Deputy Tahsildar
      ↓
Village/Ward Layout
      ↓
AI-Assisted Block Division
      ↓
≈250 Houses/Buildings per Block
      ↓
Supervisor
      ↓
One Enumerator per Block
      ↓
Block-level Fieldwork
      ↓
GPS + House Coverage
      ↓
Supervisor Monitoring
```

Important actions such as layout approval and block modification remain under the authorized officer's control.
