"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { cn } from "@ai-cio/utils";

type SensitiveRevealContextValue = {
  revealed: boolean;
  toggle: () => void;
};

const SensitiveRevealContext = createContext<SensitiveRevealContextValue | null>(null);

export function SensitiveRevealProvider({ children }: { children: ReactNode }) {
  const [revealed, setRevealed] = useState(false);
  return (
    <SensitiveRevealContext.Provider
      value={{ revealed, toggle: () => setRevealed((value) => !value) }}
    >
      {children}
    </SensitiveRevealContext.Provider>
  );
}

export function useSensitiveReveal() {
  const ctx = useContext(SensitiveRevealContext);
  if (!ctx) {
    throw new Error("useSensitiveReveal must be used within SensitiveRevealProvider");
  }
  return ctx;
}

export function useSensitiveRevealOptional() {
  return useContext(SensitiveRevealContext);
}

export function EyeIcon({ open, className }: { open: boolean; className?: string }) {
  if (open) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={cn("h-4 w-4", className)}
        aria-hidden
      >
        <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    );
  }
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("h-4 w-4", className)}
      aria-hidden
    >
      <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
      <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a18.34 18.34 0 0 1-2.09 3.09" />
      <path d="M6.61 6.61A18.34 18.34 0 0 0 2 12s3 7 10 7a10.43 10.43 0 0 0 5.08-1.27" />
      <line x1="2" x2="22" y1="2" y2="22" />
    </svg>
  );
}

export function RevealToggle({
  className,
  label = "Toggle sensitive values",
}: {
  className?: string;
  label?: string;
}) {
  const { revealed, toggle } = useSensitiveReveal();
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={revealed}
      aria-label={revealed ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
      title={revealed ? "Hide sensitive values" : "Show sensitive values"}
      className={cn(
        "inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50",
        className,
      )}
    >
      <EyeIcon open={revealed} />
      <span>{revealed ? "Hide" : "Show"}</span>
    </button>
  );
}

function maskDisplay(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "" || value === "—") return "—";
  return "••••••";
}

export function SensitiveValue({
  value,
  className,
  prefix,
}: {
  value: string | null | undefined;
  className?: string;
  prefix?: string;
}) {
  const ctx = useSensitiveRevealOptional();
  const display = value === null || value === undefined || value === "" ? "—" : `${prefix ?? ""}${value}`;
  const hidden = ctx ? !ctx.revealed : false;
  return (
    <span className={cn(hidden && "tracking-widest text-slate-500", className)}>
      {hidden ? maskDisplay(display) : display}
    </span>
  );
}

export function PasswordInput({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        {...props}
        type={visible ? "text" : "password"}
        className={cn(
          "w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 pr-10 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200",
          className,
        )}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
      >
        <EyeIcon open={visible} />
      </button>
    </div>
  );
}
