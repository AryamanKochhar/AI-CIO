export type DocumentKind = "cas_pdf" | "nsdl_statement" | "cdsl_statement" | "other";

export type DocumentStatus =
  | "pending"
  | "processing"
  | "extracted"
  | "needs_review"
  | "failed";

export type GoalType =
  | "emergency"
  | "retirement"
  | "education"
  | "home"
  | "vehicle"
  | "travel"
  | "wealth"
  | "other";

export type OnboardingStep =
  | "welcome"
  | "understand-me"
  | "finances"
  | "goals"
  | "documents"
  | "review"
  | "twin";

export interface User {
  id: number;
  name: string;
  email?: string | null;
  created_at: string;
}

export interface AssessmentSession {
  id: number;
  user_id: number;
  instrument_id: number;
  status: string;
  started_at: string;
  completed_at?: string | null;
}

export interface InstrumentQuestion {
  id: string;
  text: string;
  dimension: string;
  options: Array<{ id: string; text: string }>;
}

export interface Goal {
  id: number;
  name: string;
  goal_type: string;
  target_amount?: string | null;
  target_date?: string | null;
  current_funding?: string | null;
  priority?: string;
  flexibility?: string;
}

export interface DocumentRecord {
  id: number;
  user_id: number;
  kind: DocumentKind;
  filename: string;
  status: DocumentStatus;
  validation_status?: string | null;
  warnings?: string[];
  ingested_at?: string;
}

export interface TwinCompleteness {
  psychometric: boolean;
  income: boolean;
  expenses: boolean;
  liquid: boolean;
  liabilities: boolean;
  goals: boolean;
  portfolio: boolean;
  horizon: boolean;
}

export interface DigitalTwin {
  user: { id: number; name: string; source: string };
  behaviour: {
    status: string;
    source?: string | null;
    scores?: Record<string, number> | null;
    observations?: string[];
    provenance?: Record<string, unknown>;
  };
  financial_position: Record<string, unknown>;
  portfolio: Record<string, unknown>;
  goals: { items: Goal[]; known: boolean; source: string };
  completeness: TwinCompleteness;
  ready_for_analysis: boolean;
}
