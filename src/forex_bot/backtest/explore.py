"""Exploratory S1 run on a bounded window of the local history (ADR-009). No order, no network.

    uv run forex-backtest-explore --init-start 2019-01-01 --start 2019-04-01 --end 2019-07-01

Candles from --init-start only initialise the indicators; decisions and ticks are limited to
[--start, --end). The window must lie in 2015-2021. S1 parameters are the fixed reference
(ASSUMP-020); costs are the explicit research scenario below, never confirmed IG values.
`--compare` first runs the in-memory reference reader and checks that the streaming reader
gives identical trades, costs, journal and equity (memory figures are then not representative).
"""

from __future__ import annotations

import argparse
import json
import resource
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
    ResearchConfig,
    S1Backtest,
    ScenarioPolicy,
    StopAtExecution,
    StopType,
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
            "equity_points": len(curve),
            "end_utc": result.end_utc,
        }
    )


def _identical(a: BacktestResult, b: BacktestResult) -> list[str]:
    checks = {
        "transactions": a.trades == b.trades,
        "position ouverte": a.open_trade == b.open_trade,
        "journal": a.journal == b.journal,
        "fonds propres": a.equity_curve == b.equity_curve,
        "fin": a.end_utc == b.end_utc,
    }
    return [name for name, same in checks.items() if not same]


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
    parser.add_argument("--compare", action="store_true", help="vérifier d'abord l'égalité mémoire / flux")
    parser.add_argument("--out", type=Path, help="fichier JSON du résultat (hors Git, sous data/)")
    args = parser.parse_args(argv)
    if not args.init_start <= args.start < args.end:
        parser.error("dates attendues : init-start <= start < end")

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
    )
    params = S1Params()  # fixed reference (ASSUMP-020): N 20, M 10, ATR 14, k 2, D1 filter 55 days

    def run(ticks: Any) -> BacktestResult:
        return S1Backtest(h4, d1, ticks, gaps, params, config, start_utc=args.start, end_utc=args.end).run()

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
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "notice": "passage exploratoire hors ligne : ni validation de performance ni autorisation de trading",
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
        "result": summarize(result),
        "streaming_run_seconds": round(elapsed, 1),
        "total_seconds": round(time.perf_counter() - began, 1),
        "peak_rss_mib": round(_peak_rss_mib(), 1),
    }
    text = json.dumps(_str(report), ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
