# DAY_02 — étude de disponibilité 2015-2021 : bilan agrégé

**Statut** : bilan du passage autorisé le 2026-11-07, soumis à revue. Protocole :
`docs/experiments/DAY02_AVAILABILITY_2015_2021.md` (ADR-030 à ADR-032).

**Portée** : disponibilité sur les bougies seules, « parcours sans position ». Aucun tick lu,
aucune entrée simulée, aucun résultat de performance, aucun entraînement, aucune donnée 2022-2025.
Paramètres de la fiche figée (ADR-028), inchangés.

> **Une sortie confirmée n'est pas une entrée.** C'est un instant `D` où le passage de performance
> évaluerait une entrée, sous réserve de la suspension de la recherche pendant une position. Les
> refus à `D`, les entrées, les expirations et les sorties de position ne sont pas mesurés ici.

## 1. Passage

| Élément | Valeur |
|---|---|
| Commit | `eb48d6c57a035e34d2bb0c50f85a9fa8320d8280`, branche `docs/day02-availability-protocol`, arbre propre au lancement et à la fin, aucun fichier modifié pendant le passage |
| Commande | `uv run forex-day02-availability --out data/reports/backtests/day02_availability_2015_2021_eb48d6c.json --details-out data/reports/backtests/day02_availability_2015_2021_eb48d6c_details.jsonl` |
| Lancement / fin (UTC) | 2026-11-07 17:06:49 / 17:23:40, code de sortie 0 |
| Fenêtre | officielle, [2015-01-01, 2022-01-01) ; H1 lues depuis le 2015-01-01 (amorçage compté) |
| Trajectoires | référence `Day02Params()` (H1 → M15 → M5) et comparaison `Day02Params(trigger=Trigger.M15)` (H1 → M15), seul `trigger` diffère |
| Entrées lues | 523 566 M5, 174 525 M15, 43 630 H1, 383 trous ; **0 tick** |

**Empreintes des entrées** (complètes, identiques avant et après le passage) :

| Entrée | Empreinte | Référence |
|---|---|---|
| `intraday_2015_2021_day01_5min/5m.parquet` | `9438774154972aafa2cc924cf6042e6ae2b3c97de23328644b7d54f3af50fb82` | égale à la sortie de l'audit à 5 min |
| `intraday_2015_2021_day01_5min/15m.parquet` | `64b305201c2f8e48afd257048e07800cea1778e17228673b4c4af7c6a86a9db2` | égale à la sortie de l'audit à 5 min |
| `1h.parquet` | `a7c7f8b82ac55828bbbc25b8fd87c64cac99efb5a977187c47b381480802c585` | égale aux `existing_bars_sha256` des deux audits intraday |
| `quality_dukascopy_EURUSD.json` | `0cdcebee453a60e7a2b380393487a001dc70b7cd7d814f003731ce79b14fd6b9` | **aucune référence historique** |

**Limite conservée** : aucun audit n'a enregistré l'empreinte du rapport de qualité. Les 383 trous
chargés jusqu'au 2022-01-01, identiques au nombre des passages DAY_01, sont un **contrôle de
nombre**, **pas une preuve d'identité** du contenu historique de ce rapport.

Sorties hors Git (ADR-014), sous `data/reports/backtests/` :

| Fichier | SHA-256 |
|---|---|
| `day02_availability_2015_2021_eb48d6c.json` (agrégé) | `6fa091af…5fc5` |
| `day02_availability_2015_2021_eb48d6c.md` (agrégé) | `8ddf86e3…5504` |
| `day02_availability_2015_2021_eb48d6c_details.jsonl` (3 632 lignes : 1 816 séances × 2 trajectoires) | `775e4bba…9ddc` |

## 2. Contrôles bloquants

Tous conformes, 0 écart.

