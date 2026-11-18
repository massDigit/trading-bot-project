import pandas as pd, numpy as np
O="data/reports/backtests/day02_guides/"
df=pd.read_pickle(O+"features.pkl"); df["P1"]=df.year<=2018
for name in ("E1_9","E1_18","E3_9"):
    r=pd.read_pickle(O+f"sim_{name}.pkl")
    aff = r["mode"]!="MKT"
    vnet = r.net.fillna(0.0)
    d = (vnet-df.net)[aff]
    print(f"== {name}: applied {aff.sum()} | filled {r[aff].filled.sum()} | outcomes {r[aff].outcome.value_counts().to_dict()}")
    print(f"   total net {vnet.sum():.2f} (LATE {df.net.sum():.2f}) | paired d EUR on applied: sum {d.sum():.2f}, mean {d.mean():.3f} ± {d.std(ddof=1)/np.sqrt(len(d)):.3f}; 2015-18 {d[df.P1].sum():.2f}, 2019-21 {d[~df.P1].sum():.2f}")
    f = aff & r.filled
    m = aff & ~r.filled
    print(f"   filled: LATE net {df.net[f].sum():.2f} -> variant {r.net[f].sum():.2f} ; missed trades' LATE net {df.net[m].sum():.2f} (R {df.R[m].mean():.3f}, n {m.sum()})")
    if f.any():
        print("   fill delay (M5):", r[f].delay_m5.value_counts().sort_index().to_dict(), "| exits", r[f].reason.value_counts().to_dict(), "| LATE exits of same", df.exit[f].value_counts().to_dict())
        print("   sizes variant vs LATE (filled):", r[f]["size"].round(1).value_counts().to_dict(), df["size"][f].value_counts().to_dict())
