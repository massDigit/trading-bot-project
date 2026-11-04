"""S2 descriptive study: volatility at the decision and target / stop distances. No replay, no order.

    uv run forex-s2-volatility --journal data/reports/backtests/s2_ref_2015_2021_h1_a_decisions.jsonl \
        --out data/reports/backtests/s2_volatility_2015_2021.json \
        --details-out data/reports/backtests/s2_volatility_2015_2021_details.jsonl

Method frozen in docs/experiments/S2_VOLATILITY_2015_2021.md before any computation. Every detected
breakout of an existing S2 decision journal is read; nothing is selected by its outcome. The ATR
available at the decision (volatility) is kept apart from the ATR frozen at the identification of the
configuration. The stop and the reward/risk ratio of a breakout the engine stopped evaluating before
them (D1 trend lost) are reconstructed with the engine's own functions and always labelled as such;
the reconstruction must first find again every value the engine evaluated.
"""

from __future__ import annotations

import argparse
import bisect
import json
import statistics
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from forex_bot.backtest.data import load_bars, load_gaps
from forex_bot.backtest.engine import ResearchConfig, StopType
from forex_bot.backtest.explore import INSTRUMENT, RESEARCH_COSTS, SOURCE, _json, _provenance, _str
from forex_bot.backtest.feed import Tick
from forex_bot.backtest.s2 import S2Params
from forex_bot.backtest.s2_engine import S2Backtest
from forex_bot.history.calendar import Timeframe
from forex_bot.risk import Side

PIP = Decimal("0.0001")
EVALUATED, RECONSTRUCTED = "évaluée", "reconstruite"
GROUPS = ("faible", "moyenne", "élevée")


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def measure(engine: S2Backtest, line: dict[str, Any]) -> dict[str, Any]:
    """Distances, ratios and volatility of one breakout line, from the journal and the bars only."""
    decision = datetime.fromisoformat(line["decision_utc"])
    known, signal = line["known"], line["signal"]
    setup, quote = known["setup"], known["quote"]
    side = Side(signal["side"])
    bid, ask = _d(quote["bid"]), _d(quote["ask"])
    target, frozen_atr = _d(setup["E"]), _d(setup["atr"])
    # The pullback starts at the end of the H4 candle E (sheet S2 §4.3).
    e_start = datetime.fromisoformat(setup["E_start_utc"])
    e_index = bisect.bisect_left(engine.starts[Timeframe.H4], e_start)
    if engine.h4[e_index]["start_utc"] != e_start:
        raise ValueError(f"bougie E introuvable : {e_start.isoformat()}")
    first = bisect.bisect_left(engine.starts[Timeframe.H1], engine.h4[e_index]["end_utc"])
    bars = engine.h1[first : engine._last_available(Timeframe.H1, decision) + 1]
    margin = engine.s2.stop_atr * frozen_atr
    rebuilt_stop = (
        min(b["bid_low"] for b in bars) - margin if side is Side.LONG else max(b["ask_high"] for b in bars) + margin
    )
    engine._last_tick = Tick(datetime.fromisoformat(quote["ts_utc"]), bid, ask)
    rebuilt_ratio = engine._reward_risk(side, rebuilt_stop, target)
    if isinstance(rebuilt_ratio, str):
        raise ValueError(f"{decision.isoformat()} : {rebuilt_ratio}")
    evaluated = "reward_risk" in signal
    stop = _d(signal["stop"]) if "stop" in signal else rebuilt_stop
    ratio = _d(signal["reward_risk"]) if evaluated else rebuilt_ratio
    h4 = engine._last_available(Timeframe.H4, decision)
    atr = engine.atr.at(h4, engine._states(decision)[Timeframe.H4]) if h4 >= 0 else None
    mid = (bid + ask) / 2
    long = side is Side.LONG
    to_target = (target - ask if long else bid - target) / PIP
    to_stop = (ask - stop if long else stop - bid) / PIP
    reasons = line["reasons"]
    return {
        "decision_utc": decision,
        "side": side.value,
        "entry_action": line["entry_action"],
        "reason": reasons[-1] if reasons else "",
        "origin": EVALUATED if evaluated else RECONSTRUCTED,
        "atr_at_decision_pct": None if atr is None else atr / mid * 100,
        "frozen_atr_pct": frozen_atr / mid * 100,
        "spread_pips": (ask - bid) / PIP,
        "to_target_pips": to_target,
        "to_stop_pips": to_stop,
        "distance_ratio": to_target / to_stop,
        "reward_risk": ratio,
        "check": None
        if not evaluated
        else {"stop_found_again": rebuilt_stop == stop, "ratio_found_again": rebuilt_ratio == ratio},
    }


