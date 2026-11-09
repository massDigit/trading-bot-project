"""DAY_02 performance run on 2015-2021 (docs/experiments/DAY02_REFERENCE_2015_2021.md). No order, no network.

    uv run forex-day02-backtest --trigger M5 --scenario A \\
        --availability data/reports/backtests/day02_availability_2015_2021_eb48d6c_details.jsonl \\
        --s1-reference data/reports/backtests/s1_ref_2015_2021_h0.json \\
        --s2-reference data/reports/backtests/s2_ref_2015_2021_h1_a.json \\
        --s3-reference data/reports/backtests/s3_ref_2015_2021_d1h4_a.json \\
        --day01-reference data/reports/backtests/day01_ref_2015_2021_m5_a.json \\
        --out data/reports/backtests/day02_ref_2015_2021_m5_a.json \\
        --sessions-out data/reports/backtests/day02_ref_2015_2021_m5_a_sessions.jsonl

One continuous trajectory per run: one trigger (M5 reference `Day02Params()`, M15 comparison
`Day02Params(trigger=Trigger.M15)`), one gap scenario (A, B, C) and one rule for a stop already
beyond at the first execution tick. The engine is unchanged: this tool only reads what it recorded
(attempts, closings, trades, journal), apart from the control recomputation on candles only.

The sequence of DAY_02 configurations depends on the positions: nothing is reconciled with the
availability study by totals. Every attempt is controlled from the resume state it really lived
(protocol §5): recomputed by `configuration_from` and by the separate C6 recomputation from its resume
instant, its resume matched with the event that authorises it, and matched with the study only where
the resume state is the same. Then the funnel from searches to trades (§6), the closing orders and
the bounds. If one control fails, the report carries the controls only and the command exits with 2.
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from datetime import time as wall
from decimal import Decimal
from pathlib import Path
from typing import Any

from forex_bot.backtest.data import load_bars, load_gaps, require_development_window, stream_ticks, tick_files
from forex_bot.backtest.day01 import LONDON, london
from forex_bot.backtest.day01_availability import CANDLES_SHA256, clocks, jsonable, read_candles
from forex_bot.backtest.day01_explore import entry_measures, ratios
from forex_bot.backtest.day02 import (
    CANCELLED_INTERRUPTION,
    ENTRY_DECIDED,
    EXECUTED,
    EXIT,
    EXPIRED,
    LIQUIDATION,
    MARKET_CLOSED,
    NO_QUOTE,
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
    Day02Params,
    Search,
    Trigger,
    configuration_from,
)
from forex_bot.backtest.day02_availability import (
    CODE_PATHS,
    EXIT_ENDS,
    FORMATION_ENDS,
    GAPS_ANCHOR,
    H1_SHA256,
    H4_SHA256,
    LOT,
    OFFICIAL_WINDOW,
    QUALITY_REPORT,
    SearchLine,
    SessionPath,
    bound_errors,
    first_configuration_view,
    independent_first,
    reuse_errors,
    study_days,
)
from forex_bot.backtest.day02_engine import Day02Backtest, Day02Result
from forex_bot.backtest.day02_variants import REFERENCE, VARIANTS, needs_h4, variant_of, variant_params
from forex_bot.backtest.engine import DecisionRecord, ResearchConfig, StopAtExecution, StopType, Trade
from forex_bot.backtest.explore import RESEARCH_COSTS, _peak_rss_mib, _trade, _trade_totals
from forex_bot.backtest.feed import Silence, Tick
from forex_bot.backtest.s2 import GapScenario
from forex_bot.backtest.s2_engine import RelativeDrawdown
from forex_bot.backtest.s3_explore import Recovery, YearlyDrawdowns, concentration, months, years
from forex_bot.history.calendar import Timeframe, trading_day
from forex_bot.history.intraday import Grid
from forex_bot.history.intraday_audit import end_check, provenance, sha256_file, tree_state
from forex_bot.history.store import HistoryStore
from forex_bot.risk import Side

SOURCE, INSTRUMENT = "dukascopy", "EURUSD"
TOOL = "forex-day02-backtest"
SCENARIOS = {"A": GapScenario.OBSERVED_ONLY, "B": GapScenario.STOP_FIRST, "C": GapScenario.TARGET_FIRST}
# Availability study eb48d6c on the official window (DAY02_AVAILABILITY_2015_2021_BILAN.md §1, ADR-033).
STUDY_SHA256 = "775e4bba4a6492af4f054a415ff75cb3c125c5aa1fd9f46ee33dfd0efba69ddc"
OFFICIAL_LINES, OFFICIAL_DATES = 3632, 1816
EXECUTION_LIMIT = wall(15, 5)  # no execution after 15:05:00 London (sheet §5.6)
WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
PIP = Decimal("0.0001")

# At D: one refusal of the engine, or a decided entry (sheet §5.6). POSITION_OPEN cannot happen: the
# search is suspended while an entry is pending or a position is open; it is an anomaly if seen.
REFUSALS_AT_D = (MARKET_CLOSED, NO_QUOTE, STOP_INADMISSIBLE, TARGET_PASSED, SIZE_REFUSED)
EXECUTED_OUTCOMES = (EXECUTED, STOP_AT_EXECUTION, TARGET_AT_EXECUTION)  # an entry filled, even if exited at once
NOT_EXECUTED_OUTCOMES = (REJECTED_AT_EXECUTION, EXPIRED, CANCELLED_INTERRUPTION)
NO_CONFIGURATION = "sans configuration jusqu'à la fin de fenêtre"  # normal end of a search: nothing to end

# Exclusive outcome of an executed entry, from the engine's closing reason, which is kept as is.
CLOSED_STOP = "sortie liée au stop"
CLOSED_TARGET = "clôturée à la cible"
OPEN_AT_END = "ouverte à la fin de l'étude"
EXIT_OUTCOMES = (CLOSED_STOP, CLOSED_TARGET, TIME_EXIT, LIQUIDATION, OPEN_AT_END)
STOP_BEYOND_AT_EXECUTION = "STOP_FRANCHI_À_L'EXÉCUTION"  # filled then liquidated at the observed price
EXIT_CATEGORY = {
    "STOP_OBSERVÉ": CLOSED_STOP,
    "STOP_FERMETURE_CONNUE": CLOSED_STOP,
    "STOP_APRÈS_INTERRUPTION": CLOSED_STOP,
    "STOP_SCÉNARIO_B": CLOSED_STOP,
    STOP_BEYOND_AT_EXECUTION: CLOSED_STOP,
    "CIBLE": CLOSED_TARGET,
    "CIBLE_APRÈS_FERMETURE": CLOSED_TARGET,
    "CIBLE_APRÈS_INTERRUPTION": CLOSED_TARGET,
    "CIBLE_SCÉNARIO_C": CLOSED_TARGET,
    TARGET_AT_EXECUTION: CLOSED_TARGET,
    TIME_EXIT: TIME_EXIT,
    LIQUIDATION: LIQUIDATION,
}
IMMEDIATE_EXIT = {STOP_AT_EXECUTION: STOP_BEYOND_AT_EXECUTION, TARGET_AT_EXECUTION: TARGET_AT_EXECUTION}
# Annotations overlap the exclusive outcomes; they are never added up as exits.
INDETERMINATE = "indéterminée"
CLOSE_AFTER_INTERRUPTION = "clôture après interruption"
COINCIDENT = "échéances simultanées"
PENDING_CLOSING = "clôture en attente à la fin"
ANNOTATIONS = (INDETERMINATE, UNPLANNED_NIGHT, CLOSE_AFTER_INTERRUPTION, COINCIDENT, PENDING_CLOSING)
STOP_DISTANCE = "P_D − S : prix d'entrée estimé à D jusqu'au stop, en pips et en multiples de A (ATR H1 figé)"
APPROXIMATION_GAP = (
    "|P_D − S| moins |clôture bid de la bougie de sortie − S|, en pips, sorties confirmées des tentatives "
    "rapprochées de l'étude : (ask à D − clôture bid) à l'achat, (clôture bid − bid à D) à la vente ; "
    "P_D est l'ask à D à l'achat, le bid à D à la vente"
)


# ---------------------------------------------------------------------- run


class Day02Run(Day02Backtest):
    """The DAY_02 engine, plus observation only: tick drawdowns (global, yearly, relative), recovery,
    and the first and last tick read."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.yearly = YearlyDrawdowns()
        self.relative = RelativeDrawdown(self.config.initial_equity)
        self.recovery = Recovery(self.config.initial_equity)
        self.ticks_read = 0
        self.first_tick_utc: datetime | None = None
        self.last_tick_utc: datetime | None = None

    def _observe(self, tick: Tick) -> None:
        equity = self.balance + self._unrealized(tick)  # once per tick for every measure
        self.drawdown.observe(tick.ts_utc, equity)
        position = self.position
        self.relative.observe(tick.ts_utc, equity, None if position is None else position.decided_utc.isoformat())
        self.recovery.observe(tick.ts_utc, equity)
        self.yearly.observe(tick.ts_utc, equity)
        self.ticks_read += 1
        self.first_tick_utc = self.first_tick_utc or tick.ts_utc
        self.last_tick_utc = tick.ts_utc


