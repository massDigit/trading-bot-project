# Fiche DAY_01 — Cassure du range précédant Londres et retest (day trading)

> Identifiant code : `DAY_01` (candidate « D1 » du cahier des charges ; dans le code, `1d` désigne
> la bougie journalière). Statut : **fiche figée le 2026-11-05** (ASSUMP-027 `APPROVED`, ADR-022 ;
> conventions de données et d'interruption : ADR-021), portée **recherche hors ligne**. Aucun
> passage historique. Les valeurs numériques ont été choisies a priori, sans lecture de résultats
> ni optimisation ; elles ne seront pas modifiées au vu des résultats. Instrument : **EUR/USD seulement**.
> Aucune donnée 2022-2025. Ni validation de performance ni autorisation de trading.

**Libellés.** Comme dans les fiches S2 et S3, **H4, H1, M15 et M5 désignent des unités de temps**,
et « D1 » la bougie journalière seulement là où le contexte l'exige. Les heures sont données **en
heure locale de Londres** (`Europe/London`, GMT l'hiver, BST l'été), sauf mention « UTC » ou
« New York ».

**Ce qui est imposé et ce qui est proposé.** Chaque section sépare :
- **Exigé (cahier v1.2)** : contraintes du cahier des charges, paraphrasées avec leur section ;
- **Proposé (ASSUMP-027)** : valeurs et conventions de cette fiche, retenues au gel (§11).

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

**Variante plus simple, enregistrée comme comparaison** (cahier §6.5) : **« H4 → M15, retest et
confirmation sur M15 »**. Elle garde l'ATR H4 et le range M15 ; le retest, l'invalidation, la
confirmation et le stop sont lus sur M15 au lieu de M5, avec les mêmes règles et le même délai de
60 min. La première confirmation possible est donc à `K + 15 min` (contre `K + 5 min` en
référence), soit `K + 15 min ≤ D ≤ K + 60 min`. La fraîcheur à la décision porte sur la M15 de
confirmation. La validité de l'entrée reste de **5 minutes après `D`**. Elle ne remplace pas la
référence.

### 3.2 Série, disponibilité et états de bougie

- Série de calcul : **bid** pour le range, la cassure, le retest et la confirmation. Le stop d'une
  vente utilise l'`ask_high`, comme S2 et S3 (§5).
- Disponibilité : `available_at_utc = end_utc + L`, latence `L = 0`, comme S1 (§5 de S1,
  ADR-006). Décision à `D = available_at_utc` de la bougie qui la déclenche, avec les seules
  bougies disponibles à `D`.
- **Bougie exigée `OK`** (proposé) : toute M15 ou M5 lue par DAY_01 (range, cassure, retest,
  invalidation, confirmation) doit être à l'état `OK`. Contrairement à S1, une
  `FERMETURE_DOCUMENTÉE` ne compte pas comme utilisable : une bougie touchée par une fermeture ne
  déclenche ni ne construit rien. Une M15 ou une M5 **prévue mais absente**, ou présente mais non
  `OK`, rompt la règle qui en a besoin (§4, §8).
- **Qualité d'abord** : l'état de la bougie est vérifié **avant** d'interpréter sa clôture comme
  une cassure, une invalidation ou une confirmation. Une clôture d'une bougie non `OK` n'est
  jamais lue.
- **Convention de qualité DAY_01** (retenue par l'opérateur le 2026-11-05, ASSUMP-028, protocole
  `docs/experiments/DATA_M5_M15_2015_2021.md` §9). C'est une convention de recherche : elle ne
  change ni les données, ni les H1/H4/D1, ni les références S1-S3.
  - **M5 sans tick** : absente et non `OK`. Pas de comblement, pas de « marché calme ».
  - **M15 dont un sous-créneau M5 prévu est sans tick valide** : non `OK`. Ses OHLC observés sont
    conservés, avec le motif « sous-créneaux M5 sans tick valide : k/3 ».
  - **Silence** : interruption s'il dépasse **strictement 5 minutes** de temps d'ouverture prévue,
    pour les M5 comme pour les M15. Un silence d'exactement 5 min n'en est pas une.
  - **État à la clôture** : seule la durée de silence **déjà connue** à la clôture compte.
    L'audit rétrospectif reste séparé et ne sert jamais à une décision.
  - Le même seuil vaut pour les entrées en attente (§4.5) et les positions ouvertes (§5, ADR-021).
    Une **fermeture connue** (fermeture hebdomadaire prévue) reste distincte d'une interruption
    inexpliquée. Ces règles ne changent ni les statuts H1/H4/D1, ni l'ATR H4 (§4.1), qui gardent
    leurs règles et leur seuil de 10 min.

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

## 4. Range, cassure, retest et entrée (achat ; vente au §4.8)

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
- **Complétude** : les 28 M15 doivent être présentes et `OK`. Sinon, aucune séance ce
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
- **Données** : une M15 de la fenêtre absente ou non `OK` met fin à la recherche de cassure pour
  la séance, sans lire ni supposer de clôture.
- Aucune cassure confirmée à 11:00 : séance sans signal.

### 4.3 Retest, invalidation et confirmation (proposé)

Zone de retest de l'achat : `[Z_b, Z_h] = [RH − 0,1 × A, RH + 0,1 × A]`. Les M5 lues sont celles
qui commencent à `K` ou après. Chaque M5, à sa disponibilité, est examinée dans cet ordre :

1. **Qualité** : la M5 doit être présente et `OK`. Sinon, abandon de la tentative (« données
   inutilisables pendant le retest »), sans lire sa clôture.
2. **Invalidation** : `bid_close < Z_b`. La tentative échoue (fausse cassure) et la séance est
   consommée.
3. **Contact** (si aucun contact antérieur) : recoupement de la zone, `bid_low ≤ Z_h` **et**
   `bid_high ≥ Z_b`. La première M5 qui recoupe la zone est la **M5 de retest**.
4. **Confirmation** : à partir de la M5 de retest **incluse**, première M5 dont `bid_close > RH`.
   Une clôture dans la zone, en deçà de `RH` ou égale à `RH`, ne confirme pas et n'invalide pas :
   on attend la M5 suivante.
5. **Délai** : la M5 de confirmation doit se terminer au plus tard à `K + 60 min` (12 M5). Sinon,
   abandon (« délai de retest dépassé »), y compris quand le prix est parti sans revenir : pas de
   poursuite du prix.

**Recoupement OHLC et ticks.** Le contact est défini sur les extrêmes de la M5. Un recoupement
OHLC **ne prouve pas** qu'un tick a coté dans la zone : le prix peut la traverser entre deux
ticks consécutifs. La règle reste celle des bougies, identique en historique et en direct. Le lot
de données pourra enregistrer, à titre descriptif seulement, si un tick a coté dans la zone.

**Confirmation sur la bougie du contact** (proposée) : une même M5 peut recouper la zone et
clôturer au-delà de `RH`. Elle est alors à la fois la M5 de retest et la M5 de confirmation
(exemple B du §7). L'alternative, confirmation sur une M5 postérieure seulement, est un arbitrage
(§11).

### 4.4 Décision d'entrée (instant `D`)

`D` = disponibilité de la M5 de confirmation. La décision lit l'état **strictement antérieur à
`D`**. Entrée décidée si, dans cet ordre :
1. **aucune position DAY_01 ouverte**, y compris une position de la veille dont la liquidation
   est encore en attente (§4.7). Une seule tentative par séance ne suffit pas à le garantir ;
2. marché ouvert à `D` selon le calendrier ;
3. **cotation à `D`** : un dernier tick strictement antérieur à `D`, dans la M5 de confirmation
   (`ts ≥ D − 5 min`), avec bid et ask positifs et bid ≤ ask. Il donne `P_D` (ask à l'achat,
   bid à la vente) et le prix de sortie courant (bid à l'achat, ask à la vente). Sinon,
   abstention « absence de cotation à `D` » ;
4. **stop admissible** (§5) : à l'achat, `S` strictement en dessous du bid courant et `P_D − S > 0` ;
   à la vente, `S` strictement au-dessus de l'ask courant et `S − P_D > 0`. Sinon, abstention
   « stop non admissible ». La distance minimale d'un stop chez IG n'est pas confirmée
   (ASSUMP-008) : elle n'est pas modélisée ;
5. **cible du bon côté** : `T > P_D` à l'achat, `T < P_D` à la vente (vrai par construction,
   vérifié quand même) ;
6. taille admise par le budget de risque (§6.2).

### 4.5 Bornes de décision et d'exécution ; entrée en attente (proposé)

- **Borne de décision** : `K + 5 min ≤ D ≤ K + 60 min`. Comme `K ≤ 11:00`, aucune décision après
  **12:00:00** Londres.
- **Validité de l'entrée en attente** : **5 minutes** (une M5). L'ordre décidé à `D` est exécuté
  au **premier tick admissible** de l'intervalle `]D, D + 5 min]`. Admissible : tick valide (non
  exclu par le lot de données), marché ouvert, hors fermeture.
