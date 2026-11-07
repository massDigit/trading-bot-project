"""DAY_01 performance tool on synthetic sessions (docs/experiments/DAY01_REFERENCE_2015_2021.md).

Candles come from the same ticks through the real builder (DAY_01 convention), as in test_day01;
A = 0.00200 everywhere (synthetic H4). The study lines are produced by the availability study's own
code on the same candles, so that the reconciliation compares the two tools as they will be run.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pytest
from test_day01 import CONFIG, WINTER, _around_16h, at, candles, example_a, example_b, fill, h4_bars, tick

from forex_bot.backtest.day01 import (
    EXECUTED,
    LIQUIDATION,
    LIQUIDATION_AFTER_INTERRUPTION,
    REJECTED_AT_EXECUTION,
    SIZE_REFUSED,
    STOP_AT_EXECUTION,
    TARGET_AT_EXECUTION,
    Trigger,
    london,
)
from forex_bot.backtest.day01_availability import CONFIRMED, detail_line, expected_params, jsonable, run_trajectory
from forex_bot.backtest.day01_engine import Day01Backtest, Day01Result
from forex_bot.backtest.day01_explore import (
    CLOSED_LIQUIDATION,
    CLOSED_STOP,
    CLOSED_TARGET,
    DECIDED,
    INDETERMINATE,
    OPEN_AT_END,
    PENDING_LIQUIDATION,
    STOP_BEYOND_AT_EXECUTION,
    Day01Run,
    compare_triggers,
    execution,
    gated_report,
    liquidations,
    overlap,
    reconcile,
    scenario_triggers,
    session_lines,
    study_lines,
)
from forex_bot.backtest.engine import ResearchConfig, StopAtExecution
from forex_bot.backtest.explore import RESEARCH_COSTS
from forex_bot.backtest.feed import Silence, Tick
from forex_bot.backtest.s2 import GapScenario


class Run:
    """One synthetic DAY_01 run through the tool, with the availability study on the same candles."""

    def __init__(
        self,
        tmp_path: Path,
        ticks: list[Tick],
        day: date = WINTER,
        *,
        trigger: Trigger = Trigger.M5,
        config: ResearchConfig = CONFIG,
        scenario: GapScenario = GapScenario.OBSERVED_ONLY,
        end_utc: datetime | None = None,
        days: int = 1,
    ) -> None:
        self.m5, self.m15 = candles(tmp_path, ticks)
        self.start = london(day, time(0))
        self.end = end_utc or london(day + timedelta(days=days), time(0))
        self.h4 = h4_bars(london(day + timedelta(days=days), time(0)))
        self.params, self.config = expected_params(trigger), config
        self.engine = Day01Run(
            self.m5, self.m15, self.h4, sorted(ticks, key=lambda t: t.ts_utc), [], self.params, config,
            scenario=scenario, start_utc=self.start, end_utc=self.end,
        )  # fmt: skip
        self.result: Day01Result = self.engine.run()
        rows = {b["start_utc"]: b for b in self.m15}
        self.lines = session_lines(self.result, self.h4, [], config, rows)

    def study(self) -> list[dict[str, Any]]:
        """The availability study's JSONL lines for both triggers, on the same candles."""
        out = []
        for trigger in Trigger:
            t = run_trajectory(
                self.m5, self.m15, self.h4, [], ResearchConfig(costs=RESEARCH_COSTS), expected_params(trigger),
                self.start, self.end,
            )  # fmt: skip
            out += [json.loads(json.dumps(jsonable(detail_line(t, s)))) for s in t.sessions]
        return out


def _beyond(day: date, bid: str) -> list[Tick]:
    """Example A whose first tick after D (08:45:00.140) is at `bid`, kept until 16:30."""
    return example_a(day, [tick(at(day, 8, 45, 0, 140), bid), *fill(at(day, 8, 45, 30), at(day, 16, 30), bid)])


