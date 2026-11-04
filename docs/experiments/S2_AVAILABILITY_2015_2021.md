# S2 — Étape 3 : disponibilité des données, développement 2015-2021

**Statut** : passage du 2026-11-04, autorisé par l'opérateur (fiche S2 §9, étape 3). Aucune
transaction, aucun gain ou perte, aucun drawdown : aucun tick n'est lu. Ni validation de
performance, ni autorisation de trading.

## 1. Commande et provenance

```
uv run forex-s2-availability --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 \
    --out data/reports/backtests/s2_availability_2015_2021.json \
    --details-out data/reports/backtests/s2_availability_2015_2021_details.jsonl
```

- Commit `c86d59f04b5b9f9c2152825fc4742bae7e291f05` (branche `feat/s2-data-availability`), arbre
  propre (aucun diff non commité).
- Entrées : 43 630 H1, 10 912 H4, 1 822 D1, 383 trous du rapport de qualité, 0 tick. 152 s, pic
  de mémoire 311 Mio. Sorties hors Git.
- Paramètres S2 approuvés (ASSUMP-025), déclenchement H1 (référence), latence 0, aucune
  fermeture particulière documentée (comme la référence S1).

## 2. Méthode

- **Créneaux H1 attendus** : calculés à partir du calendrier, fermeture hebdomadaire et jours
  fériés probables (25 décembre, 1er janvier) exclus ; un créneau appartient à l'année de son
  instant de décision (fin de la H1), dans [2015-01-01, 2022-01-01).
- Chaque créneau attendu est dans une seule classe : **absent** (aucune H1, donc aucune ligne de
  journal) ; **présent non évaluable** (ligne `ÉVALUATION_IMPOSSIBLE`, cause = premier motif) ;
  **évaluable sans signal** (`AUCUN_SIGNAL`) ; **évaluable avec cassure** (nombre seul, sans
  détail à cette étape).
- Les H1 présentes hors calendrier prévu (veilles et jours fériés probables) sont comptées à part.
- **Configurations** abandonnées pour données du repli incomplètes : rapportées aux
  configurations identifiées (année de `I`), jamais ajoutées aux créneaux.
- Trajectoire sans position (aucun tick) : une cassure acceptée par les règles consomme sa
  configuration comme le ferait une entrée. À l'étape 4, une position ouverte peut modifier
  légèrement le cycle de vie des configurations.

## 3. Créneaux H1

| Année | Attendus | Absents | Présents non évaluables | Évaluables sans signal | Évaluables avec cassure | Présentes hors calendrier |
|---|---:|---:|---:|---:|---:|---:|
| 2015 | 6 216 | 0 (0,000 %) | 74 (1,190 %) | 6 121 (98,472 %) | 21 (0,338 %) | 10 |
| 2016 | 6 240 | 1 (0,016 %) | 51 (0,817 %) | 6 182 (99,071 %) | 6 (0,096 %) | 0 |
| 2017 | 6 216 | 0 (0,000 %) | 47 (0,756 %) | 6 154 (99,003 %) | 15 (0,241 %) | 9 |
| 2018 | 6 216 | 0 (0,000 %) | 23 (0,370 %) | 6 187 (99,533 %) | 6 (0,097 %) | 11 |
| 2019 | 6 216 | 2 (0,032 %) | 91 (1,464 %) | 6 120 (98,456 %) | 3 (0,048 %) | 10 |
| 2020 | 6 240 | 0 (0,000 %) | 74 (1,186 %) | 6 157 (98,670 %) | 9 (0,144 %) | 9 |
| 2021 | 6 240 | 0 (0,000 %) | 100 (1,603 %) | 6 129 (98,221 %) | 11 (0,176 %) | 0 |
| **Total** | **43 584** | **3 (0,007 %)** | **460 (1,055 %)** | **43 050 (98,775 %)** | **71 (0,163 %)** | **49** |

Créneaux absents : 2016-09-02 18:00, 2019-05-26 21:00 et 22:00 UTC. Les 49 H1 hors calendrier
sont toutes non évaluables.

**Causes des 460 lignes non évaluables** (premier motif) :

| Cause | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D1 de contexte non utilisable | 47 | 48 | 46 | 23 | 90 | 70 | 96 | 420 |
| Initialisation : aucune D1 disponible | 23 | 0 | 0 | 0 | 0 | 0 | 0 | 23 |
| Bougie de déclenchement `INTERRUPTION_INEXPLIQUÉE` | 2 | 3 | 1 | 0 | 1 | 2 | 4 | 13 |
| Configuration refusée : ATR H4 indisponible à `I` | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 4 |

Une D1 de contexte non utilisable bloque toutes les H1 jusqu'à la D1 suivante. Ces lignes se
concentrent sur 16 épisodes, au lendemain des jours fériés probables (26-28 décembre, 2 janvier) et de quelques
interruptions (2015-05-07, 2016-09-05, 2019-05-27/28, 2020-02-12, 2020-09-11, 2021-02-10,
2021-04-22, 2021-04-28, 2021-05-05). Aucune fermeture particulière n'étant documentée, ces D1
restent `INTERRUPTION_INEXPLIQUÉE`.

## 4. Configurations (comptées à part)

| Année | Identifiées | Abandonnées, données du repli incomplètes | Refusées à `I` : ATR H4 indisponible |
|---|---:|---:|---:|
| 2015 | 81 | 0 (0,000 %) | 2 |
| 2016 | 59 | 1 (1,695 %) | 0 |
| 2017 | 91 | 0 (0,000 %) | 0 |
| 2018 | 68 | 0 (0,000 %) | 0 |
| 2019 | 54 | 1 (1,852 %) | 0 |
| 2020 | 92 | 0 (0,000 %) | 2 |
| 2021 | 102 | 0 (0,000 %) | 0 |
| **Total** | **547** | **2 (0,366 %)** | **4** |

Les deux abandons (identifiées le 2016-12-26 et le 2019-12-24) viennent d'une bougie inutilisable
dans le repli ; aucun ne vient d'un créneau absent.
