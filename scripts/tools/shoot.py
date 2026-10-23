"""اسکرین‌شات‌های مستندات — سناریوی کامل در هر دو تم.

اجرا:
    SHOTS_DIR=/tmp/shots python3 scripts/tools/shoot.py

پیش‌نیاز: هر دو سرور بالا (127.0.0.1:3000 و 127.0.0.1:8000) و
`pip install playwright && playwright install chromium`.
"""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(os.environ.get("SHOTS_DIR", "/tmp/shots"))
OUT.mkdir(parents=True, exist_ok=True)

BASE = "http://127.0.0.1:3000"
GEO = {"latitude": 35.6945, "longitude": 51.4120}
QUERY = "%D8%B4%D8%A7%D8%B1%DA%98%D8%B1%20%D8%A7%D9%BE%D9%84"


def scenario(browser, theme: str) -> None:
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=2,
        locale="fa-IR",
        color_scheme=theme,
        permissions=["geolocation"],
        geolocation=GEO,
    )
    page = ctx.new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    # ۱) خانه
    page.goto(BASE, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    page.screenshot(path=OUT / f"{theme}-01-home.png", full_page=True)

    # ۲) ایجنت + پرسش اجازهٔ موقعیت
    page.goto(f"{BASE}/discover?q={QUERY}", wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    page.get_by_role("button", name="فعال‌کردن موقعیت من").click()
    page.wait_for_timeout(500)
    page.screenshot(path=OUT / f"{theme}-02-location-permission.png")

    # ۳) موقعیت ثبت شد + پیشنهاد محصول
    page.get_by_role("button", name="اجازه می‌دهم").click()
    page.wait_for_timeout(3500)
    page.screenshot(path=OUT / f"{theme}-03-agent-products.png")

    # ۴) نقشهٔ خرید + فروشگاه‌ها
    if page.get_by_role("button", name="تا ۱۰ میلیون").count():
        page.get_by_role("button", name="تا ۱۰ میلیون").click()
        page.wait_for_timeout(3000)
    if page.get_by_role("button", name="فروشگاه‌ها").count():
        page.get_by_role("button", name="فروشگاه‌ها").first.click()
        page.wait_for_timeout(8000)
    page.screenshot(path=OUT / f"{theme}-04-purchase-plan.png", full_page=True)

    # ۵) مسیریابی چندسرویسی
    if page.get_by_role("button", name="مسیریابی").count():
        page.get_by_role("button", name="مسیریابی").first.click()
        page.wait_for_timeout(700)
        page.screenshot(path=OUT / f"{theme}-05-directions.png")
        page.get_by_role("button", name="بستن").first.click()
        page.wait_for_timeout(400)

    # ۶) استعلام قیمت و موجودی
    if page.get_by_role("button", name="استعلام قیمت و موجودی").count():
        page.get_by_role("button", name="استعلام قیمت و موجودی").first.click()
        page.wait_for_timeout(3000)
        page.screenshot(path=OUT / f"{theme}-06-verification.png")

    # ۷) پیگیری استعلام‌ها
    page.goto(f"{BASE}/tracking", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    page.screenshot(path=OUT / f"{theme}-07-tracking.png", full_page=True)

    print(f"[{theme}] ✓ — console errors:", errors[:3] or "none")
    ctx.close()


with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ("light", "dark"):
        scenario(browser, theme)
    browser.close()
