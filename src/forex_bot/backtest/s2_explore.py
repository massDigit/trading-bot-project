"""S2 performance run on 2015-2021 (step 4 of docs/strategies/S2_PULLBACK.md §9). No order, no network.

    uv run forex-s2-backtest --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 --trigger H1 \
        --scenario A --s1-reference data/reports/backtests/s1_ref_2015_2021_h0.json \
        --out data/reports/backtests/s2_ref_2015_2021_h1_a.json \
        --decisions-out data/reports/backtests/s2_ref_2015_2021_h1_a_decisions.jsonl

One continuous trajectory per run: one trigger timeframe (H1 reference, H4 comparison), one gap
scenario (A observed only, B stop first, C target first) and one rule for a stop already beyond at
the first execution tick. Parameters are the approved values (ASSUMP-025), costs and sizing those
of the S1 reference. The report follows the sheet §9: the path from detected breakouts to decided
entries and to positions actually opened, trades, gross, costs, net, exits by reason, tick
drawdown in EUR and the true maximum relative drawdown, the first crossing of the 6 % review
threshold, the net without the best trade, indeterminate trades with the quotes around each gap,
results in multiples of the risk, and the time overlap of positions with the S1 reference.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from forex_bot.backtest.data import load_bars, load_gaps, stream_ticks, tick_files
from forex_bot.backtest.engine import EntryAction, ResearchConfig, StopAtExecution, StopType, TickDrawdown, Trade
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
from forex_bot.backtest.s2 import GapScenario, S2Params
from forex_bot.backtest.s2_engine import S2Backtest, S2Result
from forex_bot.history.calendar import Timeframe
from forex_bot.history.store import HistoryStore
from forex_bot.risk import Side

SCENARIOS = {"A": GapScenario.OBSERVED_ONLY, "B": GapScenario.STOP_FIRST, "C": GapScenario.TARGET_FIRST}


class S2Run(S2Backtest):
    """The S2 engine, plus observation only: a tick drawdown per year and the quotes around each gap."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.yearly_drawdown: dict[int, TickDrawdown] = {}
        self._equity_before = self.config.initial_equity
        self.gap_events: list[dict[str, Any]] = []

    def _observe(self, tick: Tick) -> None:
        equity = self.balance + self._unrealized(tick)  # once per tick for every measure
        self.drawdown.observe(tick.ts_utc, equity)
        position = self.position
        self.relative.observe(tick.ts_utc, equity, None if position is None else position.decided_utc.isoformat())
        year = tick.ts_utc.year
        if year not in self.yearly_drawdown:  # each year starts from the equity at its first tick
            self.yearly_drawdown[year] = TickDrawdown(self._equity_before, None)
        self.yearly_drawdown[year].observe(tick.ts_utc, equity)
        self._equity_before = equity

    def _after_silence(self, previous: Tick, tick: Tick) -> None:
        kind = classify_silence(
            previous.ts_utc, tick.ts_utc, self.config.gap_threshold, self.config.documented_closures
        )
        position, target = self.position, self.target
        if kind is not Silence.UNEXPLAINED or position is None:
            super()._after_silence(previous, tick)
            return
        pip = self.config.spec.pip_size
        long = position.side is Side.LONG
        exit_after = tick.bid if long else tick.ask

        def pips(level: Decimal | None) -> Decimal | None:
            if level is None:
                return None
            return ((level - position.entry_price) if long else (position.entry_price - level)) / pip

        event: dict[str, Any] = {
            "decided_utc": position.decided_utc,
            "side": position.side.value,
            "size": position.size,
            "entry_price": position.entry_price,
            "stop": position.stop,
            "target": target,
            "gap": [previous.ts_utc, tick.ts_utc],
            "before": {"bid": previous.bid, "ask": previous.ask},
            "after": {"bid": tick.bid, "ask": tick.ask},
            "distance_after_to_stop_pips": abs(exit_after - position.stop) / pip,
            "distance_after_to_target_pips": None if target is None else abs(exit_after - target) / pip,
            "outcome_pips_if_stop": pips(position.stop),
            "outcome_pips_if_target": pips(target),
            "outcome_pips_observed_after": pips(exit_after),
        }
        super()._after_silence(previous, tick)
        event["closed_by_scenario"] = self.position is None
        self.gap_events.append(event)


def _all_trades(result: S2Result) -> list[Trade]:
    return [*result.trades, *([result.open_trade] if result.open_trade else [])]