- **Échéance** : `min(D + 5 min, 16:00:00)`. Sans tick admissible avant l'échéance, l'entrée est
  **annulée** (`ENTRÉE_EXPIRÉE`) : entrée décidée mais non exécutée, comptée comme telle. Aucune
  exécution n'est supposée.
- **Borne d'exécution** : aucune exécution après **12:05:00** Londres. Une entrée en attente est
  de toute façon annulée à la liquidation de 16:00.
- **Confirmation exactement à 12:00** : la M5 [11:55, 12:00) est disponible à `D = 12:00:00.000`.
  Un tick horodaté exactement à 12:00:00.000 n'exécute pas l'ordre (exécution strictement
  postérieure), mais il compte comme cotation pour la mesure du silence. Exécution au premier tick
  admissible de ]12:00:00, 12:05:00] ; sinon annulation pour interruption dès que le silence dépasse
  5 minutes (exemple C du §7).
- **Trois durées distinctes** :
  - **fraîcheur à la décision** : le dernier tick avant `D` doit tomber dans la M5 de confirmation,
    donc dater de 5 minutes au plus (§4.4) ;
  - **validité de l'entrée** : 5 minutes après `D` ;
  - **seuil de silence** : **strictement plus de 5 minutes** d'ouverture prévue (retenu le
    2026-11-05, §3.2).
