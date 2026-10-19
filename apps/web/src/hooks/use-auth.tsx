"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { User } from "@ai-cio/contracts";
import { activateWorkspaceUser } from "@/lib/workspace-cache";

const STORAGE_KEY = "ai-cio-session";

interface SessionState {
  user: User | null;
  sessionId: number | null;
}

interface AuthContextValue extends SessionState {
  isHydrated: boolean;
  setUser: (user: User | null) => void;
  setSessionId: (id: number | null) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStorage(): SessionState {
  if (typeof window === "undefined") return { user: null, sessionId: null };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { user: null, sessionId: null };
    const value = JSON.parse(raw) as SessionState;
    if (value.user && (!Number.isInteger(value.user.id) || value.user.id <= 0)) return { user: null, sessionId: null };
    return { user: value.user ?? null, sessionId: value.user && typeof value.sessionId === "number" ? value.sessionId : null };
  } catch {
    return { user: null, sessionId: null };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ user: null, sessionId: null });
  const [isHydrated, setHydrated] = useState(false);

  useEffect(() => {
    const restored = readStorage();
    activateWorkspaceUser(restored.user?.id ?? null);
    setState(restored);
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (isHydrated) {
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
      catch { /* The active in-memory session still works when storage is disabled. */ }
    }
  }, [state, isHydrated]);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      isHydrated,
      setUser: (user) => {
        activateWorkspaceUser(user?.id ?? null);
        setState((prev) => ({ user, sessionId: prev.user?.id === user?.id ? prev.sessionId : null }));
      },
      setSessionId: (sessionId) => setState((prev) => ({ ...prev, sessionId })),
      logout: () => { activateWorkspaceUser(null); setState({ user: null, sessionId: null }); },
    }),
    [state, isHydrated],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
