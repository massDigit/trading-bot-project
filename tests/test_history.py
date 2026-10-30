"""Historical data pipeline. Synthetic CSV files in the declared format; no network.

Calendar facts used (America/New_York): EST (UTC-5) until Sunday 2019-03-10 02:00, EDT (UTC-4) after.
New York 17:00 = 22:00 UTC before the change, 21:00 UTC after.
"""

from __future__ import annotations

import os
import re
import stat
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest

from forex_bot.history import store as store_module
from forex_bot.history.bars import build_bars, summarize_ticks
from forex_bot.history.calendar import (
    MarketState,
    Partition,
    Timeframe,
    candle_end,
    candle_start,
    market_state,
    partitions_touched,
    trading_day,
)
from forex_bot.history.formats import FormatError
from forex_bot.history.quality import build_report
from forex_bot.history.store import HistoryStore, IngestError, IngestRequest

HEADER = "Gmt time,Ask,Bid,AskVolume,BidVolume\n"
RETRIEVED = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0, us: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, us, tzinfo=UTC)


def line(ts: datetime, ask: str, bid: str, av: str = "1.5", bv: str = "2.25") -> str:
    return f"{ts.strftime('%d.%m.%Y %H:%M:%S')}.{ts.microsecond // 1000:03d},{ask},{bid},{av},{bv}\n"


def write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text(HEADER + "".join(rows), encoding="utf-8")
    return path


def ingest(store: HistoryStore, path: Path, start: datetime, end: datetime) -> store_module.IngestResult:
    return store.ingest(IngestRequest(path, "dukascopy", "EURUSD", "dukascopy-ticks-csv-v1", start, end, RETRIEVED))


def every_minute(start: datetime, end: datetime, base: str = "1.10000") -> list[str]:
    """One tick per minute; bid rises by 0.00001 per minute, ask = bid + 0.00010."""
    rows, minute, cursor = [], 0, start
    while cursor < end:
        bid = D(base) + D("0.00001") * minute
        rows.append(line(cursor, f"{bid + D('0.00010'):.5f}", f"{bid:.5f}"))
        cursor += timedelta(minutes=1)
        minute += 1
    return rows


# ---------------------------------------------------------------- calendar


def test_candle_boundaries_follow_new_york_close_across_dst() -> None:
    # Friday 2019-03-08 (EST): trading day Thu 22:00 UTC -> Fri 22:00 UTC
    friday_noon = utc(2019, 3, 8, 12, 30)
    assert trading_day(friday_noon) == date(2019, 3, 8)
    assert candle_start(friday_noon, Timeframe.D1) == utc(2019, 3, 7, 22)
    assert candle_end(utc(2019, 3, 7, 22), Timeframe.D1) == utc(2019, 3, 8, 22)
    assert candle_start(friday_noon, Timeframe.H4) == utc(2019, 3, 8, 10)  # 22, 02, 06, 10, 14, 18
    # Monday 2019-03-11 (EDT): trading day Sun 21:00 UTC -> Mon 21:00 UTC
    monday_noon = utc(2019, 3, 11, 12, 30)
    assert candle_start(monday_noon, Timeframe.D1) == utc(2019, 3, 10, 21)
    assert candle_start(monday_noon, Timeframe.H4) == utc(2019, 3, 11, 9)  # 21, 01, 05, 09, 13, 17
    assert candle_start(monday_noon, Timeframe.H1) == utc(2019, 3, 11, 12)


@pytest.mark.parametrize(
    ("moment", "state"),
    [
        (utc(2019, 3, 8, 21, 59), MarketState.OPEN),  # Friday 16:59 New York
        (utc(2019, 3, 8, 22, 0), MarketState.WEEKLY_CLOSURE),  # Friday 17:00 New York
        (utc(2019, 3, 9, 12, 0), MarketState.WEEKLY_CLOSURE),
        (utc(2019, 3, 10, 20, 59), MarketState.WEEKLY_CLOSURE),  # Sunday 16:59 EDT
        (utc(2019, 3, 10, 21, 0), MarketState.OPEN),  # Sunday 17:00 EDT -> Monday trading day
        (utc(2019, 12, 25, 12, 0), MarketState.PROBABLE_HOLIDAY),
    ],
)
def test_weekly_closure_and_sunday_reopening(moment: datetime, state: MarketState) -> None:
    assert market_state(moment) is state


