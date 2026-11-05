"""M5/M15 candles built from ticks (protocol docs/experiments/DATA_M5_M15_2015_2021.md). Synthetic files only.

Thursday 2019-03-07, US winter time, UK winter time: London = UTC.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pytest

from forex_bot.history.bars import build_bars
from forex_bot.history.calendar import Timeframe
from forex_bot.history.intraday import (
    NO_TICK,
    NO_VALID_TICK,
    WINDOW_END,
    WINDOW_START,
    Content,
    Grid,
    IntradayBuild,
    build_intraday,
    check_m5_to_m15,
    check_m15_to_h1,
    check_no_leak,
    check_totals,
    check_window,
    select_files,
)
from forex_bot.history.intraday_audit import audit, checks_failed, london_instant, london_sessions, session_anomalies
from forex_bot.history.store import HistoryStore, IngestRequest

HEADER = "Gmt time,Ask,Bid,AskVolume,BidVolume\n"
RETRIEVED = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
GAP_FLAG = "trou de cotation > 10 min pendant l'ouverture prévue"


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0, us: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, us, tzinfo=UTC)


def line(ts: datetime, ask: str, bid: str, av: str = "1.5", bv: str = "2.25") -> str:
    return f"{ts.strftime('%d.%m.%Y %H:%M:%S')}.{ts.microsecond // 1000:03d},{ask},{bid},{av},{bv}\n"


def every_minute(start: datetime, end: datetime, base: str = "1.10000") -> list[str]:
    """One tick per minute; bid rises by 0.00001 per minute, ask = bid + 0.00010."""
    rows, minute, cursor = [], 0, start
    while cursor < end:
        bid = D(base) + D("0.00001") * minute
        rows.append(line(cursor, f"{bid + D('0.00010'):.5f}", f"{bid:.5f}"))
        cursor += timedelta(minutes=1)
        minute += 1
    return rows


def store_with(tmp_path: Path, name: str, files: list[tuple[list[str], datetime, datetime]]) -> HistoryStore:
    store = HistoryStore(tmp_path / name)
    for i, (rows, start, end) in enumerate(files):
        path = tmp_path / f"{name}-{i}.csv"
        path.write_text(HEADER + "".join(rows), encoding="utf-8")
        store.ingest(IngestRequest(path, "dukascopy", "EURUSD", "dukascopy-ticks-csv-v1", start, end, RETRIEVED))
    return store


def build(store: HistoryStore, end: datetime = WINDOW_END) -> IntradayBuild:
    return build_intraday(store, "dukascopy", "EURUSD", WINDOW_START, end)


def bar(result: IntradayBuild, grid: Grid, start: datetime) -> dict[str, Any]:
    return next(b for b in result.bars[grid] if b["start_utc"] == start)


def prices(b: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        b[k] for k in ("bid_open", "bid_high", "bid_low", "bid_close", "ask_open", "ask_high", "ask_low", "ask_close")
    )


# ---------------------------------------------------------------- window and file selection


@pytest.mark.parametrize(
    ("start", "end"),
    [(utc(2014, 12, 31), utc(2016, 1, 1)), (utc(2021, 1, 1), utc(2022, 1, 2)), (utc(2021, 1, 1), utc(2024, 1, 1))],
)
def test_window_outside_2015_2021_is_refused(start: datetime, end: datetime) -> None:
    with pytest.raises(ValueError, match="2022-2025"):
        check_window(start, end)


def test_files_of_2022_are_never_opened(tmp_path: Path) -> None:
    friday = every_minute(utc(2021, 12, 31, 10), utc(2021, 12, 31, 11))
    monday = every_minute(utc(2022, 1, 3, 10), utc(2022, 1, 3, 11))
    store = store_with(
        tmp_path,
        "s",
        [(friday, utc(2021, 12, 31), utc(2022, 1, 1)), (monday, utc(2022, 1, 3), utc(2022, 1, 4))],
    )
    files = select_files(store, "dukascopy", "EURUSD", WINDOW_START, WINDOW_END)
    assert [f.period_end_utc for f in files] == [utc(2022, 1, 1)]
    result = build(store)
    assert result.ticks["total"] == 60
    assert all(b["end_utc"] <= WINDOW_END for grid in Grid for b in result.bars[grid])


def test_a_file_straddling_the_window_end_stops_the_build(tmp_path: Path) -> None:
    rows = every_minute(utc(2021, 12, 31, 10), utc(2021, 12, 31, 11))
    store = store_with(tmp_path, "s", [(rows, utc(2021, 12, 31), utc(2022, 1, 2))])
    with pytest.raises(ValueError, match="à cheval"):
        build(store)


# ---------------------------------------------------------------- OHLC, tick conventions, boundaries

HAND_ROWS = [
    line(utc(2019, 3, 7, 10, 0, 10), "1.12010", "1.12000"),
    line(utc(2019, 3, 7, 10, 0, 10), "1.12015", "1.12005"),  # same timestamp: kept, file order
    line(utc(2019, 3, 7, 10, 2, 0), "1.12050", "1.12040"),
    line(utc(2019, 3, 7, 10, 2, 0), "1.12050", "1.12040"),  # exact repeat: kept, counted
    line(utc(2019, 3, 7, 10, 1, 0), "1.11990", "1.11980"),  # out of order in the file: placed by time
    line(utc(2019, 3, 7, 10, 3, 0), "1.12000", "1.12010"),  # bid > ask: excluded
    line(utc(2019, 3, 7, 10, 4, 59, 999000), "1.12030", "1.12020"),
    line(utc(2019, 3, 7, 10, 5, 0), "1.12070", "1.12060"),  # exactly on the boundary: next M5
    line(utc(2019, 3, 7, 10, 8, 0), "0.00000", "1.12060"),  # non-positive: excluded
    line(utc(2019, 3, 7, 10, 9, 0), "1.12090", "1.12080"),
    line(utc(2019, 3, 7, 10, 12, 0), "1.12110", "1.12100"),
    line(utc(2019, 3, 7, 10, 14, 0), "1.12120", "1.12110"),
]


def test_m5_and_m15_ohlc_by_hand_with_reader_tick_conventions(tmp_path: Path) -> None:
    store = store_with(tmp_path, "s", [(HAND_ROWS, utc(2019, 3, 7, 10), utc(2019, 3, 7, 10, 15))])
    result = build(store)
    first = bar(result, Grid.M5, utc(2019, 3, 7, 10))
    # Order (time, raw_row): 10:00:10 x2, 10:01 (out of order in file), 10:02 x2, [10:03 crossed], 10:04:59.999
    assert prices(first) == (
        D("1.12000"), D("1.12040"), D("1.11980"), D("1.12020"),
        D("1.12010"), D("1.12050"), D("1.11990"), D("1.12030"),
    )  # fmt: skip
    assert (first["tick_count"], first["excluded_ticks"], first["crossed_ticks"]) == (6, 1, 1)
    assert first["content"] is Content.VALID
    assert first["flags_at_close"] == ["1 tick(s) invalides exclus"] and not first["complete_at_close"]
    second = bar(result, Grid.M5, utc(2019, 3, 7, 10, 5))
    assert second["bid_open"] == D("1.12060") and second["first_tick_utc"] == utc(2019, 3, 7, 10, 5)
    assert (second["tick_count"], second["non_positive_ticks"]) == (2, 1)
    m15 = bar(result, Grid.M15, utc(2019, 3, 7, 10))
    assert prices(m15) == (
        D("1.12000"), D("1.12110"), D("1.11980"), D("1.12110"),
        D("1.12010"), D("1.12120"), D("1.11990"), D("1.12120"),
    )  # fmt: skip
    assert (m15["tick_count"], m15["excluded_ticks"], m15["valid_m5_subslots"]) == (10, 2, 3)
    assert result.ticks["total"] == 12  # nothing deleted
    assert (result.ticks["simultaneous_timestamps"], result.ticks["simultaneous_ticks"]) == (2, 4)
    assert result.ticks["exact_consecutive_repeats"] == 1
    assert result.ticks["out_of_order_within_file"] == 1
    assert result.out_of_order_ts == [utc(2019, 3, 7, 10, 1)]


def test_empty_and_invalid_only_slots_stay_distinct_and_unfilled(tmp_path: Path) -> None:
    rows = every_minute(utc(2019, 3, 7, 10), utc(2019, 3, 7, 11))
    by_minute = {i: r for i, r in enumerate(rows)}
    for minute in range(20, 25):
        del by_minute[minute]  # 10:20-10:25: no tick at all (silence 10:19 -> 10:25, 6 min)
    for minute in range(30, 35):
        by_minute[minute] = line(utc(2019, 3, 7, 10, minute), "1.10000", "1.10050")  # only crossed ticks
    store = store_with(tmp_path, "s", [(list(by_minute.values()), utc(2019, 3, 7, 10), utc(2019, 3, 7, 11))])
    result = build(store)
    empty = bar(result, Grid.M5, utc(2019, 3, 7, 10, 20))
    assert empty["content"] is Content.EMPTY and empty["expected_open"]
    assert all(v is None for v in prices(empty)) and empty["tick_count"] == empty["excluded_ticks"] == 0
    assert empty["flags_at_close"] == [NO_TICK] and not empty["complete_at_close"]  # never "quiet market"
    invalid = bar(result, Grid.M5, utc(2019, 3, 7, 10, 30))
    assert invalid["content"] is Content.INVALID_ONLY and all(v is None for v in prices(invalid))
    assert invalid["flags_at_close"] == [NO_VALID_TICK, "5 tick(s) invalides exclus"]
    assert invalid["first_tick_utc"] is None
    partial = bar(result, Grid.M15, utc(2019, 3, 7, 10, 15))
    assert partial["content"] is Content.VALID and partial["valid_m5_subslots"] == 2
    # Informative flag only: the rule for an empty sub-slot is the operator's decision.
    assert partial["flags_at_close"] == ["sous-créneaux M5 sans tick valide : 1/3"] and partial["complete_at_close"]
    # Prices of an M15 with an empty sub-slot come from its own valid ticks: minutes 15-19 and 25-29.
    assert (partial["bid_open"], partial["bid_close"]) == (D("1.10015"), D("1.10029"))
    with_invalid = bar(result, Grid.M15, utc(2019, 3, 7, 10, 30))
    assert (with_invalid["tick_count"], with_invalid["excluded_ticks"]) == (10, 5)
    assert not with_invalid["complete_at_close"]


def test_no_empty_row_is_invented_during_the_weekly_closure(tmp_path: Path) -> None:
    friday = every_minute(utc(2019, 3, 8, 21), utc(2019, 3, 8, 22))  # close at 22:00 UTC (17:00 New York)
    saturday = [line(utc(2019, 3, 9, 12, 0), "1.12010", "1.12000")]
    sunday = every_minute(utc(2019, 3, 10, 21), utc(2019, 3, 10, 22), base="1.12000")  # reopen 21:00 (US DST)
    store = store_with(tmp_path, "s", [(friday + saturday + sunday, utc(2019, 3, 8, 21), utc(2019, 3, 10, 22))])
    result = build(store)
    closed = [b for b in result.bars[Grid.M5] if not b["expected_open"]]
    assert [b["start_utc"] for b in closed] == [utc(2019, 3, 9, 12)]
    assert closed[0]["flags_at_close"] == ["ticks pendant la fermeture prévue"]
    assert not any(b["content"] is Content.EMPTY for b in result.bars[Grid.M5])
    assert len([b for b in result.bars[Grid.M15] if b["expected_open"]]) == 8


# ---------------------------------------------------------------- close-time status vs retrospective audit


def test_m15_status_is_computed_at_its_own_close_not_inherited(tmp_path: Path) -> None:
    """Last tick 08:01, next 08:14: 4 min known at 08:05, 9 at 08:10, 13 (> 10) at 08:15."""
    rows = every_minute(utc(2019, 3, 7, 7), utc(2019, 3, 7, 8, 2)) + every_minute(
        utc(2019, 3, 7, 8, 14), utc(2019, 3, 7, 9), base="1.20000"
    )
    store = store_with(tmp_path, "s", [(rows, utc(2019, 3, 7, 7), utc(2019, 3, 7, 9))])
    result = build(store)
    first = bar(result, Grid.M5, utc(2019, 3, 7, 8))
    second = bar(result, Grid.M5, utc(2019, 3, 7, 8, 5))
    assert first["complete_at_close"] and first["flags_at_close"] == []  # 4 min known at 08:05
    assert GAP_FLAG not in second["flags_at_close"]  # 9 min known at 08:10: not above the threshold yet
    assert second["flags_at_close"] == [NO_TICK]
    assert not first["complete"] and GAP_FLAG in first["flags"]  # retrospective audit sees 13 min
    m15 = bar(result, Grid.M15, utc(2019, 3, 7, 8))
    assert GAP_FLAG in m15["flags_at_close"] and not m15["complete_at_close"]  # 13 min known at 08:15


def _silence_after(tmp_path: Path, name: str, next_tick: datetime) -> IntradayBuild:
    rows = every_minute(utc(2019, 3, 7, 8), utc(2019, 3, 7, 10)) + every_minute(next_tick, utc(2019, 3, 7, 11))
    return build(store_with(tmp_path, name, [(rows, utc(2019, 3, 7, 8), utc(2019, 3, 7, 11))]))


def test_changing_only_later_ticks_never_changes_a_close_time_status(tmp_path: Path) -> None:
    """Last tick 09:59; the next one at 10:01 or at 10:19 is unknowable at 10:00."""
    early = _silence_after(tmp_path, "early", utc(2019, 3, 7, 10, 1))
    late = _silence_after(tmp_path, "late", utc(2019, 3, 7, 10, 19))
    close = utc(2019, 3, 7, 10)
    for grid in Grid:
        a = [b for b in early.bars[grid] if b["end_utc"] <= close]
        b_ = [b for b in late.bars[grid] if b["end_utc"] <= close]
        assert len(a) == len(b_) == 120 // grid.minutes
        keys = ("start_utc", "content", "tick_count", "bid_close", "complete_at_close", "flags_at_close")
        assert [tuple(x[k] for k in keys) for x in a] == [tuple(x[k] for k in keys) for x in b_]
        last_early, last_late = a[-1], b_[-1]
        assert last_early["complete"] and not last_late["complete"]  # only the audit looks past 10:00


def test_truncated_build_gives_the_same_close_time_candles(tmp_path: Path) -> None:
    thursday = every_minute(utc(2019, 3, 7, 0), utc(2019, 3, 8, 0))
    friday = every_minute(utc(2019, 3, 8, 0), utc(2019, 3, 8, 22), base="1.20000")
    store = store_with(
        tmp_path, "s", [(thursday, utc(2019, 3, 7), utc(2019, 3, 8)), (friday, utc(2019, 3, 8), utc(2019, 3, 9))]
    )
    full, truncated = build(store), build(store, end=utc(2019, 3, 8))
    leak = check_no_leak(full, truncated)
    assert leak["5m"]["compared"] > 0 and leak["15m"]["compared"] > 0
    assert leak["5m"]["close_time_differences"] == leak["15m"]["close_time_differences"] == []
    tampered = build(store, end=utc(2019, 3, 8))
    tampered.bars[Grid.M5][10]["flags_at_close"] = [GAP_FLAG]
    assert check_no_leak(full, tampered)["5m"]["close_time_differences"]


# ---------------------------------------------------------------- conservation checks


def _day_store(tmp_path: Path) -> HistoryStore:
    rows = every_minute(utc(2019, 3, 7, 6), utc(2019, 3, 7, 12))
    rows.insert(71, line(utc(2019, 3, 7, 7, 10, 30), "1.10000", "1.10050"))  # crossed, inside 07:00 H1
    rows = [r for r in rows if not r.startswith("07.03.2019 09:2")]  # 09:20-09:29: 11-min silence
    # 11:00-12:00: only invalid ticks, so the existing H1 has no 11:00 row
    rows = [r for r in rows if not r.startswith("07.03.2019 11:")]
    rows += [line(utc(2019, 3, 7, 11, m), "1.10000", "1.10050") for m in range(0, 60, 7)]
    return store_with(tmp_path, "s", [(rows, utc(2019, 3, 7, 6), utc(2019, 3, 7, 12))])


def test_conservation_m5_m15_h1_and_totals(tmp_path: Path) -> None:
    store = _day_store(tmp_path)
    result = build(store)
    h1, _ = build_bars(store, "dukascopy", "EURUSD")
    totals = check_totals(result)
    assert totals["ok"] and totals["declared_by_files"] == result.ticks["total"]
    m5_m15 = check_m5_to_m15(result.bars[Grid.M5], result.bars[Grid.M15])
    assert m5_m15["mismatches"] == m5_m15["orphan_m5_groups"] == m5_m15["gap_status_mismatches"] == []
    m15_h1 = check_m15_to_h1(result.bars[Grid.M15], h1[Timeframe.H1])
    assert m15_h1["checked_h1"] == 5 and m15_h1["hours_with_invalid_ticks_only"] == 1
    assert m15_h1["mismatches"] == m15_h1["h1_missing"] == m15_h1["h1_without_valid_m15"] == []
    assert m15_h1["gap_status_mismatches"] == []
    seven = bar(result, Grid.M15, utc(2019, 3, 7, 7))
    assert seven["excluded_ticks"] == 1 and not seven["complete_at_close"]
    # Incomplete candles with valid quotes are checked too: the 09:15 M15 touches the 11-min silence.
    assert GAP_FLAG in bar(result, Grid.M15, utc(2019, 3, 7, 9, 15))["flags_at_close"]


def test_conservation_checks_detect_a_tampered_candle(tmp_path: Path) -> None:
    store = _day_store(tmp_path)
    result = build(store)
    h1, _ = build_bars(store, "dukascopy", "EURUSD")
    target = bar(result, Grid.M15, utc(2019, 3, 7, 9, 45))  # last M15 of the hour: its close is the H1 close
    target["bid_close"] += D("0.00001")
    assert check_m5_to_m15(result.bars[Grid.M5], result.bars[Grid.M15])["mismatches"][0]["fields"] == ["bid_close"]
    assert check_m15_to_h1(result.bars[Grid.M15], h1[Timeframe.H1])["mismatches"][0]["fields"] == ["bid_close"]
    target["bid_close"] -= D("0.00001")
    bar(result, Grid.M5, utc(2019, 3, 7, 11))["tick_count"] += 1
    assert not check_totals(result)["ok"]


def test_audit_report_passes_on_consistent_synthetic_data(tmp_path: Path) -> None:
    store = _day_store(tmp_path)
    result = build(store)
    h1, _ = build_bars(store, "dukascopy", "EURUSD")
    report = audit(result, h1[Timeframe.H1], None)
    assert checks_failed(report) == []
    assert report["grids"]["5m"]["total"]["expected_EMPTY"] == 5  # 09:20, 09:25, then 11:15, 11:30, 11:50
    assert report["grids"]["5m"]["total"]["expected_INVALID_ONLY"] == 9
    assert report["silences"]["gt_60s_by_scope"]["day01_window"]["10-15 min"] == 1


def test_silence_distribution_does_not_depend_on_the_threshold(tmp_path: Path) -> None:
    store = _day_store(tmp_path)
    ten = build(store)
    short = build_intraday(store, "dukascopy", "EURUSD", WINDOW_START, WINDOW_END, timedelta(seconds=30))
    assert ten.silences == short.silences and ten.short_intervals == short.short_intervals
    assert len(short.gaps) > len(ten.gaps) == 2


# ---------------------------------------------------------------- London windows


@pytest.mark.parametrize(
    ("day", "utc_hour"),
    [
        (date(2019, 3, 29), 1),  # US already on summer time (10 March), UK not yet: London = UTC
        (date(2019, 4, 1), 0),  # BST after Sunday 31 March
        (date(2019, 10, 25), 0),  # BST until Sunday 27 October
        (date(2019, 10, 28), 1),  # GMT, while the US is on summer time until 3 November
    ],
)
def test_day01_window_follows_london_time_across_offset_weeks(day: date, utc_hour: int) -> None:
    assert london_instant(day, datetime.min.time().replace(hour=1)).hour == utc_hour


def test_no_day01_window_straddles_a_clock_change_or_a_weekly_closure() -> None:
    days = london_sessions(WINDOW_START, WINDOW_END)
    assert days[0] == date(2015, 1, 1) and days[-1] == date(2021, 12, 31)
    assert all(d.weekday() < 5 for d in days)
    assert session_anomalies(days) == {"clock_change_inside_window": [], "weekly_closure_inside_window": []}


def test_gaps_follow_the_reader_convention(tmp_path: Path) -> None:
    from forex_bot.history.bars import summarize_ticks

    store = _day_store(tmp_path)
    assert build(store).gaps == summarize_ticks(store, "dukascopy", "EURUSD").gaps
