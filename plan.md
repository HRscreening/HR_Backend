# DeskZero — Agentic Interview Scheduling: Implementation Plan

> **Date**: February 25, 2026  
> **Status**: Planning Complete — Ready for Implementation  
> **Estimated Effort**: ~17 days

---

## Table of Contents

1. [Context & Problem](#1-context--problem)
2. [Key Decisions & Rationale](#2-key-decisions--rationale)
3. [Architecture Overview](#3-architecture-overview)
4. [Database Changes](#4-database-changes)
5. [New Enums](#5-new-enums)
6. [API Endpoints](#6-api-endpoints)
7. [Background Jobs (ARQ)](#7-background-jobs-arq)
8. [New & Modified Files](#8-new--modified-files)
9. [Constraints & Limitations](#9-constraints--limitations)
10. [Complete Working Flow](#10-complete-working-flow)
11. [Implementation Phases](#11-implementation-phases)
12. [Verification & Testing](#12-verification--testing)

---

## 1. Context & Problem

DeskZero is an HR platform where **only HR users** are registered. Candidates and interview panelists are **external** — they are not on the platform and have no accounts.

Currently, the platform handles job posting, resume parsing, scoring, and application management. There is **no interview scheduling capability**. HR must manually coordinate interviews via email/calendar outside the platform.

### Goal

Build a fully automated, agentic interview scheduling system that:

- Eliminates manual coordination between HR, panelists, and candidates
- Supports multi-round interviews per job
- Collects panelist availability without HR friction
- Lets candidates self-book from available slots
- Automates reminders, calendar invites, and feedback collection
- Optionally integrates with panelists' personal Calendly accounts for auto-availability detection

---

## 2. Key Decisions & Rationale

### 2.1 Approach: "Plan B+" — HR-Only Calendly + Self-Service Panelist Availability

| Decision | Chosen | Rejected | Why |
|----------|--------|----------|-----|
| Calendly scope | Optional for panelists (personal accounts) | App-level org Calendly / Collective Event Types | Panelists are external with personal accounts; Collective Events require same Calendly org on Teams plan ($16/seat/month). Personal accounts can't join another org's Collective events. |
| Panelist availability | Auto-email availability form (+ optional Calendly connect) | HR coordinates manually | Eliminates HR friction. System sends panelists a link; they respond directly. |
| Candidate booking | Custom booking page (our system) | Calendly booking page | We need to show intersected slots from multiple panelists. Calendly can't do this across personal accounts. |
| Calendar invites | ICS files via email | Google/Outlook Calendar API | ICS is universal — works with any calendar app. No OAuth needed from participants. |
| Reminders | Our own email reminders (1 day + 1 hour before) | Rely on calendar app reminders | Calendar reminders only work if the participant adds the ICS to their calendar. We can't verify this. Every serious scheduling tool (Calendly, Greenhouse) sends its own reminders too. |
| Public pages auth | Signed JWT in URL (short-lived, single-purpose) | UUID lookup tables / Magic links | Self-expiring, tamper-proof, no extra DB table needed. Simpler than managing magic link records. |
| Panelist feedback | No-auth email forms (signed JWT links) | Built into platform | Panelists aren't on the platform. Email forms with signed links are the only frictionless option. |
| ApplicationStatus | Refactor to `ApplicationStage` with round-level stages | Keep current enum | Current `ApplicationStatus` has only one interview state. Multi-round scheduling needs `round_1`, `round_2`, `round_3` etc. |
| Calendly role | Optional convenience for auto-detecting panelist free times | Core scheduling engine | System must work fully without Calendly. It's purely a convenience — if a panelist connects their Calendly, we pre-fill their availability instead of asking them to pick manually. |

### 2.2 What Calendly Gives Us (and What It Doesn't)

| Feature | With Personal Calendly | Without |
|---------|----------------------|---------|
| Panelist availability detection | Auto from `GET /user_busy_times` API | Manual slot picking via our form |
| Candidate booking | Custom page (our system) | Same |
| Calendar invites | ICS via email (our system) | Same |
| Reminders | Our ARQ email jobs | Same |
| Feedback collection | Our forms | Same |

**Bottom line**: Calendly is a nice-to-have for panelists, not a dependency.

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        HR Dashboard                         │
│  (Configure rounds → Trigger scheduling → Review feedback)  │
└──────────────────────────┬──────────────────────────────────┘
                           │ Auth-required API
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                          │
│  interview_routes.py (auth) + interview_public_routes.py    │
│  interview_service.py + calendly_service.py                 │
│  interview_repository.py + availability_repository.py       │
└────────┬──────────────────┬─────────────────┬───────────────┘
         │                  │                 │
         ▼                  ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│  PostgreSQL  │  │  Redis/ARQ   │  │  Email (SMTP)    │
│  (Supabase)  │  │  Workers     │  │  + ICS Invites   │
└──────────────┘  └──────┬───────┘  └──────────────────┘
                         │
              ┌──────────┴──────────┐
              │    ARQ Jobs (5)     │
              │ • availability_req  │
              │ • booking_link      │
              │ • reminders (cron)  │
              │ • feedback_request  │
              │ • status_cron       │
              └─────────────────────┘

Public Pages (No Auth — Signed JWT in URL):
  • Panelist → Availability Form / Calendly Connect
  • Candidate → Booking Page
  • Panelist → Feedback Form
```

---

## 4. Database Changes

### 4.1 Modified Tables

#### `applications` — Column Changes

| Change | Column | Details |
|--------|--------|---------|
| Rename | `status` → `stage` | Reflects stage-based progression, not binary status |
| Repurpose | `current_round` | Already exists (Integer, default 0). Used to track which interview round the candidate is in. |
| Keep | `last_activity_at` | Already exists. Updated on every stage transition. |

#### `jobs` — New Columns

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `total_interview_rounds` | Integer | `NULL` | How many interview rounds this job has (1–3) |
| `interview_config_complete` | Boolean | `False` | Whether all round configs are set up |

### 4.2 New Tables

#### `interview_round_configs`

Stores per-job round configuration. Created by HR before scheduling begins.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default uuid4 | |
| `job_id` | UUID | FK → jobs.id, NOT NULL | Which job this round belongs to |
| `round_number` | Integer | NOT NULL | 1, 2, or 3 |
| `title` | String(200) | NOT NULL | e.g., "Technical Screen", "Culture Fit" |
| `interview_type` | Enum(InterviewType) | NOT NULL | video_call, phone_screen, in_person, take_home |
| `duration_minutes` | Integer | NOT NULL, default 45 | Duration of the interview |
| `panelists` | JSONB | NOT NULL | Array of `{name, email}` objects |
| `instructions` | Text | NULL | Notes for panelists (shared in the invite) |
| `meeting_link` | String(500) | NULL | Zoom/Meet link (optional, HR provides) |
| `created_at` | DateTime | NOT NULL, default now | |
| `updated_at` | DateTime | NOT NULL, default now | |

**Constraints**: UNIQUE(job_id, round_number)

#### `interviews`

One record per application per round. The core scheduling entity.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default uuid4 | |
| `application_id` | UUID | FK → applications.id, NOT NULL | |
| `round_config_id` | UUID | FK → interview_round_configs.id, NOT NULL | |
| `round_number` | Integer | NOT NULL | Denormalized for quick queries |
| `status` | Enum(InterviewStatus) | NOT NULL, default collecting_availability | Current state |
| `scheduled_start` | DateTime(tz) | NULL | Set when candidate books |
| `scheduled_end` | DateTime(tz) | NULL | start + duration |
| `candidate_email` | String(320) | NOT NULL | For sending booking link |
| `candidate_name` | String(200) | NULL | For email personalization |
| `booking_token` | String(500) | NULL | Signed JWT for candidate booking link |
| `booking_token_expires_at` | DateTime | NULL | |
| `cancelled_at` | DateTime | NULL | |
| `cancellation_reason` | Text | NULL | |
| `created_at` | DateTime | NOT NULL, default now | |
| `updated_at` | DateTime | NOT NULL, default now | |

**Indexes**: (application_id, round_number), (status), (scheduled_start)

#### `panelist_availability`

Stores each panelist's submitted time slots for an interview.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default uuid4 | |
| `interview_id` | UUID | FK → interviews.id, NOT NULL | |
| `panelist_email` | String(320) | NOT NULL | |
| `panelist_name` | String(200) | NULL | |
| `response_status` | Enum(PanelistResponseStatus) | NOT NULL, default pending | pending, submitted, expired |
| `available_slots` | JSONB | NULL | Array of `{start: ISO8601, end: ISO8601}` |
| `availability_token` | String(500) | NULL | Signed JWT for the form link |
| `token_expires_at` | DateTime | NULL | |
| `responded_at` | DateTime | NULL | |
| `calendly_connected` | Boolean | default False | Whether they used Calendly to auto-fill |
| `created_at` | DateTime | NOT NULL, default now | |

**Constraints**: UNIQUE(interview_id, panelist_email)

#### `interview_assessments`

Post-interview feedback from each panelist.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default uuid4 | |
| `interview_id` | UUID | FK → interviews.id, NOT NULL | |
| `panelist_email` | String(320) | NOT NULL | |
| `panelist_name` | String(200) | NULL | |
| `rating` | Enum(FeedbackRating) | NOT NULL | strong_yes, yes, neutral, no, strong_no |
| `technical_score` | Integer | NULL | 1–10 (optional) |
| `communication_score` | Integer | NULL | 1–10 (optional) |
| `culture_fit_score` | Integer | NULL | 1–10 (optional) |
| `strengths` | Text | NULL | Free text |
| `concerns` | Text | NULL | Free text |
| `notes` | Text | NULL | General notes |
| `recommendation` | Text | NULL | Hire / No hire / Next round |
| `feedback_token` | String(500) | NULL | Signed JWT for feedback form link |
| `token_expires_at` | DateTime | NULL | |
| `submitted_at` | DateTime | NULL | |
| `created_at` | DateTime | NOT NULL, default now | |

**Constraints**: UNIQUE(interview_id, panelist_email)

#### `interview_timeline_events`

Audit log for every state change and action on an interview.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default uuid4 | |
| `interview_id` | UUID | FK → interviews.id, NOT NULL | |
| `event_type` | String(100) | NOT NULL | e.g., "availability_requested", "slot_booked", "feedback_submitted" |
| `actor` | String(320) | NULL | Email or user ID of who triggered it |
| `details` | JSONB | NULL | Any extra context |
| `created_at` | DateTime | NOT NULL, default now | |

**Index**: (interview_id, created_at)

#### `calendly_connections`

Optional — stores OAuth tokens for panelists who connect their personal Calendly.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default uuid4 | |
| `panelist_email` | String(320) | UNIQUE, NOT NULL | |
| `calendly_user_uri` | String(500) | NOT NULL | Calendly user URI |
| `access_token` | Text | NOT NULL | Encrypted OAuth access token |
| `refresh_token` | Text | NOT NULL | Encrypted OAuth refresh token |
| `token_expires_at` | DateTime | NOT NULL | |
| `connected_at` | DateTime | NOT NULL, default now | |
| `updated_at` | DateTime | NOT NULL, default now | |

### 4.3 ER Diagram (Relationships)

```
jobs ──1:N──> interview_round_configs
                        │
applications ──1:N──> interviews ──N:1──┘
                        │
                        ├──1:N──> panelist_availability
                        ├──1:N──> interview_assessments
                        └──1:N──> interview_timeline_events

calendly_connections (standalone, keyed by panelist_email)
```

---

## 5. New Enums

### `ApplicationStage` (replaces `ApplicationStatus`)

```
applied → shortlisted → round_1 → round_2 → round_3 → offer → rejected → hired
```

> **Breaking change**: `status` column renamed to `stage`. Frontend must update simultaneously.
> Migration: `ALTER TABLE applications RENAME COLUMN status TO stage; ALTER TYPE applicationstatus RENAME TO applicationstage;` + add new values.

### `InterviewStatus`

```
collecting_availability → ready_to_book → scheduled → in_progress → awaiting_feedback → feedback_collected → completed → cancelled
```

### `InterviewType`

```
video_call | phone_screen | in_person | take_home
```

### `PanelistResponseStatus`

```
pending | submitted | expired
```

### `FeedbackRating`

```
strong_yes | yes | neutral | no | strong_no
```

---

## 6. API Endpoints

### 6.1 Auth-Required Endpoints (HR Only)

| Method | Endpoint | Purpose | Request Body |
|--------|----------|---------|-------------|
| `POST` | `/api/interviews/rounds` | Create/update round config for a job | `{job_id, round_number, title, interview_type, duration_minutes, panelists: [{name, email}], instructions?, meeting_link?}` |
| `GET` | `/api/interviews/rounds/{job_id}` | Get all round configs for a job | — |
| `PUT` | `/api/interviews/rounds/{round_config_id}` | Update a specific round config | Same as POST body |
| `DELETE` | `/api/interviews/rounds/{round_config_id}` | Delete a round config | — |
| `POST` | `/api/interviews/schedule` | Trigger interview scheduling for application(s) | `{application_ids: [uuid], round_number?: int}` |
| `POST` | `/api/interviews/schedule/bulk` | Bulk schedule multiple applications | `{application_ids: [uuid]}` |
| `GET` | `/api/interviews/{interview_id}` | Get interview details + timeline | — |
| `GET` | `/api/interviews/job/{job_id}` | List all interviews for a job (with filters) | Query: `?status=&round=&page=&limit=` |
| `GET` | `/api/interviews/application/{application_id}` | Get all interviews for an application | — |
| `PATCH` | `/api/interviews/{interview_id}/cancel` | Cancel an interview | `{reason?}` |
| `POST` | `/api/interviews/{interview_id}/advance` | Move application to next round | — |
| `GET` | `/api/interviews/{interview_id}/feedback` | View collected feedback/assessments | — |
| `POST` | `/api/interviews/{interview_id}/resend-availability` | Resend availability requests to non-responding panelists | — |
| `POST` | `/api/interviews/{interview_id}/resend-booking` | Resend booking link to candidate | — |
| `GET` | `/api/interviews/dashboard/{job_id}` | Interview stats overview for a job | — |

### 6.2 Public Endpoints (No Auth — Signed JWT in URL)

| Method | Endpoint | Purpose | Who |
|--------|----------|---------|-----|
| `GET` | `/api/public/interviews/availability/{token}` | Load availability form (pre-filled if Calendly connected) | Panelist |
| `POST` | `/api/public/interviews/availability/{token}` | Submit available time slots | Panelist |
| `GET` | `/api/public/interviews/calendly/connect/{token}` | Start Calendly OAuth flow | Panelist |
| `GET` | `/api/public/interviews/calendly/callback` | Calendly OAuth redirect handler | Calendly |
| `GET` | `/api/public/interviews/book/{token}` | Load booking page with intersected slots | Candidate |
| `POST` | `/api/public/interviews/book/{token}` | Confirm slot selection | Candidate |
| `GET` | `/api/public/interviews/feedback/{token}` | Load feedback form | Panelist |
| `POST` | `/api/public/interviews/feedback/{token}` | Submit feedback | Panelist |

### 6.3 Token Structure (Signed JWT)

```json
{
  "type": "availability | booking | feedback | calendly_connect",
  "interview_id": "uuid",
  "email": "panelist@example.com",
  "exp": 1740000000
}
```

- **Availability tokens**: 7-day expiry
- **Booking tokens**: 5-day expiry
- **Feedback tokens**: 14-day expiry
- **Calendly connect tokens**: 24-hour expiry

Signed with the same `SECRET_KEY` used for user JWTs but with a different `type` claim to prevent cross-use.

---

## 7. Background Jobs (ARQ)

### 7.1 Event-Driven Jobs

| Job | Trigger | What It Does |
|-----|---------|-------------|
| `send_availability_request` | HR moves application to interview stage | Generates signed JWT links, emails each panelist with availability form link. Includes option to connect Calendly for auto-detection. |
| `send_booking_link` | All panelists have submitted availability | Computes slot intersection, generates booking token, emails candidate with booking page link. |
| `request_panel_feedback` | `interview_status_cron` detects interview time has passed | Generates feedback tokens, emails panelists with feedback form link. |

### 7.2 Cron Jobs

| Job | Schedule | What It Does |
|-----|----------|-------------|
| `send_interview_reminders` | Every 30 min | Queries interviews with `status = scheduled` where `scheduled_start` is within 24 hours or 1 hour. Sends reminder emails to all participants (panelists + candidate). Idempotent — tracks which reminders were already sent via `interview_timeline_events`. |
| `interview_status_cron` | Every 15 min | **Transitions**: `scheduled` → `awaiting_feedback` (when `scheduled_end` has passed). **Nudges**: Re-sends availability requests to panelists who haven't responded after 3 days. **Expires**: Marks availability tokens as expired after 7 days. |

---

## 8. New & Modified Files

### 8.1 New Files (~15)

| Layer | File | Purpose |
|-------|------|---------|
| **Models** | `src/models/interview_round_config_model.py` | SQLAlchemy model for round configs |
| **Models** | `src/models/interview_model.py` | Interview, PanelistAvailability, InterviewAssessment, InterviewTimelineEvent models |
| **Models** | `src/models/calendly_connection_model.py` | Calendly OAuth token storage |
| **Schemas** | `src/schemas/interview_schemas.py` | Pydantic schemas for all interview-related request/response |
| **Routes** | `src/routes/interview_routes.py` | Auth-required HR endpoints |
| **Routes** | `src/routes/interview_public_routes.py` | Public endpoints (panelist/candidate forms) |
| **Services** | `src/services/interview_service.py` | Core scheduling logic, slot intersection, token generation |
| **Services** | `src/services/calendly_service.py` | Calendly OAuth + busy times API integration |
| **Repositories** | `src/repositories/interview_repository.py` | DB operations for interviews, round configs, timeline |
| **Repositories** | `src/repositories/availability_repository.py` | DB operations for panelist availability + assessments |
| **Workers** | `async_workers/jobs/interview_jobs.py` | All 5 ARQ job functions |
| **Utils** | `src/utils/interview_email_templates.py` | HTML email templates (availability request, booking link, reminders, feedback request, confirmation) |
| **Utils** | `src/utils/ics_generator.py` | ICS calendar invite file generation |
| **Utils** | `src/utils/slot_intersection.py` | Algorithm to compute intersected available time slots |
| **Migration** | `alembic/versions/xxx_add_interview_scheduling.py` | Alembic migration for all schema changes |

### 8.2 Modified Files (9)

| File | Change |
|------|--------|
| `src/models/enums.py` | Add `InterviewStatus`, `InterviewType`, `PanelistResponseStatus`, `FeedbackRating`. Refactor `ApplicationStatus` → `ApplicationStage` with new values. |
| `src/models/application_model.py` | Rename `status` → `stage`. Add relationship to `interviews`. |
| `src/models/job_model.py` | Add `total_interview_rounds`, `interview_config_complete` columns. Add relationship to `interview_round_configs`. |
| `src/models/__init__.py` | Import new models. |
| `src/dependency.py` | Wire `InterviewRepository`, `AvailabilityRepository`, `InterviewService`, `CalendlyService`. |
| `main.py` | Register `interview_router` (with auth) and `interview_public_router` (without auth). |
| `src/utils/email_service.py` | Add generic `send_templated_email(to, subject, html_body)` method alongside existing OTP method. |
| `workers/new_producer.py` | Add `JobConfig` entries and `enqueue_*` methods for all 5 interview jobs. |
| `async_workers/worker.py` | Register interview worker functions in `WorkerSettings.functions`. |

---

## 9. Constraints & Limitations

### Technical Constraints

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| **Email service is plain-text only** | Can't send HTML emails currently | Add `send_templated_email()` method with HTML support |
| **No OAuth token storage** | Can't persist Calendly tokens | New `calendly_connections` table with encrypted tokens |
| **SMTP via Gmail** | Rate limited (~500/day for Gmail) | Sufficient for MVP. Migrate to SendGrid/SES for scale. |
| **`ApplicationStatus` → `ApplicationStage` is breaking** | Frontend must update simultaneously | Coordinate deployment. Single migration with data transformation. |
| **ICS invites depend on email delivery** | If email goes to spam, no calendar invite | Use proper SPF/DKIM on sender domain. Add fallback download link. |
| **Slot intersection is timezone-sensitive** | Panelists may be in different timezones | Store all times in UTC. Detect timezone from browser on public forms. Convert for display. |

### Business Constraints

| Constraint | Impact |
|------------|--------|
| Max 3 interview rounds per job | Keeps the system manageable. Can extend later. |
| Calendly is optional, not required | System must work fully without it. No Calendly dependency in the critical path. |
| Panelists have no platform accounts | All interaction via signed email links. No login. |
| Candidates have no platform accounts | Same — booking and communication via signed email links. |
| Calendly personal accounts (free tier) may not have API access | The `/user_busy_times` endpoint requires at least Calendly's Standard plan. Free tier users may not be able to connect. |
| No video calling built in | HR provides meeting links (Zoom/Meet) in round config. Platform doesn't host calls. |

### Security Considerations

| Concern | Approach |
|---------|----------|
| Signed JWT link leakage | Short expiry (24h–14d). Tokens are single-purpose (type claim). One-time use for feedback (invalidated after submission). |
| Calendly OAuth tokens at rest | Encrypt `access_token` and `refresh_token` columns using Fernet or similar. |
| Public endpoints abuse | Rate limiting on all `/api/public/*` endpoints. Token validation before any DB operation. |
| Email enumeration | Public endpoints never confirm/deny whether an email exists. Generic error messages. |

---

## 10. Complete Working Flow

### Phase 0: Interview Round Configuration (One-Time per Job)

```
HR opens Job Settings → Interview Configuration tab
  │
  ├─ Sets total rounds: 2
  │
  ├─ Round 1: "Technical Screen"
  │     Type: Video Call
  │     Duration: 45 min
  │     Panelists: [alice@company.com, bob@company.com]
  │     Meeting Link: https://meet.google.com/xxx
  │     Instructions: "Focus on system design and coding"
  │
  └─ Round 2: "Culture Fit"
        Type: Video Call
        Duration: 30 min
        Panelists: [carol@company.com]
        Meeting Link: https://meet.google.com/yyy
        Instructions: "Assess team fit and values alignment"
  
  ✅ interview_config_complete = True
```

### Phase 1: Trigger Scheduling

```
HR views applications list → selects candidate(s) → clicks "Schedule Interview"
  │
  ├─ System validates: interview_config_complete == True
  ├─ Creates `interview` record (status: collecting_availability)
  ├─ Creates `panelist_availability` records (status: pending) for each panelist
  ├─ Updates application.stage → round_1
  ├─ Updates application.current_round → 1
  │
  └─ Enqueues ARQ job: `send_availability_request`
        │
        ├─ Generates signed JWT links for each panelist (7-day expiry)
        ├─ Sends email to alice@company.com:
        │     Subject: "Interview Availability Request — [Candidate] for [Job Title]"
        │     Body: "You've been selected as an interviewer for [Candidate Name]
        │            applying for [Job Title].
        │            
        │            📅 Click here to share your availability: [LINK]
        │            🔗 Or connect your Calendly for auto-detection: [CALENDLY_LINK]"
        │
        ├─ Sends same email to bob@company.com
        └─ Logs timeline event: "availability_requested"
```

### Phase 2: Panelist Responds

```
OPTION A — Manual Slot Selection:
  
  Panelist clicks availability link → Opens public form (no login)
    │
    ├─ Sees: "Select your available time slots for a 45-minute interview"
    ├─ Shows calendar picker (next 14 days, working hours)
    ├─ Panelist selects: Mon 10am-12pm, Tue 2pm-5pm, Wed 9am-11am
    ├─ Submits → available_slots saved as JSONB
    ├─ response_status → submitted
    └─ Timeline event: "availability_submitted" by alice@company.com

OPTION B — Calendly Auto-Detection:

  Panelist clicks "Connect your Calendly" link → OAuth flow
    │
    ├─ Redirects to Calendly authorization page
    ├─ Panelist authorizes → callback to our server
    ├─ System stores access_token + refresh_token in calendly_connections
    ├─ Calls GET /user_busy_times for next 14 days
    ├─ Inverts busy times → free slots
    ├─ Pre-fills the availability form with free slots
    ├─ Panelist reviews, adjusts if needed, submits
    ├─ calendly_connected = True
    └─ Same result: available_slots saved, status → submitted
```

### Phase 3: All Panelists Responded → Booking Link Sent

```
System detects: all panelists for this interview have status = submitted
  │
  ├─ Runs slot intersection algorithm:
  │     Alice: Mon 10-12, Tue 2-5, Wed 9-11
  │     Bob:   Mon 9-11, Tue 3-6, Wed 10-12
  │     ────────────────────────────────────
  │     Intersection (45-min blocks):
  │       Mon 10:00-10:45, Mon 10:45-11:00 (too short, skip)
  │       Tue 3:00-3:45, Tue 3:45-4:30, Tue 4:30-5:00 (too short)
  │       Wed 10:00-10:45, Wed 10:45-11:00 (too short)
  │     ────────────────────────────────────
  │     Available: Mon 10:00, Tue 3:00, Tue 3:45, Wed 10:00
  │
  ├─ Interview status → ready_to_book
  ├─ Generates booking token (5-day expiry)
  │
  └─ Enqueues ARQ job: `send_booking_link`
        │
        ├─ Sends email to candidate:
        │     Subject: "Book Your Interview — [Job Title] at [Company]"
        │     Body: "Great news! Your interview for [Job Title] is ready to be
        │            scheduled. Click below to pick a time that works for you.
        │            
        │            📅 Book your interview: [LINK]
        │            
        │            Available slots:
        │            • Monday, Mar 2 — 10:00 AM
        │            • Tuesday, Mar 3 — 3:00 PM, 3:45 PM
        │            • Wednesday, Mar 4 — 10:00 AM"
        │
        └─ Timeline event: "booking_link_sent"
```

### Phase 4: Candidate Books

```
Candidate clicks booking link → Opens public booking page
  │
  ├─ Sees available slots with dates/times (in candidate's detected timezone)
  ├─ Selects: Tuesday, Mar 3 at 3:00 PM
  ├─ Confirms booking
  │
  ├─ System updates interview:
  │     scheduled_start = 2026-03-03T15:00:00Z
  │     scheduled_end   = 2026-03-03T15:45:00Z
  │     status → scheduled
  │
  ├─ Generates ICS calendar invite file (RFC 5545)
  │     Event: "Interview: [Candidate] × [Company] — [Job Title]"
  │     Location: https://meet.google.com/xxx
  │     Attendees: alice@, bob@, candidate@
  │     Description: Round 1 — Technical Screen
  │
  ├─ Sends confirmation + ICS to candidate, alice, bob
  │     Subject: "Interview Confirmed — Tuesday, Mar 3 at 3:00 PM"
  │
  └─ Timeline event: "interview_booked"
```

### Phase 5: Reminders

```
ARQ Cron: send_interview_reminders (runs every 30 min)
  │
  ├─ Queries: interviews WHERE status = scheduled
  │           AND scheduled_start BETWEEN now AND now + 24h
  │           AND no "reminder_24h" timeline event exists
  │
  ├─ Sends 24-hour reminder email to all participants:
  │     "Reminder: Your interview is tomorrow at 3:00 PM"
  │
  ├─ Logs timeline: "reminder_24h_sent"
  │
  ├─ (Next run, within 1 hour of start):
  │     Sends 1-hour reminder: "Your interview starts in 1 hour"
  │     Logs timeline: "reminder_1h_sent"
  │
  └─ Idempotent: checks timeline events before sending to avoid duplicates
```

### Phase 6: Post-Interview → Feedback Collection

```
ARQ Cron: interview_status_cron (runs every 15 min)
  │
  ├─ Queries: interviews WHERE status = scheduled
  │           AND scheduled_end < now
  │
  ├─ Updates status → awaiting_feedback
  │
  └─ Enqueues: request_panel_feedback
        │
        ├─ Generates feedback tokens (14-day expiry) for each panelist
        ├─ Sends email to alice@company.com:
        │     Subject: "How Did the Interview Go? — [Candidate] for [Job Title]"
        │     Body: "The interview with [Candidate] has concluded.
        │            Please share your feedback:
        │            
        │            📝 Submit Feedback: [LINK]"
        │
        ├─ Sends same to bob@company.com
        └─ Timeline event: "feedback_requested"

Panelist clicks feedback link → Public feedback form
  │
  ├─ Fields:
  │     Overall Rating: strong_yes / yes / neutral / no / strong_no
  │     Technical Score: [1-10 slider]
  │     Communication Score: [1-10 slider]
  │     Culture Fit Score: [1-10 slider]
  │     Strengths: [text area]
  │     Concerns: [text area]
  │     Recommendation: Hire / Next Round / No Hire
  │     Notes: [text area]
  │
  ├─ Submits → saved to interview_assessments
  ├─ Token invalidated (one-time use)
  └─ Timeline event: "feedback_submitted" by alice@company.com

When ALL panelists submitted:
  └─ Interview status → feedback_collected
```

### Phase 7: HR Decides → Next Round or Final Decision

```
HR opens Interview tab on application detail page
  │
  ├─ Sees: Round 1 — Technical Screen ✅ Feedback Collected
  │     Alice: ⭐ Yes (Tech: 8, Comm: 7, Culture: 8) — "Strong on system design"
  │     Bob:   ⭐ Strong Yes (Tech: 9, Comm: 8, Culture: 9) — "Excellent candidate"
  │
  ├─ HR clicks "Advance to Round 2"
  │     application.current_round → 2
  │     application.stage → round_2
  │     Interview status → completed
  │     New interview created for Round 2 config
  │     → Flow repeats from Phase 1 with Round 2 panelists (carol@company.com)
  │
  ├─ OR HR clicks "Extend Offer"
  │     application.stage → offer
  │
  └─ OR HR clicks "Reject"
        application.stage → rejected

(Round 2 follows the exact same flow with carol@company.com as the panelist)
```

---

## 11. Implementation Phases

| Phase | What | Files | ~Days |
|-------|------|-------|-------|
| **1** | Enums + `ApplicationStage` refactor + `interview_round_configs` model + Alembic migration | `enums.py`, `application_model.py`, `job_model.py`, `interview_round_config_model.py`, migration | **2** |
| **2** | Interview + PanelistAvailability + Assessment + Timeline models + repositories | `interview_model.py`, `interview_repository.py`, `availability_repository.py` | **3** |
| **3** | Email service upgrade + HTML templates + ICS generator + slot intersection algorithm | `email_service.py`, `interview_email_templates.py`, `ics_generator.py`, `slot_intersection.py` | **3** |
| **4** | Interview service + auth-required routes + schemas | `interview_service.py`, `interview_schemas.py`, `interview_routes.py`, `dependency.py`, `main.py` | **3** |
| **5** | Public routes (availability form, booking page, feedback form) + signed JWT token service | `interview_public_routes.py` | **2** |
| **6** | ARQ jobs (all 5) + producer integration + worker registration | `interview_jobs.py`, `new_producer.py`, `worker.py` | **2** |
| **7** | Calendly OAuth for panelists (optional feature) + busy times integration | `calendly_service.py`, `calendly_connection_model.py` | **2** |

**Total: ~17 days**

---

## 12. Verification & Testing

### Unit Tests

- Slot intersection algorithm: overlapping, non-overlapping, single panelist, timezone edge cases
- Signed JWT generation + validation + expiry
- ICS file generation (validate against RFC 5545)
- Status transition state machine (valid vs. invalid transitions)
- Email template rendering

### Integration Tests

- Full flow: create round config → schedule → panelist submits availability → booking link generated → candidate books → reminders sent → feedback collected
- Bulk scheduling: 10 applications simultaneously
- Expired token handling (availability, booking, feedback)
- Calendly OAuth flow + busy times fetch

### Manual Testing

- Email rendering in Gmail, Outlook, Apple Mail
- ICS invite rendering in Google Calendar, Outlook Calendar, Apple Calendar
- Public form responsiveness (mobile + desktop)
- Timezone handling: panelist in IST, candidate in EST, HR in PST

### Load Testing

- 50 concurrent availability requests → verify email queue handles it
- SMTP rate limiting with Gmail (if > 500 emails/day, need SES/SendGrid)
