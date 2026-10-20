"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { MutualFundAnalysis, MutualFundCorrelation, MutualFundFinding, MutualFundIntelligence, MutualFundOverlap, SkillPrinciple } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { apiRequest } from "@/lib/api-client";
import { evidenceUrl, findingFundNames, focusedFundFindings, fundFindingFacts, fundGrowth, hasRecordedEvidence, jsonEvidence, measuredFundPairs, observationNumber, pairMetric, pairStatusExplanation, percentage } from "@/lib/investment-evidence";
import { ReviewProofPanel } from "@/components/decisions/review-proof";

const money = (value: unknown) => observationNumber(value) == null ? "Not measured" : formatCurrency(String(value));
const dateRange = (start?: string | null, end?: string | null) => start && end ? `${start} to ${end}` : "";

function SourceLink({ url, children }: { url?: string | null; children: React.ReactNode }) {
  const safe = evidenceUrl(url);
  return safe ? <a href={safe} target="_blank" rel="noreferrer" className="font-medium text-teal-800 underline underline-offset-4">{children} ↗</a> : <span className="text-slate-500">{children}</span>;
}

function PublishedComparison({ fund }: { fund: MutualFundAnalysis }) {
  const published = fund.published_comparison;
  const returns = published?.returns?.filter((row) => observationNumber(row.fund_return_pct) != null && observationNumber(row.benchmark_return_pct) != null) || [];
  if (!published?.available || !returns.length) return null;
  return <details className="mt-4 rounded-xl border border-blue-100 bg-[#f5f8fc] p-4">
    <summary className="cursor-pointer text-xs font-semibold text-blue-900">AMC-reported comparison · {published.observed_on || "see source date"}{published.stale ? " · source review due" : ""}</summary>
    <p className="mt-3 text-xs leading-6 text-slate-600">The AMC reports the following {published.plan} plan returns against {published.benchmark?.name || "its stated benchmark"}. These published endpoints are separate from the calculated NAV chart.</p>
    {published.option_verified !== true && <p className="mt-2 text-[11px] leading-6 text-amber-900">The source does not confirm Growth or IDCW, or exact starting dates. Use this as source context; it cannot establish this holding’s exact-option outperformance.</p>}
    <div role="region" aria-label="AMC-reported trailing fund and benchmark performance" tabIndex={0} className="mt-3 overflow-x-auto rounded-xl border border-blue-100 bg-white">
      <table className="w-full min-w-[430px] text-left text-xs"><caption className="sr-only">Published endpoint returns, not independently calculated matched TRI history.</caption><thead className="bg-slate-50 text-[10px] text-slate-500"><tr>{["Published period", "Plan", "Benchmark", "Difference"].map((label) => <th key={label} className="px-3 py-3 font-medium">{label}</th>)}</tr></thead><tbody>{returns.map((row) => <tr key={row.period} className="border-t border-slate-100"><th scope="row" className="px-3 py-3 uppercase text-slate-700">{row.period}<span className="mt-1 block text-[9px] font-normal normal-case text-slate-400">{row.annualized ? "AMC annualized" : "AMC period return"}</span></th><td className="px-3 py-3 tabular-nums">{percentage(row.fund_return_pct)}</td><td className="px-3 py-3 tabular-nums">{percentage(row.benchmark_return_pct)}</td><td className="px-3 py-3 tabular-nums">{observationNumber(row.excess_return_pp) != null ? percentage(row.excess_return_pp, 2, " pp") : "See source"}</td></tr>)}</tbody></table>
    </div>
    <p className="mt-3 text-[11px]"><SourceLink url={published.source_url}>Read the AMC comparison and its basis</SourceLink></p>
    {!!published.limitations?.length && <ul className="mt-3 list-disc space-y-1 pl-4 text-[10px] leading-6 text-slate-500">{published.limitations.map((item) => <li key={item}>{item}</li>)}</ul>}
  </details>;
}

