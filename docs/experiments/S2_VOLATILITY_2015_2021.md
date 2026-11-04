# S2 — Étude descriptive : volatilité à la décision et distances cible / stop (EUR/USD 2015-2021)

**Statut** : méthode figée le 2026-11-04, **avant tout calcul**, à la demande de l'opérateur ;
résultats **validés par l'opérateur** le 2026-11-04 (ADR-017, conclusion retenue au §10).
Étude descriptive sur des sorties existantes ; ni backtest de performance, ni modification de
S2, ni entraînement, ni optimisation, ni lecture de 2022-2025. Elle porte sur EUR/USD seul : elle
ne peut ni désigner une meilleure paire, ni établir une rentabilité.

## 1. Question

Sur les 66 cassures H1 de S2 en 2015-2021, quand la volatilité était plus élevée à la décision,
restait-il davantage de distance jusqu'à la cible par rapport à la distance au stop ?

## 2. Observations

- **Les 66 cassures détectées** du passage de référence H1-A (commit `c35d565`, journal local
  `data/reports/backtests/s2_ref_2015_2021_h1_a_decisions.jsonl`, hors Git) : toutes les lignes de
  décision avec une cassure, quelle qu'en soit l'issue. Les 7 transactions exécutées ne sont pas
  sélectionnées à part.
- Pour chaque cassure, d'après le journal : l'instant de décision `D`, le sens, la dernière
  cotation strictement antérieure à `D` (bid, ask), la configuration (`E`, début de la bougie
  `E`, ATR figé `A`), l'issue de l'entrée. Pour les 53 cassures évaluées au-delà de la tendance :
  le stop et, pour celles qui l'ont atteint, le rapport gain/risque calculés par le moteur.
- Bougies H1, H4 et D1 et trous de cotation locaux, fenêtre [2015-01-01, 2022-01-01) ; aucun tick
  relu.

## 3. Mesures

Toutes les distances sont en pips (0,0001), au prix estimé d'entrée du moteur (S2 §6.1) : ask pour
un achat, bid pour une vente.

| Mesure | Définition |
|---|---|
| **Volatilité à la décision** | ATR Wilder 14 H4 **disponible à `D`** (dernière H4 disponible, règles et continuité de S2), en % du prix médian `(bid + ask) / 2` de la cotation. **Distincte** de l'ATR figé `A` |
| ATR figé `A` | valeur fixée à l'identification `I` de la configuration, en % du même prix ; rapportée à titre d'information, jamais utilisée pour former les groupes |
| Spread | `ask − bid` de la cotation |
| Distance à la cible | achat : `E − ask` ; vente : `bid − E` |
| Distance au stop | achat : `ask − stop` ; vente : `stop − bid` |
| Rapport des distances | distance à la cible / distance au stop, prix seuls, sans coûts |
| Rapport gain/risque | celui du moteur (S2 §6.1) : gain potentiel net / perte estimée au stop, coûts de recherche compris |

**Origine de chaque valeur, toujours indiquée** :
- **évaluée** : calculée par le moteur pendant le passage et lue dans le journal ;
- **reconstruite** : recalculée hors du passage, avec les mêmes fonctions et données, pour une
  cassure où le moteur s'est arrêté avant. C'est le cas des **13 cassures refusées pour perte de
  tendance D1** : le moteur n'a calculé ni leur stop ni leur rapport. Ces valeurs sont
  **hypothétiques** : elles ne sont jamais présentées comme des rapports évalués, ni mélangées à
  eux sans être signalées.

**Reconstruction** :
- stop = extrême du repli ± 0,25 × `A` (S2 §4.3, §4.5) : plus bas `bid_low` (achat) ou plus haut
  `ask_high` (vente) des H1 qui commencent à la fin de la bougie `E` ou après et sont disponibles
  à `D` ;
- rapport = fonction du moteur, avec la cotation du journal.

**Contrôle préalable** : la reconstruction est d'abord appliquée aux cassures évaluées. Elle doit
retrouver **exactement** chaque stop et chaque rapport du journal. Le moindre écart est rapporté,
et les valeurs reconstruites ne sont alors pas publiées.

## 4. Groupes de volatilité

- Les cassures dont la volatilité à `D` est calculable sont classées par ordre croissant de cette
  volatilité. Une égalité est départagée par l'instant de décision.
