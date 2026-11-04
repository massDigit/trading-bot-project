"""S3 performance run on 2015-2021 (step 4 of docs/strategies/S3_SQUEEZE.md §9). No order, no network.

    uv run forex-s3-backtest --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 --d1-filter on \
        --scenario A --step3 data/reports/backtests/s3_availability_2015_2021_1be93fd_details.jsonl \
        --s1-reference data/reports/backtests/s1_ref_2015_2021_h0.json \
        --s1-decisions data/reports/backtests/s1_ref_2015_2021_h0_decisions.jsonl \
        --out data/reports/backtests/s3_ref_2015_2021_d1h4_a.json \
        --decisions-out data/reports/backtests/s3_ref_2015_2021_d1h4_a_decisions.jsonl

One continuous trajectory per run: one D1 setting (reference D1 -> H4, comparison H4 only), one gap
scenario (A: an unobservable possible crossing is not triggered; B: it is) and one rule for a stop
already beyond at the first execution tick. Parameters are the approved values (ASSUMP-026), costs
and sizing those of the S1 reference. The engines are unchanged: this tool only observes.

Before any result, the boxes of the run are reconciled with those of step 3 (formation instant,
bounds, ATR, end). Any difference is an anomaly: the report then carries the differences only,
no performance result, and the command exits with status 2 (protocol §5).
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from forex_bot.backtest.data import load_bars, load_gaps, stream_ticks, tick_files
from forex_bot.backtest.engine import (
    DecisionRecord,
    EntryAction,
    ResearchConfig,
    ScenarioPolicy,
    StopAtExecution,
    StopType,
    TickDrawdown,
    Trade,
)
from forex_bot.backtest.explore import (
    INSTRUMENT,
    RESEARCH_COSTS,
    SOURCE,
    _date,
    _json,
    _peak_rss_mib,
    _provenance,
    _str,
    _trade,
    _trade_totals,
    by_year,
    decision_line,
)
from forex_bot.backtest.feed import Silence, Tick, classify_silence
from forex_bot.backtest.s2_engine import RelativeDrawdown
from forex_bot.backtest.s3 import Box, S3Params
from forex_bot.backtest.s3_engine import S3Backtest, S3Result
from forex_bot.history.calendar import Timeframe
from forex_bot.history.store import HistoryStore
from forex_bot.risk import Side

SCENARIOS = {"A": ScenarioPolicy.NONE_TRIGGERED, "B": ScenarioPolicy.ALL_TRIGGERED}
BOX_FIELDS = ("BH", "BL", "AH", "A", "ended_utc", "end_reason")


# ---------------------------------------------------------------------- observation


@dataclass
class Recovery:
    """Underwater episodes of the tick equity: from a peak to the first tick back at or above it."""

    peak_eur: Decimal
    peak_utc: datetime | None = None
    trough_eur: Decimal | None = None
    trough_utc: datetime | None = None
    longest: dict[str, Any] | None = None  # longest recovered episode
    deepest: dict[str, Any] | None = None  # episode of the largest fall in EUR, recovered or not

    def observe(self, utc: datetime, equity: Decimal) -> None:
        if equity >= self.peak_eur:
            if self.trough_eur is not None and self.peak_utc is not None:
                episode = self._episode(utc)
                days = (utc - self.peak_utc).total_seconds() / 86400
                if self.longest is None or days > self.longest["days"]:
                    self.longest = episode | {"days": days}
                self._deepest(episode)
            self.peak_eur, self.peak_utc, self.trough_eur, self.trough_utc = equity, utc, None, None
            return
        if self.trough_eur is None or equity < self.trough_eur:
            self.trough_eur, self.trough_utc = equity, utc

    def _episode(self, recovered: datetime | None) -> dict[str, Any]:
        fall = self.peak_eur - (self.trough_eur or self.peak_eur)
        return {
            "peak_utc": self.peak_utc,
            "peak_eur": self.peak_eur,
            "trough_utc": self.trough_utc,
            "fall_eur": fall,
            "recovered_utc": recovered,
        }

    def _deepest(self, episode: dict[str, Any]) -> None:
        if self.deepest is None or episode["fall_eur"] > self.deepest["fall_eur"]:
            self.deepest = episode

    def close(self) -> dict[str, Any]:
        """Report at the end of the run; an episode still under water is not recovered."""
        if self.trough_eur is not None:
            self._deepest(self._episode(None))
        return {"longest_recovered": self.longest, "deepest": self.deepest}


class S3Run(S3Backtest):
    """The S3 engine, plus observation only: drawdowns, recovery and the quotes around each gap."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.yearly_drawdown: dict[int, TickDrawdown] = {}
        self.relative = RelativeDrawdown(self.config.initial_equity)
        self.recovery = Recovery(self.config.initial_equity)
        self._equity_before = self.config.initial_equity
        self.gap_events: list[dict[str, Any]] = []

    def _observe(self, tick: Tick) -> None:
        equity = self.balance + self._unrealized(tick)  # once per tick for every measure
        self.drawdown.observe(tick.ts_utc, equity)
        position = self.position
        self.relative.observe(tick.ts_utc, equity, None if position is None else position.decided_utc.isoformat())
        self.recovery.observe(tick.ts_utc, equity)
        year = tick.ts_utc.year
        if year not in self.yearly_drawdown:  # each year starts from the equity at its first tick
            self.yearly_drawdown[year] = TickDrawdown(self._equity_before, None)
        self.yearly_drawdown[year].observe(tick.ts_utc, equity)
        self._equity_before = equity

    def _after_silence(self, previous: Tick, tick: Tick) -> None:
        kind = classify_silence(
            previous.ts_utc, tick.ts_utc, self.config.gap_threshold, self.config.documented_closures
        )
        position = self.position
        if kind is not Silence.UNEXPLAINED or position is None:
            super()._after_silence(previous, tick)
            return
        pip = self.config.spec.pip_size
        long = position.side is Side.LONG
        exit_after = tick.bid if long else tick.ask
        crossings = len(position.unobservable_crossings)
        event: dict[str, Any] = {
            "decided_utc": position.decided_utc,
            "side": position.side.value,
            "size": position.size,
            "entry_price": position.entry_price,
            "stop": position.stop,
            "gap": [previous.ts_utc, tick.ts_utc],
            "before": {"bid": previous.bid, "ask": previous.ask},
            "after": {"bid": tick.bid, "ask": tick.ask},
            "distance_after_to_stop_pips": abs(exit_after - position.stop) / pip,
        }
        super()._after_silence(previous, tick)
        event["possible_unobservable_crossing"] = len(position.unobservable_crossings) > crossings
        event["stop_beyond_after_gap"] = self._crossed_after(position, tick)
        event["closed"] = self.position is None
        self.gap_events.append(event)

    @staticmethod
    def _crossed_after(position: Trade, tick: Tick) -> bool:
        return tick.bid <= position.stop if position.side is Side.LONG else tick.ask >= position.stop


