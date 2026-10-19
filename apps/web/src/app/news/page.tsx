"use client";

import { useEffect, useState } from "react";
import {
  Card,
  ErrorState,
  LoadingState,
  PageHeader,
  StatusBadge,
} from "@ai-cio/ui";
import { newsApi, type NewsProfileImpact } from "@/lib/api";
import { useRequireAuth } from "@/hooks/use-journey";
import { AiTag } from "@/components/design/ai-tag";
import { DecisionNextSteps } from "@/components/decision-next-steps";

type NewsData = Awaited<ReturnType<typeof newsApi.portfolio>>;

function urgencyLabel(value?: string) {
  if (value === "watch") return "Watch — review profile soon";
  if (value === "monitor") return "Monitor — no urgent profile change";
  if (value === "no_material_change") return "No material profile change expected";
  return value || "Profile review";
}

function ProfileImpactSection({ impact }: { impact?: NewsProfileImpact }) {
  if (!impact) return null;

  if (!impact.used) {
    return (
      <Card className="aic-card-glow">
        <p className="text-sm text-slate-600">{impact.reason || impact.error || "Profile impact analysis unavailable."}</p>
      </Card>
    );
  }

  return (
    <Card className="aic-card-glow border-indigo-100/80">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold text-slate-900">How this news affects your profile</h2>
        <AiTag />
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Interpreted against your Twin — goals, behaviour, concentration, and liquidity. For review, not trade advice.
      </p>

      {impact.urgency ? (
        <div className="mt-3">
          <StatusBadge status="known">{urgencyLabel(impact.urgency)}</StatusBadge>
        </div>
      ) : null}

      {impact.summary ? (
        <p className="mt-4 text-sm leading-relaxed text-slate-800">{impact.summary}</p>
      ) : null}

      {impact.profile_areas && impact.profile_areas.length > 0 ? (
        <div className="mt-5 space-y-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Profile areas</p>
          {impact.profile_areas.map((row, index) => (
            <div key={`${row.area}-${index}`} className="rounded-lg border border-[rgba(15,55,110,0.1)] bg-white/60 p-3">
              <p className="text-sm font-medium capitalize text-slate-900">{row.area || "Profile"}</p>
              {row.impact ? <p className="mt-1 text-sm text-slate-700">{row.impact}</p> : null}
              {row.review_note ? <p className="mt-1 text-xs text-indigo-900">{row.review_note}</p> : null}
            </div>
          ))}
        </div>
      ) : null}

      {impact.holding_impacts && impact.holding_impacts.length > 0 ? (
        <div className="mt-5 space-y-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">By holding</p>
          {impact.holding_impacts.map((row, index) => (
            <div key={`${row.holding}-${index}`} className="rounded-lg border border-[rgba(15,55,110,0.1)] bg-white/60 p-3">
              <p className="text-sm font-medium text-slate-900">{row.holding}</p>
              {row.news_context ? <p className="mt-1 text-xs text-slate-500">{row.news_context}</p> : null}
              {row.profile_effect ? <p className="mt-2 text-sm text-slate-700">{row.profile_effect}</p> : null}
              {row.suggested_review ? (
                <p className="mt-1 text-xs font-medium text-indigo-900">{row.suggested_review}</p>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {impact.suggested_profile_reviews && impact.suggested_profile_reviews.length > 0 ? (
        <div className="mt-5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">Suggested profile reviews</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {impact.suggested_profile_reviews.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {impact.model_note ? <p className="mt-4 text-xs text-slate-500">{impact.model_note}</p> : null}
    </Card>
  );
}

function formatPublishedAt(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString();
}

export default function NewsPage() {
  const user = useRequireAuth();
  const [data, setData] = useState<NewsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    newsApi.portfolio(user.id).then((payload) => {
      if (!cancelled) setData(payload);
    }).catch((err: Error) => {
      if (!cancelled) setError(err.message || "Could not load portfolio news.");
    });
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (!user) return null;
  if (error) return <ErrorState title="Portfolio news unavailable" message={error} />;
  if (!data) return <LoadingState message="Loading news and profile impact analysis..." />;

  return (
    <div className="space-y-6">
      <DecisionNextSteps />
      <Card className="aic-card-glow">
        <PageHeader
          kicker="Portfolio news"
          title="News for your largest holdings"
          description="Recent GNews articles matched to the five holdings with the highest portfolio value."
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <StatusBadge status={data.available ? "known" : "unknown"}>
            {data.status}
          </StatusBadge>
        </div>
        {data.holdings.length > 0 ? (
          <div className="mt-5 flex flex-wrap gap-2">
            {data.holdings.map((holding) => (
              <span key={holding.name} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                {holding.name}
              </span>
            ))}
          </div>
        ) : null}
      </Card>

      {!data.available ? (
        <Card className="aic-card-glow">
          <p className="text-sm text-slate-700">
            {data.status === "no_equity_holdings"
              ? "Your portfolio currently contains mutual funds only. News is available for direct equity holdings."
              : data.reason || "No portfolio news is available yet."}
          </p>
        </Card>
      ) : (
        <>
          <ProfileImpactSection impact={data.profile_impact} />
        <Card className="aic-card-glow">
          <div className="space-y-4">
            {data.articles.map((article, index) => (
              <article key={`${article.url}-${index}`} className="border-b border-slate-100 pb-4 last:border-b-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span>{article.holding}</span>
                  {article.source ? <span>· {article.source}</span> : null}
                  {article.published_at ? <span>· {formatPublishedAt(article.published_at)}</span> : null}
                </div>
                {article.url ? (
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 block text-base font-semibold text-slate-900 underline-offset-2 hover:underline"
                  >
                    {article.title || "Open article"}
                  </a>
                ) : (
                  <p className="mt-1 text-base font-semibold text-slate-900">{article.title || "Untitled article"}</p>
                )}
                {article.description ? <p className="mt-1 text-sm text-slate-600">{article.description}</p> : null}
              </article>
            ))}
          </div>
        </Card>
        </>
      )}
    </div>
  );
}
