# AI-Enumerator Assistant — App Flow

## 1. Application Entry

```text
Open App
   ↓
Splash Screen
   ↓
Check Saved Session
   ↓
+-------------------------+
| Logged in?              |
+-------------------------+
    | Yes              | No
    ↓                  ↓
Role Dashboard       Login
                         ↓
                    Authenticate
                         ↓
                    Role Check
                         ↓
                    Dashboard
```

The backend determines the user's role.

Supported roles:

```text
DEPUTY_TAHSILDAR
SUPERVISOR
ENUMERATOR
```

The user must only receive screens and operations permitted for their role.

---

# 2. Overall Application Flow

The complete fieldwork flow is:

```text
                    DEPUTY TAHSILDAR
                           ↓
                  Select Village/Ward
                           ↓
                    Create Layout
                           ↓
                 View Houses/Buildings
                           ↓
                 Generate Blocks using AI
                           ↓
             Target ≈ 250 Houses/Buildings
                           ↓
                    Review / Edit
                           ↓
                       Approve
                           ↓
                  Assign Supervisor
                           ↓
                      SUPERVISOR
                           ↓
                    View Layout
                           ↓
                     View Blocks
                           ↓
                 Count Number of Blocks
                           ↓
          Required Enumerators = Block Count
                           ↓
              Assign One Enumerator
                    to Each Block
                           ↓
                     ENUMERATOR
                           ↓
                 View Assigned Block
                           ↓
                Download for Offline Use
                           ↓
                    Open Block Map
                           ↓
                  Generate Block Route
                           ↓
                 Visit Houses/Buildings
                           ↓
              Complete / Locked / Revisit
                           ↓
                     GPS Tracking
                           ↓
              Check Block Boundary
                           ↓
                  Sync when Online
                           ↓
                      SUPERVISOR
                           ↓
                 Monitor Block Progress
                           ↓
                 Review GPS Coverage
                           ↓
               Review Field Completion
```

---

# 3. Deputy Tahsildar Flow

## 3.1 Main Flow

```text
Login
  ↓
Deputy Tahsildar Dashboard
  ↓
Select Village / Ward
  ↓
View Administrative Boundary
  ↓
View Houses / Buildings
  ↓
Create Layout
  ↓
Set Target Block Size
  ↓
Default Target ≈ 250
  ↓
Generate Blocks
  ↓
AI/GIS Processing
  ↓
View Proposed Blocks
  ↓
Review Block Counts
  ↓
Check Validation
  ↓
Edit / Split / Merge Blocks if Required
  ↓
Validate Again
  ↓
Approve Layout
  ↓
Identify Responsible Supervisor
  ↓
Assign Layout to Supervisor
  ↓
Monitor Overall Progress
```

---

# 4. Deputy Tahsildar Dashboard

The dashboard should provide an overview of administrative work.

```text
------------------------------------
       Deputy Tahsildar
------------------------------------

Villages / Wards              12

Layouts                       12

Awaiting Review                2

Approved Layouts               8

Layouts In Progress            4

------------------------------------

[ Create Layout ]

------------------------------------
Recent Layouts

Village A     Approved
Village B     In Review
Village C     In Progress

------------------------------------
```

The dashboard should use the term **Layout** for a village/ward.

---

# 5. Create Layout Flow

When the Deputy Tahsildar creates a layout:

```text
Create Layout
      ↓
Select Village / Ward
      ↓
Load Administrative Boundary
      ↓
Load Houses / Buildings
      ↓
View Map
      ↓
Set Target Block Size
      ↓
Default = 250
      ↓
Generate Blocks
```

The village/ward itself represents the layout.

```text
Village/Ward
     ↓
Layout
```

The system should not create a separate unrelated layout for each block.

---

# 6. AI Block Generation Flow

```text
Village/Ward Layout
       ↓
House/Building Data
       ↓
Road Data
       ↓
Administrative Boundary
       ↓
Target ≈ 250
       ↓
AI/GIS Block Generation
       ↓
Candidate Blocks
       ↓
Block Validation
       ↓
Display Results
```

Example:

```text
Village A

Total Houses/Buildings = 1,240

AI Generated:

B001 → 248
B002 → 252
B003 → 251
B004 → 245
B005 → 244

Total Blocks = 5
```

The system should not require every block to contain exactly 250 if geographic conditions make that impractical.

---

# 7. Block Review Flow

After generation:

