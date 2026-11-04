# S2 — Étape 4 : premier passage de performance 2015-2021, bilan

**Statut** : passages du 2026-11-04, autorisés par l'opérateur (fiche S2 §9, étape 4), selon le
protocole `docs/experiments/S2_REFERENCE_2015_2021.md` figé et poussé avant tout lancement
(commit `c35d565`). Aucun paramètre modifié après lecture des résultats. Ni validation de
performance, ni autorisation de trading. **Bilan validé par l'opérateur le 2026-11-04 (ADR-016)** :
S2 est étudiée sur la partition de développement, résultats insuffisants pour conclure.

## 1. Provenance et passages lancés

- **Code** : commit `c35d5658a25d5a3d164b7afd09f44824a089f7d6` (branche
  `feat/s2-reference-2015-2021`), arbre propre (aucun diff non commité, enregistré dans chaque
  rapport) ; copie du protocole et diff vide à côté des sorties.
- **Commandes** : celles du §5 du protocole, `--trigger H1` puis `--trigger H4`, `--scenario A`.
- **Entrées** (identiques pour les deux) : 43 630 H1, 10 912 H4, 1 822 D1, 383 trous du rapport
  de qualité, 2 557 fichiers de ticks, 195 559 278 ticks, tous dans [2015-01-01, 2022-01-01).
  H1 : 5 465 s, 367 Mio ; H4 : 5 358 s, 343 Mio. Sorties et journaux hors Git
  (`data/reports/backtests/s2_ref_2015_2021_<h1|h4>_a*`).
- **Compteur annuel des cassures** : aligné après le bilan sur la définition de l'entonnoir (toute
  ligne avec une cassure détectée, y compris non évaluable ou pendant une position). Le compteur
  repris du rapport S1 ne comptait que les entrées décidées ou refusées. Vérifié sur les journaux
  locaux, sans nouveau passage : les totaux annuels sont inchangés (H1 20, 3, 14, 6, 3, 9, 11 = 66 ;
  H4 1, 0, 2, 0, 0, 0, 0 = 3), aucune cassure de ces passages n'étant non évaluable ou pendant
  une position.

**Conditions du §4 du protocole, évaluées sur les passages A :**

| Déclenchement | Transactions indéterminées | Stop dépassé au premier tick d'exécution | B | C | Rejet |
|---|---:|---:|---|---|---|
| H1 (référence) | 0 | 0 | non lancé | non lancé | non lancé |
| H4 (comparaison) | 0 | 0 | non lancé | non lancé | non lancé |

Aucun trou de cotation inexpliqué n'est tombé pendant une position : les trajectoires B et C
seraient identiques à A par construction. Seul le scénario A existe donc pour chaque
déclenchement.

## 2. Des cassures aux positions (H1, référence)

| Étape | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Cassures détectées** | 20 | 3 | 14 | 6 | 3 | 9 | 11 | **66** |
| Non évaluables (données) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Pendant une position ouverte | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Refus : tendance D1 perdue | 5 | 1 | 0 | 2 | 0 | 4 | 1 | **13** |
| Refus : rapport gain/risque < 1 | 8 | 1 | 12 | 3 | 2 | 5 | 10 | **41** |
| Refus : marché fermé | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Refus : taille minimale | 5 | 0 | 0 | 0 | 0 | 0 | 0 | **5** |
| **Entrées décidées** | 2 | 1 | 2 | 1 | 1 | 0 | 0 | **7** |
| **Positions effectivement ouvertes** | 2 | 1 | 2 | 1 | 1 | 0 | 0 | **7** |

- Les 7 entrées décidées sont toutes devenues des positions ouvertes normalement : aucune
  exécutée puis liquidée, aucune cible atteinte au premier tick, aucune non exécutée, aucun
  rejet ni annulation.
- **Rapport gain/risque** : 41 refus, rapport médian 0,46 ; 21 sous 0,5 et 8 entre 0,9 et 1.
  Les journaux affichent alors des rapports comme « 1,00 < 1 », qui sont des valeurs juste
  inférieures à 1 arrondies à l'affichage. Le plus souvent, au moment de la cassure, le prix est
  déjà trop proche de la cible.
- **Taille minimale** : les 5 refus datent de 2015. Ils avaient tous un rapport d'au moins 1
  (1,01 à 2,69), mais une perte estimée au stop pour 0,1 contrat supérieure au budget de 0,25 %
  (environ 5 €), car le stop était large : ATR H4 élevé en 2015.
- **Entrées acceptées** : rapports de 1,03 à 3,61 ; toutes à la taille minimale de 0,1 contrat.

**Configurations** (H1) :

