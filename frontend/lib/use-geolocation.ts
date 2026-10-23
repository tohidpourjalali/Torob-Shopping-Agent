"use client";

/**
 * موقعیت‌یابی واقعی کاربر.
 *
 * درس‌های دور قبل:
 *   • هیچ فراخوانی `navigator.geolocation` وجود نداشت → «کار نمی‌کند».
 *   • اکنون هم یک حالت باقی مانده بود: وقتی صفحه در قاب (iframe) یا با
 *     Permissions-Policy محدود اجرا شود، مرورگر بدون هیچ پرسشی فوراً خطای
 *     «اجازه داده نشد» می‌دهد. کاربر فکر می‌کند دکمه خراب است، درحالی‌که
 *     مرورگر اصلاً اجازهٔ پرسیدن نداشته.
 *
 * راه‌حل: چهار وضعیت را از هم جدا می‌کنیم
 *   can_prompt     → مرورگر می‌تواند از کاربر اجازه بگیرد (حالت عادی)
 *   prompt         → اجازه از قبل داده نشده؛ دکمهٔ صریح «اجازه می‌دهم»
 *   granted/denied → نتیجهٔ واقعی
 *   blocked_frame  → قاب اجازه نمی‌دهد؛ راه‌حل: باز کردن در تب مستقل
 *   insecure       → HTTP (غیر از localhost)
 */

import { useCallback, useEffect, useState } from "react";
import { reverseLocation } from "@/lib/api";

export type GeoStatus =
  | "idle"
  | "unsupported"
  | "insecure"
  | "blocked_frame"
  | "prompt"
  | "prompting"
  | "granted"
  | "denied"
  | "unavailable"
  | "timeout";

export interface GeoState {
  status: GeoStatus;
  /** آیا مرورگر می‌تواند از کاربر اجازه بگیرد؟ */
  canPrompt?: boolean;
  lat?: number;
  lon?: number;
  accuracy?: number;
  label?: string;
  nearestArea?: string | null;
  nearestAreaKm?: number | null;
  message?: string;
}

export const GEO_MESSAGES: Record<GeoStatus, string> = {
  idle: "",
  unsupported: "این مرورگر موقعیت‌یابی ندارد؛ محله را از فهرست انتخاب کنید.",
  insecure: "موقعیت‌یابی فقط روی HTTPS یا localhost کار می‌کند؛ محله را دستی انتخاب کنید.",
  blocked_frame:
    "این صفحه داخل یک قاب نمایش داده شده و مرورگر اجازهٔ پرسیدن موقعیت را نمی‌دهد. «باز کردن در پنجرهٔ جدید» را بزنید.",
  prompt: "برای پیدا کردن فروشگاه نزدیک، اجازهٔ دسترسی به موقعیت لازم است.",
  prompting: "منتظر تأیید مرورگر بمانید… اگر پنجرهٔ اجازه را نمی‌بینید، نوار آدرس را بررسی کنید.",
  granted: "موقعیت شما ثبت شد.",
  denied:
    "اجازهٔ موقعیت رد شده است. از قفل کنار آدرس سایت، دسترسی موقعیت را روی «اجازه» بگذارید و دوباره تلاش کنید — یا محله را انتخاب کنید.",
  unavailable: "موقعیت در دسترس نیست (سیگنال GPS/شبکه). محله را انتخاب کنید یا دوباره تلاش کنید.",
  timeout: "گرفتن موقعیت طول کشید. دوباره تلاش کنید یا محله را انتخاب کنید.",
};

function frameAllowed(): boolean {
  if (typeof document === "undefined") return true;
  try {
    const fp = (document as Document & {
      featurePolicy?: { allowsFeature: (f: string) => boolean };
      permissionsPolicy?: { allowsFeature: (f: string) => boolean };
    }).featurePolicy ??
      (document as Document & { permissionsPolicy?: { allowsFeature: (f: string) => boolean } })
        .permissionsPolicy;
    if (fp?.allowsFeature) return fp.allowsFeature("geolocation");
  } catch {
    /* برخی مرورگرها این API را ندارند */
  }
  try {
    if (window.self !== window.top) {
      // داخل قاب بدون allow="geolocation" معمولاً مسدود است؛ ولی بدون API
      // نمی‌توان مطمئن بود — اجازه می‌دهیم تلاش کند و خطا را تفسیر کنیم.
      return true;
    }
  } catch {
    /* cross-origin frame */
  }
  return true;
}

