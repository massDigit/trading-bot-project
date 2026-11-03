"""Exploratory S1 run on a bounded window of the local history (ADR-009). No order, no network.

    uv run forex-backtest-explore --init-start 2019-01-01 --start 2019-04-01 --end 2019-07-01

Candles from --init-start only initialise the indicators; decisions and ticks are limited to
[--start, --end). The window must lie in 2015-2021. S1 parameters are the fixed reference
(ASSUMP-020); costs are the explicit research scenario below, never confirmed IG values.
`--decisions-out` writes one JSON line per H4 decision of the study, with only what was known at
the decision and what was decided; executions and later results go to `outcomes_after_decision`
in the report, never into those lines. `--reference` compares the trades with an earlier report.
The report also gives a breakdown per calendar year (UTC): entries by entry date, closed trades
by exit date, decisions and abstention reasons by decision date, and the maximum drawdown
observable at the tick within each year, from the equity at the start of that year.
`--compare` first runs the in-memory reference reader and checks that the streaming reader
gives identical trades, costs, journal and equity (memory figures are then not representative).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from forex_bot.backtest.data import load_bars, load_gaps, load_ticks, stream_ticks, tick_files
from forex_bot.backtest.engine import (
    BacktestResult,
    DecisionRecord,
    EntryAction,
    PositionAction,
    ResearchConfig,
    S1Backtest,
    ScenarioPolicy,
    StopAtExecution,
    StopType,
    TickDrawdown,
)
from forex_bot.backtest.feed import Tick
from forex_bot.backtest.s1 import S1Params
from forex_bot.history.calendar import Timeframe
from forex_bot.history.store import HistoryStore
from forex_bot.risk import Cost, CostModel, CostStatus

SOURCE, INSTRUMENT = "dukascopy", "EURUSD"
SCENARIO = "scénario de recherche du 2026-11-03, non confirmé chez IG"

# Research cost scenario: every amount is ASSUMED, none is an IG value (ASSUMP-006).
RESEARCH_COSTS = CostModel(
    slippage_pips=Cost(CostStatus.ASSUMED, Decimal("0.5"), "ASSUMP-006, scénario expérimental"),
    commission_per_contract=Cost(CostStatus.ASSUMED, Decimal("0"), f"aucune commission supposée ; {SCENARIO}"),
    financing_per_contract_per_night=Cost(
        CostStatus.ASSUMED, Decimal("1.00"), f"1 USD par contrat Mini et par nuit ; {SCENARIO}"
    ),
    conversion_fee_rate=Cost(CostStatus.ASSUMED, Decimal("0.005"), f"0,5 % du résultat converti ; {SCENARIO}"),
    guaranteed_stop_premium_per_contract=Cost(
        CostStatus.ASSUMED, Decimal("1.2"), f"1,2 USD par contrat (1,2 « POINTS » observés en démo) ; {SCENARIO}"
    ),
)


def _date(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def _json(value: dict[str, Any]) -> dict[str, Any]:
    converted: dict[str, Any] = _str(value)
    return converted


def _str(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _str(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_str(v) for v in value]
    return value


def _trade(trade: Any) -> dict[str, Any]:
    fields = asdict(trade)
    fields.pop("estimate")
    return _json(
        {
            **fields,
            "estimated_stop_loss_at_decision": trade.size * trade.estimate.loss_account_per_contract,
            "exposure": trade.exposure,
            "exposure_measure": trade.exposure_measure,
            "risk_overrun": trade.risk_overrun,
            "simulated_loss": trade.simulated_loss,
            "indeterminate": trade.indeterminate,
        }
    )


def summarize(result: BacktestResult) -> dict[str, Any]:
    kinds = Counter(e.kind for e in result.journal)
    reasons = Counter(e.detail for e in result.journal if e.kind == "ABSTENTION")
    curve = result.equity_curve
    peak, drawdown = Decimal("-Infinity"), Decimal(0)
    for point in curve:
        peak = max(peak, point.equity)
        drawdown = max(drawdown, peak - point.equity)
    trades = [*result.trades, *([result.open_trade] if result.open_trade else [])]
    return _json(
        {
            "journal_counts": dict(sorted(kinds.items())),
            "abstention_reasons": dict(reasons.most_common()),
            "stop_beyond_at_execution": kinds["STOP_DÉPASSÉ_À_L'EXÉCUTION"],
            "risk_overruns": [
                {"entry_utc": t.entry_utc, "measure": t.exposure_measure, "overrun_eur": t.risk_overrun}
                for t in trades
                if t.risk_overrun
            ],
            "trades": [_trade(t) for t in result.trades],
            "open_trade_at_end": _trade(result.open_trade) if result.open_trade else None,
            "balance_eur": result.balance,
            "unrealized_eur": result.unrealized,
            "equity_eur": result.equity,
            "equity_min_eur": min((p.equity for p in curve), default=None),
            "max_drawdown_on_samples_eur": drawdown,
            "closed_trade_totals": _trade_totals(result.trades),
            "entries": {
                "buys": sum(1 for t in trades if t.side.value == "LONG"),
                "sells": sum(1 for t in trades if t.side.value == "SHORT"),
            },
            "unobservable_crossings_h0": kinds["SCÉNARIO_H0"],
            "first_fully_usable_decision": first_fully_usable_decision(result),
            "tick_drawdown": asdict(result.tick_drawdown) if result.tick_drawdown else None,
            "decisions": {
                "count": len(result.decisions),
                "by_action": dict(
                    sorted(Counter(f"{r.position_action} / {r.entry_action}" for r in result.decisions).items())
                ),
            },
            "equity_points": len(curve),
            "end_utc": result.end_utc,
        }
    )


class YearlyBacktest(S1Backtest):
    """The verified engine, plus a tick-level drawdown per calendar year (observation only)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.yearly_drawdown: dict[int, TickDrawdown] = {}
        self._equity_before = self.config.initial_equity

    def _observe(self, tick: Tick) -> None:
        equity = self.balance + self._unrealized(tick)  # computed once per tick for both measures
        self.drawdown.observe(tick.ts_utc, equity)
        year = tick.ts_utc.year
        if year not in self.yearly_drawdown:  # each year starts from the equity at its first tick
            self.yearly_drawdown[year] = TickDrawdown(self._equity_before, None)
        self.yearly_drawdown[year].observe(tick.ts_utc, equity)
        self._equity_before = equity


