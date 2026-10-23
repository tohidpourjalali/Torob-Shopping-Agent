import { cn } from "@/lib/utils";
import { ShieldQuestion, ShieldCheck, ShieldAlert, FlaskConical, Clock } from "lucide-react";

type Tone = "warn" | "ok" | "bad" | "demo" | "neutral";

const TONES: Record<Tone, { cls: string; Icon: typeof ShieldCheck }> = {
  warn: {
    cls: "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-200 dark:border-amber-900",
    Icon: ShieldQuestion,
  },
  ok: {
    cls: "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-200 dark:border-emerald-900",
    Icon: ShieldCheck,
  },
  bad: {
    cls: "bg-rose-50 text-rose-800 border-rose-200 dark:bg-rose-950/40 dark:text-rose-200 dark:border-rose-900",
    Icon: ShieldAlert,
  },
  demo: {
    cls: "bg-violet-50 text-violet-800 border-violet-200 dark:bg-violet-950/40 dark:text-violet-200 dark:border-violet-900",
    Icon: FlaskConical,
  },
  neutral: {
    cls: "bg-muted text-muted-foreground border-border",
    Icon: Clock,
  },
};

export function ProvenanceBadge({
  tone = "warn",
  children,
  className,
  title,
  icon = true,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
  title?: string;
  icon?: boolean;
}) {
  const { cls, Icon } = TONES[tone];
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-5",
        cls,
        className,
      )}
    >
      {icon && <Icon className="h-3 w-3 shrink-0" aria-hidden />}
      {children}
    </span>
  );
}

/** برچسب «قیمت تأییدنشده» — همیشه روی قیمت‌ها */
export function PriceBadge({ verified }: { verified?: boolean }) {
  return verified ? (
    <ProvenanceBadge tone="ok">قیمت تأییدشده</ProvenanceBadge>
  ) : (
    <ProvenanceBadge tone="warn" title="این قیمت از snapshot دیتاست خوانده شده و قیمت زنده فروشگاه نیست">
      قیمت تأییدنشده
    </ProvenanceBadge>
  );
}

/** برچسب «موجودی نامشخص» — دیتاست موجودی ندارد */
export function StockBadge({ status }: { status?: string }) {
  if (status === "in_stock") return <ProvenanceBadge tone="ok">موجود (تأییدشده)</ProvenanceBadge>;
  if (status === "out_of_stock") return <ProvenanceBadge tone="bad">ناموجود (تأییدشده)</ProvenanceBadge>;
  return (
    <ProvenanceBadge tone="neutral" title="دیتاست هیچ فیلد موجودی انبار ندارد">
      موجودی نامشخص
    </ProvenanceBadge>
  );
}

/** برچسب نام فروشگاه — نام تأییدنشده */
export function UnverifiedNameBadge() {
  return (
    <ProvenanceBadge
      tone="warn"
      icon={false}
      title="این نام از دیتاست ثبت‌شده است و توسط ترب تأیید نشده؛ ممکن است ثبت کاربران باشد"
    >
      نام تأییدنشده
    </ProvenanceBadge>
  );
}

export function DemoBadge({ children = "نمایشی — بدون تماس واقعی" }: { children?: React.ReactNode }) {
  return <ProvenanceBadge tone="demo">{children}</ProvenanceBadge>;
}

export function OpenBadge({ isOpen }: { isOpen: boolean | null | undefined }) {
  if (isOpen === true) return <ProvenanceBadge tone="ok">الان باز است</ProvenanceBadge>;
  if (isOpen === false) return <ProvenanceBadge tone="bad">الان بسته است</ProvenanceBadge>;
  return (
    <ProvenanceBadge tone="neutral" title="ساعت کاری این فروشگاه در دیتاست ثبت نشده">
      ساعت کاری نامشخص
    </ProvenanceBadge>
  );
}
