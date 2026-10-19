"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Button,
  Card,
  CompletenessRing,
  ErrorState,
  Input,
  Label,
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
import { documentsApi, financesApi, twinApi } from "@/lib/api";
import { COMPLETENESS_LABELS, completenessPercent } from "@/lib/constants";
import { useRequireAuth, useJourney } from "@/hooks/use-journey";
import { FinancialMapView } from "@/components/financial-map/FinancialMapView";
import { MarketContextPanel } from "@/components/financial-map/MarketContextPanel";
import { TwinMascot } from "@/components/twin-mascot";
import { DecisionNextSteps } from "@/components/decision-next-steps";

export default function TwinPage() {
  const user = useRequireAuth();
  const { setStep } = useJourney();
  const [twin, setTwin] = useState<DigitalTwin | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editingFinances, setEditingFinances] = useState(false);
  const [incomeEdit, setIncomeEdit] = useState("");
  const [expensesEdit, setExpensesEdit] = useState("");
  const [liquidEdit, setLiquidEdit] = useState("");
  const [financeError, setFinanceError] = useState<string | null>(null);
  const [savingFinances, setSavingFinances] = useState(false);

  async function reloadTwin() {
    if (!user) return;
    const data = await twinApi.get(user.id);
    setTwin(data);
  }

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    setError(null);
    twinApi
      .get(user.id)
      .then((data) => {
        if (cancelled) return;
        setTwin(data);
        setError(null);
        setStep("analysis").catch(() => undefined);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message || "We couldn't assemble your financial profile.");
      });

    documentsApi
      .getTransactions(user.id)
      .then((txns) => {
        if (!cancelled) setTransactions(txns);
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [user, setStep]);

  function startFinanceEdit() {
    if (!twin) return;
    const income = twin.financial_position.income as { value?: string | null };
    const expenses = twin.financial_position.expenses as { value?: string | null };
    const liquid = twin.financial_position.liquid as { value?: string | null };
    setIncomeEdit(income.value ?? "");
    setExpensesEdit(expenses.value ?? "");
    setLiquidEdit(liquid.value ?? "");
    setFinanceError(null);
    setEditingFinances(true);
  }

  async function saveFinances() {
    if (!user) return;
    setSavingFinances(true);
    setFinanceError(null);
    try {
      const existing = await financesApi.get(user.id);
      await financesApi.update(user.id, {
        income: incomeEdit.trim() || null,
        expenses: expensesEdit.trim() || null,
        liquid: liquidEdit.trim() || null,
        cadence: (existing.cadence as string) || "monthly",
        liabilities: (existing.liabilities as Array<Record<string, unknown>>) ?? [],
      });
      await reloadTwin();
      setEditingFinances(false);
    } catch (err) {
      setFinanceError(err instanceof Error ? err.message : "Could not save finances.");
    } finally {
      setSavingFinances(false);
    }
  }

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
      {twin.demo?.synthetic ? <p className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-6 text-amber-900">{twin.demo.note}</p> : null}
      <TwinMascot completeness={twin.completeness as unknown as Record<string, boolean>} />
      <DecisionNextSteps />
      <Card className="aic-card-glow">
        <PageHeader
          kicker="Your AI-cio"
          title="Your Financial Profile"
          description="Everything we know about your financial life — with clear sources and honest gaps."
        />
        <CompletenessRing value={pct} label="Your profile" />
        <Link href="/onboarding/review" className="mt-4 inline-flex text-sm font-medium text-teal-800 underline underline-offset-4">Check or update my information ↗</Link>
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
          {editingFinances ? (
            <div className="space-y-3">
              <div>
                <Label htmlFor="twin-income">Monthly income (₹)</Label>
                <Input
                  id="twin-income"
                  inputMode="decimal"
                  value={incomeEdit}
                  onChange={(e) => setIncomeEdit(e.target.value)}
                  placeholder="e.g. 150000"
                />
              </div>
              <div>
                <Label htmlFor="twin-expenses">Monthly expenses (₹)</Label>
                <Input
                  id="twin-expenses"
                  inputMode="decimal"
                  value={expensesEdit}
                  onChange={(e) => setExpensesEdit(e.target.value)}
                  placeholder="e.g. 80000"
                />
              </div>
              <div>
                <Label htmlFor="twin-liquid">Liquid savings (₹)</Label>
                <Input
                  id="twin-liquid"
                  inputMode="decimal"
                  value={liquidEdit}
                  onChange={(e) => setLiquidEdit(e.target.value)}
                  placeholder="e.g. 200000"
                />
              </div>
              {financeError ? <p className="text-sm text-red-600">{financeError}</p> : null}
              <div className="flex flex-wrap gap-2">
                <Button onClick={saveFinances} disabled={savingFinances}>
                  {savingFinances ? "Saving…" : "Save"}
                </Button>
                <Button variant="ghost" onClick={() => setEditingFinances(false)} disabled={savingFinances}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <>
              <ul className="space-y-2 text-sm text-slate-700">
                <li>Income: {income.known ? formatCurrency(income.value) : "Not provided"}</li>
                <li>Expenses: {expenses.known ? formatCurrency(expenses.value) : "Not provided"}</li>
                <li>Liquid savings: {liquid.known ? formatCurrency(liquid.value) : "Not provided"}</li>
              </ul>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="secondary" onClick={startFinanceEdit}>
                  {income.known || expenses.known || liquid.known ? "Update finances" : "Add income & expenses"}
                </Button>
                <Link href="/onboarding/finances?return=/onboarding/twin">
                  <Button variant="ghost">Full finances form</Button>
                </Link>
              </div>
            </>
          )}
        </ProfileSection>

        <ProfileSection title="Your goals" source="You provided">
          {twin.goals.items.length ? (
            <ul className="space-y-2 text-sm text-slate-700">
              {twin.goals.items.map((goal) => (
                <li key={goal.id}>
                  {goal.name} · target {formatCurrency(goal.target_amount)}
                  {goal.target_date ? ` · by ${goal.target_date}` : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-600">Not provided — add goals so Decisions can estimate likelihood.</p>
          )}
          <div className="mt-3">
            <Link href="/onboarding/goals?return=/onboarding/twin">
              <Button variant="secondary">{twin.goals.items.length ? "Add or edit goals" : "Add goals"}</Button>
            </Link>
          </div>
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
            ? "Your core profile sections are complete. Future AI-cio analysis will build on this foundation."
            : "Some sections are still unknown. You can return anytime to add more."}
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/onboarding/review"><Button variant="secondary">Back to review</Button></Link>
          <Link href="/decisions"><Button>Explore decisions</Button></Link>
          <Link href="/tax"><Button variant="secondary">Tax intelligence</Button></Link>
          <Link href="/fd"><Button variant="secondary">Fixed deposits</Button></Link>
          <Link href="/onboarding/welcome"><Button variant="ghost">Back to onboarding</Button></Link>
        </div>
      </Card>
    </div>
  );
}