def _open_until(day: date, last: datetime) -> list[Tick]:
    """Example A executed at 08:45:00.140, then quotes every 30 s strictly before `last`."""
    return example_a(day, [tick(at(day, 8, 45, 0, 140), "1.13260"), *fill(at(day, 8, 45, 30), last, "1.13300")])


# ---------------------------------------------------------------- equivalence with the engine alone


def test_the_tool_observes_only_trades_balance_journal_and_curve_are_the_engine_s(tmp_path: Path) -> None:
    ticks = example_a(WINTER)
    run = Run(tmp_path, ticks)
    alone = Day01Backtest(
        run.m5, run.m15, run.h4, sorted(ticks, key=lambda t: t.ts_utc), [], run.params, CONFIG,
        start_utc=run.start, end_utc=run.end,
    ).run()  # fmt: skip
    assert run.result.trades == alone.trades and run.result.balance == alone.balance
    assert run.result.journal == alone.journal and run.result.equity_curve == alone.equity_curve
    assert run.result.sessions == alone.sessions and run.result.liquidations == alone.liquidations
    assert run.engine.ticks_read == len(ticks) and run.engine.first_tick_utc == min(t.ts_utc for t in ticks)


# ---------------------------------------------------------------- 1. path to D, apart from D


@pytest.mark.parametrize("trigger", list(Trigger), ids=[t.value for t in Trigger])
def test_a_confirmation_refused_at_d_for_its_size_still_matches_the_study_s_confirmation(
    tmp_path: Path, trigger: Trigger
) -> None:
    poor = ResearchConfig(costs=RESEARCH_COSTS, initial_equity=D("100"))  # budget 0.25 EUR < 0.1 contract
    run = Run(tmp_path, example_a(WINTER), trigger=trigger, config=poor)
    (session,) = run.result.sessions
    assert session.abstention == SIZE_REFUSED  # the engine's abstention is overwritten at D...
    (line,) = run.lines
    assert line["outcome"] == CONFIRMED  # ...not the path up to the confirmation
    assert line["at_d"]["decision"] == SIZE_REFUSED and line["trade"] is None
    study, errors = study_lines(run.study(), official=False)
    check = reconcile(study, errors, run.lines, trigger, official=False)
    assert check["ok"] and check["identical"] == 1 and check["confirmations"] == 1
    assert study[(WINTER.isoformat(), trigger.value)]["outcome"] == CONFIRMED
    flow = execution(run.lines, run.result)
    assert flow["ok"] and flow["confirmations"] == 1 and flow["at_d"] == {SIZE_REFUSED: 1}
    assert flow["entries_decided"] == 0 and flow["entries_executed"] == 0


def test_reconciliation_refuses_a_duplicate_couple_and_reports_every_difference(tmp_path: Path) -> None:
    run = Run(tmp_path, example_a(WINTER))
    rows = run.study()
    study, errors = study_lines([*rows, rows[0]], official=False)
    assert errors == [f"étude : doublon du couple ({WINTER.isoformat()!r}, 'M5') à la ligne 3"]
    assert not reconcile(study, errors, run.lines, Trigger.M5, official=False)["ok"]
    _, errors = study_lines(rows[:1], official=False)
    assert errors == [f"étude : 1 date(s) sans une ligne M5 et une ligne M15 : [{WINTER.isoformat()!r}]"]
    _, errors = study_lines(rows, official=True)
    assert errors == ["étude : 2 lignes et 1 dates, au lieu de 3654 et 1827"]
    altered = [dict(r, range=dict(r["range"], rh="1.13251")) if r["trigger"] == "M5" else r for r in rows]
    study, errors = study_lines(altered, official=False)
    check = reconcile(study, errors, run.lines, Trigger.M5, official=False)
    assert not check["ok"] and check["difference_count"] == 1 and check["differences"][0]["field"] == "range"


# ---------------------------------------------------------------- 2. exclusive outcomes and annotations


