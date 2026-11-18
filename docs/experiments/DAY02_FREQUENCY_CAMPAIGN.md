# Campagne exploratoire DAY_02 : fréquence, confirmations des guides et SMT (2015-2021, M5)

**Statut** : campagne **exploratoire** autorisée par l'opérateur le 2026-11-17 (ADR-039). Définitions,
paramètres, mesures et lecture ci-dessous sont **fixés et enregistrés au commit de lancement, avant
tout résultat des configurations nouvelles**. LATE (ADR-037) reste la référence de comparaison,
inchangée et reproduite. Les années 2015-2021 ont déjà été examinées : rien ici n'est une validation.
Aucune donnée 2022-2025, aucun ordre, aucune fusion. **Passages faits les 2026-11-17 et 2026-11-18 ;
bilan au §8.** Coûts, capital et risque de l'ADR-035 inchangés
(0,25 % par transaction, minimum et pas 0,1, 2 000 EUR, stop garanti simulé), une position à la fois.

## 1. Objectif et diagnostic

**Cible de l'opérateur** : environ 4 à 5 transactions par séance en moyenne pour DAY_02 seule, avec une
espérance nette positive après coûts et un risque maîtrisé. Cible de recherche, pas un quota.

**Entonnoir actuel** (étude de disponibilité M5, 1 816 séances, parcours sans position) : 31 953 M15
examinées (17,6 par séance) → 2 725 impulsions reconnues (1,50) → 1 009 drapeaux formés (0,56) →
307 sorties confirmées (0,17) ; LATE : 296 transactions (0,163 par séance, 42 par an).

