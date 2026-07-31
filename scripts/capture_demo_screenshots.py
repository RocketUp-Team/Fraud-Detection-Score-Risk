"""Capture the demo UI with live backend data."""
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE = "http://127.0.0.1:5173"
OUT = Path("screenshots/demo")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True,
        executable_path="/usr/bin/google-chrome",
        args=["--no-sandbox"],
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})

    page.goto(f"{BASE}/score", wait_until="networkidle")
    page.get_by_role("button", name="Chấm điểm", exact=True).click()
    page.get_by_text("Xác suất gian lận").wait_for()
    page.screenshot(path=str(OUT / "score-result.png"), full_page=True)

    page.goto(f"{BASE}/transactions", wait_until="networkidle")
    page.locator(".chat-fab").click()
    page.get_by_text("Trợ lý chấm điểm").wait_for()
    page.screenshot(path=str(OUT / "chat.png"), full_page=True)

    browser.close()
