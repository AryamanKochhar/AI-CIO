"use client";

import { useEffect, useState } from "react";
import {
  Card,
  ErrorState,
  LoadingState,
  PageHeader,
  StatusBadge,
} from "@ai-cio/ui";
import { newsApi } from "@/lib/api";
import { useRequireAuth } from "@/hooks/use-journey";

type NewsData = Awaited<ReturnType<typeof newsApi.portfolio>>;

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
  if (!data) return <LoadingState message="Loading news for your largest holdings..." />;

  return (
    <div className="space-y-6">
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
      )}
    </div>
  );
}
