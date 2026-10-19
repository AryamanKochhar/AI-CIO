"use client";

import { useCallback, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { DecisionObjective, DecisionResult, DigitalTwin } from "@ai-cio/contracts";
import { decisionsApi, twinApi } from "@/lib/api";
import { readTwinSnapshot, writeTwinSnapshot } from "@/lib/workspace-cache";

export type CachedDecisionResponse = Awaited<ReturnType<typeof decisionsApi.cached>>;
export const twinQueryKey = (userId: number) => ["workspace", userId, "twin"] as const;
export const decisionQueryKey = (userId: number, objective: DecisionObjective = "review_equity_portfolio") => ["workspace", userId, "cached-decision", objective] as const;

export function useDecisionWorkspace(userId?: number, objective: DecisionObjective = "review_equity_portfolio") {
  const queryClient = useQueryClient();
  const snapshot = useMemo(() => userId ? readTwinSnapshot(userId) : undefined, [userId]);
  const twin = useQuery<DigitalTwin | null>({
    queryKey: twinQueryKey(userId ?? 0), enabled: Boolean(userId),
    queryFn: async ({ signal }) => {
      const data = await twinApi.get(userId!, signal);
      writeTwinSnapshot(userId!, data);
      return data;
    },
    initialData: snapshot?.twin,
    initialDataUpdatedAt: snapshot?.writtenAt,
    staleTime: 0, refetchOnMount: true,
  });
  // Independent query: never wait for the expensive Twin request before
  // checking the persisted decision. A hard reload validates with the server.
  const cached = useQuery<CachedDecisionResponse>({
    queryKey: decisionQueryKey(userId ?? 0, objective), enabled: Boolean(userId),
    queryFn: ({ signal }) => decisionsApi.cached(userId!, objective, signal),
    staleTime: 0, refetchOnMount: "always", refetchOnWindowFocus: true,
    refetchInterval: (query) => {
      if (!query.state.data?.available) return false;
      const expiry = Date.parse(query.state.data.result?.cache?.expires_at ?? "");
      return Number.isFinite(expiry) ? Math.max(1000, Math.min(30_000, expiry - Date.now())) : 30_000;
    },
  });
  const refetchTwin = twin.refetch;
  const refetchCached = cached.refetch;
  const refresh = useCallback(async () => {
    await Promise.all([refetchTwin(), refetchCached()]);
  }, [refetchTwin, refetchCached]);
  const recordDecision = useCallback((result: DecisionResult) => {
    if (userId && result.user_id === userId) queryClient.setQueryData(decisionQueryKey(userId, result.objective), { available: true, stale: false, result });
  }, [queryClient, userId]);
  // An expired or failed backend validation must not expose an old result as
  // current, even though React Query keeps previous data during revalidation.
  const serverDecision: CachedDecisionResponse | null = cached.isError
    ? { available: false, stale: true, reason: "Saved analysis could not be revalidated. Check the connection and try again." }
    : cached.isFetching ? null : cached.data ?? null;
  return {
    twin: twin.isError ? null : twin.data ?? null,
    cached: serverDecision,
    isLoading: Boolean(userId) && !twin.data && twin.isPending,
    isValidating: twin.isFetching || cached.isFetching,
    loadError: twin.error instanceof Error ? twin.error.message : null,
    cacheError: cached.error instanceof Error ? cached.error.message : null,
    refresh, recordDecision,
  };
}
