"""DAY_02 volet C, SMT with GBP/USD (docs/experiments/DAY02_FREQUENCY_CAMPAIGN.md §4, ADR-039): SMTF, a
refusal at D when GBP/USD does not confirm the new EUR/USD extreme; SMTT, an exit confirmed when EUR/USD
sweeps the flag and GBP/USD does not. Each is LATE plus one change. Synthetic data only.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pytest
from test_day02 import CONFIG, WINTER, at, bar, candles, constant_atr, got, h1_bars, sheet_bars, sheet_ticks
from test_day02_frequency import f2_bars

from forex_bot.backtest.day01 import london
from forex_bot.backtest.day02 import (
    ENTRY_DECIDED,
    EXIT,
    SMT_DIVERGENCE,
    SMT_EXIT,
    SMT_UNDETERMINED,
    TOO_DEEP,
    Configuration,
    Day02Params,
    SmtBars,
    configuration_from,
    smt_refuses,
)
from forex_bot.backtest.day02_engine import Day02Backtest, Day02Result
from forex_bot.backtest.day02_variants import needs_smt, variant_params
from forex_bot.backtest.feed import Tick
from forex_bot.risk import Side

LATE, SMTF, SMTT = variant_params("LATE"), variant_params("SMTF"), variant_params("SMTT")
M5 = timedelta(minutes=5)
MIN = timedelta(minutes=1)
Bars = dict[datetime, dict[str, Any]]


def by_start(rows: list[dict[str, Any]]) -> Bars:
    return {b["start_utc"]: dict(b) for b in rows}


def engine_run(tmp_path: Path, ticks: list[Tick], params: Day02Params, smt: SmtBars | None) -> Day02Result:
    ticks = sorted(ticks, key=lambda t: t.ts_utc)
    m5, m15 = candles(tmp_path, ticks)
    return Day02Backtest(
        m5, m15, h1_bars(london(WINTER + timedelta(days=1), time(0)), days=6), ticks, [], params, CONFIG,
        start_utc=london(WINTER, time(0)), end_utc=london(WINTER + timedelta(days=1), time(0)), smt=smt,
    ).run()  # fmt: skip


def mirror(tmp_path: Path, ticks: list[Tick]) -> tuple[Bars, Bars]:
    """GBP/USD candles equal to the EUR/USD ones (a GBP/USD that confirms everything)."""
    m5, m15 = candles(tmp_path / "gbp", sorted(ticks, key=lambda t: t.ts_utc))
    return by_start(m5), by_start(m15)


def search_smt(m15: Bars, m5: Bars, gbp: SmtBars | None, params: Day02Params = SMTT) -> Configuration:
    return got(configuration_from(at(WINTER, 7, 0), WINTER, m15, m5, constant_atr(), params, None, gbp).configuration)


# ---------------------------------------------------------------- definitions


def test_smt_configurations_are_late_plus_their_switch_and_need_gbpusd(tmp_path: Path) -> None:
    for name, switch in (("SMTF", "smt_filter"), ("SMTT", "smt_trigger")):
        params = variant_params(name)
        assert {k for k, v in vars(params).items() if vars(LATE)[k] != v} == {switch}
        assert needs_smt(name)
    assert not needs_smt("LATE") and not needs_smt("G1A5B")
    m15, m5 = sheet_bars(WINTER)
    with pytest.raises(ValueError):
        configuration_from(at(WINTER, 7, 0), WINTER, m15, m5, constant_atr(), SMTT)
    with pytest.raises(ValueError):
        engine_run(tmp_path, sheet_ticks(WINTER), SMTF, None)


# ---------------------------------------------------------------- SMTF: refusal at D


def sheet_config() -> Configuration:
    m15, m5 = sheet_bars(WINTER)
    return got(configuration_from(at(WINTER, 7, 0), WINTER, m15, m5, constant_atr(), LATE).configuration)


def test_smtf_reads_gbpusd_highs_from_o_to_p_against_m5_highs_from_f_to_d() -> None:
    config = sheet_config()  # long, o = 08:45, p = 09:15, F = 10:00, D = 10:10
    assert (config.origin_start, config.peak_start, config.flag_utc, config.d_utc) == (
        at(WINTER, 8, 45), at(WINTER, 9, 15), at(WINTER, 10, 0), at(WINTER, 10, 10),
    )  # fmt: skip
    gbp15 = {
        at(WINTER, 8, 45) + 15 * i * MIN: bar(at(WINTER, 8, 45) + 15 * i * MIN, "1.27", "1.2710", "1.2690", "1.27")
        for i in range(3)
    }
    gbp15[at(WINTER, 9, 0)]["bid_high"] = D("1.2720")  # highest GBP/USD high of the impulse
    m5 = {s: bar(s, "1.27", "1.2715", "1.2700", "1.27", step=M5) for s in (at(WINTER, 10, 0), at(WINTER, 10, 5))}
    assert smt_refuses(config, SmtBars(gbp15, m5), SMTF) is True  # 1.2715 <= 1.2720: no confirmation
    m5[at(WINTER, 10, 5)]["bid_high"] = D("1.2721")
    assert smt_refuses(config, SmtBars(gbp15, m5), SMTF) is False  # GBP/USD makes its new high too
    m5[at(WINTER, 10, 5)]["bid_high"] = D("1.2720")
    assert smt_refuses(config, SmtBars(gbp15, m5), SMTF) is True  # equality does not exceed
    # A compared candle absent or not OK: undetermined. Candles after D are never read.
    m5[at(WINTER, 10, 10)] = bar(at(WINTER, 10, 10), "1.27", "1.2800", "1.27", "1.27", step=M5)
    assert smt_refuses(config, SmtBars(gbp15, m5), SMTF) is True
    del gbp15[at(WINTER, 9, 15)]
    assert smt_refuses(config, SmtBars(gbp15, m5), SMTF) is None
    gbp15[at(WINTER, 9, 15)] = bar(at(WINTER, 9, 15), "1.27", "1.2710", "1.2690", "1.27", ok=False)
    assert smt_refuses(config, SmtBars(gbp15, m5), SMTF) is None


def test_smtf_short_is_symmetric_on_the_lows() -> None:
    origin, peak = (D("1.1320"), at(WINTER, 8, 45)), (D("1.1300"), at(WINTER, 9, 15))
    config = Configuration(Side.SHORT, at(WINTER, 9, 30), D("0.001"), *origin, *peak, flag_utc=at(WINTER, 10, 0))
    config.ended_utc, config.outcome = at(WINTER, 10, 10), EXIT
    gbp15 = {
        at(WINTER, 8, 45) + 15 * i * MIN: bar(at(WINTER, 8, 45) + 15 * i * MIN, "1.27", "1.2710", "1.2690", "1.27")
        for i in range(3)
    }
    m5 = {s: bar(s, "1.27", "1.2710", "1.2695", "1.27", step=M5) for s in (at(WINTER, 10, 0), at(WINTER, 10, 5))}
    assert smt_refuses(config, SmtBars(gbp15, m5), SMTF) is True  # 1.2695 >= 1.2690
    m5[at(WINTER, 10, 0)]["bid_low"] = D("1.2689")
    assert smt_refuses(config, SmtBars(gbp15, m5), SMTF) is False


def test_smtf_refuses_in_the_engine_and_takes_the_trade_when_gbpusd_confirms(tmp_path: Path) -> None:
    ticks = sheet_ticks(WINTER)
    m5, m15 = mirror(tmp_path, ticks)
    confirmed = engine_run(tmp_path / "a", ticks, SMTF, SmtBars(m15, m5))
    late = engine_run(tmp_path / "b", ticks, LATE, None)
    assert len(confirmed.trades) == len(late.trades) == 1
    assert confirmed.trades[0].entry_utc == late.trades[0].entry_utc
    for s in (at(WINTER, 10, 0), at(WINTER, 10, 5)):
        m5[s]["bid_high"] = D("1.13130")  # below the GBP/USD impulse high 1.13140
    refused = engine_run(tmp_path / "c", ticks, SMTF, SmtBars(m15, m5))
    assert not refused.trades
    attempt = next(a for a in refused.attempts if a.at_d is not None)
    assert attempt.at_d == SMT_DIVERGENCE and attempt.ended_utc == at(WINTER, 10, 10)  # the search resumes at D
    del m15[at(WINTER, 9, 0)]
    undetermined = engine_run(tmp_path / "d", ticks, SMTF, SmtBars(m15, m5))
    attempt = next(a for a in undetermined.attempts if a.at_d is not None)
    assert attempt.at_d == ENTRY_DECIDED and SMT_UNDETERMINED in attempt.events and len(undetermined.trades) == 1


# ---------------------------------------------------------------- SMTT: SMT trigger in the flag


def smt_bars(low_10_00: str = "1.13070") -> tuple[Bars, Bars]:
    """Sheet candles; the M5 10:00 makes a new flag low (pauses: 1.13090, 1.13075), above E - 0.5 I."""
    m15, m5 = sheet_bars(WINTER)
    m5[at(WINTER, 10, 0)] = bar(at(WINTER, 10, 0), "1.13110", "1.13120", low_10_00, "1.13105", step=M5)
    return m15, m5


def gbp_of(m15: Bars, m5: Bars, low_10_00: str | None) -> SmtBars:
    gbp5 = {s: dict(b) for s, b in m5.items()}
    if low_10_00 is None:
        del gbp5[at(WINTER, 10, 0)]
    else:
        gbp5[at(WINTER, 10, 0)]["bid_low"] = D(low_10_00)
    return SmtBars({s: dict(b) for s, b in m15.items()}, gbp5)


def test_smtt_confirms_when_eurusd_sweeps_the_flag_and_gbpusd_does_not() -> None:
    m15, m5 = smt_bars()
    late = search_smt(m15, m5, None, LATE)
    assert (late.outcome, late.ended_utc, late.detail) == (EXIT, at(WINTER, 10, 10), None)
    smtt = search_smt(m15, m5, gbp_of(m15, m5, "1.13080"))  # GBP/USD stays above its pause low 1.13075
    assert (smtt.outcome, smtt.ended_utc, smtt.detail) == (EXIT, at(WINTER, 10, 5), SMT_EXIT)
    assert smtt.flag_extreme == D("1.13070") and smtt.stop == D("1.13045") and smtt.target == D("1.13300")
    assert smtt.smt_undetermined == 0
    # Equality with the GBP/USD flag low is not a new low: still a divergence.
    assert search_smt(m15, m5, gbp_of(m15, m5, "1.13075")).detail == SMT_EXIT


def test_smtt_no_divergence_undetermined_and_depth_first() -> None:
    m15, m5 = smt_bars()
    both = search_smt(m15, m5, gbp_of(m15, m5, "1.13074"))  # GBP/USD makes its new low too
    assert (both.outcome, both.ended_utc, both.detail) == (EXIT, at(WINTER, 10, 10), None)
    missing = search_smt(m15, m5, gbp_of(m15, m5, None))
    assert (missing.ended_utc, missing.detail, missing.smt_undetermined) == (at(WINTER, 10, 10), None, 1)
    m15d, m5d = smt_bars(low_10_00="1.13055")  # below E - 0.5 I = 1.13060: too deep before any SMT
    deep = search_smt(m15d, m5d, gbp_of(m15d, m5d, "1.13080"))
    assert (deep.outcome, deep.ended_utc) == (TOO_DEEP, at(WINTER, 10, 5))
    # No new EUR/USD low: the GBP/USD candles are irrelevant (the F2R shape of the frequency lot is not an SMT).
    m15f, m5f = f2_bars()
    plain = search_smt(m15f, m5f, gbp_of(m15f, m5f, None))
    assert (plain.ended_utc, plain.detail, plain.smt_undetermined) == (at(WINTER, 10, 10), None, 0)


def test_smtt_reads_nothing_after_the_candle_it_dates() -> None:
    m15, m5 = smt_bars()
    gbp = gbp_of(m15, m5, "1.13080")
    first = search_smt(m15, m5, gbp)
    later = {s: b for s, b in gbp.trigger.items() if s < at(WINTER, 10, 5)}  # GBP/USD after k removed
    m5_cut = {s: b for s, b in m5.items() if s < at(WINTER, 10, 5)}
    again = search_smt(m15, m5_cut, SmtBars(gbp.m15, later))
    assert first == again
