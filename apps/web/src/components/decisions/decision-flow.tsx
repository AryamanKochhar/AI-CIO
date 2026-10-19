"use client";

import { useState } from "react";
import type { DecisionResult } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";

export function DecisionFlow({ result }: { result: DecisionResult }) {
  const [selected, setSelected] = useState(0);
  const market = result.holding_market_data;
  const stages = result.execution?.stages || [];
  const fallback = (result.assumptions || []).some((line) => /fallback|LLM unavailable/i.test(line));
  const specialists = [result.tax_intelligence, result.fd_intelligence, result.trajectory_intelligence];
  const steps = [
    { title: "Your financial twin", caption: "Profile, holdings & goals", status: stages.includes("build_context") ? "Used" : "Not recorded", detail: "The saved financial profile and fixed assessment answers supply the personal context. Your income, expenses, holdings, liabilities and goals remain separate from market evidence." },
    { title: "Dhan market evidence", caption: "Daily candles → indicators", status: market?.available ? `${market.holdings?.length || 0} stocks covered` : "Limited", detail: market?.available ? `Completed daily candles produce SMA20/50, RSI14 and 20/50-session price returns. NIFTY 50 supplies the comparison. Benchmark date: ${market.benchmark?.as_of || "not recorded"}. These are dated observations, not streaming quotes.` : market?.reason || "This saved brief does not include verified holding-level market evidence. Missing data is not filled with invented indicators." },
    { title: "Equity & portfolio review", caption: fallback ? "Rules fallback" : "Evidence-led analysis", status: stages.includes("analyze") ? "Reviewed" : "Not recorded", detail: `${fallback ? "The primary analysis used a rule-based fallback." : "The recorded analyst reviews the supplied context."} Concentration, goal horizon, risk responses and available market evidence inform the review. Technical momentum alone does not establish suitability.` },
    { title: "Specialist checks", caption: "Tax · FDs · trajectory", status: `${specialists.filter((item) => item?.available).length} of 3 available`, detail: "Tax lots, deposit terms and planning scenarios add their own evidence and limits. A missing tax cost or deposit term remains a gap. Specialist disagreements are retained in the reasoning below." },
    { title: "Validation & limits", caption: "Constraints & data quality", status: result.validation?.passed ? "Passed" : "Review needed", detail: `Structural and request constraints are checked before returning the brief. This does not certify suitability or future outcomes. ${result.data_quality?.confidence_note || `Reported confidence: ${result.confidence}.`}` },
    { title: "Ranked review priorities", caption: "Evidence → useful next step", status: `${result.suggestions?.items?.length || 0} priorities`, detail: "Policy weights rank the suggested reviews and normalize relative support across this list. Support is not a probability of profit. Review the evidence, trade-offs and what-if scenarios before deciding; no trade is placed." },
  ];
  const positions = ["md:col-start-1 md:row-start-1", "md:col-start-2 md:row-start-1", "md:col-start-3 md:row-start-1", "md:col-start-3 md:row-start-2", "md:col-start-2 md:row-start-2", "md:col-start-1 md:row-start-2"];
  return (
    <section id="decision-flow" aria-labelledby="decision-flow-title" className="decision-anchor rounded-[28px] border border-slate-200 bg-white p-5 sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-[10px] font-semibold uppercase tracking-[.18em] text-teal-700">The decision flow</p><h2 id="decision-flow-title" className="mt-2 text-xl font-semibold tracking-tight text-slate-900">How this brief came together.</h2><p className="mt-2 max-w-2xl text-xs leading-6 text-slate-500">Follow the recorded stages. Select a step to see the evidence and its limits.</p></div>
        <a href="#decision-evidence" className="text-xs font-medium text-teal-800 underline underline-offset-4">Open the full trace ↓</a>
      </div>
      <ol aria-label="Decision stages in execution order" className="mt-6 grid grid-cols-1 gap-7 md:grid-cols-3 md:gap-x-8 md:gap-y-9">
        {steps.map((step, index) => <li key={step.title} className={`relative min-w-0 ${positions[index]}`}>
          <button type="button" aria-pressed={selected === index} aria-controls="decision-flow-detail" onClick={() => setSelected(index)} className={`h-full w-full rounded-2xl border p-4 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-600 ${selected === index ? "border-teal-500 bg-teal-50 shadow-sm" : "border-slate-200 bg-slate-50/60 hover:border-teal-300"}`}>
            <span className="flex items-center justify-between gap-2"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#123b48] text-[11px] font-semibold text-white">{index + 1}</span><span className={`text-right text-[10px] font-medium ${step.status === "Limited" ? "text-amber-800" : "text-teal-800"}`}>{step.status}</span></span>
            <span className="mt-3 block text-sm font-semibold text-slate-900">{step.title}</span><span className="mt-1 block text-[11px] leading-5 text-slate-500">{step.caption}</span>
          </button>
          {index < 5 ? <><span aria-hidden className="absolute -bottom-6 left-1/2 text-slate-400 md:hidden">↓</span><span aria-hidden className={`absolute hidden text-xl text-teal-600 md:block ${index === 2 ? "-bottom-8 left-1/2" : index < 2 ? "-right-6 top-1/2 -translate-y-1/2" : "-left-6 top-1/2 -translate-y-1/2"}`}>{index === 2 ? "↓" : index < 2 ? "→" : "←"}</span></> : null}
        </li>)}
      </ol>
      <div id="decision-flow-detail" aria-live="polite" className="mt-6 rounded-2xl border border-teal-100 bg-[#f1f8f5] p-4"><p className="text-xs font-semibold text-teal-900">{selected + 1}. {steps[selected].title}</p><p className="mt-2 text-xs leading-6 text-slate-600">{steps[selected].detail}</p></div>
      <p className="mt-4 flex items-center gap-2 text-xs text-slate-600"><span aria-hidden className="text-lg text-teal-700">✓</span><strong className="font-semibold text-slate-800">You make the final decision.</strong> No automatic trades.</p>
    </section>
  );
}

