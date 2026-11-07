"""Offline DAY_02 engine (docs/strategies/DAY_02_FLAG_CONTINUATION.md, ADR-026 to ADR-028). No order.

Built on the S1 engine, which it does not change, and not on the DAY_01 engine: forward-only tick
replay, state strictly before each decision, execution at the first tick strictly after it (buy at
the ask, sell at the bid), sizing on the up-to-date equity, costs and conversion, guaranteed stop
with its premium, `StopAtExecution`, equity curve, tick drawdown and valuation of a position still
open at the end of the study.

Specific to DAY_02, session by session (London date, times in Europe/London):
- configurations read on candles only (`day02.configuration_from`), one at a time, from a resume
  state; the search is suspended while an entry is pending or a position is open, and resumes with
  M15 starting at the instant that authorises it (end of a configuration, refusal at D, outcome of
  an unexecuted entry, close of the position): every resume is recorded with its cause (`Attempt`);
- A = Wilder 14 ATR on H1, continuity of the expected H1, H1 states under the H1 convention of the
  project (`ResearchConfig.gap_threshold`), on the last H1 ended by the start of the impulse window;
- decision at D (quote in the exit candle, stop admissible, target still ahead, size); pending entry
  valid in ]D, D + 5 min], cancelled as soon as a silence strictly longer than 5 min of expected-open
  time is known, including when the next tick reveals it (that tick never executes); expired otherwise;
- target at the first executable quote that reaches it; one closing order per position, the first
  deadline reached: time exit 2 h after the execution, or liquidation at 17:00 (LIQUIDATION_17H when
  both fall at the same instant), executed at the first tick strictly after it, whose delay, closed
  silence and closing reason are kept apart (`Closing`); a position may remain after its deadline
  for lack of quotes, without any invented price;
- open position across a silence strictly longer than 5 min: trade kept, marked indeterminate,
  scenario A (observed only), B (stop first) or C (target first), one trajectory each, as DAY_01;
  a known closure is not an unexplained interruption;
- at an explicit end of the study, a silence still in progress marks the open trade indeterminate,
  with no tick, price or exit invented; a closing order not executed by then is reported.
No daily or weekly loss block is simulated in this isolated reference (ADR-027).

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
from forex_bot.backtest.day01 import LONDON, M15, london
from forex_bot.backtest.day02 import (
    CANCELLED_INTERRUPTION,
    ENTRY_DECIDED,
    EXECUTED,
    EXIT,
    EXPIRED,
    LIQUIDATION,
    MARKET_CLOSED,
    NO_QUOTE,
    NO_SESSION,
    POSITION_CLOSED,
    POSITION_OPEN,
    REJECTED_AT_EXECUTION,
    SESSION_START,
    SIZE_REFUSED,
    STOP_AT_EXECUTION,
    STOP_INADMISSIBLE,
    TARGET_AT_EXECUTION,
    TARGET_PASSED,
    TIME_EXIT,
    Attempt,
    Closing,
    Configuration,
    Day02Params,
    Trigger,
    ceil_m15,
    configuration_from,
    session_day,
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
class Day02Result(BacktestResult):
    day02_params: Day02Params = field(default_factory=Day02Params)
    scenario: GapScenario = GapScenario.OBSERVED_ONLY
    attempts: list[Attempt] = field(default_factory=list)
    closings: list[Closing] = field(default_factory=list)
    skipped_days: list[tuple[date, str]] = field(default_factory=list)
    # Position still open at an explicit end of the study: silence since its last quote, still in progress.
    silence_at_end: dict[str, Any] | None = None
    unexecuted_closing: tuple[datetime, str] | None = None  # closing order due, not executed by the end


@dataclass(frozen=True)
class _Due:
    """The closing order of the open position: its deadline and its reason."""

    utc: datetime
    reason: str  # TIME_EXIT or LIQUIDATION
    coincident: bool  # time exit exactly at 17:00


class Day02Backtest(S1Backtest):
    """One DAY_02 trajectory: one gap scenario, one research configuration."""

    def __init__(
        self,
        m5: Sequence[dict[str, Any]],
        m15: Sequence[dict[str, Any]],
        h1: Sequence[dict[str, Any]],
        ticks: Iterable[Tick],
        gaps: Sequence[Gap],
        params: Day02Params,
        config: ResearchConfig,
        *,
        scenario: GapScenario = GapScenario.OBSERVED_ONLY,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
    ) -> None:
        # No H4 nor D1: S1 rules are never evaluated; the S1 parameters only carry the ATR period.
        super().__init__(
            [], [], ticks, gaps, S1Params(atr_period=params.atr_period), config, start_utc=start_utc, end_utc=end_utc
        )
        self.day02, self.scenario = params, scenario
        self.h1 = list(h1)
        self.h1_end = [b["end_utc"] for b in self.h1]
        if self.h1_end != sorted(self.h1_end):
            raise ValueError("bougies H1 attendues dans l'ordre chronologique")
        self.h1_atr = ContinuousWilderAtr(self.h1, params.atr_period)  # continuity of the expected H1
        self.m5 = {b["start_utc"]: b for b in m5}
        self.m15 = {b["start_utc"]: b for b in m15}
        self.trigger_bars = self.m5 if params.trigger is Trigger.M5 else self.m15
        self.attempts: list[Attempt] = []
        self.closings: list[Closing] = []
        self.skipped_days: list[tuple[date, str]] = []
        self.silence_at_end: dict[str, Any] | None = None
        self.unexecuted_closing: tuple[datetime, str] | None = None
        self.target: Decimal | None = None  # of the open position
        self._due: _Due | None = None  # closing order of the open position
        self._pending_target: Decimal | None = None
        self._pending_attempt: Attempt | None = None

    # ------------------------------------------------------------------ public

    def run(self) -> Day02Result:
        p = self.day02
        starts = sorted(self.m15)
        start = self.start_utc or (starts[0] if starts else None)
        end = self.end_utc or (starts[-1] + timedelta(days=1) if starts else None)
        decided: datetime | None = None
        if start is not None and end is not None:
            for day in _london_days(start, end):
                if not start <= london(day, p.impulse_start) or london(day, p.liquidation) > end:
                    continue  # the whole session must lie in the study window
                decided = self._session(day) or decided
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
        return Day02Result(
            self.config,
            self.params,
            self.trades,
            self.journal,
            self.curve,
            self.position,
            final,
            self.decisions,
            self.drawdown,
            day02_params=self.day02,
            scenario=self.scenario,
            attempts=self.attempts,
            closings=self.closings,
            skipped_days=self.skipped_days,
            silence_at_end=self.silence_at_end,
            unexecuted_closing=self.unexecuted_closing,
        )

    def atr_at(self, cutoff: datetime, known_at: datetime) -> Decimal | None:
        """A on the last H1 ended by `cutoff`, candle states as knowable at `known_at` (sheet §5.1)."""
        i = bisect.bisect_right(self.h1_end, cutoff) - 1
        if i < 0:
            return None
        cache: dict[int, BarState] = {}

        def state(j: int) -> BarState:
            if j not in cache:
                cache[j] = bar_state(
                    self.h1[j], known_at, self.gaps, self.config.gap_threshold, self.config.documented_closures
                )
            return cache[j]

        return self.h1_atr.at(i, state)

    # ------------------------------------------------------------------ session

    def _session(self, day: date) -> datetime | None:
        p = self.day02
        start = london(day, p.impulse_start)
        if not session_day(day):
            self.skipped_days.append((day, NO_SESSION))
            return None
        self._advance(start, inclusive=False)
        resume, after = start, SESSION_START
        if self.position is not None or self.pending_entry is not None:
            closed = self._wait_flat(start, day)
            if closed is None:
                self.skipped_days.append((day, "position antérieure encore ouverte à la dernière reconnaissance"))
                return None
            resume, after = max(start, closed), POSITION_CLOSED
        decided: datetime | None = None
        while True:
            search = configuration_from(resume, day, self.m15, self.trigger_bars, self.atr_at, p)
            attempt = Attempt(day, resume, after, search)
            self.attempts.append(attempt)
            config = search.configuration
            if config is None or config.ended_utc is None or config.outcome is None:
                return decided
            if config.outcome != EXIT:
                attempt.ended_utc, attempt.ended_by = config.ended_utc, config.outcome
            else:
                decided = config.ended_utc
                self._decide_entry(attempt, config)
            if attempt.ended_utc is None or attempt.ended_by is None:
                return decided  # position still open at the last possible recognition
            resume, after = attempt.ended_utc, attempt.ended_by

    def _wait_flat(self, since: datetime, day: date) -> datetime | None:
        """Replay until no position nor pending entry remains: the close instant, or None if it does not
        happen before the last recognition of session `day` (the ticks are replayed later anyway)."""
        last = london(day, self.day02.last_recognition)
        cursor = ceil_m15(since)
        while self.position is not None or self.pending_entry is not None:
            if cursor <= since:
                cursor += M15
            if cursor > last:
                return None
            self._advance(cursor, inclusive=False)
            cursor += M15
        return self.trades[-1].exit_utc if self.trades else since

    # ------------------------------------------------------------------ decision and pending entry

    def _decide_entry(self, attempt: Attempt, config: Configuration) -> None:
        p = self.day02
        decision, side = config.ended_utc, config.side
        stop, target, a = config.stop, config.target, config.atr
        if decision is None or stop is None or target is None:
            raise RuntimeError("sortie confirmée sans D, stop ou cible")
        long = side is Side.LONG
        self._advance(decision, inclusive=False)  # state strictly before D
        self._sample(decision, self._last_tick)
        last = self._last_tick
        record = DecisionRecord(
            decision,
            {
                "session": attempt.day.isoformat(),
                "quote": None if last is None else {"ts_utc": last.ts_utc, "bid": last.bid, "ask": last.ask},
                "account": {"balance": self.balance, "equity": self.balance + self._unrealized(last)},
                "position_open": self.position is not None,
            },
            PositionAction.FLAT if self.position is None else PositionAction.HELD,
        )
        self.decisions.append(record)

        def refuse(reason: str, detail: str | None = None) -> None:
            attempt.at_d = reason
            attempt.ended_utc, attempt.ended_by = decision, reason
            if detail is not None:
                attempt.events.append(f"{reason} : {detail}")
            record.entry_action = EntryAction.SIGNAL_REFUSED
            record.reasons.append(reason if detail is None else f"{reason} : {detail}")
            self._log(decision, "ABSTENTION", record.reasons[-1])

        if self.position is not None or self.pending_entry is not None or self.pending_exit is not None:
            refuse(POSITION_OPEN)  # cannot happen: the search is suspended meanwhile
            return
        if market_state(decision) is not MarketState.OPEN:
            refuse(MARKET_CLOSED)
            return
        # Quote at D: last tick strictly before D inside the exit candle (M5, or M15 in the comparison).
        if last is None or last.ts_utc < decision - p.trigger_step or not (0 < last.bid <= last.ask):
            refuse(NO_QUOTE)
            return
        entry = last.ask if long else last.bid  # P_D
        if (long and not (stop < last.bid and entry - stop > 0)) or (
            not long and not (stop > last.ask and stop - entry > 0)
        ):
            refuse(STOP_INADMISSIBLE, f"stop {stop}, bid {last.bid}, ask {last.ask}")
            return
        if (long and target <= entry) or (not long and target >= entry):
            refuse(TARGET_PASSED, f"cible {target}, P_D {entry}")
            return
        self._size(decision, EntrySignal(side, stop, a, config.peak, config.origin), record)
        if self.pending_entry is None:
            refuse(SIZE_REFUSED, record.reasons[-1] if record.reasons else None)
            return
        attempt.at_d = ENTRY_DECIDED
        deadline = decision + p.entry_validity
        attempt.decision = {
            "d_utc": decision,
            "side": side.value,
            "p_d": entry,
            "stop": stop,
            "target": target,
            "size": self.pending_entry.size,
            "deadline_utc": deadline,
        }
        self._pending_target, self._pending_attempt = target, attempt
        self._advance(deadline, inclusive=True)  # executions in ]D, D + 5 min]
        if self.pending_entry is not None:
            # No admissible tick until the deadline: interruption already known, or plain expiry.
            last = self._last_tick
            if last is not None and self._interrupted(last.ts_utc, deadline):
                known = last.ts_utc + p.interruption_threshold
                self._end_pending(
                    CANCELLED_INTERRUPTION,
                    known,
                    f"silence depuis {last.ts_utc.isoformat()} supérieur à {p.interruption_threshold} "
                    f"d'ouverture prévue après {known.isoformat()}, avant l'échéance",
                )
            else:
                self._end_pending(EXPIRED, deadline, "aucun tick admissible dans ]D, D + 5 min]")
        if attempt.entry_outcome in (EXPIRED, CANCELLED_INTERRUPTION, REJECTED_AT_EXECUTION):
            attempt.ended_utc, attempt.ended_by = attempt.entry_outcome_utc, attempt.entry_outcome
            return
        closed = self._wait_flat(deadline, attempt.day)
        if closed is not None:
            attempt.ended_utc, attempt.ended_by = closed, POSITION_CLOSED

    def _interrupted(self, start: datetime, end: datetime) -> bool:
        """Silence strictly longer than the DAY_02 threshold of expected-open time (a known closure is not)."""
        kind = classify_silence(start, end, self.day02.interruption_threshold, self.config.documented_closures)
        return kind is Silence.UNEXPLAINED

    def _end_pending(self, outcome: str, utc: datetime, detail: str) -> None:
        attempt = self._pending_attempt
        self.pending_entry, self._pending_target, self._pending_attempt = None, None, None
        if attempt is not None:
            attempt.entry_outcome, attempt.entry_outcome_utc = outcome, utc
            attempt.events.append(f"{outcome} : {detail}")
        self._log(utc, outcome, detail)

    def _loss_estimate(self, side: Side, stop: Decimal, tick: Tick) -> LossEstimate:
        """Intraday holding: no night is provisioned (sheet §7)."""
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
        """Priority on a tick (ASSUMP-024): silence, stop, target, closing order, pending entry."""
        while (tick := self._peek()) is not None:
            if until is not None and (tick.ts_utc > until if inclusive else tick.ts_utc >= until):
                return
            self._peeked = None
            previous = self._last_tick
            due = self._due
            if self.position is not None and self.pending_exit is None and due is not None and tick.ts_utc > due.utc:
                # The closing order was due at its deadline; the first tick strictly after it executes it.
                self.pending_exit = _PendingExit(due.utc, due.reason)
                self._log(due.utc, f"{due.reason}_DÉCIDÉE", "au premier tick strictement postérieur")
            if self.position is not None and previous is not None:
                self._after_silence(previous, tick)
            if self.position is not None:
                self._observed_stop(tick)
            if self.position is not None and self._target_reached(tick):
                self._close(tick, self._exit_side(tick), "CIBLE", stop_triggered=False)
            pending = self.pending_exit
            if pending is not None and self.position is not None and tick.ts_utc > pending.decided_utc:
                self._close(tick, self._exit_side(tick), pending.reason, stop_triggered=False)
            if self.pending_entry is not None:
                if previous is not None and self._interrupted(previous.ts_utc, tick.ts_utc):
                    # The interruption is known at the latest on this tick: it never executes the order.
                    self._end_pending(
                        CANCELLED_INTERRUPTION,
                        tick.ts_utc,
                        f"silence {previous.ts_utc.isoformat()} → {tick.ts_utc.isoformat()} supérieur à "
                        f"{self.day02.interruption_threshold} d'ouverture prévue, révélé au plus tard par ce tick",
                    )
                elif tick.ts_utc > self.pending_entry.decided_utc:
                    self._open(tick)
            self._last_tick = tick
            self._observe(tick)

    def _after_silence(self, previous: Tick, tick: Tick) -> None:
        """Open position across a silence (ADR-021, ADR-026): trade kept, never removed; scenarios A/B/C."""
        position = self._open_position()
        kind = classify_silence(
            previous.ts_utc, tick.ts_utc, self.day02.interruption_threshold, self.config.documented_closures
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
        pending, target, attempt = self.pending_entry, self._pending_target, self._pending_attempt
        self._pending_target, self._pending_attempt = None, None
        super()._open(tick)
        if pending is None:
            return
        position = self.position
        if position is not None and position.decided_utc == pending.decided_utc:
            outcome = EXECUTED
            self.target = target
            self._due = self._closing_due(position.entry_utc, attempt.day if attempt else None)
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
        if attempt is not None:
            attempt.entry_outcome, attempt.entry_outcome_utc = outcome, tick.ts_utc

    def _closing_due(self, executed: datetime, day: date | None) -> _Due | None:
        """First deadline: time exit 2 h after the execution, or 17:00; equality gives LIQUIDATION_17H."""
        if day is None:
            return None
        time_exit, liquidation = executed + self.day02.time_exit, london(day, self.day02.liquidation)
        if time_exit < liquidation:
            return _Due(time_exit, TIME_EXIT, False)
        return _Due(liquidation, LIQUIDATION, time_exit == liquidation)

    def _close(
        self, tick: Tick, price: Decimal, reason: str, stop_triggered: bool, hypotheses: list[str] | None = None
    ) -> None:
        pending, due = self.pending_exit, self._due
        previous = self._last_tick  # still the tick before `tick`: it is updated after the events
        self.pending_exit = None  # the S1 engine would log a channel exit: DAY_02 has only its closing order
        super()._close(tick, price, reason, stop_triggered, hypotheses)
        self.target, self._due = None, None
        if pending is not None:
            self._record_closing(tick, pending, previous, reason, due)

    def _record_closing(
        self, tick: Tick, pending: _PendingExit, previous: Tick | None, reason: str, due: _Due | None
    ) -> None:
        """Delay after the deadline, silence closed by the closing tick and closing reason, kept apart."""
        threshold, closures = self.day02.interruption_threshold, self.config.documented_closures
        kind = Silence.NONE if previous is None else classify_silence(previous.ts_utc, tick.ts_utc, threshold, closures)
        record = Closing(
            pending.decided_utc,
            pending.reason,
            tick.ts_utc,
            reason,
            None if previous is None else tick.ts_utc - previous.ts_utc,
            kind,
            due.coincident if due is not None else False,
        )
        self.closings.append(record)
        silence = "inconnu" if record.silence is None else f"{record.silence} ({kind.value})"
        self._log(
            tick.ts_utc,
            f"{pending.reason}_RÉSOLUE",
            f"motif {reason} ; délai après l'échéance {record.delay} ; silence clos par ce tick {silence}",
        )
        if record.coincident:
            self._log(tick.ts_utc, "ÉCHÉANCES_SIMULTANÉES", "sortie temporelle à 17:00 : une seule clôture")

    def _open_at_end(self, end: datetime) -> None:
        """Position still open at the explicit end: nothing is closed, priced or invented (sheet §6.3)."""
        position, last = self.position, self._last_tick
        if position is None or last is None:
            return
        kind = classify_silence(last.ts_utc, end, self.day02.interruption_threshold, self.config.documented_closures)
        self.silence_at_end = {
            "last_quote_utc": last.ts_utc,
            "end_of_study_utc": end,
            "duration": end - last.ts_utc,
            "kind": kind,
            "in_progress": True,
        }
        if kind is Silence.UNEXPLAINED:
            span = f"{last.ts_utc.isoformat()} → en cours à la fin de l'étude ({end.isoformat()})"
            position.unobservable_crossings.append(span)
            self._log(end, "INTERRUPTION_EN_COURS", f"{span} : transaction conservée, indéterminée, valorisée")
        due = self._due
        if due is not None and due.utc < end:
            self.unexecuted_closing = (due.utc, due.reason)
            self._log(end, "CLÔTURE_NON_EXÉCUTÉE", f"{due.reason} due à {due.utc.isoformat()}, aucun tick postérieur")


def _london_days(start: datetime, end: datetime) -> list[date]:
    """London calendar dates touching [start, end)."""
    first, last = start.astimezone(LONDON).date(), end.astimezone(LONDON).date()
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]
