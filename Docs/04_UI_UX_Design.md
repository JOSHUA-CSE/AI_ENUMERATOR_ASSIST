# AI-Enumerator Assistant — UI/UX Design Document

## 1. Design Goal

AI-Enumerator Assistant is a mobile application for census field staff.

The UI/UX should be inspired by the **simple, operational design approach used in the official Census 2027 digital fieldwork system**, while adding the project's own AI, GIS, GPS, route, and offline features.

The official Census 2027 HLO application is designed for field data collection, supports offline operation, direct data transmission, and multiple regional languages. Official Census information also describes Houselisting Block creation through a mapping application and progress monitoring through a management dashboard.

Therefore, the application should prioritize:

* Simple navigation
* Clear forms
* Large readable controls
* Fast field data entry
* Map-based fieldwork
* Offline operation
* Clear synchronization status
* Clear block/house information
* Minimal unnecessary decoration
* Tamil and English support initially
* Easy use outdoors

The UI should feel like a **government fieldwork application**, not a consumer social-media application.

### Technical Implementation Notes
* Built with **React Native with Expo** (Expo React Native) and TypeScript.
* Maps rendered using **react-native-maps** (with light tile overlays and high-contrast boundary polygons).
* GPS accuracy and boundary status indicators powered by **expo-location**.
* Local field state and offline questionnaire persistence backed by **expo-sqlite**.

---

# 2. Core UI/UX Concept

The complete project hierarchy must be reflected in the interface.

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
```

The application must clearly distinguish between:

### Layout

The complete selected village/ward.

### Houselisting Block (HLB)

A subdivision of the layout containing approximately 250 houses/buildings.

### House/Building

An individual field location.

### Enumerator

The field worker responsible for one assigned HLB.

The Enumerator should primarily interact with the **assigned HLB**, not the entire village/ward.

---

# 3. UI/UX Design Direction

The design should follow this principle:

```text
Official Census-style UI
          +
Simple field forms
          +
Clear operational actions
          +
Map/GIS
          +
AI assistance
          +
Offline fieldwork
```

Avoid making the application visually complicated.

### Prefer

* White/light backgrounds
* Strong government-style primary color
* Simple top bars
* Large buttons
* Clear labels
* Simple icons
* Numbered questions
* Dropdowns
* Progress indicators
* Simple maps
* Clear warning messages
* Clear sync indicators

### Avoid

* Glassmorphism
* Excessive gradients
* Complex animations
* Futuristic dashboards
* Excessive cards
* Small floating controls
* Decorative elements that reduce readability
* Too many charts on one screen

The application should prioritize **field efficiency over visual decoration**.

---

# 4. Design System

## 4.1 Colors

Use a restrained professional palette.

### Primary

Government/administrative blue.

Used for:

* App header
* Primary buttons
* Selected navigation
* Important actions

### Success

Green.

Used for:

* Completed
* Synced
* Valid
* Inside assigned HLB

### Warning

Amber/orange.

Used for:

* Locked houses
* Pending sync
* Low GPS accuracy
* Validation warnings

### Error

Red.

Used for:

* Failed synchronization
* Invalid data
* Boundary violations requiring attention
* Critical errors

### Neutral

White, light gray, dark gray.

Used for:

* Backgrounds
* Cards
* Form fields
* Secondary information

Color must never be the only way to communicate a status.

Example:

```text
✓ COMPLETED
⚠ LOCKED
● PENDING
⚠ OUTSIDE HLB
✓ SYNCED
```

---

# 5. Typography

Use a highly readable sans-serif font.

The application must support:

* English
* Tamil

The architecture should support additional Indian languages later.

Recommended hierarchy:

```text
Screen Title

Section Title

Question / Field Label

Body Text

Helper Text
```

Important information should use larger text:

* HLB ID
* House number
* House count
* Progress
* Sync status
* GPS status

---

# 6. Localization

The application should be designed for multilingual operation from the beginning.

Initial prototype:

```text
English
தமிழ்
```

The official Census 2027 mobile system supports 16 regional languages, so the project should avoid hard-coding text into UI components.

Use localization files such as:

```text
en.json
ta.json
```

Example:

```json
{
  "login": "Login",
  "assigned_hlb": "Assigned HLB",
  "completed": "Completed",
  "locked": "Locked",
  "sync": "Sync"
}
```

Tamil:

```json
{
  "login": "உள்நுழைவு",
  "assigned_hlb": "ஒதுக்கப்பட்ட HLB",
  "completed": "முடிந்தது",
  "locked": "பூட்டப்பட்டது",
  "sync": "ஒத்திசைவு"
}
```

---

# 7. Touch and Field-Use Design

The application will be used outdoors.

Important controls should be large.

Examples:

```text
[ START VISIT ]

