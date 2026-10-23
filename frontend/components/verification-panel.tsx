"use client";

/**
 * «استعلام قیمت و موجودی» — مسیری که واقعاً به نتیجه می‌رسد.
 *
 * قبلاً دکمه فقط یک رکورد نمایشی ثبت می‌کرد و متن سؤالات را داخل یک
 * `<details>` بسته پنهان می‌کرد؛ برای کاربر «کار نمی‌کند» به‌نظر می‌رسید.
 *
 * اکنون سه چیز اتفاق می‌افتد:
 *   ۱) متن آمادهٔ استعلام ساخته و نمایش داده می‌شود (قابل کپی)
 *   ۲) اگر دیتاست شمارهٔ موبایل داشته باشد، دکمهٔ واتساپ/پیامک با همان متن
 *      آماده است — یعنی کاربر می‌تواند همین حالا استعلام را بفرستد
 *   ۳) درخواست در سامانه ثبت می‌شود و در /tracking?offer=… قابل پیگیری است،
 *      با برچسب صریح «نمایشی» تا زمانی که کانال واقعی پیکربندی نشده
 */

import { useState } from "react";
import Link from "next/link";
import {
  faDecimal,
  formatNumber,
  verifyOffer,
  type StoreOffer,
  type VerificationResponse,
} from "@/lib/api";
import {
  smsHref,
  telegramShareHref,
  whatsappHref,
  isMobileNumber,
  tryOpenExternal,
} from "@/lib/geo";
import { telHref, toLatinDigits } from "@/lib/utils";
import {
  Copy,
  Check,
  Loader2,
  MessageCircle,
  MessageSquare,
  Phone,
  Send,
  History,
  FlaskConical,
  AlertTriangle,
} from "lucide-react";

