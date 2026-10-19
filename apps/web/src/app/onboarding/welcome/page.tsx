"use client";

import Link from "next/link";
import { Button, Card } from "@ai-cio/ui";
import { useRequireAuth, useJourney } from "@/hooks/use-journey";
import { JOURNEY_TO_ROUTE } from "@/lib/constants";
import { CompanionPreview } from "@/components/twin-mascot";

export default function WelcomePage() {
  const user = useRequireAuth();
  const { journey, goToResume } = useJourney();

  if (!user) return null;

  const resumeHref = journey
    ? (JOURNEY_TO_ROUTE[journey.current_step] ?? "/onboarding/understand-me")
    : "/onboarding/understand-me";
  const isReturning =
    journey &&
    journey.current_step !== "welcome" &&
    journey.current_step !== "psychometrics";

  return (
    <Card className="aic-card-glow !rounded-[28px] !p-6 sm:!p-9">
      <div className="grid items-center gap-6 md:grid-cols-[1.2fr_1fr]">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[.2em] text-teal-700">
            {isReturning
              ? "Welcome back to your story"
              : "A personal starting point"}
          </p>
          <h1 className="mt-4 text-3xl font-semibold leading-tight tracking-[-.04em] text-slate-900 sm:text-4xl">
            Let&apos;s build a picture
            <br />
            <span className="text-teal-700">that feels like you.</span>
          </h1>
          <p className="mt-5 max-w-lg text-sm leading-7 text-slate-500">
            Milo grows alongside your digital financial twin. Start with how you
            think, add your everyday money, then connect the goals and
            investments that matter.
          </p>
          <ul className="mt-5 space-y-3 text-xs text-slate-600">
            <li>
              <span className="mr-2 text-teal-700">✓</span>About 10–15 minutes
              with documents ready
            </li>
            <li>
              <span className="mr-2 text-teal-700">✓</span>Take a break and
              return to your saved steps
            </li>
            <li>
              <span className="mr-2 text-teal-700">✓</span>Skip what you
              don&apos;t know. We keep it unknown.
            </li>
          </ul>
          {isReturning ? (
            <div className="mb-6 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
              You can continue where you left off. Completed steps are saved.
            </div>
          ) : null}
          <div className="flex flex-wrap gap-3">
            {isReturning ? (
              <Button onClick={() => goToResume()}>
                Continue where I left off
              </Button>
            ) : (
              <Link href="/onboarding/understand-me">
                <Button>Build my twin ↗</Button>
              </Link>
            )}
            {!isReturning ? (
              <Link href={resumeHref}>
                <Button variant="secondary">Skip intro</Button>
              </Link>
            ) : null}
          </div>
        </div>
        <CompanionPreview />
      </div>
      <div className="mt-8 grid gap-4 border-t border-slate-100 pt-6 sm:grid-cols-3">
        {[
          ["01", "Your mindset", "A few questions about how you decide."],
          ["02", "Your everyday", "Income, spending and accessible savings."],
          ["03", "Your direction", "Goals, investments and a connected view."],
        ].map(([number, title, detail]) => (
          <div key={number}>
            <p className="text-[10px] font-semibold tracking-wider text-teal-700">
              {number}
            </p>
            <p className="mt-2 text-sm font-semibold text-slate-800">{title}</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}
