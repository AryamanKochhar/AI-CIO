"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button, ProgressBar, Stepper } from "@ai-cio/ui";
import { useAuth } from "@/hooks/use-auth";
import { useJourney } from "@/hooks/use-journey";
import { ONBOARDING_STEPS } from "@/lib/constants";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { journey } = useJourney();
  const inOnboarding = pathname.startsWith("/onboarding");
  const currentStep =
    ONBOARDING_STEPS.find((step) => pathname.startsWith(step.href))?.id ?? "welcome";
  const stepIndex = ONBOARDING_STEPS.findIndex((s) => s.id === currentStep);
  const progress = inOnboarding ? ((stepIndex + 1) / ONBOARDING_STEPS.length) * 100 : 0;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <div>
            <Link href={user ? "/onboarding/welcome" : "/"} className="text-sm font-semibold tracking-tight text-slate-900">
              AI-CIO
            </Link>
            {inOnboarding && journey ? (
              <p className="mt-0.5 text-xs text-slate-500">
                Building your financial profile · {user?.name}
              </p>
            ) : null}
          </div>
          <div className="flex items-center gap-3">
            <Link href="/onboarding/welcome" className="hidden text-sm text-slate-600 hover:text-slate-900 sm:inline">
              Help
            </Link>
            {user ? (
              <>
                <span className="hidden text-sm text-slate-600 md:inline">{user.email ?? user.name}</span>
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
        {inOnboarding ? (
          <div className="border-t border-slate-100 bg-white/70 px-4 py-3">
            <div className="mx-auto max-w-5xl space-y-3">
              <Stepper steps={ONBOARDING_STEPS} current={currentStep} />
              <ProgressBar value={progress} label={`Step ${stepIndex + 1} of ${ONBOARDING_STEPS.length}`} />
            </div>
          </div>
        ) : null}
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      <footer className="mx-auto max-w-5xl px-4 pb-10 pt-4 text-center text-xs text-slate-500">
        AI-CIO helps you understand your finances before making decisions. MVP authentication — not production-grade.
      </footer>
    </div>
  );
}
