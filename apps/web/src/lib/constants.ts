import type { OnboardingStep } from "@ai-cio/contracts";

export const ONBOARDING_STEPS: Array<{ id: OnboardingStep | "welcome"; label: string; href: string }> = [
  { id: "welcome", label: "Welcome", href: "/onboarding/welcome" },
  { id: "understand-me", label: "Understand me", href: "/onboarding/understand-me" },
  { id: "finances", label: "My finances", href: "/onboarding/finances" },
  { id: "goals", label: "My goals", href: "/onboarding/goals" },
  { id: "documents", label: "My portfolio", href: "/onboarding/documents" },
  { id: "review", label: "Review", href: "/onboarding/review" },
  { id: "twin", label: "Financial profile", href: "/onboarding/twin" },
];

export const JOURNEY_TO_ROUTE: Record<string, string> = {
  welcome: "/onboarding/welcome",
  psychometrics: "/onboarding/understand-me",
  finances: "/onboarding/finances",
  goals: "/onboarding/goals",
  portfolio: "/onboarding/documents",
  review: "/onboarding/review",
  analysis: "/onboarding/twin",
  decide: "/onboarding/twin",
};

export const GOAL_TYPES = [
  { value: "retirement", label: "Retirement" },
  { value: "emergency", label: "Emergency fund" },
  { value: "home", label: "Home" },
  { value: "education", label: "Education" },
  { value: "vehicle", label: "Vehicle" },
  { value: "travel", label: "Travel" },
  { value: "wealth", label: "Wealth creation" },
  { value: "other", label: "Custom" },
] as const;

export const DOCUMENT_TYPES = [
  { value: "cas_pdf", label: "CAS" },
  { value: "nsdl_statement", label: "NSDL" },
  { value: "cdsl_statement", label: "CDSL" },
  { value: "other", label: "Other" },
] as const;

export const COMPLETENESS_LABELS: Record<string, string> = {
  psychometric: "How you decide",
  income: "Income",
  expenses: "Expenses",
  liquid: "Liquid savings",
  liabilities: "Liabilities",
  goals: "Goals",
  portfolio: "Portfolio",
  horizon: "Investment horizon",
};

export function completenessPercent(flags: Record<string, boolean> | { [key: string]: boolean }): number {
  const keys = Object.keys(flags);
  if (!keys.length) return 0;
  const known = keys.filter((k) => flags[k]).length;
  return Math.round((known / keys.length) * 100);
}
