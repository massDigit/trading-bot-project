"""DAY_02 frequency lot (docs/experiments/DAY02_FREQUENCY_CAMPAIGN.md, ADR-039): G1A, G5B, G1A5B, E3,
F2R, RSC, M5S, each one LATE plus one change. Synthetic data only; LATE itself is unchanged.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pytest
from test_day02 import MIN, WINTER, at, bar, fill, flat, got, search, sheet_bars, sheet_ticks, target_after, tick
from test_day02_late_exit import run

from forex_bot.backtest.day02 import (
    CANCELLED_TARGET,
    ENTRY_DECIDED,
    EXHAUSTION,
    EXIT,
    EXPIRED,
    FAILED2_EXIT,
    TIME_BLOCK,
    TOO_DEEP,
    Day02Params,
    ceil_unit,
    is_failed2,
    is_nowick,
)
from forex_bot.backtest.day02_availability import bound_errors, independent_first, reuse_errors
from forex_bot.backtest.day02_variants import ALL_VARIANTS, FREQUENCY, VARIANTS, variant_of, variant_params
from forex_bot.backtest.feed import Tick

LATE = variant_params("LATE")
M5 = timedelta(minutes=5)


# ---------------------------------------------------------------- definitions


def test_each_frequency_configuration_is_late_plus_its_own_change_only() -> None:
    assert list(VARIANTS)[-4:] == ["LATE", "PROT", "PART", "FULL"]  # earlier campaigns untouched
    assert ALL_VARIANTS[len(VARIANTS) :] == ["G1A", "G5B", "G1A5B", "E3", "F2R", "RSC", "M5S"]
    expected = {
        "G1A": {"exhaustion_filter"},
        "G5B": {"time_block_ny"},
        "G1A5B": {"exhaustion_filter", "time_block_ny"},
        "E3": {"retest_entry"},
        "F2R": {"failed2_trigger"},
        "RSC": {"overlap_resume"},
        "M5S": {"unit", "max_pause"},
    }
    for name, changed in expected.items():
        params = variant_params(name)
        assert {k for k, v in vars(params).items() if vars(LATE)[k] != v} == changed, name
        assert variant_of(params) == name
    assert variant_params("G5B").time_block_ny == (time(7, 30), time(9, 30))
    assert (variant_params("M5S").unit, variant_params("M5S").max_pause) == (M5, timedelta(minutes=30))
    assert variant_params("E3").retest_validity == 9
    # The frozen defaults keep every switch of the lot off.
    reference = Day02Params()
    assert not (reference.exhaustion_filter or reference.retest_entry or reference.failed2_trigger)
    assert (reference.time_block_ny, reference.overlap_resume, reference.unit) == (None, False, timedelta(minutes=15))
    assert set(FREQUENCY) == set(expected)


def test_nowick_and_failed2_candles_long_and_short() -> None:
    s = at(WINTER, 9, 0)
    assert is_nowick(bar(s, "1.1000", "1.1010", "1.1000", "1.1008"), long=True)
    assert not is_nowick(bar(s, "1.1000", "1.1010", "1.0999", "1.1008"), long=True)  # lower wick
    assert not is_nowick(bar(s, "1.1000", "1.1010", "1.1000", "1.1000"), long=True)  # no rise
    assert is_nowick(bar(s, "1.1010", "1.1010", "1.1000", "1.1002"), long=False)
    prev = bar(s, "1.1005", "1.1010", "1.1000", "1.1006")
    assert is_failed2(bar(s, "1.1004", "1.1008", "1.0998", "1.1003"), prev, long=True)
    assert not is_failed2(bar(s, "1.1004", "1.1008", "1.0998", "1.0999"), prev, long=True)  # closes past it
    assert not is_failed2(bar(s, "1.1004", "1.1011", "1.0998", "1.1003"), prev, long=True)  # sweeps both
    assert is_failed2(bar(s, "1.1006", "1.1012", "1.1002", "1.1007"), prev, long=False)
    assert ceil_unit(at(WINTER, 9, 2), M5) == at(WINTER, 9, 5) and ceil_unit(at(WINTER, 9, 5), M5) == at(WINTER, 9, 5)


# ---------------------------------------------------------------- G1A and G5B: refusals at D


def test_g1a_refuses_a_nowick_peak_candle_and_late_takes_it(tmp_path: Path) -> None:
    # Peak candle 09:15 of the sheet opened at its low: a NoWick in the direction.
    ticks = sheet_ticks(WINTER, changes={(9, 15): ("1.13050", "1.13140", "1.13050", "1.13130")})
    late = run(tmp_path / "late", ticks, LATE)
    g1a = run(tmp_path / "g1a", ticks, variant_params("G1A"))
    assert len(late.trades) == 1 and not g1a.trades
    refused = [a for a in g1a.attempts if a.at_d is not None]
    assert [a.at_d for a in refused] == [EXHAUSTION]
    assert refused[0].ended_utc == at(WINTER, 10, 10)  # the search resumes at D
    plain = run(tmp_path / "plain", sheet_ticks(WINTER), variant_params("G1A"))  # 09:15 has a lower wick
    assert len(plain.trades) == 1


def test_g5b_refuses_an_exit_candle_opening_between_0730_and_0930_new_york(tmp_path: Path) -> None:
    shift = timedelta(hours=3)  # exit candle 13:05 London = 08:05 New York (winter)
    ticks = sheet_ticks(WINTER, shift=shift, after=target_after(WINTER, shift))
    assert len(run(tmp_path / "late", ticks, LATE).trades) == 1
    g5b = run(tmp_path / "g5b", ticks, variant_params("G5B"))
    assert not g5b.trades and [a.at_d for a in g5b.attempts if a.at_d] == [TIME_BLOCK]
    # 10:05 London = 05:05 New York: outside the block.
    assert len(run(tmp_path / "early", sheet_ticks(WINTER), variant_params("G5B")).trades) == 1


# ---------------------------------------------------------------- E3: limit order at E


def e3_ticks(after: list[Tick]) -> list[Tick]:
    return sheet_ticks(WINTER, after=after)


def test_e3_fills_at_the_first_ask_at_or_below_e_and_sizes_from_e(tmp_path: Path) -> None:
    after = [
        tick(at(WINTER, 10, 10, 0, 230), "1.13156"),
        *fill(at(WINTER, 10, 10, 30), at(WINTER, 10, 20), "1.13160"),
        tick(at(WINTER, 10, 20), "1.13130"),  # ask 1.13132 <= E = 1.13140
        *fill(at(WINTER, 10, 20, 30), at(WINTER, 11, 0), "1.13200"),
        tick(at(WINTER, 11, 0), "1.13300"),
        *fill(at(WINTER, 11, 0, 30), at(WINTER, 17, 30), "1.13250"),
    ]
    late = run(tmp_path / "late", e3_ticks(after), LATE)
    e3 = run(tmp_path / "e3", e3_ticks(after), variant_params("E3"))
    a, b = got(late.trades[0] if late.trades else None), got(e3.trades[0] if e3.trades else None)
    assert (a.entry_utc, a.entry_price) == (at(WINTER, 10, 10, 0, 230), D("1.13158"))
    assert (b.entry_utc, b.entry_price) == (at(WINTER, 10, 20), D("1.13132"))
    assert a.stop == b.stop == D("1.13050") and b.exit_reason == a.exit_reason == "CIBLE"
    # Same budget, loss estimated from E (closer to the stop): a larger size, never a larger budget.
    assert b.estimate.entry_estimate == D("1.13140") and b.size > a.size
    assert b.size * b.estimate.loss_account_per_contract <= b.risk_budget
    attempt = next(x for x in e3.attempts if x.at_d == ENTRY_DECIDED)
    assert got(attempt.decision)["limit"] == D("1.13140")
    assert got(attempt.decision)["deadline_utc"] == at(WINTER, 10, 10) + 9 * M5


def test_e3_is_cancelled_when_the_target_comes_first_and_never_fills_at_d(tmp_path: Path) -> None:
    after = [
        tick(at(WINTER, 10, 10), "1.13100"),  # exactly at D: replayed after the decision, never executes
        *fill(at(WINTER, 10, 10, 30), at(WINTER, 10, 40), "1.13180"),
        tick(at(WINTER, 10, 40), "1.13300"),  # target before any retest
        *fill(at(WINTER, 10, 40, 30), at(WINTER, 11, 30), "1.13130"),  # later retest: too late
        *fill(at(WINTER, 11, 30), at(WINTER, 17, 30), "1.13200"),
    ]
    e3 = run(tmp_path, e3_ticks(after), variant_params("E3"))
    assert not e3.trades
    attempt = next(x for x in e3.attempts if x.at_d == ENTRY_DECIDED)
    assert (attempt.entry_outcome, attempt.entry_outcome_utc) == (CANCELLED_TARGET, at(WINTER, 10, 40))
    assert attempt.ended_utc == at(WINTER, 10, 40)


def test_e3_expires_after_nine_trigger_candles_without_retest(tmp_path: Path) -> None:
    after = [*fill(at(WINTER, 10, 10, 0, 500), at(WINTER, 17, 30), "1.13170")]
    e3 = run(tmp_path, e3_ticks(after), variant_params("E3"))
    attempt = next(x for x in e3.attempts if x.at_d == ENTRY_DECIDED)
    assert (attempt.entry_outcome, attempt.entry_outcome_utc) == (EXPIRED, at(WINTER, 10, 55))
    assert not e3.trades


# ---------------------------------------------------------------- F2R: Failed 2 trigger in the flag


def f2_bars(low_10_00: str = "1.13095") -> tuple[dict[datetime, Any], dict[datetime, Any]]:
    m15, m5 = sheet_bars(WINTER)
    m5[at(WINTER, 9, 55)] = bar(at(WINTER, 9, 55), "1.13105", "1.13115", "1.13100", "1.13110", step=M5)
    m5[at(WINTER, 10, 0)] = bar(at(WINTER, 10, 0), "1.13108", "1.13112", low_10_00, "1.13105", step=M5)
    return m15, m5


def test_f2r_confirms_on_a_failed2_m5_inside_the_flag() -> None:
    m15, m5 = f2_bars()
    late = got(search(WINTER, m15, m5, params=LATE).configuration)
    f2r = got(search(WINTER, m15, m5, params=variant_params("F2R")).configuration)
    assert (late.outcome, late.ended_utc) == (EXIT, at(WINTER, 10, 10))  # the breakout of the sheet
    assert (f2r.outcome, f2r.ended_utc, f2r.detail) == (EXIT, at(WINTER, 10, 5), FAILED2_EXIT)
    assert f2r.flag_extreme == D("1.13075") and f2r.stop == D("1.13050") and f2r.target == D("1.13300")


def test_f2r_depth_first_and_no_failed2_without_the_previous_candle() -> None:
    m15, m5 = f2_bars(low_10_00="1.13055")  # Failed 2 shape, but below E - 0.5 I = 1.13060
    deep = got(search(WINTER, m15, m5, params=variant_params("F2R")).configuration)
    assert (deep.outcome, deep.ended_utc) == (TOO_DEEP, at(WINTER, 10, 5))
    m15, m5 = f2_bars()
    del m5[at(WINTER, 9, 55)]  # the candle ending at F is unknown: no Failed 2 on 10:00
    plain = got(search(WINTER, m15, m5, params=variant_params("F2R")).configuration)
    assert (plain.outcome, plain.ended_utc, plain.detail) == (EXIT, at(WINTER, 10, 10), None)


# ---------------------------------------------------------------- RSC: resume without a dead hour


def test_rsc_lets_earlier_candles_into_the_window_but_not_the_last_one() -> None:
    m15, m5 = sheet_bars(WINTER)
    resume = at(WINTER, 9, 5)
    late = search(WINTER, m15, m5, resume=resume, params=LATE)
    rsc = search(WINTER, m15, m5, resume=resume, params=variant_params("RSC"))
    assert late.configuration is None or late.configuration.recognised_utc >= at(WINTER, 10, 15)
    assert got(rsc.configuration).recognised_utc == at(WINTER, 9, 30)  # j = 09:15 starts after the resume
    assert rsc.examined == [] and got(rsc.configuration).origin_start == at(WINTER, 8, 45)
    later = search(WINTER, m15, m5, resume=at(WINTER, 9, 20), params=variant_params("RSC"))
    assert later.examined[0].t_utc == at(WINTER, 9, 45)  # j must start at 09:30 or after
    assert later.configuration is None or later.configuration.recognised_utc > at(WINTER, 9, 30)
    # The independent recomputation and the bound / reuse checks follow the same rule.
    params = variant_params("RSC")
    other = independent_first(WINTER, m15, lambda _c, _k: D("0.00100"), resume=resume, params=params)
    assert got(other)["t_j"] == at(WINTER, 9, 30)


# ---------------------------------------------------------------- M5S: one scale down


def m5s_bars() -> dict[datetime, Any]:
    rows = [
        ("1.13020", "1.13040", "1.13000", "1.13010"),
        ("1.13010", "1.13030", "1.12995", "1.13005"),
        ("1.13005", "1.13020", "1.12980", "1.13000"),
        ("1.13000", "1.13060", "1.12990", "1.13055"),
        ("1.13055", "1.13140", "1.13050", "1.13130"),
        ("1.13130", "1.13135", "1.13090", "1.13100"),
        ("1.13100", "1.13120", "1.13075", "1.13110"),
        ("1.13110", "1.13128", "1.13100", "1.13125"),
        ("1.13125", "1.13160", "1.13120", "1.13155"),
    ]
    out = {at(WINTER, 7, 0) + i * M5: flat(at(WINTER, 7, 0) + i * M5, "1.13010", M5) for i in range(7)}
    for i, prices in enumerate(rows):
        s = at(WINTER, 7, 35) + i * M5
        out[s] = bar(s, *prices, step=M5)
    return out


def test_m5s_reads_the_sheet_figure_on_m5_candles() -> None:
    m5 = m5s_bars()
    found = search(WINTER, m5, m5, params=variant_params("M5S"))
    c = got(found.configuration)
    assert c.recognised_utc == at(WINTER, 8, 0) and found.examined[0].t_utc == at(WINTER, 7, 20)
    assert (c.origin, c.origin_start, c.peak, c.peak_start) == (
        D("1.12980"),
        at(WINTER, 7, 45),
        D("1.13140"),
        at(WINTER, 7, 55),
    )
    assert c.pause_starts == [at(WINTER, 8, 0), at(WINTER, 8, 5)] and c.flag_utc == at(WINTER, 8, 10)
    assert c.deadline_utc == at(WINTER, 8, 30)  # end(p) + 30 min
    assert (c.outcome, c.ended_utc, c.stop, c.target) == (EXIT, at(WINTER, 8, 20), D("1.13050"), D("1.13300"))
    params = variant_params("M5S")
    other = independent_first(WINTER, m5, lambda _c, _k: D("0.00100"), params=params)
    assert got(other)["t_j"] == at(WINTER, 8, 0) and got(other)["F"] == at(WINTER, 8, 10)


def test_new_bounds_and_reuse_checks_accept_the_new_rules() -> None:
    from forex_bot.backtest.day02 import Search, Trigger
    from forex_bot.backtest.day02_availability import SearchLine, SessionPath

    m5 = m5s_bars()
    params = {t: variant_params("M5S", t) for t in Trigger}
    found = search(WINTER, m5, m5, params=params[Trigger.M5])
    path = SessionPath(WINTER, Trigger.M5, [SearchLine(at(WINTER, 7, 0), "début de séance", found)])
    assert bound_errors([path], m5, params) == [] and reuse_errors([path], params) == []
    m15, m5b = sheet_bars(WINTER)
    rsc = {t: variant_params("RSC", t) for t in Trigger}
    found = search(WINTER, m15, m5b, resume=at(WINTER, 9, 5), params=rsc[Trigger.M5])
    path = SessionPath(WINTER, Trigger.M5, [SearchLine(at(WINTER, 9, 5), "repli trop profond", found)])
    assert bound_errors([path], m15, rsc) == [] and reuse_errors([path], rsc) == []
    assert isinstance(found, Search)


# ---------------------------------------------------------------- causality of the new candle rules


@pytest.mark.parametrize(("name", "cut"), [("F2R", (9, 58)), ("F2R", (10, 5)), ("M5S", (8, 7)), ("M5S", (8, 15))])
def test_candles_after_an_instant_change_nothing_known_at_it(name: str, cut: tuple[int, int]) -> None:
    x = at(WINTER, *cut)
    params = variant_params(name)
    if name == "F2R":
        unit, trigger = f2_bars()
    else:
        unit = trigger = m5s_bars()
    full = search(WINTER, unit, trigger, params=params)
    for altered in (False, True):
        ku = {s: c for s, c in unit.items() if c["end_utc"] <= x}
        kt = {s: c for s, c in trigger.items() if c["end_utc"] <= x}
        if altered:
            ku |= {s: flat(s, "1.10000", c["end_utc"] - s) for s, c in unit.items() if c["end_utc"] > x}
            kt |= {s: flat(s, "1.10000", c["end_utc"] - s) for s, c in trigger.items() if c["end_utc"] > x}
        cut_search = search(WINTER, ku, kt, params=params)
        a, b = got(full.configuration), got(cut_search.configuration)
        assert a.recognised_utc == b.recognised_utc and (a.origin, a.peak) == (b.origin, b.peak)
        if got(b.ended_utc) <= x:
            assert (b.outcome, b.ended_utc, b.detail) == (a.outcome, a.ended_utc, a.detail)
        if got(a.ended_utc) <= x:
            assert (b.outcome, b.ended_utc, b.stop) == (a.outcome, a.ended_utc, a.stop)
    assert MIN == timedelta(minutes=1)


def test_m5s_reads_the_atr_at_the_start_of_the_m5_window_in_both_computations() -> None:
    m5 = m5s_bars()
    engine_calls: list[tuple[datetime, datetime]] = []
    recompute_calls: list[tuple[datetime, datetime]] = []

    def recorder(calls: list[tuple[datetime, datetime]]) -> Any:
        def atr(cutoff: datetime, known: datetime) -> D:
            calls.append((cutoff, known))
            return D("0.00100")

        return atr

    params = variant_params("M5S")
    search(WINTER, m5, m5, params=params, atr=recorder(engine_calls))
    independent_first(WINTER, m5, recorder(recompute_calls), params=params)
    assert engine_calls == recompute_calls
    assert all(known - cutoff == 4 * M5 for cutoff, known in engine_calls)
