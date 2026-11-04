"""S3 data availability, step 3 of the protocol (docs/strategies/S3_SQUEEZE.md §9). No tick, no trade.

    uv run forex-s3-availability --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 \
        --out data/reports/backtests/s3_availability_2015_2021.json

The S3 decision rules run over the local H4 and D1 candles and the gaps of the quality report
only: no tick is read, so no position, no result and no drawdown exist. Every expected H4 slot of
the window comes from the calendar (weekly closure and probable holidays excluded). Each expected
slot is either absent, or present with a computable compression (compressed or not), or present
with a compression that is not computable, with its cause.

Boxes follow the approved rules (recognition, frozen bounds, abandonment, expiry). Convention of
this study only (the S3 performance engine is unchanged): a breakout consumes its box and is not
evaluated (no expansion, D1 context, size or order). Box recognition never depends on a position
or on the evaluation of a breakout, so the box counts are those the performance engine would see.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from forex_bot.backtest.data import load_bars, load_gaps
from forex_bot.backtest.engine import DecisionRecord, EntryAction, ResearchConfig
from forex_bot.backtest.explore import INSTRUMENT, RESEARCH_COSTS, SOURCE, _date, _peak_rss_mib, _provenance, _str
from forex_bot.backtest.s1 import StateOf
from forex_bot.backtest.s3 import Box, S3Params, window
from forex_bot.backtest.s3_engine import INCOMPLETE, S3Backtest
from forex_bot.history.calendar import Timeframe, candle_end, candle_start, expected_open_hours
from forex_bot.risk import Side

ONE_HOUR = timedelta(hours=1)
NOT_EVALUATED = "cassure : boîte consommée, non évaluée à cette étape"
TOO_WIDE = "consolidation trop large"


class AvailabilityBacktest(S3Backtest):
    """S3 decisions without ticks; a breakout only consumes its box."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.abandon_cause: dict[datetime, str] = {}  # F -> why the box was abandoned
        self.breakout_side: dict[datetime, Side] = {}  # F -> side of the close out of the box

    def _box_life(
        self, t: int, decision: datetime, h4_state: StateOf, record: DecisionRecord
    ) -> tuple[Box, Side] | None:
        box = self.box
        out = super()._box_life(t, decision, h4_state, record)
        if box is not None and box.ended_utc == decision and (box.end_reason or "").startswith(INCOMPLETE):
            absent = not self._consecutive(t - 1, t)
            self.abandon_cause[box.formed_utc] = "H4 prévue absente" if absent else f"H4 {h4_state(t).value}"
        return out

    def _breakout(
        self,
        t: int,
        decision: datetime,
        h4_state: StateOf,
        context: int,
        breakout: tuple[Box, Side],
        record: DecisionRecord,
    ) -> None:
        box, side = breakout
        self.breakout_side[box.formed_utc] = side
        record.signal = {"side": side.value, "box": box.describe(), "close": self.h4[t]["bid_close"]}
        record.entry_action = EntryAction.NOT_EVALUATED
        record.reasons.append(NOT_EVALUATED)


def expected_h4_slots(start: datetime, end: datetime) -> list[datetime]:
    """Starts of the H4 slots expected open whose availability (end) is in [start, end)."""
    hours = expected_open_hours(start - timedelta(hours=4), end)
    return [h for h in hours if candle_start(h, Timeframe.H4) == h and start <= candle_end(h, Timeframe.H4) < end]


def compression_cause(engine: S3Backtest, t: int, first_width_ordinal: int | None) -> str | None:
    """None if the compression of H4 t is computable; otherwise its first cause (sheet §3)."""
    s3, ordinals = engine.s3, engine.ordinals
    instant = engine.h4_available[t]
    state = engine._state(t, instant)
    if not state.usable:
        return f"H4 elle-même inutilisable ({state.value})"
    if engine.bands_at(t) is None:
        first = t - s3.bb_period + 1
        if first < 0:
            return f"initialisation : moins de {s3.bb_period} H4 depuis le début de l'historique"
        if not engine._consecutive(first, t):
            return f"interruption : H4 prévue absente parmi les {s3.bb_period} H4 des bandes"
        return f"interruption : H4 inutilisable parmi les {s3.bb_period} H4 des bandes"
    if engine.compression_at(t).compressed is None:
        reachable = 0 if first_width_ordinal is None else ordinals[t] - first_width_ordinal
        if reachable < s3.min_history:
            return f"initialisation : moins de {s3.min_history} largeurs possibles depuis le début de l'historique"
        lo, hi = ordinals[t] - s3.history, ordinals[t] - 1
        present = len(window(ordinals, lo, hi))
        if present < hi - max(lo, ordinals[0]) + 1:
            return f"interruption : moins de {s3.min_history} largeurs, H4 prévues absentes dans les {s3.history}"
        return f"interruption : moins de {s3.min_history} largeurs, H4 inutilisables dans les {s3.history}"
    return None


