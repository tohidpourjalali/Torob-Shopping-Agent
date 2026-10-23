"""تحلیل ساعت کاری فروشگاه‌ها از ستون weekly_hours دیتاست.

ساختار واقعی دیتاست:
{"sat": {"status": "declared"|"closed"|"unsupported",
         "shifts": [{"start_time": "10:00:00", "end_time": "19:00:00"}]}, ...}

نکات صداقت داده:
- `status=declared` یعنی فروشگاه خودش اعلام کرده؛ تأیید مستقل نشده است.
- `status=closed` یعنی تعطیل اعلام‌شده.
- `status=unsupported` یعنی این اطلاعات پشتیبانی/ثبت نشده است.
- ۲,۰۰۳ فروشگاه در دیتاست اصلاً weekly_hours ندارند.
"""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
    TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:  # pragma: no cover
    TEHRAN = None

# ترتیب روزهای هفته در دیتاست (شنبه = ابتدای هفته)
DAY_KEYS = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"]
DAY_FA = {
    "sat": "شنبه", "sun": "یکشنبه", "mon": "دوشنبه", "tue": "سه‌شنبه",
    "wed": "چهارشنبه", "thu": "پنجشنبه", "fri": "جمعه",
}
# weekday() پایتون: دوشنبه=0 ... یکشنبه=6
_PY_TO_KEY = {5: "sat", 6: "sun", 0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri"}

STATUS_LABEL = {
    "declared": "اعلام‌شده توسط فروشگاه",
    "closed": "تعطیل اعلام‌شده",
    "unsupported": "ثبت‌نشده",
    "unknown": "نامشخص",
}


def now_tehran() -> datetime:
    if TEHRAN is not None:
        return datetime.now(TEHRAN)
    return datetime.utcnow() + timedelta(hours=3, minutes=30)


def _parse_time(value: Optional[str]) -> Optional[time]:
    if not value:
        return None
    try:
        parts = str(value).strip().split(":")
        return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
    except (ValueError, IndexError):
        return None


def parse_weekly(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _day_shifts(day: Dict[str, Any]) -> List[Dict[str, str]]:
    shifts = day.get("shifts") or []
    out = []
    for s in shifts if isinstance(shifts, list) else []:
        if not isinstance(s, dict):
            continue
        start = s.get("start_time")
        end = s.get("end_time")
        if start == "00:00:00" and end == "00:00:00":
            continue  # شیفت صفر یعنی تعطیل
        if _parse_time(start) and _parse_time(end):
            out.append({"start": start[:5], "end": end[:5]})
    return out


def hours_summary(raw: Optional[str], at: Optional[datetime] = None) -> Dict[str, Any]:
    """وضعیت «الان باز است؟» + جدول هفتگی + برچسب اطمینان."""
    weekly = parse_weekly(raw)
    at = at or now_tehran()

    if not weekly:
        return {
            "has_data": False,
            "status": "unset",
            "status_label": "ساعت کاری ثبت نشده",
            "is_open_now": None,
            "today": None,
            "week": [],
            "confidence": "none",
            "checked_at": at.isoformat(),
            "note": "این فروشگاه در دیتاست ساعت کاری ندارد؛ وضعیت باز/بسته نامشخص است.",
        }

    key_today = _PY_TO_KEY.get(at.weekday(), "sat")
    today = weekly.get(key_today) or {}
    today_shifts = _day_shifts(today)
    today_status = (today.get("status") or "unknown").lower()

    is_open: Optional[bool]
    next_change: Optional[str] = None
    if today_status == "closed" or not today_shifts:
        is_open = False
    else:
        is_open = False
        cur = at.time()
        for sh in today_shifts:
            start, end = _parse_time(sh["start"]), _parse_time(sh["end"])
            if start and end and start <= cur < end:
                is_open = True
                next_change = sh["end"]
                break
        if not is_open:
            upcoming = [sh for sh in today_shifts if _parse_time(sh["start"]) and _parse_time(sh["start"]) > cur]
            if upcoming:
                next_change = upcoming[0]["start"]

    week = []
    for k in DAY_KEYS:
        d = weekly.get(k) or {}
        shifts = _day_shifts(d)
        week.append({
            "day": DAY_FA[k],
            "key": k,
            "status": (d.get("status") or "unknown").lower(),
            "status_label": STATUS_LABEL.get((d.get("status") or "unknown").lower(), "نامشخص"),
            "shifts": shifts,
            "text": "، ".join(f"{s['start']}–{s['end']}" for s in shifts) if shifts else "تعطیل",
        })

    if today_status == "unsupported":
        confidence = "unsupported"
        note = "فروشگاه برای این روز ساعت کاری ثبت نکرده است."
    elif today_status == "closed":
        confidence = "declared"
        note = "فروشگاه امروز را تعطیل اعلام کرده است (اعلام خود فروشگاه، تأییدنشده)."
    else:
        confidence = "declared"
        note = "ساعت کاری اعلام‌شده توسط فروشگاه در دیتاست؛ پیش از مراجعه تأیید کنید."

    return {
        "has_data": True,
        "status": today_status,
        "status_label": STATUS_LABEL.get(today_status, "نامشخص"),
        "is_open_now": is_open,
        "today": DAY_FA.get(key_today),
        "next_change": next_change,
        "week": week,
        "confidence": confidence,
        "checked_at": at.isoformat(),
        "note": note,
    }


def open_score(summary: Dict[str, Any]) -> float:
    """امتیاز ۰..۱ برای رتبه‌بندی: باز بودن الان مهم‌ترین است."""
    if summary.get("is_open_now") is True:
        return 1.0
    if summary.get("is_open_now") is False:
        return 0.15
    return 0.45  # نامشخص
