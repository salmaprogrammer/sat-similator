# SAT Practice Simulator — Flask/SQLAlchemy Build Plan

> Translates `sat-simulator-master-build-plan new.md` (Next.js/Prisma stack) into a Flask + SQLAlchemy web-app architecture. Every feature and screen from the original plan is preserved; only the stack and delivery patterns change. Trademark/competitor notes and screen-by-screen UX specs from the original document remain authoritative — this file is the how-we-build-it companion.

---

## 1. Stack

| Concern | Original | Flask version |
|---|---|---|
| Web framework | Next.js API routes | **Flask** blueprints + Jinja2 templates |
| ORM / migrations | Prisma | **SQLAlchemy 2.x** + **Flask-Migrate** (Alembic) |
| DB | Postgres | **Postgres** (SQLite for dev) |
| Auth | NextAuth/Clerk | **Flask-Login** + **Flask-WTF**; Authlib for Google OAuth |
| Client interactivity | React | **Alpine.js + HTMX**; a small vanilla JS module for the test engine (timer, keyboard shortcuts, strikethrough, calculator, highlight) |
| Background jobs | BullMQ + Redis | **Celery + Redis** |
| DOCX parsing | `mammoth` | **`python-docx`** |
| PDF parsing | `pdf-parse` | **`pdfplumber`** |
| Markdown | native | **`markdown`** |
| Math rendering | KaTeX | KaTeX (client-side, framework-agnostic) |
| Charts | Recharts | **Chart.js** in-browser; **matplotlib** for PDF export |
| PDF export | pdf toolchain | **WeasyPrint** (HTML → PDF) |
| LLM | Anthropic TS SDK | **`anthropic`** Python SDK |
| Storage | S3 | **`boto3`** (S3 / R2 / MinIO); local filesystem in dev |
| Google APIs | `googleapis` | **`google-api-python-client`** + Authlib |
| Payments | (implied) | **Stripe** Python SDK |
| Deploy | Vercel + managed PG | **Gunicorn** + nginx on Render / Fly.io / any Linux host |

**Ops rules (from project CLAUDE.md):** single entry point `flask_app.py`; before running kill port 5000 with `lsof -ti:5000 | xargs kill -9`; the DB path must be identical across app code, seed scripts, WSGI, and CLI commands — set it once in `config.py` and import from there.

---

## 2. Project structure

```
satsimilator/
├── flask_app.py              # entry point: create_app + CLI wiring
├── celery_worker.py          # celery -A celery_worker.celery worker
├── config.py                 # Config, DevConfig, ProdConfig
├── requirements.txt
├── .env.example
├── migrations/               # alembic
├── instance/                 # sqlite dev db, uploads (gitignored)
├── app/
│   ├── __init__.py           # create_app factory + blueprint registration
│   ├── extensions.py         # db, login_manager, migrate, celery, csrf, mail
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py           # User, Student, Teacher
│   │   ├── bank.py           # QuestionBank, Question, Choice
│   │   ├── exam.py           # Exam, ExamModule, ExamModuleQuestion
│   │   ├── attempt.py        # Attempt, AttemptModule, Response, AttemptScore
│   │   ├── ingest.py         # QuestionImport, QuestionImportItem
│   │   └── moderation.py     # QuestionReport
│   ├── blueprints/
│   │   ├── auth/             # login, signup, forgot pw
│   │   ├── onboarding/       # 11-step wizard
│   │   ├── student/          # dashboard, test library
│   │   ├── test_engine/      # /attempt/<id>/module/<n>/question/<q>
│   │   ├── results/          # /attempt/<id>/results
│   │   ├── teacher/          # bank, exam assembly, classes, ingestion, moderation
│   │   └── api/              # JSON endpoints (timer sync, save answer, etc.)
│   ├── services/
│   │   ├── timer.py          # server-authoritative attempt/module clocks
│   │   ├── grading.py        # numeric-equivalence for free-response
│   │   ├── adaptive.py       # module-2 easy/hard label resolution
│   │   ├── paygate.py        # ProGate helper for Jinja
│   │   ├── stripe_.py
│   │   ├── google_sync.py
│   │   └── ingest/
│   │       ├── parse_docx.py
│   │       ├── parse_pdf.py
│   │       ├── parse_md.py
│   │       └── llm_extract.py  # Anthropic call, versioned prompt
│   ├── tasks/
│   │   └── ingest.py         # parse_import(import_id) celery task
│   ├── templates/
│   │   ├── base.html
│   │   ├── auth/  onboarding/  student/  test/  results/  teacher/
│   │   └── partials/         # HTMX fragments
│   └── static/
│       ├── css/
│       └── js/
│           ├── test_engine.js  # timer, keyboard, strikethrough
│           ├── highlight.js
│           ├── calculator.js
│           └── vendor/         # KaTeX, Chart.js
└── tests/                    # pytest
```

---

