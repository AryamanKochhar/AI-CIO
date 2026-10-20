"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
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
import type { DecisionObjective, DecisionResult } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { decisionsApi } from "@/lib/api";
import {
  COMPLETENESS_LABELS,
  DECISION_OBJECTIVES,
  completenessPercent,
} from "@/lib/constants";
import { useRequireAuth } from "@/hooks/use-journey";
import { PortfolioPerformanceChart } from "@/components/portfolio-performance-chart";
import { DecisionResultView } from "@/components/decisions/decision-result-view";
import { GlassPanel, SurfacePanel } from "@/components/design/system";
import { DecisionNextSteps } from "@/components/decision-next-steps";
import { useDecisionWorkspace } from "@/hooks/use-decision-workspace";

type Phase = "setup" | "running" | "result";

export default function DecisionsPage() {
  const user = useRequireAuth();
  const [phase, setPhase] = useState<Phase>("setup");
  const [objective, setObjective] = useState<DecisionObjective>(
    "review_equity_portfolio",
  );
  const { twin, cached, isValidating, loadError, cacheError, recordDecision } =
    useDecisionWorkspace(user?.id, objective);
  const editingSetup = useRef(false);
  const initializedGoals = useRef(false);
  const [availableCapital, setAvailableCapital] = useState("");
  const [minLiquidReserve, setMinLiquidReserve] = useState("");
  const [selectedGoalIds, setSelectedGoalIds] = useState<number[]>([]);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<DecisionResult | null>(null);
  const [cacheHint, setCacheHint] = useState<string | null>(null);

  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("objective");
    if (requested && DECISION_OBJECTIVES.some((item) => item.value === requested)) {
      editingSetup.current = true;
      setObjective(requested as DecisionObjective);
      setResult(null); setPhase("setup");
    }
  }, []);

  useEffect(() => {
    if (objective !== "plan_fire" || !twin) return;
    const requestedId = new URLSearchParams(window.location.search).get("goal_id");
    const goals = twin.goals.items.filter((goal) => goal.goal_type === "fire");
    const chosen = goals.find((goal) => String(goal.id) === requestedId) ?? goals[0];
    setSelectedGoalIds(chosen ? [chosen.id] : []);
  }, [objective, twin]);

  const selectedObjective = useMemo(
    () => DECISION_OBJECTIVES.find((item) => item.value === objective),
    [objective],
  );

  useEffect(() => {
    if (!twin) return;
    if (!initializedGoals.current) {
      initializedGoals.current = true;
      if (objective !== "plan_fire") setSelectedGoalIds(twin.goals.items.map((goal) => goal.id));
    } else {
      setSelectedGoalIds((previous) =>
        previous.filter((id) =>
          twin.goals.items.some((goal) => goal.id === id),
        ),
      );
    }
  }, [twin, objective]);

  useEffect(() => {
    if (cached?.stale) {
      setResult(null);
      setPhase((current) => (current === "running" ? current : "setup"));
      setCacheHint(
        cached.reason ||
          "Your saved analysis needs an update. Run a fresh review.",
      );
    } else if (cached?.available && cached.result && !editingSetup.current) {
      setResult(cached.result);
      setPhase("result");
      setCacheHint(
        cached.result.cache?.note || "Your saved decision is ready.",
      );
    }
  }, [cached]);

  function toggleGoal(goalId: number) {
    setSelectedGoalIds((prev) =>
      prev.includes(goalId)
        ? prev.filter((id) => id !== goalId)
        : [...prev, goalId],
    );
  }

  async function runDecision(forceRefresh: boolean) {
    if (!user || !selectedObjective) return;
    if (selectedObjective.needsCapital && !availableCapital.trim()) {
      setRunError("Enter the amount you want to allocate.");
      return;
    }

    setRunError(null);
    editingSetup.current = true;
    setPhase("running");
    if (forceRefresh) setResult(null);

    if (objective === "plan_fire" && (!twin || selectedGoalIds.length !== 1 || !twin.goals.items.some((goal) => goal.id === selectedGoalIds[0] && goal.goal_type === "fire"))) {
      setRunError("Create and save a FIRE goal, then select that goal for this review.");
      setPhase("setup");
      return;
    }
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
        available_capital: selectedObjective.needsCapital
          ? availableCapital.trim()
          : undefined,
        constraints,
        force_refresh: forceRefresh,
      });
      setResult(response);
      recordDecision(response);
      editingSetup.current = false;
      setCacheHint(response.cache?.note || null);
      setPhase("result");
    } catch (err) {
      setRunError(
        err instanceof Error
          ? err.message
          : "The decision could not be completed.",
      );
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
    editingSetup.current = true;
    setPhase("setup");
    setRunError(null);
  }

  if (!user) return <LoadingState message="Checking sign-in…" />;
  if (phase === "running") {
    return (
      <LoadingState message="Running decision analysis (portfolio, goals, tax, FDs, trajectory)… this can take up to a couple of minutes." />
    );
  }

  if (phase === "result" && result && !cached?.stale) {
    const expiresAt = Date.parse(result.cache?.expires_at || "");
    if (Number.isFinite(expiresAt) && expiresAt <= Date.now()) {
      return (
        <LoadingState message="Your saved analysis has expired. Checking the latest information…" />
      );
    }
    return (
      <div className="space-y-4">
        {isValidating ? (
          <p role="status" className="text-xs text-slate-500">
            {cached?.available
              ? "Saved analysis checked. Refreshing profile details…"
              : "Rechecking your saved analysis and profile…"}
          </p>
        ) : null}
        {loadError ? (
          <p className="text-xs text-amber-800">
            Your saved brief is available, but profile details could not be
            refreshed.
          </p>
        ) : null}
        <DecisionResultView
          result={result}
          onStartOver={startOver}
          onRefresh={handleRefresh}
          checking={isValidating}
          onExploreWhatIf={() => {
            editingSetup.current = true;
            setObjective("explore_counterfactuals");
            setPhase("setup");
            setRunError(null);
          }}
        />
      </div>
    );
  }

  if (loadError)
    return <ErrorState title="Profile unavailable" message={loadError} />;
  if (!twin) return <LoadingState message="Loading your financial profile…" />;

  const completeness = twin.completeness;
  const pct = completenessPercent({ ...completeness });
  const liquid = twin.financial_position.liquid as {
    value?: string | null;
    known?: boolean;
  };
  const portfolio = twin.portfolio.total_value as {
    value?: string | null;
    known?: boolean;
  };
  const portfolioSnapshots = (
    Array.isArray(twin.portfolio.snapshots) ? twin.portfolio.snapshots : []
  ) as Array<{
    month_year?: string;
    valuation?: string | null;
    change_amount?: string | null;
    change_pct?: string | null;
  }>;

  return (
    <div className="flex flex-col gap-6">
      <GlassPanel strong className="order-1">
        <PageHeader
          kicker="Decision support"
          title="What would you like to understand?"
          description="Start with one question. We'll connect it with your financial twin, show what matters and explain the reasoning."
        />
        <div className="mt-4">
          <CompletenessRing value={pct} label="Recorded information" />
        </div>
        {cacheHint ? (
          <p className="mt-3 text-xs leading-relaxed text-slate-600">
            {cacheHint}
          </p>
        ) : null}
        {isValidating ? (
          <p role="status" className="mt-3 text-xs text-slate-500">
            Checking latest profile…
          </p>
        ) : null}
        {cacheError ? (
          <p className="mt-3 text-xs text-amber-800">
            The saved decision could not be checked. You can still build a fresh
            brief.
          </p>
        ) : null}
      </GlassPanel>

      <SurfacePanel className="order-2">
        <p className="text-[10px] font-semibold uppercase tracking-[.18em] text-teal-700">
          01 / Choose your focus
        </p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-900">
          One question. The whole picture.
        </h2>
        <div
          className="mt-5 grid gap-3 sm:grid-cols-2"
          role="group"
          aria-label="Choose a decision focus"
        >
          {DECISION_OBJECTIVES.map((item, index) => {
            const active = objective === item.value;
            return (
              <button
                key={item.value}
                type="button"
                aria-pressed={active}
                onClick={() => {
                  editingSetup.current = true;
                  setObjective(item.value);
                }}
                className={`w-full rounded-xl border p-4 text-left transition-colors ${
                  active
                    ? "border-teal-600 bg-[#f0f8f3] ring-1 ring-teal-600"
                    : "border-slate-200 bg-white hover:border-teal-200 hover:bg-slate-50"
                }`}
              >
                <span className="mb-3 flex items-center justify-between">
                  <span
                    className={`flex h-7 w-7 items-center justify-center rounded-lg text-[10px] font-semibold ${active ? "bg-teal-700 text-white" : "bg-slate-100 text-slate-400"}`}
                  >
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="text-[10px] font-medium uppercase tracking-wider text-teal-700">
                    {active ? "Selected ✓" : "Choose ↗"}
                  </span>
                </span>
                <p className="text-sm font-semibold text-slate-900">
                  {item.label}
                </p>
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  {item.value === "review_equity_portfolio"
                    ? "Review holdings against your mindset, goals and current financial position."
                    : item.description}
                </p>
              </button>
            );
          })}
        </div>
      </SurfacePanel>

      {selectedObjective?.needsCapital ? (
        <SurfacePanel className="order-3">
          <h2 className="text-base font-semibold text-slate-900">
            Amount to allocate
          </h2>
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

      <SurfacePanel className="order-4">
        <p className="text-[10px] font-semibold uppercase tracking-[.18em] text-teal-700">
          02 / Add your direction
        </p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-900">
          {objective === "plan_fire" ? "Which saved FIRE plan should we review?" : "Which goals belong in this review?"}
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Compare goal funding under stated assumptions using income, spending
          and the money already set aside.
        </p>
        {objective === "plan_fire" ? <div className="mt-4 rounded-xl border border-teal-100 bg-teal-50/60 p-4"><p className="text-sm leading-6 text-slate-700">A FIRE goal stores your chosen age, spending, investment budget, pension and scenario assumptions. This decision uses one saved plan and applies your recorded psychometric profile.</p><Link href="/fire" className="mt-3 inline-block text-sm font-semibold text-teal-800 underline underline-offset-4">Create or update my FIRE goal ↗</Link></div> : null}
        {(objective === "plan_fire" ? twin.goals.items.filter((goal) => goal.goal_type === "fire") : twin.goals.items).length === 0 ? (
          <p className="mt-4 text-sm text-slate-600">
            No goals yet.{" "}
            <Link
              href="/onboarding/goals?return=/decisions"
              className="underline"
            >
              Add a goal
            </Link>{" "}
            and record your income and expenses to explore its funding outlook.
          </p>
        ) : (
          <ul className="mt-4 space-y-2">
            {(objective === "plan_fire" ? twin.goals.items.filter((goal) => goal.goal_type === "fire") : twin.goals.items).map((goal) => {
              const checked = selectedGoalIds.includes(goal.id);
              return (
                <li key={goal.id}>
                  <label
                    className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors ${
                      checked
                        ? "border-slate-900 bg-slate-50"
                        : "border-slate-200 bg-white hover:border-slate-300"
                    }`}
                  >
                    <input
                      type={objective === "plan_fire" ? "radio" : "checkbox"}
                      name={objective === "plan_fire" ? "fire-goal" : undefined}
                      className="mt-1"
                      checked={checked}
                      onChange={() => objective === "plan_fire" ? setSelectedGoalIds([goal.id]) : toggleGoal(goal.id)}
                    />
                    <span>
                      <span className="block font-medium text-slate-900">
                        {goal.name}
                      </span>
                      <span className="text-sm text-slate-600">
                        {goal.goal_type}
                        {goal.target_amount
                          ? ` · target ${formatCurrency(goal.target_amount)}`
                          : ""}
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

      {runError ? (
        <div
          role="alert"
          className="order-5 rounded-2xl border border-red-200 bg-red-50/90 px-5 py-4"
        >
          <p className="text-sm text-red-800">{runError}</p>
        </div>
      ) : null}

      <div className="order-5 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-teal-100 bg-[#eef7f2] px-5 py-5">
        <div>
          <p className="text-sm font-semibold text-slate-800">
            Ready for a clearer next step?
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {selectedGoalIds.length} goal
            {selectedGoalIds.length === 1 ? "" : "s"} included · educational
            review, no trades are executed.
          </p>
        </div>
        <Button onClick={handleProceed}>Build my decision brief ↗</Button>
      </div>

      <details className="order-6 rounded-2xl border border-slate-200 bg-white p-5">
        <summary className="cursor-pointer text-sm font-semibold text-slate-700">
          Review the information behind this analysis{" "}
          <span className="ml-2 text-xs font-normal text-slate-400">
            {Object.values(completeness).filter(Boolean).length} inputs ready
          </span>
        </summary>
        <SurfacePanel className="mt-4 border-0 !p-0 !shadow-none">
          <h2 className="text-base font-semibold text-slate-900">
            The context we will use
          </h2>
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
                {portfolio.known
                  ? formatCurrency(portfolio.value)
                  : "Not provided"}
              </p>
            </ProfileSection>
            <ProfileSection title="Goals" source="You provided">
              <p className="text-sm text-slate-700">
                {twin.goals.items.length
                  ? `${twin.goals.items.length} goal(s) on file`
                  : "Not provided"}
              </p>
              <Link
                href="/onboarding/goals?return=/decisions"
                className="mt-2 inline-block"
              >
                <Button variant="ghost">
                  {twin.goals.items.length ? "Edit goals" : "Add goals"}
                </Button>
              </Link>
            </ProfileSection>
          </div>
        </SurfacePanel>
      </details>

      <details className="order-7 rounded-2xl border border-slate-200 bg-white p-5">
        <summary className="cursor-pointer text-sm font-semibold text-slate-700">
          Your statement history{" "}
          <span className="ml-2 text-xs font-normal text-slate-400">
            Optional context
          </span>
        </summary>
        <SurfacePanel className="mt-4 border-0 !p-0 !shadow-none">
          <h2 className="text-base font-semibold text-slate-900">
            Portfolio performance
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Historical valuation from your statement month-end snapshots — not a
            market prediction.
          </p>
          <div className="mt-4">
            <PortfolioPerformanceChart snapshots={portfolioSnapshots} />
          </div>
        </SurfacePanel>
      </details>

      <div className="order-8">
        <DecisionNextSteps />
      </div>
    </div>
  );
}
