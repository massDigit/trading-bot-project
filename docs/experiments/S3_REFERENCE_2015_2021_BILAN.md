# S3 — Étape 4 : premier passage de performance 2015-2021, bilan

**Statut** : passages du 2026-11-04, autorisés par l'opérateur (fiche S3 §9, étape 4), selon le
protocole `docs/experiments/S3_REFERENCE_2015_2021.md`, figé et poussé avant tout lancement
(commit `15d2c83`). Aucun paramètre modifié après lecture des résultats. Ni validation de
performance, ni autorisation de trading. **Bilan validé par l'opérateur le 2026-11-04 (ADR-020).**

## 1. Provenance et passages lancés

- **Code** : commit `15d2c838006a382a051f4c77a9d0fc96a2275725` (branche
  `docs/s3-step4-protocol`). Arbre propre : aucun diff non commité, enregistré dans chaque
  rapport. Moteurs S1, S2 et S3 inchangés depuis `main`.
- **Commandes** : celles du §10 du protocole, `--d1-filter on` (référence D1 → H4), puis
  `--d1-filter off` (comparaison H4 seule), `--scenario A`.
- **Entrées** (identiques pour les deux) : 10 912 H4, 1 822 D1, 383 trous du rapport de qualité,
  2 557 fichiers de ticks, 195 559 278 ticks, tous dans [2015-01-01, 2022-01-01).
  - D1 → H4 : 5 424 s, 284 Mio.
  - H4 seule : 5 408 s, 315 Mio.
  - Sorties et journaux hors Git : `data/reports/backtests/s3_ref_2015_2021_<d1h4|h4>_a*`.
- Étape 3 (`1be93fd`) et référence S1 (`d52f24f`, 53 transactions) lues seulement.

**Contrôles bloquants (§5 et §6 du protocole)** : tous réussis dans les deux passages.

| Contrôle | D1 → H4 | H4 seule |
|---|---|---|
| Boîtes : 160 de `F` distincts de chaque côté, identiques champ par champ (`BH`, `BL`, `AH`, `A`, fin, devenir) | 160 / 160 | 160 / 160 |
| Boîtes d'un seul côté ou différentes | 0 | 0 |
| Boîtes consommées rapprochées de leur décision de cassure (`F`, instant, sens) | 160 / 160 | 160 / 160 |
| Doublons (décisions de cassure, boîtes consommées, entrées, transactions par entrée) | 0 | 0 |
| Entrées décidées = transactions ; transactions sans entrée décidée | 5 = 5 ; 0 | 7 = 7 ; 0 |
| Parcours : une catégorie par cassure, aucun motif non classé, chaque entrée attestée | oui | oui |

**Conditions du §4 du protocole, évaluées sur les passages A :**

| Réglage | Franchissements non observables enregistrés | Stop dépassé au premier tick d'exécution | B | Rejet |
|---|---:|---:|---|---|
| D1 → H4 (référence) | 0 | 0 | non lancé | non lancé |
| H4 seule (comparaison) | 0 | 0 | non lancé | non lancé |

Aucun trou de cotation n'est tombé pendant une position (0 transaction indéterminée, aucun
événement de trou en position), et aucune position n'est ouverte à la fin. Seul le scénario A
existe donc pour chaque réglage.

## 2. Rapprochement avec l'étape 3

| | Étape 3 (`1be93fd`) | H4 seule | D1 → H4 |
|---|---:|---:|---:|
| Boîtes reconnues | 160 | 160 | 160 |
| Consommées par une cassure | 160 | 160 | 160 |
| Refus trop large (`BOÎTE_REFUSÉE`) | 41 | 41 | 41 |
| Décisions H4 | 10 896 créneaux attendus + 16 H4 hors calendrier | 10 912 | 10 912 |
| Compression non calculable | 575 | 563 | 563 |
| Bougie de décision inutilisable (`INTERRUPTION_INEXPLIQUÉE`) | 28 (12 sur calendrier, 16 hors calendrier) | 28 | 28 |
| Évaluation impossible, total | — | 591 | 651 |

