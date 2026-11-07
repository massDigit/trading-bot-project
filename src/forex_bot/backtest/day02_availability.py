"""DAY_02 data availability study (docs/experiments/DAY02_AVAILABILITY_2015_2021.md).

"No-position path" on the candles only: each session starts a search at 07:00 London; every
configuration found by `day02.configuration_from` (the very function of the engine) is followed to
its end; a confirmed exit at D is counted as such (not an entry) and the search resumes at D, or at
the end of an abandoned, invalidated or expired configuration. No tick, no position, no fictitious
position. The H1 ATR comes from `Day02Backtest.atr_at` on an engine without ticks.

Sharing `configuration_from` keeps the study, the engine and the future per-configuration control
on the same rule; it does not check that rule. Check C6 recomputes the first configuration of each
session with a separate implementation written for it (separate code, same reading of the sheet).

One trajectory per trigger: the M5 reference (`Day02Params()`) and the preregistered M15 comparison
(`Day02Params(trigger=Trigger.M15)`), every other parameter identical. Blocking checks C1 to C10;
on any failure the results are withheld and the command exits with code 2.

Research only: no tick is read, no order exists, 2022-2025 stays out of reach.
"""

from __future__ import annotations

import argparse
import bisect
import itertools
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from forex_bot.backtest.bar_state import BarState, bar_state
from forex_bot.backtest.data import load_bars, load_gaps, require_development_window
from forex_bot.backtest.day01 import LONDON, M5, M15, bar_ok, london
from forex_bot.backtest.day01_availability import CANDLES_SHA256, clocks, jsonable, read_candles
from forex_bot.backtest.day02 import (
    ATR_UNAVAILABLE,
    EXIT,
    FLAG_DATA,
    PROLONGED,
    SESSION_START,
    TOO_DEEP,
    TOO_LONG,
    WINDOW_END,
    Configuration,
    Day02Params,
    Search,
    Trigger,
    ceil_m15,
    configuration_from,
    session_day,
)
from forex_bot.backtest.day02_engine import Day02Backtest
from forex_bot.backtest.engine import ResearchConfig
from forex_bot.backtest.explore import RESEARCH_COSTS
from forex_bot.backtest.feed import Silence, classify_silence
from forex_bot.backtest.s2 import ContinuousWilderAtr
from forex_bot.history.bars import Gap
from forex_bot.history.calendar import Timeframe, expected_open_minutes
from forex_bot.history.intraday import NO_TICK, NO_VALID_TICK, SUBSLOTS_FLAG, Content, Grid
from forex_bot.history.intraday_audit import end_check, provenance, sha256_file, tree_state
from forex_bot.risk import Side

SOURCE, INSTRUMENT = "dukascopy", "EURUSD"
TOOL = "forex-day02-availability"
LOT = "intraday_2015_2021_day01_5min"  # audited 5 min lot, convention extended to DAY_02 (ADR-026)
# Full H1 hash recorded before and after both intraday audits (data/reports/intraday_dukascopy_EURUSD_
# 2015_2021.json, commit 36daea1, clean tree; and its 5 min run, commit c0272cc): existing_bars_sha256.
H1_SHA256 = "a7c7f8b82ac55828bbbc25b8fd87c64cac99efb5a977187c47b381480802c585"
QUALITY_REPORT = "quality_dukascopy_EURUSD.json"
# No audit recorded the hash of the quality report: it is recorded before and after the run, without a
# historical reference. Its content is anchored by the gap count loaded up to 2022-01-01 in the DAY_01
# performance runs (bilan DAY_01, 383 gaps), on the official window only.
GAPS_ANCHOR = 383
OFFICIAL_WINDOW = (datetime(2015, 1, 1, tzinfo=UTC), datetime(2022, 1, 1, tzinfo=UTC))
# Independent count of the calendar (operator, 2026-11-07); applies to the full official window only.
CALENDAR_ANCHOR = {"weekdays": 1827, "excluded": 11, "sessions": 1816}
CODE_PATHS = ("src/", "pyproject.toml", "uv.lock")
TRIGGERS = (Trigger.M5, Trigger.M15)
PARAMS = {Trigger.M5: Day02Params(), Trigger.M15: Day02Params(trigger=Trigger.M15)}
SILENCE = timedelta(minutes=5)  # an interruption is strictly longer, in expected-open time (ADR-026)
NEEDED = (time(7), time(15))  # candles needed for recognition and exit (sheet §5.2)
FULL = (time(7), time(17))  # whole DAY_02 window, descriptive (sheet §4.1)
FORMATION_ENDS = (FLAG_DATA, TOO_DEEP, PROLONGED, WINDOW_END)  # before F
EXIT_ENDS = (FLAG_DATA, TOO_DEEP, TOO_LONG, WINDOW_END, EXIT)  # after F
NOT_FORMED = "configuration terminée avant la formation du drapeau"
# Why the H1 ATR is unavailable at an examined close (protocol §4.4), from the H1 known then only.
ATR_INITIAL = "amorçage : historique H1 initial insuffisant"
ATR_ABSENT_H1 = "interruption : H1 prévue absente"
ATR_UNUSABLE_H1 = "interruption : H1 inutilisable"
ATR_UNDETERMINED = "non déterminée"
NO_EXIT = "pas de sortie confirmée"


# ---------------------------------------------------------------- calendar (C1)


def calendar_days(start: datetime, end: datetime) -> tuple[list[date], list[date]]:
    """London weekdays whose 07:00-17:00 window lies in [start, end), and those excluded (25/12, 1/1).
    Built from the calendar rules directly, not from the engine's selection."""
    day, last = start.astimezone(LONDON).date() - timedelta(days=1), end.astimezone(LONDON).date()
    weekdays, excluded = [], []
    while day <= last:
        if day.weekday() < 5 and start <= london(day, time(7)) and london(day, time(17)) <= end:
            weekdays.append(day)
            if (day.month, day.day) in ((12, 25), (1, 1)):
                excluded.append(day)
        day += timedelta(days=1)
    return weekdays, excluded


