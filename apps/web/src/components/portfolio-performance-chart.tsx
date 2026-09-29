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

const MONTH_INDEX: Record<string, number> = {
  jan: 1,
  january: 1,
  feb: 2,
  february: 2,
  mar: 3,
  march: 3,
  apr: 4,
  april: 4,
  may: 5,
  jun: 6,
  june: 6,
  jul: 7,
  july: 7,
  aug: 8,
  august: 8,
  sep: 9,
  sept: 9,
  september: 9,
  oct: 10,
  october: 10,
  nov: 11,
  november: 11,
  dec: 12,
  december: 12,
};

/** Sort key YYYYMM for labels like "Apr 2026", "2026-04", "04/2026". */
function monthSortKey(raw: string | undefined): number {
  if (!raw) return 0;
  const s = raw.trim();
  // ISO-ish: 2026-04 or 2026/04
  const iso = s.match(/^(\d{4})[-/](\d{1,2})$/);
  if (iso) return Number(iso[1]) * 100 + Number(iso[2]);
  // 04-2026 / 04/2026
  const my = s.match(/^(\d{1,2})[-/](\d{4})$/);
  if (my) return Number(my[2]) * 100 + Number(my[1]);
  // Apr 2026 / April-2026
  const named = s.match(/^([A-Za-z]+)\s*[-/]?\s*(\d{4})$/);
  if (named) {
    const m = MONTH_INDEX[named[1].toLowerCase()];
    if (m) return Number(named[2]) * 100 + m;
  }
  return 0;
}

/** Historical portfolio valuation from CAS month-year snapshots. */
export function PortfolioPerformanceChart({ snapshots }: { snapshots: Snapshot[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const points = useMemo(() => {
    const rows = [...(snapshots || [])]
      .filter((s) => s.month_year && num(s.valuation) > 0)
      .sort((a, b) => monthSortKey(a.month_year) - monthSortKey(b.month_year));
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
  const height = 240;
  // Extra side padding so "Mon YYYY" end labels stay inside the SVG/card.
  const pad = { t: 16, r: 52, b: 44, l: 56 };
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
    <div className="overflow-visible">
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
      <div className="overflow-x-auto rounded-lg border border-slate-100 bg-white px-2 py-3 sm:px-3">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-auto w-full min-w-[320px] overflow-visible"
          role="img"
        >
          <title>Portfolio performance over time</title>
          <path d={area} fill="#0f766e22" />
          <path d={d} fill="none" stroke="#0f766e" strokeWidth={2.25} strokeLinejoin="round" />
          {points.map((p, i) => (
            <circle
              key={`${p.month_year}-${i}`}
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
          <text x={x(0)} y={height - 14} textAnchor="start" fontSize={11} fill="#64748b">
            {points[0].month_year}
          </text>
          <text
            x={x(points.length - 1)}
            y={height - 14}
            textAnchor="end"
            fontSize={11}
            fill="#64748b"
          >
            {points[points.length - 1].month_year}
          </text>
        </svg>
      </div>
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
