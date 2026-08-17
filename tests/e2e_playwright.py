"""End-to-end Playwright walkthrough — teacher and student flows.

Runs the app in headless Chromium, takes screenshots at every major step,
and emits a self-contained HTML report at instance/e2e_report.html.

Assumptions:
  - Flask dev server running on http://127.0.0.1:5000
  - DB freshly seeded (teacher@example.com / student@example.com, both password=password)
"""
from __future__ import annotations
import base64
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, expect

BASE = "http://127.0.0.1:5000"
OUT_DIR = Path(__file__).resolve().parent.parent / "instance" / "e2e_screens"
REPORT_PATH = Path(__file__).resolve().parent.parent / "instance" / "e2e_report.html"

steps: list[dict] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def snap(page: Page, title: str, note: str = "") -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{len(steps):02d}_" + re.sub(r"\W+", "_", title.lower())[:60] + ".png"
    path = OUT_DIR / fname
    page.screenshot(path=str(path), full_page=True)
    steps.append({"title": title, "note": note, "file": fname, "url": page.url})
    print(f"  📸 {title}")


def login(page: Page, email: str, password: str) -> None:
    page.goto(f"{BASE}/auth/login")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)
    # WTForms SubmitField renders as <input type="submit">; scope to the form
    page.locator('form input[type="submit"]').click()
    page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# Teacher flow
# ---------------------------------------------------------------------------

def teacher_flow(page: Page) -> None:
    print("\n▶️  TEACHER FLOW")
    steps.append({"section": "TEACHER"})

    page.goto(BASE)
    snap(page, "Landing page", "Homepage with hero and CTAs")

    login(page, "teacher@example.com", "password")
    snap(page, "Teacher home", "After login — teacher landing with three cards")

    # Banks list
    page.click('a[href="/teacher/banks"]')
    page.wait_for_load_state("networkidle")
    snap(page, "Question banks list", "Existing seed bank visible")

    # Open the seed bank
    page.click('a:has-text("Demo Bank")')
    page.wait_for_load_state("networkidle")
    snap(page, "Bank detail", "Two seed questions rendered with correct-answer marker")

    # Add a new question
    page.click('a:has-text("Add question")')
    page.wait_for_load_state("networkidle")
    snap(page, "New question form", "MCQ form with A-D choice inputs and difficulty")

    page.fill('textarea[name="stem"]', "What is 7 × 8?")
    page.fill('input[name="topic"]', "Arithmetic")
    page.select_option('select[name="difficulty"]', "easy")
    page.fill('input[name="choice_a"]', "48")
    page.fill('input[name="choice_b"]', "54")
    page.fill('input[name="choice_c"]', "56")
    page.fill('input[name="choice_d"]', "64")
    page.select_option('select[name="correct"]', "C")
    snap(page, "Question form filled", "New MCQ ready to save")

    page.locator('input[type="submit"][value="Save question"]').click()
    page.wait_for_load_state("networkidle")
    snap(page, "Bank after new question", "Third question added to Demo Bank")

    # Exams
    page.click('a[href="/teacher/exams"]')
    page.wait_for_load_state("networkidle")
    snap(page, "Exams list", "Demo Practice Test from seed")

    page.click('a:has-text("Demo Practice Test")')
    page.wait_for_load_state("networkidle")
    snap(page, "Exam detail", "Single math module, calculator on, published")

    # ------ Ingestion (§2.10) ------
    print("  — Ingestion pipeline")
    page.click('a[href="/teacher/imports/"]')
    page.wait_for_load_state("networkidle")
    snap(page, "Ingestion — empty upload page", "Dropzone with .pdf/.docx/.md chips")

    # Prepare a markdown sample and upload it
    sample = Path("/tmp/e2e_sample.md")
    sample.write_text(
        "1. If 3x + 5 = 20, what is the value of x?\n"
        "A. 3\nB. 5\nC. 15\nD. 25\nAnswer: B\n\n"
        "2. A circle has radius 4. What is its area, in terms of π?\n"
        "A. 4π\nB. 8π\nC. 16π\nD. 32π\n\n"
        "3. What is 2^3 + 5?\nA. 11\nB. 13\nC. 15\nD. 17\n"
    )
    page.set_input_files('input[type="file"]', str(sample))
    page.select_option('select[name="bank_id"]', "1")
    page.click('button:has-text("Upload & parse")')
    page.wait_for_load_state("networkidle")
    snap(page, "Ingestion review screen", "Matches the reference image — three answer-source badges")

    # Approve item 1 (has answer key)
    page.locator('form[action*="/approve"]').first.locator('button:has-text("Approve")').click()
    page.wait_for_load_state("networkidle")
    snap(page, "After approving Q1", "Green Approved badge on item 1")

    # Classes
    page.click('a[href="/teacher/classes"]')
    page.wait_for_load_state("networkidle")
    snap(page, "Classes list", "No classes yet")

    page.fill('input[name="name"]', "Period 3 · SAT Prep")
    page.click('button:has-text("Create class")')
    page.wait_for_load_state("networkidle")
    snap(page, "Class detail", "Empty class with join code, add-student form")

    page.fill('input[name="email"]', "student@example.com")
    page.click('button:has-text("Add student")')
    page.wait_for_load_state("networkidle")
    snap(page, "Class with student", "student@example.com added to roster")

    # Moderation queue
    page.click('a[href="/teacher/moderation"]')
    page.wait_for_load_state("networkidle")
    snap(page, "Moderation queue", "Empty — no student reports yet")

    # Log out
    page.click('a[href="/auth/logout"]')
    page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# Student flow
