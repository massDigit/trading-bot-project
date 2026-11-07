"""DAY_01 performance run on 2015-2021 (docs/experiments/DAY01_REFERENCE_2015_2021.md). No order, no network.

    uv run forex-day01-backtest --trigger M5 --scenario A \\
        --availability data/reports/backtests/day01_availability_2015_2021_1c1ed0f_details.jsonl \\
        --s1-reference data/reports/backtests/s1_ref_2015_2021_h0.json \\
        --s2-reference data/reports/backtests/s2_ref_2015_2021_h1_a.json \\
        --s3-reference data/reports/backtests/s3_ref_2015_2021_d1h4_a.json \\
        --out data/reports/backtests/day01_ref_2015_2021_m5_a.json \\
        --sessions-out data/reports/backtests/day01_ref_2015_2021_m5_a_sessions.jsonl

One continuous trajectory per run: one trigger (M5 reference `Day01Params()`, M15 comparison
`Day01Params(trigger=Trigger.M15)`), one gap scenario (A observed only, B stop first, C target
first) and one rule for a stop already beyond at the first execution tick. The engine is unchanged:
this tool only observes what it recorded and never re-applies a rule.

Each session is read in two separate parts (protocol §5, §6):
- its path up to D, confirmation included, in the format of the availability study; a confirmation
  stays a confirmation there even when the entry is refused at D;
- what happened at D and after: refusal or decided entry, outcome of the pending entry, then one
  exclusive outcome of an executed entry (stop, target, liquidation, still open at the end).
  Indeterminate, unplanned night and liquidation after interruption are annotations that may
  overlap those outcomes; they are never added up as further exits.

Before any result, the controls must pass: the path of every session against the availability
study, the conservation of the execution funnel, the liquidations, one position at a time, the
decision and execution bounds, the inputs and the provenance at launch. If one fails, the report
carries the controls only and the command exits with status 2.
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from datetime import time as wall
from decimal import Decimal
from pathlib import Path
from typing import Any

from forex_bot.backtest.data import load_bars, load_gaps, require_development_window, stream_ticks, tick_files
from forex_bot.backtest.day01 import (
    ATR_UNAVAILABLE,
    CANCELLED_INTERRUPTION,
    EXECUTED,
    EXPIRED,
    LIQUIDATION,
    LIQUIDATION_AFTER_INTERRUPTION,
    LONDON,
    MARKET_CLOSED,
    NO_QUOTE,
    POSITION_OPEN,
    REJECTED_AT_EXECUTION,
    SIZE_REFUSED,
    STOP_AT_EXECUTION,
    STOP_INADMISSIBLE,
    TARGET_AT_EXECUTION,
    UNPLANNED_NIGHT,
    Day01Params,
    Session,
    Trigger,
    london,
)
from forex_bot.backtest.day01_availability import (
    CANDLES_SHA256,
    CODE_PATHS,
    CONFIRMED,
    AvailabilityBacktest,
    classify,
    clocks,
    expected_params,
    jsonable,
    read_candles,
)
from forex_bot.backtest.day01_engine import Day01Backtest, Day01Result
from forex_bot.backtest.engine import DecisionRecord, ResearchConfig, StopAtExecution, StopType, Trade
from forex_bot.backtest.explore import RESEARCH_COSTS, _peak_rss_mib, _trade, _trade_totals
from forex_bot.backtest.feed import Tick
from forex_bot.backtest.s2 import GapScenario
from forex_bot.backtest.s2_engine import RelativeDrawdown
from forex_bot.backtest.s3_explore import Recovery, YearlyDrawdowns, concentration, months, years
from forex_bot.history.bars import Gap
from forex_bot.history.calendar import Timeframe
from forex_bot.history.intraday import Grid
from forex_bot.history.intraday_audit import end_check, provenance, sha256_file, tree_state
from forex_bot.history.store import HistoryStore
from forex_bot.risk import Side

SOURCE, INSTRUMENT = "dukascopy", "EURUSD"
TOOL = "forex-day01-backtest"
SCENARIOS = {"A": GapScenario.OBSERVED_ONLY, "B": GapScenario.STOP_FIRST, "C": GapScenario.TARGET_FIRST}
OFFICIAL_WINDOW = (datetime(2015, 1, 1, tzinfo=UTC), datetime(2022, 1, 1, tzinfo=UTC))
# Availability study 1c1ed0f on the official window (docs/experiments/DAY01_AVAILABILITY_2015_2021_BILAN.md).
OFFICIAL_LINES, OFFICIAL_DATES = 3654, 1827
OFFICIAL_CONFIRMATIONS = {Trigger.M5: 831, Trigger.M15: 736}
PATH_FIELDS = ("outcome", "cause", "cause_detail", "range", "breakout", "retest", "confirmation_utc")
EXECUTION_LIMIT = wall(12, 5)  # no execution after 12:05:00 London (sheet §4.5)
WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")

# At D: one refusal of the engine, or a decided entry (sheet §8).
DECIDED = "ENTRÉE_DÉCIDÉE"
REFUSALS_AT_D = (POSITION_OPEN, MARKET_CLOSED, NO_QUOTE, STOP_INADMISSIBLE, SIZE_REFUSED)
EXECUTED_OUTCOMES = (EXECUTED, STOP_AT_EXECUTION, TARGET_AT_EXECUTION)  # an entry filled, even if exited at once
NOT_EXECUTED_OUTCOMES = (REJECTED_AT_EXECUTION, EXPIRED, CANCELLED_INTERRUPTION)

# Exclusive outcome of an executed entry, from the engine's closing reason, which is kept as is.
# Stop family: the exit is tied to the stop. STOP_FRANCHI_À_L'EXÉCUTION is an executed entry liquidated
# at once at the observed exit-side price, with no guarantee of an exit at the stop level.
CLOSED_STOP = "sortie liée au stop"
CLOSED_TARGET = "clôturée à la cible"
CLOSED_LIQUIDATION = "clôturée par liquidation"
OPEN_AT_END = "ouverte à la fin de l'étude"
EXIT_OUTCOMES = (CLOSED_STOP, CLOSED_TARGET, CLOSED_LIQUIDATION, OPEN_AT_END)
STOP_BEYOND_AT_EXECUTION = "STOP_FRANCHI_À_L'EXÉCUTION"  # filled then liquidated on the same tick
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
    LIQUIDATION: CLOSED_LIQUIDATION,
}
IMMEDIATE_EXIT = {STOP_AT_EXECUTION: STOP_BEYOND_AT_EXECUTION, TARGET_AT_EXECUTION: TARGET_AT_EXECUTION}
INDETERMINATE = "indéterminée"
PENDING_LIQUIDATION = "liquidation en attente à la fin"
ANNOTATIONS = (INDETERMINATE, UNPLANNED_NIGHT, LIQUIDATION_AFTER_INTERRUPTION, PENDING_LIQUIDATION)


# ---------------------------------------------------------------------- run


class Day01Run(Day01Backtest):
    """The DAY_01 engine, plus observation only: tick drawdowns (global, yearly, relative), recovery,
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


