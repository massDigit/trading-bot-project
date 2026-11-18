"""Truncation causality (§5): trades and decisions of the replay ending 2015-04-01 must equal those of the full pass
on the sessions before the cut (a trade still open at the cut excepted)."""
import json, sys
CUT = "2015-04-01"
def decisions(path):
    out = {}
    for line in open(path):
        d = json.loads(line)
        for a in d["attempts"]:
            a = dict(a); a.pop("examined", None); a.pop("measures", None)
            out[(d["day"], a["resume_utc"])] = a
    return out
for v in sys.argv[1:]:
    t = json.load(open(f"truncated/perf_{v}.json"))["result"]["trades"]
    f = [x for x in json.load(open(f"perf_{v}_m5_a.json"))["result"]["trades"] if x["decided_utc"] < CUT]
    same = [a == b for a, b in zip(t, f)]
    tail = [] if len(t) == len(f) and all(same) else [(i, a.get("exit_reason"), b.get("exit_reason")) for i, (a, b, s) in enumerate(zip(t, f, same)) if not s]
    dt, df = decisions(f"truncated/sessions_{v}.jsonl"), decisions(f"perf_{v}_m5_a_sessions.jsonl")
    keys = [k for k in dt if k[0] < "2015-03-31"]
    bad = [k for k in keys if dt[k] != df.get(k)]
    print(f"{v}: transactions {len(t)} / complet {len(f)}, différentes {tail} ; tentatives avant le 31/03 {len(keys)}, différentes {len(bad)} {bad[:3]}")
