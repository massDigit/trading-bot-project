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
  for lack of quotes, without any invented price; the exploratory LATE configuration
  (DAY02_LATE_EXIT_CAMPAIGN.md) has no time exit and liquidates at 22:55 Europe/Paris instead;
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
import copy
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
    UNPLANNED_NIGHT,
    Attempt,
    Closing,
    Configuration,
    Context,
    Day02Params,
    Trigger,
    ceil_m15,
    configuration_from,
    liquidation_utc,
    session_day,
)
from forex_bot.backtest.day02_partials import (
    FINAL,
    MOVE_BREAK_EVEN,
    MOVE_TP1,
    PORTIONS,
    Leg,
    Plan,
    StopMove,
    ahead,
    build_plan,
    tighter,
)
from forex_bot.backtest.engine import (
    BacktestResult,
    DecisionRecord,
    EntryAction,
    PositionAction,
    ResearchConfig,
    S1Backtest,
    StopType,
    Trade,
    _PendingExit,
)
from forex_bot.backtest.feed import Silence, Tick, classify_silence
from forex_bot.backtest.s1 import EntrySignal, S1Params
from forex_bot.backtest.s2 import ContinuousWilderAtr, GapScenario, first_missing
from forex_bot.history.bars import Gap
from forex_bot.history.calendar import MarketState, market_state, trading_day
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
    unplanned_nights: list[datetime] = field(default_factory=list)  # NUIT_NON_PRÉVUE, by decision instant
    plans: list[Plan] = field(default_factory=list)  # partial exits campaign only (empty otherwise)


