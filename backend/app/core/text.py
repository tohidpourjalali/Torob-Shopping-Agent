"""ابزارهای متن فارسی: نرمال‌سازی، توکن‌سازی، تشخیص بودجه و واحد پول."""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Tuple

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_DIGIT_MAP = {ord(p): str(i) for i, p in enumerate(PERSIAN_DIGITS)}
_DIGIT_MAP.update({ord(a): str(i) for i, a in enumerate(ARABIC_DIGITS)})

ZWNJ = "\u200c"
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")

_CHAR_MAP = {
    "ي": "ی", "ى": "ی", "ﻯ": "ی",
    "ك": "ک", "ﻙ": "ک",
    "ة": "ه", "ۀ": "ه",
    "ؤ": "و", "إ": "ا", "أ": "ا", "آ": "ا", "ٱ": "ا",
    "٫": ".", "٬": ",",
}

_MULTI_SPACE = re.compile(r"\s+")


def to_latin_digits(text: str) -> str:
    """ارقام فارسی/عربی را به لاتین تبدیل می‌کند (فقط برای محاسبه، نه برای نمایش)."""
    return text.translate(_DIGIT_MAP)


def normalize(text: Optional[str]) -> str:
    """نرمال‌سازی برای مقایسه: ی/ک فارسی، ارقام لاتین، حذف نیم‌فاصله و اعراب."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", str(text))
    s = s.translate(_DIGIT_MAP)
    for a, b in _CHAR_MAP.items():
        s = s.replace(a, b)
    s = _DIACRITICS.sub("", s)
    s = s.replace(ZWNJ, " ").replace("\u200f", "").replace("\u200e", "")
    s = s.lower()
    s = _MULTI_SPACE.sub(" ", s).strip()
    return s


def tokenize(text: Optional[str]) -> List[str]:
    s = normalize(text)
    return [t for t in re.split(r"[^\w\u0600-\u06FF.]+", s) if len(t) > 0]


STOPWORDS = {
    "میخوام", "می‌خوام", "میخواستم", "خواستم", "دنبال", "یه", "یک", "برای", "با",
    "که", "و", "یا", "از", "به", "در", "تا", "هم", "چه", "چی", "کدام", "بهترین",
    "خوب", "مناسب", "حدود", "حداکثر", "تا", "زیر", "بالای", "تومان", "تومن",
    "هست", "است", "کن", "کنم", "می", "لطفا", "سلام", "میخاستم", "بدم", "بخرم",
    # واژه‌های قصد خرید — در «search_blob» هیچ‌وقت نیستند و اگر توکن بمانند،
    # جست‌وجوی AND را صفر می‌کنند («شارژر اپل برای خرید حضوری در تهران» → ۰ نتیجه)
    "خرید", "خریدن", "خرم", "بخرم", "حضوری", "حاضر", "مغازه", "فروشگاه", "فروشگاه‌ها",
    "بازار", "پاساژ", "راسته", "نزدیک", "نزدیکم", "اطراف", "محله", "شهر", "امروز",
    "فردا", "الان", "میلیون", "میلیارد", "هزار", "تومان", "تومن", "ریال",
    "کجا", "جا", "پیدا", "کنم", "بگیرم", "استعلام", "قیمت", "موجود", "موجودی",
}


# شهرها در «search_blob» محصول نیستند؛ اگر توکن بمانند، جست‌وجوی AND صفر می‌شود.
# (شهر در مرحلهٔ فروشگاه‌ها جداگانه استفاده می‌شود: services/stores.py)
CITY_WORDS = {
    "تهران", "کرج", "مشهد", "اصفهان", "شیراز", "تبریز", "اهواز", "قم", "کرمانشاه",
    "رشت", "یزد", "ارومیه", "زنجان", "کرمان", "همدان", "بندرعباس", "ساری", "قزوین",
    "خرم‌آباد", "گرگان", "اردبیل", "بوشهر", "ایلام", "سنندج", "بجنورد", "بیرجند",
    "خرم آباد", "زاهدان", "یاسوج", "شهرکرد", "سمنان", "اراک", "قشم", "کیش",
}


def content_tokens(text: Optional[str]) -> List[str]:
    """توکن‌های معنادار جست‌وجو.

    توکن‌های دوحرفی حذف می‌شوند: «ام»، «آی»، «پی» در عمل با همه‌چیز مطابقت می‌کنند
    و نتیجهٔ بی‌ربط می‌آورند («دستگاه ام‌آر‌آی» → پک کینگ). ارقام کوتاه (مثل «20»
    در «شارژر 20 وات») می‌مانند چون بخشی از مدل‌اند.
    """
    out: List[str] = []
    for t in tokenize(text):
        if t in STOPWORDS or t in CITY_WORDS:
            continue
        # تک‌رقمی‌ها معمولاً بخشی از بودجه‌اند نه مدل («تا ۳ میلیون» → «۳»)
        if t.isdigit() and len(t) == 1:
            continue
        if len(t) <= 2 and not t.isdigit():
            continue
        out.append(t)
    return out


# --------------------------------------------------------------------------- #
# بودجه
# --------------------------------------------------------------------------- #
_MULT = [
    (re.compile(r"(میلیارد|میليارد|milyard)"), 1_000_000_000),
    (re.compile(r"(میلیون|ملیون|میليون|م\b|m\b)"), 1_000_000),
    (re.compile(r"(هزار|تومن هزار)"), 1_000),
]

_NUM = re.compile(r"(\d+(?:[.,]\d+)?)")


def parse_budget(text: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    """(min, max) بودجه به تومان را از متن استخراج می‌کند. هیچ حدسی زده نمی‌شود."""
    if not text:
        return None, None
    s = normalize(text)
    best: Optional[int] = None
    for m in _NUM.finditer(s):
        raw = m.group(1).replace(",", "")
        try:
            val = float(raw)
        except ValueError:
            continue
        mult = 1
        tail = s[m.end(): m.end() + 14]
        for pat, factor in _MULT:
            if pat.search(tail):
                mult = factor
                break
        amount = int(val * mult)
        if amount >= 10_000 and (best is None or amount > best):
            best = amount
    if best is None:
        return None, None

    window_before = s[max(0, _first_num_pos(s) - 22): _first_num_pos(s) + 12]
    if any(w in window_before for w in ["حداقل", "بالای", "بیشتر از", "بیش از", "از"]):
        return best, None
    return None, best


def _first_num_pos(s: str) -> int:
    m = _NUM.search(s)
    return m.start() if m else 0


_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_DEC_SEP = "٫"   # ممیز فارسی
_THOUSANDS = "٬"  # جداکننده هزارگان فارسی


def fa_digits(text: str) -> str:
    """ارقام لاتین را در یک رشته به فارسی تبدیل می‌کند (برای متن روایی)."""
    return "".join(_FA_DIGITS[int(c)] if c.isdigit() else c for c in str(text))


def fa_number(value: Optional[float], decimals: int = 0, grouping: bool = True) -> str:
    """عدد را با ارقام و جداکننده فارسی برمی‌گرداند: 6476 → «۶٬۴۷۶»."""
    if value is None:
        return "نامشخص"
    if decimals:
        raw = f"{value:,.{decimals}f}"
        raw = raw.replace(",", "\x00").replace(".", _DEC_SEP).replace("\x00", _THOUSANDS)
    else:
        raw = f"{int(round(value)):,}".replace(",", _THOUSANDS)
    return fa_digits(raw)


def fmt_toman(value: Optional[int]) -> str:
    if value is None:
        return "نامشخص"
    if value >= 1_000_000_000:
        v = value / 1_000_000_000
        return f"{fa_number(v, 1 if v % 1 else 0)} میلیارد تومان"
    if value >= 1_000_000:
        v = value / 1_000_000
        return f"{fa_number(v, 1 if v % 1 else 0)} میلیون تومان"
    if value >= 1_000:
        return f"{fa_number(value / 1_000)} هزار تومان"
    return f"{fa_number(value)} تومان"


# ── تمیزکاری نمایشی عنوان (داده اصلی دست‌نخورده می‌ماند) ──────────────────
_TITLE_LEAD_JUNK = '#*•-"\'`«» 	\u200c\u200f'


def clean_title(text: Optional[str]) -> Optional[str]:
    """عنوان محصول/آفر در دیتاست گاهی با # یا " شروع می‌شود و فاصله اضافه دارد.

    این تابع فقط برای **نمایش** است: پیشوندهای زائد را می‌برد و فاصله‌ها را
    یکسان می‌کند. هیچ کلمه‌ای حذف یا بازنویسی نمی‌شود و ارقام لاتین دست‌نخورده
    می‌مانند (مدل محصول مثل J30 نباید به J۳۰ تبدیل شود).
    """
    if not text:
        return text
    out = " ".join(text.split())
    stripped = out.lstrip(_TITLE_LEAD_JUNK)
    # اگر بعد از بریدن، متن معناداری نماند، اصل رشته را برگردان
    return stripped or out
