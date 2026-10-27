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
- Lost updates (Lightstreamer `onItemLostUpdates`) block until an update with
  a strictly newer TIMESTAMP arrives.
- Only DLG_FLAG = DEAL is treated as tradeable (ASSUMP-012, not confirmed by IG).
- A missing or unknown DELAY value blocks the entry ("indicateur différé inconnu").
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from forex_bot.instruments import TRADEABLE, to_decimal
from forex_bot.market import DEFAULT_MAX_QUOTE_AGE, Quote, is_aware, quote_blockers

PRICE_ADAPTER = "Pricing"
PRICE_MODE = "MERGE"
PRICE_FIELDS = ("BIDPRICE1", "ASKPRICE1", "TIMESTAMP", "DLG_FLAG", "DELAY")
# Needed to build a quote. DELAY is requested but observed empty on the demo
# (2026-10-27): its absence does not hide the quote, it blocks it explicitly.
REQUIRED_PRICE_FIELDS = ("BIDPRICE1", "ASKPRICE1", "TIMESTAMP", "DLG_FLAG")
PRICE_SOURCE = "flux IG PRICE"
DEALABLE_FLAG = "DEAL"  # ASSUMP-012


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
    NOT_CONNECTED = "NOT_CONNECTED"


def parse_ig_timestamp(raw: str | None) -> datetime | None:
    """TIMESTAMP in UTC milliseconds since the epoch -> aware datetime; None if invalid."""
    if raw is None or not raw.strip().isdigit():
        return None
    millis = int(raw.strip())
    return datetime.fromtimestamp(millis // 1000, UTC) + timedelta(milliseconds=millis % 1000)


class PriceTracker:
    """Merged state of one PRICE item. Not thread-safe: callers serialise access."""

    def __init__(self) -> None:
        self.connection = ConnectionState.DISCONNECTED
        self._fields: dict[str, str | None] = {}
        self._newest_ig_time: datetime | None = None  # ordering floor, kept across reconnections
        self._ig_time_received_at: datetime | None = None
        self._lost_updates_at: datetime | None = None  # newest IG time when updates were lost
        self.accepted = 0
        self.dropped_out_of_order = 0
        self.dropped_malformed = 0

    def on_connection(self, state: ConnectionState) -> None:
        if state is not ConnectionState.CONNECTED:
            self._fields.clear()
            self._ig_time_received_at = None
        self.connection = state

    def on_lost_updates(self) -> None:
        self._lost_updates_at = self._newest_ig_time or datetime.min.replace(tzinfo=UTC)

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
            if self._newest_ig_time is not None and ig_time < self._newest_ig_time:
                self.dropped_out_of_order += 1
                return UpdateOutcome.OUT_OF_ORDER

        self._fields.update({k: v for k, v in changed.items() if k in PRICE_FIELDS})
        if ig_time is not None:
            if self._lost_updates_at is not None and ig_time > self._lost_updates_at:
                self._lost_updates_at = None
            self._newest_ig_time = ig_time
            self._ig_time_received_at = received_at_utc
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
        blockers = []
        if self._lost_updates_at is not None:
            blockers.append("mises à jour PRICE perdues, en attente d'une cotation plus récente")
        quote = self.quote()
        if quote is None:
            missing = ", ".join(self.missing_fields()) or "valeurs illisibles"
            return [*blockers, f"cotation PRICE incomplète ({missing})"]
        return blockers + quote_blockers(quote, now_utc, max_age)
