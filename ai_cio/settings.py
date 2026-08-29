"""Runtime settings for the canonical Postgres application."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/ai_cio",
)
INSTRUMENT_PATH = Path(
    os.getenv("INSTRUMENT_PATH", ROOT / "instruments" / "v1.0.json")
)
DEFAULT_USER_ID = os.getenv("AICIO_USER_ID")
PARSER_VERSION = os.getenv("CAS_PARSER_VERSION", "cas-v1")
KNOWLEDGE_DIR = ROOT / "knowledge"
UPLOAD_DIR = ROOT / "data" / "uploads"
