# SAT Practice Simulator — Master Build Plan (consolidated, v2)

> **v2 changelog:** adds a full spec for teacher-side **question ingestion from uploaded documents** (PDF / DOCX / Markdown), with automatic question + answer extraction, AI-generated answers where none are present in the source, a mandatory human review/approval step, and manual answer entry as a fallback. This closes part of the "teacher tooling" gap flagged in Part 3 of the prior version. New/changed material is marked **NEW (v2)**. Everything else is unchanged from the prior consolidated plan and is still authoritative.
>
> **This document supersedes and merges** `sat-simulator-technical-spec.md` (architecture/schema/phases) and `sat-simulator-ui-reference-spec.md` (first 18 screenshots) with 20 additional screenshots covering: accommodations, keyboard shortcuts, the "More" menu, the end-of-module review page, the break screen, math-specific tools, the test-completion flow, and the full results/analytics report, plus this round's teacher question-ingestion spec. Hand this single file to a build agent — it's the complete picture.
>
> **Trademark/competitor note (unchanged):** "SAT" is a College Board trademark; this product must be independently branded with a disclaimer. The screenshots referenced are of a real, operating product (OnePrep) plus the official-style Bluebook test engine. Rebuild the *pattern* — screen order, interaction model, information architecture — with original visual design, copy, and branding. Do not copy their logo, mascot art, pink "Pro" color system, or product name.

---

## Part 1 — Architecture

**Stack:** Next.js + TypeScript frontend, Postgres/Prisma backend, NextAuth/Clerk auth, S3-compatible storage, `mammoth`/`pdf-parse` for document parsing, KaTeX for math rendering, Recharts for charts, BullMQ+Redis for background parsing jobs, `googleapis` for Sheets/Calendar sync, an LLM provider (Anthropic API) for question/answer extraction **NEW (v2)**, hosted on Vercel + managed Postgres.

**Core schema** (users/students/teachers, question_banks/questions/choices, exams/exam_modules/exam_module_questions, attempts/responses/attempt_scores) — see the original technical spec for full DDL-level detail. **Fields confirmed needed across both rounds:**

```
students.accommodation (enum: standard | time_and_a_half | double_time)  -- §2.3
exam_modules.difficulty_variant now confirmed real in production: label module 2
   as e.g. "Math – Module 2 (Easy)" / "(Hard)" post-hoc based on module-1 performance
attempts.feedback_nps int nullable, attempts.feedback_difficulty int nullable,
   attempts.feedback_text text nullable   -- post-test survey, §2.8
responses already has time_spent_seconds — confirmed needed: results page shows
   per-difficulty average time (Easy/Medium/Hard) as a real reported metric, §2.9
responses.free_response_text  -- grid-in answers, §2.5
```

**NEW (v2) — question ingestion tables**, feeding into the existing `questions`/`choices` tables rather than replacing them:

```
question_imports (
  id, teacher_id, filename, source_type (pdf | docx | md),
  file_url, status (uploaded | parsing | parsed | failed),
  created_at, parsed_at
)

question_import_items (
  id, import_id, order_index,
  raw_text,                                 -- the original extracted chunk, for teacher reference
  parsed_stem text,
  parsed_choices jsonb,                     -- [{label:'A', text:'...'}, ...] or null for free-response
  parsed_answer text,                       -- choice label, or a JSON array of acceptable strings for free-response
  answer_source (extracted | ai_generated | missing),
  confidence_score float nullable,          -- set when answer_source = ai_generated
  suggested_topic text nullable,
  suggested_difficulty text nullable,
  status (pending_review | approved | edited | rejected),
  reviewed_by, reviewed_at,
  resulting_question_id nullable references questions(id)
)
```

**Six original build phases still stand.** Phase 3 (teacher tooling) now has a concrete spec for its document-ingestion piece — see §2.10 below and the updated priority table in Part 4. Phase 4 (simulator engine) and Phase 4.5 (results/report + paywall gating) are unchanged from the prior round.

---

## Part 2 — Full screen-by-screen UX spec

### 2.1 Auth (no CAPTCHA)
Login is email/username and password only — no CAPTCHA field. "Forgot password" link, "Sign Up" footer link. If bot/credential-stuffing protection is needed later, prefer invisible rate-limiting or a CAPTCHA that only appears after repeated failed attempts, rather than showing it on every login.

