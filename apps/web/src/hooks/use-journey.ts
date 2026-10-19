"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { userApi } from "@/lib/api";
import { JOURNEY_TO_ROUTE } from "@/lib/constants";
import { useAuth } from "@/hooks/use-auth";

export interface JourneyState {
  current_step: string;
  finances_status: string;
  goals_status: string;
  portfolio_status: string;
}

export function useJourney() {
  const { user } = useAuth();
  const router = useRouter();
  const [journey, setJourney] = useState<JourneyState | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) return null;
    setLoading(true);
    try {
      const data = (await userApi.getJourney(user.id)) as unknown as JourneyState;
      setJourney(data);
      return data;
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    refresh().catch(() => undefined);
  }, [refresh]);

  const setStep = useCallback(
    async (step: string) => {
      if (!user) return;
      await userApi.setStep(user.id, step);
      await refresh();
    },
    [user, refresh],
  );

  const resumeRoute = useCallback(async () => {
    if (!user) return "/login";
    const data = await refresh();
    if (!data) return "/onboarding/welcome";
    return JOURNEY_TO_ROUTE[data.current_step] ?? "/onboarding/welcome";
  }, [user, refresh]);

  const goToResume = useCallback(async () => {
    const route = await resumeRoute();
    router.push(route);
  }, [resumeRoute, router]);

  return { journey, loading, refresh, setStep, resumeRoute, goToResume };
}

export function useRequireAuth(redirectTo = "/login") {
  const { user, isHydrated } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (isHydrated && !user) router.replace(redirectTo);
  }, [isHydrated, user, router, redirectTo]);
  return user;
}
