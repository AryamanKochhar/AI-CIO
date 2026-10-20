"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { MutualFundIntelligence } from "@ai-cio/contracts";
import { Button, LoadingState } from "@ai-cio/ui";
import { useRequireAuth } from "@/hooks/use-journey";
import { mutualFundsApi } from "@/lib/api";
import { jsonEvidence, parseMutualFundImport } from "@/lib/investment-evidence";
import { MutualFundPanel } from "@/components/mutual-funds/mutual-fund-panel";

const FORMAT = {
  disclosure: `{
  "scheme_code": "EXACT_MFAPI_SCHEME_CODE",
  "scheme_isin": "EXACT_PLAN_AND_OPTION_ISIN",
  "source_url": "https://OFFICIAL_AMC_HOST/ORIGINAL_DOCUMENT",
  "observed_on": "YYYY-MM-DD",
  "holdings": [{
    "isin": "UNDERLYING_SECURITY_ISIN",
    "name": "NAME_AS_DISCLOSED",
    "weight_pct": "FULL_SCHEME_NAV_PERCENTAGE",
    "asset_class": "equity",
    "sector": "SECTOR_AS_DISCLOSED"
  }],
  "benchmark_id": "EXACT_TOTAL_RETURN_BENCHMARK_ID",
  "benchmark_name": "OFFICIAL_BENCHMARK_NAME",
  "benchmark_source_url": "https://OFFICIAL_INDEX_HOST/SOURCE",
  "ter_percent": "OFFICIAL_PLAN_TER_IF_KNOWN",
  "exit_load": "EXACT_OFFICIAL_EXIT_LOAD_TEXT_IF_KNOWN"
}`,
  benchmark: `{
  "benchmark_id": "EXACT_TOTAL_RETURN_BENCHMARK_ID",
  "name": "OFFICIAL_TOTAL_RETURN_INDEX_NAME",
  "kind": "TRI",
  "source_url": "https://OFFICIAL_INDEX_HOST/ORIGINAL_SERIES",
  "observed_on": "YYYY-MM-DD",
  "points": [
    { "date": "YYYY-MM-DD", "value": "OFFICIAL_POSITIVE_INDEX_LEVEL" },
    { "date": "YYYY-MM-DD", "value": "OFFICIAL_POSITIVE_INDEX_LEVEL" }
  ]
}`,
};

function ImportCard({ kind, userId, onImported }: { kind: "disclosure" | "benchmark"; userId: number; onImported: () => void }) {
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);
  const [filename, setFilename] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const title = kind === "disclosure" ? "Scheme portfolio disclosure" : "Total-return benchmark history";
  async function select(file?: File) {
    setPayload(null); setError(null); setReceipt(null); setFilename(file?.name || "");
    if (!file) return;
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error("Keep the normalized JSON file below 2 MB.");
      setPayload(parseMutualFundImport(await file.text(), kind));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "This file could not be read."); }
  }
  async function upload() {
    if (!payload) return;
    setBusy(true); setError(null); setReceipt(null);
    try {
      const result = await (kind === "disclosure" ? mutualFundsApi.importDisclosure(userId, payload) : mutualFundsApi.importBenchmark(userId, payload));
      setReceipt(result); setPayload(null); onImported();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The import was not accepted."); }
    finally { setBusy(false); }
  }
  return <article className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5"><p className="text-[10px] font-semibold uppercase tracking-wider text-teal-700">{kind === "disclosure" ? "Holdings & mandate" : "Comparable performance"}</p><h3 className="mt-2 text-base font-semibold text-slate-900">{title}</h3><p className="mt-2 text-xs leading-6 text-slate-500">{kind === "disclosure" ? "Use the official AMC portfolio file for the exact scheme. Keep weights as a percentage of the full fund NAV, including when only part of the portfolio can be identified." : "Use an official, authorised total-return series for the scheme’s actual benchmark. A price index, another category’s benchmark or fabricated history is not equivalent."}</p><details className="mt-4 rounded-xl border border-slate-200 bg-slate-50/60 p-3"><summary className="cursor-pointer text-xs font-semibold text-slate-700">Required JSON structure</summary><p className="mt-3 text-[10px] leading-5 text-slate-500">The values below are field descriptions, not sample financial data. Replace them with the original disclosed values. Remove optional fields when unknown.</p><pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words text-[10px] leading-5 text-slate-600">{FORMAT[kind]}</pre></details><label htmlFor={`mf-import-${kind}`} className="mt-5 block text-xs font-medium text-slate-700">Select normalized JSON from the official document<input id={`mf-import-${kind}`} type="file" accept=".json,application/json" disabled={busy} onChange={(event) => void select(event.target.files?.[0])} className="mt-2 block w-full rounded-xl border border-slate-200 p-2 text-[10px] text-slate-500 file:mr-3 file:rounded-lg file:border-0 file:bg-teal-50 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-teal-800" /></label>{payload && <details className="mt-3 rounded-xl border border-teal-100 p-3"><summary className="cursor-pointer text-xs font-semibold text-teal-800">Review {filename} before importing</summary><pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words text-[10px] leading-5 text-slate-500">{jsonEvidence(payload)}</pre></details>}<Button className="mt-4" disabled={!payload || busy} onClick={() => void upload()}>{busy ? "Validating and importing…" : `Import ${kind}`}</Button>{error && <p role="alert" className="mt-3 text-xs leading-6 text-orange-900">{error}</p>}{receipt && <div role="status" className="mt-4 rounded-xl border border-teal-100 bg-teal-50/60 p-3"><p className="text-xs font-semibold text-teal-900">Import accepted. Refresh the analysis to use the new evidence.</p><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-[10px] leading-5 text-teal-900">{jsonEvidence(receipt)}</pre></div>}</article>;
}