def study_days(start: datetime, end: datetime) -> list[date]:
    """Sessions as the engine selects them (`session_day`, whole 07:00-17:00 window in the study)."""
    first, last = start.astimezone(LONDON).date(), end.astimezone(LONDON).date()
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    return [d for d in days if session_day(d) and start <= london(d, time(7)) and london(d, time(17)) <= end]


# ---------------------------------------------------------------- no-position path


@dataclass
class SearchLine:
    """One search of the no-position path, with the H1 read for each examined close."""

    resume_utc: datetime
    resume_after: str
    search: Search
    atr_reads: dict[datetime, tuple[datetime, datetime | None, Decimal | None]] = field(default_factory=dict)
    atr_causes: dict[datetime, tuple[str, str | None]] = field(default_factory=dict)  # unavailable ATR only

    @property
    def configuration(self) -> Configuration | None:
        return self.search.configuration


@dataclass
class SessionPath:
    day: date
    trigger: Trigger
    searches: list[SearchLine] = field(default_factory=list)

    @property
    def configurations(self) -> list[Configuration]:
        return [s.configuration for s in self.searches if s.configuration is not None]


def _atr_recorder(engine: Day02Backtest, line: SearchLine) -> Callable[[datetime, datetime], Decimal | None]:
    def atr(cutoff: datetime, known: datetime) -> Decimal | None:
        i = bisect.bisect_right(engine.h1_end, cutoff) - 1
        value = engine.atr_at(cutoff, known)
        line.atr_reads[known] = (cutoff, engine.h1_end[i] if i >= 0 else None, value)
        if value is None or value <= 0:
            line.atr_causes[known] = atr_cause(engine, cutoff, known)
        return value

    return atr


def atr_cause(engine: Day02Backtest, cutoff: datetime, known: datetime) -> tuple[str, str | None]:
    """Why the H1 ATR on the last H1 ended by `cutoff` is unavailable, with states known at `known`.

    Diagnosis only, the ATR itself is unchanged: a fresh `ContinuousWilderAtr` (same rules, no cache)
    on the H1 up to that last one, never a later H1. The usable run ending there starts at its anchor:
    anchor 0, the run starts with the history (initial bootstrap); after an absent expected H1 or an
    unusable one, an interruption; an anchor beyond the last H1 means that H1 is itself unusable.
    Anything else stays explicitly undetermined."""
    i = bisect.bisect_right(engine.h1_end, cutoff) - 1
    if i < 0:
        return ATR_INITIAL, "aucune H1 terminée avant la fenêtre"
    cache: dict[int, BarState] = {}

    def state(j: int) -> BarState:
        if j not in cache:
            cache[j] = bar_state(
                engine.h1[j], known, engine.gaps, engine.config.gap_threshold, engine.config.documented_closures
            )
        return cache[j]

    probe = ContinuousWilderAtr(engine.h1, engine.day02.atr_period)
    value = probe.at(i, state)
    if value is not None:
        return ATR_UNDETERMINED, f"ATR {value} non positif"
    anchor = probe._anchor
    if anchor is None:
        return ATR_UNDETERMINED, None
    start = engine.h1[i]["start_utc"].isoformat()
    if anchor > i:
        return ATR_UNUSABLE_H1, f"H1 {start} inutilisable ; 0 H1 utilisable depuis la rupture"
    known_run = f"{i - anchor + 1} H1 utilisables depuis {engine.h1[anchor]['start_utc'].isoformat()}"
    if anchor == 0:
        return ATR_INITIAL, known_run
    if anchor in probe._holes:
        return ATR_ABSENT_H1, f"H1 prévue absente avant {engine.h1[anchor]['start_utc'].isoformat()} ; {known_run}"
    if not state(anchor - 1).usable:
        return ATR_UNUSABLE_H1, f"H1 {engine.h1[anchor - 1]['start_utc'].isoformat()} inutilisable ; {known_run}"
    return ATR_UNDETERMINED, known_run


def no_position_path(day: date, engine: Day02Backtest, params: Day02Params) -> SessionPath:
    """Searches of one session: resume at 07:00, then at the end of each configuration (D for an exit)."""
    path = SessionPath(day, params.trigger)
    resume, after = london(day, params.impulse_start), SESSION_START
    while True:
        line = SearchLine(resume, after, Search(resume))
        line.search = configuration_from(
            resume, day, engine.m15, engine.trigger_bars, _atr_recorder(engine, line), params
        )
        path.searches.append(line)
        config = line.configuration
        if config is None or config.ended_utc is None or config.outcome is None:
            return path
        resume, after = config.ended_utc, config.outcome


def run_trajectory(
    trigger: Trigger,
    m5: Sequence[dict[str, Any]],
    m15: Sequence[dict[str, Any]],
    h1: Sequence[dict[str, Any]],
    gaps: Sequence[Gap],
    config: ResearchConfig,
    days: Iterable[date],
) -> tuple[list[SessionPath], Day02Backtest]:
    params = PARAMS[trigger]
    engine = Day02Backtest(m5, m15, h1, [], gaps, params, config)  # no tick: only the H1 ATR is used
    return [no_position_path(day, engine, params) for day in days], engine


# ---------------------------------------------------------------- counts (§4.2) and conservation (C2)


def year_of(day: date) -> str:
    return str(day.year)


