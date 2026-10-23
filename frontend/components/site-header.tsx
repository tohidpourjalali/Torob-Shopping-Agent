"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Search, Store, Clock, Sparkles } from "lucide-react";
import { Store as StoreIcon } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "خانه", Icon: Home },
  { href: "/discover", label: "ایجنت", Icon: Sparkles },
  { href: "/stores", label: "فروشگاه‌ها", Icon: StoreIcon },
  { href: "/tracking", label: "پیگیری", Icon: Clock },
];

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-30 border-b border-border/70 bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-2xl items-center justify-between gap-2 px-3 py-2">
        <Link prefetch={false} href="/" className="flex items-center gap-1.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <StoreIcon className="h-4 w-4" aria-hidden />
          </span>
          <span className="text-[13px] font-extrabold leading-tight">
            دستیار خرید حضوری
            <span className="block text-[9px] font-normal text-muted-foreground">تورب · تهران</span>
          </span>
        </Link>

        <div className="flex items-center gap-1.5">
          <nav className="flex items-center gap-0.5" aria-label="ناوبری اصلی">
            {NAV.map(({ href, label, Icon }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-1 rounded-full px-2 py-1 text-[10px] transition-colors",
                    active
                      ? "bg-primary/10 font-bold text-primary dark:bg-primary/20"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Icon className="h-3 w-3" aria-hidden />
                  <span className="hidden sm:inline">{label}</span>
                </Link>
              );
            })}
          </nav>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
