# Fiche DAY_02 — Continuation après impulsion et drapeau (day trading)

> Identifiant code : `DAY_02` (candidate « D2 » du cahier des charges). Statut : **proposition**
> (ASSUMP-029 `PROPOSED`), rédigée le 2026-11-07 sur autorisation de l'opérateur (ADR-025),
> documentation seulement ; base de rédaction retenue et corrections demandées le 2026-11-07
> (ADR-026, §12). Portée **recherche hors ligne**. Aucun moteur, aucune analyse historique, aucun
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

**Principe retenu par l'opérateur le 2026-11-07** (ADR-026) : extension à DAY_02, avec contrôle de
couverture sur sa fenêtre propre, sans changer les H1 ni leur convention.

**Différence de contexte à noter** : la convention a été auditée sur les fenêtres de DAY_01
(01:00-16:00 Londres). DAY_02 lit des bougies M15 et M5 de 07:00 à 15:00 ; ses positions sont
suivies au tick jusqu'à leur clôture, normalement peu après 17:00 au plus tard, mais plus tard
faute de cotation (§6.3). L'étude de disponibilité de DAY_02 rapportera la fréquence des M5/M15 non
`OK` et des silences dans cette fenêtre propre, à titre descriptif, sans changer le seuil (§10.1).

**Alternative** : seuil de référence de 10 min (comparaison conservée par ADR-021). Si l'extension
n'est pas validée, DAY_02 attend une décision sur sa convention avant toute implémentation.

## 5. Impulsion, drapeau, sortie et entrée (achat ; vente au §5.8)

Une **séance** est un jour ouvré du lundi au vendredi, en heure de Londres. Pas de séance le
25 décembre ni le 1er janvier (jour férié probable, ASSUMP-023), comme DAY_01. Toutes les
quantités ci-dessous sont calculées sur des bougies disponibles à l'instant de la décision.

**Ordre à l'intérieur d'une bougie.** Une bougie ne donne que ses ouverture, plus haut, plus bas
et clôture : **l'ordre de son plus haut et de son plus bas n'est pas connu**. Aucune règle de
cette section ne le suppose. Les règles qui portent sur deux extrêmes exigent qu'ils soient
atteints dans **des bougies différentes**, ordonnées dans le temps ; quand une même bougie touche
deux seuils, une priorité fixe tranche (§5.3, §5.4), sans prétendre savoir lequel a été atteint
d'abord.

### 5.1 Impulsion (proposé)

À la disponibilité `t_j` de chaque M15 `j` de la fenêtre de reconnaissance (§5.2), sans
configuration, entrée en attente ni position en cours (§5.7), l'outil examine la **fenêtre
d'impulsion** `W_j` : les **4 M15** qui se terminent à `t_j` (bougies `j − 3` à `j`, soit 1 h).

1. **Qualité et fenêtre** : les 4 M15 doivent être prévues, présentes et `OK`, et commencer à
   **07:00 Londres ou après**. Sinon, pas de reconnaissance à `t_j` (sans abandon : l'examen
   reprend à la M15 suivante).
2. **Échelle `A`** : ATR Wilder 14 H1 (true range bid, continuité des H1 prévues), calculé sur la
   **dernière H1 terminée au plus tard au début de `W_j`**. `A` n'inclut donc aucune bougie de la
   fenêtre d'impulsion, ce qui évite de mesurer l'impulsion avec une volatilité qu'elle a
   elle-même gonflée. Non calculable : pas de reconnaissance à `t_j`, cause journalisée.
3. **Origine** : `O` = plus bas `bid_low` des 4 M15 de `W_j` ; bougie d'origine `o` = la
   **première** qui l'atteint.
4. **Sommet** : `E` = plus haut `bid_high` des 4 M15 de `W_j` (toute la fenêtre, pas seulement
   après `o`) ; bougie du sommet `p` = la **dernière** qui l'atteint.
5. **Ordre des extrêmes** : il faut **`o < p` strictement** (le plus bas est atteint dans une
   bougie antérieure à celle du plus haut) **et `p = j`** (l'impulsion est reconnue à la clôture de
   sa bougie de sommet). Si `o ≥ p`, l'ordre des extrêmes n'est pas établi ou le sommet précède
   l'origine : pas d'impulsion haussière. Si `p < j`, des bougies postérieures au sommet sont déjà
   closes : la reconnaissance n'a pas lieu à `t_j` (elle aurait dû avoir lieu à la clôture du
   sommet, avec la fenêtre de ce moment).
6. **Amplitude** : `I = E − O`.
7. **Impulsion haussière reconnue** si, en plus : 
   - **amplitude relative** : `bid_close_j − O ≥ 1,5 × A` ;
   - **clôture forte** : `bid_close_j ≥ E − 0,25 × I` (la clôture de la bougie du sommet reste dans
     le quart supérieur de l'amplitude).

   Si les conditions de hausse et de baisse (§5.8) sont réunies à la même M15, aucune impulsion
   n'est reconnue (cas ambigu, journalisé) : la règle ne choisit pas un sens après coup. Avec
   `p = j` dans les deux sens, ce cas exige que la même M15 porte le plus haut et le plus bas de la
   fenêtre ; il est donc exclu par `o < p` et ne subsiste que comme garde-fou.
8. L'impulsion reconnue ouvre une **configuration**. `O`, `o` et `A` sont figés. `E`, `p` et `I`
   ne changent que par extension (§5.3).

**Durée de l'impulsion** (bougies `o` à `p`) : de **2 à 4 M15** à la reconnaissance (`o < p = j`
dans une fenêtre de 4 M15) ; jusqu'à 6 M15 après extension (§5.3).

### 5.2 Fenêtre horaire de la séance (proposé)

