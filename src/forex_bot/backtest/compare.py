"""Compare two S1 runs over the same window (reference vs variant). Reads reports only; runs nothing.

    uv run forex-backtest-compare --reference data/reports/backtests/s1_ref_2015_2021_h0 \
        --variant data/reports/backtests/s1_gran001_2015_2021_h0 --out data/reports/backtests/s1_gran001_vs_ref

Each run is `<prefix>.json` (report) and `<prefix>_decisions.jsonl` (one line per H4 decision).
Answers the questions of docs/experiments/S1_GRANULARITY_001.md §4: fate of the reference's size
refusals in the variant, origin of the net difference (trades matched by decision instant and
side), and the effect for the account.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

SIZE_REFUSAL = "taille minimale"


def load_run(prefix: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    report = json.loads(prefix.with_suffix(".json").read_text())
    decisions: dict[str, dict[str, Any]] = {}
    with prefix.with_name(prefix.name + "_decisions.jsonl").open() as lines:
        for line in lines:
            record = json.loads(line)
            decisions[record["decision_utc"]] = record
    return report, decisions


def _trades(report: dict[str, Any]) -> list[dict[str, Any]]:
    result = report["result"]
    return [*result["trades"], *([result["open_trade_at_end"]] if result["open_trade_at_end"] else [])]


def _net(trade: dict[str, Any]) -> Decimal:
    return Decimal(trade["net_account"]) if trade["net_account"] is not None else Decimal(0)


def fate_of_size_refusals(
    reference: dict[str, dict[str, Any]], variant: dict[str, dict[str, Any]], variant_report: dict[str, Any]
) -> dict[str, Any]:
    """What the variant did at each decision instant where the reference refused the size."""
    executed = {t["decided_utc"]: t for t in _trades(variant_report)}
    fates: Counter[str] = Counter()
    still_refused: Counter[str] = Counter()
    executed_net = Decimal(0)
    executed_closed = 0
    for instant, record in reference.items():
        if not any(SIZE_REFUSAL in reason for reason in record["reasons"]):
            continue
        other = variant[instant]
        action = other["entry_action"]
        if action == "ENTRÉE_DÉCIDÉE":
            trade = executed.get(instant)
            if trade is None:
                fates["entrée décidée, non exécutée"] += 1
            else:
                fates["exécuté"] += 1
                if trade["net_account"] is not None:
                    executed_closed += 1
                    executed_net += _net(trade)
        elif action == "SIGNAL_REFUSÉ":
            fates["toujours refusé"] += 1
            still_refused.update(other["reasons"])
        elif action == "NON_ÉVALUÉE":
            fates["non évalué : position déjà ouverte"] += 1
        else:
            fates[f"trajectoire modifiée : {action}"] += 1
    return {
        "reference_size_refusals": sum(fates.values()),
        "fates": dict(fates.most_common()),
        "still_refused_reasons": dict(still_refused.most_common()),
        "executed_closed": executed_closed,
        "executed_net_eur": str(executed_net),
    }


def match_trades(reference_report: dict[str, Any], variant_report: dict[str, Any]) -> dict[str, Any]:
    """Trades matched by (decision instant, side): common ones, and those of one trajectory only."""

    def key(trade: dict[str, Any]) -> tuple[str, str]:
        return trade["decided_utc"], trade["side"]

    ref = {key(t): t for t in _trades(reference_report)}
    var = {key(t): t for t in _trades(variant_report)}
    common = sorted(ref.keys() & var.keys())
    rows = []
    for k in common:
        a, b = ref[k], var[k]
        rows.append(
            {
                "decided_utc": k[0],
                "side": k[1],
                "size_reference": a["size"],
                "size_variant": b["size"],
                "net_reference": str(_net(a)),
                "net_variant": str(_net(b)),
                "difference": str(_net(b) - _net(a)),
                "same_exit": (a["exit_utc"], a["exit_reason"]) == (b["exit_utc"], b["exit_reason"]),
            }
        )
    only_ref = [ref[k] for k in sorted(ref.keys() - var.keys())]
    only_var = [var[k] for k in sorted(var.keys() - ref.keys())]
    common_delta = sum((Decimal(r["difference"]) for r in rows), Decimal(0))
    only_ref_net = sum((_net(t) for t in only_ref), Decimal(0))
    only_var_net = sum((_net(t) for t in only_var), Decimal(0))
    return {
        "common": len(rows),
        "common_same_size": sum(1 for r in rows if Decimal(r["size_reference"]) == Decimal(r["size_variant"])),
        "common_same_exit": sum(1 for r in rows if r["same_exit"]),
        "common_net_difference_eur": str(common_delta),
        "only_reference": len(only_ref),
        "only_reference_net_eur": str(only_ref_net),
        "only_variant": len(only_var),
        "only_variant_net_eur": str(only_var_net),
        "net_difference_eur": str(common_delta + only_var_net - only_ref_net),
        "common_trades": rows,
        "only_reference_trades": [_brief(t) for t in only_ref],
        "only_variant_trades": [_brief(t) for t in only_var],
    }


def _brief(trade: dict[str, Any]) -> dict[str, Any]:
    keys = ("decided_utc", "side", "size", "entry_price", "exit_utc", "exit_reason", "net_account", "risk_overrun")
    return {k: trade[k] for k in keys}


def account_effect(reference_report: dict[str, Any], variant_report: dict[str, Any]) -> dict[str, Any]:
    def view(report: dict[str, Any]) -> dict[str, Any]:
        result = report["result"]
        totals = result["closed_trade_totals"]
        return {
            "trades_closed": totals["closed"],
            "winners": totals["winners"],
            "entries": result["entries"],
            "gross_eur": totals["gross_eur"],
            "costs_eur": totals["costs_eur"],
            "net_eur": totals["net_eur"],
            "balance_eur": result["balance_eur"],
            "equity_eur": result["equity_eur"],
            "open_trade_at_end": result["open_trade_at_end"] is not None,
            "tick_drawdown_eur": result["tick_drawdown"]["max_drawdown_eur"],
            "tick_drawdown_from_to": [
                result["tick_drawdown"]["drawdown_peak_utc"],
                result["tick_drawdown"]["trough_utc"],
            ],
            "risk_overruns": len(result["risk_overruns"]),
            "unobservable_crossings_h0": result["unobservable_crossings_h0"],
            "stop_beyond_at_execution": result["stop_beyond_at_execution"],
            "net_by_year": {y: v["closed_trades"]["net_eur"] for y, v in report["by_year"].items()},
            "tick_drawdown_by_year": {y: v["tick_drawdown"]["max_drawdown_eur"] for y, v in report["by_year"].items()},
        }

    return {"reference": view(reference_report), "variant": view(variant_report)}


def compare(reference_prefix: Path, variant_prefix: Path) -> dict[str, Any]:
    ref_report, ref_decisions = load_run(reference_prefix)
    var_report, var_decisions = load_run(variant_prefix)
    if ref_decisions.keys() != var_decisions.keys():
        raise ValueError("les deux passages n'ont pas les mêmes instants de décision")
    return {
        "reference": str(reference_prefix),
        "variant": str(variant_prefix),
        "decisions": len(ref_decisions),
        "fate_of_size_refusals": fate_of_size_refusals(ref_decisions, var_decisions, var_report),
        "trade_matching": match_trades(ref_report, var_report),
        "account_effect": account_effect(ref_report, var_report),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forex-backtest-compare", description=__doc__.splitlines()[0])
    parser.add_argument("--reference", type=Path, required=True, help="préfixe du passage de référence")
    parser.add_argument("--variant", type=Path, required=True, help="préfixe du passage variante")
    parser.add_argument("--out", type=Path, help="préfixe du fichier JSON de comparaison (hors Git)")
    args = parser.parse_args(argv)
    text = json.dumps(compare(args.reference, args.variant), ensure_ascii=False, indent=2)
    if args.out:
        args.out.with_suffix(".json").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
