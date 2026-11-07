# Fiche DAY_02 — Continuation après impulsion et drapeau (day trading)

> Identifiant code : `DAY_02` (candidate « D2 » du cahier des charges). Statut : **proposition**
> (ASSUMP-029 `PROPOSED`), rédigée le 2026-11-07 sur autorisation de l'opérateur, documentation
> seulement. Portée **recherche hors ligne**. Aucun moteur, aucune analyse historique, aucun
> backtest. Toutes les valeurs nouvelles de cette fiche sont **proposées**, choisies a priori sans
> lecture de données ni de résultats, et restent `PROPOSED` jusqu'à validation (§12). Instrument :
> **EUR/USD seulement**. Aucune donnée 2022-2025. Ni validation de performance ni autorisation de
> trading.

**Libellés.** Comme dans les fiches précédentes, **H1, M15 et M5 désignent des unités de temps**.
Les heures sont données **en heure locale de Londres** (`Europe/London`), sauf mention « UTC » ou
« New York ». Les formules sont écrites pour l'**achat** ; la vente est symétrique (§5.8).

**Ce qui est imposé, réutilisé et proposé.** Chaque section sépare :
- **Exigé (cahier v1.2)** : contraintes du cahier des charges, paraphrasées avec leur section ;
- **Valeurs existantes du projet** : capital, risque, tailles et coûts de recherche communs à S1,
  S2, S3 et DAY_01, repris **sans modification** ;
- **Proposé (ASSUMP-029)** : règles et valeurs nouvelles de cette fiche, y compris la reprise
  éventuelle d'une convention de DAY_01, qui n'est **jamais automatique** (§4).

## 1. Hypothèse de marché et références