| Étape | Bornes (Londres) | Raison |
|---|---|---|
| M15 lues pour l'impulsion | commencent à **07:00** ou après | la liquidité européenne arrive à partir de l'ouverture de Francfort et de Londres ; les heures asiatiques, plus calmes, ne sont pas visées par la recette |
| Reconnaissance d'une impulsion | `t_j` de **08:00** à **14:15** inclus | 08:00 est la première disponibilité d'une fenêtre de 4 M15 commençant à 07:00 ; à 14:15, un drapeau minimal de 2 M15 est formé au plus tôt à 14:45 |
| Formation du drapeau `F` | au plus tard **14:45** inclus | laisse au moins une M5 (ou une M15 en comparaison) avant la borne de décision |
| Décision d'entrée `D` | au plus tard **15:00** inclus | — |
| Exécution | au plus tard **15:05** inclus (validité de 5 min, §5.6) | — |
| Sortie temporelle | 2 h après l'exécution (§6.3) | — |
| Liquidation | **17:00** (§6.3) | — |

Une entrée exécutée après 15:00 dispose de **moins de 2 h** avant 17:00 : pour elle, la
liquidation précède la sortie temporelle. Faute de cotation à l'échéance, une position peut
**subsister après 17:00**, jusqu'au premier tick postérieur (§6.3).

La fenêtre couvre Londres et le chevauchement Londres / New York (environ 13:00-17:00 Londres), où
la liquidité est la plus forte. La liquidation tombe avant la clôture de New York (17:00 New York =
21:00 ou 22:00 Londres) : aucune nuit prévue, donc aucun financement, sauf `NUIT_NON_PRÉVUE`.

### 5.3 Formation du drapeau sur M15 (proposé)

Après la reconnaissance à `t_j`, les M15 qui commencent à `t_j` ou après sont lues une à une, à
leur disponibilité. Notations : `E`, `I` et `p` sont les valeurs **connues avant** la M15 lue ;
`seuil = E − 0,5 × I`. Chaque M15 est examinée dans cet ordre, la première règle applicable
s'appliquant seule :

1. **Qualité** : M15 présente et `OK` ; sinon, abandon (« données inutilisables pendant le
   drapeau »), sans lire ses prix.
2. **Expiration** (§5.5) : si la M15 se termine après l'échéance de la configuration, elle n'est
   pas lue ; la configuration a expiré à l'échéance.
3. **Profondeur** : si `bid_low < seuil`, **invalidation** (« repli trop profond »), même si la
   même M15 dépasse aussi `E`. La profondeur est comparée à l'**ancien** `E` et à l'**ancien** `I`,
   ceux qui étaient connus avant la bougie. **Priorité de l'invalidation sur l'extension** : on
   ne sait pas si le plus bas a précédé le plus haut ; une bougie qui couvre à la fois un nouveau
   sommet et un repli de plus de la moitié de l'impulsion n'est pas une pause, quelle que soit sa
   chronologie interne.
4. **Extension** : sinon, si `bid_high > E`, l'impulsion se prolonge : `E` := ce plus haut, `p` :=
   cette M15, `I := E − O`, et **le décompte du drapeau repart de zéro**. Cette M15 est une bougie
   de sommet ; elle **ne compte pas** comme bougie de pause, et son plus bas n'entre pas dans le
   drapeau. Si l'impulsion compte alors plus de **6 M15** (de `o` à `p`), la configuration est
   abandonnée (« impulsion prolongée sans pause »). La bougie d'extension n'est soumise à aucune
   condition de clôture.
5. **Bougie de pause** : sinon (`bid_low ≥ seuil` et `bid_high ≤ E`), la M15 compte comme bougie
   du drapeau.

