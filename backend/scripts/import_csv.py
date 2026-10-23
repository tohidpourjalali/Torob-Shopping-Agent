"""Import دیتاست CSV (Starcoach v16 cap300) به دیتابیس.

ویژگی‌ها:
- خواندن streaming با csv.DictReader — حافظه‌مصرف کم برای ۳۳۱k آفر و ۲۲۶k محصول.
- درج دسته‌ای با Core insert — سریع‌تر از ORM در این حجم.
- تبدیل ایمن JSON؛ مقدار خالی/«null» => NULL (هیچ مقدار فرضی ساخته نمی‌شود).
- شماره تلفن همان‌طور که در دیتاست هست ذخیره می‌شود (ارقام فارسی، بدون تغییر).
- قیمت‌های آشکارا خطادار «علامت» می‌خورند، نه حذف.
- در پایان: گزارش اعتبارسنجی + ثبت شناسنامه دیتاست در جدول dataset_meta.

اجرا:
    DATASET_DIR=/path/to/csv python scripts/import_csv.py
"""

from __future__ import annotations

import csv
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, insert, select

from app.core.text import normalize
from app.db.database import DATABASE_URL, Base, SessionLocal, engine
from app.db.models import DatasetMeta, Offer, Product, Shop

csv.field_size_limit(10 ** 9)

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
log = logging.getLogger("import_csv")

BATCH = int(os.getenv("IMPORT_BATCH_SIZE", "10000"))
NULLS = {"", "null", "none", "na", "n/a", "nan"}

# قیمت بالاتر از این آستانه در دیتاست آشکارا خطای داده است
# (بیشترین قیمت معقول مشاهده‌شده ~۴۳۰ میلیارد تومان)
PRICE_OUTLIER_MAX = 1_000_000_000_000


# --------------------------------------------------------------------------- #
# ابزارهای تبدیل
# --------------------------------------------------------------------------- #
def clean(val: Optional[str]) -> Optional[str]:
    """رشته را تمیز می‌کند؛ خالی/null => None."""
    if val is None:
        return None
    v = val.strip()
    return None if v.lower() in NULLS else v


def as_json(val: Optional[str]) -> Any:
    v = clean(val)
    if v is None:
        return None
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return None


def as_bool(val: Optional[str]) -> Optional[bool]:
    v = clean(val)
    if v is None:
        return None
    return v.lower() in {"true", "1", "yes", "بله"}


