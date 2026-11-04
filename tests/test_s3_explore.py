"""Synthetic tests of the S3 performance run tool (step 4). No real data."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from typing import Any

import pytest
import test_s3
from test_backtest import utc
from test_s3 import SUITE_1, SUITE_2, InjectedBox, Spec, X, at, d1_context, engine, scenario, spec, ticks_for

from forex_bot.backtest.engine import DecisionRecord, EntryAction, PositionAction, StopAtExecution, TickDrawdown
from forex_bot.backtest.explore import _str
from forex_bot.backtest.feed import TickFeed
from forex_bot.backtest.s3 import Box, S3Params
from forex_bot.backtest.s3_engine import S3Backtest, S3Result
from forex_bot.backtest.s3_explore import (
    NO_TICK,
    Recovery,
    S3Run,
    YearlyDrawdowns,
    breakout_category,
    compare_with_s1,
    controls,
    funnel,
    gated_report,
    reconcile_boxes,
    reconcile_breakouts,
    reconcile_entries,
    returns_to_box,
    s1_signals,
    scenario_triggers,
)
from forex_bot.risk import CostModel

Tool = Callable[..., tuple[S3Result, S3Run]]


@pytest.fixture
def tool(monkeypatch: pytest.MonkeyPatch) -> Tool:
    """The synthetic engine of test_s3, built as the run tool's S3Run (observation only)."""
    monkeypatch.setattr(test_s3, "S3Backtest", S3Run)

    def run(after: Sequence[Spec | None], **kwargs: Any) -> tuple[S3Result, S3Run]:
        built = engine(after, **kwargs)
        assert isinstance(built, S3Run)
        return built.run(), built

    return run


def never() -> dict[str, Any]:
    raise AssertionError("performance results must not be computed")


# ---------------------------------------------------------------- scenario B trigger (protocol §4)


def test_an_unobservable_possible_crossing_under_a_requires_b() -> None:
    after = [
        SUITE_1[0],
        spec("1.1349", "1.1350", "1.1340", "1.1345"),  # 30 minutes without quotes, the bid stays above the stop
        spec("1.1345", "1.1346", "1.1310", "1.1312"),  # later, the stop 1.1319 is observed
    ]
    result = engine(after, drop=(10, 6, 12)).run()
    (trade,) = result.trades
    assert trade.exit_reason == "STOP_OBSERVÉ" and trade.indeterminate
    triggers = scenario_triggers(result)
    assert triggers["scenario_b_required"] and len(triggers["unobservable_crossings"]) == 1
    assert not triggers["unobservable_crossings"][0]["open_at_end"]


def test_a_crossing_on_a_position_still_open_at_the_end_requires_b() -> None:
    result = engine(SUITE_2, drop=(10, 6, 12), end=at(13)).run()
    assert result.open_trade is not None and result.open_trade.indeterminate
    (crossing,) = scenario_triggers(result)["unobservable_crossings"]
    assert crossing["open_at_end"] and scenario_triggers(result)["scenario_b_required"]


def test_a_gap_followed_by_a_price_already_beyond_the_stop_does_not_require_b_by_itself() -> None:
    gap_then_beyond = [SUITE_1[0], spec("1.1349", "1.1350", "1.1340", "1.1310"), *SUITE_1[2:]]
    result = engine(gap_then_beyond, drop=(10, 1, 12)).run()  # 14:00, then nothing until 15:05 under the stop
    (trade,) = result.trades
    assert trade.exit_reason == "STOP_APRÈS_INTERRUPTION" and not trade.indeterminate
    triggers = scenario_triggers(result)
    assert not triggers["scenario_b_required"] and triggers["unobservable_crossings"] == []
    assert not triggers["reject_required"]


def test_a_stop_beyond_at_execution_requires_the_reject_run() -> None:
    gap_down = [spec("1.1318", "1.1317", "1.1316", "1.1317"), *SUITE_1[1:]]
    triggers = scenario_triggers(engine(gap_down).run())
    assert triggers["reject_required"] and triggers["stop_beyond_at_execution"] == 1
    assert not triggers["scenario_b_required"]


# ---------------------------------------------------------------- breakout funnel (protocol §6)


def _context_index(d1: list[dict[str, Any]], decision: datetime) -> int:
    return max(i for i, b in enumerate(d1) if b["end_utc"] <= decision)


