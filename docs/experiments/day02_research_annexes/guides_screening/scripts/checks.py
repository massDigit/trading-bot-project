import pandas as pd, numpy as np
df = pd.read_pickle("data/reports/backtests/day02_guides/features.pkl")
df["P1"]=df.year<=2018
se=lambda x: x.std(ddof=1)/np.sqrt(len(x))
print("overlap G1a&G5b:", (df.G1a&df.G5b).sum())
both = df.G1a|df.G5b
print("union removed", both.sum(), "R", round(df[both].R.mean(),3), "kept net", round(df[~both].net.sum(),2), "kept R", round(df[~both].R.mean(),3))
# hour of D (London, breakout candle start) and NY minutes
df["lon_min"] = [ (d - pd.Timedelta(minutes=5)).tz_convert("Europe/London").hour*60+(d - pd.Timedelta(minutes=5)).tz_convert("Europe/London").minute for d in df.d_utc]
df["off"] = df.lon_min - df.mins_ny  # 300 normal, 240 offset weeks
print("offset weeks (NY-London 4h):", (df.off==240).sum())
g = df.groupby(df.lon_min//60).R.agg(["count","mean","sem"]); print("R by London hour of D\n", g.round(3).to_string())
# placebo: sliding 120-min windows on London clock vs NY clock
def scan(col):
    res=[]
    for s in range(df[col].min()//15*15, df[col].max(), 15):
        m=(df[col]>=s)&(df[col]<s+120)
        if m.sum()>=20: res.append((s, m.sum(), df[m].R.mean()))
    return pd.DataFrame(res, columns=["start","n","R"])
for col in ("mins_ny","lon_min"):
    s=scan(col); print(col, "windows:", len(s), "rank of most negative:", s.sort_values("R").head(4).to_string(index=False))
# G5b split by offset weeks: news window defined on NY clock; in offset weeks London-clock window shifts
m=df.G5b
print("G5b in offset weeks n", (m&(df.off==240)).sum())
# London-clock equivalent 12:30-14:30 (no DST link)
ml=(df.lon_min>=750)&(df.lon_min<870); print("London 12:30-14:30: n",ml.sum(),"R",round(df[ml].R.mean(),3), "| NY window n",m.sum(), "R", round(df[m].R.mean(),3), "| disagree:", (ml!=m).sum())
print("late (D>=14:30 London) n", (df.lon_min>=870).sum(), "R", round(df[df.lon_min>=870].R.mean(),3))
# G5a placebo: quarter labels on shifted grids, spread of mean R across Q labels; and Q2 mean
for sh in range(0,90,15):
    q=((df.mins_ny-sh)%360)//90+1
    gm=df.groupby(q).R.mean()
    print(f"shift {sh:2d}: Q means", gm.round(3).to_dict(), "spread", round(gm.max()-gm.min(),3))
# G1a details
r=df[df.G1a]; print("G1a exits", r.exit.value_counts().to_dict(), "sides", r.side.value_counts().to_dict(), "by year", r.groupby("year").R.mean().round(2).to_dict())
print("G1a vs I_A, stop_A:", r[["I_A","stop_A","depth"]].mean().round(2).to_dict(), "others:", df[~df.G1a][["I_A","stop_A","depth"]].mean().round(2).to_dict())
r=df[df.G5b]; print("G5b exits", r.exit.value_counts().to_dict(), "by year", r.groupby("year").R.mean().round(2).to_dict())