def all_trades(result: Day01Result) -> list[Trade]:
    return [*result.trades, *([result.open_trade] if result.open_trade else [])]


# ---------------------------------------------------------------------- sessions: path to D, then D


def confirmation_of(session: Session) -> datetime | None:
    """D recorded by the engine at the confirmation, before anything is evaluated at D."""
    value = (session.retest or {}).get("confirmation_utc")
    return value if isinstance(value, datetime) else None


def path_to_d(session: Session, m15: dict[datetime, dict[str, Any]], atr_cause: str | None) -> tuple[str, str | None]:
    """Outcome up to the confirmation included, as the availability study classifies it. A refusal at
    D overwrites the engine's abstention, not the confirmation: the session stays a CONFIRMATION."""
    if confirmation_of(session) is not None:
        return CONFIRMED, None
    return classify(session, {}, m15, atr_cause)


def at_d(session: Session) -> dict[str, Any] | None:
    """What the engine decided at D and what became of the pending entry; None without confirmation."""
    if confirmation_of(session) is None:
        return None
    if session.decision is None:
        refused = session.abstention in REFUSALS_AT_D
        return {
            "decision": session.abstention if refused else f"anomalie : {session.abstention}",
            "detail": session.detail,
            "entry_outcome": session.entry_outcome,
        }
    return {"decision": DECIDED, **session.decision, "entry_outcome": session.entry_outcome}


def exit_outcome(trade: Trade) -> str:
    if trade.exit_utc is None:
        return OPEN_AT_END
    return EXIT_CATEGORY.get(trade.exit_reason or "", f"autre ({trade.exit_reason})")


def session_lines(
    result: Day01Result,
    h4: list[dict[str, Any]],
    gaps: list[Gap],
    config: ResearchConfig,
    m15: dict[datetime, dict[str, Any]],
) -> list[dict[str, Any]]:
    """One line per session: the path to D (fields of the availability study), then D and after."""
    params = result.day01_params
    probe = AvailabilityBacktest([], [], h4, [], gaps, params, config)  # ATR cause only, no replay
    trades = {t.decided_utc: t for t in all_trades(result)}
    records = {r.decision_utc: r for r in result.decisions}
    lines = []
    for s in result.sessions:
        atr = probe.atr_cause(london(s.day, params.freeze)) if s.abstention == ATR_UNAVAILABLE else None
        outcome, cause = path_to_d(s, m15, None if atr is None else atr[0])
        decision = at_d(s)
        trade = trades.get(s.decision["d_utc"]) if s.decision else None
        measured = None
        if s.decision is not None and s.range is not None:
            measured = entry_measures(s.decision, s.range["atr"], records.get(s.decision["d_utc"]), trade, config)
        lines.append(
            {
                "trigger": params.trigger.value,
                "day": s.day,
                "outcome": outcome,
                "cause": cause,
                "cause_detail": None if atr is None else atr[1],
                "range": s.range,
                "breakout": s.breakout,
                "retest": s.retest,
                "confirmation_utc": confirmation_of(s),
                "previous_position": s.previous_position,
                "at_d": decision,
                "trade": None if trade is None else trade_line(trade, result),
                "measures": measured,
                "events": s.events,
            }
        )
    return lines


STOP_DISTANCE = "|P_D − S| : prix d'entrée estimé à D jusqu'au stop, en pips et en multiples de A (ATR H4 figé)"
FIXED_COST_SHARE = (
    "(glissement + commission + prime de stop garanti) par contrat, en USD, divisés par la perte estimée au "
    "stop par contrat en USD à la cotation de dimensionnement (écart, glissement, commission et prime "
    "compris ; conversion exclue, proportionnelle)"
)


