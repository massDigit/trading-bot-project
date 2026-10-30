"""Bid/ask OHLC candles (H1, H4, D1) from normalized ticks. No filling of missing periods.

- Bid and ask candles are built separately from the same valid ticks; no spread is invented.
- Ticks with a non-positive price or bid > ask are excluded from the candles and counted.
- Order inside a candle: UTC timestamp, then line number in the raw file (simultaneous ticks
  are all kept, in their original order).
- H1 comes from ticks; H4 and D1 come from H1 (their boundaries are whole UTC hours, so the
  result is identical to an aggregation of ticks).
- A candle is `complete` only if it lies inside the declared coverage, its hours are all
  present and complete, and no tick gap longer than `gap_threshold` overlaps it while the
  market is expected open. Incomplete candles are kept and flagged, never filled; a candle
  that ends after the end of coverage is "not closed" and must not be used.
"""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from forex_bot.history.calendar import (
    ONE_HOUR,
    MarketState,
    Timeframe,
    candle_end,
    candle_start,
    expected_open_hours,
    market_state,
    trading_day,
    trading_day_start_utc,
)
from forex_bot.history.store import PRICE_TYPE, HistoryStore

# Proposal (ASSUMP-017): an interval without valid tick longer than this, while the market is
# expected open, makes the overlapping candles incomplete.
DEFAULT_GAP_THRESHOLD = timedelta(minutes=10)

PRICES = ("bid_open", "bid_high", "bid_low", "bid_close", "ask_open", "ask_high", "ask_low", "ask_close")