- 547 créées, dont 39 ont produit au moins une cassure.
- Devenir : 7 entrées décidées ; abandons pour repli trop profond (366), reprise sans entrée
  (164), expiration après 30 H4 (8) et données du repli incomplètes (2).
- Aucune n'est active à la fin. En plus, 4 configurations ont été refusées dès leur
  identification faute d'ATR H4.

## 3. Transactions et résultat (H1, référence)

Trajectoire continue, 2 000 € au départ, sans remise à zéro.

| Année (sortie) | Transactions | Gagnantes / perdantes | Brut (€) | Coûts (€) | Net (€) | Cible | Stop | Temps | Drawdown au tick intra-annuel (€) | Fonds propres fin d'année (€) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 2 | 1 / 1 | 3,75 | 0,25 | 3,50 | 1 | 1 | 0 | 6,16 | 2 003,50 |
| 2016 | 1 | 1 / 0 | 6,85 | 0,17 | 6,68 | 1 | 0 | 0 | 2,48 | 2 010,18 |
| 2017 | 2 | 1 / 1 | 5,54 | 0,25 | 5,29 | 1 | 1 | 0 | 3,65 | 2 015,47 |
| 2018 | 1 | 0 / 1 | −3,80 | 0,17 | −3,96 | 0 | 1 | 0 | 4,96 | 2 011,51 |
| 2019 | 1 | 0 / 1 | −2,44 | 0,17 | −2,61 | 0 | 1 | 0 | 3,02 | 2 008,90 |
| 2020 | 0 | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 008,90 |
| 2021 | 0 | — | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 008,90 |
| **Total** | **7** | **3 / 4** | **9,91** | **1,00** | **8,90** | **3** | **4** | **0** | **10,22** (global) | **2 008,90** |

- **Coûts** (1,00 €) :
  - glissement 0,35 USD ;
  - prime de stop garanti 0,48 USD (aux 4 sorties au stop) ;
  - financement 0,10 USD (une nuit, 2016) ;
  - commission 0 ;
  - frais de conversion 0,18 €.
- **Sorties** : 3 cibles, 4 stops observés, aucune sortie temporelle, aucune autre sortie. Durées
  de 3,8 h à 29,3 h ; 70,9 h en position sur sept ans.

| Décision (UTC) | Sens | Taille | Sortie | Net (€) | Multiple du risque estimé |
|---|---|---:|---|---:|---:|
| 2015-02-17 04:00 | achat | 0,1 | cible | 7,10 | +1,48 |
| 2015-10-02 04:00 | vente | 0,1 | stop | −3,61 | −0,97 |
| 2016-12-07 04:00 | achat | 0,1 | cible | 6,68 | +1,83 |
| 2017-03-15 06:00 | achat | 0,1 | cible | 8,78 | +3,16 |
| 2017-09-12 07:00 | achat | 0,1 | stop | −3,48 | −0,98 |
| 2018-08-22 07:00 | vente | 0,1 | stop | −3,96 | −0,98 |
| 2019-11-05 08:00 | achat | 0,1 | stop | −2,61 | −0,97 |

**Indicateurs de la trajectoire H1-A :**

| Indicateur | Valeur |
|---|---|
| Véritable drawdown relatif maximal au tick | **0,506 %** (10,22 €) : sommet 2 019,12 € le 2017-09-12 07:28:58 UTC, en cours de position ; creux 2 008,90 € le 2019-11-05 12:11:41 UTC ; sommet non retrouvé à la fin |
| Premier franchissement de 6 % | **aucun** |
| Net sans la meilleure transaction | **+0,13 €** (la meilleure, 2017-03-15, fait +8,78 € sur +8,90 €) |
| Cas indéterminés | **0** (aucun trou de cotation pendant une position) |
| Dépassements du budget de risque | 0 ; aucune perte au-delà de −1 fois le risque estimé |
| Multiples du risque | somme +2,57 ; moyenne +0,37 ; médiane −0,97 |

## 4. Déclenchement H4 (comparaison secondaire)

10 912 décisions ; 546 configurations créées, dont 3 avec une cassure.

Devenir des configurations : repli trop profond 371, reprise sans entrée 165, expiration 8,
données du repli incomplètes 2.

Les **3 cassures** (2015-04-21, 2017-03-01, 2017-10-05) sont toutes refusées pour rapport
gain/risque (0,60, 0,19, 0,48). Il n'y a donc aucune entrée.

Résultat sur la période : **0 transaction**, brut, coûts et net nuls, drawdown nul, aucun
franchissement de 6 %, aucun cas indéterminé ; aucun chevauchement possible avec S1.

