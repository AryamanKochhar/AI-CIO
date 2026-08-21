#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATABASE_PATH
from database import replace_portfolio
from parser import parse_cas

args = argparse.ArgumentParser(description="Ingest a local MFCentral CAS into SQLite.")
args.add_argument("pdf", type=Path); args.add_argument("--database", type=Path, default=DATABASE_PATH)
ns = args.parse_args(); ns.database.parent.mkdir(exist_ok=True)
result = parse_cas(ns.pdf)
if not result.holdings:
    print("Ingestion stopped: " + "; ".join(result.warnings), file=sys.stderr); raise SystemExit(2)
replace_portfolio(ns.database, result)
print(f"Ingested {len(result.holdings)} holdings and {len(result.transactions)} transactions into {ns.database}.")
if result.warnings: print("Warnings: " + "; ".join(result.warnings))
