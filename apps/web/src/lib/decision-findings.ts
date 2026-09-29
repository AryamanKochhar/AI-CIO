import type { DecisionResult } from "@ai-cio/contracts";
import type { Severity } from "@/components/design/system";

export type DecisionFinding = {
  title: string;
  detail: string;
  severity: Severity;
  metric?: string | null;
  source: string;
};

function mapWorrySeverity(raw?: string): Severity {
  const s = (raw || "").toLowerCase();
  if (s === "high" || s === "critical") return "high";
  if (s === "medium" || s === "moderate" || s === "watch") return "watch";
  if (s === "low") return "information";
  return "watch";
}

/** Derive presentation findings from existing DecisionResult fields only. */
export function buildDecisionFindings(result: DecisionResult): DecisionFinding[] {
  const out: DecisionFinding[] = [];
  const seen = new Set<string>();

  const push = (item: DecisionFinding) => {
    const key = `${item.title}|${item.detail}`.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    out.push(item);
  };

  for (const worry of result.top_worries || []) {
    push({
      title: worry.title,
      detail: worry.detail,
      severity: mapWorrySeverity(worry.severity),
      metric: worry.metric,
      source: "top_worries",
    });
  }

  const sectors = result.true_exposure?.sector_exposure || result.sector_allocation || [];
  const topSector = [...sectors]
    .map((row) => ({
      name: String(("sector" in row ? row.sector : null) || ""),
      pct: Number(("percent" in row ? row.percent : null) ?? ("weight_percent" in row ? row.weight_percent : null) ?? NaN),
    }))
    .filter((r) => r.name && Number.isFinite(r.pct))
    .sort((a, b) => b.pct - a.pct)[0];
  if (topSector && topSector.pct >= 25) {
    push({
      title: "Portfolio concentration",
      detail: `${topSector.name} represents approximately ${topSector.pct.toFixed(1)}% of classified equity exposure.`,
      severity: topSector.pct >= 40 ? "high" : "watch",
      metric: `${topSector.pct.toFixed(1)}%`,
      source: "true_exposure",
    });
  }

  const largest = result.concentration_analysis?.largest_holding_percent;
  if (largest != null && Number(largest) >= 15) {
    push({
      title: "Single-holding concentration",
      detail: `Largest holding represents approximately ${String(largest)}% of the portfolio.`,
      severity: Number(largest) >= 20 ? "high" : "watch",
      metric: `${String(largest)}%`,
      source: "concentration",
    });
  }

  const trajGoals = result.trajectory_intelligence?.goal_projections || [];
  const aligned = trajGoals.find((g) => {
    const status = String(g.likelihood_status || "").toLowerCase();
    return status.includes("likely") || status.includes("on_track") || status.includes("aligned");
  });
  const stressed = trajGoals.find((g) => {
    const status = String(g.likelihood_status || "").toLowerCase();
    return status.includes("unlikely") || status.includes("at_risk") || status.includes("behind");
  });
  if (stressed) {
    push({
      title: "Goal trajectory",
      detail:
        stressed.narrative ||
        `${stressed.goal_name || "A goal"} appears behind under the current base assumptions.`,
      severity: "watch",
      source: "trajectory",
    });
  } else if (aligned) {
    push({
      title: "Goal trajectory",
      detail:
        aligned.narrative ||
        `${aligned.goal_name || "A goal"} looks aligned under the current base scenario.`,
      severity: "information",
      source: "trajectory",
    });
  } else if (result.goal_likelihood?.[0]) {
    const g = result.goal_likelihood[0];
    push({
      title: "Goal trajectory",
      detail: g.narrative || `${g.goal_name || "Goal"} projection under stated assumptions.`,
      severity: mapWorrySeverity(g.likelihood_status || undefined),
      source: "goal_likelihood",
    });
  }

  const taxOpps = result.tax_intelligence?.opportunities || [];
  if (result.tax_intelligence?.available && taxOpps.length > 0) {
    const first = taxOpps[0];
    push({
      title: "Tax opportunity",
      detail:
        first.reason ||
        first.label ||
        `${taxOpps.length} tax opportunity${taxOpps.length === 1 ? "" : "ies"} detected from existing lots.`,
      severity: "opportunity",
      metric: `${taxOpps.length} open`,
      source: "tax",
    });
  }

  for (const item of result.suggestions?.items || []) {
    if (out.length >= 5) break;
    const kind = (item.kind || "").toLowerCase();
    push({
      title: item.title,
      detail: item.detail,
      severity: kind.includes("risk") ? "watch" : kind.includes("sector") ? "opportunity" : "information",
      source: "suggestions",
    });
  }

  if (out.length < 3 && result.decision) {
    push({
      title: "Decision summary",
      detail: result.decision,
      severity: "information",
      source: "decision",
    });
  }

  return out.slice(0, 5);
}

export function normalizeWorrySeverity(raw?: string): Severity {
  return mapWorrySeverity(raw);
}