- **Hypothèse** : un mouvement directionnel rapide et ample relativement à la volatilité récente
  (l'**impulsion**) traduit un déséquilibre d'ordres. S'il est suivi d'une pause courte et peu
  profonde (le **drapeau**), les prises de bénéfice n'ont pas inversé ce déséquilibre. La sortie de
  la pause dans le sens de l'impulsion signale sa reprise.
- **Appui** : description technique des configurations de continuation, drapeaux et fanions, par
  CME Group [R2] (cahier §6.3, §17). C'est un appui **technique**, pas une preuve statistique de
  rentabilité de notre système. La recette précise, les unités et les seuils sont des hypothèses
  propres au projet.
- **Faiblesses attendues** (cahier §6.3) :
  - impulsion épuisée : la pause précède un retournement ;
  - consolidation trop profonde ou trop longue : le déséquilibre a disparu ;
  - obstacle proche (extrême antérieur) qui arrête la reprise ;
  - impulsions provoquées par des annonces, dont l'effet n'est pas isolable (§3.4).
- **Risques partagés** : le cahier note que S2, D2 et C1 peuvent partager des risques (§6.6) : une
  reprise après repli, sur des unités différentes. Le chevauchement et les pertes simultanées avec
  S2, et avec S1, S3 et DAY_01, seront décrits (§10), sans simulation de portefeuille partagé.

## 2. Exigences du cahier v1.2 pour cette candidate

| Exigence | Section du cahier |
|---|---|
| Impulsion **mesurée relativement à la volatilité**, suivie d'une consolidation **courte et peu profonde** | §6.3 |
| Entrée après **sortie confirmée** dans le sens initial ; stop **derrière la borne opposée** | §6.3 |
| Sortie avant un obstacle supérieur, à une cible définie **ou** selon une règle suiveuse **testée séparément** | §6.3 |
| À fixer : amplitude minimale de l'impulsion, durée, profondeur, pente, construction de la figure, délai de sortie | §6.3 |
| **Aucune reconnaissance subjective après coup** | §6.3 |
| Heure de liquidation de fin de session explicite ; aucune position la nuit dans la version initiale | §6.3 |
| Unités indicatives : H1/H4 → M15 → M5 ; contexte → configuration → déclenchement ; **variante plus simple en comparaison** ; tester l'apport de l'unité d'entrée plus fine | §6.1, §6.5 |
| Bougies clôturées et pivots disponibles à l'heure de décision seulement ; fuseau, ancrage et changements d'heure fixés, identiques en historique et en direct | §5, §6.5 |
| Ne pas présenter plusieurs unités imbriquées comme des confirmations indépendantes | §6.5 |
| Contenu de la fiche : références, régime, paramètres, chronologie, invalidation, stop, cible, sortie temporelle, conservation nocturne, **calendrier d'annonces**, coûts, critères de rejet, protocole | §6.6 |
| Day trading : horaires, heure d'été, liquidation de session et annonces à intégrer à l'évaluation | §9 |
| Exécution au premier prix ultérieur admissible ; achat à l'ask, vente au bid ; résolution plus fine si stop et cible tombent dans la même bougie | §9 |
| Risque de 0,25 % des fonds propres ; signal refusé si la taille minimale dépasse le budget | §8 |
| Partitions : 2015-2021 développement ; 2022-2023 et 2024-2025 réservées | §9 |
| Mesurer corrélation, pertes simultanées et apport marginal (S2/D2/C1) | §6.6, §9 |

## 3. Données, unités et conventions

### 3.1 Rôle de chaque unité (proposé)

| Unité | Rôle dans la référence | Justification par la logique de la stratégie |
|---|---|---|
| **H1** | **contexte de volatilité seulement** : ATR Wilder 14 H1 `A`, échelle de mesure de l'impulsion, de la profondeur et des marges (§5.1). Aucun filtre de direction | L'impulsion dure de 15 min à 1 h (§5.1) : la volatilité de référence doit couvrir quelques heures, pas plusieurs jours. Une H1 sur 14 couvre environ une demi-journée ; une H4 sur 14 couvrirait plus de deux jours de cotation, une échelle plus lente que la figure. La direction est donnée par l'impulsion elle-même : un filtre de tendance H1 ajouterait une condition non exigée par la recette ; il relève d'une variante distincte (§12) |
| **M15** | **configuration** : impulsion, puis formation du drapeau | Une impulsion intrajournalière de 1 à 4 M15 et une pause de 2 à 6 M15 sont lisibles en M15 sans réduire la figure à une ou deux bougies |
| **M5** | **déclenchement** : sortie du drapeau, surveillance de la profondeur après la formation, extrême du drapeau pour le stop | Lire la sortie du drapeau sur l'unité plus fine permet d'entrer plus près de la borne ; c'est l'apport que le cahier demande de mesurer (§6.5) |
| H4 | non utilisée dans la référence | — |

Les bornes des M15 et des M5 tombent aux mêmes instants en UTC, à Londres et à New York (décalages
entiers). Les H1 sont celles du projet (ancrage UTC des heures pleines).

**Comparaison plus simple, enregistrée à l'avance** (cahier §6.5) : **« H1 → M15 »**. Même
impulsion, même formation du drapeau, mêmes stop, cible et sorties ; mais la sortie du drapeau, la
surveillance de la profondeur après la formation et l'extrême du drapeau sont lus sur **M15**
(clôture M15 au lieu de clôture M5). Elle supprime l'unité de déclenchement et mesure ce qu'apporte
M5 : retard, entrées manquées, distance du stop, coûts et espérance nette. Elle ne remplace pas la
référence.

Les trois unités ne sont **pas** des confirmations indépendantes (cahier §6.5) : M5 et M15
décrivent le même mouvement à deux résolutions, et `A` n'est qu'une échelle.

### 3.2 Série, disponibilité et états de bougie

- **Série de calcul** : **bid** pour l'impulsion, le drapeau et la sortie. Le stop d'une vente
  utilise l'`ask_high`, comme S2, S3 et DAY_01 (§6).
- **Disponibilité** : `available_at_utc = end_utc`, latence nulle, comme S1 à DAY_01. Une décision
  à l'instant `t` ne lit que les bougies disponibles à `t`.
- **Bougies M15 et M5 lues** (proposé) : exigées à l'état `OK`, qualité vérifiée **avant**
  d'interpréter leur clôture. Une bougie prévue absente, ou présente non `OK`, rompt la règle qui
  en a besoin (§5, §9).
- **Convention de qualité M5/M15** : voir le §4.1. La convention retenue pour DAY_01 (ADR-021)
  n'est **pas** reprise d'office : son extension à DAY_02 est une proposition explicite, soumise à
  validation.
- **H1 pour l'ATR** : statuts H1 existants du projet (ASSUMP-017, seuil de qualité de 10 min),
  **inchangés** ; ATR sur la continuité des H1 prévues, comme S2 et S3 pour leurs H4. Cette fiche
  ne modifie ni les H1, ni leurs statuts.

### 3.3 Heure de Londres et changements d'heure

- Les fenêtres sont fixées en heure de Londres ; leur traduction en UTC change avec l'heure d'été
  britannique (GMT = UTC, BST = UTC+1).
- De 2015 à 2021, tous les changements d'heure britanniques et américains tombent un dimanche,
  pendant la fermeture hebdomadaire (dates : fiche DAY_01 §3.3). Aucune fenêtre DAY_02 ne
  chevauche donc un changement d'heure.
- Pendant les **semaines de décalage**, New York est à 4 h de Londres au lieu de 5 h : 17:00
  Londres vaut 13:00 New York au lieu de 12:00. La fenêtre DAY_02 ne bouge pas en heure de
  Londres et reste avant la clôture de New York. Les résultats seront ventilés pour ces semaines.

### 3.4 Annonces économiques (limite explicite)

- **Aucun calendrier historique d'annonces** avec heures de publication n'est disponible dans le
  projet. Le cahier refuse de reproduire une décision ancienne à partir de données sans historique
  de publication (§5).
- **Référence proposée : sans filtre d'annonces**, sous réserve de validation (§12).
- Conséquence propre à DAY_02, plus forte que pour DAY_01 : une **impulsion** est souvent la
  réaction à une publication (par exemple zone euro vers 09:00-10:00 Londres, États-Unis à 13:30
  ou 15:00 Londres). Une partie des configurations détectées peut donc être causée par des
  annonces, sans que cette part soit mesurable. Les résultats ne diront pas si la continuation
  tient mieux ou moins bien après une annonce.
- Un filtre d'annonces relèverait d'un **protocole distinct**, après acquisition d'un calendrier
  historique horodaté et contrôlé. Il ne serait pas réglé sur les résultats de la référence.

## 4. Conventions : techniques réutilisables ou choix de stratégie

Les conventions de DAY_01 ne sont **pas transposées automatiquement**. Le tableau distingue :
- les **conventions techniques** (données, exécution, comptabilité) qui ne dépendent pas de la
  recette : leur reprise est proposée parce qu'elles décrivent comment observer et exécuter, pas
  ce qu'il faut trader ;
- les **choix de stratégie**, propres à DAY_02, justifiés par sa logique au §5 et au §6.

Toutes les lignes sont `PROPOSED` pour DAY_02, y compris celles qui reprennent une convention déjà
approuvée pour une autre stratégie.

| Domaine | Nature | Proposition pour DAY_02 | Origine |
|---|---|---|---|
| Construction des M5/M15 depuis les ticks, contenu `VALID` / `INVALID_ONLY` / `EMPTY`, sans comblement | technique | reprise | lot de données ASSUMP-028 (données déjà construites) |
| **Seuil de silence M5/M15** : interruption au-delà de **strictement 5 min** d'ouverture prévue ; M5 sans tick non `OK` ; M15 à sous-créneau M5 vide non `OK` ; état à la clôture avec la seule durée déjà connue | technique, mais **portée limitée à DAY_01 par ADR-021** | **extension explicite à DAY_02 proposée** (§4.1) | ADR-021 |
| Bougies `OK` seulement, qualité vérifiée avant la clôture | technique | reprise | DAY_01 §3.2 |
| Décision sur l'état strictement antérieur à `D` ; exécution au premier tick `ts > D` ; achat à l'ask, vente au bid ; priorité des événements sur un même tick | technique | reprise | ASSUMP-024, ADR-009 |
| Stop déjà dépassé au premier tick d'exécution : exécutée puis liquidée, compté ; rejet en variante si le cas existe | technique | reprise | ADR-009 |
| Interruption pendant une position ouverte : transaction conservée, indéterminée, scénarios A/B/C rejoués en entier | technique | reprise, avec le seuil du §4.1 | ADR-021, S2 §7 |
| Liquidation sans cotation : aucun prix supposé, premier tick postérieur, délai, silence clos et motif journalisés séparément ; `NUIT_NON_PRÉVUE` comptée | technique | reprise, avec l'heure de DAY_02 | ADR-023 |
| Position encore ouverte à la fin de l'étude : valorisée au dernier tick, présentée à part, sans sortie inventée | technique | reprise | S3, DAY_01 |
| Entrée en attente annulée sur interruption connue avant l'exécution (`ENTRÉE_ANNULÉE_INTERRUPTION`) | technique | reprise, avec le seuil du §4.1 | ADR-021 |
| Fenêtre horaire de la séance | **stratégie** | 07:00-15:00 pour les décisions (§5.2) | propre à DAY_02 |
| Heure de liquidation | **stratégie** | **17:00 Londres** (§6.3) | propre à DAY_02 |
| Nombre de tentatives | **stratégie** | configurations successives, une à la fois, sans plafond journalier (§5.7) | propre à DAY_02 |
| Validité de l'entrée en attente | **stratégie** (dépend de l'unité de déclenchement) | 5 min (§5.6) | propre à DAY_02, même valeur que DAY_01 par la même logique d'unité |
| Sortie temporelle | **stratégie** | 2 h après l'exécution (§6.3) | propre à DAY_02 |