[ SAVE ]

[ MARK COMPLETED ]

[ MARK LOCKED ]

[ ADD REVISIT ]

[ START ROUTE ]

[ SYNC DATA ]
```

The Enumerator should not need precise finger movements to use important functions.

---

# 8. Common UI Components

Create reusable components.

## Navigation

* App bar
* Bottom navigation
* Back button
* Page title

## Census Components

* Layout card
* HLB card
* House/building card
* Progress indicator
* Status badge
* Enumerator card
* Coverage card
* GPS status
* Boundary warning
* Revisit card
* Sync indicator

## Forms

* Text field
* Number field
* Dropdown
* Radio buttons
* Checkbox
* Date field
* Confirmation dialog

## States

* Loading
* Empty
* Error
* Offline
* Syncing
* Completed

---

# 9. Login Screen

The login screen should remain simple.

```text
--------------------------------
       AI-Enumerator Assistant
--------------------------------

        Mobile / User ID

        [______________]

        Password

        [______________]

        [ LOGIN ]

--------------------------------

Network:
● Online
--------------------------------
```

The role should not be manually selected.

The backend determines:

```text
DEPUTY_TAHSILDAR
SUPERVISOR
ENUMERATOR
```

and opens the appropriate dashboard.

---

# 10. Deputy Tahsildar UI

The Deputy Tahsildar is responsible for:

```text
Village/Ward
      ↓
Layout
      ↓
HLB Generation
      ↓
Review
      ↓
Approval
      ↓
Supervisor Assignment
```

---

# 11. Deputy Tahsildar Dashboard

The dashboard should provide a simple operational summary.

```text
--------------------------------
       Deputy Tahsildar
--------------------------------

Villages / Wards              12

Layouts                       12

Awaiting Review                2

Approved                       8

In Progress                    4

--------------------------------

[ CREATE LAYOUT ]

--------------------------------

Recent Layouts

Village A       Approved
Village B       In Review
Village C       In Progress
--------------------------------
```

The main action should be:

**CREATE LAYOUT**

---

# 12. Village/Ward Selection

The Deputy Tahsildar selects a village/ward.

```text
--------------------------------
Select Village / Ward
--------------------------------

Search:
[ Village name ]

--------------------------------

Village A
Estimated Buildings: 1,240

Village B
Estimated Buildings: 980

Village C
Estimated Buildings: 1,530

--------------------------------
```

Selecting a village opens its **Administrative Area Map**.

---

# 12.1 Administrative Area Map UI (Deputy Tahsildar)

The administrative-area map is designed for maximum clarity, avoiding visual clutter from hundreds of unmanaged red dots.

### Default View
* **Base Map**: High-resolution Satellite Imagery (Esri World Imagery default)
* **Overlay**: Administrative boundary polygon with semi-transparent fill (`#0284C7` fill opacity 0.22) and bright blue outline (`#38BDF8`).

### 4 Zoom-Dependent Stages

```text
1. Overview (Far Zoom: Zoom < 14):
   - Village/Ward boundary polygon only
   - Centered area name badge ("Arasur")
   - Zero individual marker clutter for a clean area overview

2. House/Building Density (Medium Zoom: Zoom 14–16):
   - Multi-tier spatial density heatmap (Green → Yellow → Orange → Red)
   - Shows building concentration clusters inside the boundary

3. Cluster View (Closer Zoom: Zoom 16–18):
   - Grouped building cluster badges with counts (e.g., 12, 28, 42)
   - Color-coded by cluster density (Blue <20, Yellow/Green 20–35, Orange/Red 35+)
   - Tapping a cluster zooms in directly to expand smaller clusters

4. Individual Detected Buildings (High Zoom: Zoom > 18):
   - Circular blue pins with white house icon (🏠)
   - Tapping displays detail popup:
     ┌────────────────────────────┐
     │ House                   ℹ  │
     │ ID: H-638401-125           │
     │ Bld: BLD-125 • No: 1/125   │
     │ 11.08250, 77.12350         │
     └────────────────────────────┘
```

