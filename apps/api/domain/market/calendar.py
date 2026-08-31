"""Indian market calendar abstraction — minimal MVP with extension point."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# NSE holidays 2026 (extend via config/DB later). Weekends handled separately.
NSE_HOLIDAYS_2026: frozenset[date] = frozenset(
    {
        date(2026, 1, 26),
        date(2026, 3, 3),
        date(2026, 3, 26),
        date(2026, 4, 3),
        date(2026, 4, 14),
        date(2026, 5, 1),
        date(2026, 8, 15),
        date(2026, 10, 2),
        date(2026, 10, 20),
        date(2026, 11, 5),
        date(2026, 11, 24),
        date(2026, 12, 25),
    }
)

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def is_trading_day(day: date | None = None) -> bool:
    d = day or datetime.now(IST).date()
    if d.weekday() >= 5:
        return False
    return d not in NSE_HOLIDAYS_2026


def is_market_hours(now: datetime | None = None) -> bool:
    dt = now.astimezone(IST) if now else datetime.now(IST)
    if not is_trading_day(dt.date()):
        return False
    t = dt.time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


def should_poll_market(now: datetime | None = None) -> bool:
    """Poll during market hours on trading days; allow one fetch after close for EOD."""
    dt = now.astimezone(IST) if now else datetime.now(IST)
    if not is_trading_day(dt.date()):
        return False
    t = dt.time()
    return MARKET_OPEN <= t <= time(16, 0)
