"""DAY_01 rules: London pre-open range, breakout and retest (docs/strategies/DAY_01_LONDON_RANGE.md).

Parameters frozen by ADR-022 (ASSUMP-027) and data conventions of ADR-021 (ASSUMP-028). Times of
the sheet are Europe/London; the conversion to UTC goes through the session date only, never
through prices. Research only: nothing here sends an order.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from forex_bot.backtest.feed import Silence
from forex_bot.history.calendar import MarketState, market_state, trading_day
from forex_bot.risk import Side

LONDON = ZoneInfo("Europe/London")
M5 = timedelta(minutes=5)
M15 = timedelta(minutes=15)


class Trigger(StrEnum):
    """Unit of the retest, invalidation, confirmation and stop (sheet §3.1)."""

    M5 = "M5"  # reference H4 -> M15 -> M5
    M15 = "M15"  # preregistered simpler comparison "H4 -> M15, retest and confirmation on M15"


@dataclass(frozen=True)
class Day01Params:
    """Values of the frozen sheet (§4, §5, §11); none was tuned on data."""

    range_start: time = time(1)  # 28 M15 of [01:00, 08:00) London
    freeze: time = time(8)  # G
    last_breakout_start: time = time(10, 45)  # breakout M15 closes from 08:15 to 11:00
    breakout_margin: Decimal = Decimal("0.1")  # x A beyond the range bound
    zone_half_width: Decimal = Decimal("0.1")  # x A around the broken bound
    retest_delay: timedelta = timedelta(minutes=60)  # confirming M5 ends at K + 60 min at the latest
    stop_margin: Decimal = Decimal("0.25")  # x A beyond the retest extreme
    reward_ratio: Decimal = Decimal("1.5")  # k, price distances estimated at D
    min_width: Decimal = Decimal("0.5")  # H / A
    max_width: Decimal = Decimal("2")
    entry_validity: timedelta = timedelta(minutes=5)  # ]D, D + 5 min]
    liquidation: time = time(16)
    # ADR-021: an interruption is a silence strictly longer than 5 min of expected-open time, for
    # pending entries and open positions alike. The H4 ATR keeps its own rules (ResearchConfig).
    interruption_threshold: timedelta = timedelta(minutes=5)
    atr_period: int = 14
    # Same rules and same 60 min delay on M15: first confirmation at K + 15 min, entry still valid 5 min.
    trigger: Trigger = Trigger.M5

    @property
    def trigger_step(self) -> timedelta:
        return M5 if self.trigger is Trigger.M5 else M15

    @property
    def range_slots(self) -> int:
        return int((datetime.combine(date.min, self.freeze) - datetime.combine(date.min, self.range_start)) / M15)


def london(day: date, moment: time) -> datetime:
    """UTC instant of a London wall-clock time on the session date."""
    return datetime.combine(day, moment, tzinfo=LONDON).astimezone(UTC)


def sessions(start: datetime, end: datetime, params: Day01Params | None = None) -> list[date]:
    """London weekdays whose range start lies in [start, end)."""
    range_start = (params or Day01Params()).range_start
    day, days = start.astimezone(LONDON).date() - timedelta(days=1), []
    while london(day, time(0)) < end:
        if day.weekday() < 5 and start <= london(day, range_start) < end:
            days.append(day)
        day += timedelta(days=1)
    return days


def session_open(day: date, params: Day01Params) -> bool:
    """A session exists if the market is expected open over the whole range window (sheet §4)."""
    cursor, end = london(day, params.range_start), london(day, params.freeze)
    while cursor < end:
        if market_state(cursor) is not MarketState.OPEN:
            return False
        cursor += M15
    return True


def bar_ok(bar: Mapping[str, Any] | None) -> bool:
    """`OK` under the DAY_01 convention: present and complete at its close (ADR-021). Holidays,
    closures, empty or invalid-only slots, empty sub-slots and silences > 5 min are never OK."""
    return bar is not None and bool(bar["complete_at_close"])


# First blocking reason of a session, in the order of the sheet §8.
NO_SESSION = "pas de séance : jour férié probable ou fermeture"
RANGE_INCOMPLETE = "range incomplet : M15 absente ou non OK dans la fenêtre"
ATR_UNAVAILABLE = "ATR H4 non calculable"
RANGE_WIDTH = "range hors largeur admissible"
BREAKOUT_DATA = "données inutilisables pendant la recherche de cassure"
NO_BREAKOUT = "aucune cassure confirmée à 11:00"
RETEST_DATA = "données inutilisables pendant le retest"
INVALIDATED = "invalidation (fausse cassure)"
RETEST_TIMEOUT = "délai de retest dépassé"
POSITION_OPEN = "position DAY_01 déjà ouverte"
MARKET_CLOSED = "marché fermé à D"
NO_QUOTE = "absence de cotation à D"
STOP_INADMISSIBLE = "stop non admissible"
SIZE_REFUSED = "taille minimale supérieure au budget"
ABSTENTIONS = (
    NO_SESSION,
    RANGE_INCOMPLETE,
    ATR_UNAVAILABLE,
    RANGE_WIDTH,
    BREAKOUT_DATA,
    NO_BREAKOUT,
    RETEST_DATA,
    INVALIDATED,
    RETEST_TIMEOUT,
    POSITION_OPEN,
    MARKET_CLOSED,
    NO_QUOTE,
    STOP_INADMISSIBLE,
    SIZE_REFUSED,
)

# Single outcome of a decided entry (sheet §8).
EXECUTED = "EXÉCUTÉE"
STOP_AT_EXECUTION = "STOP_DÉPASSÉ_À_L'EXÉCUTION"
TARGET_AT_EXECUTION = "CIBLE_ATTEINTE_À_L'EXÉCUTION"
REJECTED_AT_EXECUTION = "ENTRÉE_REJETÉE"  # only under StopAtExecution.REJECT (variant)
EXPIRED = "ENTRÉE_EXPIRÉE"
CANCELLED_INTERRUPTION = "ENTRÉE_ANNULÉE_INTERRUPTION"

# Liquidation (sheet §5). Three separate quantities are reported for every liquidation order: the
# delay after 16:00, the silence closed by the closing tick, and the closing reason.
LIQUIDATION = "LIQUIDATION_16H"  # closing reason: the 16:00 order itself closed the position
# Counted exactly when the 16:00 order closes the position on the first tick after a silence strictly
# longer than 5 min of expected-open time (unexplained). Former label LIQUIDATION_RETARDÉE (ADR-023).
LIQUIDATION_AFTER_INTERRUPTION = "LIQUIDATION_APRÈS_INTERRUPTION"
UNPLANNED_NIGHT = "NUIT_NON_PRÉVUE"  # the position closed on a later trading day than its 16:00 order


@dataclass(frozen=True)
class Liquidation:
    """How a 16:00 liquidation order ended, with its three quantities kept apart."""

    decided_utc: datetime  # 16:00:00 London
    closed_utc: datetime  # tick that closed the position, by the order or by a stop or target first
    close_reason: str  # LIQUIDATION_16H, or the stop or target reason that took precedence (§5, item 2)
    silence: timedelta | None  # wall-clock gap from the previous tick to the closing tick
    silence_kind: Silence  # under the DAY_01 threshold, strictly above 5 min of expected-open time

    @property
    def delay_after_16h(self) -> timedelta:
        return self.closed_utc - self.decided_utc

    @property
    def after_interruption(self) -> bool:
        """Definition of LIQUIDATION_APRÈS_INTERRUPTION; nothing else is counted under that label."""
        return self.close_reason == LIQUIDATION and self.silence_kind is Silence.UNEXPLAINED

    @property
    def unplanned_night(self) -> bool:
        return trading_day(self.closed_utc) != trading_day(self.decided_utc)


@dataclass
class Session:
    """What a session went through, in order; one first blocking reason at most."""

    day: date
    abstention: str | None = None
    detail: str | None = None
    previous_position: bool = False  # a DAY_01 position was still open at the freeze
    range: dict[str, Any] | None = None
    breakout: dict[str, Any] | None = None
    retest: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    entry_outcome: str | None = None
    events: list[str] = field(default_factory=list)

    def block(self, reason: str, detail: str | None = None) -> None:
        self.abstention, self.detail = reason, detail


def zone(side: Side, rh: Decimal, rl: Decimal, a: Decimal, params: Day01Params) -> tuple[Decimal, Decimal]:
    bound = rh if side is Side.LONG else rl
    half = params.zone_half_width * a
    return bound - half, bound + half


def touches(bar: Mapping[str, Any], low: Decimal, high: Decimal) -> bool:
    """Overlap of the bid extremes with the zone; it does not prove that a tick traded inside it."""
    return bool(bar["bid_low"] <= high and bar["bid_high"] >= low)
