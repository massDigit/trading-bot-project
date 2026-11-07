# DAY_01 — étude de disponibilité 2015-2021 : bilan agrégé

**Statut** : bilan du passage autorisé le 2026-11-06, rapports agrégés revus sans incohérence
(sommes des entonnoirs, totaux annuels, répartitions). Protocole :
`docs/experiments/DAY01_AVAILABILITY_2015_2021.md`.

**Portée** : disponibilité des données seulement. Aucun tick lu, aucune exécution, aucun backtest
de performance, aucun entraînement, aucune donnée 2022-2025. Paramètres de la fiche figée (ADR-022),
inchangés.

> **Une confirmation n'est pas une entrée.** Une confirmation est un instant `D` où une entrée
> **sera évaluée** (marché, cotation, stop, taille, position déjà ouverte). Les refus à `D`, les
> expirations, les annulations pour interruption et les liquidations ne sont pas mesurés ici
> (protocole §8).

## 1. Passage

| Élément | Valeur |
|---|---|
| Commit | `1c1ed0fba598a066c903373be3f81c1303e62865`, arbre propre au lancement et à la fin |
| Commande | `uv run forex-day01-availability --out data/reports/backtests/day01_availability_2015_2021_1c1ed0f.json --details-out data/reports/backtests/day01_availability_2015_2021_1c1ed0f_details.jsonl` |
| Lancement / fin (UTC) | 2026-11-06 22:11:29 / 22:14:38 (3 min 10 s), code de sortie 0 |
| Fenêtre | 2015-01-01 → 2022-01-01 (séances du 2015-01-01 au 2021-12-31) |
| Trajectoires | référence M5 `Day01Params()`, comparaison M15 `Day01Params(trigger=Trigger.M15)` |
| Entrées | 523 566 M5, 174 525 M15, 10 912 H4 ; empreintes SHA-256 identiques avant et après (5m `94387741…fb82`, 15m `64b30520…9db2`, 4h `081989d4…7989`) |

Sorties hors Git (ADR-014), sous `data/reports/backtests/` :

| Fichier | SHA-256 |
|---|---|
| `day01_availability_2015_2021_1c1ed0f.json` (agrégé) | `0686b14a…f3c9` |
| `day01_availability_2015_2021_1c1ed0f.md` (agrégé) | `56d8fbda…558e` |
| `day01_availability_2015_2021_1c1ed0f_details.jsonl` (3 654 lignes, une par séance et par trajectoire) | `24111a1d…77c3` |

## 2. Contrôles C1 à C10

Tous conformes, 0 écart.

| Contrôle | Résultat |
|---|---|
| C1 | 1 827 jours ouvrés, 11 sans séance, **1 816 séances attendues** (= bilan des données) |
| C2 | 3 ranges incomplets, aux 3 dates attendues : 2015-11-10 (silence et sous-créneau vide), 2017-01-02 et 2021-10-12 (silence > 5 min) |
| C3 | une issue exclusive par séance et par trajectoire ; entonnoirs conservatifs par année et au total ; aucune cause `ATR_AVAILABLE` |
| C4 | 0 issue de données (cassure, retest) en M5 et en M15 |
| C5 | étapes communes identiques séance par séance sur les 1 827 jours ouvrés |
| C6 | voir ci-dessous |
| C7, C8 | gel, `K`, `D − K`, contact, extrême et dernière bougie examinée dans leurs bornes |
| C9 | paramètres attendus pour chaque trajectoire, autres paramètres identiques, 0 tick lu, entrées inchangées |
| C10 | provenance relevée au lancement ; aucun changement pendant le passage |

**Portée de C6.** Le contrôle parcourt les séances de chaque trajectoire, par des requêtes DuckDB
sur la table M15, hors du moteur (l'ATR du moteur est la seule valeur reprise) :

- complétude du range comparée à l'issue du moteur sur les **1 816 séances attendues** (les
  11 jours sans séance sont sautés) ;
- `RH` et `RL` comparés sur les **1 813 ranges complets** ;
- première clôture de cassure (sens et `K`) recalculée seulement pour les séances qui atteignent
  la recherche de cassure, soit les **1 697 ranges admissibles** (1 204 cassures, 493 sans
  cassure) ; les séances arrêtées avant (ATR non calculable, largeur) ne sont pas recalculées.

C6 ne recalcule donc **pas** une cassure pour chacun des 1 827 jours ouvrés.

## 3. Parcours des séances jusqu'aux confirmations

Chaque étape donne ses entrées, qui servent de dénominateur ; les pourcentages sont calculés sur ces
entrées, pas sur le total des séances.

