"use client";

/**
 * کارت فروشگاه حضوری.
 *
 * بازطراحی این دور: اطلاعات کم‌اهمیت یا تکراری از نگاه اول حذف شد
 * (برچسب «نام تأییدنشده» و «قیمت تأییدنشده» روی هر کارت، موجودی نامشخص،
 * شمارهٔ تأییدنشده در ردیف دکمه‌ها، دلایل رتبه). حالا:
 *   • نگاه اول: نام، فاصله، محله، قیمت، ساعت کاری (اگر داده باشد)، دکمه‌ها
 *   • جزئیات (بازشدنی): پرداخت/گارانتی، امتیاز، تماس، داده‌های خام
 *   • شفافیت در یک خط در سطح فهرست (نه روی هر کارت)
 */

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import {
  OpenBadge,
} from "@/components/provenance-badge";
import {
  faDecimal,
  formatCompactToman,
  formatNumber,
  type StoreOffer,
} from "@/lib/api";
import { telHref, toLatinDigits } from "@/lib/utils";
import { DirectionsButton } from "@/components/directions-sheet";
import { ExternalLink } from "@/components/external-link";
import { VerificationPanel } from "@/components/verification-panel";
import {
  MapPin,
  Navigation,
  CreditCard,
  Phone,
  ShieldCheck,
  ChevronDown,
  Copy,
  Check,
} from "lucide-react";

const BREAKDOWN_LABELS: Record<string, string> = {
  price: "قیمت",
  distance: "فاصله",
  hours: "ساعت کاری",
  payment: "پرداخت",
  trust: "کامل‌بودن داده",
};