def counts(paths: list[SessionPath]) -> dict[str, Any]:
    by: dict[str, Counter[str]] = defaultdict(Counter)
    causes: dict[str, Counter[str]] = defaultdict(Counter)
    formation: dict[str, Counter[str]] = defaultdict(Counter)
    exit_stage: dict[str, Counter[str]] = defaultdict(Counter)
    per_session: dict[str, Counter[int]] = defaultdict(Counter)
    atr: dict[str, Counter[str]] = defaultdict(Counter)
    for path in paths:
        for key in ("total", year_of(path.day)):
            c = by[key]
            c["séances"] += 1
            c["recherches"] += len(path.searches)
            per_session[key][len(path.configurations)] += 1
            for line in path.searches:
                c["m15_examinées"] += len(line.search.examined) + (line.configuration is not None)
                for e in line.search.examined:
                    causes[key][e.cause] += 1
                    if e.cause == ATR_UNAVAILABLE:
                        atr[key][line.atr_causes.get(e.t_utc, (ATR_UNDETERMINED, None))[0]] += 1
                config = line.configuration
                if config is None:
                    continue
                c["configurations"] += 1
                c[f"configurations_{config.side.value}"] += 1
                if config.flag_utc is None:
                    formation[key][got(config.outcome)] += 1
                else:
                    c["drapeaux_formés"] += 1
                    exit_stage[key][got(config.outcome)] += 1
                    if config.outcome == EXIT:
                        c["sorties_confirmées"] += 1
    return {
        key: {
            "comptes": dict(by[key]),
            "m15_non_reconnues_par_cause": dict(causes[key]),
            "atr_h1_indisponible_par_cause": dict(atr[key]),
            "fins_avant_formation": dict(formation[key]),
            "fins_après_formation": dict(exit_stage[key]),
            "configurations_par_séance": {str(k): v for k, v in sorted(per_session[key].items())},
        }
        for key in sorted(by, key=lambda k: (k != "total", k))
    }


def got[T](value: T | None) -> T:
    if value is None:
        raise ValueError("valeur attendue absente")
    return value


def conservation_errors(paths: list[SessionPath]) -> list[str]:
    errors = []
    for path in paths:
        where = f"{path.day} {path.trigger.value}"
        if not path.searches or path.searches[-1].configuration is not None:
            errors.append(f"{where} : la dernière recherche doit se terminer sans configuration")
        if any(line.configuration is None for line in path.searches[:-1]):
            errors.append(f"{where} : une recherche sans configuration n'est pas la dernière")
        for config in path.configurations:
            stage = FORMATION_ENDS if config.flag_utc is None else EXIT_ENDS
            if config.outcome not in stage or config.ended_utc is None:
                errors.append(f"{where} {config.recognised_utc} : fin {config.outcome} hors de son étape")
    return errors


# ---------------------------------------------------------------- resumes (C3), bounds (C4), bars (C5)


def resume_errors(paths: list[SessionPath], params: Mapping[Trigger, Day02Params] = PARAMS) -> list[str]:
    errors = []
    for path in paths:
        where = f"{path.day} {path.trigger.value}"
        first = path.searches[0]
        if (first.resume_utc, first.resume_after) != (
            london(path.day, params[path.trigger].impulse_start),
            SESSION_START,
        ):
            errors.append(f"{where} : première reprise {first.resume_utc} ({first.resume_after})")
        for before, after in zip(path.searches, path.searches[1:], strict=False):
            config = before.configuration
            expected = (None, None) if config is None else (config.ended_utc, config.outcome)
            if (after.resume_utc, after.resume_after) != expected:
                errors.append(f"{where} : reprise {after.resume_utc} ({after.resume_after}) ≠ fin {expected}")
    return errors


def bound_errors(
    paths: list[SessionPath],
    m15: Mapping[datetime, Mapping[str, Any]] | None = None,
    params: Mapping[Trigger, Day02Params] = PARAMS,
) -> list[str]:
    """Bounds of valid configurations; an event that ends one (e.g. a 7th M15) is an outcome, not an error.
    Formation and exit bounds apply only when F or D exist."""
    errors = []
    for path in paths:
        p, day = params[path.trigger], path.day
        step = p.trigger_step
        for line in path.searches:
            c = line.configuration
            if c is None:
                continue
            where = f"{day} {path.trigger.value} {c.recognised_utc.isoformat()}"
            t = c.recognised_utc

            def err(text: str, where: str = where) -> None:
                errors.append(f"{where} : {text}")

            if t.minute % 15 or t.second or t.microsecond:
                err("t_j hors de la grille M15")
            if not london(day, time(8)) <= t <= london(day, p.last_recognition):
                err("t_j hors de [08:00, 14:15]")
            if t < ceil_m15(line.resume_utc) + p.window * M15:
                err("fenêtre commencée avant la reprise")
            # o < p = j, read again on the window candles (the configuration keeps only the last peak).
            window = [m15.get(t - (p.window - k) * M15) for k in range(p.window)] if m15 is not None else []
            if window and all(w is not None for w in window):
                long = c.side is Side.LONG
                tops = [w["bid_high"] if long else w["bid_low"] for w in window if w is not None]
                if tops[-1] != (max(tops) if long else min(tops)):
                    err("p ≠ j à la reconnaissance")
            if not t - p.window * M15 <= c.origin_start < t - M15:
                err("o < p non respecté ou origine hors de la fenêtre")
            if [s for s in c.extensions if s < t] or c.extensions != sorted(c.extensions):
                err("extensions non ordonnées ou antérieures à la reconnaissance")
            if c.extensions and c.peak_start != c.extensions[-1]:
                err("dernier sommet différent de la dernière extension")
            length = (c.peak_start - c.origin_start) / M15 + 1
            if c.outcome == PROLONGED:
                # The first extension that takes the impulse beyond 6 M15 ends it, at its close; the
                # impulse may then exceed 7 M15 (pauses between extensions count in its length).
                before = c.extensions[-2] if len(c.extensions) > 1 else t - M15
                if not c.extensions or (before - c.origin_start) / M15 + 1 > p.max_impulse:
                    err("abandon après une impulsion déjà au-delà de 6 M15")
                if length <= p.max_impulse or c.ended_utc != c.peak_start + M15:
                    err("impulsion prolongée sans dépassement, ou abandon hors de la clôture de l'extension")
            elif length > p.max_impulse:
                err("impulsion de plus de 6 M15 sans fin « prolongée »")
            if got(c.ended_utc) > london(day, p.last_decision):
                err("fin après 15:00")
            if c.flag_utc is None:
                if c.outcome == WINDOW_END and c.ended_utc != london(day, p.last_flag):
                    err("fin de fenêtre avant F hors de 14:45")
                continue
            # Formation exists.
            deadline = min(c.peak_start + M15 + p.max_pause, london(day, p.last_decision))
            if c.pause_starts != [c.peak_start + i * M15 for i in range(1, p.min_pause + 1)]:
                err("pauses différentes des deux M15 suivant le dernier sommet")
            if c.flag_utc != c.peak_start + (p.min_pause + 1) * M15 or c.flag_utc > london(day, p.last_flag):
                err("F mal daté ou après 14:45")
            if c.deadline_utc != deadline:
                err("Δ différent de min(fin(p) + 90 min, 15:00)")
            if c.last_examined_start is not None and c.last_examined_start + step > deadline:
                err("bougie lue se terminant après Δ")
            if c.outcome in (TOO_LONG,) or (c.outcome == WINDOW_END):
                if c.ended_utc != deadline:
                    err("expiration ailleurs qu'à Δ")
            if c.outcome == EXIT:
                d = got(c.ended_utc)
                if not c.flag_utc < d <= deadline or (d - london(day, time(0))) % step:
                    err("D hors de ]F, Δ] ou hors de la grille")
                if c.stop is None or c.target is None:
                    err("sortie sans stop ou sans cible")
    return errors


