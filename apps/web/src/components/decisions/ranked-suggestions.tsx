import Link from "next/link";
import type { DecisionResult } from "@ai-cio/contracts";

function destination(kind?: string) {
  if (kind === "tax") return ["/tax", "Review tax detail"];
  if (kind === "goals") return ["/onboarding/goals", "Review your goals"];
  if (kind === "fd") return ["/fd", "Review deposits"];
  return ["/onboarding/twin", "Check supporting profile data"];
}

export function RankedSuggestions({ suggestions }: { suggestions: DecisionResult["suggestions"] }) {
  if (!suggestions?.items?.length) return null;
  const hasRanks = Boolean(suggestions.ranking);
  return <section className="rounded-3xl border border-teal-100 bg-white p-6">
    <p className="text-xs font-semibold uppercase tracking-widest text-teal-700">Your next actions</p>
    <h2 className="mt-2 text-2xl font-semibold text-slate-900">{hasRanks ? "Suggestions ranked for review" : "Suggestions to review"}</h2>
    <p className="mt-2 text-sm leading-relaxed text-slate-600">{suggestions.ranking?.interpretation || "This older result has no ranking metadata. Refresh the analysis to calculate review priorities."}</p>
    <ol className="mt-5 space-y-3">{suggestions.items.map((item, index) => {
      const [href, cta] = destination(item.kind);
      return <li key={`${item.title}-${index}`} className="rounded-2xl border border-slate-100 bg-slate-50 p-4"><div className="flex flex-wrap justify-between gap-3"><h3 className="font-semibold text-slate-900">{item.rank ? `${item.rank}. ` : ""}{item.title}</h3>{item.relative_support_percent != null ? <span className="text-sm font-semibold tabular-nums text-teal-800">{item.relative_support_percent.toFixed(2)}% relative support</span> : null}</div>{item.relative_support_percent != null ? <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200" role="meter" aria-label={`${item.title}: relative support`} aria-valuenow={item.relative_support_percent} aria-valuemin={0} aria-valuemax={100}><div className="h-full rounded-full bg-teal-600" style={{width: `${item.relative_support_percent}%`}} /></div> : null}<p className="mt-3 text-sm leading-relaxed text-slate-700">{item.detail}</p><p className="mt-2 text-xs text-slate-500">{item.basis} {item.priority_score != null ? `· Priority ${item.priority_score}/100 · ${item.source === "rules" ? "Rule evidence" : "AI narrative"}` : ""}</p><Link href={href} className="mt-3 inline-block text-sm font-medium text-teal-800 underline underline-offset-4">{cta} →</Link></li>;
    })}</ol>
    {suggestions.ranking ? <details className="mt-4 text-xs text-slate-500"><summary className="cursor-pointer font-medium">How this ranking works</summary><p className="mt-2 leading-relaxed">{suggestions.ranking.method} Policy version: {suggestions.ranking.version}. These weights express review order. They do not estimate a chance of profit, and changing the list changes each share.</p></details> : null}
  </section>;
}