- Elles sont réparties en **trois groupes de taille égale par rang** (terciles) : faible, moyenne,
  élevée. Avec 66 valeurs : 22 par groupe. Si le nombre n'est pas divisible par 3, les groupes
  extrêmes reçoivent le reste, à parts égales autant que possible, en commençant par le groupe
  élevé.
- Les cassures sans volatilité calculable à `D` sont comptées à part.
- Aucun seuil n'est choisi ni ajusté. Les bornes des groupes sont rapportées pour la description
  seulement ; elles ne servent à rien d'autre.

## 5. Rapporté par groupe

- Nombre de cassures ; bornes de volatilité ; médiane de l'ATR figé `A`.
- Issue au moteur : entrées décidées, refus de tendance, de rapport, de taille.
- Médianes de : spread, distance à la cible, distance au stop, rapport des distances.
- Médiane des rapports gain/risque **évalués** (seulement ceux calculés par le moteur).
- Médiane des rapports **reconstruits** (13 refus de tendance), séparément.
- Médiane sur l'ensemble des 66 rapports, en indiquant combien sont reconstruits.
- Pour chaque mesure, **le nombre de valeurs disponibles** et l'**intervalle interquartile**.

## 6. Règle de lecture, fixée avant le calcul

La mesure principale est la médiane du **rapport des distances**, sur les 66 cassures. Les
distances incluent les valeurs reconstruites, signalées.

- **« La cible était relativement plus éloignée »** si cette médiane **croît** du groupe faible
  au groupe moyen puis au groupe élevé, **et** si la médiane du groupe élevé est **hors de
  l'intervalle interquartile** du groupe faible.
- **« Le stop était surtout plus large »** si cette médiane **décroît** de façon monotone, avec
  la même condition sur les intervalles. Le constat est le même si la distance au stop croît
  nettement plus vite que la distance à la cible.
- **Sinon : les observations ne permettent pas de trancher.**

Les rapports gain/risque évalués servent de contrôle. S'ils contredisent la mesure principale,
c'est dit. Avec environ 22 cassures par groupe, l'étude est descriptive : aucun test de
signification n'est présenté comme une preuve.

## 7. Sorties

- Outil `forex-s2-volatility` : lecture seule du journal et des bougies, aucune décision rejouée.
- Détail par cassure dans `data/reports/backtests/s2_volatility_2015_2021_details.jsonl`, hors
  Git.
- Tableau agrégé dans ce document après le calcul.

## 8. Résultats (calculés après le gel de la méthode)

**Provenance** :
- méthode figée au commit `5e803de`, avant tout calcul ;
- outil au commit `42f0f6e`, arbre propre ;
- commande :
  `uv run forex-s2-volatility --journal data/reports/backtests/s2_ref_2015_2021_h1_a_decisions.jsonl --out data/reports/backtests/s2_volatility_2015_2021.json --details-out data/reports/backtests/s2_volatility_2015_2021_details.jsonl` ;
- durée 8 s ; détails hors Git.

**Contrôle de la reconstruction** : sur les 53 cassures évaluées, la reconstruction retrouve
**exactement** chaque stop et chaque rapport du journal (0 écart). Les 13 refus de tendance ont des
valeurs reconstruites, signalées ci-dessous. La volatilité à la décision est calculable pour les
66 cassures.

Volatilité et ATR en % du prix ; distances et spread en pips ; médianes, avec l'intervalle
interquartile entre crochets ; `n` = nombre de valeurs.

