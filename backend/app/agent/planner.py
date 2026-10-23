"""برنامه‌ریز قطعی ایجنت — مسیر بدون مدل زبانی.

این «ماشین حالت» نیست؛ یک حلقهٔ تصمیم است: در هر گام، برنامه‌ریز با نگاه به
واقعیت‌ها و **مشاهدات ابزارهای قبلی** تصمیم می‌گیرد گام بعدی چه باشد و می‌تواند
چند بار پشت سر هم ابزار صدا بزند (مثلاً: جست‌وجو → صفر نتیجه → بررسی پوشش →
ساخت نقشهٔ خرید). همان قرارداد `Action` را دارد که مسیر LLM، پس هر دو مسیر
یک حلقهٔ واحد را می‌رانند.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.text import content_tokens, normalize, parse_budget, tokenize

# واژه‌های نوع محصول که دیتاست واقعاً پوشش می‌دهد
PRODUCT_WORDS = [
    "شارژر", "کابل", "پاوربانک", "هدفون", "هندزفری", "ایرپاد", "هدست", "اسپیکر", "دوربین",
    "کلید", "فیوز", "کنتاکتور", "رله", "سنسور", "پمپ", "اینورتر", "ژنراتور", "ترانسمیتر",
    "جارو", "چایساز", "اتو", "ساعت", "گوشی", "لپ تاپ", "لپ‌تاپ", "تلویزیون", "مانیتور",
    "یخچال", "ماشین لباسشویی", "چراغ", "لامپ", "پروژکتور", "سوکت", "پریز", "سیم",
    "دزدگیر", "منبع تغذیه", "محافظ", "هارد", "مودم", "روتر", "کیبورد", "موس", "پرینتر",
    "کولر", "پنکه", "میکروفون", "تریپاد", "گیمبال", "تبلت", "کنسول", "هارد اکسترنال",
]

STARTER_EXAMPLES = [
    "هدفون بی‌سیم تا ۵ میلیون",
    "شارژر اپل ۲۰ وات",
    "اسپیکر بلوتوثی هارمن کاردن",
    "جارو رباتیک",
]

# مترادف‌ها: خواستهٔ کاربر → عبارت مؤثرتر در دیتاست
SYNONYMS = {
    "هندزفری": ["هدفون", "هندزفری"],
    "ایرپاد": ["ایرپاد", "هدفون بی‌سیم"],
    "آیفون": ["اپل", "گوشی"],
    "موبایل": ["گوشی"],
    "کامپیوتر": ["لپ‌تاپ", "کیس"],
    "یه چیز خوب برای آشپزخانه": ["چایساز", "آسیاب", "غذاساز"],
    "نور": ["لامپ", "چراغ"],
    "اینترنت": ["مودم", "روتر"],
    "شارژ": ["شارژر", "پاوربانک"],
}

MAX_STEPS = 8


@dataclass
class Action:
    kind: str                       # tool | ask | answer
    tool: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    question: Optional[str] = None
    quick_replies: List[Dict[str, str]] = field(default_factory=list)
    message: str = ""
    stage: str = ""


# --------------------------------------------------------------------------- #
# استخراج واقعیت‌ها از پیام کاربر
# --------------------------------------------------------------------------- #
def extract_facts(message: str) -> Dict[str, Any]:
    facts: Dict[str, Any] = {}
    text = message.strip()
    if not text:
        return facts

    norm = normalize(text)
    hits = [w for w in PRODUCT_WORDS if normalize(w) in norm]
    if hits:
        facts["product_type"] = max(hits, key=len)
        # عبارت جست‌وجو = همهٔ توکن‌های معنادار پیام، نه فقط نوع محصول؛
        # وگرنه «شارژر اپل» به «شارژر» تبدیل می‌شود و برند گم می‌شود.
        words = content_tokens(text)
        facts["query"] = " ".join(words) if words else max(hits, key=len)

    bmin, bmax = parse_budget(text)
    if bmax:
        facts["budget_max"] = bmax
    if bmin:
        facts["budget_min"] = bmin

    tokens = tokenize(text)
    if tokens:
        facts["tokens"] = tokens[:8]
    return facts


def expand_query(query: Optional[str]) -> Optional[str]:
    """گسترش عبارت فقط وقتی کل درخواست یک واژهٔ مبهم است.

    چرا نه بیشتر: اگر «شارژر اپل» را با «شارژر پاوربانک» جای‌گزین کنیم، برند
    «اپل» گم می‌شود و نتیجه از ۴۰۰ محصول مرتبط به ۷۶۳ محصول بی‌ربط می‌رسد.
    گسترش فقط برای عبارت‌هایی مثل «نور» یا «اینترنت» درست است که کاربر
    چیزی جز یک مفهوم نگفته است.
    """
    if not query:
        return query
    norm = normalize(query).strip()
    for key, alts in SYNONYMS.items():
        if norm == normalize(key):
            return " ".join(alts)
    return query


# --------------------------------------------------------------------------- #
# تصمیم‌گیری
# --------------------------------------------------------------------------- #
def next_action(state: Dict[str, Any], ctx) -> Action:
    facts = state.get("facts") or {}
    artifacts = state.get("artifacts") or {}
    selection = state.get("selection") or {}
    tried = set(state.get("tried") or [])

    query = facts.get("query") or facts.get("product_type")

    # ۰) هنوز نمی‌دانیم چه می‌خواهد
    if not query and not selection.get("product_id"):
        return Action(
            kind="ask",
            stage="need",
            message="سلام! من دستیار خرید حضوری هستم. می‌گویم کدام فروشگاه تهران این کالا را دارد، "
                    "قیمتش چنده، و چطور حضوری با خیال راحت بخرید.",
            question="چه چیزی می‌خواهید بخرید؟",
            quick_replies=[{"label": e, "value": e} for e in STARTER_EXAMPLES],
        )

    # ۱) جست‌وجوی محصول
    if "search_products" not in tried:
        return Action(
            kind="tool",
            tool="search_products",
            arguments={
                "query": expand_query(query),
                "max_price": facts.get("budget_max"),
                "limit": 8,
            },
        )

    products = artifacts.get("products") or []

    # ۲) نتیجه نداشت → بررسی پوشش دیتاست (و بعد نقشهٔ عمومی)
    if not products:
        if "dataset_coverage" not in tried:
            return Action(kind="tool", tool="dataset_coverage", arguments={"query": query or ""})
        if "build_purchase_guide" not in tried:
            return Action(
                kind="tool",
                tool="build_purchase_guide",
                arguments={"intent": query or "خرید حضوری", "budget_max": facts.get("budget_max")},
            )
        return Action(kind="answer", stage="guide", message="")

    # ۳) محصول انتخاب نشده → بپرس کدام
    if not selection.get("product_id"):
        replies = [
            {"label": p["persian_title"][:52], "value": p["product_id"]} for p in products[:5]
        ]
        if facts.get("budget_max") is None and len(products) > 2:
            return Action(
                kind="ask",
                stage="product",
                message=f"{len(products)} محصول مطابق پیدا شد. برای دقیق‌تر شدن، بودجه را بگویید.",
                question="بودجه‌تان چقدر است؟",
                quick_replies=[
                    {"label": "تا ۵۰۰ هزار", "value": "تا ۵۰۰ هزار تومان"},
                    {"label": "تا ۲ میلیون", "value": "تا ۲ میلیون تومان"},
                    {"label": "تا ۱۰ میلیون", "value": "تا ۱۰ میلیون تومان"},
                    {"label": "مهم نیست", "value": "بودجه محدود نیست"},
                ],
            )
        return Action(
            kind="ask",
            stage="product",
            message="کدام محصول را می‌خواهید؟ بعد از انتخاب، فروشگاه‌های حضوری‌اش را با "
                    "قیمت و فاصله می‌آورم و قدم‌به‌قدم راهنمای خرید می‌دهم.",
            question="کدام محصول؟",
            quick_replies=replies,
        )

    # ۴) فروشگاه‌ها — شعاع کوچک، بعد یک بار شعاع بزرگ‌تر
    attempts = (state.get("attempts") or {}).get("find_stores", 0)
    if attempts == 0:
        return Action(
            kind="tool",
            tool="find_stores",
            arguments={"product_id": selection["product_id"], "radius_km": 8, "limit": 8},
        )

    stores = artifacts.get("stores") or []
    if not stores and attempts == 1:
        return Action(
            kind="tool",
            tool="find_stores",
            arguments={"product_id": selection["product_id"], "radius_km": 25, "limit": 8},
        )

    # ۵) نقشهٔ خرید حضوری (برای هر حالتی — حتی اگر فروشگاهی نبود، راهنمای عمومی)
    if "build_purchase_guide" not in tried:
        return Action(
            kind="tool",
            tool="build_purchase_guide",
            arguments={"product_id": selection["product_id"], "offer_id": selection.get("offer_id")},
        )

    return Action(kind="answer", stage="guide", message="")


def pick_product_from_message(message: str, products: List[Dict[str, Any]]) -> Optional[str]:
    """انتخاب محصول از پیام: شناسهٔ مستقیم، شمارهٔ ترتیبی، یا تطبیق عنوان."""
    text = (message or "").strip()
    if not text or not products:
        return None
    ids = {p["product_id"] for p in products}
    if text in ids:
        return text

    norm = normalize(text)
    for i, p in enumerate(products, start=1):
        title = normalize(p["persian_title"])
        if norm and (norm == str(i) or title.startswith(norm) or norm in title):
            return p["product_id"]
    return None
