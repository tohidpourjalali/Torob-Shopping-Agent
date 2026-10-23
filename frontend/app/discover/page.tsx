"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ProductCard } from "@/components/product-card";
import { StoreCard } from "@/components/store-card";
import { ToolTrace } from "@/components/tool-trace";
import { PurchasePlanCard } from "@/components/purchase-plan";
import { LocationPicker, type PickedLocation } from "@/components/location-picker";
import {
  agentCapabilities,
  agentChat,
  formatNumber,
  type AgentCapabilities,
  type AgentChatResponse,
  type ProductSummary,
} from "@/lib/api";
import {
  Send,
  Loader2,
  Sparkles,
  Bot,
  User,
  Layers,
  Store as StoreIcon,
  BookOpenCheck,
  ShieldQuestion,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Msg = { role: "user" | "agent"; text: string };

function AgentInner() {
  const router = useRouter();
  const params = useSearchParams();
  const initialQ = params.get("q") || "";

  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState(initialQ);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [state, setState] = useState<AgentChatResponse | null>(null);
  const [caps, setCaps] = useState<AgentCapabilities | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [location, setLocation] = useState<PickedLocation | null>(null);
  const [showAllProducts, setShowAllProducts] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const bootedRef = useRef(false);

  useEffect(() => {
    agentCapabilities().then(setCaps).catch(() => setCaps(null));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, loading]);

  const send = useCallback(
    async (
      text: string,
      extra?: {
        product_id?: string;
        offer_id?: string;
        message?: string;
        loc?: PickedLocation | null;
      },
    ) => {
      const loc = extra?.loc ?? location;
      const visible = (extra?.message ?? text ?? "").trim();
      if (visible && !extra?.product_id) {
        setMessages((m) => [...m, { role: "user", text: visible }]);
      }
      setLoading(true);
      setError(null);
      try {
        const res = await agentChat({
          message: extra?.message ?? text,
          session_id: sessionId,
          lat: loc?.lat ?? null,
          lon: loc?.lon ?? null,
          location_label: loc?.label ?? null,
          product_id: extra?.product_id ?? null,
          offer_id: extra?.offer_id ?? null,
        });
        setSessionId(res.session_id);
        setState(res);
        setShowAllProducts(false);
        setMessages((m) => [...m, { role: "agent", text: res.reply }]);
        if (res.stage === "guide" && res.guide && !extra?.product_id) {
          // وقتی ایجنت خودش راهنما ساخت، نیازی به پیام اضافه نیست
        }
      } catch (e) {
        setError("ارتباط با ایجنت برقرار نشد. دوباره تلاش کنید.");
      } finally {
        setLoading(false);
      }
    },
    [sessionId, location],
  );

  // اجرای خودکار پرسش اولیه از ?q=
  useEffect(() => {
    if (bootedRef.current || !initialQ) return;
    bootedRef.current = true;
    send(initialQ);
  }, [initialQ, send]);

  const pickLocation = useCallback(
    async (loc: PickedLocation) => {
      setLocation(loc);
      if (sessionId) {
        // موقعیت را با همان مختصات به نشست فعلی بفرست تا فاصله‌ها به‌روز شوند
        await send("", { message: "موقعیتم را ثبت کن و فروشگاه‌های نزدیک را نشان بده", loc });
      }
    },
    [sessionId, send],
  );

  const quick = state?.quick_replies ?? [];

  return (
    <main className="app-bg mx-auto flex min-h-[calc(100dvh-3rem)] max-w-2xl flex-col px-3 pb-24 pt-3">
      {/* هدر ایجنت */}
      <section className="mb-2 rounded-2xl border border-border bg-card/95 p-3 shadow-sm">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h1 className="flex items-center gap-1.5 text-sm font-extrabold">
              <Sparkles className="h-4 w-4 text-primary" aria-hidden />
              ایجنت خرید حضوری
            </h1>
            <p className="mt-0.5 text-[10px] leading-4 text-muted-foreground">
              خودش جست‌وجو می‌کند، فروشگاه را پیدا می‌کند و مسیر خرید حضوری را می‌چیند.
            </p>
          </div>
          <span
            className={cn(
              "shrink-0 rounded-full px-2 py-0.5 text-[9px] font-bold",
              caps?.llm_enabled
                ? "tone-blue border"
                : "tone-slate border",
            )}
            title={caps?.note}
          >
            {caps?.llm_enabled ? `مدل: ${caps.model ?? "فعال"}` : "برنامه‌ریز قطعی"}
          </span>
        </div>

        {/* موقعیت — با پرسش صریح اجازه */}
        <div className="mt-2">
          <LocationPicker value={location} onChange={pickLocation} />
        </div>

        {state?.collected?.budget_max ? (
          <div className="mt-1.5 flex flex-wrap gap-1">
            <span className="tone tone-violet border px-1.5 py-0.5 text-[9px]">
              بودجه: تا {formatNumber(state.collected.budget_max)} تومان
            </span>
          </div>
        ) : null}
      </section>

      {/* گفت‌وگو */}
      {messages.length > 0 && (
        <section className="mb-2 space-y-1.5">
          {messages.slice(-6).map((m, i) => (
            <div
              key={i}
              className={cn(
                "flex items-start gap-1.5",
                m.role === "user" ? "justify-start" : "justify-end",
              )}
            >
              {m.role === "user" && (
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted">
                  <User className="h-3 w-3" aria-hidden />
                </span>
              )}
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-2.5 py-1.5 text-[11px] leading-5",
                  m.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "border border-border bg-card",
                )}
              >
                {m.text}
              </div>
              {m.role === "agent" && (
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Bot className="h-3 w-3" aria-hidden />
                </span>
              )}
            </div>
          ))}
        </section>
      )}

      {loading && (
        <div className="mb-2 flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
          ایجنت در حال اجرای ابزارها…
        </div>
      )}

      {error && (
        <div className="tone tone-rose mb-2 border p-2 text-[11px]">{error}</div>
      )}

      {/* پرسش‌های ایجنت */}
      {state?.question && quick.length > 0 && (
        <section className="mb-2">
          <p className="mb-1 text-[11px] font-bold">{state.question}</p>
          <div className="flex flex-wrap gap-1">
            {quick.map((q) => (
              <button
                key={q.value}
                type="button"
                onClick={() => send(q.value)}
                className="tone tone-blue border px-2 py-1 text-[10px] font-medium transition-transform active:scale-95"
              >
                {q.label}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* محصولات — در مرحلهٔ راهنما جمع می‌شوند تا نتیجهٔ اصلی پایین نرود */}
      {state && state.products.length > 0 && state.stage !== "guide" && (
        <section className="mb-2">
          <h2 className="mb-1 flex items-center gap-1 text-[11px] font-bold text-muted-foreground">
            <Layers className="h-3 w-3" aria-hidden />
            {formatNumber(state.products.length)} محصول — یکی را انتخاب کنید
          </h2>
          <div className="grid gap-2">
            {state.products.map((p, i) => (
              <ProductCard
                key={p.product_id}
                product={p}
                rank={i + 1}
                onSelect={(prod) => send(prod.persian_title ?? "", { product_id: prod.product_id })}
              />
            ))}
          </div>
        </section>
      )}

      {state && state.products.length > 0 && state.stage === "guide" && (
        <section className="mb-2">
          <button
            type="button"
            onClick={() => setShowAllProducts((v) => !v)}
            className="tone tone-slate flex w-full items-center justify-between border px-2 py-1.5 text-[10px] font-semibold"
            aria-expanded={showAllProducts}
          >
            <span className="flex items-center gap-1">
              <Layers className="h-3 w-3" aria-hidden />
              {formatNumber(state.products.length)} محصول دیگر از همین جست‌وجو
            </span>
            <span className="opacity-70">{showAllProducts ? "بستن" : "نمایش"}</span>
          </button>
          {showAllProducts && (
            <div className="mt-1.5 grid gap-2">
              {state.products.map((p, i) => (
                <ProductCard
                  key={p.product_id}
                  product={p}
                  rank={i + 1}
                  onSelect={(prod) => send(prod.persian_title ?? "", { product_id: prod.product_id })}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {/* دسته‌های پیشنهادی */}
      {state && state.products.length === 0 && state.suggested_categories.length > 0 && (
        <section className="tone tone-slate mb-2 border p-2">
          <p className="mb-1 text-[10px] font-bold">دسته‌های نزدیک در دیتاست</p>
          <div className="flex flex-wrap gap-1">
            {state.suggested_categories.slice(0, 6).map((c) => (
              <button
                key={c.name}
                type="button"
                onClick={() => send(c.name)}
                className="rounded-md border border-border bg-background/60 px-1.5 py-0.5 text-[9px]"
              >
                {c.name} ({formatNumber(c.products_count)})
              </button>
            ))}
          </div>
        </section>
      )}

      {/* نقشهٔ خرید */}
      {state?.guide && (
        <section className="mb-2">
          <h2 className="mb-1 flex items-center gap-1 text-[11px] font-bold text-muted-foreground">
            <BookOpenCheck className="h-3 w-3" aria-hidden />
            نقشهٔ خرید حضوری
          </h2>
          <PurchasePlanCard
            plan={state.guide}
            origin={location ? { lat: location.lat, lon: location.lon } : null}
          />
        </section>
      )}

      {/* فروشگاه‌ها */}
      {state && state.stores.length > 0 && (
        <section className="mb-2">
          <h2 className="mb-1 flex items-center gap-1 text-[11px] font-bold text-muted-foreground">
            <StoreIcon className="h-3 w-3" aria-hidden />
            {formatNumber(state.stores.length)} فروشگاه حضوری نزدیک
          </h2>
          <div className="grid gap-2">
            {state.stores.slice(0, 6).map((s, i) => (
              <StoreCard
                key={s.offer_id}
                offer={s}
                rank={i + 1}
                origin={location ? { lat: location.lat, lon: location.lon } : null}
              />
            ))}
          </div>
        </section>
      )}

      {/* شفافیت داده — یک خط، بازشدنی؛ نه برچسب تکراری روی هر کارت */}
      {state && (state.notes.length > 0 || state.stores.length > 0) && (
        <details className="mb-2 rounded-lg border border-border bg-card/70 px-2 py-1.5">
          <summary className="flex cursor-pointer items-center gap-1 text-[9px] leading-4 text-muted-foreground">
            <ShieldQuestion className="h-2.5 w-2.5 shrink-0" aria-hidden />
            داده‌ها از کجا آمده‌اند؟ (نام و شماره تأییدنشده، قیمت snapshot، موجودی نامشخص)
          </summary>
          <ul className="mt-1 space-y-0.5">
            {state.notes.map((n, i) => (
              <li key={i} className="text-[9px] leading-4 text-muted-foreground">
                • {n}
              </li>
            ))}
            <li className="text-[9px] leading-4 text-muted-foreground">
              • قیمت‌ها تصویر لحظه‌ای دیتاست‌اند، نه قیمت زندهٔ فروشگاه؛ موجودی در دیتاست وجود ندارد.
            </li>
          </ul>
        </details>
      )}

      {/* شفافیت ایجنت — پایین صفحه، بسته و اختیاری */}
      {state && (
        <div className="mb-2">
          <ToolTrace
            calls={state.tool_calls}
            engine={state.reasoning_engine}
            modelLabel={state.model_label}
          />
        </div>
      )}

      <div ref={bottomRef} />

      {/* ورودی */}
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-background/95 backdrop-blur">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!input.trim() || loading) return;
            send(input);
            setInput("");
          }}
          className="mx-auto flex max-w-2xl items-center gap-1.5 px-3 py-2"
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="مثلاً: هدفون بی‌سیم تا ۵ میلیون"
            className="h-9 text-xs"
            aria-label="پیام به ایجنت"
          />
          <Button
            type="submit"
            size="icon"
            className="h-9 w-9 shrink-0"
            disabled={loading || !input.trim()}
            aria-label="ارسال"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Send className="h-4 w-4 rotate-180" aria-hidden />
            )}
          </Button>
        </form>
      </div>
    </main>
  );
}

export default function AgentPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[60dvh] items-center justify-center text-sm text-muted-foreground">
          <Loader2 className="ml-2 h-4 w-4 animate-spin" aria-hidden />
          در حال بارگذاری ایجنت…
        </div>
      }
    >
      <AgentInner />
    </Suspense>
  );
}
