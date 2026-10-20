"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { architectureAgents, orchestrationStages, sharedReferences, sharedSkills, type AgentId, type OrchestrationStageId } from "./model";

type Selection = { kind: "agent"; id: AgentId } | { kind: "stage"; id: OrchestrationStageId } | { kind: "twin" | "skills" };
type Wire = { id: string; path: string; kind: "context" | "return" | "decision"; agent?: AgentId };
type Box = { left: number; top: number; right: number; bottom: number; x: number; y: number };

const positions: Record<AgentId, string> = {
  equity: "xl:col-start-1 xl:row-start-1",
  "mutual-funds": "xl:col-start-2 xl:row-start-1",
  bonds: "xl:col-start-3 xl:row-start-1",
  tax: "xl:col-start-1 xl:row-start-3",
  fd: "xl:col-start-2 xl:row-start-3",
  goals: "xl:col-start-3 xl:row-start-3",
};

function Symbol({ name, className = "" }: { name: string; className?: string }) {
  const paths: Record<string, React.ReactNode> = {
    twin: <><circle cx="12" cy="7" r="3" /><path d="M5 21v-3a7 7 0 0 1 14 0v3M8 17h8M12 14v6" /><circle cx="4" cy="6" r="1" /><circle cx="21" cy="12" r="1" /><path d="M4 7v4h3M20 12h-3" /></>,
    equity: <><path d="M4 4v16h16M7 15l4-5 4 2 5-7M16 5h4v4" /></>,
    "mutual-funds": <><rect x="3" y="4" width="7" height="7" rx="2" /><rect x="14" y="4" width="7" height="7" rx="2" /><rect x="8.5" y="15" width="7" height="6" rx="2" /><path d="M6.5 11v2h11v-2M12 13v2" /></>,
    bonds: <><path d="m3 8 9-5 9 5H3ZM5 10v7M10 10v7M14 10v7M19 10v7M3 21h18M4 18h16" /></>,
    tax: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3ZM9 7h6M9 11h2M13 15h2M10 15l4-4" /></>,
    fd: <><rect x="3" y="6" width="18" height="15" rx="3" /><path d="M7 6V3h10v3M3 11h18M10 15h4M12 13v6" /></>,
    goals: <><circle cx="11" cy="13" r="8" /><circle cx="11" cy="13" r="4" /><path d="m11 13 9-10M16 3h4v4" /></>,
    coordinator: <><circle cx="12" cy="12" r="4" /><circle cx="4" cy="4" r="2" /><circle cx="20" cy="4" r="2" /><circle cx="4" cy="20" r="2" /><circle cx="20" cy="20" r="2" /><path d="m6 6 3 3m6 6 3 3M6 18l3-3m6-6 3-3" /></>,
    decision: <><rect x="5" y="3" width="14" height="18" rx="3" /><path d="m8 9 2 2 5-5M8 15h8M8 18h5" /></>,
    skills: <><path d="M12 6C8 3 4 4 3 5v14c3-2 6-1 9 1 3-2 6-3 9-1V5c-1-1-5-2-9 1ZM12 6v14" /></>,
  };
  return <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>{paths[name] || paths.coordinator}</svg>;
}

function Points({ items, dark = false }: { items: string[]; dark?: boolean }) {
  return <ul className={`space-y-2 text-xs leading-6 ${dark ? "text-slate-200" : "text-slate-600"}`}>{items.map((item) => <li key={item} className="flex items-start gap-2"><span aria-hidden className={`mt-2.5 h-1 w-1 shrink-0 rounded-full ${dark ? "bg-teal-200" : "bg-teal-600"}`} /><span>{item}</span></li>)}</ul>;
}

