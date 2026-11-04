# Fiche DAY_01 — Cassure du range précédant Londres et retest (day trading)

> Identifiant code : `DAY_01` (candidate « D1 » du cahier des charges ; dans le code, `1d` désigne
> la bougie journalière). Statut : **candidate en cours de spécification** (cahier §6.6) :
> **aucun moteur, aucun test, aucun passage**. Les valeurs numériques de cette fiche sont des
> **propositions** (ASSUMP-027, `PROPOSED`), choisies a priori, sans lecture de données ni
> optimisation ; elles attendent la validation de l'opérateur. Instrument : **EUR/USD seulement**.
> Aucune donnée 2022-2025. Ni validation de performance ni autorisation de trading.

**Libellés.** Comme dans les fiches S2 et S3, **H4, H1, M15 et M5 désignent des unités de temps**,
et « D1 » la bougie journalière seulement là où le contexte l'exige. Les heures sont données **en
heure locale de Londres** (`Europe/London`, GMT l'hiver, BST l'été), sauf mention « UTC » ou
« New York ».

**Ce qui est imposé et ce qui est proposé.** Chaque section sépare :
- **Exigé (cahier v1.2)** : contraintes du cahier des charges, paraphrasées avec leur section ;
- **Proposé (ASSUMP-027)** : valeurs et conventions de cette fiche, à valider (§11).

## 1. Hypothèse de marché et références

- **Hypothèse** : pendant les heures calmes qui précèdent l'ouverture de Londres, EUR/USD trace un
  range étroit. Ses bornes concentrent des ordres (stops et ordres conditionnels). L'arrivée de la
  liquidité européenne franchit souvent l'une d'elles. Après une cassure confirmée, un retour sur
  la borne franchie, qui tient, permet d'entrer avec un stop proche.
- **Appui** : le mécanisme de franchissement de niveaux et de réaction aux ordres conditionnels
  décrit par Osler [R4] (cahier §17). La session de Londres et le retest sont des **hypothèses
  supplémentaires**, que cette étude ne valide pas (cahier §6.3).
- **Faiblesses attendues** (cahier §6.3) :
  - faux départs : cassure suivie d'un retour durable dans le range ;
  - range trop étroit (bruit, coûts) ou trop large (stop éloigné, taille minimale) ;
  - annonces économiques : saut au-delà du stop ou de la cible (§3.4).
- **Risques partagés** : le cahier note que D1 et C3 peuvent partager des risques (§6.6). Le
  chevauchement avec S1, S2 et S3 sera mesuré (§9).

## 2. Exigences du cahier v1.2 pour cette candidate

| Exigence | Section du cahier |
|---|---|
| Fenêtre de construction du range fixée à l'avance, en heure locale de Londres, changements d'heure compris | §6.3 |
| Cassure confirmée, puis retour sur la frontière, puis clôture qui maintient le franchissement ; entrée après cette confirmation | §6.3 |
| Stop derrière le retest ; abandon si le délai de retest est dépassé | §6.3 |
| Cible sur un niveau prédéfini **ou** un multiple du risque, en **variantes séparées** | §6.3 |
| À fixer : heures, largeur admissible, marges, délai, nombre de tentatives | §6.3 |
| Heure de liquidation de fin de session explicite ; aucune position la nuit dans la version initiale | §6.3 |
| Unités indicatives : H1/H4 → M15 → M5 ; contexte → configuration → déclenchement ; variante plus simple en comparaison | §6.1, §6.5 |
| Bougies clôturées seulement ; fuseau, ancrage et changements d'heure fixés, identiques en historique et en direct | §5, §6.5 |
| Contenu de la fiche : références, régime, paramètres, chronologie, invalidation, stop, cible, sortie temporelle, conservation nocturne, **calendrier d'annonces**, coûts, critères de rejet, protocole | §6.6 |
| Day trading : horaires, heure d'été, liquidation de session et annonces à intégrer à l'évaluation | §9 |
| Exécution au premier prix ultérieur admissible ; achat à l'ask, vente au bid ; résolution plus fine si stop et cible tombent dans la même bougie | §9 |
| Risque de 0,25 % des fonds propres ; signal refusé si la taille minimale dépasse le budget | §8 |
| Partitions : 2015-2021 développement ; 2022-2023 et 2024-2025 réservées | §9 |
| Données économiques sans historique de publication : pas de reproduction d'une décision ancienne | §5 |

