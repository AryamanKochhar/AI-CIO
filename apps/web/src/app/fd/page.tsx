"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import {
  Button,
  ErrorState,
  Input,
  Label,
  LoadingState,
  StatusBadge,
} from "@ai-cio/ui";
import type { FdIntelligence } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { fdApi } from "@/lib/api";
import { useRequireAuth } from "@/hooks/use-journey";
import { DecisionNextSteps } from "@/components/decision-next-steps";

export default function FdPage() {
  const user = useRequireAuth();
  const [data, setData] = useState<FdIntelligence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [bankName, setBankName] = useState("");
  const [accountLabel, setAccountLabel] = useState("");
  const [principal, setPrincipal] = useState("");
  const [rate, setRate] = useState("");
  const [tenure, setTenure] = useState("");
  const [maturity, setMaturity] = useState("");
  const [senior, setSenior] = useState(false);

  async function load(refresh = false) {
    if (!user) return;
    setError(null);
    const payload = await fdApi.summary(user.id, refresh);
    setData(payload);
  }

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    load(false).catch((err: Error) => {
      if (!cancelled) setError(err.message || "Could not load FD intelligence.");
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!user) return;
    setFormError(null);
    setSaving(true);
    try {
      await fdApi.create(user.id, {
        bank_name: bankName.trim(),
        principal: principal.trim(),
        account_label: accountLabel.trim() || undefined,
        interest_rate_pa: rate.trim() || undefined,
        tenure_months: tenure.trim() ? Number(tenure) : undefined,
        maturity_date: maturity.trim() || undefined,
        is_senior_citizen: senior,
      });
      setBankName("");
      setAccountLabel("");
      setPrincipal("");
      setRate("");
      setTenure("");
      setMaturity("");
      setSenior(false);
      await load(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not save FD.");
    } finally {
      setSaving(false);
    }
  }

  async function onDelete(id: number) {
    if (!user) return;
    await fdApi.remove(user.id, id);
    await load(false);
  }

  if (!user) return null;
  if (error) return <ErrorState title="FD intelligence unavailable" message={error} />;
  if (!data) return <LoadingState message="Loading fixed deposits and bank FD rates…" />;

  const summary = data.summary || {};
  const rates = data.market_rates?.rates || [];
  const rateStatus = data.market_rates?.status;

  return (
    <div className="space-y-8">
      <DecisionNextSteps />
      <section className="aic-glass-strong rounded-2xl p-5 sm:p-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--aic-blue-muted)]">
          Fixed deposits
        </p>
        <h1 className="aic-title mt-2">Bank FDs & liquidity</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          Track your bank fixed deposits, compare scraped public FD rates, and see liquidity context from liquid
          savings.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <StatusBadge status={data.available ? "known" : "unknown"}>
            {data.status || "ready"}
          </StatusBadge>
          {rateStatus ? <StatusBadge status="unknown">Rates: {rateStatus}</StatusBadge> : null}
          <Button
            variant="secondary"
            onClick={() =>
              load(true).catch((err: Error) => setError(err.message || "Refresh failed"))
            }
          >
            Refresh rates
          </Button>
          <Link href="/decisions">
            <Button variant="secondary">Open decisions</Button>
          </Link>
        </div>
        <div className="mt-6 grid grid-cols-2 gap-6 border-t border-[rgba(15,55,110,0.1)] pt-6 sm:grid-cols-4">
          <div>
            <p className="aic-meta uppercase tracking-[0.08em]">Total principal</p>
            <p className="aic-num mt-1 text-2xl font-semibold text-[var(--aic-navy)] sm:text-3xl">
              {summary.total_principal ? formatCurrency(summary.total_principal) : "—"}
            </p>
          </div>
          <div>
            <p className="aic-meta uppercase tracking-[0.08em]">FDs</p>
            <p className="aic-num mt-1 text-2xl font-semibold text-[var(--aic-navy)] sm:text-3xl">
              {String(summary.fd_count ?? 0)}
            </p>
          </div>
          <div>
            <p className="aic-meta uppercase tracking-[0.08em]">Liquid cash</p>
            <p className="aic-num mt-1 text-2xl font-semibold text-[var(--aic-navy)] sm:text-3xl">
              {summary.liquid_cash ? formatCurrency(summary.liquid_cash) : "—"}
            </p>
          </div>
          <div>
            <p className="aic-meta uppercase tracking-[0.08em]">Cash + FDs</p>
            <p className="aic-num mt-1 text-2xl font-semibold text-[var(--aic-navy)] sm:text-3xl">
              {summary.combined_cash_and_fd ? formatCurrency(summary.combined_cash_and_fd) : "—"}
            </p>
          </div>
        </div>
        {data.disclaimer ? <p className="mt-4 text-xs text-slate-400">{data.disclaimer}</p> : null}
      </section>

      {(data.comments || []).length > 0 ? (
        <section className="aic-surface rounded-2xl p-5 sm:p-6">
          <h2 className="aic-section-title">FD comments</h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            {(data.comments || []).map((c) => (
              <li key={c} className="border-b border-[rgba(15,55,110,0.06)] py-2 last:border-0">
                {c}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="aic-surface rounded-2xl p-5 sm:p-6">
          <h2 className="aic-section-title">Your bank FDs</h2>
          <p className="mt-1 text-sm text-slate-600">Add each fixed deposit by bank / account.</p>
          {(data.fixed_deposits || []).length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No FDs recorded yet.</p>
          ) : (
            <ul className="mt-4 divide-y divide-[rgba(15,55,110,0.08)]">
              {(data.fixed_deposits || []).map((fd) => (
                <li key={fd.id} className="py-4 first:pt-0">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-slate-900">{fd.bank_name}</p>
                      {fd.account_label ? (
                        <p className="text-xs text-slate-500">{fd.account_label}</p>
                      ) : null}
                    </div>
                    <Button variant="ghost" onClick={() => fd.id != null && onDelete(fd.id)}>
                      Remove
                    </Button>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
                    <span>Principal {formatCurrency(fd.principal)}</span>
                    {fd.interest_rate_pa ? <span>Rate {fd.interest_rate_pa}% p.a.</span> : null}
                    {fd.tenure_months != null ? <span>{fd.tenure_months} months</span> : null}
                    {fd.maturity_date ? <span>Matures {fd.maturity_date}</span> : null}
                    {fd.rate_gap_pa ? <span>vs market max Δ {fd.rate_gap_pa}%</span> : null}
                  </div>
                </li>
              ))}
            </ul>
          )}

          <form onSubmit={onSubmit} className="mt-6 space-y-3 border-t border-[rgba(15,55,110,0.1)] pt-4">
            <h3 className="text-sm font-semibold text-slate-900">Add fixed deposit</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="fd-bank">Bank</Label>
                <Input
                  id="fd-bank"
                  value={bankName}
                  onChange={(e) => setBankName(e.target.value)}
                  placeholder="HDFC Bank"
                  required
                />
              </div>
              <div>
                <Label htmlFor="fd-account">Account / label</Label>
                <Input
                  id="fd-account"
                  value={accountLabel}
                  onChange={(e) => setAccountLabel(e.target.value)}
                  placeholder="Savings-linked FD"
                />
              </div>
              <div>
                <Label htmlFor="fd-principal">Principal (₹)</Label>
                <Input
                  id="fd-principal"
                  value={principal}
                  onChange={(e) => setPrincipal(e.target.value)}
                  required
                />
              </div>
              <div>
                <Label htmlFor="fd-rate">Booked rate % p.a.</Label>
                <Input id="fd-rate" value={rate} onChange={(e) => setRate(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="fd-tenure">Tenure (months)</Label>
                <Input id="fd-tenure" value={tenure} onChange={(e) => setTenure(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="fd-maturity">Maturity date</Label>
                <Input
                  id="fd-maturity"
                  type="date"
                  value={maturity}
                  onChange={(e) => setMaturity(e.target.value)}
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={senior} onChange={(e) => setSenior(e.target.checked)} />
              Senior citizen rate
            </label>
            {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Add FD"}
            </Button>
          </form>
        </section>

        <section className="aic-surface rounded-2xl p-5 sm:p-6">
          <h2 className="aic-section-title">Market rates</h2>
          <p className="mt-1 text-sm text-slate-600">
            Source: {data.market_rates?.source || "—"}
            {data.market_rates?.as_of_note ? ` · ${data.market_rates.as_of_note}` : ""}
          </p>
          {data.market_rates?.scrape_error ? (
            <p className="mt-2 text-xs text-amber-700">Scrape note: {data.market_rates.scrape_error}</p>
          ) : null}
          {rates.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No rates available.</p>
          ) : (
            <div className="mt-4 max-h-[32rem] overflow-auto">
              <table className="aic-table">
                <thead>
                  <tr>
                    <th>Bank</th>
                    <th className="text-right">General</th>
                    <th className="text-right">Senior</th>
                  </tr>
                </thead>
                <tbody>
                  {rates.map((row) => (
                    <tr key={row.bank}>
                      <td className="font-medium text-slate-900">{row.bank}</td>
                      <td className="num">
                        {row.general_min}
                        {row.general_max && row.general_max !== row.general_min
                          ? `–${row.general_max}`
                          : ""}
                        %
                      </td>
                      <td className="num">
                        {row.senior_min || "—"}
                        {row.senior_max && row.senior_max !== row.senior_min
                          ? `–${row.senior_max}`
                          : ""}
                        {row.senior_min ? "%" : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {data.market_rates?.source_url ? (
            <a
              href={data.market_rates.source_url}
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-block text-xs font-medium text-slate-800 underline"
            >
              View source website
            </a>
          ) : null}
        </section>
      </div>

      {(data.maturity_alerts || []).length > 0 || (data.opportunities || []).length > 0 ? (
        <section className="aic-surface rounded-2xl p-5 sm:p-6">
          <h2 className="aic-section-title">Alerts & opportunities</h2>
          <ul className="mt-4 space-y-3">
            {(data.maturity_alerts || []).map((a) => (
              <li
                key={`${a.bank_name}-${a.days_to_maturity}`}
                className="border-b border-amber-100/80 py-3 text-sm text-slate-800 last:border-0"
              >
                {a.reason}
              </li>
            ))}
            {(data.opportunities || []).map((o, idx) => (
              <li
                key={`${o.type}-${idx}`}
                className="border-b border-[rgba(15,55,110,0.08)] py-3 text-sm text-slate-800 last:border-0"
              >
                <p className="text-xs uppercase tracking-wide text-slate-500">{o.type}</p>
                <p className="mt-1">{o.reason}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
