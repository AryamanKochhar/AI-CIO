#!/usr/bin/env python3
"""Ingest a local MFCentral CAS. Default target is canonical Postgres."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parser import parse_cas


def _postgres(ns) -> None:
    from ai_cio.db.session import get_session
    from ai_cio.services.portfolio import ingest_cas

    db = get_session()
    try:
        document, result = ingest_cas(db, ns.user_id, ns.pdf)
        db.commit()
        print(
            f"Ingested {len(result.holdings)} holdings and {len(result.transactions)} "
            f"transactions as document {document.id} for user {ns.user_id}."
        )
        if result.warnings:
            print("Warnings: " + "; ".join(result.warnings))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _sqlite(ns) -> None:
    from config import DATABASE_PATH
    from database import replace_portfolio

    database = ns.database
    database.parent.mkdir(exist_ok=True)
    result = parse_cas(ns.pdf)
    if not result.holdings:
        print("Ingestion stopped: " + "; ".join(result.warnings), file=sys.stderr)
        raise SystemExit(2)
    replace_portfolio(database, result)
    print(
        f"[legacy sqlite] Ingested {len(result.holdings)} holdings and "
        f"{len(result.transactions)} transactions into {database}."
    )
    if result.warnings:
        print("Warnings: " + "; ".join(result.warnings))


args = argparse.ArgumentParser(description="Ingest a local MFCentral CAS into canonical Postgres.")
args.add_argument("pdf", type=Path)
args.add_argument("--user-id", type=int, help="Canonical users.id (required unless --sqlite)")
args.add_argument("--sqlite", action="store_true", help="Legacy SQLite path (not used by MCP/API)")
args.add_argument("--database", type=Path, default=None, help="SQLite path when using --sqlite")
ns = args.parse_args()
if ns.sqlite:
    from config import DATABASE_PATH

    if ns.database is None:
        ns.database = DATABASE_PATH
    _sqlite(ns)
else:
    if ns.user_id is None:
        args.error("--user-id is required for Postgres ingest")
    _postgres(ns)
