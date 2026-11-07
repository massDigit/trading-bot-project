# DAY_01 — passage de performance 2015-2021 : bilan agrégé

**Statut** : bilan des passages autorisés le 2026-11-07, soumis à revue. Protocole figé :
`docs/experiments/DAY01_REFERENCE_2015_2021.md` (commit `3d38ad5`).

**Portée** : recherche hors ligne sur la période de développement 2015-2021. Ni validation de
performance, ni autorisation de trading. Aucune donnée 2022-2025, aucun entraînement, aucun ordre.
Paramètres de la fiche (ADR-022) et coûts supposés figés, **inchangés après lecture des
résultats**.

> **Une confirmation n'est pas une entrée.** Les dénominateurs sont distingués à chaque étape :
> confirmations (instants `D`), entrées décidées, entrées exécutées, sorties. Les annotations
> recoupent les issues et ne sont jamais additionnées.

## 1. Passages

| Élément | Valeur |
|---|---|
| Commit | `3d38ad52bfb597808decc70e516e3e7fa3c324ba`, branche `docs/day01-performance-protocol`, arbre propre au lancement et à la fin, aucun fichier modifié pendant les passages |
| Passages | `m5_a` (référence) et `m15_a` (comparaison), lancés en parallèle le 2026-11-07 à 11:30:01 UTC, finis à 13:06:44 et 13:06:38 UTC (5 804 s et 5 797 s), code de sortie 0 |
| Commande | `uv run forex-day01-backtest --trigger M5 --scenario A --availability …/day01_availability_2015_2021_1c1ed0f_details.jsonl --s1-reference …/s1_ref_2015_2021_h0.json --s2-reference …/s2_ref_2015_2021_h1_a.json --s3-reference …/s3_ref_2015_2021_d1h4_a.json --out …/day01_ref_2015_2021_m5_a.json --sessions-out …/day01_ref_2015_2021_m5_a_sessions.jsonl` ; M15 : `--trigger M15`, sorties `m15_a` |
| Fenêtre | valeur par défaut, la fenêtre officielle : initialisation et début 2015-01-01, fin 2022-01-01 (enregistrée dans chaque rapport) |
| Configuration | scénario A (observé seulement), stop garanti, stop franchi à l'exécution : exécutée puis liquidée ; capital initial 2 000 €, risque 0,25 %, taille minimale et pas 0,1 contrat |
| Coûts supposés | glissement 0,5 pip, commission 0, financement 1 USD par contrat et par nuit, conversion 0,5 %, prime de stop garanti 1,2 USD par contrat (ASSUMED, non confirmés chez IG) |
| Entrées | 523 566 M5, 174 525 M15, 10 912 H4, 383 trous, 2 557 fichiers de ticks, 195 559 278 ticks lus ; empreintes identiques avant et après (5m `94387741…fb82`, 15m `64b30520…9db2`, 4h `081989d4…7989`) |
| Comparaison | `uv run forex-day01-compare --m5 …/day01_ref_2015_2021_m5_a_sessions.jsonl --m15 …/day01_ref_2015_2021_m15_a_sessions.jsonl --out …/day01_ref_2015_2021_compare_a.json`, code de sortie 0 |

Sorties hors Git (ADR-014), sous `data/reports/backtests/` :

| Fichier | SHA-256 |
|---|---|
| `day01_ref_2015_2021_m5_a.json` (agrégé) | `bff81694…bbbf` |
| `day01_ref_2015_2021_m5_a.md` (agrégé) | `ba3362f2…610f` |
| `day01_ref_2015_2021_m5_a_sessions.jsonl` (1 827 lignes, une par séance) | `8c48d5e3…9b12` |
| `day01_ref_2015_2021_m15_a.json` (agrégé) | `1baa13d4…6723` |
| `day01_ref_2015_2021_m15_a.md` (agrégé) | `ce78a3f1…3bec` |
| `day01_ref_2015_2021_m15_a_sessions.jsonl` (1 827 lignes) | `c370a837…36c1` |
| `day01_ref_2015_2021_compare_a.json` (une ligne par date de Londres) | `bc384403…ee41` |

## 2. Contrôles bloquants

Tous conformes pour les deux passages, aucun écart.