```text
View Generated Blocks
       ↓
Select Block
       ↓
View Boundary
       ↓
View Houses/Buildings
       ↓
View House/Building Count
       ↓
Check Validation
       ↓
+-------------------------+
| Modification Required?  |
+-------------------------+
      | Yes          | No
      ↓              ↓
Edit Block        Approve
      ↓
Split / Merge /
Adjust Boundary
      ↓
Validate
      ↓
Review Again
```

The Deputy Tahsildar must be able to:

* Edit block boundaries
* Split blocks
* Merge blocks
* Review house/building count
* Check unassigned houses
* Check duplicate assignments
* Approve the final layout

---

# 8. Layout Approval Flow

```text
Generated Layout
       ↓
Block Validation
       ↓
Deputy Tahsildar Review
       ↓
Edit if Required
       ↓
Final Validation
       ↓
Approve Layout
       ↓
Approved Layout
```

After approval:

```text
Approved Layout
       ↓
Identify Responsible Supervisor
       ↓
Assign Layout
```

The AI must not automatically approve the generated layout.

---

# 9. Supervisor Assignment Flow

```text
Approved Layout
       ↓
Select Responsible Supervisor
       ↓
Assign Layout
       ↓
Supervisor Receives Layout
       ↓
Supervisor Opens Layout
       ↓
Views All Blocks
```

Example:

```text
--------------------------------
Layout: Village A
--------------------------------

Total Houses/Buildings: 1,240

Total Blocks:              5

Required Enumerators:       5

Supervisor:                 S001
--------------------------------
```

---

# 10. Supervisor Flow

## 10.1 Main Flow

```text
Login
  ↓
Supervisor Dashboard
  ↓
View Assigned Layouts
  ↓
Select Layout
  ↓
View Village/Ward Map
  ↓
View Blocks
  ↓
View Block House/Building Counts
  ↓
Calculate Required Enumerators
  ↓
Required Enumerators = Number of Blocks
  ↓
View Available Enumerators
  ↓
Assign One Enumerator to Each Block
  ↓
Validate Assignment
  ↓
Start Monitoring
```

---

# 11. Enumerator Assignment Flow

The Supervisor must assign one Enumerator to each block.

Example:

```text
Layout: Village A

Blocks:

B001
B002
B003
B004
B005

Required Enumerators = 5
```

Assignment:

```text
E001 → B001
E002 → B002
E003 → B003
E004 → B004
E005 → B005
```

The application should show:

```text
--------------------------------
Enumerator Assignment
--------------------------------

Total Blocks              5
Required Enumerators      5
Assigned Enumerators      5

Assignment Status         COMPLETE

B001 → E001 ✓
B002 → E002 ✓
B003 → E003 ✓
B004 → E004 ✓
B005 → E005 ✓

--------------------------------
```

If an Enumerator is missing:

```text
--------------------------------
Total Blocks              5
Required Enumerators      5
Assigned Enumerators      4

⚠ 1 Enumerator Required

B005 → Not Assigned

--------------------------------
```

The Supervisor should not be able to mark the assignment as complete until every block has an Enumerator, unless an authorized exception mechanism is introduced later.

---

# 12. Supervisor Dashboard

The Supervisor dashboard should focus on **block-level progress**.

```text
--------------------------------
          Supervisor
--------------------------------

My Layouts                    4

Village A
5 Blocks
1,240 Houses/Buildings

--------------------------------

Block Progress

B001  ██████████ 100% ✓
B002  ████████░░  80%
B003  ██████░░░░  60%
B004  ███░░░░░░░  30%
B005  █████████░  90%

--------------------------------

Enumerators

E001 → B001 → Active   100%
E002 → B002 → Active    80%
E003 → B003 → Active    60%
E004 → B004 → Offline   30%
E005 → B005 → Active    90%

--------------------------------
```

---

# 13. Supervisor Block Monitoring Flow

```text
Supervisor Dashboard
       ↓
Select Layout
       ↓
Select Block
       ↓
View Block Details
       ↓
View Assigned Enumerator
       ↓
View House/Building Progress
       ↓
View Completed
       ↓
View Remaining
       ↓
View Locked Houses
       ↓
View Revisit List
       ↓
View GPS Coverage
       ↓
View Boundary Events
```

---

# 14. Enumerator Flow

## 14.1 Main Flow

