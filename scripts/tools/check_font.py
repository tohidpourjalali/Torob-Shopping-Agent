import os
from pathlib import Path

# مسیر خروجی اسکرین‌شات‌ها (قابل override با SHOTS_DIR)
OUT = Path(os.environ.get("SHOTS_DIR", Path(__file__).resolve().parents[2] / "shots"))
OUT.mkdir(parents=True, exist_ok=True)

from playwright.sync_api import sync_playwright
import os

os.makedirs(OUT, exist_ok=True)
BASE = "http://127.0.0.1:3000"

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="fa-IR")
    page = ctx.new_page()

    requested = []
    page.on("request", lambda r: requested.append(r.url) if "kalameh" in r.url else None)

    page.goto(BASE, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    # ۱) آیا فونت واقعاً در document.fonts بارگذاری شده؟
    fonts = page.evaluate("""() => {
        const out = [];
        document.fonts.forEach(f => out.push({family: f.family, weight: f.weight, status: f.status}));
        return out;
    }""")
    print("=== document.fonts ===")
    for f in fonts:
        print(f"  {f['family']:24s} weight={f['weight']:4s} status={f['status']}")

    # ۲) آیا فونت روی body اعمال شده (نه fallback)؟
    applied = page.evaluate("""() => {
        const body = document.body;
        const h1 = document.querySelector('h1');
        return {
            bodyFamily: getComputedStyle(body).fontFamily,
            h1Family: h1 ? getComputedStyle(h1).fontFamily : null,
            h1Weight: h1 ? getComputedStyle(h1).fontWeight : null,
        };
    }""")
    print("\n=== computed style ===")
    for k, v in applied.items():
        print(f"  {k}: {v}")

    # ۳) تست واقعی رندر: عرض متن با کلمه در مقابل fallback متفاوت است
    render = page.evaluate("""() => {
        const mk = (family) => {
            const s = document.createElement('span');
            s.textContent = 'دستیار خرید حضوری ترب ۱۲۳۴۵';
            s.style.cssText = `position:absolute;visibility:hidden;white-space:nowrap;font-size:32px;font-family:${family}`;
            document.body.appendChild(s);
            const w = s.getBoundingClientRect().width;
            s.remove();
            return w;
        };
        return { kalameh: mk('Kalameh'), tahoma: mk('Tahoma'), serif: mk('serif') };
    }""")
    print("\n=== اندازه رندر (عرض px) ===")
    for k, v in render.items():
        print(f"  {k:10s} {v:.1f}")
    print(f"  → کلمه با fallback فرق دارد؟ {abs(render['kalameh'] - render['tahoma']) > 1}")

    print("\n=== فایل‌های فونت درخواست‌شده ===")
    for u in sorted(set(requested)):
        print(" ", u.split("/")[-1])

    page.screenshot(path=f"{OUT}/font-home.png", full_page=False)
    page.goto(BASE + "/stores?product=product_99316b03484cd879f989633b", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    page.screenshot(path=f"{OUT}/font-stores.png", full_page=False)
    page.goto(BASE + "/discover?q=" + "%D8%B4%D8%A7%D8%B1%DA%98%D8%B1%20%D8%A7%D9%BE%D9%84", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    page.screenshot(path=f"{OUT}/font-discover.png", full_page=False)

    b.close()
