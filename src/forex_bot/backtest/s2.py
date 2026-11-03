"""S2 rules on candles available at a decision instant (docs/strategies/S2_PULLBACK.md §3-§4).

Trend resumption after a pullback towards an already known level. Parameters are the values
approved for offline research (ASSUMP-025, ADR-015). Structure is computed on the bid series.
Every pivot carries the instant it became known (availability of candle i + p), never earlier.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from forex_bot.backtest.bar_state import BarState
from forex_bot.backtest.s1 import WilderAtr
from forex_bot.history.calendar import Timeframe, expected_open_minutes
from forex_bot.risk import Side

StateOf = Callable[[int], BarState]  # state of a candle index, as known at the decision instant


class GapScenario(StrEnum):
    """Treatment of an open position across an unexplained quote gap (sheet §7)."""

    OBSERVED_ONLY = "A_OBSERVÉ_SEULEMENT"  # only the first quote after the gap counts
    STOP_FIRST = "B_STOP_D_ABORD"  # any possible stop crossing happened, before the target
    TARGET_FIRST = "C_CIBLE_D_ABORD"  # any possible target hit happened, before the stop, at level E


@dataclass(frozen=True)
class S2Params:
    pivot_d1: int = 2
    pivot_h4: int = 3
    pivot_h1: int = 2
    atr_period: int = 14  # Wilder, H4, fixed at the identification instant
    zone_atr: Decimal = Decimal("0.5")  # z: half width of the zone around K
    max_setup_h4: int = 30  # T_max: H4 candles after the candle of E
    stop_atr: Decimal = Decimal("0.25")  # b: stop margin beyond the pullback extreme
    min_reward_risk: Decimal = Decimal(1)  # R_min: net potential gain / estimated stop loss
    max_hold_h4: int = 60  # H_max: H4 candles starting after the execution
    trigger: Timeframe = Timeframe.H1  # reference; H4 is the pre-registered comparison

    def __post_init__(self) -> None:
        if min(self.pivot_d1, self.pivot_h4, self.pivot_h1, self.atr_period, self.max_setup_h4, self.max_hold_h4) < 1:
            raise ValueError("paramètres S2 invalides")
        if self.trigger not in (Timeframe.H1, Timeframe.H4):
            raise ValueError("déclenchement attendu : H1 (référence) ou H4 (comparaison)")

    def pivot_order(self, timeframe: Timeframe) -> int:
        return {Timeframe.H1: self.pivot_h1, Timeframe.H4: self.pivot_h4, Timeframe.D1: self.pivot_d1}[timeframe]


class ContinuousWilderAtr(WilderAtr):
    """Wilder ATR of S2: the same rules as S1 (sheet S1 §10.3), plus the continuity of the expected candles.

    After an expected candle that is absent (a hole in the quote calendar, not the weekly closure),
    the first candle present provides the new reference close; `period` valid true ranges are then
    needed before the ATR is available again. The S1 engine keeps its own `WilderAtr`, unchanged.
    """

    def __init__(self, bars: Sequence[dict[str, Any]], period: int) -> None:
        super().__init__(bars, period)
        self._holes = {
            i
            for i in range(1, len(bars))
            if bars[i]["start_utc"] > bars[i - 1]["end_utc"]
            and expected_open_minutes(bars[i - 1]["end_utc"], bars[i]["start_utc"]) > 0
        }

    def _run_anchor(self, t: int, state_of: StateOf) -> int:
        cached = self._anchor is not None and self._checked <= t
        lower = self._checked - self.RECHECK if cached else -1
        i = t
        while i > lower and i >= 0:
            if not state_of(i).usable:
                return i + 1
            if i in self._holes:
                return i  # candle i follows an absent one: its close is the new reference
            i -= 1
        if cached and lower >= 0 and self._anchor is not None:
            return self._anchor
        return 0


class PivotKind(StrEnum):
    HIGH = "SOMMET"
    LOW = "CREUX"


@dataclass(frozen=True)
class Pivot:
    kind: PivotKind
    index: int  # candle i
    start_utc: datetime
    end_utc: datetime
    level: Decimal  # bid_high of a HIGH, bid_low of a LOW
    confirmed_utc: datetime  # availability of candle i + p: the pivot is unknown before


def pivot_kinds(bars: Sequence[dict[str, Any]], i: int, p: int, state_of: StateOf) -> list[PivotKind]:
    """Strict pivots of candle `i` (ties: no pivot); candles i-p..i+p must be present and usable."""
    if i - p < 0 or i + p >= len(bars):
        return []
    window = range(i - p, i + p + 1)
    if any(not state_of(j).usable for j in window):
        return []
    if first_missing(bars[i - p : i + p + 1], bars[i - p]["start_utc"], bars[i + p]["end_utc"]) is not None:
        return []  # a candle of the expected schedule is absent: as unusable as a degraded one
    others = [j for j in window if j != i]
    kinds = []
    if all(bars[i]["bid_high"] > bars[j]["bid_high"] for j in others):
        kinds.append(PivotKind.HIGH)
    if all(bars[i]["bid_low"] < bars[j]["bid_low"] for j in others):
        kinds.append(PivotKind.LOW)
    return kinds


class PivotTracker:
    """Confirmed pivots of one timeframe, discovered as candles become available (forward only)."""

    def __init__(self, bars: Sequence[dict[str, Any]], available: Sequence[datetime], order: int) -> None:
        self.bars, self.available, self.order = bars, available, order
        self.pivots: list[Pivot] = []
        self._next = 0  # first candle not yet available at the last update

    def update(self, decision: datetime, state_of: StateOf) -> list[Pivot]:
        """Pivots confirmed by the candles that became available at or before `decision`."""
        found = []
        while self._next < len(self.bars) and self.available[self._next] <= decision:
            confirming = self._next
            i = confirming - self.order
            for kind in pivot_kinds(self.bars, i, self.order, state_of) if i >= 0 else []:
                bar = self.bars[i]
                level = bar["bid_high"] if kind is PivotKind.HIGH else bar["bid_low"]
                found.append(Pivot(kind, i, bar["start_utc"], bar["end_utc"], level, self.available[confirming]))
            self._next += 1
        self.pivots.extend(found)
        return found

    def of(self, kind: PivotKind) -> list[Pivot]:
        return [p for p in self.pivots if p.kind is kind]


def d1_trend(highs: Sequence[Pivot], lows: Sequence[Pivot], context: dict[str, Any] | None) -> Side | None:
    """Up: two rising highs and two rising lows, context close above the last low (down: mirror)."""
    if context is None or len(highs) < 2 or len(lows) < 2:
        return None
    close: Decimal = context["bid_close"]
    if highs[-1].level > highs[-2].level and lows[-1].level > lows[-2].level and close > lows[-1].level:
        return Side.LONG
    if highs[-1].level < highs[-2].level and lows[-1].level < lows[-2].level and close < highs[-1].level:
        return Side.SHORT
    return None


def overlaps(bar: dict[str, Any], lower: Decimal, upper: Decimal) -> bool:
    """Contact measured on the candle extremes: its bid range meets the zone (no proof of a quote in it)."""
    return bool(bar["bid_low"] <= upper and bar["bid_high"] >= lower)


def first_missing(bars: Sequence[dict[str, Any]], since: datetime, until: datetime) -> datetime | None:
    """Start of the first expected-open stretch in [since, until) not covered by `bars` (contiguous list)."""
    cursor = since
    for bar in bars:
        if bar["start_utc"] > cursor and expected_open_minutes(cursor, bar["start_utc"]) > 0:
            return cursor
        cursor = max(cursor, bar["end_utc"])
    if until > cursor and expected_open_minutes(cursor, until) > 0:
        return cursor
    return None


@dataclass
class Setup:
    """A configuration: identified at I, alive until used, abandoned, replaced or expired."""

    side: Side
    extreme: Pivot  # E
    known_level: Pivot  # K
    identified_utc: datetime  # I
    atr: Decimal  # A, fixed at I
    lower: Decimal  # K - z A
    upper: Decimal  # K + z A
    contact: int | None = None  # index of the contact candle in the trigger timeframe
    refused_utc: datetime | None = None  # last breakout without entry: later pivots must start at or after it
    used: bool = False
    history: list[str] = field(default_factory=list)

    @property
    def target(self) -> Decimal:
        return self.extreme.level

    def describe(self) -> dict[str, Any]:
        return {
            "side": self.side.value,
            "E": self.extreme.level,
            "E_start_utc": self.extreme.start_utc,
            "K": self.known_level.level,
            "identified_utc": self.identified_utc,
            "atr": self.atr,
            "zone": [self.lower, self.upper],
            "contact": self.contact,
            "refused_utc": self.refused_utc,
        }