export function VerificationPanel({
  offer,
  compact = false,
}: {
  offer: StoreOffer;
  compact?: boolean;
}) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [res, setRes] = useState<VerificationResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [channelNote, setChannelNote] = useState<string | null>(null);

  const phone = offer.shop.phone_display;
  const mobile = isMobileNumber(phone);

  const start = async () => {
    setState("loading");
    setErr(null);
    try {
      const r = await verifyOffer({ offer_id: offer.offer_id, channel: "demo" });
      setRes(r);
      setState("done");
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "ارتباط با سرویس تأیید برقرار نشد.";
      setErr(String(detail));
      setState("error");
    }
  };

  const script = (res?.script ?? []).join("\n");

  if (state === "idle" || state === "loading") {
    return (
      <button
        type="button"
        onClick={start}
        disabled={state === "loading"}
        className="inline-flex items-center gap-1 rounded-lg bg-primary px-2 py-1 text-[10px] font-bold text-primary-foreground disabled:opacity-60"
      >
        {state === "loading" ? (
          <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
        ) : (
          <FlaskConical className="h-3 w-3" aria-hidden />
        )}
        استعلام قیمت و موجودی
      </button>
    );
  }

  if (state === "error") {
    return (
      <div className="rounded-lg border border-rose-300 bg-rose-50 p-2 text-[10px] leading-5 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
        <div className="flex items-center gap-1 font-bold">
          <AlertTriangle className="h-3 w-3" aria-hidden /> استعلام ثبت نشد
        </div>
        <p className="mt-0.5">{err}</p>
        <button
          type="button"
          onClick={start}
          className="mt-1 rounded-md bg-primary px-1.5 py-0.5 text-[9px] font-bold text-primary-foreground"
        >
          تلاش دوباره
        </button>
      </div>
    );
  }

  return (
    <div className="tone tone-violet space-y-1.5 rounded-xl border p-2">
      <div className="flex flex-wrap items-center justify-between gap-1">
        <span className="inline-flex items-center gap-1 text-[10px] font-bold">
          <FlaskConical className="h-3 w-3" aria-hidden />
          درخواست ثبت شد — {res?.label}
        </span>
        <bdi className="text-[9px] opacity-70">
          {res?.checked_at ? new Date(res.checked_at).toLocaleTimeString("fa-IR") : ""}
        </bdi>
      </div>

      <p className="text-[9px] leading-4 opacity-90">{res?.note}</p>

      <div className="rounded-lg bg-background/70 p-1.5">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-[9px] font-semibold">متن آمادهٔ استعلام</span>
          <button
            type="button"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(script);
                setCopied(true);
                setTimeout(() => setCopied(false), 1600);
              } catch {
                /* clipboard در قاب ممکن نیست */
              }
            }}
            className="inline-flex items-center gap-0.5 rounded-md border border-border px-1.5 py-0.5 text-[9px]"
          >
            {copied ? <Check className="h-2.5 w-2.5" aria-hidden /> : <Copy className="h-2.5 w-2.5" aria-hidden />}
            {copied ? "کپی شد" : "کپی"}
          </button>
        </div>
        <ul className="space-y-0.5">
          {(res?.script ?? []).map((s, i) => (
            <li key={i} className="text-[9px] leading-4">
              • {s}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-wrap gap-1">
        {whatsappHref(phone, script) && (
          <button
            type="button"
            onClick={() => {
              const href = whatsappHref(phone, script)!;
              if (!tryOpenExternal(href)) {
                navigator.clipboard?.writeText(href).catch(() => {});
                setChannelNote("باز نشد (مرورگر پنجرهٔ جدید را مسدود کرد) — لینک واتساپ کپی شد.");
                return;
              }
              setChannelNote(null);
            }}
            className="inline-flex items-center gap-0.5 rounded-md bg-emerald-600 px-1.5 py-0.5 text-[9px] font-bold text-white"
          >
            <MessageCircle className="h-2.5 w-2.5" aria-hidden /> واتساپ
          </button>
        )}
        {smsHref(phone, script) && (
          <a
            href={smsHref(phone, script)!}
            className="inline-flex items-center gap-0.5 rounded-md border border-border px-1.5 py-0.5 text-[9px]"
          >
            <MessageSquare className="h-2.5 w-2.5" aria-hidden /> پیامک
          </a>
        )}
        <a
          href={telHref(phone) || "#"}
          className="inline-flex items-center gap-0.5 rounded-md border border-border px-1.5 py-0.5 text-[9px]"
          title={phone ? `شمارهٔ دیتاست: ${toLatinDigits(phone)} (تأییدنشده)` : undefined}
        >
          <Phone className="h-2.5 w-2.5" aria-hidden /> تماس
        </a>
        <button
          type="button"
          onClick={() => {
            const href = telegramShareHref(script);
            if (!tryOpenExternal(href)) {
              navigator.clipboard?.writeText(href).catch(() => {});
              setChannelNote("باز نشد (مرورگر پنجرهٔ جدید را مسدود کرد) — لینک تلگرام کپی شد.");
              return;
            }
            setChannelNote(null);
          }}
          className="inline-flex items-center gap-0.5 rounded-md border border-border px-1.5 py-0.5 text-[9px]"
        >
          <Send className="h-2.5 w-2.5" aria-hidden /> تلگرام
        </button>
        <Link prefetch={false}
          href={`/tracking?offer=${offer.offer_id}`}
          className="inline-flex items-center gap-0.5 rounded-md border border-border px-1.5 py-0.5 text-[9px]"
        >
          <History className="h-2.5 w-2.5" aria-hidden /> پیگیری
        </Link>
      </div>

      {channelNote && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-1.5 py-1 text-[9px] leading-4 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
          {channelNote}
        </p>
      )}

      {!phone && (
        <p className="text-[9px] leading-4 opacity-80">
          دیتاست برای این فروشگاه شماره ندارد؛ متن بالا را از سایت یا اینستاگرام فروشگاه بفرستید.
        </p>
      )}
      {phone && !mobile && (
        <p className="text-[9px] leading-4 opacity-80">
          شمارهٔ ثبت‌شده خط ثابت است؛ واتساپ/پیامک برای آن معنا ندارد — تماس تلفنی یا پیام در اینستاگرام.
        </p>
      )}
      {compact && (
        <p className="text-[9px] opacity-70">
          امتیاز این آفر: {offer.score != null ? faDecimal(offer.score, 2) : "—"}
          {offer.price.value_toman ? ` · ${formatNumber(offer.price.value_toman)} تومان` : ""}
        </p>
      )}
    </div>
  );
}
