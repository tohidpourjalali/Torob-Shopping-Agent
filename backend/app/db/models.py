"""مدل‌های دیتابیس (ORM) — مطابق با اسکیمای دیتاست Torob (Starcoach v16 cap300).

اصل طراحی: هر مقدار نامشخص در دیتاست به صورت NULL نگه داشته می‌شود؛ هیچ مقدار
فرضی/ساختگی جایگزین نمی‌شود. فیلدهای مشتق‌شده (مثل شماره تلفن تفکیک‌شده یا
خلاصه کانال پرداخت) فقط «تبدیل شکل» داده اصلی هستند و منبع‌شان ثبت می‌شود.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class DatasetMeta(Base):
    """شناسنامه دیتاست واردشده — برای نمایش شفاف منبع داده در UI."""
    __tablename__ = "dataset_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_name = Column(String(255), nullable=True)     # e.g. starcoach-dataset-v16-cap300-csv
    shops_count = Column(Integer, nullable=True)
    products_count = Column(Integer, nullable=True)
    offers_count = Column(Integer, nullable=True)
    offers_with_price = Column(Integer, nullable=True)
    shops_with_coords = Column(Integer, nullable=True)
    imported_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    source_note = Column(Text, nullable=True)


class Shop(Base):
    __tablename__ = "shops"

    shop_id = Column(String(64), primary_key=True)
    # نام فروشگاه در دیتاست است و لزوماً تأییدشده نیست (name_is_verified=False)
    name = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    location_label = Column(String(255), nullable=True)
    lat = Column(String(32), nullable=True)   # رشته ذخیره می‌شود تا دقت اعشار حفظ شود
    lon = Column(String(32), nullable=True)
    category_names = Column(Text, nullable=True)   # JSON: list[str]
    contacts = Column(Text, nullable=True)         # JSON: [{channel, display_number}]
    instagram = Column(String(512), nullable=True)
    website_url = Column(String(1024), nullable=True)
    payment_options = Column(Text, nullable=True)  # JSON: [{channel, provider_name, min/max_price_toman, category_names}]
    supports_fast_delivery = Column(Boolean, nullable=True)
    weekly_hours = Column(Text, nullable=True)     # JSON: {mon..sun: {status, shifts[]}}

    # --- فیلدهای مشتق‌شده (تبدیل شکل، نه اختراع داده) ---
    phone_display = Column(String(64), nullable=True)   # همان display_number دیتاست، بدون تغییر
    payment_channels = Column(String(64), nullable=True)  # e.g. "in_person,unknown" | NULL اگر خالی
    payment_providers = Column(Text, nullable=True)       # JSON: list[str]

    name_is_verified = Column(Boolean, default=False, nullable=False)
    contact_is_verified = Column(Boolean, default=False, nullable=False)

    offers = relationship("Offer", back_populates="shop", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_shops_shop_id", "shop_id"),
        Index("ix_shops_name", "name"),
    )


class Product(Base):
    __tablename__ = "products"

    product_id = Column(String(64), primary_key=True)
    persian_title = Column(String(512), nullable=True)
    brand_name = Column(String(255), nullable=True)
    category_name = Column(String(255), nullable=True)
    model = Column(String(255), nullable=True)
    image_urls = Column(Text, nullable=True)  # JSON: list[str]
    specs = Column(Text, nullable=True)       # JSON: [{key, section, value}]
    specs_count = Column(Integer, nullable=True)  # 0 => مشخصات ثبت‌نشده
    title_norm = Column(Text, nullable=True)   # نرمال‌شده برای جست‌وجوی فارسی
    search_blob = Column(Text, nullable=True)  # عنوان+برند+دسته+مدل نرمال‌شده

    # آمار پیش‌محاسبه‌شده از offers (برای جست‌وجوی سریع بدون join سنگین)
    shops_count = Column(Integer, default=0, nullable=False)
    offers_count = Column(Integer, default=0, nullable=False)
    min_price_toman = Column(Integer, nullable=True)
    max_price_toman = Column(Integer, nullable=True)
    min_price_offer_id = Column(String(64), nullable=True)

    # --- آمار پیش‌محاسبه‌شده از offers (برای جست‌وجوی سریع) ---
    offers_count = Column(Integer, default=0, nullable=False)
    shops_count = Column(Integer, default=0, nullable=False)
    min_price_toman = Column(Integer, nullable=True)
    max_price_toman = Column(Integer, nullable=True)

    offers = relationship("Offer", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_products_brand", "brand_name"),
        Index("ix_products_category", "category_name"),
        Index("ix_products_title", "persian_title"),
        Index("ix_products_search_blob", "search_blob"),
        Index("ix_products_shops_count", "shops_count"),
    )


class Offer(Base):
    __tablename__ = "offers"

    offer_id = Column(String(64), primary_key=True)
    product_id = Column(String(64), ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    shop_id = Column(String(64), ForeignKey("shops.shop_id", ondelete="CASCADE"), nullable=False)
    seller_title = Column(String(512), nullable=True)
    description = Column(Text, nullable=True)
    price_toman = Column(Integer, nullable=True)   # NULL = قیمت ثبت نشده
    last_price_changed_at = Column(DateTime, nullable=True)  # زمان تغییر قیمت، نه زمان تأیید
    warranty = Column(Text, nullable=True)
    price_is_outlier = Column(Boolean, default=False, nullable=False)

    product = relationship("Product", back_populates="offers")
    shop = relationship("Shop", back_populates="offers")

    __table_args__ = (
        Index("ix_offers_product_shop", "product_id", "shop_id"),
        Index("ix_offers_price", "price_toman"),
        Index("ix_offers_shop", "shop_id"),
    )


class VerificationRecord(Base):
    """ثبت وضعیت تأیید قیمت/موجودی/ساعت کاری از طریق کانال معتبر یا شبیه‌سازی‌شده."""
    __tablename__ = "verification_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    offer_id = Column(String(64), ForeignKey("offers.offer_id", ondelete="CASCADE"), nullable=True)
    shop_id = Column(String(64), ForeignKey("shops.shop_id", ondelete="CASCADE"), nullable=True)
    channel = Column(String(64), nullable=False)  # demo_call | demo_message | real_phone | real_message | website_form | none
    is_simulated = Column(Boolean, default=True, nullable=False)
    checked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    price_status = Column(String(64), nullable=True)   # confirmed | changed | not_confirmed | no_response | unknown
    price_verified_at = Column(DateTime, nullable=True)
    stock_status = Column(String(64), nullable=True)   # in_stock | out_of_stock | no_response | unknown
    stock_verified_at = Column(DateTime, nullable=True)
    hours_status = Column(String(64), nullable=True)   # open | closed | no_response | unknown
    hours_verified_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    response_source = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_verif_offer", "offer_id"),
        Index("ix_verif_shop", "shop_id"),
        Index("ix_verif_checked", "checked_at"),
    )


class AgentSession(Base):
    """وضعیت گفت‌وگوی کشف نیاز — تا زمینه بین نوبت‌ها حفظ شود.

    در حافظه نگه‌داشتن کافی نبود: با چند worker یا ری‌استارت سرور، زمینه
    گفت‌وگو از دست می‌رفت. اینجا فقط «آنچه کاربر گفته» ذخیره می‌شود
    (JSON) و هیچ داده شخصی حساسی نگه‌داری نمی‌شود.
    """

    __tablename__ = "agent_sessions"

    session_id = Column(String(64), primary_key=True)
    state = Column(Text, nullable=True)          # JSON: collected fields
    step = Column(String(32), nullable=True)     # last step
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_agent_sessions_updated", "updated_at"),
    )
