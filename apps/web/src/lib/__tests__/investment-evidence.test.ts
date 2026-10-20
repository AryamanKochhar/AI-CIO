import assert from "node:assert/strict";
import test from "node:test";
import type { MutualFundCorrelation, MutualFundOverlap, OrchestrationAgent } from "@ai-cio/contracts";
import { benchmarkGrowth, contributionFieldsFromPolicy, durationLabel, evidenceUrl, executionBars, findingFundNames, observationNumber, pairMetric, pairObservation, pairStatusExplanation, parseMutualFundImport, percentage } from "../investment-evidence.ts";

test("missing observations stay distinct from measured zero in fund metrics", () => {
  for (const value of [null, undefined, "", "  ", true, false, NaN, Infinity, "NaN", [], {}]) assert.equal(observationNumber(value), null);
  assert.equal(observationNumber("0"), 0);
  assert.equal(percentage(0), "0.00%");
  assert.equal(percentage(null), "Unavailable");
  assert.equal(percentage(-2.5, 2, " pp"), "-2.50 pp");
});

test("refreshing a saved review restores actual consent and explicit earmarks without inventing willingness from surplus", () => {
  assert.deepEqual(contributionFieldsFromPolicy({ declared_monthly_budget: "15000.00", total_monthly_ceiling: "12000.00", other_goal_commitments: "2000.00", reserve_commitment: "0.00" }), { budget: "15000.00", other: "2000.00", reserve: "0.00" });
  assert.deepEqual(contributionFieldsFromPolicy({ monthly_surplus: "50000.00", total_monthly_ceiling: null }), { budget: "", other: "", reserve: "" });
  assert.deepEqual(contributionFieldsFromPolicy(undefined), { budget: "", other: "", reserve: "" });
});

test("growth chart joins observation dates and rebases both at the same point", () => {
  const points = benchmarkGrowth({
    nav_history: [{ date: "2025-01-01", value: 80 }, { date: "2025-01-02", value: 100 }, { date: "2025-01-04", value: 120 }],
    benchmark_history: [{ date: "2025-01-04", value: 220 }, { date: "2025-01-02", value: 200 }, { date: "2025-01-03", value: 205 }],
  });
  assert.deepEqual(points, [{ date: "2025-01-02", fund: 100, benchmark: 100 }, { date: "2025-01-04", fund: 120, benchmark: 110.00000000000001 }]);
});

test("a growth chart cannot substitute a missing benchmark or use unadjusted IDCW NAV", () => {
  const nav_history = [{ date: "2025-01-01", value: 100 }, { date: "2025-01-02", value: 110 }];
  assert.deepEqual(benchmarkGrowth({ nav_history, benchmark_history: [] }), []);
  assert.deepEqual(benchmarkGrowth({ nav_history, benchmark_history: nav_history, option: "idcw" }), []);
  assert.deepEqual(benchmarkGrowth({ nav_history, benchmark_history: nav_history, identity_status: "mismatch" }), []);
  assert.deepEqual(benchmarkGrowth({ nav_history: [{ date: "2025-01-01", value: 0 }], benchmark_history: nav_history }), []);
});

test("overlap and correlation remain separate, symmetric and constrained to valid observations", () => {
  const overlaps: MutualFundOverlap[] = [{ fund_a: "A", fund_b: "B", weighted_overlap_pct: 0, status: "available" }];
  const correlations: MutualFundCorrelation[] = [{ fund_a: "A", fund_b: "B", correlation: .94, status: "available", observations: 36 }];
  assert.equal(pairMetric(pairObservation(overlaps, "B", "A"), "overlap"), 0);
  assert.equal(pairMetric(pairObservation(correlations, "A", "B"), "correlation"), .94);
  assert.equal(pairMetric({ ...correlations[0], status: "insufficient_data" }, "correlation"), null);
  assert.equal(pairMetric({ ...correlations[0], status: "supported" }, "correlation"), .94);
  assert.equal(pairMetric({ ...overlaps[0], weighted_overlap_pct: 15, status: "partial_coverage" }, "overlap"), 15);
  assert.equal(pairMetric({ ...correlations[0], correlation: 1.1 }, "correlation"), null);
  assert.equal(pairMetric(pairObservation(overlaps, "A", "C"), "overlap"), null);
});

