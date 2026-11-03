"""Bounded history readers: the streaming reader feeds the engine exactly like the in-memory reference.

Synthetic normalized files (one per UTC day, the layout of the real store) with simultaneous ticks
stored out of order, a tick exactly at the boundary of two files, invalid ticks and ticks outside
the window.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_backtest import (
    BREAKOUT,
    COSTS,
    FINE,
    FLAT,
    HOLD,
    REVERSE,
    WIDE,
    candles,
    ticks_for,
)

from forex_bot.backtest.data import load_ticks, require_development_window, stream_ticks, tick_files
from forex_bot.backtest.engine import BacktestResult, ResearchConfig, S1Backtest
from forex_bot.backtest.feed import Tick, TickFeed
from forex_bot.history.calendar import Timeframe
from forex_bot.history.store import TICK_SCHEMA

DAY = timedelta(days=1)


def _day(moment: datetime) -> datetime:
    return datetime(moment.year, moment.month, moment.day, tzinfo=UTC)


def write_store(directory: Path, rows: list[tuple[datetime, int, D, D]]) -> list[Path]:
    """One file per UTC day; rows keep the given (possibly unsorted) order, raw_row is explicit."""
    by_day: dict[datetime, list[tuple[datetime, int, D, D]]] = defaultdict(list)
    for row in rows:
        by_day[_day(row[0])].append(row)
    paths = []
    for day, day_rows in sorted(by_day.items()):
        columns: dict[str, list[Any]] = {
            "source": ["test"] * len(day_rows),
            "instrument": ["EURUSD"] * len(day_rows),
            "ts_utc": [r[0] for r in day_rows],
            "raw_sha256": [f"sha-{day:%Y%m%d}"] * len(day_rows),
            "raw_row": [r[1] for r in day_rows],
            "bid": [r[2] for r in day_rows],
            "ask": [r[3] for r in day_rows],
            "bid_volume": [1.0] * len(day_rows),
            "ask_volume": [1.0] * len(day_rows),
        }
        meta = {"period_start_utc": day.isoformat(), "period_end_utc": (day + DAY).isoformat()}
        path = directory / f"{day:%Y%m%d}.parquet"
        pq.write_table(pa.table(columns, schema=TICK_SCHEMA).replace_schema_metadata(meta), path)
        paths.append(path)
    return paths


def _rows(ticks: list[Tick]) -> list[tuple[datetime, int, D, D]]:
    """Ticks as stored rows, plus simultaneous ticks written in reverse order and invalid ticks."""
    rows: list[tuple[datetime, int, D, D]] = []
    line: dict[datetime, int] = defaultdict(int)
    for tick in ticks:
        day = _day(tick.ts_utc)
        line[day] += 10
        rows.append((tick.ts_utc, line[day], tick.bid, tick.ask))
        if tick.ts_utc.minute == 10:  # a simultaneous tick, stored BEFORE the first one (earlier line wins)
            rows.insert(len(rows) - 1, (tick.ts_utc, line[day] + 1, tick.bid + D("0.00002"), tick.ask + D("0.00002")))
        if tick.ts_utc.minute == 20:  # invalid ticks, excluded like in the candles
            rows.append((tick.ts_utc, line[day] + 2, tick.ask + D("0.0001"), tick.ask))
            rows.append((tick.ts_utc, line[day] + 3, D("0"), tick.ask))
    return rows


def test_both_readers_give_the_same_ticks_including_ties_and_file_boundaries(tmp_path: Path) -> None:
    ticks = ticks_for([FLAT] * 12)
    paths = write_store(tmp_path, _rows(ticks))
    start, end = datetime(2019, 3, 11, 0, 0, tzinfo=UTC), datetime(2019, 3, 12, 0, 5, tzinfo=UTC)
    files = tick_files(paths, start, end)
    assert len(files) == 2  # the window crosses a file boundary
    streamed = list(stream_ticks(files, start, end))
    assert streamed == load_ticks(files, start, end)
    assert streamed[0].ts_utc == start and streamed[-1].ts_utc == datetime(2019, 3, 12, 0, 0, tzinfo=UTC)
    times = [t.ts_utc for t in streamed]
    assert times == sorted(times) and len(times) > len(set(times))  # simultaneous ticks kept
    moment = datetime(2019, 3, 11, 1, 10, tzinfo=UTC)
    (original,) = [t for t in ticks if t.ts_utc == moment]
    tie = [t.bid for t in streamed if t.ts_utc == moment]
    assert tie == [original.bid, original.bid + D("0.00002")]  # raw-file line order, not storage order
    assert all(t.bid > 0 and t.bid <= t.ask for t in streamed)


def _engine(ticks: Any, bars_from: list[Tick], start: datetime, end: datetime) -> BacktestResult:
    h4 = [b for b in candles(bars_from, Timeframe.H4) if b["end_utc"] <= end]
    d1 = [b for b in candles(bars_from, Timeframe.D1) if b["end_utc"] <= end]
    return S1Backtest(
        h4, d1, ticks, TickFeed(bars_from).gaps(timedelta(minutes=10)), WIDE,
        ResearchConfig(costs=COSTS, min_size=FINE["min_size"], size_increment=FINE["size_increment"]),
        start_utc=start, end_utc=end,
    ).run()  # fmt: skip


def test_engine_results_are_identical_with_the_streaming_and_in_memory_readers(tmp_path: Path) -> None:
    after = (D("1.0990"), D("1.0988"), D("1.0985"), D("1.0988"))
    ticks = ticks_for([FLAT] * 25 + [BREAKOUT] + [HOLD] * 10 + [REVERSE, after, after])
    files_all = write_store(tmp_path, _rows(ticks))
    start, end = datetime(2019, 3, 10, 21, tzinfo=UTC), datetime(2019, 3, 19, 13, tzinfo=UTC)
    files = tick_files(files_all, start, end)
    in_memory = _engine(TickFeed(load_ticks(files, start, end)), ticks, start, end)
    streamed = _engine(stream_ticks(files, start, end), ticks, start, end)
    assert len(in_memory.trades) == 1 and in_memory.open_trade is not None  # a reversal across days
    assert streamed.trades == in_memory.trades
    assert streamed.open_trade == in_memory.open_trade
    assert streamed.journal == in_memory.journal
    assert streamed.equity_curve == in_memory.equity_curve
    assert streamed.end_utc == in_memory.end_utc == end


def test_window_bounds_the_engine_and_the_initialisation_period_never_trades(tmp_path: Path) -> None:
    ticks = ticks_for([FLAT] * 25 + [BREAKOUT, HOLD, HOLD])
    files_all = write_store(tmp_path, _rows(ticks))
    breakout_close = candles(ticks, Timeframe.H4)[25]["end_utc"]
    # Study starting after the breakout decision: candles before only initialise the indicators.
    start, end = breakout_close + timedelta(minutes=1), datetime(2019, 3, 15, 13, tzinfo=UTC)
    files = tick_files(files_all, start, end)
    result = _engine(stream_ticks(files, start, end), ticks, start, end)
    assert not result.trades and result.open_trade is None
    assert all(e.utc >= start for e in result.journal) and result.equity_curve[0].utc >= start
    assert result.end_utc == end and result.equity_curve[-1].utc == end


def test_windows_outside_the_development_partition_are_refused(tmp_path: Path) -> None:
    for start, end in (
        (datetime(2021, 12, 1, tzinfo=UTC), datetime(2022, 1, 2, tzinfo=UTC)),
        (datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 2, 1, tzinfo=UTC)),
        (datetime(2014, 12, 1, tzinfo=UTC), datetime(2015, 1, 2, tzinfo=UTC)),
    ):
        with pytest.raises(ValueError, match="partition de développement"):
            require_development_window(start, end)
        with pytest.raises(ValueError, match="partition de développement"):
            list(stream_ticks([], start, end))


def test_out_of_order_ticks_stop_the_engine() -> None:
    ticks = ticks_for([FLAT] * 3)
    swapped = [ticks[1], ticks[0], *ticks[2:]]
    with pytest.raises(ValueError, match="hors ordre"):
        _engine(iter(swapped), ticks, ticks[0].ts_utc, ticks[-1].ts_utc)
