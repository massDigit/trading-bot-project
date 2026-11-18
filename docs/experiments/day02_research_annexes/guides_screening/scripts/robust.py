import pandas as pd, numpy as np
O="data/reports/backtests/day02_guides/"
df=pd.read_pickle(O+"features.pkl"); df["P1"]=df.year<=2018
e3=pd.read_pickle(O+"sim_E3_9.pkl")
def stats(net, size, label):
    net=net.copy(); n=(net!=0).sum()
    eq=2000+net.cumsum(); dd=(eq.cummax()-eq).max(); ddr=((eq.cummax()-eq)/eq.cummax()).max()
    slip2 = net - 0.5*size/1.12  # +0.5 pip per trade ~ USD 0.5*size -> EUR approx
    pf=net[net>0].sum()/-net[net<0].sum()
    yr=net.groupby(df.year).sum().round(1).to_dict()
    print(f"{label:28s} n {n:3d} net {net.sum():7.2f} PF {pf:.3f} DDclos {dd:6.2f}€ ({100*ddr:.2f}%) slip x2 {slip2[net!=0].sum():7.2f} | 15-18 {net[df.P1].sum():6.2f} 19-21 {net[~df.P1].sum():6.2f} | {yr}")
late_size=df["size"]
stats(df.net, late_size, "LATE")
for k,m in {"G1a":df.G1a,"G5b":df.G5b,"G1a|G5b":df.G1a|df.G5b}.items():
    stats(df.net.where(~m,0.0), late_size.where(~m,0), f"LATE sans {k}")
v=e3.net.fillna(0.0); stats(v, e3["size"].fillna(0), "E3 (taille 0,25 %)")
# E3 at LATE size: rescale net by size ratio (net is linear in size except rounding of conversion sign: ok)
vf = (e3.net/e3["size"]*df["size"]).fillna(0.0); stats(vf, df["size"].where(e3.filled,0), "E3 à taille LATE")
# R units of LATE risk: variant net / LATE estimated stop loss
f=e3.filled
print("E3 filled: mean stop distance ratio (variant/LATE):", round(((df.E-df.S).abs()/(df.PD-df.S).abs())[f].mean(),3))
d=(v-df.net); print("E3 paired d: without best single d", round(d.drop(d.idxmax()).mean(),3), "± ", round(d.std()/np.sqrt(len(d)),3), "| max d", round(d.max(),2), "min", round(d.min(),2))
stats(v.where(~(df.G1a|df.G5b),0.0), e3["size"].fillna(0), "E3 + sans G1a|G5b")
