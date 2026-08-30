"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Button,
  Card,
  CompletenessRing,
  ErrorState,
  LoadingState,
  PageHeader,
  PortfolioTable,
  ProfileSection,
  StatusBadge,
} from "@ai-cio/ui";
import type { DigitalTwin } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { twinApi } from "@/lib/api";
import { COMPLETENESS_LABELS, completenessPercent } from "@/lib/constants";
import { useRequireAuth, useJourney } from "@/hooks/use-journey";

export default function TwinPage() {
  const user = useRequireAuth();
  const { setStep } = useJourney();
  const [twin, setTwin] = useState<DigitalTwin | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    twinApi
      .get(user.id)
      .then((data) => {
        setTwin(data);
        setStep("analysis");
      })
      .catch(() => setError("We couldn't assemble your financial profile."));
  }, [user, setStep]);

  if (!user) return null;
  if (error) return <ErrorState title="Profile unavailable" message={error} />;
  if (!twin) return <LoadingState message="Assembling your financial profile…" />;

  const income = twin.financial_position.income as { value?: string | null; known?: boolean; source?: string };
  const expenses = twin.financial_position.expenses as { value?: string | null; known?: boolean; source?: string };
  const liquid = twin.financial_position.liquid as { value?: string | null; known?: boolean; source?: string };
  const portfolio = twin.portfolio.total_value as { value?: string | null; known?: boolean; source?: string };
  const pct = completenessPercent(twin.completeness as unknown as Record<string, boolean>);
  const holdings = (twin.portfolio.holdings as Array<Record<string, string>>) ?? [];

  return (
    <div className="space-y-6">
      <Card className="aic-card-glow">
        <PageHeader
          kicker="Your AI-CIO"
          title="Your Financial Profile"
          description="Everything we know about your financial life — with clear sources and honest gaps."
        />
        <CompletenessRing value={pct} label="Your profile" />
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <ProfileSection title="How you make decisions" source="Based on your assessment">
          {twin.behaviour.status === "known" ? (
            <ul className="space-y-2 text-sm text-slate-700">
              {(twin.behaviour.observations ?? []).map((line) => (
                <li key={line} className="rounded-lg bg-slate-50 px-3 py-2">{line}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-600">Not provided</p>
          )}
        </ProfileSection>

        <ProfileSection title="Financial position" source="You provided">
          <ul className="space-y-2 text-sm text-slate-700">
            <li>Income: {income.known ? formatCurrency(income.value) : "Not provided"}</li>
            <li>Expenses: {expenses.known ? formatCurrency(expenses.value) : "Not provided"}</li>
            <li>Liquid savings: {liquid.known ? formatCurrency(liquid.value) : "Not provided"}</li>
          </ul>
        </ProfileSection>

        <ProfileSection title="Your goals" source="You provided">
          {twin.goals.items.length ? (
            <ul className="space-y-2 text-sm text-slate-700">
              {twin.goals.items.map((goal) => (
                <li key={goal.id}>{goal.name} · target {formatCurrency(goal.target_amount)}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-600">Not provided</p>
          )}
        </ProfileSection>

        <ProfileSection title="Your portfolio" source={portfolio.source ?? "Documents"}>
          <p className="text-lg font-semibold text-slate-900">
            {portfolio.known ? formatCurrency(portfolio.value) : "Not provided"}
          </p>
        </ProfileSection>
      </div>

      {holdings.length > 0 ? (
        <Card className="aic-card-glow">
          <h2 className="mb-4 text-base font-semibold text-slate-900">Holdings</h2>
          <PortfolioTable
            rows={holdings.map((row) => ({
              scheme_name: row.scheme_name,
              isin: row.isin,
              closing_units: row.closing_units,
              valuation: row.valuation,
              source: row.source ?? "CAS",
            }))}
          />
        </Card>
      ) : null}

      <Card className="aic-card-glow">
        <h2 className="mb-3 text-base font-semibold text-slate-900">What we know · What is missing</h2>
        <div className="grid gap-2 sm:grid-cols-2">
          {Object.entries(twin.completeness).map(([key, known]) => (
            <div key={key} className="flex items-center gap-2 text-sm">
              <span>{known ? "✓" : "○"}</span>
              <span className={known ? "text-slate-900" : "text-slate-500"}>
                {COMPLETENESS_LABELS[key] ?? key}
              </span>
              {!known ? <StatusBadge status="unknown">Not provided</StatusBadge> : null}
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm text-slate-600">
          {twin.ready_for_analysis
            ? "Your core profile sections are complete. Future AI-CIO analysis will build on this foundation."
            : "Some sections are still unknown. You can return anytime to add more."}
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/onboarding/review"><Button variant="secondary">Back to review</Button></Link>
          <Link href="/onboarding/welcome"><Button variant="ghost">Back to onboarding</Button></Link>
        </div>
      </Card>
    </div>
  );
}
