"""DAY_01 data availability study (docs/experiments/DAY01_AVAILABILITY_2015_2021.md).

The unchanged DAY_01 engine runs over the M15/M5 candles and the H4 ATR with an empty tick feed and
stops at the confirmation: a subclass only replaces the entry decision, to record the instant D.
Nothing at or after D is evaluated (position, quote, stop, target, size, pending entry): a
confirmation is not an entry. The retest outcomes are read from the engine's own observation
(`Session.retest`), never from a copy of its rules.

One trajectory per trigger: the M5 reference (`Day01Params()`) and the preregistered M15
comparison (`Day01Params(trigger=Trigger.M15)`), every other parameter identical. Blocking checks
C1 to C10; on any failure the results are withheld and the command exits with code 2.

Research only: no tick is read, no order exists, 2022-2025 stays out of reach.
"""

from __future__ import annotations

import argparse
import bisect
import dataclasses
import itertools
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from forex_bot.backtest.bar_state import BarState, bar_state
from forex_bot.backtest.data import load_bars, load_gaps, require_development_window
from forex_bot.backtest.day01 import (
    ATR_UNAVAILABLE,
    BREAKOUT_DATA,
    INVALIDATED,
    LONDON,
    M15,
    NO_BREAKOUT,
    NO_SESSION,
    RANGE_INCOMPLETE,
    RANGE_WIDTH,
    RETEST_DATA,
    RETEST_TIMEOUT,
    Day01Params,
    Session,
    Trigger,
    london,
)
from forex_bot.backtest.day01_engine import Day01Backtest
from forex_bot.backtest.engine import ResearchConfig
from forex_bot.backtest.explore import RESEARCH_COSTS
from forex_bot.backtest.s2 import ContinuousWilderAtr
from forex_bot.history.bars import Gap
from forex_bot.history.calendar import NEW_YORK, Timeframe
from forex_bot.history.intraday import NO_TICK, NO_VALID_TICK, SUBSLOTS_FLAG, Content, Grid
from forex_bot.history.intraday_audit import end_check, provenance, sha256_file, tree_state
from forex_bot.risk import Side

SOURCE, INSTRUMENT = "dukascopy", "EURUSD"
TOOL = "forex-day01-availability"
GRID = {Trigger.M5: Grid.M5, Trigger.M15: Grid.M15}
# Audited DAY_01 candles (data bilan §8.1, ADR-021): checked before any read.
CANDLES_SHA256 = {
    Grid.M5: "9438774154972aafa2cc924cf6042e6ae2b3c97de23328644b7d54f3af50fb82",
    Grid.M15: "64b305201c2f8e48afd257048e07800cea1778e17228673b4c4af7c6a86a9db2",
}
GAP_FLAG = "trou de cotation >"
M15_US = int(M15 / timedelta(microseconds=1))
CODE_PATHS = ("src/", "pyproject.toml", "uv.lock")  # a change there during the run is blocking (C10)

# Exclusive outcomes, by stage (protocol §4.2); a session passing every stage is a confirmation.
STAGES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("jours_ouvrés", ("PAS_DE_SÉANCE",)),
    ("séances_attendues", ("RANGE_INCOMPLET",)),
    ("ranges_complets", ("ATR_NON_CALCULABLE",)),
    ("ranges_avec_atr", ("RANGE_TROP_ÉTROIT", "RANGE_TROP_LARGE")),
    ("ranges_admissibles", ("DONNÉES_CASSURE", "AUCUNE_CASSURE")),
    (
        "cassures",
        (
            "DONNÉES_RETEST",
            "INVALIDATION_AVANT_CONTACT",
            "INVALIDATION_APRÈS_CONTACT",
            "DÉLAI_SANS_CONTACT",
            "DÉLAI_CONTACT_SANS_CONFIRMATION",
        ),
    ),
)
CONFIRMED = "CONFIRMATION"
# Causes of an H4 ATR unavailable at the freeze, read from the H4 history and its state known then.
ATR_INITIAL = "amorçage : historique H4 initial insuffisant"
ATR_ABSENT_H4 = "interruption : H4 prévue absente"
ATR_UNUSABLE_H4 = "interruption : H4 inutilisable"
ATR_UNDETERMINED = "non déterminée"
ATR_AVAILABLE = "incohérence : ATR disponible au gel"  # blocking (C3)
INCONSISTENT = "INCOHÉRENT"
COMMON_OUTCOMES = frozenset(o for _, terminal in STAGES[:5] for o in terminal)  # stages 1-5 (check C5)


@dataclass(frozen=True)
class Anchors:
    """Values the study must find, from the audited data bilan (§8.2, §8.3); None skips a check."""

    expected_sessions: int | None = None
    incomplete_ranges: frozenset[date] | None = None
    data_outcomes: int | None = None  # data outcomes during the breakout search and the retest