Le **drapeau est formé** à la disponibilité de la **2e bougie de pause consécutive suivant la
dernière bougie de sommet** `p` (pause d'au moins 30 min). Cet instant est noté `F`. Les bougies
de pause qui précèdent une extension ne comptent plus : seules comptent celles qui suivent le
dernier `p`. Si `F > 14:45`, abandon (« fin de fenêtre ») ; `F = 14:45` est admis.

Après `F`, `E`, `I` et `p` sont **figés**. Une bougie au-delà de `E` n'est plus une extension : la
sortie du drapeau se lit sur M5 (§5.4), ou sur M15 en comparaison.

**Figure retenue** (« construction de la figure », cahier §6.3) : borne supérieure **`E`**, le
dernier sommet de l'impulsion ; borne inférieure, le plus bas des bougies de pause. La figure est
une **boîte** sous le sommet, définie par des prix observés, sans tracé de droite ni ajustement.

**Pente** (« à fixer », cahier §6.3) : **non contrainte** dans la référence. Un drapeau descendant,
horizontal ou montant sous `E` est admis tant qu'il respecte la profondeur et la durée. La pente
(clôture de la dernière bougie de pause moins clôture de la première, rapportée à `A`) est
journalisée à titre descriptif. Une contrainte de pente relèverait d'une variante distincte (§12).

### 5.4 Sortie du drapeau (M5 en référence, M15 en comparaison) (proposé)

À partir de `F`, les bougies de déclenchement (M5 en référence, M15 en comparaison) qui commencent
à `F` ou après sont lues une à une, à leur disponibilité, dans cet ordre, **la même convention
valant pour les deux unités** :

1. **Qualité** : bougie présente et `OK` ; sinon, abandon (« données inutilisables pendant le
   drapeau »), sans lire ses prix.
2. **Expiration** (§5.5) : une bougie qui se termine après l'échéance n'est pas lue.
3. **Profondeur** : `bid_low < E − 0,5 × I` (valeurs figées à `F`) : **invalidation** (« repli trop
   profond »), **prioritaire sur la sortie** même si la clôture de la même bougie est au-delà de
   `E + 0,1 × A` (ordre interne inconnu, même raison qu'au §5.3).
4. **Sortie confirmée** : `bid_close > E + 0,1 × A`. Une clôture au-delà de `E` mais en deçà de la
   marge n'est pas une sortie ; un plus haut au-delà de `E` sans clôture au-delà de la marge ne
   change rien.
5. Sinon, la bougie suivante est lue.

`D` = disponibilité de la bougie de sortie (= son `end_utc`).

**Bas du drapeau** : `FL` = plus bas `bid_low` des bougies de pause M15 (après le dernier `p`) et
des bougies de déclenchement lues de `F` à la bougie de sortie incluse (pour une vente : `FH_ask`
= plus haut `ask_high` de ces bougies). En comparaison M15, les deux ensembles sont des M15.

### 5.5 Échéances de la configuration (proposé)

- **Échéance** : `Δ = min(fin(p) + 90 min, 15:00)`, où `p` est le **dernier** sommet (une
  extension repousse donc l'échéance ; après `F`, elle est figée). 90 min = 6 M15 après le
  sommet : durée maximale de la pause.
- **Borne incluse** : une bougie dont `end_utc ≤ Δ` peut former le drapeau ou confirmer la
  sortie ; une clôture **exactement** à l'échéance (`end_utc = Δ`, donc `D = Δ`) **confirme**.
  Les échéances tombent sur la grille de 15 min, donc aussi sur celle de 5 min : la règle est la
  même en M5 et en M15.
- **Expiration** : si aucune sortie n'est confirmée par une bougie se terminant au plus tard à
  `Δ`, la configuration **expire à l'instant `Δ`** (« consolidation trop longue » si
  `Δ = fin(p) + 90 min`, « fin de fenêtre » si `Δ = 15:00` ; si les deux coïncident, « fin de
  fenêtre »). **Aucune clôture postérieure** à `Δ` ne peut confirmer, même si elle sort du
  drapeau : la configuration est close à `Δ`.
- **Drapeau non formé** à `Δ` (ou après 14:45) : la configuration expire de même, avant toute
  lecture sur M5.
- La recherche d'impulsion reprend avec les M15 qui commencent à `Δ` ou après (§5.7).

### 5.6 Décision d'entrée (instant `D`) et entrée en attente

La décision lit l'état **strictement antérieur à `D`**. Entrée décidée si, dans cet ordre :
1. aucune position DAY_02 ouverte ni entrée DAY_02 en attente (§5.7) ;
2. **limite de perte journalière non atteinte**, si elle est retenue (§7.1) ;
3. marché ouvert à `D` selon le calendrier ;
4. **cotation à `D`** : dernier tick strictement antérieur à `D`, dans la bougie de sortie
   (`ts ≥ D − 5 min` en référence, `ts ≥ D − 15 min` en comparaison M15), bid et ask positifs,
   bid ≤ ask. Il donne `P_D` (ask à l'achat) et le prix de sortie courant (bid à l'achat). Sinon,
   abstention « absence de cotation à `D` » ;
5. **stop admissible** (§6.1) : `S` strictement sous le bid courant et `P_D − S > 0` ; sinon,
   abstention « stop non admissible ». Aucune distance minimale IG n'est modélisée (§8) ;
6. **cible du bon côté** : `T > P_D` (§6.2) ; sinon, abstention « cible déjà dépassée à `D` ».
   Contrairement à un multiple du risque, la cible projetée n'est pas du bon côté par
   construction : le prix peut avoir déjà parcouru l'amplitude projetée à `D` ;
7. taille admise par le budget de risque (§7).

Une abstention à `D` met fin à la configuration (§5.7).

**Exécution** : l'ordre décidé à `D` est exécuté au **premier tick admissible** de `]D, D + 5 min]`
(tick valide, marché ouvert, hors fermeture). Sans tick admissible : `ENTRÉE_EXPIRÉE`, entrée
décidée non exécutée ; aucune exécution supposée.
- **Validité de 5 min** : une M5, l'unité de déclenchement ; au-delà, la sortie du drapeau qui a
  motivé l'entrée n'est plus l'information la plus récente. Même durée en comparaison M15, pour que
  seules les unités de lecture diffèrent.
- **Interruption avant l'exécution** (convention du §4.1) : annulation dès qu'un silence de
  strictement plus de 5 min est connu, y compris révélé par le premier tick suivant, qui n'exécute
  pas (`ENTRÉE_ANNULÉE_INTERRUPTION`).
- **Limite de perte journalière atteinte pendant l'attente** (si retenue) : annulation (§7.1).
- Aucune exécution après **15:05** Londres.

### 5.7 Tentatives et configurations successives (proposé)

- **Une configuration à la fois** : tant qu'une configuration est en cours (de la reconnaissance
  de l'impulsion à son abandon, son invalidation, son expiration ou la décision à `D`), aucune
  autre impulsion n'est recherchée, dans aucun sens.
- **Une position à la fois** : aucune impulsion n'est recherchée tant qu'une entrée est en attente
  ou qu'une position DAY_02 est ouverte, y compris une position qui subsiste après 17:00 faute de
  cotation.
- **Reprise de la recherche** : après la fin d'une configuration sans entrée, ou après la sortie
  d'une position (ou l'issue d'une entrée non exécutée), la fenêtre d'impulsion suivante ne peut
  contenir **aucune M15 commençant avant cet instant** : une bougie ne sert jamais à deux
  configurations.
- **Conséquence** : la suite des configurations d'une séance **dépend des exécutions** (durée des
  positions, sorties au tick). Contrairement à DAY_01, dont le parcours jusqu'à `D` ne dépendait
  ni des ticks ni des positions, l'étude de disponibilité de DAY_02 ne peut pas reproduire à
  l'identique toutes les configurations du passage de performance (§10.1).
- **Pas de plafond journalier de tentatives** dans la référence : la recette ne porte pas sur un
  événement unique de la séance, et plusieurs impulsions peuvent se produire dans une journée. Le
  nombre de configurations, d'entrées et de pertes par séance sera rapporté. Alternatives au §12.
  La limite de perte journalière du cahier est traitée à part (§7.1) : ce n'est pas un plafond de
  tentatives.

### 5.8 Vente (règle symétrique)

- Origine `O` = plus haut `bid_high` de `W_j`, bougie `o` = la première qui l'atteint ; sommet `E` =
  plus bas `bid_low` de `W_j`, bougie `p` = la dernière qui l'atteint ; **`o < p = j`** ;
  `I = O − E`.
- Reconnaissance : `O − bid_close_j ≥ 1,5 × A` et `bid_close_j ≤ E + 0,25 × I`.
- Formation : profondeur `bid_high > E + 0,5 × I` (ancien `E`, ancien `I`) : invalidation,
  prioritaire ; sinon extension si `bid_low < E` ; sinon bougie de pause (série bid, comme
  l'achat).
- Sortie : `bid_close < E − 0,1 × A`, après le contrôle de profondeur.
- Stop au-dessus du plus haut `ask_high` du drapeau (§6.1) ; cible `T = E − I`.

## 6. Stop, cible et sorties (proposé)

### 6.1 Stop

- **Achat** : `S = FL − 0,25 × A`, derrière la borne opposée du drapeau (cahier §6.3), avec la
  marge relative de S2, S3 et DAY_01 exprimée ici en `A` H1. **Vente** : `S = FH_ask + 0,25 × A`.
- Fixé à `D`, jamais déplacé. Stop **garanti simulé** avec sa prime, comme les références
  précédentes ; aucune distance minimale IG n'est appliquée (hypothèse explicite, §8).
- **Distances du stop non présumées** : `P_D − S` dépend de la profondeur du drapeau, de la
  position de la sortie par rapport à `E` et de `A` H1. Par construction, elle vaut au plus
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

- **Sortie temporelle** (« délai de sortie », cahier §6.3) : échéance `X + 2 h`, où `X` est
  l'instant d'exécution. Si ni le stop ni la cible n'ont fermé la position, ordre de clôture au
  marché à l'échéance, exécuté au premier tick strictement postérieur (`SORTIE_TEMPORELLE`).
  - **Raison** : une continuation doit reprendre rapidement ; une position qui stagne deux heures
    après la sortie d'un drapeau formé en 30 à 90 min ne correspond plus à l'hypothèse. 2 h est
    du même ordre que la durée totale de la figure (impulsion et pause, jusqu'à 3 h).
  - Elle ne sert pas de stop : elle ferme au prix observé, gain ou perte.
- **Liquidation de fin de séance : 17:00 Londres** : toute position encore ouverte reçoit à
  17:00:00 un ordre de clôture au marché, exécuté au premier tick strictement postérieur
  (`LIQUIDATION_17H`).
  - **Raison** : 17:00 Londres clôt le chevauchement Londres / New York ; la liquidité baisse
    ensuite. L'heure reste au moins 4 h avant la clôture de New York.
  - Différence avec DAY_01 (16:00) : DAY_01 n'entrait plus après 12:05 ; DAY_02 peut entrer
    jusqu'à 15:05.
- **Laquelle s'applique** : une seule clôture en attente par position, celle de la **première
  échéance atteinte**. Pour une exécution `X < 15:00`, l'échéance temporelle (`X + 2 h < 17:00`)
  vient d'abord ; pour `X > 15:00` (au plus 15:05), la liquidation de 17:00 vient d'abord et la
  position a eu **moins de 2 h**. **Égalité exacte** (`X = 15:00:00.000`, donc `X + 2 h =
  17:00:00.000`) : une seule clôture, motif **`LIQUIDATION_17H`** ; la coïncidence avec la sortie
  temporelle est journalisée en annotation, sans double comptage. Raison : la liquidation de
  séance est une borne fixe de la stratégie, indépendante de l'entrée.
- **Après l'échéance, faute de cotation** : la position **peut subsister après 17:00**. Conventions
  techniques du §4, sans prix invisible :
  - la position reste ouverte avec son stop et sa cible jusqu'au premier tick postérieur à
    l'échéance ; le motif reste celui de l'échéance déjà atteinte (une liquidation de 17:00 ne
    remplace pas une sortie temporelle en attente) ; délai après l'échéance, silence clos et motif
    de clôture journalisés séparément ;
  - si ce tick franchit déjà le stop ou la cible, priorité du moteur : stop, cible, puis clôture en
    attente ;
  - si le silence est une interruption pendant laquelle une borne a pu être franchie, la
    transaction est indéterminée et les scénarios A, B et C s'appliquent ;
  - sans tick avant la fin de la journée de cotation, clôture à la réouverture, comptée
    `NUIT_NON_PRÉVUE`, et aucune nouvelle configuration tant que la position subsiste ;
  - sans tick avant la fin de l'étude, position valorisée à part, sans sortie inventée.
- **Interruption pendant une position ouverte** : même traitement qu'au §4 (transaction conservée,
  indéterminée, scénarios A/B/C rejoués en entier ; une fermeture connue n'est pas une
  interruption).

### 6.4 Chronologie et résolution fine

- Décision à `D` sur l'état strictement antérieur à `D` ; exécution au premier tick `ts > D` ; un
  tick horodaté exactement à `D` est rejoué après la décision.
- Priorité sur un même tick (ASSUMP-024) : silence précédant le tick ; stop ; cible ; clôture en
  attente (sortie temporelle ou liquidation) ; contrôle de la limite de perte journalière, si elle
  est retenue (§7.1) ; entrée en attente. Un tick qui fait franchir la limite n'exécute donc pas
  une entrée en attente.
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

### 7.1 Limite de perte journalière (proposé ; à trancher)

Son omission **n'est pas acquise** : que les moteurs S1 à DAY_01 ne la simulent pas ne dispense pas
de l'appliquer si elle est exigée.

**Ce que demande le cahier** (§8, paraphrasé ; le cahier n'est pas publié dans ce dépôt) :
- un **seuil de perte journalière de 1 %** (20 € pour 2 000 €), proposé pour le compte de
  référence, à côté d'un seuil hebdomadaire de 2 % et d'une revue à 6 % de baisse depuis le
  sommet ; ces limites ne sont pas encore approuvées pour le réel ;
- les pertes journalières **incluent le réalisé, le latent et les frais**, corrigées des apports et
  retraits ; les fenêtres de calcul ont des **horaires fixés et documentés** ;
- le **franchissement d'un seuil** bloque les nouvelles entrées et les augmentations d'exposition,
  annule les ordres d'entrée en attente quand la connexion le permet, déclenche une alerte et
  conserve la gestion des protections existantes ; la liquidation immédiate est une commande
  distincte ; une **reprise après arrêt de risque exige une revue et une action explicite**.

**Traduction opérationnelle proposée pour le backtest DAY_02** :

| Élément | Proposition | Raison |
|---|---|---|
| Fenêtre journalière | journée de cotation New York, 17:00 → 17:00 New York (ASSUMP-015) | ancrage déjà utilisé par le projet ; une séance DAY_02 (07:00-17:00 Londres) tombe entière dans une seule journée de cotation |
| Fonds propres de référence `R_d` | fonds propres au début de la fenêtre : solde, plus la position éventuellement encore ouverte valorisée à la dernière cotation connue avant le début | « fonds propres actualisés, positions ouvertes comprises » (cahier §8) |
| Perte du jour `L(t)` | `R_d − fonds propres(t)` ; fonds propres = solde (réalisé, **tous coûts déjà comptés** : glissement, prime, conversion, financement) + latent de la position ouverte, valorisé côté sortie à la cotation courante (bid à l'achat), converti en euros | réalisé, latent et frais (cahier §8) ; même valorisation que le drawdown au tick des passages précédents ; pas d'apports ni de retraits en backtest |
| Franchissement | `L(t) ≥ 0,01 × R_d` (atteindre le seuil suffit) | lecture prudente de « franchissement » |
| Instants de contrôle | **à chaque tick** rejoué, et avant chaque décision à `D` (état strictement antérieur à `D`) | le latent change à chaque tick ; l'état bloqué doit être connu avant toute décision |
| Effet sur les nouvelles entrées | à partir du tick de franchissement, **aucune entrée décidée** jusqu'à la remise à zéro : les configurations restent détectées et journalisées, et une sortie confirmée donne l'abstention « limite de perte journalière atteinte » (configuration consommée) | blocage des nouvelles entrées ; garder le parcours observable |
| Augmentation d'exposition | sans objet (une position à la fois, ni renforcement ni pyramidage) | — |
| Entrée en attente | annulée au tick de franchissement, ce tick n'exécute pas (`ENTRÉE_ANNULÉE_LIMITE`) ; le contrôle passe avant l'exécution sur un même tick | « annule les ordres d'entrée en attente » ; avec une seule position à la fois, une entrée en attente n'a pas de position ouverte à côté, le cas ne peut donc survenir que si les fonds propres changent sans position (non prévu) : règle écrite pour être complète |
| Position ouverte | **conservée**, avec son stop, sa cible, sa sortie temporelle et la liquidation de 17:00 ; aucune liquidation forcée | « conserve la gestion des protections » ; la liquidation immédiate est une commande distincte, non simulée |
| Alerte | événement journalisé `LIMITE_JOURNALIÈRE_ATTEINTE` (instant, `R_d`, `L`, fonds propres, position ouverte) | « déclenche une alerte » |
| Remise à zéro | **convention de simulation** : blocage levé au début de la fenêtre suivante, avec un nouveau `R_d` ; chaque blocage est compté et rapporté | le cahier exige une revue et une action explicite, impossibles en backtest : cette convention les **remplace** explicitement, elle ne les reproduit pas |
| Portée | trajectoire DAY_02 seule, avec son propre capital | sur un compte réel, la limite porterait sur tout le compte et toutes les stratégies ; ce n'est pas simulé (pas de portefeuille partagé) |

**Choix restant à trancher** (§12) :
1. appliquer la limite dans la référence DAY_02, ou la reporter à la simulation d'un compte
   commun (avec alors un simple comptage descriptif, qui **ne remplace pas** son application si
   elle est exigée) ;
2. fenêtre : journée de New York ou journée civile de Londres ;
3. latent : valorisation côté sortie sans coûts futurs (proposé), ou en déduisant les coûts de
   sortie estimés (glissement, conversion) ;
4. franchissement : `≥` (proposé) ou `>` ;
5. remise à zéro : à la fenêtre suivante (proposé), à la semaine suivante, ou arrêt de la
   trajectoire jusqu'à revue (résultats après l'arrêt non simulés) ;
6. **seuil hebdomadaire de 2 %**, exigé par le même passage : même mécanique sur la semaine de
   cotation (dimanche 17:00 → vendredi 17:00 New York), à inclure ou non ;
7. **seuil de 6 %** : les protocoles S2, S3 et DAY_01 l'ont traité comme un seuil de revue, la
   trajectoire continuant (ADR-015). La phrase du cahier sur le franchissement « d'un seuil » peut
   se lire comme s'appliquant aussi à lui ; à confirmer pour DAY_02 ;
8. comparabilité : S1 à DAY_01 ont été mesurées **sans** ces limites. Si DAY_02 les applique, une
   comparaison sans limite serait une variante distincte, préenregistrée, sur autorisation.

Avec une position à la fois et 0,25 % de risque par opération, atteindre 1 % dans une journée
demande environ quatre pertes au stop, coûts compris, ou un écart au-delà d'un stop : la limite ne
peut jouer que les jours à plusieurs configurations, possibles puisque les tentatives ne sont pas
plafonnées (§5.7). Le nombre de blocages et de configurations écartées sera rapporté.

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
`W_j` absente, non `OK` ou avant 07:00 ; `A` non calculable ; ordre des extrêmes non établi
(`o ≥ p`) ; sommet antérieur à `j` (`p < j`) ; amplitude insuffisante ; clôture non forte ; cas
ambigu. Ces cas sont comptés par cause, à la première cause dans cet ordre.

**Fin d'une configuration**, une seule cause, celle qui survient la première :
1. données inutilisables pendant le drapeau (M15 ou bougie de déclenchement absente ou non `OK`) ;
2. impulsion prolongée sans pause (plus de 6 M15) ;
3. repli trop profond (prioritaire sur une extension ou une sortie de la même bougie) ;
4. consolidation trop longue (expiration à `fin(p) + 90 min`) ;
5. fin de fenêtre (drapeau non formé à 14:45 ou expiration à 15:00) ;
6. à `D` : limite de perte journalière atteinte (si retenue) ; marché fermé ; absence de cotation ;
   stop non admissible ; cible déjà dépassée ; taille minimale supérieure au budget ;
7. entrée décidée.

**Entrée décidée**, une seule issue : exécutée ; exécutée puis liquidée
(`STOP_DÉPASSÉ_À_L'EXÉCUTION`) ; exécutée puis sortie à la cible sur le même tick
(`CIBLE_ATTEINTE_À_L'EXÉCUTION`) ; `ENTRÉE_EXPIRÉE` ; `ENTRÉE_ANNULÉE_INTERRUPTION` ;
`ENTRÉE_ANNULÉE_LIMITE` (si la limite est retenue).

**Entrée exécutée**, une seule issue : sortie liée au stop ; cible ; `SORTIE_TEMPORELLE` ;
`LIQUIDATION_17H` ; encore ouverte à la fin de l'étude. Les annotations (indéterminée,
`NUIT_NON_PRÉVUE`, clôture après interruption, coïncidence des échéances, position ouverte pendant
un blocage journalier) recoupent ces issues et ne sont jamais additionnées.

Chaque entrée décidée doit être attestée par une transaction ou un événement de non-exécution
(contrôle de S3 et DAY_01).

## 10. Protocole de test (à figer avant chaque étape, sur autorisation)

Aucune de ces étapes n'est autorisée par cette fiche.

1. **Validation de la fiche** : arbitrages du §12 tranchés, ASSUMP-029 approuvée ou corrigée.
2. **Choix de réutilisation du code** : examiné avant l'implémentation (moteur DAY_01, moteur S1 ou
   moteur propre). La fiche décrit le comportement attendu ; elle ne fige pas d'héritage
   technique.
3. **Moteur et tests synthétiques** : exemple du §11 reproduit ; vente ; `o = p` et `p < j` sans
   reconnaissance ; extension ; bougie qui dépasse `E` et franchit le seuil de profondeur
   (invalidation) ; bougies de pause antérieures à une extension non comptées ; repli trop profond
   en M15 et en M5 ; sortie et profondeur sur la même bougie ; clôture exactement à l'échéance (qui
   confirme) et clôture postérieure (sans effet) ; fin de fenêtre ; `A` excluant la fenêtre
   d'impulsion ; bougie non `OK` dont les prix ne sont pas lus ; cible déjà dépassée à `D` ; sortie
   temporelle ; liquidation de 17:00 avec et sans cotation ; échéances simultanées ; position
   subsistant après 17:00 ; `NUIT_NON_PRÉVUE` ; position ouverte à la fin de l'étude ; configurations
   successives sans bougie partagée ; limite journalière (franchissement par le latent, entrée
   refusée, position conservée, remise à zéro), si elle est retenue.
