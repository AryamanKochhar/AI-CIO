"""Narrow PPFAS published-plan comparison, separate from calculated TRI history.

This adapter reads the official monthly digital factsheet's *Fund Performance*
section. It never uses its nearby SIP or rolling-return table as trailing
performance, never creates a daily benchmark series, and never invents a
Growth/IDCW designation that the plan-level performance table does not state.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urlparse

import httpx

SCHEMES = {
    "INF879O01027": {"panel": "mySidepanelPPFCF", "scheme_code": 122639, "title": "Parag Parikh Flexi Cap Fund", "plan": "direct", "option": "growth"},
    "INF879O01100": {"panel": "mySidepanelPPTSF", "scheme_code": 147481, "title": "Parag Parikh ELSS Tax Saver Fund", "plan": "direct", "option": "growth"},
}
VERSION = "ppfas-published-plan-comparison-v1"
MAX_HTML_BYTES = 2_000_000
MONTHS = {name.lower():i for i,name in enumerate(("January","February","March","April","May","June","July","August","September","October","November","December"),1)}


def _text(value):
    return re.sub(r"\s+", " ", unescape(str(value))).strip()


class _Tables(HTMLParser):
    """Keep table boundaries and the preceding button heading, not DOM guesses."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables=[]; self.heading=""; self.button=None; self.rows=None; self.row=None; self.cell=None; self.depth=0; self.title=None; self.in_title=False; self.all_text=[]

    def handle_starttag(self,tag,attrs):
        if tag=="button": self.button=[]
        if tag=="h2" and self.title is None: self.in_title=True; self.title=[]
        if tag=="table":
            self.depth+=1
            if self.depth==1:self.rows=[]
        if self.depth==1:
            if tag=="tr": self.row=[]
            elif tag in {"td","th"}:self.cell=[]
            elif tag=="br" and self.cell is not None:self.cell.append(" ")

    def handle_data(self,data):
        self.all_text.append(data)
        if self.button is not None:self.button.append(data)
        if self.in_title:self.title.append(data)
        if self.depth==1 and self.cell is not None:self.cell.append(data)

    def handle_endtag(self,tag):
        if tag=="button" and self.button is not None:self.heading=_text(" ".join(self.button));self.button=None
        if tag=="h2":self.in_title=False
        if self.depth==1:
            if tag in {"td","th"} and self.cell is not None:
                if self.row is not None:self.row.append(_text(" ".join(self.cell)))
                self.cell=None
            elif tag=="tr" and self.row is not None:
                if self.rows is not None and self.row:self.rows.append(self.row)
                self.row=None
            elif tag=="table" and self.rows is not None:self.tables.append((self.heading,self.rows));self.rows=None
        if tag=="table":self.depth=max(0,self.depth-1)


def _percent(value):
    text=_text(value).replace("\u2212","-")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?\s*%",text):
        raise ValueError("Published return must be an explicit finite percentage")
    try:value=Decimal(text.replace("%","").strip())
    except InvalidOperation as exc:raise ValueError("Invalid published return") from exc
    if not value.is_finite() or value < -100 or value > 1000:
        raise ValueError("Published percentage is outside the adapter bounds")
    return value


def _source_month(source_url):
    url=urlparse(source_url)
    match=re.fullmatch(r"/downloads/digital-factsheet/(\d{4})/([a-z]+)-(\d{4})/",url.path)
    if url.scheme!="https" or url.hostname!="amc.ppfas.com" or url.port is not None or url.username or url.password or url.query or url.fragment or not match:
        raise ValueError("Published performance requires the configured official PPFAS monthly URL")
    year,month,repeat=match.groups()
    if year!=repeat or month not in MONTHS:
        raise ValueError("Published month/year URL is invalid")
    return int(year),MONTHS[month]