Sur les décisions H4 avec une configuration active, un seuil de reprise n'est connu que sur
83 décisions (80 clôtures en deçà, 3 cassures), contre 1 029 en H1. Un pivot de reprise H4
se confirme plus tard ; la plupart des configurations s'abandonnent avant. Conformément au
protocole, H4 ne remplace pas la référence.

## 5. Chevauchement avec la référence S1

La référence S1 (`s1_ref_2015_2021_h0.json`, commit `d52f24f`, 53 transactions) est lue
seulement.

| | Valeur |
|---|---|
| Heures en position, S2 H1 | 70,9 h |
| Heures en position, S1 | 6 615,2 h |
| Heures où les deux sont en position | **0** (même sens 0, sens opposé 0) |
| Part du temps S2 chevauchant S1 | 0 % |
| Transactions S2 chevauchant une transaction S1 | 0 sur 7 |

Le résultat est recalculé indépendamment à partir des horaires d'entrée et de sortie des deux
listes de transactions, avec le même résultat. Avec 7 positions courtes, une absence totale de
chevauchement est compatible avec le hasard : S1 n'est en position qu'environ 11 % du temps.
On ne peut rien conclure sur la complémentarité des deux stratégies.

| Net annuel (€) | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 (référence) | 0 | −3,71 | +10,59 | +26,37 | −20,75 | +12,72 | −7,58 | +17,63 |
| S2 H1-A | +3,50 | +6,68 | +5,29 | −3,96 | −2,61 | 0 | 0 | +8,90 |

## 6. Écarts avec l'étape 3

Ces écarts ne sont pas des incohérences. L'étape 3 appliquait une convention d'étude : à la
cassure, sans cotation, la configuration était consommée dès que la tendance était présente et
le marché ouvert. Le moteur de performance va plus loin : stop, rapport gain/risque, taille,
exécution.

| | Étape 3 (`5922ecc`) | Étape 4 H1-A |
|---|---:|---:|
| Configurations identifiées | 556 | 547 |
| Cassures détectées | 48 | 66 |
| dont tendance D1 perdue | 10 | 13 |
| dont tendance présente et marché ouvert | 38 (configurations consommées par convention) | 53 (41 refus de rapport, 5 refus de taille, 7 entrées) |
| Configurations avec au moins une cassure | au moins 38 | 39 |
| Abandons pour données du repli incomplètes | 2 | 2 |
| Lignes de décision non évaluables | 460 sur créneaux attendus (+ 49 H1 hors calendrier) | 509 (= 460 + 49) |

- **Refus économiques** : un refus de rapport ou de taille laisse la configuration active, avec
  son seuil consommé. Elle peut produire une nouvelle cassure sur un seuil ultérieur.
  - Sur les 39 configurations qui ont produit au moins une cassure, 14 en ont produit plusieurs
    (jusqu'à 5).
  - 27 des 66 cassures sont des deuxièmes cassures ou plus : 15 refusées pour rapport, 9 pour
    tendance, 3 pour taille.
  - À l'étape 3, ces configurations auraient été consommées dès leur première cassure.
- **Moins de configurations** : une configuration restée active n'est remplacée que par un
  nouvel extrême au-delà de `E`, ce qui empêche d'en identifier d'autres. D'où 547 configurations
  au lieu de 556, et des cycles de vie différents ensuite.
- **Positions ouvertes** : 68 décisions H1 ont lieu pendant une position, et aucune cassure
  n'y tombe. Leur effet est seulement indirect.
- **Données** : inchangées. Les causes et les 2 abandons pour données sont les mêmes ; les 49 H1
  hors calendrier, comptées à part à l'étape 3, figurent ici dans les lignes non évaluables.

Les 38 configurations consommées de l'étape 3 ne sont pas reproduites et ne doivent pas l'être :
elles résultaient d'une convention sans cotation.

## 7. Lecture

- Le moteur H1 ouvre 7 positions en sept ans : 53 cassures avec tendance présente, dont 46 sont
  refusées par les règles économiques (41 pour rapport, 5 pour taille).
- Le net est de +8,90 € pour 2 000 €. Sans la meilleure transaction, il tombe à +0,13 €.
- Aucune transaction en 2020-2021.
- Le drawdown est faible (0,51 %), parce que l'exposition est rare et minimale.
- **Ces nombres ne permettent aucune conclusion statistique sur l'avantage de S2.** Ce n'est ni
  une validation, ni un rejet définitif.
- Toute suite (paramètres, `R_min`, déclenchement, autre stratégie) relève d'une décision de
  l'opérateur. Aucune modification n'est proposée ici à partir de ces résultats.
