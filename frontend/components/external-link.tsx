"use client";

/**
 * لینک بیرونی که هرگز بی‌صدا شکست نمی‌خورد.
 *
 * داخل iframe سندباکس‌شده (پیش‌نمایش، وب‌ویو اپ) `target="_blank"` مسدود
 * می‌شود و کاربر فقط «هیچ اتفاقی نیفتاد» می‌بیند. این کامپوننت:
 *   ۱) کلیک را خودش مدیریت می‌کند و تلاش می‌کند پنجره را باز کند
 *   ۲) اگر مسدود شد، لینک را کپی می‌کند و پیام روشن نشان می‌دهد
 */

import { useState } from "react";
import { cn } from "@/lib/utils";
import { tryOpenExternal } from "@/lib/geo";
import { ExternalLink as ExternalIcon, Copy, Check, AlertTriangle } from "lucide-react";

export function ExternalLink({
  href,
  children,
  className,
  showIcon = true,
  title,
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
  showIcon?: boolean;
  title?: string;
}) {
  const [state, setState] = useState<"idle" | "blocked" | "copied">("idle");

  return (
    <span className="inline-flex flex-col gap-0.5">
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        title={title}
        onClick={(e) => {
          // در مرورگر عادی همان رفتار لینک را نگه می‌داریم، ولی چون ممکن است
          // مسدود شود، خودمان باز می‌کنیم تا بتوانیم شکست را تشخیص دهیم.
          e.preventDefault();
          if (tryOpenExternal(href)) {
            setState("idle");
            return;
          }
          setState("blocked");
          navigator.clipboard?.writeText(href).then(
            () => setState("copied"),
            () => setState("blocked"),
          );
        }}
        className={cn("inline-flex items-center gap-1", className)}
      >
        {showIcon && <ExternalIcon className="h-2.5 w-2.5" aria-hidden />}
        {children}
      </a>

      {(state === "blocked" || state === "copied") && (
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-md border px-1 py-0.5 text-[8px] leading-4",
            state === "copied"
              ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200"
              : "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200",
          )}
        >
          {state === "copied" ? (
            <>
              <Check className="h-2 w-2 shrink-0" aria-hidden />
              باز نشد (مرورگر پنجرهٔ جدید را مسدود کرد) — لینک کپی شد، در مرورگر بچسبانید
            </>
          ) : (
            <>
              <AlertTriangle className="h-2 w-2 shrink-0" aria-hidden />
              باز نشد؛ لینک: <bdi dir="ltr">{href.slice(0, 42)}…</bdi>
              <Copy className="h-2 w-2 shrink-0" aria-hidden />
            </>
          )}
        </span>
      )}
    </span>
  );
}
