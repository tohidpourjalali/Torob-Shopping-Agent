"""تست‌های ایجنت — حلقهٔ ابزارمحور، مسیر قطعی و مسیر مدل.

این تست‌ها روی **داده واقعی** (نمونهٔ conftest) اجرا می‌شوند و ادعاهای کلیدی
محصول را قفل می‌کنند:
  * ایجنت واقعاً ابزار صدا می‌زند (نه متن آماده).
  * برای کالای بیرون از دیتاست، فروشگاه/قیمت نمی‌سازد ولی کاربر را دست‌خالی
    هم نمی‌گذارد.
  * مسیر LLM با tool calling کار می‌کند و اگر مدل خطا داد، به مسیر قطعی می‌افتد.
"""

from __future__ import annotations

import pytest

from tests.conftest import requires_dataset

pytestmark = requires_dataset


# --------------------------------------------------------------------------- #
# ابزارها
# --------------------------------------------------------------------------- #
class TestToolRegistry:
    def test_every_schema_has_implementation(self):
        from app.agent.tools import IMPLEMENTATIONS, TOOL_SCHEMAS

        names = {t["function"]["name"] for t in TOOL_SCHEMAS}
        assert names == set(IMPLEMENTATIONS), "طرح‌واره و پیاده‌سازی ناهم‌خوان"

    def test_unknown_tool_does_not_raise(self, app_client):
        from app.agent.tools import ToolContext, run_tool
        from app.db.database import SessionLocal

        db = SessionLocal()
        try:
            res = run_tool(ToolContext(db, {}, {}), "nonexistent_tool", {})
            assert res.ok is False
            assert "ناشناخته" in res.summary
        finally:
            db.close()

    def test_bad_arguments_are_caught(self, app_client):
        from app.agent.tools import ToolContext, run_tool
        from app.db.database import SessionLocal

        db = SessionLocal()
        try:
            res = run_tool(ToolContext(db, {}, {}), "find_stores", {"nonsense": 1})
            assert res.ok is False
        finally:
            db.close()


# --------------------------------------------------------------------------- #
# موقعیت
# --------------------------------------------------------------------------- #
class TestLocation:
    def test_gps_label_comes_from_dataset(self, app_client):
        from app.agent.tools import ToolContext, run_tool
        from app.db.database import SessionLocal

        db = SessionLocal()
        try:
            ctx = ToolContext(db, {}, {})
            res = run_tool(ctx, "set_location", {"lat": 35.7320, "lon": 51.4200})
            assert res.ok
            loc = ctx.facts["location"]
            assert loc["source"] == "geolocation"
            # برچسب باید از محله‌های واقعی دیتاست باشد، نه ساختگی
            assert "نزدیک" in loc["label"] or loc["label"] == "موقعیت فعلی شما"
            assert loc["nearest_area_km"] is not None
        finally:
            db.close()

    def test_one_row_per_shop(self, app_client, known_product):
        """یک فروشگاه با چند آفر نباید چند بار در فهرست بیاید."""
        r = app_client.post("/api/agent/chat", json={"message": known_product["query"]})
        sid = r.json()["session_id"]
        r = app_client.post(
            "/api/agent/chat",
            json={"session_id": sid, "product_id": known_product["product_id"]},
        )
        shops = [s["shop"]["shop_id"] for s in r.json()["stores"]]
        assert len(shops) == len(set(shops))

    def test_coordinates_win_over_derived_label(self, app_client):
        """برچسب مشتق‌شدهٔ «نزدیک X» نباید جای مختصات را بگیرد (باگی که رفع شد)."""
        from app.agent.tools import ToolContext, run_tool
        from app.db.database import SessionLocal

        db = SessionLocal()
        try:
            ctx = ToolContext(db, {}, {})
            res = run_tool(
                ctx,
                "set_location",
                {"lat": 35.6945, "lon": 51.412, "label": "نزدیک شیخ هادی"},
            )
            assert res.ok is True
            assert ctx.facts["location"]["source"] == "geolocation"
            assert ctx.facts["location"]["lat"] == 35.6945
        finally:
            db.close()

    def test_unknown_area_is_labelled_honestly(self, app_client):
        from app.agent.tools import ToolContext, run_tool
        from app.db.database import SessionLocal

        db = SessionLocal()
        try:
            ctx = ToolContext(db, {}, {})
            # مختصات دور از تهران
            res = run_tool(ctx, "set_location", {"lat": 32.65, "lon": 51.67})
            assert res.ok
            assert ctx.facts["location"]["label"] == "موقعیت فعلی شما"
        finally:
            db.close()