4. **Non-régression** : rejeu S1 si un moteur partagé est modifié.
5. **Disponibilité** 2015-2021, sans tick ni position, selon la convention du §10.1.
6. **Performance** 2015-2021 : référence H1 → M15 → M5 en scénario A, comparaison H1 → M15, puis B,
   C ou rejet selon des conditions de déclenchement fixées à l'avance, comme pour S2, S3 et DAY_01.
   Avant ce passage, décision de l'opérateur sur les conditions IG (§8).

### 10.1 Étude de disponibilité : convention sans ticks ni positions (proposé)

Dans le passage de performance, la recherche est suspendue pendant une entrée en attente ou une
position ouverte, et elle reprend après la sortie (§5.7). L'instant de reprise dépend des ticks.
L'étude de disponibilité ne lit aucun tick et **n'ajoute aucune position fictive** pour imiter
cette suspension.

**Convention proposée, « parcours sans position »** : chaque configuration est suivie jusqu'à sa
fin ; une sortie confirmée à `D` est comptée comme **sortie confirmée** (pas comme une entrée) et
met fin à la configuration ; la recherche reprend avec les M15 qui commencent à `D` ou après,
comme après un refus à `D` dans le passage de performance.

**Ce qui restera comparable** :
- **à l'identique** : toute configuration qui démarre d'un même état (aucune configuration ni
  position, même instant de reprise) a le même parcours dans les deux passages (impulsion,
  extensions, drapeau, causes, échéance, `D`, niveaux structurels), car elle ne dépend que des
  bougies. En particulier, la **première configuration de chaque séance** est identique dans les
  deux passages, sauf si une position d'une séance précédente subsiste (`NUIT_NON_PRÉVUE`) ; ces
  séances sont listées ;