| Contrôle | Résultat |
|---|---|
| C1 Calendrier | 1 827 jours ouvrés, 11 exclusions (25/12, 1/1), **1 816 séances** = ancrage ; dates du calendrier égales à la sélection du moteur |
| C2 Conservation | entrées = issues + passages à chaque étape ; une configuration au plus par recherche, seule la dernière recherche d'une séance sans configuration |
| C3 Reprises | première reprise à 07:00 (`début de séance`) ; chaque reprise suivante = fin de la configuration précédente (`D` pour une sortie confirmée) avec sa cause |
| C4 Bornes | conformes sur les configurations valides ; les abandons (dont 572 impulsions prolongées) sont des issues |
| C5 Bougies non réutilisées | 0 M15 servant deux configurations ; aucune M15 commencée avant sa reprise |
| C6 Recalcul distinct | première configuration de chaque séance (séances sans configuration comprises) : reconnaissance et formation identiques ; portée : recalcul distinct de la reconnaissance et de la formation, **ATR H1 partagé** |
| C7 Étapes communes M5 / M15 | M15 examinées et parcours avant `F` identiques pour les 1 816 premières recherches |
| C8 ATR H1 | lu sur la dernière H1 terminée au plus tard au début de la fenêtre d'impulsion |
| C9 Entrées et paramètres | 0 tick ; aucune bougie au-delà du 2022-01-01 ; empreintes complètes conformes, inchangées ; 383 trous ; seul `trigger` diffère |
| C10 Provenance | arbre propre au lancement, aucun changement pendant le passage |

## 3. Parcours (issues exclusives, dénominateurs)

| Étape (dénominateur) | Issue | M5 | M15 |
|---|---|---:|---:|
| Séances | — | 1 816 | 1 816 |
| Recherches (par séance : 1 + configurations) | — | 4 541 | 4 536 |
| M15 examinées | non reconnues | 29 228 | 29 163 |
| | **impulsion reconnue** (configuration) | **2 725** | **2 720** |
| Configurations | données inutilisables pendant le drapeau | 2 | 2 |
| | repli trop profond (avant `F`) | 996 | 993 |
| | impulsion prolongée sans pause | 572 | 572 |
| | fin de fenêtre (drapeau non formé à 14:45) | 146 | 145 |
| | **drapeau formé** | **1 009** | **1 008** |
| Drapeaux formés | repli trop profond (après `F`) | 407 | 413 |
| | consolidation trop longue (expiration à `fin(p) + 90 min`) | 216 | 241 |
| | fin de fenêtre (expiration à 15:00) | 79 | 82 |
| | **sortie confirmée** (instant `D`, pas une entrée) | **307** | **272** |

Taux, avec leur dénominateur (M5) : 8,5 % des M15 examinées reconnaissent une impulsion (2 725 /
31 953) ; 37,0 % des configurations forment un drapeau (1 009 / 2 725) ; 30,4 % des drapeaux formés
donnent une sortie confirmée (307 / 1 009), soit 11,3 % des configurations.

**Par séance** (M5) : configurations 0 / 1 / 2 / 3 / 4 = 197 / 736 / 668 / 207 / 8 séances ; sorties
confirmées 0 / 1 / 2 = 1 521 / 283 / 12 séances. M15 : configurations 197 / 738 / 669 / 204 / 8 ;
sorties 1 551 / 258 / 7.

**Par sens** : configurations M5 1 302 achats, 1 423 ventes ; sorties confirmées 136 achats, 171
ventes (M15 : 119 et 153).

**Par année** (M5 ; M15 entre parenthèses quand il diffère) :

| Année | Séances | Recherches | M15 examinées | Configurations | Drapeaux formés | Sorties confirmées |
|---|---:|---:|---:|---:|---:|---:|
| 2015 | 259 | 660 (658) | 4 452 (4 444) | 401 (399) | 146 | 46 (40) |
| 2016 | 260 | 602 | 4 867 (4 864) | 342 | 132 | 36 (32) |
| 2017 | 259 | 617 (616) | 4 687 (4 668) | 358 (357) | 141 (140) | 48 (39) |
| 2018 | 259 | 672 | 4 403 (4 379) | 413 | 162 | 47 (40) |
| 2019 | 259 | 638 (637) | 4 652 (4 651) | 379 (378) | 142 | 41 (36) |
| 2020 | 260 | 678 | 4 405 (4 401) | 418 | 145 | 44 (43) |
| 2021 | 260 | 674 (673) | 4 487 (4 476) | 414 (413) | 141 | 45 (42) |

**Par heure légale** (M5) : GMT 626 séances, 888 configurations, 99 sorties ; BST 1 070, 1 636, 185 ;
semaines de décalage 120, 201, 23. Sorties confirmées par heure de `D` à Londres (M5) : 08 h 9,
09 h 70, 10 h 65, 11 h 48, 12 h 30, 13 h 33, 14 h 45, 15 h (15:00 exactement) 7.

## 4. Causes de non-reconnaissance (M5, 29 228 M15 non reconnues)

Communes aux deux sens : ATR H1 non calculable 378 ; M15 absente ou non `OK` dans la fenêtre 2.
Les 28 848 autres ont une cause par sens :

