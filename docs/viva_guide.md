# Demo and viva guide

A step-by-step script for the final-year review, plus honest answers to the questions examiners usually ask.
All demo people and complaints are **fictional** (created by `python -m app.scripts.seed_demo --reset`).

## Before the demo (10 minutes earlier)

1. Start PostgreSQL (it runs as a Windows service after installation).
2. Reset the demo data so every screen looks the same as in rehearsal:

   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m app.scripts.seed_demo --reset
   ```

3. Start the backend and frontend in two terminals (see README), open http://localhost:5173.
4. Keep `backend/.env` open privately for the passwords: `SEED_ADMIN_PASSWORD` (admin) and
   `DEMO_PASSWORD` (all demo citizens and staff).

| Role | Login | Shows |
|---|---|---|
| Citizen | `lakshmi.demo@example.com` | dashboard, filing with AI, tracking, feedback, assistant |
| Department staff | `kiran.staff.demo@example.com` (Sewerage & Drainage) | department queue, assignment, status changes |
| Administrator | `admin@example.com` | analytics, reports, user/department management, AI review, audit log |

## Demo script (about 12 minutes)

1. **Landing page (30 s).** Explain the problem: citizens do not know where to complain, departments get
   mis-routed and duplicate complaints. Point out the 112 emergency note.
2. **Citizen: complaint assistant (2 min).** Sign in as Lakshmi → *Complaint assistant* → click
   "Drainage problem in my area". Show: detected category, official helplines/portals with **source link and
   verification date**, then type "Ameerpet" as locality → map markers and straight-line distances →
   "File a complaint in this category".
3. **Citizen: filing with AI (3 min).** On the form, type a description mentioning a *live electric wire*.
   Show: the red 112 banner appears instantly (keyword rule), AI suggests the category with confidence and
   alternatives, predicted priority **with reasons**, and possible duplicates (the Ameerpet drain pair).
   Optionally use the microphone (English or Telugu), attach a photo and click *Analyse photo*.
   Submit → reference number.
4. **Staff: handling (2 min).** Sign in as Kiran → *Department complaints* (only Sewerage & Drainage) →
   open a complaint → assign / start work / resolve with a note; add an internal note.
5. **Citizen: closure and feedback (1 min).** Back as Lakshmi → notifications bell → confirm resolution →
   star rating.
6. **Admin (3 min).** *Analytics* (charts from real records, filters), *Reports* (download PDF and Excel),
   *AI review* (predictions people disagreed with, e.g. "Transformer making loud noise" predicted as Noise
   Pollution but filed as Electricity; mark incorrect; export corrections), *Audit log*.

If something fails live, say what the error message says; every API error is shown in the UI.

## Architecture in one minute

React SPA → FastAPI REST API (`/api/v1`, JWT) → services → repositories → PostgreSQL. AI, chatbot, location
and reports are separate packages. See `docs/architecture.md` for diagrams. Swagger: http://localhost:8000/docs.

## Honest answers to likely questions

**"What is your model's accuracy?"**
The category classifier is TF-IDF + logistic regression trained on a **synthetic dataset I generated**
(2,400 rows, 12 categories; `docs/ai_dataset.md`). On a random held-out split it scores 1.000, but that is an
artefact: test rows reuse the training templates. A stricter split that holds out whole scenarios gives
**accuracy 0.597, macro F1 0.560** — a more honest estimate, and real complaints would likely score lower.
The priority rules agree with the synthetic labels **73.3%** of the time (98.1% within one level), and the
emergency rules flag **85.7%** of rows labelled critical. All numbers are in `docs/ai_evaluation.md`,
produced by `python -m app.ai.train`. To claim real accuracy we would need labelled real complaints.

**"Why synthetic data?"** No public, labelled dataset of Hyderabad civic complaints was available. The
generator is deterministic and documented, so results are reproducible.

**"What does the AI decide?"** Nothing on its own. It *suggests* a category (the citizen chooses), *predicts*
a priority (staff can override; the UI labels it "AI-predicted" vs "set by staff") and lists *possible*
duplicates (never rejects a complaint). Emergency guidance comes from simple keyword rules, shown instantly.

**"Can YOLO detect potholes?"** No. YOLOv8n is a general model trained on 80 everyday object classes (COCO).
It reports objects such as vehicles or animals and image quality (blur, brightness). The UI says so, and its
category hints are never applied automatically. Detecting potholes would need a custom-trained model.

**"Where does the chatbot's office data come from?"** 20 records, each copied from an official government
website, with source URL and verification date stored (`docs/office_data_sources.md`). The bot only shows
stored contacts; if Gemini is enabled, its reply is discarded when it mentions any phone, URL or email that
is not in the retrieved records. Distances are straight-line and only shown when coordinates exist.

**"How is the system secured?"** Argon2id password hashing; short-lived JWT access tokens with rotating,
revocable refresh tokens; server-side role checks on every endpoint (citizens see only their complaints,
staff only their department's, others get 404); rate limits on login and AI endpoints; uploaded files
validated by content and decoded before storing; audit log for administrative actions; secrets in `.env`.

**"Is it deployed?"** Not yet; it runs locally. `docs/deployment.md` describes how to deploy it.

## Known limitations (say them before you are asked)

- AI metrics come from synthetic data; real-world accuracy is unknown.
- Keyword rules (emergency, chatbot) can miss paraphrases; the 112 banner is guidance, not a verified emergency.
- YOLOv8n cannot detect civic problems such as potholes or garbage.
- Office data covers city-level offices and portals, not every zonal office; it must be re-verified periodically.
- Rate limiting is in-memory (per server process); a multi-server deployment would use Redis.
- Speech recognition depends on the browser (Chrome/Edge send audio to the vendor's service).
- Gemini features (chatbot phrasing, Telugu translation) need an API key; without it, template fallbacks are used.

## Future work

Collect and label real complaints (with consent) and retrain; a custom image model for potholes/garbage;
SMS/email notifications; zonal office data via official APIs; multilingual classifier for Telugu text.
