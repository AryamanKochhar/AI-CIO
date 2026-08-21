"""CAS Financial Intelligence MCP server (stdio)."""
from decimal import Decimal
from config import DATABASE_PATH, KNOWLEDGE_DIR
from database import connect, holdings, transactions
from analysis import allocation, concentration_metrics, sip_summary, top_holdings, total_value
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("CAS Financial Intelligence")
def ready():
    if not DATABASE_PATH.exists(): raise RuntimeError("No local portfolio database. Run: python scripts/ingest.py data/cas.pdf")
    return connect(DATABASE_PATH)
def serialise(value):
    if isinstance(value, Decimal): return f"{value:.2f}"
    if isinstance(value, list): return [serialise(x) for x in value]
    if isinstance(value, dict): return {k:serialise(v) for k,v in value.items()}
    return value
@mcp.tool()
def get_holdings() -> list[dict]:
    """Return parsed current holdings with CAS source pages."""
    return serialise(holdings(ready()))
@mcp.tool()
def get_portfolio_summary() -> dict:
    """Return deterministic valuation, allocations, rankings, and concentration measurements."""
    hs=holdings(ready()); amcs=allocation(hs,"amc"); ranked=top_holdings(hs,5)
    return serialise({"total_portfolio_value":total_value(hs),"number_of_funds":len(hs),"amc_allocation":amcs,"fund_allocation":top_holdings(hs,len(hs)),"largest_holding":ranked[:1],"largest_amc_exposure":amcs[:1],"top_3_holdings":ranked[:3],"top_5_holdings":ranked,"concentration_metrics":concentration_metrics(hs)})
@mcp.tool()
def get_transactions(start_date: str|None=None,end_date: str|None=None,fund: str|None=None,amc: str|None=None,transaction_type: str|None=None) -> list[dict]:
    """Filter transactions; dates use the CAS date format stored by the parser."""
    return serialise(transactions(ready(),start_date,end_date,fund,amc,transaction_type))
@mcp.tool()
def get_sips() -> dict:
    """Return SIP activity; failed payments are separated and never included in purchases."""
    rows=transactions(ready()); relevant=[x for x in rows if x["transaction_type"] in {"SIP_PURCHASE","FAILED_PAYMENT","SIP_CANCELLED","SIP_REGISTERED"}]
    return serialise({"activity":relevant,"summary":sip_summary(rows)})
@mcp.tool()
def search_knowledge(query: str) -> list[dict]:
    """Keyword search of local educational Markdown. Not personalised financial advice."""
    terms={x.lower() for x in query.split() if len(x)>2}; results=[]
    for path in KNOWLEDGE_DIR.glob("*.md"):
        text=path.read_text(); lines=[line for line in text.splitlines() if terms & set(line.lower().split())]
        if lines: results.append({"document":path.name,"matches":lines[:8]})
    return results
@mcp.tool()
def get_source(page: int) -> dict:
    """Return traceability information for a one-based CAS page; raw source is intentionally not exposed."""
    con=ready(); rows=con.execute("SELECT f.amc,f.folio,f.scheme_name,h.valuation,h.source_page FROM holdings h JOIN funds f ON f.id=h.fund_id WHERE h.source_page=?",(page,)).fetchall()
    return serialise({"source_document":"cas.pdf","page":page,"holdings":[dict(r) for r in rows]})
if __name__ == "__main__": mcp.run()