## 3. Données, unités et conventions

### 3.1 Rôle de chaque unité (proposé)

| Unité | Rôle dans la référence | Ancrage |
|---|---|---|
| **H4** | **contexte de volatilité seulement** : ATR Wilder 14 H4 `A`, figé au gel du range (§4.1). Aucun filtre de direction dans la référence | New York 17:00, comme S1 à S3 |
| **M15** | **configuration** : construction du range ; cassure confirmée par une clôture M15 | grille de 15 min UTC |
| **M5** | **déclenchement** : retour sur la borne, invalidation, clôture de confirmation, extrême du retest pour le stop | grille de 5 min UTC |
| H1 | non utilisée dans la référence | — |

Les décalages de Londres et de New York avec UTC sont des nombres entiers d'heures. Les bornes
M15 et M5 tombent donc aux mêmes instants en UTC, à Londres et à New York.

**Variante plus simple, enregistrée comme comparaison** (cahier §6.5) : **M15 seule**. Le retest,
l'invalidation, la confirmation et le stop sont lus sur M15 au lieu de M5, avec les mêmes règles
et les mêmes délais. Elle ne remplace pas la référence.

### 3.2 Série, disponibilité et états de bougie

- Série de calcul : **bid** pour le range, la cassure, le retest et la confirmation. Le stop d'une
  vente utilise l'`ask_high`, comme S2 et S3 (§5).
- Disponibilité : `available_at_utc = end_utc + L`, latence `L = 0`, comme S1 (§5 de S1,
  ADR-006). Décision à `D = available_at_utc` de la bougie qui la déclenche, avec les seules
  bougies disponibles à `D`.
- Bougie **utilisable** : `OK` ou `FERMETURE_DOCUMENTÉE` (S1 §10.1). Une M15 ou une M5 **prévue
  mais absente**, ou présente mais **inutilisable**, rompt la règle qui en a besoin (§4, §8). Ces
  états seront définis par le lot de données M15/M5 (§10), pas par cette fiche.

### 3.3 Heure de Londres et changements d'heure

- Les fenêtres sont fixées en heure de Londres. Leur traduction en UTC change avec l'heure d'été
  britannique : GMT = UTC, BST = UTC+1.
- De 2015 à 2021, les changements d'heure britanniques et américains ont tous lieu **un dimanche,
  pendant la fermeture hebdomadaire** (vendredi 17:00 à dimanche 17:00 New York) :

  | Année | US mars | UK mars | UK octobre | US novembre |
  |---|---|---|---|---|
  | 2015 | 08/03 | 29/03 | 25/10 | 01/11 |
  | 2016 | 13/03 | 27/03 | 30/10 | 06/11 |
  | 2017 | 12/03 | 26/03 | 29/10 | 05/11 |
  | 2018 | 11/03 | 25/03 | 28/10 | 04/11 |
  | 2019 | 10/03 | 31/03 | 27/10 | 03/11 |
  | 2020 | 08/03 | 29/03 | 25/10 | 01/11 |
  | 2021 | 14/03 | 28/03 | 31/10 | 07/11 |

  Aucune fenêtre de séance ne chevauche donc un changement d'heure.
- Pendant les **semaines de décalage** (deux à trois semaines en mars, une semaine en
  octobre-novembre), New York est à 4 h de Londres au lieu de 5 h. Le début de la journée de
  cotation (17:00 New York) tombe alors à 21:00 Londres au lieu de 22:00, et les bornes H4 se
  décalent d'une heure en heure de Londres. Les fenêtres DAY_01 ne bougent pas en heure de
  Londres ; seule la dernière H4 disponible au gel peut changer (§4.1). Les résultats seront
  ventilés pour ces semaines (§9).

