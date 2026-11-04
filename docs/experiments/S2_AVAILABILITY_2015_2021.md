# S2 — Étape 3 : disponibilité des données, développement 2015-2021

**Statut** : passage du 2026-11-04, autorisé par l'opérateur (fiche S2 §9, étape 3), rejoué
après la revue d'Astra. Aucun tick lu : aucune transaction, aucun gain ou perte, aucun drawdown.
Ni validation de performance, ni autorisation de trading. Bilan non figé avant la fin de la revue.

## 1. Commande et provenance

```
uv run forex-s2-availability --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 \
    --out data/reports/backtests/s2_availability_2015_2021_5922ecc.json \
    --details-out data/reports/backtests/s2_availability_2015_2021_5922ecc_details.jsonl
```

- **Code qui a produit les chiffres** : commit `5922eccaa35c7dfcc58566ca194b882d86b1acf3`
  (branche `feat/s2-data-availability`), arbre propre (aucun diff non commité).
- Entrées : 43 630 H1, 10 912 H4, 1 822 D1, 383 trous du rapport de qualité, 0 tick. 145 s, pic
  de mémoire 311 Mio. Sorties hors Git.
- Paramètres S2 approuvés (ASSUMP-025), déclenchement H1 (référence), latence 0, aucune
  fermeture particulière documentée (comme la référence S1).
- Le premier passage (`c86d59f`, fichiers `s2_availability_2015_2021.json` et `_details.jsonl`)
  est conservé tel quel ; il est remplacé par celui-ci (§5).

## 2. Méthode

- **Créneaux H1 attendus** : calculés à partir du calendrier. Un créneau est rattaché à la
  **journée de cotation ancrée à 17 h à New York**, lue à l'heure de début du créneau. Sont
  exclues les journées de cotation tombant un samedi ou un dimanche (fermeture hebdomadaire), et,
  par **convention de calcul** du moteur (`PROBABLE_HOLIDAY`), celles du 25 décembre et du
  1er janvier ; ce ne sont pas des fermetures confirmées. Un créneau appartient à l'année de son
  instant de décision (fin de la H1, latence 0), dans [2015-01-01, 2022-01-01).
- Chaque créneau attendu est dans une seule classe : **absent** (aucune H1, donc aucune ligne de
  journal) ; **présent non évaluable** (ligne `ÉVALUATION_IMPOSSIBLE`, cause = premier motif) ;
  **évaluable sans signal** (`AUCUN_SIGNAL`) ; **évaluable avec cassure détectée**.
- Les H1 présentes hors calendrier prévu sont comptées à part.
- **Cassure détectée** : configuration active après la mise à jour de son cycle de vie, contact
  depuis `I`, seuil de reprise connu, clôture bid de la H1 au-delà du seuil, aucun motif de
  données. Une cassure sur une bougie non `OK` ou sans D1 de contexte utilisable est une ligne
  non évaluable (§8).
- **Convention de l'étude** (le moteur de performance S2 n'est pas modifié) : à toute cassure
  détectée, le seuil est consommé. Si la tendance D1 requise est toujours présente et le marché
  ouvert à l'instant de décision, la configuration est **consommée par convention** ; sinon elle
  est conservée et le motif journalisé. Ni rapport gain/risque, ni taille, ni ordre, ni cotation.
- **Configurations** : identifiées, consommées par convention, conservées après refus
  structurel, et abandonnées pour données du repli incomplètes, rapportées à l'année de `I`,
  jamais ajoutées aux créneaux.
- Sans tick, aucune position n'est jamais ouverte. À l'étape 4, une cassure pendant une position
  ouverte n'est pas évaluée, et les refus économiques (rapport, taille) laissent la configuration
  active. L'effet de ces différences sur les nombres de l'étape 4 est inconnu à ce stade.

## 3. Créneaux H1

| Année | Attendus | Absents | Présents non évaluables | Évaluables sans signal | Cassures détectées | Présentes hors calendrier |
|---|---:|---:|---:|---:|---:|---:|
| 2015 | 6 216 | 0 (0,000 %) | 74 (1,190 %) | 6 129 (98,601 %) | 13 (0,209 %) | 10 |
| 2016 | 6 240 | 1 (0,016 %) | 51 (0,817 %) | 6 185 (99,119 %) | 3 (0,048 %) | 0 |
| 2017 | 6 216 | 0 (0,000 %) | 47 (0,756 %) | 6 159 (99,083 %) | 10 (0,161 %) | 9 |
| 2018 | 6 216 | 0 (0,000 %) | 23 (0,370 %) | 6 190 (99,582 %) | 3 (0,048 %) | 11 |
| 2019 | 6 216 | 2 (0,032 %) | 91 (1,464 %) | 6 120 (98,456 %) | 3 (0,048 %) | 10 |
| 2020 | 6 240 | 0 (0,000 %) | 74 (1,186 %) | 6 159 (98,702 %) | 7 (0,112 %) | 9 |
| 2021 | 6 240 | 0 (0,000 %) | 100 (1,603 %) | 6 131 (98,253 %) | 9 (0,144 %) | 0 |
| **Total** | **43 584** | **3 (0,007 %)** | **460 (1,055 %)** | **43 073 (98,828 %)** | **48 (0,110 %)** | **49** |