@pytest.mark.parametrize(
    ("bid", "outcome", "category", "reason"),
    [
        ("1.13150", STOP_AT_EXECUTION, CLOSED_STOP, STOP_BEYOND_AT_EXECUTION),
        ("1.13400", TARGET_AT_EXECUTION, CLOSED_TARGET, TARGET_AT_EXECUTION),
    ],
    ids=["stop-beyond", "target-beyond"],
)
def test_an_immediate_exit_is_an_executed_entry_counted_once_with_its_precise_reason(
    tmp_path: Path, bid: str, outcome: str, category: str, reason: str
) -> None:
    run = Run(tmp_path, _beyond(WINTER, bid))
    (trade,) = run.result.trades
    assert trade.entry_utc == trade.exit_utc == at(WINTER, 8, 45, 0, 140)
    flow = execution(run.lines, run.result)
    assert flow["ok"] and flow["entry_outcomes"] == {outcome: 1}
    assert (flow["entries_decided"], flow["entries_executed"], flow["entries_not_executed"]) == (1, 1, 0)
    assert flow["executed_outcomes"] == {
        CLOSED_STOP: int(category == CLOSED_STOP), CLOSED_TARGET: int(category == CLOSED_TARGET),
        CLOSED_LIQUIDATION: 0, OPEN_AT_END: 0,
    }  # fmt: skip
    assert flow["closing_reasons"] == {category: {reason: 1}}
    assert scenario_triggers(run.result)["reject_required"] is (outcome == STOP_AT_EXECUTION)


def test_a_rejected_entry_is_decided_but_not_executed(tmp_path: Path) -> None:
    reject = ResearchConfig(costs=RESEARCH_COSTS, stop_at_execution=StopAtExecution.REJECT)
    run = Run(tmp_path, _beyond(WINTER, "1.13150"), config=reject)
    flow = execution(run.lines, run.result)
    assert flow["ok"] and run.result.trades == [] and run.result.open_trade is None
    assert flow["at_d"] == {DECIDED: 1} and flow["entry_outcomes"] == {REJECTED_AT_EXECUTION: 1}
    assert (flow["entries_executed"], flow["entries_not_executed"]) == (0, 1)
    assert sum(flow["executed_outcomes"].values()) == 0


def test_annotations_overlap_the_exclusive_outcome_and_are_never_added_as_exits(tmp_path: Path) -> None:
    """Silence 15:54:00 -> 16:00:30 closed by the liquidating tick: one liquidation, which is also a
    liquidation after interruption and an indeterminate trade."""
    run = Run(tmp_path, _around_16h(at(WINTER, 15, 54), at(WINTER, 16, 0, 30)))
    (trade,) = run.result.trades
    assert trade.exit_reason == LIQUIDATION and trade.indeterminate
    flow = execution(run.lines, run.result)
    assert flow["ok"] and flow["entry_outcomes"] == {EXECUTED: 1}
    assert flow["executed_outcomes"][CLOSED_LIQUIDATION] == 1 and sum(flow["executed_outcomes"].values()) == 1
    assert flow["annotations"][INDETERMINATE] == 1 and flow["annotations"][LIQUIDATION_AFTER_INTERRUPTION] == 1
    check = liquidations(run.result)
    assert check["ok"] and check["resolved"] == 1 and check["after_interruption"] == 1
    assert check["pending_at_end"] is None and scenario_triggers(run.result)["scenario_b_required"]


# ---------------------------------------------------------------- 3. liquidation still pending at the end