# ---------------------------------------------------------------------- step-3 reconciliation


def step3_boxes(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """The boxes of the step-3 detailed rows."""
    return [r for r in rows if r.get("kind") == "boîte"]


def _same(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except InvalidOperation:
        return str(a) == str(b)


def _text(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else None if value is None else str(value)


def reconcile_boxes(step3: list[dict[str, Any]], boxes: list[Box]) -> dict[str, Any]:
    """Boxes of the run against step 3, keyed by F: identical, missing on either side, or which field differs."""
    expected = {str(r["F"]): r for r in step3}
    found = {_text(b.formed_utc): {k: _text(v) for k, v in b.describe().items()} for b in boxes}
    different = []
    for key in sorted(expected.keys() & found.keys()):
        fields = {
            name: {"step3": expected[key].get(name), "run": found[key][name]}
            for name in BOX_FIELDS
            if not _same(expected[key].get(name), found[key][name])
        }
        if fields:
            different.append({"F": key, "fields": fields})
    only_run = sorted(found.keys() - expected.keys())
    only_step3 = sorted(expected.keys() - found.keys())
    return {
        "step3_boxes": len(expected),
        "run_boxes": len(found),
        "identical": len(expected.keys() & found.keys()) - len(different),
        "only_in_run": only_run,
        "only_in_step3": only_step3,
        "different": different,
        "ok": not (different or only_run or only_step3) and len(boxes) == len(found) == len(step3),
    }


# ---------------------------------------------------------------------- funnel


def breakout_category(record: DecisionRecord) -> str:
    """The single category of a breakout, from the action and the reason the engine recorded."""
    action = record.entry_action
    reason = record.reasons[-1] if record.reasons else ""
    if action is EntryAction.ENTRY_DECIDED:
        return "entrée décidée"
    if action is EntryAction.NOT_EVALUATED:
        return "non évaluée : position S3 déjà ouverte"
    if action is EntryAction.NOT_COMPUTABLE:
        if reason.startswith("bougie de cassure"):
            return "données : bougie de cassure non OK"
        if reason.startswith("bandes non calculables"):
            return "données : bandes non calculables"
        if reason.startswith("historique D1 insuffisant"):
            return "données D1 : insuffisantes"
        if reason.startswith(("D1 de contexte non utilisable", "D1 non utilisable")):
            return "données D1 : inutilisables"
        return f"données : autre ({reason})"
    if reason.startswith("pas d'expansion"):
        return "refus : pas d'expansion"
    if " contre le contexte D1" in reason:
        return "refus : contexte D1 calculable, neutre ou contraire"
    if "marché fermé" in reason:
        return "refus : marché fermé à D"
    if reason.startswith("aucune cotation connue"):
        return "refus taille : aucune cotation connue"
    if reason.startswith("estimation impossible"):
        return "refus taille : estimation impossible"
    if reason.startswith("coût inconnu"):
        return "refus taille : coût inconnu"
    if reason.startswith("taille minimale"):
        return "refus taille : taille minimale"
    return f"refus : autre ({reason})"


def _all_trades(result: S3Result) -> list[Trade]:
    return [*result.trades, *([result.open_trade] if result.open_trade else [])]


def execution_of(record: DecisionRecord, result: S3Result, trades: dict[datetime, Trade]) -> str:
    """What became of a decided entry: executed (possibly liquidated at once) or not, with the reason."""
    trade = trades.get(record.decision_utc)
    if trade is not None:
        if trade.exit_reason == "STOP_FRANCHI_À_L'EXÉCUTION":
            return "exécutée puis liquidée au premier tick (stop déjà dépassé)"
        return "exécutée : position ouverte"
    later = [r.decision_utc for r in result.decisions if r.decision_utc > record.decision_utc]
    until = later[0] if later else None
    for entry in result.journal:
        if entry.utc > record.decision_utc and (until is None or entry.utc <= until):
            if entry.kind == "ENTRÉE_REJETÉE":
                return "non exécutée : rejet à l'exécution (stop invalide)"
            if entry.kind == "ENTRÉE_ANNULÉE":
                return "non exécutée : position déjà ouverte"
    return "non exécutée : aucun tick avant la fin de la fenêtre"


def funnel(result: S3Result, records: list[DecisionRecord] | None = None) -> dict[str, Any]:
    """Boxes -> breakouts -> one category each -> decided entries -> executed or not (protocol §6)."""
    records = result.decisions if records is None else records
    breakouts = [r for r in records if r.signal is not None]
    categories = Counter(breakout_category(r) for r in breakouts)
    trades = {t.decided_utc: t for t in _all_trades(result)}
    decided = [r for r in breakouts if r.entry_action is EntryAction.ENTRY_DECIDED]
    executions = Counter(execution_of(r, result, trades) for r in decided)
    return {
        "breakouts": len(breakouts),
        "by_side": dict(Counter(str(r.signal["side"]) for r in breakouts if r.signal).most_common()),
        "categories": dict(categories.most_common()),
        "entries_decided": len(decided),
        "executions": dict(executions.most_common()),
        "checks": {
            "one_category_per_breakout": sum(categories.values()) == len(breakouts),
            "no_unclassified_reason": not any("autre (" in k for k in categories),
            "decided_equals_executed_plus_not": sum(executions.values()) == len(decided)
            and categories.get("entrée décidée", 0) == len(decided),
        },
    }


def scenario_triggers(result: S3Result) -> dict[str, Any]:
    """Protocol §4: B if the engine recorded a possible unobservable crossing under A, open trade included.

    A gap followed by a price already beyond the stop closes the position at the stop (observed): it
    is not an unobservable crossing and does not require B by itself.
    """
    crossings = [
        {"decided_utc": t.decided_utc, "open_at_end": t.exit_utc is None, "spans": t.unobservable_crossings}
        for t in _all_trades(result)
        if t.unobservable_crossings
    ]
    beyond = sum(1 for e in result.journal if e.kind == "STOP_DÉPASSÉ_À_L'EXÉCUTION")
    return {
        "unobservable_crossings": crossings,
        "scenario_b_required": bool(crossings),
        "stop_beyond_at_execution": beyond,
        "reject_required": beyond > 0,
    }


# ---------------------------------------------------------------------- measures


def _risk(trade: Trade) -> Decimal | None:
    risk = trade.size * trade.estimate.loss_account_per_contract
    return None if risk <= 0 or trade.net_account is None else trade.net_account / risk


def _stats(values: list[Decimal]) -> dict[str, Any]:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "mean": sum(values, Decimal(0)) / len(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def returns_to_box(result: S3Result) -> dict[str, Any]:
    """Description only (sheet §9): positions with a reintegration, a crossing, or no return."""
    events = {e.decided_utc: e for e in result.returns}
    groups: dict[str, list[Trade]] = defaultdict(list)
    for trade in result.trades:
        event = events.get(trade.decided_utc)
        groups["sans retour" if event is None else event.kind.value].append(trade)
    out: dict[str, Any] = {}
    for kind, trades in sorted(groups.items()):
        delays = [Decimal(events[t.decided_utc].h4_since_entry) for t in trades if t.decided_utc in events]
        out[kind] = {
            "positions": len(trades),
            "h4_since_entry": _stats(delays),
            "exits": dict(Counter(t.exit_reason for t in trades).most_common()),
            "risk_multiples": _stats([r for t in trades if (r := _risk(t)) is not None]),
        }
    open_trade = result.open_trade
    if open_trade is not None:
        event = events.get(open_trade.decided_utc)
        out["position ouverte à la fin"] = {"return": None if event is None else event.kind.value}
    return out


def months(start: datetime, end: datetime) -> list[tuple[int, int]]:
    out, year, month = [], start.year, start.month
    while (year, month) < (end.year, end.month) or (end.day > 1 and (year, month) == (end.year, end.month)):
        out.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def book_measures(result: S3Result, start: datetime, end: datetime) -> dict[str, Any]:
    """Measures of the specification (§9): expectancy in risk multiples, profit factor, exposure, months."""
    closed = [t for t in result.trades if t.net_account is not None]
    wins = [t.net_account for t in closed if t.net_account is not None and t.net_account > 0]
    losses = [t.net_account for t in closed if t.net_account is not None and t.net_account <= 0]
    multiples = [r for t in closed if (r := _risk(t)) is not None]
    exposure = sum(((t.exit_utc or end) - t.entry_utc for t in _all_trades(result)), timedelta(0))
    entered = {(t.entry_utc.year, t.entry_utc.month) for t in _all_trades(result)}
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


def concentration(trades: list[Trade]) -> dict[str, Any]:
    closed = [t for t in trades if t.net_account is not None]
    net = sum((t.net_account for t in closed if t.net_account is not None), Decimal(0))
    best = max(closed, key=lambda t: t.net_account or Decimal(0), default=None)
    if best is None or best.net_account is None:
        return {"net_eur": net, "best": None, "net_without_best_eur": net}
    return {
        "net_eur": net,
        "best": {"decided_utc": best.decided_utc, "side": best.side.value, "net_eur": best.net_account},
        "net_without_best_eur": net - best.net_account,
    }


# ---------------------------------------------------------------------- comparison with S1


def s1_signals(lines: Iterable[dict[str, Any]]) -> set[tuple[str, str]]:
    """(decision instant, side) of every S1 signal, entry decided or not."""
    return {
        (datetime.fromisoformat(r["decision_utc"]).isoformat(), str(r["signal"]["side"]))
        for r in lines
        if r.get("signal") and r["signal"].get("side")
    }


def compare_with_s1(
    result: S3Result, s1_report: dict[str, Any], signals: set[tuple[str, str]], end: datetime
) -> dict[str, Any]:
    """Coincidence of entries, time overlap, simultaneous losses and annual nets side by side (protocol §8)."""
    entries = [
        (r.decision_utc.isoformat(), str(r.signal["side"]))
        for r in result.decisions
        if r.entry_action is EntryAction.ENTRY_DECIDED and r.signal is not None
    ]
    coincident = [e for e in entries if e in signals]
    s1_trades = [*s1_report["result"]["trades"], *filter(None, [s1_report["result"].get("open_trade_at_end")])]
    s1 = [
        (
            datetime.fromisoformat(t["entry_utc"]),
            datetime.fromisoformat(t["exit_utc"]) if t.get("exit_utc") else end,
            t["side"],
            Decimal(t["net_account"]) if t.get("net_account") is not None else None,
        )
        for t in s1_trades
    ]
    same = opposite = 0.0
    overlapping = simultaneous_losses = 0
    s3 = _all_trades(result)
    for trade in s3:
        a, b = trade.entry_utc, trade.exit_utc or end
        touched = lost_together = False
        for start1, end1, side1, net1 in s1:
            seconds = (min(b, end1) - max(a, start1)).total_seconds()
            if seconds <= 0:
                continue
            touched = True
            if side1 == trade.side.value:
                same += seconds
            else:
                opposite += seconds
            if trade.net_account is not None and trade.net_account < 0 and net1 is not None and net1 < 0:
                lost_together = True
        overlapping += touched
        simultaneous_losses += lost_together
    losers = sum(1 for t in result.trades if t.net_account is not None and t.net_account < 0)
    s3_by_year: dict[int, Decimal] = defaultdict(Decimal)
    for t in result.trades:
        if t.exit_utc is not None and t.net_account is not None:
            s3_by_year[t.exit_utc.year] += t.net_account
    return {
        "s1_reference": {"commit": s1_report.get("provenance", {}).get("commit"), "trades": len(s1_trades)},
        "entries_decided": len(entries),
        "entries_coinciding_with_an_s1_signal": len(coincident),
        "coincidence_pct": None if not entries else len(coincident) / len(entries) * 100,
        "hours_same_direction": same / 3600,
        "hours_opposite_direction": opposite / 3600,
        "s3_trades": len(s3),
        "s3_trades_overlapping_an_s1_trade": overlapping,
        "s3_losing_trades": losers,
        "s3_losses_overlapping_an_s1_loss": simultaneous_losses,
        "net_by_year": {
            year: {"s1": s1_report["by_year"].get(str(year), {}).get("closed_trades", {}).get("net_eur"), "s3": net}
            for year, net in sorted(s3_by_year.items())
        },
    }


# ---------------------------------------------------------------------- report


def performance(
    result: S3Result, engine: S3Run, start: datetime, s1: dict[str, Any] | None, signals: set[tuple[str, str]]
) -> dict[str, Any]:
    trades = _all_trades(result)
    relative = engine.relative
    end = result.end_utc or datetime.now(UTC)
    report = by_year(result, engine.yearly_drawdown)
    for year, line in report.items():
        line["funnel"] = funnel(result, [r for r in result.decisions if r.decision_utc.year == year])
        line["breakouts"] = line["funnel"]["breakouts"]  # the S1 counter misses breakouts not evaluated
    return _json(
        {
            "funnel": funnel(result),
            "trades": [_trade(t) for t in result.trades],
            "open_trade_at_end": _trade(result.open_trade) if result.open_trade else None,
            "balance_eur": result.balance,
            "equity_eur": result.equity,
            "closed_trade_totals": _trade_totals(result.trades),
            "exits": dict(Counter(t.exit_reason for t in result.trades).most_common()),
            "concentration": concentration(result.trades),
            "returns_to_box": returns_to_box(result),
            "measures": book_measures(result, start, end),
            "tick_drawdown_eur": asdict(result.tick_drawdown) if result.tick_drawdown else None,
            "relative_drawdown": {
                "max_pct": relative.max_ratio * 100,
                "max_utc": relative.max_utc,
                "peak_eur_at_end": relative.peak_eur,
                "first_review_crossing_6pct": relative.first_review_crossing,
            },
            "recovery": engine.recovery.close(),
            "risk_overruns": [
                {"entry_utc": t.entry_utc, "measure": t.exposure_measure, "overrun_eur": t.risk_overrun}
                for t in trades
                if t.risk_overrun
            ],
            "indeterminate": {"trades": sum(1 for t in trades if t.indeterminate), "gap_events": engine.gap_events},
            "journal_counts": dict(sorted(Counter(e.kind for e in result.journal).items())),
            "decisions": len(result.decisions),
            "end_utc": result.end_utc,
            "s1_comparison": None if s1 is None else compare_with_s1(result, s1, signals, end),
            "by_year": report,
        }
    )


def gated_report(
    check: dict[str, Any], triggers: dict[str, Any], results: Callable[[], dict[str, Any]]
) -> dict[str, Any]:
    """Protocol §5: the performance results exist in the report only if the boxes match step 3."""
    if not check["ok"]:
        return {
            "anomaly": "boîtes différentes de l'étape 3 : résultats de performance non présentés",
            "boxes_check": check,
        }
    return {"boxes_check": check, "scenario_triggers": triggers, "result": results()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forex-s3-backtest", description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--init-start", type=_date, required=True)
    parser.add_argument("--start", type=_date, required=True)
    parser.add_argument("--end", type=_date, required=True)
    parser.add_argument("--d1-filter", choices=["on", "off"], required=True, help="on : référence D1 -> H4")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    parser.add_argument(
        "--stop-at-execution",
        choices=[s.name for s in StopAtExecution],
        default=StopAtExecution.FILL_THEN_LIQUIDATE.name,
    )
    parser.add_argument("--step3", type=Path, required=True, help="lignes détaillées de l'étape 3 (boîtes)")
    parser.add_argument("--s1-reference", type=Path, help="rapport S1 de référence")
    parser.add_argument("--s1-decisions", type=Path, help="journal des décisions S1 de référence (signaux)")
    parser.add_argument("--out", type=Path, required=True, help="rapport JSON (hors Git, sous data/)")
    parser.add_argument("--decisions-out", type=Path, help="journal JSONL des décisions (hors Git, sous data/)")
    args = parser.parse_args(argv)
    if not args.init_start <= args.start < args.end:
        parser.error("dates attendues : init-start <= start < end")

    provenance = _provenance(argv, prog="forex-s3-backtest")  # at launch: the code the run starts from
    began = time.perf_counter()
    params = S3Params(use_d1_filter=args.d1_filter == "on")  # approved values; only the D1 setting is chosen
    bars = {
        tf: load_bars(args.data_dir, SOURCE, INSTRUMENT, tf, args.init_start, args.end)
        for tf in (Timeframe.H4, Timeframe.D1)
    }
    gaps = load_gaps(args.data_dir / "reports" / f"quality_{SOURCE}_{INSTRUMENT}.json", args.end)
    files = tick_files(HistoryStore(args.data_dir).tick_files(SOURCE, INSTRUMENT), args.start, args.end)
    config = ResearchConfig(
        costs=RESEARCH_COSTS,
        stop_type=StopType.GUARANTEED,
        policy=SCENARIOS[args.scenario],
        stop_at_execution=StopAtExecution[args.stop_at_execution],
    )  # 2 000 EUR, 0.25 %, minimum and increment 0.1: the S1 reference defaults
    counted = 0

    def counting(ticks: Any) -> Any:
        nonlocal counted
        for tick in ticks:
            counted += 1
            yield tick

    engine = S3Run(
        bars[Timeframe.H4],
        bars[Timeframe.D1],
        counting(stream_ticks(files, args.start, args.end)),
        gaps,
        params,
        config,
        start_utc=args.start,
        end_utc=args.end,
    )
    result = engine.run()
    with args.step3.open() as rows:
        check = reconcile_boxes(step3_boxes(json.loads(line) for line in rows), result.boxes)
    s1 = json.loads(args.s1_reference.read_text()) if args.s1_reference else None
    signals: set[tuple[str, str]] = set()
    if args.s1_decisions:
        with args.s1_decisions.open() as lines:
            signals = s1_signals(json.loads(line) for line in lines)
    body = gated_report(check, scenario_triggers(result), lambda: performance(result, engine, args.start, s1, signals))
    if check["ok"] and args.decisions_out:
        args.decisions_out.parent.mkdir(parents=True, exist_ok=True)
        with args.decisions_out.open("w") as out:
            for record in result.decisions:
                out.write(json.dumps(decision_line(record), ensure_ascii=False, default=str) + "\n")
    full = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "notice": "passage hors ligne : ni validation de performance ni autorisation de trading",
        "provenance": provenance,
        "window": {"init_start": args.init_start, "start": args.start, "end": args.end},
        "config": {
            "d1_filter": params.use_d1_filter,
            "scenario": config.policy.value,
            "stop_type": config.stop_type.value,
            "stop_at_execution": config.stop_at_execution.value,
            "params": asdict(params),
            "costs": {name: asdict(cost) for name, cost in vars(RESEARCH_COSTS).items()},
            "initial_equity": config.initial_equity,
            "risk_fraction": config.risk_fraction,
            "min_size": config.min_size,
            "size_increment": config.size_increment,
            "latency": str(config.latency),
        },
        "inputs": {tf.value: len(b) for tf, b in bars.items()}
        | {"gaps": len(gaps), "tick_files": len(files), "ticks": counted, "step3": str(args.step3)},
        **body,
        "seconds": round(time.perf_counter() - began, 1),
        "peak_rss_mib": round(_peak_rss_mib(), 1),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(_str(full), ensure_ascii=False, indent=2, default=str))
    if not check["ok"]:
        print(f"ANOMALIE : boîtes différentes de l'étape 3, résultats non présentés ({args.out})")
        print(json.dumps(_str(check), ensure_ascii=False, indent=2))
        return 2
    print(f"rapport écrit : {args.out} ({full['seconds']} s, {full['peak_rss_mib']} Mio)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
