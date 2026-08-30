"use client";

import Link from "next/link";
import { Button, Card, PageHeader } from "@ai-cio/ui";
import { useRequireAuth, useJourney } from "@/hooks/use-journey";
import { JOURNEY_TO_ROUTE } from "@/lib/constants";

export default function WelcomePage() {
  const user = useRequireAuth();
  const { journey, goToResume } = useJourney();

  if (!user) return null;

  const resumeHref = journey ? JOURNEY_TO_ROUTE[journey.current_step] ?? "/onboarding/understand-me" : "/onboarding/understand-me";
  const isReturning = journey && journey.current_step !== "welcome" && journey.current_step !== "psychometrics";

  return (
    <Card className="aic-card-glow">
      <PageHeader
        kicker={isReturning ? "Welcome back" : "Let's begin"}
        title="Let's build your financial profile"
        description="We'll first understand how you make financial decisions, then your financial position, goals, and existing investments."
      />
      <ul className="mb-8 space-y-3 text-sm text-slate-700">
        <li>· About 10–15 minutes if you have documents ready</li>
        <li>· You can skip anything you do not know — we label it as unknown</li>
        <li>· Your data stays private to your account</li>
      </ul>
      {isReturning ? (
        <div className="mb-6 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          You can continue where you left off. Completed steps are saved.
        </div>
      ) : null}
      <div className="flex flex-wrap gap-3">
        {isReturning ? (
          <Button onClick={() => goToResume()}>Continue where I left off</Button>
        ) : (
          <Link href="/onboarding/understand-me">
            <Button>Begin</Button>
          </Link>
        )}
        {!isReturning ? (
          <Link href={resumeHref}>
            <Button variant="secondary">Skip intro</Button>
          </Link>
        ) : null}
      </div>
    </Card>
  );
}