def test_sunday_evening_belongs_to_monday_no_sunday_candle() -> None:
    assert trading_day(utc(2019, 3, 10, 21, 30)) == date(2019, 3, 11)


def test_partitions() -> None:
    assert partitions_touched(utc(2019, 3, 7), utc(2019, 3, 13)) == {Partition.DEVELOPMENT}
    assert partitions_touched(utc(2023, 1, 1), utc(2023, 1, 2)) == {Partition.VALIDATION}
    assert Partition.FINAL_TEST in partitions_touched(utc(2023, 12, 31), utc(2024, 1, 2))


def test_naive_dates_are_refused() -> None:
    with pytest.raises(ValueError):
        candle_start(datetime(2019, 3, 8, 12), Timeframe.H1)


# ---------------------------------------------------------------- OHLC by hand

HAND_ROWS = [
    line(utc(2019, 3, 7, 10, 0, 0), "1.12010", "1.12000"),
    line(utc(2019, 3, 7, 10, 0, 0), "1.12015", "1.12005"),  # same ms, different quote: legitimate
    line(utc(2019, 3, 7, 10, 15, 30, 500000), "1.12050", "1.12040"),
    line(utc(2019, 3, 7, 10, 15, 30, 500000), "1.12050", "1.12040"),  # exact repeat: kept, counted
    line(utc(2019, 3, 7, 10, 30, 0), "1.11990", "1.11980"),
    line(utc(2019, 3, 7, 10, 45, 0), "1.12000", "1.12010"),  # bid > ask: excluded
    line(utc(2019, 3, 7, 10, 59, 59, 999000), "1.12030", "1.12020"),
]


