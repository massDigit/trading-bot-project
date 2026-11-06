"""Offline DAY_01 engine (docs/strategies/DAY_01_LONDON_RANGE.md, ADR-021, ADR-022). No order.

Built on the S1 engine, which it does not change: forward-only tick replay, state strictly before
each decision, execution at the first tick strictly after it (buy at the ask, sell at the bid),
sizing on the up-to-date equity, costs and conversion, guaranteed stop with its premium,
`StopAtExecution`, equity curve and valuation of a position still open at the end of the study.

Specific to DAY_01, session by session (London date, times in Europe/London):
- range of the 28 M15 of [01:00, 08:00), frozen at 08:00 with the H4 ATR known then (ATR and its
  H4 states keep the S2/S3 rules and the `ResearchConfig` threshold, ADR-021);
- breakout on an M15 close, retest and confirmation on M5, read only from candles `OK` at their
  close under the DAY_01 convention (ADR-021), quality checked before any close is read; the
  preregistered comparison `Trigger.M15` reads the retest, invalidation, confirmation and stop on
  M15 with the same rules and the same 60 min delay (first confirmation at K + 15 min, quote at D
  in the confirming M15, entry still valid 5 min);
- one attempt per session, decision bounds, quote at D, stop and target of the sheet §5;
- pending entry valid in ]D, D + 5 min], cancelled as soon as a silence strictly longer than 5 min
  of expected-open time is known before its execution, including when the next tick reveals it
  (that tick never executes); expired otherwise;
- target exit at the first executable quote that reaches it; liquidation at the first tick
  strictly after 16:00. Each liquidation order reports its delay after 16:00, the silence closed by
  the closing tick and the closing reason; LIQUIDATION_APRÈS_INTERRUPTION and NUIT_NON_PRÉVUE are
  derived from them (`Liquidation`);
- open position across a silence strictly longer than 5 min: the trade is kept, marked
  indeterminate, and handled by scenario A (observed only), B (stop first) or C (target first),
  one trajectory each, as for S2. A known closure is not an unexplained interruption;
- at an explicit end of the study, the silence since the last quote of a position still open is
  measured: an interruption still in progress marks the trade indeterminate, distinct from a gap
  closed by a quote, with no tick, price or exit invented under any scenario; a liquidation order
  not executed by then is reported as such.

Research only: no order is ever sent and nothing here talks to a broker.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from forex_bot.backtest.bar_state import BarState, bar_state
from forex_bot.backtest.day01 import (
    ATR_UNAVAILABLE,
    BREAKOUT_DATA,
    CANCELLED_INTERRUPTION,
    EXECUTED,
    EXPIRED,
    INVALIDATED,
    LIQUIDATION,
    LIQUIDATION_AFTER_INTERRUPTION,
    M15,
    MARKET_CLOSED,
    NO_BREAKOUT,
    NO_QUOTE,
    NO_SESSION,
    POSITION_OPEN,
    RANGE_INCOMPLETE,
    RANGE_WIDTH,
    REJECTED_AT_EXECUTION,
    RETEST_DATA,
    RETEST_TIMEOUT,
    SIZE_REFUSED,
    STOP_AT_EXECUTION,
    STOP_INADMISSIBLE,
    TARGET_AT_EXECUTION,
    UNPLANNED_NIGHT,
    Day01Params,
    Liquidation,
    Session,
    Trigger,
    bar_ok,
    london,
    session_open,
    sessions,
    touches,
    zone,
)
from forex_bot.backtest.engine import (
    BacktestResult,
    DecisionRecord,
    EntryAction,
    PositionAction,
    ResearchConfig,
    S1Backtest,
    StopType,
    _PendingExit,
)
from forex_bot.backtest.feed import Silence, Tick, classify_silence
from forex_bot.backtest.s1 import EntrySignal, S1Params
from forex_bot.backtest.s2 import ContinuousWilderAtr, GapScenario
from forex_bot.history.bars import Gap
from forex_bot.history.calendar import MarketState, market_state
from forex_bot.market import Quote
from forex_bot.risk import Holding, LossEstimate, Side, estimate_loss_per_contract, usd_to_eur_from_eurusd_bid


@dataclass
class Day01Result(BacktestResult):
    day01_params: Day01Params = field(default_factory=Day01Params)
    scenario: GapScenario = GapScenario.OBSERVED_ONLY
    sessions: list[Session] = field(default_factory=list)
    liquidations: list[Liquidation] = field(default_factory=list)
    # Position still open at an explicit end of the study: silence since its last quote, still in progress.
    silence_at_end: dict[str, Any] | None = None
    unexecuted_liquidation_utc: datetime | None = None  # 16:00 order still pending at the end of the study


class Day01Backtest(S1Backtest):
    """One DAY_01 trajectory: one gap scenario, one research configuration."""

    def __init__(
        self,
        m5: Sequence[dict[str, Any]],
        m15: Sequence[dict[str, Any]],
        h4: Sequence[dict[str, Any]],
        ticks: Iterable[Tick],
        gaps: Sequence[Gap],
        params: Day01Params,
        config: ResearchConfig,
        *,
        scenario: GapScenario = GapScenario.OBSERVED_ONLY,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
    ) -> None:
        # The S1 parameters only carry the ATR period: S1 rules are never evaluated here.
        super().__init__(
            h4, [], ticks, gaps, S1Params(atr_period=params.atr_period), config, start_utc=start_utc, end_utc=end_utc
        )
        self.day01, self.scenario = params, scenario
        self.atr = ContinuousWilderAtr(h4, params.atr_period)  # continuity of the expected H4 (S2/S3 rule)
        self.m5 = {b["start_utc"]: b for b in m5}
        self.m15 = {b["start_utc"]: b for b in m15}
        self.trigger_bars = self.m5 if params.trigger is Trigger.M5 else self.m15
        self.sessions: list[Session] = []
        self.liquidations: list[Liquidation] = []
        self.silence_at_end: dict[str, Any] | None = None
        self.unexecuted_liquidation_utc: datetime | None = None
        self.target: Decimal | None = None  # of the open position
        self._pending_target: Decimal | None = None
        self._pending_session: Session | None = None

    # ------------------------------------------------------------------ public

    def run(self) -> Day01Result:
        starts = sorted(self.m15)
        start = self.start_utc or (starts[0] if starts else None)
        end = self.end_utc or (starts[-1] + timedelta(days=1) if starts else None)
        decided: datetime | None = None
        if start is not None and end is not None:
            for day in sessions(start, end, self.day01):
                if london(day, self.day01.liquidation) > end:
                    continue  # the whole session must lie in the study window
                decided = self._session(day)
        if self.end_utc is not None:
            final: datetime | None = self.end_utc
            self._advance(self.end_utc, inclusive=False)
            self._open_at_end(self.end_utc)
        else:
            self._advance(None, inclusive=True)
            instants = [m for m in (decided, self._last_tick.ts_utc if self._last_tick else None) if m is not None]
            final = max(instants, default=None)
        if final is not None:
            self._sample(final, self._last_tick)
        return Day01Result(
            self.config,
            self.params,
            self.trades,
            self.journal,
            self.curve,
            self.position,
            final,
            self.decisions,
            self.drawdown,
            day01_params=self.day01,
            scenario=self.scenario,
            sessions=self.sessions,
            liquidations=self.liquidations,
            silence_at_end=self.silence_at_end,
            unexecuted_liquidation_utc=self.unexecuted_liquidation_utc,
        )

    def _open_at_end(self, end: datetime) -> None:
        """Position still open at the explicit end: nothing is closed, priced or invented (sheet §4.7)."""
        position, last = self.position, self._last_tick
        if position is None or last is None:
            return
        kind = classify_silence(last.ts_utc, end, self.day01.interruption_threshold, self.config.documented_closures)
        self.silence_at_end = {
            "last_quote_utc": last.ts_utc,
            "end_of_study_utc": end,
            "duration": end - last.ts_utc,
            "kind": kind,
            "in_progress": True,  # no quote closes it: unlike the gaps closed by a tick
        }
        if kind is Silence.UNEXPLAINED:
            span = f"{last.ts_utc.isoformat()} → en cours à la fin de l'étude ({end.isoformat()})"
            position.unobservable_crossings.append(span)
            self._log(
                end,
                "INTERRUPTION_EN_COURS",
                f"{span} : silence non clos, aucune cotation ; transaction conservée, indéterminée, "
                "ouverte et valorisée au dernier tick observé",
            )
        if self.pending_exit is not None:
            self.unexecuted_liquidation_utc = self.pending_exit.decided_utc
            self._log(
                end,
                "LIQUIDATION_NON_EXÉCUTÉE",
                f"ordre décidé à {self.pending_exit.decided_utc.isoformat()}, aucun tick postérieur avant la fin",
            )

    # ------------------------------------------------------------------ session

    def _session(self, day: date) -> datetime:
        p = self.day01
        session = Session(day)
        self.sessions.append(session)
        freeze, liquidation = london(day, p.freeze), london(day, p.liquidation)
        if not session_open(day, p):
            session.block(NO_SESSION)
        else:
            self._advance(freeze, inclusive=False)  # state strictly before G
            self._sample(freeze, self._last_tick)
            session.previous_position = self.position is not None
            self._evaluate(session, day, freeze)
        # Liquidation of any position still open at 16:00, whatever the session went through.
        self._advance(liquidation, inclusive=False)
        if self.position is not None and self.pending_exit is None:
            self.pending_exit = _PendingExit(liquidation, LIQUIDATION)
            self._log(liquidation, "LIQUIDATION_DÉCIDÉE", "fin de séance 16:00 Londres, au premier tick postérieur")
        return liquidation

    def _evaluate(self, session: Session, day: date, freeze: datetime) -> None:
        p = self.day01
        # Range (sheet §4.1): 28 M15 present and OK, frozen at G.
        first = london(day, p.range_start)
        bars = [self.m15.get(first + i * M15) for i in range(p.range_slots)]
        if not all(bar_ok(b) for b in bars):
            missing = next(first + i * M15 for i, b in enumerate(bars) if not bar_ok(b))
            session.block(RANGE_INCOMPLETE, f"première M15 non OK : {missing.isoformat()}")
            return
        complete = [b for b in bars if b is not None]
        rh, rl = max(b["bid_high"] for b in complete), min(b["bid_low"] for b in complete)
        rah = max(b["ask_high"] for b in complete)
        a = self._atr_at(freeze)
        session.range = {"rh": rh, "rl": rl, "rah": rah, "height": rh - rl, "atr": a, "frozen_utc": freeze}
        if a is None or a <= 0:
            session.block(ATR_UNAVAILABLE)
            return
        ratio = (rh - rl) / a
        session.range["h_over_a"] = ratio
        if not p.min_width <= ratio <= p.max_width:
            session.block(RANGE_WIDTH, f"H / A = {ratio:.3f}")
            return

        # Breakout (sheet §4.2): first M15 close beyond the bound by more than the margin.
        margin = p.breakout_margin * a
        start, last = freeze, london(day, p.last_breakout_start)
        side: Side | None = None
        k = freeze
        while start <= last:
            close = start + M15
            self._advance(close, inclusive=False)
            bar = self.m15.get(start)
            if not bar_ok(bar) or bar is None:
                session.block(BREAKOUT_DATA, f"M15 {start.isoformat()}")
                return
            if bar["bid_close"] > rh + margin:
                side = Side.LONG
            elif bar["bid_close"] < rl - margin:
                side = Side.SHORT
            if side is not None:
                k = close
                session.breakout = {"side": side.value, "k_utc": k, "bid_close": bar["bid_close"]}
                break
            start = close
        if side is None:
            session.block(NO_BREAKOUT)
            return

        # Retest, invalidation and confirmation on M5, or on M15 in the comparison (sheet §3.1, §4.3, §4.8).
        z_low, z_high = zone(side, rh, rl, a, p)
        long = side is Side.LONG
        step, unit = p.trigger_step, p.trigger.value
        contact: datetime | None = None
        extreme: Decimal | None = None
        decision: datetime | None = None
        # Observation only, filled as the candles are read so that it survives every outcome of the
        # retest (data, invalidation, timeout, confirmation); it never feeds a decision.
        observed: dict[str, Any] = {"trigger": unit, "zone": (z_low, z_high), "contact_utc": None, "extreme": None}
        observed["last_examined_utc"] = None  # start of the last candle examined (its quality at least)
        session.retest = observed
        start = k
        while start + step <= k + p.retest_delay:
            end = start + step
            self._advance(end, inclusive=False)
            observed["last_examined_utc"] = start
            bar = self.trigger_bars.get(start)
            if not bar_ok(bar) or bar is None:
                session.block(RETEST_DATA, f"{unit} {start.isoformat()}, clôture non lue")
                return
            close = bar["bid_close"]
            if (long and close < z_low) or (not long and close > z_high):
                session.block(INVALIDATED, f"{unit} {start.isoformat()} clôture {close}")
                return
            if contact is None and touches(bar, z_low, z_high):
                contact = observed["contact_utc"] = start
            if contact is not None:
                level = bar["bid_low"] if long else bar["ask_high"]
                extreme = level if extreme is None else (min(extreme, level) if long else max(extreme, level))
                observed["extreme"] = extreme
                if (long and close > rh) or (not long and close < rl):
                    decision = end
                    break
            start = end
        if decision is None or extreme is None:
            session.block(RETEST_TIMEOUT)
            return
        session.retest["confirmation_utc"] = decision
        self._decide_entry(session, day, side, decision, extreme, rh, rl, a)

    def _atr_at(self, instant: datetime) -> Decimal | None:
        i = bisect.bisect_right(self.h4_available, instant) - 1
        if i < 0:
            return None
        cache: dict[int, BarState] = {}

        def state(j: int) -> BarState:
            if j not in cache:
                cache[j] = bar_state(
                    self.h4[j], instant, self.gaps, self.config.gap_threshold, self.config.documented_closures
                )
            return cache[j]

        return self.atr.at(i, state)

    # ------------------------------------------------------------------ decision and pending entry

    def _decide_entry(
        self,
        session: Session,
        day: date,
        side: Side,
        decision: datetime,
        extreme: Decimal,
        rh: Decimal,
        rl: Decimal,
        a: Decimal,
    ) -> None:
        p = self.day01
        long = side is Side.LONG
        self._sample(decision, self._last_tick)  # state strictly before D: the replay stopped there
        last = self._last_tick
        record = DecisionRecord(
            decision,
            {
                "session": day.isoformat(),
                "quote": None if last is None else {"ts_utc": last.ts_utc, "bid": last.bid, "ask": last.ask},
                "account": {"balance": self.balance, "equity": self.balance + self._unrealized(last)},
                "position_open": self.position is not None,
            },
            PositionAction.FLAT if self.position is None else PositionAction.HELD,
        )
        self.decisions.append(record)

        def refuse(reason: str, detail: str | None = None) -> None:
            session.block(reason, detail)
            record.entry_action = EntryAction.SIGNAL_REFUSED
            record.reasons.append(reason if detail is None else f"{reason} : {detail}")
            self._log(decision, "ABSTENTION", record.reasons[-1])

        if self.position is not None or self.pending_exit is not None:
            refuse(POSITION_OPEN, "aucune entrée tant qu'elle subsiste ; séance consommée")
            return
        if market_state(decision) is not MarketState.OPEN:
            refuse(MARKET_CLOSED)
            return
        # Quote at D: last tick strictly before D inside the confirming candle (M5, or M15 in the comparison).
        if last is None or last.ts_utc < decision - p.trigger_step or not (0 < last.bid <= last.ask):
            refuse(NO_QUOTE)
            return
        stop = extreme - p.stop_margin * a if long else extreme + p.stop_margin * a
        entry = last.ask if long else last.bid  # P_D
        if (long and not (stop < last.bid and entry - stop > 0)) or (
            not long and not (stop > last.ask and stop - entry > 0)
        ):
            refuse(STOP_INADMISSIBLE, f"stop {stop}, bid {last.bid}, ask {last.ask}")
            return
        target = entry + p.reward_ratio * (entry - stop) if long else entry - p.reward_ratio * (stop - entry)
        if (long and target <= entry) or (not long and target >= entry):
            refuse(STOP_INADMISSIBLE, f"cible {target} du mauvais côté de {entry}")
            return
        self._size(decision, EntrySignal(side, stop, a, rh, rl), record)
        if self.pending_entry is None:
            session.block(SIZE_REFUSED, record.reasons[-1] if record.reasons else None)
            return
        deadline = min(decision + p.entry_validity, london(day, p.liquidation))
        session.decision = {
            "d_utc": decision,
            "side": side.value,
            "p_d": entry,
            "stop": stop,
            "target": target,
            "size": self.pending_entry.size,
            "deadline_utc": deadline,
        }
        self._pending_target, self._pending_session = target, session
        self._advance(deadline, inclusive=True)  # executions in ]D, deadline]
        if self.pending_entry is None:
            return
        # No admissible tick until the deadline: interruption already known, or plain expiry.
        last = self._last_tick
        if last is not None and self._interrupted(last.ts_utc, deadline):
            known = last.ts_utc + p.interruption_threshold
            self._end_pending(
                CANCELLED_INTERRUPTION,
                known,
                f"silence depuis {last.ts_utc.isoformat()} supérieur à "
                f"{p.interruption_threshold} d'ouverture prévue après {known.isoformat()}, avant l'échéance",
            )
        else:
            self._end_pending(EXPIRED, deadline, "aucun tick admissible dans ]D, échéance]")

    def _interrupted(self, start: datetime, end: datetime) -> bool:
        """Silence strictly longer than the DAY_01 threshold of expected-open time (a known closure is not)."""
        kind = classify_silence(start, end, self.day01.interruption_threshold, self.config.documented_closures)
        return kind is Silence.UNEXPLAINED

    def _end_pending(self, outcome: str, utc: datetime, detail: str) -> None:
        session = self._pending_session
        self.pending_entry, self._pending_target, self._pending_session = None, None, None
        if session is not None:
            session.entry_outcome = outcome
            session.events.append(f"{outcome} : {detail}")
        self._log(utc, outcome, f"{detail} ; tentative consommée")

    def _loss_estimate(self, side: Side, stop: Decimal, tick: Tick) -> LossEstimate:
        """Intraday holding: no night is provisioned (sheet §6.2)."""
        config = self.config
        return estimate_loss_per_contract(
            side=side,
            stop_price=stop,
            quote=Quote(tick.bid, tick.ask, "TRADEABLE", tick.ts_utc, delayed=False, source="historique"),
            spec=config.spec,
            conversion=usd_to_eur_from_eurusd_bid(tick.bid),
            costs=config.costs,
            holding=Holding.INTRADAY,
            nights=0,
            guaranteed_stop=config.stop_type is StopType.GUARANTEED,
        )

    # ------------------------------------------------------------------ tick replay

    def _target_reached(self, tick: Tick) -> bool:
        position, target = self.position, self.target
        if position is None or target is None:
            return False
        return tick.bid >= target if position.side is Side.LONG else tick.ask <= target

    def _advance(self, until: datetime | None, *, inclusive: bool) -> None:
        """Priority on a tick (ASSUMP-024): silence, stop, target, pending liquidation, pending entry."""
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
            pending = self.pending_exit
            if pending is not None and self.position is not None and tick.ts_utc > pending.decided_utc:
                # The liquidation order closes the position here unless a stop or target did first.
                self._close(tick, self._exit_side(tick), LIQUIDATION, stop_triggered=False)
            if self.pending_entry is not None:
                if previous is not None and self._interrupted(previous.ts_utc, tick.ts_utc):
                    # The interruption is known at the latest on this tick: it never executes the order.
                    self._end_pending(
                        CANCELLED_INTERRUPTION,
                        tick.ts_utc,
                        f"silence {previous.ts_utc.isoformat()} → {tick.ts_utc.isoformat()} supérieur à "
                        f"{self.day01.interruption_threshold} d'ouverture prévue, révélé au plus tard par ce tick",
                    )
                elif tick.ts_utc > self.pending_entry.decided_utc:
                    self._open(tick)
            self._last_tick = tick
            self._observe(tick)

    def _after_silence(self, previous: Tick, tick: Tick) -> None:
        """Open position across a silence (ADR-021): the trade is kept, never removed; scenarios A/B/C."""
        position = self._open_position()
        kind = classify_silence(
            previous.ts_utc, tick.ts_utc, self.day01.interruption_threshold, self.config.documented_closures
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
        position.unobservable_crossings.append(span)
        self._log(tick.ts_utc, "INTERRUPTION_POSITION", f"{span} : transaction conservée, indéterminée")
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
                self.target,  # level T: no invisible price improvement
                "CIBLE_SCÉNARIO_C",
                stop_triggered=False,
                hypotheses=[f"cible supposée atteinte pendant le trou, avant le stop ; {accounted}"],
            )
        elif stop_hit:
            self._close(tick, self._stop_execution(tick), "STOP_APRÈS_INTERRUPTION", stop_triggered=True)
        elif target_hit:
            self._close(tick, self._exit_side(tick), "CIBLE_APRÈS_INTERRUPTION", stop_triggered=False)
        else:
            self._log(tick.ts_utc, "SCÉNARIO_A", f"{span} : franchissement possible non observé, position maintenue")

    def _open(self, tick: Tick) -> None:
        pending, target, session = self.pending_entry, self._pending_target, self._pending_session
        self._pending_target, self._pending_session = None, None
        super()._open(tick)
        if pending is None:
            return
        position = self.position
        if position is not None and position.decided_utc == pending.decided_utc:
            outcome = EXECUTED
            self.target = target
            if self._target_reached(tick):
                outcome = TARGET_AT_EXECUTION
                self._close(
                    tick,
                    self._exit_side(tick),
                    TARGET_AT_EXECUTION,
                    stop_triggered=False,
                    hypotheses=["cible déjà atteinte au premier prix : achat à l'ask (vente au bid) puis sortie"],
                )
        elif self.trades and self.trades[-1].decided_utc == pending.decided_utc:
            outcome = STOP_AT_EXECUTION  # filled then liquidated on the same tick (reference)
        else:
            outcome = REJECTED_AT_EXECUTION
        if session is not None:
            session.entry_outcome = outcome

    def _close(
        self, tick: Tick, price: Decimal, reason: str, stop_triggered: bool, hypotheses: list[str] | None = None
    ) -> None:
        pending = self.pending_exit
        previous = self._last_tick  # still the tick before `tick`: it is updated after the events
        self.pending_exit = None  # the S1 engine would log a channel exit: DAY_01 has only the liquidation
        super()._close(tick, price, reason, stop_triggered, hypotheses)
        self.target = None
        if pending is not None:
            self._record_liquidation(tick, pending, previous, reason)

    def _record_liquidation(self, tick: Tick, pending: _PendingExit, previous: Tick | None, reason: str) -> None:
        """Delay after 16:00, silence closed by the closing tick and closing reason, kept apart (sheet §5)."""
        threshold, closures = self.day01.interruption_threshold, self.config.documented_closures
        kind = Silence.NONE if previous is None else classify_silence(previous.ts_utc, tick.ts_utc, threshold, closures)
        record = Liquidation(
            pending.decided_utc,
            tick.ts_utc,
            reason,
            None if previous is None else tick.ts_utc - previous.ts_utc,
            kind,
        )
        self.liquidations.append(record)
        silence = "inconnu" if record.silence is None else f"{record.silence} ({kind.value})"
        self._log(
            tick.ts_utc,
            "LIQUIDATION_RÉSOLUE",
            f"motif {reason} ; délai après 16:00 {record.delay_after_16h} ; silence clos par ce tick {silence}",
        )
        if reason != LIQUIDATION:
            self._log(tick.ts_utc, "LIQUIDATION_ABANDONNÉE", f"{reason} avant l'exécution de la liquidation")
        if record.after_interruption:
            self._log(tick.ts_utc, LIQUIDATION_AFTER_INTERRUPTION, f"silence {record.silence} > {threshold}")
        if record.unplanned_night:
            self._log(tick.ts_utc, UNPLANNED_NIGHT, "clôture après la fin de la journée de cotation de l'ordre")
