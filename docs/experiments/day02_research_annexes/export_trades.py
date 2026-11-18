"""Export transaction par transaction des passages DAY_02 et des ventes de matinée, sans prix de marché
(dates, sens, taille, motif de sortie, résultats). Lancer depuis la racine du dépôt :
uv run python docs/experiments/day02_research_annexes/export_trades.py"""
import csv
import json
from pathlib import Path

ROOT = Path(".")
B = ROOT / "data/reports/backtests"
R = ROOT / "data/reports/research"
OUT = Path(__file__).resolve().parent / "trades"
DAY02 = {
    "REF": B / "day02_late_exit/perf_REF_m5_a.json",
    **{v: B / f"day02_campaign/perf_{v}_m5_a.json" for v in ("H1", "H2", "H3", "H1H2", "H1H3", "H2H3", "H1H2H3")},
    "LATE": B / "day02_frequency/perf_LATE_m5_a.json",
    **{v: B / f"day02_partial_exits/perf_{v}_m5_a.json" for v in ("PROT", "PART", "FULL")},
    **{v: B / f"day02_frequency/perf_{v}_m5_a.json"
       for v in ("G1A", "G5B", "G1A5B", "E3", "F2R", "RSC", "M5S", "SMTF", "SMTT")},
}
COLS = ["decided_utc", "entry_utc", "exit_utc", "side", "size", "exit_reason", "net_eur", "risk_eur", "R"]
MS_COLS = ["date", "outcome", "entry_utc", "exit_utc", "size", "pips", "gross_eur", "net_eur", "R", "slip_eur", "prem_eur"]
MORNING = {
    "MS_EURUSD_S20": [R / "morning_short/trades_S20_2015_2019.csv", R / "morning_short/trades_S20_2020_2021.csv"],
    "MS_EURUSD_S30": [R / "morning_short/trades_S30_2015_2019.csv", R / "morning_short/trades_S30_2020_2021.csv"],
    "MS_GBPUSD_S20": [R / "morning_short_gbpusd/trades_S20_2015_2021.csv"],
    "MS_GBPUSD_S30": [R / "morning_short_gbpusd/trades_S30_2015_2021.csv"],
}

OUT.mkdir(exist_ok=True)
for name, path in DAY02.items():
    trades = json.loads(path.read_text())["result"]["trades"]
    with open(OUT / f"day02_{name}.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLS)
        for t in trades:
            risk = float(t["estimated_stop_loss_at_decision"])
            net = float(t["net_account"])
            w.writerow([t["decided_utc"], t["entry_utc"], t["exit_utc"], t["side"], t["size"], t["exit_reason"],
                        round(net, 6), round(risk, 6), round(net / risk, 6)])
    print(name, len(trades))
for name, paths in MORNING.items():
    rows = [r for p in paths for r in csv.DictReader(open(p))]
    with open(OUT / f"{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MS_COLS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(float(r[k]), 6) if k in MS_COLS[5:] else r[k]) for k in MS_COLS})
    print(name, len(rows))
