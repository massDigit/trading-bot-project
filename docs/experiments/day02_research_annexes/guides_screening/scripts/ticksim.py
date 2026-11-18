"""Tick replay of LATE entries (validation) and limit-entry variants E1 (NoWick retest) / E3 (box retest).

Same conventions as the engine: buy at ask / sell at bid, guaranteed stop filled at the stop level with
1.2 USD/contract premium, target at the first executable quote beyond T, liquidation at the first tick
strictly after 22:55 Europe/Paris, 0.5 pip slippage line, conversion 1/bid (loss) or 1/ask (gain) with 0.5 % fee,
financing 1 USD/contract/night per NY trading-day change. Sizing: 0.25 % budget from the LATE trade.
"""
import json, sys, glob, math, pickle, os
from datetime import timedelta, datetime, time
from zoneinfo import ZoneInfo
import pyarrow.parquet as pq, pyarrow.compute as pc
import pandas as pd

ROOT = "./"  # racine du dépôt (copie archivée)
OUT = ROOT + "data/reports/backtests/day02_guides/"
PARIS, NY, LON = ZoneInfo("Europe/Paris"), ZoneInfo("America/New_York"), ZoneInfo("Europe/London")
PIP, UNITS, SLIP, PREM, FEE = 1e-4, 10_000, 0.5, 1.2, 0.005

idx_path = OUT + "tick_index.pkl"
if os.path.exists(idx_path):
    INDEX = pickle.load(open(idx_path, "rb"))
else:
    INDEX = []
    for p in glob.glob(ROOT + "data/normalized/ticks/dukascopy/EURUSD/*.parquet"):
        m = pq.read_schema(p).metadata
        INDEX.append((pd.Timestamp(m[b"period_start_utc"].decode()), pd.Timestamp(m[b"period_end_utc"].decode()), p))
    INDEX.sort()
    pickle.dump(INDEX, open(idx_path, "wb"))


def ticks(start, end):
    for s, e, p in INDEX:
        if s < end and start < e:
            t = pq.read_table(p, columns=["ts_utc", "raw_row", "bid", "ask"],
                              filters=[("ts_utc", ">=", start.to_pydatetime()), ("ts_utc", "<", end.to_pydatetime())])
            t = t.sort_by([("ts_utc", "ascending"), ("raw_row", "ascending")])
            for ts, b, a in zip(t["ts_utc"].to_pylist(), t["bid"].to_pylist(), t["ask"].to_pylist()):
                b, a = float(b), float(a)
                if b > 0 and a > 0 and b <= a:
                    yield pd.Timestamp(ts), b, a


def tday(ts):
    return (ts.tz_convert(NY) + pd.Timedelta(hours=7)).date()


def loss_per_contract_eur(long, entry, stop, bid):
    lq = ((entry - stop) if long else (stop - entry)) * UNITS + SLIP * PIP * UNITS + PREM
    return lq / bid * (1 + FEE)


def size_for(budget, lpc):
    return max(0, math.floor(budget / lpc / 0.1 + 1e-9)) * 0.1


def settle(long, size, entry, entry_ts, price, ts, bid, ask, stopped):
    u = size * UNITS
    move = (price - entry) if long else (entry - price)
    nights = (tday(ts) - tday(entry_ts)).days
    costs = SLIP * PIP * u + (PREM * size if stopped else 0) + nights * 1.0 * size
    nq = move * u - costs
    g = nq / (bid if nq < 0 else ask)
    return g - abs(g) * FEE


