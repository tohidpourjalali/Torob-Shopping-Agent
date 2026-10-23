/**
 * لینک‌های مسیریابی و تماس — همه با قالب رسمی هر سرویس.
 *
 * چرا این فایل وجود دارد: قبلاً فقط یک لینک Google Maps با پارامتر `origin`
 * ساخته می‌شد. سه مشکل داشت:
 *   ۱) در ایران معمولاً باز نمی‌شود (فیلتر است) → کاربر «کار نمی‌کند» می‌بیند
 *   ۲) بدون موقعیت کاربر، `origin` مقدار نامعتبر می‌گرفت
 *   ۳) اگر مرورگر/قاب اجازهٔ باز کردن تب جدید ندهد، هیچ جایگزینی نبود
 * اکنون چند سرویس + کپی مختصات + طرح `geo:` داریم.
 *
 * منبع قالب‌ها: platform.neshan.org (نشان)، Google Maps URLs (گوگل).
 */

import { toLatinDigits } from "@/lib/utils";

export type LatLon = { lat: number; lon: number };

function n(v: number) {
  return Number(v.toFixed(6));
}

export interface DirectionOption {
  key: string;
  label: string;
  hint: string;
  href: string;
}

/** گزینه‌های مسیریابی به مقصد مشخص. مبدأ اختیاری است. */
export function directionOptions(dest: LatLon, origin?: LatLon | null): DirectionOption[] {
  const d = `${n(dest.lat)},${n(dest.lon)}`;
  const o = origin ? `${n(origin.lat)},${n(origin.lon)}` : null;

  const options: DirectionOption[] = [];

  // نشان — سرویس ایرانی؛ هم وب و هم اپ اندروید را پوشش می‌دهد
  options.push({
    key: "neshan",
    label: "مسیریابی با نشان",
    hint: "در مرورگر یا اپ نشان باز می‌شود",
    href: o
      ? `https://nshn.ir?origin=${o}&destination=${d}&vehicle=d`
      : `https://nshn.ir/?lat=${n(dest.lat)}&lng=${n(dest.lon)}`,
  });

  // بلد — فقط نمایش نقطه (قالب عمومی)
  options.push({
    key: "balad",
    label: "نمایش روی بلد",
    hint: "نقطهٔ فروشگاه روی نقشه",
    href: `https://balad.ir/location?latitude=${n(dest.lat)}&longitude=${n(dest.lon)}`,
  });

  // گوگل مپ — قالب رسمی؛ ممکن است در ایران باز نشود
  options.push({
    key: "google",
    label: "مسیریابی با Google Maps",
    hint: "ممکن است در ایران در دسترس نباشد",
    href: `https://www.google.com/maps/dir/?api=1&destination=${d}${o ? `&origin=${o}` : ""}`,
  });

  // اپ نقشهٔ پیش‌فرض دستگاه (اندروید/دسکتاپ)
  options.push({
    key: "geo",
    label: "اپ نقشهٔ دستگاه",
    hint: "اپ نقشهٔ پیش‌فرض گوشی",
    href: `geo:${d}?q=${d}`,
  });

  return options;
}

/** «مختصات» به شکل قابل کپی برای اپ‌هایی که لینک نمی‌پذیرند */
export function coordsText(dest: LatLon) {
  return `${n(dest.lat)}, ${n(dest.lon)}`;
}

/** شمارهٔ بین‌المللی ایران: ۰۹۱۲… → 98912… | ۰۲۱… → 9821… (ارقام لاتین) */
export function intlPhone(input: string | null | undefined) {
  const raw = toLatinDigits(input ?? "").replace(/[^\d]/g, "").replace(/^0+/, "");
  if (!raw) return "";
  return raw.startsWith("98") ? raw : `98${raw}`;
}

/** فقط موبایل ایرانی (۰۹xxxxxxxxx) پیامک/واتساپ می‌پذیرد */
export function isMobileNumber(input: string | null | undefined) {
  const raw = toLatinDigits(input ?? "").replace(/[^\d]/g, "").replace(/^0+/, "");
  return raw.startsWith("9") && raw.length === 10;
}

/** واتساپ با متن آماده — فقط برای شمارهٔ موبایل معنا دارد */
export function whatsappHref(phone: string | null | undefined, text: string) {
  if (!isMobileNumber(phone)) return null;
  return `https://wa.me/${intlPhone(phone)}?text=${encodeURIComponent(text)}`;
}

export function smsHref(phone: string | null | undefined, text: string) {
  if (!isMobileNumber(phone)) return null;
  return `sms:+${intlPhone(phone)}?&body=${encodeURIComponent(text)}`;
}

/** اشتراک‌گذاری عمومی متن در تلگرام (کاربر مخاطب را خودش انتخاب می‌کند) */
export function telegramShareHref(text: string) {
  return `https://t.me/share/url?url=${encodeURIComponent("https://torob.com")}&text=${encodeURIComponent(text)}`;
}

/**
 * تلاش برای باز کردن یک لینک بیرونی، با تشخیص «مسدود شد».
 *
 * چرا لازم است: داخل iframe سندباکس‌شده (پیش‌نمایش، وب‌ویو اپ‌ها) مرورگر
 * `window.open` را مسدود می‌کند و `target="_blank"` **بی‌صدا** هیچ کاری
 * نمی‌کند. فرق `window.open` با لینک این است که `null` برمی‌گرداند، پس
 * می‌توانیم متوجه شویم و جایگزین نشان دهیم.
 *
 * @returns true اگر باز شد؛ false اگر مرورگر مسدود کرد.
 */
export function tryOpenExternal(href: string): boolean {
  if (typeof window === "undefined") return false;

  // طرح‌های غیر HTTP (geo:, tel:, sms:, intent:) پنجرهٔ جدید نمی‌خواهند؛
  // اپ پیش‌فرض دستگاه با ناوبری مستقیم باز می‌شود.
  if (!/^https?:\/\//i.test(href)) {
    try {
      window.location.href = href;
      return true;
    } catch {
      return false;
    }
  }

  try {
    // هشدار: `window.open(url, "_blank", "noopener")` طبق spec حتی وقتی پنجره
    // واقعاً باز می‌شود هم `null` برمی‌گرداند — و آن‌وقت «مسدود» را اشتباه
    // تشخیص می‌دهیم. پس بدون ویژگی باز می‌کنیم و خودمان `opener` را قطع می‌کنیم.
    const win = window.open(href, "_blank");
    if (win) {
      try {
        win.opener = null;
      } catch {
        /* پنجرهٔ cross-origin: دسترسی به opener مجاز نیست، مهم هم نیست */
      }
      return true;
    }
  } catch {
    /* بعضی مرورگرها استثنا می‌دهند */
  }
  return false;
}

/**
 * آیا صفحه داخل قابی اجرا می‌شود که اجازهٔ باز کردن پنجره/جغرافیا ندارد؟
 * پیش‌نمایش‌های سندباکس‌شده این‌طور هستند؛ باید به کاربر بگوییم چطور درستش کند
 * نه این‌که بی‌صدا شکست بخوریم.
 */
export function frameBlockReason(): "ok" | "iframe" | "unknown" {
  if (typeof window === "undefined") return "unknown";
  try {
    if (window.self !== window.top) return "iframe";
  } catch {
    return "iframe";
  }
  return "ok";
}
