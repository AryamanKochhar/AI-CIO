"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button, Card, PageHeader, StatusBadge } from "@ai-cio/ui";
import { reviewApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

export default function ReviewPage() {
  const { user } = useAuth();
  const [review, setReview] = useState<Record<string, any> | null>(null);

  useEffect(() => {
    if (!user) return;
    reviewApi.get(user.id).then(setReview).catch(() => setReview(null));
  }, [user]);

  if (!user) {
    return (
      <Card>
        <PageHeader title="Review" description="Please sign in first." />
        <Link href="/login"><Button>Sign in</Button></Link>
      </Card>
    );
  }

  if (!review) {
    return <Card><p className="text-sm text-slate-600">Loading your profile review…</p></Card>;
  }

  const completeness = review.completeness ?? {};

  return (
    <Card>
      <PageHeader
        title="Review your financial profile"
        description="Unknown means we do not have the fact — not that it is zero."
      />
      <div className="mb-6 flex flex-wrap gap-2">
        {Object.entries(completeness).map(([key, value]) => (
          <StatusBadge key={key} status={value ? "known" : "unknown"}>
            {key}: {value ? "known" : "unknown"}
          </StatusBadge>
        ))}
      </div>
      <div className="space-y-4 text-sm text-slate-700">
        <section>
          <h2 className="font-semibold text-slate-900">Behaviour</h2>
          <p>{review.behaviour?.status === "known" ? "Assessment complete" : "Not provided"}</p>
        </section>
        <section>
          <h2 className="font-semibold text-slate-900">Financial situation</h2>
          <p>Income: {review.finances?.income?.value ?? "unknown"}</p>
          <p>Expenses: {review.finances?.expenses?.value ?? "unknown"}</p>
          <p>Liquid savings: {review.finances?.liquid?.value ?? "unknown"}</p>
        </section>
        <section>
          <h2 className="font-semibold text-slate-900">Portfolio</h2>
          <p>Total extracted value: {review.portfolio?.total_value?.value ?? "unknown"}</p>
        </section>
      </div>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link href="/onboarding/finances"><Button variant="secondary">Edit finances</Button></Link>
        <Link href="/onboarding/goals"><Button variant="secondary">Edit goals</Button></Link>
        <Link href="/onboarding/documents"><Button variant="secondary">Edit documents</Button></Link>
        <Link href="/onboarding/twin"><Button>View financial profile</Button></Link>
      </div>
    </Card>
  );
}
