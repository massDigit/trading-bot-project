# Campagne exploratoire DAY_02 : sorties tardives (LATE) contre la référence (2015-2021, M5)

**Statut** : campagne **exploratoire** autorisée par l'opérateur le 2026-11-10 (ADR-037), **terminée
le 2026-11-10 : lecture enregistrée « piste à poursuivre », sous protocole distinct (§8)**. Ce n'est
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
`data/reports/backtests/day02_late_exit/` (hors Git). Tous lancés sur `e9960e0`, arbre propre, sans
changement de commit ni de fichier suivi pendant les passages. Aucun essai invalidé, aucune
correction de bug.

| # | Essai | Configuration | Commit | Résultat | Incident |
|---|---|---|---|---|---|
| — | définition, code et tests | §2 | e9960e0 | 591 tests | — |
| 1 | disponibilité 2015-2021 | REF | e9960e0 | C1-C10 conformes ; détail identique octet pour octet à l'étude de référence | — |
| 2 | disponibilité 2015-2021 | LATE | e9960e0 | C1-C10 conformes ; 3 632 parcours identiques à REF ; couverture §8.1 | — |
| 3 | performance M5, scénario A | REF | e9960e0 | contrôles conformes ; rapport et détail des séances identiques à `day02_ref_2015_2021_m5_a` | — |
| 4 | performance M5, scénario A | LATE | e9960e0 | contrôles conformes ; aucun scénario B/C ni rejet requis ; 0 transaction indéterminée | — |
| 5-6 | performance LATE tronquée (→2015-04-01, →2015-07-01) | LATE | e9960e0 | 63 séances et 8 transactions avant le 2015-04-01 identiques entre les deux troncatures et le passage complet | — |

## 8. Bilan (exploratoire)

### 8.1 Couverture des horaires supplémentaires (17:00 Londres → 22:55 Paris, 1 816 séances)

| Grille | Créneaux ouverts | Non `OK` | Causes | Créneaux de marché fermé |
|---|---:|---:|---|---:|
| M5 | 106 880 | 31 | 26 sans tick, 5 silence > 5 min | 264 |
| M15 | 36 224 | 13 | 7 sans tick, 6 silence > 5 min | 96 |

7 silences de plus de 5 min (156 minutes en tout) touchent 6 séances. Les créneaux de marché fermé
sont ceux des vendredis des semaines de décalage (fermeture à 22:00 Paris). Pour comparaison, la
fenêtre 07:00-17:00 compte 18 créneaux M5 non `OK` sur 217 920. Couverture suffisante ; aucune
position n'a traversé de silence inexpliqué (0 transaction indéterminée).

### 8.2 Tableau 2015-2021 (M5, scénario A, coûts et risque ADR-035)

| | REF | LATE |
|---|---:|---:|
| Transactions | 298 | 296 |
| Brut € | −17,91 | **+112,79** |
| Coûts € | 52,75 | 76,48 |
| dont glissement / prime de stop garanti / conversion / financement | 31,28 / 17,80 / 3,67 / 0 | 32,47 / 36,94 / 6,16 / 0,91 |
| **Net €** | **−70,66** | **+36,32** |
| R net (± erreur type) | −0,064 ± 0,044 | +0,029 ± 0,064 |
| R brut | −0,020 ± 0,043 | +0,091 ± 0,062 |
| Drawdown au tick € / relatif | 113,82 / 5,66 % | 52,08 / 2,55 % |
| Sorties cible / stop / échéance | 40 / 69 / 183 temporelles + 6 à 17:00 | 110 / 141 / 45 à 22:55 Paris |
| Durée médiane (q1-q3), min | 120 (84-120) | 165 (83-310) |
| Durée médiane par sortie, min | cible 59, stop 71 | cible 160, stop 121, liquidation 595 |
| Durée maximale | 2 h | 58,9 h (vendredi de décalage, clôture au dimanche soir) |
| Transactions financées / nuits | 0 / 0 | 3 / 5 (1 + 1 + 3) |
| Dépassements du budget de risque | 3 | 3 |

Par période (exploratoire) :

| | REF 2015-2018 | LATE 2015-2018 | REF 2019-2021 | LATE 2019-2021 |
|---|---:|---:|---:|---:|
| Transactions | 170 | 169 | 128 | 127 |
| Brut € | −33,86 | +44,63 | +15,95 | +68,16 |
| Net € | −61,13 | **+5,29** | −9,53 | **+31,03** |
| R net | −0,107 ± 0,061 | −0,002 ± 0,087 | −0,008 ± 0,064 | +0,070 ± 0,093 |
| Drawdown clos € | 70,93 | 45,88 | 40,08 | 34,34 |