def simulate(tr, mode, validity_m5=9):
    """mode: MKT (LATE replay), E1, E3. Returns dict."""
    long = tr.side == "LONG"
    D = tr.d_utc
    S, T = tr.S, tr.T
    sess = (D - pd.Timedelta(minutes=5)).tz_convert(LON).date()
    liq = pd.Timestamp(datetime.combine(sess, time(22, 55), tzinfo=PARIS)).tz_convert("UTC")
    level = None
    if mode == "E1" and tr.brk_nowick:
        level = tr.brk_open
    if mode == "E3":
        level = tr.E
    if mode in ("E1", "E3") and level is None:
        mode = "MKT"  # E1 applies only to NoWick breakouts; others unchanged
    pending_until = D + (pd.Timedelta(minutes=5) if mode == "MKT" else pd.Timedelta(minutes=5 * validity_m5))
    budget = float(tr.risk_budget)
    pos = None
    last = None
    out = dict(mode=mode, filled=False)
    for ts, b, a in ticks(D - pd.Timedelta(minutes=6), D + pd.Timedelta(days=4)):
        if ts < D or (ts == D):
            last = (ts, b, a)
            continue
        if pos is None:
            if ts > pending_until:
                out["outcome"] = "EXPIRED"
                return out
            if last is None:
                out["outcome"] = "NO_QUOTE"; return out
            if "size" not in out:
                lb, la = last[1], last[2]
                est = (la if long else lb) if mode == "MKT" else level
                out["size"] = size_for(budget, loss_per_contract_eur(long, est, S, lb))
                if out["size"] < 0.1:
                    out["outcome"] = "SIZE_REFUSED"; return out
            if mode == "MKT":
                fill = a if long else b
            else:
                if (mode == "E1") and ((long and b > tr.brk_high) or (not long and a < tr.brk_low)):
                    out["outcome"] = "CANCEL_NEW_EXTREME"; return out
                if mode == "E3" and ((long and b >= T) or (not long and a <= T)):
                    out["outcome"] = "CANCEL_TARGET"; return out
                if long and a <= level:
                    fill = a
                elif (not long) and b >= level:
                    fill = b
                else:
                    continue
            pos = (ts, fill)
            out.update(filled=True, entry_ts=ts, entry=fill, delay_m5=int((ts - D) / pd.Timedelta(minutes=5)) + 1)
            # same-tick checks below
        et, ep = pos
        size = out["size"]
        if (long and b <= S) or (not long and a >= S):
            out.update(exit_ts=ts, exit=S, reason="STOP", net=settle(long, size, ep, et, S, ts, b, a, True)); return out
        if (long and b >= T) or (not long and a <= T):
            px = b if long else a
            out.update(exit_ts=ts, exit=px, reason="CIBLE", net=settle(long, size, ep, et, px, ts, b, a, False)); return out
        if ts > liq:
            px = b if long else a
            out.update(exit_ts=ts, exit=px, reason="LIQ", net=settle(long, size, ep, et, px, ts, b, a, False)); return out
    out["outcome"] = "OPEN_AT_END"
    return out


if __name__ == "__main__":
    mode = sys.argv[1]
    validity = int(sys.argv[2]) if len(sys.argv) > 2 else 9
    df = pd.read_pickle(OUT + "features.pkl")
    late = pd.DataFrame(json.load(open(ROOT + "data/reports/backtests/day02_partial_exits/perf_LATE_m5_a.json"))["result"]["trades"])
    df["risk_budget"] = late.risk_budget.values
    df["late_entry"] = late.entry_price.astype(float).values
    df["late_exit"] = late.exit_price.astype(float).values
    df["late_size"] = late["size"].astype(float).values
    res = [simulate(tr, mode, validity) for tr in df.itertuples()]
    r = pd.DataFrame(res)
    r.index = df.index
    pd.to_pickle(r, OUT + f"sim_{mode}_{validity}.pkl")
    if mode == "MKT":
        ok_entry = (abs(r.entry - df.late_entry) < 1e-9).sum()
        ok_exit = (abs(r.exit - df.late_exit.values) < 1e-9).sum()
        ok_size = (abs(r["size"] - df.late_size) < 1e-9).sum()
        dn = (r.net - df.net).abs()
        print(f"entries {ok_entry}/296 exits {ok_exit}/296 sizes {ok_size}/296 max|dnet| {dn.max():.2e} sum net {r.net.sum():.4f} vs {df.net.sum():.4f}")
        print(r.reason.value_counts().to_dict())
        bad = r[(dn > 1e-6)]
        print(bad.head())
    else:
        print(r["mode"].value_counts().to_dict(), r.get("outcome", pd.Series()).value_counts().to_dict(), "filled", r.filled.sum())
