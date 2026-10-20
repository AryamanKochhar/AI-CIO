import assert from "node:assert/strict";
import test from "node:test";
import type { BondFinding, BondIntelligence, BondProduct } from "@ai-cio/contracts";
import { bondDisplayText, bondReadinessReasons, focusedBondFindings, focusedBondProducts, supportedBondBudget, verifiedBillReturns, verifiedBondPrice, verifiedBondYield } from "../bond-evidence.ts";

const product = (values: Partial<BondProduct> = {}): BondProduct => ({ isin: "IN0020240016", name: "Synthetic test government security", category: "government_dated", maturity_date: "2030-06-15", coupon_rate_pct: 7, face_value: 100, lot_size: 1, quote_status: "unavailable", eligibility_status: "terms_only", source_ids: ["fixture_source"], readiness: { status: "blocked", checks: [], reasons: ["Fresh two-sided market depth is required."] }, terms: { fixture: true }, ...values });
const priced = (values: Partial<BondProduct> = {}) => product({ price: 101, price_basis: "clean price per face value 100", comparison_price: 101.5, comparison_price_basis: "dirty", last_trade_at: "2026-10-20T10:00:00+05:30", quote_status: "verified_fresh_depth", ...values });

test("a listed coupon or a successful empty quote response never becomes a priced bond yield", () => {
  assert.equal(verifiedBondPrice(product({ price: 101.5, quote_status: "unavailable" })), null);
  assert.equal(verifiedBondPrice(priced({ quote_status: "stale" })), null);
  assert.equal(verifiedBondPrice(priced({ price_basis: null })), null);
  assert.equal(verifiedBondPrice(priced({ last_trade_at: null })), null);
  assert.equal(verifiedBondYield(priced({ ytm_pct: 7, yield_status: "not_evaluated" })), null);
  assert.equal(verifiedBondYield(priced({ ytm_pct: 6.5, yield_status: "computed_verified_cashflows" })), 6.5);
  assert.equal(verifiedBondYield(priced({ category: "sovereign_gold", ytm_pct: 2.5, yield_status: "computed_verified_cashflows" })), null);
  assert.equal(verifiedBondYield(priced({ category: "treasury_bill", ytm_pct: 7, yield_status: "computed_verified_cashflows" })), null);
});

test("priced bill returns retain distinct holding-period and ACT/365F simple annualized conventions", () => {
  const bill = priced({ category: "treasury_bill", yield_status: "computed_verified_cashflows", metrics: { holding_period_return_pct: 2, simple_annualized_yield_pct: 2 * 365 / 91, maturity_days: 91, yield_basis: "simple annualized investment yield; ACT/365F; not coupon-bond nominal YTM" } });
  assert.deepEqual(verifiedBillReturns(bill), { holdingPeriod: 2, annualized: 2 * 365 / 91, days: 91, basis: "simple annualized investment yield; ACT/365F; not coupon-bond nominal YTM" });
  assert.equal(verifiedBillReturns({ ...bill, category: "government_dated" }), null);
  assert.equal(verifiedBillReturns({ ...bill, comparison_price: null }), null);
  assert.equal(verifiedBillReturns({ ...bill, metrics: { holding_period_return_pct: 2, simple_annualized_yield_pct: 7, maturity_days: 91, yield_basis: "ACT/365F" } }), null);
});

test("product focus keeps real sourced identities, distinct roles and the richer eligible observation", () => {
  const catalogue = [product(), product({ isin: "IN0020240024" }), product({ isin: "IN0020240032", category: "treasury_bill" }), product({ isin: "IN0020240040", category: "sovereign_gold" }), product({ isin: "IN0020240057", maturity_date: "2025-01-01" }), product({ isin: "bad-identity" }), product({ isin: "IN0020240065", source_ids: [] })];
  const eligible = priced({ eligibility_status: "eligible_for_comparison", readiness: { status: "ready", checks: ["test"], reasons: [] } });
  const selected = focusedBondProducts({ catalogue_products: catalogue, eligible_products: [eligible], as_of: "2026-10-20" });
  assert.deepEqual(selected.map((row) => row.category), ["government_dated", "treasury_bill", "sovereign_gold"]);
  assert.equal(selected[0].quote_status, "verified_fresh_depth");
  assert.equal(selected.length, 3);
  assert.deepEqual(focusedBondProducts({ catalogue_products: catalogue, eligible_products: [], as_of: "2026-10-20" }, 0), []);
  assert.equal(catalogue.length, 7);
});

test("units stay withheld without a dedicated bond budget, verified pricing and complete bounded costs", () => {
  const ready = priced({ eligibility_status: "eligible_for_comparison", readiness: { status: "ready", checks: [], reasons: [] }, unit_budget: 1000, units: 5, estimated_cost: 510, budget_costs: { fixed: 2.5, rate: 0 } });
  assert.deepEqual(supportedBondBudget(ready), { budget: 1000, units: 5, cost: 510 });
  assert.equal(supportedBondBudget({ ...ready, unit_budget: null }), null);
  assert.equal(supportedBondBudget({ ...ready, estimated_cost: 1001 }), null);
  assert.equal(supportedBondBudget({ ...ready, units: 1.5 }), null);
  assert.equal(supportedBondBudget({ ...ready, quote_status: "price_only" }), null);
  assert.deepEqual(supportedBondBudget({ ...ready, estimated_cost: 507.5, budget_costs: { fixed: 0, rate: 0 } }), { budget: 1000, units: 5, cost: 507.5 });
  assert.equal(supportedBondBudget({ ...ready, estimated_cost: 505, budget_costs: { fixed: 0, rate: 0 } }), null, "clean last trade cannot substitute for dirty ask cash outlay");
  assert.equal(supportedBondBudget({ ...ready, lot_size: 100 }), null);
});

test("focused findings show distinct sourced checks and combine repeated provider gaps once", () => {
  const finding = (id: string, type: string, evidence = {}): BondFinding => ({ id, type, title: id, detail: "fixture", evidence, principle_ids: [], source_ids: [] });
  assert.deepEqual(focusedBondFindings([finding("empty", "goal_fit"), finding("gap", "quote_unavailable", { requests: 1 }), finding("one", "goal_fit", { horizon: 4 }), finding("two", "goal_fit", { horizon: 5 }), finding("three", "gold_role", { gold_weight: 2 })]).map((row) => row.id), ["one", "three"]);
  const data = { data_quality: { missing: ["Fresh two-sided market depth is required."], warnings: ["Source date reviewed."] }, catalogue_products: [product(), product()], eligible_products: [] } as unknown as BondIntelligence;
  assert.deepEqual(bondReadinessReasons(data), ["Fresh two-sided market depth is required.", "Source date reviewed."]);
  assert.equal(bondDisplayText("Goal: 2030-06-15 (Recorded target_date); 7.57% coupon."), "Goal: 2030-06-15 (recorded goal date); 7.57% coupon.");
});
