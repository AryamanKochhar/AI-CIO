import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@ai-cio/utils";

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
  steps: Array<{ id: string; label: string }>;
  current: string;
}) {
  const currentIndex = steps.findIndex((s) => s.id === current);
  return (
    <ol className="flex flex-wrap gap-2">
      {steps.map((step, index) => {
        const active = index === currentIndex;
        const done = index < currentIndex;
        return (
          <li
            key={step.id}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium",
              active && "bg-slate-900 text-white",
              done && !active && "bg-slate-100 text-slate-600",
              !active && !done && "bg-slate-50 text-slate-400",
            )}
          >
            {step.label}
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
