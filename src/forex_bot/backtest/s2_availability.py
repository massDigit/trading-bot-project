"""S2 data availability, step 3 of the protocol (docs/strategies/S2_PULLBACK.md §9). No tick, no trade.

    uv run forex-s2-availability --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 \
        --out data/reports/backtests/s2_availability_2015_2021.json

The S2 decision rules run on the H1 trigger (reference) over the local candles and the gaps of
the quality report only: no tick is read, so no position, no result and no drawdown exist. Every
expected H1 slot of the window comes from the calendar (weekly closure and probable holidays
excluded), since an absent H1 produces no decision line. Each expected slot is either absent, or
present with a decision line that is not computable (data, sheet §8), evaluable without a signal,
or evaluable with a breakout (not detailed at this step). Configurations abandoned for incomplete
pullback data are counted apart, against the configurations identified, never added to the slots.

Convention of this study only (the S2 performance engine is unchanged): a structural breakout
is counted as soon as it is detected on evaluable data, and its threshold is consumed. If the
required D1 trend still holds and the market is open at the decision, the configuration is
consumed too; otherwise it is kept and the reason is logged. No reward/risk ratio, no size, no
order and no quote: no tick is read, so there is never an open position. The effect of open
positions on the counts of step 4 is unknown.
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
from forex_bot.backtest.s2 import S2Params, Setup
from forex_bot.backtest.s2_engine import S2Backtest
from forex_bot.history.calendar import MarketState, Timeframe, expected_open_hours, market_state
from forex_bot.risk import Side

INCOMPLETE = "DONNÉES_REPLI_INCOMPLÈTES"
ONE_HOUR = timedelta(hours=1)


CONSUMED = "configuration consommée par convention de l'étude (ni rapport gain/risque, ni taille, ni ordre)"


class AvailabilityBacktest(S2Backtest):
    """S2 decisions without ticks; after a detected breakout, only the trend and the market are read."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.abandons: list[tuple[datetime, datetime, str, bool]] = []  # (I, decision, reason, missing data)
        self.consumed: list[tuple[datetime, datetime]] = []  # (I, decision)
        self.kept: list[tuple[datetime, datetime, str]] = []  # (I, decision, reason): only the threshold consumed

    def _after_breakout(self, record: DecisionRecord, decision: datetime, setup: Setup, trend: Side | None) -> None:
        if trend is not setup.side:
            reason = "tendance D1 perdue à la cassure"
        elif market_state(decision) is not MarketState.OPEN:
            reason = f"{setup.side.value} : marché fermé à l'instant de décision"
        else:
            setup.used = True
            setup.history.append(f"{decision.isoformat()} {CONSUMED}")
            self._log(decision, "CONFIGURATION_CONSOMMÉE", CONSUMED)
            record.entry_action = EntryAction.NOT_EVALUATED  # no entry is evaluated at this step
            record.reasons.append(CONSUMED)
            self.consumed.append((setup.identified_utc, decision))
            self.setup = None
            return
        self.kept.append((setup.identified_utc, decision, reason))
        self._refuse(record, decision, reason)  # the configuration stays, its threshold is consumed

    def _abandon(self, decision: datetime, reason: str, *, missing_data: bool = False) -> None:
        if self.setup is not None:
            self.abandons.append((self.setup.identified_utc, decision, reason, missing_data))
        super()._abandon(decision, reason, missing_data=missing_data)


def data_cause(record: DecisionRecord, first_d1: datetime | None) -> str:
    """First reason of a non-computable line, without its instants."""
    reason = record.reasons[0] if record.reasons else "sans motif"
    if reason.startswith("D1 de contexte"):
        if first_d1 is None or record.decision_utc < first_d1:
            return "initialisation : aucune D1 disponible"
        return "D1 de contexte non utilisable"
    if reason.startswith(f"configuration abandonnée : {INCOMPLETE}"):
        return f"configuration abandonnée : {INCOMPLETE}"
    if "ATR H4 indisponible" in reason:
        return "configuration refusée : ATR H4 indisponible à I"
    return reason


def slot_class(record: DecisionRecord) -> str:
    if record.entry_action is EntryAction.NOT_COMPUTABLE:
        return "present_not_evaluable"
    if record.entry_action is EntryAction.NO_SIGNAL:
        return "evaluable_no_signal"
    return "evaluable_breakout"  # a structural breakout detected on evaluable data


def _ratio(part: int, whole: int) -> str | None:
    return None if not whole else f"{part / whole * 100:.3f}"