| Étape (entrées) | Issue terminale | Nombre | % des entrées |
|---|---|---:|---:|
| Jours ouvrés (1 827) | pas de séance | 11 | 0,602 % |
| Séances attendues (1 816) | range incomplet | 3 | 0,165 % |
| Ranges complets (1 813) | ATR H4 non calculable | 49 | 2,703 % |
| Ranges avec ATR (1 764) | range trop étroit | 36 | 2,041 % |
| Ranges avec ATR (1 764) | range trop large | 31 | 1,757 % |
| Ranges admissibles (1 697) | données inutilisables pendant la recherche de cassure | 0 | 0,000 % |
| Ranges admissibles (1 697) | aucune cassure à 11:00 | 493 | 29,051 % |

Ces étapes sont identiques pour les deux trajectoires (C5). Elles laissent **1 204 cassures**. Le
retest se lit ensuite dans l'unité de chaque trajectoire :

| Cassures (1 204) | M5 | % | M15 | % |
|---|---:|---:|---:|---:|
| Données inutilisables pendant le retest | 0 | 0,000 % | 0 | 0,000 % |
| Invalidation avant contact | 19 | 1,578 % | 81 | 6,728 % |
| Invalidation après contact | 39 | 3,239 % | 67 | 5,565 % |
| Délai dépassé sans contact | 314 | 26,080 % | 314 | 26,080 % |
| Délai dépassé, contact sans confirmation | 1 | 0,083 % | 6 | 0,498 % |
| **Confirmations** | **831** | 69,019 % | **736** | 61,130 % |

Rapportées aux 1 816 séances attendues : 831 confirmations en M5 (45,8 %) et 736 en M15 (40,5 %).
Ce sont des **instants d'évaluation**, pas des entrées.

### Par année

| Année | Séances attendues | Ranges admissibles | Cassures | Confirmations M5 | Confirmations M15 |
|---|---:|---:|---:|---:|---:|
| 2015 | 259 | 235 | 172 | 109 | 100 |
| 2016 | 260 | 246 | 164 | 117 | 100 |
| 2017 | 259 | 250 | 177 | 125 | 111 |
| 2018 | 259 | 246 | 171 | 117 | 102 |
| 2019 | 259 | 237 | 165 | 115 | 103 |
| 2020 | 260 | 242 | 172 | 123 | 103 |
| 2021 | 260 | 241 | 183 | 125 | 117 |
| **Total** | **1 816** | **1 697** | **1 204** | **831** | **736** |

## 4. Causes d'abstention liées aux données

| Cause | Séances |
|---|---:|
| ATR H4 non calculable : amorçage, historique H4 initial insuffisant (2015-01-02, 01-05, 01-06) | 3 |
| ATR H4 non calculable : interruption, H4 inutilisable | 46 |
| ATR H4 non calculable : cause non déterminée | 0 |
| Range incomplet : silence > 5 min | 2 |
| Range incomplet : silence et sous-créneau vide | 1 |
| Données inutilisables pendant la recherche de cassure ou le retest | 0 |

ATR non calculable par année : 8, 5, 3, 3, 9, 9, 12 (2015 à 2021). Causes identiques en M5 et en
M15, les étapes étant communes.

Les autres abstentions ne relèvent pas des données : largeur du range (67), absence de cassure
(493), invalidations et délais du retest (tableau du §3).

## 5. Descriptions (sans réglage)

Ces descriptions n'autorisent aucun réglage (protocole §8). Les deux premières lignes portent sur
les 1 764 ranges avec ATR ; les suivantes sur les confirmations.

| Mesure | M5 | M15 |
|---|---|---|
| `H / A` (min / q1 / médiane / q3 / max) | 0,316 / 0,759 / 0,933 / 1,174 / 6,739 | identique |
| ATR H4 en pips (min / q1 / médiane / q3 / max) | 10,8 / 23,1 / 28,1 / 35,0 / 88,9 | identique |
| Confirmations achat / vente | 419 / 412 | 367 / 369 |
| `D − K` = 1 bougie de l'unité (achat + vente) | 387 sur 831 | 505 sur 736 |
| Confirmation sur la bougie de contact | 770 sur 831 | 687 sur 736 |
| Confirmations par heure de `D` à Londres (08 / 09 / 10 / 11) | 322 / 312 / 143 / 54 | 197 / 306 / 162 / 71 |
| Séances attendues → confirmations, BST | 1 070 → 489 | 1 070 → 432 |
| Séances attendues → confirmations, GMT | 626 → 284 | 626 → 250 |
| Séances attendues → confirmations, GMT avec décalage | 120 → 58 | 120 → 54 |