def groups(rows: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Three equal groups by rank of the volatility at the decision; the remainder goes high, then low."""
    ranked = sorted(rows, key=lambda r: (r["atr_at_decision_pct"], r["decision_utc"]))
    size, extra = divmod(len(ranked), 3)
    sizes = [size + (extra == 2), size, size + (extra >= 1)]
    return {
        GROUPS[0]: ranked[: sizes[0]],
        GROUPS[1]: ranked[sizes[0] : sizes[0] + sizes[1]],
        GROUPS[2]: ranked[sizes[0] + sizes[1] :],
    }


def describe(values: Iterable[Decimal]) -> dict[str, Any]:
    data = sorted(values)
    if not data:
        return {"n": 0}
    if len(data) < 2:
        return {"n": 1, "median": data[0]}
    q1, _, q3 = statistics.quantiles(data, n=4, method="inclusive")
    return {"n": len(data), "median": statistics.median(data), "q1": q1, "q3": q3}


def summary(members: Sequence[dict[str, Any]]) -> dict[str, Any]:
    def of(key: str, origin: str | None = None) -> dict[str, Any]:
        return describe(r[key] for r in members if origin is None or r["origin"] == origin)

    vol = [r["atr_at_decision_pct"] for r in members]
    return {
        "breakouts": len(members),
        "atr_at_decision_pct": {"min": min(vol), "max": max(vol)} if vol else None,
        "frozen_atr_pct": of("frozen_atr_pct"),
        "outcomes": dict(Counter(_outcome(r) for r in members).most_common()),
        "spread_pips": of("spread_pips"),
        "to_target_pips": of("to_target_pips"),
        "to_stop_pips": of("to_stop_pips"),
        "distance_ratio": of("distance_ratio"),
        "reward_risk_evaluated": of("reward_risk", EVALUATED),
        "reward_risk_reconstructed": of("reward_risk", RECONSTRUCTED),
        "reward_risk_all": of("reward_risk") | {"reconstructed": sum(r["origin"] == RECONSTRUCTED for r in members)},
    }


def _outcome(row: dict[str, Any]) -> str:
    if row["entry_action"] == "ENTRÉE_DÉCIDÉE":
        return "entrée décidée"
    reason = row["reason"]
    if reason.startswith("tendance D1 perdue"):
        return "refus : tendance D1 perdue"
    if reason.startswith("cible trop proche"):
        return "refus : rapport gain/risque < R_min"
    if reason.startswith("taille minimale"):
        return "refus : taille minimale"
    return f"{row['entry_action']} : {reason}"


def reading(by_group: dict[str, dict[str, Any]]) -> str:
    """The reading rule of the method (§6), applied as written."""
    ratio = [by_group[g]["distance_ratio"] for g in GROUPS]
    medians = [r["median"] for r in ratio]
    low, high = ratio[0], ratio[2]
    outside = high["median"] > low["q3"] or high["median"] < low["q1"]
    if medians[0] < medians[1] < medians[2] and outside:
        return "la cible était relativement plus éloignée"
    if medians[0] > medians[1] > medians[2] and outside:
        return "le stop était surtout plus large"
    return "les observations ne permettent pas de trancher"


def study(engine: S2Backtest, lines: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = [measure(engine, line) for line in lines if line["signal"] is not None]
    checks = [r["check"] for r in rows if r["check"] is not None]
    mismatches = [
        r["decision_utc"]
        for r in rows
        if r["check"] is not None and not (r["check"]["stop_found_again"] and r["check"]["ratio_found_again"])
    ]
    usable = [r for r in rows if r["atr_at_decision_pct"] is not None]
    by_group = {name: summary(members) for name, members in groups(usable).items()}
    result = {
        "breakouts": len(rows),
        "origins": dict(Counter(r["origin"] for r in rows)),
        "reconstruction_check": {"evaluated": len(checks), "mismatches": mismatches},
        "without_volatility_at_decision": len(rows) - len(usable),
        "groups": by_group,
        "all": summary(usable),
        "reading": reading(by_group) if len(usable) >= 3 else None,
    }
    if mismatches:  # the method: no reconstructed value is published if the check fails
        result["groups"] = result["all"] = result["reading"] = None
    return result, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forex-s2-volatility", description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--journal", type=Path, required=True, help="journal JSONL d'un passage S2 H1")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--details-out", type=Path, required=True)
    args = parser.parse_args(argv)
    provenance = _provenance(argv, prog="forex-s2-volatility")
    began = time.perf_counter()
    start, end = (
        datetime.fromisoformat("2015-01-01T00:00:00+00:00"),
        datetime.fromisoformat("2022-01-01T00:00:00+00:00"),
    )
    bars = {
        tf: load_bars(args.data_dir, SOURCE, INSTRUMENT, tf, start, end)
        for tf in (Timeframe.H1, Timeframe.H4, Timeframe.D1)
    }
    gaps = load_gaps(args.data_dir / "reports" / f"quality_{SOURCE}_{INSTRUMENT}.json", end)
    engine = S2Backtest(
        bars[Timeframe.H1],
        bars[Timeframe.H4],
        bars[Timeframe.D1],
        [],
        gaps,
        S2Params(trigger=Timeframe.H1),
        ResearchConfig(costs=RESEARCH_COSTS, stop_type=StopType.GUARANTEED),
    )  # never run: its functions only (states, ATR, stop margin, reward/risk)
    with args.journal.open() as journal:
        result, rows = study(engine, (json.loads(line) for line in journal))
    full = {
        "notice": "étude descriptive EUR/USD : ni backtest de performance, ni rentabilité, ni comparaison de paires",
        "provenance": provenance,
        "journal": str(args.journal),
        "result": result,
        "seconds": round(time.perf_counter() - began, 1),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(_str(_json(full)), ensure_ascii=False, indent=2, default=str))
    with args.details_out.open("w") as out:
        for row in rows:
            out.write(json.dumps(_str(_json(row)), ensure_ascii=False, default=str) + "\n")
    print(f"rapport écrit : {args.out} ({full['seconds']} s) ; lecture : {result['reading']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