```text
Login
  ↓
Enumerator Dashboard
  ↓
View Assigned Layout
  ↓
View Assigned Block
  ↓
Download / Update Offline Data
  ↓
Open Block Map
  ↓
Start Field Work
  ↓
Get Route
  ↓
Navigate to House/Building
  ↓
Record Household Information
  ↓
House Status
  ↓
+-------------------------+
| What happened?          |
+-------------------------+
 | Completed      | Locked
 ↓                ↓
Save Record     Add Revisit
 ↓                ↓
Next House <------+
  ↓
GPS Tracking
  ↓
Block Boundary Check
  ↓
Continue Field Work
  ↓
Sync when Online
  ↓
Finish Block
```

---

# 15. Enumerator Dashboard

The Enumerator should immediately see the assigned block.

```text
--------------------------------
        Enumerator
--------------------------------

Village: Village A

Block: B003

Total Houses:       251
Completed:          150
Remaining:          101
Locked:               4

Coverage:            60%

--------------------------------

[ Open Map ]

[ Start / Continue Route ]

--------------------------------

Sync Status:
✓ All changes synced

--------------------------------
```

The Enumerator must not be shown unrelated blocks.

---

# 16. Enumerator Block Flow

```text
Enumerator Login
       ↓
Get Assigned Block
       ↓
Load Block Boundary
       ↓
Load Houses/Buildings
       ↓
Load Existing Status
       ↓
Check Offline Data
       ↓
Open Map
       ↓
Start Fieldwork
```

The Enumerator's fieldwork area is the **assigned block**, not the complete village/ward layout.

---

# 17. Route Flow

```text
Open Assigned Block
       ↓
Get Current GPS Location
       ↓
Find Pending Houses/Buildings
       ↓
Remove Completed Houses
       ↓
Handle Locked Houses
       ↓
Load Road Network
       ↓
Generate Optimized Route
       ↓
Display Route
       ↓
Navigate
```

The route must only contain houses/buildings belonging to the assigned block.

Example:

```text
Enumerator E003
       ↓
Block B003
       ↓
251 Houses
       ↓
150 Completed
       ↓
101 Remaining
       ↓
Generate Route
       ↓
Next House
```

---

# 18. House/Building Visit Flow

```text
Reach House/Building
       ↓
Open House Record
       ↓
Record Household Information
       ↓
Optional Voice Input
       ↓
Review Information
       ↓
Save
       ↓
Choose Status
```

Status:

```text
COMPLETED
LOCKED
```

If completed:

```text
COMPLETED
    ↓
Save
    ↓
Next House
```

If locked:

```text
LOCKED
    ↓
Record Reason
    ↓
Create Revisit
    ↓
Continue Route
```

---

# 19. House Status Flow

```text
PENDING
   |
   +--------------------+
   |                    |
   ↓                    ↓
COMPLETED             LOCKED
                         |
                         ↓
                      REVISIT
                         |
                         ↓
                      PENDING
                         |
                         ↓
                     COMPLETED
```

A locked house should remain visible in the Revisit list until the revisit is completed or otherwise resolved.

---

# 20. GPS Tracking Flow

During fieldwork:

```text
Enumerator Starts Fieldwork
          ↓
GPS Tracking Starts
          ↓
Current Location
          ↓
Check Assigned Block Boundary
          ↓
+-------------------------+
| Inside Assigned Block?  |
+-------------------------+
       | Yes          | No
       ↓              ↓
Continue          Show Warning
                     ↓
               Record Event
                     ↓
             Continue Tracking
```

---

# 21. Block Boundary Warning

When the Enumerator leaves the assigned block:

```text
--------------------------------
           WARNING
--------------------------------

You are outside your
assigned block.

Assigned Block:
B003

Please return to your
assigned area.

[ OK ]
--------------------------------
```

The event should also be stored.

Example:

```text
Boundary Event

Enumerator: E003
Block: B003
Time: 10:42 AM
Location: GPS coordinates
Status: Outside Block
```

If offline, this event is saved locally and synchronized later.

---

# 22. GPS Coverage Flow

```text
Assigned Block Boundary
          +
Expected Houses/Buildings
          +
Enumerator GPS Movement
          +
Completed Houses
          ↓
Coverage Analysis
          ↓
Coverage Result
```

Example:

```text
--------------------------------
Block B003

Total Houses:        251
Completed:           225
Remaining:            26
Locked:                5

House Coverage:       90%

GPS Coverage:         94%

Possible Missed Area:
Detected
--------------------------------
```

GPS coverage is only an indicator and must not automatically mean that every household in the GPS path was visited.

---

# 23. Offline Flow

The Enumerator should download the assigned block before starting fieldwork.

