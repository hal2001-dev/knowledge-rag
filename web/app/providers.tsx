"use client";

/**
 * App-wide providers: TanStack Query + shadcn TooltipProvider + Sonner Toaster.
 * Clerk Provider는 layout.tsx에서 직접 감싼다 (NextJS 16 + Clerk 6 권장 패턴).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  // QueryClient를 렌더 1회만 생성 (HMR 시 재사용)
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>{children}</TooltipProvider>
      <Toaster richColors position="top-center" />
    </QueryClientProvider>
  );
}
