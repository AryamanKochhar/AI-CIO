import type { BondFinding, BondIntelligence, BondProduct } from "@ai-cio/contracts";

// Keep these guards local so this pure boundary can also run in Node's native
// TypeScript test runner without changing the application's module resolution.
function observationNumber(value: unknown): number | null {
  if ((typeof value !== "string" && typeof value !== "number") || (typeof value === "string" && !value.trim())) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function hasRecordedEvidence(value: unknown): boolean {
  if (value == null || (typeof value === "string" && !value.trim())) return false;
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "string" || typeof value === "boolean") return true;
  return typeof value === "object" && Object.values(value).some(hasRecordedEvidence);
}

export function bondCategoryLabel(category: string): string {
  return ({ government_dated: "Government security", treasury_bill: "Treasury bill", sovereign_gold: "Sovereign Gold Bond" } as Record<string, string>)[category] || "Bond";
}

/** Friendly source labels in prose; underlying dates and numerical evidence are unchanged. */
export function bondDisplayText(value: string): string {
  return value.replace(/\bRecorded target_date\b/g, "recorded goal date").replace(/\brecorded horizon_years\b/gi, "recorded goal horizon");
}

/** Catalogue terms and fresh executable-market observations are different evidence. */
export function verifiedBondPrice(product: BondProduct): number | null {
  const price = observationNumber(product.price);
  return product.quote_status === "verified_fresh_depth" && price != null && price > 0 && !!product.price_basis && Number.isFinite(Date.parse(product.last_trade_at || "")) ? price : null;
}

/** Cash outlay includes accrued interest when the exchange ask is quoted clean. */
export function verifiedBondComparisonPrice(product: BondProduct): number | null {
  const price = observationNumber(product.comparison_price);
  return verifiedBondPrice(product) != null && product.comparison_price_basis === "dirty" && price != null && price > 0 ? price : null;
}

/** Coupons are never substituted for a yield, including gold-linked redemption. */
export function verifiedBondYield(product: BondProduct): number | null {
  if (product.category !== "government_dated" || product.yield_status !== "computed_verified_cashflows") return null;
  return verifiedBondComparisonPrice(product) == null ? null : observationNumber(product.ytm_pct);
}

/** A bill's simple ACT/365F investment yield is not coupon-bond nominal YTM. */
export function verifiedBillReturns(product: BondProduct) {
  if (product.category !== "treasury_bill" || product.yield_status !== "computed_verified_cashflows" || verifiedBondComparisonPrice(product) == null) return null;
  const metrics = product.metrics && typeof product.metrics === "object" && !Array.isArray(product.metrics) ? product.metrics as Record<string, unknown> : {};
  const annualized = observationNumber(metrics.simple_annualized_yield_pct), holdingPeriod = observationNumber(metrics.holding_period_return_pct), days = observationNumber(metrics.maturity_days);
  if (annualized == null || holdingPeriod == null || days == null || !Number.isInteger(days) || days <= 0 || typeof metrics.yield_basis !== "string" || !metrics.yield_basis.includes("ACT/365F") || Math.abs(annualized - holdingPeriod * 365 / days) > .0001) return null;
  return { annualized, holdingPeriod, days, basis: metrics.yield_basis };
}

/** No units or spend without an actual dedicated ceiling and a verified priced comparison. */
export function supportedBondBudget(product: BondProduct) {
  const budget = observationNumber(product.unit_budget), units = observationNumber(product.units), cost = observationNumber(product.estimated_cost);
  const comparison = verifiedBondComparisonPrice(product), lot = observationNumber(product.lot_size);
  const costs = product.budget_costs && typeof product.budget_costs === "object" ? product.budget_costs as Record<string, unknown> : {};
  const fixed = observationNumber(costs.fixed), rate = observationNumber(costs.rate);
  if (product.eligibility_status !== "eligible_for_comparison" || product.readiness?.status !== "ready" || comparison == null || budget == null || budget <= 0 || units == null || !Number.isInteger(units) || units <= 0 || cost == null || cost <= 0 || cost > budget || lot == null || lot <= 0 || !Number.isInteger(lot) || units % lot !== 0 || fixed == null || fixed < 0 || rate == null || rate < 0 || Math.abs(comparison * units * (1 + rate) + fixed - cost) > .01) return null;
  return { budget, units, cost };
}

/** Prefer supported comparisons, then cover distinct sourced product families, capped at three. */
export function focusedBondProducts(data: Pick<BondIntelligence, "eligible_products" | "catalogue_products" | "as_of">, limit = 3): BondProduct[] {
  if (limit <= 0) return [];
  const identities = new Map<string, BondProduct>();
  for (const product of [...(data.eligible_products || []), ...(data.catalogue_products || [])]) if (!identities.has(product.isin)) identities.set(product.isin, product);
  const candidates = [...identities.values()].filter((product) => {
    if (!/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(product.isin || "") || !product.name?.trim() || !product.source_ids?.length || product.eligibility_status === "excluded") return false;
    const maturity = product.maturity_date;
    if (maturity && (!/^\d{4}-\d{2}-\d{2}$/.test(maturity) || !Number.isFinite(Date.parse(maturity)))) return false;
    return !maturity || !data.as_of || maturity > data.as_of;
  });
  const selected: BondProduct[] = [], categories = new Set<string>();
  for (const product of candidates) {
    if (!categories.has(product.category)) { selected.push(product); categories.add(product.category); }
    if (selected.length >= Math.min(3, Math.max(0, limit))) break;
  }
  return [...selected, ...candidates.filter((product) => !selected.some((row) => row.isin === product.isin))].slice(0, Math.min(3, limit));
}

/** Coverage failures belong in one readiness drawer, not repeated decision cards. */
export function focusedBondFindings(findings: BondFinding[], limit = 3): BondFinding[] {
  const themes = new Set<string>();
  return findings.filter((finding) => {
    if (/gap|unavailable|readiness|quote|data_quality|missing/.test(finding.type) || !hasRecordedEvidence(finding.evidence)) return false;
    if (themes.has(finding.type)) return false;
    themes.add(finding.type); return true;
  }).slice(0, Math.min(3, Math.max(0, limit)));
}

export function bondReadinessReasons(data: BondIntelligence): string[] {
  const text = (value: unknown) => typeof value === "string" && value.trim() ? [value.trim()] : [];
  const quality = data.data_quality || {};
  const reasons = [
    ...[quality.missing, quality.warnings, quality.reasons].flatMap((value) => Array.isArray(value) ? value.flatMap(text) : text(value)),
    ...[...(data.eligible_products || []), ...(data.catalogue_products || [])].flatMap((product) => (product.readiness?.reasons || []).flatMap(text)),
  ];
  return [...new Set(reasons)];
}
