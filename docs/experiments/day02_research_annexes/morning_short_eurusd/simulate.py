"""Morning short EUR/USD (PROTOCOL.md), tick simulation with the conventions of the validated DAY_02 tick
replayer. Usage: uv run --with pyarrow --with pandas python -I simulate.py 2015 2019"""
import json
import math
import pickle
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow.parquet as pq

DIR = Path(__file__).resolve().parent
ROOT = DIR.parents[3]
LON, UTC = ZoneInfo("Europe/London"), ZoneInfo("UTC")
PIP, UNITS, SLIP, PREM, FEE = 1e-4, 10_000, 0.5, 1.2, 0.005
INDEX = pickle.load(open(ROOT / "data/reports/backtests/day02_guides/tick_index.pkl", "rb"))
y0, y1 = int(sys.argv[1]), int(sys.argv[2])
assert y1 <= 2021


def ticks(start, end):
    out = []
    for s, e, p in INDEX:
        if s < end and start < e:
            t = pq.read_table(p, columns=["ts_utc", "raw_row", "bid", "ask"],
                              filters=[("ts_utc", ">=", start.to_pydatetime()), ("ts_utc", "<", end.to_pydatetime())])
            t = t.sort_by([("ts_utc", "ascending"), ("raw_row", "ascending")])
            for ts, b, a in zip(t["ts_utc"].to_pylist(), t["bid"].to_pylist(), t["ask"].to_pylist()):
                b, a = float(b), float(a)
                if b > 0 and a > 0 and b <= a:
                    out.append((pd.Timestamp(ts), b, a))
    out.sort(key=lambda x: x[0])
    return out


def at(d, hh, mm=0):
    return pd.Timestamp(datetime.combine(d, time(hh, mm), tzinfo=LON)).tz_convert(UTC)


def trade_day(d, stops, equity):
    t0, t5, t13 = at(d, 9), at(d, 9, 5), at(d, 13)
    tk = ticks(t0, t13 + pd.Timedelta(minutes=30))
    entry_tick = next((x for x in tk if x[0] < t5), None)
    if entry_tick is None:
        return {}
    ts_e, b_e, a_e = entry_tick
    exit_tick = next((x for x in tk if x[0] >= t13), None)
    res = {}
    for s in stops:
        entry = b_e
        stop = entry + s * PIP
        loss_per_contract = (s * PIP * UNITS + SLIP * PIP * UNITS + PREM) / b_e * (1 + FEE)
        budget = 0.0025 * equity[s]
        size = math.floor(budget / loss_per_contract / 0.1 + 1e-9) * 0.1
        if size < 0.1:
            res[s] = {"outcome": "SIZE_REFUSED"}
            continue
        out = None
        for ts, b, a in tk:
            if ts <= ts_e:
                continue
            if a >= stop:
                out = ("STOP", stop, ts, b, a)
                break
            if ts >= t13:
                out = ("SORTIE_13H", a, ts, b, a)
                break
        if out is None:
            res[s] = {"outcome": "NO_EXIT"}
            continue
        reason, px, ts_x, b, a = out
        u = size * UNITS
        stopped = reason == "STOP"
        gross_q = (entry - px) * u
        costs_q = SLIP * PIP * u + (PREM * size if stopped else 0.0)
        nq = gross_q - costs_q
        g = nq / (b if nq < 0 else a)
        net = g - abs(g) * FEE
        gross_eur = gross_q / (b if gross_q < 0 else a)
        est = loss_per_contract * size
        res[s] = {"outcome": reason, "date": d.isoformat(), "entry_utc": str(ts_e), "exit_utc": str(ts_x), "entry": entry,
                  "exit": px, "size": round(size, 1), "gross_eur": gross_eur, "net_eur": net, "R": net / est,
                  "slip_eur": SLIP * PIP * u / a * (1 + FEE), "prem_eur": (PREM * size / a * (1 + FEE)) if stopped else 0.0,
                  "pips": (entry - px) / PIP}
        equity[s] += net
    return res


stops = (20, 30)
equity = {s: 2000.0 for s in stops}
trades = {s: [] for s in stops}
skipped = {s: 0 for s in stops}
d = date(y0, 1, 1)
while d <= date(y1, 12, 31):
    if d.weekday() < 5:
        r = trade_day(d, stops, equity)
        for s in stops:
            if s in r and "net_eur" in r[s]:
                trades[s].append(r[s])
            else:
                skipped[s] += 1
    d += timedelta(days=1)

summary = {}
for s in stops:
    t = pd.DataFrame(trades[s])
    t["year"] = t.date.str[:4]
    cum = t.net_eur.cumsum() + 2000
    dd = ((cum.cummax() - cum) / cum.cummax()).max() * 100
    losing = (t.net_eur < 0).astype(int)
    streak = losing.groupby((losing != losing.shift()).cumsum()).cumsum().max()
    gains, losses = t.net_eur[t.net_eur > 0].sum(), -t.net_eur[t.net_eur < 0].sum()
    summary[f"S{s}"] = {
        "n": len(t), "jours_sans_transaction": skipped[s], "stop_%": round(100 * (t.outcome == "STOP").mean(), 1),
        "pips_moyens": round(t.pips.mean(), 2), "brut_eur": round(t.gross_eur.sum(), 2),
        "net_eur": round(t.net_eur.sum(), 2), "couts_eur": round(t.gross_eur.sum() - t.net_eur.sum(), 2),
        "R_net": round(t.R.mean(), 4), "se": round(t.R.std() / math.sqrt(len(t)), 4), "PF": round(gains / losses, 3),
        "par_annee_R": {y: round(g.R.mean(), 3) for y, g in t.groupby("year")},
        "par_annee_net": {y: round(g.net_eur.sum(), 2) for y, g in t.groupby("year")},
        "pire_serie_pertes": int(streak), "dd_clos_%": round(dd, 2),
        "net_glissement_x2": round(t.net_eur.sum() - t.slip_eur.sum(), 2),
        "net_prime_x2": round(t.net_eur.sum() - t.prem_eur.sum(), 2),
        "taille_mediane": float(t["size"].median()),
    }
    t.to_csv(DIR / f"trades_S{s}_{y0}_{y1}.csv", index=False)
(DIR / f"summary_{y0}_{y1}.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary, indent=1))
