# AI-Powered Intelligent Complaint Management and Resolution System

A full-stack web application to submit, classify, route, track and analyse civic complaints
(focus region: Hyderabad), built with React + FastAPI + PostgreSQL and AI/NLP modules.

## Module status

| # | Module | Status |
|---|--------|--------|
| 1 | Foundation (FastAPI app, config, health checks, Alembic, React shell, design system) | Done, tested |
| 2 | Authentication and user management (JWT, roles, profile, password reset, admin users, audit log) | Done, tested |
| 3 | Complaint submission and tracking (form, photos, reference numbers, lifecycle, comments, privacy) | Done, tested |
| 4 | Department routing, staff roles, assignment and in-app notifications | Done, tested |
| 5 | AI classification, priority, sentiment, duplicate detection (synthetic training data) | Done, tested |
| 6 | Dashboards and analytics (user stats, admin analytics with charts and filters) | Done, tested |
| 7 | PDF / Excel reports (role-scoped, audited admin exports) | Done, tested |
| 8 | Location-aware complaint assistant (verified Hyderabad offices, map, directions, hybrid keyword + ML detection) | Done, tested |
| 9 | Image analysis (OpenCV quality checks + YOLOv8n COCO objects) | Done, tested |
| 10 | Voice input (en-IN / te-IN), text-to-speech, Telugu translation for review | Done, tested |
| 11 | Feedback after resolution, AI prediction review and corrections export, deployment docs, viva guide | Done, tested |

"Done, tested" means automated tests pass (backend pytest + frontend Vitest) and the feature was exercised in a
browser. It is **not deployed online** yet (see `docs/deployment.md`).

## Documentation

| Document | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | system, lifecycle and request-flow diagrams; design decisions |
| [docs/ai_dataset.md](docs/ai_dataset.md) | how the **synthetic** training data was generated and its limitations |
| [docs/ai_evaluation.md](docs/ai_evaluation.md) | generated evaluation report (precision/recall/F1, confusion matrix) |
| [docs/office_data_sources.md](docs/office_data_sources.md) | official source for every office/helpline/portal record |
| [docs/deployment.md](docs/deployment.md) | production configuration and deployment steps |
| [docs/viva_guide.md](docs/viva_guide.md) | demo script, honest answers to likely questions, limitations |
| http://localhost:8000/docs | interactive API documentation (Swagger UI) |

## Tech stack

- **Frontend:** React 19, TypeScript, Vite 6, Tailwind CSS 4, React Router 7, Axios, Recharts, Leaflet, Vitest
- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pytest
- **AI / ML:** scikit-learn (TF-IDF + logistic regression), rule-based priority and sentiment, YOLOv8n + OpenCV,
  optional Google Gemini (rephrasing and translation only)
- **Reports:** ReportLab (PDF), OpenPyXL (Excel)
- **Database:** PostgreSQL 16

## Prerequisites (Windows)

- Python 3.12 (`py -3.12 --version`)
- Node.js 20+ (`node --version`)
- PostgreSQL 16 running on `localhost:5432`
  (installed natively; `docker-compose.yml` is provided as an alternative where Docker works)

## One-time setup

### 1. Database

Using `psql` as the `postgres` superuser:

```sql
CREATE ROLE complaints LOGIN PASSWORD 'choose-a-password';
CREATE DATABASE complaints OWNER complaints;
CREATE DATABASE complaints_test OWNER complaints;
```

### 2. Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env      # then set DATABASE_URL and JWT_SECRET_KEY
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m app.scripts.create_admin   # first administrator (uses SEED_ADMIN_* or prompts)
.\.venv\Scripts\python.exe -m app.scripts.load_offices   # verified Hyderabad offices for the assistant
.\.venv\Scripts\python.exe -m app.scripts.seed_demo --reset   # optional: FICTIONAL demo data (replaces all complaints)
```

The demo loader creates 6 fictional citizens, 6 department staff and 40 complaints at every stage, with
history, comments, assignments, AI predictions and feedback. Demo accounts end in `...demo@example.com` and
share the password `DEMO_PASSWORD` from `backend/.env` (generated on first run).

### 3. Frontend

```powershell
cd frontend
npm install
copy .env.example .env.local
```

## Running locally

Backend (terminal 1):

```powershell
cd backend
.\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

Frontend (terminal 2):

```powershell
cd frontend
npm run dev
```

- App: http://localhost:5173 (System status page: http://localhost:5173/status)
- API docs (Swagger): http://localhost:8000/docs

