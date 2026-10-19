"use client";

import Link from "next/link";
import { useState } from "react";
import { CompanionArt } from "@/components/companion-art";

export const TWIN_PARTS = [
  {
    key: "psychometric",
    label: "Your mindset",
    accessory: "Thoughtful lenses",
    detail: "Understand how you make decisions.",
    href: "/onboarding/understand-me",
    cta: "Explore my mindset",
  },
  {
    key: "income",
    label: "Your everyday",
    accessory: "Everyday satchel",
    detail: "Connect income and spending.",
    href: "/onboarding/finances",
    cta: "Add my finances",
  },
  {
    key: "liquid",
    label: "Your reserves",
    accessory: "Reserve badge",
    detail: "Record the cash you can access.",
    href: "/onboarding/finances",
    cta: "Add liquid savings",
  },
  {
    key: "goals",
    label: "Your direction",
    accessory: "Goal compass",
    detail: "Give your money a destination.",
    href: "/onboarding/goals",
    cta: "Set my goals",
  },
  {
    key: "portfolio",
    label: "Your investments",
    accessory: "Portfolio notebook",
    detail: "Bring your holdings into the picture.",
    href: "/onboarding/documents",
    cta: "Add my investments",
  },
] as const;
const STAGES = [
  "A little hello",
  "A thoughtful start",
  "Everyday context",
  "A clearer picture",
  "A sense of direction",
  "Your world, connected",
];

export function CompanionPreview({ dark = false }: { dark?: boolean }) {
  const [stage, setStage] = useState(3);
  const known = Object.fromEntries(
    TWIN_PARTS.map((part, i) => [part.key, i < stage]),
  );
  return (
    <div
      className={`companion-preview ${dark ? "companion-preview-dark" : ""}`}
    >
      <div className="relative mx-auto max-w-[380px]">
        <CompanionArt known={known} className="w-full" />
        <div className="companion-stage-label">
          <span className="h-1.5 w-1.5 rounded-full bg-teal-500" />
          {STAGES[stage]}
        </div>
      </div>
      <div
        className="mt-3 flex items-center justify-center gap-2"
        role="group"
        aria-label="Preview companion growth"
      >
        {[0, 1, 2, 3, 4, 5].map((value) => (
          <button
            key={value}
            type="button"
            aria-label={`Preview stage ${value}: ${STAGES[value]}`}
            aria-pressed={stage === value}
            onClick={() => setStage(value)}
            className={`companion-stage-button ${stage === value ? "is-selected" : ""}`}
          >
            {value === 0 ? "Start" : value}
          </button>
        ))}
      </div>
      <p
        className={`mt-3 text-center text-xs ${dark ? "text-slate-300" : "text-slate-500"}`}
      >
        Try the stages · illustration preview, not your saved data
      </p>
    </div>
  );
}

export function TwinMascot({
  completeness = {},
  compact = false,
}: {
  completeness?: Record<string, boolean>;
  compact?: boolean;
}) {
  const count = TWIN_PARTS.filter((part) => completeness[part.key]).length;
  const next = TWIN_PARTS.find((part) => !completeness[part.key]);
  if (compact)
    return (
      <section
        aria-label="Your companion's information progress"
        className="companion-compact"
      >
        <CompanionArt
          known={completeness}
          className="h-24 w-28 shrink-0 sm:h-28 sm:w-32"
        />
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-teal-700">
            Building your financial twin
          </p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">
            A little more you, with every step.
          </h2>
          <div className="mt-2 flex items-center gap-3">
            <div
              className="flex gap-1.5"
              aria-label={`${count} of 5 information areas connected`}
            >
              {TWIN_PARTS.map((part) => (
                <span
                  key={part.key}
                  className={`h-1.5 w-7 rounded-full ${completeness[part.key] ? "bg-teal-600" : "bg-slate-200"}`}
                />
              ))}
            </div>
            <span className="text-xs text-slate-500">{count}/5 connected</span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Accessories reflect information, not financial health.
          </p>
        </div>
        <Link
          href={next?.href || "/decisions"}
          className="hidden shrink-0 rounded-xl border border-teal-200 bg-white px-4 py-2.5 text-sm font-medium text-teal-800 hover:bg-teal-50 sm:block"
        >
          {next?.cta || "Open my decisions"} <span aria-hidden>↗</span>
        </Link>
      </section>
    );
  return (
    <section aria-label="Build your financial twin" className="companion-card">
      <div className="grid items-center gap-4 md:grid-cols-[minmax(0,.85fr)_minmax(0,1.4fr)] md:gap-8">
        <div className="companion-stage">
          <CompanionArt
            known={completeness}
            className="mx-auto w-full max-w-[320px]"
          />
          <span className="companion-stage-label">{STAGES[count]}</span>
        </div>
        <div className="px-1 py-3 sm:px-3">
          <p className="text-[11px] font-semibold uppercase tracking-[.18em] text-teal-700">
            Meet Milo · your financial companion
          </p>
          <h2 className="mt-3 max-w-lg text-3xl font-semibold leading-tight tracking-[-.035em] text-slate-900">
            Your financial life.
            <br />
            <span className="text-teal-700">Coming into focus.</span>
          </h2>
          <p className="mt-4 max-w-lg text-sm leading-7 text-slate-600">
            Every detail gives your digital twin a little more context, and Milo
            a new piece of the story. You can take it one step at a time.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <span className="rounded-full bg-teal-100 px-3 py-1.5 text-xs font-semibold text-teal-900">
              {count} of 5 areas connected
            </span>
            <span className="text-xs text-slate-500">
              Information progress, not a health score
            </span>
          </div>
          <Link
            href={next?.href || "/decisions"}
            className="mt-6 inline-flex items-center gap-3 rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white shadow-sm transition-colors hover:bg-teal-800"
          >
            {next?.cta || "Find my next action"}
            <span aria-hidden>↗</span>
          </Link>
          {next ? (
            <p className="mt-3 text-xs text-slate-500">Next: {next.detail}</p>
          ) : (
            <p className="mt-3 text-xs text-slate-500">
              Your recorded information is connected. Review its meaning in
              Decisions.
            </p>
          )}
        </div>
      </div>
      <div className="mt-5 grid gap-2 border-t border-teal-100 pt-5 sm:grid-cols-5">
        {TWIN_PARTS.map((part, index) => (
          <Link
            key={part.key}
            href={part.href}
            className={`companion-part ${completeness[part.key] ? "is-known" : ""}`}
          >
            <span className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-wider">
              <span>{String(index + 1).padStart(2, "0")}</span>
              <span>
                {completeness[part.key] ? "Connected ✓" : "Add detail +"}
              </span>
            </span>
            <span className="block text-xs font-semibold">{part.label}</span>
            <span className="mt-1 block text-[10px] leading-4 opacity-70">
              {part.accessory}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
