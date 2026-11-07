"""DAY_02 performance tool on synthetic sessions (docs/experiments/DAY02_REFERENCE_2015_2021.md).

Candles come from the same ticks through the real builder (5 min convention), the H1 are the fixture
of the engine tests (A = 10 pips). The study lines are produced by the availability study's own code
on the same candles, so that the partial reconciliation compares the two tools as they will be run.
Each control is also run on records falsified on purpose, to show that it blocks.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from datetime import date, time, timedelta
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
from test_day02 import (
    CONFIG,
    WINTER,
    at,
    bar,
    candles,
    fill,
    got,
    h1_bars,
    late_example,
    search,
    sheet_bars,
    sheet_ticks,
    tick,
)

from forex_bot.backtest import day02_availability, day02_explore
from forex_bot.backtest.day01 import london
from forex_bot.backtest.day01_availability import jsonable
from forex_bot.backtest.day02 import (
    EXIT,
    FLAG_DATA,
    LIQUIDATION,
    POSITION_CLOSED,
    PROLONGED,
    REJECTED_AT_EXECUTION,
    SESSION_START,
    TIME_EXIT,
    Attempt,
    Trigger,
)
from forex_bot.backtest.day02_availability import PARAMS, availability, study_days
from forex_bot.backtest.day02_engine import Day02Backtest, Day02Result
from forex_bot.backtest.day02_explore import (
    CLOSED_TARGET,
    NO_CONFIGURATION,
    Day02Run,
    all_trades,
    closings,
    compare_main,
    comparison_plan,
    controls,
    funnel,
    gated_report,
    main,
    resumes,
    scenario_triggers,
    study_lines,
)
from forex_bot.backtest.engine import ResearchConfig, StopAtExecution
from forex_bot.backtest.explore import RESEARCH_COSTS
from forex_bot.backtest.feed import Tick
from forex_bot.backtest.s2 import GapScenario
from forex_bot.history.bars import bars_table
from forex_bot.history.calendar import Timeframe
from forex_bot.history.intraday import Grid, intraday_table
from forex_bot.history.intraday_audit import sha256_file

NEXT = WINTER + timedelta(days=1)
PASSED: dict[str, Any] = {"ok": True}


class Run:
    """One synthetic DAY_02 run through the tool, with the availability study on the same candles."""

    def __init__(
        self,
        tmp_path: Path,
        ticks: list[Tick],
        *,
        days: int = 1,
        trigger: Trigger = Trigger.M5,
        config: ResearchConfig = CONFIG,
        scenario: GapScenario = GapScenario.OBSERVED_ONLY,
    ) -> None:
        self.ticks = sorted(ticks, key=lambda t: t.ts_utc)
        self.m5, self.m15 = candles(tmp_path, self.ticks)
        self.start, self.end = london(WINTER, time(0)), london(WINTER + timedelta(days=days), time(0))
        self.h1 = h1_bars(self.end, days=days + 5)
        self.args: tuple[Any, ...] = (self.m5, self.m15, self.h1, self.ticks, [], PARAMS[trigger], config)
        self.scenario = scenario
        self.engine = Day02Run(*self.args, scenario=scenario, start_utc=self.start, end_utc=self.end)
        self.result: Day02Result = self.engine.run()
        self.days = study_days(self.start, self.end)

    def study(self) -> list[dict[str, Any]]:
        """The availability study's JSONL lines for both triggers, on the same candles."""
        bars = {Grid.M5: self.m5, Grid.M15: self.m15}
        _, details = availability(bars, self.h1, [], CONFIG, self.start, self.end, official=False)
        return [json.loads(json.dumps(jsonable(d))) for d in details]

    def checks(self, result: Day02Result | None = None, study: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        lines, errors = study_lines(self.study() if study is None else study, official=False)
        checks, _ = controls(result or self.result, self.engine, self.days, lines, errors, PASSED, PASSED)
        return checks


def failed(checks: dict[str, Any]) -> list[str]:
    return sorted(name for name, check in checks.items() if not check["ok"])


def errors_of(check: dict[str, Any]) -> str:
    return " | ".join(check["errors"])


def late_execution(day: date) -> list[Tick]:
    """The sheet example shifted to D = 14:55, executed at 15:00:00.000 (time exit due at 17:00)."""
    return [tick(at(day, 14, 55), "1.13156"), tick(at(day, 15, 0), "1.13156")]


# ---------------------------------------------------------------- equivalence with the engine alone


def test_the_tool_observes_only_trades_balance_journal_and_attempts_are_the_engine_s(tmp_path: Path) -> None:
    run = Run(tmp_path, sheet_ticks(WINTER))
    alone = Day02Backtest(*run.args, start_utc=run.start, end_utc=run.end).run()
    assert run.result.trades == alone.trades and run.result.balance == alone.balance
    assert run.result.journal == alone.journal and run.result.equity_curve == alone.equity_curve
    assert run.result.attempts == alone.attempts and run.result.closings == alone.closings
    assert run.engine.ticks_read == len(run.ticks)


# ---------------------------------------------------------------- the sheet example through every control


def test_sheet_example_passes_every_control_and_matches_the_study_where_the_state_is_the_same(
    tmp_path: Path,
) -> None:
    run = Run(tmp_path, sheet_ticks(WINTER))
    checks = run.checks()
    assert failed(checks) == [], {k: c.get("errors") for k, c in checks.items()}
    assert checks["recomputation"]["attempts"] == 2
    matched = checks["availability"]
    # The first search starts at 07:00 in both; the second resumes at the close (11:02:14.510), an
    # instant at which the study (resumed at D = 10:10) has no search: §5.1 only.
    assert (matched["first_searches_compared"], matched["other_attempts_compared"]) == (1, 0)
    assert matched["side_by_side"]["passage"]["total"] == {"configurations": 1, "sorties_confirmées": 1}
    assert matched["side_by_side"]["étude"]["2019"] == {"configurations": 1, "sorties_confirmées": 1}
    assert matched["side_by_side"]["sessions_with_another_resume_sequence"] == 1  # 11:02:14.510 vs D
    flow = funnel(run.result.attempts, all_trades(run.result))
    assert flow["searches_outcomes"] == {NO_CONFIGURATION: 1, "configuration": 1}
    assert (flow["flags_formed"], flow["confirmed_exits"], flow["entries_executed"]) == (1, 1, 1)
    assert flow["executed_outcomes"][CLOSED_TARGET] == 1 and all(flow["checks"].values())


def test_comparison_m15_passes_every_control(tmp_path: Path) -> None:
    run = Run(tmp_path, sheet_ticks(WINTER), trigger=Trigger.M15)
    checks = run.checks()
    assert failed(checks) == [], {k: c.get("errors") for k, c in checks.items()}
    assert checks["availability"]["first_searches_compared"] == 1


# ---------------------------------------------------------------- §5.2 resumes (review of the protocol)


def test_a_search_ending_without_configuration_has_no_end_and_is_no_anomaly(tmp_path: Path) -> None:
    run = Run(tmp_path, sheet_ticks(WINTER))
    last = run.result.attempts[-1]
    assert last.search.configuration is None and (last.ended_utc, last.ended_by) == (None, None)
    report = resumes(run.result, run.days)
    assert report["ok"] and report["searches_without_configuration"] == 1
    falsified = copy.deepcopy(run.result)
    falsified.attempts[-1].ended_utc, falsified.attempts[-1].ended_by = at(WINTER, 14, 15), "fin inventée"
    assert "≠ événement (None, None)" in errors_of(resumes(falsified, run.days))


def test_after_a_close_the_previous_evening_the_next_session_starts_at_07_00(tmp_path: Path) -> None:
    after = [*late_execution(WINTER), *fill(at(WINTER, 15, 0, 30), at(WINTER, 17, 30), "1.13200")]
    after += fill(at(NEXT, 7, 0), at(NEXT, 17, 30), "1.13200")
    run = Run(tmp_path, late_example(WINTER, after), days=2)
    first = run.result.attempts[0]
    assert (first.ended_utc, first.ended_by) == (at(WINTER, 17, 0, 30), POSITION_CLOSED)
    (resumed, *_) = [a for a in run.result.attempts if a.day == NEXT]
    assert (resumed.resume_utc, resumed.resume_after) == (at(NEXT, 7, 0), SESSION_START)  # not 17:00:30
    checks = run.checks()
    assert failed(checks) == [], {k: c.get("errors") for k, c in checks.items()}
    assert checks["resumes"]["first_resume_delayed"] == []
    assert checks["availability"]["first_searches_compared"] == 2


def test_a_position_held_at_07_00_delays_the_first_resume_to_its_close(tmp_path: Path) -> None:
    after = [*late_execution(WINTER), *fill(at(WINTER, 15, 0, 30), at(WINTER, 17, 0, 1), "1.13200")]
    after += fill(at(NEXT, 8, 3), at(NEXT, 17, 30), "1.13200")  # no quote from 17:00 to 08:03
    run = Run(tmp_path, late_example(WINTER, after), days=2)
    (resumed, *_) = [a for a in run.result.attempts if a.day == NEXT]
    assert (resumed.resume_utc, resumed.resume_after) == (at(NEXT, 8, 3), POSITION_CLOSED)
    checks = run.checks()
    assert failed(checks) == [], {k: c.get("errors") for k, c in checks.items()}
    (delayed,) = checks["resumes"]["first_resume_delayed"]
    assert (delayed["day"], delayed["resume_utc"]) == (NEXT, at(NEXT, 8, 3))
    assert checks["availability"]["sessions_excluded_first_resume_not_at_07_00"] == [NEXT]
    falsified = copy.deepcopy(run.result)
    (wrong, *_) = [a for a in falsified.attempts if a.day == NEXT]
    wrong.resume_utc, wrong.resume_after = at(NEXT, 7, 0), SESSION_START  # as if nothing were held
    assert "≠ 07:00 sans position" in errors_of(resumes(falsified, run.days))


def test_a_position_held_past_the_last_recognition_justifies_a_session_without_search(tmp_path: Path) -> None:
    after = [*late_execution(WINTER), *fill(at(WINTER, 15, 0, 30), at(WINTER, 17, 0, 1), "1.13200")]
    after += fill(at(NEXT, 14, 30), at(NEXT, 17, 30), "1.13200")
    run = Run(tmp_path, late_example(WINTER, after), days=2)
    assert [a.day for a in run.result.attempts] == [WINTER]
    checks = run.checks()
    assert failed(checks) == [], {k: c.get("errors") for k, c in checks.items()}
    (prevented,) = checks["resumes"]["sessions_without_search"]
    assert prevented["day"] == NEXT and prevented["position_decided_utc"] == at(WINTER, 14, 55)
    falsified = copy.deepcopy(run.result)
    falsified.skipped_days = [(d, r) for d, r in falsified.skipped_days if d != NEXT]
    assert "séance sans recherche, non justifiée" in errors_of(resumes(falsified, run.days))


def test_a_rejected_entry_authorises_the_resume_at_the_recorded_instant(tmp_path: Path) -> None:
    after = [tick(at(WINTER, 10, 10, 0, 230), "1.13040"), *fill(at(WINTER, 10, 10, 30), at(WINTER, 17, 30), "1.13200")]
    config = ResearchConfig(costs=RESEARCH_COSTS, stop_at_execution=StopAtExecution.REJECT)
    run = Run(tmp_path, sheet_ticks(WINTER, after), config=config)
    first, second = run.result.attempts[:2]
    assert (first.ended_utc, first.ended_by) == (at(WINTER, 10, 10, 0, 230), REJECTED_AT_EXECUTION)
    assert (second.resume_utc, second.resume_after) == (first.ended_utc, REJECTED_AT_EXECUTION)
    checks = run.checks()
    assert failed(checks) == [], {k: c.get("errors") for k, c in checks.items()}
    flow = funnel(run.result.attempts, all_trades(run.result))
    assert flow["entry_outcomes"][REJECTED_AT_EXECUTION] == 1 and flow["entries_executed"] == 0


def test_a_misdated_resume_is_blocking_and_withholds_every_result(tmp_path: Path) -> None:
    run = Run(tmp_path, sheet_ticks(WINTER))
    falsified = copy.deepcopy(run.result)
    falsified.attempts[1].resume_utc += timedelta(minutes=1)
    checks = run.checks(falsified)
    assert {"recomputation", "resumes"} <= set(failed(checks))
    assert "≠ fin" in errors_of(checks["resumes"])
    body = gated_report(checks, {}, lambda: {"net": 1})
    assert "result" not in body and "resumes" in body["anomaly"]


# ---------------------------------------------------------------- §5.1 and §5.3 falsified


def test_a_recorded_search_different_from_its_recomputation_is_blocking(tmp_path: Path) -> None:
    run = Run(tmp_path, sheet_ticks(WINTER))
    falsified = copy.deepcopy(run.result)
    config = got(falsified.attempts[0].search.configuration)
    config.origin_start = config.origin_start - timedelta(minutes=15)
    checks = run.checks(falsified)
    assert "recomputation" in failed(checks)
    text = errors_of(checks["recomputation"])
    assert "configuration_from" in text and "recalcul_distinct_C6" in text


def test_a_falsified_study_line_is_reported_where_the_resume_state_is_the_same(tmp_path: Path) -> None:
    run = Run(tmp_path, sheet_ticks(WINTER))
    rows = run.study()
    line = next(r for r in rows if r["trigger"] == "M5")
    line["searches"][0]["configuration"]["stop"] = "1.13000"
    checks = run.checks(study=rows)
    assert failed(checks) == ["availability"]
    (difference,) = checks["availability"]["differences"]
    assert difference["field"] == "configuration"
    duplicated = [*rows, rows[0]]
    assert "doublon" in errors_of(run.checks(study=duplicated)["availability"])


# ---------------------------------------------------------------- §6 funnel


def test_unusable_data_after_the_flag_is_an_outcome_of_the_formed_flags() -> None:
    m15, m5 = sheet_bars(WINTER)
    unusable = bar(at(WINTER, 10, 5), "1.13125", "1.13160", "1.13120", "1.13155", timedelta(minutes=5), ok=False)
    m5[at(WINTER, 10, 5)] = unusable  # the second M5 after F
    found = search(WINTER, m15, m5)
    config = got(found.configuration)
    assert config.flag_utc == at(WINTER, 10, 0)
    assert (config.outcome, config.ended_utc) == (FLAG_DATA, at(WINTER, 10, 10))
    attempt = Attempt(WINTER, at(WINTER, 7, 0), SESSION_START, found, ended_utc=config.ended_utc, ended_by=FLAG_DATA)
    flow = funnel([attempt], [])
    assert flow["configuration_outcomes"][FLAG_DATA] == 0 and flow["configuration_outcomes"]["drapeau formé"] == 1
    assert flow["flags_formed"] == 1 and flow["flag_outcomes"][FLAG_DATA] == 1
    assert sum(flow["flag_outcomes"].values()) == flow["flags_formed"] and all(flow["checks"].values())
    config.outcome = PROLONGED  # not an outcome after F: the conservation of the formed flags fails
    assert not funnel([attempt], [])["checks"]["formed_flags_conserved"]


# ---------------------------------------------------------------- closings, scenarios


def test_a_time_exit_is_one_closing_with_its_deadline_and_a_falsified_order_blocks(tmp_path: Path) -> None:
    after = [tick(at(WINTER, 10, 10, 0, 230), "1.13156"), *fill(at(WINTER, 10, 10, 30), at(WINTER, 17, 30), "1.13200")]
    run = Run(tmp_path, sheet_ticks(WINTER, after))
    report = closings(run.result)
    assert report["ok"] and report["orders"] == {TIME_EXIT: 1} and report["positions_after_17h"] == 0
    flow = funnel(run.result.attempts, all_trades(run.result))
    assert flow["executed_outcomes"][TIME_EXIT] == 1
    falsified = copy.deepcopy(run.result)
    falsified.closings[0] = dataclasses.replace(falsified.closings[0], order=LIQUIDATION)
    assert "échéance ou ordre différent" in errors_of(closings(falsified))


def test_a_silence_during_a_position_requires_b_and_c(tmp_path: Path) -> None:
    after = [tick(at(WINTER, 10, 10, 0, 230), "1.13156"), *fill(at(WINTER, 10, 10, 30), at(WINTER, 10, 40, 1), "1.132")]
    after += fill(at(WINTER, 10, 45, 0, 1), at(WINTER, 17, 30), "1.13200")  # 10:40 -> 10:45:00.001: > 5 min
    run = Run(tmp_path, sheet_ticks(WINTER, after))
    triggers = scenario_triggers(run.result)
    assert triggers["scenario_b_required"] and triggers["scenario_c_required"] and not triggers["reject_required"]
    assert failed(run.checks()) == []


def test_comparisons_are_planned_only_when_both_passes_exist() -> None:
    def report(trigger: str, b: bool, reject: bool) -> dict[str, Any]:
        triggers = {"scenario_b_required": b, "scenario_c_required": b, "reject_required": reject}
        return {"config": {"trigger": trigger, "scenario": "A"}, "result": {}, "scenario_triggers": triggers}

    plan = comparison_plan(report("M5", True, False), report("M15", False, True))
    assert plan["A"].startswith("les deux passages existent")
    assert plan["B"].startswith("requis seulement en M5") and "pas lancé" in plan["B"]
    assert plan["A_rejet"].startswith("requis seulement en M15")
    both = comparison_plan(report("M5", True, False), report("M15", True, False))
    assert both["B"].startswith("requis des deux côtés") and both["A_rejet"] == "non requis"
    with pytest.raises(ValueError, match="passage A"):
        comparison_plan({"config": {"trigger": "M5", "scenario": "A"}}, report("M15", False, False))


# ---------------------------------------------------------------- end to end on a synthetic directory


def _directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ticks: list[Tick]) -> Path:
    """Data directory as on real data (ticks in the store, audited candle files, H1, quality report);
    the audited hashes and the git provenance are replaced by those of the files and a clean tree."""
    m5, m15 = candles(tmp_path, sorted(ticks, key=lambda t: t.ts_utc))
    data = tmp_path / "data"
    directory = data / "bars" / "dukascopy" / "EURUSD"
    (directory / day02_availability.LOT).mkdir(parents=True)
    hashes = {}
    for grid, rows in ((Grid.M5, m5), (Grid.M15, m15)):
        path = directory / day02_availability.LOT / f"{grid.value}.parquet"
        pq.write_table(intraday_table("dukascopy", "EURUSD", grid, rows), path)
        hashes[grid] = sha256_file(path)
    h1 = h1_bars(london(NEXT, time(0)), days=8)
    pq.write_table(bars_table("dukascopy", "EURUSD", Timeframe.H1, h1), directory / "1h.parquet")
    (data / "reports").mkdir(exist_ok=True)
    (data / "reports" / "quality_dukascopy_EURUSD.json").write_text(json.dumps({"gaps": []}))
    clean: dict[str, Any] = {"commit": "abc", "uncommitted_diff_sha256": None, "uncommitted_files": []}
    for tool in (day02_availability, day02_explore):
        monkeypatch.setattr(tool, "CANDLES_SHA256", hashes)
        monkeypatch.setattr(tool, "H1_SHA256", sha256_file(directory / "1h.parquet"))
        monkeypatch.setattr(tool, "provenance", lambda argv, name: {**clean, "command": [name]})
        monkeypatch.setattr(tool, "tree_state", lambda: dict(clean))
    return data


