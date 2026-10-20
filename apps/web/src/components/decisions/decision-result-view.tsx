"use client";

import Link from "next/link";
import { Button, StatusBadge } from "@ai-cio/ui";
import type { DecisionResult } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { TrajectoryPanel } from "@/components/trajectory-panel";
import {
  Expandable,
  GlassPanel,
  InsightRow,
  MetricTile,
  SectionHeader,
  SurfacePanel,
} from "@/components/design/system";
import {
  buildDecisionFindings,
  normalizeWorrySeverity,
} from "@/lib/decision-findings";
import {
  AgentPerspectivesPanel,
  BehavioralIntelligencePanel,
  DataQualityPanel,
  DecisionTracePanel,
  TemporalChangesPanel,
} from "@/components/decisions/decision-trace-panels";
import {
  CounterfactualsExpandable,
  CounterfactualsPanel,
} from "@/components/decisions/counterfactuals-panel";
import { AiTag } from "@/components/design/ai-tag";
import { RankedSuggestions } from "@/components/decisions/ranked-suggestions";
import { DecisionNextSteps } from "@/components/decision-next-steps";
import { FirePlanView } from "@/components/fire/fire-plan-view";
import { DecisionFlow, HoldingMarketPanel } from "@/components/decisions/decision-flow";
import { OrchestrationPanel } from "@/components/decisions/orchestration-panel";
import { MutualFundPanel } from "@/components/mutual-funds/mutual-fund-panel";
import { BondPanel } from "@/components/bonds/bond-panel";

const ALLOCATION_LABELS: Record<string, string> = {
  cash: "Cash",
  debt: "Debt / fixed income",
  equity: "Equity",
};

function equityAiUsed(result: DecisionResult): boolean {
  const agent = String(
    result.execution?.agent || result.execution?.analyzer || "",
  );
  if (!/EquityAgent/i.test(agent)) return false;
  const assumptions = result.assumptions || [];
  const llmFailed = assumptions.some((a) =>
    /Equity LLM unavailable|LLM unavailable|rule-based equity dashboard|rule-based fallback/i.test(
      a,
    ),
  );
  return !llmFailed;
}