ANCHORS_2015_2021 = Anchors(1816, frozenset({date(2015, 11, 10), date(2017, 1, 2), date(2021, 10, 12)}), 0)


def expected_params(trigger: Trigger) -> Day01Params:
    """C9: M5 reference `Day01Params()`, M15 comparison `Day01Params(trigger=Trigger.M15)`."""
    return Day01Params() if trigger is Trigger.M5 else Day01Params(trigger=Trigger.M15)


class AvailabilityBacktest(Day01Backtest):
    """The DAY_01 engine stopped at the confirmation: no entry is decided, nothing after D exists."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.confirmations: dict[date, datetime] = {}

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
        self.confirmations[day] = decision  # no quote, stop, target, size or pending entry

    def atr_cause(self, instant: datetime) -> tuple[str, str | None]:
        """Why the H4 ATR is unavailable at `instant` (the freeze), with the H4 concerned.

        Read from the H4 history and the state of each H4 known at `instant`, through a fresh
        `ContinuousWilderAtr` (same rules, no cache): the usable run that ends at the last H4 known
        starts at its anchor. Anchor 0: the run starts with the history, which is too short;
        otherwise the run follows an absent expected H4 or an unusable one. Anything else is left
        undetermined rather than attributed."""
        i = bisect.bisect_right(self.h4_available, instant) - 1
        if i < 0:
            return ATR_INITIAL, "aucune H4 disponible"
        cache: dict[int, BarState] = {}

        def state(j: int) -> BarState:
            if j not in cache:
                cache[j] = bar_state(
                    self.h4[j], instant, self.gaps, self.config.gap_threshold, self.config.documented_closures
                )
            return cache[j]

        probe = ContinuousWilderAtr(self.h4, self.day01.atr_period)
        value = probe.at(i, state)
        if value is not None:
            return (ATR_AVAILABLE if value > 0 else ATR_UNDETERMINED), f"ATR {value}"
        anchor = probe._anchor  # set by `at`: first H4 of the usable run ending at H4 i
        if anchor is None:
            return ATR_UNDETERMINED, None
        known = f"{i - anchor + 1} H4 utilisables depuis {self.h4[anchor]['start_utc'].isoformat()}"
        if anchor == 0:
            return ATR_INITIAL, known
        if anchor in probe._holes:
            return ATR_ABSENT_H4, f"H4 prévue absente avant {self.h4[anchor]['start_utc'].isoformat()} ; {known}"
        if not state(anchor - 1).usable:
            return ATR_UNUSABLE_H4, f"H4 {self.h4[anchor - 1]['start_utc'].isoformat()} inutilisable ; {known}"
        return ATR_UNDETERMINED, known


@dataclass
class Trajectory:
    params: Day01Params
    sessions: list[Session]
    confirmations: dict[date, datetime]
    outcomes: dict[date, str] = field(default_factory=dict)
    causes: dict[date, str] = field(default_factory=dict)
    cause_details: dict[date, str] = field(default_factory=dict)
    ticks_read: int = 0

    @property
    def trigger(self) -> Trigger:
        return self.params.trigger


def run_trajectory(
    m5: Sequence[dict[str, Any]],
    m15: Sequence[dict[str, Any]],
    h4: Sequence[dict[str, Any]],
    gaps: Sequence[Gap],
    config: ResearchConfig,
    params: Day01Params,
    start: datetime,
    end: datetime,
) -> Trajectory:
    engine = AvailabilityBacktest(m5, m15, h4, [], gaps, params, config, start_utc=start, end_utc=end)
    result = engine.run()
    trajectory = Trajectory(params, result.sessions, engine.confirmations)
    trajectory.ticks_read = 0 if engine._last_tick is None else 1
    m15_rows = {b["start_utc"]: b for b in m15}
    for session in result.sessions:
        atr: tuple[str, str | None] | None = None
        if session.abstention == ATR_UNAVAILABLE:
            atr = engine.atr_cause(london(session.day, params.freeze))
            if atr[1] is not None:
                trajectory.cause_details[session.day] = atr[1]
        outcome, cause = classify(session, engine.confirmations, m15_rows, None if atr is None else atr[0])
        trajectory.outcomes[session.day] = outcome
        if cause is not None:
            trajectory.causes[session.day] = cause
    return trajectory


def bar_cause(bar: dict[str, Any] | None) -> str:
    """Why a candle is not OK at its close, from its own flags (DAY_01 convention)."""
    if bar is None:
        return "absente"
    flags = bar["flags_at_close"]
    if any(NO_TICK in f or NO_VALID_TICK in f for f in flags):
        return "sans tick valide"
    silence, subslot = any(GAP_FLAG in f for f in flags), any(SUBSLOTS_FLAG in f for f in flags)
    if silence and subslot:
        return "silence et sous-créneau vide"
    if silence:
        return "silence > 5 min"
    if subslot:
        return "sous-créneau vide"
    return "autre : " + " ; ".join(flags)


def classify(
    session: Session,
    confirmations: dict[date, datetime],
    m15: dict[datetime, dict[str, Any]],
    atr_cause: str | None = None,
) -> tuple[str, str | None]:
    """Exclusive outcome of a session, read from what the engine recorded (no rule is re-applied).

    `atr_cause` comes from `AvailabilityBacktest.atr_cause`, at the freeze of the session."""
    reason = session.abstention
    if reason is None:
        return (CONFIRMED, None) if session.day in confirmations else (INCONSISTENT, "ni abstention ni confirmation")
    if reason == NO_SESSION:
        return "PAS_DE_SÉANCE", None
    if reason == RANGE_INCOMPLETE:
        first = datetime.fromisoformat((session.detail or "").rsplit(" : ", 1)[-1])
        return "RANGE_INCOMPLET", bar_cause(m15.get(first))
    if reason == ATR_UNAVAILABLE:
        return "ATR_NON_CALCULABLE", atr_cause or ATR_UNDETERMINED
    if reason == RANGE_WIDTH and session.range is not None:
        narrow = session.range["h_over_a"] < Day01Params().min_width
        return ("RANGE_TROP_ÉTROIT" if narrow else "RANGE_TROP_LARGE"), None
    if reason == BREAKOUT_DATA:
        return "DONNÉES_CASSURE", session.detail
    if reason == NO_BREAKOUT:
        return "AUCUNE_CASSURE", None
    contact = (session.retest or {}).get("contact_utc")
    if reason == RETEST_DATA:
        return "DONNÉES_RETEST", session.detail
    if reason == INVALIDATED:
        return ("INVALIDATION_AVANT_CONTACT" if contact is None else "INVALIDATION_APRÈS_CONTACT"), None
    if reason == RETEST_TIMEOUT:
        return ("DÉLAI_SANS_CONTACT" if contact is None else "DÉLAI_CONTACT_SANS_CONFIRMATION"), None
    return INCONSISTENT, reason  # an abstention at D cannot occur: the decision is never evaluated


# ---------------------------------------------------------------------------------------------- funnel


def funnel_stages(outcomes: dict[date, str], days: list[date]) -> list[dict[str, Any]]:
    """Stages in order: entering (the denominator), exclusive terminal outcomes, passing."""
    counts = Counter(outcomes[d] for d in days)
    entering, stages = len(days), []
    for name, terminal in STAGES:
        stopped = {o: counts.get(o, 0) for o in terminal}
        passing = entering - sum(stopped.values())
        stages.append({"stage": name, "entering": entering, "terminal": stopped, "passing": passing})
        entering = passing
    stages.append({"stage": "confirmations", "entering": entering, "confirmed": counts.get(CONFIRMED, 0)})
    return stages


def funnel(outcomes: dict[date, str]) -> dict[str, Any]:
    years: dict[int, list[date]] = defaultdict(list)
    for d in sorted(outcomes):
        years[d.year].append(d)
    return {
        "by_year": {str(y): funnel_stages(outcomes, days) for y, days in years.items()},
        "total": funnel_stages(outcomes, sorted(outcomes)),
    }


def conservation_errors(stages: list[dict[str, Any]]) -> list[str]:
    errors = []
    for before, after in itertools.pairwise(stages):
        if before["entering"] != before["passing"] + sum(before["terminal"].values()):
            errors.append(f"étape {before['stage']} : entrées ≠ issues + passages")
        if before["passing"] != after["entering"]:
            errors.append(f"étape {before['stage']} : passages ≠ entrées de l'étape suivante")
    last = stages[-1]
    if last["entering"] != last["confirmed"]:
        errors.append("cassures restantes ≠ confirmations")
    return errors


# ---------------------------------------------------------------------------------------------- descriptions


def summary(values: list[Decimal]) -> dict[str, str] | None:
    """Minimum, quartiles (nearest rank) and maximum; descriptive only, never a filter."""
    if not values:
        return None
    ordered = sorted(values)

    def rank(q: float) -> Decimal:
        return ordered[max(0, -(-int(q * 100) * len(ordered) // 100) - 1)]

    return {
        "n": str(len(ordered)),
        "min": f"{ordered[0]:.3f}",
        "q1": f"{rank(0.25):.3f}",
        "median": f"{rank(0.5):.3f}",
        "q3": f"{rank(0.75):.3f}",
        "max": f"{ordered[-1]:.3f}",
    }


def clocks(day: date) -> str:
    """GMT or BST at the freeze, and whether London and New York are off their usual 5 h apart."""
    moment = london(day, time(8))
    offset = moment.astimezone(LONDON).utcoffset() or timedelta(0)
    ny = moment.astimezone(NEW_YORK).utcoffset() or timedelta(0)
    season = "GMT" if offset == timedelta(0) else "BST"
    return f"{season}, décalage" if offset - ny != timedelta(hours=5) else season


def describe(t: Trajectory) -> dict[str, Any]:
    p, step = t.params, t.params.trigger_step
    by_clock: dict[str, Counter[str]] = defaultdict(Counter)
    ratios, atrs, distances = [], [], defaultdict(list)
    breakouts: Counter[str] = Counter()
    delays: dict[str, Counter[int]] = defaultdict(Counter)
    hours: dict[str, Counter[str]] = defaultdict(Counter)
    on_contact: Counter[str] = Counter()
    confirmed_by_side: Counter[str] = Counter()
    for s in t.sessions:
        outcome = t.outcomes[s.day]
        if outcome != "PAS_DE_SÉANCE":
            by_clock[clocks(s.day)]["séances_attendues"] += 1
        if outcome == CONFIRMED:
            by_clock[clocks(s.day)]["confirmations"] += 1
        if s.range is not None and s.range.get("h_over_a") is not None:
            ratios.append(s.range["h_over_a"])
            atrs.append(s.range["atr"] * 10_000)
        if s.breakout is None:
            continue
        side, k = s.breakout["side"], s.breakout["k_utc"]
        breakouts[f"{side} {k.astimezone(LONDON):%H:%M}"] += 1
        d = t.confirmations.get(s.day)
        if d is None or s.range is None or s.retest is None:
            continue
        confirmed_by_side[side] += 1
        delays[side][int((d - k) / step)] += 1
        hours[side][f"{d.astimezone(LONDON):%H}"] += 1
        if s.retest["contact_utc"] == d - step:
            on_contact[side] += 1
        bound = s.range["rh"] if side == Side.LONG.value else s.range["rl"]
        gap = bound - s.retest["extreme"] if side == Side.LONG.value else s.retest["extreme"] - bound
        distances[side].append(gap / s.range["atr"])
    return {
        "denominators": "voir l'entonnoir : chaque étape donne ses entrées",
        "by_clock": {k: dict(v) for k, v in sorted(by_clock.items())},
        "h_over_a_ranges_with_atr": summary(ratios),
        "atr_pips_ranges_with_atr": summary(atrs),
        "breakouts_by_side_and_k_london": dict(sorted(breakouts.items())),
        "confirmations_by_side": dict(confirmed_by_side),
        "d_minus_k_in_candles": {s: dict(sorted(c.items())) for s, c in delays.items()},
        "confirmed_on_contact_candle": dict(on_contact),
        "d_hour_london": {s: dict(sorted(c.items())) for s, c in hours.items()},
        "extreme_to_bound_in_a": {s: summary(v) for s, v in distances.items()},
        "unit": p.trigger.value,
    }


# ---------------------------------------------------------------------------------------------- checks


def weekdays(start: datetime, end: datetime, params: Day01Params) -> list[date]:
    """C1: London weekdays whose range start lies in [start, end) and whose 16:00 lies by `end`,
    by a plain date walk, independent of the engine's session list."""
    out, day = [], start.astimezone(LONDON).date() - timedelta(days=1)
    while day <= end.astimezone(LONDON).date():
        if (
            day.weekday() < 5
            and start <= london(day, params.range_start) < end
            and london(day, params.liquidation) <= end
        ):
            out.append(day)
        day += timedelta(days=1)
    return out