### 3.4 Annonces économiques (limite de la référence)

- **Référence : aucun filtre d'annonces**, faute de calendrier historique disponible avec les
  heures de publication. Le cahier refuse de reproduire une décision ancienne à partir de données
  sans historique de publication (§5).
- Conséquence : des cassures, retests et stops pendant des annonces (par exemple vers 09:00-10:00
  Londres pour la zone euro, ou 13:30 Londres pour les États-Unis) entrent dans les résultats.
  Leur effet n'est pas isolé.
- Un filtre d'annonces relèvera d'un **protocole distinct**, après acquisition d'un calendrier
  historique horodaté et contrôlé. Il ne sera pas réglé sur les résultats de la référence.

## 4. Range, cassure, retest et entrée (achat ; vente au §4.6)

Une **séance** est un jour ouvré du lundi au vendredi, en heure de Londres. Pas de séance le
25 décembre ni le 1er janvier (« jour férié probable », ASSUMP-023), ni un jour où la fenêtre du
range tombe dans une fermeture.

### 4.1 Construction et gel du range (proposé)

- **Fenêtre du range** : les 28 M15 qui commencent de **01:00 à 07:45 Londres**, soit
  [01:00, 08:00) Londres :
  - en UTC, [01:00, 08:00) en GMT et [00:00, 07:00) en BST ;
  - la fenêtre commence après le début de la journée de cotation (21:00 ou 22:00 Londres la
    veille) et laisse de côté l'heure qui suit la clôture de New York, où les spreads
    s'élargissent.
- **Bornes** : `RH` = plus haut `bid_high` et `RL` = plus bas `bid_low` des 28 M15 ; hauteur
  `H = RH − RL`. Pour le stop d'une vente : `RAH` = plus haut `ask_high`.
- **Gel** : à `G` = 08:00:00 Londres, disponibilité de la M15 [07:45, 08:00). Le range n'est
  plus jamais modifié ensuite.
- **Complétude** : les 28 M15 doivent être présentes et utilisables. Sinon, aucune séance ce
  jour-là (« range incomplet »), sans range partiel.
- **ATR `A`** : Wilder 14 H4, true range bid, continuité des H4 prévues (règle de S2 et S3),
  calculé sur la dernière H4 disponible à `G`. Il est figé pour la séance. Non calculable :
  aucune séance.
- **Largeur admissible** : `0,5 × A ≤ H ≤ 2 × A`. En dessous, range trop étroit (bruit, coûts) ;
  au-dessus, range trop large (stop éloigné, taille minimale, comme les refus de taille observés
  sur S3, ADR-020). Hors bornes : aucune séance, journalisée avec `H / A`.

### 4.2 Cassure confirmée (proposé)

- **Fenêtre de cassure** : M15 qui commencent de 08:00 à 10:45 Londres. Leur clôture est connue
  de 08:15 à 11:00.
- **Cassure haussière** : première M15 de la fenêtre dont `bid_close > RH + 0,1 × A`. Une clôture
  au-delà de `RH` mais en deçà de la marge n'est pas une cassure.
- Instant `K` = disponibilité de cette M15. La cassure consomme la séance (§4.5).
- **Données** : une M15 de la fenêtre absente ou inutilisable met fin à la recherche de cassure
  pour la séance, sans supposer de clôture.
- Aucune cassure confirmée à 11:00 : séance sans signal.

### 4.3 Retest, invalidation et confirmation (proposé)

Zone de retest : `[RH − 0,1 × A, RH + 0,1 × A]`. Les M5 lues sont celles qui commencent à `K` ou
après.

1. **Retour** : première M5 dont `bid_low ≤ RH + 0,1 × A`. Cette M5 est la **M5 de retest**.
2. **Invalidation** : toute M5, depuis `K` jusqu'à la confirmation, dont `bid_close < RH − 0,1 × A`.
   La tentative échoue (fausse cassure) et la séance est consommée.
