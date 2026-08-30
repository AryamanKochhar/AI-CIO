"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, Input, Label, PageHeader } from "@ai-cio/ui";
import { ApiError } from "@/lib/api-client";
import { authApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

export default function LoginPage() {
  const router = useRouter();
  const { setUser } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("register");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
      router.push("/onboarding/understand-me");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="mx-auto max-w-md">
      <PageHeader
        kicker="Welcome"
        title={mode === "register" ? "Create your account" : "Sign in"}
        description="MVP authentication for development. Use a password of at least 8 characters."
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
          <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
        </div>
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Please wait…" : mode === "register" ? "Create account" : "Sign in"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-600">
        {mode === "register" ? "Already have an account?" : "New here?"}{" "}
        <button
          type="button"
          className="font-medium text-slate-900 underline"
          onClick={() => setMode(mode === "register" ? "login" : "register")}
        >
          {mode === "register" ? "Sign in" : "Create an account"}
        </button>
      </p>
      <p className="mt-2 text-center text-xs text-slate-500">
        <Link href="/onboarding/understand-me">Continue without signing in</Link> (legacy name-only flow)
      </p>
    </Card>
  );
}