export function HoldingMarketPanel({ result }: { result: DecisionResult }) {
  const data = result.holding_market_data;
  if (!data) return null;
  return <section id="decision-market" aria-labelledby="decision-market-title" className="decision-anchor rounded-[28px] border border-slate-200 bg-white p-5 sm:p-7">
    <p className="text-[10px] font-semibold uppercase tracking-[.18em] text-teal-700">Market evidence · Dhan</p>
    <h2 id="decision-market-title" className="mt-2 text-xl font-semibold tracking-tight text-slate-900">The numbers behind the market context.</h2>
    <p className="mt-2 text-xs leading-6 text-slate-500">{data.price_basis}</p>
    {!data.available ? <p className="mt-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">{data.reason || "Market data unavailable. No indicators have been invented."}</p> : <>
      <div role="region" aria-label="Dhan holding indicators" tabIndex={0} className="mt-5 overflow-x-auto rounded-xl border border-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-600">
        <table className="w-full min-w-[740px] text-left text-xs"><caption className="sr-only">Indicators calculated from completed daily Dhan candles, with per-stock dates</caption><thead className="bg-slate-50 text-slate-500"><tr>{["Holding / date", "Close", "SMA20", "SMA50", "RSI14", "20 sessions", "50 sessions", "vs NIFTY 50*"].map((label) => <th key={label} className="whitespace-nowrap px-3 py-3 font-medium">{label}</th>)}</tr></thead><tbody>{data.holdings?.map((row) => <tr key={row.isin} className="border-t border-slate-100"><td className="px-3 py-3"><strong className="font-semibold text-slate-900">{row.symbol}</strong><span className="mt-1 block text-[10px] text-slate-500">{row.as_of} · {row.candles} candles</span></td>{[formatCurrency(row.indicators.current_close), formatCurrency(row.indicators.dma_20), formatCurrency(row.indicators.dma_50), row.indicators.rsi_14.toFixed(1), `${row.indicators.return_20d.toFixed(2)}%`, `${row.indicators.return_50d.toFixed(2)}%`, row.indicators.rs_20d == null ? "Unavailable" : `${row.indicators.rs_20d.toFixed(2)} pp`].map((value, index) => <td key={index} className="whitespace-nowrap px-3 py-3 tabular-nums text-slate-700">{value}</td>)}</tr>)}</tbody></table>
      </div>
      <p className="mt-3 text-[10px] leading-5 text-slate-500">* 20-session price-return difference, in percentage points. Returns exclude dividends; corporate-action adjustment is not independently verified. No target price or predicted return is implied.</p>
    </>}
    {!!data.failed?.length && <p className="mt-3 text-xs text-amber-900">Unavailable histories: {data.failed.map((row) => row.name).join(", ")}.</p>}
    {!!data.unmapped?.length && <p className="mt-3 text-xs text-amber-900">No verified mapping: {data.unmapped.join(", ")}. These holdings are excluded from the indicator calculation.</p>}
    <p className="mt-3 text-xs leading-6 text-slate-500">{data.methodology}</p>
  </section>;
}
