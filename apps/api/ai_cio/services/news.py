"""Portfolio news from GNews for the user's largest parsed holdings."""
from __future__ import annotations

import re
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ai_cio.settings import GNEWS_API_KEY, GNEWS_LIMIT
from ai_cio.services import portfolio as portfolio_svc

GNEWS_URL = "https://gnews.io/api/v4/search"
TOP_HOLDINGS_LIMIT = 5
CORPORATE_ACTION_SUFFIX = re.compile(
    r"\s*(?:[-|,:/]\s*)?(?:BONUS|SPLIT|RIGHTS?|DIVIDEND|MERGER|DEMERGER|BUYBACK|CONSOLIDATION|FACE\s+VALUE|FV\b).*$",
    re.IGNORECASE,
)


def _clean_stock_name(value: Any) -> str:
    name = str(value or "").strip()
    name = re.sub(r"\s*#.*$", "", name)
    name = re.sub(r"\s+EQUITY\s+SHARES?\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+(?:LIMITED|LTD\.?)\b", "", name, flags=re.IGNORECASE)
    name = CORPORATE_ACTION_SUFFIX.sub("", name)
    return re.sub(r"\s+", " ", name).strip(" -,:/")


def _gnews_query(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9\s]", " ", value)).strip()


def _gnews_term(value: str) -> str:
    return _gnews_query(value).split(" ", 1)[0]


def _article_holding(article: dict[str, Any], holdings: list[dict[str, Any]]) -> str:
    text = f"{article.get('title') or ''} {article.get('description') or ''}".lower()
    for holding in holdings:
        if _gnews_term(holding["name"]).lower() in text:
            return holding["name"]
    return "Portfolio holdings"


def get_portfolio_news(db: Session, user_id: int) -> dict[str, Any]:
    if not GNEWS_API_KEY:
        return {
            "available": False,
            "status": "not_configured",
            "holdings": [],
            "articles": [],
            "reason": "Add GNEWS_API_KEY to .env to enable portfolio news.",
        }

    all_holdings = portfolio_svc.list_holdings(db, user_id)
    holdings = [
        row
        for row in all_holdings
        if row.get("asset_class") == "equity" or row.get("amc") == "EQUITY"
    ][:TOP_HOLDINGS_LIMIT]
    if not holdings:
        holdings = [
            row
            for row in all_holdings
            if row.get("asset_class") != "equity" and row.get("amc") != "EQUITY"
        ][:TOP_HOLDINGS_LIMIT]
    selected = []
    for row in holdings:
        name = _clean_stock_name(row.get("scheme_name"))
        if name:
            selected.append(
                {
                    "name": name,
                    "valuation": str(row.get("valuation") or "0"),
                    "asset_class": row.get("asset_class"),
                }
            )
    if not selected:
        return {
            "available": False,
            "status": "no_equity_holdings",
            "holdings": [],
            "articles": [],
            "reason": "Your portfolio currently contains no direct equity holdings. News is available for stocks, not mutual-fund schemes.",
        }

    articles: list[dict[str, Any]] = []
    errors: list[str] = []
    query = " OR ".join(_gnews_term(holding["name"]) for holding in selected)
    with httpx.Client(timeout=15.0) as client:
        try:
            response = client.get(
                GNEWS_URL,
                params={
                    "q": query,
                    "lang": "en",
                    "max": GNEWS_LIMIT,
                    "apikey": GNEWS_API_KEY,
                },
            )
            response.raise_for_status()
            payload = response.json()
            for article in payload.get("articles", []):
                source = article.get("source") or {}
                articles.append(
                    {
                        "holding": _article_holding(article, selected),
                        "title": article.get("title"),
                        "description": article.get("description"),
                        "url": article.get("url"),
                        "image": article.get("image"),
                        "published_at": article.get("publishedAt"),
                        "source": source.get("name"),
                    }
                )
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(str(exc))

    if not articles and errors:
        return {
            "available": False,
            "status": "error",
            "holdings": selected,
            "articles": [],
            "reason": "GNews could not be reached. Check the API key and try again.",
        }

    articles.sort(key=lambda article: article.get("published_at") or "", reverse=True)
    return {
        "available": bool(articles),
        "status": "ready" if articles else "no_results",
        "holdings": selected,
        "articles": articles[:GNEWS_LIMIT],
        "reason": "No recent news found for the top holdings." if not articles else None,
    }
