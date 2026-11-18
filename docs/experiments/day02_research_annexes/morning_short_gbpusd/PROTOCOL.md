# GBP/USD « vente de matinée européenne » — réplication, enregistrée avant toute donnée GBP/USD (2026-11-18)

Origine : règle EUR/USD `../morning_short/PROTOCOL.md` (découverte 2015-2019, vérification 2020-2021 :
inconclusive, R +0,017 ± 0,029). Effet publié pour les devises européennes (Breedon-Ranaldo 2013 : la
devise locale baisse pendant ses heures de marché). Au moment de l'écriture, aucune donnée GBP/USD n'est
importée (téléchargement en cours) : rien de GBP/USD n'a été lu. 2022+ non téléchargé (refus codé).

## Règle (identique à EUR/USD, aucun paramètre changé)
- Chaque jour ouvré (date de Londres) : **vente** GBP/USD au premier tick à 09:00:00 Londres ou après, au
  bid ; pas de tick valide avant 09:05 : pas de transaction.
- Stop garanti à entrée + s pips, observé à l'ask, exécuté au niveau du stop. **S30 principale** (fixée
  par EUR/USD, pas de nouveau choix) ; S20 rapportée.
- Pas de cible ; sortie au premier tick à 13:00:00 Londres ou après, à l'ask. Une transaction par jour.

## Exécution et coûts
- GBP/USD coté en USD : 1 pip = 1 USD par contrat Mini de 10 000. Glissement 0,5 pip et prime de stop
  garanti 1,2 USD/contrat : **ASSUMED** (valeurs EUR/USD de l'ADR-035 ; les conditions IG GBP/USD ne sont
  pas sourcées ici) ; sensibilités ×2 rapportées. Écart : celui des ticks Dukascopy GBP/USD.
- Conversion USD → EUR par la cotation EUR/USD (dernier tick EUR/USD au plus tard à l'instant
  concerné) : estimation de la perte au bid EUR/USD de l'entrée, résultat converti au 1/bid (perte) ou
  1/ask (gain) EUR/USD de la sortie, frais 0,5 %. Pas de financement (fermée avant 17:00 New York).
- Taille : 0,25 % du capital courant (2 000 € au départ), arrondie à 0,1 inférieur, minimum 0,1 ; risque
  inchangé, pas de levier ajouté. 1 R = perte estimée au stop.

## Lecture (fixée avant calcul)
1. **Une seule** simulation sur 2015-2021 (7 ans, aucune n'a servi à concevoir la règle sur GBP/USD).
2. **Confirmée** si S30 a un R net moyen > 0 d'au moins une erreur type ; **non confirmée** si R ≤ 0 ;
   **inconclusive** entre les deux (même critère que la vérification EUR/USD).
3. Rapportés : comme EUR/USD (transactions, part stoppée, brut, coûts, net, R ± ET, PF, par année, pire
   série, drawdown clos, glissement ×2, prime ×2), plus les périodes 2015-2019 / 2020-2021 et la
   **corrélation** jour par jour des R GBP/USD et EUR/USD (S30), pour dire à quel point la réplication est
   indépendante. Contrôle préalable : les rendements bruts 09:00 → 13:00 calculés sur les ticks
   recoupent les bougies M5 GBP/USD construites.
