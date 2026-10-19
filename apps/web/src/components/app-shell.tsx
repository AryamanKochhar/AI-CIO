"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Button, ProgressBar } from "@ai-cio/ui";
import { cn } from "@ai-cio/utils";
import { useAuth } from "@/hooks/use-auth";
import { useJourney } from "@/hooks/use-journey";
import { ONBOARDING_STEPS } from "@/lib/constants";
import { SiteNav } from "@/components/site-nav";
import { TwinMascot } from "@/components/twin-mascot";
import { twinApi } from "@/lib/api";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { journey } = useJourney();
  const inOnboarding = pathname.startsWith("/onboarding");
  const [known, setKnown] = useState<Record<string, boolean>>({});
  useEffect(() => {
    let active = true;
    if (!user) { setKnown({}); return; }
    if (inOnboarding) twinApi.get(user.id).then((twin) => {
      if (active) setKnown(twin.completeness as unknown as Record<string, boolean>);
    }).catch(() => undefined);
    return () => { active = false; };
  }, [user, pathname, inOnboarding]);
  const currentStep =
    ONBOARDING_STEPS.find((step) => pathname.startsWith(step.href))?.id ?? "welcome";
  const stepIndex = ONBOARDING_STEPS.findIndex((s) => s.id === currentStep);
  const progress = inOnboarding ? ((stepIndex + 1) / ONBOARDING_STEPS.length) * 100 : 0;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-[rgba(15,55,110,0.1)] bg-white/70 backdrop-blur-xl">
        <div className="mx-auto max-w-6xl space-y-3 px-4 py-3.5 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <Link href="/" className="text-sm font-semibold tracking-[0.04em] text-[var(--aic-navy)]">
                AI-CIO
              </Link>
              {inOnboarding && journey ? (
                <p className="mt-0.5 text-xs text-slate-500">
                  Building your financial profile · {user?.name}
                </p>
              ) : null}
            </div>
            <div className="flex items-center gap-3">
              {user ? (
                <>
                  <span className="hidden text-sm text-slate-600 sm:inline">{user.email ?? user.name}</span>
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
          {user ? <SiteNav /> : null}
        </div>
        {inOnboarding ? (
          <div className="border-t border-[rgba(15,55,110,0.08)] bg-white/50 px-4 py-3 sm:px-6">
            <div className="mx-auto max-w-6xl space-y-3">
              <ol className="flex flex-wrap gap-2">
                {ONBOARDING_STEPS.map((step, index) => {
                  const active = index === stepIndex;
                  const done = index < stepIndex;
                  return (
                    <li key={step.id}>
                      <Link
                        href={step.href}
                        aria-current={active ? "step" : undefined}
                        className={cn(
                          "inline-flex rounded-full px-3 py-1 text-xs font-medium transition-colors",
                          active && "bg-[var(--aic-navy)] text-white shadow-sm",
                          done && !active && "bg-[var(--aic-ice)] text-slate-600 hover:bg-slate-200/70",
                          !active &&
                            !done &&
                            "bg-white/60 text-slate-500 hover:bg-white hover:text-slate-700",
                        )}
                      >
                        {step.label}
                      </Link>
                    </li>
                  );
                })}
              </ol>
              <ProgressBar value={progress} label={`Step ${stepIndex + 1} of ${ONBOARDING_STEPS.length}`} />
            </div>
          </div>
        ) : null}
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">
        {inOnboarding && !["/onboarding/welcome", "/onboarding/twin"].includes(pathname) ? <div className="mb-6"><TwinMascot completeness={known} /></div> : null}
        {children}
      </main>
      <footer className="mx-auto max-w-6xl px-4 pb-10 pt-2 text-center text-xs text-slate-500 sm:px-6">
        AI-CIO helps you understand your finances before making decisions. Educational guidance only — not
        investment advice.
      </footer>
    </div>
  );
}
