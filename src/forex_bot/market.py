"""Quotes and market-state gate: no entry on a closed market or a stale quote."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from forex_bot.instruments import TRADEABLE, to_decimal

# Proposal (ASSUMP-009): maximum age of a quote used for an entry decision.
DEFAULT_MAX_QUOTE_AGE = timedelta(seconds=10)
# Tolerated clock difference for a quote time slightly in the future.
CLOCK_TOLERANCE = timedelta(seconds=2)


@dataclass(frozen=True)
class Quote:
    """Two-sided quote. `bid` = price at which we sell, `offer` = price at which we buy."""

    bid: Decimal
    offer: Decimal
    market_status: str | None
    quote_time_utc: datetime | None  # broker quote time, timezone-aware UTC; None if unknown

    @property
    def spread(self) -> Decimal:
        return self.offer - self.bid


def quote_from_market_details(details: dict[str, Any]) -> Quote | None:
    """Build a Quote from GET /markets/{epic} v3.

    v3 only gives `snapshot.updateTime` as a time of day without date nor
    documented timezone: it is NOT converted, the quote time stays unknown and
    any entry based on it is blocked.
    """
    snapshot = details.get("snapshot") or {}
    bid, offer = to_decimal(snapshot.get("bid")), to_decimal(snapshot.get("offer"))
    if bid is None or offer is None:
        return None
    return Quote(bid=bid, offer=offer, market_status=snapshot.get("marketStatus"), quote_time_utc=None)


def quote_blockers(quote: Quote, now_utc: datetime, max_age: timedelta = DEFAULT_MAX_QUOTE_AGE) -> list[str]:
    """Reasons that forbid any entry on this quote. Empty list = quote usable."""
    if now_utc.tzinfo is None:
        raise ValueError("now_utc doit être une date UTC avec fuseau.")
    blockers: list[str] = []
    if quote.market_status != TRADEABLE:
        blockers.append(f"marché non négociable ({quote.market_status})")
    if quote.bid <= 0 or quote.offer < quote.bid:
        blockers.append(f"cotation incohérente (bid={quote.bid}, offer={quote.offer})")
    if quote.quote_time_utc is None:
        blockers.append("horodatage de la cotation inconnu")
    elif quote.quote_time_utc.tzinfo is None:
        blockers.append("horodatage de la cotation sans fuseau")
    else:
        age = now_utc - quote.quote_time_utc
        if age > max_age:
            blockers.append(f"cotation périmée ({age.total_seconds():.0f} s > {max_age.total_seconds():.0f} s)")
        elif age < -CLOCK_TOLERANCE:
            blockers.append("horodatage de la cotation dans le futur")
    return blockers
