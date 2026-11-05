"""M5 and M15 bid/ask candles built directly from ticks (protocol docs/experiments/DATA_M5_M15_2015_2021.md).

- Both grids are aggregated from the same ticks, never one from the other; the H1/H4/D1 code and
  files are left untouched.
- Tick conventions of `bars.py`, unchanged: invalid ticks (non-positive price, bid > ask) are
  excluded from prices and counted; simultaneous ticks are kept in `raw_row` order; nothing is
  deleted.
- Every expected-open slot gets a row, even without any tick (`EMPTY`, no price); a slot whose
  ticks are all invalid is `INVALID_ONLY` (no price). Nothing is filled, and an empty slot is never
  called a quiet market.
- Two statuses per candle, as for H1: `*_at_close` uses only ticks before the candle's own end
  (an M15 does not reuse its M5 statuses), the retrospective audit may look later.
- Only files whose declared period lies inside the requested window are opened: the store also
  holds 2022-2023 ticks, which this module must never read.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from forex_bot.history.bars import (
    DEFAULT_GAP_THRESHOLD,
    DUCKDB_MEMORY_LIMIT,
    INCOMPLETE_MARKERS,
    PRICES,
    Gap,
    overlaps_gap,
)
from forex_bot.history.calendar import MarketState, expected_open_hours, expected_open_minutes, market_state
from forex_bot.history.store import PRICE_TYPE, HistoryStore

# Development partition only (2015-2021); validation and final-test years are never opened here.
WINDOW_START = datetime(2015, 1, 1, tzinfo=UTC)
WINDOW_END = datetime(2022, 1, 1, tzinfo=UTC)

# Provisional convention for the audit only (ASSUMP-017 value, chosen for H1-D1). The M5/M15 rule
# is decided by the operator after the audit, before any DAY_01 engine.
PROVISIONAL_AUDIT_SILENCE = DEFAULT_GAP_THRESHOLD


@dataclass(frozen=True)
class QualityConvention:
    """Research convention for the status of M5/M15 candles; never changes prices or tick files."""

    name: str
    threshold: timedelta  # a silence is an interruption if strictly longer, in expected-open time
    empty_subslot_not_ok: bool  # an M15 with an expected M5 sub-slot without valid tick is not OK


# First audit (protocol §6), kept as the comparison reference.
REFERENCE_10MIN = QualityConvention("ref_10min", PROVISIONAL_AUDIT_SILENCE, empty_subslot_not_ok=False)
# Operator decision of 2026-11-05 for DAY_01 (protocol §9, ASSUMP-028).
DAY01_5MIN = QualityConvention("day01_5min", timedelta(minutes=5), empty_subslot_not_ok=True)
CONVENTIONS = {c.name: c for c in (REFERENCE_10MIN, DAY01_5MIN)}

US_PER_MINUTE = 60_000_000


class Grid(StrEnum):
    M5 = "5m"
    M15 = "15m"

    @property
    def minutes(self) -> int:
        return 5 if self is Grid.M5 else 15


class Content(StrEnum):
    VALID = "VALID"  # at least one valid tick
    INVALID_ONLY = "INVALID_ONLY"  # ticks, all invalid: no price
    EMPTY = "EMPTY"  # expected-open slot without any tick: no price


NO_TICK = "aucun tick dans le créneau"
NO_VALID_TICK = "aucun tick valide dans le créneau"
# "aucun tick" matches both content flags above.
INTRADAY_INCOMPLETE_MARKERS = (*INCOMPLETE_MARKERS, "aucun tick")
SUBSLOTS_FLAG = "sous-créneaux M5 sans tick valide"  # informative, M15 only, no effect on status

INTRADAY_SCHEMA = pa.schema(
    [
        pa.field("source", pa.string(), nullable=False),
        pa.field("instrument", pa.string(), nullable=False),
        pa.field("timeframe", pa.string(), nullable=False),
        pa.field("start_utc", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("end_utc", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("content", pa.string(), nullable=False),
        pa.field("expected_open", pa.bool_(), nullable=False),
        *[pa.field(name, PRICE_TYPE, nullable=True) for name in PRICES],  # null unless VALID
        pa.field("tick_count", pa.int64(), nullable=False),  # valid ticks
        pa.field("excluded_ticks", pa.int64(), nullable=False),
        pa.field("non_positive_ticks", pa.int64(), nullable=False),
        pa.field("crossed_ticks", pa.int64(), nullable=False),
        pa.field("first_tick_utc", pa.timestamp("us", tz="UTC"), nullable=True),
        pa.field("last_tick_utc", pa.timestamp("us", tz="UTC"), nullable=True),
        pa.field("valid_m5_subslots", pa.int64(), nullable=False),  # M5 sub-slots with a valid tick
        pa.field("complete", pa.bool_(), nullable=False),  # retrospective audit, never a decision input
        pa.field("flags", pa.list_(pa.string()), nullable=False),
        pa.field("complete_at_close", pa.bool_(), nullable=False),  # knowable at end_utc
        pa.field("flags_at_close", pa.list_(pa.string()), nullable=False),
    ]
)


@dataclass(frozen=True)
class SelectedFile:
    entry: str
    path: Path
    period_start_utc: datetime
    period_end_utc: datetime
    rows: int  # rows declared in the normalized file's metadata


@dataclass(frozen=True)
class Silence:
    """Interval between two consecutive valid ticks (distinct timestamps) longer than 60 s."""

    start_utc: datetime
    end_utc: datetime
    open_minutes: float


@dataclass
class IntradayBuild:
    window: tuple[datetime, datetime]
    convention: QualityConvention
    files: list[SelectedFile]
    coverage: list[tuple[datetime, datetime]]
    ticks: dict[str, int]
    gaps: list[Gap]
    silences: list[Silence]
    short_intervals: dict[str, int]  # counts of intervals between consecutive valid ticks <= 60 s
    out_of_order_ts: list[datetime]
    bars: dict[Grid, list[dict[str, Any]]] = field(default_factory=dict)

    @property
    def threshold(self) -> timedelta:
        return self.convention.threshold


def _utc(epoch_us: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=epoch_us)


def _us(moment: datetime) -> int:
    return round((moment - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds() * 1_000_000)


def check_window(start: datetime, end: datetime) -> None:
    if not WINDOW_START <= start < end <= WINDOW_END:
        raise ValueError("fenêtre hors de 2015-2021 : lecture refusée (2022-2025 réservés)")


def select_files(
    store: HistoryStore, source: str, instrument: str, start: datetime, end: datetime
) -> list[SelectedFile]:
    """Normalized tick files whose declared period lies inside [start, end), chosen from the manifests only."""
    check_window(start, end)
    selected = []
    for manifest in store.manifests(source, instrument):
        p_start = datetime.fromisoformat(manifest["period_start_utc"])
        p_end = datetime.fromisoformat(manifest["period_end_utc"])
        if p_end <= start or p_start >= end:
            continue
        if p_start < start or p_end > end:
            raise ValueError(f"fichier à cheval sur la fenêtre ({p_start.isoformat()} - {p_end.isoformat()})")
        entry = manifest.get("entry", manifest["sha256"])  # older manifests name the file by digest
        path = store.ticks_dir(source, instrument) / f"{entry}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"fichier normalisé absent pour {entry[:12]}")
        rows = int((pq.read_schema(path).metadata or {})[b"rows"])
        selected.append(SelectedFile(entry, path, p_start, p_end, rows))
    if not selected:
        raise FileNotFoundError("aucun fichier de ticks dans la fenêtre")
    return sorted(selected, key=lambda f: f.period_start_utc)


def _coverage(files: list[SelectedFile]) -> list[tuple[datetime, datetime]]:
    merged: list[tuple[datetime, datetime]] = []
    for f in files:
        if merged and f.period_start_utc <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], f.period_end_utc))
        else:
            merged.append((f.period_start_utc, f.period_end_utc))
    return merged


def _connect(
    store: HistoryStore, files: list[SelectedFile], start: datetime, end: datetime
) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    con.execute(f"SET memory_limit = '{DUCKDB_MEMORY_LIMIT}'")
    spill = store.data_dir / "tmp" / "duckdb"
    spill.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory = '{spill.as_posix()}'")
    con.read_parquet([f.path.as_posix() for f in files]).create_view("raw_ticks")
    # The window filter is redundant with the file selection; kept as a second guard.
    con.execute(
        f"""CREATE VIEW ticks AS
        SELECT ts_utc, epoch_us(ts_utc) AS ts_us, raw_sha256, raw_row, bid, ask, bid_volume, ask_volume,
               (bid > 0 AND ask > 0 AND bid <= ask) AS valid
        FROM raw_ticks WHERE epoch_us(ts_utc) >= {_us(start)} AND epoch_us(ts_utc) < {_us(end)}"""  # noqa: S608 (integers)
    )
    return con


def _one(con: duckdb.DuckDBPyConnection, sql: str) -> tuple[Any, ...]:
    row = con.execute(sql).fetchone()
    if row is None:
        raise RuntimeError("requête d'agrégat sans résultat")
    return row


def _tick_counts(con: duckdb.DuckDBPyConnection) -> tuple[dict[str, int], list[datetime]]:
    total = _one(
        con,
        """SELECT count(*), count(*) FILTER (WHERE valid), count(*) FILTER (WHERE bid <= 0 OR ask <= 0),
                  count(*) FILTER (WHERE bid > 0 AND ask > 0 AND bid > ask) FROM ticks""",
    )
    simultaneous = _one(
        con, "SELECT count(*), coalesce(sum(n), 0) FROM (SELECT count(*) AS n FROM ticks GROUP BY ts_us HAVING n > 1)"
    )
    repeats = _one(
        con,
        """SELECT count(*) FILTER (WHERE ts_us = prev_ts AND bid = prev_bid AND ask = prev_ask
                                   AND bid_volume IS NOT DISTINCT FROM prev_bv
                                   AND ask_volume IS NOT DISTINCT FROM prev_av)
           FROM (SELECT ts_us, bid, ask, bid_volume, ask_volume,
                        lag(ts_us) OVER w AS prev_ts, lag(bid) OVER w AS prev_bid, lag(ask) OVER w AS prev_ask,
                        lag(bid_volume) OVER w AS prev_bv, lag(ask_volume) OVER w AS prev_av
                 FROM ticks WINDOW w AS (PARTITION BY raw_sha256 ORDER BY raw_row))""",
    )
    disorder = con.execute(
        """SELECT ts_us FROM (SELECT ts_us, lag(ts_us) OVER (PARTITION BY raw_sha256 ORDER BY raw_row) AS prev
                              FROM ticks) WHERE prev IS NOT NULL AND ts_us < prev ORDER BY ts_us"""
    ).fetchall()
    counts = {
        "total": int(total[0]),
        "valid": int(total[1] or 0),
        "non_positive": int(total[2] or 0),
        "crossed": int(total[3] or 0),
        "simultaneous_timestamps": int(simultaneous[0]),
        "simultaneous_ticks": int(simultaneous[1]),
        "exact_consecutive_repeats": int(repeats[0] or 0),
        "out_of_order_within_file": len(disorder),
    }
    return counts, [_utc(int(r[0])) for r in disorder]


def _intervals(
    con: duckdb.DuckDBPyConnection, coverage: list[tuple[datetime, datetime]], threshold: timedelta
) -> tuple[list[Gap], list[Silence], dict[str, int]]:
    """Silences between consecutive valid ticks, and the gaps above `threshold` (as in `summarize_ticks`)."""
    con.execute(
        """CREATE TEMP TABLE deltas AS
           SELECT prev, ts_us, ts_us - prev AS d FROM (
               SELECT ts_us, lag(ts_us) OVER (ORDER BY ts_us, raw_row) AS prev FROM ticks WHERE valid)
           WHERE prev IS NOT NULL"""
    )
    short = _one(
        con,
        """SELECT count(*) FILTER (WHERE d = 0), count(*) FILTER (WHERE d > 0 AND d <= 1000000),
                  count(*) FILTER (WHERE d > 1000000 AND d <= 10000000),
                  count(*) FILTER (WHERE d > 10000000 AND d <= 60000000),
                  count(*) FILTER (WHERE d > 60000000) FROM deltas""",
    )
    short_intervals = {
        "same_timestamp": int(short[0] or 0),
        "le_1s": int(short[1] or 0),
        "1s_10s": int(short[2] or 0),
        "10s_60s": int(short[3] or 0),
        "gt_60s": int(short[4] or 0),
    }
    floor = min(60_000_000, int(threshold.total_seconds() * 1_000_000))
    long_rows = con.execute("SELECT prev, ts_us, d FROM deltas WHERE d > $1 ORDER BY ts_us", [floor]).fetchall()
    candidates = [(_utc(int(a)), _utc(int(b))) for a, b, _ in long_rows]
    silences = [
        Silence(before, after, expected_open_minutes(before, after))
        for (before, after), row in zip(candidates, long_rows, strict=True)
        if row[2] > 60_000_000
    ]
    gaps: list[Gap] = []
    for c_start, c_end in coverage:
        lo, hi = _us(c_start), _us(c_end)
        bounds = con.execute(
            "SELECT min(ts_us), max(ts_us) FROM ticks WHERE valid AND ts_us >= $1 AND ts_us < $2", [lo, hi]
        ).fetchone() or (None, None)
        if bounds[0] is None:
            edges = [(c_start, c_end)]
        else:
            edges = [
                (c_start, _utc(int(bounds[0]))),
                *((a, b) for a, b in candidates if c_start <= a and b < c_end),
                (_utc(int(bounds[1])), c_end),
            ]
        for before, after in edges:
            if after - before > threshold:
                gaps.append(Gap(before, after, expected_open_minutes(before, after)))
    gaps.sort(key=lambda g: g.start_utc)
    return gaps, silences, short_intervals


def _slot_rows(con: duckdb.DuckDBPyConnection, grid: Grid) -> list[dict[str, Any]]:
    """One row per slot holding at least one tick (valid or not)."""
    width = grid.minutes * US_PER_MINUTE
    key = "ts_us::HUGEINT * 1000000000 + raw_row"
    rows = con.execute(
        f"""SELECT ts_us // {width} AS slot,
                  arg_min(bid, {key}) FILTER (WHERE valid), max(bid) FILTER (WHERE valid),
                  min(bid) FILTER (WHERE valid), arg_max(bid, {key}) FILTER (WHERE valid),
                  arg_min(ask, {key}) FILTER (WHERE valid), max(ask) FILTER (WHERE valid),
                  min(ask) FILTER (WHERE valid), arg_max(ask, {key}) FILTER (WHERE valid),
                  count(*) FILTER (WHERE valid), count(*) FILTER (WHERE NOT valid),
                  count(*) FILTER (WHERE bid <= 0 OR ask <= 0),
                  count(*) FILTER (WHERE bid > 0 AND ask > 0 AND bid > ask),
                  min(ts_us) FILTER (WHERE valid), max(ts_us) FILTER (WHERE valid),
                  count(DISTINCT ts_us // {5 * US_PER_MINUTE}) FILTER (WHERE valid)
           FROM ticks GROUP BY slot ORDER BY slot"""  # noqa: S608 (integer constants)
    ).fetchall()
    result = []
    for r in rows:
        start = _utc(int(r[0]) * width)
        valid = int(r[9])
        result.append(
            {
                "start_utc": start,
                "end_utc": start + timedelta(minutes=grid.minutes),
                "content": Content.VALID if valid else Content.INVALID_ONLY,
                **{name: (Decimal(r[i + 1]) if valid else None) for i, name in enumerate(PRICES)},
                "tick_count": valid,
                "excluded_ticks": int(r[10]),
                "non_positive_ticks": int(r[11]),
                "crossed_ticks": int(r[12]),
                "first_tick_utc": _utc(int(r[13])) if valid else None,
                "last_tick_utc": _utc(int(r[14])) if valid else None,
                "valid_m5_subslots": int(r[15]),
            }
        )
    return result


def _empty(start: datetime, grid: Grid) -> dict[str, Any]:
    return {
        "start_utc": start,
        "end_utc": start + timedelta(minutes=grid.minutes),
        "content": Content.EMPTY,
        **dict.fromkeys(PRICES),
        "tick_count": 0,
        "excluded_ticks": 0,
        "non_positive_ticks": 0,
        "crossed_ticks": 0,
        "first_tick_utc": None,
        "last_tick_utc": None,
        "valid_m5_subslots": 0,
    }


def expected_slots(coverage: list[tuple[datetime, datetime]], grid: Grid) -> list[datetime]:
    """Slot starts during expected-open hours (closures fall on whole hours: slots are wholly open or closed)."""
    per_hour = 60 // grid.minutes
    step = timedelta(minutes=grid.minutes)
    return [
        hour + i * step
        for c_start, c_end in coverage
        for hour in expected_open_hours(c_start, c_end)
        for i in range(per_hour)
        if hour + (i + 1) * step <= c_end
    ]


class _GapLookup:
    """Gaps are disjoint intervals between consecutive ticks: sorted starts and ends allow bisection."""

    def __init__(self, gaps: list[Gap]) -> None:
        self.gaps = sorted(gaps, key=lambda g: g.start_utc)
        self.starts = [g.start_utc for g in self.gaps]
        self.ends = [g.end_utc for g in self.gaps]

    def touching(self, start: datetime, end: datetime) -> list[Gap]:
        lo = bisect.bisect_right(self.ends, start)
        hi = bisect.bisect_left(self.starts, end)
        return self.gaps[lo:hi]


def _covered(start: datetime, end: datetime, coverage: list[tuple[datetime, datetime]]) -> bool:
    return any(c_start <= start and end <= c_end for c_start, c_end in coverage)


def _is_complete(flags: list[str], convention: QualityConvention) -> bool:
    markers = (
        (*INTRADAY_INCOMPLETE_MARKERS, SUBSLOTS_FLAG)
        if convention.empty_subslot_not_ok
        else INTRADAY_INCOMPLETE_MARKERS
    )
    return not any(marker in flag for flag in flags for marker in markers)


def _finish(
    bar: dict[str, Any],
    grid: Grid,
    coverage: list[tuple[datetime, datetime]],
    gaps: _GapLookup,
    convention: QualityConvention,
) -> None:
    """Retrospective and close-time statuses, both from this candle's own ticks and the tick gaps."""
    threshold = convention.threshold
    start, end = bar["start_utc"], bar["end_utc"]
    state = market_state(start)
    bar["expected_open"] = state is MarketState.OPEN
    common = []
    if not _covered(start, end, coverage):
        common.append("hors couverture déclarée (bougie non clôturée ou partielle dans l'échantillon)")
    if state is MarketState.PROBABLE_HOLIDAY:
        common.append("jour férié probable")
    elif state is MarketState.WEEKLY_CLOSURE and bar["content"] is not Content.EMPTY:
        common.append("ticks pendant la fermeture prévue")
    if bar["content"] is Content.EMPTY:
        common.append(NO_TICK)
    elif bar["content"] is Content.INVALID_ONLY:
        common.append(NO_VALID_TICK)
    gap_flag = f"trou de cotation > {threshold.total_seconds() / 60:g} min pendant l'ouverture prévue"
    invalid = [f"{bar['excluded_ticks']} tick(s) invalides exclus"] if bar["excluded_ticks"] else []
    info = []
    if grid is Grid.M15 and bar["expected_open"] and bar["valid_m5_subslots"] < 3:
        info.append(f"{SUBSLOTS_FLAG} : {3 - bar['valid_m5_subslots']}/3")
    near = gaps.touching(start, end)
    retro = overlaps_gap(start, end, near, threshold)
    known = overlaps_gap(start, end, near, threshold, known_until=end)
    bar["flags"] = common + ([gap_flag] if retro else []) + invalid + info
    bar["flags_at_close"] = common + ([gap_flag] if known else []) + invalid + info
    bar["complete"] = _is_complete(bar["flags"], convention)
    bar["complete_at_close"] = _is_complete(bar["flags_at_close"], convention)


def build_intraday(
    store: HistoryStore,
    source: str,
    instrument: str,
    start: datetime = WINDOW_START,
    end: datetime = WINDOW_END,
    convention: QualityConvention = REFERENCE_10MIN,
) -> IntradayBuild:
    build, con = _prepare(store, source, instrument, start, end, convention)
    lookup = _GapLookup(build.gaps)
    for grid in Grid:
        present = {row["start_utc"]: row for row in _slot_rows(con, grid)}
        for slot in expected_slots(build.coverage, grid):
            if slot not in present:
                present[slot] = _empty(slot, grid)
        bars = [present[s] for s in sorted(present)]
        for bar in bars:
            _finish(bar, grid, build.coverage, lookup, convention)
        build.bars[grid] = bars
    con.close()
    return build


def _prepare(
    store: HistoryStore, source: str, instrument: str, start: datetime, end: datetime, convention: QualityConvention
) -> tuple[IntradayBuild, duckdb.DuckDBPyConnection]:
    files = select_files(store, source, instrument, start, end)
    coverage = _coverage(files)
    con = _connect(store, files, start, end)
    ticks, disorder = _tick_counts(con)
    gaps, silences, short = _intervals(con, coverage, convention.threshold)
    return IntradayBuild((start, end), convention, files, coverage, ticks, gaps, silences, short, disorder), con


def restatus_intraday(
    store: HistoryStore,
    source: str,
    instrument: str,
    bars: dict[Grid, list[dict[str, Any]]],
    convention: QualityConvention,
    start: datetime = WINDOW_START,
    end: datetime = WINDOW_END,
) -> IntradayBuild:
    """Statuses of already built candles under another convention; prices, counts and contents are reused.

    Only the silences are read again from the ticks of [start, end); candles ending after `end` are dropped.
    """
    build, con = _prepare(store, source, instrument, start, end, convention)
    con.close()
    lookup = _GapLookup(build.gaps)
    for grid in Grid:
        rows = []
        for source_row in bars[grid]:
            if source_row["start_utc"] < start or source_row["end_utc"] > end:
                continue
            row = {k: v for k, v in source_row.items() if k not in ("flags", "flags_at_close")}
            _finish(row, grid, build.coverage, lookup, convention)
            rows.append(row)
        build.bars[grid] = rows
    return build


def read_intraday(path: Path) -> list[dict[str, Any]]:
    """Candles written by `intraday_table`, with their content as `Content`."""
    rows: list[dict[str, Any]] = pq.read_table(path).to_pylist()
    for row in rows:
        row["content"] = Content(row["content"])
    return rows


def intraday_table(source: str, instrument: str, grid: Grid, bars: list[dict[str, Any]]) -> pa.Table:
    columns: dict[str, list[Any]] = {name: [] for name in INTRADAY_SCHEMA.names}
    fixed = {"source": source, "instrument": instrument, "timeframe": grid.value}
    for bar in bars:
        for name in INTRADAY_SCHEMA.names:
            value = fixed[name] if name in fixed else bar[name]
            columns[name].append(value.value if isinstance(value, Content) else value)
    return pa.table(columns, schema=INTRADAY_SCHEMA)


# ----------------------------------------------------------------- conservation checks


def _children(
    parents: list[dict[str, Any]], children: list[dict[str, Any]], width: timedelta
) -> dict[datetime, list[dict[str, Any]]]:
    groups: dict[datetime, list[dict[str, Any]]] = {p["start_utc"]: [] for p in parents}
    for child in children:
        start = child["start_utc"]
        anchor = start - timedelta(
            minutes=(start.minute % int(width.total_seconds() // 60)),
            seconds=start.second,
            microseconds=start.microsecond,
        )
        groups.setdefault(anchor, []).append(child)
    return groups


def _aggregate(children: list[dict[str, Any]]) -> dict[str, Any]:
    """Expected parent values from its children; EMPTY and INVALID_ONLY children give no price."""
    valid = [c for c in children if c["content"] is Content.VALID]
    result: dict[str, Any] = {
        "tick_count": sum(c["tick_count"] for c in children),
        "excluded_ticks": sum(c["excluded_ticks"] for c in children),
    }
    if not valid:
        result["content"] = Content.INVALID_ONLY if result["excluded_ticks"] else Content.EMPTY
        return result
    result.update(
        content=Content.VALID,
        bid_open=valid[0]["bid_open"],
        bid_high=max(c["bid_high"] for c in valid),
        bid_low=min(c["bid_low"] for c in valid),
        bid_close=valid[-1]["bid_close"],
        ask_open=valid[0]["ask_open"],
        ask_high=max(c["ask_high"] for c in valid),
        ask_low=min(c["ask_low"] for c in valid),
        ask_close=valid[-1]["ask_close"],
        first_tick_utc=valid[0]["first_tick_utc"],
        last_tick_utc=valid[-1]["last_tick_utc"],
        valid_subslots=len(valid),
    )
    return result


COMPARED = (*PRICES, "tick_count", "excluded_ticks", "first_tick_utc", "last_tick_utc")


def _has_gap(flags: list[str]) -> bool:
    return any(f.startswith("trou de cotation") for f in flags)


def check_m5_to_m15(m5: list[dict[str, Any]], m15: list[dict[str, Any]]) -> dict[str, Any]:
    """Prices, counts, content and gap statuses of each M15 against its three M5 (option 2: both from ticks)."""
    groups = _children(m15, m5, timedelta(minutes=15))
    mismatches: list[dict[str, Any]] = []
    status_mismatches: list[dict[str, Any]] = []
    orphans = [k.isoformat() for k in groups if k not in {b["start_utc"] for b in m15} and groups[k]]
    checked = 0
    for bar in m15:
        children = sorted(groups.get(bar["start_utc"], []), key=lambda c: c["start_utc"])
        expected = _aggregate(children)
        checked += 1
        fields = ["content", "tick_count", "excluded_ticks"]
        if expected["content"] is Content.VALID:
            fields += [f for f in COMPARED if f not in fields]
        diff = [f for f in fields if bar[f] != expected[f]]
        if expected["content"] is Content.VALID and bar["valid_m5_subslots"] != expected["valid_subslots"]:
            diff.append("valid_m5_subslots")
        if expected["content"] is not Content.VALID and any(bar[p] is not None for p in PRICES):
            diff.append("prix sans tick valide")
        if diff:
            mismatches.append({"start_utc": bar["start_utc"].isoformat(), "fields": diff})
        for key in ("flags_at_close", "flags"):
            if _has_gap(bar[key]) != any(_has_gap(c[key]) for c in children):
                status_mismatches.append({"start_utc": bar["start_utc"].isoformat(), "status": key})
    return {
        "checked_m15": checked,
        "mismatches": mismatches,
        "orphan_m5_groups": orphans,
        "gap_status_mismatches": status_mismatches,
    }


def check_m15_to_h1(m15: list[dict[str, Any]], h1: list[dict[str, Any]], compare_status: bool = True) -> dict[str, Any]:
    """Each existing H1 against its four M15; an H1 exists only for an hour with a valid tick.

    `compare_status=False` when the M15 follow another silence convention than the H1 (10 min).
    """
    groups = _children([], m15, timedelta(hours=1))
    by_hour = {b["start_utc"]: b for b in h1}
    mismatches: list[dict[str, Any]] = []
    status_mismatches: list[dict[str, Any]] = []
    missing_h1, extra_h1, invalid_only_hours = [], [], 0
    for hour, children in sorted(groups.items()):
        children.sort(key=lambda c: c["start_utc"])
        expected = _aggregate(children)
        bar = by_hour.get(hour)
        if expected["content"] is not Content.VALID:
            if bar is not None:
                extra_h1.append(hour.isoformat())
            if expected["content"] is Content.INVALID_ONLY:
                invalid_only_hours += 1
            continue
        if bar is None:
            missing_h1.append(hour.isoformat())
            continue
        diff = [f for f in COMPARED if bar[f] != expected[f]]
        if diff:
            mismatches.append({"start_utc": hour.isoformat(), "fields": diff})
        for key in ("flags_at_close", "flags") if compare_status else ():
            if _has_gap(bar[key]) != any(_has_gap(c[key]) for c in children):
                status_mismatches.append({"start_utc": hour.isoformat(), "status": key})
    extra_h1 += [h.isoformat() for h in by_hour if h not in groups]
    return {
        "checked_h1": sum(1 for h in by_hour if h in groups),
        "mismatches": mismatches,
        "h1_missing": missing_h1,
        "h1_without_valid_m15": extra_h1,
        "hours_with_invalid_ticks_only": invalid_only_hours,
        "gap_status_mismatches": status_mismatches,
    }


def check_totals(build: IntradayBuild) -> dict[str, Any]:
    """Ticks read = sum over M5 = sum over M15 = rows declared by the selected files."""
    declared = sum(f.rows for f in build.files)
    sums = {
        grid.value: {
            "valid": sum(b["tick_count"] for b in bars),
            "excluded": sum(b["excluded_ticks"] for b in bars),
            "non_positive": sum(b["non_positive_ticks"] for b in bars),
            "crossed": sum(b["crossed_ticks"] for b in bars),
        }
        for grid, bars in build.bars.items()
    }
    read = {
        "valid": build.ticks["valid"],
        "excluded": build.ticks["total"] - build.ticks["valid"],
        "non_positive": build.ticks["non_positive"],
        "crossed": build.ticks["crossed"],
    }
    ok = declared == build.ticks["total"] and all(s == read for s in sums.values())
    return {"declared_by_files": declared, "read": read, "by_grid": sums, "ok": ok}


def check_no_leak(full: IntradayBuild, truncated: IntradayBuild) -> dict[str, Any]:
    """Every candle ending by the truncation date: same prices, counts and close-time status."""
    cut = truncated.window[1]
    keys = (*COMPARED, "content", "complete_at_close", "flags_at_close")
    result: dict[str, Any] = {"cut_utc": cut.isoformat()}
    for grid in Grid:
        a = {b["start_utc"]: b for b in full.bars[grid] if b["end_utc"] <= cut}
        b_ = {b["start_utc"]: b for b in truncated.bars[grid] if b["end_utc"] <= cut}
        differ = [s.isoformat() for s in a if s not in b_ or any(a[s][k] != b_[s][k] for k in keys)]
        differ += [s.isoformat() for s in b_ if s not in a]
        retro = sum(1 for s in a if s in b_ and a[s]["flags"] != b_[s]["flags"])
        result[grid.value] = {"compared": len(a), "close_time_differences": differ, "retrospective_differences": retro}
    return result
