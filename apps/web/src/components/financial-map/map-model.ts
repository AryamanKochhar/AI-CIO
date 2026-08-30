import type { FinancialMap, FinancialMapNode } from "@ai-cio/contracts";

export function nodeById(map: FinancialMap, id: string): FinancialMapNode | undefined {
  return map.nodes.find((n) => n.id === id);
}

export function childrenOf(map: FinancialMap, id: string): FinancialMapNode[] {
  const node = nodeById(map, id);
  if (!node) return [];
  return node.child_ids.map((cid) => nodeById(map, cid)).filter(Boolean) as FinancialMapNode[];
}

export function ancestorsOf(map: FinancialMap, id: string): FinancialMapNode[] {
  const path: FinancialMapNode[] = [];
  let current = nodeById(map, id);
  while (current) {
    path.unshift(current);
    current = current.parent_id ? nodeById(map, current.parent_id) : undefined;
  }
  return path;
}

export function filterNodes(map: FinancialMap, filterId: string): Set<string> {
  if (filterId === "all") return new Set(map.nodes.map((n) => n.id));
  const visible = new Set<string>([map.root_id]);
  for (const node of map.nodes) {
    if (filterId === "cash" && ["cash", "income", "expense"].includes(node.type)) {
      visible.add(node.id);
      for (const a of ancestorsOf(map, node.id)) visible.add(a.id);
    }
    if (filterId === "equity" && (node.id === "equity" || node.parent_id === "equity" || node.id === "investments")) {
      visible.add(node.id);
      for (const a of ancestorsOf(map, node.id)) visible.add(a.id);
    }
    if (
      filterId === "mutual_funds" &&
      (node.id === "mutual_funds" || node.parent_id === "mutual_funds" || node.id === "investments")
    ) {
      visible.add(node.id);
      for (const a of ancestorsOf(map, node.id)) visible.add(a.id);
    }
    if (filterId === "goals" && (node.type === "goals" || node.type === "goal")) {
      visible.add(node.id);
      for (const a of ancestorsOf(map, node.id)) visible.add(a.id);
    }
    if (filterId === "liabilities" && (node.type === "liabilities" || node.type === "liability")) {
      visible.add(node.id);
      for (const a of ancestorsOf(map, node.id)) visible.add(a.id);
    }
  }
  return visible;
}

export function searchMap(map: FinancialMap, query: string): FinancialMapNode[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return map.nodes.filter((n) => {
    const hay = `${n.label} ${n.subtitle || ""} ${n.search_text || ""}`.toLowerCase();
    return hay.includes(q) && n.type !== "root";
  });
}
