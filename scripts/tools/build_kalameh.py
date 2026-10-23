"""تبدیل TTF کلمه به woff2 سبک برای وب.

- subset روی بازه‌های یونیکد لازم (فارسی/عربی/لاتین/اعداد/نشانه‌ها)
- خروجی woff2 (فشرده‌تر از woff و ttf)
"""

from __future__ import annotations

import os

import subprocess
import sys
from pathlib import Path

SRC = Path(os.environ.get("KALAMEH_TTF_DIR", "/tmp/kalameh"))
OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "fonts" / "kalameh"
OUT.mkdir(parents=True, exist_ok=True)

# بازه‌های یونیکد مورد نیاز رابط فارسی
UNICODES = ",".join([
    "U+0020-007E",      # لاتین پایه + علائم
    "U+00A0-00FF",      # لاتین-۱
    "U+0600-06FF",      # عربی/فارسی (شامل اعداد فارسی ۰-۹ و نیم‌فاصله)
    "U+0750-077F",      # عربی مکمل
    "U+08A0-08FF",      # عربی توسعه‌یافته
    "U+200C-200F",      # نیم‌فاصله و نشانه‌های جهت
    "U+2010-2027",      # خط تیره، نقل‌قول، سه‌نقطه
    "U+2030-205E",      # نشانه‌های دیگر
    "U+20AA",           # ₪ (کنار گذاشته می‌شود ولی بی‌ضرر است)
    "U+FB50-FDFF",      # اشکال نمایشی عربی A
    "U+FE70-FEFF",      # اشکال نمایشی عربی B
    "U+FEFF",           # BOM
])

WEIGHTS = [
    ("Kalameh-Light.ttf", "kalameh-300.woff2", 300),
    ("Kalameh_Regular.ttf", "kalameh-400.woff2", 400),
    ("Kalameh-Medium.ttf", "kalameh-500.woff2", 500),
    ("Kalameh_Bold.ttf", "kalameh-700.woff2", 700),
    ("Kalameh-ExtraBold.ttf", "kalameh-800.woff2", 800),
    ("Kalameh_Black.ttf", "kalameh-900.woff2", 900),
]

total = 0
for src_name, out_name, weight in WEIGHTS:
    src = SRC / src_name
    if not src.exists():
        print(f"  ⚠️  {src_name} موجود نیست — رد شد")
        continue
    dst = OUT / out_name
    cmd = [
        sys.executable, "-m", "fontTools.subset", str(src),
        f"--unicodes={UNICODES}",
        "--layout-features=*",
        "--flavor=woff2",
        f"--output-file={dst}",
        "--no-hinting" if weight != 400 else "--hinting",
        "--desubroutinize",
        "--name-IDs=*",
        "--drop-tables+=DSIG",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ❌ {src_name}: {r.stderr[-300:]}")
        continue
    size = dst.stat().st_size
    total += size
    before = src.stat().st_size
    print(f"  ✅ {out_name:22s} {before/1024:6.1f}KB → {size/1024:5.1f}KB  (وزن {weight})")

print(f"\nمجموع: {total/1024:.1f} KB در {OUT}")