def _unusable_context() -> list[dict[str, Any]]:
    d1 = d1_context()
    i = _context_index(d1, at(8))
    d1[i] = {**d1[i], "complete_at_close": False, "flags_at_close": ["trou de cotation"]}
    return d1


@pytest.mark.parametrize(
    ("kwargs", "category"),
    [
        ({}, "entrée décidée"),
        ({"d1": []}, "données D1 : insuffisantes"),
        ({"d1": "unusable"}, "données D1 : inutilisables"),
        ({"d1": d1_context(mirror=True)}, "refus : contexte D1 calculable, neutre ou contraire"),
        ({"params": S3Params(bb_width=D(6))}, "refus : pas d'expansion"),
        ({"costs": CostModel()}, "refus taille : coût inconnu"),
        ({"risk_fraction": D("0.0001")}, "refus taille : taille minimale"),
    ],
)
def test_each_breakout_is_in_one_category_recorded_by_the_engine(
    tool: Tool, kwargs: dict[str, Any], category: str
) -> None:
    if kwargs.get("d1") == "unusable":
        kwargs = {**kwargs, "d1": _unusable_context()}
    result, run = tool(SUITE_1, **kwargs)
    out = funnel(result, run.entry_events)
    assert out["breakouts"] == 1 and out["categories"] == {category: 1}
    assert all(out["checks"].values())


def test_neutral_or_contrary_d1_is_not_a_data_reason_without_the_filter(tool: Tool) -> None:
    for d1 in (d1_context(mirror=True), []):
        result, run = tool(SUITE_1, d1=d1, params=S3Params(use_d1_filter=False))
        assert funnel(result, run.entry_events)["categories"] == {"entrée décidée": 1}


@pytest.mark.parametrize(
    ("reason", "category"),
    [
        ("aucune cotation connue à l'instant de décision", "refus taille : aucune cotation connue"),
        ("estimation impossible : distance nulle", "refus taille : estimation impossible"),
        ("coût inconnu, jamais compté zéro : financement", "refus taille : coût inconnu"),
        ("taille minimale 0.1 > taille permise 0.0", "refus taille : taille minimale"),
        ("LONG : marché fermé à l'instant de décision", "refus : marché fermé à D"),
        ("cassure baissière contre le contexte D1", "refus : contexte D1 calculable, neutre ou contraire"),
    ],
)
def test_sizing_and_market_reasons_keep_their_own_category(reason: str, category: str) -> None:
    record = DecisionRecord(X, {}, PositionAction.FLAT, EntryAction.SIGNAL_REFUSED, [reason], {"side": "LONG"})
    assert breakout_category(record) == category


@pytest.mark.parametrize(
    ("reason", "category"),
    [
        ("bougie de cassure FERMETURE_DOCUMENTÉE", "données : bougie de cassure non OK"),
        ("bandes non calculables à la cassure", "données : bandes non calculables"),
        ("historique D1 insuffisant", "données D1 : insuffisantes"),
        ("D1 de contexte non utilisable", "données D1 : inutilisables"),
        ("D1 non utilisable dans le canal de 55 jours (règle stricte)", "données D1 : inutilisables"),
    ],
)
def test_data_reasons_at_the_breakout_keep_their_own_category(reason: str, category: str) -> None:
    record = DecisionRecord(X, {}, PositionAction.FLAT, EntryAction.NOT_COMPUTABLE, [reason], {"side": "LONG"})
    assert breakout_category(record) == category


class InjectedRun(InjectedBox, S3Run):
    """InjectedBox of test_s3, observed by the run tool."""


def test_a_breakout_during_a_position_is_not_evaluated_and_counted_once() -> None:
    base = engine(SUITE_2)
    injected = InjectedRun(
        base.h4, base.d1, ticks_for(*scenario(SUITE_2)), [], S3Params(), base.config, start_utc=base.start_utc
    )
    out = funnel(injected.run(), injected.entry_events)
    assert out["breakouts"] == 2 and all(out["checks"].values())
    assert out["categories"] == {"entrée décidée": 1, "non évaluée : position S3 déjà ouverte": 1}


