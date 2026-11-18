"""E3 decomposition against LATE (docs/experiments/DAY02_FREQUENCY_CAMPAIGN.md §2): reads both engine passes'
session files and reconciles with the screening figures (day02_guides/BILAN.md). Nothing is re-simulated.

Categories, keyed by the decision (D, side):
- filled: LATE decision also decided in E3 and executed (limit filled);
- missed: decided in E3 but not filled (expired or cancelled on target): LATE's net is forgone;
- trajectory-removed: LATE decision never decided in E3 (a different resume path);
- trajectory-added: E3 decision absent from LATE.
Sizing: E3 sizes from E; the filled trades are also shown at LATE's size (net x size_LATE / size_E3,
linear in size up to fee rounding).
"""
import json
import math
from collections import Counter
from pathlib import Path

DIR = Path(__file__).resolve().parent


def attempts(name):
    out = {}
    for line in open(DIR / f"perf_{name}_m5_a_sessions.jsonl"):
        for a in json.loads(line)["attempts"]:
            if a.get("at_d") == "ENTRÉE_DÉCIDÉE":
                out[(a["decision"]["d_utc"], a["decision"]["side"])] = a
    return out


def net(a):
    return float(a["trade"]["net_eur"]) if a.get("trade") else None


late, e3 = attempts("LATE"), attempts("E3")
filled = [k for k in late if k in e3 and e3[k].get("trade")]
missed = [k for k in late if k in e3 and not e3[k].get("trade")]
removed = [k for k in late if k not in e3]
added = [k for k in e3 if k not in late]
outcomes = Counter(e3[k]["entry_outcome"] for k in missed)
added_filled = [k for k in added if e3[k].get("trade")]

late_filled = sum(net(late[k]) for k in filled)
e3_filled = sum(net(e3[k]) for k in filled)
e3_at_late_size = sum(net(e3[k]) * float(late[k]["trade"]["size"]) / float(e3[k]["trade"]["size"]) for k in filled)
late_missed = sum(net(late[k]) for k in missed)
late_removed = sum(net(late[k]) for k in removed)
e3_added = sum(net(e3[k]) for k in added_filled)
total_late = sum(net(a) for a in late.values())
total_e3 = sum(net(a) for a in e3.values() if a.get("trade"))

print(f"LATE {len(late)} décisions, net {total_late:.2f} | E3 {len(e3)} décisions, {sum(1 for a in e3.values() if a.get('trade'))} exécutées, net {total_e3:.2f}")
print(f"exécutées communes {len(filled)} : LATE {late_filled:.2f} → E3 {e3_filled:.2f} (à taille LATE {e3_at_late_size:.2f})")
print(f"  dont amélioration de prix (taille LATE) {e3_at_late_size - late_filled:+.2f}, effet de taille {e3_filled - e3_at_late_size:+.2f}")
print(f"manquées {len(missed)} {dict(outcomes)} : valaient {late_missed:+.2f} dans LATE")
print(f"retirées par trajectoire {len(removed)} : valaient {late_removed:+.2f} ; ajoutées par trajectoire {len(added)} ({len(added_filled)} exécutées) : {e3_added:+.2f}")
check = late_filled + late_missed + late_removed
print(f"rapprochement LATE : {check:.2f} = {total_late:.2f} ; E3 : {e3_filled + e3_added:.2f} = {total_e3:.2f}")
diff = [(net(e3[k]) if e3[k].get("trade") else 0.0) - net(late[k]) for k in late if k in e3]
diff += [-net(late[k]) for k in removed]
m = sum(diff) / len(diff)
sd = math.sqrt(sum((x - m) ** 2 for x in diff) / (len(diff) - 1))
print(f"écart apparié par décision LATE (n {len(diff)}) : {m:+.3f} ± {sd / math.sqrt(len(diff)):.3f} € ; + ajoutées {e3_added:+.2f}")
json.dump({"filled": len(filled), "late_filled": late_filled, "e3_filled": e3_filled, "e3_at_late_size": e3_at_late_size,
           "missed": len(missed), "missed_outcomes": outcomes, "late_missed": late_missed, "removed": len(removed),
           "late_removed": late_removed, "added": len(added), "added_filled": len(added_filled), "e3_added": e3_added,
           "paired_mean": m, "paired_se": sd / math.sqrt(len(diff))}, open(DIR / "e3_decomp.json", "w"), indent=1)