def _gross_and_costs(trade: Any) -> tuple[Decimal, Decimal]:
    """EUR price result and EUR costs of a closed trade (net = gross - costs)."""
    gross = trade.price_pnl_quote * trade.conversion_rate
    costs = sum(trade.costs_quote.values(), Decimal(0)) * trade.conversion_rate + trade.conversion_fee
    return gross, costs


def _trade_totals(trades: list[Any]) -> dict[str, Any]:
    totals: dict[str, Any] = {
        "closed": len(trades),
        "winners": sum(1 for t in trades if t.net_account > 0),
        "losers": sum(1 for t in trades if t.net_account <= 0),
        "gross_eur": Decimal(0),
        "costs_eur": Decimal(0),
        "net_eur": Decimal(0),
        "exit_reasons": dict(sorted(Counter(t.exit_reason for t in trades).items())),
        "cost_lines_usd": {},
        "conversion_fees_eur": sum((t.conversion_fee for t in trades), Decimal(0)),
    }
    for trade in trades:
        gross, costs = _gross_and_costs(trade)
        totals["gross_eur"] += gross
        totals["costs_eur"] += costs
        totals["net_eur"] += trade.net_account
        for name, amount in trade.costs_quote.items():
            totals["cost_lines_usd"][name] = totals["cost_lines_usd"].get(name, Decimal(0)) + amount
    return totals


