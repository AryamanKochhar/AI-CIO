"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button, Card, PageHeader, StatusBadge } from "@ai-cio/ui";
import type { DigitalTwin } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { twinApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

export default function TwinPage() {
  const { user } = useAuth();
  const [twin, setTwin] = useState<DigitalTwin | null>(null);

  useEffect(() => {
    if (!user) return;
    twinApi.get(user.id).then(setTwin).catch(() => setTwin(null));
  }, [user]);

  if (!user) {
    return (
      <Card>
        <PageHeader title="Your Financial Profile" description="Please sign in first." />
        <Link href="/login"><Button>Sign in</Button></Link>
      </Card>
    );
  }

  if (!twin) {
    return <Card><p className="text-sm text-slate-600">Assembling your digital financial twin…</p></Card>;
  }

  const income = twin.financial_position.income as { value?: string | null; known?: boolean; source?: string };
  const expenses = twin.financial_position.expenses as { value?: string | null; known?: boolean; source?: string };
  const liquid = twin.financial_position.liquid as { value?: string | null; known?: boolean; source?: string };
  const portfolio = twin.portfolio.total_value as { value?: string | null; known?: boolean; source?: string };

  return (
    <div className="space-y-6">
      <Card>
        <PageHeader
          kicker="Step 4"
          title="Your Financial Profile"
          description="An assembled view of what we know about you — with provenance and completeness, never fabricated gaps."
        />
        <div className="mb-6 flex flex-wrap gap-2">
          {Object.entries(twin.completeness).map(([key, value]) => (
            <StatusBadge key={key} status={value ? "known" : "unknown"}>
              {key}
            </StatusBadge>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="text-base font-semibold text-slate-900">Behaviour</h2>
          <p className="mt-2 text-sm text-slate-600">
            {twin.behaviour.status === "known" ? "Based on your assessment" : "Not provided"}
          </p>
        </Card>
        <Card>
          <h2 className="text-base font-semibold text-slate-900">Financial position</h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            <li>Income: {income.known ? formatCurrency(income.value) : "Not provided"} · Source: {income.source ?? "—"}</li>
            <li>Expenses: {expenses.known ? formatCurrency(expenses.value) : "Not provided"}</li>
            <li>Liquid savings: {liquid.known ? formatCurrency(liquid.value) : "Not provided"}</li>
          </ul>
        </Card>
        <Card>
          <h2 className="text-base font-semibold text-slate-900">Portfolio</h2>
          <p className="mt-2 text-sm text-slate-700">
            {portfolio.known ? formatCurrency(portfolio.value) : "Not provided"}
            {portfolio.source ? ` · Source: ${portfolio.source}` : ""}
          </p>
        </Card>
        <Card>
          <h2 className="text-base font-semibold text-slate-900">Goals</h2>
          {twin.goals.items.length ? (
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              {twin.goals.items.map((goal) => (
                <li key={goal.id}>{goal.name} · target {formatCurrency(goal.target_amount)}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-slate-600">Not provided</p>
          )}
        </Card>
      </div>

      <Card>
        <p className="text-sm text-slate-600">
          Ready for future analysis: {twin.ready_for_analysis ? "Yes — core profile sections are complete." : "Not yet — some sections are still unknown."}
        </p>
        <div className="mt-4">
          <Link href="/onboarding/review"><Button variant="secondary">Back to review</Button></Link>
        </div>
      </Card>
    </div>
  );
}