## 3. SQLAlchemy schema

Translation of the Part 1 schema in the original plan (plus the v2 ingestion tables):

- **`User`** — id, email (unique), password_hash, role: `student`|`teacher`|`admin`, created_at
- **`Student`** — user_id FK, `accommodation` enum: `standard`|`time_and_a_half`|`double_time`, exam_type, test_date, current_score, goal_score, email_opt_in bool, study_days JSON, calendar_synced bool, pro_expires_at nullable
- **`Teacher`** — user_id FK, org nullable
- **`QuestionBank`** — id, teacher_id FK, name, is_public bool
- **`Question`** — id, bank_id FK, stem text, type: `mcq`|`grid_in`, topic, difficulty: `easy`|`medium`|`hard`, source: `authored`|`imported`, created_by FK
- **`Choice`** — id, question_id FK, label (A/B/C/D), text, is_correct bool
- **`Exam`** — id, name, teacher_id FK nullable (platform-owned when null), is_predicted_test bool
- **`ExamModule`** — id, exam_id FK, section: `rw`|`math`, module_number (1|2), time_limit_seconds, calculator_allowed bool, difficulty_variant: `easy`|`hard`|`fixed`
- **`ExamModuleQuestion`** — module_id FK, question_id FK, order_index
- **`Attempt`** — id, student_id FK, exam_id FK, status, started_at, completed_at nullable, accommodation_snapshot, feedback_nps int nullable, feedback_difficulty int nullable, feedback_text text nullable
- **`AttemptModule`** — attempt_id FK, module_id FK, started_at, submitted_at nullable, resolved_difficulty_label nullable (post-hoc: e.g. `Math – Module 2 (Easy)`), effective_time_limit_seconds *(module.time_limit × accommodation multiplier, snapshot at start)*
- **`Response`** — attempt_id FK, question_id FK, choice_id FK nullable, free_response_text nullable, marked_for_review bool, strikethrough_state JSON, time_spent_seconds int, is_correct bool
- **`AttemptScore`** — attempt_id FK, total, rw, math, per_topic JSON
- **`QuestionImport`** (v2) — id, teacher_id FK, filename, source_type: `pdf`|`docx`|`md`, file_url, status: `uploaded`|`parsing`|`parsed`|`failed`, error_reason nullable, prompt_version, created_at, parsed_at nullable
- **`QuestionImportItem`** (v2) — id, import_id FK, order_index, raw_text, parsed_stem text, parsed_choices JSON *(`[{label:'A', text:'...'}, ...]` or null for free-response)*, parsed_answer text *(choice label or JSON array of acceptable strings)*, answer_source enum: `extracted`|`ai_generated`|`missing`, confidence_score float nullable, suggested_topic nullable, suggested_difficulty nullable, status: `pending_review`|`approved`|`edited`|`rejected`, reviewed_by FK nullable, reviewed_at nullable, resulting_question_id FK nullable
- **`QuestionReport`** — student_id FK, question_id FK, attempt_id FK, reason, status: `open`|`resolved`|`dismissed`, created_at

---

## 4. Blueprints & routes

| Blueprint | Key routes |
|---|---|
| `auth` | `/login`, `/signup`, `/forgot`, `/logout` — no CAPTCHA (§2.1) |
| `onboarding` | `/onboarding/step/<n>` (1–11 per §2.2) |
| `student` | `/dashboard`, `/tests`, `/tests/<exam_id>/accommodations`, `/tests/<exam_id>/instructions`, `/tests/<exam_id>/start` |
| `test_engine` | `/attempt/<id>/module/<n>/question/<q>`, `/attempt/<id>/module/<n>/review` *(real submission gate per §2.6)*, `/attempt/<id>/break`, `/attempt/<id>/complete` |
| `api` | `POST /api/attempt/<id>/answer`, `POST /api/attempt/<id>/mark`, `GET /api/attempt/<id>/timer`, `POST /api/attempt/<id>/report`, `POST /api/attempt/<id>/save-and-exit`, `POST /api/attempt/<id>/strikethrough` |
| `results` | `/attempt/<id>/results`, `/attempt/<id>/results.pdf` |
| `teacher` | `/teacher/banks`, `/teacher/banks/<id>`, `/teacher/questions/new`, `/teacher/exams`, `/teacher/exams/new`, `/teacher/imports`, `/teacher/imports/<id>` *(§2.10 review screen — the reference image)*, `/teacher/classes`, `/teacher/moderation` |

---

## 5. Client-side interactivity strategy

**Full JS required** (browser-only state):

- Test-engine timer countdown, drift-corrected via HTMX poll to `/api/attempt/<id>/timer` every ~15s
- Keyboard shortcuts 1/2/3/4/Enter — listener must check `document.activeElement` and skip when inside grid-in / calculator inputs (§2.5)
- Per-choice strikethrough + global eliminate-toggle
- Calculator overlay — embed **Desmos** (their scientific/graphing calc is free and matches the SAT-day tool)
- Highlight tool — Selection API with saved offset ranges
- Break-screen countdown
- Confetti at completion

