import type { FireAllocationPlan, FirePlanningInputs } from "@ai-cio/contracts";

export type FireFormState = Record<Exclude<keyof FirePlanningInputs, "pension_inflation_linked">, string> & { pension_inflation_linked: boolean };

export const EMPTY_FIRE_FORM: FireFormState = {
  current_age: "", retirement_age: "65", monthly_spending_today: "",
  monthly_investment_budget: "", annual_pension_today: "", earmarked_assets: "",
  inflation_percent: "6", accumulation_return_percent: "8", withdrawal_rate_percent: "3.5",
  longevity_age: "95", other_goal_monthly_commitments: "0", reserve_monthly_commitment: "0",
  pension_inflation_linked: false,
};

export function fireFormFromInputs(inputs: FirePlanningInputs): FireFormState {
  return Object.fromEntries(Object.entries({ ...EMPTY_FIRE_FORM, ...inputs }).map(([key, value]) => [key, key === "pension_inflation_linked" ? Boolean(value) : value == null ? "" : String(value)])) as FireFormState;
}

export function parseFireForm(form: FireFormState): FirePlanningInputs {
  const amount = (key: keyof FireFormState, label: string, optional = false): string | null => {
    const value = String(form[key]).trim();
    if (!value && optional) return null;
    if (!/^\d+(?:\.\d{1,2})?$/.test(value) || !Number.isFinite(Number(value))) throw new Error(`Enter ${label} as a non-negative amount with up to two decimal places.`);
    return value;
  };
  const age = (key: keyof FireFormState, label: string): number => {
    const value = String(form[key]).trim();
    if (!/^\d+$/.test(value) || Number(value) < 18 || Number(value) > 120) throw new Error(`Enter ${label} as a whole number between 18 and 120.`);
    return Number(value);
  };
  const percent = (key: keyof FireFormState, label: string, positive = false): string => {
    const value = String(form[key]).trim();
    if (!/^-?\d+(?:\.\d+)?$/.test(value) || !Number.isFinite(Number(value)) || (positive && Number(value) <= 0)) throw new Error(`Enter a valid ${label}${positive ? " greater than zero" : ""}.`);
    return value;
  };
  const currentAge = age("current_age", "your current age");
  const retirementAge = age("retirement_age", "your target age");
  const longevityAge = age("longevity_age", "the planning end age");
  if (retirementAge <= currentAge) throw new Error("Choose a target age after your current age.");
  if (longevityAge <= retirementAge) throw new Error("Choose a planning end age after your target age.");
  return {
    current_age: currentAge, retirement_age: retirementAge, longevity_age: longevityAge,
    monthly_spending_today: amount("monthly_spending_today", "monthly retirement spending")!,
    monthly_investment_budget: amount("monthly_investment_budget", "your chosen monthly investment budget", true),
    annual_pension_today: amount("annual_pension_today", "annual pension", true),
    earmarked_assets: amount("earmarked_assets", "assets reserved for financial independence")!,
    inflation_percent: percent("inflation_percent", "inflation percentage"),
    accumulation_return_percent: percent("accumulation_return_percent", "annual return percentage"),
    withdrawal_rate_percent: percent("withdrawal_rate_percent", "withdrawal percentage", true),
    other_goal_monthly_commitments: amount("other_goal_monthly_commitments", "other goal contributions")!,
    reserve_monthly_commitment: amount("reserve_monthly_commitment", "reserve contribution")!,
    pension_inflation_linked: form.pension_inflation_linked,
  };
}

export function fireAllocationRows(plan: FireAllocationPlan) {
  return [
    { id: "equity", label: "Diversified equity", percent: plan.equity_percent, amount: plan.monthly_amounts.equity, colour: "#0f766e" },
    { id: "fd", label: "Bank FD set-aside", percent: plan.fd_percent, amount: plan.monthly_amounts.fd, colour: "#2563eb" },
    { id: "high_quality_debt", label: "High-quality debt", percent: plan.high_quality_debt_percent, amount: plan.monthly_amounts.high_quality_debt, colour: "#a16207" },
  ];
}
