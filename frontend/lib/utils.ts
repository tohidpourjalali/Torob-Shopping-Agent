import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

const FA_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];

/** ارقام فارسی/عربی را به لاتین برمی‌گرداند — برای tel: و کپی شماره. */
export function toLatinDigits(input: string | number): string {
  return String(input)
    .replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));
}

/** شمارهٔ قابل شماره‌گیری: فقط ارقام لاتین و علامت + */
export function telHref(phone?: string | null): string | null {
  if (!phone) return null;
  const digits = toLatinDigits(phone).replace(/[^0-9+]/g, "");
  return digits.length >= 5 ? `tel:${digits}` : null;
}

/** ارقام لاتین را در یک رشته به فارسی تبدیل می‌کند. */
export function toFaDigits(input: string | number): string {
  return String(input).replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)]);
}

/** عدد اعشاری با ممیز فارسی: 4.2 → «۴٫۲» */
export function faDecimal(value: number, decimals = 1): string {
  return toFaDigits(value.toFixed(decimals)).replace(".", "٫");
}

export function formatToman(value?: number | null): string {
  if (value == null) return "قیمت نامشخص";
  return new Intl.NumberFormat("fa-IR").format(value) + " تومان";
}

export function formatNumberIr(value?: number | null): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("fa-IR").format(value);
}

export function round2(value?: number | null): string {
  if (value == null) return "—";
  return faDecimal(value, 2);
}
