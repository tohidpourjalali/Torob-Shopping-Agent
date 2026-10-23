# ─────────────────────────────────────────────────────────────────────────────
# Torob In-Person Shopping Agent — Backend
# تصویر چندمرحله‌ای: نصب وابستگی‌ها جدا از کد تا کش لایه‌ها مؤثر باشد.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# gcc/libpq برای psycopg2 (حالت PostgreSQL)
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATASET_DIR=/data \
    DATABASE_URL=sqlite:////data/torob_agent.db

# libpq5 برای اجرای psycopg2 بدون ابزار build
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 curl \
 && rm -rf /var/lib/apt/lists/*

# کاربر غیر root
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app
COPY --from=deps /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser scripts ./scripts
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini ./

RUN mkdir -p /data && chown -R appuser:appuser /data
USER appuser

EXPOSE 8000

# دیتاست در ایمیج نیست — در زمان اجرا mount می‌شود (حجم ~۲۷۳ مگابایت)
# PORT در زمان اجرا: روی PaaS (مثل لیارا) پورت را پلتفرم تعیین می‌کند؛
# پیش‌فرض محلی ۸۰۰۰ است.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/api/health" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