**HTMX-friendly** (server round-trip):

- Onboarding wizard steps
- Save answer, mark for review, report question, save-and-exit
- Ingestion review: approve/edit/reject per item, "Approve all and publish"
- Question navigator modal open/close

---

## 6. Background jobs (Celery + Redis)

Primary task: `parse_import(import_id)` implementing §2.10:

1. Fetch file from storage
2. Dispatch by `source_type` → text extraction (`python-docx` / `pdfplumber` / `markdown`)
3. Send extracted text to Anthropic with the versioned extraction prompt — model splits into questions, detects stem/choices, marks free-response, extracts explicit answer key if present, otherwise attempts to solve (with confidence score), otherwise leaves `answer_source: missing`
4. Insert one `QuestionImportItem` per detected question
5. Flip `QuestionImport.status` → `parsed` (or `failed` with `error_reason`)

Store `prompt_version` on every import so answers can be audited or re-run.

---

## 7. Build phases

| # | Phase | Deliverables |
|---|---|---|
| 1 | **Foundation** | Flask factory, config, SQLAlchemy models, Alembic migrations, Flask-Login scaffold, seed script, base template, static asset wiring |
| 2 | **Auth + Onboarding** | §2.1 login/signup, §2.2 11-step wizard, accommodations persisted on student profile |
| 3 | **Teacher: manual question authoring + exam assembly** | Bank CRUD, question CRUD (MCQ + grid-in), exam builder with ordered modules, publish |
| 4 | **Test engine core** | Split pane, question card, MCQ + grid-in, strikethrough + global eliminate toggle, keyboard shortcuts, Report + Mark for Review, server-authoritative timer, HTMX answer save |
| 5 | **Accommodations modal + time multiplier** | §2.3 modal; multiplier applied server-side at attempt start into `effective_time_limit_seconds` |
| 6 | **Navigator modal + "Check Your Work" page** | §2.6 both surfaces; the review page is a real route and the submission gate |
| 7 | **Break screen** | §2.7 dark surface, server-authoritative countdown, `allow_early_resume` flag for practice attempts |
| 8 | **Ingestion pipeline** | §2.10 upload → Celery task → Anthropic extraction → review UI matching the reference image → approve/edit/reject → publish into `questions`/`choices` |
| 9 | **Completion + survey** | §2.8 confetti, NPS + difficulty + free-text stored on `attempts` |
| 10 | **Results / report + ProGate** | §2.9 full report; `{% progate rows=2 %}` Jinja block for free/Pro gating; WeasyPrint PDF export |
| 11 | **Dashboard, predicted-test library, Google Sheets sync** | Original spec Phase 5 |
| 12 | **Paywall / Stripe** | Free/Pro plans, exam-date-scoped one-time payment |
| 13 | **Remaining teacher tooling** | Class rosters ("My Classes"), moderation queue for student-reported questions |
| 14 | **QA, load test, deploy** | pytest coverage, locust/k6 load test on test engine, prod deploy behind gunicorn + nginx |

---

## 8. Flask-specific risks worth naming up front

- **Server-authoritative timer under multiple gunicorn workers:** compute the deadline from `AttemptModule.started_at + effective_time_limit_seconds` on every request — never cache it in worker memory. Client polls `/api/attempt/<id>/timer` for drift correction and displays local countdown between polls.
- **Keyboard shortcut collisions:** the listener must inspect `document.activeElement` (or `tagName in {INPUT, TEXTAREA}`) before firing so grid-in inputs and the calculator popup don't get hijacked.
- **PDF parsing limits:** `pdfplumber` handles text PDFs; scanned/image-only PDFs need OCR (Tesseract), correctly punted post-v1. Surface the limitation in the teacher upload UI.
- **LLM cost + latency:** ingestion is async so latency is acceptable; batch multiple questions per Anthropic call, use prompt caching, and log `prompt_version` per item.
- **Answer persistence:** never rely on Flask session cookies for in-progress answers — POST every choice change to `/api/attempt/<id>/answer` so save-and-exit and crash recovery work.
- **Free-response grading:** implement `services/grading.py::numeric_equivalent(user_input, acceptable_set)` handling fractions, decimals, and unit-free numbers. Same function grades live responses AND validates ingested `parsed_answer` for free-response items — one representation shared by ingestion and the test engine (per §2.5 and §2.10).
- **CSRF on HTMX requests:** Flask-WTF CSRF must be threaded through HTMX headers; add a small template helper that injects the token into every HTMX request.
- **Adaptive-difficulty module labels:** after module 1 completes, run `services/adaptive.py::resolve_module2(attempt_id)` to select the module 2 variant and set `AttemptModule.resolved_difficulty_label` — this label is what the results page (§2.9) surfaces.