### UI Controls
* **Top Controls Bar**:
  - `[ 🔷 Boundary ]` (toggle boundary outline on/off)
  - `[ 🏠 Buildings ]` (toggle building density/clusters/individual markers)
  - `[ 🗺️ Layers ]` (toggle between Satellite and Street Map base layers)
* **Right Floating Tools**:
  - `[ 🎯 ]` Current Location / Recenter
  - `[ ＋ ]` Zoom In
  - `[ − ]` Zoom Out
  - `[ 🗖 ]` Fit Entire Boundary
* **Bottom Information Card**:
  - Title: **Arasur Village** (`VILL-638401`)
  - 3-Column Metrics:
    - **Estimated Buildings**: `🏠 250` (or dynamic detected count)
    - **Area**: `🗺️ 2.46 km²`
    - **Status**: `[Active]` (Green pill badge)

### Map Legend
* `[ 🔷 ]` Village Boundary
* `[ 🟩🟨🟧🟥 ]` Building Density (Low → High)
* `[ 24 ]` Building Cluster (Number = count)
* `[ 🏠 ]` Detected Building (High Zoom)
* `[ 🎯 ]` My Location

---

# 13. Layout Creation Screen

The selected village/ward becomes the layout.

```text
--------------------------------
Create Layout
--------------------------------

Village/Ward:
Arasur Village

Estimated Buildings:
250

Target HLB Size:
[ 250 ]

--------------------------------

[ GENERATE HLBs ]

--------------------------------
```

The default target is:

**approximately 250 houses/buildings per HLB.**

The target should remain configurable.

---

# 14. HLB Generation Screen

The AI/GIS generation screen should be simple.

```text
--------------------------------
Generating HLBs
--------------------------------

Village:
Village A

Houses/Buildings:
1,240

Target:
250 per HLB

--------------------------------

Analyzing:

✓ House locations
✓ Roads
✓ Boundary
✓ Geographic continuity

Generating HLBs...

████████████░░░ 80%

--------------------------------
```

After completion:

```text
Generation Complete

Total HLBs: 5

[ REVIEW HLBs ]
```

The system should not automatically approve the generated HLBs.

---

# 15. HLB Review Screen

This is the main GIS screen for the Deputy Tahsildar.

```text
--------------------------------
HLB Review
--------------------------------

Village A

Houses/Buildings: 1,240
HLBs: 5

--------------------------------
              MAP
--------------------------------

B001
248 Houses

B002
252 Houses

B003
251 Houses

B004
245 Houses

B005
244 Houses

--------------------------------

[ EDIT ]

[ VALIDATE ]

[ APPROVE ]

--------------------------------
```

The map should display:

* Village/ward boundary
* HLB boundaries
* House/building points
* HLB labels

---

# 16. HLB Detail Screen

```text
--------------------------------
HLB B003
--------------------------------

Houses/Buildings: 251

Target: 250

Status:
✓ Valid

--------------------------------
              MAP
--------------------------------

Validation

✓ Inside Layout
✓ No Duplicate Houses
✓ No Unassigned Houses
✓ Geographic Boundary Valid

--------------------------------

[ EDIT HLB ]

[ SPLIT ]

[ MERGE ]

--------------------------------
```

---

# 17. HLB Validation Screen

The system should make validation understandable.

```text
--------------------------------
HLB Validation
--------------------------------

B003

House Count          251 ✓

Boundary             Valid ✓

Continuity           Valid ✓

Unassigned           0 ✓

Duplicates           0 ✓

--------------------------------

Overall Status:
✓ VALID

--------------------------------
```

If there is a problem:

```text
--------------------------------
⚠ VALIDATION WARNING

HLB B003

House Count:
315

Target:
250

Recommended action:
Review HLB boundary.

[ EDIT HLB ]

--------------------------------
```

---

# 18. Layout Approval Screen

Before approval:

