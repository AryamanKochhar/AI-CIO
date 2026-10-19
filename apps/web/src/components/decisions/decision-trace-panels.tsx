"use client";

import type {
  AgentPerspective,
  AgentPerspectives,
  BehavioralIntelligence,
  DataQualityReport,
  DecisionTrace,
  TemporalChanges,
} from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { Expandable, GlassPanel, SectionHeader, SurfacePanel } from "@/components/design/system";

function formatMaybeMoney(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  if (typeof value === "number" || /^-?\d+(\.\d+)?$/.test(String(value))) {
    try {
      return formatCurrency(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function AgentCard({ agent }: { agent: AgentPerspective }) {
  const notEval = agent.status === "not_evaluated" || agent.finding === "Not evaluated";
  return (
    <div className="aic-surface rounded-xl p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--aic-blue-muted)]">
            {agent.label}
          </p>
          <p className="mt-1 text-sm font-medium text-slate-900">
            {notEval ? "Not evaluated" : agent.finding}
          </p>
        </div>
        <span className="shrink-0 rounded-md border border-[rgba(15,55,110,0.12)] bg-white/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
          {agent.status === "available" ? agent.confidence || "available" : agent.status.replace(/_/g, " ")}
        </span>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-slate-600">
        <span className="font-medium text-slate-700">Recommendation: </span>
        {agent.recommendation || "Not evaluated"}
      </p>
      {agent.detail && agent.detail !== "Not evaluated" ? (
        <p className="mt-2 text-xs leading-relaxed text-slate-500">{agent.detail}</p>
      ) : null}
      {agent.conflicts_with && agent.conflicts_with.length > 0 ? (
        <p className="mt-2 text-[11px] text-amber-800">
          Conflicts with: {agent.conflicts_with.join(", ")}
        </p>
      ) : null}
      {agent.evidence_ref ? <a href={agent.evidence_ref} className="mt-3 inline-block text-[11px] font-semibold text-teal-800 underline underline-offset-4">Inspect this check’s facts, calculation & skill citation ↑</a> : null}
    </div>
  );
}

export function AgentPerspectivesPanel({ data }: { data?: AgentPerspectives | null }) {
  if (!data?.available || !data.agents?.length) return null;
  const synthesis = data.cio_synthesis;
  const key = data.key_disagreement;

  return (
    <GlassPanel>
      <SectionHeader
        eyebrow="Specialists"
        title={data.explanation_version ? "Distinct specialist checks" : "Agent perspectives"}
        description={data.explanation_version ? "Each lens answers a different question using the same audited findings. These are not independent votes; agreement or disagreement is not manufactured." : "Structured outputs from participating agents. Missing specialists show as Not evaluated — nothing is invented."}
      />
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {data.agents.map((agent) => (
          <AgentCard key={agent.agent} agent={agent} />
        ))}
      </div>

      {key ? (
        <div className="mt-5 rounded-xl border border-amber-200/80 bg-amber-50/70 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-900">
            Key disagreement
          </p>
          <p className="mt-1 text-sm font-medium text-slate-900">{key.title}</p>
          <p className="mt-1 text-sm leading-relaxed text-slate-700">{key.summary}</p>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-700">
            {key.portfolio_stance ? (
              <span>
                Portfolio: <strong>{key.portfolio_stance}</strong>
              </span>
            ) : null}
            {key.tax_stance ? (
              <span>
                Tax: <strong>{key.tax_stance}</strong>
              </span>
            ) : null}
          </div>
        </div>
      ) : null}

      {synthesis && !data.explanation_version ? (
        <div className="mt-4 rounded-xl border border-[rgba(15,55,110,0.12)] bg-white/50 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--aic-blue-muted)]">
            CIO synthesis
          </p>
          <p className="mt-1 text-sm leading-relaxed text-slate-800">{synthesis.conclusion}</p>
          {synthesis.agreement ? (
            <p className="mt-2 text-xs text-slate-500">
              Agreement: {synthesis.agreement}
              {synthesis.primary_conflict ? ` · Conflict: ${synthesis.primary_conflict}` : ""}
            </p>
          ) : null}
        </div>
      ) : null}
    </GlassPanel>
  );
}

export function TemporalChangesPanel({ data }: { data?: TemporalChanges | null }) {
  if (!data) return null;
  if (!data.available) {
    return (
      <SurfacePanel>
        <SectionHeader
          eyebrow="History"
          title="What's changed?"
          description={data.reason || "Insufficient historical Twin snapshots to describe changes."}
        />
      </SurfacePanel>
    );
  }

  return (
    <GlassPanel>
      <SectionHeader
        eyebrow="History"
        title="What's changed?"
        description="Derived only from Twin portfolio snapshots already on file — never fabricated."
      />
      <div className="mt-4 space-y-3">
        {(data.items || []).map((item, idx) => (
          <div
            key={`${item.metric}-${idx}`}
            className="rounded-xl border border-[rgba(15,55,110,0.1)] bg-white/45 p-4"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="text-sm font-medium text-slate-900">{item.metric}</p>
              <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Confidence: {item.confidence || "medium"}
              </span>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <div>
                <p className="aic-meta">Previous</p>
                <p className="mt-0.5 text-sm font-medium tabular-nums text-slate-800">
                  {formatMaybeMoney(item.previous_value)}
                </p>
              </div>
              <div>
                <p className="aic-meta">Current</p>
                <p className="mt-0.5 text-sm font-medium tabular-nums text-slate-800">
                  {formatMaybeMoney(item.current_value)}
                </p>
              </div>
              <div>
                <p className="aic-meta">Change</p>
                <p className="mt-0.5 text-sm font-medium tabular-nums text-slate-800">
                  {item.change_amount != null ? formatMaybeMoney(item.change_amount) : "—"}
                  {item.change_pct != null ? ` (${item.change_pct}%)` : ""}
                </p>
              </div>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Period: {item.period_from || "—"} → {item.period_to || "—"}
            </p>
            {(item.contributing_factors || []).length > 0 ? (
              <p className="mt-1 text-xs leading-relaxed text-slate-600">
                {(item.contributing_factors || []).join(" ")}
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}

export function BehavioralIntelligencePanel({ data }: { data?: BehavioralIntelligence | null }) {
  if (!data?.available) return null;
  const declared = data.declared;
  const observed = data.observed;

  return (
    <GlassPanel>
      <SectionHeader
        eyebrow="Behaviour"
        title="Observed investment behaviour"
        description="Declared questionnaire answers vs patterns visible in your portfolio and transactions — not a psychological diagnosis."
      />
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-[rgba(15,55,110,0.1)] bg-white/45 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--aic-blue-muted)]">
            Declared
          </p>
          <ul className="mt-3 space-y-3">
            {(declared?.items || []).map((item, i) => (
              <li key={`d-${i}`}>
                <p className="text-xs font-medium text-slate-800">{item.label}</p>
                <p className="mt-0.5 text-sm text-slate-700">{item.value}</p>
                {item.note ? <p className="mt-0.5 text-[11px] text-slate-500">{item.note}</p> : null}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-[rgba(15,55,110,0.1)] bg-white/45 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--aic-blue-muted)]">
            Observed
          </p>
          {observed?.behavior_score != null ? (
            <p className="mt-2 text-xs text-slate-500">
              Behavior score (transaction-derived): {observed.behavior_score}/100
            </p>
          ) : null}
          <ul className="mt-3 space-y-3">
            {(observed?.items || []).map((item, i) => (
              <li key={`o-${i}`}>
                <p className="text-xs font-medium text-slate-800">{item.label}</p>
                <p className="mt-0.5 text-sm text-slate-700">{item.value}</p>
                {item.note ? <p className="mt-0.5 text-[11px] text-slate-500">{item.note}</p> : null}
              </li>
            ))}
          </ul>
        </div>
      </div>
      {(data.divergences || []).length > 0 ? (
        <div className="mt-4 space-y-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-900">
            Divergence
          </p>
          {(data.divergences || []).map((d, i) => (
            <div key={i} className="rounded-xl border border-amber-200/80 bg-amber-50/70 p-4">
              <p className="text-sm font-medium text-slate-900">{d.title}</p>
              <p className="mt-1 text-sm leading-relaxed text-slate-700">{d.summary}</p>
              <p className="mt-2 text-[11px] text-slate-500">
                Confidence: {d.confidence || "low"}
                {d.causation_claimed ? "" : " · Causation not claimed"}
              </p>
            </div>
          ))}
        </div>
      ) : null}
      {data.disclaimer ? <p className="mt-4 text-xs leading-relaxed text-slate-500">{data.disclaimer}</p> : null}
    </GlassPanel>
  );
}

const DQ_STYLES: Record<string, string> = {
  verified: "text-teal-800 bg-teal-50/80 border-teal-200/70",
  incomplete: "text-amber-900 bg-amber-50/80 border-amber-200/70",
  conflicting: "text-orange-900 bg-orange-50/80 border-orange-200/70",
  stale: "text-slate-700 bg-slate-100/80 border-slate-200/80",
  unknown: "text-slate-600 bg-slate-50/90 border-slate-200/80",
};

export function DataQualityPanel({ data }: { data?: DataQualityReport | null }) {
  if (!data?.available) return null;
  const counts = data.counts || {};

  return (
    <SurfacePanel>
      <SectionHeader
        eyebrow="Reliability"
        title="Data quality"
        description="Completeness and conflict signals from Twin, tax lots, and trajectory — conflicts are shown, not overwritten."
      />
      {data.confidence_note ? (
        <p className="mt-3 text-sm font-medium text-slate-800">{data.confidence_note}</p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-semibold uppercase tracking-wide">
        {(["verified", "incomplete", "conflicting", "stale", "unknown"] as const).map((k) => (
          <span
            key={k}
            className={`rounded-md border px-2 py-0.5 ${DQ_STYLES[k] || DQ_STYLES.unknown}`}
          >
            {k}: {counts[k] ?? 0}
          </span>
        ))}
      </div>
      <Expandable title="Quality details" defaultOpen={false}>
        <ul className="space-y-2 text-sm text-slate-700">
          {(data.items || []).map((item, i) => (
            <li key={`${item.label}-${i}`} className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <span className="font-medium">{item.label}</span>
                {item.detail ? <span className="text-slate-600"> — {item.detail}</span> : null}
              </div>
              <span
                className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                  DQ_STYLES[item.status] || DQ_STYLES.unknown
                }`}
              >
                {item.status}
              </span>
            </li>
          ))}
        </ul>
      </Expandable>
      {data.disclaimer ? <p className="mt-2 text-xs text-slate-500">{data.disclaimer}</p> : null}
    </SurfacePanel>
  );
}

const TRACE_STEPS: Array<{ key: keyof NonNullable<DecisionTrace["steps"]>; label: string }> = [
  { key: "inputs", label: "1. Inputs" },
  { key: "observations", label: "2. Observations" },
  { key: "calculations", label: "3. Calculations / rules" },
  { key: "specialist_findings", label: "4. Specialist findings" },
  { key: "conflicts", label: "5. Conflicts / trade-offs" },
  { key: "cio_synthesis", label: "6. CIO synthesis" },
  { key: "final_finding", label: "7. Final finding" },
];

export function DecisionTracePanel({ data }: { data?: DecisionTrace | null }) {
  if (!data?.available || !data.steps) return null;
  const steps = data.steps;
  const freshness = data.data_freshness;

  return (
    <SurfacePanel>
      <SectionHeader
        eyebrow="Explainability"
        title="How this decision was formed"
        description="Observable Decision Trace from structured pipeline outputs — not private model chain-of-thought."
      />
      {freshness?.updated_at ? (
        <p className="mt-2 text-xs text-slate-500">
          Updated: {new Date(freshness.updated_at).toLocaleString()}
          {freshness.analyzer ? ` · Analyzer: ${freshness.analyzer}` : ""}
          {freshness.duration_ms != null ? ` · ${freshness.duration_ms}ms` : ""}
        </p>
      ) : null}

      <div className="mt-4 space-y-2">
        {TRACE_STEPS.map(({ key, label }) => {
          const content = steps[key];
          if (content == null) return null;

          if (key === "inputs" && Array.isArray(content)) {
            return (
              <Expandable key={key} title={label} defaultOpen={false}>
                {(content as NonNullable<DecisionTrace["steps"]>["inputs"])!.length === 0 ? (
                  <p className="text-sm text-slate-500">No structured inputs captured.</p>
                ) : (
                  <ul className="space-y-2 text-sm text-slate-700">
                    {(content as NonNullable<DecisionTrace["steps"]>["inputs"])!.map((row, i) => (
                      <li key={`${row.label}-${i}`} className="flex flex-wrap justify-between gap-2">
                        <span>{row.label}</span>
                        <span className="font-medium tabular-nums">
                          {typeof row.value === "number" ||
                          (typeof row.value === "string" && /^-?\d+(\.\d+)?$/.test(row.value))
                            ? formatMaybeMoney(row.value)
                            : row.value ?? "—"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Expandable>
            );
          }

          if (key === "observations" && Array.isArray(content)) {
            return (
              <Expandable key={key} title={label} defaultOpen>
                <ul className="space-y-2 text-sm text-slate-700">
                  {(content as NonNullable<DecisionTrace["steps"]>["observations"])!.map((row, i) => (
                    <li key={`${row.title}-${i}`}>
                      <span className="font-medium">{row.title || "Observation"}</span>
                      {row.detail ? <span className="text-slate-600"> — {row.detail}</span> : null}
                    </li>
                  ))}
                </ul>
              </Expandable>
            );
          }

          if (key === "calculations" && Array.isArray(content)) {
            return (
              <Expandable key={key} title={label}>
                <ul className="list-disc space-y-1 pl-4 text-sm text-slate-700">
                  {(content as NonNullable<DecisionTrace["steps"]>["calculations"])!.map((row, i) => (
                    <li key={i}>{row.rule}</li>
                  ))}
                </ul>
              </Expandable>
            );
          }

          if (key === "specialist_findings" && Array.isArray(content)) {
            return (
              <Expandable key={key} title={label}>
                <ul className="space-y-2 text-sm text-slate-700">
                  {(content as AgentPerspective[]).map((a) => (
                    <li key={a.agent}>
                      <span className="font-medium">{a.label}: </span>
                      {a.status === "not_evaluated" ? "Not evaluated" : a.finding}
                    </li>
                  ))}
                </ul>
              </Expandable>
            );
          }

          if (key === "conflicts" && Array.isArray(content)) {
            const list = content as NonNullable<DecisionTrace["steps"]>["conflicts"];
            return (
              <Expandable key={key} title={label} defaultOpen={(list?.length || 0) > 0}>
                {!list?.length ? (
                  <p className="text-sm text-slate-500">No structured conflicts detected.</p>
                ) : (
                  <ul className="space-y-2 text-sm text-slate-700">
                    {list.map((c, i) => (
                      <li key={i}>
                        <span className="font-medium">{c.title}: </span>
                        {c.summary}
                      </li>
                    ))}
                  </ul>
                )}
              </Expandable>
            );
          }

          if (key === "cio_synthesis" && content && typeof content === "object" && !Array.isArray(content)) {
            const syn = content as NonNullable<DecisionTrace["steps"]>["cio_synthesis"];
            return (
              <Expandable key={key} title={label} defaultOpen>
                <p className="text-sm leading-relaxed text-slate-800">{syn?.conclusion}</p>
                {syn?.note ? <p className="mt-2 text-xs text-slate-500">{syn.note}</p> : null}
              </Expandable>
            );
          }

          if (key === "final_finding" && content && typeof content === "object" && !Array.isArray(content)) {
            const fin = content as NonNullable<DecisionTrace["steps"]>["final_finding"];
            return (
              <Expandable key={key} title={label} defaultOpen>
                <p className="text-sm font-medium text-slate-900">{fin?.decision}</p>
                <p className="mt-1 text-xs text-slate-500">Confidence: {fin?.confidence || data.confidence}</p>
                {(fin?.recommended_actions || []).length > 0 ? (
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-slate-700">
                    {fin!.recommended_actions!.map((a, i) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ul>
                ) : null}
              </Expandable>
            );
          }

          return null;
        })}
      </div>
      {data.disclaimer ? <p className="mt-4 text-xs leading-relaxed text-slate-500">{data.disclaimer}</p> : null}
    </SurfacePanel>
  );
}
