"use client";

/**
 * «ردیابی ابزار» — شفافیت ایجنت.
 *
 * این بخش چیزی است که پروژه را از «نمایش قیمت» جدا می‌کند: کاربر می‌بیند ایجنت
 * در این نوبت کدام ابزارها را با چه پارامترهایی صدا زده، هر کدام چه برگردانده و
 * چقدر طول کشیده. هیچ‌کدام از این خطوط از پیش نوشته نشده‌اند.
 */

import { useState } from "react";
import { ChevronDown, Wrench, CheckCircle2, XCircle, Cpu, Braces } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatNumber, type ToolCallTrace } from "@/lib/api";

function Args({ args }: { args: Record<string, unknown> }) {
  const entries = Object.entries(args ?? {}).filter(([, v]) => v !== null && v !== undefined);
  if (!entries.length) return null;
  return (
    <div className="mt-1 flex flex-wrap gap-1" dir="rtl">
      {entries.map(([k, v]) => (
        <span
          key={k}
          className="rounded border border-border/70 bg-background/60 px-1 py-0.5 font-mono text-[9px] text-muted-foreground"
          dir="ltr"
        >
          {k}={String(v).slice(0, 24)}
        </span>
      ))}
    </div>
  );
}

export function ToolTrace({
  calls,
  engine,
  modelLabel,
}: {
  calls: ToolCallTrace[];
  engine: "llm" | "deterministic";
  modelLabel: string;
}) {
  const [open, setOpen] = useState(false);

  if (!calls?.length && !engine) return null;

  return (
    <div className="tone tone-slate overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-2.5 py-1.5 text-right"
        aria-expanded={open}
      >
        <span className="flex min-w-0 items-center gap-1.5">
          <Wrench className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="text-[11px] font-bold">
            ایجنت {formatNumber(calls.length)} ابزار صدا زد
          </span>
          <span
            className={cn(
              "flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[9px]",
              engine === "llm"
                ? "bg-primary/15 text-primary"
                : "bg-background/70 text-muted-foreground",
            )}
            title={modelLabel}
          >
            {engine === "llm" ? <Cpu className="h-2.5 w-2.5" aria-hidden /> : <Braces className="h-2.5 w-2.5" aria-hidden />}
            {engine === "llm" ? "مدل زبانی" : "برنامه‌ریز قطعی"}
          </span>
        </span>
        <ChevronDown
          className={cn("h-3.5 w-3.5 shrink-0 transition-transform", open && "rotate-180")}
          aria-hidden
        />
      </button>

      {open && (
        <ol className="space-y-1 border-t border-border/60 px-2.5 py-2">
          {calls.map((c) => (
            <li key={`${c.index}-${c.tool}`} className="flex items-start gap-1.5">
              {c.ok ? (
                <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
              ) : (
                <XCircle className="mt-0.5 h-3 w-3 shrink-0 text-rose-600 dark:text-rose-400" aria-hidden />
              )}
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-semibold">{c.title}</span>
                  <span className="shrink-0 font-mono text-[9px] text-muted-foreground" dir="ltr">
                    {c.tool} · {formatNumber(c.duration_ms)}ms
                  </span>
                </div>
                <p className="text-[10px] leading-4 text-muted-foreground">{c.summary}</p>
                <Args args={c.arguments} />
              </div>
            </li>
          ))}
          {!calls.length && (
            <li className="text-[10px] text-muted-foreground">در این نوبت ابزاری صدا زده نشد.</li>
          )}
        </ol>
      )}
    </div>
  );
}
