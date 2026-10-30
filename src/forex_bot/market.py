"""Quotes and market-state gate: no entry on a closed market or a stale quote.

Three times are kept apart:
- `quote_time_utc`  : time of the quote at IG (PRICE `TIMESTAMP`, UTC milliseconds);
- `received_at_utc` : local time at which the update carrying that quote was received;
- the connection state, tracked by `forex_bot.streaming.PriceTracker`.
Freshness is ALWAYS measured on the IG time, so a late delivery (reconnection
snapshot, delayed message) can never make an old quote look fresh.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from forex_bot.instruments import TRADEABLE, to_decimal

# Experimental parameter (ASSUMP-009), not an IG requirement: maximum age of a quote for an entry decision.
DEFAULT_MAX_QUOTE_AGE = timedelta(seconds=10)
# Tolerated clock difference for a time slightly in the future.
CLOCK_TOLERANCE = timedelta(seconds=2)


@dataclass(frozen=True)
class Quote:
    """Two-sided quote. `bid` = price at which we sell, `offer` = price at which we buy."""

    bid: Decimal
    offer: Decimal
    market_status: str | None  # normalised: TRADEABLE or the raw broker state
    quote_time_utc: datetime | None  # IG quote time, timezone-aware UTC; None if unknown
    delayed: bool | None = None  # PRICE `DELAY` flag; None = unknown (blocks)
    received_at_utc: datetime | None = None  # local receipt time
    source: str = "inconnue"

    @property
    def spread(self) -> Decimal:
        return self.offer - self.bid


def quote_from_market_details(details: dict[str, Any], received_at_utc: datetime | None = None) -> Quote | None:
    """Build a Quote from GET /markets/{epic} v3.

    v3 only gives `snapshot.updateTime` as a time of day without date nor
    documented timezone: it is NOT converted, the quote time stays unknown and
    any entry based on it is blocked.
    """
    snapshot = details.get("snapshot") or {}
    bid, offer = to_decimal(snapshot.get("bid")), to_decimal(snapshot.get("offer"))
    if bid is None or offer is None:
        return None
    return Quote(
        bid=bid,
        offer=offer,
        market_status=snapshot.get("marketStatus"),
        quote_time_utc=None,
        received_at_utc=received_at_utc,
        source="REST GET /markets/{epic} v3",
    )


def is_aware(moment: datetime) -> bool:
    return moment.tzinfo is not None and moment.utcoffset() is not None


def quote_blockers(quote: Quote, now_utc: datetime, max_age: timedelta = DEFAULT_MAX_QUOTE_AGE) -> list[str]:
    """Reasons that forbid any entry on this quote. Empty list = quote usable."""
    if not is_aware(now_utc):
        raise ValueError("now_utc doit être une date UTC avec fuseau.")
    blockers: list[str] = []
    if quote.market_status != TRADEABLE:
        blockers.append(f"marché non négociable ({quote.market_status})")
    if quote.bid <= 0 or quote.offer < quote.bid:
        blockers.append(f"cotation incohérente (bid={quote.bid}, offer={quote.offer})")
    if quote.delayed is None:
        blockers.append("indicateur de cotation différée inconnu")
    elif quote.delayed:
        blockers.append("cotation différée (DELAY=1)")
    if quote.quote_time_utc is None:
        blockers.append("horodatage de la cotation inconnu")
    elif not is_aware(quote.quote_time_utc):
        blockers.append("horodatage de la cotation sans fuseau")
    else:
        age = now_utc - quote.quote_time_utc
        if age > max_age:
            blockers.append(f"cotation périmée ({age.total_seconds():.0f} s > {max_age.total_seconds():.0f} s)")
        elif age < -CLOCK_TOLERANCE:
            blockers.append("horodatage de la cotation dans le futur")
        if quote.received_at_utc is not None and is_aware(quote.received_at_utc):
            if quote.quote_time_utc - quote.received_at_utc > CLOCK_TOLERANCE:
                blockers.append("horodatage IG postérieur à la réception locale (horloges désynchronisées)")
    return blockers
