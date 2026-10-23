"""ساخت «نقشهٔ خرید حضوری» — گام‌به‌گام، متصل به دادهٔ واقعی.

این ماژول همان چیزی است که کاربر می‌خواهد: ایجنت فقط لیست قیمت نشان نمی‌دهد،
بلکه مسیر رسیدن به خرید حضوری را می‌چیند.

قاعدهٔ حاکم: هر جمله یا از دیتاست می‌آید (با ذکر منبع) یا «راهنمای عمومی خرید»
است که صریحاً همین‌طور برچسب می‌خورد. هیچ ادعایی دربارهٔ موجودی، اصالت یا
قیمت روز ساخته نمی‌شود.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.text import fa_number, fmt_toman


def _step(title: str, detail: str, kind: str = "action", source: str = "guide") -> Dict[str, Any]:
    return {"title": title, "detail": detail, "kind": kind, "source": source}


# --------------------------------------------------------------------------- #
# چک‌لیست بازرسی کالا — راهنمای عمومی، نه ادعا دربارهٔ محصول
# --------------------------------------------------------------------------- #
_INSPECT_BY_HINT: List[tuple] = [
    (("هدفون", "هندزفری", "ایرپاد", "هدست"), [
        "هر دو گوشی را وصل کنید و بلوتوث را جفت کنید؛ قطع‌وصلی را در فاصلهٔ ۵ متری تست کنید.",
        "نویز کنسلینگ را در محیط پرصدا روشن کنید؛ تفاوت باید محسوس باشد.",
        "باتری و کابل را از نظر آثار استفاده (خط‌وخش، پین‌های خورده) ببینید.",
    ]),
    (("شارژر", "آداپتور", "پاوربانک", "کابل"), [
        "با گوشی خودتان تست شارژ بگیرید؛ سرعت شارژ را همان‌جا ببینید.",
        "ولتاژ/آمپر روی بدنه را با آنچه فروشنده می‌گوید مقایسه کنید.",
        "سریال و هولوگرام اصالت را با سایت گارانتی‌دهنده چک کنید.",
    ]),
    (("لپ تاپ", "لپ‌تاپ", "نوت بوک"), [
        "باطری، پورت‌ها، صفحه (پیکسل سوخته) و کیبورد را تک‌تک تست کنید.",
        "مدل دقیق CPU/رم/SSD را در System Information ببینید، نه از روی برچسب.",
        "فاکتور رسمی و کارت گارانتی با سریال هم‌خوان را بگیرید.",
    ]),
    (("گوشی", "موبایل", "تبلت"), [
        "IMEI روی جعبه، بدنه و داخل سیستم را مقایسه کنید.",
        "دوربین، بلندگو، میکروفن و سنسور اثر انگشت را تست کنید.",
        "وضعیت باتری (Battery Health) و سابقهٔ تعمیر را بپرسید.",
    ]),
    (("دوربین", "دزدگیر", "مدار بسته"), [
        "تصویر شبانه و دید در شب را روی مانیتور تست کنید.",
        "اتصال به اپلیکیشن و ضبط روی کارت حافظه را همان‌جا ببینید.",
        "آداپتور و کابل‌ها را داخل جعبه چک کنید.",
    ]),
    (("جارو", "چایساز", "اتو", "لوازم خانگی"), [
        "دستگاه را روشن کنید و صدای غیرعادی/لرزش را بررسی کنید.",
        "قطعات مصرفی و فیلتر را داخل جعبه ببینید.",
        "شرایط گارانتی و نمایندگی مجاز را بپرسید.",
    ]),
    (("کلید", "فیوز", "کنتاکتور", "رله", "سنسور", "اینورتر", "منبع تغذیه"), [
        "کد فنی و رنج جریان/ولتاژ را با نیاز پروژه تطبیق دهید.",
        "اصالت برند (برچسب و پلمب) را بررسی کنید؛ این اقلام تقلبی زیاد دارند.",
        "تعداد و نوع پایه‌ها را بشمارید.",
    ]),
]

_GENERIC_INSPECT = [
    "جعبه/پلمب را قبل از پرداخت باز کنید و محتویات را با لیست اقلام بسنجید.",
    "شماره سریال روی دستگاه را با جعبه و فاکتور مقایسه کنید.",
    "اگر کالا کارکرده/نمایشگاهی است، این را صریح روی فاکتور بنویسید.",
]


def inspect_checklist(title: Optional[str]) -> List[str]:
    text = title or ""
    for hints, items in _INSPECT_BY_HINT:
        if any(h in text for h in hints):
            return items
    return list(_GENERIC_INSPECT)


# --------------------------------------------------------------------------- #
# نقشهٔ خرید برای محصولِ موجود در دیتاست
# --------------------------------------------------------------------------- #
def plan_for_offer(
    *,
    product_title: Optional[str],
    offer: Optional[Dict[str, Any]] = None,
    alternatives: Optional[List[Dict[str, Any]]] = None,
    budget_max: Optional[int] = None,
) -> Dict[str, Any]:
    """نقشهٔ خرید حضوری برای یک آفر واقعی (بهترین فروشگاه انتخاب‌شده)."""
    offer = offer or {}
    shop = offer.get("shop") or {}
    price = offer.get("price") or {}
    hours = offer.get("hours") or {}
    payment = offer.get("payment") or {}
    stock = offer.get("stock") or {}

    distance = shop.get("distance_km")
    name = shop.get("name") or "این فروشگاه"
    price_value = price.get("value_toman")
    weekly = hours.get("week") or []

    steps: List[Dict[str, Any]] = []

    # ۱) قبل از حرکت
    pre: List[str] = []
    if hours.get("is_open_now") is True:
        pre.append("بر اساس ساعت کاری ثبت‌شده در دیتاست، همین حالا باز است.")
    elif hours.get("is_open_now") is False:
        pre.append("بر اساس ساعت کاری ثبت‌شده، همین حالا بسته است؛ زمان مناسب را از «ساعت کاری» ببینید.")
    else:
        pre.append("ساعت کاری این فروشگاه در دیتاست ثبت نشده؛ قبل از حرکت تماس بگیرید.")
    pre.append("قیمت و موجودی «تأییدنشده» است؛ یک تماس کوتاه قبل از حرکت، رفت‌وبرگشت هدررفته را حذف می‌کند.")
    if price_value:
        pre.append(f"قیمت ثبت‌شده در دیتاست: {fmt_toman(price_value)} — این قیمت snapshot است و ممکن است تغییر کرده باشد.")
    steps.append(_step("قبل از حرکت: تأیید تلفنی", " ".join(pre), "verify", "dataset"))

    # ۲) مسیر
    route: List[str] = []
    if distance is not None:
        route.append(f"فاصلهٔ خط مستقیم از موقعیت شما: {fa_number(distance, 1)} کیلومتر.")
    location_label = shop.get("location_label")
    if location_label:
        route.append(f"محله: {location_label}.")
    if shop.get("directions_link"):
        route.append("لینک مسیریابی (گوگل مپ) روی کارت فروشگاه آماده است.")
    steps.append(_step("مسیر و زمان‌بندی", " ".join(route) or "موقعیت فروشگاه در دیتاست ثبت نشده.", "route", "dataset"))

    # ۳) پرسش‌های تماس/حضور
    questions = [
        "قیمت امروز همین است که اعلام کردید؟",
        "موجود دارید؟ چند عدد؟",
        "گارانتی و شرایط بازگشت کالا چطور است؟",
        "امروز تا چه ساعتی باز هستید؟",
    ]
    if payment.get("has_data"):
        questions.append("پرداخت اعتباری/اقساطی که ثبت کرده‌اید، الان هم فعال است؟")
    steps.append(_step("چه بپرسید", " | ".join(questions), "ask", "guide"))

    # ۴) در فروشگاه
    steps.append(
        _step("در فروشگاه: بازرسی کالا", " ".join(inspect_checklist(product_title)), "inspect", "guide")
    )

    # ۵) پرداخت
    pay: List[str] = []
    if payment.get("has_data"):
        pay.append(f"وضعیت پرداخت ثبت‌شده: {payment.get('status_label')}.")
    else:
        pay.append("دیتاست برای این فروشگاه اطلاعات پرداخت ندارد؛ حتماً بپرسید.")
    if budget_max:
        pay.append(f"سقف بودجهٔ شما: {fmt_toman(budget_max)} — قبل از پرداخت، جمع نهایی (با مالیات/ارسال) را چک کنید.")
    pay.append("فاکتور بگیرید؛ نام کالا، سریال، قیمت و شرایط گارانتی روی آن باشد.")
    steps.append(_step("پرداخت و فاکتور", " ".join(pay), "pay", "dataset" if payment.get("has_data") else "guide"))

    # ۶) اگر موجود نبود
    alts = alternatives or []
    if alts:
        names = "، ".join(
            f"{a.get('shop', {}).get('name', '؟')}"
            + (f" ({fa_number(a.get('shop', {}).get('distance_km'), 1)} کیلومتر)" if a.get("shop", {}).get("distance_km") is not None else "")
            for a in alts[:3]
        )
        steps.append(_step("اگر موجود نبود", f"جایگزین‌های همین محصول با آفر واقعی: {names}.", "fallback", "dataset"))

    if weekly:
        steps.append(_step("ساعت کاری ثبت‌شده", _week_text(weekly), "hours", "dataset"))

    has_shop = bool(shop)
    return {
        "mode": "dataset_offer" if has_shop else "no_nearby_store",
        "headline": (
            f"خرید حضوری «{product_title or 'محصول'}» از {name}"
            if has_shop
            else f"راهنمای خرید حضوری «{product_title or 'محصول'}» — آفر نزدیکی پیدا نشد"
        ),
        "dataset_status": "found" if has_shop else "no_nearby_store",
        "steps": steps,
        "checklist": inspect_checklist(product_title),
        "questions_to_ask": questions,
        "shop": shop,
        "offer_id": offer.get("offer_id"),
        "contact": {
            "phone_display": shop.get("phone_display"),
            "phone_note": shop.get("phone_note"),
            "instagram": shop.get("instagram"),
            "website_url": shop.get("website_url"),
            "maps_link": shop.get("maps_link"),
            "directions_link": shop.get("directions_link"),
            # مختصات لازم است تا دکمهٔ مسیریابی در UI چند سرویس بسازد
            "lat": shop.get("lat"),
            "lon": shop.get("lon"),
        },
        "transparency": [
            "این نقشه از دادهٔ دیتاست + راهنمای عمومی خرید ساخته شده است."
            if has_shop
            else "این محصول در دیتاست هست، ولی در شعاع انتخابی آفری نداشت؛ راهنما عمومی است.",
            "موجودی انبار در دیتاست وجود ندارد؛ «موجود است» را هیچ‌جا ادعا نمی‌کنیم.",
            f"وضعیت موجودی: {stock.get('label') or 'نامشخص'}.",
        ],
        "notes": [
            "گام‌های «راهنمای عمومی خرید» از دیتاست نمی‌آیند و به‌عنوان توصیه علامت خورده‌اند.",
        ],
    }


def _week_text(week: List[Dict[str, Any]]) -> str:
    bits = []
    for day in week[:7]:
        label = day.get("day_label") or day.get("day") or ""
        if day.get("is_closed"):
            bits.append(f"{label}: تعطیل")
        elif day.get("open") and day.get("close"):
            bits.append(f"{label}: {day['open']}–{day['close']}")
        else:
            bits.append(f"{label}: نامشخص")
    return "، ".join(bits)


# --------------------------------------------------------------------------- #
# نقشهٔ خرید برای محصولی که در دیتاست نیست
# --------------------------------------------------------------------------- #
def plan_generic(
    *,
    intent: str,
    budget_max: Optional[int] = None,
    near_categories: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """برای هر خواستهٔ کاربر — حتی بیرون از دیتاست — نقشهٔ خرید حضوری می‌سازد.

    صادقانه می‌گوید دادهٔ فروشگاهی نداریم، اما کاربر را دست‌خالی رها نمی‌کند.
    """
    near = near_categories or []
    steps: List[Dict[str, Any]] = [
        _step(
            "۱) مشخصات لازم را قطعی کنید",
            "قبل از هر تماسی، سه چیز را بنویسید: کاربرد اصلی، اندازه/ظرفیت، و سقف بودجه. "
            "بدون این سه، هر فروشنده قیمت متفاوتی می‌دهد و مقایسه بی‌معنا می‌شود.",
            "define",
            "guide",
        ),
        _step(
            "۲) قیمت مرجع بسازید",
            "قیمت آنلاین همین مدل را در ترب/فروشگاه‌های آنلاین ببینید تا سقف منطقی داشته باشید؛ "
            "قیمت حضوری معمولاً چند درصد بالاتر است، ولی قابل چانه‌زنی است.",
            "benchmark",
            "guide",
        ),
        _step(
            "۳) سه فروشگاه را کوتاه‌لیست کنید",
            "برای این کالا دادهٔ فروشگاه حضوری در دیتاست نداریم. از محله‌های پرتراکم بازار "
            "(مثل پاساژهای علاالدین، جمهوری، ولیعصر) یا فروشگاه‌های تخصصی همان دسته شروع کنید "
            "و حتماً قبل از حرکت تلفنی موجودی را بپرسید.",
            "shortlist",
            "guide",
        ),
        _step(
            "۴) تلفنی استعلام بگیرید",
            "با این جمله شروع کنید: «سلام، [مدل دقیق] را دارید؟ قیمت امروز چند است؟ گارانتی‌اش چطور است؟» "
            "جواب‌ها را یادداشت کنید؛ اختلاف قیمت بیش از ۱۵٪ معمولاً یعنی یکی از دو طرف چیز دیگری می‌گوید.",
            "call",
            "guide",
        ),
        _step(
            "۵) حضوری بازرسی کنید",
            " ".join(inspect_checklist(intent)),
            "inspect",
            "guide",
        ),
        _step(
            "۶) پرداخت و فاکتور",
            "فاکتور بگیرید؛ سریال، مدل، قیمت و گارانتی روی آن باشد. "
            + (f"سقف بودجهٔ شما: {fmt_toman(budget_max)}." if budget_max else ""),
            "pay",
            "guide",
        ),
    ]

    if near:
        names = "، ".join(f"{c.get('name')} ({fa_number(c.get('products_count'))} محصول)" for c in near[:4])
        steps.insert(
            2,
            _step(
                "دستهٔ نزدیک در دیتاست",
                f"این محصول در دیتاست نیست، اما این دسته‌ها نزدیک‌اند و آفر واقعی دارند: {names}. "
                "اگر یکی را انتخاب کنید، فروشگاه‌های حضوری‌اش را با قیمت و فاصله می‌آورم.",
                "dataset",
                "dataset",
            ),
        )

    return {
        "mode": "general_guide",
        "headline": f"راهنمای خرید حضوری برای «{intent}»",
        "dataset_status": "not_in_dataset",
        "steps": steps,
        "checklist": inspect_checklist(intent),
        "questions_to_ask": [
            "قیمت امروز چند است؟",
            "موجود دارید؟",
            "گارانتی و شرایط بازگشت؟",
            "اصل بودن کالا را چطور تضمین می‌کنید؟",
        ],
        "shop": None,
        "offer_id": None,
        "contact": {},
        "transparency": [
            "این کالا در دیتاست ۲۲۵٬۹۰۳ محصولی ترب پیدا نشد؛ پس هیچ فروشگاه یا قیمتی برایش نشان نمی‌دهیم.",
            "گام‌های این نقشه «راهنمای عمومی خرید» هستند، نه دادهٔ دیتاست.",
        ],
        "notes": ["هیچ فروشگاه/قیمت ساختگی برای این کالا ساخته نشده است."],
    }