def _ratio(part: int, whole: int) -> str | None:
    return None if not whole else f"{part / whole * 100:.3f}"


def availability(
    h4: list[dict[str, Any]],
    d1: list[dict[str, Any]],
    gaps: list[Any],
    config: ResearchConfig,
    start: datetime,
    end: datetime,
    params: S3Params | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Aggregated counts per year and in total, and the detailed rows (absent slots, causes, boxes)."""
    engine = AvailabilityBacktest(h4, d1, [], gaps, params or S3Params(), config, start_utc=start, end_utc=end)
    result = engine.run()
    s3 = engine.s3
    index = {b["start_utc"]: i for i, b in enumerate(h4)}
    in_window = [i for i, at in enumerate(engine.h4_available) if start <= at < end]
    first_width = next((i for i in range(len(h4)) if engine.bands_at(i) is not None), None)
    first_width_ordinal = None if first_width is None else engine.ordinals[first_width]

    def empty() -> dict[str, Any]:
        return {
            "expected": 0,
            "absent": 0,
            "present_computable": 0,
            "present_not_computable": 0,
            "compressed": 0,
            "not_computable_causes": Counter(),
            "present_outside_calendar": 0,
            "runs": Counter(),
            "boxes": 0,
            "box_fates": Counter(),
            "abandon_causes": Counter(),
            "too_wide_decisions": 0,
            "atr_unavailable": 0,
        }

    years: dict[int, dict[str, Any]] = defaultdict(empty)
    details: list[dict[str, Any]] = []
    slots = expected_h4_slots(start, end)
    expected = set(slots)
    compressed: dict[int, bool] = {}
    for slot in slots:
        year = years[candle_end(slot, Timeframe.H4).year]
        year["expected"] += 1
        t = index.get(slot)
        if t is None:
            year["absent"] += 1
            details.append({"kind": "créneau H4 absent", "slot_start_utc": slot})
            continue
        cause = compression_cause(engine, t, first_width_ordinal)
        if cause is None:
            year["present_computable"] += 1
            compressed[t] = bool(engine.compression_at(t).compressed)
            year["compressed"] += compressed[t]
        else:
            year["present_not_computable"] += 1
            year["not_computable_causes"][cause] += 1
            details.append({"kind": "compression non calculable", "slot_start_utc": slot, "cause": cause})
    for t in in_window:
        if h4[t]["start_utc"] not in expected:
            years[engine.h4_available[t].year]["present_outside_calendar"] += 1
            details.append({"kind": "H4 présente hors calendrier prévu", "slot_start_utc": h4[t]["start_utc"]})

    # Maximal runs of consecutive compressed H4: several compressed candles may form one consolidation.
    formed = {b.index: b for b in engine.boxes}
    too_wide = {e.utc for e in engine.journal if e.kind == "BOÎTE_REFUSÉE" and e.detail.startswith(TOO_WIDE)}
    runs: list[list[int]] = []
    for t in in_window:
        if not compressed.get(t, False):
            continue
        if runs and runs[-1][-1] == t - 1 and engine._consecutive(t - 1, t):
            runs[-1].append(t)
        else:
            runs.append([t])
    for run in runs:
        boxes = sum(1 for t in run if t in formed)
        refused = sum(1 for t in run if engine.h4_available[t] in too_wide)
        if len(run) < s3.compressed_run:
            outcome = f"moins de {s3.compressed_run} H4 : aucune boîte possible"
        elif boxes:
            outcome = "au moins une boîte reconnue"
        elif refused:
            outcome = "aucune boîte : toutes les fenêtres examinées trop larges"
        else:
            outcome = "aucune boîte : autre motif (bougies déjà utilisées, boîte active, ATR)"
        years[engine.h4_available[run[0]].year]["runs"][outcome] += 1
        details.append(
            {
                "kind": "séquence de H4 comprimées",
                "first_available_utc": engine.h4_available[run[0]],
                "length": len(run),
                "boxes": boxes,
                "too_wide_decisions": refused,
                "outcome": outcome,
            }
        )

    for box in engine.boxes:
        year = years[box.formed_utc.year]
        year["boxes"] += 1
        if box.ended_utc is None:
            fate = "active à la fin de l'étude"
        elif box.formed_utc in engine.breakout_side:
            fate = "consommée par une cassure"
        elif box.formed_utc in engine.abandon_cause:
            fate = f"abandonnée : {INCOMPLETE}"
            year["abandon_causes"][engine.abandon_cause[box.formed_utc]] += 1
        else:
            fate = f"expirée après {s3.box_life} H4 sans cassure"
        year["box_fates"][fate] += 1
        details.append({"kind": "boîte", **box.describe(), "fate": fate, "history": box.history})
    for entry in engine.journal:
        if entry.kind == "BOÎTE_REFUSÉE":
            key = "too_wide_decisions" if entry.detail.startswith(TOO_WIDE) else "atr_unavailable"
            years[entry.utc.year][key] += 1
            details.append({"kind": "consolidation refusée", "decision_utc": entry.utc, "reason": entry.detail})

    def finish(c: dict[str, Any]) -> dict[str, Any]:
        computable, boxes = c["present_computable"], c["boxes"]
        abandoned = sum(n for fate, n in c["box_fates"].items() if fate.startswith("abandonnée"))
        expired = sum(n for fate, n in c["box_fates"].items() if fate.startswith("expirée"))
        return {
            "h4_slots": {
                "expected": c["expected"],
                "absent": c["absent"],
                "present_computable": computable,
                "present_not_computable": c["present_not_computable"],
                "pct_of_expected": {
                    k: _ratio(c[k], c["expected"]) for k in ("absent", "present_computable", "present_not_computable")
                },
                "not_computable_causes": dict(c["not_computable_causes"].most_common()),
                "not_computable_causes_pct_of_expected": {
                    k: _ratio(n, c["expected"]) for k, n in c["not_computable_causes"].most_common()
                },
                "present_outside_calendar": c["present_outside_calendar"],
            },
            "compressed_h4": {
                "candles": c["compressed"],
                "pct_of_present_computable": _ratio(c["compressed"], computable),
                "candles_in_recognised_boxes": boxes * s3.compressed_run,
                "runs": sum(c["runs"].values()),
                "runs_by_outcome": dict(c["runs"].most_common()),
            },
            "boxes": {
                "recognised": boxes,
                "fates": dict(c["box_fates"].most_common()),
                "expired": expired,
                "abandoned_missing_data": abandoned,
                "abandoned_pct_of_recognised": _ratio(abandoned, boxes),
                "expired_pct_of_recognised": _ratio(expired, boxes),
                "abandon_causes": dict(c["abandon_causes"].most_common()),
                "refused_too_wide_decisions": c["too_wide_decisions"],
                "refused_atr_unavailable": c["atr_unavailable"],
            },
        }

    total = empty()
    for counts in years.values():
        for key, value in counts.items():
            total[key] += value
    summary = {
        "by_year": {year: finish(years[year]) for year in sorted(years)},
        "total": finish(total),
        "decision_lines": len(result.decisions),
        "breakouts_not_evaluated": len(engine.breakout_side),
    }
    return summary, details


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forex-s3-availability", description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--init-start", type=_date, required=True)
    parser.add_argument("--start", type=_date, required=True)
    parser.add_argument("--end", type=_date, required=True)
    parser.add_argument("--out", type=Path, required=True, help="rapport JSON agrégé (hors Git, sous data/)")
    parser.add_argument("--details-out", type=Path, help="lignes détaillées JSONL (hors Git, sous data/)")
    args = parser.parse_args(argv)
    if not args.init_start <= args.start < args.end:
        parser.error("dates attendues : init-start <= start < end")

    provenance = _provenance(argv, prog="forex-s3-availability")
    began = time.perf_counter()
    bars = {
        tf: load_bars(args.data_dir, SOURCE, INSTRUMENT, tf, args.init_start, args.end)
        for tf in (Timeframe.H4, Timeframe.D1)
    }
    gaps = load_gaps(args.data_dir / "reports" / f"quality_{SOURCE}_{INSTRUMENT}.json", args.end)
    config = ResearchConfig(costs=RESEARCH_COSTS)
    summary, details = availability(bars[Timeframe.H4], bars[Timeframe.D1], gaps, config, args.start, args.end)
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "notice": "disponibilité des données S3 : ni transaction, ni résultat, ni drawdown",
        "provenance": provenance,
        "window": {"init_start": args.init_start, "start": args.start, "end": args.end},
        "params": asdict(S3Params()),
        "inputs": {tf.value: len(b) for tf, b in bars.items()} | {"gaps": len(gaps), "ticks": 0},
        **summary,
        "seconds": round(time.perf_counter() - began, 1),
        "peak_rss_mib": round(_peak_rss_mib(), 1),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(_str(report), ensure_ascii=False, indent=2, default=str))
    if args.details_out:
        with args.details_out.open("w") as out:
            for row in details:
                out.write(json.dumps(_str(row), ensure_ascii=False, default=str) + "\n")
    print(json.dumps(_str({"total": report["total"], "seconds": report["seconds"]}), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