def test_each_decided_entry_is_executed_or_not(tool: Tool) -> None:
    gap_down = [spec("1.1318", "1.1317", "1.1316", "1.1317"), *SUITE_1[1:]]
    result, run = tool(gap_down)
    filled = funnel(result, run.entry_events)  # executed then liquidated at once: an executed entry
    assert filled["executions"] == {"exécutée puis liquidée au premier tick (stop déjà dépassé)": 1}
    result, run = tool(gap_down, stop_at_execution=StopAtExecution.REJECT)
    rejected = funnel(result, run.entry_events)
    assert rejected["executions"] == {"non exécutée : rejet à l'exécution (stop invalide)": 1}
    result, run = tool(SUITE_1, end=at(8) + timedelta(minutes=1))  # the replay reaches the end, no tick after D
    pending = funnel(result, run.entry_events)
    assert pending["executions"] == {NO_TICK: 1}
    for out in (filled, rejected, pending):
        assert out["entries_decided"] == 1 and all(out["checks"].values())


def test_a_decided_entry_without_an_attesting_event_is_an_anomaly_that_hides_the_results(tool: Tool) -> None:
    result, _ = tool(SUITE_1, end=at(8) + timedelta(minutes=1))
    out = funnel(result, {})  # no event: "no tick before the end" is not assumed
    (execution,) = out["executions"]
    assert execution.startswith("anomalie") and not out["checks"]["every_entry_attested"]
    executed, _ = tool(SUITE_1)
    assert not funnel(executed, {})["checks"]["every_entry_attested"]  # a trade alone is not enough either
    checks = controls(result, {}, [], None)
    assert not checks["funnel"]["ok"] and checks["funnel"]["unexplained"][0]["decision_utc"] == at(8)
    report = gated_report(checks, {}, never)
    assert set(report) == {"anomaly", "controls"} and "funnel" in report["anomaly"]


# ---------------------------------------------------------------- boxes against step 3 (protocol §5)


def _boxes(n: int) -> list[Box]:
    first = datetime(2016, 1, 4, 2, tzinfo=UTC)
    out = []
    for k in range(n):
        box = Box(k, first + timedelta(hours=4 * k), D("1.1050"), D("1.1020"), D("1.1051"), D("0.0012"))
        box.end(box.formed_utc + timedelta(hours=8), "consommée par la cassure LONG")
        out.append(box)
    return out


def _rows(boxes: list[Box]) -> list[dict[str, Any]]:
    return [{"kind": "boîte", **_str(b.describe())} for b in boxes]


def test_identical_boxes_pass_the_check() -> None:
    boxes = _boxes(160)
    check = reconcile_boxes(_rows(boxes), boxes)
    assert check["ok"] and check["identical"] == 160 and check["different"] == []


def test_one_differing_box_among_160_is_named_with_its_field_and_hides_the_results() -> None:
    boxes = _boxes(160)
    rows = _rows(boxes)
    rows[41] = {**rows[41], "BL": "1.1019"}
    check = reconcile_boxes(rows, boxes)
    assert check["step3_boxes"] == check["run_boxes"] == 160 and not check["ok"]
    assert check["identical"] == 159 and check["only_in_run"] == check["only_in_step3"] == []
    (diff,) = check["different"]
    assert diff["F"] == boxes[41].formed_utc.isoformat()
    assert diff["fields"] == {"BL": {"step3": "1.1019", "run": "1.1020"}}

    report = gated_report({"boxes": check}, {"scenario_b_required": False}, never)
    assert set(report) == {"anomaly", "controls"} and "result" not in report


def test_two_identical_lists_of_159_boxes_fail_the_official_check() -> None:
    boxes = _boxes(159)
    assert reconcile_boxes(_rows(boxes), boxes)["ok"]  # the generic comparator accepts small sets
    check = reconcile_boxes(_rows(boxes), boxes, expected_count=160)
    assert not check["ok"] and check["identical"] == 159 and check["different"] == []
    report = gated_report({"boxes": check}, {}, never)
    assert set(report) == {"anomaly", "controls"}


def test_160_rows_with_a_repeated_f_are_not_160_distinct_boxes() -> None:
    boxes = _boxes(160)
    rows = _rows(boxes)
    rows[10] = rows[9]
    check = reconcile_boxes(rows, boxes, expected_count=160)
    assert check["step3_boxes"] == 160 and check["distinct_step3"] == 159 and not check["ok"]
    assert check["only_in_run"] == [boxes[10].formed_utc.isoformat()]


