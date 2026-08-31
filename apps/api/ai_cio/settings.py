"""Runtime settings for the canonical Postgres application."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

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
INSTRUMENT_PATH = Path(
    os.getenv("INSTRUMENT_PATH", ROOT / "instruments" / "v1.0.json")
)
DEFAULT_USER_ID = os.getenv("AICIO_USER_ID")
PARSER_VERSION = os.getenv("CAS_PARSER_VERSION", "cas-v1")
KNOWLEDGE_DIR = ROOT / "knowledge"
UPLOAD_DIR = ROOT / "data" / "uploads"

# Market intelligence
MARKET_POLL_INTERVAL_SECONDS = int(os.getenv("MARKET_POLL_INTERVAL_SECONDS", "300"))
MARKET_CACHE_TTL_SECONDS = int(os.getenv("MARKET_CACHE_TTL_SECONDS", "300"))
OPPORTUNITY_SECTOR_CHANGE_THRESHOLD = float(os.getenv("OPPORTUNITY_SECTOR_CHANGE_THRESHOLD", "3.0"))
OPPORTUNITY_RELATIVE_CHANGE_THRESHOLD = float(os.getenv("OPPORTUNITY_RELATIVE_CHANGE_THRESHOLD", "2.0"))
OPPORTUNITY_EXPOSURE_THRESHOLD_PCT = float(os.getenv("OPPORTUNITY_EXPOSURE_THRESHOLD_PCT", "5.0"))

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

# Email notifications
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "log")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@ai-cio.local")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", os.getenv("SMTP_USERNAME", ""))
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}
