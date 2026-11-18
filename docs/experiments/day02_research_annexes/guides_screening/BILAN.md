# DAY_02 — campagne « guides FX Replay » : bilan du criblage (2026-11-17)

Exploratoire, 2015-2021 (déjà examinées), M5, scénario A, coûts ADR-035. Base : 296 transactions
LATE (`day02_partial_exits/perf_LATE_m5_a`, 9dad2f8 ; HEAD au criblage 36807af, aucun fichier suivi
modifié). Hypothèses, paramètres et lecture fixés avant calcul dans `PREREG.md`. Scripts : `scripts/`.
Aucun passage moteur, aucune donnée 2022+, référence LATE inchangée.

## Méthode
- Caractéristiques causales (bougies terminées ≤ D ; niveaux connus avant la fenêtre d'impulsion) :
  `scripts/features.py` → `features.pkl`.
- Filtres : effet sur les mêmes entrées (`scripts/evalf.py` → `filters.csv`), contrôles et placebos
  (`checks.py`), robustesse (`robust.py`), effet de trajectoire approché par le parcours sans
  position de l'étude de disponibilité LATE (`traj.py`).
- Décalages d'entrée : simulateur au tick `scripts/ticksim.py`, **validé** : rejeu des 296 entrées
  LATE au marché identique (entrées, sorties, tailles 296/296, net à 1e-12 €).

## Résultats des filtres (R net moyen des transactions retirées)
| Id | Retirées | R retiré ± ET | 15-18 | 19-21 | Net conservé € | Lecture |
|---|---:|---:|---:|---:|---:|---|
| G1a NoWick au sommet | 28 (9 %) | −0,400 ± 0,187 | −0,32 | −0,49 | 79,06 | **prometteur** |
| G5b D ∈ [07:30, 09:30[ NY | 50 (17 %) | −0,293 ± 0,138 | −0,39 | −0,20 | 97,93 | **prometteur** (réserves) |
| G5a 2e quart 90 min | 35 (12 %) | −0,166 ± 0,176 | −0,27 | −0,09 | 63,94 | inconclusif ; placebo : pas d'effet propre du cycle |
| G4a Failed 2 dans le drapeau (garder) | 159 (54 %) | −0,049 ± 0,088 | −0,10 | +0,02 | 73,55 | inconclusif (> 50 % retirées) |
| G3b niveau 00/50 devant | 181 (61 %) | −0,010 | | | 37,29 | sans effet |
| G6 accumulation (garder) | 182 (61 %) | −0,001 | | | 41,01 | sans effet |
| G2 traversée d'un niveau majeur | 227 (77 %) | +0,007 | | | 25,73 | rejeté |
| G3c FVG opposé devant | 60 (20 %) | +0,019 | | | 31,61 | rejeté |
| G1b NoWick de continuation (garder) | 239 (81 %) | +0,044 | | | −11,70 | rejeté |
| G4b cassure échouée avant D | 107 (36 %) | +0,088 | | | −4,54 | rejeté (sens inverse) |
| G3a niveau majeur devant | 121 (41 %) | +0,095 | | | −17,16 | rejeté (sens inverse) |
| G5c impulsion contenant 08:30 NY | 35 (12 %) | +0,145 | | | 7,15 | rejeté (sens inverse) |

LATE : 296, net +36,32 €, R +0,029, PF 1,061.

## Robustesse des candidates (drawdown sur transactions closes, pas au tick)
| | n | Net € | PF | DD clos | Glissement ×2 | 15-18 | 19-21 |
|---|---:|---:|---:|---:|---:|---:|---:|
| LATE | 296 | 36,32 | 1,061 | 2,33 % | 3,24 | 5,29 | 31,03 |
| sans G1a | 268 | 79,06 | 1,152 | 2,21 % | 48,84 | 19,15 | 59,91 |
| sans G5b | 246 | 97,93 | 1,208 | 1,71 % | 70,25 | 43,53 | 54,40 |
| sans G1a ni G5b | 224 | 118,71 | 1,286 | 1,66 % | 93,31 | 48,64 | 70,07 |
| E3 (retest de E) | 206 | 89,30 | 1,180 | 2,39 % | 59,34 | 47,92 | 41,38 |
| E3 à taille LATE | 206 | 68,25 | 1,175 | 1,83 % | 44,59 | 36,87 | 31,38 |

Trajectoire (parcours sans position) : 1 configuration de remplacement par filtre, aucune
transaction LATE bloquée ; nets approchés G1a 82,16 €, G5b 93,20 €, les deux 117,08 €.

## Contrôles
- G5b : fenêtre la plus défavorable des 26 fenêtres glissantes de 2 h (pré-enregistrée, mais
  signal d'alerte) ; seulement 3 transactions diffèrent entre horloge New York et Londres
  12:30-14:30 : la donnée ne distingue pas « annonce américaine » de « midi de Londres ». Les entrées
  après 14:30 Londres sont bonnes (+0,34 R, 31) : ce n'est pas un effet « fin de fenêtre ».
- G5a : grilles décalées de 15 à 75 min → écarts entre quarts comparables (0,10 à 0,37 R) ; le cycle
  de 90 min n'apporte pas d'information propre, il recoupe la poche de G5b.
- G1a : 20 stops sur 28 ; années 2017-2019 positives ; cohérent avec la description (R moyen
  +0,15 sans extension, −0,12 avec 2 extensions ou plus), non testée à part.

## Décalages d'entrée
- E1 NoWick retest : 54 sorties NoWick, 36 annulées (nouvel extrême avant retest), 4 expirées,
  14 exécutées (validité 18 M5 : 18) ; écart apparié +7,40 € (+18,99 € à 18 M5), ET ≈ 0,53 €/transaction,
  périodes de signes opposés → **inconclusif** (effectif).
- E3 retest de E (AMD « box », contrôle générique) : 206 exécutées sur 296 ; exécutées −80,62 € → +89,30 €
  (mêmes sorties, meilleur prix, stop 19 % plus proche) ; manquées : +116,94 € dans LATE (R +0,33,
  sélection adverse) ; écart apparié +0,179 ± 0,163 €/transaction, positif dans les deux périodes →
  **prometteur de justesse** ; effet de trajectoire des 90 entrées manquées non mesuré.

## Non testé
- SMT (Wicks C, Quarterly B/C/D) : pas de données GBP/USD (adaptateur JForex limité à EUR/USD,
  compte démo requis).
- Calendrier d'annonces : aucun historique horodaté ; G5b/G5c sont des substituts horaires.
- Confirmation M1 (Failed 2) : non pertinente (coûts, données M1 non construites).

## Limites
12 hypothèses + 2 décalages sur des années déjà lues : 1 à 2 faux positifs attendus au seuil d'une
erreur type. Aucun résultat n'est validé : la validation exige un passage moteur complet puis des
données hors échantillon (2022-2023, réservées, sur autorisation).