function GrowthChart({ fund }: { fund: MutualFundAnalysis }) {
  const growth = useMemo(() => fundGrowth(fund), [fund]);
  const [inspection, setInspection] = useState<number | null>(null);
  const points = growth.points;
  if (points.length < 2) return null;
  const matched = growth.basis === "matched_benchmark";
  const width = 660, height = 220, pad = { left: 44, right: 20, top: 20, bottom: 30 };
  const values = points.flatMap((point) => point.benchmark == null ? [point.fund] : [point.fund, point.benchmark]);
  const floor = Math.min(...values) * .97, ceiling = Math.max(...values) * 1.03;
  const earliest = Date.parse(points[0].date), latest = Date.parse(points[points.length - 1].date);
  const x = (index: number) => pad.left + (Date.parse(points[index].date) - earliest) / Math.max(1, latest - earliest) * (width - pad.left - pad.right);
  const y = (value: number) => pad.top + (ceiling - value) / Math.max(1, ceiling - floor) * (height - pad.top - pad.bottom);
  const path = (key: "fund" | "benchmark") => points.map((point, index) => `${index ? "L" : "M"}${x(index).toFixed(2)},${y(point[key]!).toFixed(2)}`).join(" ");
  const cursor = inspection == null ? points.length - 1 : Math.min(inspection, points.length - 1);
  const point = points[cursor];
  return <figure className="mt-4 rounded-2xl border border-slate-200 bg-white p-3 sm:p-4">
    <figcaption className="flex flex-wrap items-center justify-between gap-2 text-xs"><span className="font-semibold text-slate-800">Growth of 100 · {matched ? "matched fund and TRI" : "Fund NAV only"}</span><span className="text-[10px] text-slate-500">{dateRange(points[0].date, points[points.length - 1].date)}</span></figcaption>
    <svg viewBox={`0 0 ${width} ${height}`} className="mt-3 h-auto w-full" role="img" aria-label={`${fund.scheme_name}, ${matched ? "with matched total-return benchmark, both" : "fund NAV only,"} rebased to 100 on ${points[0].date}`}>
      <line x1={pad.left} x2={width - pad.right} y1={y(100)} y2={y(100)} stroke="#cbd5e1" strokeDasharray="4 4" /><text x={pad.left - 7} y={y(100) + 4} textAnchor="end" fontSize="10" fill="#64748b">100</text>
      {matched && <path d={path("benchmark")} fill="none" stroke="#64748b" strokeWidth="2" strokeDasharray="5 3" />}<path d={path("fund")} fill="none" stroke="#0f766e" strokeWidth="2.5" />
      <line x1={x(cursor)} x2={x(cursor)} y1={pad.top} y2={height - pad.bottom} stroke="#99b9b2" /><circle cx={x(cursor)} cy={y(point.fund)} r="4" fill="#0f766e" />{point.benchmark != null && <circle cx={x(cursor)} cy={y(point.benchmark)} r="4" fill="#64748b" />}
      <text x={pad.left} y={height - 5} fontSize="10" fill="#64748b">{points[0].date}</text><text x={width - pad.right} y={height - 5} textAnchor="end" fontSize="10" fill="#64748b">{points[points.length - 1].date}</text>
    </svg>
    <label className="mt-2 block text-[10px] font-medium text-slate-500">Inspect an observation<input type="range" min={0} max={points.length - 1} value={cursor} onChange={(event) => setInspection(Number(event.target.value))} className="mt-2 w-full accent-teal-700" aria-label={`Inspect growth date for ${fund.scheme_name}`} /></label>
    <div aria-live="polite" className="mt-2 flex flex-wrap gap-x-5 gap-y-2 text-[11px]"><span className="text-slate-500">{point.date}</span><span className="font-semibold text-teal-800">Fund {point.fund.toFixed(2)}</span>{point.benchmark != null && <span className="text-slate-600">TRI {point.benchmark.toFixed(2)}</span>}</div>
    <p className="mt-3 text-[10px] leading-5 text-slate-500">{matched ? "Both series use the same observation dates." : "Actual Growth-option NAV observations. No benchmark series has been substituted."} NAV includes scheme expenses. This is historical fund growth, not your cashflow return or a forecast.</p>
  </figure>;
}