## API endpoints

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/v1/health` | `{"status":"ok","app":"...","environment":"development"}` |
| GET | `/api/v1/health/db` | `200 {"status":"ok","database":"reachable"}` or `503 {"status":"unavailable","database":"unreachable"}` |
| POST | `/api/v1/auth/register` | `201` user (`id, full_name, email, role, is_active, created_at, last_login_at`); `409` duplicate email; `422` invalid input |
| POST | `/api/v1/auth/login` | `200 {access_token, refresh_token, token_type, expires_in, user}`; `401` wrong credentials; `403` disabled |
| POST | `/api/v1/auth/refresh` | `200` new token pair; the old refresh token is revoked (rotation) |
| POST | `/api/v1/auth/logout` | `204`; revokes the access token and the given refresh token |
| POST | `/api/v1/auth/forgot-password` | `202` generic message (same response whether or not the email exists) |
| POST | `/api/v1/auth/reset-password` | `204`; `400` invalid/expired/used token |
| GET / PATCH | `/api/v1/users/me` | current user / update full name |
| POST | `/api/v1/users/me/change-password` | `200` new token pair; all older sessions are signed out |
| GET | `/api/v1/admin/users?search=&role=&limit=&offset=` | admin only: `{items, total}` |
| PATCH | `/api/v1/admin/users/{id}` | admin only: change `role` / `is_active` (not your own account); audited |
| GET | `/api/v1/admin/audit-logs` | admin only: `{items, total}` |

| GET | `/api/v1/categories` | active categories with their routed department |
| POST | `/api/v1/complaints` | multipart form: `subject, description, category_id, location_text`, optional `latitude, longitude, incident_at` (ISO with timezone), up to 3 `attachments` (JPEG/PNG/WebP, 5 MB each). `201` complaint detail with `reference_number` |
| GET | `/api/v1/complaints?status=&category_id=&priority=&search=&sort=&mine=&limit=&offset=` | users: own complaints only; admins: all (or `mine=true`) |
| GET | `/api/v1/complaints/{id}` | detail incl. history, comments, attachments, `allowed_transitions`; `404` if not yours |
| GET | `/api/v1/complaints/reference/{ref}` | same, looked up by reference number (case-insensitive) |
| POST | `/api/v1/complaints/{id}/comments` | `{body, is_internal}`; internal notes are admin-only and hidden from complainants |
| POST | `/api/v1/complaints/{id}/status` | `{status, note}`; transitions enforced server-side (see below) |
| GET | `/api/v1/complaints/{id}/attachments/{attachment_id}` | the image, only for people allowed to view the complaint |

### Dashboards, analytics and reports (modules 6-7)

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/v1/dashboard/summary` | any user, own complaints only: `{total, pending, by_status: {submitted, assigned, in_progress, resolved, closed}, recent_updates: [{complaint_id, reference_number, subject, from_status, to_status, note, at}]}` (10 latest status changes) |
| GET | `/api/v1/dashboard/analytics?date_from=&date_to=&category_id=&department_id=&status=` | admin only (`403` otherwise): `{generated_at, filters, totals: {total, open, pending, in_progress, resolved, closed}, by_status, by_priority (incl. not_assessed), by_category, by_department (id null = "Unassigned"), trend: {granularity: day\|week, points: [{period_start, created, resolved}]}, resolution: {average_hours, median_hours, sample_size}, oldest_open (5)}` |
| GET | `/api/v1/reports/complaints.pdf?…&search=` | landscape A4 PDF: title, generated time (IST), scope, filters, summary counts, table with repeating header and "Page X of Y" |
| GET | `/api/v1/reports/complaints.xlsx?…&search=` | Excel workbook: "Complaints" (bold frozen header, autofilter, real date cells in IST) and "Summary" (filters, counts by status/category) |

- **Dates** (`date_from`, `date_to`, `YYYY-MM-DD`) filter on the filing time and are inclusive calendar days in
  India Standard Time: `date_to=2026-10-31` means "filed before 2026-11-01 00:00 IST". `date_from` after `date_to` returns `400`.
- **Trend:** daily buckets, or ISO weeks (starting Monday) when the range is longer than 90 days. Without `date_from`
  the range starts at the earliest matching complaint; without `date_to` it ends today (IST). "Created" counts
  complaints filed in each period; "resolved" counts complaints whose `resolved_at` falls in the period
  (whenever they were filed), with the category/department/status filters applied.
