"""Legacy SQLite persistence. Runtime ingest/MCP/API use canonical Postgres."""
from __future__ import annotations
import sqlite3
from decimal import Decimal
from pathlib import Path
from parser import ParseResult

SCHEMA = '''
CREATE TABLE IF NOT EXISTS funds (id INTEGER PRIMARY KEY, amc TEXT NOT NULL, folio TEXT NOT NULL, scheme_name TEXT NOT NULL, isin TEXT, UNIQUE(amc, folio, scheme_name, isin));
CREATE TABLE IF NOT EXISTS holdings (id INTEGER PRIMARY KEY, fund_id INTEGER NOT NULL REFERENCES funds(id), opening_units TEXT, closing_units TEXT, nav TEXT, valuation TEXT, valuation_date TEXT, source_page INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY, fund_id INTEGER NOT NULL REFERENCES funds(id), date TEXT, transaction_type TEXT NOT NULL, description TEXT NOT NULL, amount TEXT, units TEXT, nav TEXT, unit_balance TEXT, source_page INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sources (page INTEGER PRIMARY KEY, text TEXT NOT NULL);
'''
def connect(path: str | Path):
    con = sqlite3.connect(path); con.row_factory = sqlite3.Row; con.executescript(SCHEMA); return con
def _d(value): return str(value) if value is not None else None
def _fund_id(con, record):
    con.execute("INSERT OR IGNORE INTO funds(amc,folio,scheme_name,isin) VALUES(?,?,?,?)", (record.amc,record.folio,record.scheme_name,record.isin))
    return con.execute("SELECT id FROM funds WHERE amc=? AND folio=? AND scheme_name=? AND isin IS ?", (record.amc,record.folio,record.scheme_name,record.isin)).fetchone()[0]
def replace_portfolio(path, result: ParseResult):
    con = connect(path)
    with con:
        for table in ("holdings", "transactions", "funds", "sources"): con.execute(f"DELETE FROM {table}")
        for page, text in result.pages.items(): con.execute("INSERT INTO sources(page,text) VALUES(?,?)", (page,text))
        for h in result.holdings:
            fid = _fund_id(con,h); con.execute("INSERT INTO holdings(fund_id,opening_units,closing_units,nav,valuation,valuation_date,source_page) VALUES(?,?,?,?,?,?,?)", (fid,_d(h.opening_units),_d(h.closing_units),_d(h.nav),_d(h.valuation),h.valuation_date,h.source_page))
        for t in result.transactions:
            fid = _fund_id(con,t); con.execute("INSERT INTO transactions(fund_id,date,transaction_type,description,amount,units,nav,unit_balance,source_page) VALUES(?,?,?,?,?,?,?,?,?)", (fid,t.date,t.transaction_type,t.description,_d(t.amount),_d(t.units),_d(t.nav),_d(t.unit_balance),t.source_page))
    return con
def _dec(v): return Decimal(v) if v is not None else Decimal("0")
def holdings(con):
    rows=con.execute("SELECT f.amc,f.folio,f.scheme_name,f.isin,h.closing_units,h.nav,h.valuation,h.valuation_date,h.source_page FROM holdings h JOIN funds f ON f.id=h.fund_id ORDER BY CAST(h.valuation AS REAL) DESC").fetchall()
    return [{**dict(r), **{k:_dec(r[k]) for k in ("closing_units","nav","valuation")}} for r in rows]
def transactions(con, start_date=None, end_date=None, fund=None, amc=None, transaction_type=None):
    sql="SELECT f.amc,f.folio,f.scheme_name,f.isin,t.date,t.transaction_type,t.description,t.amount,t.units,t.nav,t.unit_balance,t.source_page FROM transactions t JOIN funds f ON f.id=t.fund_id WHERE 1=1"; args=[]
    for condition, value in (("t.date >= ?",start_date),("t.date <= ?",end_date),("f.scheme_name LIKE ?", f"%{fund}%" if fund else None),("f.amc LIKE ?",f"%{amc}%" if amc else None),("t.transaction_type = ?",transaction_type)):
        if value: sql += " AND " + condition; args.append(value)
    rows=con.execute(sql+" ORDER BY t.date",args).fetchall()
    return [{**dict(r), **{k:(_dec(r[k]) if r[k] is not None else None) for k in ("amount","units","nav","unit_balance")}} for r in rows]