Les trois lignes par horloge de Londres répartissent les 1 816 séances attendues. `D − K` s'étend de 1 à
12 bougies en M5 et de 1 à 4 en M15, dans la limite de 60 min.

## 6. Différences M5 / M15

### Méthode de rapprochement

Les deux trajectoires sont rapprochées **par date de séance de Londres** : le champ `day` du JSONL
de détail est la date de Londres de la séance (§4 de la fiche), et chaque date doit porter
exactement une ligne M5 et une ligne M15. Pour chaque date, on compare les issues. Pour les dates
confirmées des deux côtés, on compare `D` (`confirmation_utc`) de chaque trajectoire. Le calcul lit
seulement le JSONL local, hors Git ; il ne rejoue pas l'étude.

### Synthèse agrégée

1 827 dates de Londres rapprochées, chacune avec ses deux trajectoires.

| Rapprochement | Séances |
|---|---:|
| Même issue | 1 683 |
| Issue différente | **144** |
| dont M5 confirmation → M15 invalidation après contact | 55 |
| dont M5 confirmation → M15 invalidation avant contact | 47 |
| dont M5 confirmation → M15 délai dépassé, contact sans confirmation | 5 |
| dont M5 invalidation après contact → M15 confirmation | 6 |
| dont M5 invalidation avant contact → M15 confirmation | 6 |
| dont M5 invalidation après contact → M15 invalidation avant contact | 23 |
| dont M5 invalidation avant contact → M15 invalidation après contact | 2 |

Issues différentes par année : 16, 19, 20, 18, 20, 26, 25 (2015 à 2021). Toutes surviennent après
la cassure : les étapes communes sont identiques (C5) et le délai sans contact compte 314 séances
dans les deux trajectoires.

Bilan des confirmations : 831 en M5 = 724 communes + 107 propres à M5 ; 736 en M15 = 724 communes
+ 12 propres à M15.

**Confirmations communes : 724.** Décalage `D(M15) − D(M5)` :

| Décalage | Séances |
|---|---:|
| 0 min (même `D`) | 148 |
| 5 min | 168 |
| 10 min | 373 |
| 20 min | 8 |
| 25 min | 18 |
| 35 min | 2 |
| 40 min | 6 |
| 50 min | 1 |

`D` de M15 n'est jamais antérieur à `D` de M5. Il est plus tardif de 5 à 10 min dans 541 cas et de
20 à 50 min dans 35 cas.

### Reproduction

Depuis la racine du dépôt, sur le JSONL local du passage (SHA-256 `24111a1d…77c3`) :

```
uv run python -I - data/reports/backtests/day01_availability_2015_2021_1c1ed0f_details.jsonl <<'EOF'
import json
import sys
from collections import Counter
from datetime import datetime

pairs: dict[str, dict[str, dict]] = {}
for line in open(sys.argv[1], encoding="utf-8"):
    row = json.loads(line)
    pairs.setdefault(row["day"], {})[row["trigger"]] = row  # day = London session date
assert all(set(p) == {"M5", "M15"} for p in pairs.values()), "date sans ses deux trajectoires"
print("dates de Londres rapprochées :", len(pairs))
same = [p for p in pairs.values() if p["M5"]["outcome"] == p["M15"]["outcome"]]
diff = [p for p in pairs.values() if p["M5"]["outcome"] != p["M15"]["outcome"]]
print("même issue :", len(same), "; issue différente :", len(diff))
for (m5, m15), n in Counter((p["M5"]["outcome"], p["M15"]["outcome"]) for p in diff).most_common():
    print(f"  {n:4d}  M5 {m5}  ->  M15 {m15}")
print("  par année :", sorted(Counter(p["M5"]["day"][:4] for p in diff).items()))
both = [p for p in same if p["M5"]["outcome"] == "CONFIRMATION"]
print("confirmations communes :", len(both))
delay = Counter(
    int((datetime.fromisoformat(p["M15"]["confirmation_utc"])
         - datetime.fromisoformat(p["M5"]["confirmation_utc"])).total_seconds() // 60)
    for p in both
)
print("  D(M15) - D(M5) en minutes :", sorted(delay.items()))
EOF
```

Le JSONL et tout extrait par séance restent hors Git.

## 7. Limites

- Une confirmation n'est pas une entrée : sans tick, rien n'est dit des refus à `D`, des
  expirations, des annulations pour interruption, des positions ni des liquidations.
- Les jours fériés probables (25 décembre, 1er janvier) suivent la convention du calendrier, non
  confirmée.
- La comparaison M5 / M15 décrit la disponibilité des confirmations, pas une préférence entre les
  deux unités ; aucune performance n'est mesurée.
- Aucune donnée 2022-2025 lue.
