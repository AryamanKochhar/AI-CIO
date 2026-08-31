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
  RevealToggle,
  SensitiveRevealProvider,
  StatusBadge,
  TransactionTable,
} from "@ai-cio/ui";
import type { DigitalTwin, FinancialMap, MarketContext, Transaction } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { documentsApi, twinApi } from "@/lib/api";
import { COMPLETENESS_LABELS, completenessPercent } from "@/lib/constants";
import { useRequireAuth, useJourney } from "@/hooks/use-journey";
import { FinancialMapView } from "@/components/financial-map/FinancialMapView";
import { MarketContextPanel } from "@/components/financial-map/MarketContextPanel";

export default function TwinPage() {
  const user = useRequireAuth();
  const { setStep } = useJourney();
  const [twin, setTwin] = useState<DigitalTwin | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    Promise.all([twinApi.get(user.id), documentsApi.getTransactions(user.id)])
      .then(([data, txns]) => {
        setTwin(data);
        setTransactions(txns);
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
  const financialMap = twin.financial_map as FinancialMap | undefined;
  const marketContext = twin.market_context as MarketContext | undefined;

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

      {financialMap ? (
        <Card className="aic-card-glow overflow-hidden">
          <FinancialMapView map={financialMap} />
        </Card>
      ) : (
        <Card className="aic-card-glow">
          <PageHeader
            title="Your financial map is just getting started"
            description="As you add finances, goals and statements, an interactive map of your financial life will appear here."
          />
        </Card>
      )}

      {marketContext ? (
        <Card className="aic-card-glow">
          <MarketContextPanel context={marketContext} />
        </Card>
      ) : null}

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
          {(() => {
            const provenance = twin.portfolio.provenance as
              | {
                  source?: string;
                  period_start?: string | null;
                  period_end?: string | null;
                  last_processed?: string | null;
                }
              | null
              | undefined;
            if (!provenance?.source) return null;
            return (
              <p className="mt-2 text-sm text-slate-600">
                Based on a {provenance.source}
                {provenance.period_start && provenance.period_end
                  ? ` covering ${provenance.period_start} – ${provenance.period_end}`
                  : ""}
                {provenance.last_processed ? `. Last processed ${new Date(provenance.last_processed).toLocaleDateString()}` : "."}
              </p>
            );
          })()}
        </ProfileSection>
      </div>

      {holdings.length > 0 || transactions.length > 0 ? (
        <Card className="aic-card-glow">
          <SensitiveRevealProvider>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-slate-900">Holdings list</h2>
              <RevealToggle label="financial details" />
            </div>
            <p className="mb-4 text-sm text-slate-600">
              Accessible list view of the same investments shown on your map.
            </p>
            {holdings.length > 0 ? (
              <PortfolioTable
                rows={holdings.map((row) => ({
                  scheme_name: row.scheme_name,
                  isin: row.isin,
                  closing_units: row.closing_units,
                  valuation: row.valuation,
                  source: row.source ?? "CAS",
                }))}
              />
            ) : null}
            {transactions.length > 0 ? (
              <div className={holdings.length > 0 ? "mt-6" : undefined}>
                <TransactionTable rows={transactions} showToggle={false} />
              </div>
            ) : null}
          </SensitiveRevealProvider>
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