def all_trades(result: Day02Result) -> list[Trade]:
    return [*result.trades, *([result.open_trade] if result.open_trade else [])]


def d_of(attempt: Attempt) -> datetime | None:
    """D of a decided entry, the key of its trade (Trade.decided_utc)."""
    return None if attempt.decision is None else attempt.decision["d_utc"]


def trade_of(attempt: Attempt, by_decision: Mapping[datetime, Trade]) -> Trade | None:
    d = d_of(attempt)
    return None if d is None or attempt.entry_outcome not in EXECUTED_OUTCOMES else by_decision.get(d)


def exit_outcome(trade: Trade) -> str:
    if trade.exit_utc is None:
        return OPEN_AT_END
    return EXIT_CATEGORY.get(trade.exit_reason or "", f"autre ({trade.exit_reason})")


def by_session(attempts: Iterable[Attempt]) -> dict[date, list[Attempt]]:
    out: dict[date, list[Attempt]] = defaultdict(list)
    for a in attempts:
        out[a.day].append(a)
    return out


# ---------------------------------------------------------------------- §5.1 recomputation from the resume


def recompute_errors(result: Day02Result, engine: Day02Backtest) -> list[str]:
    """Each attempt recomputed by `configuration_from` from its own resume instant, on candles only (no
    tick, no position), field by field: examined closes and causes, then the whole configuration."""
    errors = []
    for a in result.attempts:
        again = configuration_from(
            a.resume_utc, a.day, engine.m15, engine.trigger_bars, engine.atr_at, result.day02_params, engine.context_at
        )
        if again != a.search:
            errors.append(f"{a.day} reprise {a.resume_utc.isoformat()} : recherche différente du recalcul")
    return errors


def independent_errors(result: Day02Result, engine: Day02Backtest) -> list[str]:
    """C6 of the study on every attempt, from its resume instant: separate recomputation of the
    recognition and of the formation (shared H1 ATR); attempts without configuration included."""
    rows = dict(engine.m15)  # separate dictionary for the recomputation
    errors = []
    for a in result.attempts:
        mine = first_configuration_view(a.search.configuration)
        other = independent_first(
            a.day, rows, engine.atr_at, resume=a.resume_utc, params=result.day02_params, context=engine.context_at
        )
        if mine != other:
            errors.append(f"{a.day} reprise {a.resume_utc.isoformat()} : {mine} ≠ recalcul {other}")
    return errors


def session_paths(result: Day02Result) -> list[SessionPath]:
    """The attempts in the shape of the study's paths, for its bound (C4) and reuse (C5) checks."""
    trigger = result.day02_params.trigger
    return [
        SessionPath(day, trigger, [SearchLine(a.resume_utc, a.resume_after, a.search) for a in attempts])
        for day, attempts in sorted(by_session(result.attempts).items())
    ]


def recomputation(result: Day02Result, engine: Day02Backtest) -> dict[str, Any]:
    p = result.day02_params
    paths, rows = session_paths(result), dict(engine.m15)
    parts = {
        "configuration_from": recompute_errors(result, engine),
        "recalcul_distinct_C6": independent_errors(result, engine),
        "bornes_C4": bound_errors(paths, rows, {p.trigger: p}),
        "bougies_non_réutilisées_C5": reuse_errors(paths, {p.trigger: p}),
    }
    errors = [f"{name} : {e}" for name, items in parts.items() for e in items]
    return {
        "ok": not errors,
        "attempts": len(result.attempts),
        "error_count": len(errors),
        "errors": errors[:50],
        "portée_C6": "reconnaissance et formation recalculées séparément depuis chaque reprise ; ATR H1 partagé",
    }


# ---------------------------------------------------------------------- §5.2 resumes and their events


def expected_end(attempt: Attempt, trade: Trade | None) -> tuple[datetime | None, str | None]:
    """The event that ends an attempt, read from the engine's records (sheet §5.7): none for a search
    without configuration (a normal end) or for a position still open at the end of the study."""
    c = attempt.search.configuration
    if c is None:
        return None, None
    if c.outcome != EXIT:
        return c.ended_utc, c.outcome
    if attempt.at_d != ENTRY_DECIDED:
        return c.ended_utc, attempt.at_d
    if attempt.entry_outcome in NOT_EXECUTED_OUTCOMES:
        return attempt.entry_outcome_utc, attempt.entry_outcome
    if trade is None or trade.exit_utc is None:
        return None, None
    return trade.exit_utc, POSITION_CLOSED


def resumes(result: Day02Result, days: Sequence[date]) -> dict[str, Any]:
    """Every resume against the event that authorises it. Within a session, a resume is the end of the
    previous attempt. The first one of a session is 07:00 when nothing is held then, or the close of the
    position held at 07:00 (its exit tick, if later); a session without any search is justified by a
    position still held at its last recognition. A search ending without configuration has no end."""
    p, errors = result.day02_params, []
    trades = all_trades(result)
    by_decision = {t.decided_utc: t for t in trades}
    sessions = by_session(result.attempts)
    skipped = dict(result.skipped_days)
    stray = sorted(set(sessions) - set(days))
    errors += [f"tentative le {d}, hors des séances de l'étude" for d in stray]
    errors += [f"{d} : séance de l'étude marquée « {skipped[d]} »" for d in days if d in skipped and d in sessions]
    for a in result.attempts:
        trade = trade_of(a, by_decision)
        expected = expected_end(a, trade)
        if (a.ended_utc, a.ended_by) != expected:
            errors.append(
                f"{a.day} {a.resume_utc.isoformat()} : fin ({a.ended_utc}, {a.ended_by}) ≠ événement {expected}"
            )
        if a.at_d == POSITION_OPEN:
            errors.append(f"{a.day} {a.resume_utc.isoformat()} : abstention « position déjà ouverte » à D")
        if a.search.configuration is not None and expected == (None, None) and trade is not result.open_trade:
            errors.append(f"{a.day} {a.resume_utc.isoformat()} : tentative sans fin hors position ouverte à la fin")
    delayed: list[dict[str, Any]] = []
    prevented: list[dict[str, Any]] = []
    for day in days:
        start, last = london(day, p.impulse_start), london(day, p.last_recognition)
        held = [t for t in trades if t.entry_utc < start and (t.exit_utc is None or t.exit_utc >= start)]
        attempts = sessions.get(day, [])
        if not attempts:
            still = [t for t in held if t.exit_utc is None or t.exit_utc >= last]
            if still and day in skipped:
                prevented.append({"day": day, "position_decided_utc": still[0].decided_utc, "reason": skipped[day]})
            else:
                errors.append(f"{day} : séance sans recherche, non justifiée par une position encore ouverte")
            continue
        first = attempts[0]
        if first.resume_after == SESSION_START:
            if first.resume_utc != start or held:
                errors.append(f"{day} : début de séance {first.resume_utc.isoformat()} ≠ 07:00 sans position")
        elif first.resume_after == POSITION_CLOSED:
            exit_utc = held[0].exit_utc if len(held) == 1 else None
            if exit_utc is None or first.resume_utc != max(start, exit_utc):
                errors.append(f"{day} : reprise {first.resume_utc.isoformat()} sans clôture d'une position de 07:00")
            else:
                delayed.append({"day": day, "position_decided_utc": held[0].decided_utc, "resume_utc": exit_utc})
        else:
            errors.append(f"{day} : première reprise « {first.resume_after} »")
        for before, after in itertools.pairwise(attempts):
            if before.ended_utc is None or (after.resume_utc, after.resume_after) != (
                before.ended_utc,
                before.ended_by,
            ):
                errors.append(
                    f"{day} : reprise {after.resume_utc.isoformat()} ({after.resume_after}) "
                    f"≠ fin ({before.ended_utc}, {before.ended_by})"
                )
        final = attempts[-1]
        if final.search.configuration is not None:
            trade = trade_of(final, by_decision)
            if trade is None:
                errors.append(f"{day} : dernière tentative terminée sans reprise suivante")
            elif trade.exit_utc is not None and trade.exit_utc < last:
                errors.append(f"{day} : clôture {trade.exit_utc.isoformat()} avant 14:15 sans reprise suivante")
    for t in trades:
        end = t.exit_utc or result.end_utc
        inside = [a for a in result.attempts if t.decided_utc < a.resume_utc and (end is None or a.resume_utc < end)]
        errors += [f"reprise {a.resume_utc.isoformat()} pendant la position de D {t.decided_utc}" for a in inside]
    return {
        "ok": not errors,
        "error_count": len(errors),
        "errors": errors[:50],
        "first_resume_delayed": delayed,
        "sessions_without_search": prevented,
        "searches_without_configuration": sum(1 for a in result.attempts if a.search.configuration is None),
    }


# ---------------------------------------------------------------------- §5.3 partial match with the study


StudyLines = dict[tuple[str, str], dict[str, Any]]


