# Campagne exploratoire DAY_02 : sorties tardives (LATE) contre la référence (2015-2021, M5)

**Statut** : campagne **exploratoire** autorisée par l'opérateur le 2026-11-10 (ADR-037). Ce n'est
pas une validation. La définition, les mesures et la lecture ci-dessous sont fixées et enregistrées
au commit de lancement, **avant tout résultat de la variante**. La référence DAY_02 (ADR-028,
ADR-034, ADR-035) reste inchangée et reproductible. Les années 2015-2021 ont déjà été examinées.
Aucune donnée 2022-2025, aucun ordre (réel ou démo), aucune fusion ni remplacement de la référence
sans accord de l'opérateur. Aucun paramètre n'est modifié après la lecture des résultats.

## 1. Hypothèse

Les sorties imposées de la référence (sortie temporelle 2 h après l'exécution, liquidation à 17:00
Londres) interrompent peut-être trop tôt des positions qui auraient atteint leur cible. Dans la
référence, 183 des 298 transactions M5 sont closes par la sortie temporelle et 6 par la liquidation
de 17:00 : c'est la sortie la plus fréquente. Ce constat motive la question ; il ne dit pas dans quel
sens l'issue change.

## 2. Définition de la variante unique `LATE` (`--variant LATE`)

| Élément | Référence `REF` | `LATE` |
|---|---|---|
| Entrées, horaires de recherche, ATR, drapeau, `D`, exécution | fiche figée | identiques |
| Stop initial (garanti, simulé), cible `E + I` | fiche figée | identiques |
| Dimensionnement (0,25 % de risque, sans provision de nuit) | ADR-035 | identique |
| Sortie temporelle | 2 h après l'exécution | **supprimée** |
| Liquidation | 17:00 Europe/London | **22:55 Europe/Paris**, date de séance |
| Entre l'exécution et l'échéance | cible, stop, échéance | cible et stop seulement |
| Stop suiveur, sorties partielles | aucun | aucun |
| Nouvelle entrée pendant une position | non | non (une position à la fois) |
| Reprises | règles existantes | règles existantes, inchangées |

- **Heure** : 22:55 au fuseau `Europe/Paris` le jour de la séance (date de Londres, identique à
  celle de Paris à cette heure), changements d'heure de chaque fuseau compris : 21:55 UTC en hiver,
  20:55 UTC en été. Le libellé de clôture est `LIQUIDATION_22H55_PARIS`.
- **Exécution à l'échéance** : convention existante, premier tick strictement postérieur, côté de
  sortie (bid pour une vente de clôture d'un achat, ask pour l'inverse). Sans cotation, aucun prix
  n'est inventé : la position reste ouverte jusqu'à la première cotation suivante (week-end compris),
  délai et silence clos rapportés à part. Une position encore ouverte à la fin de l'étude est
  valorisée sans sortie inventée.
- **Silences pendant une position** : règles existantes (ADR-021, ADR-026), scénarios A/B/C.

## 3. Financement (modèle ADR-035) et limites

- **Règle appliquée, inchangée** : 1 USD par contrat Mini et par nuit, une nuit à chaque passage de
  17:00 New York (`trading_day`) entre l'exécution et la clôture, **même lorsque la position est
  clôturée le même jour civil**.
- **22:55 Paris est une borne de recherche, pas une garantie d'éviter le financement.** En temps
  normal, 17:00 New York tombe à 23:00 Paris et une position close à l'échéance n'est pas financée.
  Pendant les semaines où les États-Unis et l'Europe ne sont pas à la même heure (environ trois
  semaines en mars, une semaine fin octobre ou début novembre), 17:00 New York tombe à 22:00 Paris :
  une position tenue jusqu'à 22:55 franchit l'échéance et paie une nuit. Le vendredi de ces semaines,
  le marché ferme à 22:00 Paris : une position encore ouverte se clôt à la première cotation de la
  semaine suivante, et paie trois nuits dans le modèle.
- **Dimensionnement** : identique à la référence, sans provision de nuit. Le financement éventuel
  s'ajoute à la perte au stop ; les dépassements du budget de risque sont rapportés.
