import Link from "next/link";
import type { DecisionResult } from "@ai-cio/contracts";

function destination(kind?: string) {
  if (kind === "tax")
    return [
      "/tax",
      "Review the tax context",
      "Check the underlying lots and current rule assumptions.",
    ];
  if (kind === "goals")
    return [
      "/onboarding/goals",
      "Review my goals",
      "Confirm the target, time horizon and current funding.",
    ];
  if (kind === "fd")
    return [
      "/fd",
      "Review my deposits",
      "Compare maturities with upcoming cash needs.",
    ];
  if (kind === "risk" || kind === "diversification")
    return [
      "/onboarding/twin",
      "Review my exposure",
      "Check the size and source of the exposures behind this finding.",
    ];
  return [
    "/onboarding/twin",
    "Check the supporting data",
    "Confirm your profile information before considering a change.",
  ];
}

export function RankedSuggestions({
  suggestions,
}: {
  suggestions: DecisionResult["suggestions"];
}) {
  if (!suggestions?.items?.length) return null;
  const hasRanks = Boolean(suggestions.ranking);
  return (
    <section
      id="decision-actions"
      className="decision-anchor rounded-[24px] border border-[#d7e8e1] bg-white p-5 sm:p-7"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[.18em] text-teal-700">
            01 / Your next actions
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
            {hasRanks
              ? "A clear order for your review."
              : "Suggestions to review"}
          </h2>
        </div>
        <span className="rounded-full bg-[#edf6f1] px-3 py-1.5 text-[10px] font-semibold text-teal-800">
          {suggestions.items.length} suggestions · your choice
        </span>
      </div>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
        {suggestions.ranking?.interpretation ||
          "This older result has no ranking metadata. Refresh the analysis to calculate review priorities."}
      </p>
      <ol className="mt-6 space-y-4">
        {suggestions.items.map((item, index) => {
          const [href, cta, action] = destination(item.kind);
          return (
            <li
              key={`${item.title}-${index}`}
              className={`rounded-2xl border p-5 ${index === 0 ? "border-[#bddacf] bg-[#f2f9f5]" : "border-slate-200 bg-white"}`}
            >
              <div className="flex items-start gap-3 sm:gap-4">
                <span
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm font-semibold ${index === 0 ? "bg-teal-700 text-white" : "bg-slate-100 text-slate-500"}`}
                >
                  {item.rank || index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="mb-1.5 flex flex-wrap gap-2 text-[10px] font-medium uppercase tracking-wider text-slate-500">
                        {index === 0 ? (
                          <span className="text-teal-700">Start here</span>
                        ) : null}
                        <span>
                          {item.source === "rules"
                            ? "Rule evidence"
                            : "AI narrative"}
                        </span>
                      </div>
                      <h3 className="text-base font-semibold tracking-tight text-slate-900">
                        {item.title}
                      </h3>
                    </div>
                    {item.relative_support_percent != null ? (
                      <div className="text-right">
                        <p className="text-2xl font-semibold tabular-nums tracking-tight text-teal-800">
                          {item.relative_support_percent.toFixed(2)}
                          <span className="ml-0.5 text-sm">%</span>
                        </p>
                        <p className="text-[10px] text-slate-500">
                          relative review support
                        </p>
                      </div>
                    ) : null}
                  </div>
                  {item.relative_support_percent != null ? (
                    <div
                      className="mt-4 h-1.5 overflow-hidden rounded-full bg-[#dfebe6]"
                      role="meter"
                      aria-label={`${item.title}: relative review support`}
                      aria-valuenow={item.relative_support_percent}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      <div
                        className="h-full rounded-full bg-teal-600"
                        style={{
                          width: `${Math.max(0, Math.min(100, item.relative_support_percent))}%`,
                        }}
                      />
                    </div>
                  ) : null}
                  <p className="mt-4 text-sm leading-6 text-slate-600">
                    {item.detail}
                  </p>
                  <p className="mt-2 text-[11px] leading-5 text-slate-500">
                    {item.basis}
                    {item.priority_score != null
                      ? ` · Review priority ${item.priority_score}/100`
                      : ""}
                  </p>
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200/80 pt-4">
                    <p className="max-w-lg text-xs leading-5 text-slate-500">
                      {action}
                    </p>
                    <Link
                      href={href}
                      className="inline-flex shrink-0 items-center gap-3 rounded-lg border border-teal-200 bg-white px-3 py-2 text-xs font-semibold text-teal-800 transition-colors hover:bg-teal-50"
                    >
                      {cta}
                      <span aria-hidden>↗</span>
                    </Link>
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      {suggestions.ranking ? (
        <details className="mt-5 rounded-xl border border-slate-100 bg-slate-50 p-4 text-xs text-slate-500">
          <summary className="cursor-pointer font-medium text-slate-700">
            Review priority, not investment odds · how the ranking works
          </summary>
          <p className="mt-3 leading-6">
            {suggestions.ranking.method} Policy version:{" "}
            {suggestions.ranking.version}. The weights express review order.
            They do not estimate a chance of profit. Changing the suggestion
            list changes each share.
          </p>
        </details>
      ) : null}
      <a
        href="#decision-evidence"
        className="mt-5 inline-block text-xs font-medium text-teal-800 underline underline-offset-4"
      >
        Follow the full decision trace ↓
      </a>
    </section>
  );
}
