"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button, Card, EmptyState, PageHeader, StatusBadge } from "@ai-cio/ui";
import type { DocumentKind, DocumentRecord } from "@ai-cio/contracts";
import { ApiError } from "@/lib/api-client";
import { documentsApi } from "@/lib/api";
import { DOCUMENT_TYPES } from "@/lib/constants";
import { useAuth } from "@/hooks/use-auth";

export default function DocumentsPage() {
  const { user } = useAuth();
  const [kind, setKind] = useState<DocumentKind>("cas_pdf");
  const [file, setFile] = useState<File | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [holdings, setHoldings] = useState<Array<Record<string, string>>>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function refresh() {
    if (!user) return;
    const [docs, hs] = await Promise.all([
      documentsApi.list(user.id),
      documentsApi.getHoldings(user.id),
    ]);
    setDocuments(docs);
    setHoldings(hs);
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, [user]);

  async function upload() {
    if (!user || !file) return;
    setUploading(true);
    setError(null);
    setStatus("Uploading…");
    try {
      const result = await documentsApi.upload(user.id, kind, file);
      if (result.parser_pending) {
        setStatus("Document uploaded successfully. Structured extraction for this document type is not yet supported.");
      } else {
        setStatus(`Processed ${result.holdings} holdings from your statement.`);
      }
      setFile(null);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "We couldn't process this document.");
      setStatus(null);
    } finally {
      setUploading(false);
    }
  }

  if (!user) {
    return (
      <Card>
        <PageHeader title="Add your financial documents" description="Please sign in first." />
        <Link href="/login"><Button>Sign in</Button></Link>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <PageHeader
          title="Add your financial documents"
          description="Upload CAS, NSDL, CDSL, or other statements. We show clear processing states and never invent holdings."
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
        <label className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center">
          <span className="text-sm font-medium text-slate-900">Drag & drop or browse files</span>
          <span className="mt-1 text-xs text-slate-500">PDF recommended for CAS statements</span>
          <input
            type="file"
            accept=".pdf,application/pdf"
            className="mt-4 text-sm"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        {file ? <p className="mt-3 text-sm text-slate-600">Selected: {file.name}</p> : null}
        {status ? <p className="mt-3 text-sm text-slate-700">{status}</p> : null}
        {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
        <div className="mt-6 flex gap-3">
          <Button onClick={upload} disabled={!file || uploading}>
            {uploading ? "Processing…" : "Upload document"}
          </Button>
          <Link href="/onboarding/review"><Button variant="secondary">Continue to review</Button></Link>
        </div>
      </Card>

      <Card>
        <h2 className="mb-4 text-base font-semibold text-slate-900">Your documents</h2>
        {documents.length === 0 ? (
          <EmptyState title="No documents yet" description="Upload a CAS or other statement to begin building your portfolio view." />
        ) : (
          <ul className="space-y-3">
            {documents.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3">
                <div>
                  <p className="font-medium text-slate-900">{doc.filename}</p>
                  <p className="text-sm text-slate-600">{doc.kind}</p>
                </div>
                <StatusBadge status={doc.status === "pending" ? "pending" : "known"}>{doc.status}</StatusBadge>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {holdings.length > 0 ? (
        <Card>
          <h2 className="mb-4 text-base font-semibold text-slate-900">We found these investments</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-4">Fund</th>
                  <th className="py-2 pr-4">Value</th>
                  <th className="py-2">Source</th>
                </tr>
              </thead>
              <tbody>
                {holdings.map((row, index) => (
                  <tr key={`${row.scheme_name}-${index}`} className="border-t border-slate-100">
                    <td className="py-3 pr-4">{row.scheme_name}</td>
                    <td className="py-3 pr-4">₹{row.valuation}</td>
                    <td className="py-3">CAS</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