```text
Internet Available
      ↓
Download Assigned Layout
      ↓
Download Assigned Block
      ↓
Download Houses/Buildings
      ↓
Download Block Boundary
      ↓
Download Existing Records
      ↓
Store in SQLite
      ↓
Internet Lost
      ↓
Continue Field Work
      ↓
Record Local Changes
      ↓
Record GPS Locally
      ↓
Record Boundary Events Locally
      ↓
Add Changes to Sync Queue
      ↓
Internet Returns
      ↓
Upload Sync Queue
      ↓
Server Validation
      ↓
SYNCED
```

---

# 24. Offline Data

The following information should be available locally:

```text
Assigned Layout
Assigned Block
Block Boundary
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

# 25. Synchronization Flow

```text
Internet Returns
      ↓
Detect Connectivity
      ↓
Read Pending Sync Queue
      ↓
Upload Changes
      ↓
Server Authentication
      ↓
Server Validation
      ↓
+-------------------------+
| Upload Successful?      |
+-------------------------+
     | Yes            | No
     ↓               ↓
Mark SYNCED        Keep Pending
     ↓               ↓
Next Item          Retry Later
```

If a conflict occurs:

```text
Sync
 ↓
Conflict
 ↓
Mark CONFLICT
 ↓
Show Conflict
 ↓
Resolve using defined rule
```

Local data should not be deleted when synchronization fails.

---

# 26. Offline Voice Assistant Flow

```text
Enumerator
     ↓
Tap Voice Button
     ↓
Speak Tamil / English
     ↓
Offline Speech Recognition
     ↓
Convert Speech to Text
     ↓
Extract Structured Information
     ↓
Display Result
     ↓
Enumerator Reviews
     ↓
+-------------------------+
| Correct?                |
+-------------------------+
    | Yes             | No
    ↓                 ↓
Save              Edit
                      ↓
                    Save
```

Example:

```text
Voice:

"இந்த வீட்டில் நான்கு பேர் இருக்கிறார்கள்."

↓

Detected:

Household Members = 4

↓

[Confirm] [Edit]
```

The AI must not silently save uncertain extracted information.

---

# 27. Supervisor Live Monitoring Flow

```text
Supervisor Dashboard
       ↓
Select Layout
       ↓
View Blocks
       ↓
View Block Progress
       ↓
View Enumerator Status
       ↓
View GPS Coverage
       ↓
View Boundary Events
       ↓
View Locked Houses
       ↓
View Revisit Status
       ↓
Identify Possible Missed Areas
       ↓
Review Completion
```

---

# 28. Layout Completion Flow

The overall layout is complete only after its blocks are completed.

```text
Layout
  ↓
Block 1
Block 2
Block 3
...
Block N
  ↓
Check Every Block
  ↓
+-------------------------+
| All Blocks Complete?    |
+-------------------------+
      | Yes          | No
      ↓              ↓
Layout Complete    Continue
```

Example:

```text
Village A

B001 ✓
B002 ✓
B003 ✓
B004 ✓
B005 ✓

        ↓

Layout Complete
```

---

# 29. Block Completion Flow

A block should be considered field-complete when all houses/buildings have been accounted for according to the application's rules.

```text
Block
 ↓
Check Houses/Buildings
 ↓
Completed
 +
Resolved Locked/Revisit
 +
No unresolved required records
 ↓
Block Review
 ↓
Block Complete
```

The Supervisor can review the block before considering the layout complete.

---

# 30. Error Flow

## 30.1 API Failure

```text
API Request
   ↓
Failure
   ↓
Is operation offline-capable?
   | Yes
   ↓
Save Locally
   ↓
Queue for Sync
```

## 30.2 Critical Server Operation Failure

For operations such as:

* Layout approval
* Layout assignment
* Enumerator assignment

the system should not silently perform the operation offline.

```text
Request
  ↓
Server Unavailable
  ↓
Show Error
  ↓
Retry
```

Example:

```text
This action requires an internet connection.
Please reconnect and try again.
```

---

# 31. Role Navigation Rules

## Deputy Tahsildar

Can access:

* Dashboard
* Village/Ward selection
* Map
* Layout creation
* House/building data
* Block generation
* Block editing
* Block validation
* Layout approval
* Supervisor assignment
* Overall progress

Navigation:

```text
Home
Areas
Layouts
Progress
Profile
```

---

## Supervisor

Can access:

* Dashboard
* Assigned layouts
* Blocks
* Houses/buildings
* Enumerator assignment
* Enumerator monitoring
* GPS coverage
* Boundary events
* Locked houses
* Revisit status
* Progress

Navigation:

```text
Home
Layouts
Enumerators
Coverage
Profile
```

---

## Enumerator

Can access:

* Dashboard
* Assigned layout
* Assigned block
* Map
* Houses/buildings
* Route
* Household records
* Voice assistant
* Revisit list
* GPS status
* Sync

Navigation:

```text
Home
Map
Houses
Revisit
Sync
```

The Enumerator must only receive data belonging to their assigned block.

---

# 32. Access Restrictions

The application must enforce the following:

```text
Deputy Tahsildar
       ↓