3. **Confirmation** : première M5, à partir de la M5 de retest incluse, dont `bid_close > RH`,
   sans invalidation auparavant. Une clôture dans la zone mais en deçà ou à `RH` ne confirme pas
   et n'invalide pas ; on attend la M5 suivante.
4. **Délai maximal** : la M5 de confirmation doit se terminer au plus tard à `K + 60 min`
   (12 M5). Sinon, abandon (« délai de retest dépassé »), y compris quand le prix est parti sans
   revenir : pas de poursuite du prix.
5. **Données** : une M5 absente ou inutilisable entre `K` et la confirmation entraîne l'abandon
   de la tentative.

L'entrée la plus tardive possible est donc à 12:00 Londres (cassure connue à 11:00, plus 60 min).

### 4.4 Décision d'entrée (instant `D`)

`D` = disponibilité de la M5 de confirmation. Entrée décidée si :
- aucune position DAY_01 ouverte, ce qui est garanti par une seule tentative par séance ;
- marché ouvert à `D` ;
- `D` antérieur à la liquidation de 16:00 ;
- taille admise par le budget de risque (§6.2).

### 4.5 Nombre de tentatives (proposé)

**Une seule tentative par séance**. La première cassure confirmée consomme le range, quelle que
soit l'issue : entrée, invalidation, délai dépassé, données manquantes ou refus. Pas de seconde
cassure dans l'autre sens. Une variante à deux tentatives relèverait d'un protocole distinct.

### 4.6 Vente (règle symétrique)

- Cassure : `bid_close < RL − 0,1 × A`.
- Zone : `[RL − 0,1 × A, RL + 0,1 × A]`.
- Retour : `bid_high ≥ RL − 0,1 × A` (série bid, comme l'achat).
- Invalidation : `bid_close > RL + 0,1 × A`.
- Confirmation : `bid_close < RL`.
- Stop : au-dessus du plus haut `ask_high` du retest (§5).

## 5. Stop, cible et liquidation (proposé)

- **Stop** (achat) : plus bas `bid_low` des M5, de la M5 de retest à la M5 de confirmation
  incluses, moins `0,25 × A` (marge de S2 et S3). Pour une vente : plus haut `ask_high` de ces
  M5, plus `0,25 × A`. Il est fixé à `D` et n'est jamais déplacé. Stop **garanti simulé** avec sa
  prime, comme les références S1 à S3 (arbitrage au §11).
- **Cible de référence : multiple du risque.** Soit `P_D` le dernier ask connu strictement avant
  `D` (bid pour une vente). Cible `T = P_D + 1,5 × (P_D − S)` pour un achat, `T = P_D − 1,5 × (S − P_D)`
  pour une vente. Elle est connue à `D`, avant l'exécution. Exécution à la première cotation
  exécutable observée qui l'atteint (bid ≥ T à l'achat, ask ≤ T à la vente), au prix de cette
  cotation, comme S2.
- **Variante séparée : cible sur niveau prédéfini.** Projection de la hauteur du range :
  `RH + H` à l'achat, `RL − H` à la vente. Exigée par le cahier comme **variante séparée** :
  protocole distinct, non lancée avec la référence (§11).
- **Liquidation de fin de séance : 16:00 Londres.**
  - Toute position encore ouverte reçoit à 16:00:00 un ordre de clôture au marché, exécuté au
    **premier tick strictement postérieur** (bid pour un achat, ask pour une vente).
  - 16:00 Londres tombe toujours avant la clôture de New York (17:00 New York = 21:00 ou 22:00
    Londres) : aucune nuit, donc aucun financement.
