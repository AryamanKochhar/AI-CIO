"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button, Card, Input, Label, PageHeader } from "@ai-cio/ui";
import { ApiError } from "@/lib/api-client";
import { financesApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

export default function FinancesPage() {
  const { user } = useAuth();
  const [income, setIncome] = useState("");
  const [expenses, setExpenses] = useState("");
  const [liquid, setLiquid] = useState("");
  const [hasLoan, setHasLoan] = useState(false);
  const [liabilityName, setLiabilityName] = useState("");
  const [liabilityBalance, setLiabilityBalance] = useState("");
  const [liabilityPayment, setLiabilityPayment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!user) return;
    financesApi.get(user.id).then((data) => {
      setIncome(String(data.income ?? ""));
      setExpenses(String(data.expenses ?? ""));
      setLiquid(String(data.liquid ?? ""));
      const liabilities = (data.liabilities as Array<Record<string, string>>) ?? [];
      if (liabilities.length) {
        setHasLoan(true);
        setLiabilityName(liabilities[0].name ?? "");
        setLiabilityBalance(String(liabilities[0].balance ?? ""));
        setLiabilityPayment(String(liabilities[0].monthly_payment ?? ""));
      }
    }).catch(() => undefined);
  }, [user]);

  async function save(skip = false) {
    if (!user) return;
    setError(null);
    try {
      if (skip) {
        await financesApi.skip(user.id);
      } else {
        const liabilities =
          hasLoan && liabilityName && liabilityBalance
            ? [{ name: liabilityName, balance: liabilityBalance, monthly_payment: liabilityPayment || null }]
            : [];
        await financesApi.update(user.id, {
          income: income || null,
          expenses: expenses || null,
          liquid: liquid || null,
          cadence: "monthly",
          liabilities,
        });
      }
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "We couldn't save your information.");
    }
  }

  if (!user) {
    return (
      <Card>
        <PageHeader title="My finances" description="Please sign in or start the questionnaire first." />
        <Link href="/login"><Button>Sign in</Button></Link>
      </Card>
    );
  }

  return (
    <Card>
      <PageHeader
        title="Your cash situation"
        description="Enter monthly figures if you know them. Leave a field blank to keep it unknown — we will not guess."
      />
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <Label htmlFor="income">Typical monthly take-home income (₹)</Label>
          <Input id="income" value={income} onChange={(e) => setIncome(e.target.value)} placeholder="Optional" />
        </div>
        <div>
          <Label htmlFor="expenses">Typical monthly expenses (₹)</Label>
          <Input id="expenses" value={expenses} onChange={(e) => setExpenses(e.target.value)} placeholder="Optional" />
        </div>
        <div>
          <Label htmlFor="liquid">Cash or liquid savings (₹)</Label>
          <Input id="liquid" value={liquid} onChange={(e) => setLiquid(e.target.value)} placeholder="Optional" />
        </div>
      </div>
      <label className="mt-4 flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={hasLoan} onChange={(e) => setHasLoan(e.target.checked)} />
        I have a loan or other liability
      </label>
      {hasLoan ? (
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <Input value={liabilityName} onChange={(e) => setLiabilityName(e.target.value)} placeholder="Liability name" />
          <Input value={liabilityBalance} onChange={(e) => setLiabilityBalance(e.target.value)} placeholder="Outstanding balance" />
          <Input value={liabilityPayment} onChange={(e) => setLiabilityPayment(e.target.value)} placeholder="Monthly payment (optional)" />
        </div>
      ) : null}
      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
      <div className="mt-6 flex flex-wrap gap-3">
        <Button variant="secondary" onClick={() => save(true)}>I don't know — skip</Button>
        <Button onClick={() => save(false)}>Save and continue</Button>
        {saved ? (
          <Link href="/onboarding/goals"><Button variant="ghost">Next: My goals →</Button></Link>
        ) : null}
      </div>
    </Card>
  );
}
