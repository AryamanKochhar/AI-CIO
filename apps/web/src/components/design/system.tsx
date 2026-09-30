"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import { cn } from "@ai-cio/utils";

export type Severity = "high" | "watch" | "opportunity" | "information" | "medium";

const SEVERITY_STYLES: Record<Severity, string> = {
  high: "text-[var(--aic-high)] bg-orange-50/80 border-orange-200/70",
  watch: "text-[var(--aic-watch)] bg-amber-50/80 border-amber-200/70",
  medium: "text-[var(--aic-watch)] bg-amber-50/80 border-amber-200/70",
  opportunity: "text-[var(--aic-opportunity)] bg-teal-50/80 border-teal-200/70",
  information: "text-[var(--aic-info)] bg-slate-50/90 border-slate-200/80",
};

const SEVERITY_LABEL: Record<Severity, string> = {
  high: "HIGH ATTENTION",
  watch: "WATCH",
  medium: "WATCH",
  opportunity: "OPPORTUNITY",
  information: "INFORMATION",
};

export function GlassPanel({
  children,
  className,
  strong = false,
}: {
  children: ReactNode;
  className?: string;
  strong?: boolean;
}) {
  return (
    <section className={cn(strong ? "aic-glass-strong" : "aic-glass", "rounded-2xl p-5 sm:p-6", className)}>
      {children}
    </section>
  );
}

export function SurfacePanel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={cn("aic-surface rounded-2xl p-5 sm:p-6", className)}>{children}</section>;
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0 max-w-3xl">
        {eyebrow ? (
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--aic-blue-muted)]">
            {eyebrow}
          </p>
        ) : null}
        <h2 className={cn("aic-section-title", eyebrow ? "mt-1.5" : "")}>{title}</h2>
        {description ? <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const key = severity in SEVERITY_STYLES ? severity : "information";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold tracking-[0.08em]",
        SEVERITY_STYLES[key as Severity],
      )}
    >
      {SEVERITY_LABEL[key as Severity]}
    </span>
  );
}

export function InsightRow({
  index,
  title,
  detail,
  severity,
  metric,
}: {
  index?: number;
  title: string;
  detail?: string;
  severity?: Severity;
  metric?: string | null;
}) {
  return (
    <div className="flex gap-3 border-b border-[rgba(15,55,110,0.08)] py-3.5 last:border-b-0 sm:gap-4">
      {index != null ? (
        <span className="aic-meta mt-0.5 w-7 shrink-0 font-semibold tabular-nums text-[var(--aic-blue-muted)]">
          {String(index).padStart(2, "0")}
        </span>
      ) : null}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          {severity ? <SeverityBadge severity={severity} /> : null}
          <p className="aic-finding">{title}</p>
        </div>
        {detail ? <p className="mt-1 text-sm leading-relaxed text-slate-600">{detail}</p> : null}
        {metric ? <p className="mt-1 text-sm font-medium tabular-nums text-slate-800">{metric}</p> : null}
      </div>
    </div>
  );
}

export function MetricTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
}) {
  return (
    <div className="min-w-0">
      <p className="aic-meta uppercase tracking-[0.08em]">{label}</p>
      <p className="aic-num mt-1 text-2xl font-semibold text-[var(--aic-navy)] sm:text-3xl">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

export function ProgressMetric({
  label,
  score,
  max = 100,
  note,
}: {
  label: string;
  score?: number | null;
  max?: number;
  note?: string;
}) {
  const pct = score == null ? 0 : Math.max(0, Math.min(100, (score / max) * 100));
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-medium text-slate-800">{label}</p>
        <p className="aic-num text-sm font-semibold text-slate-900">
          {score != null ? score : "—"}
          <span className="font-normal text-slate-400">/{max}</span>
        </p>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200/70">
        <div
          className="h-full rounded-full bg-[var(--aic-blue)]/80 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      {note ? <p className="mt-1 text-xs text-slate-500">{note}</p> : null}
    </div>
  );
}

export function Expandable({
  title,
  children,
  defaultOpen = false,
}: {
  title: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-t border-[rgba(15,55,110,0.08)]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 py-3.5 text-left text-sm font-medium text-slate-800 hover:text-[var(--aic-navy)]"
        aria-expanded={open}
      >
        <span className="inline-flex min-w-0 flex-wrap items-center gap-2">{title}</span>
        <span className="text-slate-400">{open ? "▾" : "▸"}</span>
      </button>
      {open ? <div className="pb-4">{children}</div> : null}
    </div>
  );
}
