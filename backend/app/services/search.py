"""جست‌وجوی محصول — نرمال‌سازی فارسی + تطبیق چندتوکنی + پیشنهاد دسته.

داده واقعی: ۲۲۵,۹۰۳ محصول، ۲,۹۶۳ دسته‌بندی. جست‌وجو روی ستون پیش‌محاسبه‌شده
`search_blob` (عنوان+برند+دسته+مدل نرمال‌شده) انجام می‌شود تا نیم‌فاصله،
«ي/ك» عربی و ارقام فارسی مشکلی ایجاد نکنند.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session


from app.core.text import clean_title, content_tokens, fa_number, normalize, tokenize
from app.db.models import Offer, Product
from app.schemas import (
    PriceInfo,
    ProductDetail,
    ProductSearchRequest,
    ProductSearchResponse,
    ProductSpec,
    ProductSummary,
)

log = logging.getLogger("services.search")

_SELECT_FIELDS = (
    Product.product_id, Product.persian_title, Product.brand_name, Product.category_name,
    Product.model, Product.image_urls, Product.specs_count, Product.shops_count,
    Product.offers_count, Product.min_price_toman, Product.max_price_toman,
)

MAX_CANDIDATE_ROWS = 4000


def first_image(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, list) and data:
            return str(data[0])
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def image_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [str(x) for x in data if x] if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def parse_specs(raw: Optional[str]) -> List[Dict[str, Optional[str]]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    out: List[Dict[str, Optional[str]]] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                out.append({
                    "key": item.get("key"),
                    "section": item.get("section"),
                    "value": item.get("value"),
                })
    return out


def _unverified_price(value: Optional[int], label: str = "کمترین قیمت ثبت‌شده در دیتاست — تأییدنشده") -> PriceInfo:
    if value is None:
        return PriceInfo(
            value_toman=None, source="none", verification_status="unknown",
            label="قیمتی در دیتاست ثبت نشده است",
            note="هیچ آفر قیمت‌دار برای این محصول وجود ندارد.",
        )
    return PriceInfo(
        value_toman=value, source="dataset", is_verified=False,
        verification_status="not_confirmed", label=label,
        note="این قیمت از دیتاست (snapshot) خوانده شده و قیمت لحظه‌ای فروشگاه نیست.",
    )


# --------------------------------------------------------------------------- #
# تطبیق / امتیاز
# --------------------------------------------------------------------------- #
def _score_row(row, tokens: List[str]) -> Tuple[float, List[str], List[str]]:
    title = normalize(row.persian_title or "")
    brand = normalize(row.brand_name or "")
    category = normalize(row.category_name or "")
    model = normalize(row.model or "")
    haystack = " ".join([title, brand, category, model])

    matched = [t for t in tokens if t in haystack]
    coverage = len(matched) / max(len(tokens), 1)

    score = 0.45 * coverage

    # عنوان دقیق‌تر = امتیاز بالاتر
    if tokens and all(t in title for t in tokens):
        score += 0.30
    # برند
    if any(t in brand for t in tokens):
        score += 0.12
    # دسته‌بندی
    if any(t in category for t in tokens):
        score += 0.08
    # محبوبیت/پوشش فروشگاه‌ها
    shops = row.shops_count or 0
    score += min(0.15, shops / 40.0)

    reasons: List[str] = []
    limits: List[str] = []
    if category:
        reasons.append(f"دسته: {row.category_name}")
    if brand:
        reasons.append(f"برند: {row.brand_name}")
    if shops:
        reasons.append(f"در {fa_number(shops)} فروشگاه موجود است")
    if not matched:
        limits.append("تطابق متنی ضعیف با عبارت جست‌وجو")
    if not (row.specs_count or 0):
        limits.append("مشخصات فنی در دیتاست ثبت نشده است")
    if not (row.offers_count or 0):
        limits.append("هیچ آفری برای این محصول ثبت نشده است")

    return min(1.0, round(score, 3)), reasons, limits


def row_to_summary(row, tokens: Optional[List[str]] = None) -> ProductSummary:
    score, reasons, limits = _score_row(row, tokens) if tokens is not None else (None, [], [])
    return ProductSummary(
        product_id=row.product_id,
        persian_title=clean_title(row.persian_title),
        brand_name=row.brand_name,
        category_name=row.category_name,
        model=row.model,
        image_url=first_image(row.image_urls),
        specs_count=row.specs_count or 0,
        has_specs=bool(row.specs_count),
        shops_count=row.shops_count or 0,
        offers_count=row.offers_count or 0,
        min_price_toman=row.min_price_toman,
        max_price_toman=row.max_price_toman,
        price=_unverified_price(row.min_price_toman),
        match_score=score,
        match_reasons=reasons,
        limitations=limits,
    )


# --------------------------------------------------------------------------- #
# جست‌وجو
# --------------------------------------------------------------------------- #
def _like_any(column, tokens: List[str]):
    return or_(*[column.like(f"%{t}%") for t in tokens])


def _build_query(session: Session, tokens: List[str], request: ProductSearchRequest):
    """اجرای پرس‌وجو با یک مجموعهٔ مشخص از توکن‌ها (بدون relaxation)."""
    stmt = select(*_SELECT_FIELDS)
    if tokens:
        if request.require_all_tokens:
            for t in tokens:
                stmt = stmt.where(Product.search_blob.like(f"%{t}%"))
        else:
            stmt = stmt.where(_like_any(Product.search_blob, tokens))
    if request.category:
        stmt = stmt.where(Product.category_name.like(f"%{normalize(request.category)}%"))
    if request.brand:
        stmt = stmt.where(Product.brand_name.like(f"%{normalize(request.brand)}%"))
    if request.min_price is not None:
        stmt = stmt.where(Product.max_price_toman >= request.min_price)
    if request.max_price is not None:
        stmt = stmt.where(Product.min_price_toman <= request.max_price)
    return session.execute(stmt.limit(MAX_CANDIDATE_ROWS)).all()


def _search_with_relaxation(session: Session, tokens: List[str], request: ProductSearchRequest):
    """جست‌وجوی AND با عقب‌نشینی تدریجی.

    مسئله: کاربر جملهٔ طبیعی می‌نویسد («شارژر اپل برای خرید حضوری در تهران»).
    توکن‌های شهری/قصدی در `search_blob` نیستند؛ با AND سخت نتیجه **صفر** می‌شد و
    اپ نتیجه می‌گرفت «این کالا در دیتاست نیست» — در حالی که هست.
    راه‌حل: اگر با همهٔ توکن‌ها چیزی پیدا نشد، به‌ترتیب کم‌اهمیت‌ترین توکن را
    کنار می‌گذاریم (اول از انتها، بعد حریصانه هر توکنی) تا نتیجه پیدا شود.
    توکن‌های حذف‌شده برگردانده می‌شوند تا در پاسخ شفاف اعلام شوند.
    """
    if not tokens:
        return [], []

    rows = _build_query(session, tokens, request)
    if rows or len(tokens) == 1:
        return rows, []

    # سقف تعداد پرس‌وجوها: هر پرس‌وجو روی ۲۲۵ هزار ردیف انجام می‌شود
    budget = 8

    # ۱) کوتاه‌کردن از انتها (واژه‌های قصدی/شهری معمولاً آخر جمله‌اند)
    for keep in range(len(tokens) - 1, 0, -1):
        budget -= 1
        rows = _build_query(session, tokens[:keep], request)
        if rows:
            return rows, tokens[keep:]
        if budget <= 0:
            return [], []

    # ۲) حذف حریصانهٔ تک‌تک توکن‌ها (جunk می‌تواند وسط جمله باشد)
    remaining = list(tokens)
    dropped: List[str] = []
    while len(remaining) > 1 and budget > 0:
        for i in range(len(remaining) - 1, -1, -1):
            if budget <= 0:
                break
            budget -= 1
            trial = remaining[:i] + remaining[i + 1:]
            rows = _build_query(session, trial, request)
            if rows:
                dropped.append(remaining[i])
                return rows, dropped
        # هیچ حذف تک‌تایی جواب نداد → آخرین توکن را بردار و ادامه بده
        dropped.append(remaining.pop())

    return [], dropped


def search_products(session: Session, request: ProductSearchRequest) -> ProductSearchResponse:
    tokens = content_tokens(request.query) if request.query else []

    if not tokens and not request.category and not request.brand:
        # بدون عبارت: محبوب‌ترین محصولات دارای آفر
        rows = session.execute(
            select(*_SELECT_FIELDS)
            .where(Product.offers_count > 0)
            .order_by(Product.shops_count.desc(), Product.offers_count.desc())
            .limit(request.limit)
        ).all()
        return ProductSearchResponse(
            results=[row_to_summary(r) for r in rows],
            total=len(rows),
            query=request.query,
            note="عبارت جست‌وجو خالی بود؛ پرپوشش‌ترین محصولات نمایش داده می‌شود.",
        )

    rows, dropped = _search_with_relaxation(session, tokens, request)
    if dropped:
        log.info("search relaxed: dropped=%s kept=%s",
                 dropped, [t for t in tokens if t not in dropped])

    scored = []
    for r in rows:
        score, reasons, limits = _score_row(r, tokens)
        if request.min_match_score and score < request.min_match_score:
            continue
        scored.append((score, r, reasons, limits))
    scored.sort(key=lambda x: (x[0], x[1].shops_count or 0), reverse=True)

    total = len(scored)
    page = scored[request.offset: request.offset + request.limit]

    results: List[ProductSummary] = []
    for score, r, reasons, limits in page:
        summary = row_to_summary(r)
        summary.match_score = score
        summary.match_reasons = reasons
        summary.limitations = limits
        results.append(summary)

    suggestions = suggest_categories(session, tokens) if tokens else []

    note = None
    if not results:
        note = "محصولی با این عبارت پیدا نشد. می‌توانید دسته‌بندی را از پیشنهادها انتخاب کنید."
    elif dropped and results and request.require_all_tokens:
        # صادقانه بگو که عبارت کوتاه شد، تا کاربر فکر نکند همهٔ کلماتش اعمال شده
        note = (
            f"عبارت «{' '.join(tokens)}» نتیجه نداد؛ با «{' '.join(t for t in tokens if t not in dropped)}» "
            f"جست‌وجو شد و {fa_number(total)} محصول پیدا شد."
        )
    elif total > request.limit:
        note = f"{fa_number(total)} محصول مطابق پیدا شد؛ {fa_number(len(results))} مورد برتر نمایش داده شده است."

    return ProductSearchResponse(
        results=results, total=total, query=request.query,
        suggested_categories=suggestions, note=note,
    )


def suggest_categories(session: Session, tokens: List[str], limit: int = 8) -> List[Dict[str, Any]]:
    """دسته‌های پرتکرار مرتبط با عبارت — برای اینکه کاربر گام بعدی را راحت انتخاب کند."""
    if not tokens:
        return []
    stmt = (
        select(Product.category_name, func.count(Product.product_id).label("n"))
        .where(_like_any(Product.search_blob, tokens), Product.category_name.is_not(None))
        .group_by(Product.category_name)
        .order_by(func.count(Product.product_id).desc())
        .limit(limit)
    )
    return [{"name": name, "products_count": n} for name, n in session.execute(stmt).all()]


def get_product_detail(session: Session, product_id: str) -> Optional[ProductDetail]:
    row = session.execute(
        select(*_SELECT_FIELDS, Product.specs).where(Product.product_id == product_id)
    ).first()
    if not row:
        return None

    summary = row_to_summary(row)
    specs = parse_specs(row.specs)

    note = None
    if not specs:
        note = "برای این محصول در دیتاست هیچ مشخصات فنی ثبت نشده است؛ ما آن را حدس نمی‌زنیم."

    peers: List[str] = []
    if not specs and row.category_name:
        peers = [
            t for (t,) in session.execute(
                select(Product.persian_title)
                .where(Product.category_name == row.category_name, Product.specs_count > 4)
                .limit(3)
            ).all() if t
        ]
        peers = [clean_title(t) for t in peers]

    return ProductDetail(
        **summary.model_dump(),
        image_urls=image_list(row.image_urls),
        specs=[ProductSpec(**s) for s in specs],
        missing_specs_note=note,
        category_sample_peers=peers,
    )


def offers_count_for_product(session: Session, product_id: str) -> int:
    return session.scalar(
        select(func.count()).select_from(Offer).where(Offer.product_id == product_id)
    ) or 0
