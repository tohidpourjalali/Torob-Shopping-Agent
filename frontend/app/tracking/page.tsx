"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { DemoBadge, ProvenanceBadge } from "@/components/provenance-badge";
import {
  formatDate,
  formatNumber,
  recentVerifications,
  verifyHistory,
  verifyOffer,
  type VerificationRecent,
  type VerificationResponse,
} from "@/lib/api";
import {
  ArrowRight,
  Loader2,
  FlaskConical,
  History,
  ShieldQuestion,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Home,
} from "lucide-react";

const PRICE_LABELS: Record<string, string> = {
  confirmed: "قیمت تأیید شد",
  changed: "قیمت تغییر کرده",
  not_confirmed: "قیمت تأیید نشد",
  no_response: "پاسخی دریافت نشد",
  unknown: "نامشخص",
};

const STOCK_LABELS: Record<string, string> = {
  in_stock: "موجود",
  out_of_stock: "ناموجود",
  no_response: "پاسخی دریافت نشد",
  unknown: "نامشخص",
};

const HOURS_LABELS: Record<string, string> = {
  open: "باز",
  closed: "بسته",
  no_response: "پاسخی دریافت نشد",
  unknown: "نامشخص",
};

function StatusIcon({ status }: { status: string }) {
  if (status === "confirmed" || status === "in_stock" || status === "open")
    return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" aria-hidden />;
  if (status === "out_of_stock" || status === "closed" || status === "changed")
    return <XCircle className="h-3.5 w-3.5 text-rose-600" aria-hidden />;
  return <HelpCircle className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />;
}

function Row({ label, value, map }: { label: string; value: string; map: Record<string, string> }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b py-1 last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="flex items-center gap-1 font-medium">
        <StatusIcon status={value} />
        {map[value] ?? value}
      </span>
    </div>
  );
}

