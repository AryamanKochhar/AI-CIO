import assert from "node:assert/strict";
import test from "node:test";
import type { FireAllocationPlan } from "@ai-cio/contracts";
import { EMPTY_FIRE_FORM, fireAllocationRows, fireFormFromInputs, parseFireForm } from "../fire-form.ts";

const form = () => ({ ...EMPTY_FIRE_FORM, current_age: "35", monthly_spending_today: "40000", earmarked_assets: "500000" });

test("missing contribution willingness and pension remain unknown rather than becoming zero or surplus", () => {
  const inputs = parseFireForm(form());
  assert.equal(inputs.monthly_investment_budget, null);
  assert.equal(inputs.annual_pension_today, null);
  assert.equal(inputs.current_age, 35);
  assert.equal(inputs.retirement_age, 65);
});

test("explicit zero budget and zero pension survive parsing and saved-goal restoration", () => {
  const inputs = parseFireForm({ ...form(), monthly_investment_budget: "0", annual_pension_today: "0" });
  assert.equal(inputs.monthly_investment_budget, "0");
  assert.equal(inputs.annual_pension_today, "0");
  assert.deepEqual(parseFireForm(fireFormFromInputs(inputs)), inputs);
});

test("no age or earmarked-asset amount is inferred from a blank form", () => {
  assert.throws(() => parseFireForm(EMPTY_FIRE_FORM), /current age/);
  assert.throws(() => parseFireForm({ ...form(), earmarked_assets: "" }), /reserved/);
  assert.throws(() => parseFireForm({ ...form(), current_age: "35.5" }), /whole number/);
});

test("retirement and longevity must follow the current age in order", () => {
  assert.throws(() => parseFireForm({ ...form(), retirement_age: "35" }), /after your current age/);
  assert.throws(() => parseFireForm({ ...form(), longevity_age: "65" }), /after your target age/);
});

test("financial amounts reject negative, non-finite and ambiguous over-precision inputs", () => {
  for (const invalid of ["-1", "NaN", "Infinity", "15000.001"]) {
    assert.throws(() => parseFireForm({ ...form(), monthly_investment_budget: invalid }), /chosen monthly investment budget/);
  }
  assert.throws(() => parseFireForm({ ...form(), withdrawal_rate_percent: "0" }), /greater than zero/);
});

test("displayed allocation amounts preserve zero and unknown values for any backend template", () => {
  const plan = { id: "preservation", equity_percent: 0, fd_percent: 80, high_quality_debt_percent: 20,
    monthly_amounts: { equity: "0.00", fd: "12000.00", high_quality_debt: "3000.00" } } as FireAllocationPlan;
  const rows = fireAllocationRows(plan);
  assert.equal(rows[0].amount, "0.00");
  assert.equal(rows.reduce((sum, row) => sum + Number(row.amount), 0), 15000);
  plan.monthly_amounts.equity = null;
  assert.equal(fireAllocationRows(plan)[0].amount, null);
});