def as_dt_utc_naive(val: Optional[str]) -> Optional[datetime]:
    """ISO-8601 با offset را به UTC naive تبدیل می‌کند (سازگار با SQLite)."""
    v = clean(val)
    if v is None:
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def rows(path: Path) -> Iterator[Dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def flush(session, model, batch: List[dict]) -> int:
    if not batch:
        return 0
    session.execute(insert(model), batch)
    session.commit()
    n = len(batch)
    batch.clear()
    return n


# --------------------------------------------------------------------------- #
# shops
# --------------------------------------------------------------------------- #
def transform_shop(row: Dict[str, str]) -> dict:
    contacts = as_json(row.get("contacts"))
    phone = None
    if isinstance(contacts, list):
        for c in contacts:
            if isinstance(c, dict) and c.get("channel") == "phone" and c.get("display_number"):
                phone = str(c["display_number"]).strip()  # بدون تغییر/نرمال‌سازی
                break

    payments = as_json(row.get("payment_options"))
    channels: List[str] = []
    providers: List[str] = []
    if isinstance(payments, list):
        for p in payments:
            if not isinstance(p, dict):
                continue
            ch = p.get("channel")
            if ch and ch not in channels:
                channels.append(ch)
            pr = p.get("provider_name")
            if pr and pr not in providers:
                providers.append(pr)

    return {
        "shop_id": clean(row.get("shop_id")),
        "name": clean(row.get("name")),
        "address": clean(row.get("address")),
        "location_label": clean(row.get("location_label")),
        "lat": clean(row.get("lat")),
        "lon": clean(row.get("lon")),
        "category_names": json.dumps(as_json(row.get("category_names")) or [], ensure_ascii=False),
        "contacts": json.dumps(contacts, ensure_ascii=False) if contacts is not None else None,
        "instagram": clean(row.get("instagram")),
        "website_url": clean(row.get("website_url")),
        "payment_options": json.dumps(payments, ensure_ascii=False) if payments is not None else None,
        "supports_fast_delivery": as_bool(row.get("supports_fast_delivery")),
        "weekly_hours": json.dumps(as_json(row.get("weekly_hours")) or {}, ensure_ascii=False),
        "phone_display": phone,
        "payment_channels": ",".join(channels) if channels else None,
        "payment_providers": json.dumps(providers, ensure_ascii=False) if providers else None,
        "name_is_verified": False,
        "contact_is_verified": False,
    }


def import_shops(path: Path, session) -> int:
    total, batch = 0, []
    for row in rows(path):
        batch.append(transform_shop(row))
        if len(batch) >= BATCH:
            total += flush(session, Shop, batch)
            log.info("shops: %d", total)
    total += flush(session, Shop, batch)
    return total


# --------------------------------------------------------------------------- #
# products
# --------------------------------------------------------------------------- #
def transform_product(row: Dict[str, str]) -> dict:
    imgs = as_json(row.get("image_urls")) or []
    specs = as_json(row.get("specs")) or []
    if isinstance(specs, dict):  # محافظت: اگر ساختار dict بود
        specs = [{"key": k, "section": None, "value": v} for k, v in specs.items()]
    return {
        "product_id": clean(row.get("product_id")),
        "persian_title": clean(row.get("persian_title")),
        "brand_name": clean(row.get("brand_name")),
        "category_name": clean(row.get("category_name")),
        "model": clean(row.get("model")),
        "image_urls": json.dumps(imgs, ensure_ascii=False),
        "specs": json.dumps(specs, ensure_ascii=False),
        "specs_count": len(specs) if isinstance(specs, list) else 0,
        "title_norm": normalize(row.get("persian_title")),
        "search_blob": normalize(" ".join(filter(None, [
            row.get("persian_title"), row.get("brand_name"),
            row.get("category_name"), row.get("model"),
        ]))),
        "shops_count": 0,
        "offers_count": 0,
    }


def import_products(path: Path, session) -> int:
    total, batch = 0, []
    for row in rows(path):
        batch.append(transform_product(row))
        if len(batch) >= BATCH:
            total += flush(session, Product, batch)
            log.info("products: %d", total)
    total += flush(session, Product, batch)
    return total


# --------------------------------------------------------------------------- #
# offers
# --------------------------------------------------------------------------- #
def transform_offer(row: Dict[str, str]) -> dict:
    raw_price = clean(row.get("price_toman"))
    price: Optional[int] = None
    if raw_price is not None:
        try:
            price = int(float(raw_price))
        except (ValueError, TypeError):
            price = None
    outlier = bool(price is not None and price > PRICE_OUTLIER_MAX)
    return {
        "offer_id": clean(row.get("offer_id")),
        "product_id": clean(row.get("product_id")),
        "shop_id": clean(row.get("shop_id")),
        "seller_title": clean(row.get("seller_title")),
        "description": clean(row.get("description")),
        "price_toman": price,
        "last_price_changed_at": as_dt_utc_naive(row.get("last_price_changed_at")),
        "warranty": clean(row.get("warranty")),
        "price_is_outlier": outlier,
    }


def import_offers(path: Path, session) -> int:
    total, batch = 0, []
    for row in rows(path):
        batch.append(transform_offer(row))
        if len(batch) >= BATCH:
            total += flush(session, Offer, batch)
            log.info("offers: %d", total)
    total += flush(session, Offer, batch)
    return total


# --------------------------------------------------------------------------- #
# پیش‌محاسبه آمار (در زیرفرایند، چون SQLite با UPDATE همبسته کند است)
# --------------------------------------------------------------------------- #
def precompute_product_stats(session) -> int:
    session.close()
    script = Path(__file__).resolve().parent / "precompute_stats.py"
    subprocess.run([sys.executable, str(script)], check=True)
    return 0


# --------------------------------------------------------------------------- #
# اعتبارسنجی
# --------------------------------------------------------------------------- #
def validate(session) -> Dict[str, Any]:
    count = lambda model, *where: session.scalar(  # noqa: E731
        select(func.count()).select_from(model).where(*where) if where
        else select(func.count()).select_from(model)
    ) or 0

    orphan_offers = session.scalar(
        select(func.count()).select_from(Offer)
        .outerjoin(Shop, Offer.shop_id == Shop.shop_id)
        .where(Shop.shop_id.is_(None))
    ) or 0

    return {
        "shops": count(Shop),
        "products": count(Product),
        "offers": count(Offer),
        "offers_with_price": count(Offer, Offer.price_toman.is_not(None)),
        "offers_price_outlier": count(Offer, Offer.price_is_outlier.is_(True)),
        "shops_with_coords": count(Shop, Shop.lat.is_not(None), Shop.lon.is_not(None)),
        "shops_with_offers": session.scalar(select(func.count(func.distinct(Offer.shop_id)))) or 0,
        "offers_orphaned": orphan_offers,
        "products_without_specs": count(Product, Product.specs_count == 0),
        "products_with_offers": count(Product, Product.offers_count > 0),
        "offers_without_price_change_ts": count(Offer, Offer.last_price_changed_at.is_(None)),
    }


def main() -> None:
    base = Path(os.getenv("DATASET_DIR", "/home/user/.cache/dataset"))
    paths = {
        "shops": Path(os.getenv("SHOPS_CSV", str(base / "shops.csv"))),
        "products": Path(os.getenv("PRODUCTS_CSV", str(base / "products.csv"))),
        "offers": Path(os.getenv("OFFERS_CSV", str(base / "offers.csv"))),
    }
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        log.error("فایل(های) دیتاست پیدا نشد: %s", ", ".join(missing))
        sys.exit(2)

    log.info("DATABASE_URL=%s", DATABASE_URL)
    Base.metadata.create_all(bind=engine)

    t0 = time.time()
    session = SessionLocal()
    try:
        n_s = import_shops(paths["shops"], session)
        n_p = import_products(paths["products"], session)
        n_o = import_offers(paths["offers"], session)

        log.info("precomputing product stats ...")
        precompute_product_stats(session)   # session را می‌بندد
        session = SessionLocal()

        report = validate(session)
        session.execute(
            insert(DatasetMeta),
            [{
                "dataset_name": os.getenv("DATASET_NAME", "starcoach-dataset-v16-cap300-csv"),
                "shops_count": report["shops"],
                "products_count": report["products"],
                "offers_count": report["offers"],
                "offers_with_price": report["offers_with_price"],
                "shops_with_coords": report["shops_with_coords"],
                "imported_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "source_note": (
                    "دیتاست CSV ترب (snapshot، نه داده زنده). قیمت‌ها لحظه‌ای نیستند و "
                    "وضعیت موجودی در دیتاست وجود ندارد."
                ),
            }],
        )
        session.commit()

        log.info("=" * 70)
        log.info("گزارش اعتبارسنجی:")
        for k, v in report.items():
            log.info("  %-32s %s", k, f"{v:,}" if isinstance(v, int) else v)
        log.info("رکوردهای خوانده‌شده: shops=%d products=%d offers=%d", n_s, n_p, n_o)
        log.info("زمان اجرا: %.1f ثانیه", time.time() - t0)
        log.info("=" * 70)
    finally:
        session.close()


if __name__ == "__main__":
    main()
