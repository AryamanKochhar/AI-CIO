import Link from "next/link";
import { Card } from "@ai-cio/ui";
import { HomeActions } from "@/components/home-actions";

export default function HomePage() {
  return (
    <div className="space-y-8">
      <section className="aic-hero rounded-3xl px-8 py-14 text-white shadow-xl md:px-12">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">AI-CIO</p>
        <h1 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">
          Understand your finances.<br />Make better financial decisions.
        </h1>
        <p className="mt-4 max-w-xl text-sm leading-relaxed text-slate-300">
          AI-CIO brings your financial information, goals, and investment behaviour together in one place —
          so you can see a complete picture before anything is recommended.
        </p>
        <HomeActions />
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        {[
          ["Understand how you decide", "A short behavioural assessment — scored securely on our servers, never in your browser."],
          ["Tell us about your finances", "Income, expenses, savings, and goals at your pace. Blank means unknown, not zero."],
          ["Explore decisions", "Review your context, pick a goal, and see structured allocation ideas — not buy/sell orders."],
        ].map(([title, body]) => (
          <Card key={title} className="aic-card-glow">
            <h2 className="text-base font-semibold text-slate-900">{title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">{body}</p>
          </Card>
        ))}
      </div>

      <Card className="aic-card-glow">
        <h2 className="text-base font-semibold text-slate-900">Signed in?</h2>
        <p className="mt-2 text-sm text-slate-600">
          Use the <strong>Decisions</strong> tab in the top navigation to run the orchestrator on your profile.
        </p>
        <p className="mt-2 text-sm text-slate-600">
          <Link href="/decisions" className="font-medium text-slate-900 underline underline-offset-2">
            Go to Decisions →
          </Link>
        </p>
      </Card>
    </div>
  );
}
