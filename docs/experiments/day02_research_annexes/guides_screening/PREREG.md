# DAY_02 — campagne « guides FX Replay » : pré-enregistrement du criblage (2026-11-17)

Écrit **avant tout calcul de résultat**. Exploratoire, 2015-2021 seulement (partition de
développement déjà examinée), aucune donnée 2022-2025, aucun ordre, référence LATE inchangée.

## Base
- Transactions LATE, M5, scénario A : `day02_partial_exits/perf_LATE_m5_a.json` (296 transactions,
  net +36,32 €, commit 9dad2f8) et le détail de leurs configurations (`*_sessions.jsonl`).
- R net = net € / perte estimée au stop à la décision (définition des rapports existants).
- Caractéristiques calculées sur bougies bid M5/M15/H1 **terminées au plus tard à D** (niveaux de
  liquidité : connus avant le début de la fenêtre d'impulsion). Exécution simulée au tick après D.

## Hypothèses de filtre (paramètres fixés a priori ; achat décrit, vente symétrique)
| Id | Source | Définition | Sens attendu |
|---|---|---|---|
| G1a | NoWick C | la bougie de sommet M15 `p` est une NoWick dans le sens (bid_open == bid_low, clôture > ouverture) | retirer (impulsion terminale) |
| G1b | NoWick A | au moins une NoWick M15 dans le sens parmi les bougies d'impulsion `o..p` hors `p` | garder seulement (continuation) |
| G2 | AMD B, Wicks A/B | l'impulsion traverse un niveau majeur L (veille NY 17:00, Asie 00:00-07:00 Londres, semaine précédente) : O < L ≤ E | retirer (prise de liquidité → retournement) |
| G3a | Wicks A, fiche | niveau majeur (ensemble de G2) strictement entre P_D et T | retirer (obstacle) |
| G3b | Wicks A | niveau rond 00/50 strictement entre P_D et T | retirer (obstacle) |
| G3c | Failed 2 D | FVG M15 opposé non comblé (formé dans les 24 h avant D) situé entre P_D et T | retirer |
| G4a | Failed 2 B, AMD B | au moins une bougie de pause M15 « Failed 2 » haussière (plus bas < plus bas précédent, clôture ≥ ce plus bas, plus haut ≤ plus haut précédent) | garder seulement |
| G4b | Failed 2 B, AMD B | entre F et D, une M5 a dépassé E (bid_high > E) sans clôturer au-dessus de E | retirer (cassure échouée préalable) |
| G5a | Quarterly | D dans le 2e quart (« manipulation ») du cycle de 90 min ancré sur minuit New York | retirer ; contrôle placebo par grilles décalées |
| G5b | NoWick, Quarterly | D dans [07:30, 09:30[ New York (substitut horaire de l'annonce de 08:30, sans calendrier) | retirer |
| G5c | fiche, Quarterly | fenêtre d'impulsion (o..p) contenant 08:30 New York | retirer (impulsion d'annonce) |
| G6 | AMD A | accumulation avant l'impulsion : amplitude des corps des 8 M15 précédant W ≤ 1,0 × A | garder seulement |

## Décalages d'entrée (tick, mêmes stop S, cible T, liquidation 22:55 Paris, risque 0,25 %)
- **E1 (NoWick B)** : si la M5 de sortie est une NoWick dans le sens, ordre limite à son ouverture
  (achat : exécuté quand ask ≤ niveau), valable 9 M5 après D, annulé si le bid dépasse le plus haut
  de cette M5 avant exécution (nouvel extrême avant le retest) ; sinon entrée LATE inchangée.
  Délais d'exécution rapportés (1-3, 4-6, 7-9 M5) ; validité 18 M5 en sensibilité seulement.
- **E3 (AMD « box », contrôle)** : ordre limite au retour sur E pour toutes les entrées, 9 M5,
  annulé si la cible est atteinte avant exécution.
- Simulateur validé d'abord : rejouer les 296 entrées LATE au marché doit reproduire sorties et nets.

## Lecture (fixée avant résultats)
- Filtres : effet sur les mêmes entrées = R net moyen des transactions retirées.
  **Prometteur** : moyenne retirée < 0 de plus d'une erreur type sur 2015-2021, négative dans 2015-2018
  et 2019-2021, ≤ 50 % des transactions retirées, effet non porté par une seule transaction.
  **Rejeté** : moyenne retirée ≥ 0. **Inconclusif** : sinon.
- Décalages : écart apparié en € (variante − LATE), entrées manquées comprises ; mêmes seuils.
- Environ 12 hypothèses : 1 à 2 « prometteurs » sont attendus par hasard ; un prometteur n'est
  qu'une piste. **Validé** exigerait des données hors échantillon (réservées) : non atteignable ici ;
  au mieux « confirmé en trajectoire » par un passage moteur complet.
- SMT (Wicks C, Quarterly B/C) : non testable, pas de données GBP/USD dans le projet.
