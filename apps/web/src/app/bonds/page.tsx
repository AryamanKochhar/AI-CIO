"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { BondIntelligence } from "@ai-cio/contracts";
import { Button, LoadingState } from "@ai-cio/ui";
import { BondPanel } from "@/components/bonds/bond-panel";
import { useRequireAuth } from "@/hooks/use-journey";
import { bondsApi } from "@/lib/api";

export default function BondsPage() {
  const user = useRequireAuth();
  const [analysis, setAnalysis] = useState<BondIntelligence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    setAnalysis(null); setError(null);
    if (!user) return;
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    bondsApi.analysis(user.id, controller.signal).then((data) => { if (active) setAnalysis(data); }).catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Bond evidence could not be loaded."); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [user, revision]);
  if (!user) return <LoadingState message="Checking sign-in…" />;
  return <div className="space-y-6"><section className="rounded-[28px] border border-blue-100 bg-[#f3f7fc] p-6 sm:p-8"><p className="text-[10px] font-semibold uppercase tracking-[.18em] text-blue-800">Bond workspace</p><h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">Give every instrument a clear purpose.</h1><p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">Compare actual government-security and gold-bond terms with your goal dates. The Bond Agent works alongside the other specialists; the central coordinator keeps the budget and final priorities together.</p><div className="mt-5 flex flex-wrap gap-3"><Link href="/decisions?objective=review_bond_portfolio"><Button>Build a coordinated bond decision ↗</Button></Link><Button variant="secondary" disabled={loading} onClick={() => setRevision((value) => value + 1)}>{loading ? "Reading bond evidence…" : "Refresh bond evidence"}</Button></div></section>
    {error && <section role="alert" className="rounded-2xl border border-orange-200 bg-orange-50 p-5 text-sm leading-7 text-orange-900">{error}</section>}{loading && <p role="status" className="text-xs leading-6 text-slate-500">Reading the Dhan catalogue, supported market quotes and verified instrument terms…</p>}{analysis && <BondPanel data={analysis} showDataLink={false} onRefresh={() => setRevision((value) => value + 1)} refreshing={loading} />}
  </div>;
}