| Frein | Mesure | Nature |
|---|---|---|
| Reconnaissance de l'impulsion | 8,5 % des M15 examinées ; refus : ordre des extrêmes 30 400, `p < j` 10 452, amplitude 16 670 | stratégie (seuil 1,5 A H1, fenêtre 1 h, `p = j`) |
| Formation du drapeau | 37 % des configurations : 996 repli trop profond, 572 impulsion prolongée, 146 fin de fenêtre | stratégie |
| Sortie du drapeau | 30 % des drapeaux : 407 repli trop profond après `F`, 216 consolidation trop longue, 79 fin de fenêtre | stratégie (cassure `E + 0,1 A` sur clôture M5) |
| Horaires | impulsions 07:00-14:15, `D` ≤ 15:00 Londres | stratégie |
| Position ouverte | sous LATE une position court jusqu'à 22:55 Paris et suspend la recherche ; mais l'étude sans position ne donne que 0,17 sortie par séance | stratégie (une position à la fois, règle d'exposition) |
| Reprise | après une fin, aucune M15 commencée avant la reprise n'entre dans une fenêtre : au moins 1 h sans reconnaissance | stratégie (fiche §5.7) |
| Qualité M15/M5, cotation à `D`, exécution dans 5 min, interruption > 5 min | quelques cas | **simulation correcte** (non modifiée) |

**Conséquence** : même en convertissant chaque impulsion reconnue en transaction, l'échelle actuelle
plafonne à 1,5 par séance. Atteindre 4 à 5 exige un **changement d'échelle** (unités plus fines), pas
seulement des règles assouplies ; la campagne mesure ce que chaque levier rapporte et la distance
restante, sans présumer qu'elle est atteignable avec une espérance positive.

**Essais antérieurs à ne pas reproduire** : H1 (reconnaissance après le sommet, `p < j`), H2
(profondeur sur clôture), H3 (contexte H4), sorties partielles et protection : aucune n'est reprise ici.

## 2. Volet A : confirmation au moteur des pistes du criblage

Criblage du 2026-11-17 (`data/reports/backtests/day02_guides/`, hors Git) : effets mesurés sur les
mêmes entrées LATE ; la confirmation mesure la trajectoire réelle (reprises après une abstention,
dimensionnement sur le capital simulé, drawdown au tick). Toutes les configurations sont LATE plus une
seule modification.

| Nom | Règle (achat ; vente symétrique) |
|---|---|
| `LATE` | référence de comparaison, reproduite au commit de lancement |
| `G1A` | refus à `D` (« impulsion terminale NoWick ») si la bougie de sommet `p` est une NoWick dans le sens : `bid_open = bid_low` et `bid_close > bid_open` (vente : `bid_open = bid_high`, `bid_close < bid_open`) |
| `G5B` | refus à `D` (« créneau 07:30-09:30 New York ») si la bougie de sortie commence dans [07:30, 09:30[ `America/New_York`. **Filtre horaire**, pas un filtre d'annonces (aucun calendrier) |
| `G1A5B` | les deux refus |
| `E3` | même décision qu'à `D` (mêmes contrôles, `S`, `T`), mais **ordre limite au niveau `E`** : exécuté au premier tick `ts > D` où `ask ≤ E` (vente : `bid ≥ E`), à ce prix ; valable `]D, D + 9 M5]` ; annulé au premier tick où la cible est atteinte avant l'exécution (`ENTRÉE_ANNULÉE_CIBLE`) ; règle d'interruption existante ; sinon `ENTRÉE_EXPIRÉE`. Taille fixée à `D` sur une perte estimée depuis `E` (cotation de `D` décalée à `ask = E`, écart de `D` conservé) |

Un refus à `D` termine la configuration ; la recherche reprend à `D` (règle existante).

**Décomposition de E3** (rapprochement par `D` et sens avec LATE) : entrées exécutées (LATE → E3, à
taille LATE puis à taille E3 : effet de prix et effet de taille), entrées non exécutées (résultat LATE
perdu), entrées propres à une trajectoire (reprises), avec leurs dénominateurs.

## 3. Volet B : trois configurations pour créer des occasions

Fixées avant résultats ; aucune autre ne sera ajoutée dans ce lot.

### 3.1 `F2R` : reprise sur Failed 2 dans le drapeau (guide Failed 2s, adaptation)
- Après `F`, sur chaque M5 `k` lue (qualité, échéance et profondeur d'abord, puis cassure de
  `E + 0,1 A` inchangée), **sortie confirmée « Failed 2 »** si `bid_low_k < bid_low_{k−1}`,
  `bid_close_k ≥ bid_low_{k−1}` et `bid_high_k ≤ bid_high_{k−1}`, `k−1` la M5 précédente (pour la
  première M5 après `F`, celle qui se termine à `F`, présente et `OK`, sinon pas de Failed 2 sur `k`).
  Vente : `bid_high_k > bid_high_{k−1}`, `bid_close_k ≤ bid_high_{k−1}`, `bid_low_k ≥ bid_low_{k−1}`.
- `D` = fin de `k` ; `FL` inclut `k` ; `S = FL − 0,25 A` ; `T = E + I` ; tout le reste comme LATE.
- **Explicite dans le guide** : définition de la bougie Failed 2 (mèche au-delà de la précédente, sans
  clôture au-delà, sans balayer l'autre côté) et l'idée qu'un échec de déplacement précède un
  retournement. **Notre adaptation** : le retournement attendu est celui du **repli**, dans un drapeau
  encore valide (profondeur ≤ 50 %), dans le sens de l'impulsion : ce n'est pas une stratégie de
  retournement ; lecture sur M5 (unité de déclenchement de DAY_02), pas de M1 ni de cible H1.
- Mécanisme attendu : entrer plus tôt et convertir des drapeaux qui ne cassent jamais `E`.

### 3.2 `RSC` : reprise sans carence (reprises successives dans une tendance)
- À chaque reprise `r` (fin de configuration, refus, issue d'entrée, clôture de position), les
  fenêtres d'impulsion peuvent contenir des M15 commencées avant `r` (toujours à 07:00 ou après), mais
  la **dernière bougie `j` (= `p`) doit commencer à `ceil_m15(r)` ou après** : premier `t_j =
  ceil_m15(r) + 15 min`. Reprise de début de séance inchangée. Toutes les autres règles inchangées.
- Levée de la règle de fiche « une bougie ne sert jamais à deux configurations » ; aucune décision
  antérieure à `r`, aucun sommet reconnu rétroactivement (`p = j` reste exigé).
- Mécanisme attendu : reconnaître sans attendre une heure la reprise suivante d'une tendance (après
  une cible, un stop ou un drapeau invalidé).

### 3.3 `M5S` : même construction une échelle plus bas
- Impulsion et drapeau sur **M5** (fenêtre 4 M5, `p = j`, `o < p`, amplitude `≥ 1,5 A`, clôture forte
  0,25, au plus 6 M5 d'impulsion, au moins 2 M5 de pause, échéance `fin(p) + 30 min` plafonnée à
  15:00, profondeur 0,5) ; **`A` = ATR Wilder 14 M15** (continuité, dernière M15 terminée au début de
  la fenêtre) ; sortie sur clôture **M5** au-delà de `E + 0,1 A` (même unité que la formation, comme la
  comparaison M15 de la fiche) ; marges, stop, cible, horaires (07:00, 14:15, 14:45, 15:00) et sorties
  LATE inchangés. Reprises : grille M5.
- Mécanisme attendu : environ trois fois plus d'unités examinées ; risque connu : coûts fixes
  (glissement, prime de stop garanti) plus lourds face à des stops plus courts.

## 4. Volet C : GBP/USD et SMT (si l'acquisition aboutit)

**Acquisition** : adaptateur JForex rendu paramétrable (`--instrument`), même canal, mêmes bornes
horaires, même importeur, mêmes bougies M5/M15/H1 et même convention de qualité ; période
**[2015-01-01, 2022-01-01) seulement** (refus codé au-delà). Contrôles : comptes, heures vides,
alignement des grilles UTC avec EUR/USD.

**Séries et synchronisation** : bougies bid M5/M15 GBP/USD sur la même grille UTC que EUR/USD,
disponibles à leur `end_utc`. Une bougie GBP/USD absente ou non `OK` dans un intervalle comparé rend le
SMT **indéterminé** : aucune décision n'en dépend, cas compté à part.

- `SMTF` (filtre sur entrées LATE existantes) : à `D` d'un achat EUR/USD, **non-confirmation** si le plus
  haut GBP/USD des M5 de `F` à `D` ne dépasse pas le plus haut GBP/USD des M15 de `o` à `p` (EUR/USD fait un
  nouvel extrême, GBP/USD non) → refus ; vente symétrique sur les plus bas.
- `SMTT` (contribution au déclenchement) : après `F`, une M5 `k` où EUR/USD fait un nouveau plus bas du
  drapeau (sous tous les plus bas des pauses et M5 précédentes) alors que GBP/USD **ne fait pas** de
  nouveau plus bas sur les mêmes intervalles → sortie confirmée « SMT » à la fin de `k` (après
  profondeur et cassure) ; vente symétrique.
- **Précisions d'implémentation (2026-11-18, avant tout résultat SMT et avant l'import des données
  GBP/USD)** : extrêmes lus sur les séries bid des deux paires ; « dépasser » et « nouveau plus bas »
  sont stricts (une égalité GBP/USD ne confirme pas, n'est pas un nouvel extrême) ; SMTF lit les M15
  GBP/USD de `o` à `p` inclus et les M5 GBP/USD commencées dans `[F, D)`, rien après `D` ; SMTF
  indéterminé : entrée maintenue, événement noté ; SMTT est testé après la profondeur, la cassure (et
  rien d'autre), dans cet ordre, stop au-delà de l'extrême du drapeau bougie SMT comprise (`FL − 0,25 A`),
  cible `E + I` ; SMTT indéterminé sur `k` : pas de SMT sur `k`, compté par configuration ; sur la
  comparaison M15, les M15 GBP/USD servent de bougies de déclenchement. GBP/USD : mêmes source,
  importeur, lot M5/M15 et convention de qualité que EUR/USD, empreintes enregistrées au passage (pas de
  référence historique). Chacune est LATE plus son seul interrupteur (`smt_filter`, `smt_trigger`).
- Les formulations SMT de Matt's Wicks et de Quarterly Theory décrivent la même divergence : une seule
  famille, jamais comptée comme deux confirmations.
- **DAY_02 sur GBP/USD** : seulement avec des spécifications de contrat et de coûts GBP/USD explicites
  (`ASSUMED`, sources) ; conversion USD → EUR par la cotation EUR/USD ; résultats séparés, puis simulation
  conjointe à capital partagé et exposition contrôlée (au plus une position DAY_02 ouverte par compte, ou
  règle d'exposition présentée séparément). Si ces éléments ne sont pas réunis dans ce lot, le volet
  est rapporté comme non exécuté.

## 5. Causalité et contrôles

- Tests synthétiques : chaque règle nouvelle, troncature et altération après `T` sans effet sur ce qui
  est connu à `T`, ordre limite jamais exécuté avant `D` ni du mauvais côté, LATE inchangée (paramètres
  par défaut).
- Contrôles des passages existants (recalcul indépendant depuis chaque reprise, comparaison à l'étude
  de disponibilité de la même configuration) ; reproduction de LATE ; rejeu tronqué (→ 2015-04-01) pour
  chaque construction nouvelle (`E3`, `F2R`, `RSC`, `M5S`).

## 6. Mesures

Pour chaque configuration, sur 2015-2021 et par période 2015-2018 / 2019-2021 : transactions par
séance (dénominateur : **toutes les séances admissibles**, 1 816), par an, semaines actives, plus longue
période sans transaction ; brut, coûts, net, R net ± erreur type, PF, drawdown au tick et relatif ;
sensibilité aux coûts (glissement doublé, prime de stop garanti doublée, recalculées transaction par
transaction) ; rapprochement avec LATE par (`D`, sens) : entrées communes, retirées, ajoutées.

## 7. Lecture (fixée avant résultats, exploratoire)

- **Volet A, confirmée en trajectoire** : net supérieur à LATE sur 2015-2021 et dans chaque période ;
  sinon **non confirmée**.
- **Volet B** : **piste pour l'objectif** si fréquence ≥ 1,5 × LATE, net positif sur 2015-2021 et dans
  chaque période, R net ≥ R net LATE − une erreur type, drawdown relatif < 6 % ; **rejetée** si net ≤ 0 sur
  2015-2021 ; sinon **inconclusive**. La distance à 4-5 transactions par séance est rapportée dans tous les cas.
- Combinaisons : seulement celles enregistrées ici ; toute autre idée est présentée pour un lot ultérieur.

## 7 bis. Registre des essais

À compléter au fil des passages ; tous les essais conservés, y compris défavorables ou invalidés.

Sorties sous `data/reports/backtests/day02_frequency/` (hors Git) ; scripts de lecture et bilan chiffré
copiés dans `day02_research_annexes/frequency_lot/`, transactions sans prix dans
`day02_research_annexes/trades/`. Passage M5, scénario A, 2015-2021, 1 816 séances.

| # | Essai | Configurations | Commit | Résultat | Incident |
|---|---|---|---|---|---|
| 1 | disponibilité et performance (premier lancement) | LATE, G1A, G5B, G1A5B, E3, F2R, RSC, M5S | 380a4ef | disponibilité conforme ; rapports de performance **retenus** par le contrôle de provenance | arbre modifié pendant le passage (adaptateur JForex `--instrument`) : résultats non lus, conservés dans `withheld_dirty_tree/` |
| 2 | performance, relance | les huit | 9473895 | contrôles conformes pour sept ; E3 retenu (contrôle des reprises : 11 écarts) | E3 : l'oracle du contrôle ignorait l'issue `ENTRÉE_ANNULÉE_CIBLE` ; moteur correct ; rapport conservé dans `withheld_resume_oracle/` |
| 3 | performance E3 | E3 | 86aeb3e | contrôles conformes | correction de l'oracle et test de régression, aucun changement du moteur |
| 4 | rejeux tronqués (→ 2015-04-01) | E3, F2R, RSC, M5S | 86aeb3e | transactions et tentatives antérieures identiques au passage complet (E3 5, F2R 25, RSC 11, M5S 37 transactions ; 149 à 363 tentatives, 0 écart) | — |
| 5 | acquisition GBP/USD 2015-2021 | — | 9473895 | 22 jours incomplets au premier essai, 20 récupérés ; 2 heures vides comme EUR/USD (2016-09-02 18 h, 2019-05-26 21-23 h UTC) ; alignement : 302 M5 EUR/USD sans M5 GBP/USD, 420 M5 `OK` en EUR/USD et pas en GBP/USD | premier pipeline arrêté par sa garde « incomplet », relancé |
| 6 | disponibilité, rejeux tronqués et performance | SMTF, SMTT | 062dfd5 | contrôles conformes ; rejeux tronqués identiques (7 et 14 transactions, 159 et 158 tentatives) ; SMT indéterminé : 1 cas SMTF, 0 SMTT | — |

Aucun scénario B/C ni rejet requis, sauf **M5S** : une transaction indéterminée (2018-08-20, silence de
6 min pendant la position) demande B et C, **non exécutés** ; une seule transaction au stop garanti ne
peut pas changer la lecture de M5S (net −337,29 €). **DAY_02 sur GBP/USD** (volet C, dernier point) :
**non exécuté** (spécifications de contrat et de coûts GBP/USD non réunies).

## 8. Bilan (exploratoire)

### 8.1 Tableau 2015-2021 (M5, scénario A, coûts et risque ADR-035)

R = net / perte estimée au stop à la décision ; ± = erreur type ; DD = drawdown relatif au tick ;
« coûts ×2 » = glissement et prime de stop garanti doublés, transaction par transaction.

| | Trans. | /séance | Sem. actives | Max sans (j) | Brut € | Coûts € | **Net €** | R net | PF | DD | Net 15-18 | Net 19-21 | Coûts ×2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LATE | 296 | 0,163 | 59 % | 37 | 112,79 | 76,48 | **+36,32** | +0,029 ± 0,064 | 1,06 | 2,55 % | +5,29 | +31,03 | −33,44 |
| G1A | 269 | 0,148 | 57 % | 37 | 150,89 | 68,52 | **+82,37** | +0,077 ± 0,067 | 1,16 | 2,53 % | +16,26 | +66,11 | +19,53 |
| G5B | 246 | 0,135 | 53 % | 55 | 162,05 | 62,93 | **+99,12** | +0,095 ± 0,071 | 1,21 | 1,94 % | +40,64 | +58,48 | +42,06 |
| G1A5B | 225 | 0,124 | 50 % | 55 | 183,82 | 56,75 | **+127,07** | +0,131 ± 0,074 | 1,30 | 1,87 % | +45,75 | +81,32 | +75,25 |
| E3 | 207 | 0,114 | 44 % | 68 | 164,53 | 75,25 | **+89,28** | +0,091 ± 0,094 | 1,18 | 2,80 % | +48,94 | +40,33 | +20,16 |
| F2R | 694 | 0,382 | 88 % | 27 | 348,55 | 432,41 | **−83,86** | −0,022 ± 0,068 | 0,96 | 7,06 % | −14,41 | −69,45 | −493,01 |
| RSC | 351 | 0,193 | 63 % | 37 | 90,36 | 90,92 | **−0,56** | −0,014 ± 0,058 | 1,00 | 3,34 % | −4,64 | +4,07 | −82,92 |
| M5S | 888 | 0,489 | 94 % | 17 | 23,89 | 361,19 | **−337,29** | −0,099 ± 0,035 | 0,83 | 18,92 % | −157,78 | −179,51 | −681,98 |
| SMTF | 146 | 0,080 | 34 % | 83 | 91,24 | 36,95 | **+54,29** | +0,082 ± 0,094 | 1,19 | 2,10 % | +5,30 | +48,99 | +20,35 |
| SMTT | 594 | 0,327 | 85 % | 23 | 148,48 | 411,09 | **−262,61** | −0,103 ± 0,074 | 0,85 | 15,69 % | −225,02 | −37,59 | −657,89 |

### 8.2 Rapprochement avec LATE par (`D`, sens)

| | Communes | Net LATE → config. sur communes € | Retirées (net LATE €) | Ajoutées (net €) |
|---|---:|---:|---:|---:|
| G1A | 268 | 79,06 → 77,55 | 28 (−42,74) | 1 (+4,82) |
| G5B | 246 | 97,93 → 99,12 | 50 (−61,61) | 0 |
| G1A5B | 224 | 118,71 → 122,25 | 72 (−82,39) | 1 (+4,82) |
| E3 | 206 | −80,62 → +86,05 | 90 non exécutées (+116,94) | 1 (+3,23) |
| F2R | 175 | 15,60 → 14,78 | 121 (+20,72) | 519 (−98,64) |
| RSC | 284 | 33,97 → 54,58 | 12 (+2,35) | 67 (−55,15) |
| M5S | 2 | −8,47 → −8,19 | 294 (+44,78) | 886 (−329,10) |
| SMTF | 144 | 53,31 → 53,57 | 152 (−17,00) | 2 (+0,72) |
| SMTT | 255 | −9,39 → +6,78 | 41 (+45,71) | 339 (−269,40) |

- **E3** : les 90 entrées non exécutées (79 expirées, 11 annulées sur cible) sont les meilleures de LATE
  (sélection adverse) ; sur les 206 exécutées, le meilleur prix rapporte +68,25 € à taille LATE ; écart
  apparié +0,168 ± 0,164 R.
- **SMTF** : 155 refus à `D` sur 303 sorties confirmées.
- **SMTT** : 339 sorties « SMT » parmi les transactions (−269,40 €, R −0,171 ± 0,119, 85 % au stop) ;
  255 sorties par cassure (+6,78 €, R −0,013). Sans position, 625 sorties confirmées (358 SMT).

### 8.3 Transactions par séance, par année

| | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Séances | 259 | 260 | 259 | 259 | 259 | 260 | 260 |
| LATE | 0,166 | 0,131 | 0,181 | 0,174 | 0,158 | 0,169 | 0,162 |
| G1A | 0,147 | 0,119 | 0,170 | 0,158 | 0,143 | 0,158 | 0,142 |
| G5B | 0,135 | 0,115 | 0,154 | 0,151 | 0,131 | 0,123 | 0,138 |
| G1A5B | 0,124 | 0,108 | 0,143 | 0,135 | 0,120 | 0,112 | 0,127 |
| E3 | 0,135 | 0,092 | 0,154 | 0,100 | 0,108 | 0,092 | 0,115 |
| F2R | 0,409 | 0,338 | 0,402 | 0,402 | 0,359 | 0,388 | 0,377 |
| RSC | 0,193 | 0,158 | 0,205 | 0,212 | 0,193 | 0,204 | 0,188 |
| M5S | 0,498 | 0,488 | 0,490 | 0,498 | 0,459 | 0,515 | 0,473 |
| SMTF | 0,081 | 0,042 | 0,073 | 0,100 | 0,073 | 0,096 | 0,096 |
| SMTT | 0,317 | 0,312 | 0,386 | 0,336 | 0,301 | 0,312 | 0,327 |

Distance à l'objectif de 4 à 5 transactions par séance : la plus fréquente (M5S, 0,49) en est à un
facteur 8 à 10, avec une espérance nette négative.

### 8.4 Lecture enregistrée (§7)

- **Volet A** : G1A, G5B, G1A5B et E3 **confirmées en trajectoire** (net supérieur à LATE sur 2015-2021 et
  dans chaque période).
- **Volet B** : F2R, RSC et M5S **rejetées** (net ≤ 0 sur 2015-2021).
- **Volet C** : SMTF lue comme le volet A, **confirmée de justesse** (2015-2018 : +5,30 € contre +5,29 €) ;
  SMTT lue comme le volet B, **rejetée**. DAY_02 sur GBP/USD non exécuté.

### 8.5 Limites

- Toutes les configurations confirmées sont des **filtres** : elles réduisent la fréquence (0,08 à
  0,15 par séance contre 0,163), à l'opposé de l'objectif. Toutes celles qui l'augmentent perdent :
  les transactions ajoutées ont une espérance brute trop faible pour couvrir des coûts fixes par
  transaction (glissement, prime de stop garanti) ; voir `day02_research_annexes/cost_wall/`.
- Aucune espérance nette ne dépasse deux erreurs types (G1A5B : environ 1,8).
- G1A, G5B et E3 viennent du criblage des guides (`day02_research_annexes/guides_screening/`) sur les
  **mêmes années** : leur confirmation en trajectoire vérifie l'effet moteur, pas son existence hors
  échantillon ; G1A5B cumule deux sélections.
- G5B est un filtre horaire (aucun calendrier d'annonces) ; E3 suppose une exécution de l'ordre limite
  au premier tick qui touche `E`, sans file d'attente.
- Années 2015-2021 déjà examinées par de nombreux essais ; 2022-2025 non lues.

### 8.6 Recommandation

Aucune décision n'est prise par ce bilan. Si l'opérateur le souhaite : épreuve hors échantillon
(2022-2023) d'une configuration figée, par exemple G1A5B, sous protocole distinct gelé avant lecture ;
la fréquence visée de 4 à 5 par séance demanderait une autre construction que DAY_02 (lot ultérieur).