export function HomeArchitecture() {
  const [selection, setSelection] = useState<Selection>({ kind: "stage", id: "reconcile" });
  const [wires, setWires] = useState<Wire[]>([]);
  const [size, setSize] = useState({ width: 1, height: 1 });
  const canvas = useRef<HTMLDivElement>(null);
  const nodes = useRef<Record<string, HTMLElement | null>>({});
  const unique = useId().replace(/:/g, "");

  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    let frame = 0;
    const measure = () => {
      const base = element.getBoundingClientRect();
      const box = (id: string): Box | null => {
        const node = nodes.current[id];
        if (!node) return null;
        const r = node.getBoundingClientRect();
        return { left: r.left - base.left, right: r.right - base.left, top: r.top - base.top, bottom: r.bottom - base.top, x: r.left - base.left + r.width / 2, y: r.top - base.top + r.height / 2 };
      };
      const twin = box("twin"), central = box("coordinator"), decision = box("decision");
      if (!twin || !central || !decision) return;
      const next: Wire[] = [];
      if (window.matchMedia("(min-width: 1280px)").matches) {
        next.push({ id: "twin", kind: "context", path: `M ${twin.right} ${twin.y} L ${central.left} ${central.y}` });
        next.push({ id: "decision", kind: "decision", path: `M ${central.right} ${central.y} L ${decision.left} ${decision.y}` });
        architectureAgents.forEach((agent, i) => {
          const a = box(agent.id);
          if (!a) return;
          const top = i < 3, cy = top ? central.top : central.bottom, ay = top ? a.bottom : a.top, bend = top ? -26 : 26;
          const start = central.x + ((i % 3) - 1) * 18;
          next.push({ id: `${agent.id}-context`, agent: agent.id, kind: "context", path: `M ${start - 4} ${cy} C ${start - 4} ${cy + bend}, ${a.x - 4} ${ay - bend}, ${a.x - 4} ${ay}` });
          next.push({ id: `${agent.id}-return`, agent: agent.id, kind: "return", path: `M ${a.x + 4} ${ay} C ${a.x + 4} ${ay - bend}, ${start + 4} ${cy + bend}, ${start + 4} ${cy}` });
        });
      } else {
        next.push({ id: "twin", kind: "context", path: `M ${twin.x} ${twin.bottom} L ${central.x} ${central.top}` });
        next.push({ id: "decision", kind: "decision", path: `M ${central.left} ${central.y} H 8 V ${decision.y} H ${decision.left}` });
        const group = box("specialists");
        if (group) next.push({ id: "return", kind: "return", path: `M ${group.right} ${group.bottom - 12} H ${base.width - 4} V ${central.y} H ${central.right}` });
      }
      setSize({ width: base.width, height: base.height });
      setWires(next);
    };
    const schedule = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(measure); };
    const observer = new ResizeObserver(schedule);
    observer.observe(element);
    Object.values(nodes.current).forEach((node) => { if (node) observer.observe(node); });
    window.addEventListener("resize", schedule);
    void document.fonts.ready.then(schedule);
    schedule();
    return () => { cancelAnimationFrame(frame); observer.disconnect(); window.removeEventListener("resize", schedule); };
  }, []);

  const selectedAgent = selection.kind === "agent" ? architectureAgents.find((agent) => agent.id === selection.id) : undefined;
  const selectedStage = selection.kind === "stage" ? orchestrationStages.find((stage) => stage.id === selection.id) : undefined;
  const focusStyle = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-4";

  return <section id="home-architecture" aria-labelledby="home-architecture-title" className="scroll-mt-28 overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-[0_12px_45px_rgba(19,47,54,.045)]">
    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 px-5 py-5 sm:px-7">
      <div><p className="text-[10px] font-semibold uppercase tracking-[.2em] text-teal-700">The system, at a glance</p><h1 id="home-architecture-title" className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">Your Twin. Six specialists. One coordinated plan.</h1><p className="mt-2 max-w-2xl text-xs leading-6 text-slate-500">Select an agent or coordinator step to inspect its inputs, outputs and financial skills.</p></div>
      <div className="flex flex-wrap items-center gap-3 sm:flex-col sm:items-end"><span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[10px] font-medium text-slate-500">Architecture overview</span><Link href="#demo-personas" className={`rounded text-[11px] font-semibold text-teal-800 underline underline-offset-4 ${focusStyle}`}>Explore a demo persona ↓</Link></div>
    </div>

    <div className="border-b border-slate-100 bg-[#fbfcfa] px-5 py-3 sm:px-7"><div className="flex flex-wrap gap-x-5 gap-y-2 text-[10px] font-medium text-slate-600"><span className="flex items-center gap-2"><span aria-hidden className="text-base text-teal-600">⟶</span> Context + scoped skills</span><span className="flex items-center gap-2"><span aria-hidden className="text-base text-[#b58943]">⟵</span> Findings + sources + limits</span><span className="flex items-center gap-2"><span aria-hidden className="text-base text-indigo-500">⟶</span> Checked priorities</span><span className="xl:ml-auto">All six specialists work in parallel</span></div></div>

    <div ref={canvas} data-testid="architecture-map" className="relative bg-[#f8faf9] px-5 py-4 sm:px-7" style={{ backgroundImage: "radial-gradient(#a2b6b32b .75px, transparent .75px)", backgroundSize: "18px 18px" }}>
      <svg className="architecture-wires pointer-events-none absolute inset-0 h-full w-full overflow-visible" viewBox={`0 0 ${size.width} ${size.height}`} fill="none" aria-hidden="true">
        <defs>{[["context", "#3b938a"], ["return", "#b58943"], ["decision", "#8186ba"]].map(([kind, color]) => <marker key={kind} id={`${unique}-${kind}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="m1 1 6 3-6 3" stroke={color} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></marker>)}</defs>
        {wires.map((wire) => <path key={wire.id} d={wire.path} stroke={wire.kind === "context" ? "#3b938a" : wire.kind === "return" ? "#b58943" : "#8186ba"} strokeWidth={wire.agent && selectedAgent?.id === wire.agent ? 2 : 1.3} strokeDasharray={wire.kind === "context" ? "5 7" : wire.kind === "return" ? "2 5" : undefined} opacity={selectedAgent && wire.agent && wire.agent !== selectedAgent.id ? .2 : .85} markerEnd={`url(#${unique}-${wire.kind})`} className={wire.kind === "decision" ? "" : "flow-line"} />)}
      </svg>

      <div className="relative grid gap-y-7 xl:grid-cols-[1fr_1.16fr_1fr] xl:gap-x-12 xl:gap-y-9">
        <div ref={(node) => { nodes.current.twin = node; }} className="relative rounded-2xl border border-teal-100 bg-white p-4 shadow-sm xl:col-start-1 xl:row-start-2 xl:self-center">
          <button type="button" aria-controls="architecture-inspector" aria-pressed={selection.kind === "twin"} onClick={() => setSelection({ kind: "twin" })} className={`flex w-full items-start gap-3 rounded-lg text-left ${focusStyle}`}><span className="rounded-xl bg-teal-50 p-2 text-teal-700"><Symbol name="twin" /></span><span><span className="block text-[9px] font-semibold uppercase tracking-[.15em] text-teal-700">Your shared context</span><span className="mt-1 block text-base font-semibold text-slate-900">Digital Financial Twin</span></span></button>
          <div className="mt-3 grid grid-cols-2 gap-1.5 text-[10px] text-slate-600">{["Income & spending", "Holdings & deposits", "Goals & time horizons", "Psychometric scores"].map((label) => <span key={label} className="rounded-md bg-slate-50 px-2 py-1.5">{label}</span>)}</div><p className="mt-3 text-[10px] leading-5 text-slate-500">One user-scoped financial snapshot, including what is still unknown.</p>
        </div>

        <div ref={(node) => { nodes.current.coordinator = node; }} className="relative rounded-[22px] border border-[#254b50] bg-[#133c43] p-3.5 text-white shadow-[0_14px_35px_rgba(19,60,67,.17)] xl:col-start-2 xl:row-start-2">
          <div className="mb-2 flex items-center gap-3"><span className="rounded-xl border border-white/15 bg-white/5 p-2 text-teal-200"><Symbol name="coordinator" /></span><div><p className="text-[9px] font-medium uppercase tracking-[.17em] text-teal-200">The coordination layer</p><h3 className="mt-1 text-base font-semibold">Central orchestrator</h3></div></div>
          <ol className="space-y-1">{orchestrationStages.map((stage, index) => <li key={stage.id}><button type="button" aria-controls="architecture-inspector" aria-pressed={selectedStage?.id === stage.id} onClick={() => setSelection({ kind: "stage", id: stage.id })} className={`flex w-full items-center gap-2.5 rounded-lg px-2 py-1 text-left transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-200 ${selectedStage?.id === stage.id ? "bg-white/10 text-white" : "text-slate-200"}`}><span className="font-mono text-[9px] text-teal-200/80">0{index + 1}</span><span className="flex-1 text-[11px] font-medium">{stage.label}</span><span aria-hidden className="text-xs text-teal-200">↗</span></button></li>)}</ol>
          <p className="mt-2 border-t border-white/10 pt-2 text-[10px] leading-5 text-teal-100/80">One shared budget. One reconciled decision.</p>
        </div>

        <div className="text-center text-[10px] font-medium text-teal-700 xl:hidden"><span aria-hidden>↓ </span> Same financial context + relevant skills to all six</div>
        <div ref={(node) => { nodes.current.specialists = node; }} className="grid grid-cols-2 gap-3 xl:contents">{architectureAgents.map((agent) => <button key={agent.id} ref={(node) => { nodes.current[agent.id] = node; }} type="button" aria-label={`Explore ${agent.name} agent`} aria-controls="architecture-inspector" aria-pressed={selectedAgent?.id === agent.id} onClick={() => setSelection({ kind: "agent", id: agent.id })} className={`architecture-agent relative min-w-0 rounded-2xl border bg-white p-3 text-left shadow-sm transition-[border-color,box-shadow] hover:border-teal-400 hover:shadow-md ${positions[agent.id]} ${focusStyle} ${selectedAgent?.id === agent.id ? "border-teal-600 ring-1 ring-teal-600/20" : "border-slate-200"}`}><div className="flex items-start gap-2.5"><span className="rounded-lg bg-[#f0f6f5] p-1.5 text-teal-700"><Symbol name={agent.id} className="h-5 w-5" /></span><div className="min-w-0"><span className="block text-[9px] font-medium uppercase tracking-wider text-slate-400">{agent.eyebrow}</span><h3 className="mt-0.5 text-xs font-semibold leading-5 text-slate-800 sm:text-[13px]">{agent.id === "bonds" ? "Bonds" : agent.name}</h3></div></div><ul className="mt-2 space-y-0.5 text-[10px] leading-4 text-slate-600">{agent.outputs.map((output) => <li key={output} className="flex gap-1.5"><span aria-hidden className="text-teal-600">·</span><span>{output}</span></li>)}</ul></button>)}</div>
        <div className="rounded-xl border border-[#e8dfcc] bg-[#fffaf0] px-4 py-3 text-center text-[10px] leading-5 text-[#806236] xl:hidden">↑ Findings, calculations, sources and limits return to the coordinator for checks and ranking.</div>

        <div ref={(node) => { nodes.current.decision = node; }} className="relative rounded-2xl border border-[#dce2f0] bg-white p-4 shadow-sm xl:col-start-3 xl:row-start-2 xl:self-center"><div className="flex items-center gap-3"><span className="rounded-xl bg-indigo-50 p-2 text-indigo-500"><Symbol name="decision" /></span><div><p className="text-[9px] font-semibold uppercase tracking-[.15em] text-indigo-500">The decision brief</p><h3 className="mt-1 text-base font-semibold text-slate-900">A clear next step</h3></div></div><div className="mt-3"><Points items={["Up to four focused priorities", "Applied skills, facts and reasoning", "Actions, assumptions and alternatives"]} /></div><Link href="/decisions#decision-orchestration" className={`mt-3 inline-flex rounded text-[11px] font-semibold text-indigo-700 underline underline-offset-4 ${focusStyle}`}>Inspect a real decision →</Link></div>
      </div>
    </div>

    <div className="flex flex-wrap items-center justify-between gap-3 border-y border-slate-100 px-5 py-3 sm:px-7"><p className="text-[10px] leading-5 text-slate-500"><span className="font-semibold text-slate-700">Evidence layer</span><span className="mx-2 text-slate-300">/</span>Dhan market data · MFAPI + AMC disclosures · Bank + issue terms · Tax rules<span className="ml-2 text-slate-400">when available</span></p><button type="button" aria-pressed={selection.kind === "skills"} aria-controls="architecture-inspector" onClick={() => setSelection({ kind: "skills" })} className={`flex items-center gap-2 rounded text-[11px] font-semibold text-teal-800 ${focusStyle}`}><Symbol name="skills" className="h-4 w-4" /> Skills & the role of AI ↗</button></div>

    <div id="architecture-inspector" aria-label="Architecture details" className="bg-white p-5 sm:p-7">
      <div aria-live="polite" aria-atomic="true" className="sr-only">{selectedAgent ? `${selectedAgent.name} agent details selected` : selectedStage ? `${selectedStage.label} coordinator step selected` : selection.kind === "twin" ? "Digital Financial Twin details selected" : "Skills and AI details selected"}</div>
      {selectedAgent ? <>
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[9px] font-semibold uppercase tracking-[.18em] text-teal-700">Inside the specialist</p><h3 className="mt-1 text-lg font-semibold text-slate-900">{selectedAgent.name}</h3><p className="mt-1 text-xs leading-6 text-slate-500">{selectedAgent.description}</p></div><Link href={selectedAgent.href} className={`rounded-lg bg-slate-50 px-3 py-2 text-[11px] font-semibold text-slate-700 ${focusStyle}`}>Open workspace ↗</Link></div>
        <div className="mt-5 grid gap-5 md:grid-cols-3"><DetailColumn number="01" title="Receives" items={selectedAgent.receives} /><DetailColumn number="02" title="Returns to the coordinator" items={selectedAgent.sends} /><div className="min-w-0"><ColumnTitle number="03" title="Skills it applies" /><div className="mt-3 space-y-3">{selectedAgent.skills.map((skill) => <p key={skill.name} className="text-xs leading-6 text-slate-500"><span className="block font-semibold text-slate-800">{skill.name}</span>{skill.principle}</p>)}</div></div></div>
        <details className="mt-5 rounded-xl border border-slate-100 px-4 py-3"><summary className="cursor-pointer text-[11px] font-semibold text-slate-600">Financial reading · {selectedAgent.referenceCount} registered references + the shared portfolio guide</summary><p className="mt-3 text-[10px] leading-6 text-slate-500">Selected examples below. Registered material supplies a framework; the exact skill citation in a decision shows which principle was applied.</p><div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">{selectedAgent.references.map((reference) => <a key={reference.url} href={reference.url} target="_blank" rel="noreferrer" className={`rounded text-[11px] leading-6 text-teal-800 underline underline-offset-4 ${focusStyle}`}>{reference.label} ↗</a>)}</div></details>
      </> : selectedStage ? <>
        <p className="text-[9px] font-semibold uppercase tracking-[.18em] text-teal-700">Inside central orchestration · Step {orchestrationStages.indexOf(selectedStage) + 1} of 5</p><h3 className="mt-1 text-lg font-semibold text-slate-900">{selectedStage.label}</h3><p className="mt-1 max-w-4xl text-xs leading-6 text-slate-500">{selectedStage.description}</p><div className="mt-5 grid gap-5 md:grid-cols-3"><DetailColumn number="01" title="Receives" items={selectedStage.receives} /><DetailColumn number="02" title="What happens here" items={selectedStage.checks} /><DetailColumn number="03" title="Passes forward" items={selectedStage.sends} /></div><p className="mt-4 rounded-lg bg-slate-50 px-3 py-2 text-[10px] leading-6 text-slate-500"><span className="font-semibold text-slate-700">Role of the model:</span> {selectedStage.modelNote}</p>
      </> : selection.kind === "twin" ? <>
        <p className="text-[9px] font-semibold uppercase tracking-[.18em] text-teal-700">The starting point</p><h3 className="mt-1 text-lg font-semibold text-slate-900">One picture of the person behind the portfolio.</h3><div className="mt-4 grid gap-5 md:grid-cols-3"><DetailColumn number="01" title="Build from your records" items={["Holdings, deposits and transactions", "Income, expenses, liabilities and reserves", "Goals and psychometric assessment"]} /><DetailColumn number="02" title="Give each specialist context" items={["The same dated financial snapshot", "Risk willingness and ability to absorb loss", "The selected objective and confirmed budget"]} /><DetailColumn number="03" title="Keep the boundaries clear" items={["Unknown facts remain marked unknown", "External evidence keeps its own source and date", "New analysis does not create money or change your holdings"]} /></div>
      </> : <SkillsDetail focusStyle={focusStyle} />}
    </div>
    <div className="flex flex-wrap justify-between gap-2 border-t border-slate-100 bg-slate-50/60 px-5 py-3 text-[10px] leading-5 text-slate-500 sm:px-7"><span>This is the architecture map. Actual inputs, LLM calls and checks are recorded in Decisions.</span><span>For FIRE, the Goals specialist becomes the saved-goal FIRE planner.</span></div>
    <style jsx>{`
      @keyframes architecture-flow { to { stroke-dashoffset: -48; } }
      @media (prefers-reduced-motion: no-preference) { .architecture-wires .flow-line { animation: architecture-flow 12s linear infinite; } }
    `}</style>
  </section>;
}

function ColumnTitle({ number, title }: { number: string; title: string }) {
  return <h4 className="flex items-center gap-2 border-b border-slate-100 pb-2 text-[11px] font-semibold text-slate-800"><span className="font-mono text-[9px] text-teal-600">{number}</span>{title}</h4>;
}

function DetailColumn({ number, title, items }: { number: string; title: string; items: string[] }) {
  return <div className="min-w-0"><ColumnTitle number={number} title={title} /><div className="mt-3"><Points items={items} /></div></div>;
}

function SkillsDetail({ focusStyle }: { focusStyle: string }) {
  return <><p className="text-[9px] font-semibold uppercase tracking-[.18em] text-teal-700">The reasoning layer</p><h3 className="mt-1 text-lg font-semibold text-slate-900">Skills guide the logic. Evidence supports the answer.</h3><p className="mt-2 max-w-4xl text-xs leading-6 text-slate-500">Each specialist has its own financial guide. The coordinator also uses three shared portfolio references to reconcile the whole picture. Accepted findings cite the exact skill sections used.</p><div className="mt-5 grid gap-5 md:grid-cols-3">{sharedSkills.map((skill, index) => <div key={skill.name}><ColumnTitle number={`0${index + 1}`} title={skill.name} /><p className="mt-3 text-xs leading-6 text-slate-600">{skill.principle}</p></div>)}</div>
    <div className="mt-5 grid gap-4 md:grid-cols-2"><div className="rounded-xl bg-[#f0f7f4] p-4"><h4 className="text-xs font-semibold text-teal-900">What can go to an LLM?</h4><Points items={["Equity analysis can use relevant Twin context, market facts and skills when configured.", "The optional central explanation receives accepted proofs, specialist statuses and the shared budget.", "What-if scenarios can have a separate optional explanation."]} /></div><div className="rounded-xl bg-slate-50 p-4"><h4 className="text-xs font-semibold text-slate-800">What stays under explicit checks?</h4><Points items={["Calculations, quantities, contribution limits and priority ranking.", "Model JSON, allowed finding IDs and unsupported numbers or claims.", "Tax, FD, fund, Bond and goal calculations do not require six LLM calls."]} /></div></div>
    <details className="mt-4 rounded-xl border border-slate-100 px-4 py-3"><summary className="cursor-pointer text-[11px] font-semibold text-slate-600">Shared portfolio references and the FIRE route</summary><p className="mt-3 text-xs leading-6 text-slate-500">The saved FIRE planner uses recorded assumptions and psychometrics. Existing fund and Bond holdings supply context without being added to wealth twice. Equity reviews recorded exposure in this route. No model replaces the FIRE calculation.</p><div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">{sharedReferences.map((reference) => <a key={reference.url} href={reference.url} target="_blank" rel="noreferrer" className={`rounded text-[11px] leading-6 text-teal-800 underline underline-offset-4 ${focusStyle}`}>{reference.label} ↗</a>)}</div></details>
  </>;
}
