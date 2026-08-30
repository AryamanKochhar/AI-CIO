"use client";

import {
  RevealToggle,
  SensitiveRevealProvider,
  SensitiveValue,
  useSensitiveRevealOptional,
} from "./sensitive-reveal";

export type TransactionRow = {
  date?: string | null;
  scheme_name: string;
  transaction_type: string;
  description?: string | null;
  amount?: string | null;
  units?: string | null;
  nav?: string | null;
  unit_balance?: string | null;
  folio?: string | null;
};

function TransactionTableBody({
  rows,
  title,
  showToggle,
}: {
  rows: TransactionRow[];
  title: string;
  showToggle: boolean;
}) {
  const hasProvider = Boolean(useSensitiveRevealOptional());

  return (
    <>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        {showToggle && hasProvider ? <RevealToggle label="transaction details" /> : null}
      </div>
      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Investment</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Description</th>
              <th className="px-4 py-3">Amount</th>
              <th className="px-4 py-3">Units</th>
              <th className="px-4 py-3">NAV</th>
              <th className="px-4 py-3">Balance</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.scheme_name}-${row.date}-${index}`} className="border-t border-slate-100">
                <td className="px-4 py-3 text-slate-600">{row.date ?? "—"}</td>
                <td className="px-4 py-3 font-medium text-slate-900">{row.scheme_name}</td>
                <td className="px-4 py-3 text-slate-600">{row.transaction_type.replace(/_/g, " ")}</td>
                <td className="max-w-xs px-4 py-3 text-slate-600">
                  <SensitiveValue value={row.description ?? "—"} />
                </td>
                <td className="px-4 py-3 text-slate-900">
                  <SensitiveValue value={row.amount} prefix="₹" />
                </td>
                <td className="px-4 py-3 text-slate-600">
                  <SensitiveValue value={row.units} />
                </td>
                <td className="px-4 py-3 text-slate-600">
                  <SensitiveValue value={row.nav} prefix="₹" />
                </td>
                <td className="px-4 py-3 text-slate-600">
                  <SensitiveValue value={row.unit_balance} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function TransactionTable({
  rows,
  title = "Transactions",
  showToggle = true,
}: {
  rows: TransactionRow[];
  title?: string;
  showToggle?: boolean;
}) {
  const hasProvider = Boolean(useSensitiveRevealOptional());

  if (!rows.length) return null;

  const body = <TransactionTableBody rows={rows} title={title} showToggle={showToggle} />;

  if (hasProvider) return body;

  return <SensitiveRevealProvider>{body}</SensitiveRevealProvider>;
}