def _measured(value: Decimal | None, reason: str) -> dict[str, Any]:
    """A measure, or an absent value with the reason why it is not definable."""
    return {"value": value, "reason": None if value is not None else reason}


def entry_measures(
    decision: dict[str, Any], atr: Decimal, record: DecisionRecord | None, trade: Trade | None, config: ResearchConfig
) -> dict[str, Any]:
    """Per decided entry, never a filter (sheet §5): the three ratios side by side, the stop distance
    and the share of fixed costs in the risk. Only read from what the engine recorded at D and after."""
    spec, costs = config.spec, config.costs
    long = decision["side"] == Side.LONG.value
    p_d, stop, target = decision["p_d"], decision["stop"], decision["target"]
    risk_d = p_d - stop if long else stop - p_d
    reward_d = target - p_d if long else p_d - target
    slippage = (costs.slippage_pips.value or Decimal(0)) * spec.pip_size
    net: Decimal | None = None
    reason = "cotation ou ordre à D absents du journal des décisions"
    if record is not None and record.order is not None and record.known.get("quote") is not None:
        quote = record.known["quote"]  # same formula as S2, intraday: no night
        move = target - quote["ask"] - slippage if long else quote["bid"] - target - slippage
        gain_quote = move * spec.contract_size - (costs.commission_per_contract.value or Decimal(0))
        fee = costs.conversion_fee_rate.value or Decimal(0)
        gain = gain_quote / quote["ask"] * (1 - fee) if gain_quote > 0 else gain_quote / quote["bid"] * (1 + fee)
        loss = record.order["estimated_stop_loss"] / record.order["size"]
        net, reason = (gain / loss, "") if loss > 0 else (None, "perte estimée au stop non positive")
    obtained: Decimal | None = None
    obtained_reason, share_reason = "entrée non exécutée", "entrée non exécutée"
    share: Decimal | None = None
    if trade is not None:
        risk = trade.entry_price - stop if long else stop - trade.entry_price
        reward = target - trade.entry_price if long else trade.entry_price - target
        obtained = reward / risk if risk > 0 else None
        obtained_reason = "stop déjà dépassé au prix exécuté : risque non positif"
        premium = costs.guaranteed_stop_premium_per_contract.value if config.stop_type is StopType.GUARANTEED else 0
        fixed = slippage * spec.contract_size + (costs.commission_per_contract.value or 0) + (premium or 0)
        loss_quote = trade.estimate.loss_quote_per_contract
        share = fixed / loss_quote if loss_quote > 0 else None
        share_reason = "perte estimée au stop non positive"
    return {
        "ratios": {
            "estimated_distances_at_d": _measured(reward_d / risk_d if risk_d > 0 else None, "P_D au-delà du stop"),
            "net_estimated_at_d": _measured(net, reason),
            "obtained_at_execution": _measured(obtained, obtained_reason),
        },
        "stop_distance": {
            "definition": STOP_DISTANCE,
            "pips": risk_d / spec.pip_size,
            "atr_multiple": risk_d / atr,
        },
        "fixed_cost_share_of_risk": {"definition": FIXED_COST_SHARE, **_measured(share, share_reason)},
    }


def trade_line(trade: Trade, result: Day01Result) -> dict[str, Any]:
    liquidation = next((q for q in result.liquidations if q.closed_utc == trade.exit_utc), None)
    pending = trade.exit_utc is None and result.unexecuted_liquidation_utc is not None
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
        "annotations": annotations_of(trade, liquidation is not None and liquidation.unplanned_night,
                                   liquidation is not None and liquidation.after_interruption, pending),
    }  # fmt: skip


def annotations_of(trade: Trade, unplanned_night: bool, after_interruption: bool, pending: bool) -> list[str]:
    """Overlap the exclusive outcome; never counted as exits of their own."""
    out = [INDETERMINATE] if trade.indeterminate else []
    out += [UNPLANNED_NIGHT] if unplanned_night else []
    out += [LIQUIDATION_AFTER_INTERRUPTION] if after_interruption else []
    return out + ([PENDING_LIQUIDATION] if pending else [])


# ---------------------------------------------------------------------- reconciliation (protocol §5)


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


def reconcile(
    study: StudyLines,
    study_errors: list[str],
    lines: list[dict[str, Any]],
    trigger: Trigger,
    official: bool,
) -> dict[str, Any]:
    """Path of every session up to D included, field by field against the study (exact equality)."""
    errors = list(study_errors)
    run: dict[str, dict[str, Any]] = {}
    for line in lines:
        day = str(jsonable(line["day"]))
        if day in run:
            errors.append(f"passage : séance {day} présente plusieurs fois")
        run[day] = jsonable({f: line[f] for f in PATH_FIELDS})
    theirs = {d: r for (d, t), r in study.items() if t == trigger.value}
    common = sorted(set(run) & set(theirs))
    differences = [
        {"day": d, "field": f, "run": run[d][f], "study": theirs[d].get(f)}
        for d in common
        for f in PATH_FIELDS
        if run[d][f] != theirs[d].get(f)
    ]
    confirmations = sum(1 for line in run.values() if line["outcome"] == CONFIRMED)
    if official:
        if len(run) != OFFICIAL_DATES:
            errors.append(f"passage : {len(run)} séances au lieu de {OFFICIAL_DATES}")
        if confirmations != OFFICIAL_CONFIRMATIONS[trigger]:
            errors.append(f"passage : {confirmations} confirmations au lieu de {OFFICIAL_CONFIRMATIONS[trigger]}")
    only_run, only_study = sorted(set(run) - set(theirs)), sorted(set(theirs) - set(run))
    return {
        "ok": not (errors or differences or only_run or only_study),
        "key": "date de séance de Londres",
        "fields": list(PATH_FIELDS),
        "sessions": len(run),
        "confirmations": confirmations,
        "identical": len(common) - len({d["day"] for d in differences}),
        "only_in_run": only_run,
        "only_in_study": only_study,
        "difference_count": len(differences),
        "differences": differences[:50],
        "errors": errors,
    }