| Contrôle | M5 | M15 |
|---|---|---|
| Rapprochement avec l'étude de disponibilité (§5) : 1 827 dates, identiques champ par champ, 0 date propre à un côté | conforme, 831 confirmations | conforme, 736 confirmations |
| Parcours et exécution (§6) : chaque confirmation classée une fois, entrées décidées = somme des issues, une transaction par entrée exécutée, aucune sans entrée, une issue exclusive par entrée exécutée, sorties immédiates avec leur motif | conforme | conforme |
| Liquidations de 16:00 : grandeurs complètes, concordance avec le journal ; liquidation en attente à la fin | conforme ; aucune | conforme ; aucune |
| Bornes : une position à la fois, aucune exécution après 12:05 Londres, décisions dans `[K + unité, K + 60 min]` | conforme | conforme |
| Entrées : 0 tick hors fenêtre, empreintes inchangées, paramètres attendus (C9) | conforme | conforme |
| Provenance (C10) : commit et arbre au lancement, changements pendant le passage | conforme, aucun | conforme, aucun |

## 3. Conditions préenregistrées (§4)

Lues dans le passage A de chaque trajectoire, pour elle seule :

| Déclencheur | M5 | M15 |
|---|---|---|
| Transactions indéterminées (y compris position ouverte à la fin et liquidation en attente pendant un silence) | 0 | 0 |
| B et C requis | non | non |
| Stops dépassés à l'exécution | 0 | 0 |
| Passage de rejet requis | non | non |

**Aucun passage conditionnel n'a été lancé** : ni B, ni C, ni `--stop-at-execution REJECT`. La règle
de publication de C ne s'applique pas. Le scénario A est le seul scénario publié, pour les deux
trajectoires.

## 4. Des confirmations aux sorties

| Étape (dénominateur) | Issue | M5 | M15 |
|---|---|---:|---:|
| Confirmations | refus à `D` (position ouverte, marché fermé, cotation absente, stop non admissible, taille) | 0 | 0 |
| | entrée décidée | 831 | 736 |
| Entrées décidées | exécutée | 831 | 736 |
| | expirée, annulée pour interruption, stop ou cible atteint à l'exécution | 0 | 0 |
| Entrées exécutées | sortie liée au stop (`STOP_OBSERVÉ`) | 523 | 433 |
| | clôturée à la cible (`CIBLE`) | 299 | 280 |
| | clôturée par liquidation (`LIQUIDATION_16H`) | 9 | 23 |
| | ouverte à la fin de l'étude | 0 | 0 |

Annotations (non additives), dans les deux passages : indéterminée 0, `NUIT_NON_PRÉVUE` 0,
`LIQUIDATION_APRÈS_INTERRUPTION` 0, liquidation en attente à la fin 0. Aucune entrée non exécutée.

**Liquidations de 16:00** : 9 en M5, 23 en M15, toutes résolues, motif `LIQUIDATION_16H`, aucun
silence (nature `NONE`), aucune après interruption, aucune nuit non prévue. Délai après 16:00 : M5
de 0,019 s à 0,459 s (médiane 0,223 s), M15 de 0,009 s à 0,459 s (médiane 0,115 s).

## 5. Résultats

| Mesure | M5 (référence) | M15 (comparaison) |
|---|---:|---:|
| Transactions clôturées | 831 | 736 |
| Gagnantes / perdantes | 304 / 527 | 296 / 440 |
| Brut | −211,88 € | +23,94 € |
| Coûts | 374,83 € | 313,06 € |
| dont glissement | 161,20 USD | 138,85 USD |
| dont prime de stop garanti | 246,72 USD | 199,80 USD |
| dont commission, financement | 0 | 0 |
| dont conversion | 16,68 € | 16,12 € |
| **Net** | **−586,71 €** | **−289,12 €** |
| Solde final (= fonds propres) | 1 413,29 € | 1 710,88 € |
| Meilleure transaction | +8,75 € | +9,16 € |
| Net sans la meilleure | −595,47 € | −298,28 € |
| Espérance nette (multiples du risque) | −0,186 | −0,101 |
| Profit factor | 0,70 | 0,84 |
| Gain moyen / perte moyenne | 4,53 € / −3,72 € | 4,96 € / −3,99 € |
| Exposition | 1 121,7 h | 1 390,0 h |
| Mois sans opération / mois déficitaires (sur 84) | 0 / 66 | 0 / 49 |
| Dépassements du budget de risque (perte estimée au stop après exécution) | 12, au plus 0,17 € | 14, au plus 0,20 € |

Les coûts par poste en USD sont ceux du moteur avant conversion ; le total des coûts est en euros.

**Par année de sortie** :