- Les 575 décisions non calculables de l'étape 3 comprennent les 12 H4 inutilisables sur
  calendrier. Le moteur les classe d'abord comme bougie de décision inutilisable, avec les
  16 hors calendrier. 563 + 28 = 591 = 575 + 16.
- Les 60 évaluations impossibles supplémentaires de la référence sont les cassures bloquées par
  la règle stricte du contexte D1 (§3).
- Aucune cassure n'a eu lieu pendant une position ouverte.

## 3. Des cassures aux positions (D1 → H4, référence)

Le moteur contrôle chaque cassure dans cet ordre : disponibilité des données D1, puis expansion,
puis compatibilité de la direction D1, puis marché ouvert, puis taille
(`backtest/s3_engine.py`). **Chaque cassure est comptée à son premier blocage seulement.** Une
cassure bloquée à une étape n'est pas évaluée aux suivantes : elle aurait pu échouer aussi
plus loin.

| Étape | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Cassures (boîtes consommées)** | 18 | 23 | 27 | 24 | 26 | 24 | 18 | **160** |
| 1. Données D1 inutilisables (règle stricte, canal de 55 D1) | 5 | 12 | 6 | 3 | 12 | 12 | 10 | **60** |
| 2. Refus : pas d'expansion | 5 | 6 | 8 | 11 | 4 | 6 | 2 | **42** |
| 3. Refus : contexte D1 calculable, neutre ou contraire | 6 | 2 | 2 | 5 | 5 | 3 | 3 | **26** |
| 5. Refus : taille minimale | 2 | 2 | 11 | 5 | 3 | 3 | 1 | **27** |
| 4. Refus : marché fermé | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **Entrées décidées** | 0 | 1 | 0 | 0 | 2 | 0 | 2 | **5** |
| **Positions effectivement ouvertes** | 0 | 1 | 0 | 0 | 2 | 0 | 2 | **5** |

- 83 cassures haussières, 77 baissières.
- Les 5 entrées décidées sont toutes devenues des positions ouvertes normalement. Aucune n'a
  été exécutée puis liquidée, rejetée, annulée ou laissée sans tick.
- **Données D1** : 60 cassures sur 160 (37,5 %) tombent quand le canal de 55 D1 contient une D1
  inutilisable. Le moteur S1 applique alors sa règle stricte : évaluation impossible, pas un
  refus. Ces cassures ne sont évaluées ni sur l'expansion, ni sur la direction, ni sur la taille.
- **Blocages liés à D1** : 86 au total (60 données + 26 direction). Ils ne représentent pas
  86 entrées supplémentaires possibles sans D1. La comparaison H4 seule (§5) montre que la plupart
  de ces cassures échouent ensuite sur l'expansion ou la taille : sans D1, on passe de 5 à
  7 entrées.
- **Taille minimale** : budget de 0,25 % de 2 000 €, environ 5 €. Pour 0,1 contrat, cela
  correspond à un stop d'environ 53 pips au plus, coûts compris. Mesuré sur les 160 cassures
  du passage H4 seule :
  - les 79 refus de taille avaient une distance d'entrée au stop médiane de 90 pips (52,8 à
    272,3) ;
  - les 7 entrées acceptées, de 27,8 à 52,6 pips ;
  - la hauteur de boîte médiane était de 61 pips pour les refus de taille, contre 28 pour les
    entrées.

  Le stop de S3 (borne opposée moins 0,25 × A) s'ajoute à la hauteur de la boîte et au
  dépassement de la clôture de cassure. Avec ce capital, il dépasse donc souvent le budget.
- Toutes les entrées sont à la taille minimale de 0,1 contrat.

## 4. Transactions et résultat (D1 → H4, référence)

Trajectoire continue, 2 000 € au départ, sans remise à zéro.