- **Référence M5** : la cotation utilisée à `D` date de `[D − 5 min, D[` et l'exécution tombe dans
  `]D, D + 5 min]`. Le silence entre ces deux ticks peut donc atteindre 10 minutes, soit **plus que
  le seuil de 5 minutes**. Une interruption peut ainsi survenir pendant la validité de l'entrée.
  Avec l'ancien seuil de 10 minutes, ce n'était pas possible.
- **Variante M15** : la fraîcheur est jugée sur la M15 de confirmation, soit une cotation dans
  `[D − 15 min, D[`. Mais une M15 `OK` à sa clôture exclut tout silence connu de plus de 5 minutes
  (§3.2) : la cotation à `D` date donc de **5 minutes au plus**, comme en référence M5. L'écart entre
  cette cotation et l'exécution est au plus de 10 minutes dans les deux cas (ADR-022). L'écart de 20
  minutes envisagé avec l'ancien seuil n'existe plus.
- **Entrée en attente et interruption** (retenu le 2026-11-05) :
  - **Annulation** : l'entrée en attente est annulée dès qu'une interruption devient connue avant
    son exécution, c'est-à-dire dès que le silence depuis la dernière cotation dépasse 5 minutes
    d'ouverture prévue sans tick.
  - **Tick révélateur** : la règle vaut aussi quand c'est le premier tick suivant qui révèle
    l'interruption. Ce tick **n'exécute pas** l'ordre.
  - **Issue** : `ENTRÉE_ANNULÉE_INTERRUPTION`, journalisée avec la durée du silence. La tentative
    de la séance est consommée.
  - **Transactions exécutées** : une transaction déjà exécutée n'est jamais supprimée. Une
    interruption pendant une position ouverte relève du §5 (scénarios A, B et C).
- **Conséquence pour l'échéance** (ADR-022) : la cotation à `D` date de 5 minutes au plus. Sans
  tick admissible dans `]D, D + 5 min]` :
  - si la dernière cotation est **antérieure** à `D`, le silence dépasse 5 minutes **avant**
    l'échéance. L'entrée est annulée pour interruption (`ENTRÉE_ANNULÉE_INTERRUPTION`), à
    l'instant où le silence dépasse 5 minutes ;
  - si un tick est horodaté **exactement à `D`**, il compte comme cotation sans exécuter l'ordre.
    Le silence vaut alors exactement 5 minutes à l'échéance, ce qui ne dépasse pas le seuil.
    L'issue est `ENTRÉE_EXPIRÉE`. C'est le seul cas où elle survient dans une séance ouverte.

### 4.6 Nombre de tentatives (proposé)

**Une seule tentative par séance**. La première cassure confirmée consomme le range, quelle que
soit l'issue : entrée, invalidation, délai dépassé, données inutilisables, refus, expiration de
l'entrée. Pas de seconde cassure dans l'autre sens. Une variante à deux tentatives relèverait
d'un protocole distinct.

### 4.7 Position encore ouverte d'une séance précédente

Une liquidation retardée (§5) peut laisser une position ouverte au début de la séance suivante.
- Tant qu'elle subsiste, **aucune nouvelle entrée** n'est autorisée.
- La séance du jour est quand même évaluée et journalisée : range, cassure, retest. Les comptes de
  disponibilité restent comparables.
- Si une confirmation arrive alors que la position ancienne est encore ouverte à `D`, l'entrée est
  refusée (« position DAY_01 déjà ouverte ») et la séance est consommée. Pas de rattrapage après
  la clôture de l'ancienne position.
- Si l'ancienne position est clôturée strictement avant `D`, la décision du jour est évaluée
  normalement.
- Priorité sur un même tick : la clôture en attente de l'ancienne position passe avant toute
  entrée (§6.1). Comme une entrée ne peut pas être décidée pendant qu'une position est ouverte,
  une entrée en attente et une liquidation en attente ne coexistent jamais.
- **Fin de l'étude** : si aucun tick n'arrive avant la fin de la fenêtre étudiée, la position
  reste ouverte, valorisée au dernier tick, présentée à part, **sans sortie future inventée**
  (convention de S3).

### 4.8 Vente (règle symétrique)

