import json, sys, pandas as pd, numpy as np
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1]); import ticksim as ts
O=ts.OUT; NY="America/New_York"
df=pd.read_pickle(O+"features.pkl"); late=json.load(open(ts.ROOT+"data/reports/backtests/day02_partial_exits/perf_LATE_m5_a.json"))["result"]["trades"]
df["risk_budget"]=[t["risk_budget"] for t in late]; df["exit_utc"]=[pd.Timestamp(t["exit_utc"]) for t in late]
m15=pd.read_parquet(ts.ROOT+"data/bars/dukascopy/EURUSD/intraday_2015_2021/15m.parquet").set_index("start_utc")
m5=pd.read_parquet(ts.ROOT+"data/bars/dukascopy/EURUSD/intraday_2015_2021/5m.parquet").set_index("end_utc")
def feats(c):
    long=c["side"]=="LONG"; p=m15.loc[pd.Timestamp(c["peak_start"])]
    nw = (float(p.bid_open)==float(p.bid_low) and p.bid_close>p.bid_open) if long else (float(p.bid_open)==float(p.bid_high) and p.bid_close<p.bid_open)
    st=(pd.Timestamp(c["ended_utc"])-pd.Timedelta(minutes=5)).tz_convert(NY); mins=st.hour*60+st.minute
    return nw, 450<=mins<570
cands={}  # session day -> confirmed-exit configs of the position-free path
for line in open(ts.ROOT+"data/reports/backtests/day02_late_exit/avail_LATE_details.jsonl"):
    s=json.loads(line)
    cands[s["day"]]=[x["configuration"] for x in s["searches"] if x.get("configuration") and x["configuration"]["outcome"]=="sortie confirmée"]
df["day"]=[(d-pd.Timedelta(minutes=5)).tz_convert("Europe/London").date().isoformat() for d in df.d_utc]
late_D=set(df.d_utc)
def run(filt):
    total=0.0; nrep=0; nblocked=0; rep_net=0.0; blocked_net=0.0; rows=[]
    removed=df[filt]
    blocked=set()
    for _,tr in removed.iterrows():
        D=tr.d_utc; nxt=None
        for c in cands.get(tr.day,[]):
            D2=pd.Timestamp(c["ended_utc"])
            if D2<=D: continue
            nw,news=feats(c)
            if (FILTER=="G1a" and nw) or (FILTER=="G5b" and news) or (FILTER=="both" and (nw or news)): continue
            nxt=(D2,c); break
        if nxt is None: continue
        D2,c=nxt
        if D2 in late_D: continue  # already a LATE trade (path re-synchronised)
        long=c["side"]=="LONG"; brk=m5.loc[D2]
        row=SimpleNamespace(**dict(side=c["side"],d_utc=D2,S=float(c["stop"]),T=float(c["target"]),E=float(c["peak"]),risk_budget=tr.risk_budget,
                           brk_nowick=False,brk_open=0,brk_high=0,brk_low=0))
        r=ts.simulate(row,"MKT")
        if not r.get("filled"): continue
        nrep+=1; rep_net+=r["net"]; rows.append((D2,r["reason"],r["net"]))
        # later LATE trades of the same session overlapped by the replacement are blocked
        for _,t2 in df[(df.day==tr.day)&(df.d_utc>D2)].iterrows():
            if t2.d_utc < r["exit_ts"] and t2.d_utc not in blocked and not filt[t2.name]:
                blocked.add(t2.d_utc); nblocked+=1; blocked_net+=t2.net
    kept=df[~filt].net.sum()
    print(f"{FILTER}: removed {filt.sum()} (net {removed.net.sum():.2f}) | replacements {nrep} net {rep_net:.2f} | LATE trades blocked {nblocked} net {blocked_net:.2f} | trajectory net ≈ {kept+rep_net-blocked_net:.2f} (subset {kept:.2f})")
    return rows
for FILTER,m in (("G1a",df.G1a),("G5b",df.G5b),("both",df.G1a|df.G5b)):
    rows=run(m)
    if rows: print("   replacements exits:", pd.Series([x[1] for x in rows]).value_counts().to_dict())
