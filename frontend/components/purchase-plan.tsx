"use client";

/**
 * نقشهٔ خرید حضوری — قلب محصول.
 *
 * هر گام یا از دیتاست آمده (`source: "dataset"`) یا راهنمای عمومی خرید است
 * (`source: "guide"`). این تفکیک روی خود کارت نشان داده می‌شود، نه در مستندات.
 */

import { useState } from "react";
import {
  MapPin,
  PhoneCall,
  ClipboardCheck,
  Route,
  Wallet,
  Repeat,
  Clock,
  ShieldAlert,
  ShieldCheck,
  Copy,
  Check,
  Navigation,
  ShieldQuestion,
} from "lucide-react";
import { cn, telHref, toLatinDigits } from "@/lib/utils";
import { DirectionsButton } from "@/components/directions-sheet";
import { ExternalLink } from "@/components/external-link";
import type { PurchasePlan, PurchasePlanStep } from "@/lib/api";

const ICONS: Record<string, any> = {
  verify: PhoneCall,
  route: Route,
  ask: ClipboardCheck,
  inspect: ClipboardCheck,
  pay: Wallet,
  fallback: Repeat,
  hours: Clock,
  define: ClipboardCheck,
  benchmark: Wallet,
  shortlist: MapPin,
  call: PhoneCall,
  action: MapPin,
  dataset: MapPin,
};

const TONE: Record<string, string> = {
  verify: "tone-amber",
  call: "tone-amber",
  route: "tone-blue",
  shortlist: "tone-blue",
  dataset: "tone-blue",
  ask: "tone-violet",
  define: "tone-violet",
  inspect: "tone-emerald",
  benchmark: "tone-slate",
  pay: "tone-slate",
  fallback: "tone-rose",
  hours: "tone-slate",
  action: "tone-slate",
};

function StepCard({ step, index }: { step: PurchasePlanStep; index: number }) {
  const Icon = ICONS[step.kind] ?? MapPin;
  return (
    <li className={cn("tone p-2.5", TONE[step.kind] ?? "tone-slate")}>
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-background/70 text-[10px] font-extrabold">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1">
            <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
            <h4 className="text-[12px] font-extrabold">{step.title}</h4>
            <span
              className={cn(
                "rounded px-1 py-px text-[8px] font-semibold",
                step.source === "dataset"
                  ? "bg-primary/15 text-primary"
                  : "bg-background/70 text-muted-foreground",
              )}
            >
              {step.source === "dataset" ? "از دیتاست" : "راهنمای عمومی"}
            </span>
          </div>
          <p className="mt-1 text-[11px] leading-5">{step.detail}</p>
        </div>
      </div>
    </li>
  );
}

function CopyPhone({ phone, note }: { phone?: string | null; note?: string | null }) {
  const [copied, setCopied] = useState(false);
  const [revealed, setRevealed] = useState(false);

  if (!phone) return null;

  return (
    <div className="tone tone-amber mt-1.5 p-2">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1 text-[10px] font-bold">
          <PhoneCall className="h-3 w-3" aria-hidden />
          تماس با فروشنده
        </span>
        <button
          type="button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(toLatinDigits(phone));
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            } catch {
              setRevealed(true);
            }
          }}
          className="flex items-center gap-1 rounded-md border border-amber-300/70 bg-background/70 px-1.5 py-0.5 text-[9px] hover:bg-background dark:border-amber-800"
        >
          {copied ? <Check className="h-2.5 w-2.5" aria-hidden /> : <Copy className="h-2.5 w-2.5" aria-hidden />}
          {copied ? "کپی شد" : "کپی شماره"}
        </button>
      </div>
      <div className="mt-1 flex items-center gap-1.5">
        <bdi dir="ltr" className="font-mono text-[13px] font-bold tracking-wide">
          {phone}
        </bdi>
      </div>
      <p className="mt-0.5 text-[9px] leading-4 opacity-90">
        {note || "این شماره از دیتاست آمده و تأیید نشده است؛ پیش از اعتماد، خودتان راستی‌آزمایی کنید."}
      </p>
      {!revealed ? (
        <button
          type="button"
          onClick={() => setRevealed(true)}
          className="mt-1 rounded-md bg-primary px-2 py-1 text-[10px] font-bold text-primary-foreground"
        >
          نمایش دکمهٔ تماس
        </button>
      ) : (
        <a
          href={telHref(phone) || "#"}
          className="mt-1 inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-[10px] font-bold text-primary-foreground"
        >
          <PhoneCall className="h-3 w-3" aria-hidden />
          تماس با فروشنده
        </a>
      )}
    </div>
  );
}

