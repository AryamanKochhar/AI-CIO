"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Card, Input, Label, PageHeader, ProgressBar } from "@ai-cio/ui";
import { ApiError } from "@/lib/api-client";
import { financesApi } from "@/lib/api";
import { useRequireAuth, useJourney } from "@/hooks/use-journey";

const STEPS = ["income", "expenses", "savings", "liabilities"] as const;

export default function FinancesPage() {
  const user = useRequireAuth();
  const router = useRouter();
  const { setStep } = useJourney();
  const [step, setLocalStep] = useState(0);
  const [income, setIncome] = useState("");
  const [additionalIncome, setAdditionalIncome] = useState("");
  const [essential, setEssential] = useState("");
  const [discretionary, setDiscretionary] = useState("");
  const [liquid, setLiquid] = useState("");
  const [hasLoan, setHasLoan] = useState(false);
  const [liabilityName, setLiabilityName] = useState("");
  const [liabilityBalance, setLiabilityBalance] = useState("");
  const [liabilityPayment, setLiabilityPayment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!user) return;
    financesApi.get(user.id).then((data) => {
      setIncome(String(data.income ?? ""));
      setLiquid(String(data.liquid ?? ""));
      setEssential(String(data.expenses ?? ""));
      const liabilities = (data.liabilities as Array<Record<string, string>>) ?? [];
      if (liabilities.length) {
        setHasLoan(true);
        setLiabilityName(liabilities[0].name ?? "");
        setLiabilityBalance(String(liabilities[0].balance ?? ""));
        setLiabilityPayment(String(liabilities[0].monthly_payment ?? ""));
      }
    }).catch(() => undefined);
  }, [user]);

  const totalExpenses = [essential, discretionary].filter(Boolean).map(Number).reduce((a, b) => a + (Number.isNaN(b) ? 0 : b), 0);

  async function finish(skip = false) {
    if (!user) return;
    setSaving(true);
    setError(null);
    try {
      if (skip) {
        await financesApi.skip(user.id);
      } else {
        const combinedIncome = [income, additionalIncome].filter(Boolean).map(Number).reduce((a, b) => a + b, 0) || income || null;
        const combinedExpenses = totalExpenses > 0 ? String(totalExpenses) : essential || discretionary || null;
        const liabilities =
          hasLoan && liabilityName && liabilityBalance
            ? [{ name: liabilityName, balance: liabilityBalance, monthly_payment: liabilityPayment || null }]
            : [];
        await financesApi.update(user.id, {
          income: combinedIncome ? String(combinedIncome) : income || null,
          expenses: combinedExpenses,
          liquid: liquid || null,
          cadence: "monthly",
          liabilities,
        });
      }
      await setStep("goals");
      router.push("/onboarding/goals");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "We couldn't save your information.");
    } finally {
      setSaving(false);
    }
  }

  if (!user) return null;

  const current = STEPS[step];

  return (
    <Card className="aic-card-glow">
      <PageHeader
        title="My finances"
        description="Share what you know. Leave anything blank and we'll mark it as unknown — never as zero."
      />
      <ProgressBar value={((step + 1) / STEPS.length) * 100} label={`Section ${step + 1} of ${STEPS.length}`} />

      {current === "income" ? (
        <div className="mt-6 space-y-4">
          <div>
            <Label htmlFor="income">How much do you typically earn each month? (₹)</Label>
            <Input id="income" value={income} onChange={(e) => setIncome(e.target.value)} placeholder="Optional" />
          </div>
          <div>
            <Label htmlFor="additional">Any additional income? (₹)</Label>
            <Input id="additional" value={additionalIncome} onChange={(e) => setAdditionalIncome(e.target.value)} placeholder="Optional" />
          </div>
        </div>
      ) : null}

      {current === "expenses" ? (
        <div className="mt-6 space-y-4">
          <div>
            <Label htmlFor="essential">Essential expenses — rent, utilities, groceries (₹)</Label>
            <Input id="essential" value={essential} onChange={(e) => setEssential(e.target.value)} placeholder="Optional" />
          </div>
          <div>
            <Label htmlFor="discretionary">Discretionary spending — dining, travel, hobbies (₹)</Label>
            <Input id="discretionary" value={discretionary} onChange={(e) => setDiscretionary(e.target.value)} placeholder="Optional" />
          </div>
        </div>
      ) : null}

      {current === "savings" ? (
        <div className="mt-6">
          <Label htmlFor="liquid">How much do you keep readily available? (₹)</Label>
          <Input id="liquid" value={liquid} onChange={(e) => setLiquid(e.target.value)} placeholder="Cash and liquid savings" />
        </div>
      ) : null}

      {current === "liabilities" ? (
        <div className="mt-6 space-y-4">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={hasLoan} onChange={(e) => setHasLoan(e.target.checked)} />
            I have a loan or other liability
          </label>
          {hasLoan ? (
            <div className="grid gap-4 md:grid-cols-2">
              <Input value={liabilityName} onChange={(e) => setLiabilityName(e.target.value)} placeholder="Loan name" />
              <Input value={liabilityBalance} onChange={(e) => setLiabilityBalance(e.target.value)} placeholder="Outstanding balance (₹)" />
              <Input value={liabilityPayment} onChange={(e) => setLiabilityPayment(e.target.value)} placeholder="Monthly EMI (optional)" />
            </div>
          ) : null}
        </div>
      ) : null}

      {error ? <p className="mt-4 text-sm text-red-600" role="alert">{error}</p> : null}

      <div className="mt-8 flex flex-wrap justify-between gap-3">
        <Button variant="secondary" disabled={step === 0} onClick={() => setLocalStep(step - 1)}>
          Back
        </Button>
        <div className="flex flex-wrap gap-3">
          <Button variant="ghost" onClick={() => finish(true)} disabled={saving}>
            Skip section
          </Button>
          {step < STEPS.length - 1 ? (
            <Button onClick={() => setLocalStep(step + 1)}>Continue</Button>
          ) : (
            <Button onClick={() => finish(false)} disabled={saving}>
              {saving ? "Saving…" : "Save and continue"}
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
