"""Offline S3 engine: breakout after a volatility squeeze (docs/strategies/S3_SQUEEZE.md). No order.

Built on the S1 engine, which it does not change: same chronology, tick replay, guaranteed stop,
gap scenarios (A = H0, B = H1), sizing and valuation of a position still open at the end of the
study (no fictitious close). Only the H4 decision is S3's: bands, compression, box frozen at its
recognition, one breakout per box, expansion, D1 context, structural stop, a single strategy
exit on the 20-H4 mean, and the first close back towards the box journaled without any exit.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, fields
from datetime import datetime
from decimal import Decimal
from typing import Any

from forex_bot.backtest.bar_state import BarState, bar_state
from forex_bot.backtest.engine import (
    BacktestResult,
    DecisionRecord,
    EntryAction,
    PositionAction,
    ResearchConfig,
    S1Backtest,
    _PendingExit,
)
from forex_bot.backtest.feed import Tick
from forex_bot.backtest.s1 import EntrySignal, S1Params, StateOf
from forex_bot.backtest.s2 import ContinuousWilderAtr
from forex_bot.backtest.s3 import (
    Bands,
    Box,
    ReturnEvent,
    S3Params,
    bands,
    h4_ordinals,
    nearest_rank,
    return_kind,
    window,
)
from forex_bot.history.bars import Gap
from forex_bot.history.calendar import MarketState, market_state
from forex_bot.risk import Side

INCOMPLETE = "DONNÉES_BOÎTE_INCOMPLÈTES"


@dataclass(frozen=True)
class Compression:
    width: Decimal | None  # W(t)
    threshold: Decimal | None  # Q(t)
    reference: int  # computable widths among the expected slots before t
    compressed: bool | None  # None: not computable


@dataclass
class S3Result(BacktestResult):
    s3_params: S3Params | None = None
    boxes: list[Box] = field(default_factory=list)
    returns: list[ReturnEvent] = field(default_factory=list)  # one per position at most


class S3Backtest(S1Backtest):
    """One S3 trajectory: one D1 setting (reference or H4 only), one gap scenario, one configuration."""

    def __init__(
        self,
        h4: Sequence[dict[str, Any]],
        d1: Sequence[dict[str, Any]],
        ticks: Iterable[Tick],
        gaps: Sequence[Gap],
        params: S3Params,
        config: ResearchConfig,
        *,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
    ) -> None:
        # The S1 parameters only carry the ATR period and the D1 channel: S1 rules are never evaluated.
        s1 = S1Params(atr_period=params.atr_period, d1_channel=params.d1_channel, use_d1_filter=params.use_d1_filter)
        super().__init__(h4, d1, ticks, gaps, s1, config, start_utc=start_utc, end_utc=end_utc)
        self.s3 = params
        self.atr = ContinuousWilderAtr(h4, params.atr_period)  # continuity of the expected H4 (S2 reading)
        self.ordinals = h4_ordinals(h4)
        self._bands: dict[int, Bands | None] = {}
        self._compression: dict[int, Compression] = {}
        self.box: Box | None = None
        self.boxes: list[Box] = []
        self._previous_end: datetime | None = None  # end of the last box: its candles are never reused
        self._box_of: dict[datetime, Box] = {}  # trade decision -> its box
        self.returns: dict[datetime, ReturnEvent] = {}

    # ------------------------------------------------------------------ public

    def run(self) -> S3Result:
        base = super().run()
        values = {f.name: getattr(base, f.name) for f in fields(base)}
        return S3Result(**values, s3_params=self.s3, boxes=self.boxes, returns=list(self.returns.values()))

    # ------------------------------------------------------------------ indicators

    def _state(self, i: int, instant: datetime) -> BarState:
        return bar_state(self.h4[i], instant, self.gaps, self.config.gap_threshold, self.config.documented_closures)

    def _consecutive(self, first: int, last: int) -> bool:
        return first >= 0 and self.ordinals[last] - self.ordinals[first] == last - first

    def bands_at(self, t: int) -> Bands | None:
        """Bands of the H4 closes t-n+1..t, known at the availability of t; None if not computable."""
        if t not in self._bands:
            n, instant = self.s3.bb_period, self.h4_available[t]
            first = t - n + 1
            ok = self._consecutive(first, t) and all(self._state(i, instant).usable for i in range(first, t + 1))
            closes = [self.h4[i]["bid_close"] for i in range(first, t + 1)] if ok else []
            self._bands[t] = bands(closes, self.s3.bb_width) if ok else None
        return self._bands[t]

    def compression_at(self, t: int) -> Compression:
        """W(t) against the nearest-rank percentile of the widths of the expected slots before t."""
        if t not in self._compression:
            current = self.bands_at(t)
            ordinal = self.ordinals[t]
            previous = window(self.ordinals, ordinal - self.s3.history, ordinal - 1)
            reference = [b.width for i in previous if (b := self.bands_at(i)) is not None]
            if current is None or len(reference) < self.s3.min_history:
                result = Compression(None if current is None else current.width, None, len(reference), None)
            else:
                threshold = nearest_rank(reference, self.s3.percentile)
                result = Compression(current.width, threshold, len(reference), current.width <= threshold)
            self._compression[t] = result
        return self._compression[t]

    # ------------------------------------------------------------------ decisions

    def _decide(self, t: int, decision: datetime) -> None:
        cache: dict[int, BarState] = {}

        def h4_state(i: int) -> BarState:
            if i not in cache:
                cache[i] = self._state(i, decision)
            return cache[i]

        context = bisect.bisect_right(self.d1_available, decision) - 1
        record = DecisionRecord(decision, self._known_s3(t, decision, h4_state, context), PositionAction.FLAT)
        self.decisions.append(record)
        if self.position is not None:
            self._exit(t, decision, h4_state, record)
        breakout = self._box_life(t, decision, h4_state, record)
        if breakout is not None:
            self._breakout(t, decision, h4_state, context, breakout, record)
            return
        if self.box is None:
            self._recognise(t, decision, h4_state, record)
        if record.entry_action is EntryAction.NOT_EVALUATED and self.position is None:
            record.entry_action = EntryAction.NO_SIGNAL
        if self.position is not None and record.entry_action is not EntryAction.NOT_COMPUTABLE:
            record.entry_action = EntryAction.NOT_EVALUATED  # one S3 position at a time

    def _not_computable(self, record: DecisionRecord, reason: str) -> None:
        record.entry_action = EntryAction.NOT_COMPUTABLE
        if reason not in record.reasons:  # the same data reason may already block the exit of this decision
            record.reasons.append(reason)

    def _box_life(
        self, t: int, decision: datetime, h4_state: StateOf, record: DecisionRecord
    ) -> tuple[Box, Side] | None:
        """Update of the active box at t (sheet §4.2): abandoned, expired, unchanged, or broken out."""
        box = self.box
        if box is None or t <= box.index:
            return None
        if not self._consecutive(t - 1, t) or not h4_state(t).usable:
            self._end_box(decision, f"{INCOMPLETE} (H4 absente ou inutilisable)", "BOÎTE_ABANDONNÉE")
            self._not_computable(record, f"boîte abandonnée : {INCOMPLETE}")
            return None
        close: Decimal = self.h4[t]["bid_close"]
        if close > box.high or close < box.low:
            side = Side.LONG if close > box.high else Side.SHORT
            self._end_box(decision, f"consommée par la cassure {side.value}", "CASSURE")
            return box, side
        if self.ordinals[t] - self.ordinals[box.index] >= self.s3.box_life:
            self._end_box(decision, f"expirée après {self.s3.box_life} H4", "BOÎTE_EXPIRÉE")
            record.reasons.append("boîte expirée sans cassure")
        else:
            record.reasons.append("clôture dans la boîte")
        return None

    def _end_box(self, decision: datetime, reason: str, kind: str) -> None:
        box = self.box
        if box is None:
            return
        box.end(decision, reason)
        self._log(decision, kind, reason)
        self.box, self._previous_end = None, decision

    def _recognise(self, t: int, decision: datetime, h4_state: StateOf, record: DecisionRecord) -> None:
        """A box from the last `compressed_run` H4, all compressed, frozen at F = this decision (sheet §4.1)."""
        if not h4_state(t).usable:
            self._not_computable(record, f"bougie de décision {h4_state(t).value}")
            return
        current = self.compression_at(t)
        if current.compressed is None:
            self._not_computable(record, "compression non calculable")
            return
        run = range(t - self.s3.compressed_run + 1, t + 1)
        if not current.compressed or not self._consecutive(run.start, t):
            record.reasons.append("pas de boîte : compression absente ou trop courte")
            return
        if any(self.compression_at(i).compressed is not True for i in run):
            record.reasons.append("pas de boîte : compression absente ou trop courte")
            return
        previous_end = self._previous_end
        if previous_end is not None and self.h4[run.start]["start_utc"] < previous_end:
            record.reasons.append("pas de boîte : bougies déjà utilisées par la boîte précédente")
            return
        if any(not h4_state(i).usable for i in run):
            self._not_computable(record, "bougie de la consolidation inutilisable")
            return
        atr = self.atr.at(t, h4_state)
        if atr is None:
            self._not_computable(record, "ATR indisponible à F")
            self._log(decision, "BOÎTE_REFUSÉE", "ATR indisponible à F")
            return
        candles = [self.h4[i] for i in run]
        high: Decimal = max(b["bid_high"] for b in candles)
        low: Decimal = min(b["bid_low"] for b in candles)
        if high - low > self.s3.max_height_atr * atr:
            reason = f"consolidation trop large : {high - low} > {self.s3.max_height_atr} x A ({atr:.5f})"
            self._log(decision, "BOÎTE_REFUSÉE", reason)
            record.reasons.append(reason)
            return
        box = Box(t, decision, high, low, max(b["ask_high"] for b in candles), atr)
        self.box = box
        self.boxes.append(box)
        self._log(decision, "BOÎTE", f"BH {high} BL {low} AH {box.ask_high} A {atr:.5f}")
        record.reasons.append("boîte reconnue et figée")

    def _breakout(
        self,
        t: int,
        decision: datetime,
        h4_state: StateOf,
        context: int,
        breakout: tuple[Box, Side],
        record: DecisionRecord,
    ) -> None:
        """Decision at the first close out of the box (sheet §4.3, §8): the box is already consumed."""
        box, side = breakout
        long = side is Side.LONG
        signal: dict[str, Any] = {"side": side.value, "box": box.describe(), "close": self.h4[t]["bid_close"]}
        record.signal = signal
        if h4_state(t) is not BarState.OK:
            self._not_computable(record, f"bougie de cassure {h4_state(t).value}")
            return
        now, before = self.bands_at(t), self.bands_at(t - 1)
        if now is None or before is None:
            self._not_computable(record, "bandes non calculables à la cassure")
            return
        trend, issue = self._d1_side(context, decision)
        if self.s3.use_d1_filter and issue is not None:
            self._not_computable(record, issue)
            return
        if self.position is not None:
            record.entry_action = EntryAction.NOT_EVALUATED
            record.reasons.append("cassure pendant une position ouverte : boîte consommée")
            return
        close: Decimal = self.h4[t]["bid_close"]
        signal |= {"upper": now.upper, "lower": now.lower, "width": now.width, "previous_width": before.width}
        outside = close > now.upper if long else close < now.lower
        if not (outside and now.width > before.width):
            self._refuse(record, decision, "pas d'expansion : clôture dans la bande ou largeur qui ne s'élargit pas")
            return
        if self.s3.use_d1_filter and trend is not side:
            word = "haussière" if long else "baissière"
            self._refuse(record, decision, f"cassure {word} contre le contexte D1")
            return
        if market_state(decision) is not MarketState.OPEN:
            self._refuse(record, decision, f"{side.value} : marché fermé à l'instant de décision")
            return
        margin = self.s3.stop_atr * box.atr
        stop = box.low - margin if long else box.ask_high + margin
        signal["stop"] = stop
        self._size(decision, EntrySignal(side, stop, box.atr, box.high, box.low), record)
        if record.entry_action is EntryAction.ENTRY_DECIDED:
            self._box_of[decision] = box

    def _refuse(self, record: DecisionRecord, decision: datetime, reason: str) -> None:
        self._log(decision, "ABSTENTION", reason)
        record.entry_action = EntryAction.SIGNAL_REFUSED
        record.reasons.append(reason)

    def _d1_side(self, context: int, decision: datetime) -> tuple[Side | None, str | None]:
        """D1 context of S1 (sheet S1 §3, §10.4): side, or the data reason why it is unknown."""
        n = self.s3.d1_channel
        if context < 0 or context + 1 < n:
            return None, "historique D1 insuffisant"

        def usable(i: int) -> bool:
            return bar_state(
                self.d1[i], decision, self.gaps, self.config.gap_threshold, self.config.documented_closures
            ).usable

        if not usable(context):
            return None, "D1 de contexte non utilisable"
        first = context - n + 1
        if any(not usable(i) for i in range(first, context + 1)):
            return None, "D1 non utilisable dans le canal de 55 jours (règle stricte)"
        days = self.d1[first : context + 1]
        middle = (max(b["bid_high"] for b in days) + min(b["bid_low"] for b in days)) / 2
        close: Decimal = self.d1[context]["bid_close"]
        return (Side.LONG if close > middle else Side.SHORT if close < middle else None), None

    def _exit(self, t: int, decision: datetime, h4_state: StateOf, record: DecisionRecord) -> None:
        """Single strategy exit on the 20-H4 mean; the first close back towards the box is only journaled."""
        position = self._open_position()
        box = self._box_of[position.decided_utc]
        if not h4_state(t).usable:
            self._held_not_computable(record, decision, f"bougie de décision {h4_state(t).value}")
            return
        close: Decimal = self.h4[t]["bid_close"]
        now = self.bands_at(t)
        exit_now = now is not None and (close < now.middle if position.side is Side.LONG else close > now.middle)
        kind = return_kind(position.side, close, box.low, box.high)
        if kind is not None and position.decided_utc not in self.returns:
            since = sum(1 for i in range(t + 1) if self.h4[i]["end_utc"] > position.entry_utc)
            event = ReturnEvent(
                position.decided_utc,
                kind,
                decision,
                since,
                close,
                box.low,
                box.high,
                None if now is None else now.middle,
                self._unrealized(self._last_tick),
                exit_now,
            )
            self.returns[position.decided_utc] = event
            detail = f"clôture {close}, boîte [{box.low} ; {box.high}], {since} H4 après l'exécution, sans sortie"
            self._log(decision, kind.value, detail)
            record.reasons.append(f"{kind.value} : {detail}")
        if now is None:
            self._held_not_computable(record, decision, "moyenne de 20 H4 non calculable")
            return
        if not exit_now:
            record.position_action = PositionAction.HELD
            return
        word = "sous" if position.side is Side.LONG else "au-dessus de"
        reason = f"clôture bid {close} {word} la moyenne {now.middle:.5f}"
        self.pending_exit = _PendingExit(decision, "SORTIE_SUIVEUSE")
        self._log(decision, "SORTIE_DÉCIDÉE", reason)
        record.position_action = PositionAction.EXIT_DECIDED
        record.reasons.append(reason)

    def _held_not_computable(self, record: DecisionRecord, decision: datetime, reason: str) -> None:
        self._log(decision, "SORTIE_NON_CALCULABLE", reason)
        record.position_action = PositionAction.HELD_EXIT_NOT_COMPUTABLE
        record.reasons.append(reason)

    def _known_s3(self, t: int, decision: datetime, h4_state: StateOf, context: int) -> dict[str, Any]:
        """What was known at D: the H4, bands, compression, box, D1 context, quote, account, position."""
        bar = self.h4[t]
        now = self.bands_at(t)
        compression = self.compression_at(t)
        last = self._last_tick
        point = self.curve[-1]
        position = self.position
        returned = None if position is None else self.returns.get(position.decided_utc)
        return {
            "h4": {
                "start_utc": bar["start_utc"],
                "end_utc": bar["end_utc"],
                "state": h4_state(t).value,
                **{k: bar[k] for k in ("bid_open", "bid_high", "bid_low", "bid_close", "ask_close")},
            },
            "bands": None
            if now is None
            else {"middle": now.middle, "upper": now.upper, "lower": now.lower, "width": now.width},
            "compression": {
                "threshold": compression.threshold,
                "reference_widths": compression.reference,
                "compressed": compression.compressed,
            },
            "box": None if self.box is None else self.box.describe(),
            "d1_context": None if context < 0 else {"start_utc": self.d1[context]["start_utc"]},
            "market": market_state(decision).value,
            "quote": None if last is None else {"ts_utc": last.ts_utc, "bid": last.bid, "ask": last.ask},
            "account": {"balance": point.balance, "unrealized": point.unrealized, "equity": point.equity},
            "position": None
            if position is None
            else {
                "side": position.side.value,
                "size": position.size,
                "entry_utc": position.entry_utc,
                "stop": position.stop,
                "return": None if returned is None else {"kind": returned.kind.value, "utc": returned.utc},
            },
        }