```text
--------------------------------
Approve Layout
--------------------------------

Village A

Total Houses:       1,240
Total HLBs:              5

Target / HLB:           250

--------------------------------

B001    248 ✓
B002    252 ✓
B003    251 ✓
B004    245 ✓
B005    244 ✓

--------------------------------

Validation

✓ All houses assigned
✓ No duplicate assignments
✓ HLBs inside layout
✓ HLBs validated

--------------------------------

[ CANCEL ]

[ APPROVE LAYOUT ]

--------------------------------
```

Approval should require confirmation.

---

# 19. Supervisor Assignment Screen

After layout approval:

```text
--------------------------------
Assign Supervisor
--------------------------------

Layout:
Village A

HLBs:
5

Houses/Buildings:
1,240

Supervisor:

[ Select Supervisor ▼ ]

--------------------------------

[ ASSIGN LAYOUT ]

--------------------------------
```

After successful assignment:

```text
✓ Layout Assigned

Supervisor:
S001

HLBs:
5

Required Enumerators:
5
```

---

# 20. Supervisor UI

The Supervisor works with:

```text
Layout
   ↓
HLBs
   ↓
Enumerators
   ↓
Progress
   ↓
Coverage
```

---

# 21. Supervisor Dashboard

```text
--------------------------------
          Supervisor
--------------------------------

Assigned Layouts             4

Active Layouts               3

Completed Layouts            1

--------------------------------

Village A

HLBs                         5

Houses/Buildings          1,240

Completed                   870

Remaining                   370

Coverage                     72%

--------------------------------
```

---

# 22. Supervisor HLB List

```text
--------------------------------
Village A
--------------------------------

Total HLBs:                  5

Required Enumerators:        5

Assigned Enumerators:        5

--------------------------------

B001   E001   100% ✓

B002   E002    80%

B003   E003    60%

B004   E004    30%

B005   E005    90%

--------------------------------
```

The relationship must always be visible:

```text
HLB → Enumerator
```

---

# 23. Enumerator Assignment Screen

The Supervisor assigns one Enumerator to each HLB.

```text
--------------------------------
Enumerator Assignment
--------------------------------

HLBs:                       5

Required Enumerators:       5

Assigned:                   4

--------------------------------

B001 → E001 ✓
B002 → E002 ✓
B003 → E003 ✓
B004 → E004 ✓
B005 → Not Assigned ⚠

--------------------------------

[ ASSIGN ENUMERATOR ]

--------------------------------
```

Show:

```text
Required: 5
Assigned: 4
Remaining: 1
```

The assignment should not be considered complete until every HLB has an Enumerator, unless an authorized exception is introduced.

---

# 24. Enumerator Status Card

```text
--------------------------------
E003

Assigned HLB:
B003

Status:
● Active

Progress:
60%

Completed:
150 / 251

Last Sync:
10:42 AM

GPS:
✓ Inside HLB

--------------------------------
```

Possible states:

```text
● ACTIVE
⚠ OFFLINE
! OUTSIDE HLB
✓ COMPLETED
```

---

# 25. Supervisor Coverage Screen

The coverage map should show:

* Layout boundary
* HLB boundaries
* House/building points
* Enumerator movement
* Possible missed areas
* Boundary events

Legend:

```text
--------------------------------
MAP LEGEND

Layout Boundary
HLB Boundary
House / Building
Enumerator Route
Boundary Event
Possible Missed Area
--------------------------------
```

---

# 26. Enumerator UI

The Enumerator is the main field user.

The interface should follow the simple operational style of a census field application.

The Enumerator's primary working area is:

**Assigned HLB**

---

# 27. Enumerator Home Screen

```text
--------------------------------
          Enumerator
--------------------------------

Village:
Village A

Assigned HLB:
B003

--------------------------------

Houses/Buildings:
251

Completed:
150

Remaining:
101

Locked:
4

Progress:
████████░░░░ 60%

--------------------------------

[ OPEN HLB ]

[ START ROUTE ]

--------------------------------

Sync:
✓ All changes synced

GPS:
✓ Inside HLB
--------------------------------
```

The screen should allow the Enumerator to start fieldwork immediately.

---

# 28. Enumerator Operations Screen

The main Enumerator operations screen should use simple large actions.

```text
--------------------------------
HLB B003
--------------------------------

[ HOUSE / BUILDING ENTRY ]

[ UPDATE DATA ]

[ VIEW SUMMARY ]

[ REVISIT HOUSES ]

[ MAP & ROUTE ]

[ SYNC DATA ]

[ MARK HLB COMPLETE ]

--------------------------------
```