test("fund findings retain specific scheme context even for unresolved keys and pair findings", () => {
  const funds = [{ fund_id: "unresolved:0", scheme_name: "Synthetic Fund A" }, { fund_id: "unresolved:1", scheme_name: "Synthetic Fund B" }];
  assert.deepEqual(findingFundNames("unresolved:0", funds), ["Synthetic Fund A"]);
  assert.deepEqual(findingFundNames("unresolved:1", funds), ["Synthetic Fund B"]);
  assert.deepEqual(findingFundNames("unresolved:0:unresolved:1", funds), ["Synthetic Fund A", "Synthetic Fund B"]);
  assert.deepEqual(findingFundNames(null, funds), []);
  assert.match(pairStatusExplanation("partial_coverage"), /lower bound/);
  assert.match(pairStatusExplanation("unavailable"), /does not establish zero/);
});

test("execution timeline uses real times and preserves parallel overlap rather than list order", () => {
  const row = (id: string, start: string, end: string) => ({ id, label: id, status: "completed", started_at: start, finished_at: end } satisfies OrchestrationAgent);
  const bars = executionBars([
    row("slow", "2026-10-20T00:00:01Z", "2026-10-20T00:00:05Z"),
    row("fast", "2026-10-20T00:00:01Z", "2026-10-20T00:00:03Z"),
    row("after", "2026-10-20T00:00:03Z", "2026-10-20T00:00:05Z"),
    row("bad", "2026-10-20T00:00:05Z", "2026-10-20T00:00:01Z"),
  ]);
  assert.deepEqual(bars.map(({ id, left, width }) => ({ id, left, width })), [{ id: "slow", left: 0, width: 100 }, { id: "fast", left: 0, width: 50 }, { id: "after", left: 50, width: 50 }]);
  assert.equal(durationLabel(0), "0 ms");
  assert.equal(durationLabel(null), "Duration not recorded");
});

test("evidence links reject executable URLs and local file paths", () => {
  for (const value of ["javascript:alert(1)", "data:text/html,test", "file:///C:/secret", "/api/private", undefined]) assert.equal(evidenceUrl(value), undefined);
  assert.equal(evidenceUrl("https://www.amfiindia.com/online-center/portfolio-disclosure"), "https://www.amfiindia.com/online-center/portfolio-disclosure");
});

const disclosure = () => ({ scheme_code: 122639, source_url: "https://amc.ppfas.com/test-fixture", observed_on: "2026-09-30", holdings: [{ isin: "INE040A01034", name: "Synthetic fixture security", weight_pct: 7.75 }] });
const benchmark = () => ({ benchmark_id: "SYNTHETIC_TRI", name: "Synthetic fixture TRI", kind: "TRI", source_url: "https://www.niftyindices.com/test-fixture", observed_on: "2026-10-19", points: [{ date: "2026-10-16", value: 100 }, { date: "2026-10-19", value: 101 }] });

test("disclosure upload preserves full NAV weights and rejects fabricated numeric coercions", () => {
  const payload = disclosure();
  assert.deepEqual(parseMutualFundImport(JSON.stringify(payload), "disclosure"), payload);
  assert.equal((parseMutualFundImport(JSON.stringify(payload), "disclosure").holdings as typeof payload.holdings)[0].weight_pct, 7.75);
  assert.throws(() => parseMutualFundImport(JSON.stringify({ ...payload, holdings: [{ name: "A", weight_pct: 70 }, { name: "B", weight_pct: 40 }] }), "disclosure"), /exceed 100/);
  assert.throws(() => parseMutualFundImport(JSON.stringify({ ...payload, holdings: [{ name: "A", weight_pct: true }] }), "disclosure"), /finite/);
  assert.throws(() => parseMutualFundImport(JSON.stringify({ ...payload, observed_on: "2026-02-30" }), "disclosure"), /actual calendar/);
});

test("benchmark imports require an identified total-return series and positive observations", () => {
  assert.deepEqual(parseMutualFundImport(JSON.stringify(benchmark()), "benchmark"), benchmark());
  assert.throws(() => parseMutualFundImport(JSON.stringify({ ...benchmark(), kind: "price" }), "benchmark"), /Price indices/);
  assert.throws(() => parseMutualFundImport(JSON.stringify({ ...benchmark(), points: [{ date: "2026-01-01", value: 0 }, { date: "2026-01-02", value: 1 }] }), "benchmark"), /finite positive/);
  assert.throws(() => parseMutualFundImport("[]", "benchmark"), /JSON object/);
  assert.throws(() => parseMutualFundImport("<html>not JSON</html>", "benchmark"), /JSON object/);
});
