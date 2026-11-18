"""Bilan of the DAY_02 frequency lot (docs/experiments/DAY02_FREQUENCY_CAMPAIGN.md §6): reads the
performance reports only; nothing is re-simulated. Usage: uv run --with pandas python bilan.py [names...]
"""
import json
import math
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

DIR = Path(__file__).resolve().parent
SESSIONS = 1816  # admissible sessions 2015-2021 (availability study, C1 anchor)
FIRST_WEEK, LAST_DAY = date(2015, 1, 5), date(2021, 12, 31)


def load(name):
    d = json.loads((DIR / f"perf_{name}_m5_a.json").read_text())
    if "result" not in d:
        return None, d
    return d["result"], d


def r_of(t):
    return float(t["net_account"]) / float(t["estimated_stop_loss_at_decision"])


def stats(trades):
    n = len(trades)
    net = sum(float(t["net_account"]) for t in trades)
    rs = [r_of(t) for t in trades]
    mean = sum(rs) / n if n else float("nan")
    sd = math.sqrt(sum((x - mean) ** 2 for x in rs) / (n - 1)) if n > 1 else float("nan")
    gains = sum(float(t["net_account"]) for t in trades if float(t["net_account"]) > 0)
    losses = -sum(float(t["net_account"]) for t in trades if float(t["net_account"]) < 0)
    return {"n": n, "net": net, "R": mean, "se": sd / math.sqrt(n) if n > 1 else float("nan"),
            "PF": gains / losses if losses else float("inf")}


def cost_extra(t, slip=False, premium=False):
    """EUR added by doubling the slippage line (0.5 pip) or the guaranteed-stop premium (1.2 USD/contract)."""
    size = float(t["size"])
    usd = (0.5 * size if slip else 0.0)
    if premium and "STOP" in (t["exit_reason"] or "") and "prime de stop garanti" in (t["costs_quote"] or {}):
        usd += 1.2 * size
    return usd * float(t["conversion_rate"]) * 1.005


def frequency(trades):
    days = sorted({datetime.fromisoformat(t["decided_utc"]).date() for t in trades})
    weeks = {d - timedelta(days=d.weekday()) for d in days}
    all_weeks = (LAST_DAY - FIRST_WEEK).days // 7 + 1
    gaps = [(b - a).days for a, b in zip([FIRST_WEEK, *days], [*days, LAST_DAY])]
    per_year = defaultdict(int)
    for t in trades:
        per_year[t["decided_utc"][:4]] += 1
    return {"per_session": len(trades) / SESSIONS, "per_year": dict(sorted(per_year.items())),
            "active_weeks": len(weeks) / all_weeks, "longest_gap_days": max(gaps), "active_sessions": len(days)}


def key(t):
    return (t["decided_utc"], t["side"])


def main(names):
    rows = {}
    late, _ = load("LATE")
    late_by = {key(t): t for t in late["trades"]}
    for name in names:
        res, raw = load(name)
        if res is None:
            print(f"{name}: pas de résultat ({raw.get('anomaly')})")
            continue
        tr = res["trades"]
        p1 = [t for t in tr if t["decided_utc"][:4] <= "2018"]
        p2 = [t for t in tr if t["decided_utc"][:4] >= "2019"]
        tot = res["closed_trade_totals"]
        s = stats(tr)
        mine = {key(t): t for t in tr}
        common = set(mine) & set(late_by)
        added, removed = set(mine) - set(late_by), set(late_by) - set(mine)
        rows[name] = {
            **s, "gross": float(tot["gross_eur"]), "costs": float(tot["costs_eur"]),
            "dd_eur": float(res["tick_drawdown_eur"]["max_drawdown_eur"]),
            "dd_rel": round(float(res["relative_drawdown"]["max_pct"]), 2),
            "p1": stats(p1), "p2": stats(p2), "freq": frequency(tr),
            "slip2": s["net"] - sum(cost_extra(t, slip=True) for t in tr),
            "prem2": s["net"] - sum(cost_extra(t, premium=True) for t in tr),
            "both2": s["net"] - sum(cost_extra(t, slip=True, premium=True) for t in tr),
            "exits": tot["exit_reasons"],
            "vs_late": {
                "common": len(common),
                "common_net_late": sum(float(late_by[k]["net_account"]) for k in common),
                "common_net_here": sum(float(mine[k]["net_account"]) for k in common),
                "added": len(added), "added_net": sum(float(mine[k]["net_account"]) for k in added),
                "removed": len(removed), "removed_net_late": sum(float(late_by[k]["net_account"]) for k in removed),
            },
            "funnel": {k: res["funnel"][k] for k in ("configurations", "flags_formed", "confirmed_exits", "at_d", "entry_outcomes")},
        }
    (DIR / "bilan.json").write_text(json.dumps(rows, indent=1, default=str))
    for name, r in rows.items():
        f = r["freq"]
        print(f"{name:6s} n {r['n']:4d} /séance {f['per_session']:.3f} sem.act {100*f['active_weeks']:.0f}% max sans {f['longest_gap_days']}j | "
              f"brut {r['gross']:7.2f} coûts {r['costs']:6.2f} net {r['net']:7.2f} R {r['R']:+.3f}±{r['se']:.3f} PF {r['PF']:.2f} "
              f"DD {r['dd_rel']} | 15-18 {r['p1']['net']:7.2f} ({r['p1']['R']:+.3f}) 19-21 {r['p2']['net']:7.2f} ({r['p2']['R']:+.3f}) | "
              f"gliss×2 {r['slip2']:7.2f} prime×2 {r['prem2']:7.2f} les deux {r['both2']:7.2f}")
        print("        vs LATE:", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r["vs_late"].items()}, "| sorties", r["exits"])


if __name__ == "__main__":
    main(sys.argv[1:] or ["LATE", "G1A", "G5B", "G1A5B", "E3", "F2R", "RSC", "M5S"])