# --------------------------------------------------------------------------- #
# حلقهٔ قطعی
# --------------------------------------------------------------------------- #
class TestDeterministicLoop:
    def test_first_turn_asks_what_to_buy(self, app_client):
        r = app_client.post("/api/agent/chat", json={"message": ""})
        assert r.status_code == 200
        body = r.json()
        assert body["stage"] == "need"
        assert body["question"]
        assert body["reasoning_engine"] == "deterministic"
        assert body["llm_enabled"] is False

    def test_product_search_runs_a_real_tool(self, app_client, known_product):
        r = app_client.post("/api/agent/chat", json={"message": known_product["query"]}).json()
        assert "search_products" in [t["tool"] for t in r["tool_calls"]]
        assert r["stage"] == "product"
        assert len(r["products"]) > 0

    def test_product_selection_by_id_reaches_guide(self, app_client, known_product):
        first = app_client.post(
            "/api/agent/chat", json={"product_id": known_product["product_id"], "message": ""}
        ).json()
        assert first["stage"] == "guide"
        assert first["guide"] is not None
        assert "build_purchase_guide" in [t["tool"] for t in first["tool_calls"]]

    def test_full_flow_reaches_purchase_guide(self, app_client, known_product):
        first = app_client.post("/api/agent/chat", json={"message": known_product["query"]}).json()
        sid = first["session_id"]
        second = app_client.post("/api/agent/chat", json={"session_id": sid, "message": "تا ۵۰ میلیون"}).json()
        pid = second["products"][0]["product_id"]

        third = app_client.post("/api/agent/chat", json={"session_id": sid, "message": pid}).json()
        tools = [t["tool"] for t in third["tool_calls"]]
        assert "find_stores" in tools
        assert "build_purchase_guide" in tools
        assert third["stage"] == "guide"
        assert third["guide"] is not None
        assert len(third["guide"]["steps"]) >= 4

    def test_guide_steps_are_labeled_by_source(self, app_client, known_product):
        first = app_client.post("/api/agent/chat", json={"message": known_product["query"]}).json()
        sid = first["session_id"]
        pid = first["products"][0]["product_id"]
        r = app_client.post("/api/agent/chat", json={"session_id": sid, "message": pid}).json()
        sources = {s["source"] for s in r["guide"]["steps"]}
        assert sources <= {"dataset", "guide"}
        assert "guide" in sources, "گام‌های راهنمای عمومی باید برچسب guide داشته باشند"

    def test_session_continues_across_turns(self, app_client):
        first = app_client.post("/api/agent/chat", json={"message": "هدفون"}).json()
        second = app_client.post(
            "/api/agent/chat", json={"session_id": first["session_id"], "message": "تا ۳ میلیون"}
        ).json()
        assert second["session_id"] == first["session_id"]
        assert second["collected"].get("budget_max") == 3_000_000

    def test_geolocation_travels_with_the_request(self, app_client, known_product):
        r = app_client.post(
            "/api/agent/chat",
            json={"message": known_product["query"], "lat": 35.70, "lon": 51.40},
        ).json()
        assert "set_location" in [t["tool"] for t in r["tool_calls"]]
        assert r["collected"]["location"]["source"] == "geolocation"


# --------------------------------------------------------------------------- #
# کالای بیرون از دیتاست
# --------------------------------------------------------------------------- #
class TestOutOfCatalog:
    def test_unknown_item_still_gets_a_purchase_guide(self, app_client):
        r = app_client.post("/api/agent/chat", json={"message": "بلیط هواپیما"}).json()
        assert r["stage"] == "guide"
        assert r["guide"]["dataset_status"] == "not_in_dataset"
        assert len(r["guide"]["steps"]) >= 5

    def test_no_fabricated_shop_for_unknown_item(self, app_client):
        r = app_client.post("/api/agent/chat", json={"message": "بلیط هواپیما"}).json()
        assert r["guide"]["shop"] is None
        assert r["guide"]["offer_id"] is None
        assert r["stores"] == []
        assert r["products"] == []

    def test_guide_says_it_is_not_dataset(self, app_client):
        r = app_client.post("/api/agent/chat", json={"message": "بلیط هواپیما"}).json()
        joined = " ".join(r["guide"]["transparency"])
        assert "دیتاست" in joined

    def test_generic_head_word_is_not_matched(self, app_client):
        """«دستگاه ام‌آر‌آی» نباید دستگاه تست قند خون برگرداند."""
        r = app_client.post("/api/agent/chat", json={"message": "دستگاه ام‌آر‌آی"}).json()
        titles = " ".join(p["persian_title"] for p in r["products"])
        assert "قند خون" not in titles