def configuration_m15(c: Configuration, trigger: Trigger, p: Day02Params) -> set[datetime]:
    """M15 a configuration uses: impulse window, formation reads, and exit M15 in the comparison."""
    t = c.recognised_utc
    used = {t - (p.window - i) * M15 for i in range(p.window)}
    last = (got(c.flag_utc) - M15) if c.flag_utc is not None else c.last_examined_start
    cursor = t
    while last is not None and cursor <= last:
        used.add(cursor)
        cursor += M15
    if trigger is Trigger.M15 and c.flag_utc is not None and c.last_examined_start is not None:
        cursor = c.flag_utc
        while cursor <= c.last_examined_start:
            used.add(cursor)
            cursor += M15
    return used


def reuse_errors(paths: list[SessionPath], params: Mapping[Trigger, Day02Params] = PARAMS) -> list[str]:
    errors = []
    for path in paths:
        seen: dict[datetime, datetime] = {}
        for line in path.searches:
            c = line.configuration
            if c is None:
                continue
            used = configuration_m15(c, path.trigger, params[path.trigger])
            if any(s < line.resume_utc for s in used):
                errors.append(f"{path.day} {path.trigger.value} : M15 commencée avant la reprise {line.resume_utc}")
            for s in sorted(used):
                if s in seen:
                    errors.append(f"{path.day} {path.trigger.value} : M15 {s} réutilisée ({seen[s]})")
                seen[s] = c.recognised_utc
    return errors


# ---------------------------------------------------------------- C6: separate recomputation


def independent_first(
    day: date, m15: Mapping[datetime, Mapping[str, Any]], atr: Callable[[datetime, datetime], Decimal | None]
) -> dict[str, Any] | None:
    """First configuration of a session, recomputed from the sheet §5.1 and §5.3 without
    `configuration_from`: recognition (t_j, side, O, o, p) and formation (F, final E and p, or its end)."""
    window, t, last = 4, london(day, time(7)) + 4 * M15, london(day, time(14, 15))
    while t <= last:
        rows = [m15.get(t - (window - k) * M15) for k in range(window)]
        bars = [r for r in rows if r is not None and r["complete_at_close"]]
        a = atr(t - window * M15, t) if len(bars) == window else None
        if a is not None and a > 0:
            lows, highs, close = [r["bid_low"] for r in bars], [r["bid_high"] for r in bars], bars[-1]["bid_close"]
            found = []
            # Long: lowest low first reached strictly before the last candle, which holds the highest high.
            o, q = lows.index(min(lows)), max(k for k, v in enumerate(highs) if v == max(highs))
            if o < q == window - 1 and close - min(lows) >= Decimal("1.5") * a:
                if close >= max(highs) - Decimal("0.25") * (max(highs) - min(lows)):
                    found.append((Side.LONG, min(lows), max(highs), o))
            o, q = highs.index(max(highs)), max(k for k, v in enumerate(lows) if v == min(lows))
            if o < q == window - 1 and max(highs) - close >= Decimal("1.5") * a:
                if close <= min(lows) + Decimal("0.25") * (max(highs) - min(lows)):
                    found.append((Side.SHORT, max(highs), min(lows), o))
            if len(found) == 1:
                side, origin, peak, o = found[0]
                o_start = t - (window - o) * M15
                return {
                    "t_j": t,
                    "side": side.value,
                    "O": origin,
                    "o": o_start,
                    **_independent_flag(day, m15, side, origin, o_start, peak, t - M15),
                }
        t += M15
    return None


