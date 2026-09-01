import type { DecisionObjective, OnboardingStep } from "@ai-cio/contracts";

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
  {
    value: "cdsl_statement",
    label: "CDSL CAS",
    title: "CDSL Consolidated Account Statement",
    description: "Demat holdings, transactions, and mutual fund investments",
  },
  {
    value: "nsdl_statement",
    label: "NSDL CAS",
    title: "NSDL Demat statement",
    description: "Demat account and securities statement",
  },
  {
    value: "cas_pdf",
    label: "Mutual Fund CAS",
    title: "Mutual Fund statement",
    description: "CAMS / KFintech consolidated mutual fund statement",
  },
  {
    value: "other",
    label: "Other document",
    title: "Other document",
    description: "Upload for reference — structured extraction may be limited",
  },
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

export const DECISION_OBJECTIVES: Array<{
  value: DecisionObjective;
  label: string;
  description: string;
  needsCapital: boolean;
}> = [
  {
    value: "allocate_capital",
    label: "Allocate available capital",
    description: "See how new money could be split across cash, debt, and equity based on your profile.",
    needsCapital: true,
  },
  {
    value: "review_portfolio",
    label: "Review my portfolio",
    description: "Check fit with your goals, concentration, and what we know about your holdings.",
    needsCapital: false,
  },
  {
    value: "evaluate_portfolio_risk",
    label: "Evaluate portfolio risk",
    description: "Look at willingness, capacity, concentration, and liquidity together — not a single score.",
    needsCapital: false,
  },
  {
    value: "evaluate_strategy_suitability",
    label: "Check strategy fit",
    description: "See whether a plan lines up with your goals, horizon, and constraints.",
    needsCapital: false,
  },
];

export function completenessPercent(flags: Record<string, boolean> | { [key: string]: boolean }): number {
  const keys = Object.keys(flags);
  if (!keys.length) return 0;
  const known = keys.filter((k) => flags[k]).length;
  return Math.round((known / keys.length) * 100);
}