# --------------------------------------------------------------------------- #
# مسیر مدل زبانی (با مدل جعلی — بدون کلید و بدون شبکه)
# --------------------------------------------------------------------------- #
class FakeModel:
    def __init__(self, script):
        self.script = list(script)
        self.seen_tool_result = False

    def complete(self, system, messages, tools):
        from app.agent.llm import AssistantTurn, ToolCall

        if any(m.get("role") == "tool" for m in messages):
            self.seen_tool_result = True
            return AssistantTurn(content="نتیجه را دیدم؛ راهنما آماده است.")
        if self.script:
            name, args = self.script.pop(0)
            return AssistantTurn(tool_calls=[ToolCall(id=f"c{len(self.script)}", name=name, arguments=args)])
        return AssistantTurn(content="تمام شد.")


class TestLLMLoop:
    def test_model_can_call_a_tool_and_read_the_result(self, app_client):
        from app.agent.loop import AgentRuntime
        from app.db.database import SessionLocal
        from app.schemas import AgentChatRequest

        from tests.conftest import DATASET_DIR  # noqa: F401
        fake = FakeModel([("search_products", {"query": "شارژر", "limit": 3})])
        db = SessionLocal()
        try:
            out = AgentRuntime(db, model=fake).chat(AgentChatRequest(message="شارژر اپل"))
        finally:
            db.close()
        assert out.reasoning_engine == "llm"
        assert out.tool_calls[0].tool == "search_products"
        assert out.tool_calls[0].ok is True
        assert fake.seen_tool_result, "مدل باید نتیجهٔ ابزار را دیده باشد"

    def test_model_failure_falls_back_to_deterministic(self, app_client):
        from app.agent.llm import LLMError
        from app.agent.loop import AgentRuntime
        from app.db.database import SessionLocal
        from app.schemas import AgentChatRequest

        class BrokenModel:
            def complete(self, system, messages, tools):
                raise LLMError("سهمیه تمام شد")

        db = SessionLocal()
        try:
            out = AgentRuntime(db, model=BrokenModel()).chat(AgentChatRequest(message="شارژر اپل"))
        finally:
            db.close()
        assert out.reasoning_engine == "deterministic"
        assert "برنامه‌ریز قطعی" in out.reply or "برنامه‌ریز قطعی" in out.model_label or "پاسخ نداد" in out.reply
        assert out.products, "بعد از خطای مدل باید مسیر قطعی جواب بدهد"

    def test_capabilities_lists_tools_and_model_state(self, app_client):
        r = app_client.get("/api/agent/capabilities")
        assert r.status_code == 200
        body = r.json()
        names = {t["name"] for t in body["tools"]}
        assert {"search_products", "find_stores", "build_purchase_guide"} <= names
        assert body["llm_enabled"] in (True, False)
        assert body["note"]


# --------------------------------------------------------------------------- #
# شفافیت
# --------------------------------------------------------------------------- #
class TestTransparency:
    def test_prices_are_marked_unverified(self, app_client, known_product):
        first = app_client.post("/api/agent/chat", json={"message": known_product["query"]}).json()
        pid = first["products"][0]["product_id"]
        r = app_client.post(
            "/api/agent/chat", json={"session_id": first["session_id"], "message": pid}
        ).json()
        for store in r["stores"]:
            assert store["price"]["is_verified"] is False
            # قیمت هرگز «تأییدشده» نیست؛ یا تأییدنشده است یا نامشخص (اگر قیمت ثبت نشده)
            assert store["price"]["verification_status"] in {"not_confirmed", "unknown"}

    def test_notes_mention_snapshot_when_stores_present(self, app_client, known_product):
        first = app_client.post("/api/agent/chat", json={"message": known_product["query"]}).json()
        pid = first["products"][0]["product_id"]
        r = app_client.post(
            "/api/agent/chat", json={"session_id": first["session_id"], "message": pid}
        ).json()
        if r["stores"]:
            assert any("snapshot" in n for n in r["notes"])