### 2.2 Onboarding wizard (11 steps)
Role → exam type → test date → current score → goal score → proof chart → email opt-in → study-plan start → study days → calendar sync → paywall.

### 2.3 Accommodations modal
Shown once, before a timed test begins:
- Modal title: "Do you need extra time?"
- Three full-width selectable rows, radio-style: **Standard time**, **Time and a half (1.5x)** — 50% more time per module, **Double time (2x)** — 100% more time per module
- Footer: **Cancel** (ghost) / **Continue** (accent-filled, disabled-looking until a choice differs from default — default is Standard, always selectable)

**Build note:** store as `students.accommodation`, apply as a multiplier to every `exam_modules.time_limit_seconds` at attempt-start time server-side — never trust a client-side multiplier.

### 2.4 Pre-test instructions
The 4-rule info card (Timing / Scores / Assistive Technology / Lockdown).

### 2.5 The test-taking screen

**Header bar, confirmed tool set by section:**
| Tool | Reading & Writing | Math |
|---|---|---|
| Directions (expandable, top-left) | ✓ | ✓ |
| Timer + Hide toggle (center) | ✓ | ✓ |
| Highlight | ✓ | ✓ |
| Calculator | — | ✓ |
| Reference (formula sheet) | — | ✓ |
| More (⋯ overflow) | ✓ | ✓ |

**The "More" menu:**
- **Save and Exit** — pauses the attempt and returns to dashboard; must resume from the same question/timer state
- **Fullscreen** — toggles browser fullscreen for the test surface
- **Keyboard shortcuts** — opens a reference of the shortcuts below
- **Switch to dark mode** — a per-session/per-user theme toggle, scoped to (at least) the test screen
- **Bug Report** — opens a lightweight report form; route this to your support/feedback pipeline, not silently discarded

**Keyboard shortcuts**, shown as an inline tip under the answer choices:
- Press **1 / 2 / 3 / 4** to select choice A/B/C/D
- Press **Enter** to advance to the next question
- Implement as a real `keydown` listener scoped to the question view; must not fire while a text input (e.g. grid-in answer, calculator) has focus

**Question card:**
- Next to "Mark for Review," a **Report** link (flag icon) lets the student flag a bad/ambiguous question — route this to a moderation queue for teacher-authored content, separate from the platform's own predicted-test content
- The strikethrough control in the card header is a **global eliminate-choices mode toggle** — turns per-choice strikethrough targets on/off for the whole question. Model as `strikethrough_enabled: boolean` per question in local state, with the per-choice struck set only meaningful while it's on.
- **Free-response (grid-in) questions** — instead of A–D choice rows, render a single bordered text input labeled "Answer…". Store `responses.free_response_text`; grading needs an acceptable-answer-set comparison (numeric equivalence, not string match — "1/2" and "0.5" must both grade correct) rather than a simple choice-ID match. **NEW (v2):** the same acceptable-answer-set structure is what `question_import_items.parsed_answer` stores for imported free-response questions — ingestion and live grading share one representation.

**Footer:** first button is labeled **Previous** (not "Back"), grayed out and disabled on question 1 of a module.

### 2.6 Question navigator + the full-page "Check Your Work" review

Two related but distinct surfaces:
1. **The in-test navigator modal** — opened from the footer pill mid-module, legend shows **Unanswered** (dashed empty square) and **For Review** (flag badge); the *current* question is shown with a bold/pinned border. Title is bold two-line: `Section X, Module Y:` / `<Section name>`.
2. **The full-page "Check Your Work" review** — reached automatically after the *last* question of a module, not a modal:
   - Centered heading "Check Your Work"
   - Explanatory copy: "On test day, you won't be able to move on to the next module until time expires. For these practice questions, you can click Next when you're ready to move on." — practice mode intentionally behaves more permissively than real test day, and the app tells the student so rather than silently diverging
   - The same navigator grid, rendered inline on a full page rather than in a modal
   - Same **Previous / Next** footer controls — Next here actually submits the module and advances

**Build note:** the review page must exist as a real page/route (e.g. `/attempt/:id/module/:n/review`), not just a client-side modal — it's the actual submission gate.