def breakout_funnel(result: S2Result) -> dict[str, Any]:
    """Detected breakouts -> decided entries -> positions actually opened (sheet §8 categories)."""
    detected = [r for r in result.decisions if r.signal is not None]
    outcome: Counter[str] = Counter()
    other: Counter[str] = Counter()
    decided = []
    for record in detected:
        action = record.entry_action
        if action is EntryAction.ENTRY_DECIDED:
            decided.append(record)
            continue
        if action is EntryAction.NOT_COMPUTABLE:
            outcome["non évaluable (données à la cassure)"] += 1
            continue
        if action is EntryAction.NOT_EVALUATED:
            outcome["position déjà ouverte (seuil consommé)"] += 1
            continue
        reason = record.reasons[-1] if record.reasons else ""
        if reason.startswith("tendance D1 perdue"):
            outcome["refus : tendance D1 perdue"] += 1
        elif reason.startswith("cible trop proche"):
            outcome["refus : rapport gain/risque < R_min"] += 1
        elif "marché fermé" in reason:
            outcome["refus : marché fermé à D"] += 1
        elif reason.startswith("taille minimale"):
            outcome["refus : taille minimale"] += 1
        else:
            outcome["refus : autre"] += 1
            other[reason] += 1
    trades = {t.decided_utc: t for t in _all_trades(result)}
    executed: Counter[str] = Counter()
    for record in decided:
        trade = trades.get(record.decision_utc)
        if trade is None:
            executed["non exécutée (rejet à l'exécution ou position encore ouverte)"] += 1
        elif trade.exit_reason == "STOP_FRANCHI_À_L'EXÉCUTION":
            executed["exécutée puis liquidée au premier tick (stop déjà dépassé)"] += 1
        elif trade.exit_reason == "CIBLE_ATTEINTE_À_L'EXÉCUTION":
            executed["exécutée, cible déjà atteinte au premier tick"] += 1
        else:
            executed["position effectivement ouverte"] += 1
    kinds = Counter(e.kind for e in result.journal)
    return {
        "breakouts_detected": len(detected),
        "not_entered": dict(outcome.most_common()),
        "other_refusals": dict(other.most_common()),
        "entries_decided": len(decided),
        "after_decision": dict(executed.most_common()),
        "journal": {
            "rejected_at_execution": kinds["ENTRÉE_REJETÉE"],
            "cancelled_position_open": kinds["ENTRÉE_ANNULÉE"],
            "stop_beyond_at_execution": kinds["STOP_DÉPASSÉ_À_L'EXÉCUTION"],
        },
    }


def configurations(result: S2Result) -> dict[str, Any]:
    fates: Counter[str] = Counter()
    for setup in result.setups:
        if setup.used:
            fates["entrée décidée"] += 1
            continue
        abandoned = [h for h in setup.history if " abandonnée : " in h]
        if abandoned:
            reason = abandoned[-1].split(" abandonnée : ", 1)[1]
            fates["abandonnée : " + reason.split(" (", 1)[0].split(" :", 1)[0]] += 1
        else:
            fates["active à la fin"] += 1
    return {
        "created": len(result.setups),
        "with_a_breakout": sum(1 for s in result.setups if s.refused_utc is not None or s.used),
        "fates": dict(fates.most_common()),
    }


