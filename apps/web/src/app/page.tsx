import Link from "next/link";
import { HomeActions } from "@/components/home-actions";
import { HomeOverview } from "@/components/home-overview";
import { DemoPersonas } from "@/components/demo-personas";
import { HomeArchitecture } from "@/components/home-architecture";

export default function HomePage() {
  return (
    <div className="space-y-8">
      <HomeArchitecture />
      <section className="aic-hero relative overflow-hidden rounded-[28px] px-6 py-6 text-white shadow-[0_12px_35px_rgba(11,31,58,0.12)] sm:px-8">
        <div className="pointer-events-none absolute -right-24 -top-32 h-96 w-96 rounded-full border border-white/10" />
        <div className="relative flex flex-wrap items-center justify-between gap-5">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-teal-200">
              AI-cio / Your personal financial companion
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-[-.035em] sm:text-3xl">
              Your finances, <span className="text-[#b5e5d6]">working as one.</span>
            </h2>
            <p className="mt-2 text-xs leading-6 text-slate-300">
              See how your financial Twin and specialist agents build a decision together.
            </p>
          </div>
          <HomeActions compact />
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