### 4.1 Extension proposée de la convention de qualité ADR-021

**Proposition explicite, à valider** : appliquer à DAY_02 la convention de qualité M5/M15 et le
seuil de silence retenus pour DAY_01 (ADR-021, ASSUMP-028), **sans les modifier** :
- M5 sans tick : absente et non `OK`, sans comblement ni « marché calme » ;
- M15 dont un sous-créneau M5 prévu est sans tick valide : non `OK`, OHLC observés conservés avec
  le motif ;
- interruption si le silence dépasse **strictement 5 minutes** d'ouverture prévue, pour les M5, les
  M15, les entrées en attente et les positions ouvertes ; un silence d'exactement 5 min n'en est
  pas une ;
- à la clôture, seule la durée de silence déjà connue compte ; l'audit rétrospectif reste séparé ;
- une fermeture connue reste distincte d'une interruption inexpliquée.

**Raison** : DAY_02 lit les mêmes unités (M5, M15) sur les mêmes données. Le seuil a été fixé à
partir des seules données de cotation, avant tout moteur et sans référence à un résultat de
trading (protocole `DATA_M5_M15_2015_2021.md` §9). Une convention différente pour les mêmes bougies
rendrait les deux stratégies incomparables sans raison tirée de la recette.

**Différence de contexte à noter** : la convention a été auditée sur les fenêtres de DAY_01
(01:00-16:00 Londres). DAY_02 lit les bougies jusqu'à 17:00 et les positions jusqu'à 17:00 au
plus (§6.3). L'étude de disponibilité de DAY_02 devra rapporter la fréquence des M5/M15 non `OK`
et des silences dans sa propre fenêtre (07:00-17:00), à titre descriptif, sans changer le seuil.

**Alternative** : seuil de référence de 10 min (comparaison conservée par ADR-021). Si l'extension
n'est pas validée, DAY_02 attend une décision sur sa convention avant toute implémentation.

## 5. Impulsion, drapeau, sortie et entrée (achat ; vente au §5.8)

Une **séance** est un jour ouvré du lundi au vendredi, en heure de Londres. Pas de séance le
25 décembre ni le 1er janvier (jour férié probable, ASSUMP-023), comme DAY_01. Toutes les
quantités ci-dessous sont calculées sur des bougies disponibles à l'instant de la décision.

### 5.1 Impulsion (proposé)

À la disponibilité `t_j` de chaque M15 `j` de la fenêtre de reconnaissance (§5.2), sans
configuration ni position en cours (§5.7), l'outil examine la **fenêtre d'impulsion** `W_j` : les
**4 M15** qui se terminent à `t_j` (bougies `j − 3` à `j`, soit 1 h).

1. **Qualité et fenêtre** : les 4 M15 doivent être prévues, présentes et `OK`, et commencer à
   **07:00 Londres ou après**. Sinon, pas de reconnaissance à `t_j` (sans abandon : l'examen
   reprend à la M15 suivante).
2. **Échelle `A`** : ATR Wilder 14 H1 (true range bid, continuité des H1 prévues), calculé sur la
   **dernière H1 terminée au plus tard au début de `W_j`**. `A` n'inclut donc aucune bougie de la
   fenêtre d'impulsion, ce qui évite de mesurer l'impulsion avec une volatilité qu'elle a
   elle-même gonflée. Non calculable : pas de reconnaissance à `t_j`, cause journalisée.
3. **Origine** : `O` = plus bas `bid_low` de `W_j` ; bougie d'origine `o` = la première qui
   l'atteint.
4. **Sommet** : `E` = plus haut `bid_high` des bougies `o` à `j` ; bougie du sommet `p` = la
   dernière qui l'atteint. Il faut `o ≤ p` (le plus bas précède le plus haut, ou les deux sont dans
   la même M15).
5. **Amplitude** : `I = E − O`.
6. **Impulsion haussière reconnue** si, à la fois :
   - **amplitude relative** : `bid_close_j − O ≥ 1,5 × A` ;
   - **clôture forte** : `bid_close_j ≥ E − 0,25 × I` (la dernière clôture reste dans le quart
     supérieur de l'impulsion : le mouvement n'est pas déjà en recul).

   Si les conditions de hausse et de baisse (§5.8) sont réunies à la même M15, aucune impulsion
   n'est reconnue (cas ambigu, journalisé) : la règle ne choisit pas un sens après coup.
7. L'impulsion reconnue ouvre une **configuration**. `O`, `A` et la bougie `o` sont figés. `E`,
   `p` et `I` ne peuvent changer que par extension (§5.3).

Durée de l'impulsion : de 1 à 4 M15 (de `o` à `j`), jusqu'à 6 M15 après extension (§5.3).

### 5.2 Fenêtre horaire de la séance (proposé)

