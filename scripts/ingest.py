#!/usr/bin/env python3
"""Ingest a local MFCentral CAS into canonical Postgres."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from domain.parser import parse_cas


def main() -> None:
    from ai_cio.db.session import get_session
    from ai_cio.services.portfolio import ingest_cas

    args = argparse.ArgumentParser(description="Ingest a local MFCentral CAS into Postgres.")
    args.add_argument("pdf", type=Path)
    args.add_argument("--user-id", type=int, required=True, help="Canonical users.id")
    ns = args.parse_args()

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


if __name__ == "__main__":
    main()