def _us(moment: datetime) -> int:
    return int((moment - datetime(1970, 1, 1, tzinfo=UTC)) / timedelta(microseconds=1))


def _from_us(us: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=us)


def independent_range_and_breakout(m15: pa.Table, t: Trajectory) -> list[str]:
    """C6: range completeness and bounds, and the first breakout, recomputed by DuckDB queries on the
    M15 table, apart from the engine; the engine's ATR is the only value taken from it."""
    p = t.params
    rows = [
        {
            "day": s.day,
            "range_start": _us(london(s.day, p.range_start)),
            "freeze": _us(london(s.day, p.freeze)),
            "last_breakout": _us(london(s.day, p.last_breakout_start)),
        }
        for s in t.sessions
    ]
    if not rows:
        return []
    con = duckdb.connect()
    con.register("m15_raw", m15)
    con.register("s", pa.Table.from_pylist(rows))
    con.execute(
        "CREATE TEMP VIEW m15 AS SELECT epoch_us(start_utc) AS start_us, complete_at_close AS ok, "
        "bid_high, bid_low, bid_close FROM m15_raw"
    )
    ranges = {
        r[0]: (r[1], r[2], r[3])
        for r in con.execute(
            "SELECT s.day, count(*) FILTER (WHERE m.ok), max(m.bid_high), min(m.bid_low) FROM s JOIN m15 m "
            "ON m.start_us >= s.range_start AND m.start_us < s.freeze GROUP BY s.day"
        ).fetchall()
    }
    window: dict[date, list[tuple[int, Decimal | None, bool]]] = defaultdict(list)
    for day, start_us, close, ok in con.execute(
        "SELECT s.day, m.start_us, m.bid_close, m.ok FROM s JOIN m15 m "
        "ON m.start_us >= s.freeze AND m.start_us <= s.last_breakout ORDER BY s.day, m.start_us"
    ).fetchall():
        window[day].append((start_us, close, ok))
    con.close()
    errors = []
    for s in t.sessions:
        outcome = t.outcomes[s.day]
        if outcome == "PAS_DE_SÉANCE":
            continue
        ok, high, low = ranges.get(s.day, (0, None, None))
        complete = ok == p.range_slots
        if complete != (outcome != "RANGE_INCOMPLET"):
            errors.append(f"{s.day} : range {ok}/{p.range_slots} M15 OK, issue du moteur {outcome}")
            continue
        if not complete or s.range is None:
            continue
        if (s.range["rh"], s.range["rl"]) != (high, low):
            errors.append(f"{s.day} : range moteur {s.range['rh']}/{s.range['rl']}, recalcul {high}/{low}")
        if outcome not in ("DONNÉES_CASSURE", "AUCUNE_CASSURE") and s.breakout is None:
            continue  # stopped before the breakout search (ATR or width)
        if high is None or low is None:
            continue  # unreachable: a complete range has bounds
        margin = p.breakout_margin * s.range["atr"]
        found: tuple[str, datetime | None] | None = None
        expected, last = _us(london(s.day, p.freeze)), _us(london(s.day, p.last_breakout_start))
        for start_us, close, bar_ok in window.get(s.day, []):
            if start_us != expected or not bar_ok or close is None:
                found = ("DONNÉES_CASSURE", None)  # the expected M15 is absent or not OK
                break
            if close > high + margin or close < low - margin:
                found = ("LONG" if close > high + margin else "SHORT", _from_us(start_us) + M15)
                break
            expected += M15_US
        if found is None:
            found = ("DONNÉES_CASSURE", None) if expected <= last else ("AUCUNE_CASSURE", None)
        engine: tuple[str, datetime | None] = (
            (s.breakout["side"], s.breakout["k_utc"]) if s.breakout is not None else (outcome, None)
        )
        if found != engine:
            errors.append(f"{s.day} : cassure du moteur {engine}, recalcul {found}")
    return errors


