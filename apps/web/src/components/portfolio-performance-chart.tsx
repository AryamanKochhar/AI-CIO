"use client";

import { useMemo, useState } from "react";
import { formatCurrency } from "@ai-cio/utils";

type Snapshot = {
  month_year?: string;
  valuation?: string | null;
  change_amount?: string | null;
  change_pct?: string | null;
};

function num(v: string | null | undefined): number {
  if (v == null || v === "") return 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

/** Historical portfolio valuation from CAS month-year snapshots. */
export function PortfolioPerformanceChart({ snapshots }: { snapshots: Snapshot[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const points = useMemo(() => {
    const rows = [...(snapshots || [])]
      .filter((s) => s.month_year && num(s.valuation) > 0)
      .sort((a, b) => String(a.month_year).localeCompare(String(b.month_year)));
    return rows;
  }, [snapshots]);

  if (points.length < 2) {
    return (
      <p className="text-sm text-slate-600">
        Need at least two monthly portfolio snapshots from your statements to draw a performance graph.
      </p>
    );
  }

  const width = 640;
  const height = 220;
  const pad = { t: 16, r: 16, b: 36, l: 56 };
  const vals = points.map((p) => num(p.valuation));
  const minY = Math.min(...vals) * 0.95;
  const maxY = Math.max(...vals) * 1.05;
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const x = (i: number) => pad.l + (i / Math.max(1, points.length - 1)) * plotW;
  const y = (v: number) => pad.t + plotH - ((v - minY) / Math.max(1, maxY - minY)) * plotH;
  const d = points.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(num(p.valuation))}`).join(" ");
  const area =
    `M ${x(0)} ${y(num(points[0].valuation))} ` +
    points
      .slice(1)
      .map((p, i) => `L ${x(i + 1)} ${y(num(p.valuation))}`)
      .join(" ") +
    ` L ${x(points.length - 1)} ${pad.t + plotH} L ${x(0)} ${pad.t + plotH} Z`;

  const first = vals[0];
  const last = vals[vals.length - 1];
  const changePct = first > 0 ? ((last - first) / first) * 100 : 0;

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-4 text-sm">
        <p className="text-slate-700">
          Latest: <strong>{formatCurrency(String(last))}</strong>
        </p>
        <p className={changePct >= 0 ? "text-emerald-700" : "text-rose-700"}>
          Period change: <strong>{changePct >= 0 ? "+" : ""}{changePct.toFixed(1)}%</strong>
        </p>
        <p className="text-slate-500">
          {points[0].month_year} → {points[points.length - 1].month_year}
        </p>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full min-w-[300px]" role="img">
        <title>Portfolio performance over time</title>
        <path d={area} fill="#0f766e22" />
        <path d={d} fill="none" stroke="#0f766e" strokeWidth={2.25} strokeLinejoin="round" />
        {points.map((p, i) => (
          <circle
            key={p.month_year}
            cx={x(i)}
            cy={y(num(p.valuation))}
            r={hover === i ? 5 : 3}
            fill="#0f766e"
          />
        ))}
        <rect
          x={pad.l}
          y={pad.t}
          width={plotW}
          height={plotH}
          fill="transparent"
          onMouseMove={(e) => {
            const rect = (e.target as SVGRectElement).getBoundingClientRect();
            const rel = (e.clientX - rect.left) / Math.max(1, rect.width);
            setHover(Math.round(rel * (points.length - 1)));
          }}
          onMouseLeave={() => setHover(null)}
        />
        {[0, points.length - 1].map((i) => (
          <text key={i} x={x(i)} y={height - 10} textAnchor="middle" fontSize={10} fill="#64748b">
            {points[i].month_year}
          </text>
        ))}
      </svg>
      {hover != null && points[hover] ? (
        <p className="mt-2 text-xs text-slate-600">
          {points[hover].month_year}: {formatCurrency(points[hover].valuation || "0")}
          {points[hover].change_pct != null ? ` (${points[hover].change_pct}% MoM)` : ""}
        </p>
      ) : (
        <p className="mt-2 text-xs text-slate-500">Hover for monthly valuation. Source: statement snapshots.</p>
      )}
    </div>
  );
}
