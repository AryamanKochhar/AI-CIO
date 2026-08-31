"use client";

import { useState } from "react";
import type { MarketContext, MarketObservation, MarketSectorRow } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { cn } from "@ai-cio/utils";

function changeClass(value: string | null | undefined) {
  if (!value) return "text-slate-600";
  const n = Number(value);
  if (n > 0) return "text-emerald-700";
  if (n < 0) return "text-rose-700";
  return "text-slate-600";
}

function SectorHeatmap({
  sectors,
  exposure,
  onSelect,
  selected,
}: {
  sectors: MarketSectorRow[];
  exposure?: Record<string, unknown>;
  onSelect: (code: string) => void;
  selected: string | null;
}) {
  const expSectors = ((exposure?.sectors as Array<Record<string, string>>) || []);
  const expByCode = Object.fromEntries(
    expSectors.map((s) => [s.sector_index_code || s.sector_name, s]),
  );

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Sector</th>
            <th className="px-4 py-3">Today</th>
            <th className="px-4 py-3">Relative</th>
            <th className="px-4 py-3">Your exposure</th>
          </tr>
        </thead>
        <tbody>
          {sectors.map((row) => {
            const exp = expByCode[row.index_code] || expByCode[row.index_name];
            const active = selected === row.index_code;
            return (
              <tr
                key={row.index_code}
                className={cn("cursor-pointer border-t border-slate-100 hover:bg-slate-50", active && "bg-slate-100")}
                onClick={() => onSelect(row.index_code)}
              >
                <td className="px-4 py-3 font-medium text-slate-900">{row.index_name}</td>
                <td className={cn("px-4 py-3 font-medium", changeClass(row.change_percent))}>
                  {row.change_percent != null ? `${row.change_percent}%` : "—"}
                </td>
                <td className={cn("px-4 py-3", changeClass(row.relative_to_benchmark))}>
                  {row.relative_to_benchmark != null ? `${row.relative_to_benchmark} pp` : "—"}
                </td>
                <td className="px-4 py-3 text-slate-700">
                  {exp?.weight_percent ? `${exp.weight_percent}%` : exp?.value ? formatCurrency(exp.value) : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ObservationCard({ obs }: { obs: MarketObservation }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-semibold text-slate-900">
        {obs.sector_name} sector moved {obs.market_move_percent}%
      </p>
      {obs.user_exposure_value ? (
        <p className="mt-1 text-sm text-slate-700">
          Your identified exposure: {formatCurrency(obs.user_exposure_value)}
          {obs.user_exposure_percent ? ` (${obs.user_exposure_percent}% of equity)` : ""}
        </p>
      ) : null}
      <p className="mt-2 text-xs text-slate-500">
        Nifty 50: {obs.benchmark_move_percent ?? "—"}%
        {obs.relative_move_percent ? ` · Relative: ${obs.relative_move_percent} pp` : ""}
      </p>
      <p className="mt-2 text-xs text-slate-600">
        This is a market observation, not a buy or sell instruction.
      </p>
    </article>
  );
}

export function MarketContextPanel({ context }: { context: MarketContext }) {
  const [selected, setSelected] = useState<string | null>(null);
  if (!context.available) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
        {context.note || "Market context is not available right now."}
      </div>
    );
  }

  const sectors = context.sectors || [];
  const selectedRow = sectors.find((s) => s.index_code === selected);
  const expSectors = (context.sector_exposure?.sectors as Array<Record<string, string>>) || [];
  const selectedExp = expSectors.find((s) => s.sector_index_code === selected);
  const mfNote = (context.sector_exposure as { mutual_fund_lookthrough?: { note?: string } } | undefined)
    ?.mutual_fund_lookthrough?.note;

  return (
    <section className="space-y-4" aria-label="Market context">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Market today</p>
          <h3 className="text-lg font-semibold text-slate-900">
            {context.benchmark?.index_code ?? "Nifty 50"}
            {context.benchmark?.change_percent != null ? (
              <span className={cn("ml-2", changeClass(context.benchmark.change_percent))}>
                {context.benchmark.change_percent}%
              </span>
            ) : null}
          </h3>
          <p className="text-xs text-slate-500">
            As of {context.as_of ? new Date(context.as_of).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) : "—"}
            {" · "}Source: {context.source?.toUpperCase() ?? "NSE"}
            {" · "}Freshness: {context.freshness}
            {context.is_stale ? " (delayed)" : ""}
          </p>
        </div>
      </div>

      {context.breadth?.note ? (
        <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-700">{String(context.breadth.note)}</p>
      ) : null}

      <SectorHeatmap
        sectors={sectors}
        exposure={context.sector_exposure}
        onSelect={setSelected}
        selected={selected}
      />

      {selectedRow ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <p className="text-xs uppercase tracking-wide text-slate-500">Sector detail</p>
          <h4 className="text-base font-semibold text-slate-900">{selectedRow.index_name}</h4>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-slate-500">Today</dt>
              <dd className={changeClass(selectedRow.change_percent)}>{selectedRow.change_percent}%</dd>
            </div>
            <div>
              <dt className="text-slate-500">Relative</dt>
              <dd>{selectedRow.relative_to_benchmark ?? "—"} pp</dd>
            </div>
            {selectedExp ? (
              <>
                <div>
                  <dt className="text-slate-500">Your exposure</dt>
                  <dd>{selectedExp.value ? formatCurrency(selectedExp.value) : "—"}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Weight</dt>
                  <dd>{selectedExp.weight_percent ? `${selectedExp.weight_percent}%` : "—"}</dd>
                </div>
              </>
            ) : (
              <div className="col-span-2 text-slate-600">No identified direct equity exposure in this sector.</div>
            )}
          </dl>
        </div>
      ) : null}

      {mfNote ? <p className="text-xs text-slate-500">{mfNote}</p> : null}

      {(context.observations?.length ?? 0) > 0 ? (
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-slate-900">Why AI-CIO is showing this</h4>
          {context.observations!.map((obs, i) => (
            <ObservationCard key={`${obs.sector_index_code}-${i}`} obs={obs} />
          ))}
        </div>
      ) : null}

      {context.llm?.enabled && !context.llm.analysis_available ? (
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          AI analysis is temporarily unavailable. Market observations and your exposure data remain available.
        </p>
      ) : null}

      {(context.recent_analyses?.length ?? 0) > 0 ? (
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-slate-900">AI-CIO&apos;s analysis</h4>
          {context.recent_analyses!.map((item, i) => (
            <article key={`analysis-${i}`} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              {item.sector_name ? (
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{item.sector_name}</p>
              ) : null}
              {item.summary ? <p className="mt-1 text-sm text-slate-900">{item.summary}</p> : null}
              {(item.why_relevant?.length ?? 0) > 0 ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                  {item.why_relevant!.map((line, j) => (
                    <li key={j}>{line}</li>
                  ))}
                </ul>
              ) : null}
              <p className="mt-2 text-xs text-slate-500">
                Confidence: {item.confidence ?? "—"}
                {item.created_at
                  ? ` · ${new Date(item.created_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })}`
                  : ""}
              </p>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
