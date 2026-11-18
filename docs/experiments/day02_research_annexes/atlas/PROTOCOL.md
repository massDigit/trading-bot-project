# Atlas EUR/USD 2015-2019 — régularités intraday (enregistré le 2026-11-17, avant calcul)

Exploratoire et descriptif. **Seules les années 2015-2019 sont lues** (filtre avant tout calcul, vérifié
par assertion) ; 2020-2021 restent pour la vérification, 2022+ en réserve. Aucune stratégie, aucun
passage moteur, aucun fichier suivi modifié. Cible visée : 1 à 2 transactions par jour, stops de
20-30 pips, horizons de 1 à 4 h (mur des frais : −0,07 à −0,045 R pour une entrée au hasard).

## Données et conventions
- Bougies M5 Dukascopy `VALID`, prix milieu = (bid + ask) / 2. Prix à un instant `t` = ouverture milieu
  de la bougie commençant à `t`. Heures de Londres. Jours ouvrés avec une bougie à 07:00.
- Toute condition est connue à l'instant de décision : bougies terminées seulement.
- Rendements en pips, signés dans le sens de l'hypothèse ; une observation par jour et par test.
- Journée de trading précédente : étiquette New York 17:00 (date de `ts` New York + 7 h).

## Familles de tests (liste fermée : 48 tests)
- **T1 Heure** (27) : rendement de `h` à `h + H`, `h` ∈ 07..15 h, H ∈ {1, 2, 4} h (plafonné à 20:00).
  Signe attendu (Breedon-Ranaldo) : euro en baisse en séance européenne, en hausse en séance américaine ;
  rapporté brut, signe libre.
- **T2 Jour × séance** (10) : lundi..vendredi × {07:00-12:00, 12:00-16:00}.
- **T3 Fin de mois** (4) : dernier jour ouvré du mois, 15:00-16:00 (fixing) et 07:00-16:00 ; premier
  jour ouvré, 07:00-16:00 ; dernier jour, 12:00-16:00.
- **T4 Cassure du plus haut / plus bas de la veille** (2) : première bougie entre 07:00 et 14:00 dont le
  milieu dépasse le niveau ; entrée à l'ouverture suivante ; rendement 1 h et 2 h signé dans le sens de la
  cassure (positif = continuation, négatif = retour, « sweep »). Hausses et baisses regroupées.
- **T5 Cassure du range asiatique** (00:00-07:00) (2) : même définition, 1 h et 2 h.
- **T6 Momentum** (3) : rendement 07:00-08:00 → 08:00-16:00 ; nuit (16:00 veille → 07:00) → 07:00-16:00 ;
  veille 07:00-16:00 → 07:00-16:00 ; signé par le signe du prédicteur.

Pour T4-T5, le rendement est aussi rapporté **en excès** du rendement moyen à la même heure de départ
(référence T1 sans condition, signée de la même façon) : c'est le placebo.

## Mesures et seuils (fixés avant calcul)
- Moyenne, erreur type, t, p (bilatéral, loi normale), signe par année (5 ans), part positive.
- Correction pour 48 tests : Benjamini-Hochberg à 10 %.
- **Candidat** si : significatif après correction ; même signe au moins 4 années sur 5 ; |moyenne| ≥ 2 pips
  (au-delà de l'aller-retour écart + glissement ≈ 0,8 pip, avec marge) ; pour T4-T5, l'excès sur le
  placebo de même signe. Sinon : **sans effet exploitable**.
- Équivalent R indicatif : moyenne / (20 + 1,7) pour un stop de 20 pips.
- Les candidats ne sont pas des stratégies : chacun devra être formulé en règle, enregistré, puis passé
  au moteur et vérifié sur 2020-2021 sans retouche.
