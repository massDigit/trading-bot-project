# Campagne exploratoire DAY_02 : fréquence, confirmations des guides et SMT (2015-2021, M5)

**Statut** : campagne **exploratoire** autorisée par l'opérateur le 2026-11-17 (ADR-039). Définitions,
paramètres, mesures et lecture ci-dessous sont **fixés et enregistrés au commit de lancement, avant
tout résultat des configurations nouvelles**. LATE (ADR-037) reste la référence de comparaison,
inchangée et reproduite. Les années 2015-2021 ont déjà été examinées : rien ici n'est une validation.
Aucune donnée 2022-2025, aucun ordre, aucune fusion. Coûts, capital et risque de l'ADR-035 inchangés
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
