import type {
  AssessmentSession,
  DecisionRequestPayload,
  DecisionResult,
  DigitalTwin,
  DocumentKind,
  DocumentRecord,
  DocumentUploadResult,
  Goal,
  InstrumentQuestion,
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
  get: (userId: number) =>
    apiRequest<DigitalTwin>(`/users/${userId}/twin`, { timeoutMs: 60_000 }),
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
};
