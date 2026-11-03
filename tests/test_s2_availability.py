"""Synthetic tests of the S2 data availability study (step 3). No real data, no tick replay."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from test_backtest import COSTS, candles
from test_s2 import BASE, BREAK, CONTACT, PRE, RECOVERY, START, P, Spec, d1_context, flat, ticks_for

from forex_bot.backtest.engine import ResearchConfig
from forex_bot.backtest.feed import TickFeed
from forex_bot.backtest.s2_availability import availability
from forex_bot.history.calendar import Timeframe


def study(specs: Sequence[Spec | None], degrade: int | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ticks = ticks_for(specs)
    h1 = candles(ticks, Timeframe.H1)
    if degrade is not None:
        h1[degrade] = {**h1[degrade], "complete_at_close": False, "flags_at_close": ["trou de cotation"]}
    gaps = TickFeed(ticks).gaps(timedelta(minutes=10))
    end = START + timedelta(hours=len(specs), minutes=1)  # the last decision, at the end of the last H1, included
    return availability(
        h1, candles(ticks, Timeframe.H4), d1_context(), gaps, ResearchConfig(costs=COSTS), START, end, P
    )


def test_slots_come_from_the_calendar_and_partition_into_four_classes() -> None:
    summary, _ = study(BASE)
    slots = summary["total"]["h1_slots"]
    assert slots["expected"] == len(BASE)  # Monday-Tuesday 2019-03-11/12: every hour expected open
    assert slots["absent"] == 0 and slots["present_not_evaluable"] == 0
    assert slots["evaluable_breakout"] == 1
    assert slots["evaluable_no_signal"] == len(BASE) - 1
    assert summary["decision_lines"] == len(BASE)


def test_an_absent_h1_has_no_decision_line_but_counts_as_an_expected_slot() -> None:
    specs = [*flat("1.1000", 3), None, *flat("1.1000", 3)]
    summary, details = study(specs)
    slots = summary["total"]["h1_slots"]
    assert slots["expected"] == 7 and slots["absent"] == 1
    assert summary["decision_lines"] == 6
    assert slots["absent"] + slots["present_not_evaluable"] + slots["evaluable_no_signal"] == 7
    assert [row["slot_start_utc"] for row in details if row["kind"] == "créneau H1 absent"] == [
        START + timedelta(hours=3)
    ]


def test_a_degraded_h1_is_present_but_not_evaluable_with_its_state() -> None:
    summary, _ = study(flat("1.1000", 5), degrade=2)
    slots = summary["total"]["h1_slots"]
    assert slots["expected"] == 5 and slots["absent"] == 0
    assert slots["present_not_evaluable"] == 1 and slots["evaluable_no_signal"] == 4
    assert slots["not_evaluable_causes"] == {"bougie de déclenchement INTERRUPTION_INEXPLIQUÉE": 1}


def test_configurations_abandoned_for_incomplete_data_are_counted_apart_from_the_slots() -> None:
    specs = [*PRE, CONTACT, RECOVERY, None, BREAK, *flat("1.1098", 3)]
    summary, details = study(specs)
    total = summary["total"]
    configurations = total["configurations"]
    assert configurations["identified"] == 1 and configurations["abandoned_incomplete_data"] == 1
    assert configurations["abandoned_incomplete_data_by_cause"] == {"créneau attendu absent (H1 ou H4)": 1}
    assert configurations["pct_of_identified"] == "100.000"
    slots = total["h1_slots"]
    assert slots["expected"] == len(specs) and slots["absent"] == 1
    # The abandonment makes its own decision line not computable; the slot is counted once.
    assert slots["not_evaluable_causes"] == {"configuration abandonnée : DONNÉES_REPLI_INCOMPLÈTES": 1}
    assert slots["absent"] + slots["present_not_evaluable"] + slots["evaluable_no_signal"] + slots[
        "evaluable_breakout"
    ] == len(specs)
    assert sum(1 for row in details if row["kind"] == "configuration abandonnée") == 1
