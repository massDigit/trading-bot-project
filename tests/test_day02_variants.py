"""Exploratory DAY_02 variants H1-H3 on synthetic data (docs/experiments/DAY02_IMPROVEMENT_CAMPAIGN.md).

Each hypothesis is checked on hand-written candles against explicit expected values, then for
causality: candles, ticks or H4 after an instant T change nothing decided or recorded up to T. The
reference parameters are checked unchanged by the existing tests (test_day02*.py), which still pass.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pytest
from test_day02 import (
    CONFIG,
    MIN,
    SPREAD,
    WINTER,
    at,
    bar,
    candles,
    fill,
    flat,
    got,
    h1_bars,
    search,
    sheet_bars,
    sheet_ticks,
)

from forex_bot.backtest.day01 import london
from forex_bot.backtest.day02 import (
    CONTEXT_AGAINST,
    CONTEXT_UNAVAILABLE,
    DEEP_BEFORE_RECOGNITION,
    ENTRY_DECIDED,
    EXIT,
    PEAK_BEFORE_END,
    TOO_DEEP,
    Context,
    Day02Params,
    Search,
    configuration_from,
)
from forex_bot.backtest.day02_availability import first_configuration_view, independent_first
from forex_bot.backtest.day02_engine import Day02Backtest, Day02Result
from forex_bot.backtest.day02_variants import REFERENCE, VARIANTS, needs_h4, variant_of, variant_params
from forex_bot.backtest.feed import Tick
from forex_bot.history.calendar import MarketState, market_state
from forex_bot.risk import Side

H1 = variant_params("H1")
H2 = variant_params("H2")
H3 = variant_params("H3")


def ctx(sign: int | None, calls: list[tuple[datetime, datetime]] | None = None) -> Callable[..., int | None]:
    def context(cutoff: datetime, known: datetime) -> int | None:
        if calls is not None:
            calls.append((cutoff, known))
        return sign

    return context


def run_search(
    m15: dict[datetime, Any], m5: dict[datetime, Any], params: Day02Params, context: Callable[..., int | None]
) -> Search:
    return configuration_from(at(WINTER, 7, 0), WINTER, m15, m5, lambda c, k: D("0.00100"), params, context)


# ---------------------------------------------------------------- registry


def test_registry_has_the_reference_and_seven_variants_with_one_definition_each() -> None:
    assert list(VARIANTS) == ["REF", "H1", "H2", "H3", "H1H2", "H1H3", "H2H3", "H1H2H3", "LATE", "PROT", "PART", "FULL"]
    assert variant_params(REFERENCE) == Day02Params()  # the frozen reference is untouched
    for name in VARIANTS:
        assert variant_of(variant_params(name)) == name
    p = variant_params("H1H2H3")
    assert (p.deferred_recognition, p.depth_on_close, p.context) == (True, True, Context.H4_SMA_SLOPE)
    assert [n for n in VARIANTS if needs_h4(n)] == ["H3", "H1H3", "H2H3", "H1H2H3"]
    # Every other value is the reference's.
    diff = {k for k, v in vars(p).items() if vars(Day02Params())[k] != v}
    assert diff == {"deferred_recognition", "depth_on_close", "context"}


# ---------------------------------------------------------------- H1: deferred recognition

# Peak at 09:15 with a weak close (amplitude 9 pips at its close); the 09:30 pause closes strong.
WEAK_PEAK = {
    (9, 15): ("1.13055", "1.13140", "1.13050", "1.13070"),
    (9, 30): ("1.13070", "1.13135", "1.13065", "1.13130"),
}


def test_h1_recognises_after_the_peak_when_the_last_close_holds_the_impulse() -> None:
    m15, m5 = sheet_bars(WINTER, WEAK_PEAK)
    reference = search(WINTER, m15, m5)
    examined = {e.t_utc: e.cause for e in reference.examined}
    assert examined[at(WINTER, 9, 45)].startswith(f"hausse : {PEAK_BEFORE_END}")
    found = search(WINTER, m15, m5, params=H1)
    config = got(found.configuration)
    # Recognised at the close of 09:30 (t_j = 09:45), never at the peak close 09:30 itself.
    assert config.recognised_utc == at(WINTER, 9, 45) and config.peak_start == at(WINTER, 9, 15)
    assert (config.origin, config.peak, config.origin_start) == (D("1.12980"), D("1.13140"), at(WINTER, 8, 45))
    # The 09:30 candle, closed at t_j, is the first pause; 09:45 the second: F = 10:00.
    assert config.pause_starts == [at(WINTER, 9, 30), at(WINTER, 9, 45)]
    assert config.flag_utc == at(WINTER, 10, 0) and config.deadline_utc == at(WINTER, 11, 0)
    assert config.outcome == EXIT and config.d_utc == at(WINTER, 10, 10)
    assert config.flag_extreme == D("1.13065") and config.stop == D("1.13040") and config.target == D("1.13300")
    # Same reading by the separate recomputation (C6).
    other = independent_first(WINTER, m15, lambda c, k: D("0.00100"), params=H1)
    assert first_configuration_view(config) == other


# Origin 08:30, peak 08:45 (weak close), two pauses 09:00 and 09:15, the second closing strong.
TWO_PAUSES = {
    (8, 30): ("1.13010", "1.13030", "1.13000", "1.13020"),
    (8, 45): ("1.13020", "1.13200", "1.13015", "1.13120"),
    (9, 0): ("1.13120", "1.13160", "1.13110", "1.13130"),
    (9, 15): ("1.13130", "1.13190", "1.13120", "1.13180"),
}


def test_h1_with_two_pauses_already_closed_forms_the_flag_at_t_j_never_before() -> None:
    m15, _ = sheet_bars(WINTER, TWO_PAUSES)
    m5 = {at(WINTER, 9, 30): bar(at(WINTER, 9, 30), "1.13180", "1.13220", "1.13175", "1.13215", step=5 * MIN)}
    found = search(WINTER, m15, m5, params=H1)
    config = got(found.configuration)
    assert config.recognised_utc == at(WINTER, 9, 30) and config.peak_start == at(WINTER, 8, 45)
    assert config.pause_starts == [at(WINTER, 9, 0), at(WINTER, 9, 15)]
    # The second pause ended at 09:30 = t_j: F is t_j, the instant the flag is known.
    assert config.flag_utc == config.recognised_utc
    # The exit is read on the M5 starting at t_j or later only: D = 09:35 > t_j.
    assert config.outcome == EXIT and config.d_utc == at(WINTER, 9, 35)
    assert config.stop == D("1.13110") - D("0.00025") and config.target == D("1.13400")
    assert config.deadline_utc == at(WINTER, 9, 0) + timedelta(minutes=90)
    other = independent_first(WINTER, m15, lambda c, k: D("0.00100"), params=H1)
    assert first_configuration_view(config) == other
    # Not recognised at 09:15: the 09:00 close (1.13130) gives 13 pips < 1.5 A.
    examined = {e.t_utc: e.cause for e in found.examined}
    assert "amplitude insuffisante" in examined[at(WINTER, 9, 15)]


def test_h1_refuses_a_pause_closed_before_t_j_that_breaks_the_depth() -> None:
    deep = WEAK_PEAK | {(9, 30): ("1.13070", "1.13135", "1.13055", "1.13130")}  # low < 1.13060
    m15, m5 = sheet_bars(WINTER, deep)
    examined = {e.t_utc: e.cause for e in search(WINTER, m15, m5, params=H1).examined}
    assert examined[at(WINTER, 9, 45)].startswith(f"hausse : {DEEP_BEFORE_RECOGNITION}")
    # H2 reads that depth on the close (1.13130): the same impulse is recognised.
    both = variant_params("H1H2")
    config = got(search(WINTER, m15, m5, params=both).configuration)
    assert config.recognised_utc == at(WINTER, 9, 45) and config.flag_extreme == D("1.13055")


def test_h1_keeps_the_reference_path_when_the_peak_is_the_last_candle() -> None:
    m15, m5 = sheet_bars(WINTER)
    assert search(WINTER, m15, m5, params=H1).configuration == search(WINTER, m15, m5).configuration


# ---------------------------------------------------------------- H2: depth on the close


def test_h2_a_wick_below_the_limit_with_a_close_above_is_a_pause() -> None:
    m15, m5 = sheet_bars(WINTER, {(9, 45): ("1.13100", "1.13120", "1.13055", "1.13110")})
    assert got(search(WINTER, m15, m5).configuration).outcome == TOO_DEEP
    config = got(search(WINTER, m15, m5, params=H2).configuration)
    assert config.pause_starts == [at(WINTER, 9, 30), at(WINTER, 9, 45)] and config.flag_utc == at(WINTER, 10, 0)
    # The stop stays beyond the flag extreme, wick included.
    assert config.outcome == EXIT and config.flag_extreme == D("1.13055") and config.stop == D("1.13030")


def test_h2_a_new_high_with_a_wick_below_and_a_close_above_is_an_extension() -> None:
    m15, m5 = sheet_bars(WINTER, {(9, 45): ("1.13100", "1.13145", "1.13055", "1.13110")})
    config = got(search(WINTER, m15, m5, params=H2).configuration)
    assert config.extensions == [at(WINTER, 9, 45)] and config.peak == D("1.13145")


def test_h2_a_close_below_the_limit_invalidates_with_priority_over_an_extension() -> None:
    m15, m5 = sheet_bars(WINTER, {(9, 45): ("1.13100", "1.13145", "1.13050", "1.13058")})
    config = got(search(WINTER, m15, m5, params=H2).configuration)
    assert config.outcome == TOO_DEEP and config.ended_utc == at(WINTER, 10, 0) and config.extensions == []


def test_h2_trigger_candle_wick_below_the_limit_still_confirms_the_exit() -> None:
    m15, m5 = sheet_bars(WINTER)
    m5[at(WINTER, 10, 5)] = bar(at(WINTER, 10, 5), "1.13125", "1.13160", "1.13055", "1.13155", step=5 * MIN)
    assert got(search(WINTER, m15, m5).configuration).outcome == TOO_DEEP
    config = got(search(WINTER, m15, m5, params=H2).configuration)
    assert config.outcome == EXIT and config.d_utc == at(WINTER, 10, 10) and config.stop == D("1.13030")
    m5[at(WINTER, 10, 5)] = bar(at(WINTER, 10, 5), "1.13125", "1.13130", "1.13050", "1.13058", step=5 * MIN)
    assert got(search(WINTER, m15, m5, params=H2).configuration).outcome == TOO_DEEP


def test_h2_mirrored_for_a_sale_reads_the_bid_close_above_the_limit() -> None:
    def mirror(p: str) -> str:
        return str(D("2.26000") - D(p))

    m15, m5 = sheet_bars(WINTER, {(9, 45): ("1.13100", "1.13120", "1.13055", "1.13110")})
    flip = {
        s: bar(s, mirror(b["bid_open"]), mirror(b["bid_low"]), mirror(b["bid_high"]), mirror(b["bid_close"]))
        for s, b in m15.items()
    }
    flip5 = {
        s: bar(s, mirror(b["bid_open"]), mirror(b["bid_low"]), mirror(b["bid_high"]), mirror(b["bid_close"]), 5 * MIN)
        for s, b in m5.items()
    }
    assert got(search(WINTER, flip, flip5).configuration).outcome == TOO_DEEP
    config = got(search(WINTER, flip, flip5, params=H2).configuration)
    assert config.side is Side.SHORT and config.outcome == EXIT
    assert config.flag_extreme == D(mirror("1.13055")) + SPREAD  # ask_high of the flag, wick included


# ---------------------------------------------------------------- H3: H4 context


def test_h3_admits_only_the_direction_of_the_context_read_on_the_window_start() -> None:
    m15, m5 = sheet_bars(WINTER)
    calls: list[tuple[datetime, datetime]] = []
    config = got(run_search(m15, m5, H3, ctx(1, calls)).configuration)
    assert config.side is Side.LONG and config.recognised_utc == at(WINTER, 9, 30)
    assert calls == [(at(WINTER, 8, 30), at(WINTER, 9, 30))]  # read only once an impulse is found
    for sign, cause in ((-1, CONTEXT_AGAINST), (0, CONTEXT_AGAINST), (None, CONTEXT_UNAVAILABLE)):
        found = run_search(m15, m5, H3, ctx(sign))
        examined = {e.t_utc: e.cause for e in found.examined}
        assert examined[at(WINTER, 9, 30)] == cause
        assert found.configuration is None or found.configuration.recognised_utc > at(WINTER, 9, 30)
    # Without a context switch, the context is never read.
    unused: list[tuple[datetime, datetime]] = []
    assert run_search(m15, m5, Day02Params(), ctx(-1, unused)).configuration == search(WINTER, m15, m5).configuration
    assert unused == []


def h4_bars(
    first: datetime, count: int, closes: Callable[[int], D], bad: set[int] | None = None
) -> list[dict[str, Any]]:
    """Expected-open H4 from `first` (22:00 UTC anchor in winter), one every 4 h, weekend skipped."""
    out: list[dict[str, Any]] = []
    cursor, i = first, 0
    while len(out) < count:
        if market_state(cursor) is MarketState.OPEN:
            c = closes(i)
            ok = i not in (bad or set())
            out.append(
                {
                    "start_utc": cursor,
                    "end_utc": cursor + timedelta(hours=4),
                    "bid_open": c,
                    "bid_high": c + D("0.001"),
                    "bid_low": c - D("0.001"),
                    "bid_close": c,
                    "flags_at_close": [] if ok else ["trou de cotation > 10 min pendant l'ouverture prévue"],
                    "complete_at_close": ok,
                }
            )
            i += 1
        cursor += timedelta(hours=4)
    return out


FIRST_H4 = datetime(2019, 2, 3, 22, tzinfo=UTC)  # Sunday 17:00 New York, winter: the H4 anchor


def context_engine(h4: list[dict[str, Any]], params: Day02Params = H3) -> Day02Backtest:
    return Day02Backtest([], [], h1_bars(london(WINTER, time(0))), [], [], params, CONFIG, h4=h4)


def test_h3_context_sign_of_the_twenty_h4_slope_on_closed_contiguous_usable_bars() -> None:
    first = FIRST_H4
    cutoff = at(WINTER, 8, 30)
    up = h4_bars(first, 60, lambda i: D("1.10000") + D("0.0001") * i)
    down = h4_bars(first, 60, lambda i: D("1.20000") - D("0.0001") * i)
    flat_h4 = h4_bars(first, 60, lambda i: D("1.10000"))
    assert context_engine(up).context_at(cutoff, at(WINTER, 9, 30)) == 1
    assert context_engine(down).context_at(cutoff, at(WINTER, 9, 30)) == -1
    assert context_engine(flat_h4).context_at(cutoff, at(WINTER, 9, 30)) == 0
    # Only H4 ended by the cutoff: a later H4 (here, the one in progress) changes nothing.
    ended = [b for b in up if b["end_utc"] <= cutoff]
    crash = [*ended, *({**b, "bid_close": D("0.5")} for b in up if b["end_utc"] > cutoff)]
    assert context_engine(crash).context_at(cutoff, at(WINTER, 9, 30)) == 1
    # Sign of close(k) - close(k - 20): only the two ends matter when every bar is usable.
    k = len(ended) - 1
    bumped = [{**b, "bid_close": D("1.30")} if i == k - 10 else b for i, b in enumerate(ended)]
    assert context_engine(bumped).context_at(cutoff, at(WINTER, 9, 30)) == 1
    # Not computable: fewer than 21 H4, an unusable H4, an absent expected H4.
    assert context_engine(ended[-20:]).context_at(cutoff, at(WINTER, 9, 30)) is None
    unusable = [{**b, "complete_at_close": False} if i == k - 5 else b for i, b in enumerate(ended)]
    assert context_engine(unusable).context_at(cutoff, at(WINTER, 9, 30)) is None
    holed = [b for i, b in enumerate(ended) if i != k - 5]
    assert context_engine(holed).context_at(cutoff, at(WINTER, 9, 30)) is None
    with pytest.raises(ValueError):
        context_engine([])


# ---------------------------------------------------------------- causality of the candle rules


@pytest.mark.parametrize("name", ["H1", "H2", "H1H2"])
@pytest.mark.parametrize("cut", [(9, 40), (9, 50), (10, 7)])
def test_variant_candles_after_an_instant_change_nothing_known_at_it(name: str, cut: tuple[int, int]) -> None:
    params, x = variant_params(name), at(WINTER, *cut)
    m15, m5 = sheet_bars(WINTER, WEAK_PEAK)
    full = search(WINTER, m15, m5, params=params)
    for altered in (False, True):
        k15 = {s: c for s, c in m15.items() if c["end_utc"] <= x}
        k5 = {s: c for s, c in m5.items() if c["end_utc"] <= x}
        if altered:
            k15 |= {s: flat(s, "1.10000") for s, c in m15.items() if c["end_utc"] > x}
            k5 |= {s: flat(s, "1.10000", 5 * MIN) for s, c in m5.items() if c["end_utc"] > x}
        other = search(WINTER, k15, k5, params=params)
        assert [e for e in full.examined if e.t_utc <= x] == [e for e in other.examined if e.t_utc <= x]
        a, b = full.configuration, other.configuration
        if a is not None and a.recognised_utc <= x:
            b = got(b)
            assert (a.recognised_utc, a.origin, a.peak, a.peak_start) == (
                b.recognised_utc,
                b.origin,
                b.peak,
                b.peak_start,
            )
            if b.ended_utc is not None and b.ended_utc <= x:
                assert (b.outcome, b.ended_utc, b.stop) == (a.outcome, a.ended_utc, a.stop)
        else:
            assert b is None or b.recognised_utc > x


def test_no_event_of_any_variant_is_dated_before_its_recognition() -> None:
    for name in ("H1", "H2", "H1H2"):
        for rows in (WEAK_PEAK, TWO_PAUSES, {}):
            m15, m5 = sheet_bars(WINTER, rows)
            m5 |= {at(WINTER, 9, 30): bar(at(WINTER, 9, 30), "1.13180", "1.13220", "1.13175", "1.13215", 5 * MIN)}
            c = search(WINTER, m15, m5, params=variant_params(name)).configuration
            if c is None:
                continue
            assert got(c.ended_utc) >= c.recognised_utc
            assert c.flag_utc is None or c.flag_utc >= c.recognised_utc
            assert c.d_utc is None or c.d_utc > c.recognised_utc


# ---------------------------------------------------------------- engine: variants and causality


def run_variant(
    tmp_path: Path, ticks: list[Tick], params: Day02Params, h4: list[dict[str, Any]] | None = None
) -> Day02Result:
    ticks = sorted(ticks, key=lambda t: t.ts_utc)
    m5, m15 = candles(tmp_path, ticks)
    engine = Day02Backtest(
        m5,
        m15,
        h1_bars(london(WINTER + timedelta(days=1), time(0)), days=6),
        ticks,
        [],
        params,
        CONFIG,
        start_utc=london(WINTER, time(0)),
        end_utc=london(WINTER + timedelta(days=1), time(0)),
        h4=h4 or [],
    )
    return engine.run()


UP_H4 = h4_bars(FIRST_H4, 70, lambda i: D("1.10000") + D("0.0001") * i)


@pytest.mark.parametrize("name", ["H1", "H2", "H3", "H1H2H3"])
def test_engine_variant_decides_and_executes_after_recognition(tmp_path: Path, name: str) -> None:
    params = variant_params(name)
    result = run_variant(tmp_path, sheet_ticks(WINTER), params, UP_H4 if needs_h4(name) else None)
    first = result.attempts[0]
    config = got(first.search.configuration)
    assert first.at_d == ENTRY_DECIDED and got(config.d_utc) > config.recognised_utc
    (trade,) = result.trades
    assert trade.entry_utc > got(config.d_utc) and trade.decided_utc == config.d_utc
    # Same path as the reference on the sheet example (the peak is the last candle, no wick, context up).
    reference = run_variant(tmp_path / "ref", sheet_ticks(WINTER), Day02Params())
    assert [t.entry_utc for t in result.trades] == [t.entry_utc for t in reference.trades]


@pytest.mark.parametrize("name", ["H1H2H3"])
@pytest.mark.parametrize("cut", [(9, 50), (10, 12)])
def test_engine_variant_ticks_candles_and_h4_after_an_instant_change_nothing_known_at_it(
    tmp_path: Path, name: str, cut: tuple[int, int]
) -> None:
    params, x = variant_params(name), at(WINTER, *cut)
    full = sheet_ticks(WINTER, changes=WEAK_PEAK)
    h4_cut = [b for b in UP_H4 if b["end_utc"] <= x]
    h4_changed = [*h4_cut, *({**b, "bid_close": D("0.5")} for b in UP_H4 if b["end_utc"] > x)]
    reference = run_variant(tmp_path / "full", full, params, UP_H4)
    cases = {
        "cut": ([t for t in full if t.ts_utc < x], h4_cut),
        "changed": ([t for t in full if t.ts_utc < x] + fill(x, at(WINTER, 17, 30), "1.12900"), h4_changed),
    }
    for case, (ticks, h4) in cases.items():
        other = run_variant(tmp_path / case, ticks, params, h4)
        a, b = reference.attempts[0], other.attempts[0]
        assert [e for e in a.search.examined if e.t_utc <= x] == [e for e in b.search.examined if e.t_utc <= x]
        ca = a.search.configuration
        if ca is not None and ca.recognised_utc <= x:
            cb = got(b.search.configuration)
            assert (ca.recognised_utc, ca.origin, ca.peak) == (cb.recognised_utc, cb.origin, cb.peak)
            if ca.d_utc is not None and ca.d_utc <= x:
                assert (cb.d_utc, cb.stop, cb.target) == (ca.d_utc, ca.stop, ca.target)
                assert a.decision == b.decision
        assert [j for j in reference.journal if j.utc < x] == [j for j in other.journal if j.utc < x]
        assert [t for t in reference.trades if got(t.exit_utc) < x] == [t for t in other.trades if got(t.exit_utc) < x]