| Étape | Bornes (Londres) | Raison |
|---|---|---|
| M15 lues pour l'impulsion | commencent à **07:00** ou après | la liquidité européenne arrive à partir de l'ouverture de Francfort et de Londres ; les heures asiatiques, plus calmes, ne sont pas visées par la recette |
| Reconnaissance d'une impulsion | `t_j` de **08:00** à **14:15** | 08:00 est la première disponibilité d'une fenêtre de 4 M15 commençant à 07:00 ; à 14:15, un drapeau minimal de 2 M15 est formé au plus tôt à 14:45, ce qui laisse au moins une M5 (ou une M15 en comparaison) avant la borne de décision |
| Décision d'entrée `D` | au plus tard **15:00** | une position décidée garde au moins 2 h avant la liquidation de 17:00, la durée de la sortie temporelle (§6.3) |
| Exécution | au plus tard **15:05** (validité de 5 min, §5.6) | — |
| Liquidation | **17:00** (§6.3) | — |

La fenêtre couvre Londres et le chevauchement Londres / New York (environ 13:00-17:00 Londres), où
la liquidité est la plus forte. Elle s'arrête avant la clôture de New York (17:00 New York =
21:00 ou 22:00 Londres) : aucune nuit, donc aucun financement, sauf `NUIT_NON_PRÉVUE` (§6.3).

### 5.3 Formation du drapeau sur M15 (proposé)

Après la reconnaissance à `t_j`, les M15 qui commencent à `t_j` ou après sont lues une à une, à
leur disponibilité, dans cet ordre :

1. **Qualité** : M15 présente et `OK` ; sinon, abandon (« données inutilisables pendant le
   drapeau »), sans lire sa clôture.
2. **Extension** : si `bid_high > E`, l'impulsion se prolonge : `E` := ce plus haut, `p` := cette
   M15, `I := E − O`, et le décompte du drapeau repart de zéro. Si l'impulsion compte alors plus de
   **6 M15** (de `o` à `p`), la configuration est abandonnée (« impulsion prolongée sans pause ») :
   c'est une tendance soutenue, pas une impulsion suivie d'une pause.
3. **Profondeur** : si `bid_low < E − 0,5 × I`, la configuration est invalidée (« repli trop
   profond ») : la pause a repris plus de la moitié de l'impulsion.
4. Sinon, la M15 compte comme **M15 du drapeau**.

Le **drapeau est formé** à la disponibilité de la **2e M15 du drapeau** consécutive (pause d'au
moins 30 min). Cet instant est noté `F`. Il faut `F ≤ 14:45` ; sinon, abandon (« fin de fenêtre »).

Après `F`, une M15 au-delà de `E` n'est plus une extension : la sortie du drapeau se lit sur M5
(§5.4).

**Figure retenue** (« construction de la figure », cahier §6.3) : la borne supérieure du drapeau
est **`E`**, le sommet de l'impulsion ; la borne inférieure est le plus bas atteint pendant la
pause. La figure est donc une **boîte** sous le sommet, définie par des prix observés, sans tracé
de droite ni ajustement.

**Pente** (« à fixer », cahier §6.3) : **non contrainte** dans la référence. Un drapeau descendant,
horizontal ou montant sous `E` est admis tant qu'il respecte la profondeur et la durée. La pente
(clôture de la dernière M15 du drapeau moins clôture de la première, rapportée à `A`) est
journalisée à titre descriptif. Une contrainte de pente relèverait d'une variante distincte (§12).

### 5.4 Sortie du drapeau sur M5 (proposé)

À partir de `F`, les M5 qui commencent à `F` ou après sont lues une à une, à leur disponibilité,
dans cet ordre :

1. **Qualité** : M5 présente et `OK` ; sinon, abandon (« données inutilisables pendant le
   drapeau »), sans lire sa clôture.
2. **Profondeur** : `bid_low < E − 0,5 × I` : invalidation (« repli trop profond »).
3. **Sortie confirmée** : `bid_close > E + 0,1 × A`. Une clôture au-delà de `E` mais en deçà de la
   marge n'est pas une sortie (bruit autour du sommet).
4. **Délai** : la M5 de sortie doit se terminer au plus tard à `fin(p) + 90 min` (durée maximale de
   la pause : **6 M15** après le sommet) et au plus tard à **15:00**. Sinon, abandon
   (« consolidation trop longue » ou « fin de fenêtre »), y compris si le prix est sorti sans
   confirmation.

`D` = disponibilité de la M5 de sortie.

**Bas du drapeau** : `FL` = plus bas `bid_low` des M15 du drapeau et des M5 lues de `F` à la M5
de sortie incluse (pour une vente : `FH_ask` = plus haut `ask_high` de ces bougies).

**Comparaison « H1 → M15 »** : mêmes règles, avec des M15 lues à partir de `F` ; `D` = disponibilité
de la M15 de sortie ; `FL` sur les seules M15.

### 5.5 Décision d'entrée (instant `D`)

La décision lit l'état **strictement antérieur à `D`**. Entrée décidée si, dans cet ordre :
1. aucune position DAY_02 ouverte ni entrée DAY_02 en attente (§5.7) ;
2. marché ouvert à `D` selon le calendrier ;
3. **cotation à `D`** : dernier tick strictement antérieur à `D`, dans la bougie de sortie
   (`ts ≥ D − 5 min` en référence, `ts ≥ D − 15 min` en comparaison M15), bid et ask positifs,
   bid ≤ ask. Il donne `P_D` (ask à l'achat) et le prix de sortie courant (bid à l'achat). Sinon,
   abstention « absence de cotation à `D` » ;
4. **stop admissible** (§6.1) : `S` strictement sous le bid courant et `P_D − S > 0` ; sinon,
   abstention « stop non admissible ». Aucune distance minimale IG n'est modélisée (§8) ;
5. **cible du bon côté** : `T > P_D` (§6.2) ; sinon, abstention « cible déjà dépassée à `D` ».
   Contrairement à un multiple du risque, la cible mesurée n'est pas du bon côté par construction :
   le prix peut avoir déjà parcouru l'amplitude projetée à `D` ;
6. taille admise par le budget de risque (§7).

Une abstention à `D` met fin à la configuration (§5.7).

### 5.6 Exécution et entrée en attente (proposé)

- L'ordre décidé à `D` est exécuté au **premier tick admissible** de `]D, D + 5 min]` (tick
  valide, marché ouvert, hors fermeture). Sans tick admissible : `ENTRÉE_EXPIRÉE`, entrée décidée
  non exécutée ; aucune exécution supposée.
