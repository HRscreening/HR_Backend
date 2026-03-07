# DeskZero — Custom Interview Scheduling System
## Implementation Plan (Full — All 8 Epics)

> **Status baseline**: Epics 1, 2, and 5.1 are substantially done.
> Everything below is the remaining build.
> Strictly follows `interview_scheduler.pdf` flow.

---

## Table of Contents

1. [Current State Audit](#1-current-state-audit)
2. [Epic 1 — Interview Settings (done)](#2-epic-1--interview-settings-done)
3. [Epic 2 — Stage Transition Trigger (done)](#3-epic-2--stage-transition-trigger-done)
4. [Epic 3 — Dashboard Status Column](#4-epic-3--dashboard-status-column)
5. [Epic 4 — Candidate Sidebar Interview Tab](#5-epic-4--candidate-sidebar-interview-tab)
6. [Epic 5 — Full Scheduling Flow](#6-epic-5--full-scheduling-flow)
7. [Epic 6 — Interview Day Automation](#7-epic-6--interview-day-automation)
8. [Epic 7 — Post-Interview Capture](#8-epic-7--post-interview-capture)
9. [Epic 8 — Round Progression Loop](#9-epic-8--round-progression-loop)
10. [Rescheduling — Both Sides](#10-rescheduling--both-sides)
11. [DB Changes Required](#11-db-changes-required)
12. [New Services + Files Required](#12-new-services--files-required)
13. [Implementation Order](#13-implementation-order)
14. [Out of Scope / Optional Phase 2](#14-out-of-scope--optional-phase-2)
15. [Appendix — Key Existing Flows](#15-appendix--key-existing-flows)

---

## 1. Current State Audit

### Done ✅

| Area | What exists |
|---|---|
| `interview_round_configs` table | Full SQLAlchemy model + Alembic migration |
| `interviews` table | Full model — `booking_token`, `scheduled_start`, `scheduled_end`, `status` enum |
| `panelist_availability` table | Full model — `available_slots` JSONB, JWT token fields |
| `interview_timeline_events` table | Full audit log model |
| `move_to_round()` in `application_service.py` | Branch A (slot booking link) + Branch B (panel JWT emails) |
| `panelist_service.py` | `get_panelist_form_details()` + `submit_panelist_availability()` |
| `JWTService.create_panelist_availability_token()` | Used in Move To Round |
| Panel email service | `send_slot_availability_email()` |
| `InterviewStatus` enum | COLLECTING_AVAILABILITY, READY_TO_BOOK, SCHEDULED, COMPLETED, CANCELED, IN_PROGRESS, AWAITING_FEEDBACK, FEEDBACK_COLLECTED |

### Stub / TODO ❌

| Area | State |
|---|---|
| `interview_service.py` | Completely empty |
| `interview_assessments.py` | Comment-only schema, no SQLAlchemy model |
| `interview_slots` table | Does not exist |
| `create_candidate_booking_token()` | Not in `jwt.py` |
| Slot computation logic | Only `# TODO: enqueue background job` comment at end of `submit_panelist_availability()` |
| Reminders + voice calls | None |
| Calendar blocking | None |
| Interview day automation | None |
| Feedback form flow | None |
| DTOs in `interviews_dto.py` | Empty (only imports) |

---

## 2. Epic 1 — Interview Settings (DONE)

HR configures each round before candidates enter the pipeline.

**What's built**: `interview_round_configs` table, CRUD routes in `interview_round_config_route.py`, service in `interview_round_config_service.py`.

**Fields already available**:
- `title`, `interview_type`, `duration_minutes`, `panelists` (JSONB), `instructions`
- `start_date` / `end_date` — window for panelist availability collection
- `slots_available` (bool) — **the critical gate flag** (see §3 Epic 2 and §6.5.2)
- `meet_link` — static meeting room override

**Remove**: `candidate_slot_booking_link` — was a Calendly relic; booking is JWT-based now. Drop the column in a migration.

**Add**: `panel_mode` (see §6.5.2 Slot Computation and §11 DB Changes).

---

## 3. Epic 2 — Stage Transition Trigger (DONE)

When HR moves an application to a round in the candidate pipeline, `move_to_round()` fires.

**What's built**:
- Checks round config exists for this job + round
- Creates `Interview` record
- **Branch A** (`slots_available=True`): sends booking link to candidate (currently a `pass`)
- **Branch B** (default): generates JWT per panelist → creates `Panelist_Availability` rows → sends availability emails → `Interview.status = COLLECTING_AVAILABILITY`

**Revised Branch A logic** (replaces the old `candidate_slot_booking_link` check):
```
move_to_round() fires:

  Step 1 — Check shared slot pool:
    available_count = SELECT COUNT(*) FROM interview_slots
                      WHERE round_config_id = X AND is_booked = FALSE

  Step 2 — Branch decision:
    if round_config.slots_available == True AND available_count > 0:
        # Pool has slots — skip panelist collection entirely
        → Create Interview record (status = READY_TO_BOOK)
        → Generate candidate booking JWT
        → Store in Interview.booking_token
        → Send candidate booking email with the link
        → Log: SLOT_BOOKING_LINK_SENT
        → Done. No panelist emails.

    else:
        # Pool is empty or never filled — must collect from panelists
        → Create Interview record (status = COLLECTING_AVAILABILITY)
        → Set round_config.slots_available = False  (ensure consistent state)
        → Generate JWT per panelist → create Panelist_Availability rows
        → Send panelist availability emails
        → (When all submit → slot_computation_service → fills pool →
           sets slots_available=True → sends candidate booking link)
```

**Pool exhaustion — auto-reset**:
After any candidate books a slot:
```
remaining = SELECT COUNT(*) FROM interview_slots
            WHERE round_config_id = X AND is_booked = FALSE
if remaining == 0:
    round_config.slots_available = False
    # Next move_to_round() for this round will trigger panelist re-collection
```

**Small gaps to close**:
- Wire the Branch A email call (currently `pass`) with new JWT-based logic above
- Add `ROUND_ADVANCEMENT` timeline event at the start of `move_to_round()`
- Drop `candidate_slot_booking_link` reference from Branch A condition

---

## 4. Epic 3 — Dashboard Status Column

HR's main application list shows a live scheduling status per candidate row.

### What to expose

Add a computed `interview_status` field to the application list API response.

```
GET /applications?job_id=...
→ each item now includes:
  "interview_status": {
    "round_number": 1,
    "status": "COLLECTING_AVAILABILITY",
    "label": "Awaiting panelist slots",
    "scheduled_at": null | ISO datetime
  }
```

### Implementation

**No new DB column needed** — read from the most recent `Interview` row for this `application_id`.

1. In `ApplicationRepository.get_applications_by_job()`, left-join to `interviews` table, pick the row with the highest `round_number`.
2. Map `InterviewStatus` → human-readable label in a helper dict in `enums.py`.
3. Return as part of the application DTO.

**Status → Label mapping**:
```
COLLECTING_AVAILABILITY  → "Awaiting panelist slots"
READY_TO_BOOK            → "Ready to book"
SCHEDULED                → "Interview scheduled"
IN_PROGRESS              → "Interview in progress"
AWAITING_FEEDBACK        → "Awaiting feedback"
FEEDBACK_COLLECTED       → "Feedback collected"
COMPLETED                → "Round completed"
CANCELED                 → "Canceled"
```

---

## 5. Epic 4 — Candidate Sidebar Interview Tab

When HR clicks a candidate card, a sidebar opens with an "Interviews" tab.

### What to expose

```
GET /applications/{application_id}/interviews
→ list of all Interview rounds for this application, each containing:
  - round_number
  - title (from round_config)
  - status
  - scheduled_start / scheduled_end
  - panelist_availability list (name, email, response_status)
  - timeline_events (audit log for this round)
```

### Implementation

1. Add `InterviewRepository.get_interviews_by_application_id(application_id)` — eager-load `panelist_availability` + `events` + `round_config`.
2. Add `GET /applications/{application_id}/interviews` route in a new `interview_routes/candidate_interview_route.py` (auth-protected).
3. DTO: `ApplicationInterviewsResponseDTO` — list of `InterviewDetailDTO` (round, status, panelists, timeline).

---

## 6. Epic 5 — Full Scheduling Flow

### 5.1 Panel Availability Collection (DONE)

Flow already works:
1. `move_to_round()` → creates `Panelist_Availability` rows with JWT tokens → sends emails
2. Panelist clicks link → `GET /panelist/availability?token=...` → gets form details
3. Panelist submits slots → `POST /panelist/availability` → JSONB stored, token invalidated
4. After last panelist submits → `# TODO` at line ~190 in `panelist_service.py` — wire to slot computation below

---

### 5.2 Slot Computation + Candidate Booking

This is the core of the custom scheduling system.

#### A. `panel_mode` — The Central Switch

Add a `panel_mode` field to `interview_round_configs` that controls how panelist slots combine:

```python
class PanelMode(enum.Enum):
    PANEL      = "panel"       # All panelists together — intersection of slots
    SEQUENTIAL = "sequential"  # Each panelist separately — union of slots, N separate bookings
```

| Mode | Meaning | Slot Algorithm | Candidate Books |
|---|---|---|---|
| `PANEL` | All panelists in the same room/call | Intersection — only slots where ALL are free | Once — one shared slot |
| `SEQUENTIAL` | Each panelist 1-on-1 with candidate | Union — each panelist's slots are independent | N times — one slot per panelist |

Add `panel_mode` column to `interview_round_configs` (default `PANEL`).

#### B. New DB Table: `interview_slots`

**Key design change**: slots are at the **`round_config_id` level** — a shared pool reused across all candidates going through the same round. `booked_interview_id` records which candidate's interview claimed each slot.

- `panelist_email` is `NULL` in PANEL mode and populated per-panelist in SEQUENTIAL mode
- `booked_interview_id` is `NULL` until a candidate books the slot

```sql
CREATE TABLE interview_slots (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    round_config_id      UUID NOT NULL REFERENCES interview_round_configs(id) ON DELETE CASCADE,
    panelist_email       TEXT,            -- NULL = PANEL mode; set = SEQUENTIAL mode
    slot_start           TIMESTAMPTZ NOT NULL,
    slot_end             TIMESTAMPTZ NOT NULL,
    is_booked            BOOLEAN NOT NULL DEFAULT FALSE,
    booked_interview_id  UUID REFERENCES interviews(id) ON DELETE SET NULL,
    booked_at            TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_slots_round_config    ON interview_slots(round_config_id);
CREATE INDEX idx_slots_available       ON interview_slots(round_config_id, is_booked) WHERE is_booked = FALSE;
CREATE INDEX idx_slots_booked_iv       ON interview_slots(booked_interview_id) WHERE booked_interview_id IS NOT NULL;
CREATE INDEX idx_slots_panelist        ON interview_slots(round_config_id, panelist_email) WHERE panelist_email IS NOT NULL;
```

**SQLAlchemy model**: `src/models/interview_models/interview_slots.py`

```python
class Interview_Slot(Base):
    __tablename__ = "interview_slots"
    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    round_config_id     = Column(UUID(as_uuid=True), ForeignKey("interview_round_configs.id"), nullable=False, index=True)
    panelist_email      = Column(String, nullable=True, index=True)  # NULL = PANEL mode
    slot_start          = Column(DateTime(timezone=True), nullable=False)
    slot_end            = Column(DateTime(timezone=True), nullable=False)
    is_booked           = Column(Boolean, nullable=False, default=False)
    booked_interview_id = Column(UUID(as_uuid=True), ForeignKey("interviews.id"), nullable=True)
    booked_at           = Column(DateTime(timezone=True), nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    round_config        = relationship("Interview_Round_Configs", back_populates="slots")
    booked_interview    = relationship("Interview", foreign_keys=[booked_interview_id])
```

Add `slots = relationship("Interview_Slot", cascade="all, delete-orphan", ...)` to the `Interview_Round_Configs` model.

**Pool lifecycle**:
```
Panel submits availability → slot_computation_service writes slots (round_config_id=X)
  → round_config.slots_available = True

Candidate books a slot:
  → slot.is_booked = True, slot.booked_interview_id = interview.id
  → Check remaining unbooked slots for this round_config_id
  → If 0 remaining → round_config.slots_available = False

Next move_to_round() for this round:
  → slots_available = False → triggers fresh panelist collection
  → Panel submits → computation → new slots written → slots_available = True again
```

#### C. Slot Computation Service

**File**: `src/services/interview_services/slot_computation_service.py`

**Trigger**: Replace the `# TODO: Enqueue background job` in `panelist_service.submit_panelist_availability()` with a direct async call to this service.

**Scope**: This service writes slots to the **`interview_slots` shared pool** at the `round_config_id` level — not per-interview. It then sets `round_config.slots_available = True` and sends booking links to **all candidates currently waiting** (interviews with `status = COLLECTING_AVAILABILITY` for this round_config, if any were queued).

**Algorithm branches on `panel_mode`**:

---

**PANEL mode** (intersection):
```
1. Load all Panelist_Availability rows for this interview_id
2. Parse each panelist's available_slots JSONB → list of (start, end) datetime pairs
3. Compute intersection across ALL panelists — only ranges where everyone is free
4. Split intersecting ranges into discrete slots of duration_minutes each
5. Write slots to interview_slots (round_config_id=X, panelist_email=NULL, is_booked=False)
6. If zero intersecting slots:
   → Interview.status = COLLECTING_AVAILABILITY  (stays collecting)
   → Email HR: "No common slots found — extend window or adjust panelists"
   → Log: SLOT_COMPUTATION_FAILED
   → Return  (do NOT set slots_available=True)
7. Set round_config.slots_available = True
8. For each Interview with status=COLLECTING_AVAILABILITY for this round_config:
   → Interview.status = READY_TO_BOOK
   → Generate candidate booking JWT
   → Store in Interview.booking_token
   → Send candidate booking email
   → Log: CANDIDATE_BOOKING_LINK_SENT
```

---

**SEQUENTIAL mode** (union / independent):
```
1. Load all Panelist_Availability rows for this interview_id
2. For EACH panelist independently:
   a. Parse their available_slots JSONB → list of (start, end) pairs
   b. Split into discrete slots of duration_minutes
   c. Write slots to interview_slots (round_config_id=X, panelist_email=panelist.email)
3. If ANY panelist has zero slots → email HR about that specific panelist
   (Do not block — other panelists' slots are still written)
4. Set round_config.slots_available = True
5. For each Interview with status=COLLECTING_AVAILABILITY for this round_config:
   → Interview.status = READY_TO_BOOK
   → Generate candidate booking JWT
   → Send candidate booking email
   → Log: CANDIDATE_BOOKING_LINK_SENT
```

---

**Intersection + split helpers (pure Python)**:

```python
from datetime import datetime, timedelta

def compute_intersection(
    slot_lists: list[list[tuple[datetime, datetime]]]
) -> list[tuple[datetime, datetime]]:
    """PANEL mode: ranges covered by ALL panelists."""
    result = slot_lists[0][:]
    for panelist_slots in slot_lists[1:]:
        new_result = []
        for s1, e1 in result:
            for s2, e2 in panelist_slots:
                start = max(s1, s2)
                end = min(e1, e2)
                if end > start:
                    new_result.append((start, end))
        result = new_result
    return result

def split_into_slots(
    ranges: list[tuple[datetime, datetime]],
    duration_minutes: int,
) -> list[tuple[datetime, datetime]]:
    """Splits continuous ranges into discrete N-minute interview slots."""
    slots = []
    delta = timedelta(minutes=duration_minutes)
    for start, end in ranges:
        current = start
        while current + delta <= end:
            slots.append((current, current + delta))
            current += delta
    return slots
```

#### D. JWT for Candidate Booking

Add to `src/utils/jwt.py` → `JWTService`:

```python
def create_candidate_booking_token(
    self,
    interview_id: str,
    candidate_email: str,
    expiration_minutes: int,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "interview_id": interview_id,
        "candidate_email": candidate_email,
        "token_type": "candidate_booking",
        "iat": now,
        "exp": now + timedelta(minutes=expiration_minutes),
    }
    return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
```

Token expiry: tie to `round_config.end_date - now()` (same pattern as panelist tokens).

#### E. Candidate Booking Endpoints (Public — no auth required)

**File**: `src/routes/interview_routes/candidate_booking_route.py`

The booking endpoints branch on `panel_mode`.

---

**PANEL mode booking** (single booking):

```
GET /interview/book?token=<jwt>
    → Validate JWT
    → Return: {
        panel_mode: "panel",
        interview: { title, duration_minutes, interview_type },
        slots: [{id, slot_start, slot_end}]   -- panelist_email is NULL, not exposed
      }
    → Only slots where is_booked=False

POST /interview/book
    Body: { token: str, slot_id: UUID }
    → Validate JWT
    → SELECT FOR UPDATE SKIP LOCKED on slot
    → If already booked → 409 Conflict
    → Set Interview_Slot.is_booked = True
    → Set Interview.scheduled_start = slot_start, scheduled_end = slot_end
    → Set Interview.status = SCHEDULED
    → Invalidate booking_token
    → Generate meeting link if VIDEO_CALL
    → Log: CANDIDATE_BOOKED_SLOT
    → Send confirmation emails + .ics to candidate + ALL panelists + HR
    → Return { message: "Booked", scheduled_start, scheduled_end, meet_link }
```

---

**SEQUENTIAL mode booking** (one booking per panelist):

```
GET /interview/book?token=<jwt>
    → Validate JWT
    → Group slots by panelist_email
    → Return: {
        panel_mode: "sequential",
        interview: { title, duration_minutes, interview_type },
        panelists: [
          {
            panelist_name: str,
            panelist_email: str,
            already_booked: bool,        -- True if candidate already chose a slot for this panelist
            booked_slot: { slot_start, slot_end } | null,
            available_slots: [{id, slot_start, slot_end}]
          },
          ...
        ]
      }

POST /interview/book
    Body: { token: str, bookings: [{ panelist_email: str, slot_id: UUID }, ...] }
    → Validate JWT
    → For each booking:
        → SELECT FOR UPDATE SKIP LOCKED on slot
        → Verify slot.panelist_email matches booking.panelist_email
        → If already booked → 409 for that panelist
        → Set is_booked=True
    → Only when ALL panelists have a booked slot:
        → Set Interview.status = SCHEDULED
        → Set Interview.scheduled_start = earliest booking start
        → Invalidate booking_token
    → Generate individual meet_link per panelist if VIDEO_CALL
      (each 1-on-1 session gets its own Meet link)
    → Log: CANDIDATE_BOOKED_SLOT (one event per panelist or one aggregate event)
    → Send emails:
        - Candidate: confirmation per session + .ics per session
        - Each panelist: their specific session confirmation + .ics
        - HR: full schedule summary
    → Return { message: "Booked", sessions: [{panelist_name, slot_start, slot_end, meet_link}] }

Note: Candidate can submit bookings incrementally (one panelist at a time).
Interview.status stays READY_TO_BOOK until all panelists are booked.
```

**Repository**: `src/repositories/interview_respositories/interview_slots_repository.py`

Key methods:
```python
async def get_available_slots(self, round_config_id: UUID) -> list[Interview_Slot]:
    """PANEL mode: returns all unbooked slots for this round_config."""
    ...

async def book_slot_atomic(
    self, slot_id: UUID, interview_id: UUID, db: AsyncSession
) -> Interview_Slot | None:
    """
    Atomically claims a slot from the shared pool.
    Sets is_booked=True and booked_interview_id=interview_id.
    Returns None if slot was already taken (race condition).
    """
    result = await db.execute(
        select(Interview_Slot)
        .where(Interview_Slot.id == slot_id, Interview_Slot.is_booked == False)
        .with_for_update(skip_locked=True)
    )
    slot = result.scalar_one_or_none()
    if slot is None:
        return None  # Already taken by another candidate
    slot.is_booked = True
    slot.booked_interview_id = interview_id
    slot.booked_at = datetime.now(timezone.utc)
    return slot

async def count_remaining(self, round_config_id: UUID) -> int:
    """Count unbooked slots in the pool. Used to auto-reset slots_available."""
    ...

async def get_slots_grouped_by_panelist(
    self, round_config_id: UUID
) -> dict[str, list[Interview_Slot]]:
    """SEQUENTIAL mode: returns {panelist_email: [slot, ...]} for unbooked slots."""
    ...

async def all_panelists_booked_for_interview(
    self, interview_id: UUID, panelist_emails: list[str]
) -> bool:
    """SEQUENTIAL mode: check if every panelist has a slot with booked_interview_id=interview_id."""
    ...

async def delete_pool(self, round_config_id: UUID) -> None:
    """Wipe entire slot pool for this round (used on reschedule/reopen)."""
    ...
```

#### F. Fill `interview_service.py`

**Methods to implement**:
- `get_booking_form(token: str)` → validate JWT, read `round_config.panel_mode`, return available slots from pool
- `book_slot(token: str, slot_id: UUID)` → PANEL mode: atomic claim from shared pool + auto-reset `slots_available` if pool empty
- `book_sequential_slots(token: str, bookings: list[{panelist_email, slot_id}])` → SEQUENTIAL mode: claim one slot per panelist from pool
- `get_booking_status(token: str)` → SEQUENTIAL mode: which panelists are booked vs pending

**After every successful booking — pool check**:
```python
remaining = await slots_repo.count_remaining(round_config_id)
if remaining == 0:
    round_config.slots_available = False
    # Next move_to_round() for this round will re-collect from panelists
```

---

### 5.3 Reminders + Voice Calls

#### Reminder Schedule

After booking (`Interview.status = SCHEDULED`), schedule these reminders:

| When | Recipient | Channel |
|---|---|---|
| T-24h | Candidate + All Panelists | Email |
| T-1h | Candidate + All Panelists | Email |
| T-24h (optional) | Candidate | Voice AI call |
| T-1h (optional) | Candidate | Voice AI call |

#### New Table: `interview_reminders`

```sql
CREATE TABLE interview_reminders (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    remind_at    TIMESTAMPTZ NOT NULL,
    channel      TEXT NOT NULL,    -- 'email' | 'voice'
    recipient    TEXT NOT NULL,    -- 'candidate' | 'panelists' | specific email
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending | sent | failed | canceled
    sent_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### Implementation

- On booking confirmation, insert reminder rows into `interview_reminders`
- Background worker polls `interview_reminders` where `status='pending' AND remind_at <= now()`
- On reschedule or cancellation: UPDATE `interview_reminders` SET status='canceled' WHERE interview_id=... AND status='pending'

If using APScheduler:
- `scheduler.add_job(send_reminder, trigger="date", run_date=remind_at, args=[reminder_id])`
- Store job IDs in `Interview.scheduled_jobs` JSONB (new column — see §11)

#### Voice AI

- **Provider**: Bland.ai (`POST /v1/calls`) or Vapi.ai — both simple REST
- **Gating**: Add `voice_reminders_enabled` boolean to `interview_round_configs` (default `False`)
- If `True`, worker fires voice API call in addition to email

---

### 5.4 Calendar Blocking

#### Phase 1: .ics Files (Implement Now)

Send `.ics` attachment in every confirmation and reminder email. Universal — works with Google Calendar, Outlook, Apple Calendar. Recipient must accept, but this is industry standard.

**Library**: `pip install icalendar`

```python
from icalendar import Calendar, Event
from datetime import datetime
import uuid as uuid_lib

def generate_ics(
    title: str,
    start: datetime,
    end: datetime,
    location: str,      # meet_link or "In Person"
    description: str,
    organizer_email: str,
) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//DeskZero//Interview Scheduler//EN")
    cal.add("version", "2.0")
    cal.add("method", "REQUEST")   # Renders as an invite, not just an event

    event = Event()
    event.add("summary", title)
    event.add("dtstart", start)
    event.add("dtend", end)
    event.add("location", location)
    event.add("description", description)
    event.add("uid", str(uuid_lib.uuid4()))
    event.add("organizer", f"mailto:{organizer_email}")

    cal.add_component(event)
    return cal.to_ical()
```

Place in `src/services/calendar_service.py`.

#### Phase 2: OAuth Calendar Blocking (Optional — Scope Only)

**Google Calendar API**:
- HR/panelist OAuth via `google-auth-oauthlib`
- Store tokens in a new `google_calendar_connections` table (mirror of `calendly_connections`)
- On booking: `POST /calendars/primary/events` with `conferenceData.createRequest` → auto-generates Google Meet link
- Gate behind `calendar_integration_enabled` org flag

**Microsoft Graph API**:
- `POST /me/events` with `isOnlineMeeting: true` → creates Teams meeting + calendar block
- Requires MS OAuth per user

Both are **Phase 2**. Build the OAuth callback routes but keep behind feature flag.

#### Meeting Link Generation for VIDEO_CALL (Phase 1)

Use a **Google service account** (no user OAuth required):

1. Create a Google Calendar API service account in GCP, share a DeskZero calendar with it
2. On booking: `POST /calendars/{calendar_id}/events` with `conferenceData.createRequest.requestId = str(interview_id)`
3. Response contains `hangoutLink` → store in `Interview.meet_link` (new column)
4. Include in all confirmation emails and .ics

**For Teams**: `POST /me/onlineMeetings` via MS Graph (requires one shared app-level Teams identity).

Add a `meet_link` column to `interviews` table (separate from `interview_round_configs.meet_link` which is a static override for all candidates).

---

## 7. Epic 6 — Interview Day Automation

On the day of and during the interview, the system must act automatically.

### Jobs Scheduled at Booking Time

Schedule all three jobs when `book_slot()` succeeds.

#### Job 1: Morning Day-Of Reminder

```
run_at = scheduled_start.replace(hour=8, minute=0, second=0)
         (if scheduled_start.hour < 8, run immediately)

Action:
  → Send "Today is your interview" email to candidate
  → Send "Today is your interview" email to all panelists
  → Include: time, meet_link, instructions from round_config.instructions
```

#### Job 2: Mark IN_PROGRESS

```
run_at = scheduled_start

Action:
  → Interview.status = IN_PROGRESS
  → Log timeline event: INTERVIEW_STARTED
```

#### Job 3: Trigger Post-Interview Flow

```
run_at = scheduled_end  (= scheduled_start + duration_minutes)

Action:
  → Interview.status = AWAITING_FEEDBACK
  → Log timeline event: INTERVIEW_ENDED
  → For each panelist: create Interview_Assessment stub + send feedback email
  → Log timeline event: FEEDBACK_REQUESTED
```

Store all three job IDs in `Interview.scheduled_jobs` (JSONB). On cancellation or reschedule, cancel+reschedule all three.

---

## 8. Epic 7 — Post-Interview Capture

### 7.1 Interview Assessments Model

Implement the comment-only stub in `src/models/interview_models/interview_assessments.py`:

Add `FeedbackRating` enum to `src/models/enums.py`:
```python
class FeedbackRating(enum.Enum):
    STRONG_YES = "strong_yes"
    YES = "yes"
    NEUTRAL = "neutral"
    NO = "no"
    STRONG_NO = "strong_no"
```

SQLAlchemy model:
```python
class Interview_Assessment(Base):
    __tablename__ = "interview_assessments"
    __table_args__ = (
        UniqueConstraint("interview_id", "panelist_email", name="uq_interview_panelist_feedback"),
    )
    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interview_id        = Column(UUID(as_uuid=True), ForeignKey("interviews.id"), nullable=False, index=True)
    panelist_email      = Column(String(320), nullable=False)
    panelist_name       = Column(String(200), nullable=True)
    rating              = Column(SAEnum(FeedbackRating, name="feedback_rating_enum"), nullable=True)
    technical_score     = Column(Integer, nullable=True)       # 1–10
    communication_score = Column(Integer, nullable=True)       # 1–10
    culture_fit_score   = Column(Integer, nullable=True)       # 1–10
    strengths           = Column(TEXT, nullable=True)
    concerns            = Column(TEXT, nullable=True)
    notes               = Column(TEXT, nullable=True)
    recommendation      = Column(TEXT, nullable=True)          # "hire" | "no_hire" | "next_round"
    feedback_token      = Column(String(500), nullable=True)   # JWT for public feedback form link
    token_expires_at    = Column(DateTime(timezone=True), nullable=True)
    submitted_at        = Column(DateTime(timezone=True), nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    interview = relationship("Interview", back_populates="assessments")
```

Add `assessments = relationship("Interview_Assessment", ...)` to `Interview` model.

### 7.2 Feedback JWT

Add to `src/utils/jwt.py` → `JWTService`:

```python
def create_panelist_feedback_token(
    self,
    panelist_email: str,
    interview_id: str,
    expiration_minutes: int,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "panelist_email": panelist_email,
        "interview_id": interview_id,
        "token_type": "panelist_feedback",
        "iat": now,
        "exp": now + timedelta(minutes=expiration_minutes),
    }
    return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
```

Token expiry: 7 days from `scheduled_end`.

### 7.3 Feedback Endpoints (Public — no auth)

**File**: `src/routes/interview_routes/feedback_route.py`

```
GET  /panelist/feedback?token=<jwt>
     → Validate JWT
     → Return: { candidate_name, round_title, your_name, already_submitted: bool }

POST /panelist/feedback
     Body: { token, rating, technical_score, communication_score, culture_fit_score,
             strengths, concerns, notes, recommendation }
     → Validate JWT
     → Save to interview_assessments (update the pre-created stub row)
     → Set submitted_at = now(), feedback_token = ""
     → Log timeline event: FEEDBACK_SUBMITTED
     → If all panelists for this interview have submitted:
         → Interview.status = FEEDBACK_COLLECTED
         → Notify HR: "All feedback collected for [candidate]"
         → Log timeline event: ALL_FEEDBACK_COLLECTED
```

### 7.4 Notetaker Bot — Recall.ai (Optional, behind flag)

For `interview_type == VIDEO_CALL`, if `recallai_enabled` is True on the organization:

**At booking time**:
```python
POST https://api.recall.ai/api/v1/bot/
{
  "meeting_url": interview.meet_link,
  "bot_name": "DeskZero Notetaker",
  "transcription_options": { "provider": "assembly_ai" },
  "real_time_transcription": { "partial_results": false }
}
→ Store response.id in Interview.recall_bot_id
```

**Webhook** `POST /webhooks/recall` (validate `Recall-Signature` header):
```
On transcript.done event:
  → Fetch transcript from Recall API
  → Append to Interview_Assessment.notes for all panelists
     (or store in a separate interview_transcripts table — Phase 2)
  → Log timeline event: TRANSCRIPT_RECEIVED
```

Add to `interview_round_configs`: no new column needed — gate via org-level flag.
Add to `interviews`: `recall_bot_id` TEXT nullable column.

---

## 9. Epic 8 — Round Progression Loop

After `Interview.status = FEEDBACK_COLLECTED`, HR makes a decision.

### Endpoint

```
POST /applications/{application_id}/rounds/{round_number}/decision
Body: { decision: "advance" | "reject" | "hire" }
Auth: HR JWT required
```

### Logic

```python
if decision == "advance":
    next_round = round_number + 1
    next_config = get_round_config(job_id, next_round)
    if next_config:
        await move_to_round(application_id, job_id, next_round)
        # This re-triggers the entire Epic 5 flow for the next round
        log_event: ROUND_ADVANCED
    else:
        # No next round configured
        application.status = OFFER_EXTENDED
        log_event: OFFER_EXTENDED
        # Notify HR: "No next round config — promote to offer or add round config"

elif decision == "reject":
    application.status = REJECTED
    interview.status = COMPLETED
    send_rejection_email_to_candidate()
    log_event: APPLICATION_REJECTED

elif decision == "hire":
    application.status = HIRED
    interview.status = COMPLETED
    log_event: APPLICATION_HIRED
```

This closes the full loop — `move_to_round()` handles everything else.

---

## 10. Rescheduling — Both Sides

### 10.1 Candidate Reschedules

**Timing**: Confirmation email is sent **immediately** on booking (no delay). The reschedule link is included in that same email. There is no separate "confirmation window" — the reschedule token is valid from the moment of booking until `reschedule_cutoff_hours` before the interview.

**No double-trigger guarantee**: Reschedule uses a separate code path (`interview_service.reschedule()`, not `move_to_round()`). The `Interview.status` stays `SCHEDULED` throughout a normal reschedule — panelist availability emails are never re-sent unless the "no slots" path is hit.

**JWT**: `create_candidate_reschedule_token(interview_id, candidate_email, expiration_minutes=48*60)`
Stored in `interviews.reschedule_token` + `interviews.reschedule_token_expires_at` at booking time.
Reschedule link in confirmation email: `/interview/reschedule?token=<reschedule_token>`

---

**Reschedule page** (`GET /interview/reschedule?token=<jwt>`):
```
Shows:
  - Current booking: title, date/time, meet_link
  - Available (unbooked) slots for this interview
  - [Reschedule to new slot] button
  - [Cancel Interview] button + reason text input
  - If zero unbooked slots: [Request New Slots] button instead of slot list
```

---

**Case A — Slots exist, candidate picks a new one**:
```
POST /interview/reschedule
Body: { token: str, new_slot_id: UUID }

→ Validate reschedule_token
→ Deadline check: reject if now() > scheduled_start - reschedule_cutoff_hours
→ Release old slot back to pool:
    set is_booked=False, booked_interview_id=NULL, booked_at=NULL
    (slot is now available for other candidates)
→ If releasing old slot makes pool non-empty again:
    round_config.slots_available = True  (re-enable fast path for next move_to_round)
→ Atomically claim new slot from pool: SELECT FOR UPDATE SKIP LOCKED
→ If new slot already taken → 409, candidate must pick again
→ Update Interview.scheduled_start, scheduled_end
→ Cancel all pending interview_reminders for this interview_id
→ Insert new reminder rows (T-24h, T-1h)
→ Cancel old APScheduler jobs (from Interview.scheduled_jobs JSONB)
→ Schedule new IN_PROGRESS, AWAITING_FEEDBACK, day-of jobs
→ If VIDEO_CALL: delete old Meet event, create new one → update Interview.meet_link
→ Generate new .ics
→ Send to candidate: "Your interview has been rescheduled" + new .ics
→ Send to all panelists: reschedule notification + new .ics
→ Send to HR: reschedule notification
→ Log: CANDIDATE_RESCHEDULED
→ Interview.status stays SCHEDULED
→ Return { new_scheduled_start, new_scheduled_end, meet_link }
```

---

**Case B — No slots left in pool, candidate requests new availability**:
```
POST /interview/request-reopen
Body: { token: str }

→ Validate reschedule_token
→ Deadline check: reject if interview already IN_PROGRESS or later
→ Set Interview.status = COLLECTING_AVAILABILITY
→ Wipe the entire slot pool: DELETE FROM interview_slots WHERE round_config_id = X
    (Affects ALL unbooked slots for this round — triggers fresh collection for everyone)
→ Set round_config.slots_available = False
→ Set Interview.booking_token = "", reschedule_token = ""
→ Cancel all pending interview_reminders
→ Cancel all APScheduler jobs
→ Notify HR: "Candidate requested new slots — panel re-availability needed"
→ Log: CANDIDATE_REQUESTED_NEW_SLOTS
→ Re-issue new availability JWTs to all panelists in round_config.panelists
→ Update Panelist_Availability rows: new token, reset response_status = PENDING
→ Send panel availability emails (same as original Branch B flow)
→ From here: normal panelist submission → slot_computation_service →
     writes new pool → slots_available=True → booking link to candidate
```

---

**Case C — Candidate cancels**:
```
POST /interview/cancel
Body: { token: str, reason: str }

→ Validate reschedule_token
→ Deadline check: reject if interview IN_PROGRESS or later
→ Set Interview.status = CANCELED
→ Set Interview.cancellation_reason = reason, cancelled_at = now()
→ Release booked slot back to pool: is_booked=False, booked_interview_id=NULL, booked_at=NULL
    (slot returns to pool — available for other candidates)
→ If pool has remaining slots: ensure round_config.slots_available = True
→ Cancel all pending reminders + APScheduler jobs
→ If VIDEO_CALL: delete Meet event
→ Notify HR: "Candidate canceled" + reason
→ Notify all panelists: "Interview canceled"
→ Log: INTERVIEW_CANCELED_BY_CANDIDATE
→ HR decides next action: re-invite candidate or reject application
```

---

### 10.2 Panel Rescheduling of an Already-Booked Interview

Three cases, all triggered after `Interview.status = SCHEDULED`.

#### Case A — Panelist Cancels / Becomes Unavailable

Triggered by HR on behalf of the panelist (or directly by the panelist via a cancel link if implemented).

```
POST /interviews/{interview_id}/panelist-cancel
Body: { panelist_email: str, reason: str }
Auth: HR JWT required

Step 1 — Quorum check:
  remaining = len(round_config.panelists) - 1
  min_required = round_config.min_panelists (NULL = all required)

  If remaining >= min_required (PANEL mode) OR this is SEQUENTIAL mode:
    → PANEL: remove panelist, interview still has enough panel
      - Update Panelist_Availability row: mark as removed/unavailable
      - Notify candidate: "Panel updated, interview proceeds as scheduled"
      - Notify HR
      - Log: PANELIST_REMOVED_NO_RESCHEDULE_NEEDED
      - Interview.status stays SCHEDULED
      → Done.

  If remaining < min_required (quorum broken):
    → Must reschedule — wipe shared slot pool and re-collect:
      - Set Interview.status = COLLECTING_AVAILABILITY
      - Release booked slot: is_booked=False, booked_interview_id=NULL, booked_at=NULL
      - Wipe pool: DELETE FROM interview_slots WHERE round_config_id = X
          (shared pool cleared — affects all unbooked slots for all waiting candidates)
      - Set round_config.slots_available = False
      - Set Interview.booking_token = "", reschedule_token = ""
      - Cancel all pending reminders + APScheduler jobs
      - If VIDEO_CALL: delete Meet event
      - Send candidate: "Your interview requires rescheduling due to panel change.
                         We will send you new time slots shortly."
      - Re-issue availability JWTs to REMAINING panelists only
      - Send panel availability emails
      - Log: INTERVIEW_RESCHEDULED_PANELIST_CANCELED
      → From here: panelists submit → slot_computation_service → new pool →
           slots_available=True → booking link to candidate
```

---

#### Case B — HR Swaps a Panelist

HR replaces one panelist with another person (different email).

```
POST /interviews/{interview_id}/swap-panelist
Body: { old_panelist_email: str, new_panelist: { name, email, role } }
Auth: HR JWT required

Note: This endpoint is per-interview (not per round config).
      If HR wants to change ALL future interviews for this round, use
      POST /interview-round-configs/{id}/update-panelist (separate endpoint).

Step 1 — Update Panelist_Availability:
  → Expire / invalidate old panelist's availability row
  → Create new Panelist_Availability row for new panelist with a new JWT token

Step 2 — New panelist availability not known yet — wipe shared pool and re-collect:
    - Set Interview.status = COLLECTING_AVAILABILITY
    - Release booked slot: is_booked=False, booked_interview_id=NULL, booked_at=NULL
    - Wipe pool: DELETE FROM interview_slots WHERE round_config_id = X
        (shared pool cleared — recomputation will happen with new panelist's slots)
    - Set round_config.slots_available = False
    - Set Interview.booking_token = "", reschedule_token = ""
    - Cancel all pending reminders + APScheduler jobs
    - If VIDEO_CALL: delete Meet event
    - Send candidate: "Your interview panel has changed. New slots will be sent shortly."
    - Send availability email to NEW panelist only (existing panelists already submitted)
    - Log: PANELIST_SWAPPED_RESCHEDULE_TRIGGERED

Step 3 — When new panelist submits:
  → slot_computation_service runs with all panelist availabilities
     (existing submitted slots + new panelist's new slots)
  → New pool written to interview_slots (round_config_id=X) →
       round_config.slots_available=True → booking link to candidate
```

---

#### Case C — Panelist Requests Time Change

Panelist contacts HR saying they have a conflict at the booked time.

```
POST /interviews/{interview_id}/panelist-request-reschedule
Body: { panelist_email: str, reason: str }
Auth: HR JWT required

This is the most disruptive case — the interview is already booked and confirmed.

Approach — HR chooses one of two paths:

Option 1: Re-collect availability from ALL panelists (full reset):
  → Same as Case A quorum-broken flow above
  → Candidate gets: "Your interview requires rescheduling. New slots coming shortly."
  → All panelists re-submit → slot computation → new booking link

Option 2: Re-collect from this panelist only (targeted):
  → Same as Case B (swap flow but with same panelist)
  → Only the conflicting panelist submits new slots
  → Merge with other panelists' existing submitted slots → recompute
  → New slots → new booking link to candidate
  → Candidate gets: "Your interview time has changed. Please pick a new slot."

Endpoint accepts an optional body field:
  { reopen_scope: "all" | "this_panelist_only" }
  Default: "this_panelist_only" (less disruptive)

Log: INTERVIEW_RESCHEDULED_PANELIST_CONFLICT
```

---

### 10.3 Summary — What Each Reschedule Case Does to the State Machine

| Trigger | Status transition | Slots | Booking token | Panel re-emails | Candidate email |
|---|---|---|---|---|---|
| Candidate picks new slot (slots exist) | SCHEDULED → SCHEDULED | Old slot released to pool, new claimed | Stays invalidated | No | Reschedule confirmation + .ics |
| Candidate — no slots, requests reopen | SCHEDULED → COLLECTING_AVAILABILITY | Pool wiped (round_config_id), slots_available=False | Cleared | Yes (all panelists) | "New slots coming" |
| Candidate cancels | SCHEDULED → CANCELED | Booked slot released to pool (booked_interview_id=NULL) | Cleared | No | — |
| Panelist cancel, quorum ok | SCHEDULED → SCHEDULED | Pool untouched | Untouched | No | "Panel updated" notice |
| Panelist cancel, quorum broken | SCHEDULED → COLLECTING_AVAILABILITY | Pool wiped (round_config_id), slots_available=False | Cleared | Yes (remaining panelists) | "Rescheduling needed" |
| HR swaps panelist | SCHEDULED → COLLECTING_AVAILABILITY | Pool wiped (round_config_id), slots_available=False | Cleared | Yes (new panelist only) | "Panel changed, new slots coming" |
| Panelist time conflict — all | SCHEDULED → COLLECTING_AVAILABILITY | Pool wiped (round_config_id), slots_available=False | Cleared | Yes (all panelists) | "Rescheduling needed" |
| Panelist time conflict — targeted | SCHEDULED → COLLECTING_AVAILABILITY | Pool wiped (round_config_id), slots_available=False | Cleared | Yes (one panelist) | "New slot selection needed" |

---

## 11. DB Changes Required

### New Tables

| Table | Purpose | Sprint |
|---|---|---|
| `interview_slots` | Available + booked time slots per interview | 1 |
| `interview_assessments` | Post-interview feedback per panelist | 3 |
| `interview_reminders` | Reminder job tracking (email + voice) | 2 |

### Columns to Remove

| Table | Column | Reason |
|---|---|---|
| `interview_round_configs` | `candidate_slot_booking_link` | Calendly relic — booking is JWT-based, not an external link |

### Columns to Add (Alembic migrations)

| Table | Column | Type | Default | Purpose |
|---|---|---|---|---|
| `interviews` | `meet_link` | TEXT | NULL | Per-interview generated Meet/Teams link |
| `interviews` | `reschedule_token` | TEXT | NULL | JWT for candidate self-reschedule |
| `interviews` | `reschedule_token_expires_at` | TIMESTAMPTZ | NULL | |
| `interviews` | `scheduled_jobs` | JSONB | NULL | APScheduler job IDs for cancellation |
| `interviews` | `recall_bot_id` | TEXT | NULL | Recall.ai bot ID (optional) |
| `interview_round_configs` | `panel_mode` | ENUM(PanelMode) | `panel` | Intersection (panel) vs union (sequential) |
| `interview_round_configs` | `min_panelists` | INTEGER | NULL | Quorum — null = all required |
| `interview_round_configs` | `voice_reminders_enabled` | BOOLEAN | FALSE | Gate voice AI calls |
| `interview_round_configs` | `reschedule_cutoff_hours` | INTEGER | 2 | How many hours before can candidate reschedule |

### New Enums (add to `src/models/enums.py`)

```python
class PanelMode(enum.Enum):
    PANEL      = "panel"       # All panelists together — intersection
    SEQUENTIAL = "sequential"  # Each panelist separately — union

class FeedbackRating(enum.Enum):
    STRONG_YES = "strong_yes"
    YES = "yes"
    NEUTRAL = "neutral"
    NO = "no"
    STRONG_NO = "strong_no"
```

### Alembic Migrations (run in order)

1. `add_interview_slots_table` — `round_config_id` FK, `booked_interview_id` FK, `panelist_email`
2. `add_interview_reminders_table`
3. `add_interview_assessments_table`
4. `add_columns_to_interviews` — meet_link, reschedule_token, reschedule_token_expires_at, scheduled_jobs, recall_bot_id
5. `add_columns_to_round_configs` — panel_mode, min_panelists, voice_reminders_enabled, reschedule_cutoff_hours
6. `drop_candidate_slot_booking_link_from_round_configs`

---

## 12. New Services + Files Required

### Models
- `src/models/interview_models/interview_slots.py` — new
- `src/models/interview_models/interview_assessments.py` — implement the comment stub
- `src/models/interview_models/interview_reminders.py` — new

### Repositories
- `src/repositories/interview_respositories/interview_slots_repository.py` — new (key: `book_slot_atomic()`)
- `src/repositories/interview_respositories/interview_assessments_repository.py` — new
- `src/repositories/interview_respositories/interview_reminders_repository.py` — new

### Services
- `src/services/interview_services/slot_computation_service.py` — new (intersection algorithm + slot writes)
- `src/services/interview_services/interview_service.py` — fill (booking form, book slot, reschedule)
- `src/services/interview_services/interview_assessment_service.py` — new (feedback form, submission)
- `src/services/interview_services/reminder_service.py` — new (schedule/cancel/send reminders)
- `src/services/calendar_service.py` — new (.ics generation; Phase 2: Google/MS API)
- `src/services/meeting_link_service.py` — new (Google Meet via service account, Teams via Graph)

### Routes
- `src/routes/interview_routes/candidate_booking_route.py` — new, **public**
  - `GET  /interview/book?token=` — booking form (PANEL or SEQUENTIAL)
  - `POST /interview/book` — book slot(s)
  - `GET  /interview/reschedule?token=` — reschedule page
  - `POST /interview/reschedule` — pick new slot (Case A)
  - `POST /interview/request-reopen` — no slots, request new availability (Case B)
  - `POST /interview/cancel` — candidate cancels with reason (Case C)
- `src/routes/interview_routes/feedback_route.py` — new, **public**
  - `GET  /panelist/feedback?token=`
  - `POST /panelist/feedback`
- `src/routes/interview_routes/interview_management_route.py` — new, **HR-auth-protected**
  - `POST /applications/{id}/rounds/{n}/decision` — advance / reject / hire
  - `POST /interviews/{id}/panelist-cancel` — panelist drops out
  - `POST /interviews/{id}/swap-panelist` — HR swaps panelist on live interview
  - `POST /interviews/{id}/panelist-request-reschedule` — panelist has time conflict
- `src/routes/interview_routes/candidate_interview_route.py` — new, **HR-auth-protected**
  - `GET /applications/{id}/interviews` — Epic 4 sidebar

### Email Templates (in `src/services/email_services/`)
- `candidate/booking_link_email.py` — "Your interview slots are ready"
- `candidate/booking_confirmation_email.py` — "Your interview is confirmed" (attach .ics)
- `candidate/reschedule_email.py` — "Your interview has been rescheduled" (new .ics)
- `candidate/interview_reminder_email.py` — T-24h and T-1h reminders
- `candidate/day_of_email.py` — morning-of reminder
- `candidate/interview_rescheduled_notice_email.py` — when panelist cancels + must reschedule
- `panel/feedback_request_email.py` — "Please submit feedback for [candidate]"
- `panel/reschedule_notification_email.py` — panelist gets new slot info
- `hr/slot_computation_failed_email.py` — "No common slots found"
- `hr/interview_booked_notification_email.py` — "Candidate booked their slot"
- `hr/feedback_collected_email.py` — "All feedback submitted for [candidate]"

### JWT Methods to Add (`src/utils/jwt.py`)
- `create_candidate_booking_token(interview_id, candidate_email, expiration_minutes)`
- `create_candidate_reschedule_token(interview_id, candidate_email, expiration_minutes)`
- `create_panelist_feedback_token(panelist_email, interview_id, expiration_minutes)`

### DTOs (`src/dtos/interviews_dtos/`)
- Fill `interviews_dto.py` — `AvailableSlotsResponseDTO`, `BookSlotRequestDTO`, `BookingConfirmationDTO`
- New `assessment_dto.py` — `FeedbackSubmissionDTO`

---

## 13. Implementation Order

### Sprint 1 — Core Booking Flow (Unblocks all other epics)

1. `FeedbackRating` enum in `enums.py`
2. `interview_slots` model + Alembic migration
3. `interview_slots_repository.py` with `book_slot_atomic()`
4. `create_candidate_booking_token()` in `jwt.py`
5. `slot_computation_service.py` — intersection + split + write slots
6. Wire the `# TODO` in `panelist_service.submit_panelist_availability()` → call `slot_computation_service`
7. Fill `interview_service.py` — `get_booking_form()` + `book_slot()`
8. `candidate_booking_route.py` — `GET /interview/book` + `POST /interview/book`
9. `calendar_service.py` — `generate_ics()` only
10. Candidate booking confirmation email + .ics attachment
11. Wire Branch A in `move_to_round()` — send booking link email (`CandidateEmailService.send_booking_link_email()`)
12. All missing timeline events logged

**Milestone**: Full end-to-end booking works for first time.

---

### Sprint 2 — Rescheduling + Reminders

13. `add_columns_to_interviews` Alembic migration (reschedule_token, scheduled_jobs, meet_link, recall_bot_id)
14. `add_columns_to_round_configs` Alembic migration (min_panelists, voice_reminders_enabled, reschedule_cutoff_hours)
15. `create_candidate_reschedule_token()` in `jwt.py`
16. `POST /interview/reschedule` + `GET /interview/reschedule` endpoints
17. `interview_reminders` model + migration + repository
18. `reminder_service.py` — schedule/cancel/send + APScheduler wiring
19. `POST /interviews/{id}/panelist-cancel` endpoint
20. `POST /interview-round-configs/{id}/swap-panelist` endpoint

**Milestone**: Rescheduling from both sides works; reminders fire on schedule.

---

### Sprint 3 — HR Dashboard + Sidebar

21. Epic 3: left-join interviews into `get_applications_by_job()`, add `interview_status` to DTO
22. Epic 4: `GET /applications/{id}/interviews` + eager-load query + DTO
23. Epic 8: `POST /applications/{id}/rounds/{n}/decision` endpoint

**Milestone**: HR can see live status, view details, advance/reject/hire.

---

### Sprint 4 — Post-Interview Feedback + Day-Of Automation

24. `interview_assessments` model + Alembic migration
25. `interview_assessments_repository.py`
26. `create_panelist_feedback_token()` in `jwt.py`
27. `interview_assessment_service.py`
28. `feedback_route.py` — GET + POST
29. APScheduler jobs wired in `book_slot()`: Mark IN_PROGRESS, Mark AWAITING_FEEDBACK, Day-Of Reminder
30. HR / panelist emails for feedback collected

**Milestone**: Full post-interview feedback loop complete.

---

### Sprint 5 — Meeting Links + Optional Features

31. `meeting_link_service.py` — Google Calendar service account integration
32. Wire meeting link into `book_slot()` for VIDEO_CALL type
33. Recall.ai notetaker bot (behind `recallai_enabled` flag)
34. Voice AI reminders via Bland.ai/Vapi (behind `voice_reminders_enabled` flag)
35. OAuth calendar blocking Phase 2 (Google / MS — behind `calendar_integration_enabled` flag)

---

## 14. Out of Scope / Optional Phase 2

| Feature | Notes |
|---|---|
| Panelist OAuth calendar blocking | Per-panelist Google/MS OAuth consent flow |
| Google Meet via HR's own Google account | Requires HR Google OAuth (service account is simpler) |
| Teams meeting via MS Graph | Requires dedicated MS app registration + OAuth |
| Voice AI calls | Bland.ai/Vapi REST integration — add in Sprint 5 |
| Recall.ai notetaker bot | Webhook handler + `recallai_enabled` org flag |
| `google_calendar_connections` table | For storing per-user OAuth tokens (mirror of calendly_connections) |
| Candidate self-service cancellation | Requires cancellation policy config and deadline rules |
| SMS reminders | Twilio integration |
| Automatic round progression based on AI feedback | ML-based auto-advance |
| Calendly | Definitively ruled out — see `docs/calendly_analysis.txt` |

---

## 15. Appendix — Key Existing Flows (Do Not Break)

### `move_to_round()` entry point
File: `src/services/application_service.py`
- **Branch A** (`slots_available=True`): direct booking link → wire email call (currently `pass`)
- **Branch B** (default): panelist availability collection → `panelist_service` → `slot_computation_service`

### `submit_panelist_availability()` trigger point
File: `src/services/interview_services/panelist_service.py`, the block:
```python
if all(p.response_status == PanelistResponseStatus.SUBMITTED for p in all_panelists):
    # TODO: Enqueue background job...
    pass
```
Replace `pass` with:
```python
await slot_computation_service.compute_and_store_slots(
    interview_id=interview_id,
    round_config_id=round_config_id,
    db=self.db,
)
```

### `slots_available` Flag Lifecycle

```
False (initial) ──► move_to_round() → collect from panelists
                       ↓
                    all panelists submit
                       ↓
                    slot_computation_service writes pool
                       ↓
True             ──► move_to_round() → send booking link directly (no panelist emails)
                       ↓
                    candidate books → remaining pool count checked
                       ↓
                    remaining == 0
                       ↓
False            ──► next move_to_round() → collect from panelists again
```

### `InterviewStatus` State Machine

```
COLLECTING_AVAILABILITY
    │  (all panelists submitted + slots computed successfully)
    ▼
READY_TO_BOOK
    │  PANEL mode: candidate books one shared slot from pool
    │  SEQUENTIAL mode: candidate books N slots (one per panelist from pool)
    │    status stays READY_TO_BOOK until all N are filled
    ▼
SCHEDULED
    │  (at scheduled_start)
    ▼
IN_PROGRESS
    │  (at scheduled_end)
    ▼
AWAITING_FEEDBACK
    │  (all panelists submit feedback)
    ▼
FEEDBACK_COLLECTED
    │  (HR decision)
    ├──► COMPLETED  (hire + all done, or round completed + next round triggered)
    └──► [move_to_round(next_round)]  (advance → re-enters COLLECTING_AVAILABILITY)

CANCELED  ← can transition from any state (HR cancel, panelist cancel, candidate cancel)
```

### JWT Token Types Summary

| Token Type | Method | Stored In | Expiry | Purpose |
|---|---|---|---|---|
| Panelist availability | `create_panelist_availability_token` | `panelist_availability.availability_token` | `round_config.end_date` | Panelist submits their slots |
| Candidate booking | `create_candidate_booking_token` (new) | `interviews.booking_token` | `round_config.end_date` | Candidate picks a slot |
| Candidate reschedule | `create_candidate_reschedule_token` (new) | `interviews.reschedule_token` | 48h after booking | Self-service reschedule |
| Panelist feedback | `create_panelist_feedback_token` (new) | `interview_assessments.feedback_token` | 7 days after scheduled_end | Post-interview feedback form |

### `PanelMode` Decision Guide

| Scenario | Use Mode |
|---|---|
| Technical panel — 3 engineers review candidate together | `PANEL` |
| HR screen → then tech interview → then cultural fit (same round config) | `SEQUENTIAL` |
| Founders want to each meet the candidate individually | `SEQUENTIAL` |
| Any round where all panelists must be in the same call | `PANEL` |

### Booking Race Condition Protection

All slot booking (initial + reschedule) **must** use `SELECT FOR UPDATE SKIP LOCKED` at the DB level.
Do not rely on application-level checks — two candidates could book the same slot concurrently.
The `book_slot_atomic()` repository method handles this. Both `interview_service.book_slot()` and the reschedule handler must call it.

In SEQUENTIAL mode, each `book_slot_atomic()` call is independent per panelist slot — run them in sequence inside a single DB transaction so either all succeed or all roll back.

### `slots_available` Consistency Rule

`round_config.slots_available` must be kept consistent with the actual pool state:

```
Only set True  when: slot_computation_service successfully writes ≥1 slot to the pool
Only set False when: booking reduces pool to 0 unbooked slots
                OR:  panelist cancel / reopen wipes the pool
                OR:  HR manually resets the round
```

Never read `slots_available` without also checking `count_remaining()` inside a transaction — the flag is a fast-path cache, the count is the ground truth.