- Cassure : `bid_close < RL − 0,1 × A`.
- Zone : `[Z_b, Z_h] = [RL − 0,1 × A, RL + 0,1 × A]`.
- Contact : même recoupement, `bid_low ≤ Z_h` et `bid_high ≥ Z_b` (série bid, comme l'achat).
- Invalidation : `bid_close > Z_h`.
- Confirmation : `bid_close < RL`.
- Stop : au-dessus du plus haut `ask_high` du retest (§5).

## 5. Stop, cible et liquidation (proposé)

- **Stop** (achat) : plus bas `bid_low` des M5, de la M5 de retest à la M5 de confirmation
  incluses, moins `0,25 × A` (marge de S2 et S3). Pour une vente : plus haut `ask_high` de ces
  M5, plus `0,25 × A`. Il est fixé à `D` et n'est jamais déplacé. Stop **garanti simulé** avec sa
  prime, comme les références S1 à S3.
  - **Hypothèse explicite, conservée pour la référence de recherche** : aucune distance minimale de
    stop garanti chez IG n'est confirmée (ASSUMP-008). Elle n'est donc pas appliquée, et des stops
    courts sont simulés comme garantis.
  - Cette hypothèse **ne valide pas** l'exécutabilité de ces stops chez IG. Un minimum confirmé
    pourrait exclure ou modifier une partie des entrées ; il sera traité avant toute admission en
    paper trading.
- **Cible de référence : multiple du risque.** `P_D` est le prix d'entrée estimé à `D` (§4.4) :
  dernier ask strictement avant `D` à l'achat, dernier bid à la vente.
  - Cible `T = P_D + k × (P_D − S)` à l'achat, `T = P_D − k × (S − P_D)` à la vente, avec
    **`k = 1,5`**, appelé **rapport des distances de prix estimées à la décision**. Il est connu à
    `D`, avant l'exécution, et il est fixe.
  - Il ne faut pas le confondre avec deux autres rapports, **rapportés sans servir de filtre** :
    - **rapport net estimé à la décision** : gain net à la cible, coûts compris (glissement,
      conversion), divisé par la perte estimée au stop, coûts et prime de stop garanti compris.
      Il est inférieur à `k` ;
    - **rapport obtenu à l'exécution** : `(T − prix d'entrée exécuté) / (prix d'entrée exécuté − S)`
      à l'achat, qui diffère de `k` d'un tick à l'autre. Ni `T` ni `S` ne sont recalculés au prix
      exécuté.
  - Sortie à la **première cotation exécutable observée** qui atteint la cible : bid ≥ `T` à
    l'achat, ask ≤ `T` à la vente, au prix de cette cotation. Un écart favorable observé est
    conservé, comme S2 ; ce n'est pas le comportement confirmé d'un ordre limite IG (ASSUMP-008).
- **Premier prix d'exécution déjà au-delà d'une borne** (convention S2 §6.3, ADR-009) ; l'entrée
  n'est jamais annulée au vu de ce prix :
  - **au-delà du stop** (achat : bid ≤ `S`) : exécutée puis liquidée sur le même tick, comptée
    `STOP_DÉPASSÉ_À_L'EXÉCUTION` ; rejet à l'exécution en variante seulement si de tels cas
    existent ;
  - **au-delà de la cible** (achat : bid ≥ `T`) : exécutée à l'ask puis sortie au bid sur le même
    tick, comptée `CIBLE_ATTEINTE_À_L'EXÉCUTION`. « Cible atteinte » ne veut pas dire « gagnante » :
    l'achat à l'ask et la revente au bid peuvent perdre.
- **Variante séparée : cible sur niveau prédéfini.** Projection de la hauteur du range :
  `RH + H` à l'achat, `RL − H` à la vente. Exigée par le cahier comme **variante séparée** :
  protocole distinct, non lancée avec la référence (§11).
- **Liquidation de fin de séance : 16:00 Londres.**
  - Toute position encore ouverte reçoit à 16:00:00 un ordre de clôture au marché, exécuté au
    **premier tick strictement postérieur** (bid pour un achat, ask pour une vente).
  - Une entrée encore en attente à 16:00 est annulée (`ENTRÉE_EXPIRÉE`) ; par construction, elle
    aurait déjà expiré à 12:05.
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
     (`NUIT_NON_PRÉVUE`). La séance suivante applique le §4.7.
  5. Si aucun tick n'arrive avant la fin de l'étude : position ouverte valorisée, sans sortie
     inventée (§4.7).
- **Interruption pendant une position ouverte** (ADR-021), à tout moment entre l'exécution et la
  sortie, pas seulement à 16:00 :
  - Interruption : silence de **strictement plus de 5 minutes** d'ouverture prévue. Un silence
    d'exactement 5 minutes n'en est pas une.
  - Une interruption ne signifie pas que le stop ou la cible ont été touchés. La transaction est
    **conservée**, jamais supprimée ni annulée rétroactivement. Elle est marquée indéterminée, et le
    trou est journalisé (début, fin, cotations qui l'encadrent).
  - Traitement selon les scénarios de S2 (§7 de S2), chacun rejoué en entier :
    - **A**, observé seulement : seule la première cotation après le trou compte. Si elle est
      au-delà d'une borne, cette borne s'exécute ; sinon la position continue ;
    - **B**, stop d'abord : sortie au niveau du stop garanti, comptabilisée au premier tick qui
      clôt le trou ;
    - **C**, cible d'abord : sortie au niveau `T`, comptabilisée au premier tick qui clôt le trou,
      sans amélioration de prix invisible.
  - Une **fermeture connue** n'est pas une interruption inexpliquée. La première cotation après la
    fermeture s'applique comme une cotation observée : stop ou cible si elle les franchit.
  - **Entrée en attente et position exécutée sont distinctes** : la première est annulée (§4.5),
    la seconde n'est jamais annulée.
- **Pas de sortie temporelle intermédiaire** : seuls le stop, la cible ou la liquidation de 16:00
  ferment la position.

## 6. Exécution et risque

### 6.1 Chronologie

Mêmes règles que S1 (§5 de S1, ASSUMP-024, ADR-009) :
- décision à `D` sur l'état strictement antérieur à `D` ;
- exécution au premier tick `ts > D`, achat à l'ask et vente au bid ;
- un tick horodaté exactement à `D` est rejoué après la décision ;
- premier prix d'exécution au-delà du stop ou de la cible : §5 ;
- **priorité des événements sur un même tick** (ASSUMP-024) : 1) silence précédant le tick ;
  2) stop de la position ouverte ; 3) cible ; 4) liquidation en attente ; 5) entrée en attente.

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

