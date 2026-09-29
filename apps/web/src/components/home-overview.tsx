"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { formatCurrency } from "@ai-cio/utils";
import type { DigitalTwin } from "@ai-cio/contracts";
import { twinApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { GlassPanel, MetricTile, SectionHeader, SurfacePanel } from "@/components/design/system";

export function HomeOverview() {
  const { user } = useAuth();
  const [twin, setTwin] = useState<DigitalTwin | null>(null);

  useEffect(() => {
    if (!user) {
      setTwin(null);
      return;
    }
    let cancelled = false;
    twinApi
      .get(user.id)
      .then((data) => {
        if (!cancelled) setTwin(data);
      })
      .catch(() => {
        if (!cancelled) setTwin(null);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (!user) return null;
  if (!twin) {
    return (
      <SurfacePanel>
        <p className="text-sm text-slate-600">Loading your financial overview…</p>
      </SurfacePanel>
    );
  }

  const liquid = twin.financial_position.liquid as { value?: string | null; known?: boolean } | undefined;
  const portfolio = twin.portfolio.total_value as { value?: string | null; known?: boolean } | undefined;
  const holdings = Array.isArray(twin.portfolio.holdings) ? twin.portfolio.holdings : [];
  const goals = twin.goals.items || [];
  const keyFinding = goals.length
    ? `${goals.length} goal${goals.length === 1 ? "" : "s"} on file. Open Decisions for trajectory and attention items.`
    : "Complete goals and finances to unlock a richer Decision Brief.";

  return (
    <GlassPanel strong>
      <SectionHeader
        eyebrow="Overview"
        title="Your financial snapshot"
        description="Existing Twin data only — open Decisions for full AI-CIO analysis."
        action={
          <Link
            href="/decisions"
            className="text-sm font-medium text-[var(--aic-navy)] underline-offset-2 hover:underline"
          >
            Open Decisions →
          </Link>
        }
      />
      <div className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-4">
        <MetricTile
          label="Portfolio"
          value={portfolio?.known && portfolio.value ? formatCurrency(portfolio.value) : "—"}
        />
        <MetricTile
          label="Liquid"
          value={liquid?.known && liquid.value ? formatCurrency(liquid.value) : "—"}
        />
        <MetricTile label="Goals" value={String(goals.length)} />
        <MetricTile label="Holdings" value={String(holdings.length)} />
      </div>
      <hr className="aic-divider my-5" />
      <p className="aic-meta uppercase tracking-[0.1em]">Most important finding</p>
      <p className="mt-2 text-base leading-relaxed text-slate-800">{keyFinding}</p>
    </GlassPanel>
  );
}
