"""تست تفسیر شرایط پرداخت و ساعت کاری — با مقادیر واقعی دیتاست."""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.core.hours import hours_summary, open_score
from app.core.payment import matches_payment_filter, payment_capabilities

TEHRAN = ZoneInfo("Asia/Tehran")


def shop_with(payment_options=None, weekly_hours=None):
    return SimpleNamespace(
        payment_options=json.dumps(payment_options, ensure_ascii=False) if payment_options is not None else None,
        weekly_hours=json.dumps(weekly_hours, ensure_ascii=False) if weekly_hours is not None else None,
    )


class TestPayment:
    def test_no_data_is_unset(self):
        caps = payment_capabilities(shop_with(payment_options=[]))
        assert caps["has_data"] is False
        assert caps["status"] == "unset"
        assert caps["credit"] is None
        assert caps["installment"] is None
        assert "ثبت نشده" in caps["status_label"]

    def test_null_payment_options(self):
        caps = payment_capabilities(shop_with())
        assert caps["has_data"] is False

    def test_in_person(self):
        caps = payment_capabilities(shop_with([
            {"channel": "in_person", "provider_name": "ترب‌پی", "category_names": [],
             "min_price_toman": None, "max_price_toman": None},
        ]))
        assert caps["in_person_torob"] is True
        assert caps["status"] == "in_person"

    def test_unknown_channel_is_flagged(self):
        caps = payment_capabilities(shop_with([
            {"channel": "unknown", "provider_name": "اسنپ‌پی", "category_names": [],
             "min_price_toman": None, "max_price_toman": None},
        ]))
        assert caps["status"] == "unknown_channel"
        assert "unknown" in caps["note"]

    def test_bnpl_provider_inferred_as_credit(self):
        caps = payment_capabilities(shop_with([
            {"channel": "in_person", "provider_name": "دیجی پی", "category_names": [],
             "min_price_toman": None, "max_price_toman": None},
        ]))
        assert caps["credit"] is True
        assert caps["confidence"] == "inferred"
        assert any(m["provider"] == "دیجی پی" for m in caps["methods"])

    def test_installment_provider(self):
        caps = payment_capabilities(shop_with([
            {"channel": "unknown", "provider_name": "ازکی‌وام", "category_names": [],
             "min_price_toman": 5_000_000, "max_price_toman": 50_000_000},
        ]))
        assert caps["installment"] is True
        assert caps["methods"][0]["min_price_toman"] == 5_000_000

    def test_unknown_provider_is_other(self):
        caps = payment_capabilities(shop_with([
            {"channel": "in_person", "provider_name": "برند ناشناس", "category_names": [],
             "min_price_toman": None, "max_price_toman": None},
        ]))
        assert caps["credit"] is None
        assert any(m["type"] == "other" for m in caps["methods"])

    def test_filter_is_strict(self):
        no_data = payment_capabilities(shop_with(payment_options=[]))
        assert matches_payment_filter(no_data, want_credit=False, want_installment=False) is True
        assert matches_payment_filter(no_data, want_credit=True, want_installment=False) is False

        with_installment = payment_capabilities(shop_with([
            {"channel": "unknown", "provider_name": "ازکی‌وام", "category_names": [],
             "min_price_toman": None, "max_price_toman": None},
        ]))
        assert matches_payment_filter(with_installment, want_credit=True, want_installment=True) is True

    def test_malformed_json_does_not_crash(self):
        shop = SimpleNamespace(payment_options="{not json", weekly_hours=None)
        caps = payment_capabilities(shop)
        assert caps["has_data"] is False