| Année | M5 : transactions (gagnantes) | M5 : net | M5 : drawdown max | M15 : transactions (gagnantes) | M15 : net | M15 : drawdown max |
|---|---:|---:|---:|---:|---:|---:|
| 2015 | 109 (40) | −72,91 € | 132,04 € | 100 (42) | −16,26 € | 73,03 € |
| 2016 | 117 (45) | −67,78 € | 117,47 € | 100 (43) | −8,49 € | 72,12 € |
| 2017 | 125 (46) | −98,49 € | 135,64 € | 111 (42) | −82,38 € | 100,90 € |
| 2018 | 117 (41) | −91,74 € | 127,53 € | 102 (40) | −36,45 € | 82,19 € |
| 2019 | 115 (35) | −144,58 € | 164,84 € | 103 (38) | −81,10 € | 109,48 € |
| 2020 | 123 (47) | −58,33 € | 67,27 € | 103 (41) | −30,68 € | 43,06 € |
| 2021 | 125 (50) | −52,88 € | 77,04 € | 117 (50) | −33,76 € | 85,48 € |

Les sept années sont déficitaires dans les deux trajectoires. Le drawdown annuel part des fonds
propres du premier tick de l'année.

**Drawdown au tick** (continu depuis 2 000 €) :

| Mesure | M5 | M15 |
|---|---:|---:|
| Sommet | 2 050,35 € (2015-06-15) | 2 039,06 € (2015-06-24) |
| Drawdown maximal | 637,65 € | 329,24 € |
| Drawdown relatif maximal | 31,10 % (2021-12-07) | 16,15 % (2021-10-29) |
| Premier franchissement de 6 % (seuil de revue, la trajectoire continue) | 2015-12-09 | 2017-06-16 |
| Récupération du drawdown le plus profond | aucune à la fin de l'étude | aucune à la fin de l'étude |
| Plus longue récupération achevée | 114,9 jours (2015) | 101,8 jours (2015) |

## 6. Mesures par entrée (distributions, sans filtre)

| Mesure (dénominateur) | M5 : min / médiane / max | M15 : min / médiane / max |
|---|---|---|
| Distances estimées à `D` (entrées décidées) | 1,5 / 1,5 / 1,5 | 1,5 / 1,5 / 1,5 |
| Net estimé à `D` (entrées décidées) | 0,94 / 1,21 / 1,40 | 0,94 / 1,25 / 1,42 |
| Obtenu à l'exécution (entrées exécutées) | 1,32 / 1,50 / 1,64 | 1,35 / 1,50 / 1,66 |
| Distance du stop, pips | 3,8 / 9,3 / 34,7 | 3,8 / 10,9 / 47,2 |
| Distance du stop, multiples de `A` | 0,25 / 0,32 / 0,93 | 0,26 / 0,38 / 1,03 |
| Part des coûts fixes dans le risque (entrées exécutées) | 4,7 % / 15,4 % / 30,6 % | 3,5 % / 13,5 % / 30,6 % |

Aucune mesure absente (aucune entrée non exécutée, aucun risque non positif). Les définitions sont
celles du protocole §7 : la part des coûts fixes rapporte glissement, commission et prime de stop
garanti par contrat à la perte estimée au stop par contrat, conversion exclue.

## 7. Répartitions

| Répartition | M5 : exécutées (gagnantes), net | M15 : exécutées (gagnantes), net |
|---|---|---|
| Lundi | 178 (68), −109,99 € | 158 (64), −81,21 € |
| Mardi | 174 (50), −254,81 € | 148 (47), −174,68 € |
| Mercredi | 150 (54), −109,37 € | 132 (58), −7,31 € |
| Jeudi | 170 (75), +0,63 € | 158 (76), +72,69 € |
| Vendredi | 159 (57), −113,17 € | 140 (51), −98,61 € |
| Entrée 08 h Londres | 322 (118), −232,93 € | 197 (82), −64,43 € |
| Entrée 09 h | 312 (110), −248,14 € | 306 (111), −226,42 € |
| Entrée 10 h | 143 (56), −63,87 € | 162 (77), +51,74 € |
| Entrée 11 h | 54 (20), −41,78 € | 71 (26), −50,01 € |
| BST | 489 (169), −433,89 € | 432 (166), −242,94 € |
| GMT | 284 (109), −141,08 € | 250 (105), −51,33 € |
| GMT, semaines de décalage | 58 (26), −11,75 € | 54 (25), +5,16 € |
| Achat | 419 (142), −393,13 € | 367 (138), −231,68 € |
| Vente | 412 (162), −193,58 € | 369 (158), −57,44 € |

Description seulement : aucune répartition ne sert de filtre ni de réglage (§12 du protocole). Les
cases positives sont des sous-ensembles lus après coup, sans valeur de sélection.

