"""S1 rules on candles available at a decision instant (docs/strategies/S1_DONCHIAN.md §3-§4, §10).

Parameters are the experimental initial configuration (ASSUMP-020, ADR-008); the data rules are
the experimental reference of ADR-006. Every refusal returns a reason, never a silent default.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from forex_bot.backtest.bar_state import BarState
from forex_bot.risk import Side

TWO = Decimal(2)


@dataclass(frozen=True)
class S1Params:
    entry_channel: int = 20  # N
    exit_channel: int = 10  # M
    atr_period: int = 14
    stop_atr_multiple: Decimal = Decimal(2)  # k
    d1_channel: int = 55  # D1 candles ending with the context candle (included)
    use_d1_filter: bool = True  # False: the no-filter variant, a distinct experiment

    def __post_init__(self) -> None:
        if not 0 < self.exit_channel < self.entry_channel:
            raise ValueError("canaux attendus : 0 < M < N")
        if self.atr_period < 1 or self.d1_channel < 1 or self.stop_atr_multiple <= 0:
            raise ValueError("paramètres S1 invalides")


StateOf = Callable[[int], BarState]  # state of a candle index, as known at the decision instant


def true_range(bar: dict[str, Any], previous_close: Decimal) -> Decimal:
    high: Decimal = bar["bid_high"]
    low: Decimal = bar["bid_low"]
    return max(high - low, abs(high - previous_close), abs(low - previous_close))


class WilderAtr:
    """Wilder ATR on bid candles with explicit availability (S1 sheet §10.3).

    TR(t) is valid only if candles t and t-1 are usable. After the last unusable candle d, the
    first valid TR is TR(d+2); the ATR becomes available at d+1+period (d+15 for 14), seeded by the
    simple mean of `period` valid TRs, then Wilder's recursion. Before that it is unavailable
    (None), never zero. Values are cached per anchor so that a run stays linear in time.
    """

    # Only the most recent candles can still change state (a gap that started inside them may
    # become known later); older ones are final once a later candle holds ticks. Re-check this many.
    RECHECK = 2

    def __init__(self, bars: Sequence[dict[str, Any]], period: int) -> None:
        self._bars = bars
        self._period = period
        self._anchor: int | None = None  # first candle of the usable run ending at the last call
        self._checked = -1  # candles anchor.._checked - RECHECK were usable at the last call
        self._last = -1  # last candle included in the cached value
        self._value: Decimal | None = None

    def _run_anchor(self, t: int, state_of: StateOf) -> int:
        """First candle of the usable run that ends at `t`."""
        cached = self._anchor is not None and self._checked <= t
        lower = self._checked - self.RECHECK if cached else -1
        i = t
        while i > lower and i >= 0:
            if not state_of(i).usable:
                return i + 1
            i -= 1
        # Candles (lower, t] are usable now; the cached run started at the cached anchor, whose
        # previous candle was unusable (a state never improves) or is before the history.
        if cached and lower >= 0 and self._anchor is not None:
            return self._anchor
        return 0

    def at(self, t: int, state_of: StateOf) -> Decimal | None:
        """ATR at the close of candle `t`, or None if unavailable."""
        anchor = self._run_anchor(t, state_of)
        if self._anchor != anchor:
            self._value, self._last = None, -1
        self._anchor, self._checked = anchor, t
        first_tr = anchor + 1  # TR needs the previous close, from the same usable run
        seed_end = first_tr + self._period - 1
        if t < seed_end:
            return None
        if self._value is None or self._last > t:
            trs = [true_range(self._bars[i], self._bars[i - 1]["bid_close"]) for i in range(first_tr, seed_end + 1)]
            self._last, self._value = seed_end, sum(trs, Decimal(0)) / self._period
        while self._last < t:
            self._last += 1
            tr = true_range(self._bars[self._last], self._bars[self._last - 1]["bid_close"])
            self._value = (self._value * (self._period - 1) + tr) / self._period
        return self._value


@dataclass(frozen=True)
class EntrySignal:
    side: Side
    stop: Decimal  # technical stop, fixed at the decision, never moved afterwards
    atr: Decimal
    channel_high: Decimal
    channel_low: Decimal


@dataclass(frozen=True)
class Refusal:
    reason: str


def _channel(bars: Sequence[dict[str, Any]], first: int, last: int) -> tuple[Decimal, Decimal]:
    window = bars[first : last + 1]
    return max(b["bid_high"] for b in window), min(b["bid_low"] for b in window)


def evaluate_entry(
    t: int,
    h4: Sequence[dict[str, Any]],
    h4_state: StateOf,
    atr: WilderAtr,
    d1: Sequence[dict[str, Any]],
    d1_context: int | None,
    d1_state: StateOf,
    params: S1Params,
) -> EntrySignal | Refusal | None:
    """Entry at the close of H4 candle `t`: a signal, a data refusal, or None (no breakout)."""
    n = params.entry_channel
    if h4_state(t) is not BarState.OK:
        return Refusal(f"bougie de signal {h4_state(t).value}")
    if t < n:
        return Refusal("historique H4 insuffisant pour le canal d'entrée")
    unusable = [i for i in range(t - n, t) if not h4_state(i).usable]
    if unusable:
        return Refusal(f"bougie H4 non utilisable dans les canaux ({h4[unusable[-1]]['start_utc'].isoformat()})")
    value = atr.at(t, h4_state)
    if value is None:
        return Refusal("ATR indisponible (réamorçage)")
    high, low = _channel(h4, t - n, t - 1)
    close = h4[t]["bid_close"]
    side = Side.LONG if close > high else Side.SHORT if close < low else None
    if side is None:
        return None
    if params.use_d1_filter:
        if d1_context is None or d1_context + 1 < params.d1_channel:
            return Refusal("historique D1 insuffisant")
        if not d1_state(d1_context).usable:
            return Refusal(f"D1 de contexte {d1_state(d1_context).value}")
        first = d1_context - params.d1_channel + 1
        if any(not d1_state(i).usable for i in range(first, d1_context + 1)):
            return Refusal("D1 non utilisable dans le canal de 55 jours (règle stricte)")
        d1_high, d1_low = _channel(d1, first, d1_context)
        middle = (d1_high + d1_low) / TWO
        context_close = d1[d1_context]["bid_close"]
        if side is Side.LONG and not context_close > middle:
            return Refusal("cassure haussière contre le contexte D1")
        if side is Side.SHORT and not context_close < middle:
            return Refusal("cassure baissière contre le contexte D1")
    distance = params.stop_atr_multiple * value
    stop = close - distance if side is Side.LONG else h4[t]["ask_close"] + distance
    return EntrySignal(side, stop, value, high, low)


def evaluate_exit(
    t: int, side: Side, h4: Sequence[dict[str, Any]], h4_state: StateOf, params: S1Params
) -> bool | Refusal:
    """Strategic channel exit at the close of `t`: True / False, or a Refusal if not computable."""
    m = params.exit_channel
    if h4_state(t) is not BarState.OK or t < m:
        return Refusal("sortie stratégique non calculable (bougie de décision)")
    if any(not h4_state(i).usable for i in range(t - m, t)):
        return Refusal("sortie stratégique non calculable (canal de sortie)")
    high, low = _channel(h4, t - m, t - 1)
    close: Decimal = h4[t]["bid_close"]
    return close < low if side is Side.LONG else close > high