def risk_multiples(trades: list[Trade]) -> dict[str, Any]:
    values = []
    for trade in trades:
        risk = trade.size * trade.estimate.loss_account_per_contract
        if trade.net_account is not None and risk > 0:
            values.append(trade.net_account / risk)
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "sum": sum(values, Decimal(0)),
        "mean": sum(values, Decimal(0)) / len(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "at_least_1R": sum(1 for v in values if v >= 1),
        "at_most_minus_1R": sum(1 for v in values if v <= -1),
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


def overlap_with_s1(s2: list[Trade], s1_report: dict[str, Any], end: datetime) -> dict[str, Any]:
    """Time both strategies hold a position, same and opposite direction, and annual nets side by side."""
    s1_trades = [*s1_report["result"]["trades"], *filter(None, [s1_report["result"]["open_trade_at_end"]])]
    s1 = sorted(
        [
            (
                datetime.fromisoformat(t["entry_utc"]),
                datetime.fromisoformat(t["exit_utc"]) if t["exit_utc"] else end,
                t["side"],
            )
            for t in s1_trades
        ]
    )
    s2_rows = sorted((t.entry_utc, t.exit_utc or end, t.side.value) for t in s2)
    same = opposite = 0.0
    overlapping_trades = 0
    for start2, end2, side2 in s2_rows:
        touched = False
        for start1, end1, side1 in s1:
            seconds = (min(end1, end2) - max(start1, start2)).total_seconds()
            if seconds > 0:
                touched = True
                if side1 == side2:
                    same += seconds
                else:
                    opposite += seconds
        overlapping_trades += touched
    s2_hours = sum((b - a).total_seconds() for a, b, _ in s2_rows) / 3600
    s1_hours = sum((b - a).total_seconds() for a, b, _ in s1) / 3600
    both = (same + opposite) / 3600
    return {
        "s1_reference": {"commit": s1_report.get("provenance", {}).get("commit"), "trades": len(s1_trades)},
        "s2_hours_in_position": s2_hours,
        "s1_hours_in_position": s1_hours,
        "hours_both_in_position": both,
        "hours_same_direction": same / 3600,
        "hours_opposite_direction": opposite / 3600,
        "share_of_s2_time_overlapping_s1_pct": None if not s2_hours else both / s2_hours * 100,
        "s2_trades_overlapping_an_s1_trade": overlapping_trades,
        "s2_trades": len(s2_rows),
        "s1_net_by_year": {y: v["closed_trades"]["net_eur"] for y, v in s1_report["by_year"].items()},
    }


def report(
    result: S2Result, yearly: dict[int, TickDrawdown], gap_events: list[dict[str, Any]], s1: dict[str, Any] | None
) -> dict[str, Any]:
    trades = _all_trades(result)
    relative = result.relative_drawdown
    kinds = Counter(e.kind for e in result.journal)
    end = result.end_utc or datetime.now(UTC)
    indeterminate = [t for t in trades if t.indeterminate]
    return _json(
        {
            "trades": [_trade(t) for t in result.trades],
            "open_trade_at_end": _trade(result.open_trade) if result.open_trade else None,
            "balance_eur": result.balance,
            "equity_eur": result.equity,
            "closed_trade_totals": _trade_totals(result.trades),
            "concentration": concentration(result.trades),
            "risk_multiples": risk_multiples(result.trades),
            "tick_drawdown_eur": asdict(result.tick_drawdown) if result.tick_drawdown else None,
            "relative_drawdown": None
            if relative is None
            else {
                "max_pct": relative.max_ratio * 100,
                "max_utc": relative.max_utc,
                "peak_eur_at_end": relative.peak_eur,
                "first_review_crossing_6pct": relative.first_review_crossing,
            },
            "risk_overruns": [
                {"entry_utc": t.entry_utc, "measure": t.exposure_measure, "overrun_eur": t.risk_overrun}
                for t in trades
                if t.risk_overrun
            ],
            "funnel": breakout_funnel(result),
            "configurations": configurations(result),
            "indeterminate": {
                "trades": len(indeterminate),
                # An unexplained gap leaves the path unknown: both the stop and the target were possible.
                "gap_events": gap_events,
            },
            "journal_counts": dict(sorted(kinds.items())),
            "decisions": len(result.decisions),
            "end_utc": result.end_utc,
            "s1_overlap": None if s1 is None else overlap_with_s1(trades, s1, end),
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forex-s2-backtest", description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--init-start", type=_date, required=True)
    parser.add_argument("--start", type=_date, required=True)
    parser.add_argument("--end", type=_date, required=True)
    parser.add_argument("--trigger", choices=["H1", "H4"], required=True)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    parser.add_argument(
        "--stop-at-execution",
        choices=[s.name for s in StopAtExecution],
        default=StopAtExecution.FILL_THEN_LIQUIDATE.name,
    )
    parser.add_argument("--s1-reference", type=Path, help="rapport S1 de référence : chevauchement des positions")
    parser.add_argument("--out", type=Path, required=True, help="rapport JSON (hors Git, sous data/)")
    parser.add_argument("--decisions-out", type=Path, help="journal JSONL des décisions (hors Git, sous data/)")
    args = parser.parse_args(argv)
    if not args.init_start <= args.start < args.end:
        parser.error("dates attendues : init-start <= start < end")

    provenance = _provenance(argv, prog="forex-s2-backtest")  # at launch: the code the run starts from
    began = time.perf_counter()
    trigger = Timeframe.H1 if args.trigger == "H1" else Timeframe.H4
    params = S2Params(trigger=trigger)  # approved values (ASSUMP-025); only the trigger is chosen
    bars = {
        tf: load_bars(args.data_dir, SOURCE, INSTRUMENT, tf, args.init_start, args.end)
        for tf in (Timeframe.H1, Timeframe.H4, Timeframe.D1)
    }
    gaps = load_gaps(args.data_dir / "reports" / f"quality_{SOURCE}_{INSTRUMENT}.json", args.end)
    files = tick_files(HistoryStore(args.data_dir).tick_files(SOURCE, INSTRUMENT), args.start, args.end)
    config = ResearchConfig(
        costs=RESEARCH_COSTS,
        stop_type=StopType.GUARANTEED,
        stop_at_execution=StopAtExecution[args.stop_at_execution],
    )  # 2 000 EUR, 0.25 %, minimum and increment 0.1: the S1 reference defaults
    counted = 0

    def counting(ticks: Any) -> Any:
        nonlocal counted
        for tick in ticks:
            counted += 1
            yield tick

    engine = S2Run(
        bars[Timeframe.H1],
        bars[Timeframe.H4],
        bars[Timeframe.D1],
        counting(stream_ticks(files, args.start, args.end)),
        gaps,
        params,
        config,
        scenario=SCENARIOS[args.scenario],
        start_utc=args.start,
        end_utc=args.end,
    )
    result = engine.run()
    s1 = json.loads(args.s1_reference.read_text()) if args.s1_reference else None
    if args.decisions_out:
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
            "trigger": trigger.value,
            "scenario": SCENARIOS[args.scenario].value,
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
        | {"gaps": len(gaps), "tick_files": len(files), "ticks": counted},
        "result": report(result, engine.yearly_drawdown, engine.gap_events, s1),
        "by_year": by_year(result, engine.yearly_drawdown),
        "seconds": round(time.perf_counter() - began, 1),
        "peak_rss_mib": round(_peak_rss_mib(), 1),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(_str(full), ensure_ascii=False, indent=2, default=str))
    print(f"rapport écrit : {args.out} ({full['seconds']} s, {full['peak_rss_mib']} Mio)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