Net par année, LATE : 2015 −19,74 ; 2016 −13,01 ; 2017 +28,62 ; 2018 +9,43 ; 2019 +4,11 ;
2020 +10,35 ; 2021 +16,56 (REF : −20,00 ; −17,71 ; −5,51 ; −17,91 ; −27,42 ; +24,94 ; −7,05).

### 8.3 Décomposition de l'effet

Les deux trajectoires ont **296 entrées communes** (même `D`, même sens). Seules 2 entrées de la
référence disparaissent (bloquées par une position LATE encore ouverte, −2,05 EUR dans la
référence) et LATE n'en a aucune propre. L'effet vient donc presque entièrement des **mêmes
positions** :
- **référence close par la cible ou le stop avant l'échéance** (108 entrées) : sortie identique dans
  LATE pour les 108 (même instant, prix et motif), écart nul en R ; les écarts en EUR (−8,3 EUR)
  viennent seulement de tailles différentes, le capital ayant divergé ;
- **référence close par la sortie temporelle** (182) : dans LATE, 70 atteignent la cible, 73 le stop
  et 45 vont à la liquidation de 22:55 (avec les 6 de 17:00) ; écart moyen +0,135 R ± 0,075,
  +100,60 EUR ;
- **référence close à 17:00** (6) : +0,458 R ± 0,268, +12,66 EUR ;
- **effet apparié sur toutes les entrées communes** : +0,092 R ± 0,047 (2015-2018 : +0,100 ± 0,062 ;
  2019-2021 : +0,081 ± 0,071).

Les 45 positions liquidées à 22:55 ont un résultat moyen de +0,195 R (+35,35 EUR) : une part
importante du gain vient de positions qui n'ont atteint ni la cible ni le stop.

### 8.4 Lecture enregistrée (§6)

- **Piste à poursuivre** : les critères enregistrés sont remplis, de justesse : net positif sur
  2015-2021 (+36,32 EUR) et dans chaque période (+5,29 et +31,03 EUR), espérance nette positive
  (+0,029 R), drawdown relatif 2,55 %.
- Le critère « à reformuler » (effet apparié de plus d'une erreur type dans les deux périodes) est
  aussi rempli ; la lecture retenue est la plus favorable des deux, comme prévu.

### 8.5 Limites et prudence

- **Espérance nette non distinguable de zéro** : +0,029 R ± 0,064 (moins d'une erreur type) ; sur
  2015-2018, l'espérance nette est nulle (−0,002 R) et le net positif ne tient qu'à 5 EUR. Le
  résultat le plus solide est l'effet apparié (+0,092 R, environ deux erreurs types sur 2015-2021),
  pas la rentabilité.
- **Ampleur économique faible** : +36 EUR en sept ans sur 2 000 EUR (environ 0,26 % par an), pour
  76 EUR de coûts. Une hausse modeste des coûts réels suffirait à annuler le net.
- **Coûts sensibles à la règle** : la prime de stop garanti double (plus de positions vont au stop) ;
  le financement reste marginal dans le modèle (0,91 EUR) mais n'est pas celui d'IG.
- **Années déjà examinées** ; l'hypothèse vient de l'observation de la référence (sortie temporelle
  la plus fréquente) ; une seule variante testée ici, après sept variantes H1-H3 sur les mêmes
  années.
- **Prix de fin de journée** : les sorties de 21:55-22:00 Londres sont exécutées aux bid/ask de la
  source historique, pas aux écarts IG de cette heure, souvent plus larges autour de la clôture de
  New York.
- **Conditions IG** : incertitudes du §3 (financement réel, facturation triple, horaires du vendredi,
  stop garanti hors heures de Londres, taille minimale, conversion), non modélisées.

### 8.6 Recommandation

**Poursuivre, sous protocole distinct.** Laisser plus de temps aux positions améliore nettement la
stratégie sur les mêmes entrées (+0,09 R par transaction, dans les deux périodes), et LATE est la
première configuration DAY_02 à net positif dans ce modèle. Mais l'espérance nette reste proche de
zéro et le gain économique est faible : ce n'est ni une validation ni une stratégie prête pour le
réel. Toute suite (épreuve sur 2022-2023, conditions IG mieux documentées) doit faire l'objet d'un
protocole distinct, gelé avant toute lecture, sur autorisation de l'opérateur. La référence reste
inchangée ; aucune fusion ni remplacement sans accord.