def parse_ppfas_published_performance(html: str|bytes, identity: dict, *, source_url: str, as_of: date) -> dict:
    spec=SCHEMES.get(str(identity.get("isin") or ""))
    if spec is None or identity.get("identity_status")!="verified":
        raise ValueError("No tested published-performance adapter for this verified scheme ISIN")
    if str(identity.get("plan") or "").lower()!=spec["plan"] or str(identity.get("option") or "").lower()!=spec["option"] or str(identity.get("scheme_code"))!=str(spec["scheme_code"]):
        raise ValueError("Scheme ISIN, plan, option and code do not agree")
    year,month=_source_month(source_url)
    raw=html if isinstance(html,bytes) else html.encode("utf-8")
    if len(raw)>MAX_HTML_BYTES:raise ValueError("Published factsheet exceeds adapter size bound")
    text=raw.decode("utf-8-sig")
    panels=list(re.finditer(r'<div\b[^>]*\bid=[\"\'](mySidepanel[A-Za-z0-9]+)[\"\'][^>]*>',text,re.I))
    selected=[(i,m) for i,m in enumerate(panels) if m.group(1)==spec["panel"]]
    if len(selected)!=1:raise ValueError("Expected a unique official scheme panel")
    i,match=selected[0]; panel=text[match.start():panels[i+1].start() if i+1<len(panels) else len(text)]
    parser=_Tables();parser.feed(panel)
    title=_text(" ".join(parser.title or []))
    if title.lower()!=spec["title"].lower():raise ValueError("Scheme panel title does not match the configured ISIN")
    flat=_text(" ".join(parser.all_text))
    dates=re.findall(r"NAV as on ([A-Za-z]+ \d{1,2}, \d{4})",flat,re.I)
    if len(set(dates))!=1:raise ValueError("Factsheet must state one unambiguous scheme NAV observation date")
    try:observed=datetime.strptime(dates[0],"%B %d, %Y").date()
    except (IndexError,ValueError) as exc:raise ValueError("Unusable published observation date") from exc
    if (observed.year,observed.month)!=(year,month) or observed>as_of:
        raise ValueError("Published date is future-dated or differs from its monthly URL")
    # The tested schema labels the scheme benchmark separately from the numeric
    # table, whose final heading says only 'Benchmark Returns'. Bind both.
    benchmark_names=[row[1] for _,rows in parser.tables for row in rows if len(row)==2 and row[0].lower()=="benchmark name:"]
    if len(benchmark_names)!=1 or re.sub(r"[^a-z0-9]","",benchmark_names[0].lower())!="nifty500tri":
        raise ValueError("Published comparison does not establish the tested NIFTY 500 TRI benchmark")
    tables=[rows for heading,rows in parser.tables if heading.lower()=="fund performance"]
    if len(tables)!=1 or not tables[0] or len(tables[0][0])!=4:
        raise ValueError("Fund Performance table is missing, ambiguous or has changed schema")
    header=[cell.lower() for cell in tables[0][0]]
    if not ("annualised" in header[0] or "annualized" in header[0]) or not ("regular" in header[1] and "scheme" in header[1]) or not ("direct" in header[2] and "scheme" in header[2]) or "benchmark" not in header[3]:
        raise ValueError("Published plan/benchmark columns do not match the tested table schema")
    returns=[];seen=set()
    for row in tables[0][1:]:
        if not row:continue
        label=re.fullmatch(r"(1|3|5) years?",row[0].lower())
        if not label:continue
        if len(row)!=4:raise ValueError("Published performance row has unexpected columns")
        years=int(label.group(1)); period=f"{years}y"
        if period in seen:raise ValueError("Duplicate published performance period")
        seen.add(period);fund_return,benchmark_return=_percent(row[2]),_percent(row[3])
        # These are published trailing labels. The AMC does not give the exact
        # starting market date in this table, so do not invent one by subtraction.
        returns.append({"period":period,"window_years":years,"start_date":None,"end_date":observed.isoformat(),
                        "fund_return_pct":float(fund_return),"benchmark_return_pct":float(benchmark_return),
                        "excess_return_pp":float(fund_return-benchmark_return),"annualized":True,
                        "return_basis":"AMC published compounded annualised plan return",
                        "basis":"amc_published_reported","calculation":"excess_return_pp = published fund return minus published benchmark return"})
    if seen!={"1y","3y","5y"}:raise ValueError("Published comparison requires all tested 1/3/5-year rows")
    return {"available":True,"status":"reported_comparison_only","adapter":VERSION,"scheme_code":spec["scheme_code"],
            "scheme_name":title,"isin":identity["isin"],"plan":spec["plan"],"requested_option":spec["option"],
            "option_basis":"not_stated_in_published_table","option_verified":False,"observed_on":observed.isoformat(),
            "source_url":source_url,"source_id":f"mf_ppfas_published_{spec['scheme_code']}_{observed.isoformat()}",
            "sha256":hashlib.sha256(raw).hexdigest(),"basis":"amc_published_reported",
            "benchmark":{"id":"NIFTY500TRI","name":benchmark_names[0],"kind":"TRI","source_url":source_url},
            "returns":returns,"rolling":None,"benchmark_history":[],
            "stale":(as_of-observed).days>62,
            "limitations":["AMC-reported plan comparison, not returns recomputed from an independently obtained benchmark series.",
                            "The published plan table does not explicitly identify Growth/IDCW; requested holding option is known but this table's option basis remains unconfirmed.",
                            "Exact starting market dates are not stated; 1/3/5-year period labels are preserved without inventing dates.",
                            "Published trailing windows do not supply rolling consistency, tracking error or a benchmark chart.",
                            "62-day stale flag is application review policy, not an AMC publication guarantee."]}


def fetch_ppfas_published_performance(provider, identity: dict, *, as_of: date) -> dict|None:
    """At most three fixed official monthly URLs; use the shared bounded cache."""
    spec=SCHEMES.get(str(identity.get("isin") or ""))
    if spec is None or identity.get("identity_status")!="verified":return None
    if str(identity.get("plan") or "").lower()!=spec["plan"] or str(identity.get("option") or "").lower()!=spec["option"] or str(identity.get("scheme_code"))!=str(spec["scheme_code"]):return None
    month_end=as_of.replace(day=1)-timedelta(days=1)
    for _ in range(3):
        month_name=next(name for name,value in MONTHS.items() if value==month_end.month)
        url=f"https://amc.ppfas.com/downloads/digital-factsheet/{month_end.year}/{month_name}-{month_end.year}/"
        try:
            record=provider.cache.get(f"ppfas:published:{month_end.year}:{month_end.month}:v1",86400,
                                      lambda:provider._get(url,json_response=False).decode("utf-8-sig"),max_stale=7*86400)
            result=parse_ppfas_published_performance(record["payload"],identity,source_url=url,as_of=as_of)
            result.update({"retrieved_at":record["retrieved_at"],"cache_status":record["cache_status"],
                           "cache_stale":bool(record.get("stale"))})
            return result
        except (ValueError,OSError,RuntimeError,httpx.HTTPError):
            pass
        month_end=month_end.replace(day=1)-timedelta(days=1)
    return None
