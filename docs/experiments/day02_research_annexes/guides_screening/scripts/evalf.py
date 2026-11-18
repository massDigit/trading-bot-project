import pandas as pd, numpy as np
df = pd.read_pickle("data/reports/backtests/day02_guides/features.pkl")
df["P1"] = df.year <= 2018
def se(x): return x.std(ddof=1)/np.sqrt(len(x)) if len(x) > 1 else np.nan
def pf(x): return x[x>0].sum()/-x[x<0].sum()
# removal masks (True = trade removed by the filter)
rem = {"G1a": df.G1a, "G1b": ~df.G1b, "G2": df.G2, "G3a": df.G3a, "G3b": df.G3b, "G3c": df.G3c,
       "G4a": ~df.G4a, "G4b": df.G4b, "G5a": df.G5a, "G5b": df.G5b, "G5c": df.G5c, "G6": ~df.G6}
rows = []
for k, m in rem.items():
    r = df[m]; kept = df[~m]
    mr, s = r.R.mean(), se(r.R)
    worst = r.R.min()
    m_wo = r.R.drop(r.R.idxmin()).mean() if len(r) > 2 else np.nan  # without most negative removed
    rows.append(dict(H=k, n_rem=len(r), pct=round(100*len(r)/len(df)), Rrem=mr, se=s, z=mr/s,
        Rrem_1518=df[m & df.P1].R.mean(), Rrem_1921=df[m & ~df.P1].R.mean(), Rrem_wo_worst=m_wo,
        kept_n=len(kept), kept_net=kept.net.sum(), kept_R=kept.R.mean(), kept_PF=pf(kept.net),
        net_rem_eur=r.net.sum()))
out = pd.DataFrame(rows).set_index("H")
pd.set_option("display.width", 250)
print("LATE: n", len(df), "net", round(df.net.sum(),2), "R", round(df.R.mean(),3), "PF", round(pf(df.net),3))
print(out.round(3).to_string())
out.to_csv("data/reports/backtests/day02_guides/filters.csv")