def trajectory_errors(t: Trajectory, trigger_bars: dict[datetime, dict[str, Any]]) -> dict[str, list[str]]:
    """C3, C7, C8 and the parameter part of C9, for one trajectory."""
    p, step = t.params, t.params.trigger_step
    errors: dict[str, list[str]] = {"C3": [], "C7": [], "C8": [], "C9": []}
    if p != expected_params(t.trigger):
        errors["C9"].append(f"{t.trigger.value} : paramètres différents de l'attendu")
    if t.ticks_read:
        errors["C9"].append(f"{t.trigger.value} : au moins un tick lu")
    days = [s.day for s in t.sessions]
    if len(days) != len(set(days)):
        errors["C3"].append("séance comptée plusieurs fois")
    errors["C3"] += [f"{d} : {o} ({t.causes.get(d)})" for d, o in t.outcomes.items() if o == INCONSISTENT]
    errors["C3"] += [
        f"{d} : {ATR_AVAILABLE} ({t.cause_details.get(d)})" for d, c in t.causes.items() if c == ATR_AVAILABLE
    ]
    if set(t.confirmations) != {d for d, o in t.outcomes.items() if o == CONFIRMED}:
        errors["C3"].append("confirmations du moteur ≠ issues CONFIRMATION")
    f = funnel(t.outcomes)
    for name, stages in [*f["by_year"].items(), ("total", f["total"])]:
        errors["C3"] += [f"{name} : {e}" for e in conservation_errors(stages)]
    for s in t.sessions:
        if s.range is not None:
            winter = london(s.day, p.freeze).astimezone(LONDON).utcoffset() == timedelta(0)
            frozen = s.range["frozen_utc"]
            if frozen != london(s.day, p.freeze) or frozen.hour != (8 if winter else 7):
                errors["C7"].append(f"{s.day} : gel à {frozen.isoformat()}")
        if s.breakout is None:
            continue
        k = s.breakout["k_utc"]
        if (k - london(s.day, p.freeze)) % M15 or not london(s.day, time(8, 15)) <= k <= london(s.day, time(11)):
            errors["C7"].append(f"{s.day} : K = {k.isoformat()}")
        retest = s.retest or {}
        last, contact = retest.get("last_examined_utc"), retest.get("contact_utc")
        if last is not None and last + step > k + p.retest_delay:
            errors["C8"].append(f"{s.day} : bougie examinée au-delà de K + 60 min ({last.isoformat()})")
        if contact is not None and (last is None or contact > last):
            errors["C8"].append(f"{s.day} : contact après la dernière bougie examinée")
        d = t.confirmations.get(s.day)
        if d is None:
            continue
        if (d - k) % step or not step <= d - k <= p.retest_delay or d > london(s.day, time(12)):
            errors["C7"].append(f"{s.day} : D = {d.isoformat()}, K = {k.isoformat()}")
        if contact is None or last != d - step:
            errors["C8"].append(f"{s.day} : contact {contact}, dernière bougie {last}, D = {d.isoformat()}")
            continue
        long = s.breakout["side"] == Side.LONG.value
        levels, cursor = [], contact
        while cursor < d:
            bar = trigger_bars[cursor]
            levels.append(bar["bid_low"] if long else bar["ask_high"])
            cursor += step
        expected = min(levels) if long else max(levels)
        if retest.get("extreme") != expected:
            errors["C8"].append(f"{s.day} : extrême {retest.get('extreme')} au lieu de {expected}")
    return errors


