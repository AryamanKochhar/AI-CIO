"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
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
import type { DocumentKind, DocumentRecord, Transaction } from "@ai-cio/contracts";
import { ApiError } from "@/lib/api-client";
import { documentsApi } from "@/lib/api";
import { DOCUMENT_TYPES } from "@/lib/constants";
import { useRequireAuth, useJourney } from "@/hooks/use-journey";

type UploadPhase = "idle" | "uploading" | "processing" | "complete" | "unsupported" | "failed";

export default function DocumentsPage() {
  const user = useRequireAuth();
  const router = useRouter();
  const { setStep } = useJourney();
  const [kind, setKind] = useState<DocumentKind>("cas_pdf");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [holdings, setHoldings] = useState<Array<Record<string, string>>>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);

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
    setPhase("uploading");
    setError(null);
    setMessage("Uploading your document…");
    try {
      setPhase("processing");
      setMessage("We're reading your document…");
      const result = await documentsApi.upload(user.id, kind, file);
      if (result.parser_pending) {
        setPhase("unsupported");
        setMessage("Document uploaded successfully. Structured extraction for this document type is not yet supported.");
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

  return (
    <div className="space-y-6">
      <Card className="aic-card-glow">
        <PageHeader
          title="Let's understand what you already own"
          description="Upload your investment statements. We'll extract what we can and clearly show what's still pending."
        />
        <div className="mb-4 flex flex-wrap gap-2">
          {DOCUMENT_TYPES.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => setKind(item.value as DocumentKind)}
              className={`rounded-full border px-3 py-1.5 text-sm ${
                kind === item.value ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <FileUploadZone
          label="Drag & drop or browse files"
          hint="PDF recommended for CAS statements"
          accept=".pdf,application/pdf"
          disabled={phase === "uploading" || phase === "processing"}
          onFile={upload}
        />
        {message ? <p className="mt-4 text-sm text-slate-700">{message}</p> : null}
        {error ? <ErrorState title="Upload issue" message={error} /> : null}
      </Card>

      <Card className="aic-card-glow">
        <h2 className="mb-4 text-base font-semibold text-slate-900">Your documents</h2>
        {documents.length === 0 ? (
          <EmptyState title="No documents yet" description="Upload a CAS or other statement to begin." />
        ) : (
          <ul className="space-y-3">
            {documents.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3">
                <div>
                  <p className="font-medium text-slate-900">{doc.filename}</p>
                  <p className="text-sm text-slate-600">{doc.kind.replace("_", " ")}</p>
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
              <PageHeader title="We found these investments" description="Review the extracted holdings. Nothing is invented." />
              <RevealToggle label="financial details" className="shrink-0" />
            </div>
            <PortfolioTable
              rows={holdings.map((row) => ({
                scheme_name: row.scheme_name,
                isin: row.isin,
                closing_units: row.closing_units,
                valuation: row.valuation,
                source: "CAS",
              }))}
            />
            <div className="mt-6">
              <TransactionTable rows={transactions} showToggle={false} />
            </div>
          </SensitiveRevealProvider>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button onClick={confirmPortfolio} disabled={confirmed}>
              {confirmed ? "Confirmed" : "Everything looks correct"}
            </Button>
            <Link href="/onboarding/review">
              <Button variant="secondary">Review later</Button>
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
