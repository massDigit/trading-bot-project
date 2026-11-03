"""Bounded, read-only access to the local history for the offline backtest.

Every reader takes an explicit window [start, end) and never reads a tick outside it; the window
must lie in the development partition (2015-2021, ADR-007). Nothing is downloaded.

Two tick readers with the same contract (valid ticks only, ordered by UTC time then raw-file line):
- `stream_ticks`: one normalized file at a time (a file covers one UTC day), constant memory;
- `load_ticks`: the whole window at once through DuckDB, the in-memory reference used to check
  that both readers feed the engine identically.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq

from forex_bot.backtest.feed import Tick
from forex_bot.history.bars import Gap
from forex_bot.history.calendar import Partition, Timeframe, partitions_touched, require_utc

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _us(moment: datetime) -> int:
    return (moment - EPOCH) // timedelta(microseconds=1)


def require_development_window(start: datetime, end: datetime) -> None:
    """Refuses any window outside 2015-2021: validation and final-test data stay unread."""
    if partitions_touched(start, end) != {Partition.DEVELOPMENT}:
        raise ValueError("fenêtre hors de la partition de développement 2015-2021 (ADR-007)")


@dataclass(frozen=True)
class TickFile:
    path: Path
    period_start: datetime
    period_end: datetime  # exclusive


def tick_files(paths: Iterable[Path], start: datetime, end: datetime) -> list[TickFile]:
    """Normalized files whose declared period overlaps [start, end), sorted, checked disjoint."""
    require_development_window(start, end)
    selected = []
    for path in paths:
        meta = pq.read_schema(path).metadata or {}
        period_start = datetime.fromisoformat(meta[b"period_start_utc"].decode())
        period_end = datetime.fromisoformat(meta[b"period_end_utc"].decode())
        if period_start < end and start < period_end:
            selected.append(TickFile(path, period_start, period_end))
    selected.sort(key=lambda f: f.period_start)
    for before, after in itertools.pairwise(selected):
        if after.period_start < before.period_end:
            raise ValueError(f"périodes de fichiers chevauchantes : {before.path.name}, {after.path.name}")
    return selected


def _valid(bid: Any, ask: Any) -> bool:
    return bool(bid > 0 and ask > 0 and bid <= ask)  # same rule as the candles (history.bars)


def stream_ticks(files: Iterable[TickFile], start: datetime, end: datetime) -> Iterator[Tick]:
    """Valid ticks of [start, end), one file in memory at a time."""
    start, end = require_utc(start), require_utc(end)
    require_development_window(start, end)
    for file in files:
        table = pq.read_table(
            file.path,
            columns=["ts_utc", "raw_row", "bid", "ask"],
            filters=[("ts_utc", ">=", start), ("ts_utc", "<", end)],
        ).sort_by([("ts_utc", "ascending"), ("raw_row", "ascending")])
        for batch in table.to_batches(max_chunksize=65_536):
            columns = (batch.column(name).to_pylist() for name in ("ts_utc", "bid", "ask"))
            for ts, bid, ask in zip(*columns, strict=True):
                if _valid(bid, ask):
                    yield Tick(ts, bid, ask)


def load_ticks(files: Iterable[TickFile], start: datetime, end: datetime) -> list[Tick]:
    """In-memory reference: the same ticks as `stream_ticks`, read in one DuckDB query."""
    start, end = require_utc(start), require_utc(end)
    require_development_window(start, end)
    paths = [f.path.as_posix() for f in files]
    if not paths:
        return []
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    rows = con.execute(
        """SELECT epoch_us(ts_utc) AS us, bid, ask FROM read_parquet($1)
           WHERE epoch_us(ts_utc) >= $2 AND epoch_us(ts_utc) < $3 AND bid > 0 AND ask > 0 AND bid <= ask
           ORDER BY us, raw_row""",
        [paths, _us(start), _us(end)],
    ).fetchall()
    con.close()
    return [Tick(EPOCH + timedelta(microseconds=us), bid, ask) for us, bid, ask in rows]


def load_bars(
    data_dir: Path, source: str, instrument: str, timeframe: Timeframe, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    """Candles with start_utc >= start and end_utc <= end (initialisation period included by the caller)."""
    require_development_window(start, end)
    path = data_dir / "bars" / source / instrument / f"{timeframe.value}.parquet"
    table = pq.read_table(path, filters=[("start_utc", ">=", start), ("end_utc", "<=", end)])
    return sorted(table.to_pylist(), key=lambda bar: bar["start_utc"])


def load_gaps(report: Path, end: datetime) -> list[Gap]:
    """Gaps of the quality report that start before `end`; the engine only uses what is known at D."""
    gaps = json.loads(report.read_text())["gaps"]
    selected = [
        Gap(datetime.fromisoformat(g["start_utc"]), datetime.fromisoformat(g["end_utc"]), float(g["open_minutes"]))
        for g in gaps
    ]
    return [g for g in selected if g.start_utc < end]
