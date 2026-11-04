# S2 — Étude descriptive : volatilité à la décision et distances cible / stop (EUR/USD 2015-2021)

**Statut** : méthode figée le 2026-11-04, **avant tout calcul**, à la demande de l'opérateur.
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
