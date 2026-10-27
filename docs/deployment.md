# Deployment guide

> **Status:** the application runs locally. It has **not** been deployed online yet. This guide describes how
> to deploy it; follow it and verify each step before claiming a deployment.

## What you deploy

| Part | Technology | Notes |
|---|---|---|
| Frontend | static files from `npm run build` (`frontend/dist`) | any static host (Netlify, Vercel, Nginx, S3 + CDN) |
| Backend | FastAPI app (`uvicorn app.main:app`) | Python 3.12 host or container |
| Database | PostgreSQL 16 | managed service recommended (backups) |
| Files | `backend/uploads/` (complaint photos) | persistent disk or object storage |
| Model files | `backend/app/ai/artifacts/category_model.joblib` (committed), `backend/app/ai/weights/yolov8n.pt` (downloaded on first use) | allow outbound HTTPS once, or copy the `.pt` file in |

## 1. Database

```sql
CREATE ROLE complaints LOGIN PASSWORD '<strong password>';
CREATE DATABASE complaints OWNER complaints;
```

## 2. Backend configuration (`backend/.env` or host environment variables)

Required in production:

| Variable | Production value |
|---|---|
| `ENVIRONMENT` | `production` (disables development-only behaviour such as printing reset emails) |
| `DATABASE_URL` | `postgresql+psycopg://complaints:<password>@<host>:5432/complaints` |
| `JWT_SECRET_KEY` | a new random secret, 32+ characters: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `CORS_ORIGINS` | the exact frontend origin, e.g. `https://resolveai.example.org` (never `*`) |
| `FRONTEND_URL` | same origin, used in password-reset links |
| `SMTP_*` | a real mail service, otherwise password reset emails cannot be delivered |
| `NOMINATIM_CONTACT_EMAIL` | your contact email (OpenStreetMap usage policy) |
| `GOOGLE_CLIENT_ID` | optional, enables "Continue with Google" (see below) |

Optional: `GEMINI_API_KEY` (chatbot phrasing and Telugu translation), vision and rate-limit settings
(see `backend/.env.example`). Never commit `.env`.

### Optional: "Continue with Google"

1. Google Cloud Console → **APIs & Services → OAuth consent screen**: app name "ResolveAI", user type
   External, your support email; add yourself as a test user while the app is in "Testing".
2. **Credentials → Create credentials → OAuth client ID → Web application.**
   *Authorized JavaScript origins*: `http://localhost:5173` and your site, e.g. `https://<project>.vercel.app`.
   No redirect URI is needed (the button uses a popup and returns an ID token).
3. Copy the **Client ID** (ends in `.apps.googleusercontent.com`) into `GOOGLE_CLIENT_ID` on the backend.
   It is public by design; there is no client secret in this flow. The backend verifies every Google token's
   signature, issuer, expiry and audience, and only accepts verified Google emails.

## 3. Install, migrate and load reference data

```bash
cd backend
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head                      # creates all tables and seeds categories/departments
python -m app.scripts.load_offices        # verified Hyderabad offices for the assistant
python -m app.scripts.create_admin        # first administrator (prompts or uses SEED_ADMIN_*)
```

Do **not** run `seed_demo` in production: it creates fictional demo data.

## 4. Run the backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers
```

- Use **one worker** unless you move the in-memory rate limiter and geocoding cache to Redis; with several
  workers each process keeps its own counters.
- Put it behind a reverse proxy (Nginx, Caddy or the platform's HTTPS) and serve **HTTPS only**.
- Behind a proxy, configure it to pass the real client IP (`X-Forwarded-For`) and run uvicorn with
  `--proxy-headers --forwarded-allow-ips=<proxy IP>`, otherwise rate limits apply to the proxy's IP.
- Health checks: `GET /api/v1/health` (process up) and `GET /api/v1/health/db` (database reachable, 503 if not).
- Logs go to stdout in `key=value` format; collect them with the platform's log viewer.

## 5. Build and host the frontend

```bash
cd frontend
npm ci
echo "VITE_API_BASE_URL=https://api.resolveai.example.org/api/v1" > .env.production
npm run build        # outputs frontend/dist
```

Serve `dist/` as a single-page app: unknown paths must return `index.html` (e.g. Nginx
`try_files $uri /index.html;`, Netlify `_redirects`: `/* /index.html 200`).

## 6. After deploying, verify

1. `GET /api/v1/health` and `/api/v1/health/db` return 200.
2. Register, log in, file a complaint with a photo, see it in the admin view.
3. Password reset email arrives.
4. The browser console shows no CORS errors.
5. Back up the database and the uploads folder on a schedule, and test a restore.

## Docker (optional)

`docker-compose.yml` starts PostgreSQL only (Docker Desktop did not run on the development machine, so the
app itself is not containerised yet). A production container would use `python:3.12-slim`, install
`requirements.txt`, copy `backend/`, run `alembic upgrade head` at start, then the uvicorn command above.