def controls(
    trajectories: dict[Trigger, Trajectory],
    bars: dict[Grid, list[dict[str, Any]]],
    m15_table: pa.Table,
    start: datetime,
    end: datetime,
    anchors: Anchors,
) -> dict[str, dict[str, Any]]:
    """C1 to C9 (C10, the provenance, is checked by the command). Each entry: details and errors."""
    ref, cmp = trajectories[Trigger.M5], trajectories[Trigger.M15]
    out: dict[str, dict[str, Any]] = {}
    errors: dict[str, list[str]] = defaultdict(list)

    walk = weekdays(start, end, ref.params)
    for t in trajectories.values():
        if [s.day for s in t.sessions] != walk:
            errors["C1"].append(f"{t.trigger.value} : {len(t.sessions)} jours évalués, {len(walk)} jours ouvrés")
    expected = sum(1 for o in ref.outcomes.values() if o != "PAS_DE_SÉANCE")
    if anchors.expected_sessions is not None and expected != anchors.expected_sessions:
        errors["C1"].append(f"{expected} séances attendues au lieu de {anchors.expected_sessions}")
    out["C1"] = {"weekdays": len(walk), "no_session": len(walk) - expected, "expected_sessions": expected}

    incomplete = frozenset(d for d, o in ref.outcomes.items() if o == "RANGE_INCOMPLET")
    if anchors.incomplete_ranges is not None and incomplete != anchors.incomplete_ranges:
        errors["C2"].append(f"ranges incomplets {sorted(incomplete)} au lieu de {sorted(anchors.incomplete_ranges)}")
    out["C2"] = {"incomplete_ranges": {d.isoformat(): ref.causes.get(d) for d in sorted(incomplete)}}

    blocks = {
        t.trigger.value: sum(1 for o in t.outcomes.values() if o in ("DONNÉES_CASSURE", "DONNÉES_RETEST"))
        for t in trajectories.values()
    }
    if anchors.data_outcomes is not None and any(v != anchors.data_outcomes for v in blocks.values()):
        errors["C4"].append(f"issues de données {blocks} au lieu de {anchors.data_outcomes}")
    out["C4"] = {"data_outcomes": blocks}

    other = {s.day: s for s in cmp.sessions}
    for s in ref.sessions:
        twin = other.get(s.day)
        a, b = ref.outcomes[s.day], cmp.outcomes.get(s.day)
        if twin is None:
            errors["C5"].append(f"{s.day} absente de la trajectoire M15")
        elif (a in COMMON_OUTCOMES or b in COMMON_OUTCOMES) and a != b:
            errors["C5"].append(f"{s.day} : {a} (M5) / {b} (M15)")
        elif (s.range, s.breakout) != (twin.range, twin.breakout):
            errors["C5"].append(f"{s.day} : range ou cassure différents")
    out["C5"] = {"sessions_compared": len(ref.sessions)}

    errors["C6"] = independent_range_and_breakout(m15_table, ref)
    out["C6"] = {"method": "requêtes DuckDB sur la table M15, hors du moteur"}

    for t in trajectories.values():
        for name, errs in trajectory_errors(t, {b["start_utc"]: b for b in bars[GRID[t.trigger]]}).items():
            errors[name] += errs
    out["C3"] = {"unit": "séance, une issue exclusive par trajectoire"}
    out["C7"] = {"bounds": "gel 08:00/07:00 UTC, K dans [08:15, 11:00] Londres, D − K dans [unité, 60 min]"}
    out["C8"] = {"bounds": "contact, extrême et dernière bougie examinée cohérents avec D et K + 60 min"}

    late = [g.value for g, rows in bars.items() if any(b["end_utc"] > end for b in rows)]
    if late:
        errors["C9"].append(f"bougies postérieures à la fin de la fenêtre : {late}")
    rest = [{k: v for k, v in dataclasses.asdict(t.params).items() if k != "trigger"} for t in (ref, cmp)]
    if rest[0] != rest[1]:
        errors["C9"].append("paramètres hors unité de déclenchement différents entre M5 et M15")
    out["C9"] = {
        "expected": {"M5": "Day01Params()", "M15": "Day01Params(trigger=Trigger.M15)"},
        "params": {t.trigger.value: jsonable(dataclasses.asdict(t.params)) for t in (ref, cmp)},
        "other_params_identical": rest[0] == rest[1],
        "ticks_read": sum(t.ticks_read for t in (ref, cmp)),
    }
    for name in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"):
        out[name] |= {"ok": not errors[name], "error_count": len(errors[name]), "errors": errors[name][:20]}
    return dict(sorted(out.items()))