BAR_SCHEMA = pa.schema(
    [
        pa.field("source", pa.string(), nullable=False),
        pa.field("instrument", pa.string(), nullable=False),
        pa.field("timeframe", pa.string(), nullable=False),
        pa.field("start_utc", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("end_utc", pa.timestamp("us", tz="UTC"), nullable=False),
        *[pa.field(name, PRICE_TYPE, nullable=False) for name in PRICES],
        pa.field("tick_count", pa.int64(), nullable=False),  # volume type: number of valid ticks
        pa.field("excluded_ticks", pa.int64(), nullable=False),
        pa.field("first_tick_utc", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("last_tick_utc", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("expected_hours", pa.int64(), nullable=False),
        pa.field("present_hours", pa.int64(), nullable=False),
        # Retrospective audit status: may use ticks AFTER end_utc (e.g. a gap that starts inside the
        # candle and is only known to exceed the threshold later). Never a decision input.
        pa.field("complete", pa.bool_(), nullable=False),
        pa.field("flags", pa.list_(pa.string()), nullable=False),
        # Status knowable at end_utc: built only from ticks strictly before end_utc. Decision input.
        pa.field("complete_at_close", pa.bool_(), nullable=False),
        pa.field("flags_at_close", pa.list_(pa.string()), nullable=False),
    ]
)


@dataclass(frozen=True)
class Gap:
    start_utc: datetime  # last valid tick before the gap (or coverage start)
    end_utc: datetime  # first valid tick after the gap (or coverage end)
    open_minutes: float  # part of the gap during which the market was expected open


@dataclass
class TickSummary:
    total: int = 0
    valid: int = 0
    non_positive: int = 0
    crossed: int = 0
    out_of_order_in_file: int = 0
    simultaneous_groups: int = 0  # timestamps carried by more than one tick
    simultaneous_ticks: int = 0
    exact_repeats: int = 0  # consecutive rows identical in time, prices and volumes (kept)
    during_weekly_closure: int = 0
    first_tick_utc: datetime | None = None
    last_tick_utc: datetime | None = None
    coverage: list[tuple[datetime, datetime]] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    # expected weekly close (UTC) -> (last valid tick before it, first valid tick at or after it)
    closure_neighbours: dict[datetime, tuple[datetime | None, datetime | None]] = field(default_factory=dict)


def _one(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> tuple[Any, ...]:
    row = con.execute(sql, params).fetchone()
    if row is None:
        raise RuntimeError("requête d'agrégat sans résultat")
    return row


def _connect(store: HistoryStore, source: str, instrument: str) -> duckdb.DuckDBPyConnection:
    files = store.tick_files(source, instrument)
    if not files:
        raise FileNotFoundError("aucun fichier de ticks normalisé")
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    # Years of ticks do not fit in memory: bounded memory, spill to the data directory.
    con.execute(f"SET memory_limit = '{DUCKDB_MEMORY_LIMIT}'")
    spill = store.data_dir / "tmp" / "duckdb"
    spill.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory = '{spill.as_posix()}'")
    con.read_parquet([p.as_posix() for p in files]).create_view("raw_ticks")
    con.execute(
        """CREATE VIEW ticks AS
        SELECT ts_utc, epoch_us(ts_utc) AS ts_us, raw_sha256, raw_row, bid, ask, bid_volume, ask_volume,
               (bid > 0 AND ask > 0 AND bid <= ask) AS valid
        FROM raw_ticks"""
    )
    return con


DUCKDB_MEMORY_LIMIT = "6GB"


def expected_weekly_closes(coverage: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """(close, reopen) in UTC of every weekly closure lying inside one coverage interval."""
    result = []
    for c_start, c_end in coverage:
        day, last_day = trading_day(c_start), trading_day(c_end)
        while day <= last_day:
            if day.weekday() == 4:  # Friday trading day closes at 17:00 New York
                close = trading_day_start_utc(day + timedelta(days=1))
                reopen = trading_day_start_utc(day + timedelta(days=3))
                if c_start < close and reopen < c_end:
                    result.append((close, reopen))
            day += timedelta(days=1)
    return result


def _us(moment: datetime) -> int:
    return round((moment - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds() * 1_000_000)


def _utc(epoch_us: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=epoch_us)


def coverage_of(store: HistoryStore, source: str, instrument: str) -> list[tuple[datetime, datetime]]:
    """Union of the declared periods of the imported files."""
    periods = sorted(
        (datetime.fromisoformat(m["period_start_utc"]), datetime.fromisoformat(m["period_end_utc"]))
        for m in store.manifests(source, instrument)
    )
    merged: list[tuple[datetime, datetime]] = []
    for start, end in periods:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _covered(start: datetime, end: datetime, coverage: list[tuple[datetime, datetime]]) -> bool:
    return any(c_start <= start and end <= c_end for c_start, c_end in coverage)


def _open_minutes(start: datetime, end: datetime) -> float:
    """Minutes of [start, end) during which the market is expected open (minute resolution)."""
    minutes = 0.0
    cursor = start
    while cursor < end:
        step = min(end, cursor.replace(second=0, microsecond=0) + timedelta(minutes=1))
        if market_state(cursor) is MarketState.OPEN:
            minutes += (step - cursor).total_seconds() / 60
        cursor = step
    return minutes


def summarize_ticks(
    store: HistoryStore, source: str, instrument: str, gap_threshold: timedelta = DEFAULT_GAP_THRESHOLD
) -> TickSummary:
    con = _connect(store, source, instrument)
    summary = TickSummary(coverage=coverage_of(store, source, instrument))
    row = _one(
        con,
        """SELECT count(*), count(*) FILTER (WHERE valid),
                  count(*) FILTER (WHERE bid <= 0 OR ask <= 0),
                  count(*) FILTER (WHERE bid > 0 AND ask > 0 AND bid > ask),
                  min(ts_us), max(ts_us)
           FROM ticks""",
    )
    summary.total, summary.valid, summary.non_positive, summary.crossed = (int(v or 0) for v in row[:4])
    if row[4] is not None:
        summary.first_tick_utc, summary.last_tick_utc = _utc(row[4]), _utc(row[5])
    ordered = _one(
        con,
        """SELECT count(*) FILTER (WHERE prev_ts IS NOT NULL AND ts_us < prev_ts),
                  count(*) FILTER (WHERE ts_us = prev_ts AND bid = prev_bid AND ask = prev_ask
                                   AND bid_volume IS NOT DISTINCT FROM prev_bv
                                   AND ask_volume IS NOT DISTINCT FROM prev_av)
           FROM (SELECT ts_us, bid, ask, bid_volume, ask_volume,
                        lag(ts_us) OVER w AS prev_ts, lag(bid) OVER w AS prev_bid, lag(ask) OVER w AS prev_ask,
                        lag(bid_volume) OVER w AS prev_bv, lag(ask_volume) OVER w AS prev_av
                 FROM ticks WINDOW w AS (PARTITION BY raw_sha256 ORDER BY raw_row))""",
    )
    summary.out_of_order_in_file, summary.exact_repeats = int(ordered[0] or 0), int(ordered[1] or 0)
    simultaneous = _one(
        con, "SELECT count(*), coalesce(sum(n), 0) FROM (SELECT count(*) AS n FROM ticks GROUP BY ts_us HAVING n > 1)"
    )
    summary.simultaneous_groups, summary.simultaneous_ticks = int(simultaneous[0]), int(simultaneous[1])

    # Weekly closure boundaries fall on whole UTC hours (17:00 New York): the state of a tick is the
    # state of its hour, so ticks are counted per hour instead of being loaded one by one.
    hourly = con.execute("SELECT ts_us // 3600000000, count(*) FROM ticks WHERE valid GROUP BY 1").fetchall()
    summary.during_weekly_closure = sum(
        int(n) for hour, n in hourly if market_state(_utc(int(hour) * 3_600_000_000)) is MarketState.WEEKLY_CLOSURE
    )

    threshold_us = int(gap_threshold.total_seconds() * 1_000_000)
    for c_start, c_end in summary.coverage:
        lo, hi = _us(c_start), _us(c_end)
        bounds = _one(
            con, "SELECT min(ts_us), max(ts_us) FROM ticks WHERE valid AND ts_us >= $1 AND ts_us < $2", [lo, hi]
        )
        if bounds[0] is None:
            pairs = [(c_start, c_end)]
        else:
            inner = con.execute(
                """SELECT prev, ts_us FROM (
                        SELECT ts_us, lag(ts_us) OVER (ORDER BY ts_us) AS prev
                        FROM ticks WHERE valid AND ts_us >= $1 AND ts_us < $2)
                    WHERE ts_us - prev > $3 ORDER BY ts_us""",
                [lo, hi, threshold_us],
            ).fetchall()
            pairs = [
                (c_start, _utc(int(bounds[0]))),
                *((_utc(a), _utc(b)) for a, b in inner),
                (_utc(int(bounds[1])), c_end),
            ]
        for before, after in pairs:
            if after - before > gap_threshold:
                summary.gaps.append(Gap(before, after, _open_minutes(before, after)))

    closes = expected_weekly_closes(summary.coverage)
    if closes:
        con.execute("CREATE TEMP TABLE closes (close_us BIGINT)")
        con.executemany("INSERT INTO closes VALUES (?)", [(_us(close),) for close, _ in closes])
        con.execute("CREATE TEMP VIEW valid_ts AS SELECT ts_us FROM ticks WHERE valid")
        last_before = dict(
            con.execute(
                "SELECT c.close_us, v.ts_us FROM closes c ASOF LEFT JOIN valid_ts v ON c.close_us > v.ts_us"
            ).fetchall()
        )
        first_after = dict(
            con.execute(
                "SELECT c.close_us, v.ts_us FROM closes c ASOF LEFT JOIN valid_ts v ON c.close_us <= v.ts_us"
            ).fetchall()
        )
        for close, _ in closes:
            b, a = last_before.get(_us(close)), first_after.get(_us(close))
            summary.closure_neighbours[close] = (
                _utc(int(b)) if b is not None else None,
                _utc(int(a)) if a is not None else None,
            )
    con.close()
    return summary


def _h1_rows(store: HistoryStore, source: str, instrument: str) -> list[dict[str, Any]]:
    con = _connect(store, source, instrument)
    rows = con.execute(
        """SELECT ts_us // 3600000000 AS hour,
                  arg_min(bid, ts_us::HUGEINT * 1000000000 + raw_row) FILTER (WHERE valid),
                  max(bid) FILTER (WHERE valid), min(bid) FILTER (WHERE valid),
                  arg_max(bid, ts_us::HUGEINT * 1000000000 + raw_row) FILTER (WHERE valid),
                  arg_min(ask, ts_us::HUGEINT * 1000000000 + raw_row) FILTER (WHERE valid),
                  max(ask) FILTER (WHERE valid), min(ask) FILTER (WHERE valid),
                  arg_max(ask, ts_us::HUGEINT * 1000000000 + raw_row) FILTER (WHERE valid),
                  count(*) FILTER (WHERE valid), count(*) FILTER (WHERE NOT valid),
                  min(ts_us) FILTER (WHERE valid), max(ts_us) FILTER (WHERE valid)
           FROM ticks GROUP BY hour HAVING count(*) FILTER (WHERE valid) > 0 ORDER BY hour"""
    ).fetchall()
    con.close()
    result = []
    for r in rows:
        start = _utc(int(r[0]) * 3_600_000_000)
        result.append(
            {
                "start_utc": start,
                "end_utc": start + ONE_HOUR,
                **{name: Decimal(r[i + 1]) for i, name in enumerate(PRICES)},
                "tick_count": int(r[9]),
                "excluded_ticks": int(r[10]),
                "first_tick_utc": _utc(r[11]),
                "last_tick_utc": _utc(r[12]),
            }
        )
    return result


def overlaps_gap(
    start: datetime, end: datetime, gaps: list[Gap], threshold: timedelta, known_until: datetime | None = None
) -> bool:
    """True if a quote gap longer than `threshold` of expected-open time touches [start, end).

    With `known_until`, only what is knowable at that instant is used: a gap still open at
    `known_until` is cut there, so it counts only if its part before `known_until` already exceeds
    the threshold. Without it, the whole gap is used (retrospective audit, may look past `end`).
    """
    for gap in gaps:
        gap_end = gap.end_utc if known_until is None else min(gap.end_utc, known_until)
        lo, hi = max(start, gap.start_utc), min(end, gap_end)
        if lo < hi and _open_minutes(gap.start_utc, gap_end) * 60 > threshold.total_seconds():
            if _open_minutes(lo, hi) > 0:
                return True
    return False


# Flags that make a candle unusable; matched as substrings because some start with a count.
INCOMPLETE_MARKERS = (
    "hors couverture",
    "trou de cotation",
    "ticks pendant",
    "heures manquantes",
    "H1 incomplète",
    "jour férié",
    "tick(s) invalides exclus",
)


def _is_complete(flags: list[str]) -> bool:
    return not any(marker in flag for flag in flags for marker in INCOMPLETE_MARKERS)


def _finish(bar: dict[str, Any], summary: TickSummary, threshold: timedelta, expected: list[datetime]) -> None:
    """Sets the retrospective (`flags`, `complete`) and decision-time (`*_at_close`) statuses."""
    flags: list[str] = bar.setdefault("flags", [])
    at_close: list[str] = bar.setdefault("flags_at_close", [])
    start, end = bar["start_utc"], bar["end_utc"]
    common = []
    if not _covered(start, end, summary.coverage):
        common.append("hors couverture déclarée (bougie non clôturée ou partielle dans l'échantillon)")
    if market_state(start) is MarketState.PROBABLE_HOLIDAY:
        common.append("jour férié probable")
    elif not expected:
        common.append("ticks pendant la fermeture prévue")
    gap_flag = f"trou de cotation > {int(threshold.total_seconds() // 60)} min pendant l'ouverture prévue"
    invalid = [f"{bar['excluded_ticks']} tick(s) invalides exclus"] if bar["excluded_ticks"] else []
    flags.extend(common + ([gap_flag] if overlaps_gap(start, end, summary.gaps, threshold) else []) + invalid)
    known = overlaps_gap(start, end, summary.gaps, threshold, known_until=end)
    at_close.extend(common + ([gap_flag] if known else []) + invalid)
    bar["expected_hours"] = len(expected)
    bar.setdefault("present_hours", 1)
    bar["complete"] = _is_complete(flags)
    bar["complete_at_close"] = _is_complete(at_close)


def build_bars(
    store: HistoryStore, source: str, instrument: str, gap_threshold: timedelta = DEFAULT_GAP_THRESHOLD
) -> tuple[dict[Timeframe, list[dict[str, Any]]], TickSummary]:
    summary = summarize_ticks(store, source, instrument, gap_threshold)
    h1 = _h1_rows(store, source, instrument)
    for bar in h1:
        _finish(bar, summary, gap_threshold, expected_open_hours(bar["start_utc"], bar["end_utc"]))
    result: dict[Timeframe, list[dict[str, Any]]] = {Timeframe.H1: h1}
    for timeframe in (Timeframe.H4, Timeframe.D1):
        groups: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
        for bar in h1:
            groups[candle_start(bar["start_utc"], timeframe)].append(bar)
        bars = []
        for start in sorted(groups):
            members = groups[start]
            end = candle_end(start, timeframe)
            expected = expected_open_hours(start, end)
            present = {m["start_utc"] for m in members}
            candle: dict[str, Any] = {
                "start_utc": start,
                "end_utc": end,
                "bid_open": members[0]["bid_open"],
                "bid_high": max(m["bid_high"] for m in members),
                "bid_low": min(m["bid_low"] for m in members),
                "bid_close": members[-1]["bid_close"],
                "ask_open": members[0]["ask_open"],
                "ask_high": max(m["ask_high"] for m in members),
                "ask_low": min(m["ask_low"] for m in members),
                "ask_close": members[-1]["ask_close"],
                "tick_count": sum(m["tick_count"] for m in members),
                "excluded_ticks": sum(m["excluded_ticks"] for m in members),
                "first_tick_utc": members[0]["first_tick_utc"],
                "last_tick_utc": members[-1]["last_tick_utc"],
                "present_hours": len(present),
                "flags": [],
                "flags_at_close": [],
            }
            missing = [h for h in expected if h not in present]
            if missing:
                for key in ("flags", "flags_at_close"):
                    candle[key].append(f"heures manquantes : {len(missing)}/{len(expected)}")
            if any(not m["complete"] for m in members):
                candle["flags"].append("H1 incomplète dans la bougie")
            # Every member H1 closes no later than the candle: its decision-time status is known here.
            if any(not m["complete_at_close"] for m in members):
                candle["flags_at_close"].append("H1 incomplète dans la bougie")
            _finish(candle, summary, gap_threshold, expected)
            bars.append(candle)
        result[timeframe] = bars
    return result, summary


def bars_table(source: str, instrument: str, timeframe: Timeframe, bars: list[dict[str, Any]]) -> pa.Table:
    columns: dict[str, list[Any]] = {name: [] for name in BAR_SCHEMA.names}
    for bar in bars:
        for name in BAR_SCHEMA.names:
            if name == "source":
                columns[name].append(source)
            elif name == "instrument":
                columns[name].append(instrument)
            elif name == "timeframe":
                columns[name].append(timeframe.value)
            else:
                columns[name].append(bar[name])
    return pa.table(columns, schema=BAR_SCHEMA)


def write_bars(
    store: HistoryStore, source: str, instrument: str, bars: dict[Timeframe, list[dict[str, Any]]]
) -> list[Path]:
    directory = store.data_dir / "bars" / source / instrument
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for timeframe, rows in bars.items():
        target = directory / f"{timeframe.value}.parquet"
        tmp = target.with_name(f"{target.name}.tmp-{os.getpid()}")
        pq.write_table(bars_table(source, instrument, timeframe, rows), tmp)
        os.replace(tmp, target)
        written.append(target)
    return written
