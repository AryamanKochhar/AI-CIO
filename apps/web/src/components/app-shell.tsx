"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button, Stepper } from "@ai-cio/ui";
import { useAuth } from "@/hooks/use-auth";
import { ONBOARDING_STEPS } from "@/lib/constants";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const currentStep =
    ONBOARDING_STEPS.find((step) => pathname.startsWith(step.href))?.id ?? "welcome";

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200/80 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <Link href="/" className="text-sm font-semibold tracking-tight text-slate-900">
            AI-CIO
          </Link>
          <div className="flex items-center gap-3">
            {user ? (
              <>
                <span className="hidden text-sm text-slate-600 sm:inline">Signed in as {user.name}</span>
                <Button variant="ghost" onClick={logout}>
                  Sign out
                </Button>
              </>
            ) : (
              <Link href="/login">
                <Button variant="secondary">Sign in</Button>
              </Link>
            )}
          </div>
        </div>
      </header>
      {pathname.startsWith("/onboarding") ? (
        <div className="mx-auto max-w-5xl px-4 pt-6">
          <Stepper steps={ONBOARDING_STEPS} current={currentStep} />
        </div>
      ) : null}
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
    </div>
  );
}
