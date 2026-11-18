"""GBP/USD M5/M15 lot vs EUR/USD: grids, counts, contents, OK rate, no candle after 2021 (ADR-039 §4)."""
import json
from collections import Counter
import pyarrow.parquet as pq
B = "data/bars/dukascopy/{}/intraday_2015_2021_day01_5min/{}.parquet"
out = {}
for g in ("5m", "15m"):
    e = pq.read_table(B.format("EURUSD", g), columns=["start_utc", "content", "complete_at_close"]).to_pylist()
    p = pq.read_table(B.format("GBPUSD", g), columns=["start_utc", "end_utc", "content", "complete_at_close"]).to_pylist()
    es, ps = {r["start_utc"] for r in e}, {r["start_utc"] for r in p}
    out[g] = {"eur": len(e), "gbp": len(p), "grille_identique": es == ps, "gbp_seulement": len(ps - es), "eur_seulement": len(es - ps),
              "contenus_gbp": dict(Counter(str(r["content"]) for r in p)), "ok_eur": sum(r["complete_at_close"] for r in e),
              "ok_gbp": sum(r["complete_at_close"] for r in p),
              "ok_eur_pas_gbp": len({r["start_utc"] for r in e if r["complete_at_close"]} - {r["start_utc"] for r in p if r["complete_at_close"]}),
              "derniere_fin_gbp": str(max(r["end_utc"] for r in p))}
print(json.dumps(out, indent=1))
json.dump(out, open("data/reports/backtests/day02_frequency/gbp_alignment.json", "w"), indent=1)
