"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@ai-cio/utils";

const NAV_ITEMS = [
  { href: "/", label: "Home", exact: true },
  { href: "/onboarding/welcome", label: "Onboarding", exact: false },
  { href: "/onboarding/twin", label: "Profile", exact: false },
  { href: "/decisions", label: "Decisions", exact: false },
  { href: "/fire", label: "FIRE", exact: false },
  { href: "/mutual-funds", label: "Mutual funds", exact: false },
  { href: "/tax", label: "Tax", exact: false },
  { href: "/fd", label: "FDs", exact: false },
  { href: "/news", label: "News", exact: false },
] as const;

export function SiteNav() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-wrap items-center gap-1 rounded-full border border-[rgba(15,55,110,0.12)] bg-white/45 p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)] backdrop-blur-md">
      {NAV_ITEMS.map((item) => {
        const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "rounded-full px-3.5 py-1.5 text-sm font-medium transition-all",
              active
                ? "bg-[var(--aic-navy)] text-white shadow-sm"
                : "text-slate-600 hover:bg-white/80 hover:text-[var(--aic-navy)]",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
