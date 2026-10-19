import { financialMutationUser, notifyFinancialMutation } from "./workspace-cache";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    return response.statusText || "Request failed";
  }
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<T> {
  const timeoutMs = init?.timeoutMs ?? 30_000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const externalSignal = init?.signal;
  const abort = () => controller.abort();
  externalSignal?.addEventListener("abort", abort, { once: true });
  if (externalSignal?.aborted) controller.abort();

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      ...init,
      signal: controller.signal,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init?.headers,
      },
    });
    if (!response.ok) {
      throw new ApiError(await parseError(response));
    }
    const changedUser = financialMutationUser(path, init?.method);
    if (changedUser !== undefined) notifyFinancialMutation(changedUser ?? undefined);
    if (response.status === 204 || !response.headers.get("content-type")?.includes("json")) {
      return undefined as T;
    }
    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timer);
    externalSignal?.removeEventListener("abort", abort);
  }
}
