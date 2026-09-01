"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@ai-cio/utils";

const NAV_ITEMS = [
  { href: "/", label: "Home", exact: true },
  { href: "/decisions", label: "Decisions", exact: false },
  { href: "/onboarding/twin", label: "Profile", exact: false },
  { href: "/onboarding/welcome", label: "Onboarding", exact: false },
] as const;

export function SiteNav() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-wrap items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1">
      {NAV_ITEMS.map((item) => {
        const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              active
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:bg-white/70 hover:text-slate-900",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
