import type { DigitalTwin } from "@ai-cio/contracts";

// One tab, one active user, one short-lived snapshot. Decision payloads and
// financial data never go into localStorage. The server validates decisions.
export const TWIN_SNAPSHOT_TTL_MS = 30_000;
export const MAX_SNAPSHOT_CHARS = 128 * 1024;
export const WORKSPACE_CHANGED = "ai-cio:financial-inputs-changed";
const STORAGE_KEY = "ai-cio:twin-snapshot:v1";
const API_IDENTITY = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
let activeUserId: number | null = null;

type Snapshot = { version: 1; api: string; userId: number; writtenAt: number; expiresAt: number; twin: DigitalTwin };
type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function browserStorage(): StorageLike | undefined {
  try { return typeof window === "undefined" ? undefined : window.sessionStorage; }
  catch { return undefined; }
}

export function clearTwinSnapshot(userId?: number, storage = browserStorage()): void {
  if (!storage) return;
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (userId == null || !raw || JSON.parse(raw).userId === userId) storage.removeItem(STORAGE_KEY);
  } catch { try { storage.removeItem(STORAGE_KEY); } catch { /* Storage can be disabled. */ } }
}

export function activateWorkspaceUser(userId: number | null, storage = browserStorage()): void {
  activeUserId = userId;
  if (userId == null) { clearTwinSnapshot(undefined, storage); return; }
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    if (raw && JSON.parse(raw).userId !== userId) clearTwinSnapshot(undefined, storage);
  } catch { clearTwinSnapshot(undefined, storage); }
}

export function readTwinSnapshot(userId: number, storage = browserStorage(), now = Date.now()): Snapshot | undefined {
  if (!storage) return undefined;
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return undefined;
    if (raw.length > MAX_SNAPSHOT_CHARS) throw new Error("Oversized snapshot");
    const row = JSON.parse(raw) as Snapshot;
    if (row.version !== 1 || row.api !== API_IDENTITY || row.userId !== userId || row.twin?.user?.id !== userId ||
        !Number.isFinite(row.writtenAt) || !Number.isFinite(row.expiresAt) || row.writtenAt > now ||
        row.expiresAt <= now || row.expiresAt - row.writtenAt > TWIN_SNAPSHOT_TTL_MS ||
        !Array.isArray(row.twin?.goals?.items) || !row.twin?.completeness) throw new Error("Unverifiable snapshot");
    return row;
  } catch { clearTwinSnapshot(undefined, storage); return undefined; }
}

export function writeTwinSnapshot(userId: number, twin: DigitalTwin, storage = browserStorage(), now = Date.now()): boolean {
  if (!storage || activeUserId !== userId || twin.user.id !== userId) return false;
  try {
    const row: Snapshot = { version: 1, api: API_IDENTITY, userId, writtenAt: now, expiresAt: now + TWIN_SNAPSHOT_TTL_MS, twin };
    const raw = JSON.stringify(row);
    if (raw.length > MAX_SNAPSHOT_CHARS) { clearTwinSnapshot(userId, storage); return false; }
    storage.setItem(STORAGE_KEY, raw);
    return true;
  } catch { return false; }
}

export function notifyFinancialMutation(userId?: number): void {
  clearTwinSnapshot(userId);
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(WORKSPACE_CHANGED, { detail: { userId: userId ?? activeUserId } }));
}

export function financialMutationUser(path: string, method = "GET"): number | null | undefined {
  if (["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) return undefined;
  const user = path.match(/^\/users\/(\d+)\/(finances|goals|documents|portfolio|fds|fixed-deposits)(?:[/?]|$)/);
  if (user) return Number(user[1]);
  // Assessment routes identify their user via the active session.
  if (/^\/assessments(?:\/|$)/.test(path)) return null;
  return undefined;
}
