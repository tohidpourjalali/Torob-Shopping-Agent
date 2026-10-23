"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { ProvenanceBadge } from "@/components/provenance-badge";
import { datasetMeta, examples, formatNumber, type DatasetMeta } from "@/lib/api";
import {
  Search,
  MapPin,
  ShieldCheck,
  ArrowLeft,
  Sparkles,
  Database,
  Store,
  FlaskConical,
  Clock3,
  AlertTriangle,
} from "lucide-react";

export default function HomePage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [starters, setStarters] = useState<string[]>([]);
  const [meta, setMeta] = useState<DatasetMeta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);

  useEffect(() => {
    examples()
      .then((d) => setStarters(d.starters))
      .catch(() => {});
    datasetMeta()
      .then(setMeta)
      .catch(() => setMetaError("دیتاست وارد نشده است"));
  }, []);

  const go = (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    router.push(`/discover?q=${encodeURIComponent(trimmed)}`);
  };

  return (
    <main className="app-bg mx-auto max-w-2xl px-4 pb-16 pt-6">
      {/* برند */}
      <div className="mb-6 text-center">
        <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
          <Store className="h-7 w-7" aria-hidden />
        </div>
        <h1 className="text-xl font-extrabold sm:text-2xl">دستیار خرید حضوری ترب</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          بگو چه می‌خواهی؛ ایجنت خودش محصول را جست‌وجو می‌کند، فروشگاه‌های تهران را با قیمت و
          فاصله می‌آورد، و مسیر خرید حضوری را قدم‌به‌قدم می‌چیند.
        </p>
      </div>

      {/* جست‌وجو */}
      <Card className="border-primary/20 shadow-sm">
        <CardContent className="p-3 sm:p-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              go(query);
            }}
            className="flex gap-2"
          >
            <div className="relative flex-1">
              <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="مثلاً: شارژر اپل ۲۰ وات"
                className="h-11 pr-9 text-sm"
                aria-label="چه محصولی می‌خواهید؟"
              />
            </div>
            <Button type="submit" size="lg" className="h-11 shrink-0 px-4">
              شروع
              <ArrowLeft className="mr-1 h-4 w-4" aria-hidden />
            </Button>
          </form>

          {starters.length > 0 && (
            <div className="mt-3">
              <div className="mb-1.5 flex items-center gap-1 text-[11px] text-muted-foreground">
                <Sparkles className="h-3 w-3" aria-hidden />
                از دسته‌های پرترافیک دیتاست
              </div>
              <div className="flex flex-wrap gap-1.5">
                {starters.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => go(s)}
                    className="rounded-full border bg-background px-2.5 py-1 text-[11px] transition-colors hover:bg-accent"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* چهار مرحله */}
      <div className="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          { icon: Search, title: "کشف نیاز", desc: "سؤال هدفمند", tone: "tone-blue" },
          { icon: Store, title: "یافتن فروشگاه", desc: "بر پایه آفر واقعی", tone: "tone-violet" },
          { icon: MapPin, title: "مسیر خرید", desc: "گام‌به‌گام حضوری", tone: "tone-emerald" },
          { icon: FlaskConical, title: "تأیید", desc: "شفاف و برچسب‌دار", tone: "tone-amber" },
        ].map((s, i) => (
          <div key={i} className={`${s.tone} tone p-2.5 text-center`}>
            <s.icon className="mx-auto mb-1 h-4 w-4 text-primary" aria-hidden />
            <div className="text-[11px] font-semibold">{s.title}</div>
            <div className="text-[10px] text-muted-foreground">{s.desc}</div>
          </div>
        ))}
      </div>

      {/* شفافیت دیتاست */}
      <Card className="tone tone-amber mt-6">
        <CardContent className="p-3 sm:p-4">
          <div className="mb-2 flex items-center gap-1.5">
            <Database className="h-4 w-4" aria-hidden />
            <h2 className="text-sm font-bold">
              این داده‌ها از کجا می‌آید؟
            </h2>
          </div>

          {meta ? (
            <div className="space-y-2 text-[11px] leading-6">
              <div className="flex flex-wrap gap-1.5">
                <ProvenanceBadge tone="neutral">{formatNumber(meta.products_count)} محصول</ProvenanceBadge>
                <ProvenanceBadge tone="neutral">{formatNumber(meta.shops_count)} فروشگاه</ProvenanceBadge>
                <ProvenanceBadge tone="neutral">{formatNumber(meta.offers_count)} آفر</ProvenanceBadge>
              </div>
              <p>{meta.coverage_note}</p>
              <p className="flex items-start gap-1">
                <Clock3 className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                {meta.price_freshness_note}
              </p>
              <p className="flex items-start gap-1">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                {meta.stock_note}
              </p>
              <p className="flex items-start gap-1">
                <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                نام فروشگاه‌ها و شماره‌ها از دیتاست ثبت‌شده‌اند و تأییدنشده‌اند. ما هیچ تماس یا
                پیام واقعی بدون کانال مجاز انجام نمی‌دهیم؛ هر شبیه‌سازی صریحاً «نمایشی» برچسب می‌خورد.
              </p>
            </div>
          ) : (
            <p className="text-[11px]">
              {metaError || "در حال خواندن شناسنامه دیتاست…"}
            </p>
          )}
        </CardContent>
      </Card>

      <div className="mt-6 flex justify-center">
        <Button asChild variant="outline" size="sm" className="text-xs">
          <Link prefetch={false} href="/discover">
            گفت‌وگو با ایجنت
            <ArrowLeft className="mr-1 h-3 w-3" aria-hidden />
          </Link>
        </Button>
      </div>

      <p className="mt-8 text-center text-[10px] leading-5 text-muted-foreground">
        داده‌ها snapshot دیتاست ترب هستند و قیمت زنده نیستند. این ابزار جای تأیید نهایی
        فروشنده را نمی‌گیرد.
      </p>
    </main>
  );
}
