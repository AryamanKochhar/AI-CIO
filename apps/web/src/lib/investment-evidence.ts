import type { MutualFundAnalysis, MutualFundCorrelation, MutualFundFinding, MutualFundOverlap, OrchestrationAgent } from "@ai-cio/contracts";

/** Unknown, empty and non-finite observations stay unknown, including in charts. */
export function observationNumber(value: unknown): number | null {
  if (value == null || typeof value === "boolean" || (typeof value === "string" && !value.trim())) return null;
  if (typeof value !== "string" && typeof value !== "number") return null;
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
}

export function percentage(value: unknown, digits = 2, suffix = "%"): string {
  const number = observationNumber(value);
  return number == null ? "Unavailable" : `${number.toFixed(digits)}${suffix}`;
}

/** External evidence can link only to web sources. Relative project anchors are separate. */
export function evidenceUrl(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : undefined; }
  catch { return undefined; }
}

export function durationLabel(value: unknown): string {
  const ms = observationNumber(value);
  if (ms == null || ms < 0) return "Duration not recorded";
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function pairObservation<T extends MutualFundOverlap | MutualFundCorrelation>(rows: T[], a: string, b: string): T | undefined {
  return rows.find((row) => (row.fund_a === a && row.fund_b === b) || (row.fund_a === b && row.fund_b === a));
}

export function pairMetric(row: MutualFundOverlap | MutualFundCorrelation | undefined, kind: "overlap" | "correlation"): number | null {
  if (!row || !["supported", "limited_history", "partial_coverage", "complete", "available", "verified", "partial", "ok", "calculated"].includes(row.status)) return null;
  const value = observationNumber(kind === "overlap" ? (row as MutualFundOverlap).weighted_overlap_pct : (row as MutualFundCorrelation).correlation);
  if (value == null || (kind === "overlap" ? value < 0 || value > 100 : value < -1 || value > 1)) return null;
  return value;
}

export function findingFundNames(fundId: string | null | undefined, funds: Array<Pick<MutualFundAnalysis, "fund_id" | "scheme_name">>): string[] {
  if (!fundId) return [];
  const exact = funds.find((fund) => fund.fund_id === fundId);
  if (exact) return [exact.scheme_name];
  // Pair IDs contain complete fund keys. Unresolved keys themselves can contain
  // colons, so splitting a pair on every colon would misidentify the schemes.
  return [...new Set(funds.filter((fund) => fundId.startsWith(`${fund.fund_id}:`) || fundId.endsWith(`:${fund.fund_id}`)).map((fund) => fund.scheme_name))];
}

export function pairStatusExplanation(status?: string): string {
  return ({
    unavailable: "A required source is unavailable. Missing evidence does not establish zero overlap or zero correlation.",
    stale_disclosure: "The snapshots exceed the current application freshness window. Obtain current official disclosures before using an overlap estimate.",
    unaligned_disclosure_dates: "The portfolio snapshots have incompatible observation dates. Obtain aligned disclosures before comparing their holdings.",
    partial_coverage: "This is measured overlap among identified disclosed securities. Partial coverage makes it a lower bound, not a complete diversification assessment.",
    limited_history: "The calculation has limited common monthly history. The estimate can be unstable and does not predict future behaviour.",
    distribution_adjustment_required: "A total-return comparison for these options needs verified distribution adjustments. Raw NAV is not an equivalent return.",
    insufficient_history: "There are not enough supported common return observations to calculate this comparison.",
    zero_variance: "A return series has no measured variation in this window, so its correlation is undefined.",
    supported: "This observation meets the calculation’s data requirements. Historical overlap and co-movement do not guarantee future diversification.",
  } as Record<string, string>)[status || ""] || "Review the recorded source coverage, observation dates and calculation limits before interpreting this pair.";
}

/** Join dates before rebasing both series to 100; never align by array position. */
export function benchmarkGrowth(fund: Pick<MutualFundAnalysis, "nav_history" | "benchmark_history"> & Partial<Pick<MutualFundAnalysis, "option" | "identity_status">>) {
  if ((fund.option != null && fund.option !== "growth") || (fund.identity_status != null && fund.identity_status !== "verified")) return [];
  function validSeries(rows: Array<{ date: string; value: number }> = []) {
    return new Map(rows.filter((row) => /^\d{4}-\d{2}-\d{2}$/.test(row.date) && observationNumber(row.value) != null && row.value > 0).map((row) => [row.date, row.value]));
  }
  const nav = validSeries(fund.nav_history);
  const benchmark = validSeries(fund.benchmark_history);
  const common = [...nav.keys()].filter((date) => benchmark.has(date)).sort();
  if (common.length < 2) return [];
  const firstFund = nav.get(common[0])!;
  const firstBenchmark = benchmark.get(common[0])!;
  return common.map((date) => ({ date, fund: nav.get(date)! / firstFund * 100, benchmark: benchmark.get(date)! / firstBenchmark * 100 }));
}

/** A real NAV series remains useful without a TRI; the caller must label its basis. */
export function fundGrowth(fund: Pick<MutualFundAnalysis, "nav_history" | "benchmark_history" | "option" | "identity_status">) {
  const matched = benchmarkGrowth(fund);
  if (matched.length >= 2) return { basis: "matched_benchmark" as const, points: matched.map((point) => ({ ...point, benchmark: point.benchmark as number | null })) };
  if (fund.identity_status !== "verified" || fund.option !== "growth") return { basis: "fund_nav_only" as const, points: [] };
  const values = new Map<string, number>();
  const conflicts = new Set<string>();
  for (const row of fund.nav_history || []) {
    const value = observationNumber(row.value);
    const parsed = new Date(`${row.date}T00:00:00Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(row.date) || !Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== row.date || value == null || value <= 0) continue;
    if (values.has(row.date) && values.get(row.date) !== value) conflicts.add(row.date);
    values.set(row.date, value);
  }
  const dates = [...values.keys()].filter((date) => !conflicts.has(date)).sort();
  if (dates.length < 2) return { basis: "fund_nav_only" as const, points: [] };
  const first = values.get(dates[0])!;
  return { basis: "fund_nav_only" as const, points: dates.map((date) => ({ date, fund: values.get(date)! / first * 100, benchmark: null })) };
}

/** Empty payloads are not evidence; measured zero and recorded false remain facts. */
export function hasRecordedEvidence(value: unknown): boolean {
  if (value == null || (typeof value === "string" && !value.trim())) return false;
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "boolean" || typeof value === "string") return true;
  if (Array.isArray(value)) return value.some(hasRecordedEvidence);
  return typeof value === "object" && Object.values(value).some(hasRecordedEvidence);
}

/** Present a bounded set of genuinely supported questions, not one repeated card per fund. */
export function focusedFundFindings(findings: MutualFundFinding[], limit = 3): MutualFundFinding[] {
  const priorities: Record<string, [string, number]> = {
    persistent_underperformance: ["relative_performance", 100], psychometric_suitability: ["risk_fit", 95],
    goal_horizon_review: ["goal_fit", 90], overlap_review: ["holdings_overlap", 85],
    correlation_review: ["return_correlation", 80], regular_plan_cost_review: ["plan_cost", 70],
    persistent_outperformance: ["relative_performance", 60],
  };
  const candidates = findings.filter((finding) => priorities[finding.type] && (
    hasRecordedEvidence(finding.evidence) || finding.proof?.facts.some((fact) => hasRecordedEvidence(fact.value))
  ));
  candidates.sort((a, b) => priorities[b.type][1] - priorities[a.type][1]);
  const themes = new Set<string>();
  return candidates.filter((finding) => {
    const theme = priorities[finding.type][0];
    if (themes.has(theme)) return false;
    themes.add(theme); return true;
  }).slice(0, Math.max(0, limit));
}

/** Use financial labels for primary facts; internal IDs and object paths stay in receipts. */
export function fundFindingFacts(finding: MutualFundFinding, fund?: Pick<MutualFundAnalysis, "weight_pct">): Array<[string, string]> {
  const evidence = finding.evidence || {}, facts: Array<[string, string]> = [];
  const add = (label: string, value: unknown, format: (number: number) => string = String) => {
    const number = observationNumber(value);
    if (number != null) facts.push([label, format(number)]);
  };
  const pct = (value: number) => `${value.toFixed(2)}%`;
  const score = (value: number) => `${Number(value.toFixed(1))} / 100`;
  if (finding.type === "goal_horizon_review") {
    const goals = Array.isArray(evidence.goal_horizons) ? evidence.goal_horizons.filter((goal): goal is Record<string, unknown> => !!goal && typeof goal === "object" && !Array.isArray(goal)) : [];
    const goal = goals.find((row) => observationNumber(row.years) != null);
    if (goal) {
      if (typeof goal.name === "string" && goal.name.trim()) facts.push(["Recorded goal", goal.name]);
      const years = observationNumber(goal.years)!;
      const days = Math.max(1, Math.round(years * 365.25)), months = Math.round(years * 12);
      facts.push(["Time until goal", years <= 0 ? "At or past its target date" : days < 60 ? `About ${days} ${days === 1 ? "day" : "days"}` : years < 2 ? `About ${months} ${months === 1 ? "month" : "months"}` : `About ${Number(years.toFixed(1))} years`]);
      const others = goals.filter((row) => row !== goal && typeof row.name === "string" && row.name.trim()).map((row) => String(row.name));
      if (others.length) facts.push(["Other near-term goals", others.join(" · ")]);
    }
  } else if (finding.type === "psychometric_suitability") {
    add("Effective risk comfort", evidence.effective_risk_score, score);
    const scores = evidence.scores && typeof evidence.scores === "object" ? evidence.scores as Record<string, unknown> : {};
    add("Recorded risk willingness", scores.risk_score, score);
    add("Recorded drawdown comfort", scores.loss_aversion_score, score);
  } else if (finding.type === "correlation_review") {
    add("Historical return correlation", evidence.correlation, (value) => value.toFixed(3));
    add("Common return observations", evidence.observations, (value) => `${value} ${typeof evidence.frequency === "string" ? evidence.frequency : "recorded"} returns`);
    if (typeof evidence.start_date === "string" && typeof evidence.end_date === "string") facts.push(["Observed window", `${evidence.start_date} to ${evidence.end_date}`]);
  } else if (finding.type === "overlap_review") {
    add("Measured holdings overlap", evidence.weighted_overlap_pct, pct);
    add("First fund: identified weight", evidence.coverage_a_pct, pct);
    add("Second fund: identified weight", evidence.coverage_b_pct, pct);
    add("Shared identified securities", Array.isArray(evidence.common_securities) ? evidence.common_securities.length : evidence.common_securities);
  } else if (finding.type === "persistent_underperformance" || finding.type === "persistent_outperformance") {
    const periods = Array.isArray(evidence.compared_periods) ? evidence.compared_periods : [];
    for (const row of periods) if (row && typeof row === "object" && typeof row.period === "string") add(`Matched ${row.period.toUpperCase()} excess`, row.excess_return_pp, (value) => `${value.toFixed(2)} pp`);
    const rolling = evidence.rolling && typeof evidence.rolling === "object" ? evidence.rolling as Record<string, unknown> : {};
    add("Rolling windows above the TRI", rolling.outperformance_pct, pct);
    add("Median rolling excess", rolling.median_excess_pp, (value) => `${value.toFixed(2)} pp`);
  } else if (finding.type === "regular_plan_cost_review") {
    if (evidence.plan === "regular" || evidence.plan === "direct") facts.push(["Recorded plan", evidence.plan === "regular" ? "Regular" : "Direct"]);
    add("Disclosed plan TER", evidence.ter_percent, pct);
  }
  if (fund) add("Share of recorded investments", fund.weight_pct, pct);
  return facts.slice(0, 4);
}

/** Select only measured pairs; no all-N/A grid and no invented zero default. */
export function measuredFundPairs<T extends MutualFundOverlap | MutualFundCorrelation>(rows: T[], kind: "overlap" | "correlation"): T[] {
  const seen = new Set<string>();
  return rows.filter((row) => {
    if (row.fund_a === row.fund_b || pairMetric(row, kind) == null) return false;
    const key = [row.fund_a, row.fund_b].sort().join("\u0000");
    if (seen.has(key)) return false;
    seen.add(key); return true;
  }).sort((a, b) => Math.abs(pairMetric(b, kind)!) - Math.abs(pairMetric(a, kind)!));
}

/** Timeline positions are derived from recorded start times, never agent-list order. */
export function executionBars(agents: OrchestrationAgent[]) {
  const timed = agents.flatMap((agent) => {
    const start = Date.parse(agent.started_at || "");
    const finish = Date.parse(agent.finished_at || "");
    return Number.isFinite(start) && Number.isFinite(finish) && finish >= start ? [{ agent, start, finish }] : [];
  });
  if (!timed.length) return [];
  const first = Math.min(...timed.map((row) => row.start));
  const span = Math.max(1, Math.max(...timed.map((row) => row.finish)) - first);
  return timed.map(({ agent, start, finish }) => ({ id: agent.id, left: (start - first) / span * 100, width: Math.max(.5, (finish - start) / span * 100), start, finish }));
}

export function jsonEvidence(value: unknown): string {
  if (value == null) return "Not recorded";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

/** Restore declared consent, not a computed surplus/capacity that the user never entered. */
export function contributionFieldsFromPolicy(value: unknown) {
  const policy = value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
  const field = (key: string) => { const number = observationNumber(policy[key]); return number != null && number >= 0 ? String(policy[key]) : ""; };
  return { budget: field("declared_monthly_budget"), other: field("other_goal_commitments"), reserve: field("reserve_commitment") };
}

/** Early file feedback only. The API performs authoritative provenance and financial validation. */
export function parseMutualFundImport(text: string, kind: "disclosure" | "benchmark"): Record<string, unknown> {
  if (text.length > 2 * 1024 * 1024) throw new Error("Keep the normalized JSON file below 2 MB.");
  let payload: Record<string, unknown>;
  try {
    const parsed: unknown = JSON.parse(text);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("object");
    payload = parsed as Record<string, unknown>;
  } catch { throw new Error("Select a valid JSON object, not a PDF, spreadsheet or array."); }
  const source = evidenceUrl(payload.source_url);
  if (!source?.startsWith("https://")) throw new Error("Provide the original official HTTPS source_url.");
  const observed = String(payload.observed_on || "");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(observed) || !Number.isFinite(Date.parse(observed)) || new Date(observed).toISOString().slice(0, 10) !== observed) throw new Error("Provide observed_on as an actual calendar date in YYYY-MM-DD form.");
  if (kind === "disclosure") {
    if (!/^\d{5,6}$/.test(String(payload.scheme_code || "")) || typeof payload.scheme_code === "boolean") throw new Error("Provide the exact MFAPI scheme_code.");
    if (!Array.isArray(payload.holdings) || !payload.holdings.length) throw new Error("Provide the disclosed holdings array using full scheme NAV weights.");
    let total = 0;
    for (const row of payload.holdings) {
      if (!row || typeof row !== "object" || Array.isArray(row)) throw new Error("Every holding needs its name, ISIN and weight_pct.");
      const weight = observationNumber(row.weight_pct);
      if (!row.name || weight == null || weight < 0 || weight > 100) throw new Error("Every holding needs a name and finite weight_pct from 0 to 100.");
      total += weight;
    }
    if (total > 100.05) throw new Error("Holding weights exceed 100%. Use percentages of full scheme NAV, without renormalizing a sample.");
  } else {
    if (!payload.benchmark_id || !payload.name || !["tri", "total_return"].includes(String(payload.kind).toLowerCase())) throw new Error("Identify the benchmark and explicitly use kind TRI. Price indices are not interchangeable.");
    if (!Array.isArray(payload.points) || payload.points.length < 2) throw new Error("Provide at least two dated total-return points.");
    if (payload.points.some((point) => !point || typeof point !== "object" || !/^\d{4}-\d{2}-\d{2}$/.test(String(point.date || "")) || (observationNumber(point.value) ?? 0) <= 0)) throw new Error("Each benchmark point needs an ISO date and a finite positive value.");
  }
  return payload;
}
