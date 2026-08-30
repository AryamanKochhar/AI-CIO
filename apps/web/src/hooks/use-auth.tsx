"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { User } from "@ai-cio/contracts";

const STORAGE_KEY = "ai-cio-session";

interface SessionState {
  user: User | null;
  sessionId: number | null;
}

interface AuthContextValue extends SessionState {
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
    return JSON.parse(raw) as SessionState;
  } catch {
    return { user: null, sessionId: null };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ user: null, sessionId: null });

  useEffect(() => {
    setState(readStorage());
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      setUser: (user) => setState((prev) => ({ ...prev, user })),
      setSessionId: (sessionId) => setState((prev) => ({ ...prev, sessionId })),
      logout: () => setState({ user: null, sessionId: null }),
    }),
    [state],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
