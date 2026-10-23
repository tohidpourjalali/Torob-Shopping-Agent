"""یافتن و رتبه‌بندی فروشگاه‌های حضوری برای یک محصول.

همه ۶,۴۷۶ فروشگاه دیتاست در تهران هستند (lat 35.64–35.81, lon 51.30–51.51).
بنابراین فاصله واقعاً معنا دارد و برچسب محله (location_label) هم از خود دیتاست
گرفته می‌شود.

اصل شفافیت: هر امتیاز با breakdown برمی‌گردد تا کاربر بفهمد چرا یک فروشگاه
بالاتر آمده است. هیچ‌جا ادعا نمی‌شود قیمت/موجودی تأیید شده است.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict, List, Optional

from sqlalchemy import Float, cast, func, select
from sqlalchemy.orm import Session

from app.core.hours import hours_summary, open_score
from app.core.payment import matches_payment_filter, payment_capabilities
from app.core.text import clean_title, fa_number
from app.db.models import Offer, Product, Shop
from app.schemas import (
    HoursInfo,
    PaymentInfo,
    PriceInfo,
    ProductSummary,
    ShopInfo,
    StockInfo,
    StoreOffer,
    StoreSearchRequest,
    StoreSearchResponse,
)

log = logging.getLogger("services.stores")

# مرکز پیش‌فرض: میدان فردوسی تهران — پرتراکم‌ترین محله دیتاست (۳,۲۸۲ فروشگاه)
DEFAULT_CENTER = {"lat": 35.6945, "lon": 51.4120, "label": "میدان فردوسی، تهران"}

# اوزان امتیاز «هوشمند» — مجموع = ۱
WEIGHTS = {"price": 0.38, "distance": 0.24, "hours": 0.16, "payment": 0.10, "trust": 0.12}


def warranty_label(raw) -> Optional[str]:
    """گارانتی در دیتاست یک رشته JSON است؛ برای کاربر باید برچسب خوانا باشد، نه JSON خام."""
    if not raw:
        return None
    data = raw
    if isinstance(raw, str):
        text = raw.strip()
        if text[:1] in "{[":
            try:
                data = json.loads(text)
            except (ValueError, TypeError):
                return text or None
        else:
            return text or None
    if isinstance(data, dict):
        provider = (data.get("provider") or "").strip()
        months = data.get("period_months")
        desc = (data.get("description") or "").strip()
        if months:
            base = f"گارانتی {fa_number(months)} ماهه"
            return f"{base} — {provider}" if provider else base
        if provider:
            return provider
        if desc:
            return desc
        return None
    return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _f(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coords(shop: Shop) -> tuple[Optional[float], Optional[float]]:
    return _f(shop.lat), _f(shop.lon)


def location_suggestions(session: Session, limit: int = 12) -> List[Dict[str, Any]]:
    """برچسب‌های محله واقعی دیتاست + مرکز میانگین فروشگاه‌های همان محله."""
    rows = session.execute(
        select(
            Shop.location_label,
            func.count(Shop.shop_id),
            func.avg(cast(Shop.lat, Float)),
            func.avg(cast(Shop.lon, Float)),
        )
        .where(Shop.location_label.is_not(None))
        .group_by(Shop.location_label)
        .order_by(func.count(Shop.shop_id).desc())
        .limit(limit)
    ).all()

    out: List[Dict[str, Any]] = []
    for label, count, lat, lon in rows:
        if lat is None or lon is None:
            continue
        out.append({
            "label": label,
            "shops_count": count,
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
        })
    return out


def _resolve_center(
    session: Session, request: StoreSearchRequest
) -> tuple[float, float, str, str]:
    lat = _f(request.lat)
    lon = _f(request.lon)
    if lat is not None and lon is not None:
        return lat, lon, "user", "موقعیت انتخابی شما"

    if request.location_label:
        row = session.execute(
            select(
                func.avg(cast(Shop.lat, Float)),
                func.avg(cast(Shop.lon, Float)),
                func.count(Shop.shop_id),
            ).where(Shop.location_label == request.location_label, Shop.lat.is_not(None))
        ).first()
        if row and row[0] is not None:
            return float(row[0]), float(row[1]), "dataset_label", \
                f"مرکز محله «{request.location_label}» بر پایه {row[2]} فروشگاه دیتاست"

    return DEFAULT_CENTER["lat"], DEFAULT_CENTER["lon"], "default", \
        f"مرکز پیش‌فرض: {DEFAULT_CENTER['label']}"


def _trust_score(shop: Shop) -> float:
    """اعتماد داده‌ای: چه مقدار از اطلاعات فروشگاه در دیتاست پر شده است."""
    checks = [
        shop.name is not None,
        shop.address is not None,
        shop.phone_display is not None,
        bool(shop.weekly_hours and json.loads(shop.weekly_hours or "{}")),
        bool(shop.payment_options and shop.payment_options != "null"),
        bool(shop.website_url or shop.instagram),
        bool(shop.lat and shop.lon),
    ]
    return sum(1 for c in checks if c) / len(checks)


def search_stores(session: Session, request: StoreSearchRequest) -> StoreSearchResponse:
    product_row = session.execute(
        select(
            Product.product_id, Product.persian_title, Product.brand_name, Product.category_name,
            Product.model, Product.image_urls, Product.specs_count, Product.shops_count,
            Product.offers_count, Product.min_price_toman, Product.max_price_toman,
        ).where(Product.product_id == request.product_id)
    ).first()

    product_summary: Optional[ProductSummary] = None
    if product_row:
        from app.services.search import row_to_summary
        product_summary = row_to_summary(product_row)

    user_lat, user_lon, center_source, center_label = _resolve_center(session, request)

    rows = session.execute(
        select(Offer, Shop)
        .join(Shop, Offer.shop_id == Shop.shop_id)
        .where(Offer.product_id == request.product_id)
    ).all()

    candidates: List[StoreOffer] = []
    notes: List[str] = []
    applied: List[str] = []

    if request.radius_km:
        applied.append(f"شعاع {fa_number(request.radius_km, 1 if request.radius_km % 1 else 0)} کیلومتر")
    if request.max_price is not None:
        applied.append(f"سقف قیمت {fa_number(request.max_price)} تومان")
    if request.require_installment:
        applied.append("فقط فروشگاه‌های با امکان اقساط ثبت‌شده")
    if request.require_credit:
        applied.append("فقط فروشگاه‌های با پرداخت اعتباری ثبت‌شده")
    if request.only_open_now:
        applied.append("فقط فروشگاه‌هایی که الان باز هستند")

    prices_pool: List[int] = []

    for offer, shop in rows:
        if offer.price_is_outlier:
            notes.append("یک آفر با قیمت آشکارا خطادار در دیتاست حذف شد.")
            continue
        if request.max_price is not None and (offer.price_toman is None or offer.price_toman > request.max_price):
            continue
        if request.min_price is not None and (offer.price_toman is None or offer.price_toman < request.min_price):
            continue

        lat, lon = _coords(shop)
        distance = None
        if lat is not None and lon is not None:
            distance = haversine_km(user_lat, user_lon, lat, lon)
            if distance > request.radius_km:
                continue
        elif request.location_label:
            continue

        caps = payment_capabilities(shop)
        if not matches_payment_filter(caps, request.require_credit, request.require_installment):
            continue

        hours = hours_summary(shop.weekly_hours)
        if request.only_open_now and hours.get("is_open_now") is not True:
            continue

        if offer.price_toman is not None:
            prices_pool.append(offer.price_toman)

        price_info = (
            PriceInfo(
                value_toman=offer.price_toman,
                source="dataset",
                is_verified=False,
                verification_status="not_confirmed",
                last_price_changed_at=offer.last_price_changed_at,
                label="قیمت ثبت‌شده در دیتاست — تأییدنشده",
                note="قیمت لحظه‌ای فروشگاه نیست؛ آخرین تغییر قیمت در دیتاست ثبت شده است.",
            )
            if offer.price_toman is not None
            else PriceInfo(
                value_toman=None, source="none", verification_status="unknown",
                label="قیمت در دیتاست ثبت نشده",
                note="برای این آفر قیمتی ثبت نشده است؛ باید از فروشگاه پرسیده شود.",
            )
        )

        shop_info = ShopInfo(
            shop_id=shop.shop_id,
            name=shop.name,
            name_label="نام ثبت‌شده در دیتاست — تأییدنشده",
            name_is_verified=bool(shop.name_is_verified),
            address=shop.address,
            location_label=shop.location_label,
            lat=lat,
            lon=lon,
            distance_km=round(distance, 2) if distance is not None else None,
            phone_display=shop.phone_display,
            instagram=shop.instagram,
            website_url=shop.website_url,
            category_names=(json.loads(shop.category_names) if shop.category_names else []),
            supports_fast_delivery=shop.supports_fast_delivery,
            maps_link=(
                f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                if lat is not None and lon is not None else None
            ),
            directions_link=(
                f"https://www.google.com/maps/dir/?api=1&origin={user_lat},{user_lon}"
                f"&destination={lat},{lon}"
                if lat is not None and lon is not None else None
            ),
        )

        candidates.append(
            StoreOffer(
                offer_id=offer.offer_id,
                shop=shop_info,
                price=price_info,
                stock=StockInfo(),
                hours=HoursInfo(**hours),
                payment=PaymentInfo(**caps),
                seller_title=clean_title(offer.seller_title),
                warranty=warranty_label(offer.warranty),
            )
        )

    # --- امتیازدهی (نسبی نسبت به بهترین قیمت/فاصله در همین مجموعه) ---
    best_price = min(prices_pool) if prices_pool else None
    worst_price = max(prices_pool) if prices_pool else None
    dist_values = [c.shop.distance_km for c in candidates if c.shop.distance_km is not None]
    best_dist = min(dist_values) if dist_values else None
    worst_dist = max(dist_values) if dist_values else None

    for c in candidates:
        price = c.price.value_toman
        if price is not None and best_price and worst_price and worst_price > best_price:
            price_score = 1.0 - (price - best_price) / (worst_price - best_price)
        elif price is not None:
            price_score = 1.0
        else:
            price_score = 0.35

        d = c.shop.distance_km
        if d is not None and worst_dist and worst_dist > 0:
            distance_score = max(0.0, 1.0 - (d / max(worst_dist, request.radius_km)))
        elif d is not None:
            distance_score = 1.0
        else:
            distance_score = 0.4

        hours_s = open_score(c.hours.model_dump())
        payment_s = (
            1.0 if (c.payment.installment or c.payment.credit)
            else 0.75 if c.payment.in_person_torob
            else 0.5 if c.payment.has_data
            else 0.4
        )
        trust_s = 0.7  # baseline؛ به‌ازای هر فیلد واقعی در ادامه به‌روزرسانی می‌شود

        breakdown = {
            "price": round(price_score, 3),
            "distance": round(distance_score, 3),
            "hours": round(hours_s, 3),
            "payment": round(payment_s, 3),
            "trust": round(trust_s, 3),
        }
        c.score_breakdown = breakdown
        c.score = round(sum(WEIGHTS[k] * v for k, v in breakdown.items()), 3)

        reasons: List[str] = []
        if price is not None and best_price is not None and price == best_price:
            reasons.append("ارزان‌ترین قیمت در این محدوده")
        if c.shop.distance_km is not None and best_dist is not None and c.shop.distance_km == best_dist:
            reasons.append("نزدیک‌ترین فروشگاه به موقعیت شما")
        if c.hours.is_open_now is True:
            reasons.append(f"الان باز است (امروز {c.hours.today})")
        elif c.hours.is_open_now is False:
            reasons.append("در این ساعت بسته است")
        if c.payment.installment:
            reasons.append("اقساط/وام ثبت‌شده دارد")
        elif c.payment.credit:
            reasons.append("پرداخت اعتباری ثبت‌شده دارد")
        elif c.payment.in_person_torob:
            reasons.append("پرداخت حضوری ثبت‌شده دارد")
        c.rank_reason = reasons

        cautions: List[str] = ["قیمت تأییدنشده است", "موجودی در دیتاست ثبت نشده"]
        if not c.shop.name_is_verified:
            cautions.append("نام فروشگاه تأییدنشده")
        if c.hours.is_open_now is None:
            cautions.append("ساعت کاری نامشخص")
        if c.payment.has_data is False:
            cautions.append("روش پرداخت ثبت نشده")
        c.cautions = cautions

    # --- مرتب‌سازی ---
    if request.sort_by == "price":
        candidates.sort(key=lambda c: (c.price.value_toman is None, c.price.value_toman or 0))
    elif request.sort_by == "distance":
        candidates.sort(key=lambda c: (c.shop.distance_km is None, c.shop.distance_km or 999))
    elif request.sort_by == "hours":
        candidates.sort(key=lambda c: (c.hours.is_open_now is not True, c.shop.distance_km or 999))
    else:
        candidates.sort(key=lambda c: c.score or 0, reverse=True)

    # --- یک ردیف به‌ازای هر فروشگاه ---
    # یک فروشگاه می‌تواند چند آفر برای همان محصول داشته باشد؛ برای خرید حضوری
    # فقط بهترین آفر هر فروشگاه معنا دارد (وگرنه کاربر فکر می‌کند دو فروشگاه است).
    best_by_shop: Dict[str, StoreOffer] = {}
    for c in candidates:
        sid = c.shop.shop_id
        if sid not in best_by_shop:
            best_by_shop[sid] = c
        else:
            kept = best_by_shop[sid]
            kept_price = kept.price.value_toman
            c_price = c.price.value_toman
            if c_price is not None and (kept_price is None or c_price < kept_price):
                best_by_shop[sid] = c
    merged: List[StoreOffer] = list(best_by_shop.values())
    if len(merged) < len(candidates):
        notes.append(
            f"{len(candidates) - len(merged)} آفر تکراری از همان فروشگاه‌ها حذف شد؛ "
            "برای هر فروشگاه بهترین آفر نمایش داده می‌شود."
        )
    candidates = merged

    total = len(candidates)
    page = candidates[: request.limit]

    data_notes = [
        "قیمت‌ها snapshot دیتاست هستند، نه قیمت زنده فروشگاه.",
        "دیتاست هیچ فیلد موجودی انبار ندارد؛ وضعیت موجودی همیشه «نامشخص» است تا تأیید شود.",
    ]
    if not rows:
        notes.append("هیچ آفری برای این محصول در دیتاست ثبت نشده است.")

    alternatives_note = None
    if total == 0 and rows:
        alternatives_note = (
            "با این فیلترها فروشگاهی پیدا نشد. پیشنهاد: شعاع را بیشتر کنید یا "
            "فیلتر پرداخت/ساعت را بردارید."
        )

    return StoreSearchResponse(
        product=product_summary,
        stores=page,
        total_candidates=total,
        returned=len(page),
        radius_km=request.radius_km,
        user_location={
            "lat": round(user_lat, 6),
            "lon": round(user_lon, 6),
            "source": center_source,
            "label": center_label,
        },
        filters_applied=applied,
        alternatives_note=alternatives_note,
        data_notes=data_notes,
    )
