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
  financial_map?: FinancialMap;
  market_context?: MarketContext;
  ready_for_analysis: boolean;
}

export interface MarketSectorRow {
  index_code: string;
  index_name: string;
  change_percent?: string | null;
  relative_to_benchmark?: string | null;
  rank?: number;
}

export interface MarketObservation {
  type: string;
  sector_index_code?: string | null;
  sector_name?: string | null;
  market_move_percent?: string | null;
  benchmark_move_percent?: string | null;
  relative_move_percent?: string | null;
  user_exposure_percent?: string | null;
  user_exposure_value?: string | null;
  severity?: string;
  reason_codes?: string[];
}

export interface MarketAnalysisSummary {
  sector_name?: string | null;
  summary?: string | null;
  why_relevant?: string[];
  confidence?: string | null;
  source?: string | null;
  created_at?: string | null;
}

export interface MarketLlmStatus {
  enabled?: boolean;
  status?: string;
  analysis_available?: boolean;
}

export interface MarketContext {
  available: boolean;
  as_of?: string | null;
  freshness?: string;
  source?: string;
  is_stale?: boolean;
  note?: string;
  benchmark?: { index_code: string; change_percent?: string | null };
  sectors?: MarketSectorRow[];
  breadth?: Record<string, unknown>;
  sector_exposure?: Record<string, unknown>;
  observations?: MarketObservation[];
  llm?: MarketLlmStatus;
  recent_analyses?: MarketAnalysisSummary[];
}

export type FinancialMapNodeType =
  | "root"
  | "cash"
  | "income"
  | "expense"
  | "investments"
  | "asset_class"
  | "holding"
  | "cluster"
  | "goals"
  | "goal"
  | "liabilities"
  | "liability";

export interface FinancialMapNode {
  id: string;
  type: FinancialMapNodeType;
  label: string;
  subtitle?: string | null;
  value?: string | null;
  value_label?: string | null;
  parent_id?: string | null;
  icon?: string;
  available: boolean;
  child_ids: string[];
  search_text?: string;
  details?: Record<string, unknown>;
}

export interface FinancialMapEdge {
  from: string;
  to: string;
  kind: string;
}

export interface FinancialMapInsight {
  id: string;
  category: "information" | "attention" | "data_gap" | "positive";
  title: string;
  body: string;
  explore_node_id?: string | null;
}

export interface FinancialMap {
  root_id: string;
  nodes: FinancialMapNode[];
  edges: FinancialMapEdge[];
  allocation: Array<{ key: string; label: string; value?: string | null; percentage?: string | null }>;
  insights: FinancialMapInsight[];
  completeness: { flags: TwinCompleteness; understood_pct: number };
  filters: Array<{ id: string; label: string }>;
}
