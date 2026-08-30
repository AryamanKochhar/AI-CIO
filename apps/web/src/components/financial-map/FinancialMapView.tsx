"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FinancialMap, FinancialMapInsight, FinancialMapNode } from "@ai-cio/contracts";
import { formatCurrency, formatDate } from "@ai-cio/utils";
import { cn } from "@ai-cio/utils";
import { Button, RevealToggle, SensitiveRevealProvider, SensitiveValue, StatusBadge } from "@ai-cio/ui";
import {
  NodeBadge,
  ancestorsOf,
  childrenOf,
  filterNodes,
  nodeById,
  searchMap,
} from "./map-utils";

const INSIGHT_STYLES: Record<FinancialMapInsight["category"], string> = {
  information: "border-slate-200 bg-white",
  attention: "border-amber-200 bg-amber-50",
  data_gap: "border-slate-200 bg-slate-50",
  positive: "border-emerald-200 bg-emerald-50",
};

function CompletenessSummary({ map }: { map: FinancialMap }) {
  const labels: Record<string, string> = {
    psychometric: "Behaviour",
    portfolio: "Investments",
    goals: "Goals",
    income: "Income",
    expenses: "Expenses",
    liquid: "Cash",
    liabilities: "Liabilities",
    horizon: "Time horizon",
  };
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Financial picture</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{map.completeness.understood_pct}%</p>
      <p className="text-xs text-slate-500">of your financial picture is currently understood</p>
      <ul className="mt-3 grid grid-cols-2 gap-1.5 text-sm">
        {Object.entries(map.completeness.flags).map(([key, known]) => (
          <li key={key} className={cn("flex items-center gap-1.5", known ? "text-slate-800" : "text-slate-400")}>
            <span aria-hidden>{known ? "✓" : "○"}</span>
            {labels[key] ?? key}
          </li>
        ))}
      </ul>
    </div>
  );
}

