"use client";

import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { AuthProvider, useAuth } from "@/hooks/use-auth";
import { AppShell } from "@/components/app-shell";
import { activateWorkspaceUser, WORKSPACE_CHANGED } from "@/lib/workspace-cache";
import { twinQueryKey } from "@/hooks/use-decision-workspace";

function ScopedWorkspace({ children }: { children: ReactNode }) {
  const { user, isHydrated } = useAuth();
  const client = useQueryClient();
  const previousUser = useRef<number | null | undefined>(undefined);
  const userId = user?.id ?? null;

  useEffect(() => {
    if (!isHydrated) return;
    activateWorkspaceUser(userId);
    if (previousUser.current !== undefined && previousUser.current !== userId) {
      const previous = previousUser.current;
      // New-user hooks can mount before this effect. Cancel/remove only old
      // keys so clearing the old session cannot cancel the new user's load.
      void client.cancelQueries({ predicate: (query) => query.queryKey[0] !== "workspace" || query.queryKey[1] === previous });
      client.removeQueries({ predicate: (query) => query.queryKey[0] !== "workspace" || query.queryKey[1] === previous });
    }
    previousUser.current = userId;
  }, [client, isHydrated, userId]);

  useEffect(() => {
    if (!userId) return;
    const invalidate = (event: Event) => {
      const changedUser = (event as CustomEvent<{ userId?: number | null }>).detail?.userId;
      if (changedUser != null && changedUser !== userId) return;
      void (async () => {
        await client.cancelQueries({ queryKey: ["workspace", userId] });
        client.setQueryData(twinQueryKey(userId), null);
        client.setQueriesData({ queryKey: ["workspace", userId, "cached-decision"] }, { available: false, stale: true, reason: "Your financial inputs changed. Run a new analysis." });
        await client.invalidateQueries({ queryKey: ["workspace", userId] });
      })();
    };
    window.addEventListener(WORKSPACE_CHANGED, invalidate);
    return () => window.removeEventListener(WORKSPACE_CHANGED, invalidate);
  }, [client, userId]);

  // Reset page-local state immediately on an account switch as well as query
  // state. No previous account's result can render under a new identity.
  return <Fragment key={userId ?? "guest"}>{children}</Fragment>;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: {
    staleTime: 30_000, gcTime: 5 * 60_000, retry: false,
    refetchOnWindowFocus: false, refetchOnReconnect: true,
  } } }));

  return (
    <QueryClientProvider client={client}>
      <AuthProvider>
        <ScopedWorkspace><AppShell>{children}</AppShell></ScopedWorkspace>
      </AuthProvider>
    </QueryClientProvider>
  );
}
