"""Atlas EUR/USD 2015-2019 (PROTOCOL.md). Usage: uv run --with pyarrow --with pandas python -I atlas.py"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

DIR = Path(__file__).resolve().parent
ROOT = DIR.parents[3]
PIP = 1e-4

cols = ["start_utc", "content", "bid_open", "bid_high", "bid_low", "ask_open", "ask_high", "ask_low"]
df = pq.read_table(ROOT / "data/bars/dukascopy/EURUSD/intraday_2015_2021_day01_5min/5m.parquet", columns=cols).to_pandas()
df = df[(df.content == "VALID") & (df.start_utc < pd.Timestamp("2020-01-01", tz="UTC"))].copy()
assert df.start_utc.max() < pd.Timestamp("2020-01-01", tz="UTC")
for c in cols[2:]:
    df[c] = df[c].astype(float)
df["o"] = (df.bid_open + df.ask_open) / 2
df["h"] = (df.bid_high + df.ask_high) / 2
df["l"] = (df.bid_low + df.ask_low) / 2
lon = df.start_utc.dt.tz_convert("Europe/London")
df["date"] = lon.dt.date
df["m"] = lon.dt.hour * 60 + lon.dt.minute
df["label"] = (df.start_utc.dt.tz_convert("America/New_York") + pd.Timedelta(hours=7)).dt.date

O = df.pivot_table(index="date", columns="m", values="o", aggfunc="first")
H = df.pivot_table(index="date", columns="m", values="h", aggfunc="first")
L = df.pivot_table(index="date", columns="m", values="l", aggfunc="first")
days = [d for d in O.index if d.weekday() < 5 and not math.isnan(O.at[d, 420])]
O, H, L = O.loc[days], H.loc[days], L.loc[days]
year = pd.Series([d.year for d in days], index=days)


def p(d, minute):
    return O.at[d, minute] if minute in O.columns else np.nan


def ret(a, b):
    """Return in pips from minute a to minute b for every day."""
    return (O[b] - O[a]) / PIP if a in O.columns and b in O.columns else pd.Series(np.nan, index=O.index)


tests = {}

# T1 hour
for h in range(7, 16):
    for hz in (1, 2, 4):
        tests[f"T1 {h:02d}h +{hz}h"] = ret(h * 60, min(h + hz, 20) * 60)

# T2 weekday x session
names = ["lun", "mar", "mer", "jeu", "ven"]
for wd in range(5):
    mask = pd.Series([d.weekday() == wd for d in days], index=days)
    tests[f"T2 {names[wd]} 07-12"] = ret(420, 720)[mask]
    tests[f"T2 {names[wd]} 12-16"] = ret(720, 960)[mask]

# T3 month turn
ym = pd.Series([(d.year, d.month) for d in days], index=days)
last = ym.groupby(ym).apply(lambda s: s.index.max()).values
first = ym.groupby(ym).apply(lambda s: s.index.min()).values
tests["T3 dernier jour 15-16"] = ret(900, 960).loc[list(last)]
tests["T3 dernier jour 07-16"] = ret(420, 960).loc[list(last)]
tests["T3 premier jour 07-16"] = ret(420, 960).loc[list(first)]
tests["T3 dernier jour 12-16"] = ret(720, 960).loc[list(last)]

# baseline (placebo): mean return from each start minute, for H = 60 and 120
baseline = {hz: {m: ret(m, m + hz).mean() for m in range(425, 845, 5)} for hz in (60, 120)}


def breaks(levels_hi, levels_lo, label):
    out = {60: {}, 120: {}}
    excess = {60: {}, 120: {}}
    for d in days:
        hi, lo = levels_hi.get(d), levels_lo.get(d)
        if hi is None or lo is None or not (lo < p(d, 420) < hi):
            continue
        for m in range(420, 840, 5):  # bars starting 07:00 .. 13:55
            up, dn = H.at[d, m] > hi, L.at[d, m] < lo
            if up and dn:
                break  # both in one bar: day skipped
            if up or dn:
                sign, entry = (1 if up else -1), m + 5
                for hz in (60, 120):
                    r = sign * (p(d, entry + hz) - p(d, entry)) / PIP
                    if not math.isnan(r):
                        out[hz][d] = r
                        excess[hz][d] = r - sign * baseline[hz][entry] if entry in baseline[hz] else np.nan
                break
    for hz in (60, 120):
        tests[f"{label} +{hz // 60}h"] = pd.Series(out[hz])
        placebo[f"{label} +{hz // 60}h"] = pd.Series(excess[hz])


placebo = {}
# T4 previous trading day high / low
lab = df.groupby("label").agg(hi=("h", "max"), lo=("l", "min"))
labels = sorted(lab.index)
prev_hi, prev_lo = {}, {}
for d in days:
    i = np.searchsorted(labels, d) - 1
    if i >= 0:
        prev_hi[d], prev_lo[d] = lab.hi.iat[i], lab.lo.iat[i]
breaks(prev_hi, prev_lo, "T4 cassure veille")

# T5 Asian range 00:00-07:00 London
asia_cols = [m for m in H.columns if m < 420]
asia_hi, asia_lo = H[asia_cols].max(axis=1).to_dict(), L[asia_cols].min(axis=1).to_dict()
breaks(asia_hi, asia_lo, "T5 cassure Asie")

# T6 momentum
x = ret(420, 480)
tests["T6 07-08 -> 08-16"] = np.sign(x) * ret(480, 960)
prev_day = pd.Series(days, index=days).shift(1)
c16 = O[960]
night = pd.Series({d: (O.at[d, 420] - c16.get(pd_)) / PIP if isinstance(pd_, type(d)) else np.nan for d, pd_ in prev_day.items()})
tests["T6 nuit -> 07-16"] = np.sign(night) * ret(420, 960)
prev_sess = ret(420, 960).shift(1)
tests["T6 veille -> 07-16"] = np.sign(prev_sess) * ret(420, 960)

assert len(tests) == 48, len(tests)

rows = []
for name, s in tests.items():
    s = s.dropna()
    s = s[s != 0] if name.startswith("T6") else s
    n, mean = len(s), s.mean()
    se = s.std() / math.sqrt(n)
    t = mean / se
    by_year = s.groupby([d.year for d in s.index]).mean()
    same = int((np.sign(by_year) == np.sign(mean)).sum())
    row = {"test": name, "n": n, "mean_pips": round(mean, 2), "se": round(se, 2), "t": round(t, 2),
           "p": math.erfc(abs(t) / math.sqrt(2)), "years_same_sign": f"{same}/{len(by_year)}",
           "by_year": {int(k): round(v, 2) for k, v in by_year.items()}, "R_at_20": round(mean / 21.7, 3)}
    if name in placebo:
        e = placebo[name].dropna()
        row["excess_pips"] = round(e.mean(), 2)
        row["excess_t"] = round(e.mean() / (e.std() / math.sqrt(len(e))), 2)
    rows.append(row)

# Benjamini-Hochberg at 10 %
order = sorted(range(len(rows)), key=lambda i: rows[i]["p"])
m = len(rows)
k_max = max([k + 1 for k, i in enumerate(order) if rows[i]["p"] <= 0.10 * (k + 1) / m], default=0)
for k, i in enumerate(order):
    rows[i]["bh_10"] = k < k_max
for r in rows:
    same = int(r["years_same_sign"].split("/")[0])
    placebo_ok = "excess_pips" not in r or np.sign(r["excess_pips"]) == np.sign(r["mean_pips"])
    r["candidate"] = bool(r["bh_10"] and same >= 4 and abs(r["mean_pips"]) >= 2 and placebo_ok)

res = pd.DataFrame(rows)
pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 100)
show = ["test", "n", "mean_pips", "se", "t", "p", "years_same_sign", "R_at_20", "excess_pips", "excess_t", "bh_10", "candidate"]
res["p"] = res.p.map(lambda v: f"{v:.4f}")
print(res[show].to_string(index=False))
print("\nséance par année (T1/T2/T3/T6 significatifs) :")
for r in rows:
    if r["bh_10"]:
        print(" ", r["test"], r["by_year"])
(DIR / "results.json").write_text(json.dumps(rows, indent=1, default=str))