| Cause (première dans l'ordre de la fiche) | Hausse | Baisse |
|---|---:|---:|
| ordre des extrêmes non établi (`o ≥ p`) | 15 379 | 15 021 |
| sommet antérieur à la dernière bougie (`p < j`) | 5 164 | 5 288 |
| amplitude insuffisante | 8 209 | 8 461 |
| clôture non forte | 96 | 78 |

M15 : mêmes ordres de grandeur, 29 163 non reconnues dont 378 ATR et 2 fenêtres.

**ATR H1 indisponible** (378 M15 examinées dans chaque trajectoire, sur 16 séances) :

| Cause | M15 examinées | Séances |
|---|---:|---:|
| amorçage : historique H1 initial insuffisant | 24 | 1 (2015-01-02) |
| interruption : H1 inutilisable | 354 | 15 |
| H1 prévue absente | 0 | 0 |
| non déterminée | 0 | 0 |

Séances avec interruption : 2015-12-28, 2016-09-05, 2016-12-27, 2017-12-26, 2018-12-26, 2019-01-02,
2019-05-27, 2019-12-26, 2020-02-12, 2020-09-10, 2020-12-28, 2021-02-09, 2021-04-21, 2021-04-27,
2021-05-04. Sept d'entre elles suivent un 25 décembre ou un 1er janvier : les H1 de ces jours fériés
probables sont inutilisables selon la convention H1 existante (aucune fermeture documentée), et
l'ATR doit se reconstituer sur 15 H1. Ce bilan ne qualifie pas davantage les autres dates ; la
convention H1 n'est pas modifiée.

## 5. Mesures structurelles (M5 ; domaine et absences)

Quartiles « min / q1 / médiane / q3 / max ».

| Mesure | Domaine (n) | Valeurs | Absences |
|---|---|---|---|
| `A` (pips) | configurations (2 725) | 4,0 / 9,9 / 12,4 / 15,5 / 70,6 | 0 |
| `I` (pips) | configurations | 6,4 / 23,7 / 31,6 / 43,3 / 370,4 | 0 |
| `I / A` | configurations | 1,52 / 2,06 / 2,46 / 3,10 / 26,5 | 0 |
| impulsion à la reconnaissance (M15) | configurations | 2 / 3 / 4 / 4 / 4 | 0 |
| impulsion finale (M15) | configurations | 2 / 4 / 5 / 6 / 8 | 0 |
| extensions | configurations | 0 / 0 / 1 / 2 / 5 | 0 |
| pente du drapeau (× `A`) | drapeaux formés (1 009) | −1,40 / −0,22 / −0,02 / 0,21 / 2,54 | 1 716 terminées avant `F` |
| profondeur sur le bid (× `I`) | drapeaux formés (1 009) | 0,16 / 0,37 / 0,47 / 0,54 / 3,47 | 1 716 terminées avant `F` |
| extrême ask du stop à la vente (prix) | sorties confirmées à la vente (171) | 1,03945 / 1,10610 / 1,13167 / 1,17585 / 1,24891 | 885 avant `F`, 367 sans sortie |
| `D − F` (M5) | sorties confirmées (307) | 1 / 2 / 4 / 7 / 12 | 1 716 avant `F`, 702 sans sortie |
| `D − fin(p)` (min) | sorties confirmées | 35 / 40 / 50 / 65 / 90 | idem |
| `E − S` (pips) | sorties confirmées | 4,3 / 11,1 / 14,2 / 18,5 / 56,8 | idem |
| `E − S` (× `A`) | sorties confirmées | 0,62 / 1,02 / 1,14 / 1,32 / 2,55 | idem |
| `T − E` (pips) | sorties confirmées | 6,4 / 24,1 / 30,2 / 41,3 / 146,2 | idem |
| approché : clôture de sortie − `S` (pips) | sorties confirmées | 6,1 / 14,1 / 18,2 / 23,2 / 123,7 | idem |
| approché : `T` − clôture de sortie (pips) | sorties confirmées | −67,5 / 20,8 / 25,8 / 36,2 / 137,9 | idem |

- La profondeur au-delà de 0,5 vient des drapeaux invalidés après `F` (la bougie qui invalide est
  comprise) ; les sorties confirmées ont toutes une profondeur d'au plus 0,5 par construction.
- **Indicateurs approchés** : mesurés depuis la clôture de la bougie de sortie, pas depuis la
  cotation à `D`, dont l'égalité n'est pas supposée. Une seule clôture de sortie est déjà au-delà
  de `T` (M5 comme M15). Aucune admissibilité de stop, aucune taille, aucun coût ni rapport à `D`
  n'est mesuré ici.
- M15 : distributions de `A`, `I`, `I / A`, impulsions, pente et `E − S` quasi identiques ;
  `D − F` de 1 à 4 M15 (médiane 2), `D − fin(p)` de 45 à 90 min (médiane 60).

## 6. Couverture

| Fenêtre | Unité | Créneaux | Non `OK` | Causes |
|---|---|---:|---:|---|
| nécessaire 07:00-15:00 | M15 | 58 112 | 8 | silence > 5 min 5, sans tick 3 |
| | M5 | 174 336 | 16 | sans tick 13, silence > 5 min 3 |
| complète 07:00-17:00 | M15 | 72 640 | 10 | silence > 5 min 7, sans tick 3 |
| | M5 | 217 920 | 18 | sans tick 13, silence > 5 min 5 |

**Silences de plus de 5 min** (d'ouverture prévue, lus sur les M5 du lot audité, premier et dernier
ticks valides) : fenêtre nécessaire 3 silences distincts, 3 intersections silence–séance,
77,0 min, 3 séances ; fenêtre complète 5 silences distincts, 5 intersections, 88,2 min, 5 séances.
Aucun silence ne traverse ici plus d'une fenêtre.

## 7. Différences M5 / M15

Rapprochement par date de Londres depuis le détail local (1 816 dates de chaque côté, sans doublon).

- **Avant `F`** : identiques pour toutes les séances (contrôle C7) : 197 séances sans configuration,
  1 031 premières configurations terminées avant `F`, avec la même issue.
- **Première configuration ayant formé un drapeau** (588 séances) :

  | M5 \ M15 | sortie confirmée | pas de sortie |
  |---|---:|---:|
  | sortie confirmée | 150 | 27 |
  | pas de sortie | 0 | 411 |

  Les 27 sorties M5 sans sortie M15 se terminent en M15 par consolidation trop longue (21), repli
  trop profond (4) ou fin de fenêtre (2). Aucune sortie M15 sans sortie M5.
- **Écart d'instant** `D(M15) − D(M5)` sur les 150 sorties communes : 0 min 52, 5 min 34, 10 min 50,
  20 min 3, 25 min 8, 40 min 1, 50 min 2 ; jamais négatif.
- **Configurations suivantes** : elles dépendent de l'instant de reprise (`D`), qui diffère entre
  trajectoires : 1 811 séances ont le même nombre de configurations, 5 en ont une de moins en M15.
  Les totaux 307 / 272 sorties confirmées ne sont pas un rapprochement exact.

## 8. Lecture et limites

- Le parcours sans position **ne simule pas** la suspension de la recherche pendant une position :
  les configurations au-delà de la première de chaque séance, et donc les totaux, **ne sont pas
  attendus égaux** à ceux du passage de performance (protocole §7). Seule la première configuration
  de chaque séance est comparable à l'identique.
- 307 sorties confirmées en M5 et 272 en M15 sont des instants `D`, **pas des entrées** : les refus à
  `D` (cotation, stop admissible, cible déjà dépassée, taille) ne sont pas évalués.
- Couverture élevée dans les deux fenêtres (moins de 0,02 % de bougies non `OK`) ; l'indisponibilité
  de l'ATR touche 16 séances, dont 7 au lendemain d'un jour férié probable, conséquence de la
  convention H1 existante.
- Empreinte du rapport de qualité sans référence historique : 383 trous est un contrôle de nombre,
  pas une preuve d'identité (§1).
- Aucun calendrier d'annonces : la part des impulsions liées à une publication n'est pas mesurable.
- Aucun paramètre n'est modifié d'après ces descriptions ; aucune donnée 2022-2025.

## 9. Reproduction depuis le détail local (hors Git)

```python
import json
from collections import Counter

path = "data/reports/backtests/day02_availability_2015_2021_eb48d6c_details.jsonl"
lines = {}
for n, raw in enumerate(open(path, encoding="utf-8"), 1):
    d = json.loads(raw)
    key = (d["day"], d["trigger"])
    if key in lines:
        raise SystemExit(f"doublon {key}")
    lines[key] = d
assert n == len(lines) == 3632 and len({k[0] for k in lines}) == 1816
for trigger in ("M5", "M15"):
    ends = Counter(
        s["configuration"]["outcome"]
        for (day, t), d in lines.items() if t == trigger
        for s in d["searches"] if s["configuration"]
    )
    print(trigger, sum(ends.values()), dict(ends))
```
