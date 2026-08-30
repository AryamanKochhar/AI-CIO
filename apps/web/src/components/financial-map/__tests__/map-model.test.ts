import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { ancestorsOf, filterNodes, searchMap } from "../map-model.ts";

/** Minimal shape matching FinancialMap for pure helper tests. */
const sample = {
  root_id: "life",
  nodes: [
    {
      id: "life",
      type: "root" as const,
      label: "Life",
      available: true,
      child_ids: ["cash", "investments", "goals"],
      parent_id: null,
    },
    {
      id: "cash",
      type: "cash" as const,
      label: "Cash",
      available: true,
      child_ids: [] as string[],
      parent_id: "life",
    },
    {
      id: "investments",
      type: "investments" as const,
      label: "Investments",
      available: true,
      child_ids: ["equity"],
      parent_id: "life",
    },
    {
      id: "equity",
      type: "asset_class" as const,
      label: "Equity",
      available: true,
      child_ids: ["h1"],
      parent_id: "investments",
    },
    {
      id: "h1",
      type: "holding" as const,
      label: "HDFC Bank",
      available: true,
      child_ids: [] as string[],
      parent_id: "equity",
      search_text: "HDFC Bank INE040",
    },
    {
      id: "goals",
      type: "goals" as const,
      label: "Goals",
      available: false,
      child_ids: [] as string[],
      parent_id: "life",
    },
  ],
  edges: [],
  allocation: [],
  insights: [],
  completeness: {
    flags: {
      psychometric: true,
      income: true,
      expenses: true,
      liquid: true,
      liabilities: false,
      goals: false,
      portfolio: true,
      horizon: false,
    },
    understood_pct: 62,
  },
  filters: [],
};

describe("financial map model", () => {
  it("builds ancestor breadcrumbs", () => {
    assert.equal(ancestorsOf(sample, "h1").map((n) => n.id).join(">"), "life>investments>equity>h1");
  });

  it("filters equity branch", () => {
    const ids = filterNodes(sample, "equity");
    assert.ok(ids.has("h1"));
    assert.ok(ids.has("investments"));
    assert.ok(!ids.has("cash"));
  });

  it("searches holdings by name", () => {
    assert.equal(searchMap(sample, "hdfc")[0]?.id, "h1");
    assert.equal(searchMap(sample, "").length, 0);
  });
});
