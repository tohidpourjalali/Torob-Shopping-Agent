"""پیش‌محاسبه آمار آفرها روی جدول products.

این مرحله در SQLite با UPDATE همبسته بسیار کند است؛ بنابراین یک‌بار از روی
جدول offers می‌خوانیم و با executemany به‌روزرسانی دسته‌ای انجام می‌دهیم.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db.database import SessionLocal


def main() -> None:
    session = SessionLocal()
    try:
        session.execute(text(
            "UPDATE products SET shops_count=0, offers_count=0, "
            "min_price_toman=NULL, max_price_toman=NULL, min_price_offer_id=NULL"
        ))
        session.commit()

        print("scanning offers ...", flush=True)
        stats: dict[str, list] = {}
        rows = session.execute(text(
            "SELECT product_id, shop_id, price_toman, price_is_outlier FROM offers"
        ))
        for product_id, shop_id, price, outlier in rows:
            s = stats.get(product_id)
            if s is None:
                # [n_offers, set(shop), min_price, max_price, min_offer_id]
                s = stats[product_id] = [0, set(), None, None, None]
            s[0] += 1
            s[1].add(shop_id)
            if price is not None and not outlier:
                if s[2] is None or price < s[2]:
                    s[2] = price
                if s[3] is None or price > s[3]:
                    s[3] = price

        # شناسه ارزان‌ترین آفر (در صورت تساوی، کوچک‌ترین offer_id)
        print("resolving cheapest offers ...", flush=True)
        for offer_id, product_id, price in session.execute(text(
            "SELECT offer_id, product_id, price_toman FROM offers "
            # `price_is_outlier = FALSE` در SQLite و PostgreSQL هر دو کار می‌کند؛
            # نوشتن `=0` فقط در SQLite معتبر بود و روی PG خطا می‌داد.
            "WHERE price_toman IS NOT NULL AND price_is_outlier = FALSE"
        )):
            s = stats.get(product_id)
            if s and s[2] is not None and price == s[2]:
                if s[4] is None or offer_id < s[4]:
                    s[4] = offer_id

        print(f"updating {len(stats):,} products ...", flush=True)
        payload = [
            {
                "pid": pid,
                "n_offers": v[0],
                "n_shops": len(v[1]),
                "mn": v[2],
                "mx": v[3],
                "mid": v[4],
            }
            for pid, v in stats.items()
        ]
        for i in range(0, len(payload), 20000):
            session.execute(
                text(
                    "UPDATE products SET offers_count=:n_offers, shops_count=:n_shops, "
                    "min_price_toman=:mn, max_price_toman=:mx, min_price_offer_id=:mid "
                    "WHERE product_id=:pid"
                ),
                payload[i:i + 20000],
            )
            session.commit()
            print(f"  {min(i + 20000, len(payload)):,}", flush=True)

        print("done", flush=True)
    finally:
        session.close()


if __name__ == "__main__":
    main()
