"""DAY_01 performance tool on synthetic sessions (docs/experiments/DAY01_REFERENCE_2015_2021.md).

Candles come from the same ticks through the real builder (DAY_01 convention), as in test_day01;
A = 0.00200 everywhere (synthetic H4). The study lines are produced by the availability study's own
code on the same candles, so that the reconciliation compares the two tools as they will be run.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pytest
from test_day01 import CONFIG, WINTER, _around_16h, at, candles, example_a, example_b, fill, h4_bars, tick

from forex_bot.backtest import day01_availability, day01_explore
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
    FIXED_COST_SHARE,
    INDETERMINATE,
    OPEN_AT_END,
    PENDING_LIQUIDATION,
    STOP_BEYOND_AT_EXECUTION,
    Day01Run,
    compare_triggers,
    controls,
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
from forex_bot.history.intraday import Grid, intraday_table
from forex_bot.history.intraday_audit import sha256_file


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


def test_m5_and_m15_runs_are_matched_by_london_date_session_by_session(tmp_path: Path) -> None:
    """Example A confirms at the same D in both units (sheet §7): one common execution, with zero
    differences of entry instant, stop and size, and a result difference computed from the two nets."""
    lines = {
        trigger: [jsonable(line) for line in Run(tmp_path / trigger.value, example_a(WINTER), trigger=trigger).lines]
        for trigger in Trigger
    }
    report = compare_triggers(lines[Trigger.M5], lines[Trigger.M15])
    (row,) = report["sessions"]
    assert row["day"] == WINTER.isoformat() and row["confirmed"] == {"M5": True, "M15": True}
    diff = row["m15_minus_m5"]
    assert diff["entry_minutes"] == 0.0 and D(diff["stop"]) == 0 and D(diff["size"]) == 0
    assert D(diff["net_eur"]) == D(diff["net_eur_m15"]) - D(diff["net_eur_m5"])
    synthesis = report["synthesis"]
    assert synthesis["confirmations"] == {"common": 1, "only_m5": 0, "only_m15": 0}
    assert synthesis["executed"] == {"common": 1, "only_m5": 0, "only_m15": 0}
    assert (synthesis["same_stop"], synthesis["same_size"], synthesis["common_closed"]) == (1, 1, 1)
    assert synthesis["net_of_common_closed_eur"]["M5"] == diff["net_eur_m5"]
    with pytest.raises(ValueError, match="plusieurs fois"):
        compare_triggers([*lines[Trigger.M5], lines[Trigger.M5][0]], lines[Trigger.M15])


def test_confirmations_own_to_one_trajectory_are_counted_from_the_rows() -> None:
    def line(day: str, outcome: str, trade: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"day": day, "outcome": outcome, "trade": trade}

    trade = {"entry_utc": "2019-02-12T08:45:00+00:00", "stop": "1.13189", "size": "0.6", "net_eur": "5"}
    later = {"entry_utc": "2019-02-12T08:55:00+00:00", "stop": "1.13180", "size": "0.5", "net_eur": "-2"}
    m5 = [line("2019-02-11", CONFIRMED, trade), line("2019-02-12", CONFIRMED, trade), line("2019-02-13", "X")]
    m15 = [line("2019-02-11", "INVALIDATION_APRÈS_CONTACT"), line("2019-02-12", CONFIRMED, later),
           line("2019-02-13", CONFIRMED)]  # fmt: skip
    report = compare_triggers(m5, m15)
    synthesis = report["synthesis"]
    assert synthesis["confirmations"] == {"common": 1, "only_m5": 1, "only_m15": 1}
    assert synthesis["executed"] == {"common": 1, "only_m5": 1, "only_m15": 0}
    diff = report["sessions"][1]["m15_minus_m5"]
    assert (diff["entry_minutes"], D(diff["stop"]), D(diff["size"]), D(diff["net_eur"])) == (
        10.0, D("-0.00009"), D("-0.1"), D("-7")
    )  # fmt: skip
    assert synthesis["path_differences"] == {"CONFIRMATION -> INVALIDATION_APRÈS_CONTACT": 1, "X -> CONFIRMATION": 1}
    assert synthesis["same_stop"] == 0 and synthesis["net_of_common_closed_eur"]["m15_minus_m5"] == "-7"


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


# ---------------------------------------------------------------- per-transaction measures (§7)


def _example_a_measures() -> dict[str, Any]:
    """Example A by hand (sheet §7): P_D 1.13261 (bid 1.13259), S 1.13189, T 1.13369, executed at the
    ask 1.13262, A = 0.00200, 0.6 contract of 10 000 EUR; slippage 0.5 pip, premium 1.2 USD, fee 0.5 %."""
    loss_quote = (D("1.13261") - D("1.13189") + D("0.00005")) * 10000 + D("1.2")  # 8.9 USD per contract
    gain = (D("1.13369") - D("1.13261") - D("0.00005")) * 10000 / D("1.13261") * D("0.995")
    loss = loss_quote / D("1.13259") * D("1.005")
    return {
        "distances": D("1.5"),
        "net": gain / loss,
        "obtained": D("0.00107") / D("0.00073"),
        "pips": D("7.2"),
        "atr_multiple": D("0.36"),
        "share": (D("0.00005") * 10000 + D("1.2")) / loss_quote,
    }


def test_each_transaction_carries_its_three_ratios_stop_distance_and_fixed_cost_share(tmp_path: Path) -> None:
    run = Run(tmp_path, example_a(WINTER))
    measured = run.lines[0]["measures"]
    expected = _example_a_measures()
    ratios = measured["ratios"]
    assert ratios["estimated_distances_at_d"] == {"value": expected["distances"], "reason": None}
    assert abs(ratios["net_estimated_at_d"]["value"] - expected["net"]) < D("1e-20")
    assert ratios["obtained_at_execution"]["value"] == expected["obtained"]
    assert (measured["stop_distance"]["pips"], measured["stop_distance"]["atr_multiple"]) == (
        expected["pips"], expected["atr_multiple"]
    )  # fmt: skip
    share = measured["fixed_cost_share_of_risk"]
    assert share["value"] == expected["share"] and share["definition"] == FIXED_COST_SHARE


def test_an_undefinable_measure_is_absent_with_its_reason(tmp_path: Path) -> None:
    """Stop already beyond at the first tick: no positive risk at the executed price."""
    run = Run(tmp_path, _beyond(WINTER, "1.13150"))
    ratios = run.lines[0]["measures"]["ratios"]
    assert ratios["obtained_at_execution"] == {
        "value": None, "reason": "stop déjà dépassé au prix exécuté : risque non positif"
    }  # fmt: skip
    assert ratios["estimated_distances_at_d"]["value"] == D("1.5")
    poor = ResearchConfig(costs=RESEARCH_COSTS, initial_equity=D("100"))
    assert Run(tmp_path / "poor", example_a(WINTER), config=poor).lines[0]["measures"] is None  # not decided


# ---------------------------------------------------------------- bounds: falsified results are blocked


def _checks(run: Run, lines: list[dict[str, Any]], result: Day01Result) -> dict[str, Any]:
    study, errors = study_lines(run.study(), official=False)
    ok: dict[str, Any] = {"ok": True, "errors": []}
    return controls(study, errors, lines, result, Trigger.M5, False, ok, ok)


@pytest.mark.parametrize("fault", ["d-minus-k", "after-12h05", "overlap"])
def test_falsified_bounds_block_the_results(tmp_path: Path, fault: str) -> None:
    run = Run(tmp_path, example_a(WINTER))
    assert all(c["ok"] for c in _checks(run, run.lines, run.result).values())
    lines, result = copy.deepcopy(run.lines), copy.deepcopy(run.result)
    if fault == "d-minus-k":  # D more than 60 min after K
        lines[0]["confirmation_utc"] = lines[0]["breakout"]["k_utc"] + timedelta(minutes=65)
        expected = "D − K = 1:05:00"
    elif fault == "after-12h05":
        lines[0]["trade"]["entry_utc"] = at(WINTER, 12, 5, 0, 1)
        expected = "après 12:05 Londres"
    else:  # a second position opened before the first one is closed
        (trade,) = result.trades
        result.trades.append(dataclasses.replace(trade, entry_utc=trade.entry_utc + timedelta(minutes=1)))
        expected = "positions simultanées"
    checks = _checks(run, lines, result)
    assert not checks["bounds"]["ok"] and any(expected in e for e in checks["bounds"]["errors"])
    body = gated_report(checks, {}, lambda: {"net": 1})
    assert "result" not in body and "bounds" in body["anomaly"]


# ---------------------------------------------------------------- end to end on a synthetic directory


def _directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ticks: list[Tick]) -> Path:
    """Data directory as on real data (ticks in the store, audited candle files, H4, quality report);
    the audited hashes and the git provenance are replaced by those of the files and a clean tree."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    m5, m15 = candles(tmp_path, ticks)
    data = tmp_path / "data"
    directory = data / "bars" / "dukascopy" / "EURUSD"
    (directory / "intraday_2015_2021_day01_5min").mkdir(parents=True)
    hashes = {}
    for grid, rows in ((Grid.M5, m5), (Grid.M15, m15)):
        path = directory / "intraday_2015_2021_day01_5min" / f"{grid.value}.parquet"
        pq.write_table(intraday_table("dukascopy", "EURUSD", grid, rows), path)
        hashes[grid] = sha256_file(path)
    pq.write_table(pa.Table.from_pylist(h4_bars(london(WINTER + timedelta(days=1), time(0)))), directory / "4h.parquet")
    (data / "reports").mkdir(exist_ok=True)
    (data / "reports" / "quality_dukascopy_EURUSD.json").write_text(json.dumps({"gaps": []}))
    clean: dict[str, Any] = {"commit": "abc", "uncommitted_diff_sha256": None, "uncommitted_files": []}
    for tool in (day01_availability, day01_explore):
        monkeypatch.setattr(tool, "CANDLES_SHA256", hashes)
        monkeypatch.setattr(tool, "provenance", lambda argv, name: {**clean, "command": [name]})
        monkeypatch.setattr(tool, "tree_state", lambda: dict(clean))
    return data


