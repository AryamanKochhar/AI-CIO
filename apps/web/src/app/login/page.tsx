"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Button, Card, Input, Label, PageHeader, PasswordInput } from "@ai-cio/ui";
import { ApiError } from "@/lib/api-client";
import { authApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { useJourney } from "@/hooks/use-journey";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { setUser } = useAuth();
  const { goToResume } = useJourney();
  const [mode, setMode] = useState<"login" | "register">("register");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (params.get("mode") === "login") setMode("login");
  }, [params]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const user =
        mode === "register"
          ? await authApi.register({ name, email, password })
          : await authApi.login({ email, password });
      setUser(user);
      if (mode === "register") {
        router.push("/onboarding/welcome");
      } else {
        await goToResume();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="aic-card-glow mx-auto max-w-md">
      <PageHeader
        kicker="AI-CIO"
        title={mode === "register" ? "Create your account" : "Sign in"}
        description={
          mode === "register"
            ? "Start building your financial profile. Password must be at least 8 characters."
            : "Welcome back. Continue where you left off."
        }
      />
      <form className="space-y-4" onSubmit={handleSubmit}>
        {mode === "register" ? (
          <div>
            <Label htmlFor="name">What should we call you?</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
        ) : null}
        <div>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <Label htmlFor="password">Password</Label>
          <PasswordInput
            id="password"
            autoComplete={mode === "register" ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
        </div>
        {error ? <p className="text-sm text-red-600" role="alert">{error}</p> : null}
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Please wait…" : mode === "register" ? "Create account" : "Sign in"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-600">
        {mode === "register" ? "Already have an account?" : "New here?"}{" "}
        <button type="button" className="font-medium text-slate-900 underline" onClick={() => setMode(mode === "register" ? "login" : "register")}>
          {mode === "register" ? "Sign in" : "Create an account"}
        </button>
      </p>
      <p className="mt-3 text-center text-xs text-slate-500">
        Development authentication only — not production-grade security.
      </p>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-600">Loading…</p>}>
      <LoginForm />
    </Suspense>
  );
}
