# اسکریپت‌های تحلیل دیتاست

این اسکریپت‌ها برای **پروفایل‌گیری** دیتاست خام استفاده شدند و خروجی‌شان
مستند `docs/dataset.md` را ساخت.

| اسکریپت | کار |
|---|---|
| `profile_dataset.py` | شمارش ردیف، nullها، کلیدهای JSON، شناسه‌های تکراری |
| `profile_integrity.py` | یکپارچگی FK بین سه فایل، توزیع کانال پرداخت، ساختار specs |

اجرا:

```bash
python scripts/profile_dataset.py
python scripts/profile_integrity.py
```

مسیر دیتاست از متغیر محیطی `DATASET_DIR` خوانده می‌شود (پیش‌فرض: `./data` در ریشهٔ پروژه).

---

## `scripts/tools/` — ابزارهای بازتولید (فونت، اسکرین‌شات، بررسی رندر)

| ابزار | کار | پیش‌نیاز |
|---|---|---|
| `build_kalameh.py` | تبدیل TTF کلمه → ۶ فایل WOFF2 زیرمجموعه‌شده در `frontend/public/fonts/kalameh/` | `pip install fonttools brotli` + TTFها در `$KALAMEH_TTF_DIR` (پیش‌فرض `/tmp/kalameh`) |
| `check_font.py` | بررسی واقعی رندر فونت در مرورگر: `document.fonts`، خانواده محاسبه‌شده، مقایسه عرض با Tahoma | backend + frontend بالا، Playwright |
| `shoot.py` | سناریوی کامل ایجنت در **هر دو تم** (روشن/تاریک) با GPS شبیه‌سازی‌شده: خانه → جست‌وجو → بودجه → نقشهٔ خرید → ردیابی ابزار → پیگیری | همان + `playwright install chromium` |

خروجی `shoot.py` را در `docs/screenshots/` بریزید اگر قرار است در README دیده شود:

```bash
SHOTS_DIR=/tmp/shots python3 scripts/tools/shoot.py
cp /tmp/shots/light-01-home.png docs/screenshots/light-home.png   # و بقیه
```

مسیر خروجی اسکرین‌شات‌ها با `SHOTS_DIR` قابل تغییر است (پیش‌فرض: `/tmp/shots`).

```bash
SHOTS_DIR=/tmp/shots python3 scripts/tools/shoot.py
python3 scripts/tools/build_kalameh.py   # فقط اگر فونت را از نو می‌سازید
```

> `shoot.py` و `check_font.py` به سرورهای در حال اجرا روی `127.0.0.1:3000`
> (فرانت) و `127.0.0.1:8000` (بک‌اند) نیاز دارند.
