"""Kiểm giao diện bằng Chromium thật.

    ./pw-env/bin/python scripts/check-ui.py ./shots

Mở cả 5 màn ở 3 kích thước, kiểm tràn ngang + lỗi console + nội dung mong đợi,
rồi chụp ảnh vào thư mục truyền vào.

QUAN TRỌNG: script này chỉ bắt được lỗi đo được. Ba lỗi bố cục của dự án
(danh sách toàn ca 100 điểm, nhãn menu wrap 2 dòng, bảng feature cao gấp 4 lần
card bên cạnh) đều PASS hết assertion — chỉ lộ ra khi mở ảnh chụp lên xem.
Chạy script rồi phải nhìn ảnh.

Cài đặt (xem README mục 7):
    uv venv --python 3.11 pw-env
    uv pip install --python pw-env/bin/python playwright
    ./pw-env/bin/playwright install chromium
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("UI_BASE_URL", "http://localhost:5173")
SHOTS = sys.argv[1] if len(sys.argv) > 1 else "./shots"
PAGES = [
    ("transactions", "/transactions", "Danh sách giao dịch"),
    ("review", "/review", "Hàng chờ rà soát"),
    ("score", "/score", "Chấm điểm thử"),
    ("import", "/import", "Nạp dữ liệu"),
]
VIEWPORTS = [("desktop", 1440, 900), ("laptop", 1100, 800), ("mobile", 390, 844)]

problems = []

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for vp_name, w, h in VIEWPORTS:
        ctx = browser.new_page(viewport={"width": w, "height": h})
        errors = []
        ctx.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        ctx.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        for name, path, expect in PAGES:
            errors.clear()
            ctx.goto(f"{BASE}{path}", wait_until="networkidle")
            ctx.wait_for_timeout(700)

            if expect not in ctx.content():
                problems.append(f"{vp_name}/{name}: không thấy '{expect}'")

            # Tràn ngang: body rộng hơn viewport là lỗi layout
            overflow = ctx.evaluate(
                "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            if overflow > 1:
                problems.append(f"{vp_name}/{name}: TRÀN NGANG {overflow}px")

            for e in errors:
                problems.append(f"{vp_name}/{name}: console {e[:120]}")

            if vp_name == "desktop":
                ctx.screenshot(path=f"{SHOTS}/{name}.png", full_page=True)

        # Mở chi tiết 1 giao dịch thật
        if vp_name == "desktop":
            ctx.goto(f"{BASE}/transactions", wait_until="networkidle")
            ctx.wait_for_timeout(500)
            link = ctx.locator("table tbody tr").first.locator("a", has_text="Chi tiết")
            link.click()
            ctx.wait_for_timeout(1200)
            if "Điểm rủi ro" not in ctx.content():
                problems.append("desktop/detail: không mở được chi tiết")
            ctx.screenshot(path=f"{SHOTS}/detail.png", full_page=True)

            # Mở trợ lý
            ctx.locator(".chat-fab").click()
            ctx.wait_for_timeout(400)
            if "Trợ lý chấm điểm" not in ctx.content():
                problems.append("desktop/chat: không mở được panel")
            ctx.screenshot(path=f"{SHOTS}/chat.png")
        ctx.close()
    browser.close()

print(f"{len(problems)} vấn đề")
for p in problems:
    print("  -", p)

sys.exit(1 if problems else 0)
