export type DocumentKind = "cas_pdf" | "nsdl_statement" | "cdsl_statement" | "other" | "demo_portfolio";

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
  | "review_equity_portfolio"
  | "explore_counterfactuals";

export interface DecisionRequestPayload {
  objective: DecisionObjective;
  available_capital?: string | null;
  constraints?: Record<string, unknown>;
  requested_action?: string | null;
  /** When true, bypass cache and recompute (LLM / market / agents). */
  force_refresh?: boolean;
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
  cache?: {
    hit?: boolean;
    stale?: boolean;
    cached_at?: string | null;
    expires_at?: string | null;
    ttl_seconds?: number;
    input_fingerprint?: string;
    current_fingerprint?: string;
    note?: string;
    forced?: boolean;
  };
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
      rank?: number;
      priority_score?: number;
      relative_support_percent?: number;
      ranking_basis?: string;
      calibrated_probability?: boolean;
    }>;
    ranking?: { version: string; method: string; interpretation: string };
    ai_used?: boolean;
    ai_error?: string | null;
    disclaimer?: string;
  };
  tax_intelligence?: TaxIntelligence;
  fd_intelligence?: FdIntelligence;
  trajectory_intelligence?: TrajectoryIntelligence;
  decision_trace?: DecisionTrace;
  agent_perspectives?: AgentPerspectives;
  temporal_changes?: TemporalChanges;
  behavioral_intelligence?: BehavioralIntelligence;
  data_quality?: DataQualityReport;
  counterfactuals?: CounterfactualsPayload;
  sector_day_changes?: {
    available?: boolean;
    source?: string;
    metric?: string;
    sectors?: Array<{ name: string; day_change_percent: number }>;
    doing_well?: Array<{ name: string; day_change_percent: number }>;
    doing_poorly?: Array<{ name: string; day_change_percent: number }>;
    note?: string;
    reason?: string;
    stale?: boolean;
  };
}

export interface AgentPerspective {
  agent: string;
  label: string;
  status: "available" | "unavailable" | "not_evaluated" | string;
  finding: string;
  recommendation: string;
  confidence?: string;
  supporting_data?: Record<string, unknown>;
  risks?: string[];
  alternatives?: string[];
  conflicts_with?: string[];
  priority?: string;
  detail?: string;
}

export interface AgentDisagreement {
  title: string;
  agents: string[];
  summary: string;
  portfolio_stance?: string;
  tax_stance?: string;
  evidence?: Record<string, unknown>;
}

export interface AgentPerspectives {
  available?: boolean;
  agents?: AgentPerspective[];
  disagreements?: AgentDisagreement[];
  key_disagreement?: AgentDisagreement | null;
  cio_synthesis?: {
    conclusion?: string;
    agreement?: string;
    primary_conflict?: string | null;
    note?: string;
  };
}

export interface DecisionTraceStepInput {
  label: string;
  value?: string | number | null;
  source?: string;
}

export interface DecisionTrace {
  available?: boolean;
  generated_at?: string;
  decision?: string;
  confidence?: string;
  data_freshness?: {
    updated_at?: string;
    stages?: string[];
    duration_ms?: number;
    analyzer?: string;
  };
  steps?: {
    inputs?: DecisionTraceStepInput[];
    observations?: Array<{
      title?: string;
      detail?: string;
      severity?: string;
      metric?: string | null;
      source?: string;
    }>;
    calculations?: Array<{ rule?: string; source?: string }>;
    specialist_findings?: AgentPerspective[];
    conflicts?: AgentDisagreement[];
    cio_synthesis?: {
      conclusion?: string;
      agreement?: string;
      primary_conflict?: string | null;
      note?: string;
    };
    final_finding?: {
      decision?: string;
      recommended_actions?: string[];
      confidence?: string;
    };
  };
  disclaimer?: string;
}

export interface TemporalChangeItem {
  metric: string;
  previous_value?: string | number | null;
  current_value?: string | number | null;
  change_amount?: string | number | null;
  change_pct?: string | number | null;
  period_from?: string | null;
  period_to?: string | null;
  contributing_factors?: string[];
  confidence?: string;
}

export interface TemporalChanges {
  available?: boolean;
  items?: TemporalChangeItem[];
  reason?: string | null;
}

export interface BehavioralItem {
  label: string;
  value: string;
  score?: number | null;
  note?: string | null;
}