@dataclass(frozen=True)
class _Due:
    """The closing order of the open position: its deadline and its reason."""

    utc: datetime
    reason: str  # TIME_EXIT or the liquidation label of the parameters
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
        h4: Sequence[dict[str, Any]] = (),
        observe_counterfactual: bool = True,
    ) -> None:
        # No D1; H4 only for the H3 context of the exploratory campaign (unused by the reference).
        # S1 rules are never evaluated; the S1 parameters only carry the ATR period.
        super().__init__(
            [], [], ticks, gaps, S1Params(atr_period=params.atr_period), config, start_utc=start_utc, end_utc=end_utc
        )
        self.day02, self.scenario = params, scenario
        self.h1 = list(h1)
        self.h1_end = [b["end_utc"] for b in self.h1]
        if self.h1_end != sorted(self.h1_end):
            raise ValueError("bougies H1 attendues dans l'ordre chronologique")
        self.h1_atr = ContinuousWilderAtr(self.h1, params.atr_period)  # continuity of the expected H1
        self.context_h4 = list(h4)
        self.context_h4_end = [b["end_utc"] for b in self.context_h4]
        if self.context_h4_end != sorted(self.context_h4_end):
            raise ValueError("bougies H4 attendues dans l'ordre chronologique")
        if params.context is not Context.NONE and not self.context_h4:
            raise ValueError("contexte H4 demandé sans bougies H4")
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
        self._position_attempt: Attempt | None = None  # attempt of the open position, ended by its close
        self.unplanned_nights: list[datetime] = []  # decision instants of trades closed on a later trading day
        # Partial exits campaign: plan of the open position, every plan, passive counterfactual observers.
        self._plan: Plan | None = None
        self.plans: list[Plan] = []
        self.observe_counterfactual = observe_counterfactual
        self._shadows: list[_Shadow] = []

    # ------------------------------------------------------------------ public

    def run(self) -> Day02Result:
        p = self.day02
        starts = sorted(self.m15)
        start = self.start_utc or (starts[0] if starts else None)
        end = self.end_utc or (starts[-1] + timedelta(days=1) if starts else None)
        decided: datetime | None = None
        if start is not None and end is not None:
            for day in _london_days(start, end):
                if not start <= london(day, p.impulse_start) or liquidation_utc(day, p) > end:
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
            unplanned_nights=self.unplanned_nights,
            plans=self.plans,
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

    def context_at(self, cutoff: datetime, known_at: datetime) -> int | None:
        """H3: sign of SMA(n) minus its previous value on the H4 bid closes, i.e. of close(k) - close(k - n),
        where k is the last H4 ended by `cutoff`. The n + 1 H4 must be contiguous in the expected schedule
        and usable with states as knowable at `known_at`; otherwise None (context not computable)."""
        n = self.day02.context_period
        k = bisect.bisect_right(self.context_h4_end, cutoff) - 1
        if k - n < 0:
            return None
        bars = self.context_h4[k - n : k + 1]
        if first_missing(bars, bars[0]["start_utc"], bars[-1]["end_utc"]) is not None:
            return None
        config = self.config
        if not all(
            bar_state(b, known_at, self.gaps, config.gap_threshold, config.documented_closures).usable for b in bars
        ):
            return None
        diff = bars[-1]["bid_close"] - bars[0]["bid_close"]
        return 1 if diff > 0 else -1 if diff < 0 else 0

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
            search = configuration_from(resume, day, self.m15, self.trigger_bars, self.atr_at, p, self.context_at)
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
        # The close of the position ends the attempt (`_close`), even after the search has stopped.
        self._wait_flat(deadline, attempt.day)

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
        plan = self._plan
        if plan is not None and self.position is not None:  # a pending portion's level is reached
            price = self._exit_side(tick)
            return any(ahead(plan.side, price, plan.level(n)) for n in plan.pending())
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
            if self._shadows:
                self._follow_shadows(tick)  # a posteriori observers: they never change the replay
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
                self._take_targets(tick, "CIBLE")
            if self.position is not None and self._plan is not None:
                self._protect(tick)  # decided on this quote, in force from the next one
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
                self._take_targets(tick, "CIBLE_APRÈS_FERMETURE")
            return
        position.unobservable_crossings.append(span)
        self._log(tick.ts_utc, "INTERRUPTION_POSITION", f"{span} : transaction conservée, indéterminée")
        accounted = f"trou {span}, comptabilisé au premier tick qui le clôt ({tick.ts_utc.isoformat()})"
        if self.scenario is GapScenario.STOP_FIRST:
            self._log(tick.ts_utc, "SCÉNARIO_B", accounted)
            self._close(
                tick,
                self._stop_level(),  # the stop in force before the gap, never one decided after it
                "STOP_SCÉNARIO_B",
                stop_triggered=True,
                hypotheses=[f"stop supposé franchi pendant le trou, avant la cible ; {accounted}"],
            )
        elif self.scenario is GapScenario.TARGET_FIRST and self._plan is not None:
            self._log(tick.ts_utc, "SCÉNARIO_C", accounted)
            self._scenario_c(tick, accounted)
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
            self._take_targets(tick, "CIBLE_APRÈS_INTERRUPTION")
        else:
            self._log(tick.ts_utc, "SCÉNARIO_A", f"{span} : franchissement possible non observé, position maintenue")

    def _open(self, tick: Tick) -> None:
        pending, target, attempt = self.pending_entry, self._pending_target, self._pending_attempt
        self._pending_target, self._pending_attempt = None, None
        self._position_attempt = attempt  # a fill then liquidation closes inside the S1 call below
        super()._open(tick)
        if self.position is None:
            self._position_attempt = None  # rejected, or already closed on this tick
        if pending is None:
            return
        position = self.position
        if position is not None and position.decided_utc == pending.decided_utc:
            outcome = EXECUTED
            self.target = target
            self._due = self._closing_due(position.entry_utc, attempt.day if attempt else None)
            self._plan = self._new_plan(position, target, attempt)
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
        """First deadline: time exit 2 h after the execution, or 17:00; equality gives LIQUIDATION_17H.
        Without a time exit (LATE), the liquidation of the session alone (22:55 Europe/Paris)."""
        if day is None:
            return None
        p = self.day02
        liquidation = liquidation_utc(day, p)
        if p.time_exit is not None and (time_exit := executed + p.time_exit) < liquidation:
            return _Due(time_exit, TIME_EXIT, False)
        coincident = p.time_exit is not None and executed + p.time_exit == liquidation
        return _Due(liquidation, p.liquidation_reason, coincident)

    def _close(
        self, tick: Tick, price: Decimal, reason: str, stop_triggered: bool, hypotheses: list[str] | None = None
    ) -> None:
        pending, due, attempt = self.pending_exit, self._due, self._position_attempt
        previous = self._last_tick  # still the tick before `tick`: it is updated after the events
        entered = self._open_position().entry_utc
        plan, self._plan = self._plan, None
        self.pending_exit = None  # the S1 engine would log a channel exit: DAY_02 has only its closing order
        super()._close(tick, price, reason, stop_triggered, hypotheses)
        self.target, self._due, self._position_attempt = None, None, None
        if plan is not None:
            self._end_plan(plan, self.trades[-1], tick, reason, stop_triggered, due)
        if pending is not None:
            self._record_closing(tick, pending, previous, reason, due)
        if trading_day(tick.ts_utc) != trading_day(entered):
            # Annotation, apart from the closing reason and from any interruption: counted once per trade.
            trade = self.trades[-1]
            self.unplanned_nights.append(trade.decided_utc)
            self._log(tick.ts_utc, UNPLANNED_NIGHT, f"clôture {reason} sur une journée de cotation postérieure")
            if attempt is not None:
                attempt.events.append(f"{UNPLANNED_NIGHT} : clôture {reason}")
        if attempt is not None and attempt.ended_utc is None:
            attempt.ended_utc, attempt.ended_by = tick.ts_utc, POSITION_CLOSED  # true instant of the exit tick

    # ------------------------------------------------------------------ partial exits and protection

    def _new_plan(self, position: Trade, target: Decimal | None, attempt: Attempt | None) -> Plan | None:
        p = self.day02
        config = attempt.search.configuration if attempt is not None else None
        if not (p.partial_exits or p.protection) or target is None or config is None or config.peak is None:
            return None
        plan = build_plan(
            position.decided_utc,
            position.side,
            position.size,
            position.entry_price,
            position.stop,
            config.peak,
            target,
            partial=p.partial_exits,
            protection=p.protection,
        )
        if plan is not None:
            self.plans.append(plan)
            quantities = ", ".join(f"{n} {q}" for n, q in plan.quantities.items())
            self._log(
                position.entry_utc,
                "PLAN_DE_SORTIE",
                f"TP1 {plan.tp1:.5f}, P {plan.progress:.5f}, TP2 {plan.tp2:.5f}, TP3 {plan.tp3:.5f} ; {quantities}",
            )
        return plan

    def _stop_level(self) -> Decimal:
        """The stop in force: the protected one under a plan, the technical stop otherwise."""
        plan = self._plan
        return plan.stop if plan is not None else self._open_position().stop

    def _crossed(self, tick: Tick) -> bool:
        if self._plan is None:
            return super()._crossed(tick)
        stop = self._plan.stop
        return tick.bid <= stop if self._open_position().side is Side.LONG else tick.ask >= stop

    def _stop_execution(self, tick: Tick) -> Decimal:
        if self._plan is None:
            return super()._stop_execution(tick)
        return self._plan.stop if self.config.stop_type is StopType.GUARANTEED else self._exit_side(tick)

    def _mark_reached(self, plan: Plan, price: Decimal, utc: datetime) -> None:
        for name in ("TP1", "P", "TP2", "TP3"):
            if name not in plan.reached and ahead(plan.side, price, plan.level(name)):
                plan.reached[name] = utc

    def _take_targets(self, tick: Tick, reason: str) -> None:
        """Reference: the whole position at the target. Under a plan: every pending portion whose level
        the quote reaches, in level order, at the price of the quote; the last one closes the position."""
        plan = self._plan
        if plan is None:
            self._close(tick, self._exit_side(tick), reason, stop_triggered=False)
            return
        price = self._exit_side(tick)
        self._mark_reached(plan, price, tick.ts_utc)
        for name in plan.pending():
            if self.position is None or not ahead(plan.side, price, plan.level(name)):
                break
            self._execute_portion(tick, plan, name, price, reason)

    def _execute_portion(self, tick: Tick, plan: Plan, name: str, price: Decimal, reason: str, **kw: Any) -> None:
        position = self._open_position()
        quantity = plan.quantities[name]
        plan.executed[name] = tick.ts_utc
        if quantity >= position.size:  # the last quantity: the position closes with this portion
            self._close(tick, price, reason, stop_triggered=False, hypotheses=kw.get("hypotheses"))
            plan.legs[-1].portion = name
            return
        leg = copy.copy(position)
        leg.size = quantity
        settled = self._settle(leg, tick, price, stop_triggered=False)
        self.balance += settled.net_account
        position.size -= quantity
        position.hypotheses.extend(kw.get("hypotheses") or [])
        plan.legs.append(
            Leg(
                tick.ts_utc,
                name,
                quantity,
                price,
                reason,
                plan.stop,
                settled.move_quote,
                dict(settled.lines),
                settled.rate,
                settled.fee,
                settled.net_account,
                self._nights(position, tick),
            )
        )
        self._sample(tick.ts_utc, tick)
        self._log(
            tick.ts_utc,
            "SORTIE_PARTIELLE",
            f"{name} {quantity} à {price} ({reason}), net {settled.net_account:.2f} EUR, solde {position.size}",
        )

    def _nights(self, position: Trade, tick: Tick) -> int:
        return (trading_day(tick.ts_utc) - trading_day(position.entry_utc)).days

    def _protect(self, tick: Tick) -> None:
        """Stop of the remaining quantity moved closer on the events observed on this quote; it acts from
        the next quote. Without protection, only the events are recorded."""
        plan = self._plan
        if plan is None:
            return
        price = self._exit_side(tick)
        self._mark_reached(plan, price, tick.ts_utc)
        if not plan.protection:
            return
        candidates = []
        if "P" in plan.reached:
            candidates.append((plan.entry_price, MOVE_BREAK_EVEN))
        if "TP2" in plan.reached:
            candidates.append((plan.tp1, MOVE_TP1))
        for stop, cause in candidates:
            if tighter(plan.side, stop, plan.stop):
                distance = abs(price - stop) / self.config.spec.pip_size
                plan.moves.append(StopMove(tick.ts_utc, plan.stop, stop, cause, distance))
                self._log(tick.ts_utc, "STOP_DÉPLACÉ", f"{plan.stop} → {stop} ({cause}), en vigueur au tick suivant")
                plan.stop = stop

    def _scenario_c(self, tick: Tick, accounted: str) -> None:
        """Target first under a plan: the next pending portion is supposed executed at its level during
        the gap (levels before it supposed reached); the remaining quantity stays open and the resume quote
        is then processed as any quote (stop in force, levels, protection from the next quote)."""
        plan = self._plan
        if plan is None or not plan.pending():
            return
        name = plan.pending()[0]
        level = plan.level(name)
        self._mark_reached(plan, level, tick.ts_utc)
        self._execute_portion(
            tick,
            plan,
            name,
            level,  # level only: no invisible price improvement
            "CIBLE_SCÉNARIO_C",
            hypotheses=[f"{name} supposé atteint pendant le trou, avant le stop ; {accounted}"],
        )

    def _end_plan(
        self, plan: Plan, trade: Trade, tick: Tick, reason: str, stop_triggered: bool, due: _Due | None
    ) -> None:
        """The last execution, then the economic transaction: the whole size and the sum of every leg
        (EUR exact; quote amounts expressed at the rate of the last execution)."""
        rate = trade.conversion_rate or Decimal(1)
        plan.legs.append(
            Leg(tick.ts_utc, FINAL, trade.size, trade.exit_price or Decimal(0), reason, plan.stop,
                trade.price_pnl_quote or Decimal(0), dict(trade.costs_quote), rate, trade.conversion_fee or Decimal(0),
                trade.net_account or Decimal(0), self._nights(trade, tick))
        )  # fmt: skip
        if stop_triggered and plan.protection and plan.stop != plan.initial_stop and self.observe_counterfactual:
            self._shadows.append(_Shadow(plan, copy.copy(trade), tick.ts_utc, due))
        if len(plan.legs) == 1:
            return  # one execution: the trade is already the whole transaction
        others = plan.legs[:-1]
        trade.size = plan.size
        # EUR amounts are exact sums of the legs; quote amounts are those EUR sums at the last rate.
        trade.price_pnl_quote = sum((leg.gross_account for leg in plan.legs), Decimal(0)) / rate
        lines: dict[str, Decimal] = {}
        for leg in plan.legs:
            for name, amount in leg.lines.items():
                lines[name] = lines.get(name, Decimal(0)) + amount * leg.rate / rate
        trade.costs_quote = lines
        trade.conversion_fee = sum((leg.fee for leg in plan.legs), Decimal(0))
        trade.net_account = sum((leg.net_account for leg in plan.legs), Decimal(0))
        trade.hypotheses.append(f"sorties partielles : {', '.join(f'{leg.portion} {leg.size}' for leg in others)}")

    def _follow_shadows(self, tick: Tick) -> None:
        """What the remaining quantity closed by a moved stop would have done under the initial stop:
        initial stop, pending levels, then the liquidation order; recorded on its plan only."""
        for shadow in list(self._shadows):
            if tick.ts_utc <= shadow.since:
                continue
            if shadow.step(tick, self):
                self._shadows.remove(shadow)

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


