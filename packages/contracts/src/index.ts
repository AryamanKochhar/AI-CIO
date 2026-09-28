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
  horizon_years?: number | null;
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

export type DecisionObjective =
  | "allocate_capital"
  | "review_portfolio"
  | "evaluate_portfolio_risk"
  | "evaluate_strategy_suitability"
  | "review_equity_portfolio";

export interface DecisionRequestPayload {
  objective: DecisionObjective;
  available_capital?: string | null;
  constraints?: Record<string, unknown>;
  requested_action?: string | null;
}

export interface InvestmentStrategyView {
  name: string;
  allocation: Record<string, string>;
  rationale: string[];
  assumptions: string[];
  expected_characteristics: Record<string, string>;
  risks: string[];
  evidence?: Array<{ source: string; section: string; reference: string; content: string }>;
}

export interface StrategyEvaluationView {
  strategy: InvestmentStrategyView;
  factors: Record<string, string>;
  strengths: string[];
  weaknesses: string[];
  risks: string[];
  tradeoffs: string[];
  suitability_indicators: Record<string, string>;
  conflicts: string[];
}

export interface DecisionResult {
  decision_id: string;
  user_id: number;
  objective: DecisionObjective;
  decision: string;
  selected_strategy: InvestmentStrategyView | null;
  alternatives: InvestmentStrategyView[];
  rationale: string[];
  key_factors: string[];
  risks: string[];
  tradeoffs: string[];
  assumptions: string[];
  evidence: Array<{ source: string; section: string; reference: string; content: string; relevance?: string }>;
  strategy_evaluations: StrategyEvaluationView[];
  validation: { passed: boolean; errors: string[]; warnings: string[] };
  confidence: string;
  context_summary: Record<string, unknown>;
  execution?: {
    stages?: string[];
    capabilities?: string[];
    duration_ms?: number;
    analyzer?: string;
    agent?: string;
    focus?: string;
  };
  recommended_actions?: string[];
  insight_cards?: Array<{
    type: string;
    title: string;
    detail: string;
    severity?: string;
  }>;
  style_allocation?: Array<{
    style: string;
    value?: string | null;
    percent?: string | null;
    methodology?: string;
  }>;
  sector_allocation?: Array<{
    sector: string;
    value?: string | null;
    percent?: string | null;
    weight_percent?: string | null;
    source?: string;
  }>;
  portfolio_health?: {
    score?: number | null;
    max_score?: number;
    stars?: number;
    label?: string;
    components?: Record<
      string,
      { score?: number | null; available?: boolean; note?: string }
    >;
    methodology?: string;
  };
  top_worries?: Array<{
    title: string;
    detail: string;
    severity?: string;
    metric?: string | null;
    recommended_range?: string | null;
  }>;
  concentration_analysis?: Record<string, unknown>;
  true_exposure?: {
    question?: string;
    sector_exposure?: Array<{ sector?: string; percent?: string | null; value?: string | null }>;
    market_cap_exposure?: Array<{ category?: string; percent?: string | null; value?: string | null }>;
    economic_themes?: Array<{ theme?: string; percent?: string | null; value?: string | null }>;
    methodology?: string;
  };
  quality_valuation?: {
    available?: boolean;
    reason?: string;
    quadrants?: Record<string, unknown[]>;
    axes?: { x?: string; y?: string };
  };
  goal_likelihood?: Array<{
    goal_id?: number;
    goal_name?: string | null;
    goal_type?: string | null;
    target_amount?: string | null;
    current_amount?: string | null;
    years_remaining?: number | null;
    monthly_surplus_used?: string | null;
    assumed_annual_return_percent?: string;
    assumed_inflation_percent?: string;
    projected_corpus?: string | null;
    coverage_ratio?: string | null;
    likelihood_status?: "likely" | "possible" | "at_risk" | "unlikely" | "unknown" | string;
    likelihood_percent?: number | null;
    required_monthly_contribution?: string | null;
    missing_inputs?: string[];
    narrative?: string;
    disclaimer?: string;
  }>;
  sector_opportunity?: {
    available?: boolean;
    reason?: string;
    methodology?: string;
    disclaimer?: string;
    benchmark?: { name?: string; return_20d?: number; return_50d?: number };
    recommendations?: Array<{
      rank?: number;
      name: string;
      final_score?: number;
      technical_score?: number;
      diversification_score?: number;
      exposure_pct?: number;
      unmapped?: boolean;
      portfolio_category?: string | null;
      trend_label?: string;
      rs_label?: string;
      logic?: string;
      label?: string;
    }>;
    deprioritized?: Array<{
      name: string;
      exposure_pct?: number;
      portfolio_category?: string | null;
      final_score?: number;
      reason?: string;
      logic?: string;
    }>;
    high_exposure_categories?: Array<{ name: string; exposure_pct?: number; reason?: string }>;
    sectors?: Array<Record<string, unknown>>;
    failed?: Array<{ name?: string; reason?: string }>;
  };
  suggestions?: {
    available?: boolean;
    summary?: string;
    items?: Array<{
      title: string;
      detail: string;
      kind?: string;
      source?: string;
      basis?: string;
    }>;
    ai_used?: boolean;
    ai_error?: string | null;
    disclaimer?: string;
  };
}