| Année (sortie) | Transactions | Gagnantes / perdantes | Brut (€) | Coûts (€) | Net (€) | Sortie suiveuse | Stop | Drawdown au tick annuel (€) | Fonds propres fin d'année (€) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 0 | — | 0 | 0 | 0 | 0 | 0 | 0 | 2 000,00 |
| 2016 | 1 | 1 / 0 | 15,26 | 0,82 | 14,44 | 1 | 0 | 8,87 | 2 014,44 |
| 2017 | 0 | — | 0 | 0 | 0 | 0 | 0 | 0 | 2 014,44 |
| 2018 | 0 | — | 0 | 0 | 0 | 0 | 0 | 0 | 2 014,44 |
| 2019 | 2 | 0 / 2 | −5,55 | 0,21 | −5,76 | 2 | 0 | 8,87 | 2 008,68 |
| 2020 | 0 | — | 0 | 0 | 0 | 0 | 0 | 0 | 2 008,68 |
| 2021 | 2 | 0 / 2 | −2,87 | 0,19 | −3,06 | 2 | 0 | 4,88 | 2 005,62 |
| **Total** | **5** | **1 / 4** | **6,84** | **1,22** | **5,62** | **5** | **0** | **15,64** (global) | **2 005,62** |

- **Coûts** (1,22 €) :
  - glissement : 0,25 USD ;
  - financement : 1,00 USD (10 nuits) ;
  - commission : 0 ;
  - prime de stop garanti : 0, aucun stop atteint ;
  - frais de conversion : 0,12 €.
