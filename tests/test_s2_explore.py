"""Synthetic tests of the S2 run report (step 4): funnel, overlap with S1. No real data."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal as D
from typing import Any

from test_backtest import COSTS, candles
from test_s2 import BASE, FINE, START, P, at, d1_context, ticks_for

from forex_bot.backtest.engine import ResearchConfig
from forex_bot.backtest.feed import TickFeed
from forex_bot.backtest.s2_explore import S2Run, overlap_with_s1, report
from forex_bot.history.calendar import Timeframe


def run_base() -> tuple[S2Run, Any]:
    ticks = ticks_for(BASE)
    feed = TickFeed(ticks)
    engine = S2Run(
        candles(ticks, Timeframe.H1),
        candles(ticks, Timeframe.H4),
        d1_context(),
        feed,
        feed.gaps(timedelta(minutes=10)),
        P,
        ResearchConfig(costs=COSTS, **FINE),
    )
    return engine, engine.run()


def test_the_funnel_goes_from_breakouts_to_positions_actually_opened() -> None:
    engine, result = run_base()
    summary = report(result, engine.yearly_drawdown, engine.gap_events, None)
    funnel = summary["funnel"]
    assert funnel["breakouts_detected"] == 1 and funnel["entries_decided"] == 1
    assert funnel["not_entered"] == {}
    assert funnel["after_decision"] == {"position effectivement ouverte": 1}
    assert summary["closed_trade_totals"]["exit_reasons"] == {"CIBLE": 1}
    assert summary["configurations"] == {"created": 1, "with_a_breakout": 1, "fates": {"entrée décidée": 1}}
    assert D(summary["concentration"]["net_without_best_eur"]) == 0
    assert summary["indeterminate"]["trades"] == 0
    assert set(engine.yearly_drawdown) == {2019}


def test_overlap_with_s1_counts_same_and_opposite_direction_hours() -> None:
    _, result = run_base()
    (trade,) = result.trades
    assert trade.exit_utc is not None
    s1 = {
        "provenance": {"commit": "x"},
        "result": {
            "trades": [
                {
                    "entry_utc": (trade.entry_utc - timedelta(hours=1)).isoformat(),
                    "exit_utc": trade.exit_utc.isoformat(),
                    "side": "LONG",
                },
                {"entry_utc": at(100).isoformat(), "exit_utc": at(101).isoformat(), "side": "SHORT"},
            ],
            "open_trade_at_end": None,
        },
        "by_year": {"2019": {"closed_trades": {"net_eur": "1"}}},
    }
    overlap = overlap_with_s1(result.trades, s1, START + timedelta(days=30))
    held = (trade.exit_utc - trade.entry_utc).total_seconds() / 3600
    assert overlap["hours_same_direction"] == held and overlap["hours_opposite_direction"] == 0
    assert overlap["share_of_s2_time_overlapping_s1_pct"] == 100
    assert overlap["s2_trades_overlapping_an_s1_trade"] == 1 and overlap["s1_reference"]["trades"] == 2