- **Incertitudes sur les conditions réelles IG (signalées à part, non modélisées)** : heure exacte
  et montant réel du financement IG (taux d'intérêt et marge, non forfaitaires), facturation triple
  d'un jour de la semaine, élargissement des écarts autour de la clôture quotidienne de New York,
  horaires réels de clôture du vendredi et des veilles de fêtes, disponibilité et coût du stop garanti
  hors heures de Londres, taille minimale et conversion (ADR-035). Ces valeurs restent `ASSUMED`.

## 4. Causalité

L'échéance est fixée à l'exécution depuis la date de séance seule ; aucune information postérieure à
un instant T n'entre dans une décision à T. Vérifications :
- tests synthétiques (`tests/test_day02_late_exit.py`) : ticks tronqués ou modifiés après 11:00,
  16:00 et 20:00 sans effet sur ce qui est connu avant ; tick exactement à l'échéance qui n'exécute
  pas ; aucune cotation après l'échéance (position ouverte, ordre dû rapporté) ;
- rejeu tronqué sur données réelles : passage `LATE` arrêté au 2015-04-01 puis au 2015-07-01,
  séances, tentatives, journal et transactions identiques avant le 2015-04-01 ;
- étude de disponibilité `LATE` : parcours sans position identiques à ceux de la référence (les
  sorties n'interviennent pas dans la recherche des configurations).

## 5. Exécution prévue

1. Étude de disponibilité `LATE` 2015-2021 : contrôles C1-C10, parcours comparés à la référence
   ligne par ligne, et **couverture des horaires supplémentaires** (17:00 Londres → 22:55 Paris) :
   créneaux M5 et M15 non `OK` par cause, créneaux de marché fermé, silences de plus de 5 min.
2. Passage de performance M5 scénario A de `LATE` et **nouveau passage de la référence** au même
   commit (reproduction de `day02_ref_2015_2021_m5_a`, transactions et détail des séances).
3. Scénarios B, C et rejet à l'exécution pour `LATE` seulement si son propre passage A les exige ;
   C publié seulement s'il diffère de A.
4. Rejeu tronqué (§4).

## 6. Mesures et lecture (fixées avant les résultats)

Pour `REF` et `LATE`, sur 2015-2021 et par période 2015-2018 / 2019-2021 (exploratoire) :
- nombre de transactions ; brut, coûts (dont financement, nombre de nuits) et net ; espérance nette
  et brute en R avec erreur type ; drawdown au tick et relatif ;
- **durée des positions** (médiane, quartiles, maximum ; par motif de sortie) ;
- **sorties** : cible, stop, liquidation (et sortie temporelle pour la référence) ; délais après
  l'échéance ; clôtures après une fermeture de marché ; transactions indéterminées.

**Décomposition de l'effet** (rapprochement par instant de décision `D` et sens) :
- **entrées communes** : même décision dans les deux trajectoires ; écart de résultat transaction
  par transaction (R net, EUR), réparti selon la sortie de la référence (cible ou stop avant
  l'échéance : résultat attendu identique ; sortie temporelle ou liquidation : effet direct de la
  règle). C'est la mesure de l'effet du changement sur des positions identiques ;
- **entrées propres à une trajectoire** : différences dues aux reprises ultérieures (une position
  tenue plus longtemps bloque des entrées de la référence ; des entrées nouvelles apparaissent quand
  les trajectoires divergent). Description, pas effet causal.

**Lecture enregistrée** (exploratoire, aucune n'est une validation) :
- **piste à poursuivre** : net de `LATE` positif sur 2015-2021 **et** dans chacune des deux
  périodes, espérance nette positive, drawdown relatif sous 6 % ;
- **à reformuler** : effet moyen sur les entrées communes (R net `LATE` − `REF`) positif de plus
  d'une erreur type appariée dans chacune des deux périodes, mais net encore négatif ;
- **à abandonner** : ni l'un ni l'autre.

## 7. Registre des essais

Tous les essais sont conservés, y compris défavorables ou invalidés. Sorties sous
`data/reports/backtests/day02_late_exit/` (hors Git).

| # | Essai | Configuration | Commit | Résultat | Incident |
|---|---|---|---|---|---|
| — | définition, code et tests | §2 | (ce commit) | 591 tests | — |
