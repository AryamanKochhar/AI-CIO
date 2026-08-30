"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { AuthProvider } from "@/hooks/use-auth";
import { AppShell } from "@/components/app-shell";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={client}>
      <AuthProvider>
        <AppShell>{children}</AppShell>
      </AuthProvider>
    </QueryClientProvider>
  );
}