### 2.7 Between-module break screen
A visually distinct **dark-themed** screen (the only dark surface in the whole flow):
- Top-left: "Save and Leave" link (same save-and-exit semantics as the More menu, available even mid-break)
- Centered card: product logo, "Break Time:" label, large countdown (`MM:SS`)
- Right column: "Practice Test Break" heading, explanation that practice mode lets the student resume early while test day enforces the full countdown
- "On Test Day…" rules list (proctoring-rule content, purely informational in practice mode)
- **Resume Testing** button

**Build note:** the break timer should be server-authoritative the same way module timers are, with practice mode allowing early resume via a flag your backend honors (`allow_early_resume: true` for practice attempts, `false` for proctored/formal attempts).

### 2.8 End-of-test completion + feedback survey
- Confetti animation + mascot/logo, "Congratulations!" headline, "You've completed **[Test Name]**"
- **View Results** button (primary action)
- Inline post-test survey, always shown at completion:
  - NPS-style 0–10 scale ("Not likely" / "Extremely likely")
  - Difficulty self-report 0–10 scale ("Too easy" / "Too hard")
  - Optional free-text feedback

**Build note:** store as `attempts.feedback_nps`, `attempts.feedback_difficulty`, `attempts.feedback_text`; cross-reference the difficulty self-report against actual accuracy/time data to calibrate whether difficulty tags are accurate over time.

### 2.9 Results / report page

- Breadcrumb, title, subtitle "All modules", completion date, **Download report** button (tie to the `pdf` toolchain for a real export)
- Disclaimer callout (predicted-paper accuracy caveat)
- **Overview:** total score + R&W/Math subscores; bell-curve "you vs. platform average" chart gated behind Pro; Correct/Wrong/Accuracy/Unattempted stat cards, always visible
- **Per-module breakdown:** module names include the resolved adaptive-difficulty label (e.g. "Math – Module 2 (Easy)"); per-question grid gated behind Pro in the free tier
- **Skill breakdown:** "5 topics costing the most points" ranked list (first ~2 rows free, rest Pro-gated); accuracy-by-topic bars (2 topics free, rest Pro-gated); "time share by difficulty" donut chart, entirely Pro-gated
- Persistent bottom-pinned "Upgrade to Pro" banner while scrolling

**Build note — the paywall gating *pattern* is reusable:** free tier gets raw counts and the first 1–2 rows of any ranked/detailed breakdown; Pro unlocks comparative context, the long tail of ranked lists, and any chart requiring more than a single aggregate number. Implement as a reusable `<ProGate rowsVisible={2}>` component wrapping list/chart sections.

### 2.10 Teacher question ingestion & review — **NEW (v2)**

This is the concrete spec for the teacher-side document-upload feature. It replaces the "design from scratch" placeholder in the prior version's Part 3 for the ingestion half of teacher tooling (exam assembly, rosters, and "My Classes" are still open — see Part 3).

**Entry point:** an "Add questions" action on the teacher's question-bank / class page.

**Step 1 — Upload:**
- Teacher uploads a single file: `.pdf`, `.docx`, or `.md`. (Pasting raw text directly into a textarea is a reasonable cheap addition alongside file upload, not a blocker for v1.)
- File goes to S3-compatible storage; a `question_imports` row is created with `status: uploaded`.
- UI shows a compact upload zone with the three accepted formats labeled, and after upload, a one-line status ("parsed 12 questions, 9 with answers detected").

