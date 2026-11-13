"""Partial exits and stop protection of the DAY_02 exploratory campaign (DAY02_PARTIAL_EXITS_CAMPAIGN.md).

LATE unchanged is the reference: same entries, initial stop, initial risk and size; PROT protects the
stop of a single exit at TP2, PART splits the position into TP1 / TP2 / TP3 portions with a fixed stop,
FULL does both. Synthetic data only: the sheet example (entry 1.13158 at 10:10:00.230, initial stop
1.13050, E 1.13140, TP2 = target 1.13300), then hand-written quotes.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest
from test_day02 import CONFIG, WINTER, at, candles, fill, got, h1_bars, tick
from test_day02_late_exit import held

from forex_bot.backtest.day01 import london
from forex_bot.backtest.day02 import LATE_LIQUIDATION, Day02Params
from forex_bot.backtest.day02_engine import Day02Backtest, Day02Result
from forex_bot.backtest.day02_explore import all_trades, closings, exit_outcomes, funnel
from forex_bot.backtest.day02_partials import (
    FINAL,
    MOVE_BREAK_EVEN,
    MOVE_TP1,
    allocation,
    build_plan,
    plan_errors,
    plan_measures,
    stop_in_force,
)
from forex_bot.backtest.day02_variants import variant_of, variant_params
from forex_bot.backtest.engine import ResearchConfig
from forex_bot.backtest.feed import Tick
from forex_bot.backtest.s2 import GapScenario
from forex_bot.risk import Side

LATE, PROT, PART, FULL = (variant_params(n) for n in ("LATE", "PROT", "PART", "FULL"))
ENTRY, STOP, PEAK, TP2 = D("1.13158"), D("1.13050"), D("1.13140"), D("1.13300")
TP3 = D("1.13460")
EQUITY = {1: D("600"), 2: D("1000"), 3: D("1500"), 4: D("2000")}  # size in 0.1 steps -> capital


def run(
    tmp_path: Path,
    ticks: list[Tick],
    params: Day02Params,
    steps: int = 3,
    *,
    day: date = WINTER,
    scenario: GapScenario = GapScenario.OBSERVED_ONLY,
    observe: bool = True,
) -> Day02Result:
    ticks = sorted(ticks, key=lambda t: t.ts_utc)
    m5, m15 = candles(tmp_path, ticks)
    config: ResearchConfig = replace(CONFIG, initial_equity=EQUITY[steps])
    engine = Day02Backtest(
        m5,
        m15,
        h1_bars(london(day + timedelta(days=1), time(0)), days=6),
        ticks,
        [],
        params,
        config,
        scenario=scenario,
        start_utc=london(day, time(0)),
        end_utc=london(day + timedelta(days=1), time(0)),
        observe_counterfactual=observe,
    )
    return engine.run()


def path(*legs: tuple[tuple[int, ...], tuple[int, ...], str], day: date = WINTER) -> list[Tick]:
    """The sheet example to its execution, then flat segments [start, end) at a bid each."""
    out = held(day, at(day, 10, 10, 30))
    for start, end, bid in legs:
        out += fill(at(day, *start), at(day, *end), bid)
    return out


def checked(result: Day02Result, params: Day02Params) -> None:
    trades = {t.decided_utc: t for t in all_trades(result)}
    assert plan_errors(result.plans, trades, params.partial_exits, params.protection) == []
    assert closings(result)["ok"]
    assert funnel(result.attempts, all_trades(result), exit_outcomes(params))["ok"]


# ---------------------------------------------------------------- definition


def test_variants_change_only_the_exit_plan_of_late() -> None:
    expected = {"PROT": {"protection"}, "PART": {"partial_exits"}, "FULL": {"partial_exits", "protection"}}
    for name, params in (("PROT", PROT), ("PART", PART), ("FULL", FULL)):
        diff = {k for k, v in vars(params).items() if vars(LATE)[k] != v}
        assert diff == expected[name], name
        assert variant_of(params) == name
    assert (PROT.partial_exits, PROT.protection, PART.partial_exits, PART.protection) == (False, True, True, False)
    assert (FULL.partial_exits, FULL.protection, LATE.partial_exits, LATE.protection) == (True, True, False, False)


@pytest.mark.parametrize(
    ("steps", "split"),
    [(1, (0, 1, 0)), (2, (1, 0, 1)), (3, (1, 1, 1)), (4, (2, 1, 1)), (5, (2, 1, 2)), (6, (2, 2, 2)), (7, (3, 2, 2))],
)
def test_allocation_in_thirds_of_0_1_steps_largest_remainder_ties_tp1_then_tp3(
    steps: int, split: tuple[int, int, int]
) -> None:
    size = D("0.1") * steps
    got_split = allocation(size, partial=True)
    assert tuple(got_split.values()) == tuple(D("0.1") * s for s in split)
    assert sum(got_split.values()) == size  # never more, never less than the LATE size
    assert allocation(size, partial=False) == {"TP1": D(0), "TP2": size, "TP3": D(0)}
    with pytest.raises(ValueError, match="pas"):
        allocation(D("0.25"), partial=True)  # no finer step is ever assumed


def test_levels_from_the_entry_the_initial_risk_and_the_impulse_projection() -> None:
    utc = at(WINTER, 10, 10)
    plan = got(build_plan(utc, Side.LONG, D("0.3"), ENTRY, STOP, PEAK, TP2, partial=True, protection=True))
    # R0 = 10.8 pips; TP2 is 14.2 pips away: 2/3 of it (9.47 pips) is below R0, so TP1 is capped.
    assert plan.r0 == D("0.00108") and plan.tp1 == ENTRY + (TP2 - ENTRY) * 2 / 3
    assert (plan.progress, plan.tp2, plan.tp3) == (plan.tp1 + (TP2 - plan.tp1) / 2, TP2, TP3)
    # Far projection: TP1 = entry + 1 R0. Sale: mirrored levels.
    far = got(build_plan(utc, Side.LONG, D("0.3"), ENTRY, STOP, PEAK, D("1.13500"), partial=True, protection=True))
    assert far.tp1 == ENTRY + D("0.00108")
    sale = got(build_plan(utc, Side.SHORT, D("0.3"), D("1.12842"), D("1.12950"), D("1.12860"), D("1.12700"),
                          partial=True, protection=True))  # fmt: skip
    assert sale.tp2 < sale.progress < sale.tp1 < sale.entry_price and sale.tp3 == D("1.12540")
    # No level ahead: no plan (the immediate exits of the reference apply).
    assert build_plan(utc, Side.LONG, D("0.3"), ENTRY, ENTRY, PEAK, TP2, partial=True, protection=True) is None
    assert build_plan(utc, Side.LONG, D("0.3"), ENTRY, STOP, PEAK, ENTRY, partial=True, protection=True) is None


# ---------------------------------------------------------------- engine


def test_late_mode_is_untouched_no_plan_and_the_same_trade(tmp_path: Path) -> None:
    ticks = path(((10, 10, 30), (22, 30), "1.13200"))
    late = run(tmp_path / "late", ticks, LATE)
    assert late.plans == [] and late.trades[0].exit_reason == LATE_LIQUIDATION
    # PROT whose events never happen: identical to LATE.
    prot = run(tmp_path / "prot", ticks, PROT)
    assert [vars(t) for t in prot.trades] == [vars(t) for t in late.trades]
    assert prot.plans[0].moves == [] and prot.balance == late.balance


def test_full_tp1_then_break_even_from_the_next_quote_then_stopped_at_entry(tmp_path: Path) -> None:
    ticks = path(
        ((10, 10, 30), (11, 0), "1.13200"),
        ((11, 0), (11, 0, 1), "1.13260"),  # TP1 reached and executed (0.1)
        ((11, 0, 30), (11, 0, 31), "1.13280"),  # P reached: the stop moves, in force from the next quote
        ((11, 1), (11, 1, 1), "1.13150"),  # below the entry: the remaining 0.2 stops at the entry price
        ((11, 2), (22, 30), "1.13320"),  # what would have followed (TP2), for the observer only
    )
    result = run(tmp_path, ticks, FULL)
    (trade,) = result.trades
    (plan,) = result.plans
    assert plan.quantities == {"TP1": D("0.1"), "TP2": D("0.1"), "TP3": D("0.1")}
    assert [(leg.portion, leg.size, leg.price, leg.utc) for leg in plan.legs] == [
        ("TP1", D("0.1"), D("1.13260"), at(WINTER, 11, 0)),
        (FINAL, D("0.2"), ENTRY, at(WINTER, 11, 1)),
    ]
    (move,) = plan.moves
    assert (move.utc, move.previous, move.stop, move.cause) == (at(WINTER, 11, 0, 30), STOP, ENTRY, MOVE_BREAK_EVEN)
    assert plan.legs[-1].stop_in_force == ENTRY == stop_in_force(plan, at(WINTER, 11, 1))
    # One economic transaction: the LATE size and initial risk, the sum of its executions.
    assert trade.size == D("0.3") and trade.stop == STOP and trade.exit_reason == "STOP_OBSERVÉ"
    assert trade.net_account == sum(leg.net_account for leg in plan.legs)
    # Break-even at the price is not a net break-even: the remaining 0.2 loses its costs.
    assert plan.legs[-1].gross_account == 0 and plan.legs[-1].net_account < 0
    assert plan.legs[-1].lines["prime de stop garanti"] == D("1.2") * D("0.2")  # stopped quantity only
    assert "prime de stop garanti" not in plan.legs[0].lines
    # The gain of TP1 is in the balance from 11:00, before the close of the remaining quantity.
    assert any(p.utc == at(WINTER, 11, 0) and p.balance > EQUITY[3] for p in result.equity_curve)
    # A posteriori: with the initial stop, the remaining would have reached TP2 (0.1) then 22:55 (0.1).
    cf = got(plan.counterfactual)
    assert [(leg[0], leg[1], leg[3]) for leg in cf["legs"]] == [  # type: ignore[attr-defined]
        ("TP2", D("0.1"), "TP2"),
        ("TP3", D("0.1"), "échéance"),
    ]
    assert D(str(cf["difference"])) > 0  # a continuation cut short, measured apart
    checked(result, FULL)


def test_the_counterfactual_observer_never_changes_the_simulation(tmp_path: Path) -> None:
    ticks = path(
        ((10, 10, 30), (11, 0), "1.13200"),
        ((11, 0), (11, 0, 31), "1.13280"),
        ((11, 1), (11, 1, 1), "1.13150"),
        ((11, 2), (22, 30), "1.13320"),
    )
    on, off = run(tmp_path / "on", ticks, FULL), run(tmp_path / "off", ticks, FULL, observe=False)
    assert [vars(t) for t in on.trades] == [vars(t) for t in off.trades]
    assert on.journal == off.journal and on.balance == off.balance and on.equity_curve == off.equity_curve
    strip = [replace(p, counterfactual=None) for p in on.plans]
    assert strip == off.plans and on.plans[0].counterfactual is not None


def test_part_keeps_the_initial_stop_and_liquidates_the_remaining_at_22_55(tmp_path: Path) -> None:
    ticks = path(
        ((10, 10, 30), (11, 0), "1.13200"),
        ((11, 0), (11, 0, 31), "1.13280"),  # TP1 executed, P reached: no move without protection
        ((11, 1), (22, 30), "1.13150"),  # under the entry, above the initial stop
    )
    result = run(tmp_path, ticks, PART)
    (plan,) = result.plans
    assert plan.moves == [] and set(plan.reached) == {"TP1", "P"}
    assert [(leg.portion, leg.size, leg.reason) for leg in plan.legs] == [
        ("TP1", D("0.1"), "CIBLE"),
        (FINAL, D("0.2"), LATE_LIQUIDATION),
    ]
    assert plan.legs[-1].utc == at(WINTER, 21, 55, 30)  # LATE convention: first quote strictly after
    assert plan.counterfactual is None
    checked(result, PART)


def test_several_portions_on_one_quote_in_level_order(tmp_path: Path) -> None:
    ticks = path(((10, 10, 30), (11, 0), "1.13200"), ((11, 0), (22, 30), "1.13480"))  # jump beyond TP3
    result = run(tmp_path, ticks, FULL)
    (plan,) = result.plans
    assert [(leg.portion, leg.utc, leg.price) for leg in plan.legs] == [
        ("TP1", at(WINTER, 11, 0), D("1.13480")),
        ("TP2", at(WINTER, 11, 0), D("1.13480")),
        ("TP3", at(WINTER, 11, 0), D("1.13480")),
    ]  # three planned portions, one execution event
    assert result.trades[0].exit_reason == "CIBLE" and plan.moves == []  # closed before any move acts
    assert plan_measures(result.plans)["execution_events_per_position"] == {1: 1}
    checked(result, FULL)


def test_two_steps_tp2_reached_without_quantity_raises_the_stop_to_tp1(tmp_path: Path) -> None:
    ticks = path(
        ((10, 10, 30), (11, 0), "1.13200"),
        ((11, 0), (11, 0, 1), "1.13310"),  # TP1 (0.1) executed; P and TP2 reached on the same quote
        ((11, 0, 30), (11, 0, 31), "1.13310"),
        ((11, 1), (22, 30), "1.13240"),  # under TP1: the remaining 0.1 (TP3 portion) stops at TP1
    )
    result = run(tmp_path, ticks, FULL, steps=2)
    (plan,) = result.plans
    assert plan.quantities == {"TP1": D("0.1"), "TP2": D(0), "TP3": D("0.1")}
    assert set(plan.executed) == {"TP1"} and "TP2" in plan.reached  # reached is not executed
    assert [(m.cause, m.stop, m.utc) for m in plan.moves] == [
        (MOVE_BREAK_EVEN, ENTRY, at(WINTER, 11, 0)),
        (MOVE_TP1, plan.tp1, at(WINTER, 11, 0)),
    ]
    assert [(leg.portion, leg.size, leg.price) for leg in plan.legs] == [
        ("TP1", D("0.1"), D("1.13310")),
        (FINAL, D("0.1"), plan.tp1),
    ]
    checked(result, FULL)


@pytest.mark.parametrize("params", [PROT, FULL], ids=["PROT", "FULL"])
def test_one_step_single_exit_at_tp2_with_the_protection_only(tmp_path: Path, params: Day02Params) -> None:
    ticks = path(
        ((10, 10, 30), (11, 0), "1.13200"),
        ((11, 0), (11, 0, 1), "1.13280"),  # TP1 reached without quantity, then P: break-even
        ((11, 1), (22, 30), "1.13150"),
    )
    result = run(tmp_path, ticks, params, steps=1)
    (plan,) = result.plans
    assert plan.quantities == {"TP1": D(0), "TP2": D("0.1"), "TP3": D(0)} and plan.executed == {}
    assert [(m.cause, m.utc) for m in plan.moves] == [(MOVE_BREAK_EVEN, at(WINTER, 11, 0))]
    assert [(leg.portion, leg.size, leg.price) for leg in plan.legs] == [(FINAL, D("0.1"), ENTRY)]
    checked(result, params)


def test_a_position_may_end_after_tp1_without_tp2_or_tp3(tmp_path: Path) -> None:
    ticks = path(
        ((10, 10, 30), (11, 0), "1.13200"),
        ((11, 0), (11, 0, 1), "1.13260"),  # TP1 only
        ((11, 1), (22, 30), "1.13040"),  # initial stop (P never reached)
    )
    result = run(tmp_path, ticks, FULL, steps=4)
    (plan,) = result.plans
    assert [(leg.portion, leg.size, leg.price) for leg in plan.legs] == [
        ("TP1", D("0.2"), D("1.13260")),
        (FINAL, D("0.2"), STOP),
    ]
    assert plan.counterfactual is None  # the initial stop: nothing to compare
    checked(result, FULL)


# ---------------------------------------------------------------- interruptions


def gap_path() -> list[Tick]:
    # TP1 executed at 11:00, then an unexplained 20-minute silence; the resume quote is at 1.13270.
    return path(
        ((10, 10, 30), (11, 0), "1.13200"),
        ((11, 0), (11, 0, 1), "1.13260"),
        ((11, 20), (11, 20, 1), "1.13270"),
        ((11, 21), (22, 30), "1.13230"),
    )


def test_scenario_c_executes_the_next_pending_portion_at_its_level_and_keeps_the_rest(tmp_path: Path) -> None:
    result = run(tmp_path, gap_path(), FULL, scenario=GapScenario.TARGET_FIRST)
    (plan,) = result.plans
    # TP2 supposed reached during the gap, executed at its level; TP3 portion stays open, P recorded.
    assert [(leg.portion, leg.size, leg.price, leg.reason) for leg in plan.legs[:2]] == [
        ("TP1", D("0.1"), D("1.13260"), "CIBLE"),
        ("TP2", D("0.1"), TP2, "CIBLE_SCÉNARIO_C"),
    ]
    assert plan.reached["TP2"] == at(WINTER, 11, 20) and "TP3" not in plan.executed
    # The moves of the supposed TP2 act from the quote after the resume, never on it.
    assert all(m.utc == at(WINTER, 11, 20) for m in plan.moves)
    assert plan.legs[-1].portion == FINAL and plan.legs[-1].price == plan.tp1  # stopped at TP1 at 11:21
    assert plan.legs[-1].utc == at(WINTER, 11, 21)
    assert sum(leg.size for leg in plan.legs) == D("0.3")  # nothing forgotten, nothing closed twice
    checked(result, FULL)


def test_scenario_b_closes_the_remaining_at_the_stop_in_force_before_the_gap(tmp_path: Path) -> None:
    result = run(tmp_path, gap_path(), FULL, scenario=GapScenario.STOP_FIRST)
    (plan,) = result.plans
    assert [(leg.portion, leg.size, leg.price, leg.reason) for leg in plan.legs] == [
        ("TP1", D("0.1"), D("1.13260"), "CIBLE"),
        (FINAL, D("0.2"), STOP, "STOP_SCÉNARIO_B"),  # initial stop: P was not reached before the gap
    ]
    checked(result, FULL)


# ---------------------------------------------------------------- causality and controls


@pytest.mark.parametrize("cut", [(11, 0, 15), (11, 0, 45), (12, 0)])
def test_quotes_after_an_instant_change_nothing_known_at_it(tmp_path: Path, cut: tuple[int, int, int]) -> None:
    x = at(WINTER, *cut)
    full = path(
        ((10, 10, 30), (11, 0), "1.13200"),
        ((11, 0), (11, 0, 31), "1.13280"),
        ((11, 1), (22, 30), "1.13230"),
    )
    before = [t for t in full if t.ts_utc < x]
    reference = run(tmp_path / "full", full, FULL)
    for case, ticks in {
        "cut": before,
        "down": before + fill(x, at(WINTER, 22, 30), "1.13000"),
        "up": before + fill(x, at(WINTER, 22, 30), "1.13500"),
    }.items():
        other = run(tmp_path / case, ticks, FULL)
        a, b = reference.plans[0], other.plans[0]
        assert [leg for leg in a.legs if leg.utc < x] == [leg for leg in b.legs if leg.utc < x], case
        assert [m for m in a.moves if m.utc < x] == [m for m in b.moves if m.utc < x], case
        assert {k: v for k, v in a.reached.items() if v < x} == {k: v for k, v in b.reached.items() if v < x}, case
        assert [j for j in reference.journal if j.utc < x] == [j for j in other.journal if j.utc < x], case


def test_the_plan_control_rejects_falsified_plans(tmp_path: Path) -> None:
    ticks = path(
        ((10, 10, 30), (11, 0), "1.13200"),
        ((11, 0), (11, 0, 31), "1.13280"),
        ((11, 1), (11, 1, 1), "1.13150"),
        ((11, 2), (22, 30), "1.13200"),
    )
    result = run(tmp_path, ticks, FULL)
    trades = {t.decided_utc: t for t in all_trades(result)}
    (plan,) = result.plans

    def errors(changed: object) -> list[str]:
        return plan_errors([changed], trades, True, True)  # type: ignore[list-item]

    assert errors(plan) == []
    retro = copy.deepcopy(plan)
    retro.moves[0].utc = plan.legs[-1].utc  # a move decided on the very quote it would act on
    assert any("rétroactif" in e for e in errors(retro))
    looser = copy.deepcopy(plan)
    looser.moves[0].stop = STOP - D("0.0001")
    assert any("éloigné" in e for e in errors(looser))
    lost = copy.deepcopy(plan)
    lost.legs[-1].size = D("0.1")
    assert any("non conservées" in e for e in errors(lost))
    early = copy.deepcopy(plan)
    early.legs[0].price = plan.tp1 - D("0.0001")
    assert any("avant son niveau" in e for e in errors(early))
    assert plan_errors([plan], trades, True, False) != []  # moves without protection


def test_friday_of_a_gap_week_the_remaining_waits_for_the_next_quote(tmp_path: Path) -> None:
    day = date(2019, 3, 15)  # the week closes at 21:00 UTC, before the 21:55 UTC deadline
    reopen = datetime(2019, 3, 17, 21, 0, 5, tzinfo=at(day, 0, 0).tzinfo)
    ticks = held(day, at(day, 11, 0)) + fill(at(day, 11, 0), at(day, 11, 0, 1), "1.13260")
    ticks += fill(at(day, 11, 1), datetime(2019, 3, 15, 21, 0, tzinfo=reopen.tzinfo), "1.13200")
    ticks.append(tick(reopen, "1.13200"))
    ticks = sorted(ticks, key=lambda t: t.ts_utc)
    m5, m15 = candles(tmp_path, ticks)
    engine = Day02Backtest(
        m5, m15, h1_bars(london(day + timedelta(days=3), time(0)), days=8), ticks, [], FULL,
        replace(CONFIG, initial_equity=EQUITY[3]), start_utc=london(day, time(0)),
        end_utc=london(day + timedelta(days=3), time(0)),
    )  # fmt: skip
    result = engine.run()
    (plan,) = result.plans
    assert [(leg.portion, leg.utc, leg.financing_nights) for leg in plan.legs] == [
        ("TP1", at(day, 11, 0), 0),
        (FINAL, reopen, 3),  # held beyond the deadline over the weekend: reported, not intraday
    ]
    (closing,) = result.closings
    assert closing.delay > timedelta(days=1)
    checked(result, FULL)
