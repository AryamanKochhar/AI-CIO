"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@ai-cio/ui";
import type { User } from "@ai-cio/contracts";
import { apiRequest } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

interface Persona {
  id: string; name: string; description: string; occupation: string; age: number;
  income: string; expenses: string; liquid: string; goal: string; horizon: number;
  fixed_answers: Array<{question_id: string; question: string; answer_id: string; answer: string}>;
}

export function DemoPersonas() {
  const router = useRouter();
  const { user, setUser, setSessionId } = useAuth();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selected, setSelected] = useState("tom");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    apiRequest<{personas: Persona[]}>("/demo/personas").then((data) => { if (active) setPersonas(data.personas); })
      .catch((err: Error) => { if (active) setError(`Demo profiles are unavailable. ${err.message}`); });
    return () => { active = false; };
  }, []);
  const persona = personas.find((p) => p.id === selected);
  async function launch() {
    setLoading(true); setError(null);
    try {
      const response = await apiRequest<{user: User; session_id: number}>(`/demo/personas/${selected}/launch`, {method: "POST"});
      setUser(response.user); setSessionId(response.session_id);
      router.push("/onboarding/twin");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not launch the demo."); }
    finally { setLoading(false); }
  }
  return (
    <section id="demo-personas" className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-widest text-teal-700">Explore in one click</p>
      <h2 className="mt-2 text-2xl font-semibold text-slate-900">Try a ready-made financial life</h2>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">Skip onboarding with a synthetic persona. Every launch creates a separate demo profile with the fixed answers below, scored by the same assessment engine.</p>
      <div className="mt-5 grid gap-3 md:grid-cols-3" role="group" aria-label="Choose a demo persona">
        {personas.map((p) => <button key={p.id} type="button" aria-pressed={selected === p.id} onClick={() => setSelected(p.id)} className={`rounded-2xl border p-4 text-left transition-colors ${selected === p.id ? "border-teal-600 bg-teal-50 ring-1 ring-teal-600" : "border-slate-200 hover:bg-slate-50"}`}><span className="block text-lg font-semibold text-slate-900">{p.name}, {p.age}</span><span className="mt-1 block text-sm text-slate-700">{p.description}</span><span className="mt-2 block text-xs text-slate-500">{p.occupation} · Synthetic example</span></button>)}
      </div>
      {persona ? <div className="mt-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl bg-slate-50 p-4"><p className="text-sm text-slate-700"><strong>{persona.goal}</strong> · {persona.horizon}-year horizon<br />Monthly income ₹{Number(persona.income).toLocaleString("en-IN")} · Expenses ₹{Number(persona.expenses).toLocaleString("en-IN")}</p><Button onClick={() => void launch()} disabled={loading}>{loading ? "Building demo twin…" : `Explore as ${persona.name}`}</Button></div>
        {user ? <p className="text-xs text-slate-500">Launching switches this browser to a new demo session. Your existing account data is retained.</p> : null}
        <details open className="rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer text-sm font-semibold text-slate-900">{persona.name}&apos;s fixed psychometric answers · all {persona.fixed_answers.length} responses</summary><p className="mt-2 text-xs text-slate-500">Instrument 1.0. Fixed confidence 75/100 and response time 5 seconds are synthetic inputs; these are not measured responses. IAS is interpreted as Indian Administrative Service.</p><div className="mt-3 max-h-72 overflow-y-auto"><table className="w-full text-left text-xs"><caption className="sr-only">Preset question and answer pairs for {persona.name}</caption><thead className="sticky top-0 bg-white"><tr><th className="py-2 pr-3">Question</th><th className="py-2">Fixed answer</th></tr></thead><tbody>{persona.fixed_answers.map((answer) => <tr key={answer.question_id} className="border-t border-slate-100"><td className="py-2 pr-4 text-slate-600">{answer.question_id} · {answer.question}</td><td className="py-2 font-medium text-slate-900">{answer.answer_id}: {answer.answer}</td></tr>)}</tbody></table></div></details>
      </div> : <p className="mt-4 text-sm text-slate-500">{error || "Loading fixed persona profiles…"}</p>}
      {error && persona ? <p role="alert" className="mt-3 text-sm text-rose-700">{error}</p> : null}
    </section>
  );
}