## 7. Exemples horodatés (achat, données inventées)

**Exemple A — retest puis confirmation sur la M5 suivante.** Mardi 12 février 2019, en heure
d'hiver : Londres = UTC. ATR H4 figé `A = 0,00200` (20 pips), calculé sur la H4 [02:00, 06:00)
UTC, disponible à 06:00. Toutes les bougies citées sont `OK`, et leurs OHLC sont cohérents : plus bas ≤ ouverture et
clôture ≤ plus haut ; la clôture de chaque M5 est le bid du dernier tick qu'elle contient.

| Instant (Londres = UTC) | Événement | Connu à cet instant |
|---|---|---|
| 01:00 → 08:00 | 28 M15 du range | — |
| **08:00:00** | M15 [07:45, 08:00) disponible : **range figé** | `RH = 1,13250`, `RL = 1,13050`, `H = 20 pips = 1,0 × A`, dans [0,5 ; 2] × `A` |
| 08:15:00 | M15 [08:00, 08:15) clôture à 1,13262 | au-delà de `RH`, mais pas de `RH + 0,1 × A = 1,13270` : pas de cassure |
| **08:30:00** | M15 [08:15, 08:30) clôture à 1,13291 > 1,13270 | **cassure haussière**, `K = 08:30` ; zone [1,13230 ; 1,13270] ; délai jusqu'à 09:30 |
| 08:35:00 | M5 [08:30, 08:35) `OK` : ouverture 1,13291, plus haut 1,13296, plus bas 1,13275, clôture 1,13281 | plus bas > `Z_h = 1,13270` : pas de contact |
| 08:40:00 | M5 [08:35, 08:40) `OK` : ouverture 1,13281, plus haut 1,13284, plus bas 1,13239, clôture 1,13248 | clôture ≥ `Z_b = 1,13230` : pas d'invalidation ; 1,13239 ≤ `Z_h` et 1,13284 ≥ `Z_b` : **contact** ; clôture ≤ `RH` : pas de confirmation |
| **08:45:00** | M5 [08:40, 08:45) `OK` : ouverture 1,13248, plus haut 1,13266, plus bas 1,13241, clôture 1,13259 > `RH` | **confirmation sur la M5 suivant le contact**, `D = 08:45:00.000` ; extrême du retest : min(1,13239 ; 1,13241) = 1,13239 |
| 08:45:00.000 | décision | dernier tick avant `D` : 08:44:59.870, bid 1,13259, ask 1,13261 = `P_D` ; stop `S = 1,13239 − 0,00050 = 1,13189` < bid : admissible ; `P_D − S` = 7,2 pips ; cible `T = 1,13261 + 1,5 × 0,00072 = 1,13369` ; entrée en attente jusqu'à 08:50:00 |
| 08:45:00.000 | tick horodaté exactement à `D` | **pas utilisé pour l'entrée** (exécution à `ts > D`) |
| **08:45:00.140** | premier tick postérieur à `D`, ask 1,13262 | **entrée** à 1,13262 ; taille selon §6.2 |
| 10:12:31.405 | premier bid ≥ 1,13369 (bid 1,13370) | sortie à la cible, à 1,13370 |
| (sinon) 16:00:00 | liquidation | au premier tick postérieur à 16:00:00 |

Rapport des distances estimées à la décision : `k = 1,5` (10,8 pips / 7,2 pips). Rapport obtenu à
l'exécution : (1,13369 − 1,13262) / (1,13262 − 1,13189) = 10,7 / 7,3 ≈ 1,47. Le rapport net
estimé, coûts compris, est plus bas encore ; il est rapporté, sans filtrer l'entrée.

Le même jour en heure d'été (par exemple le mardi 9 juillet 2019, BST), toutes les heures de
Londres sont identiques. En UTC, le range va de 00:00 à 07:00, le gel a lieu à 07:00:00 UTC et la
liquidation à 15:00:00 UTC.

**Exemple B — contact et confirmation sur la même M5.** Même range et même cassure qu'en A
(`K = 08:30`, zone [1,13230 ; 1,13270]).

