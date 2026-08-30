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