def availability(
    h1: list[dict[str, Any]],
    h4: list[dict[str, Any]],
    d1: list[dict[str, Any]],
    gaps: list[Any],
    config: ResearchConfig,
    start: datetime,
    end: datetime,
    params: S2Params | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Aggregated counts per year and in total, and the detailed rows (absent slots, data lines, abandons)."""
    engine = AvailabilityBacktest(h1, h4, d1, [], gaps, params or S2Params(), config, start_utc=start, end_utc=end)
    engine.run()
    first_d1 = engine.d1_available[0] if engine.d1_available else None
    by_start = {r.known["trigger_candle"]["start_utc"]: r for r in engine.decisions}
    latency = config.latency

    def empty() -> dict[str, Any]:
        return {
            "expected_slots": 0,
            "absent": 0,
            "present_not_evaluable": 0,
            "evaluable_no_signal": 0,
            "evaluable_breakout": 0,
            "not_evaluable_causes": Counter(),
            "present_outside_calendar": Counter(),
            "configurations_identified": 0,
            "configurations_consumed": 0,
            "configurations_kept_after_breakout": Counter(),
            "configurations_abandoned_incomplete_data": Counter(),
            "configurations_refused_atr": 0,
        }

    years: dict[int, dict[str, Any]] = defaultdict(empty)
    details: list[dict[str, Any]] = []
    expected = [
        s for s in expected_open_hours(start - ONE_HOUR - latency, end) if start <= s + ONE_HOUR + latency < end
    ]
    expected_set = set(expected)
    for slot in expected:
        year = years[(slot + ONE_HOUR + latency).year]
        year["expected_slots"] += 1
        record = by_start.get(slot)
        if record is None:
            year["absent"] += 1
            details.append({"kind": "créneau H1 absent", "slot_start_utc": slot})
            continue
        cls = slot_class(record)
        year[cls] += 1
        if cls == "present_not_evaluable":
            cause = data_cause(record, first_d1)
            year["not_evaluable_causes"][cause] += 1
            details.append(
                {"kind": "ligne non évaluable", "slot_start_utc": slot, "cause": cause, "reasons": record.reasons}
            )
    for slot, record in by_start.items():
        if slot not in expected_set:
            years[record.decision_utc.year]["present_outside_calendar"][slot_class(record)] += 1
            details.append({"kind": "H1 présente hors calendrier prévu", "slot_start_utc": slot})

    for setup in engine.setups:
        years[setup.identified_utc.year]["configurations_identified"] += 1
    for identified, _ in engine.consumed:
        years[identified.year]["configurations_consumed"] += 1
    for identified, _, reason in engine.kept:
        years[identified.year]["configurations_kept_after_breakout"][reason.split(" : ")[-1]] += 1
    for identified, decision, reason, data in engine.abandons:
        if not data:
            continue
        where = reason.split("(", 1)[1].rstrip(")") if "(" in reason else ""
        cause = "bougie inutilisable" if where == "bougie inutilisable" else "créneau attendu absent (H1 ou H4)"
        years[identified.year]["configurations_abandoned_incomplete_data"][cause] += 1
        details.append(
            {
                "kind": "configuration abandonnée",
                "identified_utc": identified,
                "decision_utc": decision,
                "reason": reason,
            }
        )
    for entry in engine.journal:
        if entry.kind == "CONFIGURATION_REFUSÉE" and "ATR H4 indisponible" in entry.detail:
            years[entry.utc.year]["configurations_refused_atr"] += 1

    def finish(counts: dict[str, Any]) -> dict[str, Any]:
        slots = counts["expected_slots"]
        abandoned = sum(counts["configurations_abandoned_incomplete_data"].values())
        identified = counts["configurations_identified"]
        return {
            "h1_slots": {
                "expected": slots,
                "absent": counts["absent"],
                "present_not_evaluable": counts["present_not_evaluable"],
                "evaluable_no_signal": counts["evaluable_no_signal"],
                "evaluable_breakout": counts["evaluable_breakout"],
                "pct_of_expected": {
                    k: _ratio(counts[k], slots)
                    for k in ("absent", "present_not_evaluable", "evaluable_no_signal", "evaluable_breakout")
                },
                "not_evaluable_causes": dict(counts["not_evaluable_causes"].most_common()),
                "present_outside_calendar": dict(counts["present_outside_calendar"]),
            },
            "configurations": {
                "identified": identified,
                "consumed_by_convention": counts["configurations_consumed"],
                "kept_after_structural_refusal": dict(counts["configurations_kept_after_breakout"]),
                "abandoned_incomplete_data": abandoned,
                "pct_of_identified": _ratio(abandoned, identified),
                "abandoned_incomplete_data_by_cause": dict(counts["configurations_abandoned_incomplete_data"]),
                "refused_at_identification_atr_unavailable": counts["configurations_refused_atr"],
            },
        }

    total = empty()
    for counts in years.values():
        for key, value in counts.items():
            total[key] += value
    summary = {
        "by_year": {year: finish(years[year]) for year in sorted(years)},
        "total": finish(total),
        "decision_lines": len(engine.decisions),
    }
    return summary, details


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forex-s2-availability", description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--init-start", type=_date, required=True)
    parser.add_argument("--start", type=_date, required=True)
    parser.add_argument("--end", type=_date, required=True)
    parser.add_argument("--out", type=Path, required=True, help="rapport JSON agrégé (hors Git, sous data/)")
    parser.add_argument("--details-out", type=Path, help="lignes détaillées JSONL (hors Git, sous data/)")
    args = parser.parse_args(argv)
    if not args.init_start <= args.start < args.end:
        parser.error("dates attendues : init-start <= start < end")

    provenance = _provenance(argv, prog="forex-s2-availability")
    began = time.perf_counter()
    bars = {
        tf: load_bars(args.data_dir, SOURCE, INSTRUMENT, tf, args.init_start, args.end)
        for tf in (Timeframe.H1, Timeframe.H4, Timeframe.D1)
    }
    gaps = load_gaps(args.data_dir / "reports" / f"quality_{SOURCE}_{INSTRUMENT}.json", args.end)
    config = ResearchConfig(costs=RESEARCH_COSTS)
    summary, details = availability(
        bars[Timeframe.H1], bars[Timeframe.H4], bars[Timeframe.D1], gaps, config, args.start, args.end
    )
    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "notice": "disponibilité des données S2 : ni transaction, ni résultat, ni drawdown",
        "provenance": provenance,
        "window": {"init_start": args.init_start, "start": args.start, "end": args.end},
        "trigger": Timeframe.H1.value,
        "params": asdict(S2Params()),
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
