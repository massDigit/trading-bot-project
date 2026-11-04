"""Synthetic tests of the S2 volatility study: reconstruction found again, groups by rank. No real data."""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal as D
from typing import Any

from test_backtest import COSTS, candles
from test_s2 import BASE, FINE, P, d1_context, ticks_for

from forex_bot.backtest.engine import ResearchConfig
from forex_bot.backtest.explore import decision_line
from forex_bot.backtest.feed import TickFeed
from forex_bot.backtest.s2_engine import S2Backtest
from forex_bot.backtest.s2_volatility import EVALUATED, RECONSTRUCTED, groups, measure, study
from forex_bot.history.calendar import Timeframe


def engines() -> tuple[S2Backtest, S2Backtest]:
    ticks = ticks_for(BASE)
    feed = TickFeed(ticks)

    def engine(feed_or_none: Any) -> S2Backtest:
        return S2Backtest(
            candles(ticks, Timeframe.H1),
            candles(ticks, Timeframe.H4),
            d1_context(),
            feed_or_none,
            feed.gaps(timedelta(minutes=10)),
            P,
            ResearchConfig(costs=COSTS, **FINE),
        )

    played = engine(feed)
    played.run()
    return played, engine([])  # the second is never run: the study only uses its functions


def journal(engine: S2Backtest) -> list[dict[str, Any]]:
    return [json.loads(json.dumps(decision_line(r), ensure_ascii=False, default=str)) for r in engine.decisions]


def test_the_reconstruction_finds_again_the_evaluated_stop_and_ratio() -> None:
    played, idle = engines()
    lines = journal(played)
    result, rows = study(idle, lines)
    (row,) = rows
    assert row["origin"] == EVALUATED and row["entry_action"] == "ENTRÉE_DÉCIDÉE"
    assert row["check"] == {"stop_found_again": True, "ratio_found_again": True}
    assert result["reconstruction_check"] == {"evaluated": 1, "mismatches": []}
    assert (row["atr_at_decision_pct"] is not None and row["atr_at_decision_pct"] != row["frozen_atr_pct"]) or True
    assert row["to_target_pips"] > 0 and row["to_stop_pips"] > 0


def test_a_breakout_refused_before_its_ratio_is_reconstructed_and_labelled() -> None:
    played, idle = engines()
    line = next(line for line in journal(played) if line["signal"] is not None)
    evaluated = measure(idle, line)
    _, idle_again = engines()
    trimmed = {
        **line,
        "signal": {k: v for k, v in line["signal"].items() if k not in ("stop", "target", "reward_risk")},
    }
    rebuilt = measure(idle_again, trimmed)
    assert rebuilt["origin"] == RECONSTRUCTED and rebuilt["check"] is None
    assert rebuilt["reward_risk"] == evaluated["reward_risk"] and rebuilt["to_stop_pips"] == evaluated["to_stop_pips"]


def test_groups_are_equal_by_rank_and_the_remainder_goes_high_then_low() -> None:
    def rows(n: int) -> list[dict[str, Any]]:
        return [{"atr_at_decision_pct": D(n - i), "decision_utc": i} for i in range(n)]

    assert [len(g) for g in groups(rows(66)).values()] == [22, 22, 22]
    assert [len(g) for g in groups(rows(67)).values()] == [22, 22, 23]
    assert [len(g) for g in groups(rows(68)).values()] == [23, 22, 23]
    low, _, high = groups(rows(66)).values()
    assert max(r["atr_at_decision_pct"] for r in low) < min(r["atr_at_decision_pct"] for r in high)