- **contrôle proposé pour le passage de performance** : chaque configuration y est recalculée par
  la même fonction, sur les seules bougies, depuis son instant de reprise réel, et doit concorder
  champ par champ (contrôle bloquant, comme le rapprochement de DAY_01, mais configuration par
  configuration) ;
- les comptes de la première configuration de séance (causes de fin, sorties confirmées).

**Ce qui pourra différer**, sans qu'aucune égalité ni inclusion ne soit promise :
- le nombre et la suite des configurations après la première sortie confirmée d'une séance : une
  configuration de l'étude peut tomber pendant une position du passage de performance, et après la
  sortie de cette position, le passage de performance peut trouver une configuration que l'étude
  n'a pas, parce que l'étude a consommé d'autres bougies ;
- donc les totaux de configurations, de sorties confirmées et de causes par séance et par année.
Les deux séries seront présentées côte à côte, avec la part des séances concernées, sans les
présenter comme un rapprochement exact.

**Mesures calculables sur les bougies seules (étude) et mesures exigeant une cotation à `D`** :

| Bougies seules (structurelles) | Cotation bid/ask à `D` ou exécution (performance seulement) |
|---|---|
| `A`, `O`, `E`, `I`, bougies `o` et `p`, durée de l'impulsion, extensions | `P_D` (ask à l'achat, bid à la vente) et prix de sortie courant |
| durée du drapeau, profondeur `(E − FL) / I`, pente | admissibilité du stop par rapport au prix courant |
| niveaux `S` (bid à l'achat, `ask_high` à la vente) et `T`, échéance `Δ`, instant `D` | `P_D − S`, `T − P_D`, rapport des distances estimé à `D`, rapport net estimé |
| distances structurelles `E − S`, `T − E`, en pips et en multiples de `A` | « cible déjà dépassée » au sens du §5.6 |
| **indicateurs approchés**, étiquetés comme tels : distances depuis la clôture de la bougie de sortie (`bid_close − S`, `T − bid_close`), et « clôture au-delà de `T` » | taille, refus de taille, part des coûts fixes dans le risque |
| — | rapport obtenu à l'exécution, issues, résultats, limite journalière |

La clôture d'une bougie est la cotation de son dernier tick valide ; elle devrait correspondre à la
cotation retenue à `D` (dernier tick strictement antérieur à `D`, dans la bougie de sortie). Cette
correspondance **n'est pas supposée** : l'étude publie des indicateurs approchés, et le passage de
performance mesurera l'écart entre ces indicateurs et les valeurs à `D`.

Rapportés par l'étude, en plus : fréquence des M15 et M5 non `OK` et des silences de plus de 5 min
dans la fenêtre propre de DAY_02 (bougies de 07:00 à 15:00), à titre descriptif, sans changer le
seuil (§4.1).

### 10.2 Mesures rapportées par le passage de performance

En plus des mesures du cahier (§9) :
- parcours des impulsions aux entrées, avec les dénominateurs à chaque étape ;
- configurations, entrées et pertes par séance ; blocages par la limite journalière, si elle est
  retenue, et configurations écartées ;
- résultats par jour, par heure de décision, en heure d'hiver ou d'été et pendant les semaines de
  décalage, par sens ;
- distances du stop (pips et multiples de `A`), part des coûts fixes dans le risque, rapports
  estimés, nets estimés et obtenus, côte à côte, sans filtre ; écart entre indicateurs approchés
  de l'étude et valeurs à `D` ;
- pente du drapeau et nombre de bougies de pause (descriptif) ;
- sorties temporelles et liquidations de 17:00 (délai, silence clos, motif), positions subsistant
  après 17:00 ;
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
| 09:15:00 | `W_j` = M15 de 08:15 à 09:15 : [08:15) O 1,13020 H 1,13040 L 1,13000 C 1,13010 et les trois suivantes ci-dessous | `O` = 1,12980 (M15 de 08:45), `E` = 1,13060 (M15 de 09:00), `o < p = j` ; mais 1,13055 − 1,12980 = 7,5 pips < 15 pips : amplitude insuffisante, pas d'impulsion |
| **09:30:00** | `W_j` = M15 de 08:30 à 09:30 : [08:30) O 1,13010 H 1,13030 L 1,12995 C 1,13005 ; [08:45) O 1,13005 H 1,13020 L 1,12980 C 1,13000 ; [09:00) O 1,13000 H 1,13060 L 1,12990 C 1,13055 ; [09:15) O 1,13055 H 1,13140 L 1,13050 C 1,13130 | `O` = 1,12980 (M15 de 08:45, `o`) ; `E` = 1,13140 (M15 de 09:15, `p`) ; `o < p = j`, impulsion de 3 M15 ; `I` = 16 pips ; 1,13130 − 1,12980 = 15 pips ≥ 1,5 × `A` ; 1,13130 ≥ 1,13140 − 4 pips : **impulsion haussière reconnue** ; seuil de profondeur `E − 0,5 × I` = 1,13060 |
| 09:45:00 | M15 [09:30, 09:45) O 1,13130 H 1,13135 L 1,13090 C 1,13100 | pas d'extension (1,13135 ≤ `E`) ; 1,13090 ≥ 1,13060 : **1re bougie de pause** après le sommet |
| **10:00:00** | M15 [09:45, 10:00) O 1,13100 H 1,13120 L 1,13075 C 1,13110 | **2e bougie de pause : drapeau formé**, `F` = 10:00 ; échéance `Δ` = min(`fin(p)` + 90 min ; 15:00) = 11:00, incluse |
| 10:05:00 | M5 [10:00, 10:05) O 1,13110 H 1,13128 L 1,13100 C 1,13125 | 1,13125 ≤ `E + 0,1 × A` = 1,13150 : pas de sortie |
| **10:10:00** | M5 [10:05, 10:10) O 1,13125 H 1,13160 L 1,13120 C 1,13155 | 1,13155 > 1,13150 : **sortie confirmée**, `D` = 10:10:00.000 ; `FL` = min(1,13090 ; 1,13075 ; 1,13100 ; 1,13120) = 1,13075 |
| 10:10:00.000 | décision | dernier tick avant `D` : 10:09:59.820, bid 1,13155, ask 1,13157 = `P_D` ; `S` = 1,13075 − 2,5 pips = 1,13050 < bid : admissible ; `T` = `E + I` = 1,13300 > `P_D` ; `P_D − S` = 10,7 pips, `T − P_D` = 14,3 pips, rapport des distances estimées ≈ 1,34 ; entrée en attente jusqu'à 10:15:00 |
| 10:10:00.230 | premier tick postérieur à `D`, ask 1,13158 | **entrée** à 1,13158 |
| (cas 1) 11:02:14.510 | premier bid ≥ 1,13300 | sortie à la cible |
| (cas 2) 12:10:00.230 | aucune borne atteinte | **sortie temporelle** au premier tick postérieur à 12:10:00.230 |

Variantes de la M15 [09:45, 10:00) :
- plus haut 1,13145, plus bas 1,13075 : **extension** (`E` = 1,13145, `p` = cette M15, `I` = 16,5
  pips, nouveau seuil 1,13145 − 8,25 pips = 1,130625) ; elle n'est pas une bougie
  de pause, et la pause de 09:30 ne compte plus : le drapeau ne peut être formé qu'à 10:30 au plus
  tôt, échéance repoussée à 11:30 ;
- plus haut 1,13120, plus bas 1,13055 (< 1,13060) : **invalidation** (repli trop profond) ;
- plus haut 1,13145 **et** plus bas 1,13055 : **invalidation**, comparée à l'ancien seuil 1,13060 et
  prioritaire sur l'extension (§5.3).

Si aucune M5 ne clôturait au-delà de 1,13150 jusqu'à celle qui se termine à 11:00 incluse
(`Δ = fin(p) + 90 min`), la configuration expirerait à 11:00 ; une M5 [11:00, 11:05) clôturant à
1,13160 serait sans effet.

## 12. Arbitrages

**Base de rédaction retenue par l'opérateur le 2026-11-07** (hypothèses de recherche, pas des
paramètres démontrés optimaux ; ASSUMP-029 reste `PROPOSED`) : H1 pour l'ATR, configuration M15,
déclenchement M5 et comparaison M15, cible par projection, sortie temporelle de deux heures,
horaires proposés, configurations successives, absence de filtre d'annonces. **Principe retenu** :
extension à DAY_02 de la convention de qualité à 5 minutes, avec contrôle de couverture sur sa
fenêtre propre, sans changer les H1 ni leur convention (§4.1).