This operational style is intentionally close to the simple task-oriented structure used by official Census field applications.

The official Census 2027 HLO app is designed specifically for enumerators to collect and upload Houselisting data in the field.

---

# 29. Enumerator HLB Screen

```text
--------------------------------
My HLB
--------------------------------

Village:
Village A

HLB:
B003

Houses/Buildings:
251

Completed:
150

Remaining:
101

Locked:
4

--------------------------------

[ OPEN MAP ]

[ VIEW HOUSES ]

[ START ROUTE ]

[ REVISITS ]

--------------------------------
```

---

# 30. Enumerator Map

The map is the primary fieldwork screen.

Show:

* Current GPS location
* Assigned HLB boundary
* Houses/buildings
* House status
* Optimized route
* Next house
* GPS accuracy
* Offline status

```text
--------------------------------
HLB B003

● Current Location

              MAP

HLB Boundary
House Points
Route

Next:
House 151

--------------------------------

[ NAVIGATE ]

--------------------------------
```

The route must only contain houses/buildings inside the assigned HLB.

---

# 31. Route Screen

```text
--------------------------------
Optimized Route
--------------------------------

HLB B003

Remaining:
101 Houses

Estimated Distance:
2.8 km

Next:
House 151

--------------------------------

Start
 ↓
H151
 ↓
H152
 ↓
H158
 ↓
H159
 ↓
...

--------------------------------

[ START ROUTE ]

--------------------------------
```

The route optimization is a project feature added on top of the basic census-style field UI.

---

# 32. House/Building Entry

The entry screen should be form-driven.

```text
--------------------------------
House 102
--------------------------------

Status:
PENDING

--------------------------------

1. Building / House Number

[ 102 ]

2. Household Members

[ 4 ]

3. Ownership

[ Rented ▼ ]

4. Other Required Information

[....................]

--------------------------------

🎙 [ USE VOICE ]

--------------------------------

[ SAVE ]

--------------------------------
```

The exact official questionnaire fields should be added separately after the required questionnaire is finalized.

The official Census 2027 HLO process uses mobile data collection for housing, household amenities and related information, with validation rules built into the mobile application.

---

# 33. Form Navigation

For longer forms:

```text
--------------------------------
Question 5 of 33
--------------------------------

Question text

[ Answer ]

[ Previous ]       [ Next ]
--------------------------------
```

The official HLO operation includes 33 notified questions in Phase I, although the exact questionnaire implementation for this project should follow the requirements selected for the prototype.

The application should support:

* Required-field validation
* Valid value checks
* Conditional questions
* Clear error messages
* Save-and-continue

---

# 34. Voice Assistant

Voice should be an additional input method, not the only way to enter data.

```text
--------------------------------
Voice Assistant
--------------------------------

Language:

[ தமிழ் ] [ English ]

--------------------------------

        🎙
   Tap and Speak

--------------------------------

Recognized:

"இந்த வீட்டில் நான்கு பேர்..."

Detected:

Household Members: 4

--------------------------------

[ CONFIRM ]

[ EDIT ]

[ CANCEL ]

--------------------------------
```

Flow:

```text
Voice
 ↓
Speech Recognition
 ↓
Text
 ↓
Field Extraction
 ↓
Show Result
 ↓
Enumerator Confirms
 ↓
Save
```

The system must never silently save uncertain AI-generated values.

---

# 35. Locked House

```text
--------------------------------
House 102
--------------------------------

Status:

⚠ LOCKED

Reason:

[ No one available ▼ ]

--------------------------------

[ ADD REVISIT ]

[ CONTINUE ROUTE ]

--------------------------------
```

After adding:

```text
✓ Added to Revisit List
```

The Enumerator should be able to continue with the next house.

---

# 36. Revisit Screen

```text
--------------------------------
Revisit Houses
--------------------------------

HLB B003

House 102
Locked
No one available

[ VISIT ]

--------------------------------

House 118
Locked
No one available

[ VISIT ]

--------------------------------
```

Revisit status:

```text
PENDING
COMPLETED
CANCELLED
```

---

# 37. GPS Status

GPS should always provide a simple status.

