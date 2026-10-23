"""Pydantic schemas — قرارداد API بین بک‌اند و فرانت‌اند RTL."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# مشترک
# --------------------------------------------------------------------------- #
class DataProvenance(BaseModel):
    """منبع و سطح اطمینان هر داده — برای شفافیت در UI."""
    source: str = "dataset"
    source_label: str = "دیتاست توروب (snapshot)"
    verification_status: str = "unverified"   # verified | unverified | simulated | unknown
    verified_at: Optional[datetime] = None
    note: Optional[str] = None


class PriceInfo(BaseModel):
    value_toman: Optional[int] = None
    source: str = "dataset"
    is_verified: bool = False
    verification_status: str = "not_confirmed"  # not_confirmed | confirmed | changed | unknown
    verified_at: Optional[datetime] = None
    last_price_changed_at: Optional[datetime] = None
    is_outlier: bool = False
    label: str = "قیمت ثبت‌شده در دیتاست — تأییدنشده"
    note: Optional[str] = None


class StockInfo(BaseModel):
    """دیتاست هیچ اطلاعات موجودی ندارد؛ این فیلد همیشه unknown است تا زمانی که تأیید شود."""
    status: str = "unknown"  # unknown | in_stock | out_of_stock
    source: str = "none"
    is_verified: bool = False
    verified_at: Optional[datetime] = None
    label: str = "موجودی نامشخص — دیتاست موجودی ندارد"


class HoursInfo(BaseModel):
    has_data: bool = False
    status: str = "unset"
    status_label: str = "ساعت کاری ثبت نشده"
    is_open_now: Optional[bool] = None
    today: Optional[str] = None
    next_change: Optional[str] = None
    week: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: str = "none"
    checked_at: Optional[str] = None
    note: Optional[str] = None


class PaymentInfo(BaseModel):
    has_data: bool = False
    status: str = "unset"
    status_label: str = "اطلاعات پرداخت ثبت نشده"
    in_person_torob: Optional[bool] = None
    credit: Optional[bool] = None
    installment: Optional[bool] = None
    methods: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: str = "none"
    note: Optional[str] = None


# --------------------------------------------------------------------------- #
# محصول
# --------------------------------------------------------------------------- #
class ProductSpec(BaseModel):
    key: Optional[str] = None
    section: Optional[str] = None
    value: Optional[str] = None


class ProductSummary(BaseModel):
    product_id: str
    persian_title: Optional[str] = None
    brand_name: Optional[str] = None
    category_name: Optional[str] = None
    model: Optional[str] = None
    image_url: Optional[str] = None
    specs_count: int = 0
    has_specs: bool = False
    shops_count: int = 0
    offers_count: int = 0
    min_price_toman: Optional[int] = None
    max_price_toman: Optional[int] = None
    price: PriceInfo = Field(default_factory=PriceInfo)
    match_score: Optional[float] = None
    match_reasons: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class ProductDetail(ProductSummary):
    image_urls: List[str] = Field(default_factory=list)
    specs: List[ProductSpec] = Field(default_factory=list)
    missing_specs_note: Optional[str] = None
    category_sample_peers: List[str] = Field(default_factory=list)


class ProductSearchRequest(BaseModel):
    query: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    # دقت: همهٔ توکن‌ها لازم باشند و حداقل امتیاز تطابق
    require_all_tokens: bool = False
    min_match_score: float = 0.0


class ProductSearchResponse(BaseModel):
    results: List[ProductSummary] = Field(default_factory=list)
    total: int = 0
    query: Optional[str] = None
    suggested_categories: List[Dict[str, Any]] = Field(default_factory=list)
    note: Optional[str] = None


# --------------------------------------------------------------------------- #
# فروشگاه / آفر
# --------------------------------------------------------------------------- #
class ShopInfo(BaseModel):
    shop_id: str
    name: Optional[str] = None
    name_label: str = "نام ثبت‌شده در دیتاست — تأییدنشده"
    name_is_verified: bool = False
    address: Optional[str] = None
    location_label: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    distance_km: Optional[float] = None
    phone_display: Optional[str] = None
    phone_note: Optional[str] = "شماره از دیتاست؛ قبل از استفاده تأیید کنید."
    instagram: Optional[str] = None
    website_url: Optional[str] = None
    category_names: List[str] = Field(default_factory=list)
    supports_fast_delivery: Optional[bool] = None
    maps_link: Optional[str] = None
    directions_link: Optional[str] = None


class StoreOffer(BaseModel):
    offer_id: str
    shop: ShopInfo
    price: PriceInfo
    stock: StockInfo
    hours: HoursInfo
    payment: PaymentInfo
    seller_title: Optional[str] = None
    warranty: Optional[str] = None
    score: Optional[float] = None
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    rank_reason: List[str] = Field(default_factory=list)
    cautions: List[str] = Field(default_factory=list)


class StoreSearchRequest(BaseModel):
    product_id: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    location_label: Optional[str] = None   # مثل «فردوسی» — از برچسب‌های واقعی دیتاست
    radius_km: float = Field(default=5.0, ge=0.2, le=60)
    sort_by: str = "smart"                 # smart | price | distance | hours
    max_price: Optional[int] = None
    min_price: Optional[int] = None
    require_installment: bool = False
    require_credit: bool = False
    only_open_now: bool = False
    limit: int = Field(default=20, ge=1, le=100)


class StoreSearchResponse(BaseModel):
    product: Optional[ProductSummary] = None
    stores: List[StoreOffer] = Field(default_factory=list)
    total_candidates: int = 0
    returned: int = 0
    radius_km: float = 5.0
    user_location: Dict[str, Any] = Field(default_factory=dict)
    filters_applied: List[str] = Field(default_factory=list)
    alternatives_note: Optional[str] = None
    data_notes: List[str] = Field(default_factory=list)


class CompareRequest(BaseModel):
    offer_ids: List[str] = Field(default_factory=list, max_length=6)


class CompareRow(BaseModel):
    offer_id: str
    shop_name: Optional[str] = None
    price_toman: Optional[int] = None
    distance_km: Optional[float] = None
    open_now: Optional[bool] = None
    payment_label: str = "نامشخص"
    hours_label: str = "نامشخص"
    price_verified: bool = False
    score: float = 0.0


class CompareResponse(BaseModel):
    rows: List[CompareRow] = Field(default_factory=list)
    best_price_offer_id: Optional[str] = None
    best_distance_offer_id: Optional[str] = None
    best_overall_offer_id: Optional[str] = None
    summary: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# تأیید
# --------------------------------------------------------------------------- #
class VerificationRequest(BaseModel):
    offer_id: str
    channel: str = "demo"          # demo | real
    ask_price: bool = True
    ask_stock: bool = True
    ask_hours: bool = True


class VerificationResponse(BaseModel):
    offer_id: str
    shop_id: Optional[str] = None
    checked_at: datetime
    channel: str
    is_simulated: bool
    label: str
    price_status: str
    stock_status: str
    hours_status: str
    note: str
    script: List[str] = Field(default_factory=list)      # متن سؤال‌هایی که پرسیده می‌شود
    simulated_answer: Optional[str] = None
    real_channel_ready: bool = False
    real_channel_hint: Optional[str] = None


class VerificationRecentOut(BaseModel):
    """یک ردیف از «استعلام‌های اخیر» — با نام محصول و فروشگاه برای نمایش."""

    id: int
    offer_id: Optional[str] = None
    shop_name: Optional[str] = None
    product_title: Optional[str] = None
    channel: str
    is_simulated: bool
    checked_at: datetime
    price_status: Optional[str] = None
    stock_status: Optional[str] = None
    label: str = "نمایشی — بدون تماس واقعی"


class VerificationRecordOut(BaseModel):
    id: int
    offer_id: Optional[str] = None
    shop_id: Optional[str] = None
    channel: str
    is_simulated: bool
    checked_at: datetime
    price_status: Optional[str] = None
    stock_status: Optional[str] = None
    hours_status: Optional[str] = None
    note: Optional[str] = None


# --------------------------------------------------------------------------- #
# متادیتا
# --------------------------------------------------------------------------- #
class DatasetMetaOut(BaseModel):
    dataset_name: Optional[str] = None
    shops_count: int = 0
    products_count: int = 0
    offers_count: int = 0
    offers_with_price: int = 0
    shops_with_coords: int = 0
    imported_at: Optional[datetime] = None
    source_note: Optional[str] = None
    coverage_note: str = ""
    price_freshness_note: str = ""
    stock_note: str = ""


class LocationSuggestion(BaseModel):
    label: str
    shops_count: int
    lat: float
    lon: float


# --------------------------------------------------------------------------- #
# ایجنت (حلقهٔ ابزارمحور)
# --------------------------------------------------------------------------- #
class AgentStep(BaseModel):
    """یک گام از مسیر چهارمرحله‌ای — برای نمایش پیشرفت به کاربر."""

    step: str
    title: str
    detail: str
    status: str = "done"   # done | active | pending


class AgentChatRequest(BaseModel):
    """ورودی گفت‌وگو با ایجنت."""

    message: Optional[str] = None
    session_id: Optional[str] = None
    # موقعیت کاربر — از GPS مرورگر یا انتخاب محله
    lat: Optional[float] = None
    lon: Optional[float] = None
    location_label: Optional[str] = None
    # انتخاب صریح (کلیک روی کارت محصول یا فروشگاه)
    product_id: Optional[str] = None
    offer_id: Optional[str] = None


class ToolCallTrace(BaseModel):
    """یک فراخوانی ابزار توسط ایجنت — برای شفافیت کامل."""

    index: int
    tool: str
    title: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    ok: bool = True
    summary: str = ""
    duration_ms: int = 0


class PurchasePlanStep(BaseModel):
    title: str
    detail: str
    kind: str = "action"
    source: str = "guide"    # dataset | guide


class PurchasePlanOut(BaseModel):
    mode: str = "dataset_offer"          # dataset_offer | general_guide
    headline: str = ""
    dataset_status: str = "found"        # found | not_in_dataset
    steps: List[PurchasePlanStep] = Field(default_factory=list)
    checklist: List[str] = Field(default_factory=list)
    questions_to_ask: List[str] = Field(default_factory=list)
    shop: Optional[Dict[str, Any]] = None
    offer_id: Optional[str] = None
    contact: Dict[str, Any] = Field(default_factory=dict)
    transparency: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class AgentChatResponse(BaseModel):
    session_id: str
    stage: str = "need"                  # need | product | stores | guide
    reply: str = ""
    question: Optional[str] = None
    quick_replies: List[Dict[str, str]] = Field(default_factory=list)
    products: List[ProductSummary] = Field(default_factory=list)
    stores: List[StoreOffer] = Field(default_factory=list)
    guide: Optional[PurchasePlanOut] = None
    suggested_categories: List[Dict[str, Any]] = Field(default_factory=list)
    collected: Dict[str, Any] = Field(default_factory=dict)
    tool_calls: List[ToolCallTrace] = Field(default_factory=list)
    agent_trace: List[AgentStep] = Field(default_factory=list)
    # شفافیت دربارهٔ موتور تصمیم
    reasoning_engine: str = "deterministic"
    model_label: str = "بدون مدل (برنامه‌ریز قطعی)"
    llm_enabled: bool = False
    notes: List[str] = Field(default_factory=list)


class AgentCapabilities(BaseModel):
    """چه چیزی الان فعال است — برای صفحهٔ «دربارهٔ ایجنت»."""

    llm_enabled: bool = False
    provider: str = "none"
    model: Optional[str] = None
    model_label: str = "بدون مدل (برنامه‌ریز قطعی)"
    tools: List[Dict[str, str]] = Field(default_factory=list)
    note: str = ""