def _abstentions(records: list[DecisionRecord]) -> dict[str, int]:
    reasons: Counter[str] = Counter()
    for record in records:
        if record.entry_action in (EntryAction.SIGNAL_REFUSED, EntryAction.NOT_COMPUTABLE) or (
            record.position_action is PositionAction.HELD_EXIT_NOT_COMPUTABLE
        ):
            reasons.update(f"{record.entry_action} : {reason}" for reason in record.reasons)
    return dict(reasons.most_common())


def first_fully_usable_decision(result: BacktestResult) -> datetime | None:
    """First decision at which channels, ATR and the D1 context channel were all computable."""
    for record in result.decisions:
        known = record.known
        d1 = known["d1_context"]
        if (
            known["entry_channel"]
            and known["exit_channel"]
            and known["atr"] is not None
            and d1
            and d1["channel_middle"] is not None
        ):
            return record.decision_utc
    return None


def by_year(result: BacktestResult, yearly_drawdown: dict[int, TickDrawdown]) -> dict[int, dict[str, Any]]:
    trades = [*result.trades, *([result.open_trade] if result.open_trade else [])]
    years = sorted({r.decision_utc.year for r in result.decisions} | set(yearly_drawdown))
    report = {}
    for year in years:
        records = [r for r in result.decisions if r.decision_utc.year == year]
        entered = [t for t in trades if t.entry_utc.year == year]
        closed = [t for t in result.trades if t.exit_utc is not None and t.exit_utc.year == year]
        points = [p for p in result.equity_curve if p.utc.year == year]
        journal = Counter(e.kind for e in result.journal if e.utc.year == year)
        report[year] = _json(
            {
                "decisions": len(records),
                "by_action": dict(sorted(Counter(f"{r.position_action} / {r.entry_action}" for r in records).items())),
                "breakouts": sum(
                    1 for r in records if r.entry_action in (EntryAction.ENTRY_DECIDED, EntryAction.SIGNAL_REFUSED)
                ),
                "entries": {
                    "buys": sum(1 for t in entered if t.side.value == "LONG"),
                    "sells": sum(1 for t in entered if t.side.value == "SHORT"),
                },
                "closed_trades": _trade_totals(closed),
                "risk_overruns": sum(1 for t in entered if t.risk_overrun),
                "stop_beyond_at_execution": journal["STOP_DÉPASSÉ_À_L'EXÉCUTION"],
                "unobservable_crossings_h0": journal["SCÉNARIO_H0"],
                "abstention_reasons": _abstentions(records),
                "tick_drawdown": asdict(yearly_drawdown[year]) if year in yearly_drawdown else None,
                "year_end": None
                if not points
                else {"balance": points[-1].balance, "unrealized": points[-1].unrealized, "equity": points[-1].equity},
            }
        )
    return report


def decision_line(record: DecisionRecord) -> dict[str, Any]:
    """Decision-time information only (future model input): never an execution price or a result."""
    return _json(
        {
            "decision_utc": record.decision_utc,
            "known": record.known,
            "position_action": record.position_action.value,
            "entry_action": record.entry_action.value,
            "reasons": record.reasons,
            "signal": record.signal,
            "order": record.order,
        }
    )


def outcomes_after_decision(result: BacktestResult) -> list[dict[str, Any]]:
    """Executions and results linked to the decision that caused them, kept apart from the decision lines."""
    trades = [*result.trades, *([result.open_trade] if result.open_trade else [])]
    by_entry_decision = {t.decided_utc: t for t in trades}
    by_entry_time = {t.entry_utc: t for t in trades}
    lines = []
    for record in result.decisions:
        line: dict[str, Any] = {"decision_utc": record.decision_utc}
        if record.position_action is PositionAction.EXIT_DECIDED and record.known["position"]:
            exited = by_entry_time[record.known["position"]["entry_utc"]]
            line["exit"] = {"utc": exited.exit_utc, "price": exited.exit_price, "reason": exited.exit_reason}
        if record.entry_action is EntryAction.ENTRY_DECIDED:
            opened = by_entry_decision.get(record.decision_utc)
            line["entry"] = (
                None  # e.g. rejected at execution (see the journal)
                if opened is None
                else {
                    "utc": opened.entry_utc,
                    "price": opened.entry_price,
                    "exposure": opened.exposure,
                    "exposure_measure": opened.exposure_measure,
                    "risk_overrun": opened.risk_overrun,
                    "exit_utc": opened.exit_utc,
                    "exit_reason": opened.exit_reason,
                    "net_account": opened.net_account,
                }
            )
        if len(line) > 1:
            lines.append(_json(line))
    return lines


