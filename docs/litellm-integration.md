# LiteLLM Integration — AI-CIO

> External model gateway for market observation **interpretation**. Numerical truth remains in deterministic backend layers.

## Role

LiteLLM is the **interpretation / synthesis** layer only:

```
NSE → Market Snapshot → Sector Analytics → Portfolio Exposure → Opportunity Candidate
  → Knowledge Retrieval → Sanitized Twin Context → LiteLLM → Structured Analysis → Email
```

LiteLLM must **not** calculate portfolio weights, invent holdings, or recommend buy/sell actions.

## Architecture

```
AI-CIO (FastAPI)
    ↓
LLMProvider (abstract)
    ↓
LiteLLMProvider
    ↓
https://litellm-infra.valura.ai  (OpenAI-compatible /chat/completions)
    ↓
Configured model (LLM_MODEL)
```

When disabled or misconfigured, `DeterministicLLMProvider` produces observation text without calling the gateway.

## Configuration

Set in `.env` (never commit secrets):

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_ENABLED` | No | `true` to enable gateway calls (default `false`) |
| `LITELLM_BASE_URL` | When enabled | Gateway base URL, e.g. `https://litellm-infra.valura.ai` |
| `LITELLM_API_KEY` | When enabled | API key (rotate if ever exposed) |
| `LLM_MODEL` | When enabled | Model identifier from gateway `/v1/models` |
| `LLM_PROVIDER` | No | `litellm` (default) |

Legacy aliases `LLM_BASE_URL` and `LLM_API_KEY` are supported but `LITELLM_*` names are canonical.

### Model discovery

Query the gateway (with your key in `.env` only):

```bash
curl -s -H "Authorization: Bearer $LITELLM_API_KEY" \
  "$LITELLM_BASE_URL/v1/models" | python3 -m json.tool
```

Set `LLM_MODEL` to one of the returned `id` values. Do not guess model names in code.

## Health checks

- `GET /health` — overall API health including `llm` status summary
- `GET /health/llm` — LiteLLM configuration probe (never returns API keys)

Example shape:

```json
{
  "enabled": true,
  "configured": true,
  "reachable": true,
  "model_configured": true,
  "test_successful": true,
  "status": "ok"
}
```

LiteLLM failure does **not** prevent application startup.

## Sanitized context boundary

`TwinAnalysisContextBuilder` (`apps/api/ai_cio/services/twin_context_builder.py`) converts the Digital Financial Twin into `SanitizedAnalysisContext` before any external call.

**Included:** sector exposure, holdings summary, goals, behavioural observations, liquidity/liabilities flags, completeness, knowledge references.

**Excluded:** PAN, Aadhaar, passwords, API keys, raw CAS text, full document contents, bank account numbers.

## Structured output

The model returns JSON validated against `MarketOpportunityAnalysis`:

- `opportunity_type`, `summary`, `why_relevant`, `market_facts`, `portfolio_facts`
- `risks`, `missing_information`, `knowledge_references`, `confidence`, `recommended_next_step`

Malformed output or forbidden phrases (e.g. "buy now") cause a safe fallback to deterministic analysis; the opportunity is retained.

## Failure behavior

| Condition | Behavior |
|-----------|----------|
| `LLM_ENABLED=false` | Deterministic analysis only |
| Missing key/model | Misconfigured; deterministic fallback |
| Gateway timeout/error | Log warning; deterministic fallback |
| Invalid JSON / forbidden text | Validation failure; deterministic fallback |

Market data, Twin, and UI continue to work.

## Email

Notifications use a **deterministic template** with model-generated explanatory fields. Recipient: `NOTIFICATION_EMAIL` or user email. Development uses log provider (`EMAIL_PROVIDER=log`).

## Local development

```bash
make install
make dev-build   # after requirements.txt changes (adds litellm)
make dev-up
```

LiteLLM is external — no local LiteLLM container is started.

## Production

- Store secrets in environment / secret manager
- Use `EMAIL_PROVIDER=smtp` with `SMTP_*` variables
- Rotate API keys if exposed in chat, logs, or commits

## Security

- Never log API keys or Authorization headers
- Never commit `.env`
- Rotate exposed keys immediately
- Treat external LLM as untrusted — sanitize all Twin payloads

## Code locations

| Component | Path |
|-----------|------|
| Provider abstraction | `apps/api/ai_cio/llm/provider.py` |
| Service facade | `apps/api/ai_cio/services/llm_provider.py` |
| Twin sanitizer | `apps/api/ai_cio/services/twin_context_builder.py` |
| Market orchestration | `apps/api/ai_cio/services/market_context.py` |
| Settings | `apps/api/ai_cio/settings.py` |
| Tests | `tests/test_litellm_integration.py` |