def _independent_flag(
    day: date,
    m15: Mapping[datetime, Mapping[str, Any]],
    side: Side,
    origin: Decimal,
    o_start: datetime,
    peak: Decimal,
    p: datetime,
) -> dict[str, Any]:
    long, pauses, cursor = side is Side.LONG, 0, p + M15
    while True:
        end = cursor + M15
        if end > london(day, time(14, 45)):
            return {"F": None, "fin": WINDOW_END, "instant": london(day, time(14, 45))}
        bar = m15.get(cursor)
        if bar is None or not bar["complete_at_close"]:
            return {"F": None, "fin": FLAG_DATA, "instant": end}
        half = abs(peak - origin) / 2
        if (long and bar["bid_low"] < peak - half) or (not long and bar["bid_high"] > peak + half):
            return {"F": None, "fin": TOO_DEEP, "instant": end}
        if (long and bar["bid_high"] > peak) or (not long and bar["bid_low"] < peak):
            peak, p, pauses = (bar["bid_high"] if long else bar["bid_low"]), cursor, 0
            if (p - o_start) / M15 + 1 > 6:
                return {"F": None, "fin": PROLONGED, "instant": end}
        else:
            pauses += 1
            if pauses == 2:
                return {"F": end, "fin": None, "instant": None, "E_final": peak, "p_final": p}
        cursor = end


def first_configuration_view(c: Configuration | None) -> dict[str, Any] | None:
    """Fields of a first configuration compared by C6: recognition, then F with the final E and p, or
    the end before F. Nothing after F (exit, stop, target) is compared."""
    if c is None:
        return None
    view = {
        "t_j": c.recognised_utc,
        "side": c.side.value,
        "O": c.origin,
        "o": c.origin_start,
    }
    if c.flag_utc is not None:
        return {**view, "F": c.flag_utc, "fin": None, "instant": None, "E_final": c.peak, "p_final": c.peak_start}
    return {**view, "F": None, "fin": c.outcome, "instant": c.ended_utc}


def c6_errors(
    paths: list[SessionPath],
    m15_rows: Mapping[datetime, Mapping[str, Any]],
    atr: Callable[[datetime, datetime], Decimal | None],
) -> list[str]:
    """Sessions without configuration included: both must find none."""
    errors = []
    for path in paths:
        mine, other = (
            first_configuration_view(path.searches[0].configuration),
            independent_first(path.day, m15_rows, atr),
        )
        if mine != other:
            errors.append(f"{path.day} {path.trigger.value} : {mine} ≠ recalcul {other}")
    return errors


# ---------------------------------------------------------------- C7: steps common to M5 and M15


def c7_errors(m5: list[SessionPath], m15: list[SessionPath]) -> list[str]:
    """First search of each session, up to F: same examined closes, same recognition and formation
    (or the same end before F); sessions without configuration included."""
    errors = []
    by_day = {p.day: p for p in m15}
    for a in m5:
        b = by_day.get(a.day)
        if b is None:
            errors.append(f"{a.day} : séance absente en M15")
            continue
        sa, sb = a.searches[0], b.searches[0]
        if sa.search.examined != sb.search.examined:
            errors.append(f"{a.day} : M15 examinées différentes")
        if first_configuration_view(sa.configuration) != first_configuration_view(sb.configuration):
            errors.append(f"{a.day} : parcours commun avant F différent")
    if {p.day for p in m5} != set(by_day):
        errors.append("séances différentes entre M5 et M15")
    return errors


# ---------------------------------------------------------------- C8: H1 ATR


def c8_errors(paths: list[SessionPath], p: Mapping[Trigger, Day02Params] = PARAMS) -> list[str]:
    errors = []
    for path in paths:
        window = p[path.trigger].window
        for line in path.searches:
            c = line.configuration
            if c is None:
                continue
            read = line.atr_reads.get(c.recognised_utc)
            start = c.recognised_utc - window * M15
            if read is None:
                errors.append(f"{path.day} {c.recognised_utc} : ATR non lu à t_j")
                continue
            cutoff, h1_end, value = read
            if cutoff != start or h1_end is None or h1_end > start or value != c.atr:
                errors.append(f"{path.day} {c.recognised_utc} : ATR lu sur une H1 terminée après la fenêtre")
    return errors


# ---------------------------------------------------------------- measures (§4.3)


