"use client";

/**
 * «مسیریابی» — انتخابی که واقعاً به مقصد می‌رسد.
 *
 * باگی که کاربر گزارش کرد: «گزینه را می‌زنم، هیچ اتفاقی نمی‌افتد».
 * علت: لینک‌ها `target="_blank"` بودند. داخل iframe سندباکس‌شده (پیش‌نمایش،
 * وب‌ویو اپ‌ها) مرورگر باز کردن پنجرهٔ جدید را مسدود می‌کند و لینک **بی‌صدا**
 * هیچ کاری نمی‌کند؛ شیت هم بلافاصله بسته می‌شد، پس تنها بازخوردِ کاربر
 * «بسته شدن» بود.
 *
 * راه‌حل سه‌لایه:
 *   ۱) کلیک با `window.open` انجام می‌شود تا بتوانیم `null` (مسدود) را تشخیص دهیم
 *   ۲) اگر مسدود شد، شیت باز می‌ماند و **QR همان لینک** نشان داده می‌شود
 *      (سرور خودمان می‌سازد، پس بدون دسترسی به اینترنت هم کار می‌کند)
 *   ۳) کپی لینک + مختصات قابل انتخاب، برای وقتی که کاربر روی دسکتاپ است
 */

import { useState } from "react";
import {
  Navigation,
  X,
  Copy,
  Check,
  AlertTriangle,
  QrCode,
  Smartphone,
  Link2,
} from "lucide-react";
import {
  coordsText,
  directionOptions,
  frameBlockReason,
  tryOpenExternal,
  type LatLon,
} from "@/lib/geo";
import { cn } from "@/lib/utils";