def study_lines(rows: Iterable[dict[str, Any]], official: bool) -> tuple[StudyLines, list[str]]:
    """Lines of the availability study by (London date, trigger); a duplicate couple is refused before
    it is inserted, then each date must hold exactly one M5 and one M15 line."""
    lines: StudyLines = {}
    errors, count = [], 0
    for row in rows:
        count += 1
        key = (str(row["day"]), str(row["trigger"]))
        if key in lines:
            errors.append(f"étude : doublon du couple {key} à la ligne {count}")
            continue
        lines[key] = row
    days = {d for d, _ in lines}
    incomplete = sorted(d for d in days if any((d, t.value) not in lines for t in Trigger))
    if incomplete:
        errors.append(f"étude : {len(incomplete)} date(s) sans une ligne M5 et une ligne M15 : {incomplete[:5]}")
    if official and (count, len(days)) != (OFFICIAL_LINES, OFFICIAL_DATES):
        errors.append(f"étude : {count} lignes et {len(days)} dates, au lieu de {OFFICIAL_LINES} et {OFFICIAL_DATES}")
    return lines, errors


def search_view(search: Search) -> dict[str, Any]:
    """A search in the study's detail format (resume, examined closes, configuration), as read back."""
    c = search.configuration
    view = {
        "resume_utc": search.resume_utc,
        "examined": [{"t_utc": e.t_utc, "cause": e.cause} for e in search.examined],
        "configuration": None if c is None else vars(c),
    }
    out: dict[str, Any] = json.loads(json.dumps(jsonable(view)))
    return out


def reconcile(
    study: StudyLines, study_errors: list[str], result: Day02Result, days: Sequence[date]
) -> tuple[dict[str, Any], set[int]]:
    """Field by field with the study where the resume state is the same: the first search of every
    session that starts at 07:00, and any other attempt resuming at the instant of a study search of the
    same session. The other attempts are controlled by §5.1 only; no total is compared."""
    trigger = result.day02_params.trigger.value
    errors, differences = list(study_errors), []
    theirs = {d: row for (d, t), row in study.items() if t == trigger}
    sessions = by_session(result.attempts)
    matched: set[int] = set()  # id() of the attempts matched with the study
    first_compared = other_compared = 0
    excluded = []
    for day in days:
        row = theirs.get(day.isoformat())
        if row is None:
            errors.append(f"{day} : absente de l'étude")
            continue
        searches = {s["resume_utc"]: s for s in row["searches"]}
        attempts = sessions.get(day, [])
        at_start = bool(attempts) and attempts[0].resume_after == SESSION_START
        if not at_start:
            excluded.append(day)
        for i, a in enumerate(attempts):
            ref = searches.get(a.resume_utc.isoformat())
            if ref is None:
                if i == 0 and at_start:
                    errors.append(f"{day} : première recherche de l'étude absente à {a.resume_utc.isoformat()}")
                continue
            first_compared += i == 0 and at_start
            other_compared += not (i == 0 and at_start)
            mine = search_view(a.search)
            for key in ("examined", "configuration"):
                if mine[key] != ref[key]:
                    differences.append({"day": day, "resume_utc": a.resume_utc, "field": key})
            matched.add(id(a))
    tallies: dict[str, dict[str, Counter[str]]] = {name: defaultdict(Counter) for name in ("passage", "étude")}
    different = 0
    for day in days:
        study_searches = theirs.get(day.isoformat(), {}).get("searches", [])
        ends = {
            "passage": [c.outcome for a in sessions.get(day, []) if (c := a.search.configuration) is not None],
            "étude": [s["configuration"]["outcome"] for s in study_searches if s["configuration"] is not None],
        }
        for name, outcomes in ends.items():
            for key in ("total", str(day.year)):
                tallies[name][key]["configurations"] += len(outcomes)
                tallies[name][key]["sorties_confirmées"] += outcomes.count(EXIT)
        resumed = [a.resume_utc.isoformat() for a in sessions.get(day, [])]
        different += resumed != [s["resume_utc"] for s in study_searches]
    report = {
        "ok": not (errors or differences),
        "key": "date de séance de Londres, instant de reprise",
        "first_searches_compared": first_compared,
        "other_attempts_compared": other_compared,
        "sessions_excluded_first_resume_not_at_07_00": excluded,
        "difference_count": len(differences),
        "differences": jsonable(differences[:50]),
        "errors": errors[:50],
        "side_by_side": {
            "note": "comptes côte à côte, aucune égalité exigée",
            **{name: {k: dict(v) for k, v in sorted(t.items())} for name, t in tallies.items()},
            "sessions_with_another_resume_sequence": different,
        },
    }
    return report, matched


# ---------------------------------------------------------------------- §6 funnel


def funnel(attempts: Sequence[Attempt], trades: Sequence[Trade]) -> dict[str, Any]:
    """Searches -> configurations -> flags formed -> confirmed exits -> refusal at D or decided entry
    -> entry outcome -> exclusive outcome of an executed entry, annotations beside. The end for unusable
    data after F is an outcome of the formed flags. Read from the engine's records only."""
    configs = [a for a in attempts if a.search.configuration is not None]
    before_f: Counter[str] = Counter()
    after_f: Counter[str] = Counter()
    formed = confirmed = 0
    for c in (a.search.configuration for a in configs):
        if c is None:
            continue
        if c.flag_utc is None:
            before_f[str(c.outcome)] += 1
        else:
            formed += 1
            after_f[str(c.outcome)] += 1
            confirmed += c.outcome == EXIT
    exits = [a for a in configs if a.search.configuration is not None and a.search.configuration.outcome == EXIT]
    at_d = Counter(a.at_d or "anomalie : aucune décision" for a in exits)
    decided = [a for a in exits if a.at_d == ENTRY_DECIDED]
    entries = Counter(a.entry_outcome or "anomalie : aucune issue" for a in decided)
    executed = {d: a for a in decided if a.entry_outcome in EXECUTED_OUTCOMES and (d := d_of(a)) is not None}
    unexecuted = {d for a in decided if a.entry_outcome not in EXECUTED_OUTCOMES and (d := d_of(a)) is not None}
    per_entry = Counter(t.decided_utc for t in trades)
    by_decision = {t.decided_utc: t for t in trades}
    outcomes: Counter[str] = Counter()
    reasons: dict[str, Counter[str]] = defaultdict(Counter)
    immediate_ok = True
    for d, a in executed.items():
        trade = by_decision.get(d)
        if trade is None:
            continue
        category = exit_outcome(trade)
        outcomes[category] += 1
        reasons[category][trade.exit_reason or "—"] += 1
        expected = IMMEDIATE_EXIT.get(str(a.entry_outcome))
        immediate_ok &= trade.exit_reason == expected if expected else trade.exit_reason not in IMMEDIATE_EXIT.values()
    confirmed_ids = {id(a) for a in exits}
    stray = [a for a in attempts if id(a) not in confirmed_ids and (a.at_d is not None or a.decision is not None)]
    checks = {
        "configurations_conserved": len(configs) == sum(before_f.values()) + formed
        and set(before_f) <= set(FORMATION_ENDS),
        "formed_flags_conserved": formed == sum(after_f.values()) and set(after_f) <= set(EXIT_ENDS),
        "no_decision_without_confirmed_exit": not stray,
        "every_confirmation_classified_once": sum(at_d.values()) == confirmed
        and all(k == ENTRY_DECIDED or k in REFUSALS_AT_D for k in at_d),
        "decided_equals_sum_of_entry_outcomes": sum(entries.values()) == len(decided)
        and all(k in EXECUTED_OUTCOMES or k in NOT_EXECUTED_OUTCOMES for k in entries),
        "one_trade_per_executed_entry": all(per_entry[d] == 1 for d in executed),
        "no_trade_for_an_unexecuted_entry": all(per_entry[d] == 0 for d in unexecuted),
        "every_trade_from_an_executed_entry": set(per_entry) <= set(executed),
        "one_exclusive_outcome_per_executed_entry": sum(outcomes.values()) == len(executed)
        and all(k in EXIT_OUTCOMES for k in outcomes),
        "immediate_exits_keep_their_reason": immediate_ok,
    }
    return {
        "searches": len(attempts),
        "searches_outcomes": {NO_CONFIGURATION: len(attempts) - len(configs), "configuration": len(configs)},
        "configurations": len(configs),
        "configuration_outcomes": {**{k: before_f.get(k, 0) for k in FORMATION_ENDS}, "drapeau formé": formed},
        "flags_formed": formed,
        "flag_outcomes": {k: after_f.get(k, 0) for k in EXIT_ENDS},
        "confirmed_exits": confirmed,
        "at_d": {**{k: at_d.get(k, 0) for k in (*REFUSALS_AT_D, ENTRY_DECIDED)}, **{k: v for k, v in at_d.items()
                 if k not in (*REFUSALS_AT_D, ENTRY_DECIDED)}},
        "entries_decided": len(decided),
        "entry_outcomes": {k: entries.get(k, 0) for k in (*EXECUTED_OUTCOMES, *NOT_EXECUTED_OUTCOMES)},
        "entries_executed": len(executed),
        "entries_not_executed": len(unexecuted),
        "executed_outcomes": {k: outcomes.get(k, 0) for k in EXIT_OUTCOMES},
        "closing_reasons": {k: dict(v.most_common()) for k, v in reasons.items()},
        "checks": checks,
        "ok": all(checks.values()),
    }  # fmt: skip