export function useGeolocation() {
  const [state, setState] = useState<GeoState>({ status: "idle" });

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!("geolocation" in navigator)) {
      setState({ status: "unsupported", message: GEO_MESSAGES.unsupported, canPrompt: false });
      return;
    }
    if (!window.isSecureContext) {
      setState({ status: "insecure", message: GEO_MESSAGES.insecure, canPrompt: false });
      return;
    }
    if (!frameAllowed()) {
      setState({ status: "blocked_frame", message: GEO_MESSAGES.blocked_frame, canPrompt: false });
      return;
    }
    // وضعیت اجازه را از قبل بخوان تا بدانیم «پرسیدن» ممکن است یا نه
    const perms = (navigator as Navigator & {
      permissions?: { query: (d: { name: string }) => Promise<{ state: string }> };
    }).permissions;
    if (!perms?.query) {
      setState({ status: "prompt", message: GEO_MESSAGES.prompt, canPrompt: true });
      return;
    }
    perms
      .query({ name: "geolocation" })
      .then((p) => {
        if (p.state === "granted") {
          setState({ status: "prompt", message: "اجازهٔ موقعیت داده شده است؛ برای ثبت، دکمه را بزنید.", canPrompt: true });
        } else if (p.state === "denied") {
          setState({ status: "denied", message: GEO_MESSAGES.denied, canPrompt: false });
        } else {
          setState({ status: "prompt", message: GEO_MESSAGES.prompt, canPrompt: true });
        }
      })
      .catch(() => setState({ status: "prompt", message: GEO_MESSAGES.prompt, canPrompt: true }));
  }, []);

  const locate = useCallback(async () => {
    if (typeof window === "undefined") return null;
    if (!("geolocation" in navigator)) {
      setState({ status: "unsupported", message: GEO_MESSAGES.unsupported, canPrompt: false });
      return null;
    }
    if (!window.isSecureContext) {
      setState({ status: "insecure", message: GEO_MESSAGES.insecure, canPrompt: false });
      return null;
    }

    setState((s) => ({ ...s, status: "prompting", message: GEO_MESSAGES.prompting }));

    return new Promise<GeoState | null>((resolve) => {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          const { latitude, longitude, accuracy } = pos.coords;
          let label = "موقعیت فعلی شما";
          let nearestArea: string | null = null;
          let nearestAreaKm: number | null = null;
          try {
            const reverse = await reverseLocation(latitude, longitude);
            if (reverse?.location?.label) label = reverse.location.label;
            nearestArea = reverse?.location?.nearest_area ?? null;
            nearestAreaKm = reverse?.location?.nearest_area_km ?? null;
          } catch {
            /* برچسب محله اختیاری است */
          }
          const next: GeoState = {
            status: "granted",
            canPrompt: true,
            lat: latitude,
            lon: longitude,
            accuracy: Math.round(accuracy),
            label,
            nearestArea,
            nearestAreaKm,
            message: GEO_MESSAGES.granted,
          };
          setState(next);
          resolve(next);
        },
        (err) => {
          // خطای PERMISSION_DENIED داخل قاب یعنی «قاب اجازه نداد»، نه «کاربر رد کرد»
          const framed = (() => {
            try {
              return window.self !== window.top;
            } catch {
              return true;
            }
          })();
          const status: GeoStatus =
            err.code === err.PERMISSION_DENIED
              ? framed && !frameAllowed()
                ? "blocked_frame"
                : framed
                  ? "blocked_frame"
                  : "denied"
              : err.code === err.TIMEOUT
                ? "timeout"
                : "unavailable";
          const next: GeoState = {
            status,
            canPrompt: status === "denied" || status === "timeout" || status === "unavailable",
            message: GEO_MESSAGES[status],
          };
          setState(next);
          resolve(null);
        },
        { enableHighAccuracy: true, timeout: 12000, maximumAge: 30_000 },
      );
    });
  }, []);

  const reset = useCallback(() => setState({ status: "idle" }), []);

  return { ...state, locate, reset, busy: state.status === "prompting" };
}