export function PurchasePlanCard({
  plan,
  origin,
}: {
  plan: PurchasePlan;
  origin?: { lat: number; lon: number } | null;
}) {
  const [showChecklist, setShowChecklist] = useState(false);
  const notFound = plan.dataset_status === "not_in_dataset";

  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
      <header className={cn("px-3 py-2.5", notFound ? "tone-amber border-0 border-b" : "tone-blue border-0 border-b")}>
        <h3 className="text-[13px] font-extrabold leading-6">{plan.headline}</h3>
        <p className="mt-0.5 text-[10px] leading-4 opacity-90">
          {notFound
            ? "این کالا در دیتاست نیست؛ آدرس و قیمتی برایش ساخته نشده — فقط مسیر خرید حضوری."
            : plan.dataset_status === "no_nearby_store"
              ? "محصول در دیتاست هست، ولی در شعاع انتخابی آفری نداشت."
              : "از دادهٔ واقعی دیتاست + راهنمای عمومی خرید ساخته شده است."}
        </p>
      </header>

      <ol className="space-y-1.5 p-2.5">
        {plan.steps.map((step, i) => (
          <StepCard key={`${step.title}-${i}`} step={step} index={i} />
        ))}
      </ol>

      {plan.contact?.phone_display && (
        <div className="px-2.5 pb-2.5">
          <CopyPhone phone={plan.contact.phone_display} note={plan.contact.phone_note} />
        </div>
      )}

      <div className="flex flex-wrap gap-1.5 border-t border-border px-2.5 py-2">
        {plan.contact?.lat != null && plan.contact?.lon != null && (
          <DirectionsButton
            dest={{ lat: plan.contact.lat as number, lon: plan.contact.lon as number }}
            origin={origin ?? null}
            label={String(plan.shop?.name ?? "")}
          />
        )}
        {plan.contact?.website_url && (
          <ExternalLink
            href={plan.contact.website_url}
            className="rounded-lg border border-border px-2 py-1 text-[10px]"
          >
            سایت فروشگاه
          </ExternalLink>
        )}
        {plan.contact?.instagram && (
          <ExternalLink
            href={`https://instagram.com/${String(plan.contact.instagram).replace(/^@/, "")}`}
            className="rounded-lg border border-border px-2 py-1 text-[10px]"
          >
            اینستاگرام
          </ExternalLink>
        )}
        <button
          type="button"
          onClick={() => setShowChecklist((v) => !v)}
          className="inline-flex items-center gap-1 rounded-lg border border-border px-2 py-1 text-[10px]"
          aria-expanded={showChecklist}
        >
          <ClipboardCheck className="h-3 w-3" aria-hidden />
          چک‌لیست بازرسی
        </button>
      </div>

      {showChecklist && (
        <div className="tone tone-emerald mx-2.5 mb-2.5 p-2">
          <p className="mb-1 text-[10px] font-bold">در فروشگاه این‌ها را چک کنید</p>
          <ul className="list-inside list-disc space-y-1 text-[10px] leading-5">
            {plan.checklist.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {plan.transparency?.length > 0 && (
        <details className="border-t border-border bg-muted/30 px-2.5 py-1.5">
          <summary className="flex cursor-pointer items-center gap-1 text-[9px] leading-4 text-muted-foreground">
            <ShieldQuestion className="h-2.5 w-2.5 shrink-0" aria-hidden />
            این نقشه بر چه پایه‌ای ساخته شده؟
          </summary>
          <div className="mt-1 space-y-0.5">
            {plan.transparency.map((t, i) => (
              <p key={i} className="flex items-start gap-1 text-[9px] leading-4 text-muted-foreground">
                <ShieldAlert className="mt-0.5 h-2.5 w-2.5 shrink-0" aria-hidden />
                {t}
              </p>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}
