"use client";

import Link from "next/link";
import { useState } from "react";
import type { GroundedReview, ReviewProof, SkillPrinciple } from "@ai-cio/contracts";
import { formatCurrency } from "@ai-cio/utils";
import { apiRequest } from "@/lib/api-client";

function displayFact(value: string | null, unit: string): string {
  if (value == null) return "Not recorded";
  if (/^-?\d+(\.\d+)?$/.test(value) && unit.startsWith("INR")) {
    return formatCurrency(value) + unit.slice(3);
  }
  return `${value}${unit ? ` ${unit}` : ""}`;
}

function skillUrl(principle: SkillPrinciple): string {
  return `https://github.com/AryamanKochhar/AI-CIO/blob/main/${principle.path}#L${principle.line_start}-L${principle.line_end}`;
}

export function ReviewProofPanel({ proof }: { proof?: ReviewProof }) {
  const [verification, setVerification] = useState<"idle" | "checking" | "match" | "changed" | "unavailable">("idle");
  if (!proof) return null;
  const first = proof.principles[0];
  const knownFacts = proof.facts.filter((fact) => fact.value != null && !["", "{}", "[]", "null"].includes(String(fact.value).trim()));
  const missingFactLabels = proof.facts.filter((fact) => !knownFacts.includes(fact)).map((fact) => fact.label);
  const sources = [...new Map(proof.principles.flatMap((p) => p.source_refs).map((source) => [source.id, source])).values()];
  async function verify() {
    setVerification("checking");
    try {
      const loaded = await Promise.all(proof!.principles.map((p) => apiRequest<SkillPrinciple>(`/knowledge/principles/${encodeURIComponent(p.id)}`)));
      setVerification(loaded.every((p, i) => p.skill_sha256 === proof!.principles[i].skill_sha256 && p.excerpt === proof!.principles[i].excerpt && p.section === proof!.principles[i].section) ? "match" : "changed");
    } catch { setVerification("unavailable"); }
  }
  return <div className="mt-4 border-t border-slate-200/70 pt-4">
    {first ? <div className="rounded-xl border border-teal-100 bg-[#f5faf7] p-3">
      <p className="text-[10px] font-semibold uppercase tracking-[.1em] text-teal-800">Applied skill principle</p>
      <blockquote className="mt-2 text-xs leading-6 text-slate-700">“{first.excerpt}”</blockquote>
      <a href={skillUrl(first)} target="_blank" rel="noreferrer" className="mt-1 inline-block text-[11px] font-medium text-teal-800 underline underline-offset-4">{first.title} · {first.section} ↗</a>
    </div> : null}
    <details className="mt-3 rounded-xl border border-slate-200 bg-white p-3">
      <summary className="cursor-pointer text-xs font-semibold text-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-600">Why this follows · facts, calculation & sources</summary>
      <div className="mt-5 space-y-5 text-xs">
        {!!knownFacts.length && <section aria-label="Recorded premises"><h4 className="font-semibold text-slate-900">Recorded facts</h4><dl className="mt-3 grid gap-3 sm:grid-cols-2">{knownFacts.map((fact, index) => <div key={`${fact.path}-${index}`} className="min-w-0 rounded-xl bg-slate-50 p-3">
          <dt className="text-[11px] text-slate-500">{fact.label}</dt><dd className="mt-1 break-words font-medium text-slate-900">{displayFact(fact.value, fact.unit)}</dd><dd className="mt-2 break-words text-[10px] leading-5 text-slate-500">{fact.source}{fact.as_of ? ` · ${fact.as_of}` : ""}</dd>
        </div>)}</dl></section>}
        {!!proof.calculations.length && <section aria-label="Reproducible calculations"><h4 className="font-semibold text-slate-900">Derivation</h4>
          <div className="mt-3 space-y-3">{proof.calculations.map((calc, index) => <div key={`${calc.label}-${index}`} className="rounded-xl border border-slate-200 p-3"><p className="font-medium text-slate-800">{calc.label}</p><p className="mt-2 break-words leading-6 text-slate-600">{calc.formula}</p><p className="mt-1 break-words font-mono text-[10px] leading-6 text-slate-500">Inputs: {calc.operands.join(" ; ")}</p><p className="mt-2 font-semibold text-teal-900">Result: {displayFact(calc.result, calc.unit)}</p></div>)}</div>
        </section>}
        <section aria-label="Verified skill citations"><h4 className="font-semibold text-slate-900">Exact skill sections applied</h4><div className="mt-3 space-y-3">{proof.principles.map((principle) => <div key={principle.id} className="min-w-0 rounded-xl bg-teal-50/60 p-3">
          <p className="font-medium text-teal-900">{principle.title} / {principle.section}</p><blockquote className="mt-2 leading-6 text-slate-700">“{principle.excerpt}”</blockquote><a href={skillUrl(principle)} target="_blank" rel="noreferrer" className="mt-2 inline-block break-all text-[10px] text-teal-800 underline underline-offset-4">{principle.path} · lines {principle.line_start}–{principle.line_end} ↗</a><p className="mt-2 break-all font-mono text-[9px] leading-5 text-slate-500">Skill text SHA-256 (UTF-8, LF): {principle.skill_sha256}</p>
        </div>)}</div>
          <button type="button" onClick={() => void verify()} disabled={verification === "checking"} className="mt-3 rounded-lg border border-teal-200 px-3 py-2 text-xs font-semibold text-teal-800 hover:bg-teal-50 disabled:opacity-50">{verification === "checking" ? "Checking quoted sections…" : "Verify quoted skill sections"}</button>
          <p aria-live="polite" data-proof-verification={verification} className={`mt-2 leading-6 ${verification === "changed" ? "text-amber-800" : "text-teal-900"}`}>{verification === "match" ? "Quoted sections match the current project skill files." : verification === "changed" ? "A skill version changed. Refresh the analysis before relying on this saved citation." : verification === "unavailable" ? "The source check is unavailable right now; no match has been claimed." : ""}</p>
        </section>
        <section><h4 className="font-semibold text-slate-900">Conditional conclusion</h4><p className="mt-2 leading-6 text-slate-700">{proof.conclusion}</p></section>
        {!!(proof.missing_information.length || missingFactLabels.length) && <section><h4 className="font-semibold text-amber-900">What still needs confirmation</h4><ul className="mt-2 list-disc space-y-1 pl-4 leading-6 text-slate-600">{[...new Set([...missingFactLabels, ...proof.missing_information])].map((item) => <li key={item}>{item}</li>)}</ul></section>}
        {!!proof.assumptions.length && <section><h4 className="font-semibold text-slate-900">Assumptions and boundaries</h4><ul className="mt-2 list-disc space-y-1 pl-4 leading-6 text-slate-600">{proof.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></section>}
        {!!proof.alternatives.length && <section><h4 className="font-semibold text-slate-900">Options to compare</h4><ul className="mt-2 list-disc space-y-1 pl-4 leading-6 text-slate-600">{proof.alternatives.map((item) => <li key={item}>{item}</li>)}</ul></section>}
        {!!sources.length && <section><h4 className="font-semibold text-slate-900">Supporting source context</h4><p className="mt-1 leading-6 text-slate-500">These sources inform the skill. They do not supply your account facts or prescribe the app’s priority scores.</p><ul className="mt-2 space-y-2">{sources.map((source) => <li key={source.id}><a href={source.url} target="_blank" rel="noreferrer" className="font-medium text-teal-800 underline underline-offset-4">{source.publisher} · {source.title} ↗</a><p className="mt-1 leading-5 text-slate-500">{source.scope} Context verification: {source.verified_on}.{source.review_due ? " Source review is due." : ""}</p></li>)}</ul></section>}
        <p className="border-t border-slate-100 pt-3 text-[10px] leading-6 text-slate-500">{proof.scope} Project skill excerpts are condensed guides, not quotations from complete books. Finding fingerprint: <span className="break-all font-mono">{proof.digest.slice(0,16)}</span>.</p>
      </div>
    </details>
  </div>;
}

export function SpecialistReview({ reviews }: { reviews?: GroundedReview[] }) {
  if (!reviews?.length) return null;
  return <section aria-label="Source-backed specialist review" className="space-y-4">{reviews.map((review) => <article key={review.id || review.title} className="rounded-2xl border border-teal-100 bg-white p-5 sm:p-6"><p className="text-[10px] font-semibold uppercase tracking-wider text-teal-700">A distinct {review.theme} check</p><h2 className="mt-2 text-lg font-semibold text-slate-900">{review.title}</h2><p className="mt-3 text-sm leading-6 text-slate-600">{review.detail}</p><ReviewProofPanel proof={review.proof} />{review.action && <Link href={review.action.href} className="mt-4 inline-block text-xs font-semibold text-teal-800 underline underline-offset-4">{review.action.label} ↗</Link>}</article>)}</section>;
}
