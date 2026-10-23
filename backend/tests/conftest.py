"""تنظیمات pytest: یک دیتابیس کوچک نمونه از داده واقعی دیتاست ساخته می‌شود.

چرا نمونه کوچک: اجرای تست‌ها نباید به دیتابیس ۴۰۰ مگابایتی وابسته باشد.
اما ساختار/مقادیر کاملاً از دیتاست واقعی گرفته می‌شود (نه داده ساختگی).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

DATASET_DIR = Path(os.getenv("DATASET_DIR", "/home/user/.cache/dataset"))


def _dataset_available() -> bool:
    return all(
        (DATASET_DIR / f).exists() for f in ("shops.csv", "products.csv", "offers.csv")
    )


requires_dataset = pytest.mark.skipif(
    not _dataset_available(),
    reason="دیتاست CSV در دسترس نیست (DATASET_DIR را تنظیم کنید)",
)


@pytest.fixture(scope="session")
def db_path(tmp_path_factory) -> str:
    """دیتابیس نمونه با ۴۰۰ فروشگاه/۲۰۰۰ محصول/۵۰۰۰ آفر از داده واقعی."""
    if not _dataset_available():
        pytest.skip("دیتاست در دسترس نیست")

    import csv
    import json
    import sqlite3

    path = tmp_path_factory.mktemp("db") / "test.db"
    csv.field_size_limit(10 ** 9)

    # انتخاب نمونه‌ای که شامل محصولات دارای آفر واقعی باشد
    with open(DATASET_DIR / "offers.csv", encoding="utf-8-sig", newline="") as f:
        offers = [r for _, r in zip(range(6000), csv.DictReader(f))]

    product_ids = {o["product_id"] for o in offers}
    shop_ids = {o["shop_id"] for o in offers}

    shops, products = [], []
    with open(DATASET_DIR / "shops.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["shop_id"] in shop_ids:
                shops.append(r)
    with open(DATASET_DIR / "products.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["product_id"] in product_ids:
                products.append(r)

    # ساخت دیتابیس با همان importer پروژه (تست خود importer هم هست)
    from sqlalchemy import create_engine, insert
    from sqlalchemy.orm import sessionmaker

    from app.db.database import Base
    from app.db.models import Offer, Product, Shop

    url = f"sqlite:///{path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()

    sys.path.insert(0, str(BACKEND / "scripts"))
    import import_csv as imp

    s.execute(insert(Shop), [imp.transform_shop(r) for r in shops])
    s.execute(insert(Product), [imp.transform_product(r) for r in products])
    s.execute(insert(Offer), [imp.transform_offer(r) for r in offers])
    s.commit()

    # آمار پیش‌محاسبه‌شده (نسخه ساده درون‌خطی تا به subprocess نیاز نباشد)
    rows = s.execute(
        __import__("sqlalchemy").text(
            "SELECT product_id, COUNT(*), COUNT(DISTINCT shop_id), "
            "MIN(CASE WHEN price_toman IS NOT NULL AND price_is_outlier=0 THEN price_toman END), "
            "MAX(CASE WHEN price_toman IS NOT NULL AND price_is_outlier=0 THEN price_toman END) "
            "FROM offers GROUP BY product_id"
        )
    ).all()
    for pid, n, nshops, mn, mx in rows:
        s.execute(
            __import__("sqlalchemy").text(
                "UPDATE products SET offers_count=:n, shops_count=:ns, "
                "min_price_toman=:mn, max_price_toman=:mx WHERE product_id=:p"
            ),
            {"n": n, "ns": nshops, "mn": mn, "mx": mx, "p": pid},
        )
    s.commit()
    s.close()
    engine.dispose()

    return url


@pytest.fixture(scope="session")
def app_client(db_path):
    """TestClient با دیتابیس نمونه."""
    import importlib

    os.environ["DATABASE_URL"] = db_path
    # ماژول‌های db/app باید بعد از تنظیم env بازخوانی شوند
    for mod in [m for m in list(sys.modules) if m.startswith("app.")]:
        del sys.modules[mod]

    from fastapi.testclient import TestClient

    main = importlib.import_module("app.main")
    with TestClient(main.app) as client:
        yield client


@pytest.fixture(scope="session")
def sample_offer(app_client):
    """یک آفر واقعی از دیتابیس نمونه."""
    import sqlite3

    db = os.environ["DATABASE_URL"].replace("sqlite:///", "")
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT o.offer_id, o.product_id, o.shop_id FROM offers o "
        "WHERE o.price_toman IS NOT NULL AND o.price_is_outlier=0 "
        "AND o.product_id IN (SELECT product_id FROM products WHERE shops_count > 2) "
        "LIMIT 1"
    ).fetchone()
    con.close()
    assert row, "آفر نمونه پیدا نشد"
    return {"offer_id": row[0], "product_id": row[1], "shop_id": row[2]}


@pytest.fixture(scope="session")
def known_product(app_client):
    """یک محصول واقعی از دیتابیس نمونه + واژه‌ای از عنوانش برای جست‌وجو.

    چرا لازم است: دیتابیس تست فقط نمونه‌ای از داده است؛ عبارتی مثل «شارژر اپل»
    ممکن است در آن نباشد. تست‌ها باید با داده‌ای کار کنند که واقعاً وجود دارد.
    """
    import sqlite3

    db = os.environ["DATABASE_URL"].replace("sqlite:///", "")
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT product_id, persian_title, shops_count FROM products "
        "WHERE shops_count > 1 AND persian_title IS NOT NULL "
        "ORDER BY shops_count DESC LIMIT 1"
    ).fetchone()
    con.close()
    assert row, "محصول نمونه پیدا نشد"
    title = row[1]
    return {
        "product_id": row[0],
        "title": title,
        "query": title.split()[0],
        "shops_count": row[2],
    }
