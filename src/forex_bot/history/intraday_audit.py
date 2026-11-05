"""Builds and audits the M5/M15 candles (protocol docs/experiments/DATA_M5_M15_2015_2021.md).

    uv run forex-intraday --leak-cut 2018-07-01

Data only: no strategy, no signal, no performance measure. Reads 2015-2021 ticks only. Writes the
candles and the detailed report under data/ (outside Git); exits with status 3 if a conservation or
anti-leak check fails, so that the run stops for a diagnosis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

from forex_bot.history.calendar import ONE_HOUR, MarketState, market_state
from forex_bot.history.intraday import (
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
    intraday_table,
)
from forex_bot.history.store import HistoryStore

LONDON = ZoneInfo("Europe/London")
DAY01_WINDOW = (time(1), time(16))  # Europe/London, DAY_01 sheet §3
SUBWINDOWS = {"01-08": (time(1), time(8)), "08-12": (time(8), time(12)), "12-16": (time(12), time(16))}
SILENCE_BUCKETS = [1, 2, 3, 5, 10, 15, 30, 60]  # minutes of expected-open time


# ----------------------------------------------------------------- London sessions


def london_instant(day: date, moment: time) -> datetime:
    return datetime.combine(day, moment, tzinfo=LONDON).astimezone(UTC)


def london_sessions(start: datetime, end: datetime) -> list[date]:
    """London weekdays whose whole DAY_01 window lies in [start, end)."""
    day, days = start.astimezone(LONDON).date(), []
    while london_instant(day, DAY01_WINDOW[0]) < end:
        if (
            day.weekday() < 5
            and start <= london_instant(day, DAY01_WINDOW[0])
            and london_instant(day, DAY01_WINDOW[1]) <= end
        ):
            days.append(day)
        day += timedelta(days=1)
    return days


def session_anomalies(days: list[date]) -> dict[str, list[str]]:
    """Windows that would straddle a clock change or an expected weekly closure (none expected)."""
    clock, closure = [], []
    for day in days:
        lo, hi = london_instant(day, DAY01_WINDOW[0]), london_instant(day, DAY01_WINDOW[1])
        if (lo.astimezone(LONDON).utcoffset(), lo.astimezone(ZoneInfo("America/New_York")).utcoffset()) != (
            (hi - timedelta(microseconds=1)).astimezone(LONDON).utcoffset(),
            (hi - timedelta(microseconds=1)).astimezone(ZoneInfo("America/New_York")).utcoffset(),
        ):
            clock.append(day.isoformat())
        hour = lo
        while hour < hi:
            if market_state(hour) is MarketState.WEEKLY_CLOSURE:
                closure.append(day.isoformat())
                break
            hour += ONE_HOUR
    return {"clock_change_inside_window": clock, "weekly_closure_inside_window": closure}


def _in_day01(moment: datetime) -> bool:
    local = moment.astimezone(LONDON)
    return local.weekday() < 5 and DAY01_WINDOW[0] <= local.time() < DAY01_WINDOW[1]


# ----------------------------------------------------------------- audit


def _flag_key(flag: str) -> str:
    """Flag family: drops the leading count ("3 tick(s) invalides exclus") and the trailing ratio."""
    head = flag.split(" :")[0]
    return head.split(" ", 1)[1] if head[:1].isdigit() else head


def _grid_summary(bars: list[dict[str, Any]]) -> dict[str, Any]:
    by_year: dict[str, Counter[str]] = defaultdict(Counter)
    flags_at_close: dict[str, Counter[str]] = defaultdict(Counter)
    for bar in bars:
        year = str(bar["start_utc"].year)
        c = by_year[year]
        scope = "expected" if bar["expected_open"] else "outside_expected_with_ticks"
        c[scope] += 1
        c[f"{scope}_{bar['content'].value}"] += 1
        if bar["expected_open"]:
            c["ok_at_close"] += bar["complete_at_close"]
            c["ok_retrospective"] += bar["complete"]
            c["retrospective_only_incomplete"] += bar["complete_at_close"] and not bar["complete"]
            c["incomplete_with_valid_ticks"] += bar["content"] is Content.VALID and not bar["complete_at_close"]
            if bar["content"] is Content.EMPTY:
                c["empty_touched_by_gap_retrospective"] += any(f.startswith("trou") for f in bar["flags"])
                c["empty_touched_by_gap_at_close"] += any(f.startswith("trou") for f in bar["flags_at_close"])
        for flag in bar["flags_at_close"]:
            flags_at_close[year][_flag_key(flag)] += 1
    total: Counter[str] = Counter()
    for c in by_year.values():
        total.update(c)
    flags_total: Counter[str] = Counter()
    for c in flags_at_close.values():
        flags_total.update(c)
    return {
        "by_year": {y: dict(c) for y, c in sorted(by_year.items())},
        "total": dict(total),
        "flags_at_close_by_year": {y: dict(c) for y, c in sorted(flags_at_close.items())},
        "flags_at_close_total": dict(flags_total),
    }


def _day01(build: IntradayBuild, days: list[date]) -> dict[str, Any]:
    index = {grid: {b["start_utc"]: b for b in build.bars[grid]} for grid in Grid}

    def slots(grid: Grid, day: date, lo: time, hi: time) -> list[dict[str, Any] | None]:
        start, end = london_instant(day, lo), london_instant(day, hi)
        step = timedelta(minutes=grid.minutes)
        result, cursor = [], start
        while cursor < end:
            result.append(index[grid].get(cursor))
            cursor += step
        return result

    def all_ok(bars: list[dict[str, Any] | None]) -> bool:
        return all(b is not None and b["complete_at_close"] for b in bars)

    by_year: dict[str, Counter[str]] = defaultdict(Counter)
    windows: dict[str, dict[str, Counter[str]]] = {g.value: defaultdict(Counter) for g in Grid}
    for day in days:
        c = by_year[str(day.year)]
        c["sessions"] += 1
        holiday = market_state(london_instant(day, DAY01_WINDOW[0])) is MarketState.PROBABLE_HOLIDAY
        c["sessions_probable_holiday"] += holiday
        c["range_28_m15_ok"] += all_ok(slots(Grid.M15, day, time(1), time(8)))
        c["m15_08_12_all_ok"] += all_ok(slots(Grid.M15, day, time(8), time(12)))
        c["m5_08_12_all_ok"] += all_ok(slots(Grid.M5, day, time(8), time(12)))
        c["m5_08_16_all_ok"] += all_ok(slots(Grid.M5, day, time(8), time(16)))
        c["range_ok_and_m5_08_12_all_ok"] += all_ok(slots(Grid.M15, day, time(1), time(8))) and all_ok(
            slots(Grid.M5, day, time(8), time(12))
        )
        for grid in Grid:
            for name, (lo, hi) in SUBWINDOWS.items():
                w = windows[grid.value][name]
                for bar in slots(grid, day, lo, hi):
                    w["slots"] += 1
                    if bar is None:
                        w["no_row"] += 1  # expected-open slots always have a row: only on closed days
                        continue
                    w[bar["content"].value] += 1
                    w["ok_at_close"] += bar["complete_at_close"]
                    w["valid_not_ok_at_close"] += bar["content"] is Content.VALID and not bar["complete_at_close"]
                    for flag in bar["flags_at_close"]:
                        w[f"flag: {_flag_key(flag)}"] += 1
    return {
        "sessions_by_year": {y: dict(c) for y, c in sorted(by_year.items())},
        "windows": {g: {n: dict(c) for n, c in w.items()} for g, w in windows.items()},
    }


def _silences(build: IntradayBuild) -> dict[str, Any]:
    def bucket(minutes: float) -> str:
        if minutes <= SILENCE_BUCKETS[0]:
            return f"<= {SILENCE_BUCKETS[0]} min"
        for lo, hi in pairwise(SILENCE_BUCKETS):
            if minutes <= hi:
                return f"{lo}-{hi} min"
        return f"> {SILENCE_BUCKETS[-1]} min"

    order = [f"<= {SILENCE_BUCKETS[0]} min"]
    order += [f"{lo}-{hi} min" for lo, hi in pairwise(SILENCE_BUCKETS)]
    order += [f"> {SILENCE_BUCKETS[-1]} min"]
    by_scope: dict[str, Counter[str]] = defaultdict(Counter)
    by_year: dict[str, Counter[str]] = defaultdict(Counter)
    open_quantiles: list[float] = []
    for s in build.silences:
        if s.open_minutes <= 0:
            by_scope["closed_time_only"]["count"] += 1
            continue
        scope = "day01_window" if _in_day01(s.start_utc) else "other_open_hours"
        key = bucket(s.open_minutes)
        by_scope[scope][key] += 1
        by_year[str(s.start_utc.year)][key] += 1
        open_quantiles.append(s.open_minutes)
    open_quantiles.sort()

    def q(p: float) -> float | None:
        return (
            round(open_quantiles[min(len(open_quantiles) - 1, int(p * len(open_quantiles)))], 2)
            if open_quantiles
            else None
        )

    return {
        "definition": (
            "intervalle entre deux ticks valides consécutifs (horodatages distincts) ; au-delà de 60 s, "
            "durée en temps d'ouverture prévue ; fenêtre DAY_01 selon l'instant du début du silence"
        ),
        "intervals_le_60s": build.short_intervals,
        "buckets": order,
        "gt_60s_by_scope": {k: dict(v) for k, v in sorted(by_scope.items())},
        "gt_60s_by_year": {k: dict(v) for k, v in sorted(by_year.items())},
        "gt_60s_open_minutes_quantiles": {"p50": q(0.5), "p90": q(0.9), "p99": q(0.99), "max": q(1.0)},
        "longest_in_day01_window": [
            {
                "start_utc": s.start_utc.isoformat(),
                "end_utc": s.end_utc.isoformat(),
                "open_minutes": round(s.open_minutes, 1),
            }
            for s in sorted(
                (s for s in build.silences if _in_day01(s.start_utc) and s.open_minutes > 0),
                key=lambda s: -s.open_minutes,
            )[:15]
        ],
    }


def audit(
    build: IntradayBuild,
    h1: list[dict[str, Any]],
    truncated: IntradayBuild | None,
) -> dict[str, Any]:
    start, end = build.window
    days = london_sessions(start, end)
    m5, m15 = build.bars[Grid.M5], build.bars[Grid.M15]
    checks = {
        "totals": check_totals(build),
        "m5_to_m15": check_m5_to_m15(m5, m15),
        "m15_to_h1": check_m15_to_h1(m15, h1),
        "london_sessions": session_anomalies(days),
    }
    if truncated is not None:
        checks["no_leak"] = check_no_leak(build, truncated)
    # The existing H1 were built with a coverage running to 2024: only the silence that reaches the
    # end of this window can be judged differently. Every mismatch is listed with that explanation.
    tail = [g.start_utc for g in build.gaps if g.end_utc == build.coverage[-1][1]]
    for mismatch in checks["m15_to_h1"]["gap_status_mismatches"]:
        hour = datetime.fromisoformat(mismatch["start_utc"])
        mismatch["explained_by_window_end"] = bool(tail) and hour + ONE_HOUR > tail[0]
    return {
        "window": [start.isoformat(), end.isoformat()],
        "silence_threshold_min": build.threshold.total_seconds() / 60,
        "silence_threshold_status": "convention provisoire d'audit (ASSUMP-017), règle M5/M15 à décider",
        "files": {
            "count": len(build.files),
            "first_period_start_utc": build.files[0].period_start_utc.isoformat(),
            "last_period_end_utc": build.files[-1].period_end_utc.isoformat(),
            "entries_sha256": hashlib.sha256("\n".join(sorted(f.entry for f in build.files)).encode()).hexdigest(),
        },
        "coverage": [[s.isoformat(), e.isoformat()] for s, e in build.coverage],
        "ticks": {
            **build.ticks,
            "out_of_order_in_day01_window": sum(1 for t in build.out_of_order_ts if _in_day01(t)),
        },
        "gaps_above_threshold": len(build.gaps),
        "checks": checks,
        "grids": {grid.value: _grid_summary(build.bars[grid]) for grid in Grid},
        "m15_subslots_without_valid_tick": dict(
            Counter(
                f.split(" : ")[1]
                for b in m15
                for f in b["flags_at_close"]
                if f.startswith("sous-créneaux") and b["content"] is Content.VALID
            )
        ),
        "day01": _day01(build, days),
        "silences": _silences(build),
    }


def checks_failed(report: dict[str, Any]) -> list[str]:
    """Checks that must stop the run (conservation, anti-leak, London windows)."""
    c = report["checks"]
    failed = []
    if not c["totals"]["ok"]:
        failed.append("totaux de ticks")
    if c["m5_to_m15"]["mismatches"] or c["m5_to_m15"]["orphan_m5_groups"]:
        failed.append("M5 -> M15")
    if c["m15_to_h1"]["mismatches"] or c["m15_to_h1"]["h1_missing"] or c["m15_to_h1"]["h1_without_valid_m15"]:
        failed.append("M15 -> H1")
    if c["m5_to_m15"]["gap_status_mismatches"]:
        failed.append("états de silence M5 -> M15")
    if any(c["london_sessions"].values()):
        failed.append("fenêtres de Londres")
    leak = c.get("no_leak")
    if leak and any(leak[g.value]["close_time_differences"] for g in Grid):
        failed.append("anti-fuite")
    # H1 status mismatches are expected only at the end of coverage; listed for diagnosis, never hidden.
    unexplained = [m for m in c["m15_to_h1"]["gap_status_mismatches"] if not m["explained_by_window_end"]]
    if unexplained:
        failed.append("états de silence M15 -> H1")
    return failed


# ----------------------------------------------------------------- outputs


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def existing_bar_hashes(store: HistoryStore, source: str, instrument: str) -> dict[str, str]:
    directory = store.data_dir / "bars" / source / instrument
    return {p.name: sha256_file(p) for p in sorted(directory.glob("*.parquet"))}


def read_h1(store: HistoryStore, source: str, instrument: str) -> list[dict[str, Any]]:
    """Existing H1 rows of the window only (filtered at read time)."""
    path = store.data_dir / "bars" / source / instrument / "1h.parquet"
    table = pq.read_table(path, filters=[("start_utc", ">=", WINDOW_START), ("start_utc", "<", WINDOW_END)])
    return list(table.to_pylist())


def write_outputs(store: HistoryStore, source: str, instrument: str, build: IntradayBuild) -> dict[str, str]:
    directory = store.data_dir / "bars" / source / instrument / "intraday_2015_2021"
    directory.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for grid in Grid:
        target = directory / f"{grid.value}.parquet"
        tmp = target.with_name(f"{target.name}.tmp-{os.getpid()}")
        pq.write_table(intraday_table(source, instrument, grid, build.bars[grid]), tmp)
        os.replace(tmp, target)
        hashes[target.as_posix()] = sha256_file(target)
    return hashes


def provenance(argv: list[str] | None) -> dict[str, Any]:
    executable = shutil.which("git")

    def git(*command: str) -> str:
        if executable is None:
            return ""
        done = subprocess.run([executable, *command], capture_output=True, text=True, check=False)  # noqa: S603
        return done.stdout.strip()

    diff = git("diff", "HEAD")
    return {
        "commit": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "uncommitted_diff_sha256": hashlib.sha256(diff.encode()).hexdigest() if diff else None,
        "command": ["forex-intraday", *(sys.argv[1:] if argv is None else argv)],
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def to_markdown(report: dict[str, Any]) -> str:
    p, c = report["provenance"], report["checks"]
    lines = [
        "# Audit M5/M15 EUR/USD 2015-2021 (détail, hors Git)",
        "",
        f"Commit `{p['commit']}`, diff non commité : {p['uncommitted_diff_sha256'] or 'aucun'} ; "
        f"commande `{' '.join(p['command'])}`.",
        f"Seuil de silence : {report['silence_threshold_min']:.0f} min ({report['silence_threshold_status']}).",
        f"Contrôles en échec : {', '.join(report['failed_checks']) or 'aucun'}.",
        "",
        "## Contrôles",
        "",
        "```json",
        json.dumps(
            {
                "totals": c["totals"],
                "m5_to_m15": {k: (v if not isinstance(v, list) else len(v)) for k, v in c["m5_to_m15"].items()},
                "m15_to_h1": {k: (v if not isinstance(v, list) else len(v)) for k, v in c["m15_to_h1"].items()},
                "m15_to_h1_gap_status_mismatches": c["m15_to_h1"]["gap_status_mismatches"],
                "london_sessions": {k: len(v) for k, v in c["london_sessions"].items()},
                "no_leak": {
                    k: (
                        v
                        if not isinstance(v, dict)
                        else {**v, "close_time_differences": len(v["close_time_differences"])}
                    )
                    for k, v in c.get("no_leak", {}).items()
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        "```",
        "",
    ]
    for grid, summary in report["grids"].items():
        lines += [f"## Bougies {grid}", "", "| Année | " + " | ".join(sorted(summary["total"])) + " |"]
        lines.append("|---" * (len(summary["total"]) + 1) + "|")
        for year, counts in summary["by_year"].items():
            lines.append(f"| {year} | " + " | ".join(str(counts.get(k, 0)) for k in sorted(summary["total"])) + " |")
        lines += ["", "Marques à la clôture : " + json.dumps(summary["flags_at_close_total"], ensure_ascii=False), ""]
    lines += [
        "## Fenêtres DAY_01",
        "",
        "```json",
        json.dumps(report["day01"], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Silences",
        "",
        "```json",
        json.dumps(report["silences"], indent=2, ensure_ascii=False),
        "```",
    ]
    return "\n".join(lines) + "\n"


def _date(text: str) -> datetime:
    return datetime.combine(date.fromisoformat(text), time(), tzinfo=UTC)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forex-intraday", description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--source", default="dukascopy")
    parser.add_argument("--instrument", default="EURUSD")
    parser.add_argument("--leak-cut", type=_date, required=True, help="date de la construction tronquée (anti-fuite)")
    args = parser.parse_args(argv)
    store = HistoryStore(args.data_dir)
    before = existing_bar_hashes(store, args.source, args.instrument)
    build = build_intraday(store, args.source, args.instrument)
    outputs = write_outputs(store, args.source, args.instrument, build)
    truncated = build_intraday(store, args.source, args.instrument, WINDOW_START, args.leak_cut)
    report = audit(build, read_h1(store, args.source, args.instrument), truncated)
    after = existing_bar_hashes(store, args.source, args.instrument)
    report["provenance"] = provenance(argv)
    report["outputs_sha256"] = outputs
    report["existing_bars_sha256"] = {"before": before, "after": after, "unchanged": before == after}
    report["failed_checks"] = checks_failed(report) + ([] if before == after else ["fichiers H1/H4/D1 modifiés"])
    reports = store.data_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stem = reports / f"intraday_{args.source}_{args.instrument}_2015_2021"
    stem.with_suffix(".json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    stem.with_suffix(".md").write_text(to_markdown(report), encoding="utf-8")
    print(f"Rapport : {stem}.json / .md")
    print(f"Contrôles en échec : {', '.join(report['failed_checks']) or 'aucun'}")
    return 3 if report["failed_checks"] else 0


if __name__ == "__main__":
    sys.exit(main())