def counts(flow: dict[str, Any]) -> dict[str, Any]:
    """A funnel without its controls, which hold on the whole run only."""
    return {k: v for k, v in flow.items() if k not in ("checks", "ok")}


def trade_annotations(result: Day02Result) -> dict[datetime, list[str]]:
    """Per trade (by its D): annotations that overlap its exclusive outcome."""
    nights = set(result.unplanned_nights)
    closings = {q.closed_utc: q for q in result.closings}
    out: dict[datetime, list[str]] = {}
    for t in all_trades(result):
        q = closings.get(t.exit_utc) if t.exit_utc is not None else None
        marks = [INDETERMINATE] if t.indeterminate else []
        marks += [UNPLANNED_NIGHT] if t.decided_utc in nights else []
        marks += [CLOSE_AFTER_INTERRUPTION] if q is not None and q.silence_kind is Silence.UNEXPLAINED else []
        marks += [COINCIDENT] if q is not None and q.coincident else []
        marks += [PENDING_CLOSING] if t.exit_utc is None and result.unexecuted_closing is not None else []
        out[t.decided_utc] = marks
    return out


# ---------------------------------------------------------------------- closings and bounds


def due_of(entry_utc: datetime, day: date, p: Day02Params) -> tuple[datetime, str, bool]:
    """First deadline (sheet §6.3): time exit 2 h after the execution or 17:00; LIQUIDATION_17H if equal."""
    time_exit, liquidation = entry_utc + p.time_exit, london(day, p.liquidation)
    return (
        (time_exit, TIME_EXIT, False)
        if time_exit < liquidation
        else (liquidation, LIQUIDATION, time_exit == liquidation)
    )