def test_a_missing_box_and_a_different_end_are_reported() -> None:
    boxes = _boxes(3)
    rows = _rows(boxes)
    rows[2] = {**rows[2], "end_reason": "expirée après 30 H4"}
    check = reconcile_boxes(rows[1:], boxes)
    assert not check["ok"] and check["only_in_run"] == [boxes[0].formed_utc.isoformat()]
    assert [d["fields"].keys() for d in check["different"]] == [{"end_reason": None}.keys()]


def test_each_consumed_box_matches_its_breakout_decision(tool: Tool) -> None:
    result, run = tool(SUITE_1)
    check = reconcile_breakouts(result)
    assert check["ok"] and check["boxes_consumed"] == check["breakout_decisions"] == check["matched"] == 1
    result.boxes[0].end_reason = "consommée par la cassure SHORT"  # the side no longer matches the decision
    check = reconcile_breakouts(result)
    assert not check["ok"] and check["boxes_without_breakout_decision"] and check["breakout_decisions_without_box"]
    checks = controls(result, run.entry_events, _rows(result.boxes), None)
    assert checks["boxes"]["ok"] and not checks["breakouts"]["ok"]
    assert set(gated_report(checks, {}, never)) == {"anomaly", "controls"}


def test_the_engine_boxes_reconcile_with_themselves_through_the_step3_format() -> None:
    result = engine(SUITE_1).run()
    check = reconcile_boxes(_rows(result.boxes), result.boxes)
    assert check["ok"] and check["identical"] == len(result.boxes) == 1


# ---------------------------------------------------------------- observation and comparison


def test_the_run_tool_only_observes() -> None:
    specs, starts = scenario(SUITE_2)
    base = engine(SUITE_2)
    args = (base.h4, base.d1)
    plain = S3Backtest(*args, TickFeed(ticks_for(specs, starts)), [], S3Params(), base.config, start_utc=base.start_utc)
    run = S3Run(*args, TickFeed(ticks_for(specs, starts)), [], S3Params(), base.config, start_utc=base.start_utc)
    plain_result, observed = plain.run(), run.run()
    assert [(t.entry_utc, t.exit_utc, t.net_account) for t in plain_result.trades] == [
        (t.entry_utc, t.exit_utc, t.net_account) for t in observed.trades
    ]
    assert observed.balance == plain_result.balance and run.relative.peak_eur >= base.config.initial_equity


def test_returns_to_box_group_positions_by_their_first_close_back() -> None:
    out = returns_to_box(engine(SUITE_1).run())
    assert out["RÉINTÉGRATION"]["positions"] == 1 and out["RÉINTÉGRATION"]["exits"] == {"SORTIE_SUIVEUSE": 1}
    assert out["RÉINTÉGRATION"]["h4_since_entry"]["median"] == 1
    assert returns_to_box(engine(SUITE_2).run())["sans retour"]["positions"] == 1


def test_coincidence_with_an_s1_signal_and_simultaneous_losses() -> None:
    result = engine(SUITE_1).run()  # one long entry decided at 2019-02-13 10:00, a loss
    trade = result.trades[0]
    s1_report = {
        "result": {
            "trades": [
                {
                    "entry_utc": (trade.entry_utc - timedelta(hours=1)).isoformat(),
                    "exit_utc": (trade.entry_utc + timedelta(hours=2)).isoformat(),
                    "side": "LONG",
                    "net_account": "-3.5",
                }
            ],
            "open_trade_at_end": None,
        },
        "by_year": {"2019": {"closed_trades": {"net_eur": "-3.5"}}},
    }
    lines: list[dict[str, Any]] = [
        {"decision_utc": "2019-02-13T10:00:00+00:00", "signal": {"side": "LONG"}},
        {"signal": None},
    ]
    window = list(range(2015, 2022))
    out = compare_with_s1(result, s1_report, s1_signals(lines), utc(2019, 3, 1), window)
    assert out["entries_coinciding_with_an_s1_signal"] == 1 and out["coincidence_pct"] == 100
    assert out["s3_losses_overlapping_an_s1_loss"] == 1 and out["hours_same_direction"] == 2
    assert list(out["net_by_year"]) == window  # the seven years, S3 at 0 EUR without a closed trade
    assert all(out["net_by_year"][y]["s3"] == 0 for y in window if y != 2019)
    assert trade.net_account is not None and out["net_by_year"][2019]["s3"] == trade.net_account < 0
    other_side = compare_with_s1(result, s1_report, {("2019-02-13T10:00:00+00:00", "SHORT")}, utc(2019, 3, 1), window)
    assert other_side["entries_coinciding_with_an_s1_signal"] == 0