Can manage assigned administrative areas/layouts
```

```text
Supervisor
       ↓
Can manage assigned layouts and their blocks
```

```text
Enumerator
       ↓
Can work only on assigned block
```

The backend must enforce these restrictions in addition to the mobile UI.

---

# 33. Complete Role-Based Flow

```text
                    ┌──────────────────┐
                    │ Deputy Tahsildar │
                    └────────┬─────────┘
                             ↓
                    Select Village/Ward
                             ↓
                          Layout
                             ↓
                     Generate Blocks
                             ↓
                    ≈250 Houses/Block
                             ↓
                       Review/Edit
                             ↓
                         Approve
                             ↓
                  Assign to Supervisor
                             ↓
                    ┌────────────────┐
                    │   Supervisor   │
                    └───────┬────────┘
                            ↓
                       View Blocks
                            ↓
                 Number of Blocks = N
                            ↓
                  Require N Enumerators
                            ↓
                  Assign One per Block
                            ↓
                    ┌────────────────┐
                    │   Enumerator   │
                    └───────┬────────┘
                            ↓
                    Assigned Block
                            ↓
                     Download Offline
                            ↓
                      Open Block Map
                            ↓
                    Optimize Route
                            ↓
                    Visit Houses
                            ↓
             ┌──────────────┴──────────────┐
             ↓                             ↓
        COMPLETED                       LOCKED
             ↓                             ↓
        Save Record                    Revisit
             ↓                             ↓
             └──────────────┬──────────────┘
                            ↓
                       GPS Tracking
                            ↓
                   Boundary Monitoring
                            ↓
                     Offline Sync
                            ↓
                    Supervisor Review
                            ↓
                     Block Complete
                            ↓
                  All Blocks Complete?
                            ↓
                     Layout Complete
```

---

# 34. Core App Flow Rules

The AI coding agent must always follow these rules.

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
Number of Blocks = Number of Enumerators Required
```

### Rule 5

```text
One Block → One Primary Enumerator
```

### Rule 6

```text
Enumerator → Works Only Within Assigned Block
```

### Rule 7

```text
Enumerator Route → Only Houses/Buildings in Assigned Block
```

### Rule 8

```text
Enumerator GPS → Checked Against Assigned Block Boundary
```

### Rule 9

```text
Outside Block → Enumerator Warning + Boundary Event
```

### Rule 10

```text
AI Generated Blocks → Deputy Tahsildar Review → Approval
```

### Rule 11

```text
Enumerator Fieldwork → Offline Supported
```

### Rule 12

```text
Offline Changes → SQLite → Sync Queue → Backend
```

### Rule 13

```text
All Role Permissions → Enforced by Backend
```

---

# 35. Final Application Flow

The complete application can be summarized as:

```text
                    AI-ENUMERATOR ASSISTANT

                           LOGIN
                             ↓
                     Identify User Role
                             ↓
       ┌─────────────────────┼─────────────────────┐
       ↓                     ↓                     ↓
 DEPUTY TAHSILDAR        SUPERVISOR           ENUMERATOR
       ↓                     ↓                     ↓
Select Village/Ward     View Assigned        View Assigned
       ↓                  Layouts              Block
Create Layout                ↓                     ↓
       ↓                 View Blocks          Download Data
Generate Blocks              ↓                     ↓
       ↓              Assign Enumerators      Open Map
≈250 Houses/Block            ↓                     ↓
       ↓              Monitor Progress       Get Route
Review/Edit                  ↓                     ↓
       ↓              GPS/Coverage           Visit Houses
Approve                      ↓                     ↓
       ↓                Review Blocks       Complete/Locked
Assign Supervisor            ↓                     ↓
       ↓                Layout Status        GPS Tracking
       └─────────────────────┼─────────────────────┘
                             ↓
                      Offline Synchronization
                             ↓
                       Supervisor Review
                             ↓
                      Block Completion
                             ↓
                      Layout Completion
```

This flow defines the primary navigation and fieldwork behavior of the AI-Enumerator Assistant.
