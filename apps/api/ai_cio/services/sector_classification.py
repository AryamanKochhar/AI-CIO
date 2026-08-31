"""Security sector classification from authoritative NSE sector indices."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ai_cio.db.models import Security
from domain.market.providers.nse import NIFTY_SECTOR_INDICES, NSEProvider

logger = logging.getLogger(__name__)


def lookup_sector(db: Session, isin: str | None, symbol: str | None = None) -> dict | None:
    if isin:
        row = db.query(Security).filter(Security.isin == isin).first()
        if row and row.sector_name:
            return {
                "sector_index_code": row.sector_index_code,
                "sector_name": row.sector_name,
                "source": row.classification_source or "nse",
                "classified_at": row.classified_at.isoformat() if row.classified_at else None,
            }
    if symbol:
        row = db.query(Security).filter(Security.symbol == symbol).first()
        if row and row.sector_name:
            return {
                "sector_index_code": row.sector_index_code,
                "sector_name": row.sector_name,
                "source": row.classification_source or "nse",
                "classified_at": row.classified_at.isoformat() if row.classified_at else None,
            }
    return None


def sync_sector_constituents(db: Session, provider: NSEProvider | None = None) -> int:
    """Fetch NSE sector index constituents and upsert securities. Returns rows upserted."""
    nse = provider or NSEProvider()
    count = 0
    now = datetime.now(timezone.utc)
    try:
        for code, label in NIFTY_SECTOR_INDICES:
            try:
                constituents = nse.get_sector_constituents(code, label)
            except Exception as exc:
                logger.warning("sector_constituents_failed code=%s err=%s", code, exc)
                continue
            for c in constituents:
                row = None
                if c.isin:
                    row = db.query(Security).filter(Security.isin == c.isin).first()
                if not row and c.symbol:
                    row = db.query(Security).filter(Security.symbol == c.symbol).first()
                if not row:
                    row = Security(isin=c.isin, symbol=c.symbol, name=c.name)
                    db.add(row)
                row.symbol = c.symbol or row.symbol
                row.name = c.name or row.name
                row.isin = c.isin or row.isin
                row.sector_index_code = c.sector_index_code
                row.sector_name = c.sector_name
                row.classification_source = "nse_sector_index"
                row.classified_at = now
                count += 1
        db.flush()
        return count
    finally:
        nse.close()