| Instant | Événement | Lecture, dans l'ordre du §4.3 |
|---|---|---|
| 08:35:00 | M5 [08:30, 08:35) `OK` : ouverture 1,13291, plus haut 1,13296, plus bas 1,13275, clôture 1,13281 | pas d'invalidation ; pas de contact |
| **08:40:00** | M5 [08:35, 08:40) `OK` : ouverture 1,13281, plus haut 1,13284, plus bas 1,13244, clôture 1,13258 | 1) `OK` ; 2) clôture ≥ `Z_b` : pas d'invalidation ; 3) 1,13244 ≤ `Z_h` et 1,13284 ≥ `Z_b` : **contact** ; 4) clôture > `RH = 1,13250` : **confirmation sur la même M5**, `D = 08:40:00.000` |
| 08:40:00.000 | décision | dernier tick avant `D` : 08:39:59.910, bid 1,13258, ask 1,13260 = `P_D` ; stop `S = 1,13244 − 0,00050 = 1,13194` (plus bas de cette seule M5) < bid : admissible ; `P_D − S` = 6,6 pips ; cible `T = 1,13260 + 1,5 × 0,00066 = 1,13359` ; entrée en attente jusqu'à 08:45:00 |

Si cette M5 avait été `INTERRUPTION_INEXPLIQUÉE` ou `FERMETURE_DOCUMENTÉE`, sa clôture n'aurait
pas été lue : abandon de la tentative à 08:40:00, sans contact ni confirmation.

**Exemple C — confirmation exactement à 12:00.** Cassure connue à `K = 11:00` (M15 [10:45, 11:00)).
La M5 [11:55, 12:00) confirme : `D = 12:00:00.000`, dernière décision possible (`K + 60 min`).

Dernier tick de la M5 de confirmation : 11:59:58.300.

| Cas | Ticks après 11:59:58.300 | Effet |
|---|---|---|
| 1 | un tick exactement à 12:00:00.000, puis un tick à 12:03:10 | le tick de 12:00:00.000 n'exécute pas (`ts > D` exigé) mais compte pour le silence ; **entrée** à 12:03:10 |
| 2 | aucun tick avant 12:04:58.300 | le silence dépasse 5 min juste après 12:04:58.300 : **`ENTRÉE_ANNULÉE_INTERRUPTION`** ; un tick arrivé ensuite (12:05:00 compris) n'exécute pas ; séance consommée (§4.5) |
| 3 | un tick exactement à 12:00:00.000, puis aucun jusqu'à 12:05:00 inclus | silence d'exactement 5 min à l'échéance, sans dépasser le seuil : **`ENTRÉE_EXPIRÉE`** à 12:05:00 ; séance consommée |

## 8. Abstentions et non-exécutions (première cause journalisée)

Dans l'ordre d'évaluation, une seule cause par séance :
1. pas de séance : jour férié probable, ou fermeture ;
2. range incomplet : M15 absente ou non `OK` dans la fenêtre ;
3. ATR H4 non calculable ;
4. range hors largeur admissible (`H / A` journalisé) ;
5. données inutilisables pendant la recherche de cassure (M15 absente ou non `OK`) ;
6. aucune cassure confirmée à 11:00 ;
7. données inutilisables pendant le retest (M5 absente ou non `OK`, clôture non lue) ;
8. invalidation (fausse cassure) ;
9. délai de retest dépassé ;
10. position DAY_01 déjà ouverte à `D` (§4.7) ;
11. marché fermé à `D` ;
12. absence de cotation à `D` ;
13. stop non admissible ;
14. taille minimale supérieure au budget.

Une **entrée décidée** a ensuite une seule issue :
- exécutée, position ouverte ;
- exécutée puis liquidée (`STOP_DÉPASSÉ_À_L'EXÉCUTION`) ;
- exécutée puis sortie à la cible sur le même tick (`CIBLE_ATTEINTE_À_L'EXÉCUTION`) ;
- **non exécutée** : `ENTRÉE_EXPIRÉE` (aucun tick admissible avant l'échéance du §4.5 ; seulement
  après une cotation horodatée exactement à `D`, voir la conséquence du §4.5) ;
- **non exécutée** : `ENTRÉE_ANNULÉE_INTERRUPTION` (interruption connue avant l'exécution, y compris
  révélée par le premier tick suivant, §4.5) ; tentative consommée.

Comme pour S3, les motifs sont comptés **au premier blocage** : un blocage à une étape ne dit
rien des étapes suivantes. Chaque entrée décidée doit être attestée par une transaction ou par
un événement de non-exécution (contrôle de S3, ADR-020).

## 9. Protocole de test (à figer avant chaque étape)

1. **Lot de données M15/M5** (§10) : construction et audit de couverture 2015-2021, **avant** tout
   moteur DAY_01.
2. **Moteur et tests synthétiques** : exemples A, B et C du §7 reproduits, vente, changement
   d'heure, chacune des abstentions et non-exécutions du §8, bougie non `OK` dont la clôture
   n'est pas lue, liquidation sans cotation, `NUIT_NON_PRÉVUE`, position de la veille, position
   ouverte à la fin de l'étude.
3. **Non-régression** : rejeu S1 si un moteur partagé est modifié.
4. **Disponibilité** 2015-2021 : séances attendues, ranges complets, ranges admissibles, cassures,
   retests, sans exécution.