export function DirectionsButton({
  dest,
  origin,
  label,
  className,
  size = "sm",
}: {
  dest: LatLon;
  origin?: LatLon | null;
  label?: string;
  className?: string;
  size?: "sm" | "xs";
}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState<"none" | "link" | "coords">("none");
  /** لینکی که مرورگر اجازهٔ باز کردنش را نداد */
  const [blocked, setBlocked] = useState<string | null>(null);
  /** لینکی که کاربر برای دیدن QR انتخاب کرده */
  const [qrFor, setQrFor] = useState<string | null>(null);

  const framed = frameBlockReason() === "iframe";
  const options = directionOptions(dest, origin);

  const copy = async (value: string, kind: "link" | "coords") => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(kind);
      setTimeout(() => setCopied("none"), 2000);
    } catch {
      /* clipboard در قاب ممکن نیست؛ متن قابل انتخاب است */
    }
  };

  const choose = (href: string) => {
    const ok = tryOpenExternal(href);
    if (ok) {
      setOpen(false);
      setBlocked(null);
      return;
    }
    // مسدود شد: هیچ‌چیز را نمی‌بندیم، جایگزین نشان می‌دهیم
    setBlocked(href);
    void copy(href, "link");
  };

  const qrSrc = (href: string) => `/api/qr?data=${encodeURIComponent(href)}&scale=6`;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "inline-flex items-center gap-1 rounded-lg bg-primary font-bold text-primary-foreground",
          size === "xs" ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-1 text-[10px]",
          className,
        )}
      >
        <Navigation className={size === "xs" ? "h-2.5 w-2.5" : "h-3 w-3"} aria-hidden />
        مسیریابی
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-3 backdrop-blur-[2px]"
          role="dialog"
          aria-modal="true"
          aria-label="انتخاب سرویس مسیریابی"
          onClick={() => setOpen(false)}
        >
          <div
            className="max-h-[85dvh] w-full max-w-md overflow-y-auto rounded-2xl border border-border bg-card p-3 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-1 flex items-center justify-between">
              <h3 className="text-[12px] font-extrabold">مسیریابی {label ? `— ${label}` : ""}</h3>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="بستن"
                className="rounded-md p-1 text-muted-foreground"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>

            <p className="mb-2 text-[10px] leading-4 text-muted-foreground">
              مقصد: <bdi dir="ltr">{coordsText(dest)}</bdi>
            </p>

            {/* --- حالت مسدود --- */}
            {blocked && (
              <div className="mb-2 rounded-xl border border-amber-300 bg-amber-50 p-2 dark:border-amber-800 dark:bg-amber-950/40">
                <p className="flex items-start gap-1 text-[10px] font-bold leading-5 text-amber-900 dark:text-amber-100">
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
                  این مرورگر باز کردن پنجرهٔ جدید را مسدود کرد؛ به همین دلیل «هیچ اتفاقی
                  نیفتاد». دو راه کارساز:
                </p>

                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => copy(blocked, "link")}
                    className="inline-flex items-center gap-1 rounded-lg bg-primary px-2 py-1 text-[10px] font-bold text-primary-foreground"
                  >
                    {copied === "link" ? (
                      <Check className="h-3 w-3" aria-hidden />
                    ) : (
                      <Copy className="h-3 w-3" aria-hidden />
                    )}
                    {copied === "link" ? "لینک کپی شد" : "کپی لینک"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setQrFor(blocked)}
                    className="inline-flex items-center gap-1 rounded-lg border border-amber-400/70 bg-background/70 px-2 py-1 text-[10px] font-semibold text-amber-900 dark:text-amber-100"
                  >
                    <QrCode className="h-3 w-3" aria-hidden />
                    نمایش QR برای گوشی
                  </button>
                </div>

                <input
                  readOnly
                  value={blocked}
                  dir="ltr"
                  onFocus={(e) => e.currentTarget.select()}
                  aria-label="لینک مسیریابی"
                  className="mt-1.5 w-full rounded-md border border-amber-300/70 bg-background/80 px-1.5 py-1 font-mono text-[9px] dark:border-amber-800"
                />
                <p className="mt-1 text-[9px] leading-4 text-amber-900/90 dark:text-amber-100/90">
                  لینک را در یک تب مرورگر بچسبانید، یا QR را با دوربین گوشی اسکن کنید تا
                  مسیریابی روی گوشی باز شود.
                </p>
              </div>
            )}

            {/* --- QR --- */}
            {qrFor && (
              <div className="mb-2 flex flex-col items-center gap-1 rounded-xl border border-border bg-background/70 p-2">
                <span className="flex items-center gap-1 text-[10px] font-bold">
                  <Smartphone className="h-3 w-3 text-primary" aria-hidden />
                  با دوربین گوشی اسکن کنید
                </span>
                {/* تصویر از سرور خودمان ساخته می‌شود؛ به اینترنت نیاز ندارد */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={qrSrc(qrFor)}
                  alt="کد QR لینک مسیریابی"
                  className="h-40 w-40 rounded-lg bg-white p-1"
                  width={160}
                  height={160}
                />
                <button
                  type="button"
                  onClick={() => setQrFor(null)}
                  className="text-[9px] text-muted-foreground underline"
                >
                  بستن QR
                </button>
              </div>
            )}

            {framed && !blocked && (
              <p className="mb-2 flex items-start gap-1 rounded-lg border border-amber-300/70 bg-amber-50 p-1.5 text-[9px] leading-4 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                <AlertTriangle className="mt-0.5 h-2.5 w-2.5 shrink-0" aria-hidden />
                این صفحه داخل قاب نمایش داده می‌شود؛ ممکن است مرورگر باز کردن نقشه را
                مسدود کند. اگر باز نشد، همین‌جا QR و «کپی لینک» را می‌بینید.
              </p>
            )}

            {/* --- گزینه‌ها --- */}
            <div className="grid gap-1.5">
              {options.map((o) => (
                <div
                  key={o.key}
                  className="flex items-center gap-1 rounded-xl border border-border bg-background/70 hover:border-primary"
                >
                  <button
                    type="button"
                    onClick={() => choose(o.href)}
                    className="flex min-w-0 flex-1 items-center justify-between gap-2 px-2.5 py-2 text-right text-[11px]"
                  >
                    <span className="flex items-center gap-1.5">
                      <Navigation className="h-3.5 w-3.5 text-primary" aria-hidden />
                      <span className="font-semibold">{o.label}</span>
                    </span>
                    <span className="shrink-0 text-[9px] text-muted-foreground">{o.hint}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setQrFor(qrFor === o.href ? null : o.href)}
                    aria-label={`QR برای ${o.label}`}
                    title="QR برای گوشی"
                    className="m-1 rounded-md border border-border p-1 text-muted-foreground"
                  >
                    <QrCode className="h-3 w-3" aria-hidden />
                  </button>
                </div>
              ))}
            </div>

            <div className="mt-2 flex gap-1.5">
              <button
                type="button"
                onClick={() => copy(coordsText(dest), "coords")}
                className="flex flex-1 items-center justify-center gap-1 rounded-xl border border-dashed border-border px-2 py-1.5 text-[10px]"
              >
                {copied === "coords" ? (
                  <Check className="h-3 w-3" aria-hidden />
                ) : (
                  <Copy className="h-3 w-3" aria-hidden />
                )}
                {copied === "coords" ? "مختصات کپی شد" : "کپی مختصات"}
              </button>
              <button
                type="button"
                onClick={() => copy(options[0].href, "link")}
                className="flex flex-1 items-center justify-center gap-1 rounded-xl border border-dashed border-border px-2 py-1.5 text-[10px]"
              >
                <Link2 className="h-3 w-3" aria-hidden />
                {copied === "link" ? "کپی شد" : "کپی لینک مسیر"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