- **Resolution time** = `resolved_at - created_at`, averaged (and median) only over complaints that have a
  `resolved_at`; `sample_size` is reported with it. Complaints closed without being resolved are not included.
- **Who sees what:** one helper (`app/services/complaint_scope.py`) decides scope: admins see all complaints,
  everyone else only their own. Analytics are admin-only; reports are available to every user but scoped.
- **Privacy in reports:** no email addresses or phone numbers; the complainant's full name appears only in admin exports.
  Admin exports are audit-logged as `report.exported` with the filters, format and row count.
- **Limits:** at most 5,000 rows per report (newest first); the report states when it is truncated.
  The PDF uses the built-in Helvetica font, so non-Latin text (e.g. Telugu subjects) does not render in PDFs; Excel is unaffected.

Frontend: dashboard stat cards and "Recent updates" (`/app`), admin analytics with filters, KPI cards and charts
(`/app/admin/analytics`, each chart has a text summary and a data table), and report downloads (`/app/reports`).

### Complaint lifecycle

```
submitted -> assigned -> in_progress -> resolved -> closed
                              ^             |
                              +-- reopen ---+
```

- Admins drive the lifecycle and may close early (e.g. duplicate) with a reason.
- The complainant may confirm a resolution (resolved -> closed) or reopen it (resolved -> in_progress) with a reason.
- A note is required to resolve, to reopen, and to close before resolution. Every change is recorded in the history.
- Priority is predicted by the AI module at submission (`priority_source = ai`, shown as "AI-predicted") until staff set it (`priority_source = staff`).

### Departments, staff, assignment and notifications (module 4)

| Method | Path | Response |
|--------|------|----------|
| GET / POST | `/api/v1/admin/departments` | admin only: all departments (incl. inactive) / create `{name, description?, contact_email?, is_active?}`; `409` duplicate name; audited |
| PATCH | `/api/v1/admin/departments/{id}` | admin only: partial update; `409` duplicate name or deactivating a department that still has active categories; audited |
| GET / POST | `/api/v1/admin/categories` | admin only: all categories with department mapping / create `{name, slug, description?, department_id, is_active?}`; `409` duplicate name/slug; `400` inactive department; audited |
| PATCH | `/api/v1/admin/categories/{id}` | admin only: partial update incl. re-mapping `department_id` (affects only complaints filed afterwards); audited |
| GET | `/api/v1/departments/{id}/staff` | active staff of a department (assignment candidates); admins: any department, staff: own only (`403` otherwise) |
| PATCH | `/api/v1/admin/users/{id}` | now also accepts `role: "staff"` + `department_id` (required for staff, cleared for other roles); `UserOut` includes `department` |
| POST | `/api/v1/complaints/{id}/assign` | `{department_id?, assignee_id?, note?}`; admins may re-route and/or assign, staff assign within their department. The assignee must be an active staff member of the (new) department. A `submitted` complaint that gets an assignee moves to `assigned`. Audited |
| GET | `/api/v1/notifications?unread_only=&limit=&offset=` | own notifications, newest first: `{items, total, unread}` |
| POST | `/api/v1/notifications/{id}/read` | mark one as read (`404` if it is not yours) |
| POST | `/api/v1/notifications/read-all` | `{updated}` |

- Roles: `user` (citizen), `staff` (department officer), `admin`. Admins manage every complaint; staff see,
  move and add internal notes only on complaints whose stored department is their own (others are `404`).
  `mine=true` on the list restricts admins/staff to complaints they filed themselves.
- Complaint detail adds `assigned_to`, `assignments` (routing history, only for managers) and `can_manage`.
- Notifications: the complainant on status changes and public comments by others; the assignee on assignment;
  the assignee (or, if unassigned, all active department staff) when the complainant comments or reopens.
  Notification failures are logged and never fail the main action.

Uploaded images are identified by their file contents (magic bytes), not by name or declared type, stored
under random names in `backend/uploads/` (git-ignored), and served only through the authorized endpoint.

Rate limits: register, login, refresh, forgot/reset password and change password allow
5 attempts per minute per client IP (`429` with `Retry-After` when exceeded). The limiter is in-memory,
so limits apply per server process.

### AI analysis (module 5)

