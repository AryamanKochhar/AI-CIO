import Link from "next/link";
import { HomeActions } from "@/components/home-actions";
import { HomeOverview } from "@/components/home-overview";
import { DemoPersonas } from "@/components/demo-personas";
import { CompanionPreview } from "@/components/twin-mascot";

export default function HomePage() {
  return (
    <div className="space-y-8">
      <section className="aic-hero relative overflow-hidden rounded-[32px] px-7 py-9 text-white shadow-[0_20px_50px_rgba(11,31,58,0.18)] md:px-12 md:py-10">
        <div className="pointer-events-none absolute -right-24 -top-32 h-96 w-96 rounded-full border border-white/10" />
        <div className="grid items-center gap-5 md:grid-cols-[1.25fr_1fr]">
          <div className="relative py-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-teal-200">
              Your personal financial companion
            </p>
            <h1 className="mt-5 text-4xl font-semibold leading-[1.13] tracking-[-.045em] md:text-[48px]">
              A little more clarity.
              <br />
              <span className="text-[#b5e5d6]">A lot more you.</span>
            </h1>
            <p className="mt-5 max-w-md text-sm leading-7 text-slate-300">
              Connect your everyday money, goals and investments. Build a
              financial twin that grows with you, then find a clear next step.
            </p>
            <HomeActions />
            <div className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-[11px] text-slate-300">
              <span>✓ Explore with a demo persona</span>
              <span>✓ See the reasoning behind every suggestion</span>
            </div>
          </div>
          <CompanionPreview dark />
        </div>
      </section>

      <HomeOverview />
      <DemoPersonas />

      <div className="grid gap-6 md:grid-cols-3">
        {[
          [
            "01 / Start with your story",
            "A short assessment connects how you think with what matters to you.",
          ],
          [
            "02 / Bring the picture together",
            "Add finances, goals and investments at your pace. Unknown stays unknown.",
          ],
          [
            "03 / Decide with context",
            "Compare ranked suggestions, check the evidence and explore alternatives.",
          ],
        ].map(([title, body]) => (
          <div
            key={title}
            className="border-t border-[rgba(15,55,110,0.12)] pt-4"
          >
            <h2 className="text-base font-semibold text-[var(--aic-navy)]">
              {title}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              {body}
            </p>
          </div>
        ))}
      </div>

      <p className="text-sm text-slate-600">
        <Link
          href="/decisions"
          className="font-medium text-[var(--aic-navy)] underline underline-offset-2"
        >
          Go to Decisions →
        </Link>
      </p>
    </div>
  );
}
