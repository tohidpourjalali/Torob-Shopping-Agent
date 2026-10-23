"""درخواست تأیید قیمت / موجودی / ساعت کاری.

سه حالت، همه با برچسب صریح در پاسخ:
1) DEMO — شبیه‌سازی کامل: هیچ تماس یا پیامی ارسال نمی‌شود. پاسخ شبیه‌سازی‌شده
   با برچسب «نمایشی» برمی‌گردد و در دیتابیس با is_simulated=True ثبت می‌شود.
2) REAL-READY — اگر کانال واقعی (تلفنی/پیام‌رسان) در env پیکربندی شده باشد،
   متن سؤال آماده و ارسال می‌شود؛ در غیر این صورت صادقانه اعلام می‌کنیم که
   کانال واقعی وجود ندارد و به DEMO برمی‌گردیم.
3) MANUAL — اسکریپت گفت‌وگو به کاربر داده می‌شود تا خودش تماس بگیرد/پیام دهد.

نکته اخلاقی/واقعیت داده: شماره‌های دیتاست از نوع display_number هستند و
تأیید مالکیت نشده‌اند؛ هرگز به‌عنوان «شماره تماس قطعی فروشگاه» نمایش داده
نمی‌شوند و برای ارسال پیام واقعی بدون تأیید استفاده نمی‌شوند.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import Offer, Shop, VerificationRecord
from app.schemas import VerificationRequest, VerificationResponse
from app.core.text import fmt_toman

MODE_DEMO = "demo"
MODE_REAL = "real"


def real_channel_status() -> tuple[bool, Optional[str]]:
    provider = (os.getenv("TELEPHONY_PROVIDER") or "none").strip().lower()
    has_key = bool(os.getenv("TELEPHONY_API_KEY"))
    has_from = bool(os.getenv("TELEPHONY_FROM_NUMBER"))
    if provider in {"", "none"}:
        return False, (
            "هیچ کانال تماس واقعی پیکربندی نشده است (TELEPHONY_PROVIDER=none). "
            "تأیید به حالت نمایشی محدود می‌شود."
        )
    if not (has_key and has_from):
        return False, (
            f"ارائه‌دهنده «{provider}» انتخاب شده اما TELEPHONY_API_KEY یا "
            "TELEPHONY_FROM_NUMBER تنظیم نشده است."
        )
    return True, f"کانال واقعی «{provider}» پیکربندی شده است."


def build_script(offer: Offer, shop: Optional[Shop], ask_price: bool, ask_stock: bool, ask_hours: bool) -> List[str]:
    title = None
    if offer.product is not None:
        title = offer.product.persian_title
    lines: List[str] = []
    lines.append(f"سلام، از طرف دستیار خرید ترب تماس می‌گیرم درباره «{title or 'این محصول'}».")
    if ask_price:
        price_part = f"قیمت ثبت‌شده {fmt_toman(offer.price_toman)}" if offer.price_toman else "قیمتی برای این محصول ثبت نشده"
        lines.append(f"می‌خواستم قیمت فعلی را تأیید کنم؛ {price_part} است. آیا قیمت همین است؟")
    if ask_stock:
        lines.append("الان موجود دارید؟ چند عدد؟")
    if ask_hours:
        lines.append("امروز تا چه ساعتی باز هستید؟")
    lines.append("ممنون، اگر موجود نبود جایگزین پیشنهادی دارید؟")
    return lines


def verify_offer(session: Session, request: VerificationRequest) -> VerificationResponse:
    offer = session.query(Offer).filter(Offer.offer_id == request.offer_id).first()
    if not offer:
        raise ValueError(f"offer_not_found:{request.offer_id}")
    if offer.price_is_outlier:
        raise ValueError(f"offer_price_outlier:{request.offer_id}")

    shop = session.query(Shop).filter(Shop.shop_id == offer.shop_id).first()
    script = build_script(offer, shop, request.ask_price, request.ask_stock, request.ask_hours)

    channel = (request.channel or MODE_DEMO).strip().lower()
    ready, hint = real_channel_status()

    if channel == MODE_REAL and not ready:
        channel = MODE_DEMO  # بازگشت صادقانه به حالت نمایشی

    is_simulated = channel != MODE_REAL

    if is_simulated:
        # --- شبیه‌سازی: هیچ تماسی انجام نمی‌شود ---
        price_status = "no_response"
        stock_status = "unknown"
        hours_status = "unknown"
        simulated_answer = (
            "این پاسخ شبیه‌سازی‌شده است. در حالت نمایشی هیچ تماس یا پیامی به فروشگاه "
            "ارسال نشده و پاسخی دریافت نشده است."
        )
        note = (
            "حالت نمایشی (Demo): هیچ ارتباط واقعی برقرار نشد. برای نتیجه واقعی باید "
            "کانال تماس/پیام‌رسان پیکربندی شود یا خودتان با فروشگاه تماس بگیرید."
        )
        if hint:
            note = f"{note} {hint}"
    else:
        # --- کانال واقعی: اینجا باید provider صدا زده شود ---
        price_status = "no_response"
        stock_status = "unknown"
        hours_status = "unknown"
        simulated_answer = None
        note = (
            "درخواست تأیید از طریق کانال واقعی ارسال شد. پاسخ فروشنده هنوز ثبت نشده است؛ "
            "تا زمان دریافت پاسخ، قیمت و موجودی «تأییدنشده» باقی می‌ماند."
        )

    rec = VerificationRecord(
        offer_id=offer.offer_id,
        shop_id=offer.shop_id,
        channel=("demo" if is_simulated else "real_phone"),
        is_simulated=is_simulated,
        checked_at=datetime.utcnow(),
        price_status=price_status,
        stock_status=stock_status,
        hours_status=hours_status,
        note=note,
        response_source=("simulation" if is_simulated else "telephony_api"),
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)

    return VerificationResponse(
        offer_id=offer.offer_id,
        shop_id=offer.shop_id,
        checked_at=rec.checked_at,
        channel=rec.channel,
        is_simulated=is_simulated,
        label="نمایشی — بدون تماس واقعی" if is_simulated else "کانال واقعی",
        price_status=price_status,
        stock_status=stock_status,
        hours_status=hours_status,
        note=note,
        script=script,
        simulated_answer=simulated_answer,
        real_channel_ready=ready,
        real_channel_hint=hint,
    )


def latest_record(session: Session, offer_id: str) -> Optional[VerificationRecord]:
    return (
        session.query(VerificationRecord)
        .filter(VerificationRecord.offer_id == offer_id)
        .order_by(VerificationRecord.checked_at.desc())
        .first()
    )