class TestHours:
    WEEKLY = {
        "sat": {"status": "declared", "shifts": [{"start_time": "10:00:00", "end_time": "19:00:00"}]},
        "sun": {"status": "declared", "shifts": [{"start_time": "10:00:00", "end_time": "19:00:00"}]},
        "mon": {"status": "declared", "shifts": [{"start_time": "10:00:00", "end_time": "19:00:00"}]},
        "tue": {"status": "declared", "shifts": [{"start_time": "10:00:00", "end_time": "19:00:00"}]},
        "wed": {"status": "declared", "shifts": [{"start_time": "10:00:00", "end_time": "19:00:00"}]},
        "thu": {"status": "declared", "shifts": [{"start_time": "10:00:00", "end_time": "14:00:00"}]},
        "fri": {"status": "closed", "shifts": [{"start_time": "00:00:00", "end_time": "00:00:00"}]},
    }

    def test_no_data(self):
        s = hours_summary(None)
        assert s["has_data"] is False
        assert s["is_open_now"] is None
        assert s["status"] == "unset"

    def test_empty_dict_is_no_data(self):
        assert hours_summary("{}")["has_data"] is False

    def test_open_during_shift(self):
        # دوشنبه ساعت ۱۲ تهران
        at = datetime(2026, 10, 19, 12, 0, tzinfo=TEHRAN)  # 2026-10-19 is Monday
        s = hours_summary(json.dumps(self.WEEKLY), at=at)
        assert s["has_data"] is True
        assert s["is_open_now"] is True
        assert s["next_change"] == "19:00"

    def test_closed_before_opening(self):
        at = datetime(2026, 10, 19, 8, 0, tzinfo=TEHRAN)  # Monday 08:00
        s = hours_summary(json.dumps(self.WEEKLY), at=at)
        assert s["is_open_now"] is False
        assert s["next_change"] == "10:00"

    def test_closed_after_shift(self):
        at = datetime(2026, 10, 19, 20, 0, tzinfo=TEHRAN)
        s = hours_summary(json.dumps(self.WEEKLY), at=at)
        assert s["is_open_now"] is False

    def test_friday_closed(self):
        at = datetime(2026, 10, 23, 12, 0, tzinfo=TEHRAN)  # Friday
        s = hours_summary(json.dumps(self.WEEKLY), at=at)
        assert s["is_open_now"] is False
        assert s["today"] == "جمعه"

    def test_week_has_seven_days_in_persian(self):
        s = hours_summary(json.dumps(self.WEEKLY))
        assert len(s["week"]) == 7
        assert s["week"][0]["day"] == "شنبه"
        assert s["week"][6]["day"] == "جمعه"

    def test_thursday_short_shift(self):
        at = datetime(2026, 10, 22, 15, 0, tzinfo=TEHRAN)  # Thursday
        s = hours_summary(json.dumps(self.WEEKLY), at=at)
        assert s["is_open_now"] is False  # ۱۵ بعد از ۱۴

    def test_declared_confidence_note(self):
        s = hours_summary(json.dumps(self.WEEKLY))
        assert s["confidence"] == "declared"
        assert "اعلام‌شده" in s["note"]

    def test_unsupported_day(self):
        weekly = {"mon": {"status": "unsupported", "shifts": []}}
        s = hours_summary(json.dumps(weekly))
        assert s["confidence"] in {"unsupported", "declared"}

    def test_open_score_ordering(self):
        assert open_score({"is_open_now": True}) > open_score({"is_open_now": None})
        assert open_score({"is_open_now": None}) > open_score({"is_open_now": False})

    def test_malformed_json(self):
        assert hours_summary("{bad json")["has_data"] is False


class TestWarrantyLabel:
    """گارانتی در دیتاست JSON است؛ کاربر نباید JSON خام ببیند."""

    def test_parses_dataset_json(self):
        from app.services.stores import warranty_label
        raw = '{"description":null,"period_months":null,"provider":"بدون گارانتی"}'
        assert warranty_label(raw) == "بدون گارانتی"

    def test_months_and_provider(self):
        from app.services.stores import warranty_label
        raw = '{"description":null,"period_months":12,"provider":"شرکت نمونه"}'
        assert warranty_label(raw) == "گارانتی ۱۲ ماهه — شرکت نمونه"

    def test_months_only(self):
        from app.services.stores import warranty_label
        assert warranty_label('{"period_months":6}') == "گارانتی ۶ ماهه"

    def test_plain_text_passthrough(self):
        from app.services.stores import warranty_label
        assert warranty_label("تست و تحویل در حضور مشتری") == "تست و تحویل در حضور مشتری"

    def test_broken_json_does_not_crash(self):
        from app.services.stores import warranty_label
        assert warranty_label("{not json") == "{not json"

    def test_empty_is_none(self):
        from app.services.stores import warranty_label
        assert warranty_label(None) is None
        assert warranty_label("") is None
        assert warranty_label('{"provider":null}') is None

    def test_no_raw_json_reaches_user(self):
        from app.services.stores import warranty_label
        for raw in ('{"provider":"الف","period_months":18}', '{"period_months":3}', '{}'):
            out = warranty_label(raw) or ""
            assert not out.strip().startswith(("{", "[")), f"JSON خام: {out!r}"
