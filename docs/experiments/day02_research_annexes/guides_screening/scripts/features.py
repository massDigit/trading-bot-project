"""DAY02 guides screening: causal features of each LATE trade (bars ending <= D only)."""
import json, sys
from datetime import timedelta
import pandas as pd
import numpy as np

ROOT = "./"  # racine du dépôt (copie archivée)
BASE = ROOT + "data/reports/backtests/day02_partial_exits/perf_LATE_m5_a"
OUT = ROOT + "data/reports/backtests/day02_guides/"
NY, LON = "America/New_York", "Europe/London"

trades = pd.DataFrame(json.load(open(BASE + ".json"))["result"]["trades"])
cfg = {}
for line in open(BASE + "_sessions.jsonl"):
    s = json.loads(line)
    for a in s["attempts"]:
        if a.get("trade"):
            cfg[a["decision"]["d_utc"]] = a

m5 = pd.read_parquet(ROOT + "data/bars/dukascopy/EURUSD/intraday_2015_2021/5m.parquet")
m15 = pd.read_parquet(ROOT + "data/bars/dukascopy/EURUSD/intraday_2015_2021/15m.parquet")
for b in (m5, m15):
    b.set_index("start_utc", inplace=True, drop=False)
    b.sort_index(inplace=True)
    for c in ("bid_open", "bid_high", "bid_low", "bid_close", "ask_high", "ask_low"):
        b[c] = b[c].astype(float)

# trading day = NY 17:00 rollover; week = trading days grouped Monday-based
m5v = m5[m5.content == "VALID"].copy()
ny = m5v.start_utc.dt.tz_convert(NY)
m5v["tday"] = (ny + pd.Timedelta(hours=7)).dt.date  # 17:00 NY -> next day
daily = m5v.groupby("tday").agg(H=("bid_high", "max"), L=("bid_low", "min"))
tdays = pd.to_datetime(pd.Series(daily.index))
daily["week"] = (tdays - pd.to_timedelta(tdays.dt.weekday, unit="D")).dt.date.values
weekly = daily.groupby("week").agg(H=("H", "max"), L=("L", "min"))


def levels_before(t0):
    """Major levels known at t0 (UTC): previous trading day, Asia session of the London date, previous week."""
    tday = (t0.tz_convert(NY) + pd.Timedelta(hours=7)).date()
    prev = daily.index[daily.index < tday]
    out = {}
    if len(prev):
        out["PDH"], out["PDL"] = daily.loc[prev[-1], ["H", "L"]]
    wk = (pd.Timestamp(tday) - pd.Timedelta(days=pd.Timestamp(tday).weekday())).date()
    pw = weekly.index[weekly.index < wk]
    if len(pw):
        out["PWH"], out["PWL"] = weekly.loc[pw[-1], ["H", "L"]]
    lon = t0.tz_convert(LON)
    a0 = lon.normalize().tz_convert("UTC")
    a1 = (lon.normalize() + pd.Timedelta(hours=7)).tz_convert("UTC")
    asia = m5v[(m5v.start_utc >= a0) & (m5v.end_utc <= min(a1, t0))]
    if len(asia):
        out["ASH"], out["ASL"] = asia.bid_high.max(), asia.bid_low.min()
    return out


def nowick(c, long):
    return (c.bid_open == c.bid_low and c.bid_close > c.bid_open) if long else (c.bid_open == c.bid_high and c.bid_close < c.bid_open)


