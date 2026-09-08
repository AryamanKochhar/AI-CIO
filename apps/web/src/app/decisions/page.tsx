"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
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

type Phase = "setup" | "running" | "result";

const ALLOCATION_LABELS: Record<string, string> = {
  cash: "Cash",
  debt: "Debt / fixed income",
  equity: "Equity",
};

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
      .then((data) => {
        if (cancelled) return;
        setTwin(data);
        setSelectedGoalIds((prev) => {
          if (prev.length) return prev.filter((id) => data.goals.items.some((g) => g.id === id));
          return data.goals.items.map((g) => g.id);
        });
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

  async function handleProceed() {
    if (!user || !selectedObjective) return;
    if (selectedObjective.needsCapital && !availableCapital.trim()) {
      setRunError("Enter the amount you want to allocate.");
      return;
    }

    setRunError(null);
    setPhase("running");
    setResult(null);

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
      });
      setResult(response);
      setPhase("result");
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "The decision could not be completed.");
      setPhase("setup");
    }
  }

  function startOver() {
    setPhase("setup");
    setResult(null);
    setRunError(null);
  }

  if (!user) return null;
  if (loadError) return <ErrorState title="Profile unavailable" message={loadError} />;
  if (!twin) return <LoadingState message="Loading your financial profile…" />;

  const completeness = twin.completeness;
  const pct = completenessPercent({ ...completeness });
  const liquid = twin.financial_position.liquid as { value?: string | null; known?: boolean };
  const portfolio = twin.portfolio.total_value as { value?: string | null; known?: boolean };

  if (phase === "running") {
    return <LoadingState message="Running your decision analysis…" />;
  }

  if (phase === "result" && result) {
    return (
      <div className="space-y-6">
        <Card className="aic-card-glow">
          <PageHeader
            kicker="Decision result"
            title="Here is what the analysis found"
            description="This is structured guidance for review — not a buy or sell instruction."
          />
          <p className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-800">{result.decision}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusBadge status="known">Confidence: {result.confidence}</StatusBadge>
            <StatusBadge status={result.validation.passed ? "known" : "unknown"}>
              Validation: {result.validation.passed ? "passed" : "issues found"}
            </StatusBadge>
            {result.execution?.agent ? (
              <StatusBadge status="known">Agent: {result.execution.agent}</StatusBadge>
            ) : null}
          </div>
        </Card>

        {result.goal_likelihood && result.goal_likelihood.length > 0 ? (
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">How likely are you to hit your goals?</h2>
            <p className="mt-1 text-sm text-slate-600">
              Illustrative projection from surplus (income − expenses), current funding, and your target date —
              assuming ~10% p.a. returns. Not a guarantee.
            </p>
            <ul className="mt-4 space-y-3">
              {result.goal_likelihood.map((item) => {
                const status = item.likelihood_status ?? "unknown";
                const badgeStatus =
                  status === "likely" || status === "possible" ? "known" : "unknown";
                return (
                  <li
                    key={item.goal_id ?? item.goal_name}
                    className="rounded-lg border border-slate-200 bg-white p-4"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-slate-900">{item.goal_name || "Goal"}</p>
                      <StatusBadge status={badgeStatus}>
                        {status.replace(/_/g, " ")}
                        {item.likelihood_percent != null ? ` · ~${item.likelihood_percent}%` : ""}
                      </StatusBadge>
                    </div>
                    <p className="mt-2 text-sm text-slate-700">{item.narrative}</p>
                    <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                      {item.projected_corpus ? <span>Projected: {formatCurrency(item.projected_corpus)}</span> : null}
                      {item.target_amount ? <span>Target: {formatCurrency(item.target_amount)}</span> : null}
                      {item.required_monthly_contribution ? (
                        <span>Need ~{formatCurrency(item.required_monthly_contribution)}/mo</span>
                      ) : null}
                      {item.years_remaining != null ? <span>~{item.years_remaining} years</span> : null}
                    </div>
                    {item.disclaimer ? <p className="mt-2 text-xs text-slate-400">{item.disclaimer}</p> : null}
                  </li>
                );
              })}
            </ul>
          </Card>
        ) : null}

        {result.portfolio_health?.score != null ? (
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">AI Portfolio Health Score</h2>
            <p className="mt-1 text-sm text-slate-600">
              One score from available Twin metrics. Missing fundamentals are excluded, not invented.
            </p>
            <div className="mt-4 flex flex-wrap items-end gap-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  {result.portfolio_health.label ?? "Portfolio Health"}
                </p>
                <p className="text-4xl font-semibold text-slate-900">
                  {result.portfolio_health.score}
                  <span className="text-lg text-slate-500">/{result.portfolio_health.max_score ?? 100}</span>
                </p>
                <p className="mt-1 text-amber-600">
                  {"★".repeat(result.portfolio_health.stars ?? 0)}
                  {"☆".repeat(Math.max(0, 5 - (result.portfolio_health.stars ?? 0)))}
                </p>
              </div>
            </div>
            {result.portfolio_health.components ? (
              <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(result.portfolio_health.components).map(([key, comp]) => (
                  <div key={key} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      {key.replace(/_/g, " ")}
                    </p>
                    <p className="mt-1 text-xl font-semibold text-slate-900">
                      {comp.available && comp.score != null ? comp.score : "—"}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">{comp.note}</p>
                  </div>
                ))}
              </div>
            ) : null}
            {result.portfolio_health.methodology ? (
              <p className="mt-4 text-xs text-slate-500">{result.portfolio_health.methodology}</p>
            ) : null}
          </Card>
        ) : null}

        {result.top_worries && result.top_worries.length > 0 ? (
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">What should I worry about?</h2>
            <p className="mt-1 text-sm text-slate-600">Top issues that need attention before optional optimisation.</p>
            <ol className="mt-4 space-y-3">
              {result.top_worries.map((worry, idx) => (
                <li
                  key={`${worry.title}-${idx}`}
                  className="rounded-lg border border-slate-200 bg-white p-4"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-slate-900">
                      {idx + 1}. {worry.title}
                    </span>
                    {worry.severity ? (
                      <StatusBadge status={worry.severity === "high" ? "unknown" : "known"}>
                        {worry.severity}
                      </StatusBadge>
                    ) : null}
                  </div>
                  <p className="mt-2 text-sm text-slate-700">{worry.detail}</p>
                  {worry.metric ? (
                    <p className="mt-1 text-sm font-medium text-slate-800">Metric: {worry.metric}</p>
                  ) : null}
                  {worry.recommended_range ? (
                    <p className="mt-1 text-xs text-slate-500">{worry.recommended_range}</p>
                  ) : null}
                </li>
              ))}
            </ol>
          </Card>
        ) : null}

        {result.concentration_analysis && Object.keys(result.concentration_analysis).length > 0 ? (
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">Portfolio concentration analysis</h2>
            <p className="mt-1 text-sm text-slate-600">Identify concentration risk — not just allocation charts.</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Largest holding", result.concentration_analysis.largest_holding_percent],
                ["Top 3", result.concentration_analysis.top_3_percent],
                ["Top 5", result.concentration_analysis.top_5_percent],
                ["Top 10", result.concentration_analysis.top_10_percent],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">
                    {value != null ? `${value}%` : "—"}
                  </p>
                </div>
              ))}
            </div>
            {Array.isArray(result.concentration_analysis.asset_class_concentration) ? (
              <div className="mt-4">
                <p className="text-sm font-medium text-slate-900">Asset-class concentration</p>
                <ul className="mt-2 space-y-1 text-sm text-slate-700">
                  {(result.concentration_analysis.asset_class_concentration as Array<{ bucket?: string; percent?: string }>).map(
                    (row) => (
                      <li key={row.bucket} className="flex justify-between gap-3">
                        <span>{(row.bucket || "").replace(/_/g, " ")}</span>
                        <span className="font-medium">{row.percent ? `${row.percent}%` : "—"}</span>
                      </li>
                    ),
                  )}
                </ul>
              </div>
            ) : null}
            {Array.isArray(result.concentration_analysis.geographic_concentration) ? (
              <p className="mt-3 text-xs text-slate-500">
                {(result.concentration_analysis.geographic_concentration as Array<{ region?: string; note?: string }>)[0]
                  ?.note || "Geographic tags limited to domestic statements today."}
              </p>
            ) : null}
          </Card>
        ) : null}

        {result.true_exposure ? (
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">True portfolio exposure</h2>
            <p className="mt-1 text-sm text-slate-600">
              {result.true_exposure.question ?? "What am I actually invested in?"}
            </p>
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              <div>
                <p className="text-sm font-medium text-slate-900">Sector exposure</p>
                <ul className="mt-2 space-y-1 text-sm text-slate-700">
                  {(result.true_exposure.sector_exposure || []).slice(0, 6).map((row) => (
                    <li key={row.sector} className="flex justify-between gap-2">
                      <span>{row.sector}</span>
                      <span className="font-medium">{row.percent ? `${row.percent}%` : "—"}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-sm font-medium text-slate-900">Market cap</p>
                <ul className="mt-2 space-y-1 text-sm text-slate-700">
                  {(result.true_exposure.market_cap_exposure || []).slice(0, 6).map((row) => (
                    <li key={row.category} className="flex justify-between gap-2">
                      <span>{row.category}</span>
                      <span className="font-medium">{row.percent ? `${row.percent}%` : "—"}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-sm font-medium text-slate-900">Economic themes</p>
                <ul className="mt-2 space-y-1 text-sm text-slate-700">
                  {(result.true_exposure.economic_themes || []).slice(0, 6).map((row) => (
                    <li key={row.theme} className="flex justify-between gap-2">
                      <span>{row.theme}</span>
                      <span className="font-medium">{row.percent ? `${row.percent}%` : "—"}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            {result.true_exposure.methodology ? (
              <p className="mt-4 text-xs text-slate-500">{result.true_exposure.methodology}</p>
            ) : null}
          </Card>
        ) : null}

        {result.quality_valuation ? (
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">Quality × Valuation</h2>
            <p className="mt-1 text-sm text-slate-600">
              Analytical framework for holdings — not a buy/sell signal.
            </p>
            {result.quality_valuation.available ? (
              <p className="mt-3 text-sm text-slate-700">Fundamentals loaded.</p>
            ) : (
              <div className="mt-4">
                <div className="relative mx-auto aspect-square max-w-md rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4">
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="h-px w-full bg-slate-300" />
                  </div>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="h-full w-px bg-slate-300" />
                  </div>
                  <p className="absolute left-3 top-3 text-xs text-slate-500">Watch</p>
                  <p className="absolute right-3 top-3 text-xs text-slate-500">Attractive</p>
                  <p className="absolute bottom-3 left-3 text-xs text-slate-500">Value trap</p>
                  <p className="absolute bottom-3 right-3 text-xs text-slate-500">Expensive</p>
                  <p className="absolute inset-0 flex items-center justify-center px-8 text-center text-sm text-slate-600">
                    No holdings placed — fundamentals not available yet
                  </p>
                </div>
                <p className="mt-3 text-xs text-slate-500">{result.quality_valuation.reason}</p>
              </div>
            )}
          </Card>
        ) : null}

        {result.recommended_actions && result.recommended_actions.length > 0 ? (
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">What you should do / change</h2>
            <p className="mt-1 text-sm text-slate-600">
              Concrete review actions from your holdings, concentration, and style/sector tilts — not automatic trades.
            </p>
            <ul className="mt-4 space-y-2 text-sm text-slate-700">
              {result.recommended_actions.map((line) => (
                <li key={line} className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-100">
                  {line}
                </li>
              ))}
            </ul>
          </Card>
        ) : null}

        {result.insight_cards && result.insight_cards.length > 0 ? (
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">Portfolio insights</h2>
            <p className="mt-1 text-sm text-slate-600">
              Why these decisions matter — concentration, sector/style imbalance, behaviour.
            </p>
            <div className="mt-4 space-y-3">
              {result.insight_cards.map((card) => (
                <div
                  key={`${card.type}-${card.title}`}
                  className="rounded-lg border border-slate-200 bg-slate-50 p-4"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium text-slate-900">{card.title}</p>
                    {card.severity ? (
                      <StatusBadge status={card.severity === "high" ? "unknown" : "known"}>
                        {card.severity}
                      </StatusBadge>
                    ) : null}
                    <span className="text-xs uppercase tracking-wide text-slate-500">{card.type}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-700">{card.detail}</p>
                </div>
              ))}
            </div>
          </Card>
        ) : null}

        {(result.style_allocation && result.style_allocation.length > 0) ||
        (result.sector_allocation && result.sector_allocation.length > 0) ? (
          <div className="grid gap-4 md:grid-cols-2">
            {result.style_allocation && result.style_allocation.length > 0 ? (
              <Card className="aic-card-glow">
                <h2 className="text-base font-semibold text-slate-900">Style mix (heuristic)</h2>
                <p className="mt-1 text-xs text-slate-500">From fund/holding names — not official categories.</p>
                <ul className="mt-3 space-y-2 text-sm text-slate-700">
                  {result.style_allocation.slice(0, 8).map((row) => (
                    <li key={row.style} className="flex justify-between gap-3 border-b border-slate-100 py-1">
                      <span>{row.style.replace(/_/g, " ")}</span>
                      <span className="font-medium">{row.percent ? `${row.percent}%` : "—"}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null}
            {result.sector_allocation && result.sector_allocation.length > 0 ? (
              <Card className="aic-card-glow">
                <h2 className="text-base font-semibold text-slate-900">Sector mix</h2>
                <p className="mt-1 text-xs text-slate-500">Direct equity when classifiable; may use name hints.</p>
                <ul className="mt-3 space-y-2 text-sm text-slate-700">
                  {result.sector_allocation.slice(0, 8).map((row) => (
                    <li key={row.sector} className="flex justify-between gap-3 border-b border-slate-100 py-1">
                      <span>{row.sector}</span>
                      <span className="font-medium">
                        {row.percent ?? row.weight_percent
                          ? `${row.percent ?? row.weight_percent}%`
                          : "—"}
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null}
          </div>
        ) : null}

        {result.selected_strategy && Object.keys(result.selected_strategy.allocation).length > 0 ? (
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">
              Suggested approach: {result.selected_strategy.name}
            </h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {Object.entries(result.selected_strategy.allocation).map(([key, amount]) => (
                <div key={key} className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500">
                    {ALLOCATION_LABELS[key] ?? key}
                  </p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">{formatCurrency(amount)}</p>
                </div>
              ))}
            </div>
            <ul className="mt-4 space-y-2 text-sm text-slate-700">
              {result.selected_strategy.rationale.map((line) => (
                <li key={line} className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-100">{line}</li>
              ))}
            </ul>
          </Card>
        ) : null}

        {result.alternatives.length > 0 ? (
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">Other options to compare</h2>
            <div className="mt-4 space-y-4">
              {result.alternatives.map((strategy) => (
                <div key={strategy.name} className="rounded-lg border border-slate-200 p-4">
                  <p className="font-medium text-slate-900">{strategy.name}</p>
                  <div className="mt-2 flex flex-wrap gap-3 text-sm text-slate-700">
                    {Object.entries(strategy.allocation).map(([key, amount]) => (
                      <span key={key}>
                        {ALLOCATION_LABELS[key] ?? key}: {formatCurrency(amount)}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        ) : null}

        {result.strategy_evaluations.length > 0 ? (
          <Card className="aic-card-glow">
            <h2 className="mb-4 text-base font-semibold text-slate-900">How each option fits you</h2>
            <div className="space-y-4">
              {result.strategy_evaluations.map((evaluation) => (
                <div key={evaluation.strategy.name} className="rounded-lg border border-slate-200 p-4">
                  <p className="font-medium text-slate-900">{evaluation.strategy.name}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {Object.entries(evaluation.suitability_indicators).map(([key, value]) => (
                      <StatusBadge key={key} status={value === "unknown" ? "unknown" : "known"}>
                        {key.replace(/_/g, " ")}: {value}
                      </StatusBadge>
                    ))}
                  </div>
                  {evaluation.conflicts.length > 0 ? (
                    <ul className="mt-3 space-y-1 text-sm text-amber-800">
                      {evaluation.conflicts.map((line) => (
                        <li key={line}>⚠ {line}</li>
                      ))}
                    </ul>
                  ) : null}
                  {evaluation.strengths.length > 0 ? (
                    <p className="mt-2 text-sm text-slate-700">
                      Strengths: {evaluation.strengths.join(" · ")}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          </Card>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2">
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">Observations</h2>
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              {result.rationale.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </Card>
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">Risks & trade-offs</h2>
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              {[...result.risks, ...result.tradeoffs].map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </Card>
        </div>

        {result.evidence.length > 0 ? (
          <Card className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">Knowledge used</h2>
            <div className="mt-3 space-y-3">
              {result.evidence.map((item) => (
                <div key={`${item.reference}-${item.section}`} className="rounded-lg bg-slate-50 p-3 text-sm">
                  <p className="font-medium text-slate-900">{item.section}</p>
                  <p className="text-xs text-slate-500">{item.reference}</p>
                  <p className="mt-2 text-slate-700">{item.content}</p>
                </div>
              ))}
            </div>
          </Card>
        ) : null}

        <div className="flex flex-wrap gap-3">
          <Button onClick={startOver}>Run another decision</Button>
          <Link href="/onboarding/twin">
            <Button variant="secondary">Back to profile</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="aic-card-glow">
        <PageHeader
          kicker="Decision support"
          title="Review your context, then proceed"
          description="We pull together your risk profile, goals, portfolio metrics, and knowledge skills before the equity agent runs."
        />
        <CompletenessRing value={pct} label="Profile completeness" />
      </Card>

      <Card className="aic-card-glow">
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
      </Card>

      <Card className="aic-card-glow">
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
      </Card>

      <Card className="aic-card-glow">
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
      </Card>

      {selectedObjective?.needsCapital ? (
        <Card className="aic-card-glow">
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
        </Card>
      ) : null}

      {runError ? (
        <Card className="border-red-200 bg-red-50">
          <p className="text-sm text-red-800">{runError}</p>
        </Card>
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
