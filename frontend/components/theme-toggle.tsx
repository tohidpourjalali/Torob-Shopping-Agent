"use client";

/**
 * سوییچ روشن/تاریک.
 *
 * چرا این‌طور نوشته شده: `next-themes` تم را فقط بعد از mount می‌داند، پس اگر
 * مستقیم `theme` را رندر کنیم، بین HTML سرور و کلاینت اختلاف می‌شود (hydration
 * mismatch). راه استاندارد: تا mount شدن، آیکون ثابت رندر می‌شود.
 */

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun, Monitor } from "lucide-react";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "light", label: "روشن", Icon: Sun },
  { value: "dark", label: "تاریک", Icon: Moon },
  { value: "system", label: "سیستم", Icon: Monitor },
] as const;

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const active = mounted ? (theme ?? "system") : "system";

  return (
    <div
      role="group"
      aria-label="حالت نمایش"
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full border border-border bg-card p-0.5",
        className,
      )}
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const isActive = active === value;
        return (
          <button
            key={value}
            type="button"
            onClick={() => setTheme(value)}
            aria-pressed={isActive}
            aria-label={label}
            title={label}
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-full transition-colors",
              isActive
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
          </button>
        );
      })}
      {/* خوانندهٔ صفحه بفهمد الان کدام است */}
      <span className="sr-only">
        حالت فعلی: {resolvedTheme === "dark" ? "تاریک" : "روشن"}
      </span>
    </div>
  );
}
