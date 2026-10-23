"use client";

/**
 * تصویر محصول.
 *
 * وضعیت واقعی: تصاویر از `image.torob.com` می‌آیند و این دامنه از محیط اجرا
 * (sandbox/پیش‌نمایش بدون شبکه) قابل دسترسی نیست. بنابراین دو چیز لازم است:
 *   ۱) اگر تصویر رسید، دقیق و بدون کشیدگی نمایش داده شود (`object-contain`،
 *      نسبت ابعاد حفظ می‌شود، پیش‌بارگذاری تنبل).
 *   ۲) اگر نرسید، جای‌گزین **صادق و ثابت** نمایش داده شود — نه عکس ساختگی و نه
 *      مستطیل خالی. برای هر محصول یک رنگ/حرف ثابت از شناسه ساخته می‌شود تا
 *      کارت‌ها از هم قابل تفکیک باشند، و برچسب می‌گوید تصویر بارگذاری نشده.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { ImageOff, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

const TONES = [
  "from-sky-100 to-sky-50 dark:from-sky-950/60 dark:to-sky-900/30",
  "from-violet-100 to-violet-50 dark:from-violet-950/60 dark:to-violet-900/30",
  "from-emerald-100 to-emerald-50 dark:from-emerald-950/60 dark:to-emerald-900/30",
  "from-amber-100 to-amber-50 dark:from-amber-950/60 dark:to-amber-900/30",
  "from-rose-100 to-rose-50 dark:from-rose-950/60 dark:to-rose-900/30",
  "from-slate-100 to-slate-50 dark:from-slate-900/60 dark:to-slate-800/30",
];

function hash(text: string): number {
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) >>> 0;
  return h;
}

export function ProductImage({
  src,
  alt,
  className,
  imgClassName,
  seed,
  timeoutMs = 6000,
  showRetry = true,
}: {
  src?: string | null;
  alt?: string;
  className?: string;
  imgClassName?: string;
  seed?: string;
  timeoutMs?: number;
  showRetry?: boolean;
}) {
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(!src);
  const [attempt, setAttempt] = useState(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const key = seed || alt || src || "product";
  const tone = TONES[hash(key) % TONES.length];
  const initials = useMemo(() => {
    const words = (alt || "").trim().split(/\s+/).filter(Boolean);
    if (!words.length) return "؟";
    return words
      .slice(0, 2)
      .map((w) => Array.from(w)[0])
      .join("");
  }, [alt]);

  useEffect(() => {
    setReady(false);
    setFailed(!src);
    if (!src) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setFailed(true), timeoutMs);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [src, timeoutMs, attempt]);

  const imageUrl = src ? (attempt === 0 ? src : `${src}${src.includes("?") ? "&" : "?"}r=${attempt}`) : null;

  return (
    <div
      className={cn(
        "relative flex items-center justify-center overflow-hidden rounded-lg border border-border/50",
        className,
      )}
    >
      {/* جای‌گزین ثابت — همیشه هست تا هیچ‌وقت مستطیل خالی دیده نشود */}
      <div
        className={cn(
          "absolute inset-0 flex flex-col items-center justify-center gap-0.5 bg-gradient-to-br",
          tone,
        )}
      >
        <span className="text-[15px] font-extrabold opacity-70">{initials}</span>
        <span className="flex items-center gap-0.5 text-[8px] leading-3 text-muted-foreground">
          <ImageOff className="h-2.5 w-2.5" aria-hidden />
          بدون تصویر
        </span>
      </div>

      {imageUrl && !failed && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={imageUrl}
          src={imageUrl}
          alt={alt || "تصویر محصول"}
          className={cn(
            "relative h-full w-full object-contain transition-opacity duration-300",
            ready ? "opacity-100" : "opacity-0",
            imgClassName,
          )}
          loading="lazy"
          decoding="async"
          // دامنهٔ تصویر hotlink protection دارد؛ بدون referrer قابل‌اعتمادتر است
          referrerPolicy="no-referrer"
          onLoad={() => {
            setReady(true);
            setFailed(false);
            if (timerRef.current) clearTimeout(timerRef.current);
          }}
          onError={() => {
            if (attempt < 1) setAttempt((a) => a + 1);
            else setFailed(true);
          }}
        />
      )}

      {failed && showRetry && src && (
        <button
          type="button"
          onClick={() => {
            setFailed(false);
            setAttempt((a) => a + 1);
          }}
          className="absolute bottom-0.5 left-0.5 rounded bg-background/85 p-0.5 text-muted-foreground shadow-sm"
          aria-label="تلاش دوباره برای بارگذاری تصویر"
          title="تصویر بارگذاری نشد — تلاش دوباره"
        >
          <RefreshCw className="h-2.5 w-2.5" aria-hidden />
        </button>
      )}
    </div>
  );
}