## 8. Comparaison M5 / M15 (scénario A)

Rapprochement par date de séance de Londres, depuis les deux détails locaux (1 827 dates de chaque
côté, doublons refusés). Toutes les synthèses sont calculées depuis les lignes par date.

**Confirmations et exécutions** :

| | Communes | Propres à M5 | Propres à M15 |
|---|---:|---:|---:|
| Confirmations | 724 | 107 | 12 |
| Entrées exécutées | 724 | 107 | 12 |

Conforme à l'attendu du bilan de disponibilité (724 / 107 / 12). Toute confirmation a donné une
entrée exécutée, dans les deux trajectoires. Les séances communes ont le même sens.

**Différences de parcours** (issue M5 → issue M15, 144 séances) :

| M5 → M15 | Séances |
|---|---:|
| confirmation → invalidation après contact | 55 |
| confirmation → invalidation avant contact | 47 |
| confirmation → délai de contact sans confirmation | 5 |
| invalidation après contact → invalidation avant contact | 23 |
| invalidation après contact → confirmation | 6 |
| invalidation avant contact → confirmation | 6 |
| invalidation avant contact → invalidation après contact | 2 |

**Séances exécutées dans les deux (724)** :

| Écart M15 − M5 | Séances |
|---|---:|
| Entrée au même instant (écart < 30 s) | 148 |
| Entrée environ 5 min plus tard | 168 |
| Entrée environ 10 min plus tard | 373 |
| Entrée 12,5 à 30 min plus tard | 26 |
| Entrée 30 min plus tard ou davantage (au plus 50 min) | 9 |
| Stop identique | 425 |
| Taille identique / plus petite en M15 / plus grande en M15 | 248 / 246 / 230 |

Aucune entrée M15 n'est antérieure à l'entrée M5 de la même séance.

Issues des entrées exécutées communes (M5 → M15) :

| M5 \ M15 | sortie liée au stop | clôturée à la cible | clôturée par liquidation |
|---|---:|---:|---:|
| sortie liée au stop | 395 | 24 | 4 |
| clôturée à la cible | 33 | 250 | 9 |
| clôturée par liquidation | 0 | 1 | 8 |

**Nets par groupe de séances** :

| Groupe | Transactions (gagnantes) | Net M5 | Net M15 |
|---|---:|---:|---:|
| Séances communes | 724 (M5 297, M15 290) | −239,97 € | −295,44 € (écart −55,47 €) |
| Propres à M5 | 107 (7) | −346,74 € | — |
| Propres à M15 | 12 (6) | — | +6,32 € |
| **Total** | 831 / 736 | −586,71 € | −289,12 € |

Sur les séances communes, M15 perd davantage que M5. L'écart de net total entre les trajectoires
vient des 107 séances confirmées en M5 seulement (7 gagnantes, 100 sorties liées au stop), qui en
M15 finissent invalidées ou en délai. Chaque trajectoire a son propre capital et dimensionne sur
son propre solde : les tailles des séances communes ne sont pas indépendantes de l'historique de
chaque trajectoire.

La comparaison ne remplace pas la référence : M5 reste la référence préenregistrée ; aucune
trajectoire n'est choisie d'après ces résultats.

## 9. Chevauchement avec S1, S2 et S3 (description)

Trajectoires indépendantes, chacune avec son capital : **pas un portefeuille partagé**. Les nets
additionnés ne constitueraient pas l'évaluation d'un portefeuille commun, qui demanderait de
simuler conjointement décisions, capital et risque global.

| Référence (commit, transactions) | Trajectoire | Transactions DAY_01 chevauchantes | Pertes DAY_01 simultanées à une perte de la référence | Heures même sens / sens opposé |
|---|---|---:|---:|---|
| S1 (`d52f24f`, 53) | M5 | 78 / 831 | 29 / 527 | 45,5 / 44,7 |
| | M15 | 71 / 736 | 25 / 440 | 55,3 / 53,2 |
| S2 (`c35d565`, 7) | M5 | 1 | 1 | 4,9 / 0,0 |
| | M15 | 1 | 1 | 4,8 / 0,0 |
| S3 (`15d2c83`, 5) | M5 | 4 | 1 | 1,8 / 4,2 |
| | M15 | 3 | 0 | 2,2 / 3,9 |

Nets annuels côte à côte (€, 0 une année sans clôture) :

