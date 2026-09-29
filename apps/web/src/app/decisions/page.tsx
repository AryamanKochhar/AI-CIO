"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Button,
  CompletenessRing,
  ErrorState,
  Input,
  Label,
  LoadingState,
  PageHeader,
  ProfileSection,
  StatusBadge,
} from "@ai-cio/ui";
import type { DecisionObjective, DecisionResult, DigitalTwin } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { decisionsApi, twinApi } from "@/lib/api";
import { COMPLETENESS_LABELS, DECISION_OBJECTIVES, completenessPercent } from "@/lib/constants";
import { useRequireAuth } from "@/hooks/use-journey";
import { PortfolioPerformanceChart } from "@/components/portfolio-performance-chart";
import { DecisionResultView } from "@/components/decisions/decision-result-view";
import { GlassPanel, SectionHeader, SurfacePanel } from "@/components/design/system";

type Phase = "setup" | "running" | "result";

export default function DecisionsPage() {
  const user = useRequireAuth();
  const [twin, setTwin] = useState<DigitalTwin | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("setup");
  const [objective, setObjective] = useState<DecisionObjective>("review_equity_portfolio");
  const [availableCapital, setAvailableCapital] = useState("");
  const [minLiquidReserve, setMinLiquidReserve] = useState("");
  const [selectedGoalIds, setSelectedGoalIds] = useState<number[]>([]);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<DecisionResult | null>(null);
  const [cacheHint, setCacheHint] = useState<string | null>(null);

  const selectedObjective = useMemo(
    () => DECISION_OBJECTIVES.find((item) => item.value === objective),
    [objective],
  );

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setLoadError(null);
    twinApi
      .get(user.id)
      .then(async (data) => {
        if (cancelled) return;
        setTwin(data);
        setSelectedGoalIds((prev) => {
          if (prev.length) return prev.filter((id) => data.goals.items.some((g) => g.id === id));
          return data.goals.items.map((g) => g.id);
        });
        try {
          const cached = await decisionsApi.cached(user.id, "review_equity_portfolio");
          if (cancelled) return;
          if (cached.available && cached.result) {
            setResult(cached.result);
            setObjective((cached.result.objective as DecisionObjective) || "review_equity_portfolio");
            setPhase("result");
            setCacheHint(cached.result.cache?.note || "Loaded cached decision.");
          } else if (cached.stale) {
            setCacheHint(cached.reason || "Previous decision is stale — data changed. Run again.");
          }
        } catch {
          // best-effort cache hydrate
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setLoadError(err.message || "Could not load your profile.");
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  function toggleGoal(goalId: number) {
    setSelectedGoalIds((prev) =>
      prev.includes(goalId) ? prev.filter((id) => id !== goalId) : [...prev, goalId],
    );
  }

  async function runDecision(forceRefresh: boolean) {
    if (!user || !selectedObjective) return;
    if (selectedObjective.needsCapital && !availableCapital.trim()) {
      setRunError("Enter the amount you want to allocate.");
      return;
    }

    setRunError(null);
    setPhase("running");
    if (forceRefresh) setResult(null);

    const constraints: Record<string, unknown> = {};
    if (minLiquidReserve.trim()) {
      constraints.min_liquid_reserve = minLiquidReserve.trim();
    }
    if (selectedGoalIds.length) {
      constraints.goal_ids = selectedGoalIds;
    }

    try {
      const response = await decisionsApi.run(user.id, {
        objective,
        available_capital: selectedObjective.needsCapital ? availableCapital.trim() : undefined,
        constraints,
        force_refresh: forceRefresh,
      });
      setResult(response);
      setCacheHint(response.cache?.note || null);
      setPhase("result");
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "The decision could not be completed.");
      setPhase(result ? "result" : "setup");
    }
  }

  function handleProceed() {
    void runDecision(false);
  }

  function handleRefresh() {
    void runDecision(true);
  }

  function startOver() {
    setPhase("setup");
    setRunError(null);
  }

  if (!user) return <LoadingState message="Checking sign-in…" />;
  if (loadError) return <ErrorState title="Profile unavailable" message={loadError} />;
  if (!twin) return <LoadingState message="Loading your financial profile…" />;

  const completeness = twin.completeness;
  const pct = completenessPercent({ ...completeness });
  const liquid = twin.financial_position.liquid as { value?: string | null; known?: boolean };
  const portfolio = twin.portfolio.total_value as { value?: string | null; known?: boolean };
  const portfolioSnapshots = (Array.isArray(twin.portfolio.snapshots)
    ? twin.portfolio.snapshots
    : []) as Array<{
    month_year?: string;
    valuation?: string | null;
    change_amount?: string | null;
    change_pct?: string | null;
  }>;

  if (phase === "running") {
    return (
      <LoadingState message="Running decision analysis (portfolio, goals, tax, FDs, trajectory)… this can take up to a couple of minutes." />
    );
  }

  if (phase === "result" && result) {
    return (
      <DecisionResultView
        result={result}
        onStartOver={startOver}
        onRefresh={handleRefresh}
      />
    );
  }

  return (
    <div className="space-y-8">
      <GlassPanel strong>
        <PageHeader
          kicker="Decision support"
          title="Review your context, then proceed"
          description="Unchanged Twin/portfolio data reuses the last cached decision — no new LLM or market calls. Use Refresh analysis only when you want a fresh run."
        />
        <div className="mt-4">
          <CompletenessRing value={pct} label="Profile completeness" />
        </div>
        {cacheHint ? (
          <p className="mt-3 text-xs leading-relaxed text-slate-600">{cacheHint}</p>
        ) : null}
      </GlassPanel>

      <SurfacePanel>
        <h2 className="text-base font-semibold text-slate-900">Portfolio performance</h2>
        <p className="mt-1 text-sm text-slate-600">
          Historical valuation from your statement month-end snapshots — not a market prediction.
        </p>
        <div className="mt-4">
          <PortfolioPerformanceChart snapshots={portfolioSnapshots} />
        </div>
      </SurfacePanel>

      <SurfacePanel>
        <h2 className="text-base font-semibold text-slate-900">What the orchestrator will use</h2>
        <p className="mt-1 text-sm text-slate-600">
          Missing items are noted but may not block every decision type.
        </p>
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {Object.entries(completeness).map(([key, known]) => (
            <div key={key} className="flex items-center gap-2 text-sm">
              <span>{known ? "✓" : "○"}</span>
              <span className={known ? "text-slate-900" : "text-slate-500"}>
                {COMPLETENESS_LABELS[key] ?? key}
              </span>
              <StatusBadge status={known ? "known" : "unknown"}>
                {known ? "ready" : "missing"}
              </StatusBadge>
            </div>
          ))}
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <ProfileSection title="Liquid savings" source="You provided">
            <p className="text-sm text-slate-700">
              {liquid.known ? formatCurrency(liquid.value) : "Not provided"}
            </p>
          </ProfileSection>
          <ProfileSection title="Portfolio" source="Documents">
            <p className="text-sm text-slate-700">
              {portfolio.known ? formatCurrency(portfolio.value) : "Not provided"}
            </p>
          </ProfileSection>
          <ProfileSection title="Goals" source="You provided">
            <p className="text-sm text-slate-700">
              {twin.goals.items.length
                ? `${twin.goals.items.length} goal(s) on file`
                : "Not provided"}
            </p>
            <Link href="/onboarding/goals?return=/decisions" className="mt-2 inline-block">
              <Button variant="ghost">{twin.goals.items.length ? "Edit goals" : "Add goals"}</Button>
            </Link>
          </ProfileSection>
        </div>
      </SurfacePanel>

      <SurfacePanel>
        <h2 className="text-base font-semibold text-slate-900">Which goals should we score?</h2>
        <p className="mt-1 text-sm text-slate-600">
          Select goals to estimate how likely you are to hit them given income, expenses, and current funding.
        </p>
        {twin.goals.items.length === 0 ? (
          <p className="mt-4 text-sm text-slate-600">
            No goals yet.{" "}
            <Link href="/onboarding/goals?return=/decisions" className="underline">
              Add a goal
            </Link>{" "}
            (and income/expenses on your profile) for a likelihood estimate.
          </p>
        ) : (
          <ul className="mt-4 space-y-2">
            {twin.goals.items.map((goal) => {
              const checked = selectedGoalIds.includes(goal.id);
              return (
                <li key={goal.id}>
                  <label
                    className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors ${
                      checked ? "border-slate-900 bg-slate-50" : "border-slate-200 bg-white hover:border-slate-300"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={checked}
                      onChange={() => toggleGoal(goal.id)}
                    />
                    <span>
                      <span className="block font-medium text-slate-900">{goal.name}</span>
                      <span className="text-sm text-slate-600">
                        {goal.goal_type}
                        {goal.target_amount ? ` · target ${formatCurrency(goal.target_amount)}` : ""}
                        {goal.target_date ? ` · by ${goal.target_date}` : ""}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
        <div className="mt-3">
          <Link href="/onboarding/twin">
            <Button variant="ghost">Update income on profile</Button>
          </Link>
        </div>
      </SurfacePanel>

      <SurfacePanel>
        <h2 className="text-base font-semibold text-slate-900">What do you want to do?</h2>
        <div className="mt-4 space-y-3">
          {DECISION_OBJECTIVES.map((item) => {
            const active = objective === item.value;
            return (
              <button
                key={item.value}
                type="button"
                onClick={() => setObjective(item.value)}
                className={`w-full rounded-xl border p-4 text-left transition-colors ${
                  active
                    ? "border-slate-900 bg-slate-50 ring-2 ring-slate-900/10"
                    : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                <p className="font-medium text-slate-900">{item.label}</p>
                <p className="mt-1 text-sm text-slate-600">{item.description}</p>
              </button>
            );
          })}
        </div>
      </SurfacePanel>

      {selectedObjective?.needsCapital ? (
        <SurfacePanel>
          <h2 className="text-base font-semibold text-slate-900">Amount to allocate</h2>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="capital">Available capital (₹)</Label>
              <Input
                id="capital"
                type="text"
                inputMode="decimal"
                placeholder="e.g. 100000"
                value={availableCapital}
                onChange={(e) => setAvailableCapital(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="reserve">Minimum cash to keep (optional)</Label>
              <Input
                id="reserve"
                type="text"
                inputMode="decimal"
                placeholder="e.g. 20000"
                value={minLiquidReserve}
                onChange={(e) => setMinLiquidReserve(e.target.value)}
              />
            </div>
          </div>
        </SurfacePanel>
      ) : null}

      {runError ? (
        <div className="rounded-2xl border border-red-200 bg-red-50/90 px-5 py-4">
          <p className="text-sm text-red-800">{runError}</p>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <Button onClick={handleProceed}>Proceed with analysis</Button>
        <Link href="/onboarding/twin">
          <Button variant="secondary">Back to profile</Button>
        </Link>
      </div>

      <p className="text-xs text-slate-500">
        AI-CIO provides structured observations for review. This is not investment advice and does not execute trades.
      </p>
    </div>
  );
}
