"""S3 rules on H4 candles (docs/strategies/S3_SQUEEZE.md §3-§5): breakout after a volatility squeeze.

Parameters are the reference values approved for offline research (ASSUMP-026, ADR-017, ADR-018).
Bands and structure are computed on the bid series. Every value is computed from candles available
at its own decision instant, never later.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from forex_bot.history.calendar import MarketState, Timeframe, candle_start, market_state
from forex_bot.risk import Side

ONE_HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class S3Params:
    bb_period: int = 20  # H4 closes of the Bollinger bands
    bb_width: Decimal = Decimal(2)  # population standard deviations
    history: int = 360  # expected H4 slots before t whose widths form the reference
    min_history: int = 240  # computable widths required in the reference
    percentile: Decimal = Decimal("0.20")  # nearest-rank threshold of the reference
    compressed_run: int = 6  # consecutive compressed H4 that make a box
    max_height_atr: Decimal = Decimal(3)  # box height <= 3 x A
    atr_period: int = 14  # Wilder, H4, continuity of the expected candles, fixed at F
    box_life: int = 30  # expected H4 slots after F
    stop_atr: Decimal = Decimal("0.25")  # b: stop margin beyond the opposite bound
    d1_channel: int = 55  # D1 context of S1: middle of the 55-day channel
    use_d1_filter: bool = True  # False: the pre-registered H4-only comparison

    def __post_init__(self) -> None:
        if min(self.bb_period, self.compressed_run, self.atr_period, self.box_life, self.d1_channel) < 1:
            raise ValueError("paramètres S3 invalides")
        if not 0 < self.min_history <= self.history:
            raise ValueError("historique de compression attendu : 0 < minimum <= fenêtre")
        if not 0 < self.percentile < 1 or self.bb_width <= 0 or self.max_height_atr <= 0 or self.stop_atr < 0:
            raise ValueError("paramètres S3 invalides")


@dataclass(frozen=True)
class Bands:
    middle: Decimal  # M: mean of the closes
    upper: Decimal  # U = M + k sigma
    lower: Decimal  # B = M - k sigma
    width: Decimal  # W = (U - B) / M


def bands(closes: Sequence[Decimal], width: Decimal) -> Bands:
    """Bollinger bands of `closes` with the population standard deviation (division by n)."""
    n = Decimal(len(closes))
    middle = sum(closes, Decimal(0)) / n
    sigma = (sum(((c - middle) ** 2 for c in closes), Decimal(0)) / n).sqrt()
    upper, lower = middle + width * sigma, middle - width * sigma
    return Bands(middle, upper, lower, (upper - lower) / middle)


def nearest_rank(values: Sequence[Decimal], fraction: Decimal) -> Decimal:
    """The ceil(fraction x n)-th smallest value (nearest-rank percentile)."""
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def h4_ordinals(bars: Sequence[dict[str, Any]]) -> list[int]:
    """Position of each H4 candle in the expected schedule (open H4 slots and candles present).

    Two candles are consecutive when their ordinals differ by one: an expected slot without a
    candle breaks the continuity, the weekly closure and the probable holidays do not.
    """
    if not bars:
        return []
    present = {b["start_utc"] for b in bars}
    slots: set[datetime] = set(present)
    hour = bars[0]["start_utc"]
    while hour < bars[-1]["end_utc"]:
        if candle_start(hour, Timeframe.H4) == hour and market_state(hour) is MarketState.OPEN:
            slots.add(hour)
        hour += ONE_HOUR
    ordered = sorted(slots)
    rank = {start: i for i, start in enumerate(ordered)}
    return [rank[b["start_utc"]] for b in bars]


def window(ordinals: Sequence[int], first: int, last: int) -> range:
    """Indices of the candles whose ordinal is in [first, last] (ordinals increase with the index)."""
    return range(bisect.bisect_left(ordinals, first), bisect.bisect_right(ordinals, last))


class ReturnKind(StrEnum):
    """First close back towards the box after the execution (sheet §5): observed, never an exit by itself."""

    REINTEGRATION = "RÉINTÉGRATION"  # bid close inside the box, bounds included
    CROSSING = "TRAVERSÉE"  # bid close straight beyond the opposite bound


def return_kind(side: Side, close: Decimal, low: Decimal, high: Decimal) -> ReturnKind | None:
    """Kind of a bid close relative to the box, for a position of `side`; None if still beyond the breakout bound."""
    if side is Side.LONG:
        if close > high:
            return None
        return ReturnKind.REINTEGRATION if close >= low else ReturnKind.CROSSING
    if close < low:
        return None
    return ReturnKind.REINTEGRATION if close <= high else ReturnKind.CROSSING


@dataclass
class Box:
    """A consolidation recognised and frozen at F; one breakout at most."""

    index: int  # H4 candle whose availability is F
    formed_utc: datetime  # F
    high: Decimal  # BH, bid
    low: Decimal  # BL, bid
    ask_high: Decimal  # AH, for the stop of a sale
    atr: Decimal  # A at F
    ended_utc: datetime | None = None
    end_reason: str | None = None
    history: list[str] = field(default_factory=list)

    def end(self, utc: datetime, reason: str) -> None:
        self.ended_utc, self.end_reason = utc, reason
        self.history.append(f"{utc.isoformat()} {reason}")

    def describe(self) -> dict[str, Any]:
        return {
            "F": self.formed_utc,
            "BH": self.high,
            "BL": self.low,
            "AH": self.ask_high,
            "A": self.atr,
            "ended_utc": self.ended_utc,
            "end_reason": self.end_reason,
        }


@dataclass(frozen=True)
class ReturnEvent:
    """The first close back towards the box of an open position (logged once per position)."""

    decided_utc: datetime  # the trade's decision, its identifier
    kind: ReturnKind
    utc: datetime  # availability of the H4 that closed back
    h4_since_entry: int  # H4 candles ending after the execution, this one included
    close: Decimal
    box_low: Decimal
    box_high: Decimal
    middle: Decimal | None  # M at that close, None if not computable
    unrealized: Decimal  # EUR, liquidation value at the last tick before the decision
    exit_decided: bool  # the same close also triggered the trailing exit