# ---------------------------------------------------------------------- execution funnel (protocol §6)


def execution(lines: list[dict[str, Any]], result: Day01Result) -> dict[str, Any]:
    """Confirmations -> refusal at D or decided entry -> pending entry outcome -> exclusive exit outcome,
    with the annotations beside. Read from the engine only."""
    confirmed = [line for line in lines if line["outcome"] == CONFIRMED]
    decisions = Counter(str(line["at_d"]["decision"]) for line in confirmed if line["at_d"] is not None)
    decided = [line for line in confirmed if line["at_d"] is not None and line["at_d"]["decision"] == DECIDED]
    entries = Counter(str(line["at_d"]["entry_outcome"] or "anomalie : aucune issue") for line in decided)
    executed = {line["at_d"]["d_utc"]: line for line in decided if line["at_d"]["entry_outcome"] in EXECUTED_OUTCOMES}
    unexecuted = {line["at_d"]["d_utc"] for line in decided if line["at_d"]["entry_outcome"] not in EXECUTED_OUTCOMES}
    trades = all_trades(result)
    per_entry = Counter(t.decided_utc for t in trades)
    by_decision = {t.decided_utc: t for t in trades}
    exits: Counter[str] = Counter()
    reasons: dict[str, Counter[str]] = defaultdict(Counter)
    marks: Counter[str] = Counter()
    immediate_ok = True
    for d, line in executed.items():
        trade = by_decision.get(d)
        if trade is None:
            continue
        category = exit_outcome(trade)
        exits[category] += 1
        reasons[category][trade.exit_reason or "—"] += 1
        marks.update(line["trade"]["annotations"] if line["trade"] else [])
        expected = IMMEDIATE_EXIT.get(line["at_d"]["entry_outcome"])
        immediate_ok &= trade.exit_reason == expected if expected else trade.exit_reason not in IMMEDIATE_EXIT.values()
    checks = {
        "every_confirmation_classified_once": sum(decisions.values()) == len(confirmed)
        and all(k == DECIDED or k in REFUSALS_AT_D for k in decisions),
        "decided_equals_sum_of_entry_outcomes": sum(entries.values()) == len(decided)
        and all(k in EXECUTED_OUTCOMES or k in NOT_EXECUTED_OUTCOMES for k in entries),
        "one_trade_per_executed_entry": all(per_entry[d] == 1 for d in executed),
        "no_trade_for_an_unexecuted_entry": all(per_entry[d] == 0 for d in unexecuted),
        "every_trade_from_an_executed_entry": set(per_entry) <= set(executed),
        "one_exclusive_outcome_per_executed_entry": sum(exits.values()) == len(executed)
        and all(k in EXIT_OUTCOMES for k in exits),
        "immediate_exits_keep_their_reason": immediate_ok,
    }
    return {
        "confirmations": len(confirmed),
        "at_d": dict(decisions.most_common()),
        "entries_decided": len(decided),
        "entry_outcomes": dict(entries.most_common()),
        "entries_executed": len(executed),
        "entries_not_executed": len(unexecuted),
        "executed_outcomes": {k: exits.get(k, 0) for k in EXIT_OUTCOMES},
        "closing_reasons": {k: dict(v.most_common()) for k, v in reasons.items()},
        "annotations": {
            "note": "annotations non additives : elles recoupent les issues exclusives",
            **{k: marks.get(k, 0) for k in ANNOTATIONS},
        },
        "checks": checks,
        "ok": all(checks.values()),
    }


def counts(funnel: dict[str, Any]) -> dict[str, Any]:
    """The counts of a funnel without its controls, which hold on the whole run only (by year, a trade
    may come from an entry of the previous year)."""
    return {k: v for k, v in funnel.items() if k not in ("checks", "ok")}


