"""Synthetic tests of the S3 data availability study (step 3). No real data, no tick replay."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal as D
from typing import Any

from test_backtest import candles
from test_s3 import ALL_SLOTS, SUITE_1, Spec, X, at, d1_context, scenario, spec, ticks_for

from forex_bot.backtest.engine import ResearchConfig
from forex_bot.backtest.explore import RESEARCH_COSTS
from forex_bot.backtest.feed import TickFeed
from forex_bot.backtest.s3 import S3Params
from forex_bot.backtest.s3_availability import availability, expected_h4_slots
from forex_bot.history.calendar import Timeframe, candle_end

BANDS_BROKEN = "interruption : H4 inutilisable parmi les 20 H4 des bandes"
INSIDE_BOX = [spec("1.1345", "1.1346", "1.1344", "1.1345")] * 40


def study(
    specs: Sequence[Spec | None],
    *,
    start: datetime,
    degrade: Sequence[int] = (),
    params: S3Params | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """`specs` from the history start; `degrade`: offsets from X whose H4 is flagged (X-20 always)."""
    starts = ALL_SLOTS[: len(specs)]
    ticks = ticks_for(specs, starts)
    h4 = candles(ticks, Timeframe.H4)
    by_start = {b["start_utc"]: i for i, b in enumerate(h4)}
    x = ALL_SLOTS.index(X)
    for k in [-20, *degrade]:
        i = by_start[ALL_SLOTS[x + k]]
        h4[i] = {**h4[i], "complete_at_close": False, "flags_at_close": ["trou de cotation"]}
    end = candle_end(starts[-1], Timeframe.H4) + timedelta(minutes=1)
    gaps = TickFeed(ticks).gaps(timedelta(minutes=10))
    return availability(h4, d1_context(), gaps, ResearchConfig(costs=RESEARCH_COSTS), start, end, params)


def example(after: Sequence[Spec | None] = SUITE_1, **kwargs: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    specs, _ = scenario(after)
    return study(specs, start=at(-20), **kwargs)


def test_expected_slots_partition_and_the_example_box_is_consumed_by_its_breakout() -> None:
    summary, _ = example()
    total = summary["total"]
    slots = total["h4_slots"]
    assert slots["expected"] == 20 + 6 + 3 + len(SUITE_1)  # X-20 .. the last H4 of the suite
    assert slots["absent"] == 0
    assert slots["present_computable"] + slots["present_not_computable"] == slots["expected"]
    causes = slots["not_computable_causes"]
    assert causes.pop(BANDS_BROKEN) == 19  # X-19 .. X-1: the degraded X-20 is in their 20 closes
    (own,) = causes  # X-20 itself
    assert own.startswith("H4 elle-même inutilisable") and causes[own] == 1
    assert slots["pct_of_expected"]["present_not_computable"] == f"{20 / slots['expected'] * 100:.3f}"
    boxes = total["boxes"]
    assert boxes["recognised"] == 1 and boxes["fates"] == {"consommée par une cassure": 1}
    assert boxes["expired"] == 0 and boxes["abandoned_missing_data"] == 0
    assert summary["breakouts_not_evaluated"] == 1


def test_compressed_candles_are_not_boxes() -> None:
    summary, details = example()
    compressed = summary["total"]["compressed_h4"]
    assert compressed["candles"] >= 6 and compressed["candles_in_recognised_boxes"] == 6
    assert summary["total"]["boxes"]["recognised"] == 1
    (run,) = [r for r in details if r["kind"] == "séquence de H4 comprimées" and r["boxes"]]
    assert run["length"] >= 6 and run["boxes"] == 1
    assert compressed["runs_by_outcome"]["au moins une boîte reconnue"] == 1


def test_initialisation_of_the_bands_and_of_the_reference_widths() -> None:
    specs, _ = scenario(SUITE_1)
    summary, _ = study(specs, start=candle_end(ALL_SLOTS[0], Timeframe.H4))
    causes = summary["total"]["h4_slots"]["not_computable_causes"]
    assert causes["initialisation : moins de 20 H4 depuis le début de l'historique"] == 19
    # First width at the 20th H4; 240 widths are possible only from the 260th.
    assert causes["initialisation : moins de 240 largeurs possibles depuis le début de l'historique"] == 240


def test_an_absent_h4_in_a_box_is_counted_absent_and_abandons_the_box() -> None:
    specs, _ = scenario(SUITE_1)
    x = ALL_SLOTS.index(X)
    specs[x + 6] = None  # the H4 after F is missing
    summary, details = study(specs, start=at(-20))
    slots = summary["total"]["h4_slots"]
    assert slots["absent"] == 1 and slots["expected"] == 20 + 6 + 3 + len(SUITE_1)
    assert [r["slot_start_utc"] for r in details if r["kind"] == "créneau H4 absent"] == [ALL_SLOTS[x + 6]]
    assert slots["not_computable_causes"]["interruption : H4 prévue absente parmi les 20 H4 des bandes"] >= 1
    boxes = summary["total"]["boxes"]
    assert boxes["abandoned_missing_data"] == 1 and boxes["abandon_causes"] == {"H4 prévue absente": 1}
    assert boxes["abandoned_pct_of_recognised"] == "100.000"


def test_an_unusable_h4_in_a_box_abandons_it_with_its_state() -> None:
    summary, _ = example(degrade=[7])
    boxes = summary["total"]["boxes"]
    assert boxes["abandoned_missing_data"] == 1
    ((cause, n),) = boxes["abandon_causes"].items()
    assert cause.startswith("H4 ") and cause != "H4 prévue absente" and n == 1


def test_a_consolidation_too_wide_is_refused_at_each_window_but_is_one_run() -> None:
    summary, details = example(params=S3Params(max_height_atr=D(1)))  # 28 pips > 1 x 12 pips
    total = summary["total"]
    assert total["boxes"]["recognised"] == 0
    assert total["boxes"]["refused_too_wide_decisions"] >= 1
    runs = [r for r in details if r["kind"] == "séquence de H4 comprimées" and r["length"] >= 6]
    assert len(runs) == 1 and runs[0]["too_wide_decisions"] == total["boxes"]["refused_too_wide_decisions"]
    assert total["compressed_h4"]["runs_by_outcome"]["aucune boîte : toutes les fenêtres examinées trop larges"] == 1


def test_a_box_without_breakout_expires() -> None:
    specs, _ = scenario([])
    summary, _ = study([*specs[:-3], *INSIDE_BOX], start=at(-20))
    boxes = summary["total"]["boxes"]
    assert boxes["expired"] >= 1 and boxes["fates"]["expirée après 30 H4 sans cassure"] == boxes["expired"]
    assert boxes["expired_pct_of_recognised"] is not None


def test_expected_h4_slots_follow_the_calendar() -> None:
    first, until = at(-20), at(10)
    assert expected_h4_slots(first, until) == [s for s in ALL_SLOTS if first <= candle_end(s, Timeframe.H4) < until]