Réconciliation des 43 630 H1 lues (une ligne de décision chacune) : 43 584 créneaux attendus
− 3 absents = 43 581 H1 sur un créneau attendu, + 49 H1 hors calendrier prévu (toutes non
évaluables) = 43 630. Créneaux absents : 2016-09-02 18:00, 2019-05-26 21:00 et 22:00 UTC.

**Causes des 460 lignes non évaluables** (premier motif) :

| Cause | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D1 de contexte non utilisable | 47 | 48 | 46 | 23 | 90 | 70 | 96 | 420 |
| Initialisation : aucune D1 disponible | 23 | 0 | 0 | 0 | 0 | 0 | 0 | 23 |
| Bougie de déclenchement `INTERRUPTION_INEXPLIQUÉE` | 2 | 3 | 1 | 0 | 1 | 2 | 4 | 13 |
| Configuration refusée : ATR H4 indisponible à `I` | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 4 |

Une D1 de contexte non utilisable bloque toutes les H1 jusqu'à la D1 suivante. Ces lignes se
concentrent sur 16 épisodes, surtout au lendemain des jours de la convention (26-28 décembre,
2 janvier), et sur quelques interruptions (2015-05-07, 2016-09-05, 2019-05-27/28, 2020-02-12,
2020-09-11, 2021-02-10, 2021-04-22, 2021-04-28, 2021-05-05). Aucune fermeture particulière
n'étant documentée, ces D1 restent `INTERRUPTION_INEXPLIQUÉE`.

## 4. Configurations (comptées à part des créneaux)

| Année | Identifiées | Consommées par convention | Conservées après refus structurel (tendance D1 perdue) | Abandonnées, données du repli incomplètes | Refusées à `I` : ATR H4 indisponible |
|---|---:|---:|---:|---:|---:|
| 2015 | 85 | 9 | 4 | 0 (0,000 %) | 2 |
| 2016 | 60 | 2 | 1 | 1 (1,667 %) | 0 |
| 2017 | 93 | 10 | 0 | 0 (0,000 %) | 0 |
| 2018 | 68 | 3 | 0 | 0 (0,000 %) | 0 |
| 2019 | 54 | 3 | 0 | 1 (1,852 %) | 0 |
| 2020 | 93 | 3 | 4 | 0 (0,000 %) | 2 |
| 2021 | 103 | 8 | 1 | 0 (0,000 %) | 0 |
| **Total** | **556** | **38** | **10** | **2 (0,360 %)** | **4** |

Les 48 cassures détectées se répartissent en 38 configurations consommées par convention et
10 refus structurels où seul le seuil est consommé (tous pour tendance D1 perdue ; aucun pour
marché fermé). Les deux abandons pour données incomplètes (configurations identifiées le
2016-12-26 et le 2019-12-24) viennent d'une bougie inutilisable dans le repli ; aucun ne vient
d'un créneau absent.

## 5. Avant / après la correction

Le premier passage (`c86d59f`) comptait la cassure, mais sans cotation `_reward_risk` renvoyait
« aucune cotation connue à l'instant de décision » : `_size` n'était jamais atteint et aucune
configuration n'était consommée. Une configuration restait donc active et pouvait produire
plusieurs cassures, et bloquait l'identification de nouvelles configurations.

| | `c86d59f` (avant) | `5922ecc` (après) |
|---|---:|---:|
| Créneaux H1 attendus | 43 584 | 43 584 |
| Absents | 3 | 3 |
| Lignes non évaluables | 460 | 460 |
| Évaluables sans signal | 43 050 | 43 073 |
| Cassures détectées | 71 | 48 |
| Configurations identifiées | 547 | 556 |
| Configurations consommées par convention | 0 (aucune, par construction) | 38 |
| Configurations conservées après refus structurel | non compté | 10 |
| Abandons pour données du repli incomplètes | 2 | 2 |

Les données (créneaux, absents, non évaluables, abandons pour données) sont inchangées ; seuls
les nombres qui dépendent du cycle de vie des configurations changent.
