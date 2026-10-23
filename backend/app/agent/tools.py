"""رجیستری ابزارهای ایجنت — هر ابزار یک قابلیت واقعی روی دادهٔ دیتاست.

ابزارها به دو دسته تقسیم می‌شوند:
  ۱) ابزارهای داده: جست‌وجوی محصول، فروشگاه، مقایسه، تأیید قیمت
  ۲) ابزارهای راهنما: موقعیت، نقشهٔ خرید حضوری، پوشش دیتاست

هر ابزار یک `summary` فارسی برمی‌گرداند که هم در «ردیابی استدلال» به کاربر
نشان داده می‌شود و هم به مدل (در حالت LLM) به‌عنوان observation داده می‌شود.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agent import shopping
from app.core.text import content_tokens, fa_number, fmt_toman, normalize, tokenize

# واژه‌های سربسیار کلی: اگر تنها توکنِ باقی‌ماندهٔ عبارت این باشد، جست‌وجو بی‌معنا می‌شود
GENERIC_HEADS = {
    "دستگاه", "لوازم", "وسیله", "محصول", "کالا", "چیز", "مدل", "برند", "جنس", "خرید",
}
from app.schemas import ProductSearchRequest, StoreSearchRequest
from app.services import search as search_service
from app.services import stores as stores_service
from app.services import verification as verification_service

log = logging.getLogger("agent.tools")

MAX_TOOL_RESULT_CHARS = 4000


@dataclass
class ToolResult:
    ok: bool
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)

    def observation(self) -> str:
        """متن فشرده برای مدل — نه کل JSON سنگین."""
        payload = {
            "ok": self.ok,
            "summary": self.summary,
            **{k: v for k, v in self.data.items() if k not in {"raw", "stores_full"}},
        }
        text = json.dumps(payload, ensure_ascii=False, default=str)
        if len(text) > MAX_TOOL_RESULT_CHARS:
            text = text[:MAX_TOOL_RESULT_CHARS] + "…(بریده شد)"
        return text


@dataclass
class ToolContext:
    db: Session
    facts: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)

    @property
    def lat(self) -> Optional[float]:
        loc = self.facts.get("location") or {}
        return loc.get("lat")

    @property
    def lon(self) -> Optional[float]:
        loc = self.facts.get("location") or {}
        return loc.get("lon")


# --------------------------------------------------------------------------- #
# ابزارهای داده
# --------------------------------------------------------------------------- #
def _search_products(ctx: ToolContext, query: Optional[str] = None, category: Optional[str] = None,
                     max_price: Optional[int] = None, min_price: Optional[int] = None,
                     limit: int = 8) -> ToolResult:
    limit = max(1, min(int(limit or 8), 20))
    budget = max_price if max_price is not None else ctx.facts.get("budget_max")
    base = dict(
        query=query or ctx.facts.get("query"),
        category=category or ctx.facts.get("category"),
        max_price=int(budget) if budget else None,
        min_price=int(min_price) if min_price else None,
        limit=limit,
    )
    # فقط تطبیق دقیق (همهٔ توکن‌ها). عمداً به OR سقوط نمی‌کنیم:
    # OR برای «بلیط هواپیما» اسباب‌بازی هواپیما و برای «دستگاه ام‌آر‌آی» پک کینگ برمی‌گرداند.
    # اگر چیزی پیدا نشد، ایجنت مسیر «پوشش دیتاست → دسته‌های نزدیک → راهنمای خرید» را می‌رود.
    effective = content_tokens(base.get("query") or "")
    all_tokens = tokenize(base.get("query") or "")
    if len(effective) == 1 and len(all_tokens) >= 2 and effective[0] in GENERIC_HEADS:
        # مثل «دستگاه ام‌آر‌آی» که فقط «دستگاه» می‌ماند — نتیجه‌اش دستگاه قند خون است، نه آنچه خواسته
        return ToolResult(
            ok=False,
            summary="عبارت بیش از حد کلی بود؛ نمی‌توانم محصول دقیق را تشخیص دهم",
            data={"too_generic": True, "effective_tokens": effective,
                  "dropped_tokens": [t for t in all_tokens if t not in effective]},
        )

    resp = search_service.search_products(ctx.db, ProductSearchRequest(**base, require_all_tokens=True))
    strict = True
    products = [p.model_dump() for p in resp.results]
    ctx.artifacts["products"] = products
    ctx.artifacts["suggested_categories"] = resp.suggested_categories

    if products:
        cheapest = min(
            (p["min_price_toman"] for p in products if p.get("min_price_toman")), default=None
        )
        summary = f"{fa_number(resp.total)} محصول پیدا شد"
        if cheapest:
            summary += f"؛ ارزان‌ترین از {fmt_toman(cheapest)}"
    else:
        summary = "محصولی با این عبارت پیدا نشد"

    return ToolResult(
        ok=bool(products),
        summary=summary,
        data={
            "total": resp.total,
            "products": [
                {
                    "product_id": p["product_id"],
                    "title": p["persian_title"],
                    "brand": p.get("brand_name"),
                    "category": p.get("category_name"),
                    "shops": p.get("shops_count"),
                    "min_price": p.get("min_price_toman"),
                    "max_price": p.get("max_price_toman"),
                    "has_specs": p.get("has_specs"),
                }
                for p in products
            ],
            "strict_match": strict,
            "suggested_categories": [
                {"name": c["name"], "count": c.get("products_count")}
                for c in resp.suggested_categories[:6]
            ],
        },
    )


def _get_product(ctx: ToolContext, product_id: str) -> ToolResult:
    detail = search_service.get_product_detail(ctx.db, product_id)
    if detail is None:
        return ToolResult(False, "محصول پیدا نشد", {})
    data = detail.model_dump()
    ctx.artifacts["selected_product"] = data
    specs = data.get("specs") or []
    return ToolResult(
        True,
        f"«{data['persian_title']}» — {fa_number(len(specs))} مشخصه ثبت‌شده",
        {
            "product_id": data["product_id"],
            "title": data["persian_title"],
            "brand": data.get("brand_name"),
            "category": data.get("category_name"),
            "specs_count": len(specs),
            "specs": specs[:12],
            "missing_specs_note": data.get("missing_specs_note"),
            "min_price": data.get("min_price_toman"),
            "shops_count": data.get("shops_count"),
        },
    )


def _find_stores(ctx: ToolContext, product_id: str, lat: Optional[float] = None,
                 lon: Optional[float] = None, location_label: Optional[str] = None,
                 radius_km: float = 8.0, only_open_now: bool = False,
                 require_credit: bool = False, require_installment: bool = False,
                 sort_by: str = "smart", limit: int = 8) -> ToolResult:
    req = StoreSearchRequest(
        product_id=product_id,
        lat=lat if lat is not None else ctx.lat,
        lon=lon if lon is not None else ctx.lon,
        location_label=location_label or (ctx.facts.get("location") or {}).get("label"),
        radius_km=float(max(0.3, min(float(radius_km or 8.0), 40.0))),
        only_open_now=only_open_now,
        require_credit=require_credit,
        require_installment=require_installment,
        sort_by=sort_by if sort_by in {"smart", "price", "distance", "hours"} else "smart",
        limit=max(1, min(int(limit or 8), 20)),
    )
    resp = stores_service.search_stores(ctx.db, req)
    stores = [s.model_dump() for s in resp.stores]
    ctx.artifacts["stores"] = stores
    ctx.artifacts["stores_meta"] = {
        "total_candidates": resp.total_candidates,
        "radius_km": resp.radius_km,
        "user_location": resp.user_location,
        "filters_applied": resp.filters_applied,
        "alternatives_note": resp.alternatives_note,
    }
    if stores:
        best = stores[0]
        summary = (
            f"{fa_number(resp.returned)} فروشگاه در شعاع {fa_number(resp.radius_km)} کیلومتر؛ "
            f"بهترین: {best['shop']['name']}"
        )
        if best.get("price", {}).get("value_toman"):
            summary += f" با قیمت {fmt_toman(best['price']['value_toman'])}"
    else:
        summary = resp.alternatives_note or "در این شعاع فروشگاهی پیدا نشد"

    return ToolResult(
        ok=bool(stores),
        summary=summary,
        data={
            "count": resp.returned,
            "total_candidates": resp.total_candidates,
            "radius_km": resp.radius_km,
            "filters": resp.filters_applied,
            "stores": [
                {
                    "offer_id": s["offer_id"],
                    "shop": s["shop"]["name"],
                    "distance_km": s["shop"].get("distance_km"),
                    "price": s["price"].get("value_toman"),
                    "price_verified": s["price"].get("is_verified"),
                    "open_now": s["hours"].get("is_open_now"),
                    "payment": s["payment"].get("status_label"),
                    "score": s.get("score"),
                }
                for s in stores
            ],
        },
    )


def _compare_offers(ctx: ToolContext, offer_ids: List[str]) -> ToolResult:
    rows = stores_service.compare_offers(ctx.db, offer_ids[:6])
    if not rows:
        return ToolResult(False, "آفری برای مقایسه پیدا نشد", {})
    ctx.artifacts["compare"] = [r.model_dump() for r in rows]
    cheapest = min((r.price_toman for r in rows if r.price_toman), default=None)
    return ToolResult(
        True,
        f"{fa_number(len(rows))} فروشگاه مقایسه شد" + (f"؛ کم‌ترین {fmt_toman(cheapest)}" if cheapest else ""),
        {
            "rows": [
                {
                    "shop": r.shop_name,
                    "price": r.price_toman,
                    "distance_km": r.distance_km,
                    "open_now": r.is_open_now,
                    "payment": r.payment_label,
                }
                for r in rows
            ]
        },
    )


def _request_verification(ctx: ToolContext, offer_id: str) -> ToolResult:
    try:
        rec = verification_service.request_verification(ctx.db, offer_id)
    except Exception as exc:  # noqa: BLE001 - خطای تأیید نباید ایجنت را بشکند
        return ToolResult(False, f"تأیید انجام نشد: {exc}", {})
    data = rec.model_dump() if hasattr(rec, "model_dump") else dict(rec)
    ctx.artifacts["verification"] = data
    return ToolResult(
        True,
        f"{data.get('label', 'درخواست تأیید')} — {data.get('note', '')[:120]}",
        {
            "channel": data.get("channel"),
            "is_simulated": data.get("is_simulated"),
            "price_status": data.get("price_status"),
            "stock_status": data.get("stock_status"),
            "script": data.get("script", [])[:6],
        },
    )


# --------------------------------------------------------------------------- #
# ابزارهای موقعیت
# --------------------------------------------------------------------------- #
def _list_locations(ctx: ToolContext, limit: int = 10) -> ToolResult:
    locs = stores_service.location_suggestions(ctx.db, max(1, min(int(limit or 10), 20)))
    ctx.artifacts["locations"] = locs
    return ToolResult(
        True,
        f"{fa_number(len(locs))} محله پرترافیک دیتاست",
        {"locations": locs},
    )


# برچسب‌هایی که خودمان می‌سازیم و محلهٔ دیتاست نیستند
_DERIVED_PREFIXES = ("نزدیک ", "موقعیت ")


def _set_location(ctx: ToolContext, lat: Optional[float] = None, lon: Optional[float] = None,
                  label: Optional[str] = None) -> ToolResult:
    # مختصات دقیق همیشه بر برچسب مقدم است: برچسبی مثل «نزدیک شیخ هادی» نام محلهٔ
    # دیتاست نیست و اگر اول بررسی شود، ما را به مسیر اشتباه می‌برد.
    if lat is not None and lon is not None:
        label = None
    elif label and label.strip().startswith(_DERIVED_PREFIXES):
        label = None  # برچسب مشتق‌شدهٔ خودمان؛ بی‌فایده است

    if label:
        rows = stores_service.location_suggestions(ctx.db, 40)
        match = next((r for r in rows if normalize(r["label"]) == normalize(label)), None)
        if match is None:
            return ToolResult(False, f"محلهٔ «{label}» در دیتاست نبود", {"available": [r["label"] for r in rows[:8]]})
        ctx.facts["location"] = {
            "lat": match["lat"], "lon": match["lon"], "label": match["label"], "source": "dataset_label"
        }
        return ToolResult(
            True,
            f"مرکز جست‌وجو روی «{match['label']}» تنظیم شد ({fa_number(match['shops_count'])} فروشگاه)",
            {"location": ctx.facts["location"]},
        )

    if lat is None or lon is None:
        return ToolResult(False, "مختصات نامعتبر", {})

    # محلهٔ نزدیک به مختصات کاربر — برچسب از دیتاست، نه حدس
    label_found: Optional[str] = None
    rows = stores_service.location_suggestions(ctx.db, 40)
    best, best_d = None, 1e9
    for r in rows:
        d = _haversine(float(lat), float(lon), r["lat"], r["lon"])
        if d < best_d:
            best, best_d = r, d
    if best and best_d <= 6.0:
        label_found = f"نزدیک {best['label']}"
    ctx.facts["location"] = {
        "lat": float(lat),
        "lon": float(lon),
        "label": label_found or "موقعیت فعلی شما",
        "source": "geolocation",
        "nearest_area": best["label"] if best else None,
        "nearest_area_km": round(best_d, 1) if best else None,
    }
    return ToolResult(
        True,
        f"موقعیت شما ثبت شد" + (f" ({label_found})" if label_found else ""),
        {"location": ctx.facts["location"]},
    )


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------- #
# ابزارهای راهنما
# --------------------------------------------------------------------------- #
def _dataset_coverage(ctx: ToolContext, query: str) -> ToolResult:
    """آیا دیتاست این خواسته را پوشش می‌دهد؟ اگر نه، نزدیک‌ترین دسته‌ها را می‌دهد."""
    tokens = tokenize(query)
    products = search_service.search_products(
        ctx.db, ProductSearchRequest(query=query, limit=3, require_all_tokens=True)
    )
    suggestions = products.suggested_categories or search_service.suggest_categories(ctx.db, tokens, 6)
    covered = products.total > 0
    ctx.artifacts["coverage"] = {
        "covered": covered,
        "total": products.total,
        "categories": suggestions,
    }
    return ToolResult(
        True,
        (
            f"این خواسته در دیتاست هست ({fa_number(products.total)} محصول)"
            if covered
            else f"در دیتاست نبود؛ {fa_number(len(suggestions))} دستهٔ نزدیک پیشنهاد می‌شود"
        ),
        {
            "covered": covered,
            "total": products.total,
            "categories": [{"name": c["name"], "count": c.get("products_count")} for c in suggestions[:6]],
        },
    )


def _build_purchase_guide(ctx: ToolContext, product_id: Optional[str] = None,
                          offer_id: Optional[str] = None, intent: Optional[str] = None,
                          budget_max: Optional[int] = None) -> ToolResult:
    """نقشهٔ خرید حضوری — وقتی محصول/فروشگاه انتخاب شده، یا وقتی در دیتاست نیست."""
    budget = budget_max or ctx.facts.get("budget_max")

    # مسیر ۱: محصول در دیتاست
    if product_id or ctx.artifacts.get("selected_product"):
        pid = product_id or ctx.artifacts["selected_product"]["product_id"]
        product = search_service.get_product_detail(ctx.db, pid)
        if product is not None:
            if not ctx.artifacts.get("stores"):
                _find_stores(ctx, product_id=pid, limit=8)
            stores = ctx.artifacts.get("stores") or []
            chosen = None
            if offer_id:
                chosen = next((s for s in stores if s["offer_id"] == offer_id), None)
            chosen = chosen or (stores[0] if stores else None)
            plan = shopping.plan_for_offer(
                product_title=product.persian_title,
                offer=chosen,
                alternatives=[s for s in stores if not chosen or s["offer_id"] != chosen["offer_id"]],
                budget_max=int(budget) if budget else None,
            )
            ctx.artifacts["guide"] = plan
            return ToolResult(
                True,
                f"نقشهٔ خرید حضوری ساخته شد ({fa_number(len(plan['steps']))} گام)",
                {"guide": plan},
            )

    # مسیر ۲: بیرون از دیتاست — راهنمای عمومی
    text = intent or ctx.facts.get("query") or ctx.facts.get("product_type") or "خرید حضوری"
    coverage = ctx.artifacts.get("coverage") or {}
    plan = shopping.plan_generic(
        intent=text,
        budget_max=int(budget) if budget else None,
        near_categories=coverage.get("categories"),
    )
    ctx.artifacts["guide"] = plan
    return ToolResult(
        True,
        "این کالا در دیتاست نبود؛ نقشهٔ خرید عمومی ساخته شد",
        {"guide": plan},
    )


# --------------------------------------------------------------------------- #
# طرح‌واره‌ها (برای tool calling مدل) + نگاشت به پیاده‌سازی
# --------------------------------------------------------------------------- #
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "جست‌وجوی محصول در کاتالوگ واقعی دیتاست (۲۲۵٬۹۰۳ محصول).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "عبارت جست‌وجو به فارسی"},
                    "category": {"type": "string"},
                    "max_price": {"type": "integer", "description": "سقف قیمت به تومان"},
                    "min_price": {"type": "integer"},
                    "limit": {"type": "integer", "default": 8},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": "جزئیات یک محصول شامل مشخصات ثبت‌شده (اگر نباشد حدس نمی‌زنیم).",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_stores",
            "description": "فروشگاه‌های حضوری دارای آفر واقعی برای یک محصول، با فاصله و قیمت.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "radius_km": {"type": "number", "default": 8},
                    "only_open_now": {"type": "boolean", "default": False},
                    "require_credit": {"type": "boolean", "default": False},
                    "require_installment": {"type": "boolean", "default": False},
                    "sort_by": {"type": "string", "enum": ["smart", "price", "distance", "hours"]},
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dataset_coverage",
            "description": "بررسی اینکه آیا دیتاست این خواسته را پوشش می‌دهد؛ اگر نه نزدیک‌ترین دسته‌ها را می‌دهد.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_purchase_guide",
            "description": "ساخت نقشهٔ گام‌به‌گام خرید حضوری. برای محصول موجود در دیتاست با product_id، و برای کالای بیرون از دیتاست با intent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "offer_id": {"type": "string"},
                    "intent": {"type": "string"},
                    "budget_max": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_verification",
            "description": "درخواست تأیید قیمت/موجودی از فروشنده. بدون کانال واقعی، صریحاً «نمایشی» برچسب می‌خورد.",
            "parameters": {
                "type": "object",
                "properties": {"offer_id": {"type": "string"}},
                "required": ["offer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_location",
            "description": "ثبت موقعیت کاربر (مختصات GPS یا نام محله) برای محاسبهٔ فاصله.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "label": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_locations",
            "description": "فهرست محله‌های پرترافیک دیتاست (برای وقتی موقعیت کاربر در دسترس نیست).",
            "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_offers",
            "description": "مقایسهٔ چند آفر (حداکثر ۶) از نظر قیمت، فاصله، ساعت و پرداخت.",
            "parameters": {
                "type": "object",
                "properties": {"offer_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["offer_ids"],
            },
        },
    },
]

IMPLEMENTATIONS: Dict[str, Callable[..., ToolResult]] = {
    "search_products": _search_products,
    "get_product": _get_product,
    "find_stores": _find_stores,
    "dataset_coverage": _dataset_coverage,
    "build_purchase_guide": _build_purchase_guide,
    "request_verification": _request_verification,
    "set_location": _set_location,
    "list_locations": _list_locations,
    "compare_offers": _compare_offers,
}

TOOL_TITLES = {
    "search_products": "جست‌وجوی محصول",
    "get_product": "بررسی جزئیات محصول",
    "find_stores": "یافتن فروشگاه حضوری",
    "dataset_coverage": "بررسی پوشش دیتاست",
    "build_purchase_guide": "ساخت نقشهٔ خرید حضوری",
    "request_verification": "درخواست تأیید قیمت",
    "set_location": "ثبت موقعیت",
    "list_locations": "فهرست محله‌ها",
    "compare_offers": "مقایسهٔ فروشگاه‌ها",
}


def run_tool(ctx: ToolContext, name: str, arguments: Dict[str, Any]) -> ToolResult:
    fn = IMPLEMENTATIONS.get(name)
    if fn is None:
        return ToolResult(False, f"ابزار ناشناخته: {name}", {"available": list(IMPLEMENTATIONS)})
    try:
        return fn(ctx, **(arguments or {}))
    except TypeError as exc:
        return ToolResult(False, f"پارامترهای ابزار نامعتبر: {exc}", {})
    except Exception as exc:  # noqa: BLE001 - یک ابزار خراب نباید کل گفت‌وگو را بشکند
        log.exception("tool %s failed", name)
        return ToolResult(False, f"خطا در اجرای {name}: {type(exc).__name__}", {})