function TrackingInner() {
  const params = useSearchParams();
  const [offerId, setOfferId] = useState(params.get("offer") || "");
  const [current, setCurrent] = useState<VerificationResponse | null>(null);
  const [history, setHistory] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<VerificationRecent[]>([]);
  const [showManual, setShowManual] = useState(false);

  const loadRecent = () =>
    recentVerifications(8)
      .then(setRecent)
      .catch(() => setRecent([]));

  useEffect(() => {
    loadRecent();
  }, []);

  // ورود مستقیم به /tracking?offer=... باید تاریخچه را نشان دهد،
  // بدون اینکه یک رکورد تأیید *جدید* بسازد (ساخت رکورد فقط با دکمه «تأیید»).
  useEffect(() => {
    const id = params.get("offer")?.trim();
    if (!id) return;
    let alive = true;
    setLoading(true);
    verifyHistory(id)
      .then((h) => {
        if (alive) {
          setHistory(h);
          setError(null);
        }
      })
      .catch(() => {
        if (alive) setError("این آفر پیدا نشد یا قابل تأیید نیست.");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async () => {
    if (!offerId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const [v, h] = await Promise.all([
        verifyOffer({ offer_id: offerId.trim(), channel: "demo" }),
        verifyHistory(offerId.trim()).catch(() => []),
      ]);
      setCurrent(v);
      setHistory(h);
      loadRecent();
    } catch {
      setError("این آفر پیدا نشد یا قابل تأیید نیست.");
      setCurrent(null);
      setHistory(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto max-w-2xl px-3 pb-16 pt-3">
      <header className="mb-3 flex items-center justify-between">
        <Button asChild size="sm" variant="ghost" className="h-8 px-2 text-xs">
          <Link prefetch={false} href="/stores">
            <ArrowRight className="ml-1 h-3 w-3" aria-hidden />
            فروشگاه‌ها
          </Link>
        </Button>
        <Button asChild size="sm" variant="ghost" className="h-8 px-2 text-xs">
          <Link prefetch={false} href="/">
            <Home className="h-4 w-4" aria-hidden />
          </Link>
        </Button>
      </header>

      <h1 className="mb-1 flex items-center gap-1.5 text-base font-extrabold">
        <History className="h-5 w-5 text-primary" aria-hidden />
        پیگیری تأیید قیمت و موجودی
      </h1>
      <p className="mb-3 text-[11px] leading-5 text-muted-foreground">
        تاریخچهٔ استعلام‌ها و متن آمادهٔ تماس. تا وقتی پاسخ واقعی فروشنده ثبت نشود،
        قیمت و موجودی تأییدنشده می‌مانند.
      </p>

      {/* استعلام‌های اخیر — بدون نیاز به شناسه */}
      <Card className="mb-3">
        <CardContent className="p-3">
          <h2 className="mb-1.5 flex items-center gap-1 text-[11px] font-bold">
            <History className="h-3.5 w-3.5 text-primary" aria-hidden />
            استعلام‌های اخیر
          </h2>
          {recent.length === 0 ? (
            <p className="text-[10px] leading-5 text-muted-foreground">
              هنوز استعلامی ثبت نشده. از کارت فروشگاه، دکمهٔ «استعلام قیمت و موجودی» را
              بزنید؛ همان‌جا متن آماده و راه‌های تماس ساخته می‌شود.
            </p>
          ) : (
            <ul className="space-y-1">
              {recent.map((r) => (
                <li key={r.id}>
                  <Link prefetch={false}
                    href={`/tracking?offer=${r.offer_id ?? ""}`}
                    className="flex items-center justify-between gap-2 rounded-lg border border-border px-2 py-1.5 text-[10px] hover:border-primary"
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">
                        {r.product_title ?? "محصول نامشخص"}
                      </span>
                      <span className="block truncate text-[9px] text-muted-foreground">
                        {r.shop_name ?? "فروشگاه نامشخص"} · {r.label}
                      </span>
                    </span>
                    <bdi className="shrink-0 text-[9px] text-muted-foreground">
                      {new Date(r.checked_at).toLocaleTimeString("fa-IR")}
                    </bdi>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <button
        type="button"
        onClick={() => setShowManual((v) => !v)}
        className="mb-1 text-[10px] text-muted-foreground underline"
      >
        {showManual ? "بستن" : "شناسهٔ آفر را دستی دارم"}
      </button>

      <Card className={showManual ? "mb-3" : "mb-3 hidden"}>
        <CardContent className="p-3">
          <label className="mb-1 block text-[10px] text-muted-foreground">شناسه آفر</label>
          <div className="flex gap-1.5">
            <Input
              value={offerId}
              onChange={(e) => setOfferId(e.target.value)}
              placeholder="offer_..."
              className="h-9 text-xs"
              dir="ltr"
              aria-label="شناسه آفر"
            />
            <Button size="sm" className="h-9 shrink-0 text-xs" onClick={run} disabled={loading}>
              {loading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <>
                  <FlaskConical className="ml-1 h-3.5 w-3.5" aria-hidden />
                  تأیید
                </>
              )}
            </Button>
          </div>
          <p className="mt-1.5 text-[10px] leading-5 text-muted-foreground">
            این مسیر برای وقتی است که شناسهٔ آفر را از جای دیگری دارید.
          </p>
        </CardContent>
      </Card>

      {error && (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 p-2 text-[11px] text-rose-800 dark:border-rose-900 dark:bg-rose-950/40">
          {error}
        </div>
      )}

      {current && (
        <Card className="mb-3 border-violet-200 dark:border-violet-900">
          <CardContent className="p-3">
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <DemoBadge>{current.label}</DemoBadge>
              <ProvenanceBadge tone="neutral" icon={false}>
                {current.channel}
              </ProvenanceBadge>
              <span className="text-[10px] text-muted-foreground">
                {formatDate(current.checked_at)}
              </span>
            </div>

            <p className="mb-2 rounded-md bg-violet-50 p-2 text-[11px] leading-6 text-violet-900 dark:bg-violet-950/40 dark:text-violet-200">
              {current.note}
            </p>

            <div className="text-[11px]">
              <Row label="قیمت" value={current.price_status} map={PRICE_LABELS} />
              <Row label="موجودی" value={current.stock_status} map={STOCK_LABELS} />
              <Row label="ساعت کاری" value={current.hours_status} map={HOURS_LABELS} />
            </div>

            {current.script.length > 0 && (
              <div className="mt-2">
                <div className="mb-1 text-[11px] font-semibold">
                  اگر خودتان تماس گرفتید، این‌ها را بپرسید:
                </div>
                <ul className="list-disc space-y-0.5 pr-4 text-[11px] leading-6 text-muted-foreground">
                  {current.script.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            )}

            {!current.real_channel_ready && current.real_channel_hint && (
              <div className="mt-2 flex items-start gap-1 rounded-md border border-amber-200 bg-amber-50 p-2 text-[10px] leading-5 text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
                <ShieldQuestion className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                {current.real_channel_hint}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {history && history.length > 0 && (
        <Card>
          <CardContent className="p-3">
            <h2 className="mb-1.5 text-[13px] font-bold">
              تاریخچه تأیید ({formatNumber(history.length)})
            </h2>
            <ul className="space-y-1.5">
              {history.map((h: any) => (
                <li key={h.id} className="rounded-md border p-2 text-[11px]">
                  <div className="flex flex-wrap items-center justify-between gap-1">
                    <span className="flex items-center gap-1">
                      {h.is_simulated ? <DemoBadge>نمایشی</DemoBadge> : <ProvenanceBadge tone="ok">واقعی</ProvenanceBadge>}
                      <span className="text-muted-foreground">{h.channel}</span>
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {formatDate(h.checked_at)}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-muted-foreground">
                    <span>قیمت: {PRICE_LABELS[h.price_status] ?? "نامشخص"}</span>
                    <span>موجودی: {STOCK_LABELS[h.stock_status] ?? "نامشخص"}</span>
                    <span>ساعت: {HOURS_LABELS[h.hours_status] ?? "نامشخص"}</span>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {!current && history !== null && history.length === 0 && (
        <Card>
          <CardContent className="p-4 text-center text-[11px] leading-6 text-muted-foreground">
            هنوز تأییدی برای این آفر ثبت نشده است.
            <br />
            از صفحه فروشگاه‌ها روی «درخواست تأیید قیمت» بزنید یا شناسه آفر را اینجا وارد کنید.
          </CardContent>
        </Card>
      )}

      {loading && !current && history === null && (
        <Card>
          <CardContent className="flex items-center justify-center gap-1 p-4 text-[11px] text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            در حال خواندن تاریخچه تأیید…
          </CardContent>
        </Card>
      )}
    </main>
  );
}

export default function TrackingPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[60dvh] items-center justify-center text-sm text-muted-foreground">
          <Loader2 className="ml-2 h-4 w-4 animate-spin" aria-hidden />
          در حال بارگذاری…
        </div>
      }
    >
      <TrackingInner />
    </Suspense>
  );
}