export interface BehavioralIntelligence {
  available?: boolean;
  declared?: {
    available?: boolean;
    source?: string | null;
    status?: string;
    items?: BehavioralItem[];
  };
  observed?: {
    available?: boolean;
    source?: string;
    status?: string;
    behavior_score?: number | null;
    items?: BehavioralItem[];
  };
  divergences?: Array<{
    title: string;
    summary: string;
    confidence?: string;
    causation_claimed?: boolean;
    evidence?: Record<string, unknown>;
  }>;
  disclaimer?: string;
}

export interface DataQualityItem {
  label: string;
  status: "verified" | "incomplete" | "conflicting" | "stale" | "unknown" | string;
  detail?: string;
  source?: string;
}

export interface DataQualityReport {
  available?: boolean;
  counts?: Record<string, number>;
  items?: DataQualityItem[];
  confidence_note?: string;
  disclaimer?: string;
}

export interface CounterfactualScenario {
  id: string;
  kind: "recommendation_replay" | "forward_what_if" | "retrospective_path" | string;
  title: string;
  question?: string;
  actual?: Record<string, unknown>;
  alternatives?: Array<Record<string, unknown>>;
  deltas?: Record<string, unknown>;
  assumptions?: string[];
  confidence?: string | number;
  ai_explanation?: string;
  ai_why_it_matters?: string;
  ai_priority_rank?: number;
}

export interface CounterfactualsPayload {
  available?: boolean;
  scenarios?: CounterfactualScenario[];
  disclaimer?: string;
  ai?: {
    used?: boolean;
    reason?: string;
    error?: string;
    cio_narrative?: string;
    priority_focus?: string;
    tradeoff_insight?: string;
    suggested_next_review?: string;
    model_note?: string;
  };
}

export interface TrajectoryScoreComponent {
  score?: number | null;
  status?: string;
  note?: string;
  raw?: string | null;
}

export interface TrajectoryIntelligence {
  available?: boolean;
  status?: string;
  reason?: string;
  snapshot?: {
    net_worth?: string | null;
    investable_assets?: string | null;
    monthly_income?: string | null;
    monthly_expenses?: string | null;
    monthly_surplus?: string | null;
    savings_rate_percent?: string | null;
    portfolio_value?: string | null;
    liquid_savings?: string | null;
    fixed_deposits?: string | null;
    liabilities?: string | null;
    liquid_months_cover?: string | null;
    cadence_assumption?: string;
  };
  score?: {
    overall_score?: number | null;
    max_score?: number;
    component_scores?: Record<string, TrajectoryScoreComponent>;
    component_weights?: Record<string, number>;
    explanations?: string[];
    missing_data?: string[];
    label?: string;
    disclaimer?: string;
  };
  projections?: {
    principal?: string | null;
    monthly_contribution?: string | null;
    contribution_growth_pa?: string | null;
    inflation_pa?: string | null;
    horizons?: number[];
    scenarios?: Record<string, string | null>;
    series?: Record<
      string,
      Array<{
        year: number;
        value?: string | null;
        contributions?: string | null;
        growth?: string | null;
      }>
    >;
    endpoints_by_horizon?: Record<
      string,
      Record<string, { year?: number; value?: string | null; contributions?: string | null; growth?: string | null }>
    >;
    sensitivity_matrix?: {
      horizon_years?: number;
      rows?: Array<Record<string, string | null>>;
    };
    assumptions?: string[];
    disclaimer?: string;
  };
  goal_projections?: Array<{
    goal_id?: number;
    goal_name?: string | null;
    target_amount?: string | null;
    years_remaining?: number | null;
    projected_corpus?: string | null;
    coverage_ratio?: string | null;
    likelihood_status?: string;
    likelihood_percent?: number | null;
    required_monthly_contribution?: string | null;
    narrative?: string;
    scenario_funding?: Record<
      string,
      {
        projected_corpus?: string | null;
        coverage_ratio?: string | null;
        likelihood_status?: string;
        likelihood_percent?: number | null;
        required_monthly_contribution?: string | null;
        shortfall_or_surplus?: string | null;
      }
    >;
  }>;
  behavior?: {
    available?: boolean;
    status?: string;
    behavior_score?: number | null;
    components?: Record<string, TrajectoryScoreComponent>;
    metrics?: Record<string, unknown>;
    comments?: string[];
    missing_data?: string[];
    source?: string;
    disclaimer?: string;
  };
  insights?: string[];
  recommended_actions?: string[];
  what_if?: {
    horizon_years?: number;
    monthly_contribution?: string | null;
    annual_return_percent?: string | null;
    projected_value?: string | null;
    base_projected_value?: string | null;
    delta_vs_base?: string | null;
    note?: string;
  };
  decision_impact?: Record<string, unknown>;
  assumptions?: string[];
  disclaimer?: string;
}

