# EUR/USD « vente de matinée européenne » — règle enregistrée avant simulation (2026-11-17)

Origine : atlas 2015-2019 (`../atlas/RESULTS.md`), seul candidat : 09:00 → 13:00 Londres, −3,46 pips,
5/5 années ; effet publié (Breedon-Ranaldo 2013). Exploratoire. 2022+ non lu.

## Règle (figée)
- Chaque jour ouvré (lundi-vendredi, date de Londres) : **vente** EUR/USD au premier tick à 09:00:00
  Londres ou après, au bid. Pas de tick valide avant 09:05 : pas de transaction ce jour-là.
- **Stop garanti** à entrée + s pips, observé à l'ask, exécuté au niveau du stop, prime 1,2 USD/contrat.
  Deux variantes seulement : **S20** (s = 20) et **S30** (s = 30).
- Pas de cible. **Sortie** au premier tick à 13:00:00 Londres ou après, à l'ask.
- Une transaction par jour au plus, aucune autre condition (ni jour, ni volatilité, ni tendance).

## Exécution et coûts (conventions du simulateur au tick validé sur les 296 transactions LATE)
- Coûts ADR-035 : glissement 0,5 pip (ligne de coût), prime 1,2 USD/contrat si stop, conversion au
  1/bid (perte) ou 1/ask (gain) avec frais 0,5 % ; pas de financement (fermée avant 17:00 New York).
- Taille : 0,25 % du capital courant (départ 2 000 € à chaque période), perte au stop estimée au tick
  d'entrée (distance + glissement + prime, convertie au bid, frais compris), arrondie à 0,1 inférieur,
  minimum 0,1 ; risque initial inchangé, pas de levier ajouté. 1 R = cette perte estimée.
- Contrat Mini 10 000 unités ; ticks Dukascopy bid/ask (`data/normalized/ticks`), ticks invalides écartés.

## Déroulement et lecture (fixés avant calcul)
1. Simulation **2015-2019** seulement ; la variante **principale** est celle au R net moyen le plus élevé
   sur 2015-2019 (l'autre reste rapportée).
2. Puis **une seule** simulation 2020-2021, sans retouche d'aucun paramètre.
3. **Confirmée** si, sur 2020-2021, la principale a un R net moyen > 0 d'au moins une erreur type ;
   **non confirmée** si R net ≤ 0 ; **inconclusive** entre les deux.
4. Rapportés : transactions, part stoppée, brut, coûts, net, R net ± ET, PF, par année, plus mauvaise
   série de pertes, drawdown sur transactions closes, sensibilité glissement ×2 et prime ×2.
