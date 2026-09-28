"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Button,
  Card,
  ErrorState,
  LoadingState,
  PageHeader,
  StatusBadge,
} from "@ai-cio/ui";
import type { TaxIntelligence, TaxOpportunity } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { taxApi } from "@/lib/api";
import { useRequireAuth } from "@/hooks/use-journey";

function Metric({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">
        {value != null && value !== "" ? formatCurrency(value) : "—"}
      </p>
    </div>
  );
}

function OpportunityCard({ item }: { item: TaxOpportunity }) {
  return (
    <li className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-medium text-slate-900">{item.label || item.type || "Opportunity"}</p>
        {item.term ? (
          <span className="text-xs uppercase tracking-wide text-slate-500">{item.term.replace(/_/g, " ")}</span>
        ) : null}
        {item.confidence != null ? (
          <StatusBadge status={item.confidence >= 0.5 ? "known" : "unknown"}>
            Confidence {(item.confidence * 100).toFixed(0)}%
          </StatusBadge>
        ) : null}
      </div>
      {item.security ? <p className="mt-1 text-sm font-medium text-slate-800">{item.security}</p> : null}
      <p className="mt-2 text-sm text-slate-700">{item.reason}</p>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
        {item.amount ? <span>Amount: {formatCurrency(item.amount)}</span> : null}
        {item.estimated_tax_impact ? (
          <span>Est. tax impact: {formatCurrency(item.estimated_tax_impact)}</span>
        ) : null}
        {item.threshold_remaining ? (
          <span>Threshold remaining: {formatCurrency(item.threshold_remaining)}</span>
        ) : null}
        {item.holding_period_days != null ? <span>Holding days: {item.holding_period_days}</span> : null}
      </div>
      {item.risks && item.risks.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-500">
          {item.risks.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export default function TaxPage() {
  const user = useRequireAuth();
  const [data, setData] = useState<TaxIntelligence | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setError(null);
    taxApi
      .summary(user.id)
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || "Could not load tax intelligence.");
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (!user) return null;
  if (error) return <ErrorState title="Tax intelligence unavailable" message={error} />;
  if (!data) return <LoadingState message="Building tax lots and capital-gains estimates…" />;

  const summary = data.summary || {};
  const loss = data.loss_inventory || {};
  const est = (data.tax_estimate || {}) as Record<string, string | undefined>;
  const tlh = (data.opportunities || []).filter((o) => o.type === "tax_loss_harvesting");
  const gainHarvest = (data.opportunities || []).filter((o) => o.type === "gain_harvesting");
  const lossUtil = (data.opportunities || []).filter((o) => o.type === "loss_utilization");
  const realized = data.tax_lots?.realized || [];
  const unrealized = data.tax_lots?.unrealized || [];

  return (
    <div className="space-y-6">
      <div id="overview">
      <Card className="aic-card-glow">
        <PageHeader
          kicker="Tax intelligence"
          title="Your capital-gains position"
          description="Deterministic estimates from uploaded CDSL / NSDL / broker data. Analytical only — not tax advice."
        />
        <div className="mt-3 flex flex-wrap gap-2">
          {data.financial_year ? (
            <StatusBadge status="known">FY {data.financial_year}</StatusBadge>
          ) : null}
          {data.assessment_year ? (
            <StatusBadge status="known">AY {data.assessment_year}</StatusBadge>
          ) : null}
          {data.rule_version ? (
            <StatusBadge status="unknown">Rule {data.rule_version}</StatusBadge>
          ) : null}
          <StatusBadge status={data.available ? "known" : "unknown"}>
            {data.status || (data.available ? "ready" : "incomplete")}
          </StatusBadge>
        </div>
        {!data.available ? (
          <p className="mt-4 text-sm text-amber-800">
            {data.reason ||
              "Upload portfolio documents so holdings and transactions can feed the tax engine."}
          </p>
        ) : null}
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="STCG" value={summary.stcg} />
          <Metric label="LTCG" value={summary.ltcg} />
          <Metric label="STCL" value={summary.stcl} />
          <Metric label="LTCL" value={summary.ltcl} />
          <Metric label="Unrealized gains" value={summary.unrealized_gains} />
          <Metric label="Unrealized losses" value={summary.unrealized_losses} />
          <Metric label="Estimated CG tax" value={summary.estimated_tax} />
          <Metric label="Realized gains" value={summary.realized_gains} />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-slate-200 bg-white px-3 py-3 text-sm text-slate-700">
            <p className="text-xs uppercase tracking-wide text-slate-500">Est. STCG tax</p>
            <p className="mt-1 font-semibold">{formatCurrency(est.estimated_stcg_tax)}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white px-3 py-3 text-sm text-slate-700">
            <p className="text-xs uppercase tracking-wide text-slate-500">Est. LTCG tax</p>
            <p className="mt-1 font-semibold">{formatCurrency(est.estimated_ltcg_tax)}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white px-3 py-3 text-sm text-slate-700">
            <p className="text-xs uppercase tracking-wide text-slate-500">112A exemption applied</p>
            <p className="mt-1 font-semibold">{formatCurrency(est.ltcg_exemption_applied)}</p>
          </div>
        </div>
        {data.disclaimer ? <p className="mt-4 text-xs text-slate-400">{data.disclaimer}</p> : null}
      </Card>
      </div>

      {data.alerts && data.alerts.length > 0 ? (
        <Card className="aic-card-glow">
          <h2 className="text-base font-semibold text-slate-900">Tax alerts</h2>
          <p className="mt-1 text-sm text-slate-600">Events derived from the tax engine — not LLM guesses.</p>
          <ul className="mt-4 space-y-2">
            {data.alerts.map((alert) => (
              <li
                key={`${alert.type}-${alert.title}`}
                className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium text-slate-900">{alert.title}</p>
                  {alert.severity ? (
                    <StatusBadge status={alert.severity === "warning" ? "unknown" : "known"}>
                      {alert.severity}
                    </StatusBadge>
                  ) : null}
                </div>
                <p className="mt-1 text-sm text-slate-700">{alert.detail}</p>
                {alert.href ? (
                  <a href={alert.href} className="mt-2 inline-block text-xs font-medium text-slate-800 underline">
                    Jump to section
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {data.comments && data.comments.length > 0 ? (
        <Card className="aic-card-glow">
          <h2 className="text-base font-semibold text-slate-900">Tax comments</h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            {data.comments.map((c) => (
              <li key={c} className="rounded-lg bg-white px-3 py-2 ring-1 ring-slate-100">
                {c}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2" id="harvesting">
        <Card className="aic-card-glow">
          <h2 className="text-base font-semibold text-slate-900">Tax-loss harvesting</h2>
          <p className="mt-1 text-sm text-slate-600">
            Potential opportunities to realize losses that may offset eligible gains — subject to rules and portfolio goals.
          </p>
          {tlh.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No TLH candidates with usable cost data right now.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {tlh.map((item) => (
                <OpportunityCard key={`${item.security}-${item.amount}`} item={item} />
              ))}
            </ul>
          )}
        </Card>

        <Card className="aic-card-glow">
          <h2 className="text-base font-semibold text-slate-900">Gain harvesting</h2>
          <p className="mt-1 text-sm text-slate-600">
            Where realizing eligible LTCG may stay within the configured 112A threshold headroom.
          </p>
          {gainHarvest.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No gain-harvesting candidates identified.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {gainHarvest.map((item) => (
                <OpportunityCard key={`${item.security}-${item.amount}`} item={item} />
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div id="holding-period">
      <Card className="aic-card-glow">
        <h2 className="text-base font-semibold text-slate-900">Holding-period events</h2>
        <p className="mt-1 text-sm text-slate-600">
          Securities approaching the long-term classification boundary. The system shows tax consequence, not “wait.”
        </p>
        {(data.holding_period_events || []).length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">No near-term holding-period events with usable dates.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {(data.holding_period_events || []).map((ev) => (
              <li key={`${ev.security}-${ev.days_to_long_term}`} className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium text-slate-900">{ev.security}</p>
                  <StatusBadge status="known">
                    {ev.days_to_long_term != null ? `${ev.days_to_long_term} days to LT` : "Approaching LT"}
                  </StatusBadge>
                </div>
                <p className="mt-2 text-sm text-slate-700">{ev.reason}</p>
                {ev.unrealized_gain_loss ? (
                  <p className="mt-1 text-xs text-slate-500">
                    Unrealized: {formatCurrency(ev.unrealized_gain_loss)}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Card>
      </div>

      <div id="losses">
      <Card className="aic-card-glow">
        <h2 className="text-base font-semibold text-slate-900">Loss inventory</h2>
        <p className="mt-1 text-sm text-slate-600">Current-year realized losses from available transactions.</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Metric label="Current-year STCL" value={loss.current_year_stcl} />
          <Metric label="Current-year LTCL" value={loss.current_year_ltcl} />
        </div>
        <p className="mt-3 text-sm text-slate-600">
          Prior-year STCL / LTCL:{" "}
          {loss.carry_forward_history === "unavailable"
            ? "Carry-forward history unavailable"
            : "See note below"}
        </p>
        {loss.note ? <p className="mt-2 text-xs text-slate-500">{loss.note}</p> : null}
        {lossUtil.length > 0 ? (
          <ul className="mt-4 space-y-3">
            {lossUtil.map((item) => (
              <OpportunityCard key={item.reason} item={item} />
            ))}
          </ul>
        ) : null}
      </Card>
      </div>

      <div id="data-quality">
      <Card className="aic-card-glow">
        <h2 className="text-base font-semibold text-slate-900">Tax data quality</h2>
        <p className="mt-1 text-sm text-slate-600">
          {data.data_quality?.message || "Coverage of holdings with usable cost information."}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {data.data_quality?.coverage_pct != null ? (
            <StatusBadge status={data.data_quality.coverage_pct >= 70 ? "known" : "unknown"}>
              {data.data_quality.coverage_pct}% coverage
            </StatusBadge>
          ) : null}
          {data.data_quality?.insufficient_cost_basis_count != null ? (
            <StatusBadge status="unknown">
              {data.data_quality.insufficient_cost_basis_count} need review
            </StatusBadge>
          ) : null}
        </div>
        {(data.missing_data || []).length > 0 ? (
          <ul className="mt-4 max-h-64 space-y-2 overflow-y-auto text-sm text-slate-700">
            {(data.missing_data || []).slice(0, 20).map((row, idx) => (
              <li key={`${row.security}-${idx}`} className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2">
                <span className="font-medium">{String(row.security || "Unknown")}</span>
                {row.reason ? ` — ${String(row.reason).replace(/_/g, " ")}` : ""}
                {row.note ? ` (${String(row.note)})` : ""}
              </li>
            ))}
          </ul>
        ) : null}
      </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="aic-card-glow">
          <h2 className="text-base font-semibold text-slate-900">Realized tax lots</h2>
          <p className="mt-1 text-sm text-slate-600">Traceable FIFO lots from transactions (sample).</p>
          {realized.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No realized lots reconstructed yet.</p>
          ) : (
            <ul className="mt-4 max-h-80 space-y-2 overflow-y-auto text-sm">
              {realized.slice(0, 40).map((lot, idx) => (
                <li
                  key={`${lot.security}-${lot.sale_date}-${idx}`}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2"
                >
                  <p className="font-medium text-slate-900">{String(lot.security)}</p>
                  <p className="text-xs text-slate-500">
                    {String(lot.acquisition_date)} → {String(lot.sale_date)} · {String(lot.term || "—")} · gain{" "}
                    {formatCurrency(String(lot.gain_loss ?? ""))}
                  </p>
                  {Array.isArray(lot.source_transaction_ids) ? (
                    <p className="mt-1 text-[11px] text-slate-400">
                      Sources: {(lot.source_transaction_ids as string[]).slice(0, 3).join(", ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="aic-card-glow">
          <h2 className="text-base font-semibold text-slate-900">Open lots (unrealized)</h2>
          <p className="mt-1 text-sm text-slate-600">Positions with usable cost / price for estimates.</p>
          {unrealized.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No open lots with usable cost data.</p>
          ) : (
            <ul className="mt-4 max-h-80 space-y-2 overflow-y-auto text-sm">
              {unrealized.slice(0, 40).map((lot, idx) => (
                <li
                  key={`${lot.security}-${lot.acquisition_date}-${idx}`}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2"
                >
                  <p className="font-medium text-slate-900">{String(lot.security)}</p>
                  <p className="text-xs text-slate-500">
                    Qty {String(lot.qty)} · {String(lot.term || "term unknown")} · unrealized{" "}
                    {formatCurrency(String(lot.unrealized_gain_loss ?? ""))}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card className="aic-card-glow">
        <h2 className="text-base font-semibold text-slate-900">Use this in decisions</h2>
        <p className="mt-1 text-sm text-slate-600">
          The Tax Agent runs with Decisions so recommendations can show estimated tax impact.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link href="/decisions">
            <Button>Open decisions</Button>
          </Link>
          <Link href="/onboarding/documents">
            <Button variant="secondary">Upload statements</Button>
          </Link>
        </div>
        {data.assumptions && data.assumptions.length > 0 ? (
          <ul className="mt-4 list-disc space-y-1 pl-5 text-xs text-slate-500">
            {data.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        ) : null}
      </Card>
    </div>
  );
}
