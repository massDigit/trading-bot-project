# Mur des frais EUR/USD — mesure descriptive (2026-11-17)

Définitions fixées avant calcul. Aucune stratégie, aucun paramètre choisi, aucun passage moteur, aucun
fichier suivi modifié. Données : bougies M5 Dukascopy bid/ask 2015-2021 (`intraday_2015_2021_day01_5min`),
bougies `VALID` seulement. Années 2022+ non lues. Périodes rapportées : 2015-2019 (recherche) et
2020-2021 (vérification) séparément.

## A. Écart achat/vente
Médiane et moyenne de `ask_close − bid_close` en pips, par heure de Londres (07:00-16:00).

## B. Entrée au hasard avec bracket (le « mur »)
- Instants d'entrée : toutes les 30 min de 07:00 à 15:30 Londres ; achat **et** vente à chaque instant
  (la dérive s'annule ; le résultat mesure ce que coûte le fait de trader, pas une direction).
- Entrée à l'ouverture de la bougie M5 suivante : achat à `ask_open`, vente à `bid_open`.
- Stop s ∈ {5, 7.5, 10, 15, 20, 30} pips ; cible t = s (1:1) et t = 2s (1:2), mesurés depuis le prix d'entrée,
  observés côté sortie (bid pour un achat, ask pour une vente).
- Si stop et cible sont touchés dans la même bougie M5 : compté **stop** (prudent), nombre rapporté.
- Sinon liquidation à l'ouverture de la première bougie commençant à 22:55 Paris ou après (LATE).
- Coûts ADR-035 : glissement 0,5 pip par transaction ; prime de stop garanti 1,2 pip (1,2 USD par contrat
  Mini de 10 000) si stop ; conversion 0,5 % du résultat ; pas de financement (même jour, approximation).
- 1 R = s + 0,5 + 1,2 pips (perte au stop, frais compris, avant conversion), comme
  `estimated_stop_loss_at_decision`.
- Mesures : R net moyen ± erreur type, part cible/stop/liquidation, durée médiane jusqu'à la sortie, et
  nombre maximal de transactions successives par jour (07:00-16:00, une position à la fois) que cette
  durée permet.

## Lecture
Le R net moyen d'une entrée au hasard est l'avantage qu'une stratégie doit apporter **en plus du hasard**
pour être à l'équilibre, pour chaque taille de stop. Croisé avec la durée, il dit quelle fréquence est
compatible avec quel avantage requis. Descriptif : aucune conclusion de rentabilité.