# ---------------------------------------------------------------------------

def student_flow(page: Page) -> None:
    print("\n▶️  STUDENT FLOW")
    steps.append({"section": "STUDENT"})

    login(page, "student@example.com", "password")
    snap(page, "Student dashboard", "Recent activity, integrations, upgrade card")

    page.click('a[href="/student/tests"]')
    page.wait_for_load_state("networkidle")
    snap(page, "Tests library", "Published exams — start test buttons")

    # Start Demo Practice Test → accommodations → instructions
    page.locator('a:has-text("Start test")').first.click()
    page.wait_for_load_state("networkidle")
    snap(page, "Accommodations modal (§2.3)", "Standard / 1.5× / 2× radio cards")

    page.click('label:has-text("Time and a half")')
    page.click('button:has-text("Continue")')
    page.wait_for_load_state("networkidle")
    snap(page, "Instructions page (§2.4)", "4-rule info card")

    page.click('button:has-text("I\'m ready — start test")')
    page.wait_for_load_state("networkidle")
    snap(page, "Test engine — question 1", "Split pane, timer, tools row, MCQ choices")

    # Pick choice B (correct for Q1)
    page.click('.choice:has(.choice-label:text-is("B")) label')
    page.wait_for_timeout(600)  # let the debounced save fire
    snap(page, "Q1 — choice B selected", "Answer saved via HTMX; API records is_correct=True")

    # Toggle mark for review
    page.click('.mark-btn')
    page.wait_for_timeout(300)
    snap(page, "Q1 — marked for review", "🚩 badge on button")

    # Enable strikethrough mode
    page.click('.strike-toggle')
    page.wait_for_timeout(500)
    snap(page, "Q1 — strikethrough mode on", "Eliminate mode toggled; per-choice ✕ buttons visible")
    # Click strike targets — force=True in case Alpine's x-show hasn't finished
    try:
        page.locator('.strike-target').nth(0).click(force=True)
        page.wait_for_timeout(200)
        page.locator('.strike-target').nth(3).click(force=True)
        page.wait_for_timeout(300)
        snap(page, "Q1 — struck A & D", "Choices A and D visibly struck out")
    except Exception as e:
        print(f"  ⚠️  strike click failed: {e}")

    # Open the More menu
    page.click('.tool-more')
    page.wait_for_timeout(400)
    snap(page, "More menu", "Save/Fullscreen/Shortcuts/Dark mode/Bug report")

    try:
        page.locator('.more-menu a:has-text("Keyboard shortcuts")').click(force=True)
        page.wait_for_timeout(300)
        snap(page, "Keyboard shortcuts modal", "1–4 select choice, Enter advances")
        page.locator('.overlay:visible button:has-text("Close")').click(force=True)
        page.wait_for_timeout(200)
    except Exception as e:
        print(f"  ⚠️  shortcuts modal step skipped: {e}")

    # Advance to Q2
    page.click('button:has-text("Next")')
    page.wait_for_load_state("networkidle")
    snap(page, "Test engine — question 2", "Geometry question")

    # Pick the correct answer C
    page.click('.choice:has(.choice-label:text-is("C")) label')
    page.wait_for_timeout(600)
    snap(page, "Q2 — choice C selected", "Answered")

    # Open navigator
    try:
        page.click('.pill-btn')
        page.wait_for_timeout(400)
        snap(page, "Navigator modal (§2.6)", "Grid of question chips with legend")
        page.locator('.overlay:visible button:has-text("Close")').click(force=True)
        page.wait_for_timeout(200)
    except Exception as e:
        print(f"  ⚠️  navigator step skipped: {e}")

    # Go to Check Your Work
    page.click('button:has-text("Next")')
    page.wait_for_load_state("networkidle")
    snap(page, "Check Your Work page (§2.6)", "Real submission gate — Submit test button")

    # Submit
    page.on("dialog", lambda dialog: dialog.accept())
    page.click('button:has-text("Submit test")')
    page.wait_for_load_state("networkidle")
    snap(page, "Completion page (§2.8)", "Confetti + Congratulations + inline NPS/difficulty survey")

    # Fill and submit the survey
    page.click('.nps-scale label:has-text("9")')
    page.locator('.survey-block .nps-scale').nth(1).locator('label:has-text("6")').click()
    page.fill('textarea[name="text"]', "Slick UI. Felt like the real thing.")
    snap(page, "Survey filled in", "NPS=9, Difficulty=6, free-text response")

    page.click('button:has-text("Submit & view results")')
    page.wait_for_load_state("networkidle")
    snap(page, "Results page (§2.9)", "Overview, stat cards, per-module, skill breakdown; Pro sections gated")

    # Upgrade → dev grant → back to results
    page.locator('a:has-text("Upgrade to Pro")').first.click()
    page.wait_for_load_state("networkidle")
    snap(page, "Upgrade page", "Free vs Pro plans; dev-grant button in dev mode")

    page.click('button:has-text("Dev grant Pro")')
    page.wait_for_load_state("networkidle")
    snap(page, "After dev-grant", "Pro is active until test-date+60 days")

    # Back to dashboard to show pro card
    page.click('a[href="/student/dashboard"]')
    page.wait_for_load_state("networkidle")
    snap(page, "Dashboard as Pro", "Pro-until card shown")

    # And revisit results — Pro sections now visible
    page.goto(f"{BASE}/attempt/1/results")
    page.wait_for_load_state("networkidle")
    snap(page, "Results page as Pro", "Bell curve, per-question grid, time-share donut now visible")


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def build_report() -> None:
    def embed(fname: str) -> str:
        p = OUT_DIR / fname
        if not p.exists():
            return ""
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{data}"

    parts = [
        """<!DOCTYPE html><html><head><meta charset="utf-8"/>
<title>SatSimilator — E2E Report</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #fafafa; color: #0f172a; }
  header { padding: 32px 48px; background: white; border-bottom: 1px solid #e2e8f0; position: sticky; top: 0; z-index: 10; }
  h1 { margin: 0 0 4px; }
  h2.section { margin: 48px 48px 16px; padding: 12px 0; border-bottom: 2px solid #2563eb; color: #2563eb; }
  .step { display: grid; grid-template-columns: 320px 1fr; gap: 24px; padding: 24px 48px; border-bottom: 1px solid #e2e8f0; align-items: start; }
  .step .meta { position: sticky; top: 120px; }
  .step h3 { margin: 0 0 6px; font-size: 18px; }
  .step .note { color: #64748b; font-size: 14px; margin-bottom: 12px; }
  .step .url { color: #94a3b8; font-size: 12px; word-break: break-all; }
  .step img { width: 100%; max-width: 1200px; border: 1px solid #e2e8f0; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
  .num { color: #94a3b8; font-weight: 600; margin-right: 6px; }
  .summary { padding: 24px 48px; background: white; }
  .pill { display: inline-block; padding: 4px 10px; background: #e0f2fe; color: #0369a1; border-radius: 999px; font-size: 12px; margin-right: 8px; }
</style></head><body>
<header>
  <h1>SatSimilator — End-to-end Playwright walkthrough</h1>
"""
    ]
    n_steps = len([s for s in steps if "file" in s])
    parts.append(f'<div><span class="pill">{n_steps} screens captured</span>')
    parts.append(f'<span class="pill">Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}</span></div>')
    parts.append('</header>')

    idx = 0
    for s in steps:
        if "section" in s:
            parts.append(f'<h2 class="section">{s["section"]} flow</h2>')
            continue
        idx += 1
        img_src = embed(s["file"])
        parts.append(f"""
<div class="step">
  <div class="meta">
    <h3><span class="num">#{idx:02d}</span>{s['title']}</h3>
    <div class="note">{s['note']}</div>
    <div class="url">{s['url']}</div>
  </div>
  <div><img src="{img_src}" alt="{s['title']}"/></div>
</div>""")
    parts.append("</body></html>")
    REPORT_PATH.write_text("".join(parts))
    print(f"\n📄 Report written to {REPORT_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        page = ctx.new_page()
        page.on("console", lambda m: print(f"  [js:{m.type}] {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: print(f"  [js:error] {e}"))

        try:
            teacher_flow(page)
            student_flow(page)
        finally:
            build_report()
            browser.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