@dataclass
class _Shadow:
    """Remaining quantity closed by a moved stop, followed with the initial stop (a posteriori only)."""

    plan: Plan
    trade: Trade  # copy of the closed trade, remaining size and entry
    since: datetime  # its real close: the observer starts at the next quote
    due: _Due | None
    open: dict[str, Decimal] = field(default_factory=dict)  # pending portion -> quantity
    legs: list[tuple[str, Decimal, Decimal, str]] = field(default_factory=list)  # portion, size, price, how
    net: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        pending = self.plan.pending()
        self.open = {n: self.plan.quantities[n] for n in pending}
        left = self.trade.size - sum(self.open.values(), Decimal(0))
        if left > 0:  # the remaining size not attached to a pending portion stays to the deadline
            self.open[FINAL] = left

    def _settle(self, engine: Day02Backtest, tick: Tick, name: str, price: Decimal, how: str, stop: bool) -> None:
        leg = copy.copy(self.trade)
        leg.size = self.open.pop(name)
        settled = engine._settle(leg, tick, price, stop_triggered=stop)
        self.net += settled.net_account
        self.legs.append((name, leg.size, price, how))

    def step(self, tick: Tick, engine: Day02Backtest) -> bool:
        """True when the observer is closed. Initial stop first, then levels, then the liquidation."""
        plan = self.plan
        long = plan.side is Side.LONG
        price = tick.bid if long else tick.ask
        if (tick.bid <= plan.initial_stop) if long else (tick.ask >= plan.initial_stop):
            for name in list(self.open):
                self._settle(engine, tick, name, plan.initial_stop, "stop initial", True)
        else:
            for name in [n for n in PORTIONS if n in self.open]:
                if ahead(plan.side, price, plan.level(name)):
                    self._settle(engine, tick, name, price, name, False)
            if self.open and self.due is not None and tick.ts_utc > self.due.utc:
                for name in list(self.open):
                    self._settle(engine, tick, name, price, "échéance", False)
        if self.open:
            return False
        actual = plan.legs[-1].net_account
        plan.counterfactual = {
            "closed_utc": tick.ts_utc,
            "legs": self.legs,
            "net_account": self.net,
            "actual_net_of_remaining": actual,
            "difference": self.net - actual,  # > 0: continuation cut short; < 0: loss avoided
        }
        return True


def _london_days(start: datetime, end: datetime) -> list[date]:
    """London calendar dates touching [start, end)."""
    first, last = start.astimezone(LONDON).date(), end.astimezone(LONDON).date()
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]