- **Validité de 5 min** : une M5, l'unité de déclenchement. Au-delà, la sortie du drapeau qui a
  motivé l'entrée n'est plus l'information la plus récente. La même durée est proposée pour la
  comparaison M15, pour que seules les unités de lecture diffèrent.
- **Interruption avant l'exécution** (convention du §4.1, si elle est validée) : annulation dès
  qu'un silence de strictement plus de 5 min est connu, y compris révélé par le premier tick
  suivant, qui n'exécute pas (`ENTRÉE_ANNULÉE_INTERRUPTION`).
- Aucune exécution après **15:05** Londres.

### 5.7 Tentatives et configurations successives (proposé)

- **Une configuration à la fois** : tant qu'une configuration est en cours (de la reconnaissance
  de l'impulsion à son abandon, son invalidation ou la décision à `D`), aucune autre impulsion
  n'est recherchée, dans aucun sens.
- **Une position à la fois** : aucune impulsion n'est recherchée tant qu'une entrée est en attente
  ou qu'une position DAY_02 est ouverte.
- **Reprise de la recherche** : après la fin d'une configuration sans entrée, ou après la sortie
  d'une position, la fenêtre d'impulsion suivante ne peut contenir **aucune M15 commençant avant
  cette fin** : une bougie ne sert jamais à deux configurations.
- **Pas de plafond journalier** dans la référence : la recette ne porte pas sur un événement
  unique de la séance (contrairement au range de DAY_01), et plusieurs impulsions peuvent se
  produire dans une journée. Le nombre de configurations, d'entrées et de pertes par séance sera
  rapporté. Alternatives au §12 : une ou deux tentatives par séance.
- Le seuil de perte journalière du cahier (§8, 1 %) n'est pas un mécanisme des moteurs de recherche
  actuels ; il n'est pas simulé ici. Le nombre de séances dont les pertes DAY_02 cumulées
  dépasseraient 1 % des fonds propres sera rapporté, à titre descriptif.

### 5.8 Vente (règle symétrique)

- Origine `O` = plus haut `bid_high` de `W_j` ; sommet `E` = plus bas `bid_low` de `o` à `j` ;
  `I = O − E`.