function Finding({ finding, sources, fundNames, fund }: { finding: MutualFundFinding; sources: MutualFundIntelligence["sources"]; fundNames: string[]; fund?: MutualFundAnalysis }) {
  const [principles, setPrinciples] = useState<SkillPrinciple[]>([]);
  const [verification, setVerification] = useState<"idle" | "loading" | "loaded" | "unavailable">("idle");
  async function inspect() {
    if (verification !== "idle") return;
    setVerification("loading");
    try {
      const ids = [...new Set(finding.principle_ids || [])];
      const loaded = await Promise.all(ids.map((id) => apiRequest<SkillPrinciple>(`/knowledge/principles/${encodeURIComponent(id)}`)));
      if (!loaded.every((principle, index) => principle.id === ids[index] && principle.excerpt && principle.skill_sha256)) throw new Error("Unverifiable principle");
      setPrinciples(loaded); setVerification("loaded");
    } catch { setVerification("unavailable"); }
  }
  const facts = fundFindingFacts(finding, fund);
  const refs = (sources || []).filter((source) => finding.source_ids?.includes(source.id));
  return <article id={`mf-finding-${finding.id}`} className="min-w-0 rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
    {!!fundNames.length && <p className="mb-3 break-words text-[10px] font-semibold leading-5 text-teal-800">{fundNames.join(" / ")}</p>}
    <h4 className="text-sm font-semibold text-slate-900">{finding.title}</h4><p className="mt-3 text-xs leading-6 text-slate-600">{finding.detail}</p>
    {!!facts.length && <dl className="mt-3 grid gap-2 rounded-xl bg-slate-50 p-3 sm:grid-cols-2">{facts.slice(0, 4).map(([label, value]) => <div key={label} className="min-w-0"><dt className="text-[10px] capitalize text-slate-500">{label}</dt><dd className="mt-1 break-words text-xs font-semibold text-slate-800">{value}</dd></div>)}</dl>}
    {finding.suggested_action && <p className="mt-3 rounded-xl bg-[#f2f8f4] p-3 text-xs leading-6 text-teal-900"><strong>Next step:</strong> {finding.suggested_action}</p>}
    {finding.proof ? <ReviewProofPanel proof={finding.proof} /> : <details className="mt-4 rounded-xl border border-slate-200 p-3" onToggle={(event) => { if (event.currentTarget.open) void inspect(); }}>
      <summary className="cursor-pointer text-xs font-semibold text-slate-700">Sources and applied skill principles</summary>
      {verification === "loading" && <p className="mt-3 text-xs text-slate-500">Checking the cited skill sections…</p>}
      {verification === "unavailable" && <p className="mt-3 text-xs leading-6 text-amber-900">The cited section could not be loaded. No quotation has been inferred.</p>}
      {principles.map((principle) => <div key={principle.id} className="mt-3 rounded-xl bg-teal-50/60 p-3"><p className="text-xs font-semibold text-teal-900">{principle.title} · {principle.section}</p><blockquote className="mt-2 text-xs leading-6 text-slate-700">“{principle.excerpt}”</blockquote><p className="mt-2 break-words text-[10px] leading-5 text-slate-500">{principle.path} · lines {principle.line_start}–{principle.line_end}</p><ul className="mt-3 space-y-2">{principle.source_refs?.map((source) => <li key={source.id} className="text-[10px] leading-5"><SourceLink url={source.url}>{source.publisher} · {source.title}</SourceLink></li>)}</ul></div>)}
      {!!refs.length && <ul className="mt-4 space-y-2">{refs.map((source) => <li key={source.id} className="text-[11px] leading-6"><SourceLink url={source.url}>{source.title}</SourceLink>{source.observed_on && <span className="ml-2 text-slate-500">{source.observed_on}</span>}</li>)}</ul>}
      {hasRecordedEvidence(finding.evidence) && <details className="mt-3"><summary className="cursor-pointer text-[10px] text-slate-500">Technical evidence receipt</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-3 font-mono text-[10px] leading-5 text-slate-600">{jsonEvidence(finding.evidence)}</pre></details>}
    </details>}
  </article>;
}

function PairObservationDetails({ row, kind }: { row: MutualFundOverlap | MutualFundCorrelation; kind: "overlap" | "correlation" }) {
  const overlap = kind === "overlap" ? row as MutualFundOverlap : null;
  const correlation = kind === "correlation" ? row as MutualFundCorrelation : null;
  const common = overlap && (Array.isArray(overlap.common_securities) ? overlap.common_securities.length : observationNumber(overlap.common_securities));
  const fields: Array<[string, string]> = overlap ? [
    ["Identified weights in the two funds", `${percentage(overlap.coverage_a_pct)} / ${percentage(overlap.coverage_b_pct)}`],
    ["Disclosure dates", overlap.observed_on_a && overlap.observed_on_b ? `${overlap.observed_on_a} / ${overlap.observed_on_b}` : "See source receipt"],
    ...(common == null ? [] : [["Shared identified securities", String(common)] as [string, string]]),
  ] : [
    ["Common return observations", `${correlation?.observations} ${correlation?.frequency || "recorded"} returns`],
    ["Observed window", dateRange(correlation?.start_date, correlation?.end_date)],
  ];
  return <div className="mt-3"><p className="text-xs leading-6 text-slate-600">{pairStatusExplanation(row.status)}</p><dl className="mt-3 grid gap-3 sm:grid-cols-2">{fields.filter(([, value]) => value).map(([label, value]) => <div key={label}><dt className="text-[10px] text-slate-500">{label}</dt><dd className="mt-1 text-[11px] font-semibold text-slate-800">{value}</dd></div>)}</dl>
    <details className="mt-3 rounded-xl border border-teal-100 bg-white p-3"><summary className="cursor-pointer text-[11px] font-semibold text-slate-700">Calculation and source-coverage receipt</summary>{row.method && <p className="mt-3 text-[10px] leading-6 text-slate-500">{row.method}</p>}<pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-[10px] leading-5 text-slate-600">{jsonEvidence(row)}</pre></details>
  </div>;
}

function Convergence({ data }: { data: MutualFundIntelligence }) {
  const overlaps = measuredFundPairs(data.overlaps || [], "overlap");
  const correlations = measuredFundPairs(data.correlations || [], "correlation");
  const [kind, setKind] = useState<"overlap" | "correlation">(overlaps.length ? "overlap" : "correlation");
  const [selected, setSelected] = useState<Partial<Record<"overlap" | "correlation", string>>>({});
  const mode = kind === "overlap" && !overlaps.length ? "correlation" : kind === "correlation" && !correlations.length ? "overlap" : kind;
  const pairs = mode === "overlap" ? overlaps : correlations;
  const key = (row: MutualFundOverlap | MutualFundCorrelation) => [row.fund_a, row.fund_b].sort().join("|");
  const row = pairs.find((pair) => key(pair) === selected[mode]) || pairs[0];
  if (!row) return null;
  const name = (id: string) => data.funds.find((fund) => fund.fund_id === id)?.scheme_name || id;
  const value = pairMetric(row, mode)!;
  return <div className="mt-4">
    <div className="flex flex-wrap gap-2" role="group" aria-label="Choose convergence measurement">{(["overlap", "correlation"] as const).filter((measurement) => measurement === "overlap" ? overlaps.length : correlations.length).map((measurement) => <button key={measurement} type="button" aria-pressed={mode === measurement} onClick={() => setKind(measurement)} className={`rounded-xl border px-4 py-2 text-xs font-semibold ${mode === measurement ? "border-teal-600 bg-teal-50 text-teal-900" : "border-slate-200 bg-white text-slate-500"}`}>{measurement === "overlap" ? "Holdings overlap" : "Return correlation"}</button>)}</div>
    <p className="mt-3 text-xs leading-6 text-slate-500">{mode === "overlap" ? "Shared disclosed securities, measured using the smaller full-NAV weight of each security." : "Aligned completed-month NAV returns measure historical co-movement independently of holdings overlap."}</p>
    <label htmlFor="mf-measured-pair" className="mt-4 block text-xs font-medium text-slate-700">Inspect a measured pair<select id="mf-measured-pair" value={key(row)} onChange={(event) => setSelected((current) => ({ ...current, [mode]: event.target.value }))} className="mt-2 w-full min-w-0 rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-800">{pairs.map((pair) => <option key={key(pair)} value={key(pair)}>{name(pair.fund_a)} / {name(pair.fund_b)}</option>)}</select></label>
    <div aria-live="polite" className="mt-4 rounded-xl border border-teal-100 bg-[#f4f9f6] p-4"><p className="text-xs font-semibold text-slate-800">{name(row.fund_a)} ↔ {name(row.fund_b)}</p><p className="mt-2 text-xl font-semibold text-teal-900">{mode === "overlap" ? `${value.toFixed(2)}% weighted overlap` : `${value.toFixed(3)} return correlation`}</p><PairObservationDetails row={row} kind={mode} /></div>
    <p className="mt-3 text-[10px] leading-5 text-slate-500">{overlaps.length} measured holdings pairs · {correlations.length} measured return pairs. Unmeasured pairs are excluded; missing evidence is never zero.</p>
  </div>;
}

function FundDetail({ fund, sources }: { fund: MutualFundAnalysis; sources: MutualFundIntelligence["sources"] }) {
  const metrics: Array<[string, unknown]> = [["Annualized volatility", fund.metrics?.volatility_pct], ["Maximum drawdown", fund.metrics?.max_drawdown_pct], ["Investor XIRR", fund.metrics?.xirr_pct], ["Tracking error", fund.metrics?.tracking_error_pct], ["Disclosed plan TER", fund.ter_percent]];
  const knownMetrics = metrics.filter(([, value]) => observationNumber(value) != null);
  const refs = (sources || []).filter((source) => Array.isArray(fund.source_ids) && fund.source_ids.includes(source.id));
  const riskWindow = fund.metrics?.risk_window as { start_date?: string; end_date?: string } | undefined;
  return <div className="mt-4">
    <GrowthChart fund={fund} />
    {!!knownMetrics.length && <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">{knownMetrics.map(([label, value]) => <div key={label} className="rounded-xl bg-white p-3"><dt className="text-[10px] text-slate-500">{label}</dt><dd className="mt-1 text-sm font-semibold tabular-nums text-slate-900">{percentage(value)}</dd></div>)}</dl>}
    {riskWindow?.start_date && riskWindow?.end_date && <p className="mt-2 text-[10px] leading-5 text-slate-500">Historical risk window: {dateRange(riskWindow.start_date, riskWindow.end_date)}. Volatility uses supported daily observations; drawdown is the largest observed peak-to-trough decline.</p>}
    {fund.metrics?.rolling && fund.metrics.rolling.observations > 0 && observationNumber(fund.metrics.rolling.outperformance_pct) != null && <p className="mt-3 text-[11px] leading-6 text-slate-600">Rolling {fund.metrics.rolling.window_years}-year windows: {fund.metrics.rolling.observations} observations; {percentage(fund.metrics.rolling.outperformance_pct)} exceeded the matched benchmark. Overlapping windows are not independent.</p>}
    {typeof fund.exit_load === "string" && fund.exit_load.trim() && <p className="mt-3 text-[11px] leading-6 text-slate-600"><strong>Disclosed exit terms:</strong> {fund.exit_load}</p>}
    {fund.disclosure?.available && <p className="mt-3 text-[11px] leading-6 text-slate-600">Disclosed holdings: {fund.disclosure.observed_on}{fund.disclosure.stale ? " · review due" : ""}; identified full-NAV weight {percentage(fund.disclosure.coverage_pct)}. <SourceLink url={fund.disclosure.source_url}>Portfolio source</SourceLink></p>}
    {!!refs.length && <p className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-[10px]">{refs.map((source) => <span key={source.id}><SourceLink url={source.url}>{source.title}</SourceLink>{source.observed_on ? ` · ${source.observed_on}` : ""}</span>)}</p>}
    <PublishedComparison fund={fund} />
  </div>;
}

function CoverageDetails({ data, showDataLink }: { data: MutualFundIntelligence; showDataLink: boolean }) {
  const warnings = [...new Set([...(data.data_quality?.warnings || []), ...(data.data_quality?.missing || [])])];
  const missingChecks = [...new Set((data.action_checks?.funds || []).flatMap((check) => check.missing_information || []))];
  const additional = [...new Map([...(data.findings || []), ...data.funds.flatMap((fund) => fund.findings || [])].map((finding) => [finding.id, finding])).values()].filter((finding) => finding.type.endsWith("_gap"));
  const missingThemes = [...new Set(additional.map((finding) => finding.title))];
  return <details id="mf-source-coverage" className="m-5 rounded-xl border border-slate-200 bg-slate-50/50 p-4 sm:mx-7">
    <summary className="cursor-pointer text-xs font-semibold text-slate-700">Data coverage, sources and switch checks</summary>
    <p className="mt-3 text-xs leading-6 text-slate-600">The main view shows measured evidence. Benchmark-relative conclusions require the right TRI; switching costs require verified tax lots and applicable exit terms. Missing values are withheld.</p>
    {!!warnings.length && <ul className="mt-3 list-disc space-y-2 pl-4 text-[11px] leading-6 text-slate-600">{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
    {!!missingThemes.length && <p className="mt-3 text-[11px] leading-6 text-slate-500">Source checks: {missingThemes.join("; ")}.</p>}
    {!!missingChecks.length && <div className="mt-4"><h3 className="text-xs font-semibold text-slate-800">Before a fund switch</h3><ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] leading-6 text-slate-600">{missingChecks.map((item) => <li key={item}>{item}</li>)}</ul><Link href="/tax" className="mt-2 inline-block text-xs font-semibold text-teal-800 underline underline-offset-4">Review recorded tax lots ↗</Link></div>}
    {!!data.sources?.length && <div className="mt-4"><h3 className="text-xs font-semibold text-slate-800">Dated sources ({data.sources.length})</h3><ul className="mt-3 space-y-3">{data.sources.map((source) => <li key={source.id} className="text-[11px] leading-6"><SourceLink url={source.url}>{source.title}</SourceLink>{source.observed_on && <span className="ml-2 text-slate-500">{source.observed_on}</span>}{source.verification && <p className="text-[10px] text-slate-500">{source.verification}</p>}</li>)}</ul></div>}
    {showDataLink && <Link href="/mutual-funds#mf-evidence-imports" className="mt-4 inline-block text-xs font-semibold text-teal-800 underline underline-offset-4">Manage official source evidence ↗</Link>}
    {(hasRecordedEvidence(data.data_quality?.budget) || hasRecordedEvidence(data.data_quality?.psychometrics)) && <details className="mt-4 rounded-xl border border-slate-200 bg-white p-3"><summary className="cursor-pointer text-[11px] font-semibold text-slate-700">Recorded budget and psychometric constraints</summary><pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words font-mono text-[10px] leading-5 text-slate-600">{jsonEvidence({ budget: data.data_quality?.budget, psychometrics: data.data_quality?.psychometrics })}</pre></details>}
  </details>;
}

export function MutualFundPanel({ data, showDataLink = true, context }: { data?: MutualFundIntelligence | null; showDataLink?: boolean; context?: "fire" }) {
  const [period, setPeriod] = useState("3y");
  const [selectedFund, setSelectedFund] = useState<string | null>(null);
  const [allExposure, setAllExposure] = useState(false);
  if (!data?.result_version) return null;
  const funds = data.funds || [];
  const active = funds.find((fund) => fund.fund_id === selectedFund) || funds.find((fund) => fundGrowth(fund).points.length >= 2) || funds[0];
  const allFindings = [...new Map([...(data.findings || []), ...funds.flatMap((fund) => fund.findings || [])].map((finding) => [finding.id, finding])).values()];
  const findings = focusedFundFindings(allFindings);
  const exposure = data.combined_exposure;
  const measuredPairs = measuredFundPairs(data.overlaps || [], "overlap").length + measuredFundPairs(data.correlations || [], "correlation").length;
  const benchmarkRows = funds.some((fund) => observationNumber(fund.metrics?.returns?.find((row) => row.period === period)?.benchmark_return_pct) != null);
  const performanceFunds = funds.filter((fund) => observationNumber(fund.metrics?.returns?.find((row) => row.period === period)?.fund_return_pct) != null);
  const navCount = funds.filter((fund) => (fund.nav_history || []).some((row) => observationNumber(row.value) != null && row.value > 0)).length;
  const disclosureCount = funds.filter((fund) => fund.disclosure?.available && !fund.disclosure.stale).length;
  const triCount = funds.filter((fund) => fund.benchmark?.available).length;
  return <section id="decision-mutual-funds" aria-labelledby="mf-title" className="decision-anchor overflow-hidden rounded-[28px] border border-slate-200 bg-white">
    <div className="border-b border-slate-100 bg-[#f4f9f6] p-5 sm:p-7"><p className="text-[10px] font-semibold uppercase tracking-[.18em] text-teal-700">Mutual Fund Agent</p><h2 id="mf-title" className="mt-2 text-xl font-semibold tracking-tight text-slate-900">Your funds, in focus.</h2><p className="mt-2 max-w-3xl text-xs leading-6 text-slate-600">Actual NAV performance, measured fund similarity and the securities you own beneath the funds.</p><p className="mt-3 text-[11px] leading-6 text-slate-500">As of {data.as_of || "the recorded observation"} · {funds.length} funds · {navCount} NAV histories/quotes · {disclosureCount} current holdings disclosures · {triCount} matched TRI sources. <a href="#mf-source-coverage" className="font-semibold text-teal-800 underline underline-offset-4">Source coverage</a></p></div>
    {context === "fire" && <p className="m-5 rounded-xl border border-teal-100 bg-teal-50/60 p-4 text-xs leading-6 text-teal-900 sm:mx-7">Historical fund evidence informs the FIRE review. It does not add assets or a second allocation; the saved goal retains its own budget and return assumptions.</p>}
    {!!findings.length && <div className="border-b border-slate-100 p-5 sm:p-7"><h3 className="text-base font-semibold text-slate-900">Focus on {findings.length === 1 ? "one priority" : `these ${findings.length} priorities`}</h3><p className="mt-2 text-xs leading-6 text-slate-500">One supported finding per question. The central coordinator reconciles these with your other agents.</p><div className="mt-4 grid gap-4 lg:grid-cols-2">{findings.map((finding) => <Finding key={finding.id} finding={finding} sources={data.sources} fundNames={findingFundNames(finding.fund_id, funds)} fund={funds.find((row) => row.fund_id === finding.fund_id)} />)}</div></div>}
    {!funds.length ? <div className="p-5 sm:p-7"><p className="text-sm leading-7 text-slate-600">Add your actual fund holdings to compare their performance and portfolio role.</p><Link href="/onboarding/documents?return=/mutual-funds" className="mt-4 inline-block text-sm font-semibold text-teal-800 underline underline-offset-4">Add a mutual fund statement ↗</Link></div> : <>
      <div className="p-5 sm:p-7"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-base font-semibold text-slate-900">Actual fund performance</h3><p className="mt-2 text-xs leading-6 text-slate-500">Growth-option NAV returns, net of scheme expenses. Select a fund for its dated chart and risk history.</p></div><div className="flex gap-1 rounded-xl bg-slate-100 p-1" role="group" aria-label="Performance comparison period">{["1y", "3y", "5y"].map((value) => <button key={value} type="button" aria-pressed={period === value} onClick={() => setPeriod(value)} className={`rounded-lg px-3 py-2 text-xs font-semibold ${period === value ? "bg-white text-teal-900 shadow-sm" : "text-slate-500"}`}>{value.toUpperCase()}</button>)}</div></div>
        {!!performanceFunds.length && <div role="region" aria-label="Fund benchmark comparisons" tabIndex={0} className="mt-4 overflow-x-auto rounded-xl border border-slate-200"><table className={`w-full ${benchmarkRows ? "min-w-[680px]" : "min-w-[480px]"} text-left text-xs`}><caption className="sr-only">Measured fund returns. Benchmark columns appear only when at least one matched total-return comparison is supported.</caption><thead className="bg-slate-50 text-[10px] text-slate-500"><tr>{["Fund / exact variant", `${period.toUpperCase()} ${period === "1y" ? "return" : "CAGR"}`, "Observation dates", ...(benchmarkRows ? ["Matched TRI", "Excess (pp)"] : [])].map((label) => <th key={label} className="px-4 py-3 font-medium">{label}</th>)}</tr></thead><tbody>{performanceFunds.map((fund) => { const value = fund.metrics.returns.find((row) => row.period === period)!; return <tr key={fund.fund_id} className={`border-t border-slate-100 align-top ${active?.fund_id === fund.fund_id ? "bg-teal-50/40" : ""}`}><td className="max-w-xs px-4 py-4"><button type="button" onClick={() => setSelectedFund(fund.fund_id)} className="text-left text-xs font-semibold text-teal-900 underline decoration-teal-200 underline-offset-4">{fund.scheme_name}</button><p className="mt-1 text-[10px] capitalize text-slate-500">{fund.plan} · {fund.option}</p></td><td className="whitespace-nowrap px-4 py-4 font-semibold tabular-nums text-slate-800">{percentage(value.fund_return_pct)}</td><td className="px-4 py-4 text-[10px] leading-5 text-slate-500">{dateRange(value.start_date, value.end_date)}</td>{benchmarkRows && <><td className="px-4 py-4 text-[10px] leading-5 text-slate-600">{observationNumber(value.benchmark_return_pct) != null ? <>{percentage(value.benchmark_return_pct)}<span className="mt-1 block text-slate-500">{fund.benchmark?.name}</span></> : <a href="#mf-source-coverage" className="underline underline-offset-4">Source needed</a>}</td><td className="whitespace-nowrap px-4 py-4 tabular-nums text-slate-700">{observationNumber(value.excess_return_pp) != null ? percentage(value.excess_return_pp, 2, " pp") : "—"}</td></>}</tr>; })}</tbody></table></div>}
        {!!performanceFunds.length && <p className="mt-3 text-[10px] leading-5 text-slate-500">{benchmarkRows ? "Matched comparisons use the same dates and total-return basis." : "Fund NAV only: benchmark-relative judgements are withheld until a matched TRI is available."} CAGR is a fund history measure; investor XIRR requires complete dated cashflows.</p>}
        {active && <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50/40 p-4 sm:p-5"><label htmlFor="mf-inspect-fund" className="text-xs font-semibold text-slate-700">Inspect one fund</label><select id="mf-inspect-fund" value={active.fund_id} onChange={(event) => setSelectedFund(event.target.value)} className="mt-2 w-full min-w-0 rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-800">{funds.map((fund) => <option key={fund.fund_id} value={fund.fund_id}>{fund.scheme_name}</option>)}</select><p className="mt-2 break-words text-[10px] text-slate-500">{active.isin} · {active.identity_status} identity</p><FundDetail key={active.fund_id} fund={active} sources={data.sources} /></div>}
      </div>
      {!!measuredPairs && <div className="border-t border-slate-100 p-5 sm:p-7"><h3 className="text-base font-semibold text-slate-900">How similar are your funds?</h3><Convergence data={data} /></div>}
      {!!exposure?.securities?.length && <div className="border-t border-slate-100 p-5 sm:p-7"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-base font-semibold text-slate-900">Your largest underlying positions</h3>{observationNumber(exposure.known_coverage_pct) != null && <span className="text-[10px] text-slate-500">Known coverage {percentage(exposure.known_coverage_pct)}</span>}</div><p className="mt-2 text-xs leading-6 text-slate-500">Direct stocks plus identified fund holdings, counted once per security. Coverage is partial where fund disclosures are unavailable.</p><div role="region" aria-label="Combined direct and mutual fund exposure" tabIndex={0} className="mt-4 overflow-x-auto rounded-xl border border-slate-200"><table className="w-full min-w-[520px] text-left text-xs"><thead className="bg-slate-50 text-[10px] text-slate-500"><tr>{["Underlying security", "Direct stocks", "Through funds", "Portfolio weight"].map((label) => <th key={label} className="px-4 py-3 font-medium">{label}</th>)}</tr></thead><tbody>{exposure.securities.slice(0, allExposure ? undefined : 5).map((security) => <tr key={security.isin} className="border-t border-slate-100"><th scope="row" className="px-4 py-3 text-left font-medium text-slate-800">{security.name}</th><td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-600">{money(security.direct_value)}</td><td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-600">{money(security.mf_value)}</td><td className="whitespace-nowrap px-4 py-3 tabular-nums text-teal-800">{percentage(security.portfolio_weight_pct)}</td></tr>)}</tbody></table></div>{exposure.securities.length > 5 && <button type="button" aria-expanded={allExposure} onClick={() => setAllExposure((value) => !value)} className="mt-3 text-xs font-semibold text-teal-800 underline underline-offset-4">{allExposure ? "Show the top five" : `Show all ${exposure.securities.length} identified securities`}</button>}{observationNumber(exposure.unmapped_value) != null && Number(exposure.unmapped_value) > 0 && <p className="mt-3 text-[10px] leading-5 text-slate-500">Not yet mapped to underlying securities: {money(exposure.unmapped_value)}. This amount remains part of your portfolio.</p>}</div>}
    </>}
    <CoverageDetails data={data} showDataLink={showDataLink} />
  </section>;
}
