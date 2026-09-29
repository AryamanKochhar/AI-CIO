"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Button,
  Card,
  ErrorState,
  LoadingState,
  PageHeader,
  ProfileSection,
  StatusBadge,
} from "@ai-cio/ui";
import { formatCurrency } from "@ai-cio/utils";
import { reviewApi } from "@/lib/api";
import { COMPLETENESS_LABELS } from "@/lib/constants";
import { useRequireAuth, useJourney } from "@/hooks/use-journey";

type MoneyValue = { value?: string | number | null };
type ReviewGoal = { name: string; target_amount?: string | number | null };
type ReviewPayload = {
  completeness?: Record<string, boolean>;
  behaviour?: {
    source?: string;
    status?: string;
    observations?: string[];
  };
  finances?: {
    income?: MoneyValue;
    expenses?: MoneyValue;
    liquid?: MoneyValue;
  };
  goals?: { items?: ReviewGoal[] };
  portfolio?: { total_value?: MoneyValue };
};

export default function ReviewPage() {
  const user = useRequireAuth();
  const router = useRouter();
  const { setStep } = useJourney();
  const [review, setReview] = useState<ReviewPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    reviewApi
      .get(user.id)
      .then((payload) => setReview(payload as ReviewPayload))
      .catch(() => setError("We couldn't load your review. Please try again."));
  }, [user]);

  async function continueToProfile() {
    await setStep("review");
    router.push("/onboarding/twin");
  }

  if (!user) return null;
  if (error) return <ErrorState title="Review unavailable" message={error} />;
  if (!review) return <LoadingState message="Preparing your review…" />;

  const completeness = review.completeness ?? {};

  return (
    <div className="space-y-6">
      <Card className="aic-card-glow">
        <PageHeader
          title="Review your information"
          description="Unknown means we don't have the fact — not that it is zero."
        />
        <div className="flex flex-wrap gap-2">
          {Object.entries(completeness).map(([key, value]) => (
            <StatusBadge key={key} status={value ? "known" : "unknown"}>
              {COMPLETENESS_LABELS[key] ?? key}: {value ? "provided" : "missing"}
            </StatusBadge>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <ProfileSection title="How you make decisions" source={review.behaviour?.source}>
          {review.behaviour?.status === "known" ? (
            <ul className="space-y-2 text-sm text-slate-700">
              {(review.behaviour?.observations ?? []).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-600">Not provided</p>
          )}
        </ProfileSection>

        <ProfileSection title="Financial position" source="You provided">
          <ul className="space-y-2 text-sm text-slate-700">
            <li>
              Income:{" "}
              {review.finances?.income?.value
                ? formatCurrency(review.finances.income.value)
                : "Not provided"}
            </li>
            <li>
              Expenses:{" "}
              {review.finances?.expenses?.value
                ? formatCurrency(review.finances.expenses.value)
                : "Not provided"}
            </li>
            <li>
              Liquid savings:{" "}
              {review.finances?.liquid?.value
                ? formatCurrency(review.finances.liquid.value)
                : "Not provided"}
            </li>
          </ul>
        </ProfileSection>

        <ProfileSection title="Goals" source="You provided">
          {review.goals?.items?.length ? (
            <ul className="space-y-2 text-sm text-slate-700">
              {review.goals.items.map((g) => (
                <li key={g.name}>
                  {g.name} · {formatCurrency(g.target_amount)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-600">Not provided</p>
          )}
        </ProfileSection>

        <ProfileSection title="Portfolio" source="CAS">
          <p className="text-sm text-slate-700">
            Total:{" "}
            {review.portfolio?.total_value?.value
              ? formatCurrency(review.portfolio.total_value.value)
              : "Not provided"}
          </p>
        </ProfileSection>
      </div>

      <Card className="aic-card-glow">
        <div className="flex flex-wrap gap-3">
          <Link href="/onboarding/finances">
            <Button variant="secondary">Edit finances</Button>
          </Link>
          <Link href="/onboarding/goals">
            <Button variant="secondary">Edit goals</Button>
          </Link>
          <Link href="/onboarding/documents">
            <Button variant="secondary">Edit portfolio</Button>
          </Link>
          <Button onClick={continueToProfile}>View my financial profile</Button>
        </div>
      </Card>
    </div>
  );
}
