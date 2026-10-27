"""State of the IG `PRICE` stream for one epic (pure logic, no network).

Source: IG Labs Streaming API reference, `PRICE:{account identifier}:{epic}`,
mode MERGE, data adapter `Pricing`. Fields used:
- BIDPRICE1 / ASKPRICE1 : top tier of the ladder (bid / ask);
- TIMESTAMP             : "Update time in UTC milliseconds";
- DLG_FLAG              : dealing status (CLOSED, CALL, DEAL, EDIT, CLOSINGSONLY, DEALNOEDIT,
                          AUCTION, AUCTIONNOEDIT, SUSPEND);
- DELAY                 : delayed price flag (0 = false, 1 = true).
The legacy `MARKET:{epic}` subscription (end of life announced by IG) is not used.

Rules
-----
- Three facts are kept apart: IG quote time (TIMESTAMP), local receipt time and
  connection state. Freshness is measured on the IG time only.
- MERGE updates may be partial: fields are merged; a quote is produced only
  when every field is known.
- An update whose TIMESTAMP is older than the newest one already accepted is
  dropped (out of order). The newest TIMESTAMP survives reconnections, so a
  reconnection snapshot can never bring back an older quote nor make one
  look fresh.
- On disconnection or stall the merged fields are cleared: values received
  before and after a gap are never combined.
- Lost updates (Lightstreamer `onItemLostUpdates`) make the merged state
  unreliable: it is cleared and the entry stays blocked until a complete
  resynchronisation, i.e. every required field received again after the loss
  with a TIMESTAMP strictly newer than the last one before the loss. A
  TIMESTAMP alone, or a partial update, is not enough (in MERGE mode unchanged
  fields are not resent: a new subscription snapshot is usually needed).
  Resynchronisation only restores the consistency of the stream: the quote is
  then evaluated like any other and stays blocked by any remaining condition
  (e.g. DELAY absent, stale TIMESTAMP, DLG_FLAG other than DEAL).
- TIMESTAMP must be ASCII digits within a plausible range (not before
  2000-01-01, not ahead of the local receipt time by more than the clock
  tolerance); otherwise the update is dropped, so an aberrant value can never
  become the ordering floor. These bounds are project parameters, not IG
  requirements.
- Only DLG_FLAG = DEAL is treated as tradeable (ASSUMP-012, not confirmed by IG).
- A missing or unknown DELAY value blocks the entry ("indicateur différé inconnu").
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from forex_bot.instruments import TRADEABLE, to_decimal
from forex_bot.market import CLOCK_TOLERANCE, DEFAULT_MAX_QUOTE_AGE, Quote, is_aware, quote_blockers

PRICE_ADAPTER = "Pricing"
PRICE_MODE = "MERGE"
PRICE_FIELDS = ("BIDPRICE1", "ASKPRICE1", "TIMESTAMP", "DLG_FLAG", "DELAY")
# Needed to build a quote. DELAY is requested but observed empty on the demo
# (2026-10-27): its absence does not hide the quote, it blocks it explicitly.
REQUIRED_PRICE_FIELDS = ("BIDPRICE1", "ASKPRICE1", "TIMESTAMP", "DLG_FLAG")
PRICE_SOURCE = "flux IG PRICE"
DEALABLE_FLAG = "DEAL"  # ASSUMP-012
# Project parameter (not an IG requirement): older TIMESTAMP values are treated as aberrant.
EARLIEST_PLAUSIBLE_TIMESTAMP = datetime(2000, 1, 1, tzinfo=UTC)
_ASCII_DIGITS = re.compile(r"[0-9]{1,20}")


def price_item(account_id: str, epic: str) -> str:
    return f"PRICE:{account_id}:{epic}"


class ConnectionState(StrEnum):
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    STALLED = "STALLED"
    DISCONNECTED = "DISCONNECTED"


def connection_state_from_lightstreamer(status: str) -> ConnectionState:
    """Map a Lightstreamer client status ("CONNECTED:WS-STREAMING", "STALLED", ...)."""
    if status.startswith("CONNECTED:") and not status.endswith("SENSING"):
        return ConnectionState.CONNECTED
    if status == "STALLED":
        return ConnectionState.STALLED
    if status.startswith("CONNECTING") or status.endswith("SENSING"):
        return ConnectionState.CONNECTING
    return ConnectionState.DISCONNECTED


class UpdateOutcome(StrEnum):
    ACCEPTED = "ACCEPTED"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    MALFORMED = "MALFORMED"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    NOT_CONNECTED = "NOT_CONNECTED"


def parse_ig_timestamp(raw: str | None) -> datetime | None:
    """TIMESTAMP in UTC milliseconds since the epoch -> aware datetime; None if not representable."""
    if raw is None or not _ASCII_DIGITS.fullmatch(raw.strip()):
        return None
    millis = int(raw.strip())
    try:
        return datetime.fromtimestamp(millis // 1000, UTC) + timedelta(milliseconds=millis % 1000)
    except (OverflowError, OSError, ValueError):
        return None


class PriceTracker:
    """Merged state of one PRICE item. Not thread-safe: callers serialise access."""

    def __init__(self) -> None:
        self.connection = ConnectionState.DISCONNECTED
        self._fields: dict[str, str | None] = {}
        self._newest_ig_time: datetime | None = None  # ordering floor, kept across reconnections
        self._ig_time_received_at: datetime | None = None
        self._resync_after: datetime | None = None  # set on lost updates: newest IG time before the loss
        self.accepted = 0
        self.dropped_out_of_order = 0
        self.dropped_malformed = 0
        self.dropped_out_of_range = 0

    def on_connection(self, state: ConnectionState) -> None:
        if state is not ConnectionState.CONNECTED:
            self._fields.clear()
            self._ig_time_received_at = None
        self.connection = state

    def on_lost_updates(self) -> None:
        """Merged values may be stale: forget them and require a complete resynchronisation."""
        self._resync_after = self._newest_ig_time or EARLIEST_PLAUSIBLE_TIMESTAMP
        self._fields.clear()
        self._ig_time_received_at = None

    def on_update(self, changed: Mapping[str, str | None], received_at_utc: datetime) -> UpdateOutcome:
        """Apply the CHANGED fields of one update (Lightstreamer `getChangedFields()`)."""
        if not is_aware(received_at_utc):
            raise ValueError("received_at_utc doit être une date UTC avec fuseau.")
        if self.connection is not ConnectionState.CONNECTED:
            return UpdateOutcome.NOT_CONNECTED
        for name in ("BIDPRICE1", "ASKPRICE1"):
            if name in changed and changed[name] is not None and to_decimal(changed[name]) is None:
                self.dropped_malformed += 1
                return UpdateOutcome.MALFORMED
        ig_time: datetime | None = None
        if "TIMESTAMP" in changed:
            ig_time = parse_ig_timestamp(changed["TIMESTAMP"])
            if ig_time is None:
                self.dropped_malformed += 1
                return UpdateOutcome.MALFORMED
            if ig_time < EARLIEST_PLAUSIBLE_TIMESTAMP or ig_time - received_at_utc > CLOCK_TOLERANCE:
                self.dropped_out_of_range += 1
                return UpdateOutcome.OUT_OF_RANGE
            if self._newest_ig_time is not None and ig_time < self._newest_ig_time:
                self.dropped_out_of_order += 1
                return UpdateOutcome.OUT_OF_ORDER

        self._fields.update({k: v for k, v in changed.items() if k in PRICE_FIELDS})
        if ig_time is not None:
            self._newest_ig_time = ig_time
            self._ig_time_received_at = received_at_utc
        if (
            self._resync_after is not None
            and not self.missing_fields()
            and self._newest_ig_time is not None
            and self._newest_ig_time > self._resync_after
        ):
            self._resync_after = None
        self.accepted += 1
        return UpdateOutcome.ACCEPTED

    def missing_fields(self) -> list[str]:
        return [name for name in REQUIRED_PRICE_FIELDS if self._fields.get(name) in (None, "")]

    @property
    def dealing_flag(self) -> str | None:
        flag = self._fields.get("DLG_FLAG")
        return flag.strip() if flag is not None else None

    def quote(self) -> Quote | None:
        """Current quote, or None while the merged state is incomplete."""
        if self.missing_fields():
            return None
        bid, offer = to_decimal(self._fields["BIDPRICE1"]), to_decimal(self._fields["ASKPRICE1"])
        ig_time = parse_ig_timestamp(self._fields["TIMESTAMP"])
        if bid is None or offer is None or ig_time is None:
            return None
        flag = (self._fields["DLG_FLAG"] or "").strip()  # observed padded with spaces on the demo
        delay = self._fields.get("DELAY")
        return Quote(
            bid=Decimal(bid),
            offer=Decimal(offer),
            market_status=TRADEABLE if flag == DEALABLE_FLAG else f"DLG_FLAG={flag}",
            quote_time_utc=ig_time,
            delayed={"0": False, "1": True}.get(delay or ""),
            received_at_utc=self._ig_time_received_at,
            source=PRICE_SOURCE,
        )

    def blockers(self, now_utc: datetime, max_age: timedelta = DEFAULT_MAX_QUOTE_AGE) -> list[str]:
        """Reasons forbidding an entry on the streamed quote. Empty list = usable."""
        if self.connection is not ConnectionState.CONNECTED:
            return [f"flux PRICE non connecté ({self.connection})"]
        if self._resync_after is not None:
            return ["mises à jour PRICE perdues : resynchronisation complète requise"]
        quote = self.quote()
        if quote is None:
            missing = ", ".join(self.missing_fields()) or "valeurs illisibles"
            return [f"cotation PRICE incomplète ({missing})"]
        return quote_blockers(quote, now_utc, max_age)
