import axios, { AxiosInstance } from "axios";

/** در مرورگر از پروکسی نسبی استفاده می‌کنیم تا preview و دمو کار کند. */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { "Content-Type": "application/json", "Accept-Language": "fa" },
  /**
   * کوکی/XSRF هرگز لازم نیست (API توکن‌محور نیست) و همین گزینه یک باگ
   * محیطی مهم را می‌بندد: در سندباکس/iframe بدون `allow-same-origin`،
   * خواندن `document.cookie` استثنای SecurityError می‌دهد و axios **قبل از
   * ارسال درخواست** crash می‌کند؛ نتیجه: هیچ داده‌ای نمی‌آمد و دکمه‌هایی مثل
   * «مسیریابی» اصلاً ساخته نمی‌شدند. با false، مسیر کوکی کلاً اجرا نمی‌شود.
   */
  withXSRFToken: false,
  withCredentials: false,
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err?.response?.data?.detail ?? err?.message ?? "خطای نامشخص";
    console.error("API error:", detail);
    return Promise.reject(err);
  },
);

/** پیام خطای فارسی و قابل‌فهم از هر خطای axios */
export function apiErrorText(err: unknown, fallback = "ارتباط با سرویس برقرار نشد."): string {
  const detail =
    (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail ??
    (err as { message?: string })?.message;
  if (!detail) return fallback;
  if (/sandbox/i.test(String(detail))) return fallback;
  return String(detail);
}

/* ------------------------------------------------------------------ */
/* انواع پایه                                                          */
/* ------------------------------------------------------------------ */

export interface PriceInfo {
  value_toman: number | null;
  source: string;
  is_verified: boolean;
  verification_status: string;
  verified_at?: string | null;
  last_price_changed_at?: string | null;
  is_outlier?: boolean;
  label: string;
  note?: string | null;
}

export interface StockInfo {
  status: string;
  source: string;
  is_verified: boolean;
  label: string;
}

export interface HoursDay {
  day: string;
  key: string;
  status: string;
  status_label: string;
  shifts: { start: string; end: string }[];
  text: string;
}

export interface HoursInfo {
  has_data: boolean;
  status: string;
  status_label: string;
  is_open_now: boolean | null;
  today?: string | null;
  next_change?: string | null;
  week: HoursDay[];
  confidence: string;
  checked_at?: string | null;
  note?: string | null;
}

export interface PaymentMethod {
  provider: string;
  type: string;
  label: string;
  confidence: string;
  min_price_toman?: number | null;
  max_price_toman?: number | null;
  channel?: string;
}

export interface PaymentInfo {
  has_data: boolean;
  status: string;
  status_label: string;
  in_person_torob: boolean | null;
  credit: boolean | null;
  installment: boolean | null;
  methods: PaymentMethod[];
  confidence: string;
  note?: string | null;
}

export interface ProductSpec {
  key?: string | null;
  section?: string | null;
  value?: string | null;
}

export interface ProductSummary {
  product_id: string;
  persian_title?: string | null;
  brand_name?: string | null;
  category_name?: string | null;
  model?: string | null;
  image_url?: string | null;
  specs_count: number;
  has_specs: boolean;
  shops_count: number;
  offers_count: number;
  min_price_toman?: number | null;
  max_price_toman?: number | null;
  price: PriceInfo;
  match_score?: number | null;
  match_reasons: string[];
  limitations: string[];
}

export interface ProductDetail extends ProductSummary {
  image_urls: string[];
  specs: ProductSpec[];
  missing_specs_note?: string | null;
  category_sample_peers: string[];
}

export interface ShopInfo {
  shop_id: string;
  name?: string | null;
  name_label: string;
  name_is_verified: boolean;
  address?: string | null;
  location_label?: string | null;
  lat?: number | null;
  lon?: number | null;
  distance_km?: number | null;
  phone_display?: string | null;
  phone_note?: string | null;
  instagram?: string | null;
  website_url?: string | null;
  category_names: string[];
  supports_fast_delivery?: boolean | null;
  maps_link?: string | null;
  directions_link?: string | null;
}

export interface StoreOffer {
  offer_id: string;
  shop: ShopInfo;
  price: PriceInfo;
  stock: StockInfo;
  hours: HoursInfo;
  payment: PaymentInfo;
  seller_title?: string | null;
  warranty?: string | null;
  score?: number | null;
  score_breakdown: Record<string, number>;
  rank_reason: string[];
  cautions: string[];
}

export interface StoreSearchRequest {
  product_id: string;
  lat?: number | null;
  lon?: number | null;
  location_label?: string | null;
  radius_km?: number;
  sort_by?: string;
  max_price?: number | null;
  min_price?: number | null;
  require_installment?: boolean;
  require_credit?: boolean;
  only_open_now?: boolean;
  limit?: number;
}

export interface StoreSearchResponse {
  product?: ProductSummary | null;
  stores: StoreOffer[];
  total_candidates: number;
  returned: number;
  radius_km: number;
  user_location: Record<string, unknown>;
  filters_applied: string[];
  alternatives_note?: string | null;
  data_notes: string[];
}

export interface AgentStep {
  step: string;
  title: string;
  detail: string;
  status: string;
}

export interface DiscoveryResponse {
  session_id: string;
  step: string;
  message: string;
  question?: string | null;
  quick_replies: { label: string; value: string }[];
  missing_info: string[];
  collected: Record<string, unknown>;
  products: ProductSummary[];
  suggested_categories: { name: string; products_count: number }[];
  agent_trace: AgentStep[];
  notes: string[];
}

export interface VerificationResponse {
  offer_id: string;
  shop_id?: string | null;
  checked_at: string;
  channel: string;
  is_simulated: boolean;
  label: string;
  price_status: string;
  stock_status: string;
  hours_status: string;
  note: string;
  script: string[];
  simulated_answer?: string | null;
  real_channel_ready: boolean;
  real_channel_hint?: string | null;
}

export interface DatasetMeta {
  dataset_name?: string | null;
  shops_count: number;
  products_count: number;
  offers_count: number;
  offers_with_price: number;
  shops_with_coords: number;
  imported_at?: string | null;
  source_note?: string | null;
  coverage_note: string;
  price_freshness_note: string;
  stock_note: string;
}

export interface LocationSuggestion {
  label: string;
  shops_count: number;
  lat: number;
  lon: number;
}

/* ------------------------------------------------------------------ */
/* توابع API                                                          */
/* ------------------------------------------------------------------ */


/* ------------------------------------------------------------------ */
/* ایجنت                                                              */
/* ------------------------------------------------------------------ */

export interface ToolCallTrace {
  index: number;
  tool: string;
  title: string;
  arguments: Record<string, unknown>;
  ok: boolean;
  summary: string;
  duration_ms: number;
}

export interface PurchasePlanStep {
  title: string;
  detail: string;
  kind: string;
  source: "dataset" | "guide";
}

export interface PurchasePlan {
  mode: string;
  headline: string;
  dataset_status: "found" | "not_in_dataset" | "no_nearby_store";
  steps: PurchasePlanStep[];
  checklist: string[];
  questions_to_ask: string[];
  shop?: Record<string, any> | null;
  offer_id?: string | null;
  contact: Record<string, any>;
  transparency: string[];
  notes: string[];
}

export interface AgentChatResponse {
  session_id: string;
  stage: "need" | "product" | "stores" | "guide";
  reply: string;
  question?: string | null;
  quick_replies: { label: string; value: string }[];
  products: ProductSummary[];
  stores: StoreOffer[];
  guide?: PurchasePlan | null;
  suggested_categories: { name: string; products_count: number }[];
  collected: Record<string, any>;
  tool_calls: ToolCallTrace[];
  agent_trace: AgentStep[];
  reasoning_engine: "llm" | "deterministic";
  model_label: string;
  llm_enabled: boolean;
  notes: string[];
}

export interface AgentCapabilities {
  llm_enabled: boolean;
  provider: string;
  model?: string | null;
  model_label: string;
  tools: { name: string; title: string; description: string }[];
  note: string;
}

export async function agentChat(body: {
  message?: string;
  session_id?: string | null;
  lat?: number | null;
  lon?: number | null;
  location_label?: string | null;
  product_id?: string | null;
  offer_id?: string | null;
}): Promise<AgentChatResponse> {
  const { data } = await api.post("/agent/chat", body);
  return data;
}

export async function agentCapabilities(): Promise<AgentCapabilities> {
  const { data } = await api.get("/agent/capabilities");
  return data;
}

export async function reverseLocation(lat: number, lon: number) {
  const { data } = await api.post("/location/reverse", null, { params: { lat, lon } });
  return data as { ok: boolean; summary: string; location: Record<string, any> };
}

export async function health() {
  const { data } = await api.get("/health");
  return data;
}

export async function examples(): Promise<{
  starters: string[];
  budget_options: { label: string; value: string }[];
  note: string;
}> {
  const { data } = await api.get("/examples");
  return data;
}

export async function datasetMeta(): Promise<DatasetMeta> {
  const { data } = await api.get("/dataset/meta");
  return data;
}

export async function datasetLocations(limit = 12): Promise<LocationSuggestion[]> {
  const { data } = await api.get("/dataset/locations", { params: { limit } });
  return data;
}

export async function discover(body: {
  message?: string;
  session_id?: string | null;
  answers?: Record<string, unknown>;
}): Promise<DiscoveryResponse> {
  const { data } = await api.post("/discover", body);
  return data;
}

export async function searchProducts(body: {
  query?: string;
  category?: string;
  brand?: string;
  min_price?: number;
  max_price?: number;
  limit?: number;
}): Promise<{
  results: ProductSummary[];
  total: number;
  query?: string;
  suggested_categories: { name: string; products_count: number }[];
  note?: string;
}> {
  const { data } = await api.post("/products/search", body);
  return data;
}

export async function productDetail(productId: string): Promise<ProductDetail> {
  const { data } = await api.get(`/products/${productId}`);
  return data;
}

export async function searchStores(body: StoreSearchRequest): Promise<StoreSearchResponse> {
  const { data } = await api.post("/stores/search", body);
  return data;
}

export async function compareStores(offerIds: string[]) {
  const { data } = await api.post("/stores/compare", { offer_ids: offerIds });
  return data;
}

export async function verifyOffer(body: {
  offer_id: string;
  channel?: string;
}): Promise<VerificationResponse> {
  const { data } = await api.post("/verify", body);
  return data;
}

export interface VerificationRecent {
  id: number;
  offer_id?: string | null;
  shop_name?: string | null;
  product_title?: string | null;
  channel: string;
  is_simulated: boolean;
  checked_at: string;
  price_status?: string | null;
  stock_status?: string | null;
  label: string;
}

export async function recentVerifications(limit = 10): Promise<VerificationRecent[]> {
  const { data } = await api.get("/verifications/recent", { params: { limit } });
  return data;
}

export async function verifyHistory(offerId: string) {
  const { data } = await api.get(`/verify/${offerId}`);
  return data;
}

/* ------------------------------------------------------------------ */
/* کمکی‌ها                                                            */
/* ------------------------------------------------------------------ */

const faNum = new Intl.NumberFormat("fa-IR");

export function formatToman(value?: number | null): string {
  if (value == null) return "نامشخص";
  return `${faNum.format(value)} تومان`;
}

const FA_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];