def compare_with_reference(summary: dict[str, Any], reference: dict[str, Any]) -> list[str]:
    """Trades and their exact amounts must not change when only observation is added."""
    keys = ("trades", "open_trade_at_end", "balance_eur", "journal_counts")
    return [key for key in keys if summary.get(key) != reference["result"].get(key)]


def _identical(a: BacktestResult, b: BacktestResult) -> list[str]:
    checks = {
        "transactions": a.trades == b.trades,
        "position ouverte": a.open_trade == b.open_trade,
        "journal": a.journal == b.journal,
        "fonds propres": a.equity_curve == b.equity_curve,
        "fin": a.end_utc == b.end_utc,
    }
    return [name for name, same in checks.items() if not same]


def _provenance(argv: list[str] | None) -> dict[str, Any]:
    """Commit and state of the working tree the run used, and its command line."""

    executable = shutil.which("git")

    def git(*command: str) -> str:
        if executable is None:
            return ""
        # Fixed read-only git arguments, no user input.
        done = subprocess.run([executable, *command], capture_output=True, text=True, check=False)  # noqa: S603
        return done.stdout.strip()

    diff = git("diff", "HEAD")
    return {
        "commit": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "uncommitted_diff_sha256": hashlib.sha256(diff.encode()).hexdigest() if diff else None,
        "uncommitted_files": git("diff", "HEAD", "--name-only").splitlines(),
        "command": ["forex-backtest-explore", *(sys.argv[1:] if argv is None else argv)],
    }