export function DecisionResultView({
  result,
  onStartOver,
  onRefresh,
  onExploreWhatIf,
  refreshing = false,
  checking = false,
}: {
  result: DecisionResult;
  onStartOver: () => void;
  onRefresh?: () => void;
  onExploreWhatIf?: () => void;
  refreshing?: boolean;
  checking?: boolean;
}) {
  const findings = buildDecisionFindings(result);
  const score = result.trajectory_intelligence?.score;
  const tax = result.tax_intelligence;
  const fd = result.fd_intelligence;
  const sector = result.sector_opportunity;
  const cacheHit = Boolean(result.cache?.hit);
  const focusWhatIf = result.objective === "explore_counterfactuals";
  const aiReasoned = equityAiUsed(result);
  const opportunities = [
    ...((tax?.opportunities || []).map((o) => ({
      title: o.label || o.type || "Tax opportunity",
      detail: o.reason || "",
      kind: "tax",
    })) || []),
    ...((sector?.recommendations || []).slice(0, 3).map((r) => ({
      title: r.name,
      detail: r.logic || `Rule-based sector score ${r.final_score}`,
      kind: "sector",
    })) || []),
  ].slice(0, 6);

  if (result.objective === "plan_fire") {
    return <div className="space-y-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-[10px] font-semibold uppercase tracking-[.18em] text-teal-700">Your saved FIRE decision</p><p className="mt-2 text-xs leading-6 text-slate-500">Saved goal inputs, cashflow capacity and psychometric preferences · scenario support, no automatic investments.</p></div><div className="flex flex-wrap gap-2"><Link href={result.fire_plan?.goal_id ? `/fire?goal_id=${result.fire_plan.goal_id}` : "/fire"}><Button variant="secondary">Edit FIRE assumptions</Button></Link>{onRefresh ? <Button variant="secondary" disabled={refreshing} onClick={onRefresh}>{refreshing ? "Updating…" : "Refresh FIRE decision"}</Button> : null}<Button variant="secondary" onClick={onStartOver}>Change focus</Button></div></div><OrchestrationPanel trace={result.orchestration} cached={cacheHit} />{result.fire_plan?.version ? <FirePlanView plan={result.fire_plan} /> : <SurfacePanel><p className="text-sm text-amber-900">No FIRE calculation is attached to this decision. Save a FIRE goal and run the review again.</p><Link href="/fire" className="mt-4 inline-block text-sm font-semibold text-teal-800 underline">Set up my FIRE goal ↗</Link></SurfacePanel>}<MutualFundPanel data={result.mutual_fund_intelligence} context="fire" /><BondPanel data={result.bond_intelligence} /></div>;
  }

  // Focused What-if mode: skip the full decision brief clutter
  if (focusWhatIf) {
    return (
      <div className="space-y-8">
        <GlassPanel strong>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--aic-blue-muted)]">
            Counterfactuals
          </p>
          <h1 className="aic-title mt-2">Explore a different path.</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-600">
            Compare the trade-offs before changing direction. These are
            illustrative scenarios, with assumptions and AI narrative identified
            where used.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusBadge status="known">
              Confidence: {result.confidence}
            </StatusBadge>
            {result.cache?.hit ? (
              <StatusBadge status="known">Cached</StatusBadge>
            ) : null}
          </div>
        </GlassPanel>

        <OrchestrationPanel trace={result.orchestration} cached={cacheHit} />
        <CounterfactualsPanel data={result.counterfactuals} />
        <MutualFundPanel data={result.mutual_fund_intelligence} /><BondPanel data={result.bond_intelligence} />

        <div className="flex flex-wrap gap-3">
          {onRefresh ? (
            <Button onClick={onRefresh} disabled={refreshing}>
              {refreshing ? "Refreshing…" : "Refresh analysis"}
            </Button>
          ) : null}
          <Button variant="secondary" onClick={onStartOver}>
            Change setup
          </Button>
          <Link href="/onboarding/twin">
            <Button variant="secondary">Back to profile</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[.2em] text-teal-700">
            Your decision workspace
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Review the priorities. Understand the evidence. Explore your
            options.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {onExploreWhatIf ? (
            <Button variant="secondary" onClick={onExploreWhatIf}>
              Explore a what-if ↗
            </Button>
          ) : null}
          <Button variant="secondary" onClick={onStartOver}>
            Change focus
          </Button>
          {onRefresh ? (
            <Button
              variant="secondary"
              onClick={onRefresh}
              disabled={refreshing}
            >
              {refreshing ? "Updating…" : "Refresh analysis ↻"}
            </Button>
          ) : null}
        </div>
      </div>
      <GlassPanel strong>
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--aic-blue-muted)]">
          AI-cio Decision Brief
        </p>
        <h1 className="aic-title mt-2">What deserves a closer look.</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
          Structured guidance from your Twin, equity, mutual funds, tax, FDs and goals —
          for review, not a buy or sell instruction.
        </p>
        {result.cache?.note ? (
          <p
            className={`mt-3 rounded-xl border px-3 py-2 text-xs leading-relaxed ${
              cacheHit
                ? "border-teal-200/80 bg-teal-50/70 text-teal-900"
                : "border-[rgba(15,55,110,0.12)] bg-white/50 text-slate-600"
            }`}
          >
            {checking
              ? "Rechecking saved analysis — "
              : cacheHit
                ? "Saved result — "
                : "New analysis — "}
            {checking
              ? "Current inputs are being checked. Review the saved time below."
              : result.cache.note}
            {result.cache.cached_at
              ? ` · Saved ${new Date(result.cache.cached_at).toLocaleString()}`
              : ""}
          </p>
        ) : null}

        <div className="mt-6 grid gap-6 border-t border-[rgba(15,55,110,0.1)] pt-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
          <div className="order-2 rounded-2xl border border-white/80 bg-white/65 p-4 lg:order-2">
            <p className="aic-meta uppercase tracking-[0.1em]">
              Financial trajectory
            </p>
            <p className="aic-num mt-1 text-4xl font-semibold text-[var(--aic-navy)]">
              {score?.overall_score != null ? score.overall_score : "—"}
              <span className="text-xl font-normal text-slate-400">
                {" "}
                / {score?.max_score ?? 100}
              </span>
            </p>
            <p className="mt-2 text-sm font-medium text-slate-800">
              {score?.label || "Score pending"}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              {(score?.explanations || [])[0] || result.decision}
            </p>
          </div>
          <div className="order-1 lg:order-1">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <p className="aic-meta uppercase tracking-[0.1em]">
                The key takeaway
              </p>
              {result.suggestions?.explanation_version === "applied-principles-v1" ? <span className="rounded-md bg-teal-50 px-2 py-1 text-[10px] font-semibold text-teal-800">Skill-cited derivation</span> : aiReasoned ? <AiTag /> : null}
            </div>
            <p className="mt-3 text-xl font-medium leading-relaxed tracking-tight text-slate-800">
              {result.decision}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <StatusBadge status="known">
                Confidence: {result.confidence}
              </StatusBadge>
              {result.data_quality?.confidence_note ? (
                <StatusBadge status="known">
                  {result.data_quality.confidence_note}
                </StatusBadge>
              ) : null}
              {tax?.available ? (
                <StatusBadge status="known">Tax intelligence</StatusBadge>
              ) : null}
              {fd?.available ? (
                <StatusBadge status="known">FD intelligence</StatusBadge>
              ) : null}
            </div>
          </div>
        </div>
      </GlassPanel>

      <nav
        aria-label="Decision brief sections"
        className="decision-jumpnav grid gap-3 sm:grid-cols-3"
      >
        {(result.suggestions?.items?.length
          ? [
              [
                "#decision-actions",
                "01",
                "Review the priorities",
                "Ranked suggestions and a useful next step.",
              ],
            ]
          : [
              [
                "#decision-findings",
                "01",
                "Review the findings",
                "What your current information tells us.",
              ],
            ]
        )
          .concat(
            result.trajectory_intelligence
              ? [
                  [
                    "#decision-outlook",
                    "02",
                    "Explore your outlook",
                    "Compare scenarios and goal funding.",
                  ],
                ]
              : [
                  [
                    "#decision-details",
                    "02",
                    "Explore the trade-offs",
                    "Assumptions, risks and alternative paths.",
                  ],
                ],
            [
              [
                "#decision-evidence",
                "03",
                "Follow the reasoning",
                "Inspect the decision trace and data quality.",
              ],
            ],
          )
          .map(([href, number, title, description]) => (
            <a
              key={href}
              href={href}
              className="rounded-2xl border border-slate-200 bg-white p-4 transition-colors hover:border-teal-200 hover:bg-teal-50/50"
            >
              <span className="text-[10px] font-semibold tracking-wider text-teal-700">
                {number}{" "}
                <span className="float-right" aria-hidden>
                  ↓
                </span>
              </span>
              <span className="mt-2 block text-sm font-semibold text-slate-800">
                {title}
              </span>
              <span className="mt-1 block text-xs leading-5 text-slate-500">
                {description}
              </span>
            </a>
          ))}
      </nav>
      {result.orchestration?.version ? <OrchestrationPanel trace={result.orchestration} cached={cacheHit} /> : <DecisionFlow result={result} />}
      <RankedSuggestions suggestions={result.suggestions} />
      <MutualFundPanel data={result.mutual_fund_intelligence} /><BondPanel data={result.bond_intelligence} />
      <TemporalChangesPanel data={result.temporal_changes} />

      {result.sector_day_changes?.available ? (
        <GlassPanel>
          <SectionHeader
            eyebrow="Market context"
            title="Sectors today"
            description="Trendlyne mcap-weighted day change — short-term context for what is strong vs weak."
          />
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-teal-800">
                Doing well
              </p>
              <ul className="mt-2 space-y-1.5">
                {(result.sector_day_changes.doing_well || []).map((row) => (
                  <li
                    key={`well-${row.name}`}
                    className="flex justify-between gap-3 text-sm"
                  >
                    <span className="text-slate-700">{row.name}</span>
                    <span className="font-medium tabular-nums text-teal-700">
                      {row.day_change_percent > 0 ? "+" : ""}
                      {row.day_change_percent}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-rose-800">
                Under pressure
              </p>
              <ul className="mt-2 space-y-1.5">
                {(result.sector_day_changes.doing_poorly || []).map((row) => (
                  <li
                    key={`poor-${row.name}`}
                    className="flex justify-between gap-3 text-sm"
                  >
                    <span className="text-slate-700">{row.name}</span>
                    <span className="font-medium tabular-nums text-rose-700">
                      {row.day_change_percent}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          {result.sector_day_changes.note ? (
            <p className="mt-3 text-xs text-slate-500">
              {result.sector_day_changes.note}
            </p>
          ) : null}
        </GlassPanel>
      ) : null}

      {result.suggestions?.explanation_version !== "applied-principles-v1" && findings.length > 0 ? (
        <div id="decision-findings" className="decision-anchor">
          <GlassPanel>
            <SectionHeader
              eyebrow="Intelligence"
              title="What AI-cio found"
              action={aiReasoned ? <AiTag /> : null}
            />
            <div className="mt-2">
              {findings.map((f, idx) => (
                <InsightRow
                  key={`${f.source}-${f.title}-${idx}`}
                  index={idx + 1}
                  title={f.title}
                  detail={f.detail}
                  severity={f.severity}
                  metric={f.metric}
                />
              ))}
            </div>
          </GlassPanel>
        </div>
      ) : null}

      {result.suggestions?.explanation_version !== "applied-principles-v1" && result.top_worries && result.top_worries.length > 0 ? (
        <SurfacePanel>
          <SectionHeader
            eyebrow="Priority"
            title="What needs attention"
            description="Existing concentration and portfolio flags, ordered for review."
          />
          <div className="mt-1">
            {result.top_worries.map((worry, idx) => (
              <InsightRow
                key={`${worry.title}-${idx}`}
                index={idx + 1}
                title={worry.title}
                detail={worry.detail}
                severity={normalizeWorrySeverity(worry.severity)}
                metric={worry.metric}
              />
            ))}
          </div>
        </SurfacePanel>
      ) : null}

      {result.suggestions?.explanation_version !== "applied-principles-v1" && opportunities.length > 0 ? (
        <SurfacePanel>
          <SectionHeader
            eyebrow="Forward look"
            title="Opportunities discovered"
            description="From existing suggestions, tax lots, and sector ranks — educational only."
          />
          <div className="mt-1">
            {opportunities.map((item, idx) => (
              <InsightRow
                key={`${item.title}-${idx}`}
                index={idx + 1}
                title={item.title}
                detail={item.detail}
                severity="opportunity"
              />
            ))}
          </div>
        </SurfacePanel>
      ) : null}

      <AgentPerspectivesPanel data={result.agent_perspectives} />

      <BehavioralIntelligencePanel data={result.behavioral_intelligence} />

      {result.trajectory_intelligence ? (
        <div id="decision-outlook" className="decision-anchor">
          <TrajectoryPanel data={result.trajectory_intelligence} hideActions={result.suggestions?.explanation_version === "applied-principles-v1"} />
        </div>
      ) : null}

      {(result.goal_likelihood && result.goal_likelihood.length > 0) ||
      (result.trajectory_intelligence?.goal_projections || []).length > 0 ? (
        <SurfacePanel>
          <SectionHeader
            title="Goals"
            description="Illustrative goal projections. Coverage scores and status bands are heuristics, not calibrated probabilities of success."
          />
          <div className="mt-4 divide-y divide-[rgba(15,55,110,0.08)]">
            {(result.trajectory_intelligence?.goal_projections?.length
              ? result.trajectory_intelligence.goal_projections
              : result.goal_likelihood || []
            ).map((item) => (
              <div
                key={item.goal_id ?? item.goal_name}
                className="flex flex-col gap-2 py-4 sm:flex-row sm:items-start sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="aic-finding">{item.goal_name || "Goal"}</p>
                  {item.narrative ? (
                    <p className="mt-1 text-sm text-slate-600">
                      {item.narrative}
                    </p>
                  ) : null}
                </div>
                <div className="flex shrink-0 flex-wrap gap-x-4 gap-y-1 text-sm text-slate-700 sm:justify-end">
                  {item.target_amount ? (
                    <span>
                      <span className="aic-meta block">Target</span>
                      <span className="font-medium tabular-nums">
                        {formatCurrency(item.target_amount)}
                      </span>
                    </span>
                  ) : null}
                  {item.projected_corpus ? (
                    <span>
                      <span className="aic-meta block">Projected</span>
                      <span className="font-medium tabular-nums">
                        {formatCurrency(item.projected_corpus)}
                      </span>
                    </span>
                  ) : null}
                  {item.years_remaining != null ? (
                    <span>
                      <span className="aic-meta block">Horizon</span>
                      <span className="font-medium">
                        ~{item.years_remaining}y
                      </span>
                    </span>
                  ) : null}
                  {item.likelihood_status ? (
                    <span>
                      <span className="aic-meta block">Status</span>
                      <span className="font-medium capitalize">
                        {String(item.likelihood_status).replace(/_/g, " ")}
                        {item.likelihood_percent != null
                          ? ` · coverage score ${item.likelihood_percent}/100`
                          : ""}
                      </span>
                    </span>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </SurfacePanel>
      ) : null}

      {tax ? (
        <SurfacePanel>
          <SectionHeader
            title="Tax intelligence"
            description="Deterministic estimates from existing lots — not tax advice."
            action={
              <Link
                href="/tax"
                className="text-sm font-medium text-[var(--aic-navy)] underline-offset-2 hover:underline"
              >
                Open tax →
              </Link>
            }
          />
          {!tax.available ? (
            <p className="mt-4 text-sm text-amber-800">
              {tax.reason || "Tax analysis incomplete."}
            </p>
          ) : (
            <>
              <div className="mt-5 grid grid-cols-2 gap-6 sm:grid-cols-4">
                <MetricTile
                  label="STCG"
                  value={
                    tax.summary?.stcg ? formatCurrency(tax.summary.stcg) : "—"
                  }
                />
                <MetricTile
                  label="LTCG"
                  value={
                    tax.summary?.ltcg ? formatCurrency(tax.summary.ltcg) : "—"
                  }
                />
                <MetricTile
                  label="Est. tax"
                  value={
                    tax.summary?.estimated_tax
                      ? formatCurrency(tax.summary.estimated_tax)
                      : "—"
                  }
                />
                <MetricTile
                  label="Opportunities"
                  value={String((tax.opportunities || []).length)}
                />
              </div>
              {(tax.comments || []).length > 0 ? (
                <Expandable title="Tax findings & comments">
                  <ul className="space-y-2 text-sm text-slate-700">
                    {(tax.comments || []).slice(0, 6).map((c) => (
                      <li key={c}>• {c}</li>
                    ))}
                  </ul>
                </Expandable>
              ) : null}
            </>
          )}
        </SurfacePanel>
      ) : null}

      {fd ? (
        <SurfacePanel>
          <SectionHeader
            title="Fixed deposits & cash"
            action={
              <Link
                href="/fd"
                className="text-sm font-medium text-[var(--aic-navy)] underline-offset-2 hover:underline"
              >
                Open FDs →
              </Link>
            }
          />
          {!fd.available ? (
            <p className="mt-4 text-sm text-amber-800">
              {fd.reason || "FD analysis incomplete."}
            </p>
          ) : (
            <div className="mt-5 grid grid-cols-2 gap-6 sm:grid-cols-4">
              <MetricTile
                label="FD principal"
                value={
                  fd.summary?.total_principal
                    ? formatCurrency(fd.summary.total_principal)
                    : "—"
                }
              />
              <MetricTile
                label="FDs"
                value={String(fd.summary?.fd_count ?? 0)}
              />
              <MetricTile
                label="Liquid cash"
                value={
                  fd.summary?.liquid_cash
                    ? formatCurrency(fd.summary.liquid_cash)
                    : "—"
                }
              />
              <MetricTile
                label="Cash + FDs"
                value={
                  fd.summary?.combined_cash_and_fd
                    ? formatCurrency(fd.summary.combined_cash_and_fd)
                    : "—"
                }
              />
            </div>
          )}
        </SurfacePanel>
      ) : null}

      {result.suggestions?.explanation_version !== "applied-principles-v1" && result.recommended_actions && result.recommended_actions.length > 0 ? (
        <SurfacePanel>
          <SectionHeader
            title="Recommended review actions"
            description="From existing analysis — not automatic trades."
            action={aiReasoned ? <AiTag /> : null}
          />
          <ol className="mt-4 space-y-3">
            {result.recommended_actions.map((line, idx) => (
              <li key={line} className="flex gap-3 text-sm text-slate-700">
                <span className="aic-meta w-6 shrink-0 font-semibold tabular-nums text-[var(--aic-blue-muted)]">
                  {String(idx + 1).padStart(2, "0")}
                </span>
                <span className="leading-relaxed">{line}</span>
              </li>
            ))}
          </ol>
        </SurfacePanel>
      ) : null}

      <div id="decision-evidence" className="decision-anchor space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[.18em] text-teal-700">
              03 / Behind the brief
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
              Every finding has a trail.
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              Follow the inputs, analysis and checks that led to this result.
            </p>
          </div>
          <a
            href="#decision-actions"
            className="text-xs font-medium text-teal-800 underline underline-offset-4"
          >
            Back to the priorities ↑
          </a>
        </div>
        <HoldingMarketPanel result={result} />
        <DecisionTracePanel data={result.decision_trace} />
      </div>

      <DataQualityPanel data={result.data_quality} />

      <div id="decision-details" className="decision-anchor">
        <SurfacePanel>
          <SectionHeader
            title="Detailed analysis"
            description="Secondary evidence — expand as needed."
          />
          <div className="mt-2">
            {result.portfolio_health?.score != null ? (
              <Expandable title="Portfolio health score">
                <p className="aic-num text-3xl font-semibold text-[var(--aic-navy)]">
                  {result.portfolio_health.score}
                  <span className="text-base font-normal text-slate-400">
                    /{result.portfolio_health.max_score ?? 100}
                  </span>
                </p>
                {result.portfolio_health.components ? (
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {Object.entries(result.portfolio_health.components).map(
                      ([key, comp]) => (
                        <div key={key}>
                          <p className="aic-meta uppercase">
                            {key.replace(/_/g, " ")}
                          </p>
                          <p className="mt-0.5 font-medium tabular-nums">
                            {comp.available && comp.score != null
                              ? comp.score
                              : "—"}
                          </p>
                          <p className="text-xs text-slate-500">{comp.note}</p>
                        </div>
                      ),
                    )}
                  </div>
                ) : null}
              </Expandable>
            ) : null}

            {result.concentration_analysis &&
            Object.keys(result.concentration_analysis).length > 0 ? (
              <Expandable title="Concentration details">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  {[
                    [
                      "Largest",
                      result.concentration_analysis.largest_holding_percent,
                    ],
                    ["Top 3", result.concentration_analysis.top_3_percent],
                    ["Top 5", result.concentration_analysis.top_5_percent],
                    ["Top 10", result.concentration_analysis.top_10_percent],
                  ].map(([label, value]) => (
                    <div key={String(label)}>
                      <p className="aic-meta uppercase">{String(label)}</p>
                      <p className="mt-0.5 text-lg font-semibold tabular-nums">
                        {value != null ? `${String(value)}%` : "—"}
                      </p>
                    </div>
                  ))}
                </div>
              </Expandable>
            ) : null}

            {result.true_exposure ? (
              <Expandable title="True exposure breakdown">
                <div className="grid gap-4 md:grid-cols-3">
                  {(
                    [
                      [
                        "Sector",
                        result.true_exposure.sector_exposure,
                        "sector",
                      ],
                      [
                        "Market cap",
                        result.true_exposure.market_cap_exposure,
                        "category",
                      ],
                      ["Themes", result.true_exposure.economic_themes, "theme"],
                    ] as const
                  ).map(([label, rows, key]) => (
                    <div key={label}>
                      <p className="text-sm font-medium text-slate-900">
                        {label}
                      </p>
                      <ul className="mt-2 space-y-1 text-sm text-slate-700">
                        {(rows || []).slice(0, 6).map((row) => {
                          const name = String(
                            (row as Record<string, unknown>)[key] || "",
                          );
                          return (
                            <li
                              key={name}
                              className="flex justify-between gap-2"
                            >
                              <span>{name}</span>
                              <span className="font-medium tabular-nums">
                                {row.percent ? `${row.percent}%` : "—"}
                              </span>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ))}
                </div>
              </Expandable>
            ) : null}

            {sector ? (
              <Expandable title="Sector opportunity ranks">
                {!sector.available ? (
                  <p className="text-sm text-amber-800">{sector.reason}</p>
                ) : (
                  <ol className="space-y-3">
                    {(sector.recommendations || []).map((rec) => (
                      <li key={rec.name} className="text-sm">
                        <p className="font-medium text-slate-900">
                          {rec.rank}. {rec.name} · score {rec.final_score}
                        </p>
                        {rec.logic ? (
                          <p className="mt-1 text-slate-600">{rec.logic}</p>
                        ) : null}
                      </li>
                    ))}
                  </ol>
                )}
              </Expandable>
            ) : null}

            {result.style_allocation?.length ||
            result.sector_allocation?.length ? (
              <Expandable title="Style & sector mix">
                <div className="grid gap-4 md:grid-cols-2">
                  {result.style_allocation?.length ? (
                    <ul className="space-y-1 text-sm">
                      {result.style_allocation.slice(0, 8).map((row) => (
                        <li
                          key={row.style}
                          className="flex justify-between gap-2"
                        >
                          <span>{String(row.style).replace(/_/g, " ")}</span>
                          <span className="font-medium tabular-nums">
                            {row.percent ? `${row.percent}%` : "—"}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {result.sector_allocation?.length ? (
                    <ul className="space-y-1 text-sm">
                      {result.sector_allocation.slice(0, 8).map((row) => (
                        <li
                          key={row.sector}
                          className="flex justify-between gap-2"
                        >
                          <span>{row.sector}</span>
                          <span className="font-medium tabular-nums">
                            {(row.percent ?? row.weight_percent)
                              ? `${row.percent ?? row.weight_percent}%`
                              : "—"}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </Expandable>
            ) : null}

            {result.rationale.length > 0 || result.risks.length > 0 ? (
              <Expandable
                title={
                  aiReasoned ? (
                    <span className="inline-flex items-center gap-2">
                      Observations, risks & trade-offs
                      <AiTag />
                    </span>
                  ) : (
                    "Observations, risks & trade-offs"
                  )
                }
              >
                <div className="grid gap-4 md:grid-cols-2">
                  <ul className="space-y-2 text-sm text-slate-700">
                    {result.rationale.map((line) => (
                      <li key={line}>• {line}</li>
                    ))}
                  </ul>
                  <ul className="space-y-2 text-sm text-slate-700">
                    {[...result.risks, ...result.tradeoffs].map((line) => (
                      <li key={line}>• {line}</li>
                    ))}
                  </ul>
                </div>
              </Expandable>
            ) : null}

            {result.selected_strategy &&
            Object.keys(result.selected_strategy.allocation).length > 0 ? (
              <Expandable
                title={`Suggested approach: ${result.selected_strategy.name}`}
              >
                <div className="grid gap-3 sm:grid-cols-3">
                  {Object.entries(result.selected_strategy.allocation).map(
                    ([key, amount]) => (
                      <div key={key}>
                        <p className="aic-meta uppercase">
                          {ALLOCATION_LABELS[key] ?? key}
                        </p>
                        <p className="mt-1 text-lg font-semibold tabular-nums">
                          {formatCurrency(amount)}
                        </p>
                      </div>
                    ),
                  )}
                </div>
              </Expandable>
            ) : null}

            {result.evidence.length > 0 ? (
              <Expandable title="Methodology & knowledge sources">
                <div className="space-y-3">
                  {result.evidence.map((item) => (
                    <div
                      key={`${item.reference}-${item.section}`}
                      className="text-sm"
                    >
                      <p className="font-medium text-slate-900">
                        {item.section}
                      </p>
                      <p className="aic-meta">{item.reference}</p>
                      <p className="mt-1 text-slate-700">{item.content}</p>
                    </div>
                  ))}
                </div>
              </Expandable>
            ) : null}

            <CounterfactualsExpandable
              data={result.counterfactuals}
              defaultOpen={false}
            />
          </div>
        </SurfacePanel>
      </div>

      <DecisionNextSteps />

      <div className="flex flex-wrap gap-3">
        {onRefresh ? (
          <Button onClick={onRefresh} disabled={refreshing}>
            {refreshing ? "Refreshing…" : "Refresh analysis"}
          </Button>
        ) : null}
        <Button variant="secondary" onClick={onStartOver}>
          Change setup
        </Button>
        <Link href="/onboarding/twin">
          <Button variant="secondary">Back to profile</Button>
        </Link>
      </div>
    </div>
  );
}