### Inside HLB

```text
✓ INSIDE ASSIGNED HLB
```

### Poor GPS

```text
⚠ GPS ACCURACY LOW
```

### Outside HLB

```text
⚠ OUTSIDE ASSIGNED HLB

Please return to HLB B003.
```

---

# 38. HLB Boundary Warning

When the Enumerator moves outside the assigned HLB:

```text
--------------------------------
           ⚠ WARNING
--------------------------------

You are outside your
assigned HLB.

Assigned HLB:

B003

Please return to your
assigned area.

[ OK ]

--------------------------------
```

The system should record:

* Enumerator ID
* HLB ID
* GPS location
* Timestamp
* Boundary event

The official Census 2027 system assigns Enumerators to enumeration blocks for house-to-house work; our application extends this concept with explicit GPS boundary monitoring.

---

# 39. GPS Coverage UI

```text
--------------------------------
HLB B003
--------------------------------

Total Houses:        251

Completed:           225

Remaining:            26

Locked:                5

House Coverage:       90%

GPS Coverage:         94%

--------------------------------

Possible Missed Area

⚠ Detected

[ VIEW MAP ]

--------------------------------
```

GPS coverage is only an indicator.

GPS movement must not automatically be treated as proof that a household was interviewed.

---

# 40. Offline UX

Offline operation must be clearly visible.

The official Census 2027 HLO application is explicitly designed as a secure offline mobile application for field data collection.

### Online

```text
● ONLINE
```

### Offline

```text
⚠ OFFLINE

Working with saved data
```

### Offline + Pending Changes

```text
⚠ OFFLINE

12 changes waiting to sync
```

### Syncing

```text
↻ SYNCING

8 / 12 changes
```

### Complete

```text
✓ ALL CHANGES SYNCED
```

Offline status should be visible without taking significant screen space.

---

# 41. Offline Fieldwork

The Enumerator should download the assigned HLB before starting work.

Local data:

```text
Assigned Layout
Assigned HLB
HLB Boundary
House/Building List
House Status
Household Records
Revisit Records
Route
GPS Records
Boundary Events
Pending Sync Operations
```

The Enumerator must be able to continue core fieldwork without internet.

---

# 42. Sync Screen

```text
--------------------------------
Synchronization
--------------------------------

Status:
OFFLINE

Pending Changes:
12

House Records:
8

GPS Records:
3

Boundary Events:
1

--------------------------------

[ SYNC NOW ]

--------------------------------
```

After synchronization:

```text
--------------------------------
Synchronization Complete

✓ 12 Changes Synced

No Pending Changes
--------------------------------
```

---

# 43. Supervisor Progress UI

Progress should be shown at three levels.

## Layout

```text
Village A

1,240 Houses
870 Completed

70% Complete
```

## HLB

```text
B003

251 Houses
225 Completed

90% Complete
```

## House

```text
House 102

✓ Completed
```

This gives the Supervisor both an overall and detailed view.

---

# 44. HLB Completion Screen

The Enumerator should be able to mark an HLB complete only after reviewing its status.

```text
--------------------------------
Complete HLB
--------------------------------

HLB B003

Total Houses:       251
Completed:          246
Locked/Revisit:       5

Pending:              0

--------------------------------

✓ All houses accounted for

--------------------------------

[ MARK HLB COMPLETE ]

--------------------------------
```

If unresolved records remain:

```text
⚠ HLB cannot be completed

5 houses still require action.
```

The Supervisor can then review the HLB.

---

# 45. Layout Completion

The complete layout is finished only after its HLBs are completed/reviewed.

```text
Village A

B001 ✓
B002 ✓
B003 ✓
B004 ✓
B005 ✓

        ↓

LAYOUT COMPLETE
```

---

# 46. Accessibility

The application should support:

* Large text
* High contrast
* Clear icons
* Text labels
* Large touch targets
* Screen-reader-friendly controls where practical
* Tamil
* English
* Clear warnings
* Simple map controls

Do not rely only on color.

---

# 47. Error and Validation UI

The official Census digital approach includes validation rules to improve consistency and accuracy.

Our application should therefore use immediate validation.

Example:

```text
Household Members

[ -1 ]

⚠ Please enter a valid value.
```

Another:

```text
Required Field

⚠ This field cannot be empty.
```

