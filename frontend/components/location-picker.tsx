"use client";

/**
 * «موقعیت من» — با پرسش صریح اجازه از کاربر.
 *
 * رفتار قبلی: کلیک روی دکمه، بی‌صدا شکست می‌خورد (در قاب/HTTP/رد اجازه) و
 * کاربر فقط یک پیام کوتاه می‌دید. اینجا:
 *   ۱) قبل از درخواست، دلیل نیاز توضیح داده می‌شود؛ کاربر با دکمهٔ «اجازه می‌دهم»
 *      درخواست را می‌فرستد (مرورگر پنجرهٔ اجازه را نشان می‌دهد).
 *   ۲) اگر مرورگر اجازهٔ پرسیدن نداشته باشد (iframe / Permissions-Policy)،
 *      راه‌حل مشخص داده می‌شود: باز کردن در پنجرهٔ جدید.
 *   ۳) همیشه یک راه جایگزین هست: انتخاب محله از فهرست واقعی دیتاست
 *      (با مختصات واقعی همان محله) — بدون نیاز به GPS.
 */

import { useEffect, useMemo, useState } from "react";
import { datasetLocations, formatNumber, type LocationSuggestion } from "@/lib/api";
import { useGeolocation } from "@/lib/use-geolocation";
import { frameBlockReason } from "@/lib/geo";
import {
  LocateFixed,
  Loader2,
  MapPin,
  ShieldQuestion,
  ExternalLink,
  Check,
  Search,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface PickedLocation {
  lat: number;
  lon: number;
  label: string;
  source: "gps" | "area";
}

export function LocationPicker({
  value,
  onChange,
  compact = false,
}: {
  value?: PickedLocation | null;
  onChange: (loc: PickedLocation) => void;
  compact?: boolean;
}) {
  const geo = useGeolocation();
  const [step, setStep] = useState<"idle" | "explain" | "areas">("idle");
  const [areas, setAreas] = useState<LocationSuggestion[]>([]);
  const [q, setQ] = useState("");
  const [firewall, setFirewall] = useState<"ok" | "iframe" | "unknown">("ok");

  useEffect(() => setFirewall(frameBlockReason()), []);

  useEffect(() => {
    if (step !== "areas" || areas.length) return;
    datasetLocations(40)
      .then(setAreas)
      .catch(() => setAreas([]));
  }, [step, areas.length]);

  const filtered = useMemo(() => {
    const needle = q.trim();
    const list = needle ? areas.filter((a) => a.label.includes(needle)) : areas;
    return list.slice(0, 12);
  }, [areas, q]);

  const askPermission = async () => {
    const res = await geo.locate();
    // اگر مرورگر اجازهٔ پرسیدن نداشته باشد، پنل راه‌حل را باز نگه می‌داریم
    // (به‌جای برگشتن به حالت اولیه که کاربر فکر می‌کند «هیچ اتفاقی نیفتاد»)
    if (!res) setStep("explain");
    if (res?.lat != null && res?.lon != null) {
      setStep("idle");
      onChange({
        lat: res.lat,
        lon: res.lon,
        label: res.label || res.nearestArea || "موقعیت فعلی شما",
        source: "gps",
      });
    }
  };

  const pickArea = (a: LocationSuggestion) => {
    onChange({ lat: a.lat, lon: a.lon, label: a.label, source: "area" });
    setStep("idle");
    setQ("");
  };

  // ---- نمایش وضعیت انتخاب‌شده ----
  if (value) {
    return (
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="tone tone-emerald inline-flex items-center gap-1 border px-2 py-1 text-[10px] font-semibold">
          <MapPin className="h-3 w-3" aria-hidden />
          {value.source === "gps" ? "موقعیت شما" : "محله"} · {value.label}
        </span>
        <button
          type="button"
          onClick={() => setStep("areas")}
          className="rounded-lg border border-border px-2 py-1 text-[10px] text-muted-foreground"
        >
          تغییر
        </button>
        {step === "areas" && <AreaList {...{ filtered, q, setQ, pickArea, setStep }} />}
      </div>
    );
  }

  return (
    <div className={compact ? "" : "tone tone-blue rounded-xl border p-2"}>
      {/* توضیح + دکمهٔ اصلی */}
      {step === "idle" && (
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => setStep("explain")}
            disabled={geo.busy}
            className="inline-flex items-center gap-1 rounded-lg bg-primary px-2.5 py-1.5 text-[10px] font-bold text-primary-foreground disabled:opacity-60"
          >
            {geo.busy ? (
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
            ) : (
              <LocateFixed className="h-3 w-3" aria-hidden />
            )}
            فعال‌کردن موقعیت من
          </button>
          <button
            type="button"
            onClick={() => setStep("areas")}
            className="rounded-lg border border-border bg-background/70 px-2.5 py-1.5 text-[10px] font-medium"
          >
            انتخاب محله
          </button>
          {geo.status === "blocked_frame" ? (
            <span className="flex flex-wrap items-center gap-1 text-[9px] leading-4 text-muted-foreground">
              <AlertTriangle className="mt-0.5 h-2.5 w-2.5 shrink-0" aria-hidden />
              {geo.message}
              <a
                href={typeof window !== "undefined" ? window.location.href : "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 rounded-md bg-primary px-1.5 py-0.5 font-bold text-primary-foreground"
              >
                <ExternalLink className="h-2.5 w-2.5" aria-hidden /> پنجرهٔ جدید
              </a>
            </span>
          ) : geo.status === "insecure" || geo.status === "denied" ? (
            <span className="flex items-start gap-1 text-[9px] leading-4 text-muted-foreground">
              <AlertTriangle className="mt-0.5 h-2.5 w-2.5 shrink-0" aria-hidden />
              {geo.message}
            </span>
          ) : (
            <span className="text-[9px] leading-4 text-muted-foreground">
              {geo.message || "فاصله تا فروشگاه‌ها با موقعیت شما دقیق می‌شود."}
            </span>
          )}
        </div>
      )}

      {/* توضیح اجازه — کاربر خودش درخواست را می‌فرستد */}
      {step === "explain" && (
        <div className="space-y-1.5">
          <p className="flex items-start gap-1 text-[10px] font-semibold leading-5">
            <ShieldQuestion className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
            برای پیدا کردن نزدیک‌ترین فروشگاه، به موقعیت شما نیاز داریم. مرورگر الان یک
            پنجرهٔ اجازه نشان می‌دهد؛ فقط با تأیید شما خوانده می‌شود و جایی ذخیره نمی‌شود.
          </p>

          {firewall === "iframe" && (
            <div className="rounded-lg border border-amber-300/70 bg-background/70 p-1.5 text-[9px] leading-4 dark:border-amber-800">
              این صفحه داخل یک قاب (iframe) اجرا می‌شود و بیشتر مرورگرها در این حالت
              اجازهٔ موقعیت نمی‌دهند. اگر پنجرهٔ اجازه نیامد، در پنجرهٔ جدید باز کنید:
              <div className="mt-1 flex gap-1">
                <a
                  href={typeof window !== "undefined" ? window.location.href : "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-md bg-primary px-1.5 py-0.5 text-[9px] font-bold text-primary-foreground"
                >
                  <ExternalLink className="h-2.5 w-2.5" aria-hidden /> باز کردن در پنجرهٔ جدید
                </a>
                <button
                  type="button"
                  onClick={() => {
                    const url = window.location.href;
                    navigator.clipboard?.writeText(url).catch(() => {});
                    setStep("areas");
                  }}
                  className="rounded-md border border-border px-1.5 py-0.5 text-[9px]"
                >
                  کپی لینک و انتخاب محله
                </button>
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={askPermission}
              disabled={geo.busy}
              className="inline-flex items-center gap-1 rounded-lg bg-primary px-2.5 py-1.5 text-[10px] font-bold text-primary-foreground disabled:opacity-60"
            >
              {geo.busy ? (
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
              ) : (
                <Check className="h-3 w-3" aria-hidden />
              )}
              اجازه می‌دهم
            </button>
            <button
              type="button"
              onClick={() => setStep("areas")}
              className="rounded-lg border border-border px-2.5 py-1.5 text-[10px]"
            >
              به‌جایش محله را انتخاب می‌کنم
            </button>
            <button
              type="button"
              onClick={() => setStep("idle")}
              className="rounded-lg px-2 py-1.5 text-[10px] text-muted-foreground"
            >
              بعداً
            </button>
          </div>

          {geo.status === "denied" && (
            <p className="text-[9px] leading-4 text-rose-700 dark:text-rose-300">
              اجازه رد شده است. روی آیکن قفل کنار آدرس سایت بزنید و «موقعیت» را روی
              «اجازه» بگذارید، بعد دوباره تلاش کنید.
            </p>
          )}
          {geo.status === "prompting" && (
            <p className="text-[9px] leading-4 text-muted-foreground">{geo.message}</p>
          )}
        </div>
      )}

      {step === "areas" && <AreaList {...{ filtered, q, setQ, pickArea, setStep }} />}
    </div>
  );
}

function AreaList({
  filtered,
  q,
  setQ,
  pickArea,
  setStep,
}: {
  filtered: LocationSuggestion[];
  q: string;
  setQ: (v: string) => void;
  pickArea: (a: LocationSuggestion) => void;
  setStep: (s: "idle" | "explain" | "areas") => void;
}) {
  return (
    <div className="mt-1.5 w-full rounded-xl border border-border bg-background/80 p-1.5">
      <div className="mb-1 flex items-center gap-1">
        <Search className="h-3 w-3 text-muted-foreground" aria-hidden />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="جست‌وجوی محله (مثلاً فردوسی)"
          className="h-6 w-full rounded-md border border-border bg-background px-1.5 text-[10px]"
          aria-label="جست‌وجوی محله"
        />
        <button
          type="button"
          onClick={() => setStep("idle")}
          className="shrink-0 rounded-md px-1.5 text-[10px] text-muted-foreground"
        >
          بستن
        </button>
      </div>
      <div className="flex max-h-40 flex-wrap gap-1 overflow-y-auto">
        {filtered.length === 0 && (
          <span className="p-1 text-[9px] text-muted-foreground">
            محله‌ای با این نام در دیتاست نیست.
          </span>
        )}
        {filtered.map((a) => (
          <button
            key={a.label}
            type="button"
            onClick={() => pickArea(a)}
            className={cn(
              "rounded-md border border-border bg-card px-1.5 py-0.5 text-[9px] hover:border-primary",
            )}
            title={`${formatNumber(a.shops_count)} فروشگاه در این محله`}
          >
            {a.label}
            <span className="ms-1 opacity-60">{formatNumber(a.shops_count)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