function InsightPanel({
  insights,
  onExplore,
}: {
  insights: FinancialMapInsight[];
  onExplore: (id: string) => void;
}) {
  if (!insights.length) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
        Insights will appear as more of your financial picture is filled in.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-slate-900">Things worth knowing</h3>
      {insights.map((insight) => (
        <article
          key={insight.id}
          className={cn("rounded-2xl border px-4 py-3", INSIGHT_STYLES[insight.category])}
        >
          <div className="mb-1 flex items-center justify-between gap-2">
            <p className="text-sm font-medium text-slate-900">{insight.title}</p>
            <StatusBadge
              status={
                insight.category === "attention"
                  ? "pending"
                  : insight.category === "positive"
                    ? "success"
                    : insight.category === "data_gap"
                      ? "unknown"
                      : "known"
              }
            >
              {insight.category.replace("_", " ")}
            </StatusBadge>
          </div>
          <p className="text-sm leading-relaxed text-slate-700">{insight.body}</p>
          {insight.explore_node_id ? (
            <button
              type="button"
              className="mt-2 text-xs font-medium text-slate-900 underline"
              onClick={() => onExplore(insight.explore_node_id!)}
            >
              Explore
            </button>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function NodeDetails({
  node,
  onClose,
  onDrill,
}: {
  node: FinancialMapNode;
  onClose: () => void;
  onDrill: (id: string) => void;
}) {
  const d = node.details || {};
  const clusterHoldings = (d.holdings as Array<Record<string, string | null>> | undefined) || [];

  return (
    <aside className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">{node.type.replace("_", " ")}</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-900">{node.label}</h3>
          {node.subtitle ? <p className="text-sm text-slate-600">{node.subtitle}</p> : null}
        </div>
        <button type="button" onClick={onClose} className="rounded-lg px-2 py-1 text-sm text-slate-500 hover:bg-slate-100" aria-label="Close details">
          ✕
        </button>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 text-sm">
        {node.value ? (
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">{node.value_label || "Value"}</p>
            <p className="text-xl font-semibold text-slate-900">
              <SensitiveValue value={formatCurrency(node.value)} />
            </p>
          </div>
        ) : null}

        {!node.available ? (
          <p className="rounded-xl bg-slate-50 px-3 py-2 text-slate-600">
            {(d.note as string) || "AI-CIO doesn't have this information yet."}
          </p>
        ) : null}

        <dl className="grid grid-cols-2 gap-3">
          {d.invested_amount ? (
            <div>
              <dt className="text-xs text-slate-500">Invested</dt>
              <dd className="font-medium"><SensitiveValue value={formatCurrency(String(d.invested_amount))} /></dd>
            </div>
          ) : null}
          {d.unrealised_pl ? (
            <div>
              <dt className="text-xs text-slate-500">Unrealised P/L</dt>
              <dd className="font-medium">
                <SensitiveValue value={formatCurrency(String(d.unrealised_pl))} />
                {d.unrealised_pl_pct ? ` (${d.unrealised_pl_pct}%)` : ""}
              </dd>
            </div>
          ) : null}
          {d.closing_units ? (
            <div>
              <dt className="text-xs text-slate-500">Units</dt>
              <dd className="font-medium"><SensitiveValue value={String(d.closing_units)} /></dd>
            </div>
          ) : null}
          {d.nav ? (
            <div>
              <dt className="text-xs text-slate-500">NAV / price</dt>
              <dd className="font-medium"><SensitiveValue value={formatCurrency(String(d.nav))} /></dd>
            </div>
          ) : null}
          {d.folio ? (
            <div>
              <dt className="text-xs text-slate-500">Folio</dt>
              <dd className="font-medium"><SensitiveValue value={String(d.folio)} /></dd>
            </div>
          ) : null}
          {d.isin ? (
            <div>
              <dt className="text-xs text-slate-500">ISIN</dt>
              <dd className="font-medium"><SensitiveValue value={String(d.isin)} /></dd>
            </div>
          ) : null}
          {d.target_amount ? (
            <div>
              <dt className="text-xs text-slate-500">Target</dt>
              <dd className="font-medium"><SensitiveValue value={formatCurrency(String(d.target_amount))} /></dd>
            </div>
          ) : null}
          {d.current_funding ? (
            <div>
              <dt className="text-xs text-slate-500">Recorded funding</dt>
              <dd className="font-medium"><SensitiveValue value={formatCurrency(String(d.current_funding))} /></dd>
            </div>
          ) : null}
          {d.progress_pct ? (
            <div><dt className="text-xs text-slate-500">Progress</dt><dd className="font-medium">{String(d.progress_pct)}%</dd></div>
          ) : null}
          {d.balance ? (
            <div>
              <dt className="text-xs text-slate-500">Balance</dt>
              <dd className="font-medium"><SensitiveValue value={formatCurrency(String(d.balance))} /></dd>
            </div>
          ) : null}
          {d.monthly_payment ? (
            <div>
              <dt className="text-xs text-slate-500">Monthly payment</dt>
              <dd className="font-medium"><SensitiveValue value={formatCurrency(String(d.monthly_payment))} /></dd>
            </div>
          ) : null}
        </dl>

        {(d.source || d.period_start) ? (
          <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Source</p>
            {d.source ? <p className="mt-1 text-slate-800">{String(d.source)}</p> : null}
            {d.period_start && d.period_end ? (
              <p className="text-slate-600">Period {String(d.period_start)} – {String(d.period_end)}</p>
            ) : null}
            {d.last_processed ? (
              <p className="text-slate-600">Last processed {formatDate(String(d.last_processed))}</p>
            ) : null}
          </div>
        ) : null}

        {typeof d.note === "string" && node.available ? (
          <p className="text-slate-600">{d.note}</p>
        ) : null}

        {clusterHoldings.length > 0 ? (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">All holdings</p>
            <ul className="max-h-64 space-y-2 overflow-y-auto">
              {clusterHoldings.map((h, i) => (
                <li key={`${h.label}-${i}`} className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2">
                  <span className="line-clamp-2 text-slate-800">{h.label}</span>
                  <span className="shrink-0 font-medium">
                    <SensitiveValue value={formatCurrency(h.value)} />
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {node.child_ids.length > 0 ? (
          <Button type="button" onClick={() => onDrill(node.id)} className="w-full">
            Explore this area
          </Button>
        ) : null}
      </div>
    </aside>
  );
}

function MapListFallback({
  map,
  focusId,
  onSelect,
}: {
  map: FinancialMap;
  focusId: string;
  onSelect: (id: string) => void;
}) {
  const kids = childrenOf(map, focusId);
  const focus = nodeById(map, focusId);
  return (
    <div className="space-y-3 md:hidden" role="list" aria-label="Financial map list">
      {focus ? (
        <button
          type="button"
          className="w-full rounded-2xl border border-slate-900 bg-slate-900 px-4 py-3 text-left text-white"
          onClick={() => onSelect(focus.id)}
        >
          <p className="text-xs text-slate-300">You are here</p>
          <p className="font-semibold">{focus.label}</p>
          {focus.value ? (
            <p className="text-sm">
              <SensitiveValue value={formatCurrency(focus.value)} />
            </p>
          ) : null}
        </button>
      ) : null}
      {kids.map((child) => (
        <button
          key={child.id}
          type="button"
          role="listitem"
          onClick={() => onSelect(child.id)}
          className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left"
        >
          <span>
            <span className="block text-sm font-medium text-slate-900">{child.label}</span>
            {child.subtitle ? <span className="text-xs text-slate-500">{child.subtitle}</span> : null}
          </span>
          <span className="text-sm font-medium text-slate-800">
            {child.value ? <SensitiveValue value={formatCurrency(child.value)} /> : child.available ? "View" : "Missing"}
          </span>
        </button>
      ))}
    </div>
  );
}

export function FinancialMapView({ map }: { map: FinancialMap }) {
  const [focusId, setFocusId] = useState(map.root_id);
  const [selectedId, setSelectedId] = useState<string | null>(map.root_id);
  const [filterId, setFilterId] = useState("all");
  const [query, setQuery] = useState("");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ x: number; y: number; px: number; py: number } | null>(null);

  const focus = nodeById(map, focusId) || nodeById(map, map.root_id)!;
  const trail = ancestorsOf(map, focusId);
  const visibleIds = useMemo(() => filterNodes(map, filterId), [map, filterId]);
  const children = useMemo(
    () => childrenOf(map, focusId).filter((c) => visibleIds.has(c.id)),
    [map, focusId, visibleIds],
  );
  const selected = selectedId ? nodeById(map, selectedId) : null;
  const results = useMemo(() => searchMap(map, query), [map, query]);

  useEffect(() => {
    setFocusId(map.root_id);
    setSelectedId(map.root_id);
  }, [map.root_id]);

  function select(id: string) {
    setSelectedId(id);
  }

  function drill(id: string) {
    const node = nodeById(map, id);
    if (node && node.child_ids.length > 0) {
      setFocusId(id);
      setSelectedId(id);
      setPan({ x: 0, y: 0 });
      setZoom(1);
    } else {
      setSelectedId(id);
    }
  }

  function goUp() {
    if (focus.parent_id) {
      setFocusId(focus.parent_id);
      setSelectedId(focus.parent_id);
    }
  }

  function reset() {
    setFocusId(map.root_id);
    setSelectedId(map.root_id);
    setFilterId("all");
    setQuery("");
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }

  function onPointerDown(e: React.PointerEvent) {
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y };
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!dragRef.current) return;
    setPan({
      x: dragRef.current.px + (e.clientX - dragRef.current.x),
      y: dragRef.current.py + (e.clientY - dragRef.current.y),
    });
  }
  function onPointerUp() {
    dragRef.current = null;
  }

  return (
    <SensitiveRevealProvider>
    <section className="space-y-4" aria-label="Your financial map">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Your financial map</p>
          <h2 className="text-xl font-semibold text-slate-900 md:text-2xl">
            See how your money, investments, goals and accounts connect.
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            Explore your financial life based only on what AI-CIO already knows — nothing invented.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <RevealToggle label="map values" />
          <Button type="button" variant="secondary" onClick={goUp} disabled={!focus.parent_id}>
            Up
          </Button>
          <Button type="button" variant="ghost" onClick={reset}>
            Reset
          </Button>
        </div>
      </div>

      <nav aria-label="Map location" className="flex flex-wrap items-center gap-1 text-sm text-slate-600">
        <span className="text-xs uppercase tracking-wide text-slate-400">You are here</span>
        {trail.map((node, index) => (
          <span key={node.id} className="inline-flex items-center gap-1">
            {index > 0 ? <span className="text-slate-300">/</span> : null}
            <button
              type="button"
              className={cn(
                "rounded px-1.5 py-0.5 hover:bg-slate-100",
                node.id === focusId ? "font-semibold text-slate-900" : "text-slate-600",
              )}
              onClick={() => drill(node.id)}
            >
              {node.label}
            </button>
          </span>
        ))}
      </nav>

      <div className="flex flex-wrap gap-2">
        {map.filters.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilterId(f.id)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-medium transition",
              filterId === f.id ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-700",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="relative">
        <label className="sr-only" htmlFor="map-search">Search your map</label>
        <input
          id="map-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search investments, goals, accounts…"
          className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
        />
        {results.length > 0 ? (
          <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-xl border border-slate-200 bg-white shadow-lg">
            {results.slice(0, 12).map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between px-4 py-2 text-left text-sm hover:bg-slate-50"
                  onClick={() => {
                    setQuery("");
                    if (r.parent_id) setFocusId(r.parent_id);
                    setSelectedId(r.id);
                  }}
                >
                  <span>{r.label}</span>
                  <span className="text-xs text-slate-500">{r.type.replace("_", " ")}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <div className="hidden items-center justify-between gap-2 md:flex">
            <div className="flex gap-2">
              <Button type="button" variant="secondary" onClick={() => setZoom((z) => Math.min(1.8, z + 0.15))} aria-label="Zoom in">+</Button>
              <Button type="button" variant="secondary" onClick={() => setZoom((z) => Math.max(0.6, z - 0.15))} aria-label="Zoom out">−</Button>
            </div>
            <p className="text-xs text-slate-500">Drag to pan · click a node to inspect · explore to drill in</p>
          </div>

          <div
            className="relative hidden min-h-[420px] overflow-hidden rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-50 via-white to-slate-100 md:block"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerLeave={onPointerUp}
            role="application"
            aria-label="Interactive financial map canvas"
          >
            <div
              className="absolute inset-0 flex flex-col items-center justify-center gap-10 p-8 transition-transform duration-300 ease-out"
              style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
            >
              <NodeBadge node={focus} active={selectedId === focus.id} onSelect={select} onDrill={drill} />
              {children.length ? (
                <div className="relative w-full max-w-4xl">
                  <svg className="pointer-events-none absolute left-1/2 top-[-2.5rem] h-10 w-full -translate-x-1/2" aria-hidden>
                    <line x1="50%" y1="0" x2="50%" y2="100%" stroke="#cbd5e1" strokeWidth="1.5" />
                  </svg>
                  <div className="flex flex-wrap items-start justify-center gap-4">
                    {children.map((child) => (
                      <div key={child.id} className="flex flex-col items-center gap-2">
                        <div className="h-6 w-px bg-slate-300" aria-hidden />
                        <NodeBadge
                          node={child}
                          active={selectedId === child.id}
                          onSelect={select}
                          onDrill={drill}
                        />
                        {child.child_ids.length > 0 ? (
                          <button
                            type="button"
                            className="text-[11px] font-medium text-slate-600 underline"
                            onClick={() => drill(child.id)}
                          >
                            Explore
                          </button>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="max-w-md text-center text-sm text-slate-600">
                  {focus.available
                    ? "No further branches here — open the details panel for what we know."
                    : "This part of your financial picture is still empty."}
                </p>
              )}
            </div>
          </div>

          <MapListFallback
            map={map}
            focusId={focusId}
            onSelect={(id) => {
              select(id);
              const n = nodeById(map, id);
              if (n && n.child_ids.length) drill(id);
            }}
          />

          {map.allocation.length > 0 ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Allocation of known assets</p>
              <div className="mt-3 flex h-3 overflow-hidden rounded-full bg-slate-100">
                {map.allocation.map((slice, i) => (
                  <div
                    key={slice.key}
                    title={`${slice.label} ${slice.percentage}%`}
                    className={cn(
                      i === 0 && "bg-slate-800",
                      i === 1 && "bg-slate-500",
                      i === 2 && "bg-slate-300",
                      i > 2 && "bg-slate-200",
                    )}
                    style={{ width: `${Math.max(2, Number(slice.percentage || 0))}%` }}
                  />
                ))}
              </div>
              <ul className="mt-3 flex flex-wrap gap-4 text-sm text-slate-700">
                {map.allocation.map((slice) => (
                  <li key={slice.key}>
                    <span className="font-medium">{slice.label}</span>{" "}
                    {slice.percentage}% · <SensitiveValue value={formatCurrency(slice.value)} />
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="space-y-4">
          <CompletenessSummary map={map} />
          {selected ? (
            <div className="min-h-[280px]">
              <NodeDetails
                node={selected}
                onClose={() => setSelectedId(focusId)}
                onDrill={drill}
              />
            </div>
          ) : null}
          <InsightPanel
            insights={map.insights}
            onExplore={(id) => {
              const node = nodeById(map, id);
              if (!node) return;
              if (node.parent_id && node.child_ids.length === 0) setFocusId(node.parent_id);
              else if (node.child_ids.length) setFocusId(node.id);
              setSelectedId(id);
            }}
          />
        </div>
      </div>
    </section>
    </SensitiveRevealProvider>
  );
}