def test_command_end_to_end_writes_and_rereads_the_report_and_the_session_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _directory(tmp_path, monkeypatch, example_a(WINTER))
    window = ["--data-dir", str(data), "--init-start", "2019-01-01", "--start", "2019-02-12", "--end", "2019-02-13"]
    study = tmp_path / "study.jsonl"
    assert day01_availability.main([*window, "--out", str(tmp_path / "s.json"), "--details-out", str(study)]) == 0
    sessions = {}
    for trigger in Trigger:
        out, sessions[trigger] = tmp_path / f"{trigger.value}.json", tmp_path / f"{trigger.value}_sessions.jsonl"
        argv = [*window, "--trigger", trigger.value, "--scenario", "A", "--availability", str(study)]
        assert day01_explore.main([*argv, "--out", str(out), "--sessions-out", str(sessions[trigger])]) == 0
        report = json.loads(out.read_text(encoding="utf-8"))
        assert all(c["ok"] for c in report["controls"].values()) and report["inputs"]["ticks"] > 0
        assert report["controls"]["availability"]["identical"] == 1
        assert report["controls"]["provenance"]["launch"]["commit"] == "abc"
        result = report["result"]
        assert result["execution"]["confirmations"] == 1 and result["execution"]["entries_executed"] == 1
        assert result["execution"]["executed_outcomes"]["clôturée à la cible"] == 1
        assert result["ratios"]["estimated_distances_at_d"]["median"] == "1.5"
        assert out.with_suffix(".md").read_text(encoding="utf-8").startswith("# DAY_01")
        (line,) = [json.loads(r) for r in sessions[trigger].read_text(encoding="utf-8").splitlines()]
        assert line["outcome"] == CONFIRMED and line["at_d"]["decision"] == DECIDED
        measured, expected = line["measures"], _example_a_measures()
        assert D(measured["stop_distance"]["pips"]) == expected["pips"]
        assert D(measured["stop_distance"]["atr_multiple"]) == expected["atr_multiple"]
        assert D(measured["fixed_cost_share_of_risk"]["value"]) == expected["share"]
        assert D(measured["ratios"]["obtained_at_execution"]["value"]) == expected["obtained"]
    compared = tmp_path / "compare.json"
    argv = ["--m5", str(sessions[Trigger.M5]), "--m15", str(sessions[Trigger.M15]), "--out", str(compared)]
    assert day01_explore.compare_main(argv) == 0
    synthesis = json.loads(compared.read_text(encoding="utf-8"))["synthesis"]
    assert synthesis["confirmations"] == {"common": 1, "only_m5": 0, "only_m15": 0}


def test_command_end_to_end_withholds_results_when_the_study_disagrees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _directory(tmp_path, monkeypatch, example_a(WINTER))
    window = ["--data-dir", str(data), "--init-start", "2019-01-01", "--start", "2019-02-12", "--end", "2019-02-13"]
    study = tmp_path / "study.jsonl"
    assert day01_availability.main([*window, "--out", str(tmp_path / "s.json"), "--details-out", str(study)]) == 0
    rows = [json.loads(r) for r in study.read_text(encoding="utf-8").splitlines()]
    rows[0]["confirmation_utc"] = None  # a falsified study line
    study.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out, sessions = tmp_path / "r.json", tmp_path / "sessions.jsonl"
    argv = [*window, "--trigger", rows[0]["trigger"], "--scenario", "A", "--availability", str(study)]
    assert day01_explore.main([*argv, "--out", str(out), "--sessions-out", str(sessions)]) == 2
    report = json.loads(out.read_text(encoding="utf-8"))
    assert "result" not in report and not report["controls"]["availability"]["ok"] and not sessions.exists()
