"""مسیرهای API — قرارداد کامل برای فرانت‌اند RTL."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import io

from fastapi import APIRouter
from fastapi import Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import DatasetMeta, Offer, Product, Shop, VerificationRecord
from app.schemas import (
    VerificationRecentOut,
    AgentCapabilities,
    AgentChatRequest,
    AgentChatResponse,
    CompareRequest,
    CompareResponse,
    CompareRow,
    DatasetMetaOut,
    LocationSuggestion,
    ProductDetail,
    ProductSearchRequest,
    ProductSearchResponse,
    StoreSearchRequest,
    StoreSearchResponse,
    VerificationRecordOut,
    VerificationRequest,
    VerificationResponse,
)
from app.agent import AgentRuntime, capabilities as agent_capabilities
from app.agent import planner
from app.services import search as search_service
from app.services import stores as stores_service
from app.services import verification as verification_service
from app.core.text import fa_number

log = logging.getLogger("api")

router = APIRouter()
meta_router = APIRouter()


# --------------------------------------------------------------------------- #
# سلامت و متادیتا
# --------------------------------------------------------------------------- #
@router.get("/health")
def health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """liveness + وضعیت داده. هرگز 500 نمی‌دهد تا healthcheck PaaS نشکند."""
    try:
        shops = db.scalar(select(func.count()).select_from(Shop)) or 0
        products = db.scalar(select(func.count()).select_from(Product)) or 0
        offers = db.scalar(select(func.count()).select_from(Offer)) or 0
    except Exception as exc:  # جدول‌ها ساخته نشده‌اند / دیتابیس در دسترس نیست
        log.warning("health: database not ready: %s", exc)
        return {
            "status": "degraded",
            "database": "unavailable",
            "counts": {"shops": 0, "products": 0, "offers": 0},
            "dataset_loaded": False,
            "hint": "جداول ساخته نشده‌اند یا اتصال دیتابیس برقرار نیست؛ "
                    "اسکریپت scripts/import_csv.py را اجرا کنید.",
        }
    return {
        "status": "ok",
        "database": "connected",
        "counts": {"shops": shops, "products": products, "offers": offers},
        "dataset_loaded": products > 0,
    }


@router.get("/dataset/meta", response_model=DatasetMetaOut)
def dataset_meta(db: Session = Depends(get_db)) -> DatasetMetaOut:
    row = db.execute(select(DatasetMeta).order_by(DatasetMeta.id.desc()).limit(1)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=503, detail="دیتاست وارد نشده است. اسکریپت import را اجرا کنید.")

    priced = db.scalar(select(func.count()).select_from(Offer).where(Offer.price_toman.is_not(None))) or 0
    outlier = db.scalar(select(func.count()).select_from(Offer).where(Offer.price_is_outlier.is_(True))) or 0

    return DatasetMetaOut(
        dataset_name=row.dataset_name,
        shops_count=row.shops_count or 0,
        products_count=row.products_count or 0,
        offers_count=row.offers_count or 0,
        offers_with_price=priced,
        shops_with_coords=row.shops_with_coords or 0,
        imported_at=row.imported_at,
        source_note=row.source_note,
        coverage_note=(
            f"تمام {fa_number(row.shops_count)} فروشگاه دیتاست در تهران هستند "
            f"({fa_number(row.shops_with_coords)} فروشگاه مختصات دارند)."
        ),
        price_freshness_note=(
            f"{fa_number(priced)} آفر قیمت دارند؛ این قیمت‌ها snapshot دیتاست هستند و قیمت زنده نیستند. "
            f"{fa_number(outlier)} آفر با قیمت آشکارا خطادار علامت خورده و از رتبه‌بندی حذف می‌شوند."
        ),
        stock_note="دیتاست هیچ فیلد موجودی انبار ندارد؛ وضعیت موجودی همیشه «نامشخص» است تا تأیید شود.",
    )


@router.get("/dataset/locations", response_model=List[LocationSuggestion])
def locations(db: Session = Depends(get_db), limit: int = Query(12, ge=1, le=40)):
    return [LocationSuggestion(**x) for x in stores_service.location_suggestions(db, limit)]


@router.get("/examples")
def examples() -> Dict[str, Any]:
    return {
        "starters": planner.STARTER_EXAMPLES,
        "budget_options": [
            {"label": "تا ۵۰۰ هزار تومان", "value": "تا ۵۰۰ هزار تومان"},
            {"label": "تا ۲ میلیون تومان", "value": "تا ۲ میلیون تومان"},
            {"label": "تا ۱۰ میلیون تومان", "value": "تا ۱۰ میلیون تومان"},
            {"label": "مهم نیست، مقایسه کن", "value": "بودجه محدود نیست"},
        ],
        "note": "این مثال‌ها از دسته‌بندی‌های پرترافیک دیتاست انتخاب شده‌اند.",
    }


# --------------------------------------------------------------------------- #
# محصول
# --------------------------------------------------------------------------- #
@router.post("/products/search", response_model=ProductSearchResponse)
def products_search(payload: ProductSearchRequest, db: Session = Depends(get_db)):
    return search_service.search_products(db, payload)


@router.get("/products/{product_id}", response_model=ProductDetail)
def product_detail(product_id: str, db: Session = Depends(get_db)):
    detail = search_service.get_product_detail(db, product_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="محصول پیدا نشد")
    return detail


@router.get("/products", response_model=ProductSearchResponse)
def products_quick(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return search_service.search_products(
        db, ProductSearchRequest(query=q, category=category, limit=limit)
    )


# --------------------------------------------------------------------------- #
# فروشگاه
# --------------------------------------------------------------------------- #
@router.post("/stores/search", response_model=StoreSearchResponse)
def stores_search(payload: StoreSearchRequest, db: Session = Depends(get_db)):
    if not payload.product_id:
        raise HTTPException(status_code=422, detail="product_id الزامی است")
    return stores_service.search_stores(db, payload)


@router.post("/stores/compare", response_model=CompareResponse)
def stores_compare(payload: CompareRequest, db: Session = Depends(get_db)):
    if not payload.offer_ids:
        raise HTTPException(status_code=422, detail="حداقل یک offer_id لازم است")

    rows_in = db.execute(
        select(Offer, Shop).join(Shop, Offer.shop_id == Shop.shop_id)
        .where(Offer.offer_id.in_(payload.offer_ids))
    ).all()

    if not rows_in:
        raise HTTPException(status_code=404, detail="هیچ‌کدام از آفرها پیدا نشد")

    from app.core.hours import hours_summary
    from app.core.payment import payment_capabilities

    rows: List[CompareRow] = []
    for offer, shop in rows_in:
        caps = payment_capabilities(shop)
        hours = hours_summary(shop.weekly_hours)
        rows.append(CompareRow(
            offer_id=offer.offer_id,
            shop_name=shop.name,
            price_toman=offer.price_toman,
            open_now=hours.get("is_open_now"),
            payment_label=caps.get("status_label", "نامشخص"),
            hours_label=hours.get("status_label", "نامشخص"),
            price_verified=False,
            score=0.0,
        ))

    priced = [r for r in rows if r.price_toman is not None]
    best_price = min(priced, key=lambda r: r.price_toman) if priced else None

    summary: List[str] = []
    if best_price:
        summary.append(
            f"کمترین قیمت ثبت‌شده: {fa_number(best_price.price_toman)} تومان "
            f"در «{best_price.shop_name or 'فروشگاه بدون نام'}» — تأییدنشده."
        )
    open_now = [r for r in rows if r.open_now is True]
    if open_now:
        summary.append(f"{fa_number(len(open_now))} فروشگاه در این ساعت باز است.")
    unknown_hours = [r for r in rows if r.open_now is None]
    if unknown_hours:
        summary.append(f"ساعت کاری {fa_number(len(unknown_hours))} فروشگاه نامشخص است.")

    return CompareResponse(
        rows=rows,
        best_price_offer_id=best_price.offer_id if best_price else None,
        best_distance_offer_id=None,
        best_overall_offer_id=best_price.offer_id if best_price else None,
        summary=summary,
        notes=[
            "مقایسه بر پایه قیمت ثبت‌شده در دیتاست است، نه قیمت تأییدنشده (هیچ قیمتی تأیید نشده).",
            "برای فاصله، از صفحه فروشگاه‌ها با موقعیت مکانی استفاده کنید.",
        ],
    )


# --------------------------------------------------------------------------- #
# QR — پل بین «مرورگر مسدودکننده» و گوشی کاربر
# --------------------------------------------------------------------------- #
@router.get("/qr")
def qr_code(data: str, scale: int = 6):
    """تصویر QR از یک URL — بدون هیچ سرویس بیرونی، روی سرور ساخته می‌شود.

    چرا لازم است: وقتی صفحه داخل iframe یا وب‌ویو اجرا می‌شود، مرورگر
    `window.open` را مسدود می‌کند و لینک مسیریابی هیچ کاری نمی‌کند. با این
    endpoint همان لینک را روی گوشی کاربر اسکن می‌کنیم — مسیر واقعاً باز می‌شود.
    """
    payload = (data or "").strip()
    if not payload:
        raise HTTPException(status_code=400, detail="پارامتر data لازم است")
    if len(payload) > 1200:
        raise HTTPException(status_code=400, detail="طول داده بیش از حد مجاز است")

    import segno

    buf = io.BytesIO()
    segno.make(payload, error="m").save(
        buf, kind="png", scale=max(2, min(scale, 14)), border=2, dark="#0f172a"
    )
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# --------------------------------------------------------------------------- #
# تأیید
# --------------------------------------------------------------------------- #
@router.post("/verify", response_model=VerificationResponse)
def verify(payload: VerificationRequest, db: Session = Depends(get_db)):
    try:
        return verification_service.verify_offer(db, payload)
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("offer_not_found"):
            raise HTTPException(status_code=404, detail="آفر پیدا نشد")
        if msg.startswith("offer_price_outlier"):
            raise HTTPException(
                status_code=422,
                detail="قیمت این آفر در دیتاست آشکارا خطادار است و قابل تأیید نیست.",
            )
        raise HTTPException(status_code=400, detail=msg)


@router.get("/verifications/recent", response_model=List[VerificationRecentOut])
def recent_verifications(limit: int = 10, db: Session = Depends(get_db)):
    """آخرین استعلام‌های ثبت‌شده — تا صفحهٔ پیگیری بدون شناسه هم چیزی نشان دهد."""
    from app.db.models import Offer, Product, Shop

    rows = (
        db.execute(
            select(VerificationRecord, Offer, Shop, Product)
            .outerjoin(Offer, Offer.offer_id == VerificationRecord.offer_id)
            .outerjoin(Shop, Shop.shop_id == VerificationRecord.shop_id)
            .outerjoin(Product, Product.product_id == Offer.product_id)
            .order_by(VerificationRecord.checked_at.desc())
            .limit(max(1, min(limit, 50)))
        )
        .all()
    )
    out = []
    for rec, _offer, shop, product in rows:
        out.append(
            VerificationRecentOut(
                id=rec.id,
                offer_id=rec.offer_id,
                shop_name=shop.name if shop is not None else None,
                product_title=product.persian_title if product is not None else None,
                channel=rec.channel,
                is_simulated=rec.is_simulated,
                checked_at=rec.checked_at,
                price_status=rec.price_status,
                stock_status=rec.stock_status,
                label="نمایشی — بدون تماس واقعی" if rec.is_simulated else "پاسخ واقعی فروشنده",
            )
        )
    return out


@router.get("/verify/{offer_id}", response_model=List[VerificationRecordOut])
def verify_history(offer_id: str, db: Session = Depends(get_db)):
    recs = db.execute(
        select(VerificationRecord)
        .where(VerificationRecord.offer_id == offer_id)
        .order_by(VerificationRecord.checked_at.desc())
        .limit(20)
    ).scalars().all()
    return [VerificationRecordOut.model_validate(r, from_attributes=True) for r in recs]


# --------------------------------------------------------------------------- #
# عامل کشف نیاز
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# ایجنت (حلقهٔ ابزارمحور)
# --------------------------------------------------------------------------- #
@router.post("/agent/chat", response_model=AgentChatResponse)
def agent_chat(payload: AgentChatRequest, db: Session = Depends(get_db)) -> AgentChatResponse:
    """گفت‌وگو با ایجنت: خودش ابزار صدا می‌زند و نقشهٔ خرید حضوری می‌سازد."""
    return AgentRuntime(db).chat(payload)


@router.get("/agent/capabilities", response_model=AgentCapabilities)
def agent_caps() -> AgentCapabilities:
    """شفافیت: مدل فعال است یا نه، و چه ابزارهایی در اختیار ایجنت است."""
    return AgentCapabilities(**agent_capabilities())


@router.post("/location/reverse")
def location_reverse(lat: float, lon: float, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """نزدیک‌ترین محلهٔ دیتاست به مختصات کاربر (برای برچسب «موقعیت شما»)."""
    from app.agent.tools import ToolContext, run_tool

    ctx = ToolContext(db, {}, {})
    res = run_tool(ctx, "set_location", {"lat": lat, "lon": lon})
    return {"ok": res.ok, "summary": res.summary, "location": ctx.facts.get("location")}


# مسیر قدیمی /api/discover حذف شد؛ جایش POST /api/agent/chat است.