The category classifier, priority rules, sentiment lexicon and duplicate detection are described in
[docs/ai_dataset.md](docs/ai_dataset.md); measured results are in [docs/ai_evaluation.md](docs/ai_evaluation.md)
(generated by the training script). **The training data is synthetic**, so those scores overestimate
real-world performance. The trained model (`backend/app/ai/artifacts/category_model.joblib`) is committed;
retrain with `.\.venv\Scripts\python.exe -m app.ai.train` from `backend/`. If the model file is missing, the
API reports `model_status: "not_trained"` and the rule-based parts keep working.

| Method | Path | Response |
|--------|------|----------|
| POST | `/api/v1/ai/analyze` | `{subject, description, latitude?, longitude?, category_id?}` -> suggested `category` + `alternatives` (top 3) with confidence, routed `department`, `priority {level, factors}`, `sentiment`, `possible_emergency` + `emergency_message`, possible `duplicates`, `model_version`, `disclaimer`. Login required; 30 requests/min per IP. Non-staff only see `reference_number`, `status`, `similarity` of duplicates. Nothing is stored |
| GET | `/api/v1/complaints/{id}/ai` | staff only: prediction stored at submission + fresh similar complaints |
| PATCH | `/api/v1/complaints/{id}/priority` | staff only: `{priority, note?}`; sets `priority_source = staff`, adds a history entry and an audit-log entry (`complaint.priority_override`) |

`POST /api/v1/complaints` also accepts an optional `ai_category_accepted` form field (true/false). The AI
analysis runs after the complaint is saved and never blocks a submission. Emergency guidance (call 112) is
shown instantly from keyword rules while typing; it is never a verified emergency.

### Complaint assistant, photos, voice and translation (modules 8-10)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/chatbot/message` | `{messages, location?}` → reply, detected category, verified offices/channels with source URL and verification date, map/directions links, steps |
| GET | `/api/v1/offices?category=&lat=&lng=` | verified offices and online channels, nearest first |
| POST | `/api/v1/ai/image-analysis` | multipart `image` → quality checks + YOLOv8n COCO detections + hints (nothing stored) |
| GET | `/api/v1/complaints/{id}/attachments/{aid}/analysis` | same, for a stored photo (cached) |
| POST | `/api/v1/ai/translate` | Telugu ↔ English for review only; `503` without a Gemini key |

### Feedback and AI review (module 11)

| Method | Path | Notes |
|---|---|---|
| POST / GET | `/api/v1/complaints/{id}/feedback` | complainant only, once, after resolution: rating 1-5, resolved?, AI helpful?, comment |
| GET | `/api/v1/admin/ai-review?review_status=&flagged_only=` | admin: predictions with disagreement signals |
| PATCH | `/api/v1/admin/ai-review/{prediction_id}` | admin: mark `correct` / `incorrect` (+ corrected category, note); audited |
| GET | `/api/v1/admin/ai-review/summary` | agreement and acceptance rates, ratings (usage signals, not model accuracy) |
| GET | `/api/v1/admin/ai-review/corrections.csv` | reviewed corrections for a manual retraining run; audited |

Reviews and feedback **never retrain the model automatically**.

### Password reset email

Set `SMTP_*` in `backend/.env` to send real email. Without SMTP, **development mode only** prints the
reset email (including the link) to the backend console; other environments log an error and send nothing.
The reset token is placed in the URL fragment (`#token=...`), so it is never sent to a server or written
to access logs, and the page removes it from the address bar after reading it.

## Tests

```powershell
cd backend;  .\.venv\Scripts\python.exe -m pytest -q
cd frontend; npm test; npm run typecheck
```

## Environment variables

Backend (`backend/.env`, see `.env.example`): `DATABASE_URL`, `CORS_ORIGINS`, `FRONTEND_URL`, `ENVIRONMENT`,
`LOG_LEVEL`, `JWT_SECRET_KEY` (required, 32+ characters), token lifetimes, rate-limit settings, optional `SMTP_*`,
and `SEED_ADMIN_*` for the first administrator.
Tests use a separate database named `<your database>_test` (e.g. `complaints_test`), which must exist; set
`TEST_DATABASE_URL` to use another test database (its name must end in `_test` or `_test_<suffix>`).
Frontend (`frontend/.env.local`): `VITE_API_BASE_URL`. Only `VITE_` values reach the browser, so never put secrets there.

## Project structure

```
backend/   FastAPI app (api, core, db, models, schemas, services, repositories,
           ai, chatbot, location, reports), alembic/, tests/
frontend/  React app (components, pages, layouts, services, hooks, types, utils)
docs/      Architecture, API and viva documentation
```