### 12.1 Points corrigés le 2026-11-07 (à valider)

| # | Point | Règle proposée |
|---|---|---|
| R1 | Ordre des extrêmes | `E` et `O` sur toute la fenêtre ; `o` première bougie de `O`, `p` dernière bougie de `E` ; **`o < p = j`** ; aucun ordre supposé à l'intérieur d'une bougie ; impulsion de 2 à 4 M15 à la reconnaissance (§5.1) |
| R2 | Extension et profondeur sur la même M15 | profondeur comparée à l'**ancien** `E` / `I` ; **invalidation prioritaire** sur l'extension ; la bougie d'extension n'est pas une bougie de pause ; les deux bougies de pause suivent le **dernier** sommet (§5.3) |
| R3 | Sortie et profondeur sur la même bougie de déclenchement | invalidation prioritaire, en M5 comme en M15 (§5.4) |
| R4 | Échéances | `Δ = min(fin(p) + 90 min, 15:00)`, **borne incluse** : une clôture exactement à `Δ` confirme ; expiration à `Δ`, aucune clôture postérieure ne sauve la configuration ; mêmes règles en M5 et en M15 (§5.5) |
| R5 | Étude de disponibilité | « parcours sans position », sans position fictive ; première configuration de séance identique, suite pouvant différer ; contrôle par configuration dans le passage de performance ; mesures structurelles distinguées des mesures à `D` (§10.1) |
| R6 | Limite de perte journalière | traduction opérationnelle au §7.1 |
| R7 | Horaires | entrée après 15:00 : moins de 2 h avant 17:00 ; position pouvant subsister après 17:00 faute de cotation ; échéances simultanées : motif `LIQUIDATION_17H` (§5.2, §6.3) |

