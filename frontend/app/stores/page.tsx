"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StoreCard } from "@/components/store-card";
import { ProvenanceBadge } from "@/components/provenance-badge";
import { ProductImage } from "@/components/product-image";
import { LocationPicker, type PickedLocation } from "@/components/location-picker";
import {
  compareStores,
  formatCompactToman,
  formatNumber,
  productDetail,
  searchProducts,
  searchStores,
  type ProductDetail,
  type StoreSearchResponse,
} from "@/lib/api";
import {
  Loader2,
  SlidersHorizontal,
  MapPin,
  ArrowRight,
  AlertTriangle,
  GitCompareArrows,
  CheckCircle2,
  Home,
  X,
} from "lucide-react";

const RADIUS_OPTIONS = [1, 2, 3, 5, 10, 20];
const SORT_OPTIONS = [
  { key: "smart", label: "هوشمند" },
  { key: "price", label: "ارزان‌ترین" },
  { key: "distance", label: "نزدیک‌ترین" },
  { key: "hours", label: "الان باز" },
];

function StoresInner() {
  const params = useSearchParams();
  const productId = params.get("product") || "";

  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [picked, setPicked] = useState<PickedLocation | null>(null);
  const [radius, setRadius] = useState(5);
  const [sortBy, setSortBy] = useState("smart");
  const [onlyOpen, setOnlyOpen] = useState(false);
  const [requireCredit, setRequireCredit] = useState(false);
  const [requireInstallment, setRequireInstallment] = useState(false);

  const [data, setData] = useState<StoreSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selected, setSelected] = useState<string[]>([]);
  const [compare, setCompare] = useState<any>(null);

  useEffect(() => {
    if (!productId) return;
    productDetail(productId).then(setProduct).catch(() => {});
  }, [productId]);

  const load = useCallback(async () => {
    if (!productId) return;
    setLoading(true);
    setError(null);
    setCompare(null);
    try {
      const res = await searchStores({
        product_id: productId,
        lat: picked?.lat ?? null,
        lon: picked?.lon ?? null,
        location_label: picked?.source === "area" ? picked.label : null,
        radius_km: radius,
        sort_by: sortBy,
        only_open_now: onlyOpen,
        require_credit: requireCredit,
        require_installment: requireInstallment,
        limit: 30,
      });
      setData(res);
    } catch {
      setError("دریافت فروشگاه‌ها ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }, [productId, picked, radius, sortBy, onlyOpen, requireCredit, requireInstallment]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleSelect = (offerId: string) => {
    setSelected((prev) =>
      prev.includes(offerId)
        ? prev.filter((x) => x !== offerId)
        : prev.length >= 4
          ? prev
          : [...prev, offerId],
    );
  };

  const runCompare = async () => {
    if (selected.length < 2) return;
    try {
      const res = await compareStores(selected);
      setCompare(res);
    } catch {
      setError("مقایسه ناموفق بود.");
    }
  };

  const priceRange = useMemo(() => {
    if (!data?.stores?.length) return null;
    const prices = data.stores
      .map((s) => s.price.value_toman)
      .filter((v): v is number => typeof v === "number");
    if (!prices.length) return null;
    return { min: Math.min(...prices), max: Math.max(...prices) };
  }, [data]);

  if (!productId) {
    return <ProductEntry />;
  }

  return (
    <main className="mx-auto max-w-2xl px-3 pb-24 pt-3">
      <header className="mb-3 flex items-center justify-between gap-2">
        <Button asChild size="sm" variant="ghost" className="h-8 px-2 text-xs">
          <Link prefetch={false} href="/discover">
            <ArrowRight className="ml-1 h-3 w-3" aria-hidden />
            بازگشت
          </Link>
        </Button>
        <Button asChild size="sm" variant="ghost" className="h-8 px-2 text-xs">
          <Link prefetch={false} href="/">
            <Home className="h-4 w-4" aria-hidden />
          </Link>
        </Button>
      </header>

      {/* محصول انتخاب‌شده */}
      {product && (
        <Card className="mb-3">
          <CardContent className="p-3">
            <div className="flex gap-2.5">
              <ProductImage
                src={product.image_url}
                alt={product.persian_title || ""}
                seed={product.product_id}
                className="h-14 w-14 shrink-0"
              />
              <div className="min-w-0 flex-1">
                <h1 className="line-clamp-2 text-[13px] font-bold leading-5">
                  {product.persian_title}
                </h1>
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                  <ProvenanceBadge tone="neutral" icon={false}>
                    {formatNumber(product.shops_count)} فروشگاه
                  </ProvenanceBadge>
                  {product.category_name && <span className="truncate">{product.category_name}</span>}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* فیلترها */}
      <Card className="mb-3">
        <CardContent className="space-y-2.5 p-3">
          <div className="flex items-center gap-1 text-[11px] font-semibold text-muted-foreground">
            <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden />
            فیلترها
          </div>

          {/* موقعیت — GPS با اجازهٔ صریح یا انتخاب محله از دیتاست */}
          <div>
            <label className="mb-1 block text-[10px] text-muted-foreground">
              موقعیت شما (برای محاسبهٔ فاصله)
            </label>
            <LocationPicker value={picked} onChange={setPicked} compact />
          </div>

          {/* شعاع */}
          <div>
            <label className="mb-1 block text-[10px] text-muted-foreground">
              شعاع: {formatNumber(radius)} کیلومتر
            </label>
            <div className="flex flex-wrap gap-1">
              {RADIUS_OPTIONS.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRadius(r)}
                  className={
                    "rounded-md border px-2 py-0.5 text-[10px] " +
                    (radius === r ? "border-primary bg-primary/10 font-semibold" : "")
                  }
                >
                  {formatNumber(r)} کیلومتر
                </button>
              ))}
            </div>
          </div>

          {/* مرتب‌سازی */}
          <div>
            <label className="mb-1 block text-[10px] text-muted-foreground">مرتب‌سازی</label>
            <div className="flex flex-wrap gap-1">
              {SORT_OPTIONS.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  onClick={() => setSortBy(s.key)}
                  className={
                    "rounded-md border px-2 py-0.5 text-[10px] " +
                    (sortBy === s.key ? "border-primary bg-primary/10 font-semibold" : "")
                  }
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* سوییچ‌ها */}
          <div className="flex flex-wrap gap-x-3 gap-y-1 pt-0.5">
            {[
              { label: "فقط باز الان", checked: onlyOpen, set: setOnlyOpen },
              { label: "پرداخت اعتباری", checked: requireCredit, set: setRequireCredit },
              { label: "اقساط/وام", checked: requireInstallment, set: setRequireInstallment },
            ].map((f) => (
              <label key={f.label} className="flex items-center gap-1 text-[11px]">
                <input
                  type="checkbox"
                  checked={f.checked}
                  onChange={(e) => f.set(e.target.checked)}
                  className="h-3.5 w-3.5 accent-primary"
                />
                {f.label}
              </label>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* خلاصه */}
      {data && (
        <div className="mb-2 space-y-1.5">
          <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
            <ProvenanceBadge tone="neutral" icon={false}>
              {formatNumber(data.returned)} از {formatNumber(data.total_candidates)} فروشگاه
            </ProvenanceBadge>
            {(data.user_location as any)?.label && (
              <span className="inline-flex items-center gap-0.5 text-muted-foreground">
                <MapPin className="h-3 w-3" aria-hidden />
                {(data.user_location as any).label}
              </span>
            )}
            {priceRange && (
              <span className="text-muted-foreground">
                بازه قیمت: {formatCompactToman(priceRange.min)} — {formatCompactToman(priceRange.max)}
              </span>
            )}
          </div>

          {data.filters_applied.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {data.filters_applied.map((f) => (
                <span key={f} className="rounded bg-secondary px-1.5 py-0.5 text-[10px]">
                  {f}
                </span>
              ))}
            </div>
          )}

          {data.alternatives_note && (
            <div className="flex items-start gap-1 rounded-lg border border-amber-200 bg-amber-50 p-2 text-[11px] leading-5 text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              {data.alternatives_note}
            </div>
          )}
        </div>
      )}

      {/* لیست */}
      {loading && (
        <div className="flex items-center justify-center gap-2 py-10 text-xs text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          در حال جست‌وجوی فروشگاه‌های دیتاست…
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-2 text-[11px] text-rose-800 dark:border-rose-900 dark:bg-rose-950/40">
          {error}
        </div>
      )}

      {!loading && data && data.stores.length === 0 && (
        <Card>
          <CardContent className="p-4 text-center text-xs leading-6 text-muted-foreground">
            فروشگاهی با این فیلترها پیدا نشد.
            <br />
            شعاع را بیشتر کنید یا فیلترهای پرداخت/ساعت را بردارید.
          </CardContent>
        </Card>
      )}

      <div className="space-y-2">
        {data?.stores.map((s, i) => (
          <StoreCard
              origin={picked ? { lat: picked.lat, lon: picked.lon } : null}
            key={s.offer_id}
            offer={s}
            rank={i + 1}
            selected={selected.includes(s.offer_id)}
            onToggleSelect={toggleSelect}
          />
        ))}
      </div>

      {/* نتیجه مقایسه */}
      {compare && (
        <Card className="mt-3 border-primary/40">
          <CardContent className="p-3">
            <h2 className="mb-1.5 flex items-center gap-1 text-[13px] font-bold">
              <GitCompareArrows className="h-4 w-4" aria-hidden />
              مقایسه {formatNumber(compare.rows.length)} فروشگاه
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-[11px]">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="py-1 text-right font-medium">فروشگاه</th>
                    <th className="py-1 text-right font-medium">قیمت</th>
                    <th className="py-1 text-right font-medium">پرداخت</th>
                    <th className="py-1 text-right font-medium">وضعیت</th>
                  </tr>
                </thead>
                <tbody>
                  {compare.rows.map((r: any) => (
                    <tr key={r.offer_id} className="border-b last:border-0">
                      <td className="py-1 font-medium">{r.shop_name || "بدون نام"}</td>
                      <td className="py-1">{formatCompactToman(r.price_toman)}</td>
                      <td className="py-1 text-muted-foreground">{r.payment_label}</td>
                      <td className="py-1">
                        {r.open_now === true ? "باز" : r.open_now === false ? "بسته" : "نامشخص"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {compare.summary?.length > 0 && (
              <ul className="mt-2 space-y-0.5">
                {compare.summary.map((s: string, i: number) => (
                  <li key={i} className="flex items-start gap-1 text-[11px] leading-5">
                    <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-primary" aria-hidden />
                    {s}
                  </li>
                ))}
              </ul>
            )}
            {compare.notes?.length > 0 && (
              <ul className="mt-1.5 space-y-0.5">
                {compare.notes.map((n: string, i: number) => (
                  <li key={i} className="text-[10px] leading-5 text-muted-foreground">
                    • {n}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      {/* نوار مقایسه */}
      {selected.length >= 2 && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t bg-background/95 p-2 backdrop-blur">
          <div className="mx-auto flex max-w-2xl items-center gap-2">
            <span className="text-[11px] text-muted-foreground">
              {formatNumber(selected.length)} مورد انتخاب شده
            </span>
            <Button size="sm" className="h-8 flex-1 text-xs" onClick={runCompare}>
              <GitCompareArrows className="ml-1 h-3.5 w-3.5" aria-hidden />
              مقایسه کن
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-8 text-xs"
              onClick={() => setSelected([])}
            >
              پاک کردن
            </Button>
          </div>
        </div>
      )}

      {/* یادداشت داده */}
      {data?.data_notes && data.data_notes.length > 0 && (
        <ul className="mt-4 space-y-0.5">
          {data.data_notes.map((n, i) => (
            <li key={i} className="text-[10px] leading-5 text-muted-foreground">
              • {n}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

export default function StoresPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[100dvh] items-center justify-center text-sm text-muted-foreground">
          <Loader2 className="ml-2 h-4 w-4 animate-spin" aria-hidden />
          در حال بارگذاری…
        </div>
      }
    >
      <StoresInner />
    </Suspense>
  );
}


/**
 * ورود بدون انتخاب محصول — قبلاً یک بن‌بست بود («محصولی انتخاب نشده»).
 * اکنون جست‌وجوی واقعی روی دیتاست، و هر نتیجه مستقیم به فروشگاه‌های همان محصول.
 */
function ProductEntry() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<{ product_id: string; persian_title?: string | null; shops_count: number }[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const run = async () => {
    const term = q.trim();
    if (!term) return;
    setBusy(true);
    setNote(null);
    try {
      const res = await searchProducts({ query: term, limit: 8 });
      setItems(res.results ?? []);
      if (!res.results?.length) setNote("برای این عبارت محصولی در دیتاست پیدا نشد؛ از صفحهٔ گفت‌وگو امتحان کنید.");
    } catch {
      setNote("جست‌وجو ناموفق بود.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto max-w-2xl px-3 pb-16 pt-3">
      <header className="mb-3 flex items-center justify-between">
        <Button asChild size="sm" variant="ghost" className="h-8 px-2 text-xs">
          <Link prefetch={false} href="/discover">
            <ArrowRight className="ml-1 h-3 w-3" aria-hidden /> گفت‌وگو با ایجنت
          </Link>
        </Button>
        <Button asChild size="sm" variant="ghost" className="h-8 px-2 text-xs">
          <Link prefetch={false} href="/"><Home className="h-4 w-4" aria-hidden /></Link>
        </Button>
      </header>

      <h1 className="mb-1 flex items-center gap-1.5 text-base font-extrabold">
        <MapPin className="h-5 w-5 text-primary" aria-hidden />
        فروشگاه‌های حضوری
      </h1>
      <p className="mb-3 text-[11px] leading-5 text-muted-foreground">
        محصول را جست‌وجو کنید تا فروشگاه‌های حضوری دارای آفر، با فاصله و قیمت دیده شوند.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          run();
        }}
        className="mb-3 flex gap-1.5"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="مثلاً شارژر اپل، هدفون سونی"
          aria-label="جست‌وجوی محصول"
          className="h-9 w-full rounded-lg border border-border bg-background px-2 text-xs"
        />
        <Button size="sm" className="h-9 shrink-0 text-xs" type="submit" disabled={busy}>
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : "جست‌وجو"}
        </Button>
      </form>

      {note && <p className="mb-2 text-[10px] text-muted-foreground">{note}</p>}

      <div className="grid gap-1.5">
        {items.map((it) => (
          <Link
            key={it.product_id}
            href={`/stores?product=${it.product_id}`}
            className="flex items-center justify-between gap-2 rounded-xl border border-border bg-card px-2.5 py-2 text-[11px] hover:border-primary"
          >
            <span className="line-clamp-1">{it.persian_title ?? "بدون عنوان"}</span>
            <span className="shrink-0 text-[9px] text-muted-foreground">
              {formatNumber(it.shops_count)} فروشگاه
            </span>
          </Link>
        ))}
      </div>
    </main>
  );
}