/** ارقام لاتین → فارسی (برای متن‌هایی که Intl روی‌شان اعمال نشده). */
export function toFaDigits(input: string | number): string {
  return String(input).replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)]);
}

/** اعشار با ممیز فارسی: 4.2 → «۴٫۲» */
export function faDecimal(value: number, decimals = 1): string {
  return toFaDigits(value.toFixed(decimals)).replace(".", "٫");
}

/** اعشار یک‌رقمی، بدون صفرِ انتهایی: 2.0 → «۲»، 2.8 → «۲٫۸» */
function faOne(value: number): string {
  const out = faDecimal(value, 1);
  return out.endsWith("٫۰") ? out.slice(0, -2) : out;
}

export function formatCompactToman(value?: number | null): string {
  if (value == null) return "نامشخص";
  if (value >= 1_000_000_000) return `${faOne(value / 1_000_000_000)} میلیارد تومان`;
  if (value >= 1_000_000) return `${faOne(value / 1_000_000)} میلیون تومان`;
  if (value >= 1_000) return `${faNum.format(Math.round(value / 1_000))} هزار تومان`;
  return `${faNum.format(value)} تومان`;
}

export function formatNumber(value?: number | null): string {
  if (value == null) return "—";
  return faNum.format(value);
}

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("fa-IR", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}