def test_h1_bid_ask_ohlc_computed_by_hand(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    ingest(store, write_csv(tmp_path / "hand.csv", HAND_ROWS), utc(2019, 3, 7, 10), utc(2019, 3, 7, 11))
    bars, summary = build_bars(store, "dukascopy", "EURUSD")
    (h1,) = bars[Timeframe.H1]
    assert h1["start_utc"] == utc(2019, 3, 7, 10) and h1["end_utc"] == utc(2019, 3, 7, 11)
    # bid: open = first row (1.12000, not 1.12005), high 1.12040, low 1.11980, close 1.12020
    assert (h1["bid_open"], h1["bid_high"], h1["bid_low"], h1["bid_close"]) == (
        D("1.12000"),
        D("1.12040"),
        D("1.11980"),
        D("1.12020"),
    )
    # ask: open 1.12010, high 1.12050, low 1.11990, close 1.12030 (crossed tick excluded from both sides)
    assert (h1["ask_open"], h1["ask_high"], h1["ask_low"], h1["ask_close"]) == (
        D("1.12010"),
        D("1.12050"),
        D("1.11990"),
        D("1.12030"),
    )
    assert (h1["tick_count"], h1["excluded_ticks"]) == (6, 1)
    assert summary.crossed == 1
    # gaps of 15 min > 10 min while open: kept, flagged, not filled
    assert not h1["complete"]
    assert any(f.startswith("trou de cotation") for f in h1["flags"])


def test_simultaneous_ticks_are_not_duplicates(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    ingest(store, write_csv(tmp_path / "hand.csv", HAND_ROWS), utc(2019, 3, 7, 10), utc(2019, 3, 7, 11))
    summary = summarize_ticks(store, "dukascopy", "EURUSD")
    assert summary.total == 7  # nothing removed
    assert (summary.simultaneous_groups, summary.simultaneous_ticks) == (2, 4)
    assert summary.exact_repeats == 1  # reported, still kept


# ---------------------------------------------------------------- H4 / D1 from a full trading day


def test_h4_d1_aggregation_and_completeness(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    # Friday trading day: Thu 22:00 UTC -> Fri 22:00 UTC, one tick per minute (1440 ticks)
    rows = every_minute(utc(2019, 3, 7, 22), utc(2019, 3, 8, 22))
    rows.insert(600, line(utc(2019, 3, 8, 7, 59, 30), "1.12510", "1.12500"))  # spike, inside 06:00-10:00 H4
    ingest(store, write_csv(tmp_path / "fri.csv", rows), utc(2019, 3, 7, 22), utc(2019, 3, 9))
    bars, _ = build_bars(store, "dukascopy", "EURUSD")
    (d1,) = bars[Timeframe.D1]
    assert (d1["start_utc"], d1["end_utc"]) == (utc(2019, 3, 7, 22), utc(2019, 3, 8, 22))
    # bid opens at 1.10000 (minute 0), closes at 1.10000 + 1439 x 0.00001 = 1.11439, high = spike 1.12500
    assert (d1["bid_open"], d1["bid_close"], d1["bid_high"], d1["bid_low"]) == (
        D("1.10000"),
        D("1.11439"),
        D("1.12500"),
        D("1.10000"),
    )
    assert d1["ask_close"] == D("1.11449") and d1["ask_high"] == D("1.12510")
    assert d1["tick_count"] == 1441 and d1["expected_hours"] == 24 and d1["present_hours"] == 24
    assert d1["complete"], d1["flags"]
    h4 = bars[Timeframe.H4]
    assert [b["start_utc"].hour for b in h4] == [22, 2, 6, 10, 14, 18]
    assert all(b["complete"] for b in h4)
    assert h4[2]["bid_high"] == D("1.12500")  # spike lands in the 06:00 UTC candle only
    assert len(bars[Timeframe.H1]) == 24


def test_missing_hour_is_reported_not_filled(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    rows = every_minute(utc(2019, 3, 7, 22), utc(2019, 3, 8, 22))
    rows = [r for r in rows if not r.startswith("08.03.2019 03:")]  # whole 03:00 UTC hour missing
    ingest(store, write_csv(tmp_path / "fri.csv", rows), utc(2019, 3, 7, 22), utc(2019, 3, 9))
    bars, summary = build_bars(store, "dukascopy", "EURUSD")
    assert utc(2019, 3, 8, 3) not in {b["start_utc"] for b in bars[Timeframe.H1]}  # no invented candle
    (d1,) = bars[Timeframe.D1]
    assert not d1["complete"] and "heures manquantes : 1/24" in d1["flags"]
    assert not bars[Timeframe.H4][1]["complete"]  # 02:00-06:00 UTC
    report = build_report(store, "dukascopy", "EURUSD", summary, bars)
    assert utc(2019, 3, 8, 3).isoformat() in report["missing_open_hours"]
    assert any(g["classification"].startswith("TROU") for g in report["gaps"])


def test_weekend_is_a_normal_closure_and_candle_beyond_coverage_is_flagged(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    friday = every_minute(utc(2019, 3, 8, 20), utc(2019, 3, 8, 22))
    sunday = every_minute(utc(2019, 3, 10, 21), utc(2019, 3, 10, 23), base="1.12000")
    ingest(store, write_csv(tmp_path / "w.csv", friday + sunday), utc(2019, 3, 8, 20), utc(2019, 3, 10, 23))
    bars, summary = build_bars(store, "dukascopy", "EURUSD")
    report = build_report(store, "dukascopy", "EURUSD", summary, bars)
    weekend = [g for g in report["gaps"] if g["duration_min"] > 2000]
    assert len(weekend) == 1 and weekend[0]["classification"] == "fermeture normale (horaire prévu)"
    assert summary.during_weekly_closure == 0
    (transition,) = report["weekly_transitions"]
    assert transition["expected_close_utc"] == utc(2019, 3, 8, 22).isoformat()
    assert transition["expected_reopen_utc"] == utc(2019, 3, 10, 21).isoformat()  # after the US DST change
    assert transition["first_tick_minus_expected_reopen_min"] == 0.0
    monday = bars[Timeframe.D1][-1]  # Sun 21:00 -> Mon 21:00 UTC, data stops at Sun 23:00
    assert monday["start_utc"] == utc(2019, 3, 10, 21)
    assert not monday["complete"]
    assert any(f.startswith("hors couverture") for f in monday["flags"])


def test_ticks_during_expected_closure_are_flagged(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    rows = [line(utc(2019, 3, 9, 12, 0), "1.12010", "1.12000")]  # Saturday
    ingest(store, write_csv(tmp_path / "sat.csv", rows), utc(2019, 3, 9), utc(2019, 3, 10))
    bars, summary = build_bars(store, "dukascopy", "EURUSD")
    assert summary.during_weekly_closure == 1
    assert "ticks pendant la fermeture prévue" in bars[Timeframe.H1][0]["flags"]
    assert not bars[Timeframe.H1][0]["complete"]


# ---------------------------------------------------------------- import: immutability, idempotence, resume


def test_reimport_is_idempotent_without_duplicates(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    path = write_csv(tmp_path / "hand.csv", HAND_ROWS)
    first = ingest(store, path, utc(2019, 3, 7, 10), utc(2019, 3, 7, 11))
    assert (first.raw_status, first.normalized_status, first.rows) == ("copied", "written", 7)
    copy = tmp_path / "renamed-export.csv"
    copy.write_bytes(path.read_bytes())  # same content under another name
    second = ingest(store, copy, utc(2019, 3, 7, 10), utc(2019, 3, 7, 11))
    assert (second.raw_status, second.normalized_status) == ("already_present", "already_present")
    assert second.sha256 == first.sha256
    assert len(store.tick_files("dukascopy", "EURUSD")) == 1
    assert summarize_ticks(store, "dukascopy", "EURUSD").total == 7


def test_raw_copy_is_immutable_and_manifest_complete(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    result = ingest(store, write_csv(tmp_path / "hand.csv", HAND_ROWS), utc(2019, 3, 7, 10), utc(2019, 3, 7, 11))
    raw = store.raw_dir("dukascopy", "EURUSD") / f"{result.sha256}.csv"
    assert not raw.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    (manifest,) = store.manifests("dukascopy", "EURUSD")
    assert manifest["sha256"] == result.sha256
    assert manifest["period_start_utc"] == "2019-03-07T10:00:00+00:00"
    assert manifest["retrieved_at_utc"] == RETRIEVED.isoformat()
    assert manifest["partitions"] == ["DEVELOPMENT"]
    assert manifest["original_filename"] == "hand.csv"


def test_overlapping_different_file_is_refused(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    ingest(store, write_csv(tmp_path / "a.csv", HAND_ROWS), utc(2019, 3, 7, 10), utc(2019, 3, 7, 11))
    other = write_csv(tmp_path / "b.csv", HAND_ROWS[:3])
    with pytest.raises(IngestError, match="chevauchant"):
        ingest(store, other, utc(2019, 3, 7, 10, 30), utc(2019, 3, 7, 12))
    ingest(store, other, utc(2019, 3, 7, 11), utc(2019, 3, 7, 12))  # adjacent period: accepted


def test_resume_after_interrupted_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = HistoryStore(tmp_path / "data")
    path = write_csv(tmp_path / "hand.csv", HAND_ROWS)
    original = HistoryStore._normalize

    def crash(*args: object, **kwargs: object) -> tuple[int, int]:
        ticks_dir = store.ticks_dir("dukascopy", "EURUSD")
        (ticks_dir / f"partial.parquet.tmp-{os.getpid()}").write_bytes(b"half-written")
        raise KeyboardInterrupt

    monkeypatch.setattr(HistoryStore, "_normalize", crash)
    with pytest.raises(KeyboardInterrupt):
        ingest(store, path, utc(2019, 3, 7, 10), utc(2019, 3, 7, 11))
    assert store.tick_files("dukascopy", "EURUSD") == []  # no partial output published
    monkeypatch.setattr(HistoryStore, "_normalize", original)
    result = ingest(store, path, utc(2019, 3, 7, 10), utc(2019, 3, 7, 11))
    assert (result.raw_status, result.normalized_status) == ("already_present", "written")
    assert not list(store.ticks_dir("dukascopy", "EURUSD").glob("*.tmp-*"))
    assert summarize_ticks(store, "dukascopy", "EURUSD").total == 7


def test_rows_outside_declared_period_are_excluded_and_counted(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    result = ingest(store, write_csv(tmp_path / "hand.csv", HAND_ROWS), utc(2019, 3, 7, 10), utc(2019, 3, 7, 10, 30))
    assert (result.rows, result.rows_outside_period) == (4, 3)


def test_final_test_partition_is_refused(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    path = write_csv(tmp_path / "x.csv", [line(utc(2024, 3, 7, 10), "1.1", "1.0")])
    with pytest.raises(IngestError, match="test final"):
        ingest(store, path, utc(2024, 3, 7), utc(2024, 3, 8))
    assert not (tmp_path / "data" / "raw").exists()


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("Time,Ask,Bid,AskVolume,BidVolume\n", "en-tête"),
        (HEADER + "07.03.2019 10:00:00.000,1.120101,1.12000,1,1\n", "plus de 5 décimales"),
        (HEADER + "2019-03-07 10:00:00,1.12010,1.12000,1,1\n", "horodatage illisible"),
        (HEADER + "07.03.2019 10:00:00.000,1.12010,1.12000\n", "colonnes"),
    ],
)
def test_format_mismatch_is_rejected_with_line(tmp_path: Path, content: str, message: str) -> None:
    store = HistoryStore(tmp_path / "data")
    path = tmp_path / "bad.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(FormatError, match=message):
        ingest(store, path, utc(2019, 3, 7), utc(2019, 3, 8))
    assert store.tick_files("dukascopy", "EURUSD") == []


# ---------------------------------------------------------------- JForex request windows (future adapter)


@pytest.mark.parametrize("from_inclusive", [True, False])
def test_jforex_windows_neither_duplicate_nor_drop_boundary_ticks(from_inclusive: bool) -> None:
    from forex_bot.history.jforex import tick_windows

    hour = 3_600_000
    # ticks (ms): two distinct ticks at the hour boundary, one at the last ms of the first hour
    ticks = [0, hour - 1, hour, hour, hour + 5, 2 * hour - 1, 2 * hour]

    def server(frm: int, to: int) -> list[int]:  # simulated IHistory.getTicks: `to` inclusive
        return [t for t in ticks if (t >= frm if from_inclusive else t > frm) and t <= to]

    kept = [t for w in tick_windows(0, 2 * hour) for t in server(w.request_from_ms, w.request_to_ms) if w.keep(t)]
    assert kept == [0, hour - 1, hour, hour, hour + 5, 2 * hour - 1]  # both simultaneous ticks kept once
    windows = tick_windows(0, 2 * hour)
    assert [(w.start_ms, w.end_ms) for w in windows] == [(0, hour), (hour, 2 * hour)]


# ---------------------------------------------------------------- JForex SDK adapter output


JFOREX_HEADER = "time_ms,ask,bid,ask_volume,bid_volume\n"
JAVA_SOURCE = Path(__file__).resolve().parents[1] / "tools/jforex-ticks/src/main/java/forexbot/jforex/TickExport.java"


def test_jforex_sdk_csv_epoch_milliseconds_are_utc(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    start = utc(2019, 3, 7)
    ms = int(utc(2019, 3, 7, 12, 30, 15, 250_000).timestamp() * 1000)
    path = tmp_path / "2019-03-07.csv"
    path.write_text(JFOREX_HEADER + f"{ms},1.13067,1.13064,1.12,5.06\n{ms},1.13068,1.13064,0.75,1.0\n")
    request = IngestRequest(
        path, "dukascopy", "EURUSD", "jforex-sdk-ticks-csv-v1", start, start + timedelta(days=1), RETRIEVED
    )
    assert store.ingest(request).rows == 2
    bars, summary = build_bars(store, "dukascopy", "EURUSD")
    assert summary.simultaneous_groups == 1
    h1 = [b for b in bars[Timeframe.H1] if b["start_utc"] == utc(2019, 3, 7, 12)]
    assert h1 and h1[0]["bid_open"] == D("1.13064") and h1[0]["ask_close"] == D("1.13068")


@pytest.mark.parametrize("value", ["-5", "1.5e12", "", "2019-03-07"])
def test_jforex_sdk_csv_rejects_non_integer_time(tmp_path: Path, value: str) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(JFOREX_HEADER + f"{value},1.13067,1.13064,1.12,5.06\n")
    start = utc(2019, 3, 7)
    request = IngestRequest(
        path, "dukascopy", "EURUSD", "jforex-sdk-ticks-csv-v1", start, start + timedelta(days=1), RETRIEVED
    )
    with pytest.raises(FormatError, match="ligne 2"):
        HistoryStore(tmp_path / "data").ingest(request)


def test_java_adapter_is_read_only_and_demo_only() -> None:
    """Static guard on the Java adapter source: no trading engine, no live server, no PIN."""
    source = JAVA_SOURCE.read_text(encoding="utf-8")
    for forbidden in ("getEngine", "IEngine", "IOrder", "submitOrder", "closeOrders", "/live/", "getCaptchaImage"):
        assert forbidden not in source, forbidden
    assert 'DEMO_JNLP = "https://platform.dukascopy.com/demo/jforex.jnlp"' in source
    assert source.count("client.connect(") == 1 and "client.connect(DEMO_JNLP, username, password)" in source
    assert "ALLOWED_TO = LocalDate.of(2024, 1, 1)" in source


def test_java_adapter_accepts_only_the_operator_listed_empty_hours() -> None:
    """Empty open hours are accepted only from the closed list decided by the operator (2026-10-30)."""
    source = JAVA_SOURCE.read_text(encoding="utf-8")
    declaration = re.search(r"ACCEPTED_EMPTY_HOURS = Set\.of\(([^)]*)\);", source)
    assert declaration is not None
    assert re.findall(r'"([^"]+)"', declaration.group(1)) == ["2016-09-02T18", "2019-05-26T21", "2019-05-26T22"]
    assert source.count("ACCEPTED_EMPTY_HOURS") == 2  # declaration and a single lookup
    assert '"  \\"accepted_empty_hours_utc\\": "' in source


# ---------------------------------------------------------------- purge


def test_purge_lists_then_deletes_only_dukascopy_files(tmp_path: Path) -> None:
    from forex_bot.history.purge import purge, purge_targets

    store = HistoryStore(tmp_path / "data")
    start = utc(2019, 3, 7, 10)
    ingest(store, write_csv(tmp_path / "a.csv", [line(start, "1.12010", "1.12000")]), start, start + timedelta(hours=1))
    raw = next(store.raw_dir("dukascopy", "EURUSD").glob("*.csv"))
    assert not os.access(raw, os.W_OK)  # immutable copy must still be deletable by the purge
    (tmp_path / "data/dukascopy-sdk/ticks").mkdir(parents=True)
    (tmp_path / "data/reports").mkdir()
    (tmp_path / "data/reports/quality_dukascopy_EURUSD.md").write_text("x")
    (tmp_path / "data/reports/quality_other_EURUSD.md").write_text("keep")
    other = tmp_path / "data/raw/other/EURUSD/file.csv"
    other.parent.mkdir(parents=True)
    other.write_text("keep")
    app = tmp_path / "JForex"
    (app / "Strategies").mkdir(parents=True)

    targets = purge_targets(tmp_path / "data", app)
    assert {t.path.name for t in targets} == {"dukascopy-sdk", "dukascopy", "quality_dukascopy_EURUSD.md", "JForex"}
    assert purge(targets, confirm=False) == []
    assert raw.exists() and app.exists()

    purge(targets, confirm=True)
    assert purge_targets(tmp_path / "data", app) == []
    assert other.exists() and (tmp_path / "data/reports/quality_other_EURUSD.md").exists()


def test_identical_files_without_ticks_cover_each_declared_period(tmp_path: Path) -> None:
    """Two Saturdays: same header-only content, different periods; both are covered."""
    store = HistoryStore(tmp_path / "data")
    sat1, sat2 = utc(2019, 3, 9), utc(2019, 3, 16)
    a = write_csv(tmp_path / "2019-03-09.csv", [])
    b = write_csv(tmp_path / "2019-03-16.csv", [])
    assert ingest(store, a, sat1, sat1 + timedelta(days=1)).rows == 0
    assert ingest(store, b, sat2, sat2 + timedelta(days=1)).rows == 0
    assert ingest(store, b, sat2, sat2 + timedelta(days=1)).normalized_status == "already_present"
    periods = {(m["period_start_utc"], m["period_end_utc"]) for m in store.manifests("dukascopy", "EURUSD")}
    assert len(periods) == 2
    with pytest.raises(IngestError, match="chevauchant"):
        ingest(store, a, sat2 + timedelta(hours=12), sat2 + timedelta(days=2))


def test_file_with_ticks_declared_for_another_period_is_refused(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "data")
    start = utc(2019, 3, 7, 10)
    path = write_csv(tmp_path / "a.csv", [line(start, "1.12010", "1.12000")])
    ingest(store, path, start, start + timedelta(hours=1))
    with pytest.raises(IngestError, match="autres métadonnées"):
        ingest(store, path, utc(2019, 3, 20), utc(2019, 3, 21))