export default function MutualFundsPage() {
  const user = useRequireAuth();
  const [analysis, setAnalysis] = useState<MutualFundIntelligence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  const [changed, setChanged] = useState(false);
  useEffect(() => {
    setAnalysis(null); setError(null);
    if (!user) return;
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    mutualFundsApi.analysis(user.id, controller.signal).then((data) => { if (active) { setAnalysis(data); setChanged(false); } }).catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Fund analysis is unavailable."); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [user, revision]);
  if (!user) return <LoadingState message="Checking sign-in…" />;
  return <div className="space-y-6"><section className="rounded-[28px] border border-teal-100 bg-[#f1f8f4] p-6 sm:p-8"><p className="text-[10px] font-semibold uppercase tracking-[.18em] text-teal-700">Mutual fund workspace</p><h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">A clear view beneath your funds.</h1><p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">Scheme identity and NAV history connect to your financial Twin. Official disclosures reveal underlying exposure; an appropriate total-return benchmark makes performance comparisons meaningful.</p><div className="mt-5 flex flex-wrap gap-3"><Link href="/decisions?objective=review_mutual_fund_portfolio"><Button>Build a coordinated fund decision ↗</Button></Link><Button variant="secondary" disabled={loading} onClick={() => setRevision((value) => value + 1)}>{loading ? "Reading fund evidence…" : "Refresh fund analysis"}</Button><Link href="/onboarding/documents?return=/mutual-funds" className="self-center text-xs font-semibold text-teal-800 underline underline-offset-4">Update my portfolio statement</Link></div>{changed && <p role="status" className="mt-4 text-xs font-semibold text-amber-900">Evidence changed. Refresh this analysis and rebuild any saved decision.</p>}</section>
    {error && <section role="alert" className="rounded-2xl border border-orange-200 bg-orange-50 p-5 text-sm leading-7 text-orange-900">{error}</section>}{loading && <p role="status" className="text-xs leading-6 text-slate-500">Loading the analysis from your stored holdings and available sources…</p>}{analysis && <MutualFundPanel data={analysis} showDataLink={false} />}
    <section id="mf-evidence-imports" className="rounded-[28px] border border-slate-200 bg-slate-50/50 p-5 sm:p-7"><p className="text-[10px] font-semibold uppercase tracking-[.18em] text-teal-700">Fill a source gap</p><h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-900">Add official disclosure or benchmark evidence.</h2><p className="mt-3 max-w-3xl text-xs leading-6 text-slate-600">These advanced imports accept normalized public investment data. Use the exact source document and observation date. The server validates the source host and structure; an uploaded URL alone does not independently authenticate the document.</p><div className="mt-5 grid gap-4 lg:grid-cols-2"><ImportCard key={`disclosure-${user.id}`} kind="disclosure" userId={user.id} onImported={() => setChanged(true)} /><ImportCard key={`benchmark-${user.id}`} kind="benchmark" userId={user.id} onImported={() => setChanged(true)} /></div><p className="mt-4 text-[10px] leading-6 text-slate-500">Imports are scoped to the active user. They add dated evidence and do not replace fund units, account transactions or questionnaire answers. Unknown inputs remain unknown.</p></section>
  </div>;
}
