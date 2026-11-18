"""Morning short GBP/USD (PROTOCOL.md): same rule and conventions as ../morning_short/simulate.py, USD -> EUR
through the EUR/USD quote. Usage: uv run --with pyarrow --with pandas python -I simulate.py"""
import json
import math
import pickle
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow.parquet as pq

DIR = Path(__file__).resolve().parent
ROOT = DIR.parents[3]
LON, UTC = ZoneInfo("Europe/London"), ZoneInfo("UTC")
PIP, UNITS, SLIP, PREM, FEE = 1e-4, 10_000, 0.5, 1.2, 0.005
EUR_INDEX = pickle.load(open(ROOT / "data/reports/backtests/day02_guides/tick_index.pkl", "rb"))
END = pd.Timestamp("2022-01-01", tz="UTC")


def build_index(directory):
    out = []
    for path in sorted(directory.glob("*.parquet")):
        t = pq.read_table(path, columns=["ts_utc"])
        if t.num_rows:
            lo, hi = pd.Timestamp(t["ts_utc"][0].as_py()), pd.Timestamp(max(t["ts_utc"].to_pylist()))
            lo = min(lo, pd.Timestamp(min(t["ts_utc"].to_pylist())))
            out.append((lo, hi + pd.Timedelta(microseconds=1), str(path)))
    assert all(e <= END for _, e, _ in out), "GBP/USD au-delà de 2021"
    return out


GBP_INDEX = build_index(ROOT / "data/normalized/ticks/dukascopy/GBPUSD")


def ticks(index, start, end):
    out = []
    for s, e, p in index:
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


def eur_at(eur, ts):
    """Last EUR/USD tick at or before `ts`."""
    last = None
    for x in eur:
        if x[0] > ts:
            break
        last = x
    return last


def trade_day(d, stops, equity):
    t0, t5, t13 = at(d, 9), at(d, 9, 5), at(d, 13)
    tk = ticks(GBP_INDEX, t0, t13 + pd.Timedelta(minutes=30))
    eur = ticks(EUR_INDEX, t0 - pd.Timedelta(minutes=30), t13 + pd.Timedelta(minutes=30))
    entry_tick = next((x for x in tk if x[0] < t5), None)
    if entry_tick is None:
        return {}
    ts_e, b_e, a_e = entry_tick
    eur_e = eur_at(eur, ts_e)
    if eur_e is None:
        return {s: {"outcome": "NO_EURUSD"} for s in stops}
    res = {}
    for s in stops:
        entry = b_e
        stop = entry + s * PIP
        loss_per_contract = (s * PIP * UNITS + SLIP * PIP * UNITS + PREM) / eur_e[1] * (1 + FEE)
        size = math.floor(0.0025 * equity[s] / loss_per_contract / 0.1 + 1e-9) * 0.1
        if size < 0.1:
            res[s] = {"outcome": "SIZE_REFUSED"}
            continue
        out = None
        for ts, b, a in tk:
            if ts <= ts_e:
                continue
            if a >= stop:
                out = ("STOP", stop, ts)
                break
            if ts >= t13:
                out = ("SORTIE_13H", a, ts)
                break
        if out is None:
            res[s] = {"outcome": "NO_EXIT"}
            continue
        reason, px, ts_x = out
        eur_x = eur_at(eur, ts_x)
        if eur_x is None:
            res[s] = {"outcome": "NO_EURUSD"}
            continue
        eb, ea = eur_x[1], eur_x[2]
        u = size * UNITS
        stopped = reason == "STOP"
        gross_q = (entry - px) * u
        nq = gross_q - SLIP * PIP * u - (PREM * size if stopped else 0.0)
        g = nq / (eb if nq < 0 else ea)
        net = g - abs(g) * FEE
        res[s] = {"outcome": reason, "date": d.isoformat(), "entry_utc": str(ts_e), "exit_utc": str(ts_x), "entry": entry,
                  "exit": px, "size": round(size, 1), "gross_eur": gross_q / (eb if gross_q < 0 else ea), "net_eur": net,
                  "R": net / (loss_per_contract * size), "slip_eur": SLIP * PIP * u / ea * (1 + FEE),
                  "prem_eur": (PREM * size / ea * (1 + FEE)) if stopped else 0.0, "pips": (entry - px) / PIP}
        equity[s] += net
    return res


