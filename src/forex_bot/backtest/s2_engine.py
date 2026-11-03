"""Offline S2 backtest engine (docs/strategies/S2_PULLBACK.md), built on the verified S1 engine.

Reused unchanged from `S1Backtest`: forward-only tick replay, execution at the first tick strictly
after the decision (buy at the ask, sell at the bid), state read strictly before D, sizing on the
up-to-date equity, costs and conversion, guaranteed stop with its premium, `StopAtExecution`,
equity curve and tick-level drawdown. S1 itself is not modified.

Specific to S2: decisions at each candle of the trigger timeframe (H1 reference, H4 comparison);
confirmed pivots on D1, H4 and H1; the configuration lifecycle; a target exit at the first
executable quote that reaches it (bid for a long, ask for a short); a time exit; quote gaps under
scenario A (observed only), B (stop first) or C (target first, at level E), each one trajectory.

Research only: no order is ever sent and nothing here talks to a broker.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
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
    StopType,
    Trade,
)
from forex_bot.backtest.feed import Silence, Tick, classify_silence
from forex_bot.backtest.s1 import EntrySignal, S1Params
from forex_bot.backtest.s2 import (
    ContinuousWilderAtr,
    GapScenario,
    Pivot,
    PivotKind,
    PivotTracker,
    S2Params,
    Setup,
    StateOf,
    d1_trend,
    first_missing,
    overlaps,
)
from forex_bot.history.bars import Gap
from forex_bot.history.calendar import (
    ONE_HOUR,
    MarketState,
    Timeframe,
    candle_end,
    candle_start,
    floor_hour,
    market_state,
)
from forex_bot.risk import Side

TIME_EXIT = "SORTIE_TEMPORELLE"
REVIEW_DRAWDOWN = Decimal("0.06")  # review threshold of the cahier des charges §8 (sheet §9)


@dataclass
class RelativeDrawdown:
    """True maximum of (peak - equity) / peak at the tick, and the first crossing of the review threshold.

    Research run: the crossing is reported and the trajectory goes on (in operation it would block new
    entries until a review; not simulated). Falls during quote gaps stay unknown.
    """

    peak_eur: Decimal
    max_ratio: Decimal = Decimal(0)
    max_utc: datetime | None = None
    first_review_crossing: dict[str, Any] | None = None

    def observe(self, utc: datetime, equity: Decimal, open_trade: str | None) -> None:
        self.peak_eur = max(self.peak_eur, equity)
        ratio = (self.peak_eur - equity) / self.peak_eur
        if ratio > self.max_ratio:
            self.max_ratio, self.max_utc = ratio, utc
        if ratio >= REVIEW_DRAWDOWN and self.first_review_crossing is None:
            self.first_review_crossing = {
                "utc": utc,
                "peak_eur": self.peak_eur,
                "equity_eur": equity,
                "ratio": ratio,
                "open_trade_decided_utc": open_trade,
            }


@dataclass
class S2Result(BacktestResult):
    s2_params: S2Params = field(default_factory=S2Params)
    scenario: GapScenario = GapScenario.OBSERVED_ONLY
    setups: list[Setup] = field(default_factory=list)  # every configuration identified, in order
    relative_drawdown: RelativeDrawdown | None = None


class S2Backtest(S1Backtest):
    """One S2 trajectory: one trigger timeframe, one gap scenario, one research configuration."""

    def __init__(
        self,
        h1: Sequence[dict[str, Any]],
        h4: Sequence[dict[str, Any]],
        d1: Sequence[dict[str, Any]],
        ticks: Iterable[Tick],
        gaps: Sequence[Gap],
        params: S2Params,
        config: ResearchConfig,
        *,
        scenario: GapScenario = GapScenario.OBSERVED_ONLY,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
    ) -> None:
        # The S1 parameters only carry the ATR period: S1 rules are never evaluated here.
        atr_only = S1Params(atr_period=params.atr_period)
        super().__init__(h4, d1, ticks, gaps, atr_only, config, start_utc=start_utc, end_utc=end_utc)
        self.h1, self.s2, self.scenario = h1, params, scenario
        # S2 reads the ATR with the continuity of the expected H4 (the S1 engine keeps its own, unchanged).
        self.atr = ContinuousWilderAtr(h4, params.atr_period)
        self._notes: list[tuple[str, bool]] = []  # (reason, missing data) raised during the current decision
        self.h1_available = [b["end_utc"] + config.latency for b in h1]
        if self.h1_available != sorted(self.h1_available):
            raise ValueError("bougies attendues dans l'ordre chronologique")
        self.bars = {Timeframe.H1: h1, Timeframe.H4: h4, Timeframe.D1: d1}
        self.available = {
            Timeframe.H1: self.h1_available,
            Timeframe.H4: self.h4_available,
            Timeframe.D1: self.d1_available,
        }
        self.starts = {tf: [b["start_utc"] for b in bars] for tf, bars in self.bars.items()}
        self.pivots = {
            tf: PivotTracker(self.bars[tf], self.available[tf], params.pivot_order(tf))
            for tf in (Timeframe.H1, Timeframe.H4, Timeframe.D1)
        }
        self.setup: Setup | None = None
        self.setups: list[Setup] = []  # every configuration identified, for the report
        self.relative = RelativeDrawdown(config.initial_equity)
        self.target: Decimal | None = None  # of the open position
        self._due: tuple[Trade, datetime] | None = None  # time-exit instant of the open position
        self._pending_target: Decimal | None = None

    # ------------------------------------------------------------------ public

    def run(self) -> S2Result:
        trigger = self.s2.trigger
        decided: datetime | None = None
        for t, decision in enumerate(self.available[trigger]):
            if not self._in_window(decision):
                continue
            self._advance(decision, inclusive=False)  # state strictly before D
            self._sample(decision, self._last_tick)
            self._decide_s2(t, decision)
            decided = decision
        if self.end_utc is not None:
            end: datetime | None = self.end_utc
            self._advance(self.end_utc, inclusive=False)
        else:
            self._advance(None, inclusive=True)
            instants = [m for m in (decided, self._last_tick.ts_utc if self._last_tick else None) if m is not None]
            end = max(instants, default=None)
        if end is not None:
            self._sample(end, self._last_tick)
        return S2Result(
            self.config,
            self.params,
            self.trades,
            self.journal,
            self.curve,
            self.position,
            end,
            self.decisions,
            self.drawdown,
            s2_params=self.s2,
            scenario=self.scenario,
            setups=self.setups,
            relative_drawdown=self.relative,
        )

    # ------------------------------------------------------------------ decisions

    def _states(self, decision: datetime) -> dict[Timeframe, StateOf]:
        caches: dict[Timeframe, dict[int, BarState]] = {tf: {} for tf in self.bars}

        def state_of(tf: Timeframe) -> StateOf:
            def state(i: int) -> BarState:
                if i not in caches[tf]:
                    caches[tf][i] = bar_state(
                        self.bars[tf][i],
                        decision,
                        self.gaps,
                        self.config.gap_threshold,
                        self.config.documented_closures,
                    )
                return caches[tf][i]

            return state

        return {tf: state_of(tf) for tf in self.bars}

    def _last_available(self, tf: Timeframe, decision: datetime) -> int:
        return bisect.bisect_right(self.available[tf], decision) - 1

    def _trend(self, decision: datetime, d1_state: StateOf) -> tuple[Side | None, str | None]:
        """D1 trend at `decision`, or the data reason why it is unknown."""
        context = self._last_available(Timeframe.D1, decision)
        if context < 0 or not d1_state(context).usable:
            return None, "D1 de contexte absente ou non utilisable"
        tracker = self.pivots[Timeframe.D1]
        return d1_trend(tracker.of(PivotKind.HIGH), tracker.of(PivotKind.LOW), self.d1[context]), None

    def _decide_s2(self, t: int, decision: datetime) -> None:
        states = self._states(decision)
        new_pivots = {
            tf: self.pivots[tf].update(decision, states[tf]) for tf in (Timeframe.H1, Timeframe.H4, Timeframe.D1)
        }
        self._notes = []
        trend, trend_issue = self._trend(decision, states[Timeframe.D1])
        if trend_issue is not None:
            self._notes.append((trend_issue, True))
        record = DecisionRecord(decision, self._known_s2(t, decision, states, trend), PositionAction.FLAT)
        self.decisions.append(record)

        if self.position is not None:
            record.position_action = PositionAction.HELD
            due = self._time_exit_due()
            if decision >= due:  # the exit itself is driven by the ticks, not by this decision
                record.reasons.append(f"échéance de sortie temporelle {due.isoformat()} atteinte")

        self._identify(new_pivots[Timeframe.H4], decision, states, trend)
        self._check_alive(decision, states)
        setup = self.setup
        record.reasons.extend(reason for reason, _ in self._notes)
        if setup is None:
            missing_data = any(data for _, data in self._notes)
            if not self._notes:
                record.reasons.append("pas de tendance D1" if trend is None else "pas de configuration")
            self._no_entry(record, EntryAction.NOT_COMPUTABLE if missing_data else EntryAction.NO_SIGNAL, None)
            return
        self._update_contact(setup, decision)
        trigger = self.s2.trigger
        threshold = self._threshold(setup, t)
        bar = self.bars[trigger][t]
        if setup.contact is None or threshold is None:
            self._no_entry(
                record,
                EntryAction.NO_SIGNAL,
                "pas de contact depuis I" if setup.contact is None else "pas de seuil de reprise connu",
            )
            return
        long = setup.side is Side.LONG
        broken = bar["bid_close"] > threshold.level if long else bar["bid_close"] < threshold.level
        if not broken:
            self._no_entry(record, EntryAction.NO_SIGNAL, "clôture en deçà du seuil")
            return
        # The first close beyond the threshold consumes it, whatever happens to the entry.
        setup.refused_utc = decision
        record.signal = {
            "side": setup.side.value,
            "threshold": threshold.level,
            "threshold_confirmed_utc": threshold.confirmed_utc,
        }
        if self.position is not None:
            record.entry_action = EntryAction.NOT_EVALUATED
            record.reasons.append("cassure pendant une position ouverte : seuil consommé")
            return
        if states[trigger](t) is not BarState.OK:
            self._refuse(record, decision, f"bougie de cassure {states[trigger](t).value}")
            return
        if trend is not setup.side:
            self._refuse(record, decision, "tendance D1 perdue à la cassure")
            return
        stop = self._stop(setup, decision)
        record.signal.update({"stop": stop, "target": setup.target})
        ratio = self._reward_risk(setup.side, stop, setup.target)
        if isinstance(ratio, str):
            self._refuse(record, decision, ratio)
            return
        record.signal["reward_risk"] = ratio
        if ratio < self.s2.min_reward_risk:
            self._refuse(record, decision, f"cible trop proche : rapport {ratio:.2f} < {self.s2.min_reward_risk}")
            return
        if market_state(decision) is not MarketState.OPEN:
            self._refuse(record, decision, f"{setup.side.value} : marché fermé à l'instant de décision")
            return
        signal = EntrySignal(setup.side, stop, setup.atr, setup.extreme.level, setup.known_level.level)
        self._size(decision, signal, record)
        if record.entry_action is EntryAction.ENTRY_DECIDED:
            setup.used = True
            self._pending_target = setup.target
            setup.history.append(f"{decision.isoformat()} entrée décidée")
            self.setup = None

    def _no_entry(self, record: DecisionRecord, action: EntryAction, reason: str | None) -> None:
        record.entry_action = EntryAction.NOT_EVALUATED if self.position is not None else action
        if reason is not None:
            record.reasons.append(reason)

    def _refuse(self, record: DecisionRecord, decision: datetime, reason: str) -> None:
        self._log(decision, "ABSTENTION", reason)
        record.entry_action = EntryAction.SIGNAL_REFUSED
        record.reasons.append(reason)

    def _time_exit_due(self) -> datetime:
        """Availability of the H_max-th H4 of the quote calendar starting after the execution tick.

        Counted on the expected schedule, not on the candles present: a missing candle never
        lengthens the holding. Computed once per position.
        """
        position = self._open_position()
        if self._due is not None and self._due[0] is position:
            return self._due[1]
        count, hour = 0, floor_hour(position.entry_utc) + ONE_HOUR
        while True:
            if candle_start(hour, Timeframe.H4) == hour and market_state(hour) is not MarketState.WEEKLY_CLOSURE:
                count += 1
                if count == self.s2.max_hold_h4:
                    due = candle_end(hour, Timeframe.H4) + self.config.latency
                    self._due = (position, due)
                    return due
            hour += ONE_HOUR

    # ------------------------------------------------------------------ configuration

    def _identify(
        self, new_h4: list[Pivot], decision: datetime, states: dict[Timeframe, StateOf], trend: Side | None
    ) -> None:
        """A configuration from an H4 extreme confirmed exactly at `decision` (sheet §4.2)."""
        for pivot in new_h4:
            if pivot.confirmed_utc != decision or trend is None:
                continue
            side = Side.LONG if pivot.kind is PivotKind.HIGH else Side.SHORT
            if side is not trend:
                continue
            current = self.setup
            if current is not None and not current.used:
                beyond = (
                    pivot.level > current.extreme.level if side is Side.LONG else pivot.level < current.extreme.level
                )
                if current.side is not side or not beyond:
                    continue  # a pivot of the pullback: the configuration is unchanged
                self._abandon(decision, "remplacée par un nouvel extrême au-delà de E")
            self._create(pivot, side, decision, states)

    def _create(self, extreme: Pivot, side: Side, decision: datetime, states: dict[Timeframe, StateOf]) -> None:
        long = side is Side.LONG
        candidates = [
            p
            for p in self.pivots[Timeframe.H4].of(extreme.kind)
            if p.index < extreme.index and (p.level < extreme.level if long else p.level > extreme.level)
        ]
        if not candidates:
            reason = f"configuration refusée, {side.value} : aucun niveau connu K pour E {extreme.level}"
            self._log(decision, "CONFIGURATION_REFUSÉE", reason)
            self._notes.append((reason, False))
            return
        known = max(candidates, key=lambda p: p.index)
        atr = self.atr.at(self._last_available(Timeframe.H4, decision), states[Timeframe.H4])
        if atr is None:
            reason = f"configuration refusée, {side.value} : ATR H4 indisponible à I"
            self._log(decision, "CONFIGURATION_REFUSÉE", reason)
            self._notes.append((reason, True))
            return
        half = self.s2.zone_atr * atr
        setup = Setup(side, extreme, known, decision, atr, known.level - half, known.level + half)
        self.setup = setup
        self.setups.append(setup)
        self._log(
            decision,
            "CONFIGURATION",
            f"{side.value} E {extreme.level} K {known.level} A {atr:.5f} zone [{setup.lower:.5f} ; {setup.upper:.5f}]",
        )
        self._check_alive(decision, states)

    def _abandon(self, decision: datetime, reason: str, *, missing_data: bool = False) -> None:
        if self.setup is not None:
            self.setup.history.append(f"{decision.isoformat()} abandonnée : {reason}")
            self._log(decision, "CONFIGURATION_ABANDONNÉE", reason)
            self._notes.append((f"configuration abandonnée : {reason}", missing_data))
        self.setup = None

    def _pullback(self, tf: Timeframe, setup: Setup, decision: datetime) -> list[int]:
        """Indices of the candles of `tf` that start at or after the end of E and are available at `decision`."""
        first = bisect.bisect_left(self.starts[tf], setup.extreme.end_utc)
        return list(range(first, self._last_available(tf, decision) + 1))

    def _check_alive(self, decision: datetime, states: dict[Timeframe, StateOf]) -> None:
        setup = self.setup
        if setup is None:
            return
        long = setup.side is Side.LONG
        h1 = self._pullback(Timeframe.H1, setup, decision)
        h4 = self._pullback(Timeframe.H4, setup, decision)
        known_until = decision - self.config.latency  # candles ending by then must exist
        missing = first_missing([self.h1[i] for i in h1], setup.extreme.end_utc, known_until)
        if missing is None:  # an absent H4 is knowable at the end of its slot, even with its H1 present
            missing = first_missing(
                [self.h4[i] for i in h4], setup.extreme.end_utc, candle_start(known_until, Timeframe.H4)
            )
        unusable = [i for i in h1 if not states[Timeframe.H1](i).usable] + [
            i for i in h4 if not states[Timeframe.H4](i).usable
        ]
        if missing is not None or unusable:
            where = missing.isoformat() if missing is not None else "bougie inutilisable"
            self._abandon(decision, f"DONNÉES_REPLI_INCOMPLÈTES ({where})", missing_data=True)
            return
        for i in h4:
            close = self.h4[i]["bid_close"]
            if (long and close < setup.lower) or (not long and close > setup.upper):
                self._abandon(decision, f"repli trop profond : clôture H4 {close} au-delà de la borne")
                return
        for i in h1:
            bar = self.h1[i]
            if (long and bar["bid_high"] > setup.target) or (not long and bar["bid_low"] < setup.target):
                self._abandon(decision, "reprise sans entrée : E dépassé")
                return
        expiry = setup.extreme.index + self.s2.max_setup_h4
        if expiry < len(self.h4) and self.h4_available[expiry] < decision:
            self._abandon(decision, f"expirée après {self.s2.max_setup_h4} H4")

    def _update_contact(self, setup: Setup, decision: datetime) -> None:
        if setup.contact is not None:
            return
        tf = self.s2.trigger
        bars = self.bars[tf]
        first = bisect.bisect_left(self.starts[tf], setup.identified_utc)
        for i in range(first, self._last_available(tf, decision) + 1):
            if overlaps(bars[i], setup.lower, setup.upper):
                setup.contact = i
                setup.history.append(f"contact {bars[i]['start_utc'].isoformat()}")
                return

    def _threshold(self, setup: Setup, t: int) -> Pivot | None:
        """Last recovery pivot: start(r) >= end(contact), confirmed at or before start(h) (sheet §4.4)."""
        if setup.contact is None:
            return None
        tf = self.s2.trigger
        bars = self.bars[tf]
        kind = PivotKind.HIGH if setup.side is Side.LONG else PivotKind.LOW
        earliest = bars[setup.contact]["end_utc"]
        if setup.refused_utc is not None:
            earliest = max(earliest, setup.refused_utc)
        start_h = bars[t]["start_utc"]
        candidates = []
        for p in reversed(self.pivots[tf].pivots):  # in candle order: stop at the first one too early
            if p.start_utc < earliest:
                break
            if p.kind is kind and p.confirmed_utc <= start_h:
                candidates.append(p)
        return max(candidates, key=lambda p: (p.confirmed_utc, p.index), default=None)

    def _stop(self, setup: Setup, decision: datetime) -> Decimal:
        bars = [self.h1[i] for i in self._pullback(Timeframe.H1, setup, decision)]
        margin = self.s2.stop_atr * setup.atr
        if setup.side is Side.LONG:
            low: Decimal = min(b["bid_low"] for b in bars)
            return low - margin
        high: Decimal = max(b["ask_high"] for b in bars)
        return high + margin

    def _reward_risk(self, side: Side, stop: Decimal, target: Decimal) -> Decimal | str:
        """Net potential gain at the target / estimated loss at the stop, per contract, before D."""
        last = self._last_tick
        if last is None:
            return "aucune cotation connue à l'instant de décision"
        try:
            estimate = self._loss_estimate(side, stop, last)
        except ValueError as exc:
            return f"estimation impossible : {exc}"
        if estimate.excluded_unknown:
            return "coût inconnu, jamais compté zéro : " + ", ".join(estimate.excluded_unknown)
        config, costs = self.config, self.config.costs
        units = config.spec.contract_size
        slippage = (costs.slippage_pips.value or Decimal(0)) * config.spec.pip_size
        move = target - last.ask - slippage if side is Side.LONG else last.bid - target - slippage
        gain_quote = (
            move * units
            - (costs.commission_per_contract.value or Decimal(0))
            - (costs.financing_per_contract_per_night.value or Decimal(0)) * config.estimated_nights
        )
        fee = costs.conversion_fee_rate.value or Decimal(0)
        gain = gain_quote / last.ask * (1 - fee) if gain_quote > 0 else gain_quote / last.bid * (1 + fee)
        return gain / estimate.loss_account_per_contract

    # ------------------------------------------------------------------ observation

    def _known_s2(
        self, t: int, decision: datetime, states: dict[Timeframe, StateOf], trend: Side | None
    ) -> dict[str, Any]:
        bar = self.bars[self.s2.trigger][t]
        last = self._last_tick
        point = self.curve[-1]
        position = self.position
        return {
            "trigger_candle": {
                "timeframe": self.s2.trigger.value,
                "start_utc": bar["start_utc"],
                "end_utc": bar["end_utc"],
                "state": states[self.s2.trigger](t).value,
                **{k: bar[k] for k in ("bid_high", "bid_low", "bid_close", "ask_close")},
            },
            "d1_trend": None if trend is None else trend.value,
            "setup": None if self.setup is None else self.setup.describe(),
            "market": market_state(decision).value,
            "quote": None if last is None else {"ts_utc": last.ts_utc, "bid": last.bid, "ask": last.ask},
            "account": {"balance": point.balance, "unrealized": point.unrealized, "equity": point.equity},
            "position": None
            if position is None
            else {"side": position.side.value, "size": position.size, "stop": position.stop, "target": self.target},
        }

    # ------------------------------------------------------------------ tick replay

    def _observe(self, tick: Tick) -> None:
        equity = self.balance + self._unrealized(tick)  # once per tick for both measures
        self.drawdown.observe(tick.ts_utc, equity)
        position = self.position
        self.relative.observe(tick.ts_utc, equity, None if position is None else position.decided_utc.isoformat())

    def _target_reached(self, tick: Tick) -> bool:
        position, target = self.position, self.target
        if position is None or target is None:
            return False
        return tick.bid >= target if position.side is Side.LONG else tick.ask <= target

    def _advance(self, until: datetime | None, *, inclusive: bool) -> None:
        while (tick := self._peek()) is not None:
            if until is not None and (tick.ts_utc > until if inclusive else tick.ts_utc >= until):
                return
            self._peeked = None
            previous = self._last_tick
            if self.position is not None and previous is not None:
                self._after_silence(previous, tick)
            if self.position is not None:
                self._observed_stop(tick)
            if self.position is not None and self._target_reached(tick):
                self._close(tick, self._exit_side(tick), "CIBLE", stop_triggered=False)
            if self.position is not None and tick.ts_utc > self._time_exit_due():
                # The deadline exists on its own: no decision candle needs to close at it.
                self._close(tick, self._exit_side(tick), TIME_EXIT, stop_triggered=False)
            if self.pending_entry is not None and tick.ts_utc > self.pending_entry.decided_utc:
                self._open(tick)
            self._last_tick = tick
            self._observe(tick)

    def _after_silence(self, previous: Tick, tick: Tick) -> None:
        position = self._open_position()
        kind = classify_silence(
            previous.ts_utc, tick.ts_utc, self.config.gap_threshold, self.config.documented_closures
        )
        if kind is Silence.NONE:
            return
        span = f"{previous.ts_utc.isoformat()} → {tick.ts_utc.isoformat()}"
        stop_hit, target_hit = self._crossed(tick), self._target_reached(tick)
        if kind is Silence.KNOWN_CLOSURE:
            if stop_hit:
                self._close(tick, self._stop_execution(tick), "STOP_FERMETURE_CONNUE", stop_triggered=True)
            elif target_hit:
                self._close(tick, self._exit_side(tick), "CIBLE_APRÈS_FERMETURE", stop_triggered=False)
            return
        # Unexplained gap: the order of the crossings during it is unknown (sheet §7).
        position.unobservable_crossings.append(span)
        accounted = f"trou {span}, comptabilisé au premier tick qui le clôt ({tick.ts_utc.isoformat()})"
        if self.scenario is GapScenario.STOP_FIRST:
            self._log(tick.ts_utc, "SCÉNARIO_B", accounted)
            self._close(
                tick,
                position.stop,
                "STOP_SCÉNARIO_B",
                stop_triggered=True,
                hypotheses=[f"stop supposé franchi pendant le trou, avant la cible ; {accounted}"],
            )
        elif self.scenario is GapScenario.TARGET_FIRST and self.target is not None:
            self._log(tick.ts_utc, "SCÉNARIO_C", accounted)
            self._close(
                tick,
                self.target,  # level E: no invisible price improvement
                "CIBLE_SCÉNARIO_C",
                stop_triggered=False,
                hypotheses=[f"cible supposée atteinte pendant le trou, avant le stop ; {accounted}"],
            )
        elif stop_hit:
            hypotheses = []
            if self.config.stop_type is StopType.NORMAL:
                hypotheses.append(f"exécution supposée au premier prix observé après l'interruption {span}")
            self._close(
                tick, self._stop_execution(tick), "STOP_APRÈS_INTERRUPTION", stop_triggered=True, hypotheses=hypotheses
            )
        elif target_hit:
            self._close(tick, self._exit_side(tick), "CIBLE_APRÈS_INTERRUPTION", stop_triggered=False)
        else:
            self._log(tick.ts_utc, "SCÉNARIO_A", f"{span} : franchissement possible non observé, position maintenue")

    def _open(self, tick: Tick) -> None:
        pending, target = self.pending_entry, self._pending_target
        self._pending_target = None
        super()._open(tick)
        position = self.position
        if position is None or pending is None or position.decided_utc != pending.decided_utc:
            return  # rejected, or filled then liquidated beyond the stop
        self.target = target
        self._log(tick.ts_utc, "ÉCHÉANCE_TEMPORELLE", self._time_exit_due().isoformat())
        if self._target_reached(tick):
            self._close(
                tick,
                self._exit_side(tick),
                "CIBLE_ATTEINTE_À_L'EXÉCUTION",
                stop_triggered=False,
                hypotheses=[
                    "cible déjà atteinte au premier prix : achat à l'ask (vente au bid) puis sortie au même tick"
                ],
            )

    def _close(
        self, tick: Tick, price: Decimal, reason: str, stop_triggered: bool, hypotheses: list[str] | None = None
    ) -> None:
        super()._close(tick, price, reason, stop_triggered, hypotheses)
        self.target = None