| Année | DAY_01 M5 | DAY_01 M15 | S1 | S2 | S3 |
|---|---:|---:|---:|---:|---:|
| 2015 | −72,91 | −16,26 | 0,00 | +3,50 | 0,00 |
| 2016 | −67,78 | −8,49 | −3,71 | +6,68 | +14,44 |
| 2017 | −98,49 | −82,38 | +10,59 | +5,29 | 0,00 |
| 2018 | −91,74 | −36,45 | +26,37 | −3,96 | 0,00 |
| 2019 | −144,58 | −81,10 | −20,75 | −2,61 | −5,76 |
| 2020 | −58,33 | −30,68 | +12,72 | 0,00 | 0,00 |
| 2021 | −52,88 | −33,76 | −7,58 | 0,00 | −3,06 |

Les pertes DAY_01 ne sont pas surtout simultanées à des pertes S1, S2 ou S3 (29 sur 527 en M5) :
c'est la conséquence de leur nombre et de la rareté des positions des références, pas un résultat
de diversification, puisque DAY_01 est déficitaire seul.

## 10. Lecture (§9 du protocole)

1. **Le net n'est pas positif** dans le seul scénario publié, ni en M5 (référence, −586,71 €,
   −29,3 % du capital initial) ni en M15 (−289,12 €). Les sept années sont déficitaires dans les
   deux trajectoires. Ce n'est pas un résultat favorable sur la période de développement.
2. Avant coûts, le brut est négatif en M5 (−211,88 €) et proche de zéro en M15 (+23,94 €) ; les
   coûts supposés (médiane de 15 % et 13 % du risque en coûts fixes) aggravent le résultat sans en
   être la seule cause en M5.
3. Le seuil de revue de 6 % de drawdown relatif est franchi dès 2015 en M5 et en 2017 en M15 ; le
   drawdown relatif maximal atteint 31,1 % en M5 et 16,1 % en M15, sans récupération à la fin.
4. Avec 831 et 736 transactions, l'échantillon n'est pas petit ; ce bilan ne fait toutefois aucun
   test statistique et n'en tire aucune conclusion statistique.
5. Aucun scénario B ou C n'était requis : le résultat ne dépend pas des trous de cotation au sens
   du §4 (aucune transaction indéterminée).
6. Les stops courts (médiane 9,3 pips en M5) sont simulés comme garantis sans minimum IG confirmé
   (ASSUMP-008) ; un stop garanti plus large ou indisponible changerait la taille et la prime, sans
   que ce bilan puisse le mesurer.
7. Aucun filtre d'annonces (fiche §3.4) : c'est une limite, pas une mesure.

**Aucun paramètre n'est modifié** d'après ces résultats. Les répartitions (§7), l'écart M5 / M15 et
les sous-ensembles positifs sont descriptifs ; en faire une variante serait un réglage après
lecture, exclu par le protocole (§12) et à décider, le cas échéant, par une nouvelle fiche
préenregistrée sur autorisation.

## 11. Limites

- Coûts supposés (ASSUMED), non confirmés chez IG : glissement, prime de stop garanti, conversion,
  financement.
- Stops garantis simulés sans distance minimale IG (ASSUMP-008).
- Scénario A seul : les franchissements non observables pendant un trou ne sont pas inventés ;
  aucune transaction concernée ici.
- Période de développement seulement ; la période réservée au test final n'est pas lue.
- Les comparaisons avec S1, S2 et S3 décrivent des trajectoires indépendantes, pas un portefeuille.

## 12. Reproduction des synthèses de la comparaison

Depuis les deux détails locaux hors Git (non publiés), par date de séance de Londres :

```python
import json
from decimal import Decimal

B = "data/reports/backtests/"
S = {}
for t in ("m5", "m15"):
    S[t] = {}
    for n, line in enumerate(open(B + f"day01_ref_2015_2021_{t}_a_sessions.jsonl"), 1):
        r = json.loads(line)
        if r["day"] in S[t]:
            raise SystemExit(f"doublon {t} {r['day']}")
        S[t][r["day"]] = r
    assert n == len(S[t]) == 1827
assert S["m5"].keys() == S["m15"].keys()
ex = {t: {d for d, r in S[t].items() if r["trade"]} for t in S}
groups = {
    "communes": ex["m5"] & ex["m15"],
    "propres M5": ex["m5"] - ex["m15"],
    "propres M15": ex["m15"] - ex["m5"],
}
for name, days in groups.items():
    for t in ("m5", "m15"):
        net = sum((Decimal(S[t][d]["trade"]["net_eur"]) for d in days if S[t][d]["trade"]), Decimal(0))
        print(name, t, len(days), round(net, 2))
```
