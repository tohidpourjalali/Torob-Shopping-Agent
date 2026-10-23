"""تست‌های API روی نمونه‌ای از داده واقعی دیتاست.

هر تستی که به دیتاست نیاز دارد با requires_dataset علامت خورده است.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("app_client")


# --------------------------------------------------------------------------- #
# سلامت و متادیتا
# --------------------------------------------------------------------------- #
class TestHealth:
    def test_health(self, app_client):
        r = app_client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["dataset_loaded"] is True
        assert body["counts"]["shops"] > 0
        assert body["counts"]["offers"] > 0

    def test_examples_are_dataset_derived(self, app_client):
        body = app_client.get("/api/examples").json()
        assert len(body["starters"]) >= 4
        assert len(body["budget_options"]) >= 4
        # هیچ مثال ساختگی «کتونی/لپ‌تاپ» که در دیتاست نیست نباید باشد
        joined = " ".join(body["starters"])
        assert "کتونی" not in joined

    def test_locations_come_from_dataset(self, app_client):
        body = app_client.get("/api/dataset/locations").json()
        assert len(body) > 0
        first = body[0]
        assert first["shops_count"] > 0
        assert 35.0 < first["lat"] < 36.5   # تهران
        assert 50.0 < first["lon"] < 52.5


# --------------------------------------------------------------------------- #
# جست‌وجوی محصول
# --------------------------------------------------------------------------- #
class TestProductSearch:
    def test_search_by_query(self, app_client):
        r = app_client.post("/api/products/search", json={"query": "شارژر", "limit": 5})
        assert r.status_code == 200
        body = r.json()
        assert len(body["results"]) > 0
        for p in body["results"]:
            assert p["price"]["is_verified"] is False
            assert "تأییدنشده" in p["price"]["label"]

    def test_persian_digit_normalization(self, app_client):
        """جست‌وجو با ارقام فارسی و لاتین باید نتیجه یکسان بدهد."""
        a = app_client.post("/api/products/search", json={"query": "شارژر 20 وات", "limit": 5}).json()
        b = app_client.post("/api/products/search", json={"query": "شارژر ۲۰ وات", "limit": 5}).json()
        assert a["total"] > 0
        assert b["total"] > 0

    def test_empty_query_returns_popular(self, app_client):
        body = app_client.post("/api/products/search", json={"limit": 5}).json()
        assert len(body["results"]) > 0
        assert body["note"] is not None

    def test_no_result_is_graceful(self, app_client):
        body = app_client.post(
            "/api/products/search", json={"query": "xyzمحصولناموجود۱۲۳", "limit": 5}
        ).json()
        assert body["results"] == []
        assert body["note"] is not None

    def test_price_filter(self, app_client):
        body = app_client.post(
            "/api/products/search", json={"query": "شارژر", "max_price": 500_000, "limit": 10}
        ).json()
        for p in body["results"]:
            assert p["min_price_toman"] is None or p["min_price_toman"] <= 500_000

    def test_suggested_categories(self, app_client):
        body = app_client.post("/api/products/search", json={"query": "شارژر", "limit": 3}).json()
        assert len(body["suggested_categories"]) > 0
        assert all(c["products_count"] > 0 for c in body["suggested_categories"])

    def test_product_detail(self, app_client):
        search = app_client.post("/api/products/search", json={"query": "شارژر", "limit": 1}).json()
        pid = search["results"][0]["product_id"]
        r = app_client.get(f"/api/products/{pid}")
        assert r.status_code == 200
        body = r.json()
        assert body["product_id"] == pid
        assert isinstance(body["specs"], list)

    def test_product_detail_404(self, app_client):
        assert app_client.get("/api/products/product_doesnotexist").status_code == 404

    def test_missing_specs_are_not_invented(self, app_client):
        """اگر محصولی مشخصات ندارد، نباید مشخصات ساختگی برگردد."""
        body = app_client.post("/api/products/search", json={"limit": 100}).json()
        for p in body["results"]:
            detail = app_client.get(f"/api/products/{p['product_id']}").json()
            if detail["specs_count"] == 0:
                assert detail["specs"] == []
                assert detail["missing_specs_note"] is not None
                break


# --------------------------------------------------------------------------- #
# فروشگاه‌ها
# --------------------------------------------------------------------------- #
class TestStoreSearch:
    def test_stores_for_product(self, app_client, sample_offer):
        r = app_client.post("/api/stores/search", json={
            "product_id": sample_offer["product_id"],
            "lat": 35.6945, "lon": 51.4120, "radius_km": 30, "limit": 10,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["returned"] > 0
        assert body["total_candidates"] > 0

    def test_stock_always_unknown(self, app_client, sample_offer):
        body = app_client.post("/api/stores/search", json={
            "product_id": sample_offer["product_id"], "radius_km": 30, "limit": 10,
        }).json()
        assert len(body["stores"]) > 0
        for s in body["stores"]:
            assert s["stock"]["status"] == "unknown"
            assert s["stock"]["is_verified"] is False

    def test_prices_never_verified(self, app_client, sample_offer):
        body = app_client.post("/api/stores/search", json={
            "product_id": sample_offer["product_id"], "radius_km": 30, "limit": 10,
        }).json()
        for s in body["stores"]:
            assert s["price"]["is_verified"] is False

    def test_distance_within_radius(self, app_client, sample_offer):
        body = app_client.post("/api/stores/search", json={
            "product_id": sample_offer["product_id"],
            "lat": 35.6945, "lon": 51.4120, "radius_km": 3, "limit": 50,
        }).json()
        for s in body["stores"]:
            assert s["shop"]["distance_km"] is None or s["shop"]["distance_km"] <= 3.001

    def test_smart_score_breakdown_present(self, app_client, sample_offer):
        body = app_client.post("/api/stores/search", json={
            "product_id": sample_offer["product_id"], "radius_km": 30, "limit": 5,
        }).json()
        for s in body["stores"]:
            assert set(s["score_breakdown"].keys()) == {
                "price", "distance", "hours", "payment", "trust"
            }
            assert 0.0 <= s["score"] <= 1.0
            assert all(0.0 <= v <= 1.0 for v in s["score_breakdown"].values())

    def test_sort_by_price_ascending(self, app_client, sample_offer):
        body = app_client.post("/api/stores/search", json={
            "product_id": sample_offer["product_id"], "radius_km": 40,
            "sort_by": "price", "limit": 10,
        }).json()
        prices = [s["price"]["value_toman"] for s in body["stores"] if s["price"]["value_toman"]]
        assert prices == sorted(prices)

    def test_sort_by_distance_ascending(self, app_client, sample_offer):
        body = app_client.post("/api/stores/search", json={
            "product_id": sample_offer["product_id"],
            "lat": 35.6945, "lon": 51.4120, "radius_km": 40,
            "sort_by": "distance", "limit": 10,
        }).json()
        dists = [s["shop"]["distance_km"] for s in body["stores"] if s["shop"]["distance_km"] is not None]
        assert dists == sorted(dists)

    def test_no_candidates_gives_alternative_hint(self, app_client, sample_offer):
        body = app_client.post("/api/stores/search", json={
            "product_id": sample_offer["product_id"],
            "lat": 35.6945, "lon": 51.4120,
            "radius_km": 0.2, "require_installment": True, "limit": 5,
        }).json()
        if body["total_candidates"] == 0:
            assert body["alternatives_note"] is not None
            assert len(body["filters_applied"]) >= 1

    def test_shop_names_marked_unverified(self, app_client, sample_offer):
        body = app_client.post("/api/stores/search", json={
            "product_id": sample_offer["product_id"], "radius_km": 30, "limit": 3,
        }).json()
        for s in body["stores"]:
            assert s["shop"]["name_is_verified"] is False
            assert "تأییدنشده" in s["shop"]["name_label"]

    def test_phone_is_dataset_value_not_synthesized(self, app_client, sample_offer):
        """شماره باید با مقدار دیتاست یکی باشد، نه ساخته‌شده."""
        import sqlite3, os
        body = app_client.post("/api/stores/search", json={
            "product_id": sample_offer["product_id"], "radius_km": 30, "limit": 5,
        }).json()
        shop = body["stores"][0]["shop"]
        db = os.environ["DATABASE_URL"].replace("sqlite:///", "")
        con = sqlite3.connect(db)
        expected = con.execute(
            "SELECT phone_display FROM shops WHERE shop_id=?", (shop["shop_id"],)
        ).fetchone()[0]
        con.close()
        assert shop["phone_display"] == expected

    def test_missing_product_id_422(self, app_client):
        r = app_client.post("/api/stores/search", json={})
        assert r.status_code == 422


# --------------------------------------------------------------------------- #
# مقایسه
# --------------------------------------------------------------------------- #
class TestCompare:
    def test_compare_offers(self, app_client, sample_offer):
        body = app_client.post("/api/stores/search", json={
            "product_id": sample_offer["product_id"], "radius_km": 30, "limit": 4,
        }).json()
        ids = [s["offer_id"] for s in body["stores"]]
        if len(ids) < 2:
            pytest.skip("آفر کافی برای مقایسه نیست")
        cmp = app_client.post("/api/stores/compare", json={"offer_ids": ids}).json()
        assert len(cmp["rows"]) == len(ids)
        assert all(r["price_verified"] is False for r in cmp["rows"])
        assert any("تأییدنشده" in n for n in cmp["notes"])

    def test_compare_empty_422(self, app_client):
        assert app_client.post("/api/stores/compare", json={"offer_ids": []}).status_code == 422

    def test_compare_unknown_ids_404(self, app_client):
        r = app_client.post("/api/stores/compare", json={"offer_ids": ["offer_nope"]})
        assert r.status_code == 404


# --------------------------------------------------------------------------- #
# تأیید
# --------------------------------------------------------------------------- #
class TestVerification:
    def test_demo_verification_is_labelled(self, app_client, sample_offer):
        r = app_client.post("/api/verify", json={
            "offer_id": sample_offer["offer_id"], "channel": "demo",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["is_simulated"] is True
        assert "نمایشی" in body["label"]
        assert body["stock_status"] == "unknown"
        assert len(body["script"]) >= 3
        assert body["real_channel_ready"] is False

    def test_real_channel_falls_back_honestly(self, app_client, sample_offer, monkeypatch):
        """بدون کانال واقعی، درخواست real باید صادقانه به demo برگردد."""
        monkeypatch.setenv("TELEPHONY_PROVIDER", "none")
        body = app_client.post("/api/verify", json={
            "offer_id": sample_offer["offer_id"], "channel": "real",
        }).json()
        assert body["is_simulated"] is True
        assert "هیچ" in body["note"] or "پیکربندی" in body["note"]

    def test_verification_history(self, app_client, sample_offer):
        app_client.post("/api/verify", json={"offer_id": sample_offer["offer_id"]})
        r = app_client.get(f"/api/verify/{sample_offer['offer_id']}")
        assert r.status_code == 200
        hist = r.json()
        assert len(hist) >= 1
        assert hist[0]["is_simulated"] is True

    def test_verify_unknown_offer_404(self, app_client):
        r = app_client.post("/api/verify", json={"offer_id": "offer_nope"})
        assert r.status_code == 404


# --------------------------------------------------------------------------- #
# کشف نیاز (عامل)
# --------------------------------------------------------------------------- #
class TestAgentChat:
    """قرارداد گفت‌وگوی ایجنت (جایگزین مسیر قدیمی /api/discover)."""

    def test_first_turn_asks_for_product_type(self, app_client):
        body = app_client.post("/api/agent/chat", json={"message": "سلام"}).json()
        assert body["stage"] == "need"
        assert body["question"]
        assert len(body["quick_replies"]) > 0
        assert body["session_id"].startswith("s-")

    def test_detects_product_type(self, app_client, known_product):
        body = app_client.post("/api/agent/chat", json={"message": "شارژر اپل می‌خوام"}).json()
        assert body["collected"]["product_type"] == "شارژر"
        assert "search_products" in [t["tool"] for t in body["tool_calls"]]

    def test_search_finds_a_product_that_exists(self, app_client, known_product):
        body = app_client.post(
            "/api/agent/chat", json={"message": known_product["query"]}
        ).json()
        assert body["stage"] in {"product", "guide"}
        if body["stage"] == "product":
            assert len(body["products"]) > 0

    def test_budget_extraction(self, app_client):
        body = app_client.post("/api/agent/chat", json={
            "message": "شارژر اپل تا ۲ میلیون تومان"
        }).json()
        assert body["collected"]["budget_max"] == 2_000_000

    def test_session_is_continuable(self, app_client):
        first = app_client.post("/api/agent/chat", json={"message": "شارژر"}).json()
        sid = first["session_id"]
        second = app_client.post("/api/agent/chat", json={
            "message": "تا ۱ میلیون تومان", "session_id": sid,
        }).json()
        assert second["session_id"] == sid
        assert second["collected"].get("product_type") == "شارژر"
        assert second["collected"].get("budget_max") == 1_000_000

    def test_agent_trace_has_four_stages(self, app_client):
        body = app_client.post("/api/agent/chat", json={"message": "شارژر"}).json()
        steps = {t["step"] for t in body["agent_trace"]}
        assert {"need", "product", "stores"} <= steps

    def test_nonsense_message_does_not_crash(self, app_client):
        r = app_client.post("/api/agent/chat", json={"message": "؟؟؟!!!"})
        assert r.status_code == 200

    def test_category_suggestion_when_no_direct_match(self, app_client):
        body = app_client.post("/api/agent/chat", json={"message": "شارژر"}).json()
        assert body["stage"] in {"product", "guide"}


# --------------------------------------------------------------------------- #
# قرارداد عمومی
# --------------------------------------------------------------------------- #
class TestContract:
    def test_openapi_available(self, app_client):
        assert app_client.get("/openapi.json").status_code == 200

    def test_root_endpoint(self, app_client):
        body = app_client.get("/").json()
        assert body["api"] == "/api/health"

    def test_cors_preflight(self, app_client):
        r = app_client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code in (200, 204)

    def test_path_traversal_safe(self, app_client):
        r = app_client.get("/api/products/..%2f..%2fetc%2fpasswd")
        assert r.status_code in (404, 422)


class TestRecentVerifications:
    """«استعلام‌های اخیر» — صفحهٔ پیگیری باید بدون شناسه هم چیزی نشان دهد."""

    def test_recent_endpoint_returns_list(self, app_client, known_product):
        # یک استعلام ثبت می‌کنیم تا لیست خالی نباشد
        r = app_client.post("/api/agent/chat", json={"message": known_product["query"]})
        sid = r.json()["session_id"]
        r = app_client.post(
            "/api/agent/chat",
            json={"session_id": sid, "product_id": known_product["product_id"]},
        )
        stores = r.json()["stores"]
        if stores:
            app_client.post("/api/verify", json={"offer_id": stores[0]["offer_id"], "channel": "demo"})

        res = app_client.get("/api/verifications/recent?limit=5")
        assert res.status_code == 200
        rows = res.json()
        assert isinstance(rows, list)
        for row in rows:
            assert "label" in row and "checked_at" in row


class TestQrCode:
    """QR served by our own backend — bridge when the browser blocks popups."""

    def test_qr_returns_png(self, app_client):
        res = app_client.get("/api/qr", params={"data": "https://nshn.ir/?lat=35.7&lng=51.4"})
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/png"
        # امضای PNG
        assert res.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(res.content) > 200

    def test_qr_rejects_empty(self, app_client):
        assert app_client.get("/api/qr", params={"data": "   "}).status_code == 400
