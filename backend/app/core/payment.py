"""تفسیر شرایط پرداخت فروشگاه‌ها بر پایه داده واقعی دیتاست.

واقعیت دیتاست (v16 cap300):
- ستون `payment_options` برای تنها ۲۶۶ فروشگاه از ۶,۴۷۶ فروشگاه مقدار دارد.
- مقدار `channel` فقط دو حالت دارد: `in_person` (۸۲) و `unknown` (۱۸۴).
- اطلاعات اعتباری/اقساطی در دیتاست به‌صورت فیلد صریح وجود ندارد؛ تنها
  `provider_name` (مثل اسنپ‌پی، دیجی‌پی، تارا، ازکی‌وام، ترب‌پی) موجود است.

بنابراین: هر تفسیر اعتباری/اقساطی «استنتاج از نام ارائه‌دهنده» است، نه داده
تأییدشده. این ماژول نوع پرداخت را با سطح اطمینان مشخص برمی‌گرداند تا UI
بتواند صادقانه آن را برچسب بزند.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

# نگاشت ارائه‌دهنده -> نوع سرویس. منبع: دانش عمومی درباره سرویس‌های پرداخت ایران.
# چون دیتاست نوع سرویس را صریح نمی‌دهد، اطمینان "inferred" است.
PROVIDER_CATALOG: Dict[str, Dict[str, str]] = {
    "اسنپ‌پی": {"type": "bnpl", "label": "اعتباری (خرید اعتباری اسنپ‌پی)", "operator": "اسنپ"},
    "snappay": {"type": "bnpl", "label": "اعتباری (خرید اعتباری اسنپ‌پی)", "operator": "اسنپ"},
    "دیجی پی": {"type": "bnpl", "label": "اعتباری (دیجی‌پی)", "operator": "دیجی‌کالا"},
    "digipay": {"type": "bnpl", "label": "اعتباری (دیجی‌پی)", "operator": "دیجی‌کالا"},
    "تارا": {"type": "bnpl", "label": "اعتباری/اقساطی (تارا)", "operator": "تارا"},
    "tara": {"type": "bnpl", "label": "اعتباری/اقساطی (تارا)", "operator": "تارا"},
    "ازکی‌وام": {"type": "installment", "label": "وام/اقساط (ازکی‌وام)", "operator": "ازکی"},
    "azkivam": {"type": "installment", "label": "وام/اقساط (ازکی‌وام)", "operator": "ازکی"},
    "ترب‌پی": {"type": "torob_pay", "label": "پرداخت ترب‌پی", "operator": "ترب"},
    "torobpay": {"type": "torob_pay", "label": "پرداخت ترب‌پی", "operator": "ترب"},
}

PAYMENT_TYPE_LABELS = {
    "in_person": "پرداخت حضوری در فروشگاه",
    "torob_pay": "پرداخت از طریق ترب‌پی",
    "bnpl": "خرید اعتباری (BNPL)",
    "installment": "اقساط/وام",
    "credit": "اعتباری",
    "other": "سایر روش‌های پرداخت",
    "unset": "اطلاعات پرداخت ثبت نشده",
    "unknown_channel": "کانال پرداخت نامشخص",
}


def _safe_list(raw: Optional[str]) -> List[Dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def payment_capabilities(shop) -> Dict[str, Any]:
    """خلاصه‌ی قابل‌نمایش از شرایط پرداخت یک فروشگاه + سطح اطمینان."""
    options = _safe_list(getattr(shop, "payment_options", None))

    if not options:
        return {
            "has_data": False,
            "status": "unset",
            "status_label": PAYMENT_TYPE_LABELS["unset"],
            "in_person_torob": None,
            "credit": None,
            "installment": None,
            "methods": [],
            "confidence": "none",
            "note": "در دیتاست هیچ روش پرداختی برای این فروشگاه ثبت نشده است.",
        }

    methods: List[Dict[str, Any]] = []
    channels = set()
    in_person: Optional[bool] = None
    credit: Optional[bool] = None
    installment: Optional[bool] = None

    for opt in options:
        channel = (opt.get("channel") or "").strip().lower() or "unknown"
        provider = (opt.get("provider_name") or "").strip()
        channels.add(channel)

        if channel == "in_person":
            in_person = True

        cat = PROVIDER_CATALOG.get(provider) or PROVIDER_CATALOG.get(provider.replace(" ", ""))
        if cat:
            if cat["type"] in {"bnpl", "credit"}:
                credit = True
            if cat["type"] == "installment":
                installment = True
                credit = True
            methods.append({
                "provider": provider,
                "type": cat["type"],
                "label": cat["label"],
                "confidence": "inferred",  # استنتاج از نام ارائه‌دهنده
                "min_price_toman": opt.get("min_price_toman"),
                "max_price_toman": opt.get("max_price_toman"),
                "channel": channel,
            })
        elif provider:
            methods.append({
                "provider": provider,
                "type": "other",
                "label": f"پذیرنده {provider}",
                "confidence": "inferred",
                "min_price_toman": opt.get("min_price_toman"),
                "max_price_toman": opt.get("max_price_toman"),
                "channel": channel,
            })

    if channel_unclear := ("unknown" in channels and "in_person" not in channels):
        status = "unknown_channel"
    elif in_person:
        status = "in_person"
    else:
        status = "other"

    note = "منبع: ستون payment_options دیتاست."
    if channel_unclear:
        note += " کانال پرداخت در دیتاست «unknown» ثبت شده است."
    if credit or installment:
        note += " نوع اعتباری/اقساطی از نام ارائه‌دهنده استنتاج شده و تأیید نشده است."

    return {
        "has_data": True,
        "status": status,
        "status_label": PAYMENT_TYPE_LABELS.get(status, status),
        "in_person_torob": in_person,
        "credit": credit,
        "installment": installment,
        "methods": methods,
        "confidence": "inferred",
        "note": note,
    }


def matches_payment_filter(caps: Dict[str, Any], want_credit: bool, want_installment: bool) -> bool:
    """فیلتر سخت‌گیرانه: فقط فروشگاه‌هایی که داده‌شان صریحاً تأییدکننده است."""
    if want_installment and not caps.get("installment"):
        return False
    if want_credit and not caps.get("credit"):
        return False
    return True
