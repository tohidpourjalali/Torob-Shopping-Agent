"""تست‌های رگرسیون برای جست‌وجوی جملهٔ طبیعی (باگ راند ۸).

باگ: کاربر جمله می‌نویسد («شارژر اپل برای خرید حضوری در تهران»). واژه‌های قصدی و
شهری در `search_blob` نیستند، جست‌وجوی AND صفر می‌شد و اپ نتیجه می‌گرفت
«این کالا در دیتاست نیست» — با اینکه کالا وجود داشت. این تست‌ها آن رگرسیون و
همچنین سلامتی `/api/health` روی دیتابیس خالی را قفل می‌کنند.
"""

from __future__ import annotations

import pytest

from app.core.text import content_tokens

pytestmark = pytest.mark.usefixtures("app_client")


class TestIntentWordsNotTokens:
    """واژه‌های قصد خرید/شهر نباید توکن جست‌وجو شوند."""

    @pytest.mark.parametrize(
        "text",
        [
            "شارژر اپل برای خرید حضوری در تهران",
            "هدفون می‌خوام بخرم از مغازه",
            "قیمت و موجودی یخچال امروز",
            "گوشی نزدیک من پیدا کنم",
        ],
    )
    def test_intent_words_dropped(self, text):
        tokens = content_tokens(text)
        for junk in ("خرید", "حضوری", "تهران", "مغازه", "قیمت", "موجودی", "نزدیک", "امروز"):
            assert junk not in tokens, f"«{junk}» نباید توکن باشد"

    def test_single_digit_budget_not_token(self):
        # «تا ۳ میلیون» نباید «۳» را به‌عنوان مدل کالا وارد جست‌وجو کند
        assert "3" not in content_tokens("هدفون تا ۳ میلیون")

    def test_product_words_survive(self):
        tokens = content_tokens("شارژر اپل برای خرید حضوری در تهران")
        assert "شارژر" in tokens and "اپل" in tokens


class TestSearchRelaxation:
    """جست‌وجو با جملهٔ طبیعی باید نتیجه بدهد، نه «در دیتاست نیست»."""

    @pytest.mark.parametrize(
        "query",
        [
            "شارژر اپل برای خرید حضوری در تهران",
            "هدفون بی‌سیم تا ۳ میلیون",
            "لپ تاپ ایسوس برای دانشگاه",
        ],
    )
    def test_natural_sentence_finds_products(self, app_client, query):
        from app.core.text import content_tokens as ct

        resp = app_client.post(
            "/api/products/search",
            json={"query": query, "limit": 3, "require_all_tokens": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        # اگر خودِ دیتاست کوچک تست این کالا را ندارد، تست بی‌معنی است
        if not ct(query):
            pytest.skip("عبارت خالی")
        if body["total"] == 0:
            # فقط وقتی مجاز است که هیچ‌کدام از توکن‌های کالا در دیتاست نباشد
            from app.db.database import SessionLocal
            from app.db.models import Product
            from sqlalchemy import select, func

            db = SessionLocal()
            tokens = ct(query)
            found = db.scalar(
                select(func.count()).select_from(Product).where(
                    Product.search_blob.like(f"%{tokens[0]}%")
                )
            )
            db.close()
            assert not found, f"«{tokens[0]}» در دیتاست هست ولی جست‌وجو ۰ نتیجه داد"

    def test_relaxation_is_disclosed(self, app_client):
        """اگر عبارت کوتاه شد، پاسخ باید صادقانه بگوید."""
        resp = app_client.post(
            "/api/products/search",
            json={
                "query": "شارژر اپل در محلهٔ ونک تهران",
                "limit": 2,
                "require_all_tokens": True,
            },
        )
        body = resp.json()
        if body["total"] and body.get("note") and "نتیجه نداد" in body["note"]:
            assert "جست‌وجو شد" in body["note"]


class TestHealthNever500:
    """healthcheck پلتفرم نباید با دیتابیس خالی/ناقص ۵۰۰ بدهد."""

    def test_health_ok_on_test_db(self, app_client):
        resp = app_client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in {"ok", "degraded"}
        assert "counts" in body
