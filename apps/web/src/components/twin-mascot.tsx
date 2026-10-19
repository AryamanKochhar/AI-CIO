import Link from "next/link";

const PARTS = [
  { key: "psychometric", label: "Mind", detail: "How you make decisions", href: "/onboarding/understand-me" },
  { key: "income", label: "Toolkit", detail: "Income and spending", href: "/onboarding/finances" },
  { key: "liquid", label: "Shield", detail: "Liquid savings recorded", href: "/onboarding/finances" },
  { key: "goals", label: "Compass", detail: "Goals and time horizon", href: "/onboarding/goals" },
  { key: "portfolio", label: "Growth chart", detail: "Your investments", href: "/onboarding/documents" },
] as const;

export function TwinMascot({ completeness = {} }: { completeness?: Record<string, boolean> }) {
  const count = PARTS.filter((part) => completeness[part.key]).length;
  return (
    <section aria-label="Build your financial twin" className="rounded-3xl border border-teal-100 bg-gradient-to-br from-teal-50 via-white to-blue-50 p-6">
      <div className="flex flex-col items-center gap-6 sm:flex-row">
        <svg viewBox="0 0 240 220" role="img" aria-label={`Your twin has ${count} of 5 knowledge accessories`} className="h-48 w-52 shrink-0">
          <ellipse cx="120" cy="202" rx="75" ry="9" fill="#cbd5e1" opacity=".4" />
          <path d="M78 160 L72 192 M162 160 L168 192" stroke="#123651" strokeWidth="14" strokeLinecap="round" />
          <rect x="67" y="100" width="106" height="78" rx="32" fill="#0f766e" />
          <path d="M70 118 L47 143 M170 118 L193 143" stroke="#0f766e" strokeWidth="15" strokeLinecap="round" />
          <rect x="61" y="35" width="118" height="89" rx="34" fill="#ccfbf1" stroke="#0f766e" strokeWidth="4" />
          <circle cx="95" cy="74" r="6" fill="#123651" /><circle cx="145" cy="74" r="6" fill="#123651" />
          <path d="M101 93 Q120 109 139 93" fill="none" stroke="#123651" strokeWidth="4" strokeLinecap="round" />
          {completeness.psychometric ? <g fill="#2563eb"><rect x="80" y="54" width="33" height="30" rx="11" fill="none" stroke="#2563eb" strokeWidth="3" /><rect x="127" y="54" width="33" height="30" rx="11" fill="none" stroke="#2563eb" strokeWidth="3" /><path d="M113 67h14" stroke="#2563eb" strokeWidth="3" /></g> : null}
          {completeness.income ? <g><rect x="35" y="137" width="40" height="35" rx="7" fill="#d97706" /><path d="M45 137v-9h20v9" fill="none" stroke="#92400e" strokeWidth="3" /><path d="M35 149h40" stroke="#fcd34d" strokeWidth="3" /></g> : null}
          {completeness.liquid ? <g><path d="M172 126l31 9v22q-4 17-31 29-27-12-31-29v-22z" fill="#2563eb" /><path d="M159 153l9 9 17-20" fill="none" stroke="white" strokeWidth="4" strokeLinecap="round" /></g> : null}
          {completeness.goals ? <g><circle cx="120" cy="137" r="17" fill="#fef3c7" stroke="#d97706" strokeWidth="2" /><path d="M125 127l-2 14-10 7 2-14z" fill="#d97706" /></g> : null}
          {completeness.portfolio ? <g stroke="#16a34a" strokeWidth="4" fill="none" strokeLinecap="round"><path d="M185 85h35V45" opacity=".3" /><path d="M187 75l10-12 9 5 13-23" /></g> : null}
        </svg>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-widest text-teal-700">Your digital financial twin</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-900">Meet your growing companion</h2>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-600">Each detail you share adds a useful part to your twin. Accessories show information available, while the analysis explains what it means.</p>
          <p className="mt-3 text-sm font-medium text-teal-800">{count} of 5 parts added</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {PARTS.map((part) => <Link key={part.key} href={part.href} title={part.detail} className={`rounded-full border px-3 py-1.5 text-xs font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${completeness[part.key] ? "border-teal-200 bg-teal-100 text-teal-900" : "border-slate-200 bg-white text-slate-600"}`}>{completeness[part.key] ? "✓ " : "+ "}{part.label}</Link>)}
          </div>
        </div>
      </div>
    </section>
  );
}
