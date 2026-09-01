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
  const [objective, setObjective] = useState<DecisionObjective>("allocate_capital");
  const [availableCapital, setAvailableCapital] = useState("");
  const [minLiquidReserve, setMinLiquidReserve] = useState("");
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
        if (!cancelled) setTwin(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setLoadError(err.message || "Could not load your profile.");
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  async function handleProceed() {
    if (!user || !selectedObjective) return;
    if (selectedObjective.needsCapital && !availableCapital.trim()) {
      setRunError("Enter the amount you want to allocate.");
      return;
    }

    setRunError(null);
    setPhase("running");
    setResult(null);

    const constraints: Record<string, string> = {};
    if (minLiquidReserve.trim()) {
      constraints.min_liquid_reserve = minLiquidReserve.trim();
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
          </div>
        </Card>

        {result.selected_strategy ? (
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
          description="We pull together your profile, goals, portfolio, behaviour, and market context before any analysis runs."
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
          </ProfileSection>
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
