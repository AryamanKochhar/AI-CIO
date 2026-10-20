import type {
  AssessmentSession,
  DecisionRequestPayload,
  DecisionResult,
  DigitalTwin,
  DocumentKind,
  DocumentRecord,
  DocumentUploadResult,
  Goal,
  FirePlan,
  FirePlanningInputs,
  MutualFundIntelligence,
  BondIntelligence,
  InstrumentQuestion,
  TaxIntelligence,
  FdIntelligence,
  FixedDepositHolding,
  TrajectoryIntelligence,
  Transaction,
  User,
} from "@ai-cio/contracts";
import { apiRequest } from "./api-client";

export const authApi = {
  register: (payload: { name: string; email: string; password: string }) =>
    apiRequest<User>("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload: { email: string; password: string }) =>
    apiRequest<User>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
};

export const userApi = {
  create: (name: string) =>
    apiRequest<User>("/users", { method: "POST", body: JSON.stringify({ name }) }),
  getJourney: (userId: number) => apiRequest<Record<string, unknown>>(`/users/${userId}/journey`),
  setStep: (userId: number, current_step: string) =>
    apiRequest(`/users/${userId}/journey`, {
      method: "PUT",
      body: JSON.stringify({ current_step }),
    }),
};

export const psychometricsApi = {
  getQuestions: () =>
    apiRequest<{ questions: InstrumentQuestion[] }>("/instruments/current/questions"),
  getActive: (userId: number) =>
    apiRequest<{ active: boolean; session_id?: number; answered_count?: number; total_questions?: number }>(
      `/users/${userId}/assessments/active`,
    ),
  startAssessment: (userId: number) =>
    apiRequest<AssessmentSession>("/assessments/start", {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    }),
  submitResponse: (
    sessionId: number,
    payload: { question_id: string; answer: string; confidence: number; response_time_ms: number },
  ) =>
    apiRequest(`/assessments/${sessionId}/responses`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  complete: (sessionId: number) =>
    apiRequest(`/assessments/${sessionId}/complete`, { method: "POST" }),
  getObservations: (sessionId: number) =>
    apiRequest<{ observations: string[] }>(`/assessments/${sessionId}/observations`),
};

export const financesApi = {
  get: (userId: number) => apiRequest<Record<string, unknown>>(`/users/${userId}/finances`),
  update: (userId: number, payload: Record<string, unknown>) =>
    apiRequest(`/users/${userId}/finances`, { method: "PUT", body: JSON.stringify(payload) }),
  skip: (userId: number) =>
    apiRequest(`/users/${userId}/finances`, {
      method: "PUT",
      body: JSON.stringify({ skipped: true }),
    }),
};

export const goalsApi = {
  list: (userId: number) => apiRequest<Goal[]>(`/users/${userId}/goals`),
  create: (userId: number, payload: Record<string, unknown>) =>
    apiRequest<Goal>(`/users/${userId}/goals`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (userId: number, goalId: number, payload: Record<string, unknown>) =>
    apiRequest<Goal>(`/users/${userId}/goals/${goalId}`, { method: "PUT", body: JSON.stringify(payload) }),
  remove: (userId: number, goalId: number) =>
    apiRequest(`/users/${userId}/goals/${goalId}`, { method: "DELETE" }),
  skip: (userId: number) => apiRequest(`/users/${userId}/goals/skip`, { method: "POST" }),
};

export const documentsApi = {
  list: (userId: number) => apiRequest<DocumentRecord[]>(`/users/${userId}/documents`),
  upload: (userId: number, kind: DocumentKind, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiRequest<DocumentUploadResult>(
      `/users/${userId}/documents?kind=${kind}`,
      {
        method: "POST",
        body: form,
        timeoutMs: 120_000,
      },
    );
  },
  getHoldings: (userId: number) =>
    apiRequest<Array<Record<string, string>>>(`/users/${userId}/holdings`),
  getTransactions: (userId: number) =>
    apiRequest<Transaction[]>(`/users/${userId}/transactions`),
  confirmPortfolio: (userId: number) =>
    apiRequest(`/users/${userId}/portfolio/confirm`, { method: "POST" }),
};

export const twinApi = {
  get: (userId: number, signal?: AbortSignal) =>
    apiRequest<DigitalTwin>(`/users/${userId}/twin`, { timeoutMs: 90_000, signal }),
};

export const reviewApi = {
  get: (userId: number) => apiRequest<Record<string, unknown>>(`/users/${userId}/review`),
};

export const decisionsApi = {
  run: (userId: number, payload: DecisionRequestPayload) =>
    apiRequest<DecisionResult>(`/users/${userId}/decisions`, {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 120_000,
    }),
  cached: (userId: number, objective?: string, signal?: AbortSignal) => {
    const q = objective ? `?objective=${encodeURIComponent(objective)}` : "";
    return apiRequest<{
      available: boolean;
      stale?: boolean;
      reason?: string;
      result?: DecisionResult;
      cache?: DecisionResult["cache"];
    }>(`/users/${userId}/decisions/cached${q}`, { timeoutMs: 30_000, signal });
  },
  trajectory: (userId: number, horizonYears = 20) =>
    apiRequest<TrajectoryIntelligence>(
      `/users/${userId}/decisions/trajectory?horizon_years=${horizonYears}`,
      { timeoutMs: 60_000 },
    ),
  whatIf: (
    userId: number,
    payload: {
      monthly_contribution?: string;
      annual_return_percent?: string;
      horizon_years?: number;
      contribution_growth_pa?: string;
      goal_ids?: number[];
    },
  ) =>
    apiRequest<TrajectoryIntelligence>(`/users/${userId}/decisions/what-if`, {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 60_000,
    }),
};

export const mutualFundsApi = {
  analysis: (userId: number, signal?: AbortSignal) =>
    apiRequest<MutualFundIntelligence>(`/users/${userId}/mutual-funds`, { timeoutMs: 120_000, signal }),
  importDisclosure: (userId: number, payload: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/users/${userId}/mutual-funds/disclosures`, { method: "POST", body: JSON.stringify(payload) }),
  importBenchmark: (userId: number, payload: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/users/${userId}/mutual-funds/benchmarks`, { method: "POST", body: JSON.stringify(payload) }),
};

export const bondsApi = {
  analysis: (userId: number, signal?: AbortSignal) =>
    apiRequest<BondIntelligence>(`/users/${userId}/bonds`, { timeoutMs: 120_000, signal }),
};

export const taxApi = {
  summary: (userId: number, financialYear?: string) => {
    const q = financialYear ? `?financial_year=${encodeURIComponent(financialYear)}` : "";
    return apiRequest<TaxIntelligence>(`/users/${userId}/tax/summary${q}`, { timeoutMs: 60_000 });
  },
  opportunities: (userId: number, financialYear?: string) => {
    const q = financialYear ? `?financial_year=${encodeURIComponent(financialYear)}` : "";
    return apiRequest<{
      available?: boolean;
      financial_year?: string;
      opportunities?: TaxIntelligence["opportunities"];
      holding_period_events?: TaxIntelligence["holding_period_events"];
      disclaimer?: string;
    }>(`/users/${userId}/tax/opportunities${q}`, { timeoutMs: 60_000 });
  },
  lots: (userId: number, financialYear?: string) => {
    const q = financialYear ? `?financial_year=${encodeURIComponent(financialYear)}` : "";
    return apiRequest<{
      available?: boolean;
      financial_year?: string;
      rule_version?: string;
      tax_lots?: TaxIntelligence["tax_lots"];
      missing_data?: TaxIntelligence["missing_data"];
      data_quality?: TaxIntelligence["data_quality"];
      disclaimer?: string;
    }>(`/users/${userId}/tax/lots${q}`, { timeoutMs: 60_000 });
  },
};

export const fdApi = {
  summary: (userId: number, refresh = false) =>
    apiRequest<FdIntelligence>(`/users/${userId}/fd/summary${refresh ? "?refresh=true" : ""}`, {
      timeoutMs: 60_000,
    }),
  rates: (userId: number, refresh = false) =>
    apiRequest<NonNullable<FdIntelligence["market_rates"]>>(
      `/users/${userId}/fd/rates${refresh ? "?refresh=true" : ""}`,
      { timeoutMs: 60_000 },
    ),
  list: (userId: number) =>
    apiRequest<{ items: FixedDepositHolding[] }>(`/users/${userId}/fd/holdings`),
  create: (
    userId: number,
    payload: {
      bank_name: string;
      principal: string;
      account_label?: string;
      interest_rate_pa?: string;
      tenure_months?: number;
      start_date?: string;
      maturity_date?: string;
      compounding?: string;
      is_senior_citizen?: boolean;
      notes?: string;
    },
  ) =>
    apiRequest<FixedDepositHolding>(`/users/${userId}/fd/holdings`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  remove: (userId: number, fdId: number) =>
    apiRequest<{ ok: boolean }>(`/users/${userId}/fd/holdings/${fdId}`, { method: "DELETE" }),
};

export type NewsProfileImpact = {
  used: boolean;
  summary?: string;
  urgency?: "watch" | "monitor" | "no_material_change" | string;
  profile_areas?: Array<{
    area?: string;
    impact?: string;
    review_note?: string;
  }>;
  holding_impacts?: Array<{
    holding?: string;
    news_context?: string;
    profile_effect?: string;
    suggested_review?: string;
  }>;
  suggested_profile_reviews?: string[];
  model_note?: string;
  reason?: string;
  error?: string;
};

export const newsApi = {
  portfolio: (userId: number) =>
    apiRequest<{
      available: boolean;
      status: string;
      holdings: Array<{ name: string; valuation: string; asset_class?: string | null }>;
      articles: Array<{
        holding: string;
        title?: string;
        description?: string;
        url?: string;
        image?: string;
        published_at?: string;
        source?: string;
      }>;
      profile_impact?: NewsProfileImpact;
      reason?: string | null;
    }>(`/users/${userId}/news`, { timeoutMs: 90_000 }),
};


export const fireApi = {
  preview: (userId: number, inputs: FirePlanningInputs) =>
    apiRequest<FirePlan>(`/users/${userId}/fire/preview`, { method: "POST", body: JSON.stringify(inputs), timeoutMs: 60_000 }),
};