export interface TaxOpportunity {
  type?: string;
  security?: string | null;
  isin?: string | null;
  amount?: string | null;
  estimated_tax_impact?: string | null;
  threshold?: string;
  threshold_remaining?: string;
  holding_period_days?: number | null;
  term?: string | null;
  confidence?: number;
  reason?: string;
  risks?: string[];
  label?: string;
}

export interface TaxIntelligence {
  available?: boolean;
  agent?: string;
  status?: string;
  reason?: string;
  financial_year?: string;
  assessment_year?: string;
  rule_version?: string;
  as_of?: string;
  summary?: {
    stcg?: string;
    ltcg?: string;
    stcl?: string;
    ltcl?: string;
    realized_gains?: string;
    realized_losses?: string;
    unrealized_gains?: string;
    unrealized_losses?: string;
    estimated_tax?: string;
    taxable_gains_estimate?: {
      stcg?: string;
      ltcg_after_exemption?: string;
    };
  };
  tax_estimate?: Record<string, unknown>;
  by_security?: Array<Record<string, unknown>>;
  loss_inventory?: {
    current_year_stcl?: string;
    current_year_ltcl?: string;
    prior_year_stcl?: string | null;
    prior_year_ltcl?: string | null;
    carry_forward_history?: string;
    note?: string;
    set_off_rules?: Record<string, unknown>;
  };
  opportunities?: TaxOpportunity[];
  holding_period_events?: Array<{
    type?: string;
    security?: string;
    isin?: string | null;
    days_to_long_term?: number | null;
    unrealized_gain_loss?: string | null;
    current_term?: string | null;
    reason?: string;
    risks?: string[];
  }>;
  tax_lots?: {
    realized?: Array<Record<string, unknown>>;
    unrealized?: Array<Record<string, unknown>>;
  };
  data_quality?: {
    coverage_pct?: number;
    insufficient_cost_basis_count?: number;
    message?: string;
    total_holdings?: number;
    usable_cost_lots?: number;
    insufficient?: number;
  };
  missing_data?: Array<Record<string, unknown>>;
  comments?: string[];
  assumptions?: string[];
  rules_used?: string[];
  alerts?: Array<{
    type?: string;
    severity?: string;
    title?: string;
    detail?: string;
    href?: string;
  }>;
  tax_implications_for_recommendations?: Array<Record<string, unknown>>;
  disclaimer?: string;
}

export interface FixedDepositHolding {
  id?: number;
  bank_name: string;
  account_label?: string | null;
  principal?: string;
  interest_rate_pa?: string | null;
  tenure_months?: number | null;
  start_date?: string | null;
  maturity_date?: string | null;
  compounding?: string | null;
  is_senior_citizen?: boolean;
  notes?: string | null;
  market_match?: Record<string, unknown> | null;
  rate_gap_pa?: string | null;
}

export interface FdIntelligence {
  available?: boolean;
  agent?: string;
  status?: string;
  reason?: string;
  summary?: {
    fd_count?: number;
    total_principal?: string;
    bank_count?: number;
    liquid_cash?: string | null;
    combined_cash_and_fd?: string | null;
  };
  fixed_deposits?: FixedDepositHolding[];
  by_bank?: Array<{ bank_name: string; principal?: string }>;
  market_rates?: {
    source?: string;
    source_url?: string;
    status?: string;
    as_of_note?: string | null;
    rates?: Array<{
      bank?: string;
      general_min?: string | null;
      general_max?: string | null;
      senior_min?: string | null;
      senior_max?: string | null;
    }>;
    disclaimer?: string;
    scrape_error?: string;
  };
  top_market_rates?: Array<Record<string, unknown>>;
  opportunities?: Array<{
    type?: string;
    bank_name?: string | null;
    reason?: string;
    amount?: string;
    confidence?: number;
  }>;
  maturity_alerts?: Array<{
    type?: string;
    bank_name?: string;
    days_to_maturity?: number;
    principal?: string;
    reason?: string;
  }>;
  comments?: string[];
  assumptions?: string[];
  fd_implications_for_recommendations?: Array<Record<string, unknown>>;
  disclaimer?: string;
}
