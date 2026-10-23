"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ProvenanceBadge, PriceBadge } from "@/components/provenance-badge";
import { ProductImage } from "@/components/product-image";
import {
  formatCompactToman,
  formatNumber,
  productDetail,
  type ProductDetail,
} from "@/lib/api";
import {
  ArrowRight,
  Loader2,
  Store,
  AlertCircle,
  Info,
  ArrowLeft,
} from "lucide-react";

export default function ProductPage() {
  const params = useParams();
  const router = useRouter();
  const id = String(params?.id || "");

  const [data, setData] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    productDetail(id)
      .then(setData)
      .catch(() => setError("این محصول در دیتاست پیدا نشد."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <main className="flex min-h-[60dvh] items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="ml-2 h-4 w-4 animate-spin" aria-hidden />
        در حال خواندن محصول…
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="mx-auto max-w-2xl p-6 text-center">
        <p className="text-sm text-muted-foreground">{error || "محصول پیدا نشد."}</p>
        <Button asChild size="sm" className="mt-3">
          <Link href="/discover">بازگشت به گفت‌وگو</Link>
        </Button>
      </main>
    );
  }

  const grouped = data.specs.reduce<Record<string, typeof data.specs>>((acc, s) => {
    const key = s.section || "سایر";
    (acc[key] ||= []).push(s);
    return acc;
  }, {});

  return (
    <main className="mx-auto max-w-2xl px-3 pb-24 pt-3">
      <Button asChild size="sm" variant="ghost" className="mb-2 h-8 px-2 text-xs">
        <Link href="/discover">
          <ArrowRight className="ml-1 h-3 w-3" aria-hidden />
          بازگشت
        </Link>
      </Button>

      {/* هدر محصول */}
      <Card>
        <CardContent className="p-3">
          <div className="flex gap-3">
            <ProductImage
              src={data.image_url}
              alt={data.persian_title || ""}
              className="h-24 w-24 shrink-0"
            />
            <div className="min-w-0 flex-1">
              <h1 className="text-sm font-bold leading-6">{data.persian_title}</h1>
              <div className="mt-1 space-y-0.5 text-[11px] text-muted-foreground">
                {data.brand_name && <div>برند: {data.brand_name}</div>}
                {data.category_name && <div>دسته: {data.category_name}</div>}
                {data.model && <div>مدل: {data.model}</div>}
              </div>
            </div>
          </div>

          {/* قیمت */}
          <div className="mt-3 rounded-lg border bg-muted/40 p-2.5">
            <div className="flex items-end justify-between gap-2">
              <div>
                <div className="text-[10px] text-muted-foreground">
                  کمترین قیمت ثبت‌شده در دیتاست
                </div>
                <div className="text-base font-extrabold text-primary">
                  {formatCompactToman(data.min_price_toman)}
                </div>
                {data.max_price_toman != null &&
                  data.max_price_toman !== data.min_price_toman && (
                    <div className="text-[10px] text-muted-foreground">
                      بیشترین: {formatCompactToman(data.max_price_toman)}
                    </div>
                  )}
              </div>
              <div className="flex flex-col items-end gap-1">
                <PriceBadge verified={data.price?.is_verified} />
                <ProvenanceBadge tone="neutral" icon={false}>
                  {formatNumber(data.shops_count)} فروشگاه
                </ProvenanceBadge>
              </div>
            </div>
            {data.price?.note && (
              <p className="mt-1.5 text-[10px] leading-5 text-muted-foreground">{data.price.note}</p>
            )}
          </div>

          <Button
            className="mt-3 w-full"
            size="sm"
            onClick={() => router.push(`/stores?product=${encodeURIComponent(data.product_id)}`)}
          >
            <Store className="ml-1 h-4 w-4" aria-hidden />
            دیدن فروشگاه‌های حضوری این محصول
            <ArrowLeft className="mr-1 h-3.5 w-3.5" aria-hidden />
          </Button>
        </CardContent>
      </Card>

      {/* مشخصات */}
      <Card className="mt-3">
        <CardContent className="p-3">
          <h2 className="mb-2 flex items-center gap-1 text-[13px] font-bold">
            <Info className="h-4 w-4" aria-hidden />
            مشخصات فنی
          </h2>

          {data.specs.length === 0 ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-[11px] leading-6 text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
              <div className="mb-1 flex items-center gap-1 font-semibold">
                <AlertCircle className="h-3.5 w-3.5" aria-hidden />
                مشخصاتی ثبت نشده است
              </div>
              <p>
                {data.missing_specs_note ||
                  "برای این محصول در دیتاست مشخصات فنی ثبت نشده است و ما آن را حدس نمی‌زنیم."}
              </p>
              {data.category_sample_peers.length > 0 && (
                <div className="mt-1.5">
                  <div className="font-medium">نمونه‌هایی از همین دسته که مشخصات دارند:</div>
                  <ul className="mt-0.5 list-disc pr-4 leading-6">
                    {data.category_sample_peers.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-2.5">
              {Object.entries(grouped).map(([section, items]) => (
                <div key={section}>
                  <div className="mb-1 text-[11px] font-semibold text-primary">{section}</div>
                  <dl className="divide-y rounded-lg border">
                    {items.map((s, i) => (
                      <div key={i} className="flex gap-2 px-2 py-1 text-[11px]">
                        <dt className="w-32 shrink-0 text-muted-foreground">{s.key}</dt>
                        <dd className="flex-1 leading-5">{s.value ?? "نامشخص"}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ))}
            </div>
          )}

          <p className="mt-2 text-[10px] leading-5 text-muted-foreground">
            تعداد مشخصات ثبت‌شده: {formatNumber(data.specs_count)} مورد. منبع: دیتاست ترب.
          </p>
        </CardContent>
      </Card>

      {/* تصاویر */}
      {data.image_urls.length > 1 && (
        <Card className="mt-3">
          <CardContent className="p-3">
            <h2 className="mb-2 text-[13px] font-bold">تصاویر</h2>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {data.image_urls.slice(0, 10).map((u, i) => (
                <ProductImage
                  key={i}
                  src={u}
                  alt={`تصویر ${i + 1}`}
                  className="h-16 w-16 shrink-0"
                />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