- Reconnaissance : `O − bid_close_j ≥ 1,5 × A` et `bid_close_j ≤ E + 0,25 × I`.
- Extension : `bid_low < E`. Profondeur : `bid_high > E + 0,5 × I` (série bid, comme l'achat).
- Sortie : `bid_close < E − 0,1 × A`.
- Stop au-dessus du plus haut `ask_high` du drapeau (§6.1) ; cible `T = E − I`.

## 6. Stop, cible et sorties (proposé)

### 6.1 Stop

- **Achat** : `S = FL − 0,25 × A`, derrière la borne opposée du drapeau (cahier §6.3), avec la
  marge relative de S2, S3 et DAY_01 exprimée ici en `A` H1. **Vente** : `S = FH_ask + 0,25 × A`.
- Fixé à `D`, jamais déplacé. Stop **garanti simulé** avec sa prime, comme les références
  précédentes ; aucune distance minimale IG n'est appliquée (hypothèse explicite, §8).
- **Distances du stop non présumées** : `P_D − S` dépend de la profondeur du drapeau, de la
  position de la sortie par rapport à `E` et de `A` H1. Par construction, elle reste inférieure à
  `0,5 × I + (P_D − E) + 0,25 × A`, mais aucune valeur typique n'est supposée ici, ni tirée de
  DAY_01, dont les stops reposent sur une autre construction (extrême d'un retest M5 et `A` H4). Sa
  distribution sera mesurée par l'étude de disponibilité, avant tout passage de performance.

### 6.2 Cible de référence : projection de l'impulsion

- **Cible** : `T = E + I` à l'achat, `T = E − I` à la vente : l'amplitude de l'impulsion est
  projetée depuis la borne du drapeau.
- **Justification par la logique de la stratégie** : la recette suppose que la reprise prolonge le
  déséquilibre qui a produit l'impulsion ; la mesure naturelle de ce qui reste à parcourir est
  donc l'amplitude de l'impulsion elle-même. C'est la règle de projection usuelle des figures de
  continuation, et elle utilise une grandeur déjà définie par la figure. Ce choix n'est pas
  motivé par les résultats de DAY_01 (dont la cible était un multiple du risque) : il découle de
  ce que la configuration mesure.
- Sortie à la **première cotation exécutable observée** qui atteint la cible : bid ≥ `T` à
  l'achat, ask ≤ `T` à la vente, au prix de cette cotation (convention S2 et DAY_01 ; pas le
  comportement confirmé d'un ordre limite IG, §8).
- **Rapports rapportés sans servir de filtre** : rapport des distances estimées à la décision
  `(T − P_D) / (P_D − S)`, qui **varie** d'une configuration à l'autre ; rapport net estimé à `D`,
  coûts compris ; rapport obtenu à l'exécution. Aucun rapport minimal n'est exigé dans la
  référence (alternative au §12).
- **Premier prix d'exécution déjà au-delà d'une borne** (ADR-009) : au-delà du stop, exécutée puis
  liquidée (`STOP_DÉPASSÉ_À_L'EXÉCUTION`) ; au-delà de la cible, exécutée puis sortie sur le même
  tick (`CIBLE_ATTEINTE_À_L'EXÉCUTION`, qui n'est pas forcément un gain).
- **Variantes séparées**, non lancées avec la référence (cahier §6.3 : sortie avant un obstacle,
  cible définie ou règle suiveuse, testées séparément) : multiple du risque ; sortie avant un
  obstacle supérieur ; sortie suiveuse (§12).

### 6.3 Sortie temporelle et liquidation de fin de séance

- **Sortie temporelle** (« délai de sortie », cahier §6.3) : si ni le stop ni la cible n'ont fermé
  la position **2 h après l'exécution**, ordre de clôture au marché, exécuté au premier tick
  strictement postérieur à cette échéance (`SORTIE_TEMPORELLE`).
  - **Raison** : une continuation doit reprendre rapidement ; une position qui stagne deux heures
    après la sortie d'un drapeau formé en 30 à 90 min ne correspond plus à l'hypothèse. 2 h est
    du même ordre que la durée totale de la figure (impulsion et pause, jusqu'à 3 h).
  - Elle ne sert pas de stop : elle ferme au prix observé, gain ou perte.
- **Liquidation de fin de séance : 17:00 Londres** : toute position encore ouverte reçoit à
  17:00:00 un ordre de clôture au marché, exécuté au premier tick strictement postérieur
  (`LIQUIDATION_17H`). Avec `D ≤ 15:00`, la sortie temporelle (au plus vers 17:05) et la
  liquidation se recoupent seulement pour les entrées les plus tardives : la première échéance
  atteinte s'applique.
  - **Raison** : 17:00 Londres clôt le chevauchement Londres / New York ; la liquidité baisse
    ensuite. L'heure reste au moins 4 h avant la clôture de New York.
  - Différence avec DAY_01 (16:00) : DAY_01 n'entrait plus après 12:05 ; DAY_02 peut entrer
    jusqu'à 15:05 et doit laisser à la position le temps de sa sortie temporelle.
- **Aucune cotation à l'échéance** (temporelle ou 17:00) : conventions techniques du §4, sans prix
  invisible : la position reste ouverte avec son stop et sa cible jusqu'au premier tick
  postérieur ; délai après l'échéance, silence clos et motif de clôture journalisés séparément ;
  si ce tick franchit déjà le stop ou la cible, priorité du moteur (stop, cible, puis clôture en
  attente) ; si le silence est une interruption pendant laquelle une borne a pu être franchie, la
  transaction est indéterminée et les scénarios A, B et C s'appliquent ; sans tick avant la fin de
  la journée de cotation, clôture à la réouverture, comptée `NUIT_NON_PRÉVUE`, et aucune nouvelle
  configuration tant que la position subsiste ; sans tick avant la fin de l'étude, position
  valorisée à part, sans sortie inventée.
- **Interruption pendant une position ouverte** : même traitement qu'au §4 (transaction conservée,
  indéterminée, scénarios A/B/C rejoués en entier ; une fermeture connue n'est pas une
  interruption).

### 6.4 Chronologie et résolution fine

- Décision à `D` sur l'état strictement antérieur à `D` ; exécution au premier tick `ts > D` ; un
  tick horodaté exactement à `D` est rejoué après la décision.
- Priorité sur un même tick (ASSUMP-024) : silence précédant le tick ; stop ; cible ; clôture en
  attente (sortie temporelle ou liquidation) ; entrée en attente.
- Les ticks résolvent l'ordre du stop et de la cible ; un trou de cotation qui empêche de trancher
  rend la transaction indéterminée (scénarios A, B, C).

## 7. Taille et coûts (valeurs existantes du projet, inchangées)

- Taille : 0,25 % des fonds propres estimés à `D`, perte au stop coûts compris, minimum 0,1
  contrat, incrément 0,1, capital initial 2 000 € (ADR-003, ASSUMP-020 et références S1 à DAY_01).
- Coûts de recherche communs (`RESEARCH_COSTS`, statut `ASSUMED`) : glissement 0,5 pip, commission
  0, conversion 0,5 %, prime de stop garanti, financement 1 USD par contrat et par nuit (seulement
  en cas de `NUIT_NON_PRÉVUE`). Aucun de ces montants n'est modifié par cette fiche.
- **Rappel (bilan DAY_01, ADR-024)** : DAY_01 M5 était **déficitaire avant coûts** (brut
  −211,88 €) ; les coûts (374,83 €) ont aggravé ce résultat, ils ne l'expliquent pas à eux seuls.
  Rien dans cette fiche ne suppose qu'une construction différente des stops changerait ce constat
  pour DAY_02 : la part des coûts fixes dans le risque sera mesurée, pas présumée.

## 8. Conditions IG : informations manquantes et hypothèses concernées

Point ouvert **distinct**, qui ne bloque pas cette rédaction. Aucun contact avec IG, aucun ordre.
La décision de confirmer ces points avant les passages de performance, ou de mener l'étude sous
hypothèses explicites, sera prise séparément par l'opérateur.

| Information manquante | Référence | Hypothèse de recherche actuelle | Ce qu'elle peut affecter dans DAY_02 |
|---|---|---|---|
| Distance minimale d'un stop garanti, et sa référence de mesure | ASSUMP-008 | non modélisée : tout stop du bon côté est admis et garanti | admissibilité des entrées à stop court ; taille ; part des entrées exclues ou à stop élargi |
| Montant et mode de calcul de la prime de stop garanti | ASSUMP-006, `docs/CONFIRMATIONS.md` | 1,2 USD par contrat, observé en démo, non confirmé | coût fixe par contrat ; part des coûts fixes dans le risque ; net |
| Côté de déclenchement des stops (bid à l'achat, ask à la vente) | ASSUMP-008 | convention usuelle des CFD | instant et prix de sortie au stop |
| Disponibilité d'un stop normal à la place du stop garanti pour le profil visé | `docs/CONFIRMATIONS.md` §5 | stop garanti obligatoire supposé | glissement au stop ; prime |
| Taille minimale et incrément du contrat EUR/USD Mini | ASSUMP-005 | 0,1 contrat, pas de 0,1 | refus de taille ; arrondi du risque |
| Glissement à l'exécution au marché | ASSUMP-006 | 0,5 pip, scénario expérimental | coût de chaque entrée et sortie au marché (entrées, sorties temporelles, liquidations) |
| Commission | ASSUMP-006 | 0 | coût fixe |
| Frais de conversion du résultat | ASSUMP-006 | 0,5 % | net en euros |
| Financement d'une nuit | ASSUMP-006 | 1 USD par contrat et par nuit | seulement les `NUIT_NON_PRÉVUE` |
| Exécution d'un ordre limite à la cible (amélioration de prix) | ASSUMP-008 | sortie au prix de la première cotation qui atteint la cible | prix de sortie à la cible |
| Écart entre cotations Dukascopy et prix IG | calibrage prévu (`.ai/TASKS.md`) | cotations Dukascopy comme approximation | tous les prix, spreads et déclenchements |
| Horaires et fermetures particulières d'IG | ASSUMP-016 | calendrier hebdomadaire du projet | séances, liquidations, `NUIT_NON_PRÉVUE` |

La demande préparée `docs/IG_SUPPORT_REQUEST.md` n'est pas envoyée ; son envoi relève de
l'opérateur.

## 9. Abstentions, fins de configuration et non-exécutions

**À chaque M15 examinée pour une impulsion** (pas de reconnaissance, l'examen continue) : M15 de
`W_j` absente, non `OK` ou avant 07:00 ; `A` non calculable ; amplitude insuffisante ; clôture non
forte ; `o > p` ; cas ambigu (hausse et baisse à la fois). Ces cas sont comptés par cause.

**Fin d'une configuration**, une seule cause, dans l'ordre où elle survient :
1. données inutilisables pendant le drapeau (M15 ou M5 absente ou non `OK`) ;
2. impulsion prolongée sans pause (plus de 6 M15) ;
3. repli trop profond ;
4. consolidation trop longue (pas de sortie à `fin(p) + 90 min`) ;
5. fin de fenêtre (drapeau formé après 14:45 ou sortie après 15:00) ;
6. à `D` : marché fermé ; absence de cotation ; stop non admissible ; cible déjà dépassée ; taille
   minimale supérieure au budget ;
7. entrée décidée.

**Entrée décidée**, une seule issue : exécutée ; exécutée puis liquidée
(`STOP_DÉPASSÉ_À_L'EXÉCUTION`) ; exécutée puis sortie à la cible sur le même tick
(`CIBLE_ATTEINTE_À_L'EXÉCUTION`) ; `ENTRÉE_EXPIRÉE` ; `ENTRÉE_ANNULÉE_INTERRUPTION`.

**Entrée exécutée**, une seule issue : sortie liée au stop ; cible ; `SORTIE_TEMPORELLE` ;
`LIQUIDATION_17H` ; encore ouverte à la fin de l'étude. Les annotations (indéterminée,
`NUIT_NON_PRÉVUE`, clôture après interruption) recoupent ces issues et ne sont jamais additionnées.

Chaque entrée décidée doit être attestée par une transaction ou un événement de non-exécution
(contrôle de S3 et DAY_01).

## 10. Protocole de test (à figer avant chaque étape, sur autorisation)

Aucune de ces étapes n'est autorisée par cette fiche.

1. **Validation de la fiche** : arbitrages du §12 tranchés, ASSUMP-029 approuvée ou corrigée.
2. **Choix de réutilisation du code** : examiné avant l'implémentation (moteur DAY_01, moteur S1 ou
   moteur propre). La fiche décrit le comportement attendu ; elle ne fige pas d'héritage
   technique.
3. **Moteur et tests synthétiques** : exemples du §11 reproduits ; vente ; extension ; repli trop
   profond (M15 et M5) ; consolidation trop longue ; fin de fenêtre ; cas ambigu ; `A` excluant la
   fenêtre d'impulsion ; bougie non `OK` dont la clôture n'est pas lue ; cible déjà dépassée à
   `D` ; sortie temporelle ; liquidation de 17:00 avec et sans cotation ; `NUIT_NON_PRÉVUE` ;
   position ouverte à la fin de l'étude ; configurations successives sans bougie partagée.
4. **Non-régression** : rejeu S1 si un moteur partagé est modifié.
5. **Disponibilité** 2015-2021, sans tick ni exécution : impulsions reconnues, drapeaux formés,
   fins de configuration par cause, sorties, distribution des distances de stop et des rapports
   estimés à `D` (descriptif), fréquence des bougies non `OK` dans 07:00-17:00.
6. **Performance** 2015-2021 : référence H1 → M15 → M5 en scénario A, comparaison H1 → M15, puis B,
   C ou rejet selon des conditions de déclenchement fixées à l'avance, comme pour S2, S3 et DAY_01.
   Avant ce passage, décision de l'opérateur sur les conditions IG (§8).

Rapportés, en plus des mesures du cahier (§9) :
- parcours des impulsions aux entrées, avec les dénominateurs à chaque étape ;
- configurations, entrées et pertes par séance ; séances dont les pertes cumulées dépasseraient
  1 % ;
- résultats par jour, par heure de décision, en heure d'hiver ou d'été et pendant les semaines de
  décalage, par sens ;
- distances du stop (pips et multiples de `A`), part des coûts fixes dans le risque, rapports
  estimés, nets estimés et obtenus, côte à côte, sans filtre ;
- pente du drapeau et nombre de M15 du drapeau (descriptif) ;
- sorties temporelles et liquidations de 17:00 (délai, silence clos, motif) ;
- **chevauchement et pertes simultanées**, décrits séparément avec **S1, S2, S3 et DAY_01** (M5,
  référence), puis en union sans doublon des transactions DAY_02 concernées : heures en même sens
  et en sens opposé, transactions DAY_02 perdantes qui chevauchent une perte de chaque référence.
  Ces mesures décrivent des trajectoires indépendantes, chacune avec son capital : **elles ne
  constituent pas une simulation de portefeuille partagé** ;
- part des configurations touchées par une annonce : **non mesurable** (§3.4).

## 11. Exemple horodaté (achat, données inventées)

Mardi 12 février 2019, heure d'hiver (Londres = UTC). `A` = ATR H1 = 0,00100 (10 pips), calculé sur
la H1 [07:00, 08:00), dernière H1 terminée au plus tard au début de `W_j` (08:30). Toutes les
bougies citées sont `OK`.

| Instant | Événement | Lecture |
|---|---|---|
| 09:15:00 | `W_j` = M15 de 08:15 à 09:15 (plus bas 1,12980) | `bid_close` 1,13055 − 1,12980 = 7,5 pips < 15 pips : pas d'impulsion |
| **09:30:00** | `W_j` = M15 de 08:30 à 09:30 : [08:30) O 1,13010 H 1,13030 L 1,12995 C 1,13005 ; [08:45) O 1,13005 H 1,13020 L 1,12980 C 1,13000 ; [09:00) O 1,13000 H 1,13060 L 1,12990 C 1,13055 ; [09:15) O 1,13055 H 1,13140 L 1,13050 C 1,13130 | `O` = 1,12980 (M15 de 08:45) ; `E` = 1,13140 (M15 de 09:15, `o < p`) ; `I` = 16 pips ; 1,13130 − 1,12980 = 15 pips ≥ 1,5 × `A` ; 1,13130 ≥ 1,13140 − 4 pips : **impulsion haussière reconnue** ; seuil de profondeur `E − 0,5 × I` = 1,13060 |
| 09:45:00 | M15 [09:30, 09:45) O 1,13130 H 1,13135 L 1,13090 C 1,13100 | pas d'extension (1,13135 ≤ `E`) ; 1,13090 ≥ 1,13060 : **1re M15 du drapeau** |
| **10:00:00** | M15 [09:45, 10:00) O 1,13100 H 1,13120 L 1,13075 C 1,13110 | **2e M15 du drapeau : drapeau formé**, `F` = 10:00 ; délai de sortie jusqu'à `fin(p)` + 90 min = 11:00 |
| 10:05:00 | M5 [10:00, 10:05) O 1,13110 H 1,13128 L 1,13100 C 1,13125 | 1,13125 ≤ `E + 0,1 × A` = 1,13150 : pas de sortie |
| **10:10:00** | M5 [10:05, 10:10) O 1,13125 H 1,13160 L 1,13120 C 1,13155 | 1,13155 > 1,13150 : **sortie confirmée**, `D` = 10:10:00.000 ; `FL` = min(1,13090 ; 1,13075 ; 1,13100 ; 1,13120) = 1,13075 |
| 10:10:00.000 | décision | dernier tick avant `D` : 10:09:59.820, bid 1,13155, ask 1,13157 = `P_D` ; `S` = 1,13075 − 2,5 pips = 1,13050 < bid : admissible ; `T` = `E + I` = 1,13300 > `P_D` ; `P_D − S` = 10,7 pips, `T − P_D` = 14,3 pips, rapport des distances estimées ≈ 1,34 ; entrée en attente jusqu'à 10:15:00 |
| 10:10:00.230 | premier tick postérieur à `D`, ask 1,13158 | **entrée** à 1,13158 |
| (cas 1) 11:02:14.510 | premier bid ≥ 1,13300 | sortie à la cible |
| (cas 2) 12:10:00.230 | aucune borne atteinte | **sortie temporelle** au premier tick postérieur à 12:10:00.230 |

Si la M15 [09:45, 10:00) avait eu un plus haut de 1,13145, elle aurait prolongé l'impulsion
(`E` = 1,13145, `I` = 16,5 pips) et le décompte du drapeau serait reparti de zéro. Si son plus bas
avait été 1,13055 (< 1,13060), la configuration aurait été invalidée (repli trop profond).

## 12. Arbitrages (tous `PROPOSED`, à trancher avant la validation)

| # | Point | Proposition de référence | Alternatives |
|---|---|---|---|
| 1 | Unités | H1 (ATR seulement) → M15 (impulsion, drapeau) → M5 (sortie) | H4 pour l'ATR ; filtre de direction H1 en variante distincte |
| 2 | Comparaison plus simple | « H1 → M15 » : sortie, profondeur après formation et extrême lus sur M15 | M15 seule, ATR M15 |
| 3 | Échelle `A` | ATR Wilder 14 H1, dernière H1 terminée avant le début de `W_j` | ATR M15 sur 14 M15 ; ATR H1 incluant la fenêtre |
| 4 | Fenêtre d'impulsion | 4 M15 glissantes (1 h) | 2 ou 6 M15 |
| 5 | Amplitude minimale | `bid_close_j − O ≥ 1,5 × A` | 1 × `A` ; 2 × `A` |
| 6 | Clôture forte | `bid_close_j ≥ E − 0,25 × I` | sans condition ; tiers supérieur |
| 7 | Extension | permise jusqu'à 6 M15 d'impulsion, décompte du drapeau remis à zéro | sans extension (abandon au premier dépassement avant formation) |
| 8 | Profondeur | au plus 50 % de `I`, sur les plus bas (M15 puis M5) | 38,2 % ; mesurée sur les clôtures |
| 9 | Durée du drapeau | au moins 2 M15, sortie au plus tard 6 M15 après le sommet | 1 à 4 M15 ; 3 à 8 M15 |
| 10 | Figure et pente | boîte sous `E`, pente non contrainte, journalisée | drapeau à pente opposée exigé ; fanion (bornes convergentes) en variante |
| 11 | Sortie du drapeau | clôture M5 au-delà de `E + 0,1 × A` | sans marge ; marge `0,2 × A` |
| 12 | Stop | `FL − 0,25 × A`, garanti simulé, sans minimum IG | marge `0,1 × A` ; stop normal si le minimum IG exclut les stops courts (§8) |
| 13 | Cible | projection `E + I`, sans rapport minimal | multiple du risque (`k = 1,5`) ; sortie avant obstacle ; sortie suiveuse ; rapport net minimal (protocoles distincts) |
| 14 | Sortie temporelle | 2 h après l'exécution | 1 h ; aucune (liquidation seule) |
| 15 | Fenêtre de séance | impulsion depuis 07:00, reconnaissance 08:00-14:15, drapeau formé au plus tard à 14:45, `D` ≤ 15:00 | 08:00-12:00 (Londres seule) ; jusqu'à 16:00 |
| 16 | Liquidation | 17:00 Londres, premier tick postérieur | 16:00 ; 18:00 |
| 17 | Tentatives | configurations successives, une à la fois, sans bougie partagée, sans plafond journalier | une par séance ; deux par séance |
| 18 | Validité de l'entrée | 5 min, référence et comparaison | 1 min ; 15 min en comparaison M15 |
| 19 | Convention de qualité M5/M15 | **extension explicite d'ADR-021** à DAY_02 (§4.1) | seuil de 10 min ; convention propre à valider |
| 20 | Conventions techniques d'exécution et de comptabilité | reprises (§4) | — |
| 21 | Annonces | aucun filtre ; limite explicite (§3.4) | filtre en protocole distinct, après calendrier historique |
| 22 | Conditions IG | étude sous les hypothèses actuelles ; décision séparée avant les passages de performance (§8) | confirmation préalable |
| 23 | Instrument | EUR/USD seulement | GBP/USD (cahier §2), après données et décision |
| 24 | Réutilisation du code | non figée ; examinée avant l'implémentation (§10) | — |