### 12.2 Arbitrages résiduels

| # | Point | Proposition | Alternatives |
|---|---|---|---|
| 1 | Limite journalière dans la référence | appliquée (§7.1) | reportée à la simulation d'un compte commun |
| 2 | Fenêtre journalière | journée de cotation New York | journée civile de Londres |
| 3 | Latent dans la perte du jour | valorisé côté sortie, coûts futurs non déduits | coûts de sortie estimés déduits |
| 4 | Franchissement | `L ≥ 1 %` de `R_d` | `L > 1 %` |
| 5 | Remise à zéro | à la fenêtre suivante, convention qui remplace la revue | semaine suivante ; arrêt de la trajectoire |
| 6 | Seuil hebdomadaire de 2 % | même mécanique sur la semaine de cotation | non appliqué dans la référence |
| 7 | Seuil de 6 % | revue, trajectoire continue (comme S2 à DAY_01) | blocage des entrées |
| 8 | Comparaison sans limite | aucune dans la référence ; variante préenregistrée sur autorisation | — |
| 9 | Priorité invalidation / extension (R2, R3) | invalidation | extension prioritaire ; bougie ambiguë abandonnée sans cause de profondeur |
| 10 | Échéance incluse (R4) | incluse | exclue |
| 11 | Motif des échéances simultanées (R7) | `LIQUIDATION_17H` | `SORTIE_TEMPORELLE` |
| 12 | Fenêtre d'impulsion | 4 M15 glissantes (1 h) | 2 ou 6 M15 |
| 13 | Amplitude minimale | `bid_close_j − O ≥ 1,5 × A` | 1 × `A` ; 2 × `A` |
| 14 | Clôture forte | `bid_close_j ≥ E − 0,25 × I` | sans condition ; tiers supérieur |
| 15 | Extension | jusqu'à 6 M15 d'impulsion, sans condition de clôture | sans extension ; clôture forte exigée |
| 16 | Profondeur | au plus 50 % de `I`, sur les plus bas | 38,2 % ; sur les clôtures |
| 17 | Durée du drapeau | au moins 2 bougies de pause, sortie au plus tard 6 M15 après le sommet | 1 à 4 M15 ; 3 à 8 M15 |
| 18 | Figure et pente | boîte sous `E`, pente non contrainte, journalisée | pente opposée exigée ; fanion en variante |
| 19 | Sortie du drapeau | clôture au-delà de `E + 0,1 × A` | sans marge ; `0,2 × A` |
| 20 | Stop | `FL − 0,25 × A`, garanti simulé, sans minimum IG | marge `0,1 × A` ; stop normal si le minimum IG exclut les stops courts (§8) |
| 21 | Variantes de sortie | protocoles distincts : multiple du risque, obstacle, suiveuse, rapport net minimal | — |
| 22 | Tentatives | sans plafond, une configuration et une position à la fois | une ou deux par séance |
| 23 | Validité de l'entrée | 5 min, référence et comparaison | 1 min ; 15 min en comparaison M15 |
| 24 | Conditions IG | étude sous les hypothèses actuelles ; décision avant les passages de performance (§8) | confirmation préalable |
| 25 | Instrument | EUR/USD seulement | GBP/USD (cahier §2), après données et décision |
| 26 | Réutilisation du code | non figée ; examinée avant l'implémentation (§10) | — |
