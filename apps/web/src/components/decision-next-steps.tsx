"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const STEPS = [
  [
    "/onboarding/twin",
    "Your picture",
    "Confirm the facts in your financial twin.",
  ],
  [
    "/decisions",
    "Your next decision",
    "Compare priorities and understand the reasoning.",
  ],
  ["/tax", "The implications", "Check the tax context before making changes."],
  ["/fd", "Near-term needs", "Connect deposits and cash with upcoming plans."],
] as const;

export function DecisionNextSteps() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Financial decision flow"
      className="decision-flow rounded-2xl border border-slate-200 bg-white p-2"
    >
      <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map(([href, title, detail], index) => (
          <Link
            key={href}
            href={href}
            aria-current={pathname === href ? "page" : undefined}
            className={`decision-flow-step ${pathname === href ? "is-active" : ""}`}
          >
            <span className="mb-3 flex items-center justify-between">
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-semibold ${pathname === href ? "bg-teal-700 text-white" : "bg-slate-100 text-slate-500"}`}
              >
                {index + 1}
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-teal-700">
                {pathname === href ? "You are here" : "Explore ↗"}
              </span>
            </span>
            <span className="block text-sm font-semibold text-slate-800">
              {title}
            </span>
            <span className="mt-1.5 block text-xs leading-5 text-slate-500">
              {detail}
            </span>
          </Link>
        ))}
      </div>
    </nav>
  );
}
