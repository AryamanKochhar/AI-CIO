# Financial Explainability Skill — AI-CIO

Use when writing user-facing copy for market observations, Twin insights, or emails.

## Tone

- Plain language; avoid "LLM", "API", "prompt", "model" in user UI.
- Lead with **what happened** (market), then **why it matters to this user** (exposure), then **what to review** (not what to trade).

## Required disclosures

Every market observation must show:

- **Source:** NSE (or configured provider)
- **As of:** timestamp
- **Freshness:** Live / Recent / Stale — never label cached data as live

Include: "This is a market observation, not a buy/sell instruction."

## Forbidden language

Reject or sanitize:

- Buy now / Sell now
- Guaranteed / Risk-free / Certain return
- This stock will rise/fall
- Definitely buy/sell

Email template: `build_market_observation_email()` in `apps/api/ai_cio/services/notifications.py`.

## UI patterns

- **Market today** — benchmark move
- **Sector movement** — heatmap
- **Your exposure** — only when authoritative from Twin
- **Why AI-CIO is showing this** — deterministic observation
- **AI-CIO's analysis** — when structured analysis exists

## Related docs

- `docs/notification-architecture.md`
- `docs/litellm-integration.md`
