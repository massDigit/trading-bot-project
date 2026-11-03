"""Offline S1 backtest engine (docs/strategies/S1_DONCHIAN.md §5, §6, §8, §10).

Chronology: the decision linked to H4 candle t is taken at D(t) = end_utc(t) + latency, with the
candles available at D(t) only, their state re-evaluated with the information available at D(t).
Exits are evaluated before entries. Orders execute at the first tick strictly after D(t): buy at
the ask, sell at the bid. Between decisions every tick is replayed in order to monitor the stop.

Ticks are consumed forward only, from any iterable (in-memory list or streaming reader); they must
be sorted by time. With a study window [start_utc, end_utc), decisions and ticks outside it are
ignored: candles before start_utc only feed the indicators (initialisation period).

Instant D: the state used by the decision (balance, positions, quotes, equity point) is the state
strictly before D. Ticks stamped exactly at D are replayed after the decision: they can trigger the
stop of a position still open, never execute an order decided at D (execution needs ts > D).

End of the study: the window end when given (ticks at or after it are never read), otherwise
max(last decision instant, last tick). Every remaining tick before it is replayed, then a final
point valued with the last tick is added at the end; the curve never goes back in time.

Event priority on a tick: a silence before it, then the stop of the open position, then a pending
channel exit, then a pending entry. A stop crossed on the tick that would have executed a channel
exit takes precedence: the resting stop order is reached first, the channel exit is dropped.

Accounting: the balance moves only when a trade is closed; the unrealized result is the liquidation
value of the open position at the last known tick (exit-side price, exit costs accrued so far,
conversion on the less favourable side); equity = balance + unrealized. Equity is sampled at every
H4 decision and every exit; a position still open at the end of the study is valued, never closed.

Sizing is fixed before the simulated sending, at D, on the equity estimated with the last tick
strictly before D (balance + unrealized, so a reversal accounts for the position being exited).
The executed entry is never removed afterwards: its risk at the executed price is recorded with
any overrun of the budget. Two losses are kept apart: the loss estimated at the stop after
execution (exposure of an open position) and the loss actually simulated and booked. A market
order whose first execution tick is already beyond its stop is handled by an explicit
`StopAtExecution` rule, never by silently dropping the order.

Research only: costs, sizes and conversions are explicit scenario parameters, never confirmed
broker values; an unknown cost blocks the entry instead of counting as zero. No order is ever
sent and nothing here talks to a broker.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum
from typing import Any

from forex_bot.backtest.bar_state import BarState, GapIndex, bar_state
from forex_bot.backtest.feed import Silence, Tick, classify_silence
from forex_bot.backtest.s1 import EntrySignal, Refusal, S1Params, WilderAtr, evaluate_entry, evaluate_exit
from forex_bot.history.bars import DEFAULT_GAP_THRESHOLD, Gap
from forex_bot.history.calendar import MarketState, market_state, trading_day
from forex_bot.instruments import EURUSD_MINI, ContractSpec
from forex_bot.market import Quote
from forex_bot.risk import (
    CostModel,
    Holding,
    LossEstimate,
    Side,
    estimate_loss_per_contract,
    usd_to_eur_from_eurusd_bid,
)


class StopType(StrEnum):
    GUARANTEED = "GARANTI"  # executed at the stop level; premium booked separately when triggered
    NORMAL = "NORMAL"  # executed at the first observable exit-side price at or after the trigger


class StopAtExecution(StrEnum):
    """Market entry whose execution tick is already beyond the technical stop."""

    # Filled at the execution price, then liquidated at once at the exit-side price of the same
    # tick: the stop could not be attached on the right side, so no guarantee and no premium.
    FILL_THEN_LIQUIDATE = "EXÉCUTÉE_PUIS_LIQUIDÉE"
    # Modelled acceptance condition: the order carrying an invalid attached stop is rejected at
    # execution. Broker behaviour not confirmed (ASSUMP-008): a scenario, not a fact.
    REJECT = "REJETÉE_STOP_INVALIDE"


class ScenarioPolicy(StrEnum):
    """What an unobservable possible crossing is assumed to be, for ALL such events of a run."""

    NONE_TRIGGERED = "AUCUN_DÉCLENCHEMENT_NON_OBSERVABLE"  # H0 everywhere
    ALL_TRIGGERED = "TOUS_DÉCLENCHÉS"  # H1 everywhere


@dataclass(frozen=True)
class ResearchConfig:
    """Scenario parameters of a run. None of them is a confirmed IG value."""

    costs: CostModel  # every applicable cost must be explicit (ASSUMED); UNKNOWN blocks entries
    stop_type: StopType = StopType.GUARANTEED
    policy: ScenarioPolicy = ScenarioPolicy.NONE_TRIGGERED
    stop_at_execution: StopAtExecution = StopAtExecution.FILL_THEN_LIQUIDATE
    spec: ContractSpec = EURUSD_MINI  # contract size and pip from the demo observation (ASSUMP-005)
    min_size: Decimal = Decimal("0.1")  # scenario: unit and value unconfirmed (ASSUMP-005)
    size_increment: Decimal = Decimal("0.1")  # scenario: increment unknown (ASSUMP-004)
    initial_equity: Decimal = Decimal("2000")  # EUR, ADR-003
    risk_fraction: Decimal = Decimal("0.0025")  # of the up-to-date equity (proposal, cahier §8)
    estimated_nights: int = 1  # financing provision in the sizing estimate
    latency: timedelta = timedelta(0)  # L: candle available at end_utc + L
    gap_threshold: timedelta = DEFAULT_GAP_THRESHOLD
    documented_closures: frozenset[date] = frozenset()  # trading days with a cited closure source


@dataclass(frozen=True)
class EquityPoint:
    utc: datetime
    balance: Decimal  # EUR, realized
    unrealized: Decimal  # EUR, liquidation value of the open position (0 if flat)

    @property
    def equity(self) -> Decimal:
        return self.balance + self.unrealized


@dataclass
class Trade:
    side: Side
    size: Decimal  # contracts
    decided_utc: datetime
    entry_utc: datetime
    entry_price: Decimal
    stop: Decimal  # technical stop, never moved
    estimate: LossEstimate  # at the sizing quote, before the simulated sending
    risk_budget: Decimal  # EUR, equity estimated at D x risk fraction
    # EUR, "perte estimée au stop après exécution": size x loss per contract recomputed at the executed
    # price; None when the stop is already beyond the execution price (no stop loss to estimate).
    stop_loss_at_execution: Decimal | None
    exit_utc: datetime | None = None
    exit_price: Decimal | None = None  # execution price only; costs are booked separately
    exit_reason: str | None = None
    price_pnl_quote: Decimal | None = None  # USD, prices only
    costs_quote: dict[str, Decimal] = field(default_factory=dict)  # USD, one line per cost
    conversion_rate: Decimal | None = None  # USD -> EUR applied to the net result
    conversion_fee: Decimal | None = None  # EUR
    net_account: Decimal | None = None  # EUR, after costs and conversion
    unobservable_crossings: list[str] = field(default_factory=list)  # INDÉTERMINÉE if not empty
    hypotheses: list[str] = field(default_factory=list)
    liquidation_loss: Decimal | None = None  # EUR, simulated loss of an immediate liquidation at entry

    @property
    def indeterminate(self) -> bool:
        return bool(self.unobservable_crossings)

    @property
    def exposure(self) -> Decimal:
        """EUR compared with the budget: estimated stop loss after execution, else the liquidation loss."""
        if self.stop_loss_at_execution is not None:
            return self.stop_loss_at_execution
        return self.liquidation_loss or Decimal(0)

    @property
    def exposure_measure(self) -> str:
        if self.stop_loss_at_execution is not None:
            return "perte estimée au stop après exécution"
        return "perte simulée de la liquidation immédiate"

    @property
    def risk_overrun(self) -> Decimal:
        """EUR above the budget at the executed price; kept, never used to drop the trade."""
        return max(Decimal(0), self.exposure - self.risk_budget)

    @property
    def simulated_loss(self) -> Decimal | None:
        """EUR actually booked as a loss when the trade is closed (0 for a gain); None while open."""
        return None if self.net_account is None else max(Decimal(0), -self.net_account)


@dataclass(frozen=True)
class JournalEntry:
    utc: datetime
    kind: str
    detail: str


@dataclass
class BacktestResult:
    config: ResearchConfig
    params: S1Params
    trades: list[Trade]
    journal: list[JournalEntry]
    equity_curve: list[EquityPoint]  # chronological; last point at end_utc
    open_trade: Trade | None  # still open at the end of the study, valued in the last point
    end_utc: datetime | None  # max(last decision instant, last tick); None without data

    @property
    def balance(self) -> Decimal:
        return self.equity_curve[-1].balance if self.equity_curve else self.config.initial_equity

    @property
    def unrealized(self) -> Decimal:
        return self.equity_curve[-1].unrealized if self.equity_curve else Decimal(0)

    @property
    def equity(self) -> Decimal:
        return self.balance + self.unrealized


@dataclass(frozen=True)
class _Settlement:
    move_quote: Decimal  # USD, prices only
    lines: dict[str, Decimal]  # USD, one line per cost
    rate: Decimal  # USD -> EUR
    fee: Decimal  # EUR
    net_account: Decimal  # EUR


@dataclass(frozen=True)
class _PendingEntry:
    decided_utc: datetime
    signal: EntrySignal
    size: Decimal
    estimate: LossEstimate
    budget: Decimal


@dataclass(frozen=True)
class _PendingExit:
    decided_utc: datetime
    reason: str


class S1Backtest:
    """One trajectory: one stop type, one scenario policy. Run several configs for scenarios."""

    def __init__(
        self,
        h4: Sequence[dict[str, Any]],
        d1: Sequence[dict[str, Any]],
        ticks: Iterable[Tick],
        gaps: Sequence[Gap],
        params: S1Params,
        config: ResearchConfig,
        *,
        start_utc: datetime | None = None,
        end_utc: datetime | None = None,
    ) -> None:
        self.h4, self.d1, self.params, self.config = h4, d1, params, config
        if start_utc is not None and end_utc is not None and start_utc >= end_utc:
            raise ValueError("fenêtre d'étude vide")
        self.start_utc, self.end_utc = start_utc, end_utc
        self._ticks: Iterator[Tick] = iter(ticks)
        self._peeked: Tick | None = None
        self._exhausted = False
        self.gaps = GapIndex(gaps)
        self.h4_available = [b["end_utc"] + config.latency for b in h4]
        self.d1_available = [b["end_utc"] + config.latency for b in d1]
        if self.h4_available != sorted(self.h4_available) or self.d1_available != sorted(self.d1_available):
            raise ValueError("bougies attendues dans l'ordre chronologique")
        self.atr = WilderAtr(h4, params.atr_period)
        self.balance = config.initial_equity
        self.trades: list[Trade] = []
        self.journal: list[JournalEntry] = []
        self.curve: list[EquityPoint] = []
        self.position: Trade | None = None
        self.pending_entry: _PendingEntry | None = None
        self.pending_exit: _PendingExit | None = None
        self._last_tick: Tick | None = None

    # ------------------------------------------------------------------ public

    def run(self) -> BacktestResult:
        decided: datetime | None = None
        for t, decision in enumerate(self.h4_available):
            if not self._in_window(decision):
                continue  # before start: initialisation only; at or after end: outside the study
            self._advance(decision, inclusive=False)  # state strictly before D
            self._sample(decision, self._last_tick)
            self._decide(t, decision)
            decided = decision
        if self.end_utc is not None:
            end: datetime | None = self.end_utc
            self._advance(self.end_utc, inclusive=False)  # the window excludes its end
        else:
            self._advance(None, inclusive=True)
            instants = [m for m in (decided, self._last_tick.ts_utc if self._last_tick else None) if m is not None]
            end = max(instants, default=None)
        if end is not None:
            self._sample(end, self._last_tick)
        return BacktestResult(self.config, self.params, self.trades, self.journal, self.curve, self.position, end)

    def _in_window(self, moment: datetime) -> bool:
        return (self.start_utc is None or moment >= self.start_utc) and (self.end_utc is None or moment < self.end_utc)

    # ------------------------------------------------------------------ decisions

    def _log(self, utc: datetime, kind: str, detail: str) -> None:
        self.journal.append(JournalEntry(utc, kind, detail))

    def _decide(self, t: int, decision: datetime) -> None:
        h4_cache: dict[int, BarState] = {}
        d1_cache: dict[int, BarState] = {}

        def state(bars: Sequence[dict[str, Any]], cache: dict[int, BarState], i: int) -> BarState:
            if i not in cache:
                cache[i] = bar_state(
                    bars[i], decision, self.gaps, self.config.gap_threshold, self.config.documented_closures
                )
            return cache[i]

        def h4_state(i: int) -> BarState:
            return state(self.h4, h4_cache, i)

        def d1_state(i: int) -> BarState:
            return state(self.d1, d1_cache, i)

        exiting = False
        if self.position is not None:
            exit_now = evaluate_exit(t, self.position.side, self.h4, h4_state, self.params)
            if isinstance(exit_now, Refusal):
                self._log(decision, "SORTIE_NON_CALCULABLE", exit_now.reason)
            elif exit_now:
                self.pending_exit = _PendingExit(decision, "SORTIE_CANAL")
                self._log(decision, "SORTIE_DÉCIDÉE", "clôture bid au-delà du canal de sortie")
                exiting = True
            if not exiting:
                return  # one S1 position at a time: no new entry while one is open

        context = bisect.bisect_right(self.d1_available, decision) - 1
        result = evaluate_entry(
            t, self.h4, h4_state, self.atr, self.d1, context if context >= 0 else None, d1_state, self.params
        )
        if result is None:
            return
        if isinstance(result, Refusal):
            self._log(decision, "ABSTENTION", result.reason)
            return
        if market_state(decision) is not MarketState.OPEN:
            self._log(decision, "SIGNAL_EXPIRÉ", f"{result.side.value} : marché fermé à l'instant de décision")
            return
        self._size(decision, result)

    def _size(self, decision: datetime, signal: EntrySignal) -> None:
        config = self.config
        last = self._last_tick  # last tick strictly before D: the replay stopped there
        if last is None:
            self._log(decision, "ABSTENTION", "aucune cotation connue à l'instant de décision")
            return
        try:
            estimate = self._loss_estimate(signal.side, signal.stop, last)
        except ValueError as exc:
            self._log(decision, "ABSTENTION", f"estimation impossible : {exc}")
            return
        if estimate.excluded_unknown:
            self._log(
                decision, "ABSTENTION", "coût inconnu, jamais compté zéro : " + ", ".join(estimate.excluded_unknown)
            )
            return
        equity = self.balance + self._unrealized(last)  # a reversal counts the position being exited
        budget = equity * config.risk_fraction
        units = (budget / estimate.loss_account_per_contract / config.size_increment).to_integral_value(ROUND_FLOOR)
        size = units * config.size_increment
        if size < config.min_size:
            self._log(decision, "ABSTENTION", f"taille minimale {config.min_size} > taille permise {size}")
            return
        self.pending_entry = _PendingEntry(decision, signal, size, estimate, budget)
        self._log(
            decision,
            "ENTRÉE_DÉCIDÉE",
            f"{signal.side.value} {size} contrat(s), stop {signal.stop}, fonds propres estimés {equity:.2f} EUR",
        )

    def _loss_estimate(self, side: Side, stop: Decimal, tick: Tick) -> LossEstimate:
        config = self.config
        return estimate_loss_per_contract(
            side=side,
            stop_price=stop,
            quote=Quote(tick.bid, tick.ask, "TRADEABLE", tick.ts_utc, delayed=False, source="historique"),
            spec=config.spec,
            conversion=usd_to_eur_from_eurusd_bid(tick.bid),
            costs=config.costs,
            holding=Holding.OVERNIGHT,
            nights=config.estimated_nights,
            guaranteed_stop=config.stop_type is StopType.GUARANTEED,
        )

    # ------------------------------------------------------------------ tick replay

    def _advance(self, until: datetime | None, *, inclusive: bool) -> None:
        while (tick := self._peek()) is not None:
            if until is not None and (tick.ts_utc > until if inclusive else tick.ts_utc >= until):
                return
            self._peeked = None
            previous = self._last_tick
            if self.position is not None and previous is not None:
                self._after_silence(previous, tick)
            if self.position is not None:
                self._observed_stop(tick)  # before a pending exit: the resting stop is reached first
            if self.pending_exit is not None and tick.ts_utc > self.pending_exit.decided_utc:
                pending, self.pending_exit = self.pending_exit, None
                if self.position is not None:
                    self._close(tick, self._exit_side(tick), pending.reason, stop_triggered=False)
            if self.pending_entry is not None and tick.ts_utc > self.pending_entry.decided_utc:
                self._open(tick)
            self._last_tick = tick

    def _peek(self) -> Tick | None:
        """Next tick of the window, read lazily; checks the chronological order."""
        while self._peeked is None and not self._exhausted:
            tick = next(self._ticks, None)
            if tick is None or (self.end_utc is not None and tick.ts_utc >= self.end_utc):
                self._exhausted = True  # nothing at or after the window end is ever read
            elif self.start_utc is not None and tick.ts_utc < self.start_utc:
                continue
            else:
                if self._last_tick is not None and tick.ts_utc < self._last_tick.ts_utc:
                    raise ValueError(f"ticks hors ordre chronologique à {tick.ts_utc.isoformat()}")
                self._peeked = tick
        return self._peeked

    def _open_position(self) -> Trade:
        if self.position is None:
            raise RuntimeError("aucune position ouverte")
        return self.position

    def _exit_side(self, tick: Tick) -> Decimal:
        return tick.bid if self._open_position().side is Side.LONG else tick.ask

    def _crossed(self, tick: Tick) -> bool:
        position = self._open_position()
        if position.side is Side.LONG:  # stop protecting a long position: triggered on the bid
            return tick.bid <= position.stop
        return tick.ask >= position.stop

    def _stop_execution(self, tick: Tick) -> Decimal:
        position = self._open_position()
        if self.config.stop_type is StopType.GUARANTEED:
            return position.stop
        return self._exit_side(tick)

    def _observed_stop(self, tick: Tick) -> None:
        if self._crossed(tick):
            self._close(tick, self._stop_execution(tick), "STOP_OBSERVÉ", stop_triggered=True)

    def _after_silence(self, previous: Tick, tick: Tick) -> None:
        position = self._open_position()
        kind = classify_silence(
            previous.ts_utc, tick.ts_utc, self.config.gap_threshold, self.config.documented_closures
        )
        if kind is Silence.NONE:
            return
        span = f"{previous.ts_utc.isoformat()} → {tick.ts_utc.isoformat()}"
        if self._crossed(tick):
            hypotheses = []
            if kind is Silence.UNEXPLAINED and self.config.stop_type is StopType.NORMAL:
                hypotheses.append(f"exécution supposée au premier prix observé après l'interruption {span}")
            reason = "STOP_FERMETURE_CONNUE" if kind is Silence.KNOWN_CLOSURE else "STOP_APRÈS_INTERRUPTION"
            self._close(tick, self._stop_execution(tick), reason, stop_triggered=True, hypotheses=hypotheses)
            return
        if kind is Silence.UNEXPLAINED:
            position.unobservable_crossings.append(span)
            if self.config.policy is ScenarioPolicy.ALL_TRIGGERED:
                self._close(
                    tick,
                    position.stop,  # normal stop: slippage booked separately as a cost
                    "STOP_SCÉNARIO_H1",
                    stop_triggered=True,
                    hypotheses=[f"déclenchement supposé pendant l'interruption {span}"],
                )
            else:
                self._log(tick.ts_utc, "SCÉNARIO_H0", f"franchissement possible non observable {span} : non déclenché")

    # ------------------------------------------------------------------ positions

    def _open(self, tick: Tick) -> None:
        pending, self.pending_entry = self.pending_entry, None
        if pending is None:
            return
        if self.position is not None:
            self._log(tick.ts_utc, "ENTRÉE_ANNULÉE", "position déjà ouverte")
            return
        signal = pending.signal
        long = signal.side is Side.LONG
        beyond = (long and tick.bid <= signal.stop) or (not long and tick.ask >= signal.stop)
        if beyond and self.config.stop_at_execution is StopAtExecution.REJECT:
            self._log(
                tick.ts_utc,
                "STOP_DÉPASSÉ_À_L'EXÉCUTION",
                f"{signal.side.value} : stop {signal.stop} déjà dépassé au premier prix ({StopAtExecution.REJECT})",
            )
            self._log(
                tick.ts_utc,
                "ENTRÉE_REJETÉE",
                "condition d'acceptation modélisée : stop attaché du mauvais côté au prix d'exécution "
                "(comportement courtier non confirmé, ASSUMP-008)",
            )
            return
        price = tick.ask if long else tick.bid
        self.position = Trade(
            signal.side,
            pending.size,
            pending.decided_utc,
            tick.ts_utc,
            price,
            signal.stop,
            pending.estimate,
            pending.budget,
            None,
        )
        if beyond:
            # No stop loss to estimate: the liquidation loss is the exposure; trade booked, overrun recorded.
            self._log(
                tick.ts_utc,
                "STOP_DÉPASSÉ_À_L'EXÉCUTION",
                f"{signal.side.value} : stop {signal.stop} déjà dépassé au premier prix "
                f"({StopAtExecution.FILL_THEN_LIQUIDATE})",
            )
            loss = -self._settle(self.position, tick, self._exit_side(tick), stop_triggered=False).net_account
            self.position.liquidation_loss = max(Decimal(0), loss)
            self._log_entry(tick, pending)
            self._close(
                tick,
                self._exit_side(tick),
                "STOP_FRANCHI_À_L'EXÉCUTION",
                stop_triggered=False,
                hypotheses=["stop non attachable au prix d'exécution : liquidation immédiate, sans garantie"],
            )
            return
        self.position.stop_loss_at_execution = (
            pending.size * self._loss_estimate(signal.side, signal.stop, tick).loss_account_per_contract
        )
        self._log_entry(tick, pending)

    def _log_entry(self, tick: Tick, pending: _PendingEntry) -> None:
        position = self._open_position()
        self._log(tick.ts_utc, "ENTRÉE", f"{position.side.value} {position.size} à {position.entry_price}")
        if position.risk_overrun:
            self._log(
                tick.ts_utc,
                "DÉPASSEMENT_RISQUE",
                f"{position.exposure_measure} {position.exposure:.2f} EUR > budget {pending.budget:.2f} EUR "
                f"(+{position.risk_overrun:.2f}) : exécution conservée",
            )

    def _settle(self, trade: Trade, tick: Tick, price: Decimal, stop_triggered: bool) -> _Settlement:
        """Result of closing `trade` at `price` on `tick`: prices, one line per cost, conversion."""
        config, spec = self.config, self.config.spec
        units = trade.size * spec.contract_size
        move = price - trade.entry_price if trade.side is Side.LONG else trade.entry_price - price
        costs = config.costs
        lines: dict[str, Decimal] = {}

        def value(name: str, amount: Decimal | None) -> Decimal:
            if amount is None:  # cannot happen: the entry required every applicable cost
                raise ValueError(f"coût {name} inconnu à la sortie")
            return amount

        lines["glissement"] = value("glissement", costs.slippage_pips.value) * spec.pip_size * units
        lines["commission"] = value("commission", costs.commission_per_contract.value) * trade.size
        nights = (trading_day(tick.ts_utc) - trading_day(trade.entry_utc)).days
        if nights:
            per_night = value("financement", costs.financing_per_contract_per_night.value)
            lines["financement overnight"] = per_night * trade.size * nights
        if stop_triggered and config.stop_type is StopType.GUARANTEED:
            premium = value("prime", costs.guaranteed_stop_premium_per_contract.value)
            lines["prime de stop garanti"] = premium * trade.size
        net_quote = move * units - sum(lines.values(), Decimal(0))
        # Research convention: the less favourable side for the result (1/bid for a loss, 1/ask for a gain).
        rate = Decimal(1) / (tick.bid if net_quote < 0 else tick.ask)
        gross_account = net_quote * rate
        fee = abs(gross_account) * value("conversion", costs.conversion_fee_rate.value)
        return _Settlement(move * units, lines, rate, fee, gross_account - fee)

    def _unrealized(self, tick: Tick | None) -> Decimal:
        """Liquidation value of the open position at `tick` (exit-side price, no stop premium)."""
        if self.position is None or tick is None:
            return Decimal(0)
        return self._settle(self.position, tick, self._exit_side(tick), stop_triggered=False).net_account

    def _sample(self, utc: datetime, tick: Tick | None) -> None:
        self.curve.append(EquityPoint(utc, self.balance, self._unrealized(tick)))

    def _close(
        self, tick: Tick, price: Decimal, reason: str, stop_triggered: bool, hypotheses: list[str] | None = None
    ) -> None:
        trade = self._open_position()
        settled = self._settle(trade, tick, price, stop_triggered)
        trade.exit_utc, trade.exit_price, trade.exit_reason = tick.ts_utc, price, reason
        trade.price_pnl_quote, trade.costs_quote = settled.move_quote, settled.lines
        trade.conversion_rate, trade.conversion_fee = settled.rate, settled.fee
        trade.net_account = settled.net_account
        trade.hypotheses.extend(hypotheses or [])
        self.balance += settled.net_account
        self.trades.append(trade)
        self.position = None
        self._sample(tick.ts_utc, tick)
        self._log(tick.ts_utc, "SORTIE", f"{reason} à {price}, résultat net {trade.net_account:.2f} EUR")
        if self.pending_exit is not None:
            self.pending_exit = None
            self._log(tick.ts_utc, "SORTIE_CANAL_ABANDONNÉE", f"{reason} avant l'exécution de la sortie au canal")