def _peak_rss_mib() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 2**20 if sys.platform == "darwin" else peak / 2**10  # bytes on macOS, KiB on Linux


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forex-backtest-explore", description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--init-start", type=_date, required=True)
    parser.add_argument("--start", type=_date, required=True)
    parser.add_argument("--end", type=_date, required=True)
    parser.add_argument("--stop-type", choices=[s.name for s in StopType], default=StopType.GUARANTEED.name)
    parser.add_argument(
        "--policy", choices=[p.name for p in ScenarioPolicy], default=ScenarioPolicy.NONE_TRIGGERED.name
    )
    parser.add_argument(
        "--stop-at-execution",
        choices=[s.name for s in StopAtExecution],
        default=StopAtExecution.FILL_THEN_LIQUIDATE.name,
    )
    parser.add_argument(
        "--min-size", type=Decimal, default=ResearchConfig.min_size, help="taille minimale (scénario de recherche)"
    )
    parser.add_argument(
        "--size-increment", type=Decimal, default=ResearchConfig.size_increment, help="incrément de taille (scénario)"
    )
    parser.add_argument(
        "--risk-fraction",
        type=Decimal,
        default=ResearchConfig.risk_fraction,
        help="fraction des fonds propres risquée par opération (scénario de recherche)",
    )
    parser.add_argument("--compare", action="store_true", help="vérifier d'abord l'égalité mémoire / flux")
    parser.add_argument("--out", type=Path, help="fichier JSON du résultat (hors Git, sous data/)")
    parser.add_argument("--decisions-out", type=Path, help="journal JSONL des décisions H4 (hors Git, sous data/)")
    parser.add_argument("--reference", type=Path, help="rapport JSON antérieur : transactions attendues identiques")
    args = parser.parse_args(argv)
    if not args.init_start <= args.start < args.end:
        parser.error("dates attendues : init-start <= start < end")

    provenance = _provenance(argv)  # at launch: the code and tree the run actually starts from
    began = time.perf_counter()
    h4 = load_bars(args.data_dir, SOURCE, INSTRUMENT, Timeframe.H4, args.init_start, args.end)
    d1 = load_bars(args.data_dir, SOURCE, INSTRUMENT, Timeframe.D1, args.init_start, args.end)
    gaps = load_gaps(args.data_dir / "reports" / f"quality_{SOURCE}_{INSTRUMENT}.json", args.end)
    files = tick_files(HistoryStore(args.data_dir).tick_files(SOURCE, INSTRUMENT), args.start, args.end)
    config = ResearchConfig(
        costs=RESEARCH_COSTS,
        stop_type=StopType[args.stop_type],
        policy=ScenarioPolicy[args.policy],
        stop_at_execution=StopAtExecution[args.stop_at_execution],
        min_size=args.min_size,
        size_increment=args.size_increment,
        risk_fraction=args.risk_fraction,
    )
    params = S1Params()  # fixed reference (ASSUMP-020): N 20, M 10, ATR 14, k 2, D1 filter 55 days

    yearly: dict[int, TickDrawdown] = {}

    def run(ticks: Any) -> BacktestResult:
        engine = YearlyBacktest(h4, d1, ticks, gaps, params, config, start_utc=args.start, end_utc=args.end)
        result = engine.run()
        yearly.clear()
        yearly.update(engine.yearly_drawdown)
        return result

    comparison: dict[str, Any] | None = None
    if args.compare:
        reference = run(load_ticks(files, args.start, args.end))
        differences = _identical(reference, run(stream_ticks(files, args.start, args.end)))
        comparison = {"identical": not differences, "differences": differences}
        if differences:
            print(json.dumps(comparison, ensure_ascii=False, indent=2))
            return 1

    counted = 0

    def counting(ticks: Any) -> Any:
        nonlocal counted
        tick: Tick
        for tick in ticks:
            counted += 1
            yield tick

    run_began = time.perf_counter()
    result = run(counting(stream_ticks(files, args.start, args.end)))
    elapsed = time.perf_counter() - run_began
    summary = summarize(result)
    reference_differences: list[str] | None = None
    if args.reference:
        reference_differences = compare_with_reference(summary, json.loads(args.reference.read_text()))
    if args.decisions_out:
        args.decisions_out.parent.mkdir(parents=True, exist_ok=True)
        with args.decisions_out.open("w") as out:
            for record in result.decisions:
                out.write(json.dumps(decision_line(record), ensure_ascii=False) + "\n")
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "notice": "passage hors ligne : ni validation de performance ni autorisation de trading",
        "provenance": provenance,
        "window": {"init_start": args.init_start, "start": args.start, "end": args.end},
        "config": {
            "stop_type": config.stop_type.value,
            "policy": config.policy.value,
            "stop_at_execution": config.stop_at_execution.value,
            "params": asdict(params),
            "costs": {name: asdict(cost) for name, cost in vars(RESEARCH_COSTS).items()},
            "initial_equity": config.initial_equity,
            "risk_fraction": config.risk_fraction,
            "min_size": config.min_size,
            "size_increment": config.size_increment,
        },
        "inputs": {"h4": len(h4), "d1": len(d1), "gaps": len(gaps), "tick_files": len(files), "ticks": counted},
        "reader_comparison": comparison,
        "result": summary,
        "expected_decisions": sum(1 for b in h4 if args.start <= b["end_utc"] + config.latency < args.end),
        "reference_differences": reference_differences,
        "by_year": by_year(result, yearly),
        "outcomes_after_decision": outcomes_after_decision(result),
        "streaming_run_seconds": round(elapsed, 1),
        "total_seconds": round(time.perf_counter() - began, 1),
        "peak_rss_mib": round(_peak_rss_mib(), 1),
    }
    text = json.dumps(_str(report), ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"rapport écrit : {args.out} ({report['streaming_run_seconds']} s, {report['peak_rss_mib']} Mio)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