def _stats(values: list[Decimal]) -> dict[str, Any] | None:
    if not values:
        return None
    v = sorted(values)
    return {
        "n": len(v),
        "min": v[0],
        "q1": v[len(v) // 4],
        "médiane": v[len(v) // 2],
        "q3": v[(3 * len(v)) // 4],
        "max": v[-1],
    }


@dataclass
class Measure:
    defined_on: str
    values: list[Decimal] = field(default_factory=list)
    absent: Counter[str] = field(default_factory=Counter)

    def report(self) -> dict[str, Any]:
        return {"défini_sur": self.defined_on, "valeurs": _stats(self.values), "absences": dict(self.absent)}


PIP = Decimal("0.0001")


def flag_bars(
    c: Configuration, m15: Mapping[datetime, Any], trigger_bars: Mapping[datetime, Any], step: timedelta
) -> list[Mapping[str, Any]]:
    """Pause M15 after the last peak, then the trigger candles read from F to the last one examined."""
    out = [m15[s] for s in c.pause_starts if s in m15]
    if c.flag_utc is not None and c.last_examined_start is not None:
        cursor = c.flag_utc
        while cursor <= c.last_examined_start:
            if cursor in trigger_bars and bar_ok(trigger_bars[cursor]):
                out.append(trigger_bars[cursor])
            cursor += step
    return out


def measures(paths: list[SessionPath], engine: Day02Backtest) -> dict[str, Any]:
    """Each measure names the configurations it is defined on; an undefined value is counted absent
    with its reason, never invented nor dropped silently."""
    step = engine.day02.trigger_step
    m: dict[str, Measure] = {
        "A_pips": Measure("configurations"),
        "I_pips": Measure("configurations"),
        "I_sur_A": Measure("configurations"),
        "impulsion_M15_reconnaissance": Measure("configurations"),
        "impulsion_M15_finale": Measure("configurations"),
        "extensions": Measure("configurations"),
        "pente_sur_A": Measure("drapeaux formés"),
        "profondeur_bid_sur_I": Measure("drapeaux formés (bid, achat et vente)"),
        "extrême_ask_stop_vente": Measure("sorties confirmées à la vente (ask_high du drapeau)"),
        "D_moins_F_bougies": Measure("sorties confirmées"),
        "D_moins_fin_p_minutes": Measure("sorties confirmées"),
        "E_moins_S_pips": Measure("sorties confirmées"),
        "T_moins_E_pips": Measure("sorties confirmées"),
        "E_moins_S_sur_A": Measure("sorties confirmées"),
        "approché_clôture_moins_S_pips": Measure("sorties confirmées (indicateur approché, clôture de sortie)"),
        "approché_T_moins_clôture_pips": Measure("sorties confirmées (indicateur approché, clôture de sortie)"),
    }
    beyond_target = 0
    for path in paths:
        for c in path.configurations:
            long = c.side is Side.LONG
            m["A_pips"].values.append(c.atr / PIP)
            m["I_pips"].values.append(c.amplitude / PIP)
            m["I_sur_A"].values.append(c.amplitude / c.atr)
            m["impulsion_M15_reconnaissance"].values.append(
                Decimal((c.recognised_utc - M15 - c.origin_start) // M15 + 1)
            )
            m["impulsion_M15_finale"].values.append(Decimal((c.peak_start - c.origin_start) // M15 + 1))
            m["extensions"].values.append(Decimal(len(c.extensions)))
            formed = ("pente_sur_A", "profondeur_bid_sur_I")
            exits = [k for k, v in m.items() if v.defined_on.startswith("sorties")]
            if c.flag_utc is None:
                for k in formed:
                    m[k].absent[NOT_FORMED] += 1
            else:
                m["pente_sur_A"].values.append(got(c.slope))
                bars = flag_bars(c, engine.m15, engine.trigger_bars, step)
                extreme = min(b["bid_low"] for b in bars) if long else max(b["bid_high"] for b in bars)
                m["profondeur_bid_sur_I"].values.append(abs(c.peak - extreme) / c.amplitude)
            if c.outcome != EXIT:
                reason = NOT_FORMED if c.flag_utc is None else NO_EXIT
                for k in exits:
                    if k != "extrême_ask_stop_vente" or not long:
                        m[k].absent[reason] += 1
                continue
            d, stop, target = got(c.ended_utc), got(c.stop), got(c.target)
            if not long:
                m["extrême_ask_stop_vente"].values.append(got(c.flag_extreme))
            exit_bar = engine.trigger_bars[d - step]
            close = exit_bar["bid_close"]
            sign = 1 if long else -1
            m["D_moins_F_bougies"].values.append(Decimal((d - got(c.flag_utc)) // step))
            m["D_moins_fin_p_minutes"].values.append(Decimal((d - c.peak_start - M15) // timedelta(minutes=1)))
            m["E_moins_S_pips"].values.append(sign * (c.peak - stop) / PIP)
            m["T_moins_E_pips"].values.append(sign * (target - c.peak) / PIP)
            m["E_moins_S_sur_A"].values.append(sign * (c.peak - stop) / c.atr)
            m["approché_clôture_moins_S_pips"].values.append(sign * (close - stop) / PIP)
            m["approché_T_moins_clôture_pips"].values.append(sign * (target - close) / PIP)
            beyond_target += (long and close >= target) or (not long and close <= target)
    return {
        **{k: v.report() for k, v in m.items()},
        "approché_clôture_de_sortie_au_delà_de_T": beyond_target,
        "note": "indicateurs approchés : clôture de la bougie de sortie, pas la cotation à D (non supposée égale)",
    }


def descriptions(paths: list[SessionPath], engine: Day02Backtest) -> dict[str, Any]:
    by_side: Counter[str] = Counter()
    by_clock: dict[str, Counter[str]] = defaultdict(Counter)
    examined_hour: Counter[str] = Counter()
    exit_hour: Counter[str] = Counter()
    for path in paths:
        clock = clocks(path.day)
        by_clock[clock]["séances"] += 1
        for line in path.searches:
            for e in line.search.examined:
                examined_hour[e.t_utc.astimezone(LONDON).strftime("%H")] += 1
            c = line.configuration
            if c is None:
                continue
            examined_hour[c.recognised_utc.astimezone(LONDON).strftime("%H")] += 1
            by_side[c.side.value] += 1
            by_clock[clock]["configurations"] += 1
            if c.outcome == EXIT:
                by_clock[clock]["sorties_confirmées"] += 1
                exit_hour[got(c.ended_utc).astimezone(LONDON).strftime("%H")] += 1
    return {
        "par_sens": dict(by_side),
        "par_heure_légale": {k: dict(v) for k, v in by_clock.items()},
        "m15_examinées_par_heure": dict(sorted(examined_hour.items())),
        "sorties_par_heure": dict(sorted(exit_hour.items())),
        "mesures": measures(paths, engine),
    }


# ---------------------------------------------------------------- coverage (§4.4)


def bar_cause(bar: Mapping[str, Any] | None) -> str:
    """Why a candle is not OK at its close, first cause in a fixed order."""
    if bar is None:
        return "absente"
    flags = list(bar["flags_at_close"])
    content = bar["content"]
    if content is Content.EMPTY or NO_TICK in flags:
        return "sans tick"
    if content is Content.INVALID_ONLY or NO_VALID_TICK in flags:
        return "ticks invalides seulement"
    if any(f.startswith("trou de cotation") for f in flags):
        return "silence > 5 min"
    if any(f.startswith(SUBSLOTS_FLAG) for f in flags):
        return "sous-créneau M5 vide"
    if "jour férié probable" in flags:
        return "jour férié probable"
    return "autre"


def silences(m5: Sequence[Mapping[str, Any]]) -> list[tuple[datetime, datetime, float]]:
    """Silences strictly longer than 5 min of expected-open time between consecutive valid ticks, read
    from the audited M5 (last and first valid tick of consecutive candles with a valid tick). A silence
    longer than 5 min cannot lie inside one M5: every such silence spans two candles."""
    valid = [b for b in m5 if b["content"] is Content.VALID and b["first_tick_utc"] is not None]
    out = []
    for before, after in itertools.pairwise(valid):
        start, end = before["last_tick_utc"], after["first_tick_utc"]
        # Same classification as the engine: exact duration first, then expected-open time.
        if classify_silence(start, end, SILENCE) is Silence.UNEXPLAINED:
            out.append((start, end, expected_open_minutes(start, end)))
    return out


def coverage(days: list[date], m5: Sequence[Mapping[str, Any]], m15: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Needed coverage (07:00-15:00, recognition and exit) and descriptive coverage of the whole DAY_02
    window (07:00-17:00): candles not OK by cause, and silences > 5 min intersecting each window."""
    rows = {Grid.M5: {b["start_utc"]: b for b in m5}, Grid.M15: {b["start_utc"]: b for b in m15}}
    found = silences(m5)
    starts = [s for s, _, _ in found]
    out: dict[str, Any] = {"source_des_silences": "M5 auditées à 5 min : dernier et premier tick valides"}
    for name, (lo, hi) in (("nécessaire_07_15", NEEDED), ("complète_07_17", FULL)):
        part: dict[str, Any] = {}
        for grid, step in ((Grid.M15, M15), (Grid.M5, M5)):
            expected, causes = 0, Counter[str]()
            for day in days:
                cursor = london(day, lo)
                while cursor < london(day, hi):
                    expected += 1
                    bar = rows[grid].get(cursor)
                    if not bar_ok(bar):
                        causes[bar_cause(bar)] += 1
                    cursor += step
            part[grid.value] = {"créneaux": expected, "non_ok": sum(causes.values()), "causes": dict(causes)}
        distinct: set[tuple[datetime, datetime]] = set()
        crossings, minutes, sessions = 0, 0.0, 0
        for day in days:
            a, b = london(day, lo), london(day, hi)
            hits = [(s, e) for s, e, _ in found[: bisect.bisect_left(starts, b)] if e > a]
            sessions += bool(hits)
            crossings += len(hits)
            distinct.update(hits)
            minutes += sum(expected_open_minutes(max(s, a), min(e, b)) for s, e in hits)
        part["silences_plus_de_5_min"] = {
            "silences_distincts": len(distinct),  # each silence once, however many windows it crosses
            "intersections_silence_séance": crossings,  # one per (silence, session window) pair
            "minutes_dans_les_fenêtres": round(minutes, 3),
            "séances_touchées": sessions,
        }
        out[name] = part
    return out


# ---------------------------------------------------------------- report


def check(errors: list[str], **extra: Any) -> dict[str, Any]:
    return {"ok": not errors, "error_count": len(errors), "errors": errors[:50], **extra}


def detail_lines(paths: list[SessionPath]) -> list[dict[str, Any]]:
    lines = []
    for path in paths:
        lines.append(
            {
                "day": path.day,
                "trigger": path.trigger.value,
                "searches": [
                    {
                        "resume_utc": s.resume_utc,
                        "resume_after": s.resume_after,
                        "examined": [{"t_utc": e.t_utc, "cause": e.cause} for e in s.search.examined],
                        "configuration": None if s.configuration is None else vars(s.configuration),
                    }
                    for s in path.searches
                ],
            }
        )
    return lines


def availability(
    bars: Mapping[Grid, Sequence[dict[str, Any]]],
    h1: Sequence[dict[str, Any]],
    gaps: Sequence[Gap],
    config: ResearchConfig,
    start: datetime,
    end: datetime,
    *,
    official: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    weekdays, excluded = calendar_days(start, end)
    days = study_days(start, end)
    c1 = []
    if sorted(set(weekdays) - set(excluded)) != days:
        c1.append("séances du moteur différentes du calendrier construit indépendamment")
    found = {"weekdays": len(weekdays), "excluded": len(excluded), "sessions": len(days)}
    if official and found != CALENDAR_ANCHOR:
        c1.append(f"calendrier {found} ≠ ancrage {CALENDAR_ANCHOR}")
    paths: dict[Trigger, list[SessionPath]] = {}
    engines: dict[Trigger, Day02Backtest] = {}
    for trigger in TRIGGERS:
        paths[trigger], engines[trigger] = run_trajectory(
            trigger, bars[Grid.M5], bars[Grid.M15], h1, gaps, config, days
        )
    every = [p for t in TRIGGERS for p in paths[t]]
    m15_rows = {b["start_utc"]: b for b in bars[Grid.M15]}  # separate dictionary for the recomputation
    params_diff = {k for k, v in vars(PARAMS[Trigger.M5]).items() if vars(PARAMS[Trigger.M15])[k] != v}
    checks = {
        "C1": check(c1, calendrier=found, ancrage=CALENDAR_ANCHOR if official else None),
        "C2": check(conservation_errors(every)),
        "C3": check(resume_errors(every)),
        "C4": check(bound_errors(every, m15_rows)),
        "C5": check(reuse_errors(every)),
        "C6": check(
            [e for t in TRIGGERS for e in c6_errors(paths[t], m15_rows, engines[t].atr_at)],
            portée="première configuration de chaque séance, séances sans configuration comprises",
        ),
        "C7": check(c7_errors(paths[Trigger.M5], paths[Trigger.M15])),
        "C8": check(c8_errors(every)),
        "C9": check(
            [] if params_diff == {"trigger"} else [f"paramètres différents : {sorted(params_diff)}"],
            paramètres={t.value: vars(PARAMS[t]) for t in TRIGGERS},
            ticks_lus=sum(e._last_tick is not None for e in engines.values()),
        ),
    }
    if checks["C9"]["ticks_lus"]:
        checks["C9"] = check(["ticks lus"], **{k: v for k, v in checks["C9"].items() if k not in ("ok", "errors")})
    report = {
        "tool": TOOL,
        "window": {"start": start, "end": end, "officielle": official},
        "note": "une sortie confirmée est un instant D, pas une entrée ; parcours sans position",
        "checks": checks,
        "comptes": {t.value: counts(paths[t]) for t in TRIGGERS},
        "descriptions": {t.value: descriptions(paths[t], engines[t]) for t in TRIGGERS},
        "couverture": coverage(days, bars[Grid.M5], bars[Grid.M15]),
    }
    return report, detail_lines(every)


def withhold(report: dict[str, Any]) -> dict[str, Any]:
    kept = ("tool", "window", "note", "checks", "failed_checks", "inputs")
    return {k: v for k, v in report.items() if k in kept} | {"résultats": "masqués : contrôle en échec"}


def to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# DAY_02 — disponibilité des données (rapport agrégé)",
        "",
        report["note"],
        "",
        "| Contrôle | Conforme |",
        "|---|---|",
    ]
    lines += [f"| {k} | {'oui' if v['ok'] else 'non'} |" for k, v in report["checks"].items()]
    for trigger, by in report.get("comptes", {}).items():
        total = by["total"]["comptes"]
        lines += ["", f"## {trigger}", ""] + [f"- {k} : {v}" for k, v in total.items()]
    return "\n".join(lines) + "\n"


def _date(text: str) -> datetime:
    return datetime.combine(date.fromisoformat(text), time(), tzinfo=UTC)


def main(argv: list[str] | None = None) -> int:
    launch = provenance(argv, TOOL)
    parser = argparse.ArgumentParser(prog=TOOL, description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--start", type=_date, default=_date("2015-01-01"))
    parser.add_argument("--end", type=_date, default=_date("2022-01-01"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--details-out", type=Path, required=True)
    args = parser.parse_args(argv)
    require_development_window(args.start, args.end)
    directory = args.data_dir / "bars" / SOURCE / INSTRUMENT
    candles = {g: directory / LOT / f"{g.value}.parquet" for g in Grid}
    h1_path = directory / f"{Timeframe.H1.value}.parquet"
    quality = args.data_dir / "reports" / QUALITY_REPORT
    inputs = (*candles.values(), h1_path, quality)
    before = {path.as_posix(): sha256_file(path) for path in inputs}
    wrong = [g.value for g, path in candles.items() if before[path.as_posix()] != CANDLES_SHA256[g]]
    if before[h1_path.as_posix()] != H1_SHA256:
        wrong.append("1h")
    if wrong:
        print(f"empreintes {wrong} différentes de l'audit : aucune lecture", file=sys.stderr)
        return 2
    bars: dict[Grid, list[dict[str, Any]]] = {g: read_candles(path, args.end)[0] for g, path in candles.items()}
    h1 = load_bars(args.data_dir, SOURCE, INSTRUMENT, Timeframe.H1, args.start, args.end)
    gaps = load_gaps(quality, args.end)
    official = (args.start, args.end) == OFFICIAL_WINDOW
    report, details = availability(
        bars, h1, gaps, ResearchConfig(costs=RESEARCH_COSTS), args.start, args.end, official=official
    )
    after = {path.as_posix(): sha256_file(path) for path in inputs}
    late = [b["end_utc"] for g in Grid for b in bars[g] if b["end_utc"] > args.end]
    late += [b["end_utc"] for b in h1 if b["end_utc"] > args.end]
    c9 = report["checks"]["C9"]
    c9["inputs_sha256"] = {
        "before": before,
        "after": after,
        "unchanged": before == after,
        "références": {
            "5m": CANDLES_SHA256[Grid.M5],
            "15m": CANDLES_SHA256[Grid.M15],
            "1h": H1_SHA256,
            QUALITY_REPORT: "aucune référence historique : empreinte enregistrée au passage",
        },
    }
    extra = (["empreintes des entrées modifiées pendant le passage"] if before != after else []) + (
        [f"{len(late)} bougie(s) lue(s) après la fin"] if late else []
    )
    if official and len(gaps) != GAPS_ANCHOR:
        extra.append(f"{len(gaps)} trous chargés ≠ {GAPS_ANCHOR} (passages DAY_01)")
    if extra:
        c9["ok"], c9["error_count"], c9["errors"] = False, c9["error_count"] + len(extra), [*c9["errors"], *extra]
    finish = end_check(launch, tree_state())
    code_changed = finish["commit"] != launch["commit"] or any(
        f.startswith(CODE_PATHS) for f in finish["files_changed_during_run"]
    )
    c10 = ["arbre non propre au lancement"] if launch["uncommitted_diff_sha256"] else []
    c10 += ["code ou commit modifié pendant le passage"] if code_changed else []
    report["checks"]["C10"] = check(c10, launch=launch, end=finish)
    report["failed_checks"] = [name for name, c in report["checks"].items() if not c["ok"]]
    report["inputs"] = {"m5": len(bars[Grid.M5]), "m15": len(bars[Grid.M15]), "h1": len(h1), "gaps": len(gaps)}
    if report["failed_checks"]:
        report = withhold(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8")
    args.out.with_suffix(".md").write_text(to_markdown(jsonable(report)), encoding="utf-8")
    if not report["failed_checks"]:
        args.details_out.write_text(
            "".join(json.dumps(jsonable(d), ensure_ascii=False) + "\n" for d in details), encoding="utf-8"
        )
    print(f"contrôles en échec : {report['failed_checks'] or 'aucun'} ; rapport : {args.out}")
    return 2 if report["failed_checks"] else 0


if __name__ == "__main__":
    sys.exit(main())
