"""Cost wall, EUR/USD M5 2015-2021 (PROTOCOL.md). Usage: uv run --with pyarrow --with pandas python cost_wall.py"""
import json
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

DIR = Path(__file__).resolve().parent
ROOT = DIR.parents[3]
PIP = 1e-4
SLIP, PREM, FEE = 0.5, 1.2, 0.005
STOPS = [5, 7.5, 10, 15, 20, 30]
RATIOS = [1, 2]

cols = ["start_utc", "content", "bid_open", "bid_high", "bid_low", "bid_close", "ask_open", "ask_high", "ask_low", "ask_close"]
df = pq.read_table(ROOT / "data/bars/dukascopy/EURUSD/intraday_2015_2021_day01_5min/5m.parquet", columns=cols).to_pandas()
df = df[df.content == "VALID"].sort_values("start_utc").reset_index(drop=True)
assert df.start_utc.max() < pd.Timestamp("2022-01-01", tz="UTC")
for c in cols[2:]:
    df[c] = df[c].astype(float)
ts = df.start_utc
lon = ts.dt.tz_convert("Europe/London")
paris = ts.dt.tz_convert("Europe/Paris")
df["lon_date"], df["lon_time"], df["year"] = lon.dt.date, lon.dt.time, lon.dt.year
df["paris_date"], df["paris_time"] = paris.dt.date, paris.dt.time
df["period"] = np.where(df.year <= 2019, "2015-2019", "2020-2021")

# A. spread by London hour
day = df[(df.lon_time >= time(7)) & (df.lon_time < time(16))].copy()
day["spread"] = (day.ask_close - day.bid_close) / PIP
day["hour"] = day.start_utc.dt.tz_convert("Europe/London").dt.hour
spread = day.groupby(["period", "hour"]).spread.agg(["median", "mean"]).round(2)

# B. random bracket entries
bo, bh, bl = df.bid_open.values, df.bid_high.values, df.bid_low.values
ao, ah, al = df.ask_open.values, df.ask_high.values, df.ask_low.values
starts = ts.values
liq = np.array([(pt >= time(22, 55)) for pt in df.paris_time])
decision = df[(df.lon_time.apply(lambda t: t.minute in (0, 30) and time(7) <= t <= time(15, 30)))].index
rows = []
for i in decision:
    j = i + 1  # entry bar: the next M5 bar, same London day
    if j >= len(df) or df.lon_date.iat[j] != df.lon_date.iat[i] or (starts[j] - starts[i]) != np.timedelta64(5, "m"):
        continue
    # last bar index before liquidation (first bar starting at/after 22:55 Paris on the entry's Paris date)
    k = j
    pd_entry = df.paris_date.iat[j]
    while k < len(df) and df.paris_date.iat[k] == pd_entry and not liq[k]:
        k += 1
    if k >= len(df) or df.paris_date.iat[k] != pd_entry:
        continue  # no liquidation bar the same day: skipped (counted)
    for side in (1, -1):
        entry = ao[j] if side == 1 else bo[j]
        if side == 1:
            adverse, favour, exitp = bl[j:k], bh[j:k], bo[k]
        else:
            adverse, favour, exitp = ah[j:k], al[j:k], ao[k]
        for s in STOPS:
            for r in RATIOS:
                stop = entry - side * s * PIP
                tgt = entry + side * r * s * PIP
                hs = np.nonzero((adverse <= stop) if side == 1 else (adverse >= stop))[0]
                ht = np.nonzero((favour >= tgt) if side == 1 else (favour <= tgt))[0]
                fs = hs[0] if len(hs) else np.inf
                ft = ht[0] if len(ht) else np.inf
                if fs == np.inf and ft == np.inf:
                    out, pips, n = "LIQ", side * (exitp - entry) / PIP - SLIP, k - j
                elif fs <= ft:
                    out, pips, n = "STOP", -s - SLIP - PREM, fs + 1
                else:
                    out, pips, n = "CIBLE", r * s - SLIP, ft + 1
                pips -= abs(pips) * FEE
                rows.append((df.period.iat[i], df.year.iat[i], s, r, side, out, pips / (s + SLIP + PREM), n * 5, bool(fs == ft and fs != np.inf)))
res = pd.DataFrame(rows, columns=["period", "year", "stop", "ratio", "side", "outcome", "R", "minutes", "ambiguous"])

summary = []
for (period, s, r), g in res.groupby(["period", "stop", "ratio"]):
    med = g.minutes.median()
    per_year = g.groupby("year").R.mean()
    summary.append({
        "period": period, "stop_pips": s, "target": f"1:{r}", "n": len(g),
        "R_net": round(g.R.mean(), 3), "se": round(g.R.std() / np.sqrt(len(g)), 3),
        "worst_year_R": round(per_year.min(), 3), "best_year_R": round(per_year.max(), 3),
        "cible_%": round(100 * (g.outcome == "CIBLE").mean(), 1), "stop_%": round(100 * (g.outcome == "STOP").mean(), 1),
        "liq_%": round(100 * (g.outcome == "LIQ").mean(), 1), "ambiguous_%": round(100 * g.ambiguous.mean(), 1),
        "median_minutes": med, "max_trades_per_day": round(540 / med, 1),
        "cost_share_of_R": round((SLIP + PREM * (g.outcome == "STOP").mean()) / (s + SLIP + PREM), 3),
    })
summary = pd.DataFrame(summary)
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)
print("A. écart (pips) par heure de Londres\n", spread.unstack(0))
print("\nB. entrée au hasard\n", summary.to_string(index=False))
(DIR / "results.json").write_text(json.dumps({"spread": spread.reset_index().to_dict("records"), "bracket": summary.to_dict("records")}, indent=1, default=str))
res.to_pickle(DIR / "trades.pkl")
