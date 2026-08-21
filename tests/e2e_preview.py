"""Quick visual verification of the redesign — captures key screens in both
themes and emits instance/preview.html for a side-by-side review.
"""
from __future__ import annotations
import base64
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, BrowserContext

BASE = "http://127.0.0.1:5000"
OUT = Path(__file__).resolve().parent.parent / "instance" / "preview_screens"
REPORT = Path(__file__).resolve().parent.parent / "instance" / "preview.html"

pairs: list[dict] = []


def snap(page: Page, key: str, theme: str) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    fname = f"{key}__{theme}.png"
    page.screenshot(path=str(OUT / fname), full_page=True)
    return fname


def record(key: str, title: str, note: str, theme: str, fname: str) -> None:
    entry = next((p for p in pairs if p["key"] == key), None)
    if not entry:
        entry = {"key": key, "title": title, "note": note}
        pairs.append(entry)
    entry[theme] = fname


def set_theme_via_url(page: Page, url: str, theme: str) -> None:
    """Set localStorage.theme then navigate — theme applies before paint."""
    page.goto(url)
    page.evaluate(f"localStorage.setItem('theme', '{theme}')")
    page.reload()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)


def login(ctx: BrowserContext, email: str) -> None:
    page = ctx.new_page()
    page.goto(f"{BASE}/auth/login")
    page.wait_for_selector('input[name="email"]', timeout=10_000)
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', 'password')
    page.locator('form input[type="submit"]').click()
    page.wait_for_load_state("networkidle")
    page.close()


def capture(ctx: BrowserContext, url: str, key: str, title: str, note: str) -> None:
    for theme in ("light", "dark"):
        page = ctx.new_page()
        set_theme_via_url(page, url, theme)
        fname = snap(page, key, theme)
        page.close()
        record(key, title, note, theme, fname)


def build_report() -> None:
    parts = ["""<!DOCTYPE html><html><head><meta charset='utf-8'/>
<title>SatSimilator — Redesign preview</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #0e0d0c; color: #f6f3ee; }
  header { padding: 24px 32px; background: #1a1917; border-bottom: 1px solid #2a2724; position: sticky; top: 0; z-index: 10; }
  h1 { margin: 0; font-size: 20px; }
  header p { margin: 6px 0 0; color: #a8a29a; font-size: 13px; }
  .step { padding: 24px 32px; border-bottom: 1px solid #2a2724; }
  .step h3 { margin: 0 0 4px; font-size: 18px; }
  .note { color: #a8a29a; font-size: 14px; margin-bottom: 16px; }
  .compare { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  figure { margin: 0; }
  figcaption { padding: 6px 0; color: #a8a29a; font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }
  img { width: 100%; border: 1px solid #2a2724; border-radius: 6px; }
</style></head><body>
<header><h1>SatSimilator — Redesign preview</h1><p>Light and dark theme side-by-side for the key screens</p></header>
"""]
    for p in pairs:
        light_img = ""
        dark_img = ""
        if "light" in p:
            light_img = "data:image/png;base64," + base64.b64encode((OUT/p["light"]).read_bytes()).decode()
        if "dark" in p:
            dark_img = "data:image/png;base64," + base64.b64encode((OUT/p["dark"]).read_bytes()).decode()
        parts.append(f"""
<div class="step">
  <h3>{p['title']}</h3>
  <div class="note">{p['note']}</div>
  <div class="compare">
    <figure><figcaption>light</figcaption><img src="{light_img}"/></figure>
    <figure><figcaption>dark</figcaption><img src="{dark_img}"/></figure>
  </div>
</div>""")
    parts.append("</body></html>")
    REPORT.write_text("".join(parts))


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Public pages — no auth
        pub = browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        capture(pub, f"{BASE}/", "landing", "Landing", "Homepage hero + feature cards")
        capture(pub, f"{BASE}/auth/login", "login", "Login page", "Auth card")
        capture(pub, f"{BASE}/auth/signup", "signup", "Signup page", "Auth card")
        pub.close()

        # Teacher pages
        tctx = browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        login(tctx, "teacher@example.com")
        capture(tctx, f"{BASE}/teacher/", "teacher_home", "Teacher home", "Three cards for banks / exams / ingestion")
        capture(tctx, f"{BASE}/teacher/banks/1", "bank_detail", "Bank detail", "Seed bank with two questions")
        capture(tctx, f"{BASE}/teacher/imports/", "ingest_index", "Ingestion index", "Upload dropzone + file-type chips")
        tctx.close()

        # Student pages
        sctx = browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        login(sctx, "student@example.com")
        capture(sctx, f"{BASE}/student/dashboard", "dashboard", "Student dashboard", "Recent activity + integrations + upgrade card")
        capture(sctx, f"{BASE}/student/tests", "tests_lib", "Test library", "Published tests")
        capture(sctx, f"{BASE}/student/tests/1/accommodations", "accommodations", "Accommodations", "Standard / 1.5x / 2x radio cards")
        capture(sctx, f"{BASE}/attempt/1/results", "results_review", "Results — with Review Your Answers", "New per-question review section at the bottom (edit #5)")
        sctx.close()

        browser.close()
        build_report()
        print(f"preview written to {REPORT} ({REPORT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