- **Sorties** : toutes par la sortie suiveuse (clôture H4 de l'autre côté de la moyenne). Aucun
  stop atteint. Les pertes restent entre −0,31 et −0,78 fois le risque estimé. Durées de 8 h à
  184 h, 248 h en position sur sept ans.

Meilleure transaction : +14,44 € (achat de mars 2016, +3,28 fois le risque estimé). Les
quatre autres sont perdantes. Le détail transaction par transaction reste dans les rapports
locaux.

**Retours vers la boîte** (description seulement, aucune sortie simulée) : les 5 positions ont
eu une réintégration, après 1 à 4 H4 (médiane 2). Aucune traversée ni position sans retour.
Toutes sont ensuite sorties par la sortie suiveuse, dont la gagnante de 2016.

**Indicateurs de la trajectoire D1 → H4 :**

| Indicateur | Valeur |
|---|---|
| Véritable drawdown relatif maximal au tick | **0,774 %** (15,64 €) : sommet 2 020,90 € le 2016-04-01 12:15:26 UTC, en cours de position ; creux 2 005,26 € le 2021-12-29 13:56:53 UTC ; sommet non retrouvé à la fin |
| Premier franchissement de 6 % | **aucun** |
| Net sans la meilleure transaction | **−8,82 €** (la meilleure, 2016-03-28, fait +14,44 € sur +5,62 €) |
| Espérance nette | +0,21 fois le risque estimé ; médiane −0,47 |
| Profit factor | 1,64 |
| Gain moyen / perte moyenne | +14,44 € / −2,21 € |
| Mois sans entrée | 79 sur 84 |
| Mois déficitaires | 2019-05, 2019-11, 2021-10, 2021-12 |
| Cas indéterminés | **0** |
| Dépassements du budget de risque | 0 |

## 5. H4 seule (comparaison secondaire)

Mêmes 160 cassures, sans contexte D1 : le premier motif bloquant devient l'expansion ou la
taille.

| Étape | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Cassures** | 18 | 23 | 27 | 24 | 26 | 24 | 18 | **160** |
| Refus : pas d'expansion | 7 | 8 | 12 | 13 | 11 | 14 | 8 | **73** |
| Refus : taille minimale | 11 | 13 | 15 | 11 | 13 | 10 | 6 | **79** |
| Refus : marché fermé à la décision | 0 | 1 | 0 | 0 | 0 | 0 | 0 | **1** |
| **Entrées décidées = positions ouvertes** | 0 | 1 | 0 | 0 | 2 | 0 | 4 | **7** |

- Les 7 transactions comprennent les 5 de la référence, identiques, et 2 transactions de plus
  en 2021 : une gagnante, une perdante, nettes ensemble de −0,25 €. Leur détail reste dans les
  rapports locaux.
- **Résultat** : brut +7,54 €, coûts 2,17 €, net **+5,37 €** (2 gagnantes, 5 perdantes ; toutes
  par la sortie suiveuse ; aucun stop).
- **Drawdown** : relatif maximal au tick de **0,786 %** (15,89 €), même sommet que la référence,
  creux le 2021-12-29. Aucun franchissement de 6 %.
- **Net sans la meilleure transaction** : −9,07 €.
- **Autres mesures** : espérance +0,14 fois le risque estimé ; profit factor 1,48 ; 488 h en
  position ; 77 mois sans entrée sur 84.

Conformément au protocole, cette comparaison ne remplace pas la référence. Les deux réglages ne
diffèrent que par deux transactions de 2021, de résultat opposé.

## 6. Comparaison à la référence S1

La référence S1 (`s1_ref_2015_2021_h0.json`, commit `d52f24f`, 53 transactions) est lue
seulement.

| | D1 → H4 | H4 seule |
|---|---:|---:|
| Entrées S3 décidées sur la même H4 et dans le même sens qu'un signal S1 | 1 sur 5 (20 %) | 3 sur 7 (43 %) |
| Transactions S3 chevauchant une transaction S1 | 4 sur 5 | 4 sur 7 |
| Heures de chevauchement, même sens / sens opposé | 55,6 h / 0 h (sur 248 h) | 55,6 h / 0 h (sur 488 h) |
| **Pertes S3 simultanées à une perte S1** | **4 sur 4** | **4 sur 5** |

| Net annuel (€) | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 (référence) | 0 | −3,71 | +10,59 | +26,37 | −20,75 | +12,72 | −7,58 | +17,63 |
| S3 D1 → H4 | 0 | +14,44 | 0 | 0 | −5,76 | 0 | −3,06 | +5,62 |
| S3 H4 seule | 0 | +14,44 | 0 | 0 | −5,76 | 0 | −3,31 | +5,37 |

Les quatre pertes de la référence S3 chevauchent toutes une transaction perdante de S1.

## 7. Lecture (règles du §9 du protocole)

- **Fréquence** : le moteur de référence ouvre 5 positions en sept ans sur 160 cassures. Les
  blocages, comptés au premier motif dans l'ordre du moteur, se répartissent ainsi :
  - 60 cassures sont bloquées par les données D1 (règle stricte de S1) ;
  - 42 faute d'expansion ;
  - 26 par un contexte D1 neutre ou contraire ;
  - 27 par la taille minimale.

  Les 86 blocages liés à D1 ne sont pas 86 entrées perdues : sans D1, on obtient 7 entrées au
  lieu de 5.

  Sans D1, la taille minimale devient le premier obstacle : 79 cassures sur 160. Au capital de
  2 000 € et au risque de 0,25 %, le stop structurel de S3 dépasse souvent le budget pour
  0,1 contrat.
- **Résultat** (règle 1) : le net de la référence est de +5,62 € pour 2 000 €, seul scénario
  publié (B et rejet sans objet). Il est strictement positif, mais repose sur une seule
  transaction (+14,44 €). Sans elle, il est de −8,82 € (règle 2 : indicateur, pas un motif de
  rejet automatique).
- **Drawdown** : 0,77 %, loin du seuil de revue de 6 %. Il reflète surtout une exposition rare et
  minimale, et le sommet de 2016 n'est pas retrouvé à la fin.
- **Redondance avec S1** (règle 3) : les 4 pertes de la référence sont toutes simultanées à une
  perte de S1, et 4 de ses 5 transactions chevauchent une transaction S1. Selon le protocole,
  quand les pertes S3 sont surtout simultanées à des pertes S1, la lecture est que S3 apporte
  peu par rapport à S1, quel que soit son net. La coïncidence des entrées reste faible (1 sur 5).
- **Effectif** (règle 4) : 5 transactions (7 sans D1). **Ces nombres ne permettent aucune
  conclusion statistique sur l'avantage de S3.** Ce n'est ni une validation, ni un rejet
  définitif.
- Toute suite relève d'une décision de l'opérateur : paramètres, règle D1 stricte, capital ou
  risque, abandon ou autre stratégie. Aucune modification n'est proposée ici à partir de ces
  résultats.
