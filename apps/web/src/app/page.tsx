import Link from "next/link";
import { Button, Card, PageHeader } from "@ai-cio/ui";

export default function HomePage() {
  return (
    <div className="space-y-8">
      <section className="rounded-3xl bg-slate-900 px-8 py-12 text-white shadow-xl">
        <PageHeader
          kicker="AI-CIO"
          title="One journey toward clearer financial decisions"
          description="Understand how you decide, capture what you know about your finances, upload statements, and review your digital financial profile — all in one calm, guided experience."
        />
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/login">
            <Button>Get started</Button>
          </Link>
          <Link href="/onboarding/understand-me">
            <Button variant="secondary" className="border-white/20 bg-white/10 text-white hover:bg-white/20">
              Continue onboarding
            </Button>
          </Link>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        {[
          ["Understand me", "A short behavioural questionnaire scored securely on our servers."],
          ["My finances & goals", "Progressive forms that never invent missing numbers."],
          ["Your financial profile", "A digital twin assembled from what you provide and your documents."],
        ].map(([title, body]) => (
          <Card key={title}>
            <h2 className="text-base font-semibold text-slate-900">{title}</h2>
            <p className="mt-2 text-sm text-slate-600">{body}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