def liquidations(result: Day01Result) -> dict[str, Any]:
    """Resolved liquidations carry their three quantities; an order still pending at the end is reported
    with what is known (decision, waiting time to the end, open position, silence in progress), never
    with an invented closing instant, reason or quote, and is no failure."""
    errors = []
    closed = {t.exit_utc: t for t in result.trades}
    for q in result.liquidations:
        trade = closed.get(q.closed_utc)
        if trade is None or trade.exit_reason != q.close_reason:
            errors.append(f"liquidation décidée à {q.decided_utc.isoformat()} sans transaction clôturée correspondante")
        if q.silence is None or not q.close_reason:
            errors.append(f"liquidation décidée à {q.decided_utc.isoformat()} sans silence clos ou motif")
    resolved_exits = {q.closed_utc for q in result.liquidations}
    errors += [
        f"clôture {t.exit_utc} par {LIQUIDATION} sans ordre de liquidation"
        for t in result.trades
        if t.exit_reason == LIQUIDATION and t.exit_utc not in resolved_exits
    ]
    journal = Counter(e.kind for e in result.journal)
    after = sum(1 for q in result.liquidations if q.after_interruption)
    nights = sum(1 for q in result.liquidations if q.unplanned_night)
    if journal[LIQUIDATION_AFTER_INTERRUPTION] != after or journal[UNPLANNED_NIGHT] != nights:
        errors.append("annotations de liquidation différentes du journal du moteur")
    pending = None
    if result.unexecuted_liquidation_utc is not None:
        if result.open_trade is None or result.end_utc is None:
            errors.append("liquidation en attente à la fin sans position ouverte")
        else:
            pending = {
                "decided_utc": result.unexecuted_liquidation_utc,
                "end_of_study_utc": result.end_utc,
                "waiting_until_end": result.end_utc - result.unexecuted_liquidation_utc,
                "open_trade_decided_utc": result.open_trade.decided_utc,
                "silence_in_progress": result.silence_at_end,
                "closing": "aucune : ni instant, ni motif, ni cotation",
            }
    delays = sorted(q.delay_after_16h for q in result.liquidations)
    return {
        "ok": not errors,
        "errors": errors,
        "resolved": len(result.liquidations),
        "delay_after_16h": None if not delays else {"min": delays[0], "median": delays[len(delays) // 2],
                                                     "max": delays[-1]},
        "silence_kinds": dict(Counter(q.silence_kind.value for q in result.liquidations).most_common()),
        "close_reasons": dict(Counter(q.close_reason for q in result.liquidations).most_common()),
        "after_interruption": after,
        "unplanned_nights": nights,
        "pending_at_end": pending,
    }  # fmt: skip


def bounds(lines: list[dict[str, Any]], result: Day01Result) -> dict[str, Any]:
    """One position at a time; D within [K + unit, K + 60 min]; no execution after 12:05 London."""
    params, errors = result.day01_params, []
    for line in lines:
        d, breakout = line["confirmation_utc"], line["breakout"]
        if d is not None and breakout is not None:
            delay = d - breakout["k_utc"]
            if not params.trigger_step <= delay <= params.retest_delay:
                errors.append(f"{line['day']} : D − K = {delay}")
        trade = line["trade"]
        if trade is not None:
            if trade["entry_utc"] > london(line["day"], EXECUTION_LIMIT):
                errors.append(f"{line['day']} : exécution {trade['entry_utc'].isoformat()} après 12:05 Londres")
    ordered = sorted(all_trades(result), key=lambda t: t.entry_utc)
    for before, after in itertools.pairwise(ordered):
        if before.exit_utc is None or after.entry_utc < before.exit_utc:
            errors.append(f"positions simultanées : {before.entry_utc.isoformat()} et {after.entry_utc.isoformat()}")
    return {"ok": not errors, "errors": errors}


def scenario_triggers(result: Day01Result) -> dict[str, Any]:
    """Protocol §4, read in the run's own report: B and C if at least one indeterminate trade (an
    unexplained silence during a position, a position open at the end and a liquidation pending
    through that silence included); the rejection if at least one stop beyond at the first tick."""
    crossings = [
        {"decided_utc": t.decided_utc, "open_at_end": t.exit_utc is None, "spans": t.unobservable_crossings}
        for t in all_trades(result)
        if t.unobservable_crossings
    ]
    beyond = sum(1 for e in result.journal if e.kind == "STOP_DÉPASSÉ_À_L'EXÉCUTION")
    return {
        "indeterminate_trades": crossings,
        "scenario_b_required": bool(crossings),
        "scenario_c_required": bool(crossings),
        "stop_beyond_at_execution": beyond,
        "reject_required": beyond > 0,
        "pending_liquidation_at_end": result.unexecuted_liquidation_utc,
    }


def controls(
    study: StudyLines,
    study_errors: list[str],
    lines: list[dict[str, Any]],
    result: Day01Result,
    trigger: Trigger,
    official: bool,
    inputs: dict[str, Any],
    origin: dict[str, Any],
) -> dict[str, Any]:
    """Every control that must pass before any result is presented (protocol §5, §6)."""
    flow = execution(lines, result)
    return {
        "availability": reconcile(study, study_errors, lines, trigger, official),
        "execution": {"ok": flow["ok"], "checks": flow["checks"]},
        "liquidations": {k: v for k, v in liquidations(result).items() if k in ("ok", "errors", "pending_at_end")},
        "bounds": bounds(lines, result),
        "inputs": inputs,
        "provenance": origin,
    }


def gated_report(
    checks: dict[str, Any], triggers: dict[str, Any], results: Callable[[], dict[str, Any]]
) -> dict[str, Any]:
    """Protocol §5, §6: the results exist in the report only if every control passes."""
    failed = sorted(name for name, check in checks.items() if not check["ok"])
    if failed:
        return {"anomaly": f"contrôles en échec ({', '.join(failed)}) : résultats non présentés", "controls": checks}
    return {"controls": checks, "scenario_triggers": triggers, "result": results()}


# ---------------------------------------------------------------------- measures (protocol §7)


def _stats(values: list[Decimal]) -> dict[str, Any] | None:
    if not values:
        return None
    return {"n": len(values), "min": min(values), "median": statistics.median(values), "max": max(values)}


def ratios(lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Distributions of the per-entry measures (`entry_measures`); the detail stays in the local
    session file. Absent values are counted with their reasons, never replaced."""
    values: dict[str, list[Decimal]] = defaultdict(list)
    absent: dict[str, Counter[str]] = defaultdict(Counter)
    for line in lines:
        measured = line.get("measures")
        if measured is None:
            continue
        entries = {**measured["ratios"], "fixed_cost_share_of_risk": measured["fixed_cost_share_of_risk"]}
        for name, item in entries.items():
            if item["value"] is None:
                absent[name][item["reason"]] += 1
            else:
                values[name].append(item["value"])
        values["stop_distance_pips"].append(measured["stop_distance"]["pips"])
        values["stop_distance_atr_multiple"].append(measured["stop_distance"]["atr_multiple"])
    names = ("estimated_distances_at_d", "net_estimated_at_d", "obtained_at_execution", "fixed_cost_share_of_risk")
    return {
        **{name: _stats(values[name]) for name in (*names, "stop_distance_pips", "stop_distance_atr_multiple")},
        "absent": {name: dict(absent[name]) for name in names if absent[name]},
        "definitions": {"stop_distance": STOP_DISTANCE, "fixed_cost_share_of_risk": FIXED_COST_SHARE},
        "note": "rapports côte à côte, sans filtre ; estimés : entrées décidées ; obtenu et coûts fixes : exécutées",
    }


def breakdowns(lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Executed entries by weekday, London entry hour, clock (GMT, BST, offset weeks) and side."""
    groups: dict[str, dict[str, list[Decimal | None]]] = defaultdict(lambda: defaultdict(list))
    for line in lines:
        trade = line["trade"]
        if trade is None:
            continue
        day: date = line["day"]
        net = trade["net_eur"]
        groups["weekday"][f"{day.isoweekday()} {WEEKDAYS[day.weekday()]}"].append(net)
        groups["entry_hour_london"][trade["entry_utc"].astimezone(LONDON).strftime("%H")].append(net)
        groups["clock"][clocks(day)].append(net)
        groups["side"][line["at_d"]["side"]].append(net)
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


def measures(result: Day01Result, start: datetime, end: datetime) -> dict[str, Any]:
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


def overlap(result: Day01Result, other: dict[str, Any], end: datetime, window_years: list[int]) -> dict[str, Any]:
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
    overlapping = simultaneous = 0
    for trade in all_trades(result):
        a, b = trade.entry_utc, trade.exit_utc or end
        touched = lost = False
        for start1, end1, side1, net1 in theirs:
            seconds = (min(b, end1) - max(a, start1)).total_seconds()
            if seconds <= 0:
                continue
            touched = True
            same, opposite = (same + seconds, opposite) if side1 == trade.side.value else (same, opposite + seconds)
            lost |= trade.net_account is not None and trade.net_account < 0 and net1 is not None and net1 < 0
        overlapping += touched
        simultaneous += lost
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
        "day01_trades": len(all_trades(result)),
        "day01_trades_overlapping": overlapping,
        "day01_losses_overlapping_a_loss": simultaneous,
        "day01_losing_trades": sum(1 for t in result.trades if t.net_account is not None and t.net_account < 0),
        "hours_same_direction": same / 3600,
        "hours_opposite_direction": opposite / 3600,
        "net_by_year": {y: {"day01": ours.get(y, Decimal(0)), "reference": other_by_year.get(y, Decimal(0))}
                        for y in window_years},
        "note": "trajectoires indépendantes, chacune avec son capital : pas un portefeuille partagé",
    }  # fmt: skip


def performance(
    result: Day01Result,
    engine: Day01Run,
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
            "execution": counts(execution([line for line in lines if line["day"].year == year], result)),
            "closed_trades": _trade_totals(closed),
            "tick_drawdown": None if dd is None else asdict(dd),
        }
    report: dict[str, Any] = jsonable(
        {
            "execution": execution(lines, result),
            "liquidations": liquidations(result),
            "trades": [_trade(t) for t in result.trades],
            "open_trade_at_end": _trade(result.open_trade) if result.open_trade else None,
            "silence_at_end": result.silence_at_end,
            "balance_eur": result.balance,
            "equity_eur": result.equity,
            "closed_trade_totals": _trade_totals(result.trades),
            "concentration": concentration(result.trades),
            "ratios": ratios(lines),
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
            "comparisons": {name: overlap(result, ref, end, years(start, end)) for name, ref in references.items()},
            "by_year": by_year,
            "end_utc": result.end_utc,
        }
    )
    return report


# ---------------------------------------------------------------------- M5 / M15 (protocol §8)


def _dec(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def compare_triggers(m5: Iterable[dict[str, Any]], m15: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """The two session files of the same scenario, matched by London date (duplicates refused). One
    row per date with both outcomes and, for entries executed in both, the M15 − M5 differences of
    entry instant, stop, size and result; every synthesis is computed from these rows."""
    sides: dict[str, dict[str, dict[str, Any]]] = {}
    for name, rows in (("M5", m5), ("M15", m15)):
        sides[name] = {}
        for line in rows:
            if line["day"] in sides[name]:
                raise ValueError(f"{name} : séance {line['day']} présente plusieurs fois")
            sides[name][line["day"]] = line
    if set(sides["M5"]) != set(sides["M15"]):
        raise ValueError("les deux passages ne portent pas sur les mêmes dates de Londres")
    sessions = []
    for day in sorted(sides["M5"]):
        a, b = sides["M5"][day], sides["M15"][day]
        row: dict[str, Any] = {
            "day": day,
            "outcome": {"M5": a["outcome"], "M15": b["outcome"]},
            "confirmed": {"M5": a["outcome"] == CONFIRMED, "M15": b["outcome"] == CONFIRMED},
            "executed": {"M5": a.get("trade") is not None, "M15": b.get("trade") is not None},
            "m15_minus_m5": None,
        }
        if a.get("trade") is not None and b.get("trade") is not None:
            ta, tb = a["trade"], b["trade"]
            net_a, net_b = _dec(ta["net_eur"]), _dec(tb["net_eur"])
            row["m15_minus_m5"] = {
                "entry_minutes": (datetime.fromisoformat(tb["entry_utc"]) - datetime.fromisoformat(ta["entry_utc"]))
                .total_seconds() / 60,
                "stop": Decimal(tb["stop"]) - Decimal(ta["stop"]),
                "size": Decimal(tb["size"]) - Decimal(ta["size"]),
                "net_eur": None if net_a is None or net_b is None else net_b - net_a,
                "net_eur_m5": net_a,
                "net_eur_m15": net_b,
            }  # fmt: skip
        sessions.append(row)

    def split(key: str) -> dict[str, int]:
        return {
            "common": sum(1 for r in sessions if r[key]["M5"] and r[key]["M15"]),
            "only_m5": sum(1 for r in sessions if r[key]["M5"] and not r[key]["M15"]),
            "only_m15": sum(1 for r in sessions if r[key]["M15"] and not r[key]["M5"]),
        }

    both = [r["m15_minus_m5"] for r in sessions if r["m15_minus_m5"] is not None]
    closed = [d for d in both if d["net_eur"] is not None]
    report: dict[str, Any] = jsonable(
        {
            "key": "date de séance de Londres",
            "dates": len(sessions),
            "synthesis": {
                "confirmations": split("confirmed"),
                "executed": split("executed"),
                "path_differences": dict(
                    Counter(
                        f"{r['outcome']['M5']} -> {r['outcome']['M15']}"
                        for r in sessions
                        if r["outcome"]["M5"] != r["outcome"]["M15"]
                    ).most_common()
                ),
                "entry_delay_minutes": dict(sorted(Counter(d["entry_minutes"] for d in both).items())),
                "same_stop": sum(1 for d in both if d["stop"] == 0),
                "same_size": sum(1 for d in both if d["size"] == 0),
                "common_closed": len(closed),
                "net_of_common_closed_eur": {
                    "M5": sum((d["net_eur_m5"] for d in closed), Decimal(0)),
                    "M15": sum((d["net_eur_m15"] for d in closed), Decimal(0)),
                    "m15_minus_m5": sum((d["net_eur"] for d in closed), Decimal(0)),
                },
            },
            "sessions": sessions,
            "note": "détail par séance : sortie locale, hors Git",
        }
    )
    return report


# ---------------------------------------------------------------------- command


def _date(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def to_markdown(report: dict[str, Any]) -> str:
    config = report["config"]
    lines = [f"# DAY_01 — passage {config['trigger']} / scénario {config['scenario']} (rapport agrégé)", ""]
    lines += [report["notice"], "", "| Contrôle | Conforme |", "|---|---|"]
    lines += [f"| {name} | {'oui' if c['ok'] else 'NON'} |" for name, c in report["controls"].items()]
    if "result" not in report:
        return "\n".join([*lines, "", f"**{report['anomaly']}**", ""])
    ex = report["result"]["execution"]
    lines += ["", "## Des confirmations aux issues", "", f"Confirmations : {ex['confirmations']} (pas des entrées)."]
    lines += [""]
    lines += ["| Étape | Issue | Nombre |", "|---|---|---:|"]
    lines += [f"| à D | {k} | {n} |" for k, n in ex["at_d"].items()]
    lines += [f"| entrée décidée | {k} | {n} |" for k, n in ex["entry_outcomes"].items()]
    lines += [f"| entrée exécutée | {k} | {n} |" for k, n in ex["executed_outcomes"].items()]
    marks = {k: v for k, v in ex["annotations"].items() if k != "note"}
    lines += ["", "Annotations (non additives) : " + ", ".join(f"{k} {v}" for k, v in marks.items()), ""]
    totals = report["result"]["closed_trade_totals"]
    lines += [f"Net {totals['net_eur']} EUR (brut {totals['gross_eur']}, coûts {totals['costs_eur']}).", ""]
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
    for name in ("s1", "s2", "s3"):
        parser.add_argument(f"--{name}-reference", type=Path, help=f"rapport {name.upper()} de référence")
    parser.add_argument("--out", type=Path, required=True, help="rapport JSON (hors Git, sous data/)")
    parser.add_argument("--sessions-out", type=Path, required=True, help="détail JSONL par séance (hors Git)")
    args = parser.parse_args(argv)
    if not args.init_start <= args.start < args.end:
        parser.error("dates attendues : init-start <= start < end")
    require_development_window(args.init_start, args.end)
    began = time.perf_counter()
    trigger = Trigger(args.trigger)
    params: Day01Params = expected_params(trigger)  # approved values; only the trigger is chosen
    directory = args.data_dir / "bars" / SOURCE / INSTRUMENT
    candles = {g: directory / "intraday_2015_2021_day01_5min" / f"{g.value}.parquet" for g in Grid}
    h4_path = directory / f"{Timeframe.H4.value}.parquet"
    before = {path.as_posix(): sha256_file(path) for path in (*candles.values(), h4_path)}
    wrong = [g.value for g, path in candles.items() if before[path.as_posix()] != CANDLES_SHA256[g]]
    if wrong:
        print(f"empreintes des bougies {wrong} différentes de l'audit : aucune lecture", file=sys.stderr)
        return 2
    bars = {g: read_candles(path, args.end)[0] for g, path in candles.items()}
    h4 = load_bars(args.data_dir, SOURCE, INSTRUMENT, Timeframe.H4, args.init_start, args.end)
    gaps = load_gaps(args.data_dir / "reports" / f"quality_{SOURCE}_{INSTRUMENT}.json", args.end)
    files = tick_files(HistoryStore(args.data_dir).tick_files(SOURCE, INSTRUMENT), args.start, args.end)
    config = ResearchConfig(
        costs=RESEARCH_COSTS, stop_type=StopType.GUARANTEED, stop_at_execution=StopAtExecution[args.stop_at_execution]
    )  # 2 000 EUR, 0.25 %, minimum and increment 0.1: the references S1 to S3
    seen = [0]
    engine = Day01Run(
        bars[Grid.M5], bars[Grid.M15], h4, _counting(stream_ticks(files, args.start, args.end), seen), gaps, params,
        config, scenario=SCENARIOS[args.scenario], start_utc=args.start, end_utc=args.end,
    )  # fmt: skip
    result = engine.run()
    m15_rows = {b["start_utc"]: b for b in bars[Grid.M15]}
    lines = session_lines(result, h4, gaps, config, m15_rows)
    official = (args.start, args.end) == OFFICIAL_WINDOW
    with args.availability.open(encoding="utf-8") as rows:
        study, study_errors = study_lines((json.loads(r) for r in rows), official)
    after = {path.as_posix(): sha256_file(path) for path in (*candles.values(), h4_path)}
    finish = end_check(launch, tree_state())
    code_changed = finish["commit"] != launch["commit"] or any(
        f.startswith(CODE_PATHS) for f in finish["files_changed_during_run"]
    )
    window_ok = engine.first_tick_utc is None or (
        args.start <= engine.first_tick_utc and (engine.last_tick_utc or args.start) < args.end
    )
    inputs_errors = [] if before == after else ["empreintes des entrées modifiées pendant le passage"]
    inputs_errors += [] if window_ok else ["tick lu hors de la fenêtre"]
    inputs_errors += [] if params == expected_params(trigger) else ["paramètres différents de l'attendu"]
    provenance_errors = [] if not launch["uncommitted_diff_sha256"] else ["arbre non propre au lancement"]
    provenance_errors += ["code ou commit modifié pendant le passage"] if code_changed else []
    checks = controls(
        study, study_errors, lines, result, trigger, official,
        {"ok": not inputs_errors, "errors": inputs_errors, "sha256": {"before": before, "after": after}},
        {"ok": not provenance_errors, "errors": provenance_errors, "launch": launch, "end": finish},
    )  # fmt: skip
    references = {}
    for name in ("s1", "s2", "s3"):
        path = getattr(args, f"{name}_reference")
        if path is not None:
            references[name] = json.loads(path.read_text(encoding="utf-8"))
    body = gated_report(
        checks, jsonable(scenario_triggers(result)), lambda: performance(result, engine, lines, args.start, references)
    )
    passed = "result" in body
    report: dict[str, Any] = jsonable(
        {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "notice": "passage hors ligne : ni validation de performance ni autorisation de trading ; "
            "une confirmation n'est pas une entrée",
            "window": {"init_start": args.init_start, "start": args.start, "end": args.end},
            "config": {
                "trigger": trigger.value,
                "scenario": args.scenario,
                "gap_scenario": SCENARIOS[args.scenario].value,
                "stop_type": config.stop_type.value,
                "stop_at_execution": config.stop_at_execution.value,
                "params": asdict(params),
                "costs": {name: asdict(cost) for name, cost in vars(RESEARCH_COSTS).items()},
                "initial_equity": config.initial_equity,
                "risk_fraction": config.risk_fraction,
                "min_size": config.min_size,
                "size_increment": config.size_increment,
            },
            "inputs": {"m5": len(bars[Grid.M5]), "m15": len(bars[Grid.M15]), "h4": len(h4), "gaps": len(gaps),
                       "tick_files": len(files), "ticks": seen[0], "availability": str(args.availability)},
            **body,
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
    args.sessions_out.parent.mkdir(parents=True, exist_ok=True)
    args.sessions_out.write_text(
        "".join(json.dumps(jsonable(line), ensure_ascii=False) + "\n" for line in lines), encoding="utf-8"
    )
    print(f"rapport écrit : {args.out} ({report['seconds']} s, {report['peak_rss_mib']} Mio)")
    return 0


def compare_main(argv: list[str] | None = None) -> int:
    """M5 / M15 comparison of the same scenario, from the two local session files (protocol §8)."""
    parser = argparse.ArgumentParser(prog="forex-day01-compare", description=compare_main.__doc__)
    parser.add_argument("--m5", type=Path, required=True)
    parser.add_argument("--m15", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    with args.m5.open(encoding="utf-8") as a, args.m15.open(encoding="utf-8") as b:
        report = compare_triggers((json.loads(r) for r in a), (json.loads(r) for r in b))
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"comparaison écrite : {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
