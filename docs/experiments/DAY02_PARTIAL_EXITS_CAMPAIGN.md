# Campagne exploratoire DAY_02 : prises de bénéfices partielles et protection du solde (2015-2021, M5)

**Statut** : campagne **exploratoire** autorisée par l'opérateur le 2026-11-13 (ADR-038), sur la base
du cadrage présenté le même jour et de ses précisions. Ce n'est pas une validation. Définitions,
mesures et lecture fixées et enregistrées au commit de lancement, **avant tout résultat**. La
référence de cette campagne est **LATE inchangée** (ADR-037) ; la référence DAY_02 et tous les
résultats antérieurs restent conservés et reproductibles. Années 2015-2021 déjà utilisées par
plusieurs essais. Aucune donnée 2022-2025, aucun ordre, aucun réglage guidé par les résultats.

Source d'hypothèses : méthodes de sorties partielles et de suivi du solde décrites par Kathy Lien
(pages 105-107, 151 et 210 de son ouvrage, selon l'opérateur). Ce ne sont pas des preuves de
rentabilité pour DAY_02.

## 1. Plan 2 × 2

| | Stop fixe | Stop protégé (§4) |
|---|---|---|
| **Sortie unique à TP2** | **LATE** (référence, inchangée) | **PROT** |
| **Sorties TP1 / TP2 / TP3** | **PART** | **FULL** |

PART − LATE : effet des prises partielles (et du TP3 plus lointain) ; PROT − LATE : effet de la
protection ; FULL : l'hypothèse complète et l'interaction. Aucune autre configuration ; aucun
paramètre testé en variante (TP3 = E + 1,5 I n'est pas testé, sur décision de l'opérateur).

Communs aux quatre : entrées, horaires de recherche, stop initial, taille et risque initial total de
LATE ; aucune sortie temporelle ; liquidation de tout le solde à 22:55 `Europe/Paris` au premier tick
strictement postérieur (convention LATE) ; une position à la fois ; reprises inchangées.

## 2. Niveaux, fixés à l'exécution (achat ; vente symétrique)

`R0` = prix exécuté − stop initial (le risque de LATE). `E` = extrême de l'impulsion, `I` = son
amplitude ; `TP2 = E + I` est la cible de LATE.

- **TP1** = entrée + min(1 × R0, ⅔ × (TP2 − entrée)) ;
- **P** = TP1 + ½ × (TP2 − TP1), seuil de progression vers TP2 ;
- **TP2** = E + I ;
- **TP3** = E + 2 I.

Sur la géométrie à l'entrée des 296 transactions LATE (aucun résultat utilisé) : TP1 médian 1,0 R
(plafonné dans 49 % des cas), P 1,26 R, TP2 1,52 R, TP3 3,2 R (57 pips). La distance de TP3 est
connue à l'entrée ; **la fréquence de son atteinte n'est pas supposée : la campagne la mesure.**

## 3. Quantités

Taille exécutée de LATE, inchangée (une seule position économique, risque non multiplié). En pas de
0,1 contrat, `n` pas : tiers au plus fort reste, égalités TP1 > TP3 > TP2.

| Taille | TP1 / TP2 / TP3 |
|---|---|
| 0,1 | 0 / 0,1 / 0 (sortie unique à TP2 ; protection dans FULL comme dans PROT) |
| 0,2 | 0,1 / 0 / 0,1 |
| 0,3 | 0,1 / 0,1 / 0,1 |
| 0,4 | 0,2 / 0,1 / 0,1 |
| 0,5 | 0,2 / 0,1 / 0,2 |
| 0,6 / 0,7 | 0,2 / 0,2 / 0,2 et 0,3 / 0,2 / 0,2 |

PROT : toute la taille sur TP2. Aucune taille gonflée, aucun pas plus fin supposé. Dans LATE, 17 %
des positions font 0,1, 37 % 0,2, 31 % 0,3 : **moins de la moitié ont trois portions** ; le bilan est
ventilé par nombre de pas.

## 4. Événements, exécutions, protection

- **Niveau atteint et portion exécutée sont deux événements distincts.** Un niveau est atteint à la
  première cotation exécutable (bid pour un achat, ask pour une vente) au niveau ou au-delà, qu'il
  porte une quantité ou non. Une portion s'exécute à la première cotation qui atteint son niveau, au
  prix de cette cotation ; plusieurs portions peuvent s'exécuter sur la même cotation, dans l'ordre
  des niveaux. La dernière quantité clôt la position.
- **Protection (PROT, FULL)**, le stop du solde ne fait que se resserrer (`max` pour un achat) :
  1. **P atteint** (ce qui suppose TP1 atteint, avec ou sans quantité) : stop au **prix d'entrée** ;
  2. **TP2 atteint** (avec ou sans quantité, par exemple pour 0,2 contrat) : stop au **niveau TP1**.
- **Chronologie** : sur une cotation, silence, stop en vigueur, niveaux, puis déplacements ; un
  déplacement décidé sur une cotation n'agit qu'à partir de la cotation suivante. Aucun ordre
  intrabougie n'est supposé (lecture tick par tick).
- **Parcours admis** : une position peut sortir à TP1 puis au stop ou à l'échéance sans atteindre TP2
  ni TP3 ; les contrôles exigent la conservation des quantités, pas l'ordre des noms.

## 5. Interruptions (scénarios existants)

- **A** : franchissements observés seulement ; à la cotation de reprise, stop en vigueur puis niveaux
  atteints par cette cotation.
- **B** (stop d'abord) : tout le solde sort au **stop en vigueur avant le trou**, jamais à un stop
  décidé après.
- **C** (cible d'abord) : la **prochaine portion non exécutée portant une quantité** est supposée
  exécutée pendant le trou, **à son niveau** (sans amélioration de prix) ; les niveaux qui la
  précèdent sont notés atteints. Les autres portions restent ouvertes. La cotation de reprise est
  ensuite traitée comme toute cotation : stop en vigueur (les déplacements issus de l'événement
  supposé n'agissent qu'à la cotation suivante), puis niveaux atteints par son prix. Aucune portion
  oubliée, aucune double sortie, aucune protection rétroactive.
- Fermeture connue : stop en vigueur, puis niveaux atteints, comme en A.

## 6. Comptabilité

- **Break-even au prix** (stop au prix d'entrée) ≠ **net du solde** (une sortie à ce stop reste
  négative : glissement 0,5 pip, prime de stop garanti 1,2 USD par contrat déclenché, conversion) ≠
  **net de la transaction entière** (somme de toutes ses exécutions).
- Chaque exécution porte ses coûts : glissement sur sa quantité, conversion à 0,5 % de son résultat,
  financement pour chaque nuit qu'elle a franchie, prime seulement sur la quantité sortie au stop. Son
  net est porté au solde du compte à son instant.
- La transaction économique garde la taille et le stop initial (le risque `R` reste celui de LATE) ;
  ses montants en EUR sont la somme exacte des exécutions (montants en USD exprimés au taux de la
  dernière exécution).

## 7. Fin de journée, vendredi, absence de cotation

Convention LATE : tout le solde à 22:55 Paris, premier tick strictement postérieur. Un vendredi des
semaines de décalage, le marché ferme avant : le solde sort à la première cotation de la semaine
suivante (trois nuits financées dans le modèle). Sans cotation avant la fin de l'étude : position
ouverte valorisée, ordre dû rapporté, aucune sortie inventée. **Les positions conservées au-delà de
l'échéance sont rapportées à part** et ne sont pas des clôtures intraday réussies.

## 8. Causalité

Niveaux et quantités fixés à l'exécution ; événements lus sur les cotations déjà reçues ;
déplacements effectifs à la cotation suivante. Tests (`tests/test_day02_partials.py`) : troncature et
altération après T, plusieurs portions sur une cotation, déplacement non rétroactif, contrôle qui
rejette des plans falsifiés ; rejeu tronqué de FULL sur données réelles (→2015-04-01 contre
→2015-07-01 et complet).

**Comparaison « sans déplacement du stop »** : un observateur passif suit chaque solde clos par un
stop déplacé avec le stop initial (stop initial, niveaux restants, puis échéance) ; il n'est jamais lu
par une décision, et un test vérifie qu'il ne change rien à la simulation. Il donne les **pertes
évitées** (solde qui aurait fini plus bas) et les **continuations interrompues trop tôt** (plus haut).

## 9. Exécution prévue

Études de disponibilité LATE, PROT, PART, FULL (parcours d'entrée identiques) ; passages M5 scénario
A des quatre ; **LATE doit reproduire exactement `day02_late_exit/perf_LATE_m5_a`** ; B, C et rejet
seulement si le passage A d'une configuration les exige ; rejeux tronqués de FULL.

## 10. Mesures et lecture (fixées avant les résultats)

Par configuration et par période (2015-2018 / 2019-2021) : transactions, brut, coûts par nature, net,
espérance en R du risque initial, drawdown, durée, sorties ; quantités prévues et exécutées et gains
réalisés à chaque TP, niveaux atteints (avec et sans quantité), résultat du solde par issue (stop
initial, stop au prix d'entrée, stop à TP1, TP, 22:55), déplacements du stop (dont ceux à moins de
5 pips de la cotation), pertes évitées et continuations interrompues (observateur), positions
conservées au-delà de l'échéance ; ventilation par nombre de pas ; effet apparié contre LATE sur les
entrées communes et différences dues aux reprises.

**Lecture** : exploratoire. Une configuration dont le net dépasse celui de LATE sur 2015-2021 et dans
chaque période est une **piste à approfondir** ; l'effet apparié rapporté à son erreur type est un
**indicateur**, ni une preuve de robustesse ni un motif automatique d'abandon. Le bilan explique les
mécanismes, les compromis (fréquence des petits gains contre continuations coupées, coûts des
sorties multiples) et l'effet de la granularité des tailles. Une amélioration simulée ne vaut pas
confirmation d'exécutabilité chez IG.

## 11. Limites IG (non modélisées)

Clôture partielle d'une position et quantité minimale réelle (0,01 relevé sur le compte, non utilisé) ;
modification d'un stop garanti et sa distance minimale (5 points relevés ; non appliquée, ADR-035 ;
les déplacements plus proches sont comptés) ; financement réel ; écarts de fin de journée ; horaires
du vendredi. Coûts `ASSUMED` de l'ADR-035.

## 12. Registre des essais

Sorties sous `data/reports/backtests/day02_partial_exits/` (hors Git). Tous les essais conservés.

| # | Essai | Configuration | Commit | Résultat | Incident |
|---|---|---|---|---|---|
| — | définitions, code et tests | §1-§8 | (ce commit) | 616 tests | — |