**Step 2 — Background parsing job (BullMQ + Redis):**
- `.docx` → `mammoth`; `.pdf` → `pdf-parse` (scanned/image-only PDFs won't extract text this way — flag as a known limitation, OCR is a later enhancement, not v1 scope); `.md` → parsed directly, since it's already structured text.
- The extracted raw text is sent through an LLM extraction step (Anthropic API) that:
  - splits the document into individual questions
  - identifies the stem and, for multiple-choice, the A–D choices
  - marks a question as free-response when no choice set is present
  - detects an explicit answer key if the document contains one (inline "Answer: C" markers, a bold/starred choice, or a separate answer-key section at the end) → `answer_source: extracted`
  - if no answer key is present anywhere in the document, the model attempts to solve the question itself → `answer_source: ai_generated`, with a `confidence_score`
  - if the model can't confidently produce an answer, the item is left with `answer_source: missing` and no `parsed_answer`
  - assigns a best-guess `suggested_topic` and `suggested_difficulty` for teacher confirmation
- Each extracted question becomes one `question_import_items` row. When the whole document is processed, `question_imports.status` flips to `parsed` (or `failed` with a reason, surfaced in the UI, if parsing errors out).

**Step 3 — Review screen (mandatory before anything is published):**
- One card per extracted item, showing the parsed stem and choices, plus a status badge:
  - **"Answer from doc"** (green) — `answer_source: extracted`
  - **"AI-suggested — needs review"** (amber) — `answer_source: ai_generated`, always shown regardless of confidence score; low-confidence items are visually flagged the same way, not silently trusted
  - **"No answer found"** (neutral) — `answer_source: missing`, with a dropdown for the teacher to pick the correct choice (or type the accepted answer(s) for free-response) before it can be approved
- Teacher actions per item: **Edit** (stem, choices, topic, difficulty, or the answer itself), **Approve**, **Reject**. A bulk **"Approve all and publish"** action is available, but it still requires the teacher to have looked at the screen and clicked it — nothing auto-publishes on parse completion.
- On approve, an import item is written into the standard `questions` (+ `choices`) tables — the same tables the exam assembly and test engine already consume — and `question_import_items.resulting_question_id` is set. Free-response answers are stored as an acceptable-answer-set, matching the grading structure already used in §2.5, not a single string.

**Build notes:**
- The "mandatory human review step" already flagged in the original Phase 3 scope is now concrete: no `ai_generated` or `missing` answer can reach `questions`/`choices` without an explicit approve action tied to a `reviewed_by` teacher and `reviewed_at` timestamp.
- Version the extraction prompt/pipeline (store a `prompt_version` or model identifier alongside the import job) so answers can be audited or re-run later if the extraction approach changes.
- Large documents should parse as a single background job but the review UI should paginate/batch rather than render every item on one unscrollable page.
- Because approved items land in the exact same schema the test engine and exam assembly already use, nothing downstream needs to know or care whether a question was hand-authored or ingested from a document.

---

## Part 3 — What's still missing

Question ingestion (upload → parse → AI-assisted extraction → human review → publish) now has a full spec as of v2 — see §2.10. Still undesigned, with no reference UI to reverse-engineer:
- Exam assembly UI (building a fixed-form test out of an approved question bank)
- Class rosters / "My Classes"
- Teacher-side moderation queue for student-reported questions (referenced in §2.5, not yet speced as a screen)

These still need to be designed from scratch using the schema and Phase 3 guidance in the original technical spec.

---

## Part 4 — Updated build-priority table

| Priority | Item | Source |
|---|---|---|
| 1 | Schema + auth + onboarding wizard | Part 1 + §2.1–2.2 |
| 2 | Manual question creation + fixed-form exam assembly (teacher side, no reference UI — design fresh) | Original spec Phase 3 |
| 3 | Test engine core: timer (server-authoritative), split pane, question card, per-choice strikethrough + global eliminate toggle, keyboard shortcuts, Report/Mark for Review | §2.5 |
| 4 | Accommodations modal + time-multiplier logic | §2.3 |
| 5 | Question navigator modal + full-page "Check Your Work" review/submission gate | §2.6 |
| 6 | Break screen (dark mode, server-authoritative countdown, early-resume flag) | §2.7 |
| 7 | Document parser (`.pdf`/`.docx`/`.md`) + AI question/answer extraction + mandatory human review UI | §2.10 **(NEW v2, fully speced)** |
| 8 | Completion flow + post-test survey | §2.8 |
| 9 | Results/report page incl. adaptive-difficulty module labeling, per-topic skill breakdown, `<ProGate>` pattern | §2.9 |
| 10 | Dashboard, predicted-test library, Google Sheets sync | Original spec Phase 5 |
| 11 | Paywall/monetization (free/Pro table + exam-date-scoped one-time payment) | Original UI spec |
| 12 | Exam assembly UI, class rosters, teacher moderation queue (still no reference UI) | Part 3 |
| 13 | QA, load testing, deployment | Original spec Phase 6 |

This ordering front-loads the parts with the most reference material (the test engine, the ingestion pipeline now fully speced in v2) and pushes the remaining zero-reference-material teacher tooling (exam assembly, rosters, moderation queue) later, where the schema and product decisions elsewhere in this document will matter most.