def test_a_liquidation_pending_at_the_end_is_reported_without_invented_closing_and_passes(tmp_path: Path) -> None:
    """Last tick 15:59:30, explicit end 16:04:30: the 16:00 order waits 4 min 30 s, the silence (exactly
    5 min) is no interruption, so B and C are not required by this trade."""
    end = at(WINTER, 16, 4, 30)
    run = Run(tmp_path, _open_until(WINTER, at(WINTER, 16, 0)), end_utc=end)
    check = liquidations(run.result)
    assert check["ok"] and check["errors"] == [] and check["resolved"] == 0
    pending = check["pending_at_end"]
    assert (pending["decided_utc"], pending["end_of_study_utc"]) == (at(WINTER, 16, 0), end)
    assert pending["waiting_until_end"] == timedelta(minutes=4, seconds=30)
    assert pending["open_trade_decided_utc"] == at(WINTER, 8, 45)
    silence = pending["silence_in_progress"]
    assert silence["kind"] is Silence.NONE and silence["in_progress"]
    assert run.result.open_trade is not None and run.result.open_trade.exit_utc is None
    flow = execution(run.lines, run.result)
    assert flow["ok"] and flow["executed_outcomes"][OPEN_AT_END] == 1
    assert flow["annotations"][PENDING_LIQUIDATION] == 1 and flow["annotations"][INDETERMINATE] == 0
    assert run.lines[0]["trade"]["exit_reason"] is None and run.lines[0]["trade"]["exit_utc"] is None
    assert not scenario_triggers(run.result)["scenario_b_required"]


def test_a_liquidation_pending_through_an_interruption_at_the_end_requires_b_and_c(tmp_path: Path) -> None:
    run = Run(tmp_path, _open_until(WINTER, at(WINTER, 10, 0)))  # silence from 09:59:30 to midnight
    check = liquidations(run.result)
    assert check["ok"] and check["pending_at_end"]["silence_in_progress"]["kind"] is Silence.UNEXPLAINED
    triggers = scenario_triggers(run.result)
    assert triggers["scenario_b_required"] and triggers["scenario_c_required"]
    assert triggers["indeterminate_trades"][0]["open_at_end"]
    assert triggers["pending_liquidation_at_end"] == at(WINTER, 16, 0)
    flow = execution(run.lines, run.result)
    assert flow["ok"] and flow["annotations"][INDETERMINATE] == 1 and flow["annotations"][PENDING_LIQUIDATION] == 1


# ---------------------------------------------------------------- gating, comparisons


def test_a_failed_control_withholds_every_result() -> None:
    body = gated_report({"availability": {"ok": False}, "execution": {"ok": True}}, {}, lambda: {"net": 1})
    assert "result" not in body and "scenario_triggers" not in body and "availability" in body["anomaly"]
    assert gated_report({"execution": {"ok": True}}, {"b": False}, lambda: {"net": 1})["result"] == {"net": 1}


def test_m5_and_m15_runs_are_matched_by_london_date(tmp_path: Path) -> None:
    lines = {
        trigger: [jsonable(line) for line in Run(tmp_path / trigger.value, example_a(WINTER), trigger=trigger).lines]
        for trigger in Trigger
    }
    report = compare_triggers(lines[Trigger.M5], lines[Trigger.M15])
    assert report["dates"] == 1 and report["executed_in_both"] == 1 and report["path_differences"] == {}
    assert report["entry_delay_m15_minus_m5_minutes"] == {"0": 1}  # same D on example A (sheet §7)
    with pytest.raises(ValueError, match="plusieurs fois"):
        compare_triggers([*lines[Trigger.M5], lines[Trigger.M5][0]], lines[Trigger.M15])


def test_overlap_with_another_reference_is_descriptive(tmp_path: Path) -> None:
    run = Run(tmp_path, example_b(WINTER))  # entry 08:40:00.200, liquidated at 16:00:30
    (trade,) = run.result.trades
    other = {
        "provenance": {"commit": "abc"},
        "result": {
            "trades": [
                {"entry_utc": at(WINTER, 8, 0).isoformat(), "exit_utc": at(WINTER, 9, 40, 0, 200).isoformat(),
                 "side": "SHORT", "net_account": "-3"},
            ],
            "open_trade_at_end": None,
        },
    }  # fmt: skip
    report = overlap(run.result, other, run.end, [2019])
    assert report["day01_trades_overlapping"] == 1 and report["hours_opposite_direction"] == 1.0
    assert report["day01_losses_overlapping_a_loss"] == 0  # the DAY_01 trade wins
    assert report["net_by_year"][2019] == {"day01": trade.net_account, "reference": D("-3")}
