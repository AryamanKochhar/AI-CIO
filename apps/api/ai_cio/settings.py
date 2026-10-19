"""Runtime settings for the canonical Postgres application."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
# Explicit process configuration wins. Tests never load live database/provider
# credentials from a developer's .env, even when the app uses a shared database.
if os.getenv("AICIO_TESTING") != "1":
    load_dotenv(Path(os.getenv("AICIO_ENV_FILE", str(ROOT / ".env"))), override=False)

def _require_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is required. Copy .env.example to .env and run `make dev-up`."
        )
    if url.startswith("sqlite"):
        raise RuntimeError(
            "SQLite is not supported as the runtime database. Use PostgreSQL via `make dev-up`."
        )
    return url


DATABASE_URL = _require_database_url()
INSTRUMENT_PATH = Path(os.getenv("INSTRUMENT_PATH", "instruments/v1.0.json"))
if not INSTRUMENT_PATH.is_absolute():
    INSTRUMENT_PATH = ROOT / INSTRUMENT_PATH
DEFAULT_USER_ID = os.getenv("AICIO_USER_ID")
PARSER_VERSION = os.getenv("CAS_PARSER_VERSION", "cas-v1")
KNOWLEDGE_DIR = ROOT / "knowledge"
UPLOAD_DIR = ROOT / "data" / "uploads"

# Market intelligence
MARKET_POLL_INTERVAL_SECONDS = int(os.getenv("MARKET_POLL_INTERVAL_SECONDS", "300"))
MARKET_CACHE_TTL_SECONDS = int(os.getenv("MARKET_CACHE_TTL_SECONDS", "300"))
try:
    DECISION_CACHE_TTL_SECONDS = max(0, min(int(os.getenv("DECISION_CACHE_TTL_SECONDS", "300")), 3600))
except ValueError:
    DECISION_CACHE_TTL_SECONDS = 0  # A malformed TTL disables reuse.
OPPORTUNITY_SECTOR_CHANGE_THRESHOLD = float(os.getenv("OPPORTUNITY_SECTOR_CHANGE_THRESHOLD", "3.0"))
OPPORTUNITY_RELATIVE_CHANGE_THRESHOLD = float(os.getenv("OPPORTUNITY_RELATIVE_CHANGE_THRESHOLD", "2.0"))
OPPORTUNITY_EXPOSURE_THRESHOLD_PCT = float(os.getenv("OPPORTUNITY_EXPOSURE_THRESHOLD_PCT", "5.0"))

# Portfolio news (GNews)
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "").strip()
GNEWS_LIMIT = max(1, min(int(os.getenv("GNEWS_LIMIT", "5")), 100))

# LLM (LiteLLM gateway — external infrastructure)
LLM_ENABLED = os.getenv("LLM_ENABLED", "false").lower() in {"1", "true", "yes"}
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "litellm")
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
LITELLM_BASE_URL = (os.getenv("LITELLM_BASE_URL") or os.getenv("LLM_BASE_URL", "")).strip().rstrip("/")
LITELLM_API_KEY = (os.getenv("LITELLM_API_KEY") or os.getenv("LLM_API_KEY", "")).strip()
# Backward-compatible aliases (do not set both naming schemes to different values)
LLM_BASE_URL = LITELLM_BASE_URL
LLM_API_KEY = LITELLM_API_KEY
OPPORTUNITY_ANALYSIS_PROMPT_VERSION = os.getenv("OPPORTUNITY_ANALYSIS_PROMPT_VERSION", "v1")

# Equity / Decisions LLM — toggle provider in .env (openai | openrouter)
EQUITY_LLM_PROVIDER = os.getenv("EQUITY_LLM_PROVIDER", "openai").strip().lower()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free").strip()
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip().rstrip("/")
# OPEN_API_KEY is accepted as an alias for OPENAI_API_KEY (common typo / shorthand).
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY") or "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
EQUITY_AGENT_ENABLED = os.getenv("EQUITY_AGENT_ENABLED", "true").lower() in {"1", "true", "yes"}


def equity_llm_provider() -> str:
    return "openai" if EQUITY_LLM_PROVIDER == "openai" else "openrouter"


def equity_llm_api_key() -> str:
    return OPENAI_API_KEY if equity_llm_provider() == "openai" else OPENROUTER_API_KEY


def equity_llm_model() -> str:
    return OPENAI_MODEL if equity_llm_provider() == "openai" else OPENROUTER_MODEL


def equity_llm_base_url() -> str:
    return OPENAI_BASE_URL if equity_llm_provider() == "openai" else OPENROUTER_BASE_URL


def equity_llm_configured() -> bool:
    return bool(equity_llm_api_key())

# DhanHQ (sector opportunity scorer on Decisions — read-only market data)
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "").strip()
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
DHAN_PIN = os.getenv("DHAN_PIN", "").strip()
DHAN_TOTP_SECRET = os.getenv("DHAN_TOTP_SECRET", "").strip()
SECTOR_OPPORTUNITY_ENABLED = os.getenv("SECTOR_OPPORTUNITY_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
TAX_INTELLIGENCE_ENABLED = os.getenv("TAX_INTELLIGENCE_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
FD_INTELLIGENCE_ENABLED = os.getenv("FD_INTELLIGENCE_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
TRAJECTORY_INTELLIGENCE_ENABLED = os.getenv("TRAJECTORY_INTELLIGENCE_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}

# Trendlyne sector day-change for Decisions equity context
TRENDLYNE_SECTOR_DAY_CHANGE_ENABLED = os.getenv(
    "TRENDLYNE_SECTOR_DAY_CHANGE_ENABLED", "true"
).lower() in {"1", "true", "yes"}
TRENDLYNE_SECTOR_CACHE_TTL_SECONDS = int(os.getenv("TRENDLYNE_SECTOR_CACHE_TTL_SECONDS", "300"))

# Email notifications
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "log")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@ai-cio.local")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", os.getenv("SMTP_USERNAME", ""))
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}