- **Aucune cotation à 16:00** : convention proposée, sans prix invisible.
  1. Aucun prix n'est supposé à 16:00. La position reste ouverte, avec son stop et sa cible,
     jusqu'au premier tick postérieur, qui l'exécute. Le délai est journalisé
     (`LIQUIDATION_RETARDÉE`, avec sa durée).
  2. Si ce premier tick franchit déjà le stop ou la cible, la priorité du moteur s'applique : le
     stop d'abord (ASSUMP-024), puis la cible, puis la liquidation en attente.
  3. Si le silence est une interruption inexpliquée pendant laquelle le stop ou la cible ont pu
     être franchis sans être observés, la transaction est **indéterminée**. Les scénarios A, B et
     C s'appliquent comme pour S2 (§6.4).
  4. Si aucun tick n'arrive avant la fin de la journée de cotation (fermeture anticipée non
     documentée), la liquidation se fait au premier tick de la réouverture, écart compris. La
     position a alors passé une nuit : le cas est **compté et rapporté**, jamais masqué
     (`NUIT_NON_PRÉVUE`).
- **Pas de sortie temporelle intermédiaire** : seuls le stop, la cible ou la liquidation de 16:00
  ferment la position.

## 6. Exécution et risque

### 6.1 Chronologie

Mêmes règles que S1 (§5 de S1, ASSUMP-024, ADR-009) :
- décision à `D` sur l'état strictement antérieur à `D` ;
- exécution au premier tick `ts > D`, achat à l'ask et vente au bid ;
- un tick horodaté exactement à `D` est rejoué après la décision ;
- stop déjà franchi au premier tick d'exécution : exécutée puis liquidée (référence), rejet en
  variante si nécessaire.

### 6.2 Taille et coûts

- Taille : 0,25 % des fonds propres estimés à `D`, perte au stop avec coûts, minimum 0,1 contrat,
  incrément 0,1, comme les références S1 à S3.
- Les stops courts du retest donnent des tailles supérieures au minimum. Les coûts fixes par
  contrat (glissement, prime de stop garanti) pèsent donc plus en proportion du risque : ils sont
  rapportés à part.
- Coûts : `RESEARCH_COSTS` (glissement 0,5 pip, commission 0, conversion 0,5 %, prime de stop
  garanti). Pas de financement, puisqu'il n'y a pas de nuit, sauf `NUIT_NON_PRÉVUE`.

### 6.3 Résolution fine

Les ticks résolvent l'ordre du stop et de la cible. Si ni les ticks ni les M5 ne permettent de
trancher (trou de cotation), la transaction est indéterminée et les scénarios A, B et C
s'appliquent.

## 7. Exemple horodaté (achat, données inventées)

Mardi 12 février 2019, en heure d'hiver : Londres = UTC. ATR H4 figé `A = 0,00200` (20 pips),
calculé sur la H4 [02:00, 06:00) UTC, disponible à 06:00.