| | Faible | Moyenne | Élevée | Toutes |
|---|---|---|---|---|
| Cassures | 22 | 22 | 22 | 66 |
| ATR H4 à la décision (bornes du groupe) | 0,146 – 0,221 | 0,222 – 0,316 | 0,345 – 0,729 | 0,146 – 0,729 |
| ATR figé `A` (médiane, n = 22 / 22 / 22 / 66) | 0,186 | 0,272 | 0,461 | 0,272 |
| Années des décisions | 2016 : 1 ; 2017 : 3 ; 2019 : 3 ; 2020 : 7 ; 2021 : 8 | 2015 : 1 ; 2016 : 1 ; 2017 : 9 ; 2018 : 6 ; 2020 : 2 ; 2021 : 3 | **2015 : 19** ; 2016 : 1 ; 2017 : 2 | |
| Issue : entrées / refus tendance / refus rapport / refus taille | 1 / 6 / 15 / 0 | 4 / 2 / 16 / 0 | 2 / 5 / 10 / 5 | 7 / 13 / 41 / 5 |
| Spread (n = 22 / 22 / 22 / 66) | 0,3 [0,2 – 0,3] | 0,3 [0,2 – 0,4] | 0,3 [0,2 – 0,4] | 0,3 [0,2 – 0,4] |
| Distance à la cible (n = 22 / 22 / 22 / 66) | 25,1 [19,1 – 51,6] | 29,8 [18,8 – 44,0] | 80,8 [40,2 – 162,2] | 40,9 [20,5 – 69,2] |
| Distance au stop (n = 22 / 22 / 22 / 66) | 38,6 [35,4 – 50,8] | 57,8 [41,7 – 70,0] | 99,7 [78,4 – 130,0] | 58,5 [39,0 – 89,0] |
| **Rapport des distances** (n = 22 / 22 / 22 / 66) | **0,90** [0,53 – 1,08] | **0,50** [0,27 – 1,02] | **0,89** [0,51 – 1,63] | 0,72 [0,33 – 1,14] |
| Rapport gain/risque **évalué** | 0,60 [0,37 – 0,87], n = 16 | 0,45 [0,23 – 0,93], n = 20 | 0,95 [0,45 – 1,48], n = 17 | 0,58 [0,31 – 0,99], n = 53 |
| Rapport gain/risque **reconstruit** (refus de tendance, hypothétique) | 1,33 [1,00 – 1,64], n = 6 | 0,27 [0,26 – 0,28], n = 2 | 0,73 [0,69 – 1,57], n = 5 | 0,97 [0,30 – 1,59], n = 13 |
| Rapport gain/risque, tous (dont reconstruits) | 0,78, n = 22 (6) | 0,43, n = 22 (2) | 0,84, n = 22 (5) | 0,67, n = 66 (13) |

Les distances au stop des 13 refus de tendance sont aussi reconstruites (6, 2 et 5 par groupe) ;
celles des 53 autres cassures sont évaluées.

## 9. Réponse

**Les observations ne permettent pas de trancher** (règle du §6). La médiane du rapport des
distances n'est pas monotone : 0,90, puis 0,50, puis 0,89. Celle du groupe élevé reste dans
l'intervalle interquartile du groupe faible.

Ce que montrent les chiffres, sans plus :
- **Les deux distances grandissent avec la volatilité** : de 25 à 81 pips jusqu'à la cible, de 39 à
  100 pips jusqu'au stop, entre les groupes faible et élevé. La cible n'est pas relativement plus
  éloignée, et le stop n'est pas relativement plus large : leur rapport médian est presque le même
  (0,90 et 0,89).
- **Le groupe moyen** a un stop plus large sans cible plus éloignée (rapport 0,50). Avec 22
  observations et des intervalles qui se recouvrent largement, ce creux n'est pas interprétable.
- Les rapports gain/risque **évalués** vont dans le même sens que le rapport des distances
  (0,60, 0,45, 0,95), avec les mêmes recouvrements. Ils ne permettent pas non plus de trancher.
- Le spread médian est le même dans les trois groupes (0,3 pip). Rapporté à des distances de 25 à
  100 pips, il ne départage pas les groupes.
- **Confusion avec l'année** : 19 des 22 cassures du groupe élevé datent de 2015. Le groupe faible
  vient surtout de 2020-2021. La volatilité ne peut pas être séparée ici de la période : ce qui
  distingue les groupes peut tenir à 2015 autant qu'à la volatilité.
- Les 5 refus pour taille minimale sont tous dans le groupe élevé (2015) : stop large, budget de
  0,25 %.

Cette étude porte sur EUR/USD seul, 66 cassures, et décrit l'échantillon. Elle ne désigne aucune
meilleure paire, n'établit aucune rentabilité et ne justifie aucun changement de paramètre de S2.

## 10. Conclusion retenue par l'opérateur (ADR-017)

« Sur les 66 cassures EUR/USD étudiées, la cible et le stop sont plus éloignés dans le groupe le
plus volatil, mais le rapport cible/stop ne s'améliore pas de façon régulière. »

Cela ne prouve ni que la volatilité est sans effet, ni qu'une autre paire serait préférable. S2
reste inchangée ; aucun autre calcul S2 n'est demandé.
