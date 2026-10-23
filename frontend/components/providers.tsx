"use strict";

import * as React from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import { ToasterComponent as Toaster } from "@/components/ui/sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system" enableSystem>
      {children}
      <Toaster />
    </NextThemesProvider>
  );
}
