"use client";

import Link from "next/link";
import { useState } from "react";
import type { BondFinding, BondIntelligence, BondProduct, SkillPrinciple } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { apiRequest } from "@/lib/api-client";
import { bondCategoryLabel, bondDisplayText, bondReadinessReasons, focusedBondFindings, focusedBondProducts, supportedBondBudget, verifiedBillReturns, verifiedBondComparisonPrice, verifiedBondPrice, verifiedBondYield } from "@/lib/bond-evidence";
import { evidenceUrl, hasRecordedEvidence, jsonEvidence, observationNumber, percentage } from "@/lib/investment-evidence";
import { ReviewProofPanel } from "@/components/decisions/review-proof";

function SourceLink({ url, children }: { url?: string | null; children: React.ReactNode }) {
  const safe = evidenceUrl(url);
  return safe ? <a href={safe} target="_blank" rel="noreferrer" className="text-teal-800 underline underline-offset-4">{children} ↗</a> : <span>{children}</span>;
}

function BondProductCard({ product, sources }: { product: BondProduct; sources: BondIntelligence["sources"] }) {
  const price = verifiedBondPrice(product), ytm = verifiedBondYield(product), budget = supportedBondBudget(product);
  const comparisonPrice = verifiedBondComparisonPrice(product), billReturns = verifiedBillReturns(product);
  const coupon = observationNumber(product.coupon_rate_pct), face = observationNumber(product.face_value);
  const duration = observationNumber(product.modified_duration), dv01 = observationNumber(product.dv01);
  const calculation = product.metrics && typeof product.metrics === "object" ? product.metrics as Record<string, unknown> : {};
  const ask = observationNumber(calculation.comparison_ask);
  const gold = product.category === "sovereign_gold";
  const refs = (sources || []).filter((source) => product.source_ids.includes(source.id));
  return <article className="min-w-0 rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
    <p className="text-[10px] font-semibold uppercase tracking-wide text-teal-700">{bondCategoryLabel(product.category)}</p><h4 className="mt-2 text-sm font-semibold leading-6 text-slate-900">{product.name}</h4><p className="mt-2 break-all font-mono text-[10px] text-slate-500">{product.isin}</p>
    <p className="mt-3 inline-block rounded-lg bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-600">{price == null ? "Terms comparison · no verified market price" : "Verified priced comparison"}</p>
    <dl className="mt-4 grid grid-cols-2 gap-4 text-xs">
      {product.maturity_date && <div><dt className="text-[10px] text-slate-500">Scheduled maturity</dt><dd className="mt-1 font-semibold text-slate-900">{product.maturity_date}</dd></div>}
      {coupon != null && <div><dt className="text-[10px] text-slate-500">{gold ? "Coupon on original issue price" : "Annual coupon"}</dt><dd className="mt-1 font-semibold text-slate-900">{coupon === 0 ? "Zero coupon" : percentage(coupon)}</dd></div>}
      {face != null && face > 0 && !gold && <div><dt className="text-[10px] text-slate-500">Face value</dt><dd className="mt-1 font-semibold text-slate-900">{formatCurrency(String(face))}</dd></div>}
      {typeof product.lot_size === "number" && product.lot_size > 0 && <div><dt className="text-[10px] text-slate-500">Exchange lot size</dt><dd className="mt-1 font-semibold text-slate-900">{product.lot_size}</dd></div>}
      {price != null && <div><dt className="text-[10px] text-slate-500">Observed last trade</dt><dd className="mt-1 font-semibold text-slate-900">{price.toFixed(2)}<span className="mt-1 block text-[10px] font-normal leading-5 text-slate-500">{product.price_basis}</span></dd></div>}
      {comparisonPrice != null && <div><dt className="text-[10px] text-slate-500">Comparison cash outlay per unit</dt><dd className="mt-1 font-semibold text-slate-900">{formatCurrency(String(comparisonPrice))}<span className="mt-1 block text-[10px] font-normal leading-5 text-slate-500">Observed ask including any verified accrued interest, before separately stated fees.</span></dd></div>}
      {ytm != null && <div><dt className="text-[10px] text-slate-500">Cashflow-based YTM</dt><dd className="mt-1 font-semibold text-teal-900">{percentage(ytm)}</dd></div>}
      {billReturns && <><div><dt className="text-[10px] text-slate-500">Bill simple annualized yield</dt><dd className="mt-1 font-semibold text-teal-900">{percentage(billReturns.annualized)}<span className="mt-1 block text-[10px] font-normal text-slate-500">ACT/365F · not nominal YTM</span></dd></div><div><dt className="text-[10px] text-slate-500">Bill holding-period return</dt><dd className="mt-1 font-semibold text-slate-900">{percentage(billReturns.holdingPeriod)}<span className="mt-1 block text-[10px] font-normal text-slate-500">{billReturns.days} days to maturity</span></dd></div></>}
      {ytm != null && duration != null && <div><dt className="text-[10px] text-slate-500">Modified duration</dt><dd className="mt-1 font-semibold text-slate-900">{duration.toFixed(2)} years</dd></div>}
      {ytm != null && dv01 != null && <div><dt className="text-[10px] text-slate-500">DV01 · per quoted unit</dt><dd className="mt-1 font-semibold text-slate-900">{formatCurrency(String(dv01))}</dd></div>}
    </dl>
    {comparisonPrice != null && ask != null && typeof calculation.settlement_date === "string" && <p className="mt-3 text-[10px] leading-6 text-slate-500">Calculation basis: ask {ask.toFixed(2)} ({String(calculation.comparison_price_basis || product.price_basis)}); verified settlement {calculation.settlement_date}. The full cash outlay above is used for yields and bounded quantities.</p>}
    {product.goal_role && <p className="mt-4 rounded-xl bg-[#f3f8f5] p-3 text-xs leading-6 text-teal-900">{bondDisplayText(product.goal_role)}</p>}
    {gold ? <p className="mt-3 text-[10px] leading-6 text-slate-600">Gold exposure: redemption value depends on the applicable gold-price terms. The coupon is not a fixed total return or a replacement for cash needed on a fixed date.</p> : <p className="mt-3 text-[10px] leading-6 text-slate-500">Coupon differs from yield. A sale before maturity depends on market price and liquidity; scheduled maturity alone does not establish a funded goal.</p>}
    {budget && <p className="mt-3 text-xs leading-6 text-teal-900">Dedicated comparison budget {formatCurrency(String(budget.budget))}: {budget.units} units, estimated cost {formatCurrency(String(budget.cost))}. No order is placed.</p>}
    {!!refs.length && <ul className="mt-4 space-y-2 border-t border-slate-100 pt-3">{refs.map((source) => <li key={source.id} className="text-[10px] leading-5"><SourceLink url={source.url}>{source.title}</SourceLink>{source.observed_on && <span className="ml-1 text-slate-500">· {source.observed_on}</span>}</li>)}</ul>}
    {hasRecordedEvidence(product.terms) && <details className="mt-3"><summary className="cursor-pointer text-[10px] font-semibold text-slate-600">Verified terms and their basis</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-slate-50 p-3 text-[10px] leading-5 text-slate-600">{jsonEvidence(product.terms)}</pre></details>}
  </article>;
}

function BondFindingCard({ finding, sources }: { finding: BondFinding; sources: BondIntelligence["sources"] }) {
  const [principles, setPrinciples] = useState<SkillPrinciple[]>([]);
  const [state, setState] = useState<"idle" | "loading" | "ready" | "unavailable">("idle");
  async function inspect() {
    if (state !== "idle") return;
    setState("loading");
    try {
      const ids = [...new Set(finding.principle_ids || [])];
      const loaded = await Promise.all(ids.map((id) => apiRequest<SkillPrinciple>(`/knowledge/principles/${encodeURIComponent(id)}`)));
      if (!loaded.every((principle, index) => principle.id === ids[index] && principle.excerpt && principle.skill_sha256)) throw new Error("Unverified skill section");
      setPrinciples(loaded); setState("ready");
    } catch { setState("unavailable"); }
  }
  const refs = (sources || []).filter((source) => finding.source_ids?.includes(source.id));
  return <article className="min-w-0 rounded-2xl border border-slate-200 bg-white p-4 sm:p-5"><h4 className="text-sm font-semibold text-slate-900">{finding.title}</h4><p className="mt-3 text-xs leading-6 text-slate-600">{bondDisplayText(finding.detail)}</p>{finding.suggested_action && <p className="mt-3 rounded-xl bg-[#f3f8f5] p-3 text-xs leading-6 text-teal-900"><strong>Next step:</strong> {bondDisplayText(finding.suggested_action)}</p>}
    {finding.proof ? <ReviewProofPanel proof={finding.proof} /> : <details className="mt-4 rounded-xl border border-slate-200 p-3" onToggle={(event) => { if (event.currentTarget.open) void inspect(); }}><summary className="cursor-pointer text-xs font-semibold text-slate-700">Applied skills and source facts</summary>
      {state === "loading" && <p className="mt-3 text-xs text-slate-500">Checking exact skill sections…</p>}{state === "unavailable" && <p className="mt-3 text-xs leading-6 text-amber-900">The cited skill section could not be loaded. No quotation has been inferred.</p>}
      {principles.map((principle) => <div key={principle.id} className="mt-3 rounded-xl bg-teal-50/60 p-3"><p className="text-xs font-semibold text-teal-900">{principle.title} · {principle.section}</p><blockquote className="mt-2 text-xs leading-6 text-slate-700">“{principle.excerpt}”</blockquote><p className="mt-2 break-words text-[10px] text-slate-500">{principle.path} · lines {principle.line_start}–{principle.line_end}</p><ul className="mt-3 space-y-2">{principle.source_refs?.map((source) => <li key={source.id} className="text-[10px] leading-5"><SourceLink url={source.url}>{source.publisher} · {source.title}</SourceLink></li>)}</ul></div>)}
      {!!refs.length && <ul className="mt-3 space-y-2">{refs.map((source) => <li key={source.id} className="text-[10px] leading-5"><SourceLink url={source.url}>{source.title}</SourceLink>{source.observed_on ? ` · ${source.observed_on}` : ""}</li>)}</ul>}
      {hasRecordedEvidence(finding.evidence) && <details className="mt-3"><summary className="cursor-pointer text-[10px] font-semibold text-slate-600">Recorded calculation receipt</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-slate-50 p-3 text-[10px] leading-5 text-slate-600">{jsonEvidence(finding.evidence)}</pre></details>}
    </details>}
  </article>;
}

export function BondPanel({ data, showDataLink = true, onRefresh, refreshing = false }: { data?: BondIntelligence | null; showDataLink?: boolean; onRefresh?: () => void; refreshing?: boolean }) {
  if (!data?.version) return null;
  const products = focusedBondProducts(data), findings = focusedBondFindings(data.findings || []), reasons = bondReadinessReasons(data);
  const pricedCount = products.filter((product) => verifiedBondPrice(product) != null).length;
  const sourceDate = data.as_of || "the recorded observation";
  const nextAction = typeof data.data_quality?.next_action === "string" ? data.data_quality.next_action : "Refresh the read-only data check. A priced product comparison needs current bid/ask evidence, trade timestamps and verified cashflows; a catalogue entry alone is not an available offer.";
  return <section id="decision-bonds" aria-labelledby="bond-panel-title" className="decision-anchor overflow-hidden rounded-[28px] border border-slate-200 bg-white">
    <div className="border-b border-slate-100 bg-[#f3f7fc] p-5 sm:p-7"><p className="text-[10px] font-semibold uppercase tracking-[.18em] text-blue-800">Bond Agent</p><h2 id="bond-panel-title" className="mt-2 text-xl font-semibold tracking-tight text-slate-900">Match instruments to the role your money needs.</h2><p className="mt-2 max-w-3xl text-xs leading-6 text-slate-600">Dated government-security terms, goal timing and portfolio risk join the central review. Gold-linked products retain a separate portfolio role.</p><p className="mt-3 text-[11px] leading-6 text-slate-500">As of {sourceDate} · {products.length} sourced product comparisons · {pricedCount} verified priced comparisons · one shared investment budget.</p></div>
    {!!findings.length && <div className="border-b border-slate-100 p-5 sm:p-7"><h3 className="text-base font-semibold text-slate-900">What matters for your plan</h3><div className="mt-4 grid gap-4 lg:grid-cols-2">{findings.map((finding) => <BondFindingCard key={finding.id} finding={finding} sources={data.sources} />)}</div></div>}
    {!!products.length && <div className="p-5 sm:p-7"><h3 className="text-base font-semibold text-slate-900">{pricedCount ? "Sourced instruments to compare" : "Actual instruments and their terms"}</h3><p className="mt-2 text-xs leading-6 text-slate-500">{pricedCount ? "Compare the dated market evidence with maturity, liquidity and goal constraints." : "These are real catalogue instruments with sourced terms. Their presence does not establish a fresh quote, availability or a buy recommendation."}</p><div className="mt-4 grid gap-4 lg:grid-cols-3">{products.map((product) => <BondProductCard key={product.isin} product={product} sources={data.sources} />)}</div></div>}
    <details id="bond-data-readiness" className="m-5 rounded-xl border border-slate-200 bg-slate-50/50 p-4 sm:mx-7"><summary className="cursor-pointer text-xs font-semibold text-slate-700">Market-data readiness, sources and checks</summary><p className="mt-3 text-xs leading-6 text-slate-600">{nextAction}</p>{!!reasons.length && <ul className="mt-3 list-disc space-y-2 pl-4 text-[11px] leading-6 text-slate-600">{reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
      {!!data.excluded_products?.length && <p className="mt-3 text-[11px] leading-6 text-slate-500">{data.excluded_products.length} instruments were excluded by the checks. Excluded instruments are not product suggestions.</p>}
      <div className="mt-4 flex flex-wrap gap-4 text-xs font-semibold text-teal-800">{onRefresh && <button type="button" disabled={refreshing} onClick={onRefresh} className="underline underline-offset-4 disabled:opacity-50">{refreshing ? "Checking market evidence…" : "Refresh read-only evidence"}</button>}<Link href="/onboarding/goals" className="underline underline-offset-4">Review goal dates</Link>{showDataLink && <Link href="/bonds" className="underline underline-offset-4">Open bond workspace ↗</Link>}</div>
      {!!data.sources?.length && <div className="mt-4 border-t border-slate-200 pt-4"><h3 className="text-xs font-semibold text-slate-800">Dated evidence sources</h3><ul className="mt-3 space-y-3">{data.sources.map((source) => <li key={source.id} className="text-[11px] leading-6"><SourceLink url={source.url}>{source.title}</SourceLink>{source.observed_on && <span className="ml-2 text-slate-500">{source.observed_on}</span>}</li>)}</ul></div>}
      {(hasRecordedEvidence(data.methods) || hasRecordedEvidence(data.constraint_policy)) && <details className="mt-4 rounded-xl border border-slate-200 bg-white p-3"><summary className="cursor-pointer text-[11px] font-semibold text-slate-700">Calculation methods and central constraints</summary><pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words font-mono text-[10px] leading-5 text-slate-600">{jsonEvidence({ methods: data.methods, constraints: data.constraint_policy })}</pre></details>}
    </details>
  </section>;
}