# ---------------------------------------------------------------------------------------------- report


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (Decimal, timedelta)):
        return str(value)
    return value


def availability(
    bars: dict[Grid, list[dict[str, Any]]],
    m15_table: pa.Table,
    h4: Sequence[dict[str, Any]],
    gaps: Sequence[Gap],
    config: ResearchConfig,
    start: datetime,
    end: datetime,
    anchors: Anchors,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Both trajectories, their checks and, only if every check passes, the results."""
    trajectories = {
        trigger: run_trajectory(bars[Grid.M5], bars[Grid.M15], h4, gaps, config, expected_params(trigger), start, end)
        for trigger in Trigger
    }
    checks = controls(trajectories, bars, m15_table, start, end, anchors)
    report: dict[str, Any] = {"window": {"start": start, "end": end}, "checks": checks}
    report["failed_checks"] = [name for name, c in checks.items() if not c["ok"]]
    details = []
    for t in trajectories.values():
        for s in t.sessions:
            details.append(
                {
                    "trigger": t.trigger.value,
                    "day": s.day,
                    "outcome": t.outcomes[s.day],
                    "cause": t.causes.get(s.day),
                    "cause_detail": t.cause_details.get(s.day),
                    "range": s.range,
                    "breakout": s.breakout,
                    "retest": s.retest,
                    "confirmation_utc": t.confirmations.get(s.day),
                }
            )
    report["funnel"] = {t.trigger.value: funnel(t.outcomes) for t in trajectories.values()}
    report["descriptions"] = {t.trigger.value: describe(t) for t in trajectories.values()}
    report["causes"] = {
        t.trigger.value: dict(Counter(f"{t.outcomes[d]} : {c}" for d, c in t.causes.items() if t.outcomes[d] in (
            "RANGE_INCOMPLET", "ATR_NON_CALCULABLE")))
        for t in trajectories.values()
    }  # fmt: skip
    report["note"] = "une confirmation est un instant D où une entrée sera évaluée, pas une entrée"
    if report["failed_checks"]:
        return jsonable(withhold(report)), []
    return jsonable(report), [jsonable(d) for d in details]


def withhold(report: dict[str, Any]) -> dict[str, Any]:
    """On a failed check, only the checks and the provenance are kept (protocol §5)."""
    kept = {k: v for k, v in report.items() if k not in ("funnel", "descriptions", "causes")}
    kept["results_withheld"] = True
    return kept


def to_markdown(report: dict[str, Any]) -> str:
    lines = ["# DAY_01 — disponibilité des données (rapport agrégé)", ""]
    lines += [
        f"Fenêtre : {report['window']['start']} → {report['window']['end']}. Aucun tick lu, aucune exécution.",
        "",
    ]
    lines += ["| Contrôle | Conforme | Écarts |", "|---|---|---:|"]
    lines += [f"| {n} | {'oui' if c['ok'] else 'NON'} | {c['error_count']} |" for n, c in report["checks"].items()]
    if report.get("results_withheld"):
        return "\n".join([*lines, "", "**Résultats masqués : contrôle en échec.**", ""])
    for unit, f in report["funnel"].items():
        lines += [
            "",
            f"## Entonnoir {unit} (total)",
            "",
            "| Étape | Entrées (dénominateur) | Issue | Nombre | % des entrées |",
        ]
        lines += ["|---|---:|---|---:|---:|"]
        for stage in f["total"]:
            if stage["stage"] == "confirmations":
                lines.append(f"| confirmations | {stage['entering']} | {CONFIRMED} | {stage['confirmed']} | |")
                continue
            for outcome, n in stage["terminal"].items():
                lines.append(
                    f"| {stage['stage']} | {stage['entering']} | {outcome} | {n} | {_pct(n, stage['entering'])} |"
                )
    lines += ["", report["note"], ""]
    return "\n".join(lines)


def _pct(part: int, whole: int) -> str:
    return "—" if whole == 0 else f"{100 * part / whole:.3f} %".replace(".", ",")


def read_candles(path: Path, end: datetime) -> tuple[list[dict[str, Any]], pa.Table]:
    """Candles ending by `end` only (filtered at read time), with their content as `Content`."""
    table = pq.read_table(path, filters=[("end_utc", "<=", end)])
    rows: list[dict[str, Any]] = table.to_pylist()
    for row in rows:
        row["content"] = Content(row["content"])
    return sorted(rows, key=lambda b: b["start_utc"]), table


def _date(text: str) -> datetime:
    return datetime.combine(date.fromisoformat(text), time(), tzinfo=UTC)


def main(argv: list[str] | None = None) -> int:
    launch = provenance(argv, TOOL)
    parser = argparse.ArgumentParser(prog=TOOL, description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--init-start", type=_date, default=_date("2015-01-01"))
    parser.add_argument("--start", type=_date, default=_date("2015-01-01"))
    parser.add_argument("--end", type=_date, default=_date("2022-01-01"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--details-out", type=Path, required=True)
    args = parser.parse_args(argv)
    require_development_window(args.init_start, args.end)
    directory = args.data_dir / "bars" / SOURCE / INSTRUMENT
    candles = {g: directory / "intraday_2015_2021_day01_5min" / f"{g.value}.parquet" for g in Grid}
    h4_path = directory / f"{Timeframe.H4.value}.parquet"
    before = {path.as_posix(): sha256_file(path) for path in (*candles.values(), h4_path)}
    wrong = [g.value for g, path in candles.items() if before[path.as_posix()] != CANDLES_SHA256[g]]
    if wrong:
        print(f"empreintes des bougies {wrong} différentes de l'audit : aucune lecture", file=sys.stderr)
        return 2
    read = {g: read_candles(path, args.end) for g, path in candles.items()}
    bars = {g: rows for g, (rows, _) in read.items()}
    h4 = load_bars(args.data_dir, SOURCE, INSTRUMENT, Timeframe.H4, args.init_start, args.end)
    gaps = load_gaps(args.data_dir / "reports" / f"quality_{SOURCE}_{INSTRUMENT}.json", args.end)
    full = (args.start, args.end) == (_date("2015-01-01"), _date("2022-01-01"))
    report, details = availability(
        bars, read[Grid.M15][1], h4, gaps, ResearchConfig(costs=RESEARCH_COSTS), args.start, args.end,
        ANCHORS_2015_2021 if full else Anchors(),
    )  # fmt: skip
    after = {path.as_posix(): sha256_file(path) for path in (*candles.values(), h4_path)}
    finish = end_check(launch, tree_state())
    code_changed = finish["commit"] != launch["commit"] or any(
        f.startswith(CODE_PATHS) for f in finish["files_changed_during_run"]
    )
    report["checks"]["C9"]["inputs_sha256"] = {"before": before, "after": after, "unchanged": before == after}
    c10 = [] if not launch["uncommitted_diff_sha256"] else ["arbre non propre au lancement"]
    c10 += ["code ou commit modifié pendant le passage"] if code_changed else []
    report["checks"]["C10"] = {
        "ok": not c10,
        "error_count": len(c10),
        "errors": c10,
        "launch": launch,
        "end": finish,
        "rule": "arbre propre au lancement ; aucun changement de code (src, pyproject, uv.lock) pendant le passage",
    }
    if before != after:
        c9 = report["checks"]["C9"]
        c9["ok"], c9["error_count"] = False, c9["error_count"] + 1
        c9["errors"] = [*c9["errors"], "empreintes des entrées modifiées pendant le passage"]
    report["failed_checks"] = [name for name, c in report["checks"].items() if not c["ok"]]
    report["anchors"] = "bilan des données 2015-2021" if full else "aucune (fenêtre partielle)"
    report["inputs"] = {"m5": len(bars[Grid.M5]), "m15": len(bars[Grid.M15]), "h4": len(h4), "gaps": len(gaps)}
    if report["failed_checks"]:
        report = withhold(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8")
    args.out.with_suffix(".md").write_text(to_markdown(jsonable(report)), encoding="utf-8")
    if not report["failed_checks"]:
        args.details_out.write_text(
            "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in details), encoding="utf-8"
        )
    print(f"contrôles en échec : {report['failed_checks'] or 'aucun'} ; rapport : {args.out}")
    return 2 if report["failed_checks"] else 0


if __name__ == "__main__":
    sys.exit(main())
