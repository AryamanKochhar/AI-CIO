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
  statement_period?: { start?: string | null; end?: string | null } | null;
  metadata?: Record<string, unknown> | null;
}

export interface DocumentUploadResult {
  document_id: number;
  user_id: number;
  kind: DocumentKind;
  filename: string;
  status: string;
  validation_status?: string | null;
  holdings: number;
  transactions: number;
  warnings: string[];
  parser_pending: boolean;
  already_processed?: boolean;
  summary?: {
    demat_accounts?: number;
    equity_holdings?: number;
    mutual_fund_folios?: number;
    demat_transactions?: number;
    mutual_fund_transactions?: number;
    portfolio_value?: string | null;
    equity_value?: string | null;
    mutual_fund_value?: string | null;
    cas_id?: string | null;
  } | null;
  statement_period?: { start?: string | null; end?: string | null } | null;
  successful_sections?: string[];
  failed_sections?: string[];
}

export interface Transaction {
  date?: string | null;
  scheme_name: string;
  transaction_type: string;
  description?: string | null;
  amount?: string | null;
  units?: string | null;
  nav?: string | null;
  unit_balance?: string | null;
  folio?: string | null;
  isin?: string | null;
  amc?: string | null;
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
