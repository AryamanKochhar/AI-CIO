"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@ai-cio/ui";
import type { User } from "@ai-cio/contracts";
import { apiRequest } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

interface Persona {
  id: string;
  name: string;
  description: string;
  occupation: string;
  age: number;
  income: string;
  expenses: string;
  liquid: string;
  goal: string;
  horizon: number;
  household?: string;
  holding_count?: number;
  goal_count?: number;
  fd_count?: number;
  holding_names?: string[];
  fixed_answers: Array<{
    question_id: string;
    question: string;
    answer_id: string;
    answer: string;
  }>;
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
    apiRequest<{ personas: Persona[] }>("/demo/personas")
      .then((data) => {
        if (active) setPersonas(data.personas);
      })
      .catch((err: Error) => {
        if (active) setError(`Demo profiles are unavailable. ${err.message}`);
      });
    return () => {
      active = false;
    };
  }, []);
  const persona = personas.find((p) => p.id === selected);
  async function launch() {
    setLoading(true);
    setError(null);
    try {
      const response = await apiRequest<{ user: User; session_id: number }>(
        `/demo/personas/${selected}/launch`,
        { method: "POST" },
      );
      setUser(response.user);
      setSessionId(response.session_id);
      router.push("/onboarding/twin");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not launch the demo.",
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <section
      id="demo-personas"
      className="scroll-mt-40 rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm sm:p-7"
    >
      <p className="text-xs font-semibold uppercase tracking-widest text-teal-700">
        Explore in one click
      </p>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
          Different lives. A personal starting point.
        </h2>
        <span className="rounded-full border border-teal-100 bg-teal-50 px-3 py-1.5 text-[11px] font-medium text-teal-800">
          No onboarding needed
        </span>
      </div>
      <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
        Choose a life to explore. Each synthetic persona has a complete starting
        profile and a transparent set of fixed assessment answers. Every launch
        opens a separate demo.
      </p>
      <div
        className="mt-5 grid gap-3 md:grid-cols-3"
        role="group"
        aria-label="Choose a demo persona"
      >
        {personas.map((p, index) => (
          <button
            key={p.id}
            type="button"
            aria-pressed={selected === p.id}
            onClick={() => setSelected(p.id)}
            className={`group rounded-2xl border p-5 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-600 ${selected === p.id ? "border-teal-500 bg-[#f0f8f3] ring-1 ring-teal-500" : "border-slate-200 hover:border-teal-200 hover:bg-slate-50"}`}
          >
            <span className="mb-4 flex items-center justify-between">
              <span
                className={`flex h-11 w-11 items-center justify-center rounded-2xl text-lg font-semibold ${index === 0 ? "bg-[#d9ede1] text-[#28665b]" : index === 1 ? "bg-[#e6e4f5] text-[#665789]" : "bg-[#f7e8d8] text-[#9b6b3e]"}`}
              >
                {p.name[0]}
              </span>
              <span
                className={`text-[10px] font-semibold uppercase tracking-wider ${selected === p.id ? "text-teal-700" : "text-slate-400"}`}
              >
                {selected === p.id ? "Selected ✓" : "Explore ↗"}
              </span>
            </span>
            <span className="block text-xl font-semibold tracking-tight text-slate-900">
              {p.name}
              <span className="ml-2 text-sm font-normal text-slate-400">
                {p.age}
              </span>
            </span>
            <span className="mt-2 block min-h-10 text-sm leading-5 text-slate-700">
              {p.description}
            </span>
            <span className="mt-3 block text-[11px] text-slate-500">
              {p.occupation}
            </span>
            <span className="mt-4 flex items-center justify-between border-t border-slate-200/70 pt-3 text-[11px]">
              <span className="text-slate-500">{p.goal}</span>
              <span className="font-medium text-slate-700">
                {p.horizon} years
              </span>
            </span>
          </button>
        ))}
      </div>
      {persona ? (
        <div className="mt-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-[#f3f6fa] px-5 py-4">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                A snapshot of {persona.name}&apos;s world
              </p>
              <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-700">
                <span>
                  <span className="text-xs text-slate-500">
                    Income / month{" "}
                  </span>
                  <strong className="font-semibold">
                    ₹{Number(persona.income).toLocaleString("en-IN")}
                  </strong>
                </span>
                <span>
                  <span className="text-xs text-slate-500">Expenses </span>
                  <strong className="font-semibold">
                    ₹{Number(persona.expenses).toLocaleString("en-IN")}
                  </strong>
                </span>
                <span>
                  <span className="text-xs text-slate-500">
                    Liquid savings{" "}
                  </span>
                  <strong className="font-semibold">
                    ₹{Number(persona.liquid).toLocaleString("en-IN")}
                  </strong>
                </span>
              </div>
            </div>
            <Button onClick={() => void launch()} disabled={loading}>
              {loading ? "Building demo twin…" : `Explore as ${persona.name}`}
            </Button>
          </div>
          <div className="rounded-2xl border border-teal-100 bg-teal-50/60 p-4 text-xs leading-6 text-slate-600">
            <p className="font-semibold text-teal-900">A complete worked example</p>
            <p>{persona.holding_count} holdings · {persona.goal_count} goals · {persona.fd_count} fixed deposits · purchase and sale history</p>
            <p className="mt-1">{(persona.holding_names || []).join(" · ")}</p>
            <p className="mt-1">{persona.household}. Quantities, costs and finances are invented; Dhan market indicators are fetched separately and dated in Decisions.</p>
          </div>
          {user ? (
            <p className="text-xs text-slate-500">
              Launching switches this browser to a new demo session. Your
              existing account data is retained.
            </p>
          ) : null}
          <details
            open
            className="rounded-2xl border border-slate-200 p-4 sm:p-5"
          >
            <summary className="cursor-pointer text-sm font-semibold text-slate-900">
              {persona.name}&apos;s fixed psychometric answers · all{" "}
              {persona.fixed_answers.length} responses
            </summary>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              Instrument 1.0. Every answer below is fixed. Confidence 75/100 and
              response time 5 seconds are synthetic inputs.{" "}
              {persona.id === "tom"
                ? "IAS means Indian Administrative Service in this example."
                : "These are examples, not measured responses from a real person."}
            </p>
            <div
              className="mt-4 max-h-72 overflow-y-auto rounded-xl border border-slate-100"
              tabIndex={0}
              role="region"
              aria-label={`${persona.name}'s complete fixed answer table`}
            >
              <table className="w-full text-left text-xs">
                <caption className="sr-only">
                  Preset question and answer pairs for {persona.name}
                </caption>
                <thead className="sticky top-0 bg-[#f5f8fa]">
                  <tr>
                    <th className="px-3 py-3 font-medium text-slate-500">
                      Assessment question
                    </th>
                    <th className="px-3 py-3 font-medium text-slate-500">
                      Fixed answer
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {persona.fixed_answers.map((answer) => (
                    <tr
                      key={answer.question_id}
                      className="border-t border-slate-100 even:bg-slate-50/60"
                    >
                      <td className="px-3 py-3 leading-5 text-slate-600">
                        <span className="mr-2 font-medium text-teal-700">
                          {answer.question_id}
                        </span>
                        {answer.question}
                      </td>
                      <td className="min-w-32 px-3 py-3 font-medium leading-5 text-slate-900">
                        {answer.answer_id}: {answer.answer}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      ) : (
        <p className="mt-4 text-sm text-slate-500">
          {error || "Loading fixed persona profiles…"}
        </p>
      )}
      {error && persona ? (
        <p role="alert" className="mt-3 text-sm text-rose-700">
          {error}
        </p>
      ) : null}
    </section>
  );
}
