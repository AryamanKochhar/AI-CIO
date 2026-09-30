"use client";

import type { ReactNode } from "react";
import type { CounterfactualScenario, CounterfactualsPayload } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { Expandable } from "@/components/design/system";
import { AiTag } from "@/components/design/ai-tag";

function fmt(value: unknown): string {
  if (value == null || value === "") return "—";
  if (typeof value === "number" || /^-?\d+(\.\d+)?$/.test(String(value))) {
    try {
      return formatCurrency(value as string | number);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function RuleTag() {
  return (
    <span className="inline-flex shrink-0 items-center rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
      Rules
    </span>
  );
}

/** Only the metrics that usually matter — skip empty noise. */
function keyMetrics(row: Record<string, unknown>): Array<{ label: string; value: unknown }> {
  const pairs: Array<[string, unknown]> = [
    ["Largest holding", row.largest_holding_percent != null ? `${row.largest_holding_percent}%` : null],
    ["Portfolio", row.portfolio_value],
    ["Cash freed", row.cash_freed],
    ["Amount shifted", row.amount_shifted],
    ["Liquid", row.liquid],
    ["Months cover", row.months_cover],
    ["Monthly SIP", row.monthly_contribution],
    ["Projected", row.projected_value],
    ["Δ vs base", row.delta_vs_base],
    ["Δ vs actual", row.delta_vs_actual_end],
    ["Return", row.annual_return_percent != null ? `${row.annual_return_percent}%` : null],
    ["Unrealized loss", row.unrealized_loss],
    ["Tax impact", row.estimated_tax_impact ?? row.illustrative_tax_impact],
    ["Start", row.start_value],
    ["End", row.end_value],
  ];
  return pairs
    .filter(([, v]) => v != null && v !== "")
    .slice(0, 5)
    .map(([label, value]) => ({ label, value }));
}

function Side({
  label,
  row,
}: {
  label: string;
  row: Record<string, unknown>;
}) {
  const metrics = keyMetrics(row);
  return (
    <div className="rounded-lg border border-[rgba(15,55,110,0.1)] bg-white/50 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-700">{label}</p>
        <RuleTag />
      </div>
      <div className="mt-2 space-y-1">
        {metrics.map((m) => (
          <div key={m.label} className="flex justify-between gap-3 text-sm">
            <span className="text-slate-600">{m.label}</span>
            <span className="font-medium tabular-nums text-slate-900">
              {typeof m.value === "string" && (m.value.includes("%") || m.label === "Months cover")
                ? String(m.value)
                : fmt(m.value)}
            </span>
          </div>
        ))}
      </div>
      {typeof row.summary === "string" && row.summary ? (
        <p className="mt-2 text-xs leading-relaxed text-slate-600">{row.summary}</p>
      ) : null}
    </div>
  );
}

function AiBlock({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-indigo-200/70 bg-indigo-50/40 p-4">
      <div className="flex items-center gap-2">
        <AiTag />
        <p className="text-[11px] font-semibold uppercase tracking-wide text-indigo-900">{title}</p>
      </div>
      <div className="mt-2 space-y-1.5 text-sm leading-relaxed text-slate-800">{children}</div>
    </div>
  );
}

function ScenarioCard({ scenario }: { scenario: CounterfactualScenario }) {
  const actual = scenario.actual || {};
  const alt = (scenario.alternatives || [])[0] || {};

  return (
    <div className="rounded-xl border border-[rgba(15,55,110,0.1)] bg-white/45 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-900">
            {scenario.ai_priority_rank != null ? `${scenario.ai_priority_rank}. ` : ""}
            {scenario.title}
          </p>
        </div>
        <RuleTag />
      </div>

      {(scenario.ai_explanation || scenario.ai_why_it_matters) && (
        <div className="mt-3 rounded-lg border border-indigo-200/70 bg-indigo-50/50 p-3">
          <div className="flex items-center gap-2">
            <AiTag />
            <p className="text-[10px] font-semibold uppercase tracking-wide text-indigo-900">Explanation</p>
          </div>
          {scenario.ai_why_it_matters ? (
            <p className="mt-1 text-xs font-medium text-slate-800">{scenario.ai_why_it_matters}</p>
          ) : null}
          {scenario.ai_explanation ? (
            <p className="mt-1 text-xs leading-relaxed text-slate-600">{scenario.ai_explanation}</p>
          ) : null}
        </div>
      )}

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Side label={String(actual.label || "Current")} row={actual} />
        <Side label={String(alt.label || "Alternative")} row={alt} />
      </div>
    </div>
  );
}

function AiSynthesis({ data }: { data: CounterfactualsPayload }) {
  if (!data.ai?.used) {
    if (data.ai?.error || data.ai?.reason) {
      return <p className="text-xs text-slate-500">{data.ai.error || data.ai.reason}</p>;
    }
    return null;
  }
  return (
    <AiBlock title="Synthesis">
      {data.ai.cio_narrative ? <p>{data.ai.cio_narrative}</p> : null}
      {data.ai.priority_focus ? (
        <p>
          <span className="font-medium text-slate-700">Focus: </span>
          {data.ai.priority_focus}
        </p>
      ) : null}
      {data.ai.tradeoff_insight ? (
        <p>
          <span className="font-medium text-slate-700">Trade-off: </span>
          {data.ai.tradeoff_insight}
        </p>
      ) : null}
      {data.ai.suggested_next_review ? (
        <p>
          <span className="font-medium text-slate-700">Next review: </span>
          {data.ai.suggested_next_review}
        </p>
      ) : null}
    </AiBlock>
  );
}

export function CounterfactualsExpandable({
  data,
  defaultOpen = false,
}: {
  data?: CounterfactualsPayload | null;
  defaultOpen?: boolean;
}) {
  if (!data?.available || !data.scenarios?.length) {
    return (
      <Expandable title="What if?" defaultOpen={defaultOpen}>
        <p className="text-sm text-slate-600">Not enough data for scenarios yet.</p>
      </Expandable>
    );
  }

  return (
    <Expandable title="What if?" defaultOpen={defaultOpen}>
      <div className="mb-4">
        <AiSynthesis data={data} />
      </div>
      <div className="space-y-3">
        {data.scenarios.map((s) => (
          <ScenarioCard key={s.id} scenario={s} />
        ))}
      </div>
    </Expandable>
  );
}

export function CounterfactualsPanel({ data }: { data?: CounterfactualsPayload | null }) {
  if (!data?.available || !data.scenarios?.length) {
    return (
      <section className="aic-glass rounded-2xl p-5 sm:p-6">
        <h2 className="aic-section-title">What if?</h2>
        <p className="mt-2 text-sm text-slate-600">
          Not enough Twin / tax / trajectory data yet. Complete portfolio and finances, then refresh.
        </p>
      </section>
    );
  }

  return (
    <section className="aic-glass-strong rounded-2xl p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="aic-section-title">What if you had done X?</h2>
        {data.ai?.used ? <AiTag /> : <RuleTag />}
      </div>
      <p className="mt-2 text-sm text-slate-600">
        Numbers from rules · narrative tagged <span className="font-medium text-indigo-800">AI</span> when
        available.
      </p>

      <div className="mt-4">
        <AiSynthesis data={data} />
      </div>

      <div className="mt-5 space-y-3">
        {data.scenarios.map((s) => (
          <ScenarioCard key={s.id} scenario={s} />
        ))}
      </div>
    </section>
  );
}