def test_recovery_reports_the_longest_recovered_and_the_deepest_episode() -> None:
    recovery = Recovery(D(2000))
    t0 = datetime(2016, 1, 4, tzinfo=UTC)
    for day, equity in enumerate(["2000", "1990", "2001", "1950", "1980"]):
        recovery.observe(t0 + timedelta(days=day), D(equity))
    out = recovery.close()
    assert out["longest_recovered"]["days"] == 2 and out["longest_recovered"]["fall_eur"] == 10
    assert out["deepest"]["fall_eur"] == 51 and out["deepest"]["recovered_utc"] is None


def test_the_yearly_drawdown_starts_at_the_equity_of_the_first_tick_of_the_year() -> None:
    yearly, overall = YearlyDrawdowns(), TickDrawdown(D(2000), None)
    path = [
        (datetime(2015, 12, 31, 21, 59, tzinfo=UTC), "2000"),
        (datetime(2016, 1, 3, 22, 0, tzinfo=UTC), "1990"),  # lower at the first tick of January
        (datetime(2016, 1, 4, 9, 0, tzinfo=UTC), "1995"),
        (datetime(2016, 1, 5, 9, 0, tzinfo=UTC), "1985"),
    ]
    for moment, equity in path:
        yearly.observe(moment, D(equity))
        overall.observe(moment, D(equity))
    year = yearly.years[2016]
    assert year.observed_ticks == 3 and year.drawdown_peak_utc == path[2][0]
    assert year.max_drawdown_eur == 10  # 1995 -> 1985; from December's 2000 it would be 15
    assert overall.max_drawdown_eur == 15  # the global drawdown stays continuous
    assert yearly.years[2015].max_drawdown_eur == 0


# ---------------------------------------------------------------- duplicates hidden by dictionaries


def test_the_intact_single_entry_scenario_passes_every_control(tool: Tool) -> None:
    result, run = tool(SUITE_1)
    checks = controls(result, run.entry_events, _rows(result.boxes), None)
    assert all(check["ok"] for check in checks.values())
    assert checks["entries"]["entries_decided"] == checks["entries"]["trades"] == 1
    assert set(gated_report(checks, {}, lambda: {"ok": True})) == {"controls", "scenario_triggers", "result"}


def test_a_duplicated_breakout_decision_is_reported_and_blocks(tool: Tool) -> None:
    result, run = tool(SUITE_1)
    breakout = next(r for r in result.decisions if r.signal is not None)
    result.decisions.append(replace(breakout))  # two decided entries for one trade
    checks = controls(result, run.entry_events, _rows(result.boxes), None)
    (box,) = checks["breakouts"]["duplicates"]["breakout_decisions_per_box"]
    assert box == {"id": at(5).isoformat(), "occurrences": 2} and not checks["breakouts"]["ok"]
    (entry,) = checks["entries"]["duplicates"]["decided_entries"]
    assert entry == {"id": str(at(8)), "occurrences": 2} and not checks["entries"]["ok"]
    assert set(gated_report(checks, {}, never)) == {"anomaly", "controls"}


def test_a_duplicated_trade_is_reported_and_blocks(tool: Tool) -> None:
    result, run = tool(SUITE_1)
    result.trades.append(result.trades[0])  # two trades for one decided entry
    checks = controls(result, run.entry_events, _rows(result.boxes), None)
    assert checks["breakouts"]["ok"]
    (trade,) = checks["entries"]["duplicates"]["trades_per_entry"]
    assert trade == {"id": str(at(8)), "occurrences": 2} and not checks["entries"]["ok"]
    assert set(gated_report(checks, {}, never)) == {"anomaly", "controls"}


def test_a_closed_trade_and_the_open_trade_of_the_same_entry_are_a_duplicate(tool: Tool) -> None:
    result, _ = tool(SUITE_1)
    result.open_trade = replace(result.trades[0], exit_utc=None)
    check = reconcile_entries(result)
    assert check["duplicates"]["trades_per_entry"] == [{"id": str(at(8)), "occurrences": 2}] and not check["ok"]
