import type { OnboardingStep } from "@ai-cio/contracts";

export const ONBOARDING_STEPS: Array<{ id: OnboardingStep; label: string; href: string }> = [
  { id: "understand-me", label: "Understand me", href: "/onboarding/understand-me" },
  { id: "finances", label: "My finances", href: "/onboarding/finances" },
  { id: "goals", label: "My goals", href: "/onboarding/goals" },
  { id: "documents", label: "Documents", href: "/onboarding/documents" },
  { id: "review", label: "Review", href: "/onboarding/review" },
  { id: "twin", label: "Financial profile", href: "/onboarding/twin" },
];

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
  { value: "cas_pdf", label: "CAS (MFCentral)" },
  { value: "nsdl_statement", label: "NSDL statement" },
  { value: "cdsl_statement", label: "CDSL statement" },
  { value: "other", label: "Other" },
] as const;