| Instant (Londres = UTC) | Événement | Connu à cet instant |
|---|---|---|
| 01:00 → 08:00 | 28 M15 du range | — |
| **08:00:00** | M15 [07:45, 08:00) disponible : **range figé** | `RH = 1,13250`, `RL = 1,13050`, `H = 20 pips = 1,0 × A`, dans [0,5 ; 2] × `A` |
| 08:15:00 | M15 [08:00, 08:15) clôture à 1,13262 | au-delà de `RH`, mais pas de `RH + 0,1 × A = 1,13270` : pas de cassure |
| **08:30:00** | M15 [08:15, 08:30) clôture à 1,13291 > 1,13270 | **cassure haussière**, `K = 08:30` ; zone [1,13230 ; 1,13270] ; délai jusqu'à 09:30 |
| 08:35:00 | M5 [08:30, 08:35) : plus bas 1,13275 | pas de retour |
| 08:40:00 | M5 [08:35, 08:40) : plus bas 1,13262 ≤ 1,13270, clôture 1,13248 | **retest** ; clôture ≤ `RH` (pas de confirmation) et ≥ 1,13230 (pas d'invalidation) |
| **08:45:00** | M5 [08:40, 08:45) : plus bas 1,13241, clôture 1,13259 > `RH` | **signal connu**, `D = 08:45:00.000` |
| 08:45:00.000 | décision | stop `S = 1,13241 − 0,00050 = 1,13191` ; dernier ask avant `D` : 1,13261 (08:44:59.870) ; cible `T = 1,13261 + 1,5 × 0,00070 = 1,13366` |
| 08:45:00.000 | tick horodaté exactement à `D` | **pas utilisé pour l'entrée** (exécution à `ts > D`) |
| **08:45:00.140** | premier tick postérieur à `D`, ask 1,13262 | **entrée** à 1,13262 ; taille selon §6.2 |
| 10:12:31.405 | premier bid ≥ 1,13366 (bid 1,13367) | sortie à la cible, à 1,13367 |
| (sinon) 16:00:00 | liquidation | au premier tick postérieur à 16:00:00 |

Le même jour en heure d'été (par exemple le mardi 9 juillet 2019, BST), toutes les heures de
Londres sont identiques. En UTC, le range va de 00:00 à 07:00, le gel a lieu à 07:00:00 UTC et la
liquidation à 15:00:00 UTC.

## 8. Abstentions (première cause journalisée)

Dans l'ordre d'évaluation, une seule cause par séance :
1. pas de séance : jour férié probable, ou fermeture ;
2. range incomplet : M15 absente ou inutilisable dans la fenêtre ;
3. ATR H4 non calculable ;
4. range hors largeur admissible (`H / A` journalisé) ;
5. données manquantes pendant la recherche de cassure ;
6. aucune cassure confirmée à 11:00 ;
7. invalidation (fausse cassure) ;
8. délai de retest dépassé ;
9. données manquantes pendant le retest ;
10. marché fermé à `D` ;
11. taille minimale supérieure au budget.

Comme pour S3, les motifs sont comptés **au premier blocage** : un blocage à une étape ne dit
rien des étapes suivantes.

## 9. Protocole de test (à figer avant chaque étape)

1. **Lot de données M15/M5** (§10) : construction et audit de couverture 2015-2021, **avant** tout
   moteur DAY_01.
2. **Moteur et tests synthétiques** : exemple du §7 reproduit, vente, changement d'heure, chacune
   des abstentions du §8, liquidation sans cotation, `NUIT_NON_PRÉVUE`.
3. **Non-régression** : rejeu S1 si un moteur partagé est modifié.
4. **Disponibilité** 2015-2021 : séances attendues, ranges complets, ranges admissibles, cassures,
   retests, sans exécution.
5. **Performance** 2015-2021 : référence H4 → M15 → M5 en scénario A, comparaison M15 seule, B, C
   ou rejet selon des conditions de déclenchement fixées à l'avance, comme pour S2 et S3.

Rapportés, en plus des mesures du cahier (§9) et de celles de S3 :
- parcours des séances aux entrées ;
- résultats par jour de la semaine, par heure d'entrée, en heure d'hiver ou d'été et pendant les
  semaines de décalage ;
- liquidations à 16:00 et liquidations retardées ;
- chevauchement et pertes simultanées avec S1, S2 et S3 ;
- part des séances avec annonces non mesurable (limite du §3.4).

## 10. Préalable : lot de données M15/M5 (distinct, à venir)

Les bougies M15 et M5 **n'existent pas encore** : le code ne construit que H1, H4 et D1
(`history/calendar.py`). Les ticks EUR/USD 2015-2021 sont présents en local. Un lot distinct
devra construire ces bougies et **auditer leur couverture avant l'implémentation du moteur
DAY_01** (cahier §14 : couverture auditée avant le passage des données à la recherche). Il devra
couvrir :

- **Agrégation bid/ask depuis les ticks locaux** :
  - OHLC bid et ask séparés, nombre de ticks ;
  - même méthode que les H1, H4 et D1 existantes, aucun comblement ;
  - contrôle de cohérence : trois M5 complètes forment la M15 correspondante, quatre M15 la H1
    existante (mêmes prix extrêmes, ouverture et clôture) ;
  - le nombre de ticks est une activité du fournisseur, pas un volume de marché (cahier §5).
- **Bornes des bougies** : `[start_utc, end_utc)` sur la grille de 5 et 15 minutes UTC ; un tick
  exactement à une borne appartient à la bougie qui commence ; aucun tick hors de sa bougie ni
  compté deux fois.
- **Changements d'heure de Londres** :
  - fenêtres DAY_01 converties en UTC pour chaque séance 2015-2021, avec les dates du §3.3 ;
  - tests autour de chaque changement britannique et américain, et des semaines de décalage ;
  - aucune séance qui chevauche un changement.
- **Bougie absente ou inutilisable** : calendrier des créneaux M15 et M5 prévus, selon la
  fermeture hebdomadaire et les jours fériés probables.
  - **Absente** : créneau prévu sans aucun tick.
  - **Inutilisable** : bougie présente mais touchée par un silence au-delà du seuil
    (`INTERRUPTION_INEXPLIQUÉE`), par une fermeture ou par un jour férié probable.
  - À 5 minutes, un créneau calme sans tick n'est pas forcément une panne. Le lot devra mesurer
    la fréquence de ces créneaux dans les fenêtres DAY_01 (01:00-16:00 Londres) et proposer une
    règle avant le moteur.
- **État connu à la clôture** : l'état d'une bougie à son `available_at_utc` ne doit utiliser
  que l'information connue à cet instant, distinct de l'audit a posteriori (ADR-006). Un silence
  commencé dans la bougie et qui se prolonge après sa clôture n'est connu, à la clôture, que
  pour sa partie déjà écoulée.
- **Couverture** : par année, et dans les fenêtres DAY_01 :
  - créneaux prévus, absents et inutilisables ;
  - séances avec un range complet ;
  - séances avec les M5 complètes de 08:00 à 12:00.
- **Bornes** : 2015-2021 seulement, lecteur refusant 2022-2025 ; sorties hors Git (`data/`).

## 11. Arbitrages à valider par l'opérateur

| # | Point | Proposition de référence | Alternatives |
|---|---|---|---|
| 1 | Fenêtre du range | [01:00, 08:00) Londres, 28 M15 | [00:00, 08:00) ; [00:00, 07:00) |
| 2 | Rôle de H4 / H1 | H4 pour l'ATR seulement, pas de filtre de direction ; H1 non utilisée | filtre de direction H4 ou H1, en variante distincte |
| 3 | Largeur admissible | `0,5 × A ≤ H ≤ 2 × A`, `A` = ATR Wilder 14 H4 | ATR D1 ; bornes en pips |
| 4 | Confirmation de cassure | clôture M15 au-delà de la borne de plus de `0,1 × A`, de 08:15 à 11:00 | sans marge ; fenêtre plus courte |
| 5 | Retest | M5 qui touche la zone `± 0,1 × A`, puis clôture M5 au-delà de la borne ; invalidation par une clôture en deçà de la zone | confirmation sur la M5 suivant le retest seulement |
| 6 | Délai de retest | 60 min (12 M5) après `K` | 30 ou 90 min |
| 7 | Tentatives | une par séance | deux (protocole distinct) |
| 8 | Stop | extrême du retest ± `0,25 × A`, garanti simulé | stop normal, si la distance minimale du stop garanti chez IG exclut les stops courts (ASSUMP-008, non confirmé) |
| 9 | Cible | `1,5 ×` le risque depuis le dernier prix connu avant `D` | `1 ×` ou `2 ×` ; variante séparée : `RH + H` / `RL − H` |
| 10 | Liquidation | 16:00 Londres, au premier tick postérieur ; convention du §5 si aucune cotation | 15:00 ou 16:30 |
| 11 | Annonces | aucun filtre (limite inscrite au §3.4) | filtre en protocole distinct, après calendrier historique |
| 12 | Variante simple | M15 seule | — |
| 13 | Instrument | EUR/USD seulement | GBP/USD (cahier §2), après données et décision |
| 14 | Ordre des lots | lot M15/M5 (construction et audit) avant le moteur | — |
