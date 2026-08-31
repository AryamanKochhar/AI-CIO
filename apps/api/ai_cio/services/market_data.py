"""Market data fetch, persistence, and cache."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from ai_cio.db.models import MarketIndex, MarketIndexSnapshot
from ai_cio.settings import MARKET_CACHE_TTL_SECONDS, MARKET_POLL_INTERVAL_SECONDS
from domain.market.calendar import should_poll_market
from domain.market.contracts import MarketIndexSnapshot as SnapshotContract
from domain.market.providers.base import MarketDataProvider
from domain.market.providers.nse import NSEProvider

logger = logging.getLogger(__name__)

_last_fetch_at: datetime | None = None
_cached_snapshots: list[SnapshotContract] | None = None


def get_provider() -> MarketDataProvider:
    return NSEProvider()


def _upsert_index(db: Session, snap: SnapshotContract) -> MarketIndex:
    row = (
        db.query(MarketIndex)
        .filter(MarketIndex.provider == snap.provider, MarketIndex.symbol == snap.index_code)
        .first()
    )
    if not row:
        row = MarketIndex(
            provider=snap.provider,
            symbol=snap.index_code,
            name=snap.index_name,
            category=snap.category,
        )
        db.add(row)
        db.flush()
    else:
        row.name = snap.index_name
        row.category = snap.category
        row.updated_at = datetime.now(timezone.utc)
    return row


def _persist_snapshot(db: Session, index: MarketIndex, snap: SnapshotContract) -> MarketIndexSnapshot:
    ts = snap.timestamp if snap.timestamp.tzinfo else snap.timestamp.replace(tzinfo=timezone.utc)
    existing = (
        db.query(MarketIndexSnapshot)
        .filter(MarketIndexSnapshot.index_id == index.id, MarketIndexSnapshot.timestamp == ts)
        .first()
    )
    if existing:
        return existing
    row = MarketIndexSnapshot(
        index_id=index.id,
        timestamp=ts,
        current_value=snap.current_value,
        close_value=snap.previous_close,
        open_value=None,
        high_value=snap.day_high,
        low_value=snap.day_low,
        percentage_change=snap.change_percent,
        year_high=snap.year_high,
        year_low=snap.year_low,
        source=snap.source,
        fetched_at=datetime.now(timezone.utc),
        is_stale=snap.is_stale,
    )
    db.add(row)
    return row


def _latest_db_snapshots(db: Session) -> list[SnapshotContract]:
    rows = (
        db.query(MarketIndexSnapshot, MarketIndex)
        .join(MarketIndex, MarketIndex.id == MarketIndexSnapshot.index_id)
        .order_by(MarketIndexSnapshot.fetched_at.desc())
        .all()
    )
    seen: set[int] = set()
    out: list[SnapshotContract] = []
    for snap, idx in rows:
        if idx.id in seen:
            continue
        seen.add(idx.id)
        out.append(
            SnapshotContract(
                provider=idx.provider,
                index_code=idx.symbol,
                index_name=idx.name,
                category=idx.category,
                timestamp=snap.timestamp,
                current_value=Decimal(str(snap.current_value)) if snap.current_value is not None else None,
                previous_close=Decimal(str(snap.close_value)) if snap.close_value is not None else None,
                change=None,
                change_percent=Decimal(str(snap.percentage_change)) if snap.percentage_change is not None else None,
                day_high=Decimal(str(snap.high_value)) if snap.high_value is not None else None,
                day_low=Decimal(str(snap.low_value)) if snap.low_value is not None else None,
                year_high=Decimal(str(snap.year_high)) if snap.year_high is not None else None,
                year_low=Decimal(str(snap.year_low)) if snap.year_low is not None else None,
                source=snap.source,
                is_stale=snap.is_stale,
            )
        )
    return out


def _with_stale(snap: SnapshotContract) -> SnapshotContract:
    return SnapshotContract(
        provider=snap.provider,
        index_code=snap.index_code,
        index_name=snap.index_name,
        category=snap.category,
        timestamp=snap.timestamp,
        current_value=snap.current_value,
        previous_close=snap.previous_close,
        change=snap.change,
        change_percent=snap.change_percent,
        day_high=snap.day_high,
        day_low=snap.day_low,
        year_high=snap.year_high,
        year_low=snap.year_low,
        source=snap.source,
        is_stale=True,
    )


def fetch_and_persist(db: Session, *, force: bool = False) -> list[SnapshotContract]:
    """Fetch from NSE, persist snapshots, return normalized list."""
    global _last_fetch_at, _cached_snapshots
    now = datetime.now(timezone.utc)
    if (
        not force
        and _last_fetch_at
        and _cached_snapshots
        and (now - _last_fetch_at).total_seconds() < MARKET_CACHE_TTL_SECONDS
    ):
        return _cached_snapshots

    if not force and not should_poll_market(now):
        stale = _latest_db_snapshots(db)
        if stale:
            return [_with_stale(s) for s in stale]

    provider = get_provider()
    try:
        broad = provider.get_broad_market_indices()
        sectors = provider.get_sectoral_indices()
        all_snaps = broad + sectors
        for snap in all_snaps:
            idx = _upsert_index(db, snap)
            _persist_snapshot(db, idx, snap)
        db.flush()
        _last_fetch_at = now
        _cached_snapshots = all_snaps
        logger.info("market_fetch success indices=%s", len(all_snaps))
        return all_snaps
    except Exception as exc:
        logger.warning("market_fetch failed: %s", exc)
        stale = _latest_db_snapshots(db)
        if not stale:
            raise
        return [_with_stale(s) for s in stale]
    finally:
        if isinstance(provider, NSEProvider):
            provider.close()


def get_market_snapshots(db: Session, *, force: bool = False) -> list[SnapshotContract]:
    try:
        return fetch_and_persist(db, force=force)
    except Exception:
        return _latest_db_snapshots(db)


def freshness_label(snaps: list[SnapshotContract]) -> str:
    if not snaps:
        return "unavailable"
    if any(s.is_stale for s in snaps):
        return "stale"
    if _last_fetch_at and (datetime.now(timezone.utc) - _last_fetch_at) < timedelta(seconds=MARKET_POLL_INTERVAL_SECONDS):
        return "live"
    return "recent"
