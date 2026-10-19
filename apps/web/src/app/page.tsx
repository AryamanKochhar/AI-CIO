import Link from "next/link";
import { HomeActions } from "@/components/home-actions";
import { HomeOverview } from "@/components/home-overview";
import { DemoPersonas } from "@/components/demo-personas";

export default function HomePage() {
  return (
    <div className="space-y-8">
      <section className="aic-hero overflow-hidden rounded-3xl px-7 py-12 text-white shadow-[0_20px_50px_rgba(11,31,58,0.25)] md:px-12 md:py-14">
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-300">AI-CIO</p>
        <h1 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight md:text-[2.125rem] md:leading-tight">
          What is happening with your financial life?
        </h1>
        <p className="mt-4 max-w-xl text-sm leading-relaxed text-slate-300">
          AI-CIO brings your finances, goals, and behaviour into one decision system — so the most important
          findings are visible before you dig into the detail.
        </p>
        <HomeActions />
      </section>

      <HomeOverview />
      <DemoPersonas />

      <div className="grid gap-6 md:grid-cols-3">
        {[
          ["Understand how you decide", "A short behavioural assessment — scored securely on our servers."],
          ["Tell us about your finances", "Income, expenses, savings, and goals. Blank means unknown, not zero."],
          ["Open Decisions", "Run the orchestrator and read the AI-CIO Decision Brief."],
        ].map(([title, body]) => (
          <div key={title} className="border-t border-[rgba(15,55,110,0.12)] pt-4">
            <h2 className="text-base font-semibold text-[var(--aic-navy)]">{title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">{body}</p>
          </div>
        ))}
      </div>

      <p className="text-sm text-slate-600">
        <Link href="/decisions" className="font-medium text-[var(--aic-navy)] underline underline-offset-2">
          Go to Decisions →
        </Link>
      </p>
    </div>
  );
}
