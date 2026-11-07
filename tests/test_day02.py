"""DAY_02 rules and engine on synthetic data (docs/strategies/DAY_02_FLAG_CONTINUATION.md, ADR-026 to 028).

Two kinds of tests:
- the candle rules (`configuration_from`) on hand-written candles, compared with explicit expected
  values (the example of the sheet §11 and its limit cases), never with another run of the same code;
- the engine on M5 and M15 built by the real builder from the very ticks that the engine replays,
  under the DAY_01 convention extended to DAY_02 (silence > 5 min, empty sub-slot not OK).

The H1 for the ATR are synthetic, with the schema of `history.bars.build_bars`: every true range is
0.00100 around 1.13000, hence A = 0.00100 (10 pips) as in the sheet §11. Spread 0.2 pip everywhere.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pytest

from forex_bot.backtest.day01 import london
from forex_bot.backtest.day02 import (
    AMPLITUDE,
    CANCELLED_INTERRUPTION,
    ENTRY_DECIDED,
    EXECUTED,
    EXIT,
    EXPIRED,
    FLAG_DATA,
    LIQUIDATION,
    ORDER,
    PEAK_BEFORE_END,
    POSITION_CLOSED,
    PROLONGED,
    REJECTED_AT_EXECUTION,
    SESSION_START,
    SIZE_REFUSED,
    STOP_AT_EXECUTION,
    TIME_EXIT,
    TOO_DEEP,
    TOO_LONG,
    UNPLANNED_NIGHT,
    WEAK_CLOSE,
    WINDOW_DATA,
    WINDOW_END,
    Day02Params,
    Search,
    Trigger,
    ceil_m15,
    configuration_from,
)
from forex_bot.backtest.day02_engine import Day02Backtest, Day02Result
from forex_bot.backtest.engine import ResearchConfig, StopAtExecution
from forex_bot.backtest.explore import RESEARCH_COSTS
from forex_bot.backtest.feed import Silence, Tick
from forex_bot.backtest.s2 import GapScenario
from forex_bot.history.calendar import MarketState, market_state
from forex_bot.history.intraday import DAY01_5MIN, Grid, build_intraday
from forex_bot.history.store import HistoryStore, IngestRequest
from forex_bot.risk import Side

WINTER = date(2019, 2, 12)  # Tuesday, GMT: London = UTC (sheet §11)
SUMMER = date(2019, 7, 9)  # Tuesday, BST: London = UTC + 1
SPREAD = D("0.00002")
A = D("0.00100")
MIN = timedelta(minutes=1)
SEC = timedelta(seconds=1)
CONFIG = ResearchConfig(costs=RESEARCH_COSTS)


def at(day: date, hh: int, mm: int, ss: int = 0, ms: int = 0) -> datetime:
    return london(day, time(hh, mm, ss, ms * 1000))


def got[T](value: T | None) -> T:
    assert value is not None
    return value


# ---------------------------------------------------------------- hand-written candles


def bar(
    start: datetime, o: str, h: str, low: str, c: str, step: timedelta = timedelta(minutes=15), ok: bool = True
) -> dict[str, Any]:
    prices = {"open": D(o), "high": D(h), "low": D(low), "close": D(c)}
    out: dict[str, Any] = {"start_utc": start, "end_utc": start + step, "complete_at_close": ok}
    for name, value in prices.items():
        out[f"bid_{name}"], out[f"ask_{name}"] = value, value + SPREAD
    return out


def flat(start: datetime, price: str, step: timedelta = timedelta(minutes=15)) -> dict[str, Any]:
    return bar(start, price, price, price, price, step)


# The M15 of the sheet §11, from 08:15 to 10:00 London.
SHEET_M15 = [
    ((8, 15), ("1.13020", "1.13040", "1.13000", "1.13010")),
    ((8, 30), ("1.13010", "1.13030", "1.12995", "1.13005")),
    ((8, 45), ("1.13005", "1.13020", "1.12980", "1.13000")),
    ((9, 0), ("1.13000", "1.13060", "1.12990", "1.13055")),
    ((9, 15), ("1.13055", "1.13140", "1.13050", "1.13130")),
    ((9, 30), ("1.13130", "1.13135", "1.13090", "1.13100")),
    ((9, 45), ("1.13100", "1.13120", "1.13075", "1.13110")),
]
SHEET_M5 = [
    ((10, 0), ("1.13110", "1.13128", "1.13100", "1.13125")),
    ((10, 5), ("1.13125", "1.13160", "1.13120", "1.13155")),
]


def sheet_bars(
    day: date, m15_changes: dict[tuple[int, int], tuple[str, str, str, str]] | None = None
) -> tuple[dict[datetime, dict[str, Any]], dict[datetime, dict[str, Any]]]:
    """M15 from 07:00 (flat at 1.13010 before 08:15) and the M5 of the sheet §11."""
    rows = dict(SHEET_M15) | (m15_changes or {})
    m15 = {
        at(day, 7, 0) + i * timedelta(minutes=15): flat(at(day, 7, 0) + i * timedelta(minutes=15), "1.13010")
        for i in range(5)
    }
    for (hh, mm), prices in rows.items():
        m15[at(day, hh, mm)] = bar(at(day, hh, mm), *prices)
    m5 = {at(day, hh, mm): bar(at(day, hh, mm), *prices, step=timedelta(minutes=5)) for (hh, mm), prices in SHEET_M5}
    return m15, m5


def constant_atr(calls: list[tuple[datetime, datetime]] | None = None) -> Callable[[datetime, datetime], D | None]:
    def atr(cutoff: datetime, known: datetime) -> D | None:
        if calls is not None:
            calls.append((cutoff, known))
        return A

    return atr


def search(
    day: date,
    m15: dict[datetime, Any],
    trigger: dict[datetime, Any],
    resume: datetime | None = None,
    params: Day02Params | None = None,
    atr: Callable[[datetime, datetime], D | None] | None = None,
) -> Search:
    return configuration_from(
        resume or at(day, 7, 0), day, m15, trigger, atr or constant_atr(), params or Day02Params()
    )


# ---------------------------------------------------------------- rules on candles: the sheet example


def test_sheet_example_path_on_candles_matches_the_sheet_values() -> None:
    m15, m5 = sheet_bars(WINTER)
    calls: list[tuple[datetime, datetime]] = []
    found = search(WINTER, m15, m5, atr=constant_atr(calls))
    config = got(found.configuration)
    assert config.side is Side.LONG
    assert config.recognised_utc == at(WINTER, 9, 30)
    assert (config.origin, config.origin_start) == (D("1.12980"), at(WINTER, 8, 45))
    assert (config.peak, config.peak_start) == (D("1.13140"), at(WINTER, 9, 15))
    assert config.amplitude == D("0.00160") and config.depth_limit == D("1.13060")
    assert config.extensions == []
    assert config.pause_starts == [at(WINTER, 9, 30), at(WINTER, 9, 45)]
    assert config.flag_utc == at(WINTER, 10, 0) and config.deadline_utc == at(WINTER, 11, 0)
    assert config.outcome == EXIT and config.d_utc == at(WINTER, 10, 10)
    assert config.flag_extreme == D("1.13075")
    assert config.stop == D("1.13050") and config.target == D("1.13300")
    assert config.slope == D("0.1")  # (1.13110 - 1.13100) / A
    # The M15 closes examined before 09:30, from the first full window (07:00-08:00), at 08:00.
    assert [e.t_utc for e in found.examined] == [at(WINTER, 8, 0) + i * timedelta(minutes=15) for i in range(6)]
    assert AMPLITUDE in found.examined[-1].cause  # 09:15: o < p = j, 7.5 pips < 15 pips
    # A is read on the last H1 ended by the start of the window, as known at t_j.
    assert calls[-1] == (at(WINTER, 8, 30), at(WINTER, 9, 30))


def test_sheet_example_is_mirrored_for_a_sale() -> None:
    def mirror(p: str) -> str:
        return str(D("2.26000") - D(p))

    rows = {k: (mirror(o), mirror(low), mirror(h), mirror(c)) for k, (o, h, low, c) in SHEET_M15}
    m15 = {
        at(WINTER, 7, 0) + i * timedelta(minutes=15): flat(
            at(WINTER, 7, 0) + i * timedelta(minutes=15), mirror("1.13010")
        )
        for i in range(5)
    }
    for (hh, mm), prices in rows.items():
        m15[at(WINTER, hh, mm)] = bar(at(WINTER, hh, mm), *prices)
    m5 = {
        at(WINTER, hh, mm): bar(
            at(WINTER, hh, mm), mirror(o), mirror(low), mirror(h), mirror(c), step=timedelta(minutes=5)
        )
        for (hh, mm), (o, h, low, c) in SHEET_M5
    }
    config = got(search(WINTER, m15, m5).configuration)
    assert config.side is Side.SHORT and config.recognised_utc == at(WINTER, 9, 30)
    assert (config.origin, config.peak) == (D("1.13020"), D("1.12860"))
    assert config.outcome == EXIT and config.d_utc == at(WINTER, 10, 10)
    # Stop on the ask: highest ask_high of the flag + 0.25 A; target E - I.
    assert config.flag_extreme == D("1.12925") + SPREAD
    assert config.stop == D("1.12925") + SPREAD + D("0.00025") and config.target == D("1.12700")


# ---------------------------------------------------------------- order of the extremes


def test_extremes_in_one_candle_give_no_impulse_in_either_direction() -> None:
    m15, m5 = sheet_bars(WINTER, {(9, 15): ("1.13000", "1.13140", "1.12970", "1.13130")})
    found = search(WINTER, m15, m5)
    examined = {e.t_utc: e.cause for e in found.examined}
    assert examined[at(WINTER, 9, 30)] == f"hausse : {ORDER} ; baisse : {ORDER}"


def test_peak_before_the_last_candle_is_not_recognised_later() -> None:
    # The peak at 09:15 is followed at 09:30 by a lower candle: p < j at 09:45; and at 09:30 the
    # amplitude counted on the 09:15 close is too small, so no impulse is recognised retroactively.
    m15, m5 = sheet_bars(WINTER, {(9, 15): ("1.13055", "1.13140", "1.13050", "1.13060")})
    found = search(WINTER, m15, m5)
    examined = {e.t_utc: e.cause for e in found.examined}
    assert AMPLITUDE in examined[at(WINTER, 9, 30)]
    assert examined[at(WINTER, 9, 45)].startswith(f"hausse : {PEAK_BEFORE_END}")
    assert found.configuration is None or found.configuration.recognised_utc > at(WINTER, 9, 45)


def test_weak_close_and_missing_window_candle_are_counted_without_recognition() -> None:
    m15, m5 = sheet_bars(WINTER, {(9, 15): ("1.13055", "1.13140", "1.13050", "1.13135")})
    del m15[at(WINTER, 8, 30)]
    found = search(WINTER, m15, m5)
    examined = {e.t_utc: e.cause for e in found.examined}
    assert examined[at(WINTER, 9, 15)] == WINDOW_DATA and examined[at(WINTER, 9, 30)] == WINDOW_DATA
    # I = 1.13200 - 1.12980 = 22 pips, strong close from 1.13145; amplitude 16 pips is enough.
    m15, m5 = sheet_bars(WINTER, {(9, 15): ("1.13055", "1.13200", "1.13050", "1.13140")})
    examined = {e.t_utc: e.cause for e in search(WINTER, m15, m5).examined}
    assert examined[at(WINTER, 9, 30)].startswith(f"hausse : {WEAK_CLOSE}")


# ---------------------------------------------------------------- extension, depth, deadlines


def test_extension_restarts_the_pause_count_and_moves_the_deadline() -> None:
    m15, m5 = sheet_bars(WINTER, {(9, 45): ("1.13100", "1.13145", "1.13075", "1.13110")})
    m15[at(WINTER, 10, 0)] = bar(at(WINTER, 10, 0), "1.13110", "1.13120", "1.13080", "1.13100")
    m15[at(WINTER, 10, 15)] = bar(at(WINTER, 10, 15), "1.13100", "1.13130", "1.13090", "1.13120")
    m5 = {
        at(WINTER, 10, 30): bar(
            at(WINTER, 10, 30), "1.13120", "1.13160", "1.13110", "1.13156", step=timedelta(minutes=5)
        )
    }
    config = got(search(WINTER, m15, m5).configuration)
    assert config.extensions == [at(WINTER, 9, 45)]
    assert (config.peak, config.peak_start, config.amplitude) == (D("1.13145"), at(WINTER, 9, 45), D("0.00165"))
    # The 09:30 pause preceded the extension: only the pauses after the last peak count.
    assert config.pause_starts == [at(WINTER, 10, 0), at(WINTER, 10, 15)]
    assert config.flag_utc == at(WINTER, 10, 30) and config.deadline_utc == at(WINTER, 11, 30)
    assert config.outcome == EXIT and config.d_utc == at(WINTER, 10, 35)  # 1.13156 > 1.13145 + 0.1 A


def test_depth_uses_the_old_peak_and_has_priority_over_an_extension() -> None:
    # Same candle above E and below the old limit 1.13060: invalidated, not extended.
    m15, m5 = sheet_bars(WINTER, {(9, 45): ("1.13100", "1.13145", "1.13055", "1.13110")})
    config = got(search(WINTER, m15, m5).configuration)
    assert config.outcome == TOO_DEEP and config.ended_utc == at(WINTER, 10, 0) and config.extensions == []
    # 1.13062 is above the old limit 1.13060 but below the new one 1.130625: the old values decide.
    m15, m5 = sheet_bars(WINTER, {(9, 45): ("1.13100", "1.13145", "1.13062", "1.13110")})
    config = got(search(WINTER, m15, m5).configuration)
    assert config.extensions == [at(WINTER, 9, 45)]
    assert (config.outcome, config.ended_utc) == (FLAG_DATA, at(WINTER, 10, 15))  # no M15 at 10:00 here


def test_depth_on_the_trigger_candle_has_priority_over_the_exit() -> None:
    m15, m5 = sheet_bars(WINTER)
    m5[at(WINTER, 10, 5)] = bar(at(WINTER, 10, 5), "1.13125", "1.13160", "1.13055", "1.13155", step=5 * MIN)
    config = got(search(WINTER, m15, m5).configuration)
    assert config.outcome == TOO_DEEP and config.ended_utc == at(WINTER, 10, 10) and config.stop is None


def flats(count: int) -> dict[datetime, dict[str, Any]]:
    """`count` flat M15 at 1.13010 from 07:00 London."""
    return {at(WINTER, 7, 0) + i * 15 * MIN: flat(at(WINTER, 7, 0) + i * 15 * MIN, "1.13010") for i in range(count)}


def no_exit_m5(day: date, until: tuple[int, int]) -> dict[datetime, dict[str, Any]]:
    """M5 below the exit level from 10:00 to `until` (start of the last one excluded)."""
    out, cursor = {}, at(day, 10, 0)
    while cursor < at(day, *until):
        out[cursor] = flat(cursor, "1.13120", 5 * MIN)
        cursor += 5 * MIN
    return out


def test_a_close_exactly_at_the_deadline_confirms() -> None:
    m15, _ = sheet_bars(WINTER)
    m5 = no_exit_m5(WINTER, (10, 55)) | {
        at(WINTER, 10, 55): bar(at(WINTER, 10, 55), "1.13120", "1.13160", "1.13110", "1.13155", 5 * MIN)
    }
    config = got(search(WINTER, m15, m5).configuration)
    assert config.outcome == EXIT and config.d_utc == at(WINTER, 11, 0) == config.deadline_utc


def test_expiry_at_the_deadline_is_not_saved_by_a_later_close() -> None:
    m15, _ = sheet_bars(WINTER)
    m5 = no_exit_m5(WINTER, (11, 0)) | {
        at(WINTER, 11, 0): bar(at(WINTER, 11, 0), "1.13120", "1.13170", "1.13110", "1.13165", 5 * MIN)
    }
    config = got(search(WINTER, m15, m5).configuration)
    assert config.outcome == TOO_LONG and config.ended_utc == at(WINTER, 11, 0)
    assert config.last_examined_start == at(WINTER, 10, 55)  # the 11:00 candle is never read


def test_window_end_caps_the_deadline_at_15_00_and_the_flag_at_14_45() -> None:
    shift = timedelta(hours=4, minutes=30)  # recognition at 14:00, F at 14:30, Δ = min(15:30, 15:00)
    m15, m5 = sheet_bars(WINTER)
    m15 = flats(40) | {s + shift: dict(b, start_utc=s + shift, end_utc=b["end_utc"] + shift) for s, b in m15.items()}
    m5 = no_exit_m5(WINTER, (10, 30))
    m5 = {s + shift: dict(b, start_utc=s + shift, end_utc=b["end_utc"] + shift) for s, b in m5.items()}
    config = got(search(WINTER, m15, m5).configuration)
    assert config.recognised_utc == at(WINTER, 14, 0) and config.flag_utc == at(WINTER, 14, 30)
    assert config.deadline_utc == at(WINTER, 15, 0)
    assert config.outcome == WINDOW_END and config.ended_utc == at(WINTER, 15, 0)
    # Recognition at 14:15 (latest): the flag would form at 14:45 at the earliest, here one extension
    # pushes it beyond 14:45: window end at 14:45, before any trigger candle is read.
    shift = timedelta(hours=4, minutes=45)
    m15, _ = sheet_bars(WINTER, {(9, 30): ("1.13130", "1.13142", "1.13090", "1.13100")})
    m15 = flats(40) | {s + shift: dict(b, start_utc=s + shift, end_utc=b["end_utc"] + shift) for s, b in m15.items()}
    config = got(search(WINTER, m15, {}).configuration)
    assert config.recognised_utc == at(WINTER, 14, 15) and config.extensions == [at(WINTER, 14, 15)]
    assert config.outcome == WINDOW_END and config.ended_utc == at(WINTER, 14, 45) and config.flag_utc is None


def test_prolonged_impulse_is_abandoned_after_six_m15() -> None:
    m15, m5 = sheet_bars(WINTER)
    highs = ["1.13150", "1.13160", "1.13170", "1.13180"]  # 09:30 to 10:15: o = 08:45, p = 10:15 -> 7 M15
    for i, h in enumerate(highs):
        start = at(WINTER, 9, 30) + i * 15 * MIN
        m15[start] = bar(start, "1.13130", h, "1.13120", "1.13140")
    config = got(search(WINTER, m15, m5).configuration)
    assert config.extensions == [at(WINTER, 9, 30), at(WINTER, 9, 45), at(WINTER, 10, 0), at(WINTER, 10, 15)]
    assert config.outcome == PROLONGED and config.ended_utc == at(WINTER, 10, 30)


def test_unusable_candles_end_the_configuration_without_reading_them() -> None:
    m15, m5 = sheet_bars(WINTER)
    m15[at(WINTER, 9, 45)] = dict(m15[at(WINTER, 9, 45)], complete_at_close=False, bid_low=D("1.10000"))
    config = got(search(WINTER, m15, m5).configuration)
    assert config.outcome == FLAG_DATA and config.ended_utc == at(WINTER, 10, 0)
    m15, m5 = sheet_bars(WINTER)
    del m5[at(WINTER, 10, 5)]
    config = got(search(WINTER, m15, m5).configuration)
    assert config.outcome == FLAG_DATA and config.ended_utc == at(WINTER, 10, 10)


def test_comparison_m15_reads_the_exit_on_m15_with_the_same_rules() -> None:
    m15, _ = sheet_bars(WINTER)
    m15[at(WINTER, 10, 0)] = bar(at(WINTER, 10, 0), "1.13110", "1.13160", "1.13100", "1.13155")
    config = got(search(WINTER, m15, m15, params=Day02Params(trigger=Trigger.M15)).configuration)
    assert config.outcome == EXIT and config.d_utc == at(WINTER, 10, 15)
    assert config.flag_extreme == D("1.13075") and config.stop == D("1.13050")


def test_resume_mid_m15_never_reuses_a_candle_started_before_it() -> None:
    assert ceil_m15(at(WINTER, 11, 2, 14, 510)) == at(WINTER, 11, 15)
    assert ceil_m15(at(WINTER, 11, 15)) == at(WINTER, 11, 15)
    found = search(WINTER, flats(40), {}, resume=at(WINTER, 11, 2, 14, 510))
    assert found.examined[0].t_utc == at(WINTER, 12, 15)  # window 11:15-12:15
    assert found.examined[-1].t_utc == at(WINTER, 14, 15)


# ---------------------------------------------------------------- causality of the candle rules


@pytest.mark.parametrize("cut", [(9, 40), (10, 0), (10, 7)])
def test_candles_after_an_instant_change_nothing_known_at_it(cut: tuple[int, int]) -> None:
    x = at(WINTER, *cut)
    m15, m5 = sheet_bars(WINTER)
    full = search(WINTER, m15, m5)
    for altered in (False, True):
        k15 = {s: c for s, c in m15.items() if c["end_utc"] <= x}
        k5 = {s: c for s, c in m5.items() if c["end_utc"] <= x}
        if altered:  # different candles after x instead of none
            k15 |= {s: flat(s, "1.10000") for s, c in m15.items() if c["end_utc"] > x}
            k5 |= {s: flat(s, "1.10000", 5 * MIN) for s, c in m5.items() if c["end_utc"] > x}
        cut_search = search(WINTER, k15, k5)
        assert [e for e in full.examined if e.t_utc <= x] == [e for e in cut_search.examined if e.t_utc <= x]
        a, b = got(full.configuration), got(cut_search.configuration)
        assert a.recognised_utc == b.recognised_utc and (a.origin, a.peak) == (b.origin, b.peak)
        assert (a.flag_utc if got(a.flag_utc) <= x else None) == (
            b.flag_utc if b.flag_utc is not None and b.flag_utc <= x else None
        )
        if got(b.ended_utc) <= x:
            assert (b.outcome, b.ended_utc) == (a.outcome, a.ended_utc)


# ---------------------------------------------------------------- engine inputs


def h1_bars(
    until: datetime,
    days: int = 6,
    skip: set[datetime] | None = None,
    bad: set[datetime] | None = None,
    wide: set[datetime] | None = None,
) -> list[dict[str, Any]]:
    """Expected-open H1 ending by `until`, schema of history.bars, true range 0.00100 around 1.13000."""
    bars, cursor = [], (until - timedelta(days=days)).replace(minute=0, second=0, microsecond=0)
    while cursor + timedelta(hours=1) <= until:
        if market_state(cursor) is MarketState.OPEN and cursor not in (skip or set()):
            half = D("0.0005") * (5 if cursor in (wide or set()) else 1)
            ok = cursor not in (bad or set())
            mid = D("1.13000")
            bars.append(
                {
                    "start_utc": cursor,
                    "end_utc": cursor + timedelta(hours=1),
                    "bid_open": mid,
                    "bid_high": mid + half,
                    "bid_low": mid - half,
                    "bid_close": mid,
                    "ask_open": mid + SPREAD,
                    "ask_high": mid + half + SPREAD,
                    "ask_low": mid - half + SPREAD,
                    "ask_close": mid + SPREAD,
                    "tick_count": 100,
                    "excluded_ticks": 0,
                    "first_tick_utc": cursor,
                    "last_tick_utc": cursor + timedelta(minutes=59),
                    "flags": [] if ok else ["trou de cotation > 10 min pendant l'ouverture prévue"],
                    "flags_at_close": [] if ok else ["trou de cotation > 10 min pendant l'ouverture prévue"],
                    "expected_hours": 1,
                    "present_hours": 1,
                    "complete": ok,
                    "complete_at_close": ok,
                }
            )
        cursor += timedelta(hours=1)
    return bars


def engine(h1: list[dict[str, Any]], **kwargs: Any) -> Day02Backtest:
    return Day02Backtest([], [], h1, [], [], Day02Params(), CONFIG, **kwargs)


# ---------------------------------------------------------------- ATR H1


def test_h1_fixture_has_the_schema_of_the_history_builder() -> None:
    keys = {
        "start_utc",
        "end_utc",
        "bid_open",
        "bid_high",
        "bid_low",
        "bid_close",
        "ask_open",
        "ask_high",
        "ask_low",
        "ask_close",
        "tick_count",
        "excluded_ticks",
        "first_tick_utc",
        "last_tick_utc",
        "flags",
        "flags_at_close",
        "expected_hours",
        "present_hours",
        "complete",
        "complete_at_close",
    }
    (first, *_) = h1_bars(at(WINTER, 7, 0))
    assert set(first) == keys


def test_atr_h1_value_and_bootstrap() -> None:
    cutoff = at(WINTER, 8, 30)
    assert engine(h1_bars(at(WINTER, 8, 0))).atr_at(cutoff, at(WINTER, 9, 30)) == A
    # Bootstrap: 14 valid true ranges need 15 usable H1; with 14 only, no ATR (never zero).
    few = h1_bars(at(WINTER, 8, 0), days=1)[-14:]
    assert engine(few).atr_at(cutoff, at(WINTER, 9, 30)) is None
    assert engine(h1_bars(at(WINTER, 8, 0), days=1)[-15:]).atr_at(cutoff, at(WINTER, 9, 30)) == A


def test_atr_h1_restarts_after_an_absent_or_unusable_expected_h1() -> None:
    known = at(WINTER, 9, 30)
    for kind in ("skip", "bad"):
        hole = at(WINTER, 0, 0)  # expected H1 [00:00, 01:00) absent or unusable
        holes = {"skip": {hole} if kind == "skip" else None, "bad": {hole} if kind == "bad" else None}
        h1 = h1_bars(at(WINTER, 8, 0), skip=holes["skip"], bad=holes["bad"])
        assert engine(h1).atr_at(at(WINTER, 8, 30), known) is None, kind
        h1 = h1_bars(at(WINTER, 17, 0), skip=holes["skip"], bad=holes["bad"])
        # The H1 of 01:00 gives the new reference close; 14 true ranges from 02:00 to 15:00: the ATR
        # exists from the close of the 15:00 H1 (16:00), not before.
        assert engine(h1).atr_at(at(WINTER, 16, 0), at(WINTER, 16, 0)) == A, kind
        assert engine(h1).atr_at(at(WINTER, 15, 0), at(WINTER, 16, 0)) is None, kind


def test_atr_h1_continues_across_the_known_weekly_closure() -> None:
    monday = date(2019, 2, 11)
    h1 = [b for b in h1_bars(at(monday, 8, 0), days=4) if b["start_utc"] >= datetime(2019, 2, 8, 12, tzinfo=UTC)]
    # Friday 12:00 UTC to Monday 08:00: the weekly closure is not an absent expected H1.
    assert engine(h1).atr_at(at(monday, 8, 0), at(monday, 9, 0)) == A


def test_atr_never_reads_the_impulse_window() -> None:
    # A wide H1 [08:00, 09:00) overlaps the window 08:30-09:30: A comes from the H1 ended by 08:30.
    h1 = h1_bars(at(WINTER, 10, 0), wide={at(WINTER, 8, 0)})
    assert engine(h1).atr_at(at(WINTER, 8, 30), at(WINTER, 9, 30)) == A
    assert engine(h1).atr_at(at(WINTER, 9, 0), at(WINTER, 9, 30)) != A


# ---------------------------------------------------------------- ticks of the sheet example


def tick(moment: datetime, bid: str | D) -> Tick:
    b = D(bid)
    return Tick(moment, b, b + SPREAD)


def fill(start: datetime, end: datetime, bid: str | D, step: timedelta = timedelta(seconds=30)) -> list[Tick]:
    out, cursor = [], start
    while cursor < end:
        out.append(tick(cursor, bid))
        cursor += step
    return out


def candle_ticks(start: datetime, length: timedelta, o: str, h: str, low: str, c: str, last_ms: int = 0) -> list[Tick]:
    """Ticks giving exactly (o, h, low, c): open, high one minute later, low one minute after, then the close."""
    last = start + length - SEC + timedelta(milliseconds=last_ms)
    return [
        tick(start, o),
        tick(start + MIN, h),
        tick(start + 2 * MIN, low),
        *fill(start + 2 * MIN + 30 * SEC, start + length - SEC, c),
        tick(last, c),
    ]


def sheet_ticks(
    day: date,
    after: list[Tick] | None = None,
    shift: timedelta = timedelta(0),
    changes: dict[tuple[int, int], tuple[str, str, str, str]] | None = None,
) -> list[Tick]:
    """The candles of the sheet §11 from the ticks; `after` follows the last tick 10:09:59.820."""
    out = fill(at(day, 7, 0), at(day, 8, 15) + shift, "1.13010")
    rows = dict(SHEET_M15) | (changes or {})
    for (hh, mm), prices in rows.items():
        out += candle_ticks(at(day, hh, mm) + shift, 15 * MIN, *prices)
    out += candle_ticks(at(day, 10, 0) + shift, 5 * MIN, *SHEET_M5[0][1])
    out += candle_ticks(at(day, 10, 5) + shift, 5 * MIN, *SHEET_M5[1][1], last_ms=820)
    if after is None:
        after = target_after(day, shift)
    return out + after


def target_after(day: date, shift: timedelta = timedelta(0)) -> list[Tick]:
    """Entry tick 10:10:00.230 (ask 1.13158), target reached at 11:02:14.510 (case 1 of the sheet)."""
    out = [
        tick(at(day, 10, 10, 0, 230) + shift, "1.13156"),
        *fill(at(day, 10, 10, 30) + shift, at(day, 11, 2, 14) + shift, "1.13200"),
    ]
    out += [tick(at(day, 11, 2, 14, 510) + shift, "1.13300")]
    return out + fill(at(day, 11, 2, 30) + shift, at(day, 17, 30), "1.13250")


def candles(tmp_path: Path, ticks: list[Tick]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """M5 and M15 built from `ticks` by the real builder, one file per UTC day, 5 min convention."""
    by_day: dict[date, list[Tick]] = defaultdict(list)
    for t in ticks:
        by_day[t.ts_utc.date()].append(t)
    tmp_path.mkdir(parents=True, exist_ok=True)
    store = HistoryStore(tmp_path / "data")
    for day, rows in sorted(by_day.items()):
        path = tmp_path / f"{day}.csv"
        lines = ["Gmt time,Ask,Bid,AskVolume,BidVolume\n"]
        lines += [
            f"{t.ts_utc:%d.%m.%Y %H:%M:%S}.{t.ts_utc.microsecond // 1000:03d},{t.ask},{t.bid},1,1\n"
            for t in sorted(rows, key=lambda t: t.ts_utc)
        ]
        path.write_text("".join(lines), encoding="utf-8")
        start = datetime.combine(day, time(), tzinfo=UTC)
        store.ingest(
            IngestRequest(
                path, "dukascopy", "EURUSD", "dukascopy-ticks-csv-v1", start, start + timedelta(days=1), start
            )
        )
    built = build_intraday(store, "dukascopy", "EURUSD", convention=DAY01_5MIN)
    return built.bars[Grid.M5], built.bars[Grid.M15]


def run(
    tmp_path: Path,
    ticks: list[Tick],
    day: date = WINTER,
    *,
    days: int = 1,
    trigger: Trigger = Trigger.M5,
    scenario: GapScenario = GapScenario.OBSERVED_ONLY,
    config: ResearchConfig = CONFIG,
    end_utc: datetime | None = None,
) -> Day02Result:
    ticks = sorted(ticks, key=lambda t: t.ts_utc)
    m5, m15 = candles(tmp_path, ticks)
    engine = Day02Backtest(
        m5,
        m15,
        h1_bars(london(day + timedelta(days=days), time(0)), days=days + 5),
        ticks,
        [],
        Day02Params(trigger=trigger),
        config,
        scenario=scenario,
        start_utc=london(day, time(0)),
        end_utc=end_utc or london(day + timedelta(days=days), time(0)),
    )
    return engine.run()


# ---------------------------------------------------------------- engine: the sheet example


@pytest.mark.parametrize("day", [WINTER, SUMMER], ids=["GMT", "BST"])
def test_sheet_example_case_1_target_in_london_time(tmp_path: Path, day: date) -> None:
    result = run(tmp_path, sheet_ticks(day), day)
    first = result.attempts[0]
    config = got(first.search.configuration)
    assert (config.recognised_utc, config.flag_utc, config.d_utc) == (at(day, 9, 30), at(day, 10, 0), at(day, 10, 10))
    assert (config.stop, config.target, config.atr) == (D("1.13050"), D("1.13300"), A)
    assert first.resume_utc == at(day, 7, 0) and first.resume_after == SESSION_START
    assert first.at_d == ENTRY_DECIDED and first.entry_outcome == EXECUTED
    assert got(first.decision)["p_d"] == D("1.13157")
    (trade,) = result.trades
    assert (trade.entry_utc, trade.entry_price) == (at(day, 10, 10, 0, 230), D("1.13158"))
    assert (trade.exit_utc, trade.exit_reason) == (at(day, 11, 2, 14, 510), "CIBLE")
    assert result.closings == []
    # Resume after the close in the middle of an M15: the next window starts at 11:15.
    second = result.attempts[1]
    assert second.resume_utc == at(day, 11, 2, 14, 510) and second.resume_after == POSITION_CLOSED
    assert second.search.examined[0].t_utc == at(day, 12, 15)


def test_sheet_example_case_2_time_exit(tmp_path: Path) -> None:
    after = [tick(at(WINTER, 10, 10, 0, 230), "1.13156"), *fill(at(WINTER, 10, 10, 30), at(WINTER, 17, 30), "1.13200")]
    after.append(tick(at(WINTER, 12, 10, 0, 230), "1.13200"))  # exactly at the deadline: does not execute
    result = run(tmp_path, sheet_ticks(WINTER, after))
    (trade,) = result.trades
    # Due at 12:10:00.230: the 12:10:00 tick is before it, the 12:10:30 tick executes the order.
    assert (trade.exit_utc, trade.exit_reason) == (at(WINTER, 12, 10, 30), TIME_EXIT)
    (closing,) = result.closings
    assert (closing.decided_utc, closing.order, closing.close_reason) == (
        at(WINTER, 12, 10, 0, 230),
        TIME_EXIT,
        TIME_EXIT,
    )
    assert closing.delay == timedelta(seconds=29, milliseconds=770) and not closing.coincident
    assert result.attempts[1].resume_utc == at(WINTER, 12, 10, 30)


def test_comparison_m15_engine_decides_at_the_m15_close(tmp_path: Path) -> None:
    result = run(tmp_path, sheet_ticks(WINTER), trigger=Trigger.M15)
    config = got(result.attempts[0].search.configuration)
    assert config.d_utc == at(WINTER, 10, 15) and config.stop == D("1.13050")
    assert result.attempts[0].entry_outcome == EXECUTED
    assert result.trades[0].entry_utc > at(WINTER, 10, 15)


# ---------------------------------------------------------------- execution bounds


def entry_cases(day: date, ticks_after_d: list[Tick]) -> list[Tick]:
    rest = fill(at(day, 10, 20), at(day, 17, 30), "1.13200")
    return sheet_ticks(day, ticks_after_d + rest)


def test_a_tick_exactly_at_d_never_executes(tmp_path: Path) -> None:
    after = [tick(at(WINTER, 10, 10), "1.13156"), tick(at(WINTER, 10, 10, 0, 1), "1.13156")]
    result = run(tmp_path, entry_cases(WINTER, after))
    assert result.trades[0].entry_utc == at(WINTER, 10, 10, 0, 1)


def test_silence_of_exactly_five_minutes_keeps_the_entry_valid(tmp_path: Path) -> None:
    after = [tick(at(WINTER, 10, 10), "1.13156"), tick(at(WINTER, 10, 15), "1.13156")]
    result = run(tmp_path, entry_cases(WINTER, after))
    assert result.attempts[0].entry_outcome == EXECUTED
    assert result.trades[0].entry_utc == at(WINTER, 10, 15)  # validity ]D, D + 5 min], bound included


def test_no_tick_until_the_deadline_after_a_tick_at_d_expires(tmp_path: Path) -> None:
    after = [tick(at(WINTER, 10, 10), "1.13156"), tick(at(WINTER, 10, 15, 0, 1), "1.13156")]
    result = run(tmp_path, entry_cases(WINTER, after))
    first = result.attempts[0]
    assert (first.entry_outcome, first.entry_outcome_utc) == (EXPIRED, at(WINTER, 10, 15))
    assert result.trades == [] or result.trades[0].decided_utc != at(WINTER, 10, 10)
    assert result.attempts[1].resume_utc == at(WINTER, 10, 15) and result.attempts[1].resume_after == EXPIRED


def test_silence_strictly_above_five_minutes_cancels_the_entry(tmp_path: Path) -> None:
    after = [tick(at(WINTER, 10, 15), "1.13156")]  # 10:09:59.820 -> 10:15:00: 5 min 0.18 s
    result = run(tmp_path, entry_cases(WINTER, after))
    first = result.attempts[0]
    assert (first.entry_outcome, first.entry_outcome_utc) == (CANCELLED_INTERRUPTION, at(WINTER, 10, 15))
    assert all(t.decided_utc != at(WINTER, 10, 10) for t in result.trades)
    assert result.attempts[1].resume_after == CANCELLED_INTERRUPTION


def test_refusal_at_d_resumes_at_d(tmp_path: Path) -> None:
    result = run(tmp_path, sheet_ticks(WINTER), config=ResearchConfig(costs=RESEARCH_COSTS, min_size=D("100")))
    first, second = result.attempts[:2]
    assert (first.at_d, first.ended_utc, first.ended_by) == (SIZE_REFUSED, at(WINTER, 10, 10), SIZE_REFUSED)
    assert (second.resume_utc, second.resume_after) == (at(WINTER, 10, 10), SIZE_REFUSED)
    assert second.search.examined[0].t_utc == at(WINTER, 11, 15)  # window 10:15-11:15
    assert result.trades == []


def test_abandoned_configuration_resumes_at_its_end(tmp_path: Path) -> None:
    ticks = sheet_ticks(
        WINTER,
        fill(at(WINTER, 10, 10), at(WINTER, 17, 30), "1.13120"),
        changes={(9, 45): ("1.13100", "1.13120", "1.13055", "1.13110")},
    )
    result = run(tmp_path, ticks)
    first, second = result.attempts[:2]
    assert got(first.search.configuration).outcome == TOO_DEEP and first.ended_utc == at(WINTER, 10, 0)
    assert (second.resume_utc, second.resume_after) == (at(WINTER, 10, 0), TOO_DEEP)


def test_every_resume_is_the_end_of_the_previous_attempt(tmp_path: Path) -> None:
    for case, ticks in {"target": sheet_ticks(WINTER), "refused": sheet_ticks(WINTER)}.items():
        config = CONFIG if case == "target" else ResearchConfig(costs=RESEARCH_COSTS, min_size=D("100"))
        result = run(tmp_path / case, ticks, config=config)
        for before, after in zip(result.attempts, result.attempts[1:], strict=False):
            assert (after.resume_utc, after.resume_after) == (before.ended_utc, before.ended_by)
        for attempt in result.attempts:
            if attempt.ended_by == POSITION_CLOSED:
                trade = next(t for t in result.trades if t.decided_utc == got(attempt.decision)["d_utc"])
                assert attempt.ended_utc == trade.exit_utc


# ---------------------------------------------------------------- positions and closing orders


def late_example(day: date, after: list[Tick]) -> list[Tick]:
    """The sheet example shifted by 4 h 45: recognition 14:15, F 14:45, D 14:55, Δ = 15:00."""
    return sheet_ticks(day, after, shift=timedelta(hours=4, minutes=45))


def test_equal_deadlines_give_one_liquidation_and_a_night_without_quote(tmp_path: Path) -> None:
    # Tick exactly at D (no execution, counts for the silence), execution exactly at 15:00:00.000:
    # time exit due at 17:00:00.000 = liquidation. No tick after 17:00 until the next morning.
    after = [tick(at(WINTER, 14, 55), "1.13156"), tick(at(WINTER, 15, 0), "1.13156")]
    after += fill(at(WINTER, 15, 0, 30), at(WINTER, 17, 0, 1), "1.13200")
    nxt = WINTER + timedelta(days=1)
    after += fill(at(nxt, 7, 0), at(nxt, 17, 30), "1.13200")  # neither stop nor target
    result = run(tmp_path, late_example(WINTER, after), days=2)
    first = result.attempts[0]
    assert got(first.search.configuration).d_utc == at(WINTER, 14, 55)
    (trade,) = [t for t in result.trades if t.decided_utc == at(WINTER, 14, 55)]
    assert trade.entry_utc == at(WINTER, 15, 0)
    assert (trade.exit_utc, trade.exit_reason) == (at(nxt, 7, 0), LIQUIDATION)
    assert trade.indeterminate  # the night is an unexplained silence of an open market: scenario A
    (closing,) = result.closings
    assert (closing.decided_utc, closing.order, closing.coincident) == (at(WINTER, 17, 0), LIQUIDATION, True)
    assert closing.silence_kind is Silence.UNEXPLAINED
    # The attempt is ended by the real close, replayed after its search had stopped (14:15).
    assert (first.ended_utc, first.ended_by) == (at(nxt, 7, 0), POSITION_CLOSED)
    # Unplanned night: one annotation, apart from the closing reason and from the interruption.
    assert result.unplanned_nights == [at(WINTER, 14, 55)]
    assert [j.utc for j in result.journal if j.kind == UNPLANNED_NIGHT] == [at(nxt, 7, 0)]
    assert sum(e.startswith(UNPLANNED_NIGHT) for e in first.events) == 1
    assert "financement overnight" in trade.costs_quote  # costs unchanged: one night financed
    # The next session waited for the close, then resumed from the event that authorises it.
    resumed = next(a for a in result.attempts if a.day == nxt)
    assert (resumed.resume_utc, resumed.resume_after) == (first.ended_utc, first.ended_by)


@pytest.mark.parametrize(
    ("scenario", "reason"),
    [
        (GapScenario.OBSERVED_ONLY, TIME_EXIT),
        (GapScenario.STOP_FIRST, "STOP_SCÉNARIO_B"),
        (GapScenario.TARGET_FIRST, "CIBLE_SCÉNARIO_C"),
    ],
)
def test_silence_during_a_position(tmp_path: Path, scenario: GapScenario, reason: str) -> None:
    # Exactly 5 min of silence (10:30 -> 10:35) is no interruption; 10:40 -> 10:45:00.001 is one.
    after = [
        tick(at(WINTER, 10, 10, 0, 230), "1.13156"),
        *fill(at(WINTER, 10, 10, 30), at(WINTER, 10, 30, 1), "1.13200"),
        *fill(at(WINTER, 10, 35), at(WINTER, 10, 40, 1), "1.13200"),
    ]
    after += fill(at(WINTER, 10, 45, 0, 1), at(WINTER, 17, 30), "1.13200")
    result = run(tmp_path, sheet_ticks(WINTER, after), scenario=scenario)
    trade = result.trades[0]
    assert trade.unobservable_crossings == [
        f"{at(WINTER, 10, 40).isoformat()} → {at(WINTER, 10, 45, 0, 1).isoformat()}"
    ]
    assert trade.exit_reason == reason
    if scenario is GapScenario.STOP_FIRST:
        assert trade.exit_price == D("1.13050") and trade.exit_utc == at(WINTER, 10, 45, 0, 1)
    if scenario is GapScenario.TARGET_FIRST:
        assert trade.exit_price == D("1.13300")


def test_open_position_at_the_end_of_the_study_is_valued_without_exit(tmp_path: Path) -> None:
    after = [tick(at(WINTER, 10, 10, 0, 230), "1.13156"), *fill(at(WINTER, 10, 10, 30), at(WINTER, 12, 0), "1.13200")]
    result = run(tmp_path, sheet_ticks(WINTER, after))  # no tick after 12:00 until the end of the study
    trade = got(result.open_trade)
    assert trade.exit_utc is None and result.trades == []
    assert result.unexecuted_closing == (at(WINTER, 12, 10, 0, 230), TIME_EXIT)
    assert got(result.silence_at_end)["kind"] is Silence.UNEXPLAINED and trade.indeterminate
    # Really still open: its attempt is not ended, and no later attempt claims a resume after it.
    first = result.attempts[0]
    assert (first.entry_outcome, first.ended_utc, first.ended_by) == (EXECUTED, None, None)
    assert result.attempts == [first] and result.unplanned_nights == []


# ---------------------------------------------------------------- causality of the engine


@pytest.mark.parametrize("cut", [(9, 50), (10, 12)])
def test_ticks_and_candles_after_an_instant_change_nothing_known_at_it(tmp_path: Path, cut: tuple[int, int]) -> None:
    x = at(WINTER, *cut)
    full = sheet_ticks(WINTER)
    changed = [t for t in full if t.ts_utc < x] + fill(x, at(WINTER, 17, 30), "1.12900")
    reference = run(tmp_path / "full", full)
    for name, ticks in {"cut": [t for t in full if t.ts_utc < x], "changed": changed}.items():
        other = run(tmp_path / name, ticks)
        a, b = reference.attempts[0], other.attempts[0]
        assert [e for e in a.search.examined if e.t_utc <= x] == [e for e in b.search.examined if e.t_utc <= x]
        ca, cb = got(a.search.configuration), got(b.search.configuration)
        assert (ca.recognised_utc, ca.origin, ca.peak) == (cb.recognised_utc, cb.origin, cb.peak)
        if got(ca.d_utc) <= x:
            assert (cb.d_utc, cb.stop, cb.target) == (ca.d_utc, ca.stop, ca.target)
            assert a.decision == b.decision
            entry = other.trades[0].entry_utc if other.trades else got(other.open_trade).entry_utc
            assert entry == reference.trades[0].entry_utc
        before = [j for j in reference.journal if j.utc < x]
        assert before == [j for j in other.journal if j.utc < x]


def test_stop_reached_overnight_is_an_unplanned_night_with_its_stop_reason(tmp_path: Path) -> None:
    after = [tick(at(WINTER, 14, 55), "1.13156"), tick(at(WINTER, 15, 0), "1.13156")]
    after += fill(at(WINTER, 15, 0, 30), at(WINTER, 17, 0, 1), "1.13200")
    nxt = WINTER + timedelta(days=1)
    after += fill(at(nxt, 7, 0), at(nxt, 17, 30), "1.13000")  # below the stop 1.13050
    result = run(tmp_path, late_example(WINTER, after), days=2)
    (trade,) = [t for t in result.trades if t.decided_utc == at(WINTER, 14, 55)]
    assert (trade.exit_utc, trade.exit_reason, trade.exit_price) == (
        at(nxt, 7, 0),
        "STOP_APRÈS_INTERRUPTION",
        D("1.13050"),
    )
    assert trade.indeterminate and result.unplanned_nights == [at(WINTER, 14, 55)]
    assert [j.kind for j in result.journal].count(UNPLANNED_NIGHT) == 1
    (closing,) = result.closings  # the 17:00 order was due; the stop took precedence on the same tick
    assert (closing.order, closing.close_reason) == (LIQUIDATION, "STOP_APRÈS_INTERRUPTION")
    first = result.attempts[0]
    assert (first.ended_utc, first.ended_by) == (at(nxt, 7, 0), POSITION_CLOSED)


def test_close_after_the_last_recognition_ends_the_attempt_the_same_day(tmp_path: Path) -> None:
    after = [tick(at(WINTER, 14, 55), "1.13156"), tick(at(WINTER, 15, 0), "1.13156")]
    after += fill(at(WINTER, 15, 0, 30), at(WINTER, 17, 30), "1.13200")
    result = run(tmp_path, late_example(WINTER, after))
    (trade,) = result.trades
    assert (trade.exit_utc, trade.exit_reason) == (at(WINTER, 17, 0, 30), LIQUIDATION)
    first = result.attempts[0]
    assert (first.ended_utc, first.ended_by) == (trade.exit_utc, POSITION_CLOSED)
    assert result.attempts == [first]  # no recognition is possible after 14:15: nothing resumes
    assert result.unplanned_nights == [] and UNPLANNED_NIGHT not in [j.kind for j in result.journal]


@pytest.mark.parametrize("rule", list(StopAtExecution), ids=[r.name for r in StopAtExecution])
def test_stop_already_beyond_at_execution(tmp_path: Path, rule: StopAtExecution) -> None:
    after = [tick(at(WINTER, 10, 10, 0, 230), "1.13040"), *fill(at(WINTER, 10, 10, 30), at(WINTER, 17, 30), "1.13200")]
    config = ResearchConfig(costs=RESEARCH_COSTS, stop_at_execution=rule)
    result = run(tmp_path, sheet_ticks(WINTER, after), config=config)
    first, second = result.attempts[:2]
    execution = at(WINTER, 10, 10, 0, 230)
    assert result.open_trade is None and result.closings == []
    decided = [t for t in result.trades if t.decided_utc == at(WINTER, 10, 10)]
    if rule is StopAtExecution.FILL_THEN_LIQUIDATE:
        (trade,) = decided  # one trade only, filled then liquidated on the same tick
        assert (trade.entry_utc, trade.exit_utc, trade.exit_reason) == (
            execution,
            execution,
            "STOP_FRANCHI_À_L'EXÉCUTION",
        )
        assert "prime de stop garanti" not in trade.costs_quote
        assert (first.entry_outcome, first.ended_utc, first.ended_by) == (STOP_AT_EXECUTION, execution, POSITION_CLOSED)
    else:
        assert decided == []
        expected = (REJECTED_AT_EXECUTION, execution, REJECTED_AT_EXECUTION)
        assert (first.entry_outcome, first.ended_utc, first.ended_by) == expected
    assert (second.resume_utc, second.resume_after) == (first.ended_utc, first.ended_by)
    assert second.search.examined[0].t_utc == at(WINTER, 11, 15)