5. **Performance** 2015-2021 : référence H4 → M15 → M5 en scénario A, comparaison « H4 → M15,
   retest et confirmation sur M15 », puis B, C ou rejet selon des conditions de déclenchement
   fixées à l'avance, comme pour S2 et S3.

Rapportés, en plus des mesures du cahier (§9) et de celles de S3 :
- parcours des séances aux entrées ;
- résultats par jour de la semaine, par heure d'entrée, en heure d'hiver ou d'été et pendant les
  semaines de décalage ;
- liquidations à 16:00, liquidations retardées, entrées expirées ;
- rapports des distances estimés, nets estimés et obtenus à l'exécution, côte à côte ;
- chevauchement et pertes simultanées avec S1, S2 et S3 ;
- part des séances avec annonces non mesurable (limite du §3.4).

## 10. Préalable : lot de données M15/M5

> **Réalisé le 2026-11-05** (PR #18) : M5 et M15 2015-2021 construites directement depuis les
> ticks, puis auditées (`docs/experiments/DATA_M5_M15_2015_2021.md` et `_BILAN.md`). Intégrité
> validée par l'opérateur ; convention de qualité DAY_01 au §3.2. Le texte ci-dessous est le
> cahier des charges du lot, conservé tel qu'écrit avant sa réalisation.

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
- **Ticks : conventions existantes du lecteur, reprises sans changement** (`history/bars.py`,
  `history/quality.py`, `docs/DATA.md` §4 et §6). **Aucune suppression silencieuse** : chaque cas
  est compté et rapporté.
  - **Prix nul ou négatif, bid > ask** : seuls ticks **invalides**. Ils sont exclus des bougies,
    comptés, et la bougie est marquée (`tick(s) invalides exclus`), donc non `OK`.
  - **Ticks distincts au même horodatage** : **légitimes** (plusieurs cotations par
    milliseconde). Ils sont conservés, dans l'ordre de leur ligne dans le fichier (`raw_row`).
  - **Doublons exacts** : lignes consécutives identiques (horodatage, prix, volumes). Elles sont
    conservées et comptées, car indiscernables d'une cotation répétée. Les doublons entre
    fichiers sont évités à l'import (empreinte, périodes chevauchantes).
  - **Erreurs d'ordre chronologique** dans un fichier : comptées et rapportées. Les bougies
    ordonnent les ticks par horodatage, puis par `raw_row`. Le lot rapportera combien tombent dans
    les fenêtres DAY_01.
  - **Ticks pendant la fermeture prévue** : conservés ; la bougie est marquée incomplète.
- **Contrôles de conservation**, par bougie et par jour :
  - ouverture = premier tick valide dans l'ordre (horodatage, `raw_row`), clôture = dernier,
    plus haut et plus bas = extrêmes des ticks valides, séparément pour le bid et l'ask ;
  - nombre de ticks valides et nombre de ticks exclus de chaque M5, sommés, égaux à ceux de la M15
    et de la H1 correspondantes, puis au total des ticks lus ;
  - trois M5 forment la M15 (ouverture de la première, clôture de la dernière, extrêmes), et quatre
    M15 la H1 existante, à l'identique.
- **Bougie absente ou inutilisable** : calendrier des créneaux M15 et M5 prévus, selon la
  fermeture hebdomadaire et les jours fériés probables.
  - **Absente** : créneau prévu sans aucun tick.
  - **Inutilisable** : bougie présente mais touchée par un silence au-delà du seuil
    (`INTERRUPTION_INEXPLIQUÉE`), par une fermeture ou par un jour férié probable.
  - À 5 minutes, un créneau calme sans tick n'est pas forcément une panne. Le lot devra mesurer
    la fréquence de ces créneaux dans les fenêtres DAY_01 (01:00-16:00 Londres) et proposer une
    règle avant le moteur.
- **Seuil de silence** : le seuil actuel de 10 minutes a été fixé pour des bougies H1 à D1. Le lot
  devra examiner explicitement s'il convient à des M5 : un silence de 9 minutes recouvre presque
  deux M5 sans être classé comme interruption. Le lot mesurera la distribution des silences dans
  les fenêtres DAY_01 et proposera un seuil, ou une règle propre aux M5, **à partir des seules
  données de cotation**, avant le moteur et sans référence à un résultat de trading.
- **État connu à la clôture** : l'état d'une bougie à son `available_at_utc` ne doit utiliser
  que l'information connue à cet instant, distinct de l'audit a posteriori (ADR-006). Un silence
  commencé dans la bougie et qui se prolonge après sa clôture n'est connu, à la clôture, que
  pour sa partie déjà écoulée.
- **Contrôles anti-fuite temporelle**, sur le modèle des tests de PR #3 sur de vraies clôtures
  H1, H4 et D1 :
  - aucune bougie lue avant son `available_at_utc` ;
  - état à la clôture identique, que les ticks postérieurs soient chargés ou non ;
  - range figé à 08:00 identique, que les données postérieures soient présentes ou tronquées ;
  - fenêtres en heure de Londres calculées par la date de séance seulement, jamais à partir des
    prix.
- **Couverture** : par année, et dans les fenêtres DAY_01 :
  - créneaux prévus, absents et inutilisables ;
  - séances avec un range complet ;
  - séances avec les M5 complètes de 08:00 à 12:00.
- **Bornes** : 2015-2021 seulement, lecteur refusant 2022-2025 ; sorties hors Git (`data/`).

## 11. Arbitrages (tous tranchés au gel du 2026-11-05, ADR-022)

Les lignes marquées « retenu » ont été choisies explicitement par l'opérateur. Les autres sont
retenues telles que proposées.

| # | Point | Proposition de référence | Alternatives |
|---|---|---|---|
| 1 | Fenêtre du range | [01:00, 08:00) Londres, 28 M15 | [00:00, 08:00) ; [00:00, 07:00) |
| 2 | Rôle de H4 / H1 | H4 pour l'ATR seulement, pas de filtre de direction ; H1 non utilisée | filtre de direction H4 ou H1, en variante distincte |
| 3 | Largeur admissible | `0,5 × A ≤ H ≤ 2 × A`, `A` = ATR Wilder 14 H4 | ATR D1 ; bornes en pips |
| 4 | Confirmation de cassure | clôture M15 au-delà de la borne de plus de `0,1 × A`, de 08:15 à 11:00 | sans marge ; fenêtre plus courte |
| 5 | Retest (**retenu par l'opérateur le 2026-11-05** : confirmation possible sur la M5 du contact) | M5 qui recoupe la zone `± 0,1 × A` (`bid_low ≤ Z_h` et `bid_high ≥ Z_b`), puis clôture M5 au-delà de la borne, **éventuellement sur la même M5** ; invalidation par une clôture au-delà de la zone, côté range | confirmation sur une M5 postérieure au contact seulement |
| 6 | Délai de retest | 60 min (12 M5) après `K` | 30 ou 90 min |
| 7 | Tentatives | une par séance | deux (protocole distinct) |
| 8 | Stop (**hypothèse conservée le 2026-11-05** : garanti simulé sans minimum IG confirmé, exécutabilité non validée) | extrême du retest ± `0,25 × A`, garanti simulé | stop normal, si la distance minimale du stop garanti chez IG exclut les stops courts (ASSUMP-008, non confirmé) |
| 9 | Cible (**retenu le 2026-11-05** : `k = 1,5`, sans filtre sur le rapport net) | rapport des distances de prix estimées à la décision `k = 1,5`, depuis `P_D` ; rapports net estimé et obtenu à l'exécution rapportés, **sans filtre** | filtre sur le rapport net estimé (comme `R_min` de S2) ; `k = 1` ou `2` ; variante séparée : `RH + H` / `RL − H` |
| 10 | Liquidation | 16:00 Londres, au premier tick postérieur ; convention du §5 si aucune cotation | 15:00 ou 16:30 |
| 11 | Annonces | aucun filtre (limite inscrite au §3.4) | filtre en protocole distinct, après calendrier historique |
| 12 | Variante simple | « H4 → M15, retest et confirmation sur M15 » | — |
| 13 | Instrument | EUR/USD seulement | GBP/USD (cahier §2), après données et décision |
| 14 | Ordre des lots | lot M15/M5 (construction et audit) avant le moteur | — |
| 15 | Validité de l'entrée en attente (**retenu le 2026-11-05** : 5 min) | 5 min après `D`, au premier tick admissible ; sinon `ENTRÉE_EXPIRÉE` ; aucune exécution après 12:05 | 1 min ; 15 min |
| 16 | Bougies admises | `OK` seulement, pour toute M15 et M5 lue ; qualité vérifiée avant la clôture | `OK` ou `FERMETURE_DOCUMENTÉE`, comme S1 |
| 17 | Cotation à `D` | dernier tick avant `D` dans la M5 de confirmation, bid ≤ ask | fraîcheur plus courte (par exemple 60 s) |
| 18 | Stop admissible | du bon côté du prix de sortie courant, distance strictement positive ; distance minimale IG non modélisée | distance minimale une fois confirmée chez IG (ASSUMP-008) |
| 19 | Position de la veille | aucune entrée tant qu'elle subsiste ; séance consommée sans rattrapage | autoriser une décision après sa clôture, dans le délai de retest |
| 20 | Seuil de silence M5 et M15 (**retenu le 2026-11-05** : strictement plus de 5 min) | interruption au-delà de 5 min d'ouverture prévue ; à la clôture, seule la durée déjà connue compte (§3.2) ; même seuil pour les positions ouvertes, transaction conservée, scénarios A/B/C (§5, ADR-021) | 10 min (référence de comparaison conservée) |
| 21 | M5 sans tick ; M15 à sous-créneau vide (**retenu le 2026-11-05**) | M5 absente, non `OK` ; M15 non `OK`, OHLC observés conservés, motif précis | M15 jugée sur ses seuls ticks |
| 22 | Entrée en attente et interruption (**retenu le 2026-11-05**) | annulation dès qu'une interruption est connue avant l'exécution, y compris révélée par le premier tick suivant ; `ENTRÉE_ANNULÉE_INTERRUPTION`, tentative consommée ; aucune transaction exécutée supprimée | exécuter et journaliser |