WINDOW = ["--start", "2019-02-11", "--end", "2019-02-13"]  # Monday: the H1 ATR is ready on Tuesday


def test_command_end_to_end_writes_the_reports_the_session_files_and_the_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _directory(tmp_path, monkeypatch, sheet_ticks(WINTER))
    study = tmp_path / "study.jsonl"
    window = ["--data-dir", str(data), *WINDOW]
    assert day02_availability.main([*window, "--out", str(tmp_path / "s.json"), "--details-out", str(study)]) == 0
    reports, sessions = {}, {}
    for trigger in Trigger:
        out, sessions[trigger] = tmp_path / f"{trigger.value}.json", tmp_path / f"{trigger.value}_sessions.jsonl"
        argv = [*window, "--init-start", "2019-02-11", "--trigger", trigger.value, "--scenario", "A"]
        argv += ["--availability", str(study), "--out", str(out), "--sessions-out", str(sessions[trigger])]
        assert main(argv) == 0
        reports[trigger] = out
        report = json.loads(out.read_text(encoding="utf-8"))
        assert all(c["ok"] for c in report["controls"].values()) and report["inputs"]["ticks"] > 0
        assert report["controls"]["availability"]["first_searches_compared"] == 2
        assert report["controls"]["provenance"]["launch"]["commit"] == "abc"
        flow = report["result"]["funnel"]
        assert (flow["confirmed_exits"], flow["entries_executed"]) == (1, 1)
        assert flow["executed_outcomes"][CLOSED_TARGET] == 1 and FLAG_DATA in flow["flag_outcomes"]
        assert report["result"]["relative_drawdown"]["first_review_crossing_6pct"] is None
        assert out.with_suffix(".md").read_text(encoding="utf-8").startswith("# DAY_02 — passage")
        lines = [json.loads(r) for r in sessions[trigger].read_text(encoding="utf-8").splitlines()]
        assert [line["day"] for line in lines] == ["2019-02-11", "2019-02-12"]
        (executed,) = [a for line in lines for a in line["attempts"] if a["trade"] is not None]
        assert executed["configuration"]["outcome"] == EXIT and executed["matched_with_study"]
        assert executed["approximation_gap_pips"] is not None and executed["measures"]["stop_distance"]["pips"]
    plan = tmp_path / "plan.json"
    argv = ["--m5-report", str(reports[Trigger.M5]), "--m15-report", str(reports[Trigger.M15])]
    assert compare_main([*argv, "--plan", "--out", str(plan)]) == 0
    assert json.loads(plan.read_text(encoding="utf-8"))["B"] == "non requis"
    compared = tmp_path / "compare.json"
    files = ["--m5", str(sessions[Trigger.M5]), "--m15", str(sessions[Trigger.M15])]
    assert compare_main([*argv, *files, "--out", str(compared)]) == 0
    first = json.loads(compared.read_text(encoding="utf-8"))["first_configuration_same_state"]
    assert first["sessions"] == 2 and first["executed"] == {"common": 1, "only_m5": 0, "only_m15": 0}
    # Same trigger on both sides: no comparison is produced.
    wrong = ["--m5-report", str(reports[Trigger.M5]), "--m15-report", str(reports[Trigger.M5])]
    assert compare_main([*wrong, *files, "--out", str(tmp_path / "no.json")]) == 2
    assert not (tmp_path / "no.json").exists()


def test_command_end_to_end_withholds_results_when_the_study_disagrees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _directory(tmp_path, monkeypatch, sheet_ticks(WINTER))
    study = tmp_path / "study.jsonl"
    window = ["--data-dir", str(data), *WINDOW]
    assert day02_availability.main([*window, "--out", str(tmp_path / "s.json"), "--details-out", str(study)]) == 0
    rows = [json.loads(r) for r in study.read_text(encoding="utf-8").splitlines()]
    target = next(r for r in rows if r["trigger"] == "M5" and r["day"] == WINTER.isoformat())
    target["searches"][0]["configuration"]["target"] = "1.14000"  # a falsified study line
    study.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out, sessions = tmp_path / "r.json", tmp_path / "sessions.jsonl"
    argv = [*window, "--init-start", "2019-02-11", "--trigger", "M5", "--scenario", "A", "--availability", str(study)]
    assert main([*argv, "--out", str(out), "--sessions-out", str(sessions)]) == 2
    report = json.loads(out.read_text(encoding="utf-8"))
    assert "result" not in report and not report["controls"]["availability"]["ok"] and not sessions.exists()
