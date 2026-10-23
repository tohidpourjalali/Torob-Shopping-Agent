"""نقطه ورود FastAPI — دستیار خرید حضوری ترب."""

from __future__ import annotations

import logging
import os

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.db.init_db import init_db

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
)
log = logging.getLogger("main")

APP_ENV = os.getenv("APP_ENV", "development")
APP_VERSION = "1.0.0"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """ساخت جدول‌ها در استارتاپ (idempotent).

    روی PaaS، برنامه معمولاً قبل از اجرای import بالا می‌آید؛ بدون این کار
    healthcheck با خطای «relation does not exist» می‌شکند و استقرار ناموفق
    علامت می‌خورد. شکست اتصال هم کشنده نیست تا بتوانیم پیام روشن بدهیم.
    """
    try:
        init_db()
        log.info("database initialized")
    except Exception as exc:  # pragma: no cover - فقط در نبود دیتابیس
        log.warning("init_db failed: %s", exc)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Torob In-Person Shopping Agent",
    description=(
        "دستیار خرید حضوری: کشف نیاز → انتخاب محصول از کاتالوگ واقعی ترب → "
        "یافتن فروشگاه‌های تهران دارای آفر → مقایسه و تأیید قیمت/موجودی."
    ),
    version=APP_VERSION,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# پیش‌فرض: اجازه به فرانت‌اند محلی و preview. در تولید با FRONTEND_ORIGINS محدود کنید.
_origins = os.getenv("FRONTEND_ORIGINS", "*")
allow_origins = ["*"] if _origins.strip() == "*" else [o.strip() for o in _origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False if allow_origins == ["*"] else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {
        "app": "torob-in-person-shopping-agent",
        "version": APP_VERSION,
        "env": APP_ENV,
        "docs": "/docs",
        "api": "/api/health",
        "note": "داده‌ها از snapshot دیتاست ترب خوانده می‌شوند و قیمت زنده نیستند.",
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):  # pragma: no cover
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "خطای داخلی سرور", "path": request.url.path},
    )