def summarize(t):
    t = t.copy()
    t["year"] = t.date.str[:4]
    cum = t.net_eur.cumsum() + 2000
    dd = ((cum.cummax() - cum) / cum.cummax()).max() * 100
    losing = (t.net_eur < 0).astype(int)
    streak = losing.groupby((losing != losing.shift()).cumsum()).cumsum().max()
    gains, losses = t.net_eur[t.net_eur > 0].sum(), -t.net_eur[t.net_eur < 0].sum()
    return {
        "n": len(t), "stop_%": round(100 * (t.outcome == "STOP").mean(), 1), "pips_moyens": round(t.pips.mean(), 2),
        "brut_eur": round(t.gross_eur.sum(), 2), "net_eur": round(t.net_eur.sum(), 2),
        "couts_eur": round(t.gross_eur.sum() - t.net_eur.sum(), 2), "R_net": round(t.R.mean(), 4),
        "se": round(t.R.std() / math.sqrt(len(t)), 4), "PF": round(gains / losses, 3),
        "par_annee_R": {y: round(g.R.mean(), 3) for y, g in t.groupby("year")},
        "par_annee_net": {y: round(g.net_eur.sum(), 2) for y, g in t.groupby("year")},
        "pire_serie_pertes": int(streak), "dd_clos_%": round(dd, 2),
        "net_glissement_x2": round(t.net_eur.sum() - t.slip_eur.sum(), 2),
        "net_prime_x2": round(t.net_eur.sum() - t.prem_eur.sum(), 2), "taille_mediane": float(t["size"].median()),
    }


stops = (20, 30)
equity = {s: 2000.0 for s in stops}
trades = {s: [] for s in stops}
skipped = {s: {} for s in stops}
d = date(2015, 1, 1)
while d <= date(2021, 12, 31):
    if d.weekday() < 5:
        r = trade_day(d, stops, equity)
        for s in stops:
            if s in r and "net_eur" in r[s]:
                trades[s].append(r[s])
            else:
                why = r.get(s, {}).get("outcome", "PAS_DE_TICK_09H")
                skipped[s][why] = skipped[s].get(why, 0) + 1
    d += timedelta(days=1)

summary = {}
for s in stops:
    t = pd.DataFrame(trades[s])
    t.to_csv(DIR / f"trades_S{s}_2015_2021.csv", index=False)
    summary[f"S{s}"] = {"2015-2021": summarize(t), "2015-2019": summarize(t[t.date < "2020"]),
                        "2020-2021": summarize(t[t.date >= "2020"]), "jours_sans_transaction": skipped[s]}

# Independence: day-by-day correlation with the EUR/USD S30 trades.
eur = pd.concat([pd.read_csv(ROOT / f"data/reports/research/morning_short/trades_S30_{p}.csv") for p in ("2015_2019", "2020_2021")])
both = pd.DataFrame(trades[30]).merge(eur[["date", "R", "pips"]], on="date", suffixes=("_gbp", "_eur"))
summary["correlation_S30"] = {"jours_communs": len(both), "R": round(both.R_gbp.corr(both.R_eur), 3),
                              "pips": round(both.pips_gbp.corr(both.pips_eur), 3)}

# Check: tick returns vs the built M5 candles (mid open 09:00 and 13:00 London).
m5 = pq.read_table(ROOT / "data/bars/dukascopy/GBPUSD/intraday_2015_2021_day01_5min/5m.parquet",
                   columns=["start_utc", "bid_open", "ask_open"]).to_pandas()
m5["mid"] = (m5.bid_open.astype(float) + m5.ask_open.astype(float)) / 2
mid = dict(zip(m5.start_utc, m5.mid))
t30 = pd.DataFrame(trades[30])
t30 = t30[t30.outcome == "SORTIE_13H"]
rows = []
for _, r in t30.iterrows():
    dd_ = date.fromisoformat(r.date)
    o9, o13 = mid.get(at(dd_, 9)), mid.get(at(dd_, 13))
    if o9 is not None and o13 is not None:
        rows.append(((o9 - o13) / PIP, r.pips))
chk = pd.DataFrame(rows, columns=["bars", "ticks"])
summary["controle_bougies"] = {"jours": len(chk), "correlation": round(chk.bars.corr(chk.ticks), 4),
                               "ecart_moyen_pips": round((chk.ticks - chk.bars).mean(), 3)}

(DIR / "summary.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary, indent=1))