export function StoreCard({
  offer,
  rank,
  selected,
  onToggleSelect,
  origin,
}: {
  offer: StoreOffer;
  rank?: number;
  selected?: boolean;
  onToggleSelect?: (offerId: string) => void;
  /** موقعیت کاربر — برای مسیریابی از مبدأ خودش */
  origin?: { lat: number; lon: number } | null;
}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const shop = offer.shop;
  const hasCoords = shop.lat != null && shop.lon != null;
  const pay = offer.payment;
  const payChips: string[] = [];
  if (pay.in_person_torob) payChips.push("پذیرش حضوری ترب");
  if (pay.installment) payChips.push("اقساط");
  if (pay.credit) payChips.push("اعتبار خرید");

  return (
    <Card className={selected ? "ring-2 ring-primary" : undefined}>
      <CardContent className="p-3">
        {/* سر کارت */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              {rank != null && (
                <span className="rounded-md bg-primary px-1.5 py-0.5 text-[10px] font-bold text-primary-foreground">
                  {formatNumber(rank)}
                </span>
              )}
              <h3 className="truncate text-[13px] font-bold">{shop.name || "فروشگاه بدون نام"}</h3>
            </div>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-muted-foreground">
              {shop.location_label && (
                <span className="inline-flex items-center gap-0.5">
                  <MapPin className="h-2.5 w-2.5" aria-hidden />
                  {shop.location_label}
                </span>
              )}
              {shop.distance_km != null && (
                <span className="inline-flex items-center gap-0.5 font-semibold text-foreground">
                  <Navigation className="h-2.5 w-2.5" aria-hidden />
                  {faDecimal(shop.distance_km, 1)} کیلومتر
                </span>
              )}
              {offer.hours.has_data && <OpenBadge isOpen={offer.hours.is_open_now} />}
            </div>
          </div>

          {onToggleSelect && (
            <label className="flex shrink-0 cursor-pointer items-center gap-1 text-[10px] text-muted-foreground">
              <input
                type="checkbox"
                checked={!!selected}
                onChange={() => onToggleSelect(offer.offer_id)}
                className="h-3.5 w-3.5 accent-primary"
              />
              مقایسه
            </label>
          )}
        </div>

        {/* قیمت — یک عدد درشت، بدون برچسب تکراری */}
        <div className="mt-2">
          <div className="text-[15px] font-extrabold text-primary">
            {offer.price.value_toman != null
              ? formatCompactToman(offer.price.value_toman)
              : "قیمت ثبت نشده"}
          </div>
          <div className="text-[9px] text-muted-foreground">قیمت ثبت‌شده در دیتاست</div>
        </div>

        {(offer.warranty || payChips.length > 0) && (
          <div className="mt-1 flex flex-wrap gap-1">
            {offer.warranty && (
              <span className="inline-flex items-center gap-0.5 rounded-md border border-border bg-muted px-1.5 py-0.5 text-[9px]">
                <ShieldCheck className="h-2.5 w-2.5" aria-hidden />
                گارانتی
              </span>
            )}
            {payChips.map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-0.5 rounded-md border border-border bg-muted px-1.5 py-0.5 text-[9px]"
              >
                <CreditCard className="h-2.5 w-2.5" aria-hidden />
                {c}
              </span>
            ))}
          </div>
        )}

        {/* اقدام‌ها */}
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {hasCoords && (
            <DirectionsButton
              dest={{ lat: shop.lat as number, lon: shop.lon as number }}
              origin={origin ?? null}
              label={shop.name ?? undefined}
            />
          )}
          <VerificationPanel offer={offer} />
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="inline-flex items-center gap-0.5 rounded-lg border border-border px-2 py-1 text-[10px]"
          >
            <ChevronDown className={"h-3 w-3 transition-transform " + (open ? "rotate-180" : "")} aria-hidden />
            {open ? "بستن" : "جزئیات"}
          </button>
        </div>

        {open && (
          <div className="mt-2 space-y-2 border-t pt-2 text-[10px]">
            {/* تماس */}
            <div className="tone tone-emerald rounded-lg border p-2">
              <div className="mb-1 flex items-center gap-1 font-semibold">
                <Phone className="h-3 w-3" aria-hidden /> تماس با فروشگاه
              </div>
              {shop.phone_display ? (
                <div className="flex flex-wrap items-center gap-1.5">
                  <bdi dir="ltr" className="rounded bg-background/70 px-1.5 py-0.5 font-mono text-[12px] font-bold tabular-nums">
                    {shop.phone_display}
                  </bdi>
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(toLatinDigits(shop.phone_display || ""));
                        setCopied(true);
                        setTimeout(() => setCopied(false), 1500);
                      } catch {
                        /* clipboard در قاب ممکن نیست */
                      }
                    }}
                    className="inline-flex items-center gap-0.5 rounded-md border border-border bg-background/70 px-1.5 py-0.5 text-[9px]"
                  >
                    {copied ? <Check className="h-2.5 w-2.5" aria-hidden /> : <Copy className="h-2.5 w-2.5" aria-hidden />}
                    {copied ? "کپی شد" : "کپی"}
                  </button>
                  <a
                    href={telHref(shop.phone_display) ?? "#"}
                    className="inline-flex items-center gap-0.5 rounded-md bg-primary px-1.5 py-0.5 text-[9px] font-bold text-primary-foreground"
                  >
                    <Phone className="h-2.5 w-2.5" aria-hidden /> تماس
                  </a>
                </div>
              ) : (
                <p className="text-[9px] leading-4 opacity-90">
                  دیتاست شماره‌ای برای این فروشگاه ندارد؛ از مسیریابی یا سایت فروشگاه استفاده کنید.
                </p>
              )}
              <div className="mt-1 flex flex-wrap gap-1">
                {shop.instagram && (
                  <ExternalLink
                    href={`https://instagram.com/${String(shop.instagram).replace(/^@/, "")}`}
                    className="rounded-md border border-border bg-background/70 px-1.5 py-0.5 text-[9px]"
                  >
                    اینستاگرام
                  </ExternalLink>
                )}
                {shop.website_url && (
                  <ExternalLink
                    href={shop.website_url}
                    className="rounded-md border border-border bg-background/70 px-1.5 py-0.5 text-[9px]"
                  >
                    سایت
                  </ExternalLink>
                )}
              </div>
              {shop.address && (
                <p className="mt-1 text-[9px] leading-4 opacity-80">{shop.address}</p>
              )}
            </div>

            {/* ساعت کاری */}
            {offer.hours.has_data && (
              <div className="rounded-lg border border-border p-2">
                <div className="font-semibold">{offer.hours.status_label}</div>
                {offer.hours.today && <div className="opacity-80">امروز: {offer.hours.today}</div>}
                {offer.hours.next_change && <div className="opacity-80">{offer.hours.next_change}</div>}
              </div>
            )}

            {/* پرداخت */}
            {pay.has_data && (
              <div className="rounded-lg border border-border p-2">
                <div className="flex items-center gap-1 font-semibold">
                  <CreditCard className="h-3 w-3" aria-hidden /> پرداخت: {pay.status_label}
                </div>
                {pay.methods.length > 0 && (
                  <div className="mt-0.5 opacity-80">
                    {pay.methods.map((m) => m.label).join(" · ")}
                  </div>
                )}
              </div>
            )}

            {/* امتیاز */}
            {Object.keys(offer.score_breakdown).length > 0 && (
              <div className="rounded-lg border border-border p-2">
                <div className="mb-1 font-semibold">
                  امتیاز تطابق: {offer.score != null ? faDecimal(offer.score, 2) : "—"}
                </div>
                {Object.entries(offer.score_breakdown).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2">
                    <span className="w-16 shrink-0 text-muted-foreground">
                      {BREAKDOWN_LABELS[k] ?? k}
                    </span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${Math.round(Math.max(0, Math.min(1, v)) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
                {offer.rank_reason.length > 0 && (
                  <ul className="mt-1 space-y-0.5">
                    {offer.rank_reason.map((r, i) => (
                      <li key={i} className="text-muted-foreground">
                        • {r}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {offer.cautions.length > 0 && (
              <ul className="tone tone-amber rounded-lg border p-2">
                {offer.cautions.map((c, i) => (
                  <li key={i} className="leading-4">
                    • {c}
                  </li>
                ))}
              </ul>
            )}

            <p className="text-[9px] leading-4 text-muted-foreground">
              نام و شمارهٔ این فروشگاه از دیتاست آمده و تأیید نشده است. قیمت، قیمت زندهٔ
              فروشگاه نیست و موجودی در دیتاست وجود ندارد.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
