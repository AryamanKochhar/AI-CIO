import Link from "next/link";

const STEPS = [
  ["/onboarding/twin", "1. Check your twin", "Confirm finances, goals and statement data."],
  ["/decisions", "2. Compare suggestions", "Review rank, evidence and missing information."],
  ["/tax", "3. Check the trade-offs", "Review taxes before changing investments."],
  ["/fd", "4. Review liquidity", "Compare deposit maturities with upcoming needs."],
] as const;

export function DecisionNextSteps() {
  return <nav aria-label="Financial decision flow" className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4">{STEPS.map(([href, title, detail]) => <Link key={href} href={href} className="rounded-xl p-3 transition-colors hover:bg-teal-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-600"><span className="block text-sm font-semibold text-teal-800">{title} →</span><span className="mt-1 block text-xs leading-relaxed text-slate-600">{detail}</span></Link>)}</nav>;
}
