"""Exploratory DAY_02 exit configuration LATE (docs/experiments/DAY02_LATE_EXIT_CAMPAIGN.md).

Same entries, stop, target and sizing as the frozen reference; no time exit after 2 h; liquidation at
22:55 Europe/Paris instead of 17:00 London, executed at the first tick strictly after it, never at an
invented price; financing of the ADR-035 model whenever 17:00 New York is crossed, even on the same
calendar day. Synthetic data only.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest
from test_day02 import CONFIG, SUMMER, WINTER, at, candles, fill, got, h1_bars, sheet_ticks, tick

from forex_bot.backtest.day01 import london
from forex_bot.backtest.day02 import (
    LATE_LIQUIDATION,
    LIQUIDATION,
    POSITION_CLOSED,
    TIME_EXIT,
    UNPLANNED_NIGHT,
    Day02Params,
    liquidation_utc,
)
from forex_bot.backtest.day02_engine import Day02Backtest, Day02Result
from forex_bot.backtest.day02_explore import (
    EXIT_OUTCOMES,
    LATE_EXIT_OUTCOMES,
    all_trades,
    closings,
    due_of,
    exit_outcomes,
    funnel,
)
from forex_bot.backtest.day02_variants import REFERENCE, variant_of, variant_params
from forex_bot.backtest.feed import Silence, Tick
from forex_bot.history.calendar import trading_day

LATE = variant_params("LATE")
# 2019: the United States moved to summer time on 10 March and back on 3 November, Europe on
# 31 March and 27 October. In between, 17:00 New York falls at 22:00 Paris instead of 23:00.
SPRING_GAP = date(2019, 3, 12)  # Tuesday: London GMT, Paris UTC+1, New York EDT
AUTUMN_GAP = date(2019, 10, 29)  # Tuesday: London GMT, Paris UTC+1, New York EDT
SPRING_FRIDAY = date(2019, 3, 15)  # Friday of the spring gap: the week closes at 21:00 UTC


def run(
    tmp_path: Path,
    ticks: list[Tick],
    params: Day02Params,
    day: date = WINTER,
    *,
    days: int = 1,
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
        params,
        CONFIG,
        start_utc=london(day, time(0)),
        end_utc=end_utc or london(day + timedelta(days=days), time(0)),
    )
    return engine.run()


def held(day: date, until: datetime, bid: str = "1.13200") -> list[Tick]:
    """The sheet example (entry 10:10:00.230, stop 1.13050, target 1.13300), then a flat price."""
    return sheet_ticks(day, [tick(at(day, 10, 10, 0, 230), "1.13156"), *fill(at(day, 10, 10, 30), until, bid)])


# ---------------------------------------------------------------- definition


def test_late_changes_only_the_closing_deadlines_of_the_reference() -> None:
    reference = Day02Params()
    diff = {k for k, v in vars(LATE).items() if vars(reference)[k] != v}
    assert diff == {"time_exit", "liquidation", "liquidation_zone"}
    assert (LATE.time_exit, LATE.liquidation, LATE.liquidation_zone) == (None, time(22, 55), "Europe/Paris")
    assert (LATE.liquidation_reason, reference.liquidation_reason) == (LATE_LIQUIDATION, LIQUIDATION)
    assert variant_of(LATE) == "LATE" and variant_of(reference) == REFERENCE
    assert exit_outcomes(LATE) == LATE_EXIT_OUTCOMES and exit_outcomes(reference) == EXIT_OUTCOMES
    with pytest.raises(ValueError, match="échéances"):
        exit_outcomes(Day02Params(time_exit=None))  # a combination nobody registered


@pytest.mark.parametrize(
    ("day", "utc", "financed"),
    [
        (WINTER, datetime(2019, 2, 12, 21, 55, tzinfo=UTC), False),  # 16:55 New York
        (SUMMER, datetime(2019, 7, 9, 20, 55, tzinfo=UTC), False),  # 16:55 New York
        (SPRING_GAP, datetime(2019, 3, 12, 21, 55, tzinfo=UTC), True),  # 17:55 New York
        (AUTUMN_GAP, datetime(2019, 10, 29, 21, 55, tzinfo=UTC), True),  # 17:55 New York
        (date(2019, 3, 29), datetime(2019, 3, 29, 21, 55, tzinfo=UTC), True),  # Friday, the week is closed
        (date(2019, 4, 1), datetime(2019, 4, 1, 20, 55, tzinfo=UTC), False),  # both zones in summer time
    ],
)
def test_late_liquidation_is_22_55_paris_through_every_daylight_saving_change(
    day: date, utc: datetime, financed: bool
) -> None:
    assert liquidation_utc(day, LATE) == utc
    entry = london(day, time(10))
    assert due_of(entry, day, LATE) == (utc, LATE_LIQUIDATION, False)  # control recomputed apart
    # A position held to the deadline crosses 17:00 New York (ADR-035 financing) only in the gap weeks.
    assert (trading_day(utc) != trading_day(entry)) is financed
    # The reference is untouched: 17:00 London, time exit first when earlier.
    assert liquidation_utc(day, Day02Params()) == london(day, time(17))
    assert due_of(entry, day, Day02Params()) == (entry + timedelta(hours=2), TIME_EXIT, False)


# ---------------------------------------------------------------- engine


@pytest.mark.parametrize(("day", "deadline"), [(WINTER, (21, 55)), (SUMMER, (21, 55))], ids=["GMT", "BST"])
def test_late_keeps_the_position_beyond_two_hours_and_17_00_until_22_55_paris(
    tmp_path: Path, day: date, deadline: tuple[int, int]
) -> None:
    ticks = held(day, at(day, 22, 30))
    reference = run(tmp_path / "ref", ticks, Day02Params(), day)
    late = run(tmp_path / "late", ticks, LATE, day)
    # Same decision, execution, stop, target and size.
    (r,), (t,) = reference.trades, late.trades
    assert (r.decided_utc, r.entry_utc, r.entry_price, r.stop, r.size) == (
        t.decided_utc,
        t.entry_utc,
        t.entry_price,
        t.stop,
        t.size,
    )
    assert (r.exit_utc, r.exit_reason) == (at(day, 12, 10, 30), TIME_EXIT)
    # 22:55 Paris = 21:55 London in both seasons; a tick exactly at the deadline does not execute it.
    assert (t.exit_utc, t.exit_reason) == (at(day, *deadline, 30), LATE_LIQUIDATION)
    (closing,) = late.closings
    assert (closing.decided_utc, closing.order, closing.coincident) == (at(day, *deadline), LATE_LIQUIDATION, False)
    assert closing.delay == timedelta(seconds=30) and closing.silence_kind is Silence.NONE
    assert "financement overnight" not in t.costs_quote and late.unplanned_nights == []
    # No new entry while the position is open; the attempt ends with the real close.
    first = late.attempts[0]
    assert (first.ended_utc, first.ended_by) == (t.exit_utc, POSITION_CLOSED)
    assert all(a.resume_utc >= got(t.exit_utc) for a in late.attempts[1:])
    report = closings(late)
    assert report["ok"] and report["orders"] == {LATE_LIQUIDATION: 1}
    assert report["positions_after_17h"] == 1  # closed 30 s after its own liquidation instant
    flow = funnel(late.attempts, all_trades(late), exit_outcomes(LATE))
    assert flow["ok"] and flow["executed_outcomes"][LATE_LIQUIDATION] == 1


def test_late_target_and_stop_still_close_the_position_in_the_extra_hours(tmp_path: Path) -> None:
    day = WINTER
    target = held(day, at(day, 15, 0)) + fill(at(day, 15, 0), at(day, 22, 30), "1.13310")
    (t,) = run(tmp_path / "target", target, LATE, day).trades
    assert (t.exit_utc, t.exit_reason) == (at(day, 15, 0), "CIBLE")
    stop = held(day, at(day, 18, 0)) + fill(at(day, 18, 0), at(day, 22, 30), "1.13040")
    (s,) = run(tmp_path / "stop", stop, LATE, day).trades
    assert s.exit_utc == at(day, 18, 0) and (s.exit_reason or "").startswith("STOP")


@pytest.mark.parametrize("day", [SPRING_GAP, AUTUMN_GAP])
def test_late_crossing_17_00_new_york_on_the_same_calendar_day_is_financed(tmp_path: Path, day: date) -> None:
    late = run(tmp_path, held(day, at(day, 22, 30)), LATE, day)
    (t,) = late.trades
    assert (t.exit_utc, t.exit_reason) == (at(day, 21, 55, 30), LATE_LIQUIDATION)
    assert got(t.exit_utc).date() == got(t.entry_utc).date()  # same calendar day, one night financed
    assert t.costs_quote["financement overnight"] == D("1") * t.size
    assert late.unplanned_nights == [t.decided_utc]
    assert [j.utc for j in late.journal if j.kind == UNPLANNED_NIGHT] == [t.exit_utc]
    assert closings(late)["ok"]


def test_late_deadline_after_the_weekly_close_executes_at_the_first_quote_of_the_next_week(tmp_path: Path) -> None:
    day = SPRING_FRIDAY  # the week closes at 17:00 New York = 21:00 UTC, before the 21:55 UTC deadline
    reopen = datetime(2019, 3, 17, 21, 0, 5, tzinfo=UTC)  # Sunday 17:00:05 New York
    ticks = [*held(day, datetime(2019, 3, 15, 21, 0, tzinfo=UTC)), tick(reopen, "1.13200")]
    late = run(tmp_path, ticks, LATE, day, days=3)
    (t,) = late.trades
    assert (t.exit_utc, t.exit_reason) == (reopen, LATE_LIQUIDATION)  # no price invented on Friday
    assert t.costs_quote["financement overnight"] == D("3") * t.size  # Fri -> Mon trading days
    (closing,) = late.closings
    assert closing.silence_kind is Silence.KNOWN_CLOSURE
    assert closings(late)["ok"]


def test_late_no_quote_after_the_deadline_leaves_the_position_open_with_its_order_due(tmp_path: Path) -> None:
    day = WINTER
    late = run(tmp_path, held(day, at(day, 21, 50)), LATE, day)
    assert late.trades == [] and late.open_trade is not None
    assert late.unexecuted_closing == (at(day, 21, 55), LATE_LIQUIDATION)


# ---------------------------------------------------------------- causality


@pytest.mark.parametrize("cut", [(11, 0), (16, 0), (20, 0)])
def test_late_ticks_after_an_instant_change_nothing_known_at_it(tmp_path: Path, cut: tuple[int, int]) -> None:
    day, x = WINTER, at(WINTER, *cut)
    full = held(day, at(day, 22, 30))
    before = [t for t in full if t.ts_utc < x]
    cases = {
        "cut": before,
        "stop": before + fill(x, at(day, 22, 30), "1.13040"),
        "target": before + fill(x, at(day, 22, 30), "1.13310"),
    }
    reference = run(tmp_path / "full", full, LATE, day)
    for case, ticks in cases.items():
        other = run(tmp_path / case, ticks, LATE, day)
        a, b = reference.attempts[0], other.attempts[0]
        assert (a.resume_utc, a.search.configuration, a.entry_outcome) == (
            b.resume_utc,
            b.search.configuration,
            b.entry_outcome,
        ), case
        assert [j for j in reference.journal if j.utc < x] == [j for j in other.journal if j.utc < x], case
        (t,) = all_trades(reference)
        (u,) = all_trades(other)
        assert (t.decided_utc, t.entry_utc, t.entry_price, t.size) == (
            u.decided_utc,
            u.entry_utc,
            u.entry_price,
            u.size,
        )
        assert u.exit_utc is None or u.exit_utc >= x  # nothing closed before the change
    # Truncated: the position stays open, its order is due later, no exit nor price invented.
    cut_run = run(tmp_path / "cut-only", before, LATE, day)
    assert cut_run.trades == [] and cut_run.open_trade is not None
