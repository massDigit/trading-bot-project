"""Synthetic tests of the S2 data availability study (step 3). No real data, no tick replay."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from test_backtest import COSTS, candles
from test_s2 import BASE, BREAK, CONFIRM, CONTACT, PRE, RECOVERY, START, P, Spec, at, d1_context, flat, h1, ticks_for

from forex_bot.backtest.engine import EntryAction, ResearchConfig
from forex_bot.backtest.feed import TickFeed
from forex_bot.backtest.s2_availability import CONSUMED, AvailabilityBacktest, availability
from forex_bot.history.calendar import MarketState, Timeframe, market_state


def engine_for(specs: Sequence[Spec | None]) -> AvailabilityBacktest:
    ticks = ticks_for(specs)
    gaps = TickFeed(ticks).gaps(timedelta(minutes=10))
    end = START + timedelta(hours=len(specs), minutes=1)
    engine = AvailabilityBacktest(
        candles(ticks, Timeframe.H1),
        candles(ticks, Timeframe.H4),
        d1_context(),
        [],
        gaps,
        P,
        ResearchConfig(costs=COSTS),
        start_utc=START,
        end_utc=end,
    )
    engine.run()
    return engine


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


# Two occasions from the same configuration: the engine of performance refuses the first breakout
# (target too close) and enters on the second; the study consumes the configuration at the first.
TWO_OCCASIONS: list[Spec] = [
    *PRE,
    CONTACT,
    h1("1.1072", "1.1180", "1.1068", "1.1170"),  # recovery pivot 1.1180
    h1("1.1170", "1.1175", "1.1150", "1.1160"),  # confirms it
    h1("1.1160", "1.1195", "1.1158", "1.1190"),  # breakout 1, at(4)
    h1("1.1190", "1.1192", "1.1100", "1.1105"),
    h1("1.1105", "1.1188", "1.1102", "1.1185"),
    h1("1.1185", "1.1186", "1.1100", "1.1105"),
    h1("1.1105", "1.1106", "1.1060", "1.1065"),
    h1("1.1065", "1.1110", "1.1062", "1.1090"),  # new recovery pivot 1.1110
    h1("1.1090", "1.1095", "1.1075", "1.1080"),  # confirms it
    h1("1.1080", "1.1115", "1.1078", "1.1112"),  # breakout 2 in the engine of performance, at(11)
    *flat("1.1112", 2),
]


def test_a_consumed_configuration_gives_no_second_breakout() -> None:
    engine = engine_for(TWO_OCCASIONS)
    (setup,) = engine.setups
    first = next(r for r in engine.decisions if r.decision_utc == at(4))
    assert first.signal is not None and first.reasons == [CONSUMED]
    assert setup.used and engine.setup is None and engine.consumed == [(setup.identified_utc, at(4))]
    second = next(r for r in engine.decisions if r.decision_utc == at(11))
    assert second.signal is None and second.entry_action is EntryAction.NO_SIGNAL
    summary, _ = study(TWO_OCCASIONS)
    assert summary["total"]["h1_slots"]["evaluable_breakout"] == 1
    assert summary["total"]["configurations"]["consumed_by_convention"] == 1
    assert not engine.kept and not first.signal.keys() & {"stop", "reward_risk"}  # no ratio computed


def test_a_structural_refusal_consumes_the_threshold_only() -> None:
    # The breakout closes the last H1 before the weekly closure: decision Friday 17:00 New York.
    filler = 119 - len(PRE) - 3
    specs = [*PRE, CONTACT, RECOVERY, CONFIRM, *flat("1.1075", filler), BREAK]
    decision = START + timedelta(hours=len(specs))
    assert market_state(decision) is MarketState.WEEKLY_CLOSURE
    engine = engine_for(specs)
    (setup,) = engine.setups
    line = engine.decisions[-1]
    assert line.decision_utc == decision and line.signal is not None
    assert line.entry_action is EntryAction.SIGNAL_REFUSED
    assert line.reasons == ["LONG : marché fermé à l'instant de décision"]
    assert engine.setup is setup and not setup.used and setup.refused_utc == decision  # threshold consumed
    assert engine.kept == [(setup.identified_utc, decision, "LONG : marché fermé à l'instant de décision")]
    summary, _ = study(specs)
    configurations = summary["total"]["configurations"]
    assert summary["total"]["h1_slots"]["evaluable_breakout"] == 1
    assert configurations["consumed_by_convention"] == 0
    assert configurations["kept_after_structural_refusal"] == {"marché fermé à l'instant de décision": 1}
