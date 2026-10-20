"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Input, Label, LoadingState } from "@ai-cio/ui";
import type { FirePlan, Goal } from "@ai-cio/contracts";
import { useRequireAuth } from "@/hooks/use-journey";
import { fireApi, goalsApi } from "@/lib/api";
import { EMPTY_FIRE_FORM, fireFormFromInputs, parseFireForm, type FireFormState } from "@/lib/fire-form";
import { GlassPanel, SurfacePanel } from "@/components/design/system";
import { FirePlanView } from "@/components/fire/fire-plan-view";

type FieldKey = Exclude<keyof FireFormState, "pension_inflation_linked">;

export default function FirePage() {
  const user = useRequireAuth();
  const router = useRouter();
  const [form, setForm] = useState<FireFormState>({ ...EMPTY_FIRE_FORM });
  const [savedGoal, setSavedGoal] = useState<Goal | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"preview" | "save" | null>(null);
  const [plan, setPlan] = useState<FirePlan | null>(null);
  const [previewKey, setPreviewKey] = useState("");
  const [savedKey, setSavedKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const formKey = JSON.stringify(form);
  const currentPreview = Boolean(plan && formKey === previewKey);
  const savedCurrent = Boolean(savedGoal && savedKey === formKey);

  useEffect(() => {
    if (!user) return;
    let active = true;
    setLoading(true);
    goalsApi.list(user.id).then((goals) => {
      if (!active) return;
      const requestedId = new URLSearchParams(window.location.search).get("goal_id");
      const fireGoals = goals.filter((goal) => goal.goal_type === "fire" && goal.planning_inputs);
      const existing = fireGoals.find((goal) => String(goal.id) === requestedId) ?? fireGoals[0];
      setSavedGoal(existing ?? null);
      setPlan(null);
      setError(null);
      if (existing?.planning_inputs) {
        const restored = fireFormFromInputs(existing.planning_inputs);
        setForm(restored); setSavedKey(JSON.stringify(restored));
      } else {
        setForm({ ...EMPTY_FIRE_FORM }); setSavedKey("");
      }
    }).catch((err) => active && setError(err instanceof Error ? err.message : "Saved goals could not be loaded."))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [user]);

  function change(key: FieldKey, value: string) {
    setForm((previous) => ({ ...previous, [key]: value }));
    setNotice(null);
  }
  async function preview(event: React.FormEvent) {
    event.preventDefault();
    if (!user) return;
    setError(null); setNotice(null);
    try {
      const inputs = parseFireForm(form);
      setBusy("preview");
      const response = await fireApi.preview(user.id, inputs);
      setPlan(response); setPreviewKey(formKey);
    } catch (err) { setError(err instanceof Error ? err.message : "Your plan could not be calculated."); }
    finally { setBusy(null); }
  }
  async function save() {
    if (!user || !currentPreview) return;
    setError(null); setNotice(null); setBusy("save");
    try {
      const inputs = parseFireForm(form);
      const payload = {
        name: `Financial independence by ${inputs.retirement_age}`,
        goal_type: "fire", planning_inputs: inputs,
        current_funding: inputs.earmarked_assets,
        horizon_years: inputs.retirement_age - inputs.current_age,
        priority: "high", flexibility: "somewhat",
      };
      const saved = savedGoal ? await goalsApi.update(user.id, savedGoal.id, payload) : await goalsApi.create(user.id, payload);
      setSavedGoal(saved); setSavedKey(formKey);
      setNotice("FIRE goal saved. Run the decision to review this plan with your recorded profile.");
    } catch (err) { setError(err instanceof Error ? err.message : "Your goal could not be saved."); }
    finally { setBusy(null); }
  }
  function input(key: FieldKey, label: string, hint: string, placeholder = "", required = false) {
    return <div key={key} className="min-w-0"><Label htmlFor={`fire-${key}`}>{label}</Label><Input id={`fire-${key}`} inputMode={key.includes("age") ? "numeric" : "decimal"} value={form[key]} onChange={(event) => change(key, event.target.value)} placeholder={placeholder} required={required} aria-describedby={`hint-${key}`} disabled={Boolean(busy)} /><p id={`hint-${key}`} className="mt-1.5 text-xs leading-5 text-slate-500">{hint}</p></div>;
  }
  if (!user || loading) return <LoadingState message="Loading your financial independence goal…" />;

  return <div className="space-y-6">
    <GlassPanel strong>
      <p className="text-[11px] font-semibold uppercase tracking-[.18em] text-teal-700">FIRE / Your chosen finish line</p>
      <h1 className="aic-title mt-3">Make work a choice.</h1>
      <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">Start with the life you want to fund. We work backwards from spending and time, then use your psychometric profile to compare investment mixes you can sustain.</p>
      <p className="mt-3 text-xs leading-6 text-slate-500">FIRE means Financial Independence, Retire Early. Your target can be 65 or another age; financial independence does not require leaving work early.</p>
      <ol aria-label="Financial independence planning flow" className="mt-5 grid gap-2 text-xs font-medium text-teal-900 sm:grid-cols-4">{["1 · Confirm your inputs", "2 · Inspect the funding gap", "3 · Compare a suitable mix", "4 · Save and review decisions"].map((step) => <li key={step} className="rounded-xl border border-teal-100 bg-white/70 p-3">{step}</li>)}</ol>
    </GlassPanel>

    <SurfacePanel>
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold tracking-tight text-slate-900">Your life, your numbers</h2><p className="mt-2 text-sm leading-6 text-slate-600">Use today&apos;s rupees. Keep emergency money and assets promised to other goals outside the FIRE pot.</p></div>{savedGoal ? <span className="rounded-full bg-teal-50 px-3 py-1 text-xs text-teal-900">Editing saved FIRE goal</span> : null}</div>
      <form onSubmit={preview} className="mt-6 space-y-6">
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {input("current_age", "Your age now", "Enter your age; it is never inferred from a persona.", "e.g. 35", true)}
          {input("retirement_age", "Financial independence at age", "65 is an editable starting point.", "65", true)}
          {input("monthly_spending_today", "Retirement spending / month (₹ today)", "Include housing, health costs, tax and the lifestyle you want.", "e.g. 60000", true)}
          {input("monthly_investment_budget", "Willing to invest / month (₹)", "Your total chosen investment budget before the commitments below. Blank means unconfirmed, never your entire surplus.", "Confirm an amount, including 0")}
          {input("earmarked_assets", "Already reserved for FIRE (₹)", "Enter 0 if you are starting fresh. Exclude your home unless you plan to release its value.", "e.g. 500000", true)}
          {input("annual_pension_today", "Expected pension / year (₹ today)", "Enter 0 if none is expected. Blank is unknown and blocks a complete funding calculation.", "Confirm an amount, including 0")}
          {input("other_goal_monthly_commitments", "Other goals / month (₹)", "Additional commitments from this same budget, not already included in recorded expenses.", "0", true)}
          {input("reserve_monthly_commitment", "Emergency reserve saving / month (₹)", "Additional reserve saving from this same budget, not already included in recorded expenses.", "0", true)}
        </div>
        <details className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4"><summary className="cursor-pointer text-sm font-semibold text-slate-800">Scenario assumptions · review before relying on the result</summary><p className="mt-3 text-xs leading-6 text-slate-600">These are editable planning assumptions. The 8% return and 3.5% withdrawal starting values are illustrations, not forecasts or an India-specific safe rate. Taxes and costs reduce actual returns.</p><div className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {input("inflation_percent", "Inflation / year (%)", "Spending rises with this assumed rate.", "6", true)}
          {input("accumulation_return_percent", "Nominal return / year (%)", "Same assumed return across allocation comparisons; no return is promised.", "8", true)}
          {input("withdrawal_rate_percent", "First-year withdrawal (%)", "Annual spending gap divided by this rate gives the target corpus.", "3.5", true)}
          {input("longevity_age", "Plan spending through age", "Used for a finite-horizon comparison and longevity review.", "95", true)}
        </div><label className="mt-5 flex items-start gap-3 text-sm text-slate-700"><input type="checkbox" className="mt-1" checked={form.pension_inflation_linked} disabled={Boolean(busy)} onChange={(event) => { setForm((previous) => ({ ...previous, pension_inflation_linked: event.target.checked })); setNotice(null); }} /><span>Pension keeps pace with inflation after retirement.<span className="mt-1 block text-xs leading-5 text-slate-500">Today’s annual pension is inflated to your target age first. Leave unchecked if payments stay fixed after retirement; confirm the scheme terms.</span></span></label></details>
        <div className="flex flex-wrap items-center justify-between gap-4"><p className="max-w-xl text-xs leading-6 text-slate-500">Recorded income and expenses limit capacity; expenses must already include EMI. Only additional commitments outside those expenses belong in the goal and reserve fields. Your chosen budget limits willingness. Your questionnaire affects allocation preference; it cannot remove a funding gap.</p><Button type="submit" disabled={Boolean(busy)}>{busy === "preview" ? "Calculating your plan…" : "Calculate my FIRE path ↗"}</Button></div>
      </form>
    </SurfacePanel>
    {error ? <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p> : null}
    {plan ? <div className="space-y-5">{!currentPreview ? <p role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Inputs changed. Calculate again to update the plan before saving.</p> : null}<div className={!currentPreview ? "opacity-60" : ""}><FirePlanView plan={plan} /></div><SurfacePanel><div className="flex flex-wrap items-center justify-between gap-4"><div><h2 className="text-lg font-semibold text-slate-900">Turn the calculation into a goal</h2><p className="mt-2 text-sm text-slate-600">Saving keeps the assumptions with this goal. The decision uses that saved version.</p></div><div className="flex flex-wrap gap-3"><Button variant="secondary" onClick={() => void save()} disabled={Boolean(busy) || !currentPreview || savedCurrent}>{busy === "save" ? "Saving…" : savedCurrent ? "Goal saved ✓" : "Save FIRE goal"}</Button><Button disabled={!savedCurrent || !currentPreview || Boolean(busy)} onClick={() => savedGoal && router.push(`/decisions?objective=plan_fire&goal_id=${savedGoal.id}`)}>Review my FIRE decision ↗</Button></div></div>{notice ? <p role="status" className="mt-4 text-sm text-teal-900">{notice}</p> : null}</SurfacePanel></div> : null}
    <div className="flex flex-wrap gap-5 text-xs font-medium text-teal-800"><Link href="/onboarding/understand-me" className="underline underline-offset-4">Review my psychometric profile ↗</Link><Link href="/onboarding/finances" className="underline underline-offset-4">Update recorded income and expenses ↗</Link><Link href="/onboarding/goals?return=/fire" className="underline underline-offset-4">See all my goals ↗</Link></div>
  </div>;
}
