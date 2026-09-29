"use client";

import { useMemo, useState } from "react";
import { Button, Card, StatusBadge } from "@ai-cio/ui";
import type { TrajectoryIntelligence } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";

const SCENARIO_COLORS: Record<string, string> = {
  conservative: "#64748b",
  base: "#0f766e",
  optimistic: "#b45309",
};

function num(v: string | null | undefined): number {
  if (v == null || v === "") return 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function moneyOrDash(v: string | null | undefined): string {
  if (v == null || v === "") return "—";
  try {
    return formatCurrency(v);
  } catch {
    return String(v);
  }
}

function WealthChart({
  series,
  goals,
  horizon,
}: {
  series: NonNullable<NonNullable<TrajectoryIntelligence["projections"]>["series"]>;
  goals: NonNullable<TrajectoryIntelligence["goal_projections"]>;
  horizon: number;
}) {
  const [hoverYear, setHoverYear] = useState<number | null>(null);
  const width = 640;
  const height = 270;
  const pad = { t: 16, r: 28, b: 40, l: 56 };

  const points = useMemo(() => {
    const names = Object.keys(series || {});
    let maxY = 1;
    for (const name of names) {
      for (const p of series[name] || []) {
        if (p.year <= horizon) maxY = Math.max(maxY, num(p.value));
      }
    }
    for (const g of goals || []) {
      maxY = Math.max(maxY, num(g.target_amount));
    }
    const plotW = width - pad.l - pad.r;
    const plotH = height - pad.t - pad.b;
    const x = (year: number) => pad.l + (year / Math.max(1, horizon)) * plotW;
    const y = (v: number) => pad.t + plotH - (v / maxY) * plotH;
    return { names, maxY, x, y, plotW, plotH };
    // pad is a stable module-level-ish constant object on each render of this component
    // eslint-disable-next-line react-hooks/exhaustive-deps -- pad.* are fixed chart margins
  }, [series, goals, horizon]);

  const hoverVals =
    hoverYear == null
      ? null
      : Object.fromEntries(
          Object.entries(series || {}).map(([name, path]) => {
            const pt = (path || []).find((p) => p.year === hoverYear);
            return [name, pt];
          }),
        );

  return (
    <div className="relative w-full overflow-x-auto rounded-lg border border-slate-100 bg-white px-2 py-3 sm:px-3">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full min-w-[320px] overflow-visible" role="img">
        <title>Projected wealth scenarios</title>
        {[0, 0.25, 0.5, 0.75, 1].map((f) => {
          const yy = pad.t + points.plotH * (1 - f);
          const label = points.maxY * f;
          return (
            <g key={f}>
              <line x1={pad.l} x2={width - pad.r} y1={yy} y2={yy} stroke="#e2e8f0" strokeWidth={1} />
              <text x={pad.l - 8} y={yy + 4} textAnchor="end" fontSize={10} fill="#64748b">
                {label >= 1e7
                  ? `₹${(label / 1e7).toFixed(1)}Cr`
                  : label >= 1e5
                    ? `₹${(label / 1e5).toFixed(1)}L`
                    : `₹${Math.round(label / 1000)}k`}
              </text>
            </g>
          );
        })}
        {points.names.map((name) => {
          const path = (series[name] || []).filter((p) => p.year <= horizon);
          if (path.length < 2) return null;
          const d = path
            .map((p, i) => `${i === 0 ? "M" : "L"} ${points.x(p.year)} ${points.y(num(p.value))}`)
            .join(" ");
          return (
            <path
              key={name}
              d={d}
              fill="none"
              stroke={SCENARIO_COLORS[name] || "#334155"}
              strokeWidth={2.25}
              strokeLinejoin="round"
            />
          );
        })}
        {(goals || []).map((g) => {
          const yr = Math.min(horizon, Math.max(0, Number(g.years_remaining) || 0));
          if (!yr || !g.target_amount) return null;
          const cx = points.x(yr);
          const cy = points.y(num(g.target_amount));
          return (
            <g key={String(g.goal_id ?? g.goal_name)}>
              <line
                x1={cx}
                x2={cx}
                y1={pad.t}
                y2={pad.t + points.plotH}
                stroke="#cbd5e1"
                strokeDasharray="4 4"
              />
              <circle cx={cx} cy={cy} r={5} fill="#1e293b" />
              <text x={cx + 6} y={cy - 6} fontSize={10} fill="#334155">
                {g.goal_name}
              </text>
            </g>
          );
        })}
        {[0, 5, 10, 15, 20, 25, 30]
          .filter((y) => y <= horizon)
          .map((y) => {
            const isFirst = y === 0;
            const isLast = y === horizon || (y === Math.max(...[0, 5, 10, 15, 20, 25, 30].filter((v) => v <= horizon)));
            return (
              <text
                key={y}
                x={points.x(y)}
                y={height - 12}
                textAnchor={isFirst ? "start" : isLast ? "end" : "middle"}
                fontSize={10}
                fill="#64748b"
              >
                {y}y
              </text>
            );
          })}
        <rect
          x={pad.l}
          y={pad.t}
          width={points.plotW}
          height={points.plotH}
          fill="transparent"
          onMouseMove={(e) => {
            const rect = (e.target as SVGRectElement).getBoundingClientRect();
            const rel = (e.clientX - rect.left) / Math.max(1, rect.width);
            setHoverYear(Math.round(rel * horizon));
          }}
          onMouseLeave={() => setHoverYear(null)}
        />
        {hoverYear != null ? (
          <line
            x1={points.x(hoverYear)}
            x2={points.x(hoverYear)}
            y1={pad.t}
            y2={pad.t + points.plotH}
            stroke="#94a3b8"
            strokeWidth={1}
          />
        ) : null}
      </svg>
      {hoverVals && hoverYear != null ? (
        <div className="mt-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
          <p className="font-medium text-slate-900">Year {hoverYear}</p>
          {Object.entries(hoverVals).map(([name, pt]) => (
            <p key={name}>
              <span className="capitalize">{name}</span>: {moneyOrDash(pt?.value)}
              {pt?.contributions ? ` · contrib ${moneyOrDash(pt.contributions)}` : ""}
              {pt?.growth ? ` · growth ${moneyOrDash(pt.growth)}` : ""}
            </p>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-xs text-slate-500">Hover the chart to compare scenarios by year.</p>
      )}
    </div>
  );
}

export function TrajectoryPanel({ data }: { data: TrajectoryIntelligence }) {
  const [horizon, setHorizon] = useState(20);
  const snap = data.snapshot;
  const score = data.score;
  const proj = data.projections;
  const behavior = data.behavior;
  const endpoints = useMemo(
    () => proj?.endpoints_by_horizon?.[String(horizon)] || {},
    [proj?.endpoints_by_horizon, horizon],
  );

  const whatIfBase = num(proj?.monthly_contribution);
  const [whatIfMonthly, setWhatIfMonthly] = useState(
    whatIfBase > 0 ? String(Math.round(whatIfBase)) : "20000",
  );

  const localWhatIf = useMemo(() => {
    if (data.what_if) return data.what_if;
    const rows = proj?.sensitivity_matrix?.rows || [];
    const match = rows.find((r) => Math.abs(num(r.monthly_contribution) - num(whatIfMonthly)) < 1);
    if (!match) return null;
    const base = endpoints.base?.value;
    return {
      monthly_contribution: whatIfMonthly,
      projected_value: match.base || null,
      base_projected_value: base || null,
      delta_vs_base: base && match.base ? String(num(match.base) - num(base)) : null,
      horizon_years: proj?.sensitivity_matrix?.horizon_years || 15,
      note: "From sensitivity matrix (illustrative). Not a guarantee.",
    };
  }, [data.what_if, proj, whatIfMonthly, endpoints]);

  if (!data || (data.available === false && data.status === "insufficient_data")) {
    return (
      <Card className="aic-card-glow">
        <h2 className="text-base font-semibold text-slate-900">Financial trajectory</h2>
        <p className="mt-2 text-sm text-amber-800">
          {data?.reason ||
            "Need portfolio value, surplus, or goals to project where current decisions may lead."}
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card className="aic-card-glow border-teal-200/60 bg-gradient-to-br from-slate-50 via-white to-teal-50/40">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal-800">
          Financial trajectory
        </p>
        <div className="mt-3 flex flex-wrap items-end gap-6">
          <div>
            <p className="text-4xl font-semibold tabular-nums text-slate-900">
              {score?.overall_score != null ? score.overall_score : "—"}
              <span className="text-lg font-normal text-slate-500"> / {score?.max_score ?? 100}</span>
            </p>
            <p className="mt-1 text-sm text-slate-700">{score?.label || "Score pending"}</p>
          </div>
          <div className="max-w-xl flex-1">
            <p className="text-sm text-slate-700">
              {(score?.explanations || [])[0] ||
                "How well your current surplus, goals, and investing patterns align under stated assumptions."}
            </p>
            {(score?.explanations || []).slice(1).map((e) => (
              <p key={e} className="mt-1 text-xs text-slate-500">
                {e}
              </p>
            ))}
          </div>
        </div>
        {score?.component_scores ? (
          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(score.component_scores).map(([key, comp]) => (
              <div key={key} className="rounded-lg border border-slate-200 bg-white/80 px-3 py-2">
                <p className="text-xs uppercase tracking-wide text-slate-500">{key.replace(/_/g, " ")}</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">
                  {comp.score != null ? comp.score : "—"}
                </p>
                <p className="text-xs text-slate-500">
                  {comp.status === "insufficient_data" ? "Insufficient data" : comp.note}
                </p>
              </div>
            ))}
          </div>
        ) : null}
        {score?.disclaimer ? <p className="mt-3 text-xs text-slate-400">{score.disclaimer}</p> : null}
      </Card>

      {snap ? (
        <Card className="aic-card-glow">
          <h2 className="text-base font-semibold text-slate-900">Your financial position</h2>
          <p className="mt-1 text-sm text-slate-600">
            Snapshot from Twin — {snap.cadence_assumption || "amounts treated as monthly when cadence unknown."}
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(
              [
                ["Net worth", snap.net_worth],
                ["Portfolio", snap.portfolio_value],
                ["Investable", snap.investable_assets],
                ["Monthly income", snap.monthly_income],
                ["Monthly expenses", snap.monthly_expenses],
                ["Monthly surplus", snap.monthly_surplus],
                ["Savings rate", snap.savings_rate_percent, "%"],
                ["Liquid savings", snap.liquid_savings],
                ["Liabilities", snap.liabilities],
              ] as Array<[string, string | null | undefined, string?]>
            ).map(([label, value, suffix]) => (
              <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">
                  {value == null ? "—" : suffix === "%" ? `${value}%` : moneyOrDash(value)}
                </p>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      {proj?.series ? (
        <Card className="aic-card-glow">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Where you are headed</h2>
              <p className="mt-1 text-sm text-slate-600">
                Projected wealth performance under conservative / base / optimistic return assumptions —
                illustrative only, not a prediction or guarantee.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {[5, 10, 15, 20, 25, 30].map((h) => (
                <Button
                  key={h}
                  type="button"
                  variant={horizon === h ? "primary" : "secondary"}
                  onClick={() => setHorizon(h)}
                >
                  {h}Y
                </Button>
              ))}
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-xs">
            {Object.entries(proj.scenarios || {}).map(([name, rate]) => (
              <span key={name} className="inline-flex items-center gap-1.5 capitalize text-slate-700">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ background: SCENARIO_COLORS[name] || "#334155" }}
                />
                {name} ~{rate}%
              </span>
            ))}
          </div>
          <div className="mt-4">
            <WealthChart series={proj.series} goals={data.goal_projections || []} horizon={horizon} />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {(["conservative", "base", "optimistic"] as const).map((name) => {
              const pt = endpoints[name];
              return (
                <div key={name} className="rounded-lg border border-slate-200 bg-white px-3 py-3">
                  <p className="text-xs uppercase tracking-wide text-slate-500 capitalize">
                    {name} @ {horizon}y
                  </p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">{moneyOrDash(pt?.value)}</p>
                  {pt?.contributions || pt?.growth ? (
                    <p className="mt-1 text-xs text-slate-500">
                      Contrib {moneyOrDash(pt.contributions)} · Growth {moneyOrDash(pt.growth)}
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>
          {(proj.assumptions || []).length > 0 ? (
            <details className="mt-4">
              <summary className="cursor-pointer text-sm font-medium text-slate-800">
                Projection assumptions
              </summary>
              <ul className="mt-2 space-y-1 text-xs text-slate-600">
                {(proj.assumptions || []).map((a) => (
                  <li key={a}>• {a}</li>
                ))}
                <li>
                  • Current portfolio ₹{proj.principal || "—"} · Monthly contrib ₹
                  {proj.monthly_contribution || "—"} · Inflation {proj.inflation_pa || "—"}%
                </li>
              </ul>
            </details>
          ) : null}
          {proj.disclaimer ? <p className="mt-3 text-xs text-slate-400">{proj.disclaimer}</p> : null}
        </Card>
      ) : null}

      {(data.goal_projections || []).length > 0 ? (
        <Card className="aic-card-glow">
          <h2 className="text-base font-semibold text-slate-900">Goal funding under scenarios</h2>
          <p className="mt-1 text-sm text-slate-600">
            Same goals, with conservative / base / optimistic funding ranges.
          </p>
          <ul className="mt-4 space-y-3">
            {(data.goal_projections || []).map((g) => {
              const pct = g.likelihood_percent;
              const widthPct = pct != null ? Math.min(100, Math.max(0, pct)) : 0;
              return (
                <li
                  key={String(g.goal_id ?? g.goal_name)}
                  className="rounded-lg border border-slate-200 bg-white p-4"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium text-slate-900">{g.goal_name || "Goal"}</p>
                    {g.likelihood_status ? (
                      <StatusBadge
                        status={
                          g.likelihood_status === "likely" || g.likelihood_status === "possible"
                            ? "known"
                            : "unknown"
                        }
                      >
                        {g.likelihood_status.replace(/_/g, " ")}
                        {pct != null ? ` · ~${pct}%` : ""}
                      </StatusBadge>
                    ) : null}
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded bg-slate-100">
                    <div className="h-full bg-teal-700" style={{ width: `${widthPct}%` }} />
                  </div>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                    {g.target_amount ? <span>Target {moneyOrDash(g.target_amount)}</span> : null}
                    {g.projected_corpus ? <span>Base proj {moneyOrDash(g.projected_corpus)}</span> : null}
                    {g.required_monthly_contribution ? (
                      <span>Need ~{moneyOrDash(g.required_monthly_contribution)}/mo</span>
                    ) : null}
                  </div>
                  {g.scenario_funding ? (
                    <div className="mt-2 grid gap-2 text-xs text-slate-600 sm:grid-cols-3">
                      {Object.entries(g.scenario_funding).map(([name, row]) => (
                        <p key={name} className="capitalize">
                          {name}: {moneyOrDash(row.projected_corpus)}
                          {row.shortfall_or_surplus != null
                            ? ` (gap ${moneyOrDash(row.shortfall_or_surplus)})`
                            : ""}
                        </p>
                      ))}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </Card>
      ) : null}

      {behavior ? (
        <Card className="aic-card-glow">
          <h2 className="text-base font-semibold text-slate-900">What your investing behavior shows</h2>
          <p className="mt-1 text-sm text-slate-600">
            Observed from transactions — separate from psychometric questionnaire answers.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {behavior.behavior_score != null ? (
              <StatusBadge status="known">Behavior score: {behavior.behavior_score}/100</StatusBadge>
            ) : (
              <StatusBadge status="unknown">Behavior score: insufficient data</StatusBadge>
            )}
            {behavior.source ? <StatusBadge status="unknown">{behavior.source}</StatusBadge> : null}
          </div>
          {behavior.components ? (
            <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {Object.entries(behavior.components).map(([key, comp]) => (
                <div key={key} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                  <p className="text-xs uppercase tracking-wide text-slate-500">{key.replace(/_/g, " ")}</p>
                  <p className="mt-1 font-semibold text-slate-900">
                    {comp.score != null ? comp.score : "Insufficient data"}
                  </p>
                  <p className="text-xs text-slate-500">{comp.note}</p>
                </div>
              ))}
            </div>
          ) : null}
          {(behavior.comments || []).length > 0 ? (
            <ul className="mt-4 space-y-1 text-sm text-slate-700">
              {(behavior.comments || []).map((c) => (
                <li key={c}>• {c}</li>
              ))}
            </ul>
          ) : null}
          {behavior.disclaimer ? <p className="mt-3 text-xs text-slate-400">{behavior.disclaimer}</p> : null}
        </Card>
      ) : null}

      <Card className="aic-card-glow">
        <h2 className="text-base font-semibold text-slate-900">What-if</h2>
        <p className="mt-1 text-sm text-slate-600">
          Explore a different monthly contribution vs the current surplus assumption.
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <label className="text-sm text-slate-700">
            Monthly investment (₹)
            <input
              className="mt-1 block w-40 rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={whatIfMonthly}
              onChange={(e) => setWhatIfMonthly(e.target.value.replace(/[^\d.]/g, ""))}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            {[5000, 10000, 20000].map((add) => (
              <Button
                key={add}
                type="button"
                variant="secondary"
                onClick={() => setWhatIfMonthly(String(Math.round(whatIfBase + add)))}
              >
                +₹{(add / 1000).toFixed(0)}k
              </Button>
            ))}
          </div>
        </div>
        {localWhatIf ? (
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800">
            <p>
              At ~{localWhatIf.horizon_years || 15} years (base return):{" "}
              <strong>{moneyOrDash(localWhatIf.projected_value)}</strong>
            </p>
            {localWhatIf.delta_vs_base != null ? (
              <p className="mt-1 text-slate-600">
                Δ vs current surplus path: {moneyOrDash(localWhatIf.delta_vs_base)} (illustrative)
              </p>
            ) : null}
            {localWhatIf.note ? <p className="mt-1 text-xs text-slate-500">{localWhatIf.note}</p> : null}
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">
            Adjust contribution to compare against the sensitivity matrix when available.
          </p>
        )}
        {(proj?.sensitivity_matrix?.rows || []).length > 0 ? (
          <div className="mt-4 overflow-x-auto">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
              Sensitivity @ {proj?.sensitivity_matrix?.horizon_years}y
            </p>
            <table className="min-w-full text-left text-xs text-slate-700">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500">
                  <th className="py-2 pr-3">Contribution</th>
                  <th className="py-2 pr-3">Conservative</th>
                  <th className="py-2 pr-3">Base</th>
                  <th className="py-2">Optimistic</th>
                </tr>
              </thead>
              <tbody>
                {(proj?.sensitivity_matrix?.rows || []).map((row) => (
                  <tr key={String(row.monthly_contribution)} className="border-b border-slate-100">
                    <td className="py-2 pr-3">{moneyOrDash(row.monthly_contribution)}</td>
                    <td className="py-2 pr-3">{moneyOrDash(row.conservative)}</td>
                    <td className="py-2 pr-3">{moneyOrDash(row.base)}</td>
                    <td className="py-2">{moneyOrDash(row.optimistic)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>

      {(data.insights || []).length > 0 || (data.recommended_actions || []).length > 0 ? (
        <Card className="aic-card-glow">
          <h2 className="text-base font-semibold text-slate-900">Trajectory insights & actions</h2>
          {(data.insights || []).length > 0 ? (
            <ul className="mt-3 space-y-1 text-sm text-slate-700">
              {(data.insights || []).slice(0, 6).map((c) => (
                <li key={c}>• {c}</li>
              ))}
            </ul>
          ) : null}
          {(data.recommended_actions || []).length > 0 ? (
            <ol className="mt-4 list-decimal space-y-1 pl-5 text-sm text-slate-800">
              {(data.recommended_actions || []).slice(0, 5).map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ol>
          ) : null}
          {data.disclaimer ? <p className="mt-3 text-xs text-slate-400">{data.disclaimer}</p> : null}
        </Card>
      ) : null}
    </div>
  );
}
