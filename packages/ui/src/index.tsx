"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@ai-cio/utils";
import { SensitiveValue } from "./sensitive-reveal";

export {
  EyeIcon,
  PasswordInput,
  RevealToggle,
  SensitiveRevealProvider,
  SensitiveValue,
  useSensitiveReveal,
  useSensitiveRevealOptional,
} from "./sensitive-reveal";
export { TransactionTable, type TransactionRow } from "./transaction-table";

type ButtonVariant = "primary" | "secondary" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  children: ReactNode;
}

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-300 disabled:text-slate-500",
  secondary:
    "bg-white text-slate-900 border border-slate-200 hover:bg-slate-50 disabled:opacity-50",
  ghost: "bg-transparent text-slate-600 hover:bg-slate-100 disabled:opacity-50",
};

export function Button({
  variant = "primary",
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-lg px-4 py-2.5 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400",
        variants[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-2xl border border-slate-200 bg-white p-6 shadow-sm", className)}>
      {children}
    </div>
  );
}

export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200",
        className,
      )}
      {...props}
    />
  );
}

export function Label({
  children,
  htmlFor,
}: {
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-slate-700">
      {children}
    </label>
  );
}

export function ProgressBar({ value, label }: { value: number; label?: string }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="space-y-2">
      {label ? <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p> : null}
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-slate-800 transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function Stepper({
  steps,
  current,
}: {
  steps: Array<{ id: string; label: string; href?: string }>;
  current: string;
}) {
  const currentIndex = steps.findIndex((s) => s.id === current);
  return (
    <ol className="flex flex-wrap gap-2">
      {steps.map((step, index) => {
        const active = index === currentIndex;
        const done = index < currentIndex;
        const className = cn(
          "inline-flex rounded-full px-3 py-1 text-xs font-medium transition-colors",
          active && "bg-slate-900 text-white",
          done && !active && "bg-slate-100 text-slate-600 hover:bg-slate-200",
          !active && !done && "bg-slate-50 text-slate-500 hover:bg-slate-100 hover:text-slate-700",
          step.href && "cursor-pointer",
        );
        return (
          <li key={step.id}>
            {step.href ? (
              <a href={step.href} className={className} aria-current={active ? "step" : undefined}>
                {step.label}
              </a>
            ) : (
              <span className={className} aria-current={active ? "step" : undefined}>
                {step.label}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-10 text-center">
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      <p className="mt-2 text-sm text-slate-600">{description}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function StatusBadge({
  status,
  children,
}: {
  status: "known" | "unknown" | "pending" | "success" | "error";
  children: ReactNode;
}) {
  const styles = {
    known: "bg-emerald-50 text-emerald-800",
    unknown: "bg-slate-100 text-slate-600",
    pending: "bg-amber-50 text-amber-800",
    success: "bg-emerald-50 text-emerald-800",
    error: "bg-red-50 text-red-800",
  };
  return (
    <span className={cn("inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium", styles[status])}>
      {children}
    </span>
  );
}

export function PageHeader({
  kicker,
  title,
  description,
}: {
  kicker?: string;
  title: string;
  description?: string;
}) {
  return (
    <header className="mb-8 space-y-2">
      {kicker ? (
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">{kicker}</p>
      ) : null}
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">{title}</h1>
      {description ? <p className="max-w-2xl text-sm leading-relaxed text-slate-600">{description}</p> : null}
    </header>
  );
}

export function LoadingState({ message = "Loading…" }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white px-6 py-14 text-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-slate-800" />
      <p className="mt-4 text-sm text-slate-600">{message}</p>
    </div>
  );
}

export function ErrorState({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-red-100 bg-red-50 px-6 py-8 text-center">
      <h3 className="text-base font-semibold text-red-900">{title}</h3>
      <p className="mt-2 text-sm text-red-700">{message}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ProfileSection({
  title,
  source,
  children,
}: {
  title: string;
  source?: string | null;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        {source ? <span className="text-xs text-slate-500">Source: {source}</span> : null}
      </div>
      {children}
    </section>
  );
}

export function GoalCard({
  name,
  type,
  target,
  selected,
  onClick,
}: {
  name: string;
  type: string;
  target?: string | null;
  selected?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full rounded-xl border px-4 py-4 text-left transition",
        selected ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white hover:border-slate-300",
      )}
    >
      <p className="font-medium">{name}</p>
      <p className={cn("mt-1 text-sm", selected ? "text-slate-200" : "text-slate-600")}>
        {type}{target ? ` · ${target}` : ""}
      </p>
    </button>
  );
}

export function PortfolioTable({
  rows,
}: {
  rows: Array<{
    scheme_name: string;
    isin?: string | null;
    closing_units?: string;
    valuation: string;
    source?: string;
  }>;
}) {
  if (!rows.length) return null;
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Investment</th>
            <th className="px-4 py-3">ISIN</th>
            <th className="px-4 py-3">Units</th>
            <th className="px-4 py-3">Value</th>
            <th className="px-4 py-3">Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={`${row.scheme_name}-${i}`} className="border-t border-slate-100">
              <td className="px-4 py-3 font-medium text-slate-900">{row.scheme_name}</td>
              <td className="px-4 py-3 text-slate-600">{row.isin ?? "—"}</td>
              <td className="px-4 py-3 text-slate-600">
                <SensitiveValue value={row.closing_units ?? "—"} />
              </td>
              <td className="px-4 py-3 text-slate-900">
                <SensitiveValue value={row.valuation} prefix="₹" />
              </td>
              <td className="px-4 py-3 text-slate-600">{row.source ?? "CAS"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function FileUploadZone({
  label,
  hint,
  accept,
  disabled,
  onFile,
}: {
  label: string;
  hint?: string;
  accept?: string;
  disabled?: boolean;
  onFile: (file: File) => void;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-12 text-center transition",
        disabled ? "border-slate-200 bg-slate-50 opacity-60" : "border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-white",
      )}
    >
      <span className="text-sm font-medium text-slate-900">{label}</span>
      {hint ? <span className="mt-1 text-xs text-slate-500">{hint}</span> : null}
      <input
        type="file"
        accept={accept}
        disabled={disabled}
        className="mt-4 text-sm"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
        }}
      />
    </label>
  );
}

export function CompletenessRing({ value, label }: { value: number; label: string }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="flex items-center gap-4">
      <div
        className="relative flex h-16 w-16 items-center justify-center rounded-full"
        style={{ background: `conic-gradient(#0f172a ${pct}%, #e2e8f0 0)` }}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-sm font-semibold text-slate-900">
          {pct}%
        </div>
      </div>
      <div>
        <p className="text-sm font-medium text-slate-900">{label}</p>
        <p className="text-xs text-slate-500">Based on what you&apos;ve shared so far</p>
      </div>
    </div>
  );
}
