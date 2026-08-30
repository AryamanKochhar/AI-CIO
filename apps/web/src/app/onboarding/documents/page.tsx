"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  FileUploadZone,
  PageHeader,
  PortfolioTable,
  RevealToggle,
  SensitiveRevealProvider,
  StatusBadge,
  TransactionTable,
} from "@ai-cio/ui";
import type { DocumentKind, DocumentRecord, DocumentUploadResult, Transaction } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { ApiError } from "@/lib/api-client";
import { documentsApi } from "@/lib/api";
import { DOCUMENT_TYPES } from "@/lib/constants";
import { useRequireAuth, useJourney } from "@/hooks/use-journey";

type UploadPhase = "idle" | "uploading" | "processing" | "complete" | "unsupported" | "failed";

function kindLabel(kind: string) {
  return DOCUMENT_TYPES.find((item) => item.value === kind)?.label ?? kind.replaceAll("_", " ");
}

export default function DocumentsPage() {
  const user = useRequireAuth();
  const router = useRouter();
  const { setStep } = useJourney();
  const [kind, setKind] = useState<DocumentKind>("cdsl_statement");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [holdings, setHoldings] = useState<Array<Record<string, string>>>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [uploadResult, setUploadResult] = useState<DocumentUploadResult | null>(null);

  const selected = DOCUMENT_TYPES.find((item) => item.value === kind) ?? DOCUMENT_TYPES[0];

  const equityHoldings = useMemo(
    () => holdings.filter((row) => (row.asset_class || row.amc) === "equity" || row.amc === "EQUITY"),
    [holdings],
  );
  const mfHoldings = useMemo(
    () => holdings.filter((row) => !((row.asset_class || row.amc) === "equity" || row.amc === "EQUITY")),
    [holdings],
  );
  const equityTxns = useMemo(
    () => transactions.filter((row) => row.amc === "EQUITY"),
    [transactions],
  );
  const mfTxns = useMemo(
    () => transactions.filter((row) => row.amc !== "EQUITY"),
    [transactions],
  );

  async function refresh() {
    if (!user) return;
    const [docs, hs, txns] = await Promise.all([
      documentsApi.list(user.id),
      documentsApi.getHoldings(user.id),
      documentsApi.getTransactions(user.id),
    ]);
    setDocuments(docs);
    setHoldings(hs);
    setTransactions(txns);
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, [user]);

  async function upload(file: File) {
    if (!user) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please upload a PDF file.");
      setPhase("failed");
      return;
    }
    setPhase("uploading");
    setError(null);
    setUploadResult(null);
    setMessage("Uploading your statement…");
    try {
      setPhase("processing");
      setMessage(
        kind === "cdsl_statement"
          ? "Reading your CDSL statement…"
          : "We're reading your document…",
      );
      const result = await documentsApi.upload(user.id, kind, file);
      setUploadResult(result);
      if (result.already_processed) {
        setPhase("complete");
        setMessage("This statement has already been processed.");
      } else if (result.parser_pending) {
        setPhase("unsupported");
        setMessage("Document uploaded successfully. Structured extraction for this document type is not yet supported.");
      } else if (kind === "cdsl_statement") {
        setPhase("complete");
        setMessage("Your CDSL CAS was successfully processed.");
      } else {
        setPhase("complete");
        setMessage(`We found ${result.holdings} investments in your statement.`);
      }
      await refresh();
      await setStep("portfolio");
    } catch (err) {
      setPhase("failed");
      setError(err instanceof ApiError ? err.message : "We couldn't process this document. Please try again.");
      setMessage(null);
    }
  }

  async function confirmPortfolio() {
    if (!user) return;
    await documentsApi.confirmPortfolio(user.id);
    setConfirmed(true);
    await setStep("review");
    router.push("/onboarding/review");
  }

  if (!user) return null;

  const summary = uploadResult?.summary;
  const period = uploadResult?.statement_period;

  return (
    <div className="space-y-6">
      <Card className="aic-card-glow">
        <PageHeader
          title="Add a document"
          description="What would you like to add? We'll read what we can and show you exactly what was found."
        />
        <div className="grid gap-3 sm:grid-cols-2">
          {DOCUMENT_TYPES.map((item) => {
            const active = kind === item.value;
            return (
              <button
                key={item.value}
                type="button"
                onClick={() => {
                  setKind(item.value as DocumentKind);
                  setError(null);
                  setMessage(null);
                  setPhase("idle");
                }}
                className={`rounded-2xl border px-4 py-4 text-left transition ${
                  active
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                <p className="text-sm font-semibold">{item.label}</p>
                <p className={`mt-1 text-xs leading-relaxed ${active ? "text-slate-200" : "text-slate-600"}`}>
                  {item.description}
                </p>
              </button>
            );
          })}
        </div>
      </Card>

      <Card className="aic-card-glow">
        <PageHeader
          title={
            kind === "cdsl_statement"
              ? "Upload your CDSL Consolidated Account Statement"
              : `Upload your ${selected.title}`
          }
          description={
            kind === "cdsl_statement"
              ? "We'll securely read your holdings and transaction history to build a more complete picture of your portfolio."
              : selected.description
          }
        />
        <FileUploadZone
          label="Drag & drop or browse files"
          hint="PDF only · Maximum 25 MB"
          accept=".pdf,application/pdf"
          disabled={phase === "uploading" || phase === "processing"}
          onFile={upload}
        />
        {phase === "processing" ? (
          <ul className="mt-4 space-y-1 text-sm text-slate-700">
            <li>Reading your statement</li>
            <li>Verifying document type</li>
            <li>Extracting accounts, holdings and transactions</li>
          </ul>
        ) : null}
        {message ? <p className="mt-4 text-sm text-slate-700">{message}</p> : null}
        {error ? <ErrorState title="Upload issue" message={error} /> : null}
      </Card>

      {uploadResult && !uploadResult.parser_pending && phase === "complete" ? (
        <Card className="aic-card-glow">
          <PageHeader
            title="Review what we found"
            description={
              period?.start && period?.end
                ? `Statement period ${period.start} — ${period.end}`
                : "Nothing here is invented — only what we could read from your statement."
            }
          />
          {summary ? (
            <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {summary.portfolio_value ? (
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Portfolio value</p>
                  <p className="text-lg font-semibold text-slate-900">{formatCurrency(summary.portfolio_value)}</p>
                </div>
              ) : null}
              {summary.equity_value ? (
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Equity</p>
                  <p className="text-lg font-semibold text-slate-900">{formatCurrency(summary.equity_value)}</p>
                </div>
              ) : null}
              {summary.mutual_fund_value ? (
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Mutual funds</p>
                  <p className="text-lg font-semibold text-slate-900">{formatCurrency(summary.mutual_fund_value)}</p>
                </div>
              ) : null}
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Found</p>
                <p className="text-sm text-slate-800">
                  {summary.demat_accounts ?? 0} demat accounts · {summary.equity_holdings ?? 0} securities ·{" "}
                  {summary.mutual_fund_folios ?? uploadResult.holdings} fund folios ·{" "}
                  {uploadResult.transactions} transactions
                </p>
              </div>
            </div>
          ) : (
            <p className="mb-4 text-sm text-slate-700">
              Found {uploadResult.holdings} investments and {uploadResult.transactions} transactions.
            </p>
          )}
          {uploadResult.failed_sections?.length ? (
            <p className="mb-4 text-sm text-amber-800">
              We extracted your holdings, but some sections could not be read completely.
            </p>
          ) : null}
        </Card>
      ) : null}

      <Card className="aic-card-glow">
        <h2 className="mb-4 text-base font-semibold text-slate-900">Your documents</h2>
        {documents.length === 0 ? (
          <EmptyState title="No documents yet" description="Upload a CDSL CAS or other statement to begin." />
        ) : (
          <ul className="space-y-3">
            {documents.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3">
                <div>
                  <p className="font-medium text-slate-900">{doc.filename}</p>
                  <p className="text-sm text-slate-600">
                    {kindLabel(doc.kind)}
                    {doc.statement_period?.start && doc.statement_period?.end
                      ? ` · ${doc.statement_period.start} — ${doc.statement_period.end}`
                      : ""}
                  </p>
                </div>
                <StatusBadge status={doc.status === "pending" ? "pending" : doc.status === "failed" ? "error" : "known"}>
                  {doc.status.replace("_", " ")}
                </StatusBadge>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {holdings.length > 0 ? (
        <Card className="aic-card-glow">
          <SensitiveRevealProvider>
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <PageHeader
                title="Your portfolio from this statement"
                description="Review holdings and transactions before adding them to your profile."
              />
              <RevealToggle label="financial details" className="shrink-0" />
            </div>

            {equityHoldings.length > 0 ? (
              <div className="mb-6">
                <h3 className="mb-3 text-sm font-semibold text-slate-900">Equity</h3>
                <PortfolioTable
                  rows={equityHoldings.map((row) => ({
                    scheme_name: row.scheme_name,
                    isin: row.isin,
                    closing_units: row.closing_units,
                    valuation: row.valuation,
                    source: row.amc === "EQUITY" ? "CDSL" : row.amc,
                  }))}
                />
              </div>
            ) : null}

            {mfHoldings.length > 0 ? (
              <div className="mb-6">
                <h3 className="mb-3 text-sm font-semibold text-slate-900">Mutual funds</h3>
                <div className="overflow-x-auto rounded-xl border border-slate-200">
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-4 py-3">Fund</th>
                        <th className="px-4 py-3">Folio</th>
                        <th className="px-4 py-3">Units</th>
                        <th className="px-4 py-3">NAV</th>
                        <th className="px-4 py-3">Invested</th>
                        <th className="px-4 py-3">Value</th>
                        <th className="px-4 py-3">P/L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mfHoldings.map((row, index) => (
                        <tr key={`${row.scheme_name}-${row.folio}-${index}`} className="border-t border-slate-100">
                          <td className="px-4 py-3 font-medium text-slate-900">{row.scheme_name}</td>
                          <td className="px-4 py-3 text-slate-600">{row.folio ?? "—"}</td>
                          <td className="px-4 py-3 text-slate-600">{row.closing_units}</td>
                          <td className="px-4 py-3 text-slate-600">{row.nav ? `₹${row.nav}` : "—"}</td>
                          <td className="px-4 py-3 text-slate-600">
                            {row.invested_amount ? `₹${row.invested_amount}` : "—"}
                          </td>
                          <td className="px-4 py-3 text-slate-900">₹{row.valuation}</td>
                          <td className="px-4 py-3 text-slate-600">
                            {row.unrealised_pl
                              ? `₹${row.unrealised_pl}${row.unrealised_pl_pct ? ` (${row.unrealised_pl_pct}%)` : ""}`
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <PortfolioTable
                rows={holdings.map((row) => ({
                  scheme_name: row.scheme_name,
                  isin: row.isin,
                  closing_units: row.closing_units,
                  valuation: row.valuation,
                  source: "CAS",
                }))}
              />
            )}

            {equityTxns.length > 0 ? (
              <div className="mb-6">
                <TransactionTable
                  title="Demat transactions"
                  rows={equityTxns.slice(0, 50)}
                  showToggle={false}
                />
              </div>
            ) : null}
            {mfTxns.length > 0 ? (
              <TransactionTable title="Mutual fund transactions" rows={mfTxns.slice(0, 50)} showToggle={false} />
            ) : transactions.length > 0 && equityTxns.length === 0 ? (
              <TransactionTable rows={transactions.slice(0, 50)} showToggle={false} />
            ) : null}
          </SensitiveRevealProvider>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button onClick={confirmPortfolio} disabled={confirmed}>
              {confirmed ? "Added to portfolio" : "Confirm and add to my portfolio"}
            </Button>
            <Link href="/onboarding/review">
              <Button variant="secondary">Cancel</Button>
            </Link>
          </div>
        </Card>
      ) : (
        <div className="flex justify-end">
          <Link href="/onboarding/review">
            <Button variant="secondary">Continue to review</Button>
          </Link>
        </div>
      )}
    </div>
  );
}
