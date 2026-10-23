"""تست دودی سرتاسری روی داده واقعی: کشف نیاز → محصول → فروشگاه → مقایسه → تأیید.

اجرا:
    DATABASE_URL=sqlite:////path/torob.db python scripts/smoke_test.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
FAILS: list[str] = []


def check(label: str, cond: bool, extra: str = "") -> None:
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {label} {extra}")
    if not cond:
        FAILS.append(label)


def timed(label: str, fn):
    t0 = time.time()
    out = fn()
    print(f"      ({label}: {1000 * (time.time() - t0):.0f} ms)")
    return out


print("=" * 78)
print("۱) سلامت و متادیتا")
print("=" * 78)
h = client.get("/api/health").json()
check("health ok", h["status"] == "ok", str(h["counts"]))
check("دیتاست وارد شده", h["dataset_loaded"])

meta = client.get("/api/dataset/meta").json()
check("۲۲۵٬۹۰۳ محصول", meta["products_count"] == 225_903, str(meta["products_count"]))
check("۶٬۴۷۶ فروشگاه", meta["shops_count"] == 6_476, str(meta["shops_count"]))
check("۳۳۱٬۵۰۶ آفر", meta["offers_count"] == 331_506, str(meta["offers_count"]))
check("هشدار «قیمت زنده نیست» موجود است", "snapshot" in meta["price_freshness_note"])
check("هشدار «موجودی نامشخص» موجود است", "موجودی" in meta["stock_note"])

locs = timed("locations", lambda: client.get("/api/dataset/locations").json())
check("محله‌های واقعی دیتاست", len(locs) > 0, f"مثال: {locs[0]['label']} ({locs[0]['shops_count']} فروشگاه)")

print()
print("=" * 78)
print("۲) مرحله کشف نیاز (گام ۱)")
print("=" * 78)
r = client.post("/api/discover", json={"message": "سلام"}).json()
check("نوع محصول پرسیده می‌شود", r["step"] == "clarifying" and "product_type" in r["missing_info"])
check("گزینه‌های شروع بر پایه دیتاست", len(r["quick_replies"]) > 0)
session_id = r["session_id"]

r2 = client.post("/api/discover", json={"message": "شارژر اپل می‌خوام", "session_id": session_id}).json()
check("نوع محصول تشخیص داده شد", r2["collected"].get("product_type") == "شارژر", str(r2["collected"].get("product_type")))
check("برند از کاتالوگ تشخیص داده شد", r2["collected"].get("brand") == "اپل", str(r2["collected"].get("brand")))
check("محصولات پیشنهاد شدند", len(r2["products"]) > 0, f"{len(r2['products'])} مورد")
check("ردیف استدلال عامل (۴ مرحله)", len(r2["agent_trace"]) == 4)

print()
print("=" * 78)
print("۳) انتخاب محصول دارای بیشترین پوشش فروشگاه (گام ۲)")
print("=" * 78)
best = max(r2["products"], key=lambda p: p["shops_count"])
print(f"      محصول: {best['persian_title']}")
print(f"      فروشگاه‌ها: {best['shops_count']} | آفرها: {best['offers_count']}")
print(f"      قیمت: {best['min_price_toman']:,} تا {best['max_price_toman']:,} تومان")
check("تعداد فروشگاه > 0", best["shops_count"] > 0)
check("قیمت «تأییدنشده» برچسب خورده", best["price"]["is_verified"] is False and "تأییدنشده" in best["price"]["label"])

detail = client.get(f"/api/products/{best['product_id']}").json()
check("جزئیات محصول خوانده شد", detail["product_id"] == best["product_id"])
if detail["specs"]:
    print(f"      مشخصات ثبت‌شده: {len(detail['specs'])} مورد")
else:
    check("محصول بدون مشخصات صادقانه علامت خورده",
          detail["missing_specs_note"] is not None, detail["missing_specs_note"] or "")

print()
print("=" * 78)
print("۴) یافتن فروشگاه‌های حضوری (گام ۳)")
print("=" * 78)


def do_stores():
    return client.post("/api/stores/search", json={
        "product_id": best["product_id"],
        "lat": 35.6945, "lon": 51.4120,
        "radius_km": 5, "sort_by": "smart", "limit": 10,
    })


s = timed("stores/search", do_stores)
check("کد ۲۰۰", s.status_code == 200, s.text[:200] if s.status_code != 200 else "")
s = s.json()
check("فروشگاه پیدا شد", s["returned"] > 0, f"{s['returned']} از {s['total_candidates']} کاندید")
check("شعاع اعمال شد", "شعاع" in " ".join(s["filters_applied"]))
check("هشدار موجودی نامشخص", any("موجودی" in n for n in s["data_notes"]))
check("مختصات مرکز مشخص است", s["user_location"].get("source") is not None)

if s["stores"]:
    top = s["stores"][0]
    print(f"      برترین فروشگاه: {top['shop']['name']}")
    print(f"      فاصله: {top['shop']['distance_km']} km | امتیاز: {top['score']}")
    print(f"      دلایل رتبه: {top['rank_reason']}")
    print(f"      هشدارها: {top['cautions']}")
    check("امتیاز دارای breakdown شفاف", len(top["score_breakdown"]) == 5, str(top["score_breakdown"]))
    check("موجودی همیشه نامشخص", top["stock"]["status"] == "unknown")
    check("قیمت تأییدنشده", top["price"]["is_verified"] is False)
    check("دفترچه فاصله معتبر", 0 <= top["shop"]["distance_km"] <= 5.01)

    # مرتب‌سازی بر اساس قیمت
    priced = [x for x in s["stores"] if x["price"]["value_toman"]]
    if len(priced) > 1:
        vals = [x["price"]["value_toman"] for x in priced]
        check("قیمت‌ها منطقی هستند", min(vals) > 0)

    print()
    print("=" * 78)
    print("۵) مقایسه فروشگاه‌ها")
    print("=" * 78)
    ids = [x["offer_id"] for x in s["stores"][:4]]
    cmp = client.post("/api/stores/compare", json={"offer_ids": ids}).json()
    check("مقایسه برگشت", len(cmp["rows"]) > 0, f"{len(cmp['rows'])} ردیف")
    check("خلاصه مقایسه ارائه شد", len(cmp["summary"]) > 0, cmp["summary"][0] if cmp["summary"] else "")
    check("هشدار تأییدنشده بودن قیمت", any("تأییدنشده" in n for n in cmp["notes"]))

    print()
    print("=" * 78)
    print("۶) درخواست تأیید قیمت/موجودی (گام ۴)")
    print("=" * 78)
    v = client.post("/api/verify", json={"offer_id": top["offer_id"], "channel": "demo"})
    check("کد ۲۰۰", v.status_code == 200, v.text[:200] if v.status_code != 200 else "")
    v = v.json()
    check("صریحاً «شبیه‌سازی» برچسب خورده", v["is_simulated"] is True)
    check("برچسب نمایشی در پاسخ", "نمایشی" in v["label"], v["label"])
    check("اعلام شده هیچ تماس واقعی انجام نشد", "هیچ" in v["note"] or "ارسال نشده" in v["note"])
    check("اسکریپت گفت‌وگو تولید شد", len(v["script"]) >= 3, f"{len(v['script'])} خط")
    check("موجودی تأییدنشده باقی ماند", v["stock_status"] == "unknown")
    print("      اسکریپت پیشنهادی:")
    for line in v["script"]:
        print(f"        - {line}")

    hist = client.get(f"/api/verify/{top['offer_id']}").json()
    check("تاریخچه تأیید ثبت شد", len(hist) >= 1)
    check("رکورد با پرچم simulated ذخیره شد", hist[0]["is_simulated"] is True)

print()
print("=" * 78)
print("۷) بررسی سناریوی جایگزین (فیلتر سخت‌گیرانه)")
print("=" * 78)
alt = client.post("/api/stores/search", json={
    "product_id": best["product_id"], "lat": 35.6945, "lon": 51.4120,
    "radius_km": 1, "require_installment": True, "limit": 5,
}).json()
print(f"      شعاع ۱ کیلومتر + الزام اقساط: {alt['returned']} نتیجه از {alt['total_candidates']} کاندید")
if alt["total_candidates"] == 0:
    check("پیشنهاد جایگزین ارائه شد", alt["alternatives_note"] is not None,
          (alt["alternatives_note"] or "")[:80])
    check("فیلترها شفاف اعلام شدند", len(alt["filters_applied"]) >= 2, str(alt["filters_applied"]))

print()
print("=" * 78)
print(f"نتیجه: {'همه تست‌ها موفق' if not FAILS else str(len(FAILS)) + ' تست ناموفق'}")
if FAILS:
    for f in FAILS:
        print(f"  - {f}")
print("=" * 78)
sys.exit(1 if FAILS else 0)