rows = []
for _, tr in trades.iterrows():
    a = cfg[tr.decided_utc]
    c, dec = a["configuration"], a["decision"]
    long = c["side"] == "LONG"
    sg = 1 if long else -1
    D = pd.Timestamp(dec["d_utc"])
    A, O, E = float(c["atr"]), float(c["origin"]), float(c["peak"])
    I = abs(E - O)
    PD, S, T = float(dec["p_d"]), float(dec["stop"]), float(dec["target"])
    o0, p0 = pd.Timestamp(c["origin_start"]), pd.Timestamp(c["peak_start"])
    F = pd.Timestamp(c["flag_utc"])
    W0 = pd.Timestamp(c["recognised_utc"]) - pd.Timedelta(hours=1)
    imp = m15.loc[o0:p0]
    pauses = [m15.loc[pd.Timestamp(x)] for x in c["pause_starts"]]
    trig = m5[(m5.start_utc >= F) & (m5.end_utc <= D)]
    brk = trig.iloc[-1]
    assert brk.end_utc == D
    r = dict(d_utc=D, side=c["side"], R=float(tr.net_account) / float(tr.estimated_stop_loss_at_decision),
             net=float(tr.net_account), size=float(tr["size"]), exit=tr.exit_reason, A=A, I_A=I / A,
             stop_A=abs(PD - S) / A, n_ext=len(c["extensions"]), n_pause=len(pauses),
             depth=(E - min(p.bid_low for p in pauses)) / I if long else (max(p.bid_high for p in pauses) - E) / I)
    r["year"] = D.year
    r["hour_lon"] = (D - pd.Timedelta(minutes=5)).tz_convert(LON).hour
    # G1 NoWick
    r["G1a"] = nowick(m15.loc[p0], long)
    r["G1b"] = any(nowick(x, long) for _, x in imp.iloc[:-1].iterrows())
    # G2 / G3 levels known before the impulse window
    lv = levels_before(min(W0, o0))
    highs = [v for k, v in lv.items() if k.endswith("H")]
    lows = [v for k, v in lv.items() if k.endswith("L")]
    swept = [L for L in (highs if long else lows) if (O < L <= E if long else E <= L < O)]
    r["G2"] = bool(swept)
    lo, hi = sorted((PD, T))
    r["G3a"] = any(lo < L < hi for L in lv.values())
    k0 = np.floor(lo / 0.005) * 0.005
    r["G3b"] = any(lo < x < hi for x in np.arange(k0, hi + 0.005, 0.005))
    # G3c opposing unfilled M15 FVG between P_D and T, formed within 24 h before D
    win = m15[(m15.start_utc >= D - pd.Timedelta(hours=24)) & (m15.end_utc <= D) & (m15.content == "VALID")]
    g = False
    for i in range(len(win) - 2):
        c1, c3 = win.iloc[i], win.iloc[i + 2]
        if c3.start_utc - c1.start_utc != pd.Timedelta(minutes=30):
            continue
        after = win.iloc[i + 3:]
        if long and c1.bid_low > c3.bid_high:  # bearish FVG above
            zl, zh = c3.bid_high, c1.bid_low
            if (after.bid_high < zh).all() and lo < zl < hi:
                g = True
        if not long and c1.bid_high < c3.bid_low:  # bullish FVG below
            zl, zh = c1.bid_high, c3.bid_low
            if (after.bid_low > zl).all() and lo < zh < hi:
                g = True
    r["G3c"] = g
    # G4a Failed 2 among pause candles (previous candle = previous M15)
    f2 = False
    for p in pauses:
        prev = m15.loc[p.start_utc - pd.Timedelta(minutes=15)]
        if long and p.bid_low < prev.bid_low and p.bid_close >= prev.bid_low and p.bid_high <= prev.bid_high:
            f2 = True
        if not long and p.bid_high > prev.bid_high and p.bid_close <= prev.bid_high and p.bid_low >= prev.bid_low:
            f2 = True
    r["G4a"] = f2
    pre = trig.iloc[:-1]
    r["G4b"] = bool(((pre.bid_high > E) & (pre.bid_close <= E)).any() if long else ((pre.bid_low < E) & (pre.bid_close >= E)).any())
    # G5 time
    bny = brk.start_utc.tz_convert(NY)
    mins = bny.hour * 60 + bny.minute
    r["q90"] = (mins % 360) // 90 + 1
    r["mins_ny"] = mins
    r["G5a"] = r["q90"] == 2
    r["G5b"] = 7 * 60 + 30 <= mins < 9 * 60 + 30
    r["G5c"] = any((x.tz_convert(NY).hour, x.tz_convert(NY).minute) == (8, 30) for x in imp.start_utc)
    # G6 accumulation before W
    acc = m15[(m15.start_utc >= W0 - pd.Timedelta(hours=2)) & (m15.end_utc <= W0)]
    if len(acc) == 8:
        bodies_hi = np.maximum(acc.bid_open, acc.bid_close).max()
        bodies_lo = np.minimum(acc.bid_open, acc.bid_close).min()
        r["acc_A"] = (bodies_hi - bodies_lo) / A
        r["G6"] = r["acc_A"] <= 1.0
    else:
        r["acc_A"], r["G6"] = np.nan, False
    # E1 inputs
    r["brk_nowick"] = nowick(brk, long)
    r["brk_open"], r["brk_high"], r["brk_low"] = brk.bid_open, brk.bid_high, brk.bid_low
    r.update(E=E, O=O, PD=PD, S=S, T=T, F=F)
    rows.append(r)

df = pd.DataFrame(rows)
df.to_pickle(OUT + "features.pkl")
print(df.drop(columns=["F"]).describe(include="all").T[["count", "mean", "top", "freq"]].to_string())