AI block generation:

```text
⚠ BLOCK VALIDATION FAILED

B003 has 315 houses.

Target:
250

[ REVIEW BLOCK ]
```

---

# 48. Main Navigation

## Deputy Tahsildar

```text
Home | Areas | Layouts | Progress | Profile
```

## Supervisor

```text
Home | Layouts | Enumerators | Coverage | Profile
```

## Enumerator

```text
Home | Map | Houses | Revisit | Sync
```

The Enumerator navigation should prioritize:

1. Home
2. Map
3. Houses
4. Revisit
5. Sync

---

# 49. Role-Specific UI Philosophy

## Deputy Tahsildar

UI priority:

```text
MAP
 ↓
LAYOUT
 ↓
HLBs
 ↓
VALIDATION
 ↓
APPROVAL
```

The Deputy needs more GIS and map functionality.

---

## Supervisor

UI priority:

```text
LAYOUT
 ↓
HLBs
 ↓
ENUMERATORS
 ↓
PROGRESS
 ↓
COVERAGE
```

The Supervisor needs monitoring and assignment functionality.

---

## Enumerator

UI priority:

```text
ASSIGNED HLB
 ↓
MAP
 ↓
HOUSE
 ↓
FORM
 ↓
SAVE
 ↓
NEXT HOUSE
```

The Enumerator needs the simplest interface because this is the most repetitive field workflow.

---

# 50. UI/UX Rules

## Rule 1

One main action per screen.

## Rule 2

Use simple operational screens rather than decorative dashboards.

## Rule 3

The application must clearly distinguish:

```text
Layout
HLB
House/Building
```

## Rule 4

The Enumerator should primarily operate inside the assigned HLB.

## Rule 5

The route must only include houses/buildings belonging to the assigned HLB.

## Rule 6

The HLB boundary must always be available for GPS checking.

## Rule 7

Leaving the HLB should produce a clear warning.

## Rule 8

The event should be recorded for Supervisor monitoring.

## Rule 9

AI-generated HLBs must be reviewed and approved by the Deputy Tahsildar.

## Rule 10

AI-generated household information must be confirmed before saving.

## Rule 11

Core Enumerator operations must work offline.

## Rule 12

Sync status must always be understandable.

## Rule 13

Forms should use clear labels, validation, and simple navigation.

## Rule 14

Use Tamil and English from the beginning through a localization system.

## Rule 15

The UI should remain usable on low-end Android devices.

## Rule 16

Do not overload the Enumerator screen with Supervisor or Deputy Tahsildar information.

---

# 51. Final UI/UX Structure

The final product should follow:

```text
                    AI-ENUMERATOR ASSISTANT
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ↓                ↓                ↓
      DEPUTY TAHSILDAR    SUPERVISOR      ENUMERATOR
             │                │                │
             ↓                ↓                ↓
      Village/Ward        Layout          Assigned HLB
             ↓                ↓                ↓
          Layout            HLBs           Map
             ↓                ↓                ↓
       Generate HLBs     Assign E      Route
             ↓                ↓                ↓
       Review / Edit      Monitor       House
             ↓                ↓                ↓
          Validate        Coverage      Form
             ↓                ↓                ↓
          Approve         Revisit      Voice
             ↓                ↓                ↓
     Assign Supervisor     GPS          Complete
                              │                │
                              └───────┬────────┘
                                      ↓
                                  Sync
                                      ↓
                                  Review
```

---

# 52. Final Design Principle

The UI should be:

> **Census-style in operation, GIS-based in planning, AI-assisted in decision making, and offline-first in fieldwork.**

The project should **learn from the official Census 2027 application's field-oriented design rather than attempting to visually copy it**.

The official system already demonstrates the importance of:

* Mobile field collection
* Offline operation
* Houselisting Blocks
* Direct digital submission
* Multilingual operation
* Validation
* Supervisor monitoring
* Mapping for HLB creation

Our application adds:

* AI-assisted HLB generation
* One-Enumerator-per-HLB assignment workflow
* Route optimization
* GPS boundary warnings
* GPS coverage analysis
* Offline voice assistance
* Integrated Deputy Tahsildar → Supervisor → Enumerator workflow

This gives the application a familiar fieldwork experience while preserving the project's own innovation.
