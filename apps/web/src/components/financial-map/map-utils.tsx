"use client";

import type { FinancialMapNode } from "@ai-cio/contracts";
import { SensitiveValue } from "@ai-cio/ui";
import { formatCurrency } from "@ai-cio/utils";
import { cn } from "@ai-cio/utils";

export { ancestorsOf, childrenOf, filterNodes, nodeById, searchMap } from "./map-model";

const ICONS: Record<string, string> = {
  life: "◎",
  cash: "₹",
  income: "↑",
  expense: "↓",
  investments: "◈",
  equity: "▣",
  mutual_fund: "◉",
  cluster: "⋯",
  goals: "◎",
  goal: "◎",
  liability: "▣",
  liabilities: "▣",
};

export function nodeIcon(node: FinancialMapNode): string {
  return ICONS[node.icon || node.type] || "•";
}

export function NodeBadge({
  node,
  active,
  dimmed,
  onSelect,
  onDrill,
}: {
  node: FinancialMapNode;
  active?: boolean;
  dimmed?: boolean;
  onSelect: (id: string) => void;
  onDrill?: (id: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(node.id)}
      onDoubleClick={() => onDrill?.(node.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" && onDrill && node.child_ids.length > 0) {
          e.preventDefault();
          onDrill(node.id);
        }
      }}
      aria-pressed={active}
      aria-label={`${node.label}${node.value ? `, ${formatCurrency(node.value)}` : ""}${node.child_ids.length ? ". Press Enter to explore." : ""}`}
      className={cn(
        "group relative flex min-w-[9.5rem] max-w-[14rem] flex-col items-start rounded-2xl border px-4 py-3 text-left transition duration-200",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400",
        active
          ? "border-slate-900 bg-slate-900 text-white shadow-lg"
          : node.available
            ? "border-slate-200 bg-white text-slate-900 hover:border-slate-400 hover:shadow-md"
            : "border-dashed border-slate-200 bg-slate-50 text-slate-500",
        dimmed && !active && "opacity-40",
      )}
    >
      <span className={cn("mb-1 text-xs", active ? "text-slate-300" : "text-slate-500")}>
        {nodeIcon(node)} {node.type.replace("_", " ")}
      </span>
      <span className="text-sm font-semibold leading-snug">{node.label}</span>
      {node.subtitle ? (
        <span className={cn("mt-0.5 line-clamp-2 text-xs", active ? "text-slate-300" : "text-slate-500")}>
          {node.subtitle}
        </span>
      ) : null}
      {node.value ? (
        <span className={cn("mt-2 text-sm font-medium", active ? "text-white" : "text-slate-800")}>
          <SensitiveValue value={formatCurrency(node.value)} />
        </span>
      ) : null}
      {node.child_ids.length > 0 ? (
        <span className={cn("mt-2 text-[10px] uppercase tracking-wide", active ? "text-slate-400" : "text-slate-400")}>
          {node.child_ids.length} connected · Enter to open
        </span>
      ) : null}
    </button>
  );
}
