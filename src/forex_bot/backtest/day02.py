"""DAY_02 rules: continuation after an impulse and a flag (docs/strategies/DAY_02_FLAG_CONTINUATION.md).

Sheet frozen by ADR-028 (ASSUMP-029), chronology and reference values of ADR-027, quality convention
of ADR-021 extended to DAY_02 by ADR-026. Times of the sheet are Europe/London; the conversion to
UTC goes through the session date only, never through prices.

Everything here reads candles only, never ticks nor positions: `configuration_from` gives the path
of one configuration from a resume state (no configuration, no entry, no position). The engine, the
future availability study and the per-configuration control share it, which keeps them consistent;
it is not, on its own, an independent check of the rule (tests compare it with explicit values).

The order of the high and the low inside a candle is never known and never assumed: rules on two
extremes need two different candles, and a candle touching two thresholds is settled by a fixed
priority (depth first). Research only: nothing here sends an order.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from forex_bot.backtest.day01 import M5, M15, bar_ok, london
from forex_bot.risk import Side


class Trigger(StrEnum):
    """Unit on which the flag exit, the depth after the flag and its extreme are read (sheet §3.1)."""

    M5 = "M5"  # reference H1 -> M15 -> M5
    M15 = "M15"  # preregistered simpler comparison "H1 -> M15"


@dataclass(frozen=True)
class Day02Params:
    """Values of the frozen sheet (§5, §6, §12); none was tuned on data."""

    window: int = 4  # M15 of the impulse window (1 h)
    impulse_start: time = time(7)  # first M15 of an impulse window starts at 07:00 London or later
    last_recognition: time = time(14, 15)  # t_j from 08:00 to 14:15 included
    last_flag: time = time(14, 45)  # F at 14:45 at the latest
    last_decision: time = time(15)  # D at 15:00 at the latest (cap of the deadline)
    min_amplitude: Decimal = Decimal("1.5")  # bid_close_j - O >= 1.5 x A
    strong_close: Decimal = Decimal("0.25")  # bid_close_j >= E - 0.25 x I
    max_impulse: int = 6  # M15 from o to p, extensions included
    max_depth: Decimal = Decimal("0.5")  # x I below E
    min_pause: int = 2  # pause candles after the last peak
    max_pause: timedelta = timedelta(minutes=90)  # exit candle ends at end(p) + 90 min at the latest
    exit_margin: Decimal = Decimal("0.1")  # x A beyond E
    stop_margin: Decimal = Decimal("0.25")  # x A beyond the flag extreme
    entry_validity: timedelta = timedelta(minutes=5)  # ]D, D + 5 min]
    time_exit: timedelta = timedelta(hours=2)  # after the execution
    liquidation: time = time(17)
    # ADR-021 extended by ADR-026: interruption = silence strictly longer than 5 min of expected-open
    # time, for pending entries and open positions. The H1 ATR keeps the H1 convention (ResearchConfig).
    interruption_threshold: timedelta = timedelta(minutes=5)
    atr_period: int = 14
    trigger: Trigger = Trigger.M5

    @property
    def trigger_step(self) -> timedelta:
        return M5 if self.trigger is Trigger.M5 else M15


# Reasons an examined M15 does not recognise an impulse (the search goes on), sheet §9.
WINDOW_DATA = "M15 absente, non OK ou avant 07:00 dans la fenêtre d'impulsion"
ATR_UNAVAILABLE = "ATR H1 non calculable"
ORDER = "ordre des extrêmes non établi (o ≥ p)"
PEAK_BEFORE_END = "sommet antérieur à la dernière bougie (p < j)"
AMPLITUDE = "amplitude insuffisante"
WEAK_CLOSE = "clôture non forte"
AMBIGUOUS = "cas ambigu : hausse et baisse à la fois"

# End of a configuration, one cause, the first that occurs (sheet §9).
FLAG_DATA = "données inutilisables pendant le drapeau"
PROLONGED = "impulsion prolongée sans pause"
TOO_DEEP = "repli trop profond"
TOO_LONG = "consolidation trop longue"
WINDOW_END = "fin de fenêtre"
EXIT = "sortie confirmée"  # an instant D, not an entry

# At D (sheet §5.6), first refusal in this order.
POSITION_OPEN = "position DAY_02 déjà ouverte ou entrée en attente"
MARKET_CLOSED = "marché fermé à D"
NO_QUOTE = "absence de cotation à D"
STOP_INADMISSIBLE = "stop non admissible"
TARGET_PASSED = "cible déjà dépassée à D"
SIZE_REFUSED = "taille minimale supérieure au budget"
ENTRY_DECIDED = "ENTRÉE_DÉCIDÉE"

# Outcome of a decided entry (sheet §9).
EXECUTED = "EXÉCUTÉE"
STOP_AT_EXECUTION = "STOP_DÉPASSÉ_À_L'EXÉCUTION"
TARGET_AT_EXECUTION = "CIBLE_ATTEINTE_À_L'EXÉCUTION"
REJECTED_AT_EXECUTION = "ENTRÉE_REJETÉE"  # only under StopAtExecution.REJECT (variant)
EXPIRED = "ENTRÉE_EXPIRÉE"
CANCELLED_INTERRUPTION = "ENTRÉE_ANNULÉE_INTERRUPTION"

# Closing orders (sheet §6.3): the first deadline reached; equality gives LIQUIDATION_17H.
TIME_EXIT = "SORTIE_TEMPORELLE"
LIQUIDATION = "LIQUIDATION_17H"

# What authorises a resume of the search (sheet §5.7, §10.1).
SESSION_START = "début de séance"
POSITION_CLOSED = "clôture de la position"
NO_SESSION = "pas de séance : jour férié probable"


def session_day(day: date) -> bool:
    """London weekday other than 25 December and 1 January (sheet §5)."""
    return day.weekday() < 5 and (day.month, day.day) not in {(12, 25), (1, 1)}


def ceil_m15(moment: datetime) -> datetime:
    """First M15 boundary at or after `moment` (UTC grid; London offsets are whole hours)."""
    floor = moment.replace(minute=moment.minute - moment.minute % 15, second=0, microsecond=0)
    return floor if floor == moment else floor + M15


@dataclass(frozen=True)
class Examined:
    """One M15 close examined for an impulse that did not open a configuration."""

    t_utc: datetime
    cause: str  # common cause, or "hausse : ... ; baisse : ..."


@dataclass
class Configuration:
    """Path of one configuration, from the recognition of its impulse to its end (candles only)."""

    side: Side
    recognised_utc: datetime  # t_j
    atr: Decimal  # A, on the last H1 ended by the start of the impulse window
    origin: Decimal  # O
    origin_start: datetime  # candle o
    peak: Decimal  # E, last peak
    peak_start: datetime  # candle p, last peak
    extensions: list[datetime] = field(default_factory=list)  # starts of the extension M15
    pause_starts: list[datetime] = field(default_factory=list)  # pause M15 after the last peak
    flag_utc: datetime | None = None  # F
    deadline_utc: datetime | None = None  # Δ, frozen at F
    outcome: str | None = None  # end cause, EXIT included
    ended_utc: datetime | None = None  # instant the end is known (D for an exit)
    detail: str | None = None
    flag_extreme: Decimal | None = None  # FL (long, bid) or FH_ask (short) up to the exit candle
    stop: Decimal | None = None  # S, for an exit
    target: Decimal | None = None  # T, for an exit
    slope: Decimal | None = None  # (close of the last pause M15 - close of the first) / A
    last_examined_start: datetime | None = None  # start of the last candle read

    @property
    def amplitude(self) -> Decimal:
        """I = |E - O|."""
        return abs(self.peak - self.origin)

    @property
    def depth_limit(self) -> Decimal:
        """Long: E - 0.5 I (below it, the pullback is too deep); short: E + 0.5 I."""
        half = Decimal("0.5") * self.amplitude
        return self.peak - half if self.side is Side.LONG else self.peak + half

    @property
    def d_utc(self) -> datetime | None:
        return self.ended_utc if self.outcome == EXIT else None


@dataclass
class Search:
    """One search from a resume state: the M15 examined, then the configuration it opened, if any."""

    resume_utc: datetime
    examined: list[Examined] = field(default_factory=list)
    configuration: Configuration | None = None


# ATR H1 on the last H1 ended by `cutoff`, candle states as knowable at `known_at`.
AtrOf = Callable[[datetime, datetime], Decimal | None]


def _side_cause(side: Side, window: list[Mapping[str, Any]], a: Decimal, p: Day02Params) -> tuple[str | None, Any]:
    """Why `window` is not an impulse on `side` (None if it is), with (O, o, E, p) when it is."""
    long = side is Side.LONG
    lows, highs = [b["bid_low"] for b in window], [b["bid_high"] for b in window]
    if long:
        origin, peak = min(lows), max(highs)
        o = lows.index(origin)  # first candle reaching O
        k = len(highs) - 1 - highs[::-1].index(peak)  # last candle reaching E
    else:
        origin, peak = max(highs), min(lows)
        o = highs.index(origin)
        k = len(lows) - 1 - lows[::-1].index(peak)
    if not o < k:
        return ORDER, None
    if k != len(window) - 1:
        return PEAK_BEFORE_END, None  # restriction chosen for the reference (p = j), not implied by o < p
    close, amplitude = window[-1]["bid_close"], abs(peak - origin)
    move = close - origin if long else origin - close
    if move < p.min_amplitude * a:
        return AMPLITUDE, None
    strong = close >= peak - p.strong_close * amplitude if long else close <= peak + p.strong_close * amplitude
    if not strong:
        return WEAK_CLOSE, None
    return None, (origin, o, peak)


def configuration_from(
    resume_utc: datetime,
    day: date,
    m15: Mapping[datetime, Mapping[str, Any]],
    trigger_bars: Mapping[datetime, Mapping[str, Any]],
    atr_of: AtrOf,
    params: Day02Params,
) -> Search:
    """Path from a resume state at `resume_utc` (no configuration, entry or position) on session `day`.

    Only M15 starting at `resume_utc` or later and at 07:00 London or later can enter an impulse
    window: a candle never serves two configurations. Every event is dated by the close of the
    candle that reveals it (or by the deadline), from candles ended by then only.
    """
    p = params
    search = Search(resume_utc)
    first_start = max(ceil_m15(resume_utc), london(day, p.impulse_start))
    t = first_start + p.window * M15
    last = london(day, p.last_recognition)
    while t <= last:
        starts = [t - (p.window - i) * M15 for i in range(p.window)]
        bars = [m15.get(s) for s in starts]
        window = [b for b in bars if bar_ok(b) and b is not None]
        if len(window) != p.window:
            search.examined.append(Examined(t, WINDOW_DATA))
            t += M15
            continue
        a = atr_of(starts[0], t)
        if a is None or a <= 0:
            search.examined.append(Examined(t, ATR_UNAVAILABLE))
            t += M15
            continue
        long_cause, long_found = _side_cause(Side.LONG, window, a, p)
        short_cause, short_found = _side_cause(Side.SHORT, window, a, p)
        if long_found is not None and short_found is not None:
            search.examined.append(Examined(t, AMBIGUOUS))
            t += M15
            continue
        if long_found is None and short_found is None:
            search.examined.append(Examined(t, f"hausse : {long_cause} ; baisse : {short_cause}"))
            t += M15
            continue
        side = Side.LONG if long_found is not None else Side.SHORT
        origin, o, peak = long_found if long_found is not None else short_found
        config = Configuration(side, t, a, origin, starts[o], peak, starts[-1])
        search.configuration = config
        _follow(config, day, m15, trigger_bars, p)
        return search
    return search


def _deadline(config: Configuration, day: date, p: Day02Params) -> tuple[datetime, str]:
    """Δ = min(end(p) + 90 min, 15:00) and the cause of an expiry at Δ (window end when they coincide)."""
    by_pause, cap = config.peak_start + M15 + p.max_pause, london(day, p.last_decision)
    return (by_pause, TOO_LONG) if by_pause < cap else (cap, WINDOW_END)


def _end(config: Configuration, outcome: str, utc: datetime, detail: str | None = None) -> None:
    config.outcome, config.ended_utc, config.detail = outcome, utc, detail


def _follow(
    config: Configuration,
    day: date,
    m15: Mapping[datetime, Mapping[str, Any]],
    trigger_bars: Mapping[datetime, Mapping[str, Any]],
    p: Day02Params,
) -> None:
    """Flag formation on M15 (§5.3), then exit on the trigger unit (§5.4), deadlines (§5.5)."""
    long = config.side is Side.LONG
    last_flag = london(day, p.last_flag)
    pauses: list[Mapping[str, Any]] = []
    start = config.recognised_utc
    # Formation: the first rule that applies alone, values known before the candle.
    while True:
        end = start + M15
        deadline, cause = _deadline(config, day, p)
        if end > deadline:
            _end(config, cause, deadline)
            return
        if end > last_flag:
            _end(config, WINDOW_END, last_flag, "drapeau non formé à 14:45")
            return
        bar = m15.get(start)
        config.last_examined_start = start
        if not bar_ok(bar) or bar is None:
            _end(config, FLAG_DATA, end, f"M15 {start.isoformat()}, prix non lus")
            return
        limit = config.depth_limit  # old E and old I: priority of the invalidation over the extension
        if (long and bar["bid_low"] < limit) or (not long and bar["bid_high"] > limit):
            _end(config, TOO_DEEP, end, f"M15 {start.isoformat()}")
            return
        if (long and bar["bid_high"] > config.peak) or (not long and bar["bid_low"] < config.peak):
            config.peak = bar["bid_high"] if long else bar["bid_low"]
            config.peak_start = start
            config.extensions.append(start)
            pauses = []  # an extension candle is not a pause; only pauses after the last peak count
            if (config.peak_start - config.origin_start) / M15 + 1 > p.max_impulse:
                _end(config, PROLONGED, end)
                return
        else:
            pauses.append(bar)
            if len(pauses) == p.min_pause:
                config.flag_utc = end
                break
        start = end
    config.pause_starts = [b["start_utc"] for b in pauses]
    config.deadline_utc, cause = _deadline(config, day, p)
    config.slope = (pauses[-1]["bid_close"] - pauses[0]["bid_close"]) / config.atr
    extreme = min(b["bid_low"] for b in pauses) if long else max(b["ask_high"] for b in pauses)
    # Exit on the trigger unit, E, I and the deadline frozen at F; same rules on M5 and M15.
    step = p.trigger_step
    level = config.peak + p.exit_margin * config.atr if long else config.peak - p.exit_margin * config.atr
    start = config.flag_utc
    while True:
        end = start + step
        if end > config.deadline_utc:  # included bound: a close exactly at Δ can confirm
            _end(config, cause, config.deadline_utc)
            return
        bar = trigger_bars.get(start)
        config.last_examined_start = start
        if not bar_ok(bar) or bar is None:
            _end(config, FLAG_DATA, end, f"{p.trigger.value} {start.isoformat()}, prix non lus")
            return
        extreme = min(extreme, bar["bid_low"]) if long else max(extreme, bar["ask_high"])
        if (long and bar["bid_low"] < config.depth_limit) or (not long and bar["bid_high"] > config.depth_limit):
            _end(config, TOO_DEEP, end, f"{p.trigger.value} {start.isoformat()}")  # before the exit (§5.4)
            return
        if (long and bar["bid_close"] > level) or (not long and bar["bid_close"] < level):
            config.flag_extreme = extreme
            margin = p.stop_margin * config.atr
            config.stop = extreme - margin if long else extreme + margin
            amplitude = config.amplitude
            config.target = config.peak + amplitude if long else config.peak - amplitude
            _end(config, EXIT, end)
            return
        start = end


@dataclass(frozen=True)
class Closing:
    """How a closing order (time exit or 17:00 liquidation) ended, its quantities kept apart."""

    decided_utc: datetime  # its deadline
    order: str  # TIME_EXIT or LIQUIDATION
    closed_utc: datetime
    close_reason: str  # the order itself, or the stop / target / scenario that took precedence
    silence: timedelta | None  # wall-clock gap from the previous tick to the closing tick
    silence_kind: Any  # feed.Silence under the DAY_02 threshold
    coincident: bool = False  # the time exit fell exactly at 17:00: one closing, LIQUIDATION_17H

    @property
    def delay(self) -> timedelta:
        return self.closed_utc - self.decided_utc


@dataclass
class Attempt:
    """One search as the engine lived it: its resume state, the path, what happened at D and after."""

    day: date
    resume_utc: datetime
    resume_after: str  # what authorised this resume: session start, end cause, refusal, entry outcome, close
    search: Search
    at_d: str | None = None  # refusal at D or ENTRY_DECIDED
    decision: dict[str, Any] | None = None
    entry_outcome: str | None = None
    entry_outcome_utc: datetime | None = None
    ended_utc: datetime | None = None  # instant that authorises the next resume
    ended_by: str | None = None
    events: list[str] = field(default_factory=list)