def closings(result: Day02Result) -> dict[str, Any]:
    """Each resolved closing order carries its delay, closed silence and reason, and the trade it closes;
    a closing still due at the end is reported with what is known, never with an invented close."""
    p, errors = result.day02_params, []
    days = {d_of(a): a.day for a in result.attempts if d_of(a) is not None}
    closed = {t.exit_utc: t for t in result.trades}
    for q in result.closings:
        trade = closed.get(q.closed_utc)
        if trade is None or trade.exit_reason != q.close_reason:
            errors.append(f"clôture due à {q.decided_utc.isoformat()} sans transaction clôturée correspondante")
            continue
        day = days.get(trade.decided_utc)
        if day is None or (q.decided_utc, q.order, q.coincident) != due_of(trade.entry_utc, day, p):
            errors.append(f"clôture due à {q.decided_utc.isoformat()} : échéance ou ordre différent de la fiche")
        if q.silence is None or not q.close_reason:
            errors.append(f"clôture due à {q.decided_utc.isoformat()} sans silence clos ou motif")
    per_trade = Counter(q.closed_utc for q in result.closings)
    errors += [f"plusieurs clôtures pour la sortie {utc}" for utc, n in per_trade.items() if n > 1]
    errors += [
        f"clôture {t.exit_utc} par {t.exit_reason} sans ordre de clôture"
        for t in result.trades
        if t.exit_reason in (TIME_EXIT, LIQUIDATION) and t.exit_utc not in per_trade
    ]
    nights = sorted(
        t.decided_utc for t in result.trades if t.exit_utc and trading_day(t.exit_utc) != trading_day(t.entry_utc)
    )
    journal = sum(1 for e in result.journal if e.kind == UNPLANNED_NIGHT)
    if sorted(result.unplanned_nights) != nights or journal != len(nights):
        errors.append("nuits non prévues différentes des transactions ou du journal du moteur")
    pending = None
    if result.unexecuted_closing is not None:
        if result.open_trade is None or result.end_utc is None:
            errors.append("clôture en attente à la fin sans position ouverte")
        else:
            due, order = result.unexecuted_closing
            pending = {
                "decided_utc": due,
                "order": order,
                "end_of_study_utc": result.end_utc,
                "waiting_until_end": result.end_utc - due,
                "open_trade_decided_utc": result.open_trade.decided_utc,
                "silence_in_progress": result.silence_at_end,
                "closing": "aucune : ni instant, ni motif, ni cotation",
            }
    delays = sorted(q.delay for q in result.closings)
    after_17 = [
        t.decided_utc
        for t in all_trades(result)
        if (day := days.get(t.decided_utc)) is not None
        and (t.exit_utc is None or t.exit_utc > london(day, p.liquidation))
    ]
    return {
        "ok": not errors,
        "errors": errors[:50],
        "resolved": len(result.closings),
        "orders": dict(Counter(q.order for q in result.closings).most_common()),
        "close_reasons": dict(Counter(q.close_reason for q in result.closings).most_common()),
        "delay_after_deadline": None if not delays else {"min": delays[0], "median": delays[len(delays) // 2],
                                                         "max": delays[-1]},
        "silence_kinds": dict(Counter(q.silence_kind.value for q in result.closings).most_common()),
        "coincident_deadlines": sum(1 for q in result.closings if q.coincident),
        "after_interruption": sum(1 for q in result.closings if q.silence_kind is Silence.UNEXPLAINED),
        "positions_after_17h": len(after_17),
        "unplanned_nights": len(nights),
        "pending_at_end": pending,
    }  # fmt: skip


def bounds(result: Day02Result) -> dict[str, Any]:
    """D at 15:00 at the latest; execution in ]D, D + 5 min] and not after 15:05 London; one position at
    a time."""
    p, errors = result.day02_params, []
    by_decision = {t.decided_utc: t for t in all_trades(result)}
    for a in result.attempts:
        d = d_of(a)
        if d is None:
            continue
        if d > london(a.day, p.last_decision):
            errors.append(f"{a.day} : D {d.isoformat()} après 15:00")
        trade = trade_of(a, by_decision)
        if trade is not None:
            if not d < trade.entry_utc <= d + p.entry_validity:
                errors.append(f"{a.day} : exécution {trade.entry_utc.isoformat()} hors de ]D, D + 5 min]")
            if trade.entry_utc > london(a.day, EXECUTION_LIMIT):
                errors.append(f"{a.day} : exécution {trade.entry_utc.isoformat()} après 15:05 Londres")
    ordered = sorted(all_trades(result), key=lambda t: t.entry_utc)
    for before, after in itertools.pairwise(ordered):
        if before.exit_utc is None or after.entry_utc < before.exit_utc:
            errors.append(f"positions simultanées : {before.entry_utc.isoformat()} et {after.entry_utc.isoformat()}")
    return {"ok": not errors, "errors": errors[:50]}


def scenario_triggers(result: Day02Result) -> dict[str, Any]:
    """Protocol §4, read in the run's own report: B and C if at least one indeterminate trade (a silence
    strictly longer than 5 min during a position, closing orders pending and a position open at the end
    included); the rejection if at least one stop beyond at the first execution tick."""
    crossings = [
        {"decided_utc": t.decided_utc, "open_at_end": t.exit_utc is None, "spans": t.unobservable_crossings}
        for t in all_trades(result)
        if t.unobservable_crossings
    ]
    beyond = sum(1 for a in result.attempts if a.entry_outcome == STOP_AT_EXECUTION)
    return {
        "indeterminate_trades": crossings,
        "scenario_b_required": bool(crossings),
        "scenario_c_required": bool(crossings),
        "stop_beyond_at_execution": beyond,
        "reject_required": beyond > 0,
        "pending_closing_at_end": result.unexecuted_closing,
    }


def controls(
    result: Day02Result,
    engine: Day02Backtest,
    days: Sequence[date],
    study: StudyLines,
    study_errors: list[str],
    inputs: dict[str, Any],
    origin: dict[str, Any],
) -> tuple[dict[str, Any], set[int]]:
    """Every control that must pass before any result is presented (protocol §5, §6)."""
    flow = funnel(result.attempts, all_trades(result))
    matched_report, matched = reconcile(study, study_errors, result, days)
    checks = {
        "recomputation": recomputation(result, engine),
        "resumes": resumes(result, days),
        "availability": matched_report,
        "execution": {"ok": flow["ok"], "checks": flow["checks"]},
        "closings": {k: v for k, v in closings(result).items() if k in ("ok", "errors", "pending_at_end")},
        "bounds": bounds(result),
        "inputs": inputs,
        "provenance": origin,
    }
    return checks, matched


def gated_report(
    checks: dict[str, Any], triggers: dict[str, Any], results: Callable[[], dict[str, Any]]
) -> dict[str, Any]:
    """The results exist in the report only if every control passes."""
    failed = sorted(name for name, check in checks.items() if not check["ok"])
    if failed:
        anomaly = f"contrôles en échec ({', '.join(failed)}) : résultats non présentés"
        return {"anomaly": anomaly, "controls": checks}
    return {"controls": checks, "scenario_triggers": triggers, "result": results()}


# ---------------------------------------------------------------------- session lines (local detail)


def trade_line(trade: Trade, marks: list[str]) -> dict[str, Any]:
    return {
        "entry_utc": trade.entry_utc,
        "entry_price": trade.entry_price,
        "size": trade.size,
        "stop": trade.stop,
        "exit_utc": trade.exit_utc,
        "exit_price": trade.exit_price,
        "exit_reason": trade.exit_reason,
        "exit_outcome": exit_outcome(trade),
        "net_eur": trade.net_account,
        "annotations": marks,
    }


def approximation_gap(attempt: Attempt, record: DecisionRecord | None, engine: Day02Backtest) -> Decimal | None:
    """Value at D minus the study's approximate indicator, on the distance to the stop, in pips. The
    value at D is |P_D − S| with P_D the ask at D for a purchase and the bid at D for a sale; the study
    measures |bid close of the exit candle − S|. Hence (ask at D − bid close) for a purchase and
    (bid close − bid at D) for a sale: the stop cancels out."""
    c, quote = attempt.search.configuration, None if record is None else record.known.get("quote")
    if c is None or c.ended_utc is None or quote is None:
        return None
    bar = engine.trigger_bars.get(c.ended_utc - engine.day02.trigger_step)
    if bar is None:
        return None
    long = c.side is Side.LONG
    gap: Decimal = quote["ask"] - bar["bid_close"] if long else bar["bid_close"] - quote["bid"]
    return gap / PIP


def passage_of(scenario: str, rule: StopAtExecution) -> str:
    """Name of the pre-registered pass (protocol §4): the scenario, with the rejection rule apart."""
    return f"{scenario}_rejet" if rule is StopAtExecution.REJECT else scenario


def session_lines(
    result: Day02Result,
    engine: Day02Backtest,
    days: Sequence[date],
    matched: set[int],
    scenario: str,
    window: tuple[datetime, datetime] | None = None,
) -> list[dict[str, Any]]:
    """One line per session of the study: its attempts as the engine lived them, with their trade and
    measures; a session without search carries its justification. Each line names the pass that
    produced it (trigger, scenario, execution rule, window), checked again before any comparison."""
    config, sessions = result.config, by_session(result.attempts)
    by_decision = {t.decided_utc: t for t in all_trades(result)}
    records = {r.decision_utc: r for r in result.decisions}
    marks, skipped = trade_annotations(result), dict(result.skipped_days)
    lines = []
    for day in days:
        attempts = []
        for a in sessions.get(day, []):
            c, d = a.search.configuration, d_of(a)
            trade = trade_of(a, by_decision)
            measured = None
            if a.decision is not None and c is not None:
                measured = entry_measures(a.decision, c.atr, records.get(a.decision["d_utc"]), trade, config)
                measured["stop_distance"]["definition"] = STOP_DISTANCE
            gap = approximation_gap(a, records.get(c.ended_utc) if c and c.ended_utc else None, engine)
            attempts.append(
                {
                    **search_view(a.search),
                    "resume_after": a.resume_after,
                    "at_d": a.at_d,
                    "decision": a.decision,
                    "entry_outcome": a.entry_outcome,
                    "entry_outcome_utc": a.entry_outcome_utc,
                    "ended_utc": a.ended_utc,
                    "ended_by": a.ended_by,
                    "events": a.events,
                    "matched_with_study": id(a) in matched,
                    "approximation_gap_pips": gap if id(a) in matched and c and c.outcome == EXIT else None,
                    "trade": None if trade is None else trade_line(trade, marks.get(trade.decided_utc, [])),
                    "measures": measured,
                    "d_utc": d,
                }
            )
        lines.append(
            {
                "trigger": result.day02_params.trigger.value,
                "scenario": scenario,
                "stop_at_execution": config.stop_at_execution.value,
                "passage": passage_of(scenario, config.stop_at_execution),
                "window": None if window is None else {"start": window[0], "end": window[1]},
                "day": day,
                "without_search": skipped.get(day) if day not in sessions else None,
                "attempts": attempts,
            }
        )
    return lines


# ---------------------------------------------------------------------- measures (protocol §7)


def _stats(values: list[Decimal]) -> dict[str, Any] | None:
    if not values:
        return None
    return {"n": len(values), "min": min(values), "median": statistics.median(values), "max": max(values)}


def entry_ratios(lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Distributions of the per-entry measures of DAY_01's tool, over the attempts; stop distance in A H1."""
    out = ratios([a for line in lines for a in line["attempts"]])
    return {**out, "definitions": {**out["definitions"], "stop_distance": STOP_DISTANCE}}


def per_session(lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Configurations, executed entries and losses per session, as distributions over the sessions."""
    out: dict[str, Counter[int]] = defaultdict(Counter)
    for line in lines:
        attempts = line["attempts"]
        trades = [a["trade"] for a in attempts if a["trade"] is not None]
        out["configurations"][sum(1 for a in attempts if a["configuration"] is not None)] += 1
        out["entries_executed"][len(trades)] += 1
        out["losses"][sum(1 for t in trades if t["net_eur"] is not None and t["net_eur"] < 0)] += 1
    return {name: {str(k): v for k, v in sorted(c.items())} for name, c in out.items()}


def breakdowns(lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Executed entries by weekday, London decision hour, clock (GMT, BST, offset weeks) and side."""
    groups: dict[str, dict[str, list[Decimal | None]]] = defaultdict(lambda: defaultdict(list))
    for line in lines:
        day: date = line["day"]
        for a in line["attempts"]:
            trade = a["trade"]
            if trade is None:
                continue
            net = trade["net_eur"]
            groups["weekday"][f"{day.isoweekday()} {WEEKDAYS[day.weekday()]}"].append(net)
            groups["decision_hour_london"][a["d_utc"].astimezone(LONDON).strftime("%H")].append(net)
            groups["clock"][clocks(day)].append(net)
            groups["side"][a["decision"]["side"]].append(net)
    return {
        name: {
            key: {
                "executed": len(nets),
                "closed": sum(1 for n in nets if n is not None),
                "winners": sum(1 for n in nets if n is not None and n > 0),
                "net_eur": sum((n for n in nets if n is not None), Decimal(0)),
            }
            for key, nets in sorted(values.items())
        }
        for name, values in groups.items()
    }


def _risk_multiple(trade: Trade) -> Decimal | None:
    risk = trade.size * trade.estimate.loss_account_per_contract
    return None if risk <= 0 or trade.net_account is None else trade.net_account / risk


def measures(result: Day02Result, start: datetime, end: datetime) -> dict[str, Any]:
    """Measures of the specification (§9): expectancy in risk multiples, profit factor, exposure, months."""
    closed = [t for t in result.trades if t.net_account is not None]
    wins = [t.net_account for t in closed if t.net_account is not None and t.net_account > 0]
    losses = [t.net_account for t in closed if t.net_account is not None and t.net_account <= 0]
    multiples = [r for t in closed if (r := _risk_multiple(t)) is not None]
    exposure = sum(((t.exit_utc or end) - t.entry_utc for t in all_trades(result)), timedelta(0))
    entered = {(t.entry_utc.year, t.entry_utc.month) for t in all_trades(result)}
    net_by_month: dict[tuple[int, int], Decimal] = defaultdict(Decimal)
    for t in closed:
        if t.exit_utc is not None and t.net_account is not None:
            net_by_month[(t.exit_utc.year, t.exit_utc.month)] += t.net_account
    calendar = months(start, end)
    return {
        "expectancy_risk_multiples": None if not multiples else sum(multiples, Decimal(0)) / len(multiples),
        "profit_factor": None if not losses or sum(losses) == 0 else sum(wins, Decimal(0)) / -sum(losses),
        "average_win_eur": None if not wins else sum(wins, Decimal(0)) / len(wins),
        "average_loss_eur": None if not losses else sum(losses, Decimal(0)) / len(losses),
        "winners": len(wins),
        "losers": len(losses),
        "exposure_hours": exposure.total_seconds() / 3600,
        "months": len(calendar),
        "months_without_entry": sum(1 for m in calendar if m not in entered),
        "losing_months": sorted(f"{y}-{m:02d}" for (y, m), v in net_by_month.items() if v < 0),
    }


def overlap(result: Day02Result, other: dict[str, Any], end: datetime, window_years: list[int]) -> dict[str, Any]:
    """Description only (protocol §8): time overlap, simultaneous losses and annual nets side by side
    with another reference. Independent trajectories, each with its own capital: no shared portfolio."""
    body = other["result"]
    rows = [*body["trades"], *filter(None, [body.get("open_trade_at_end")])]
    theirs = [
        (
            datetime.fromisoformat(t["entry_utc"]),
            datetime.fromisoformat(t["exit_utc"]) if t.get("exit_utc") else end,
            t["side"],
            Decimal(t["net_account"]) if t.get("net_account") is not None else None,
        )
        for t in rows
    ]
    same = opposite = 0.0
    overlapping: set[datetime] = set()
    simultaneous: set[datetime] = set()
    for trade in all_trades(result):
        a, b = trade.entry_utc, trade.exit_utc or end
        for start1, end1, side1, net1 in theirs:
            seconds = (min(b, end1) - max(a, start1)).total_seconds()
            if seconds <= 0:
                continue
            overlapping.add(trade.decided_utc)
            same, opposite = (same + seconds, opposite) if side1 == trade.side.value else (same, opposite + seconds)
            if trade.net_account is not None and trade.net_account < 0 and net1 is not None and net1 < 0:
                simultaneous.add(trade.decided_utc)
    ours: dict[int, Decimal] = defaultdict(Decimal)
    other_by_year: dict[int, Decimal] = defaultdict(Decimal)
    for t in result.trades:
        if t.exit_utc is not None and t.net_account is not None:
            ours[t.exit_utc.year] += t.net_account
    for _, exit_utc, _, net in theirs:
        if net is not None and exit_utc != end:
            other_by_year[exit_utc.year] += net
    return {
        "reference": {"commit": other.get("provenance", {}).get("commit"), "trades": len(rows)},
        "day02_trades": len(all_trades(result)),
        "day02_trades_overlapping": len(overlapping),
        "day02_losses_overlapping_a_loss": sorted(simultaneous),
        "day02_losing_trades": sum(1 for t in result.trades if t.net_account is not None and t.net_account < 0),
        "hours_same_direction": same / 3600,
        "hours_opposite_direction": opposite / 3600,
        "net_by_year": {y: {"day02": ours.get(y, Decimal(0)), "reference": other_by_year.get(y, Decimal(0))}
                        for y in window_years},
        "note": "trajectoires indépendantes, chacune avec son capital : pas un portefeuille partagé",
    }  # fmt: skip


def comparisons(result: Day02Result, references: dict[str, dict[str, Any]], start: datetime) -> dict[str, Any]:
    """Overlap with each reference, then the union without duplicate of the DAY_02 losses concerned."""
    end = result.end_utc or start
    by_reference = {name: overlap(result, ref, end, years(start, end)) for name, ref in references.items()}
    union = sorted({d for item in by_reference.values() for d in item["day02_losses_overlapping_a_loss"]})
    return {"by_reference": by_reference, "union_day02_losses_overlapping_a_loss": len(union)}


def performance(
    result: Day02Result,
    engine: Day02Run,
    lines: list[dict[str, Any]],
    start: datetime,
    references: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    end = result.end_utc or start
    trades = all_trades(result)
    by_year: dict[int, dict[str, Any]] = {}
    for year in years(start, end):
        closed = [t for t in result.trades if t.exit_utc is not None and t.exit_utc.year == year]
        dd = engine.yearly.years.get(year)
        by_year[year] = {
            "funnel": counts(funnel([a for a in result.attempts if a.day.year == year], trades)),
            "closed_trades": _trade_totals(closed),
            "tick_drawdown": None if dd is None else asdict(dd),
        }
    marks = Counter(m for items in trade_annotations(result).values() for m in items)
    gaps = [a["approximation_gap_pips"] for line in lines for a in line["attempts"]]
    report: dict[str, Any] = jsonable(
        {
            "funnel": funnel(result.attempts, trades),
            "annotations": {"note": "non additives : elles recoupent les issues exclusives",
                            **{k: marks.get(k, 0) for k in ANNOTATIONS}},
            "closings": closings(result),
            "trades": [_trade(t) for t in result.trades],
            "open_trade_at_end": _trade(result.open_trade) if result.open_trade else None,
            "silence_at_end": result.silence_at_end,
            "balance_eur": result.balance,
            "equity_eur": result.equity,
            "closed_trade_totals": _trade_totals(result.trades),
            "concentration": concentration(result.trades),
            "per_session": per_session(lines),
            "ratios": entry_ratios(lines),
            "approximation_gap_pips": {
                "definition": APPROXIMATION_GAP,
                "values": _stats([g for g in gaps if g is not None]),
            },
            "flag_slope_atr_multiple": {
                "definition": "pente du drapeau (clôture de la dernière pause moins la première) / A, entrées décidées",
                "values": _stats(
                    [c.slope for a in result.attempts if a.at_d == ENTRY_DECIDED
                     and (c := a.search.configuration) is not None and c.slope is not None]
                ),
            },
            "breakdowns": breakdowns(lines),
            "measures": measures(result, start, end),
            "tick_drawdown_eur": asdict(result.tick_drawdown) if result.tick_drawdown else None,
            "relative_drawdown": {
                "max_pct": engine.relative.max_ratio * 100,
                "max_utc": engine.relative.max_utc,
                "first_review_crossing_6pct": engine.relative.first_review_crossing,
            },
            "recovery": engine.recovery.close(),
            "risk_overruns": [
                {"entry_utc": t.entry_utc, "measure": t.exposure_measure, "overrun_eur": t.risk_overrun}
                for t in trades
                if t.risk_overrun
            ],
            "journal_counts": dict(sorted(Counter(e.kind for e in result.journal).items())),
            "comparisons": comparisons(result, references, start),
            "by_year": by_year,
            "end_utc": result.end_utc,
        }
    )  # fmt: skip
    return report


# ---------------------------------------------------------------------- M5 / M15 (protocol §8)


def _dec(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def comparison_plan(m5: dict[str, Any], m15: dict[str, Any]) -> dict[str, Any]:
    """From the two A reports: which comparisons can exist. B, C and the rejection are triggered for each
    side separately; one required on one side only gives no comparison, and the other side is not run
    to fill the table."""
    for name, report, trigger in (("M5", m5, Trigger.M5), ("M15", m15, Trigger.M15)):
        config = report.get("config", {})
        if "result" not in report or config.get("trigger") != trigger.value or config.get("passage") != "A":
            raise ValueError(f"{name} : rapport d'un passage A {trigger.value} conforme attendu")
    a, b = m5["scenario_triggers"], m15["scenario_triggers"]
    plan = {"A": "les deux passages existent : comparaison à produire"}
    for passage, key in (("B", "scenario_b_required"), ("C", "scenario_c_required"), ("A_rejet", "reject_required")):
        if a[key] and b[key]:
            plan[passage] = "requis des deux côtés : comparaison à produire après les deux passages"
        elif a[key] or b[key]:
            side = "M5" if a[key] else "M15"
            plan[passage] = f"requis seulement en {side} : aucune comparaison, l'autre côté n'est pas lancé"
        else:
            plan[passage] = "non requis"
    return plan


def compare_triggers(m5: Iterable[dict[str, Any]], m15: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """The two session files of the same scenario, by London date (duplicates refused, same dates). Per
    date, counts of each trajectory; entry by entry only for the first configuration of a session when
    both trajectories start it from the same state (07:00, nothing held). No pairing beyond it."""
    sides: dict[str, dict[str, dict[str, Any]]] = {}
    for name, rows in (("M5", m5), ("M15", m15)):
        sides[name] = {}
        for line in rows:
            if line["trigger"] != name:
                raise ValueError(f"{name} : ligne du déclenchement {line['trigger']}")
            if line["day"] in sides[name]:
                raise ValueError(f"{name} : séance {line['day']} présente plusieurs fois")
            sides[name][line["day"]] = line
    if set(sides["M5"]) != set(sides["M15"]):
        raise ValueError("les deux passages ne portent pas sur les mêmes dates de Londres")
    if len({line["scenario"] for side in sides.values() for line in side.values()}) > 1:
        raise ValueError("les deux passages ne sont pas du même scénario")

    def tally(line: dict[str, Any]) -> dict[str, int]:
        attempts = line["attempts"]
        configs = [a["configuration"] for a in attempts if a["configuration"] is not None]
        return {
            "attempts": len(attempts),
            "configurations": len(configs),
            "confirmed_exits": sum(1 for c in configs if c["outcome"] == EXIT),
            "entries_decided": sum(1 for a in attempts if a["at_d"] == ENTRY_DECIDED),
            "entries_executed": sum(1 for a in attempts if a["trade"] is not None),
        }

    rows_out: list[dict[str, Any]] = []
    for day in sorted(sides["M5"]):
        a, b = sides["M5"][day], sides["M15"][day]
        fa, fb = (a["attempts"] or [None])[0], (b["attempts"] or [None])[0]
        same_state = bool(fa and fb and fa["resume_after"] == fb["resume_after"] == SESSION_START)
        first: dict[str, Any] | None = None
        if same_state and fa is not None and fb is not None:
            ca, cb = fa["configuration"], fb["configuration"]
            first = {
                "confirmed": {"M5": bool(ca) and ca["outcome"] == EXIT, "M15": bool(cb) and cb["outcome"] == EXIT},
                "executed": {"M5": fa["trade"] is not None, "M15": fb["trade"] is not None},
                "m15_minus_m5": None,
            }
            if fa["trade"] is not None and fb["trade"] is not None:
                ta, tb = fa["trade"], fb["trade"]
                net_a, net_b = _dec(ta["net_eur"]), _dec(tb["net_eur"])
                first["m15_minus_m5"] = {
                    "entry_minutes": (datetime.fromisoformat(tb["entry_utc"]) - datetime.fromisoformat(ta["entry_utc"]))
                    .total_seconds() / 60,
                    "stop": Decimal(tb["stop"]) - Decimal(ta["stop"]),
                    "size": Decimal(tb["size"]) - Decimal(ta["size"]),
                    "net_eur": None if net_a is None or net_b is None else net_b - net_a,
                    "net_eur_m5": net_a,
                    "net_eur_m15": net_b,
                }  # fmt: skip
        rows_out.append({"day": day, "counts": {"M5": tally(a), "M15": tally(b)}, "first_same_state": first})

    paired = [r["first_same_state"] for r in rows_out if r["first_same_state"] is not None]

    def split(key: str) -> dict[str, int]:
        return {
            "common": sum(1 for f in paired if f[key]["M5"] and f[key]["M15"]),
            "only_m5": sum(1 for f in paired if f[key]["M5"] and not f[key]["M15"]),
            "only_m15": sum(1 for f in paired if f[key]["M15"] and not f[key]["M5"]),
        }

    both = [f["m15_minus_m5"] for f in paired if f["m15_minus_m5"] is not None]
    closed = [d for d in both if d["net_eur"] is not None]
    totals = {side: Counter[str]() for side in ("M5", "M15")}
    for r in rows_out:
        for side in totals:
            totals[side].update(r["counts"][side])
    report: dict[str, Any] = jsonable(
        {
            "key": "date de séance de Londres",
            "dates": len(rows_out),
            "totals": {side: dict(c) for side, c in totals.items()},
            "sessions_with_the_same_counts": sum(1 for r in rows_out if r["counts"]["M5"] == r["counts"]["M15"]),
            "first_configuration_same_state": {
                "sessions": len(paired),
                "confirmed_exits": split("confirmed"),
                "executed": split("executed"),
                "entry_delay_minutes": dict(sorted(Counter(d["entry_minutes"] for d in both).items())),
                "same_stop": sum(1 for d in both if d["stop"] == 0),
                "same_size": sum(1 for d in both if d["size"] == 0),
                "common_closed": len(closed),
                "net_of_common_closed_eur": {
                    "M5": sum((d["net_eur_m5"] for d in closed), Decimal(0)),
                    "M15": sum((d["net_eur_m15"] for d in closed), Decimal(0)),
                    "m15_minus_m5": sum((d["net_eur"] for d in closed), Decimal(0)),
                },
                "note": "appariement limité à la première configuration de séance à même état de reprise",
            },
            "sessions": rows_out,
            "note": "détail par séance : sortie locale, hors Git",
        }
    )
    return report


# ---------------------------------------------------------------------- command


def _date(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def to_markdown(report: dict[str, Any]) -> str:
    config = report["config"]
    lines = [f"# DAY_02 — passage {config['trigger']} / scénario {config['scenario']} (rapport agrégé)", ""]
    lines += [report["notice"], "", "| Contrôle | Conforme |", "|---|---|"]
    lines += [f"| {name} | {'oui' if c['ok'] else 'NON'} |" for name, c in report["controls"].items()]
    if "result" not in report:
        return "\n".join([*lines, "", f"**{report['anomaly']}**", ""])
    flow = report["result"]["funnel"]
    lines += ["", "## Des recherches aux issues", "", "| Étape | Issue | Nombre |", "|---|---|---:|"]
    for step, key in (
        ("recherches", "searches_outcomes"),
        ("configurations", "configuration_outcomes"),
        ("drapeaux formés", "flag_outcomes"),
        ("sorties confirmées (pas des entrées)", "at_d"),
        ("entrées décidées", "entry_outcomes"),
        ("entrées exécutées", "executed_outcomes"),
    ):
        lines += [f"| {step} | {k} | {n} |" for k, n in flow[key].items()]
    totals = report["result"]["closed_trade_totals"]
    lines += ["", f"Net {totals['net_eur']} EUR (brut {totals['gross_eur']}, coûts {totals['costs_eur']}).", ""]
    return "\n".join(lines)


def _counting(ticks: Iterator[Tick], seen: list[int]) -> Iterator[Tick]:
    for t in ticks:
        seen[0] += 1
        yield t


def main(argv: list[str] | None = None) -> int:
    launch = provenance(argv, TOOL)  # at launch: the code the run starts from
    parser = argparse.ArgumentParser(prog=TOOL, description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--init-start", type=_date, default=_date("2015-01-01"))
    parser.add_argument("--start", type=_date, default=_date("2015-01-01"))
    parser.add_argument("--end", type=_date, default=_date("2022-01-01"))
    parser.add_argument("--trigger", choices=[t.value for t in Trigger], required=True)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    rules = [s.name for s in StopAtExecution]
    parser.add_argument("--stop-at-execution", choices=rules, default=StopAtExecution.FILL_THEN_LIQUIDATE.name)
    parser.add_argument("--availability", type=Path, required=True, help="détail JSONL de l'étude de disponibilité")
    for name in ("s1", "s2", "s3", "day01"):
        parser.add_argument(f"--{name}-reference", type=Path, help=f"rapport {name.upper()} de référence")
    parser.add_argument("--out", type=Path, required=True, help="rapport JSON (hors Git, sous data/)")
    parser.add_argument("--sessions-out", type=Path, required=True, help="détail JSONL par séance (hors Git)")
    parser.add_argument("--variant", choices=list(VARIANTS), default=REFERENCE, help="campagne exploratoire H1-H3")
    args = parser.parse_args(argv)
    if not args.init_start <= args.start < args.end:
        parser.error("dates attendues : init-start <= start < end")
    require_development_window(args.init_start, args.end)
    began = time.perf_counter()
    trigger = Trigger(args.trigger)
    # Frozen values: only the trigger is chosen, plus, for the exploratory campaign, a registered variant.
    params = variant_params(args.variant, trigger)
    reference = args.variant == REFERENCE
    official = (args.start, args.end) == OFFICIAL_WINDOW
    directory = args.data_dir / "bars" / SOURCE / INSTRUMENT
    candles = {g: directory / LOT / f"{g.value}.parquet" for g in Grid}
    h1_path = directory / f"{Timeframe.H1.value}.parquet"
    h4_path = directory / f"{Timeframe.H4.value}.parquet"
    quality = args.data_dir / "reports" / QUALITY_REPORT
    with_h4 = needs_h4(args.variant)
    inputs = (*candles.values(), h1_path, quality, *((h4_path,) if with_h4 else ()))
    before = {path.as_posix(): sha256_file(path) for path in inputs}
    wrong = [g.value for g, path in candles.items() if before[path.as_posix()] != CANDLES_SHA256[g]]
    wrong += ["1h"] if before[h1_path.as_posix()] != H1_SHA256 else []
    wrong += ["4h"] if with_h4 and before[h4_path.as_posix()] != H4_SHA256 else []
    study_hash = sha256_file(args.availability)
    # The anchored study is the reference's; a variant is matched with its own study (same variant).
    wrong += ["étude de disponibilité"] if official and reference and study_hash != STUDY_SHA256 else []
    if wrong:
        print(f"empreintes {wrong} différentes des références : aucune lecture", file=sys.stderr)
        return 2
    bars = {g: read_candles(path, args.end)[0] for g, path in candles.items()}
    h1 = load_bars(args.data_dir, SOURCE, INSTRUMENT, Timeframe.H1, args.init_start, args.end)
    h4 = load_bars(args.data_dir, SOURCE, INSTRUMENT, Timeframe.H4, args.init_start, args.end) if with_h4 else []
    gaps = load_gaps(quality, args.end)
    files = tick_files(HistoryStore(args.data_dir).tick_files(SOURCE, INSTRUMENT), args.start, args.end)
    config = ResearchConfig(
        costs=RESEARCH_COSTS, stop_type=StopType.GUARANTEED, stop_at_execution=StopAtExecution[args.stop_at_execution]
    )  # 2 000 EUR, 0.25 %, minimum and increment 0.1: the references S1 to DAY_01
    seen = [0]
    engine = Day02Run(
        bars[Grid.M5], bars[Grid.M15], h1, _counting(stream_ticks(files, args.start, args.end), seen), gaps, params,
        config, scenario=SCENARIOS[args.scenario], start_utc=args.start, end_utc=args.end, h4=h4,
    )  # fmt: skip
    result = engine.run()
    days = study_days(args.start, args.end)
    with args.availability.open(encoding="utf-8") as rows:
        study, study_errors = study_lines((json.loads(r) for r in rows), official)
    study_variants = {str(row.get("variant", REFERENCE)) for row in study.values()}
    if study_variants != {args.variant}:
        study_errors = [*study_errors, f"étude de la variante {sorted(study_variants)}, passage {args.variant}"]
    after = {path.as_posix(): sha256_file(path) for path in inputs}
    finish = end_check(launch, tree_state())
    code_changed = finish["commit"] != launch["commit"] or any(
        f.startswith(CODE_PATHS) for f in finish["files_changed_during_run"]
    )
    window_ok = engine.first_tick_utc is None or (
        args.start <= engine.first_tick_utc and (engine.last_tick_utc or args.start) < args.end
    )
    inputs_errors = [] if before == after else ["empreintes des entrées modifiées pendant le passage"]
    inputs_errors += [] if sha256_file(args.availability) == study_hash else ["étude modifiée pendant le passage"]
    inputs_errors += [] if window_ok else ["tick lu hors de la fenêtre"]
    inputs_errors += [] if params == variant_params(args.variant, trigger) else ["paramètres différents de l'attendu"]
    inputs_errors += [] if variant_of(params) == args.variant else ["paramètres hors de la variante"]
    late_h4 = [b for b in h4 if b["end_utc"] > args.end]
    inputs_errors += [f"{len(late_h4)} H4 lue(s) après la fin"] if late_h4 else []
    inputs_errors += [f"{len(gaps)} trous chargés ≠ {GAPS_ANCHOR}"] if official and len(gaps) != GAPS_ANCHOR else []
    provenance_errors = [] if not launch["uncommitted_diff_sha256"] else ["arbre non propre au lancement"]
    provenance_errors += ["code ou commit modifié pendant le passage"] if code_changed else []
    references_sha256 = {
        "5m": CANDLES_SHA256[Grid.M5],
        "15m": CANDLES_SHA256[Grid.M15],
        "1h": H1_SHA256,
        **({"4h": H4_SHA256} if with_h4 else {}),
        QUALITY_REPORT: "aucune référence historique : empreinte enregistrée au passage ; ancrage par les trous",
        "étude": STUDY_SHA256
        if official and reference
        else "variante ou fenêtre non officielle : empreinte enregistrée seulement",
    }
    checks, matched = controls(
        result, engine, days, study, study_errors,
        {"ok": not inputs_errors, "errors": inputs_errors, "gaps": len(gaps),
         "sha256": {"before": before, "after": after, "study": study_hash, "references": references_sha256}},
        {"ok": not provenance_errors, "errors": provenance_errors, "launch": launch, "end": finish},
    )  # fmt: skip
    references = {}
    for name in ("s1", "s2", "s3", "day01"):
        path = getattr(args, f"{name}_reference")
        if path is not None:
            references[name] = json.loads(path.read_text(encoding="utf-8"))
    lines = session_lines(result, engine, days, matched, args.scenario, (args.start, args.end))
    body = gated_report(
        checks, jsonable(scenario_triggers(result)), lambda: performance(result, engine, lines, args.start, references)
    )
    passed = "result" in body
    sessions_file = None
    if passed:  # written only for a pass that passed its controls; its hash ties it to this report
        args.sessions_out.parent.mkdir(parents=True, exist_ok=True)
        args.sessions_out.write_text(
            "".join(json.dumps(jsonable(line), ensure_ascii=False) + "\n" for line in lines), encoding="utf-8"
        )
        sessions_file = {"path": str(args.sessions_out), "sha256": sha256_file(args.sessions_out), "lines": len(lines)}
    report: dict[str, Any] = jsonable(
        {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "notice": "passage hors ligne : ni validation de performance ni autorisation de trading ; "
            "une sortie confirmée n'est pas une entrée",
            "window": {"init_start": args.init_start, "start": args.start, "end": args.end, "official": official},
            "config": {
                **({} if reference else {"variant": args.variant}),
                "trigger": trigger.value,
                "scenario": args.scenario,
                "passage": passage_of(args.scenario, config.stop_at_execution),
                "gap_scenario": SCENARIOS[args.scenario].value,
                "stop_type": config.stop_type.value,
                "stop_at_execution": config.stop_at_execution.value,
                "params": asdict(params),
                "costs": {name: asdict(cost) for name, cost in vars(RESEARCH_COSTS).items()},
                "initial_equity": config.initial_equity,
                "risk_fraction": config.risk_fraction,
                "min_size": config.min_size,
                "size_increment": config.size_increment,
                "daily_weekly_limits": "non appliquées (ADR-027), franchissements non décrits ; 6 % : seuil de revue",
            },
            "inputs": {"m5": len(bars[Grid.M5]), "m15": len(bars[Grid.M15]), "h1": len(h1), "h4": len(h4),
                       "gaps": len(gaps), "tick_files": len(files), "ticks": seen[0], "sessions": len(days),
                       "availability": str(args.availability)},
            **body,
            "sessions_file": sessions_file,
            "seconds": round(time.perf_counter() - began, 1),
            "peak_rss_mib": round(_peak_rss_mib(), 1),
        }
    )  # fmt: skip
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.out.with_suffix(".md").write_text(to_markdown(report), encoding="utf-8")
    if not passed:
        print(f"ANOMALIE : {body['anomaly']} ({args.out})")
        return 2
    print(f"rapport écrit : {args.out} ({report['seconds']} s, {report['peak_rss_mib']} Mio)")
    return 0


def sessions_file_errors(report: dict[str, Any], path: Path) -> list[str]:
    """The session file must be the one the report wrote (hash recorded at the run) and every line must
    name the report's pass: trigger, scenario, execution rule (A apart from A with rejection), window."""
    recorded = report.get("sessions_file") or {}
    if not recorded.get("sha256"):
        return ["aucun fichier par séance enregistré dans le rapport"]
    if sha256_file(path) != recorded["sha256"]:
        return [f"{path} n'est pas le fichier par séance écrit par ce rapport (empreinte différente)"]
    config, window = report["config"], report["window"]
    expected = {
        "trigger": config["trigger"],
        "scenario": config["scenario"],
        "stop_at_execution": config["stop_at_execution"],
        "passage": config["passage"],
        "window": {"start": window["start"], "end": window["end"]},
    }
    lines = [json.loads(r) for r in path.read_text(encoding="utf-8").splitlines()]
    errors = [] if len(lines) == recorded.get("lines") else [f"{len(lines)} lignes ≠ {recorded.get('lines')}"]
    for key, value in expected.items():
        if any(line.get(key) != value for line in lines):
            errors.append(f"lignes d'un autre {key} que le rapport ({value})")
    return errors


def compare_main(argv: list[str] | None = None) -> int:
    """M5 / M15 comparison of one scenario from the two local session files, only if both passes exist
    and passed (protocol §8); or, with --plan, which comparisons the two A passes call for."""
    parser = argparse.ArgumentParser(prog="forex-day02-compare", description=(compare_main.__doc__ or "").split(";")[0])
    parser.add_argument("--m5-report", type=Path, required=True, help="rapport JSON du passage M5")
    parser.add_argument("--m15-report", type=Path, required=True, help="rapport JSON du passage M15")
    parser.add_argument("--plan", action="store_true", help="à partir des deux passages A : comparaisons prévues")
    parser.add_argument("--m5", type=Path, help="détail JSONL du passage M5")
    parser.add_argument("--m15", type=Path, help="détail JSONL du passage M15")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    m5_report = json.loads(args.m5_report.read_text(encoding="utf-8"))
    m15_report = json.loads(args.m15_report.read_text(encoding="utf-8"))
    if args.plan:
        try:
            plan = comparison_plan(m5_report, m15_report)
        except ValueError as error:
            print(f"plan refusé : {error}", file=sys.stderr)
            return 2
        args.out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"plan écrit : {args.out}")
        return 0
    reasons = []
    for name, report in (("M5", m5_report), ("M15", m15_report)):
        if "result" not in report or report.get("config", {}).get("trigger") != name:
            reasons.append(f"{name} : passage absent, non conforme ou d'un autre déclenchement")
    keys = ("scenario", "stop_at_execution", "passage")
    if [m5_report.get("config", {}).get(k) for k in keys] != [m15_report.get("config", {}).get(k) for k in keys]:
        reasons.append("les deux passages ne sont pas du même scénario ni de la même règle d'exécution")
    if m5_report.get("window") != m15_report.get("window"):
        reasons.append("les deux passages ne portent pas sur la même fenêtre")
    if args.m5 is None or args.m15 is None:
        reasons.append("détails --m5 et --m15 attendus")
    if reasons:
        print(f"comparaison non produite : {' ; '.join(reasons)}", file=sys.stderr)
        return 2
    sides = {}
    for name, report, path in (("M5", m5_report, args.m5), ("M15", m15_report, args.m15)):
        errors = sessions_file_errors(report, path)
        reasons += [f"{name} : {e}" for e in errors]
        if not errors:
            sides[name] = [json.loads(r) for r in path.read_text(encoding="utf-8").splitlines()]
    if reasons:
        print(f"comparaison non produite : {' ; '.join(reasons)}", file=sys.stderr)
        return 2
    try:
        report = compare_triggers(sides["M5"], sides["M15"])
    except ValueError as error:
        print(f"comparaison non produite : {error}", file=sys.stderr)
        return 2
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"comparaison écrite : {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
