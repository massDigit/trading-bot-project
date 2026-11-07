# DAY_02 — Disponibilité des données, développement 2015-2021 (protocole)

**Statut** : protocole **approuvé dans son principe** le 2026-11-07 (commit `3345afd`), avec quatre
précisions intégrées (calendrier, couverture, portée des contrôles, mesures ; ADR-031). Fiche figée
`docs/strategies/DAY_02_FLAG_CONTINUATION.md` (ADR-028), §10.1. Outil `forex-day02-availability`
(`backtest/day02_availability.py`) et tests synthétiques écrits. Passage 2015-2021 autorisé et
lancé le 2026-11-07 depuis `eb48d6c`, C1 à C10 conformes ; bilan agrégé
`DAY02_AVAILABILITY_2015_2021_BILAN.md`, validé après précisions ; étude **close** (ADR-033). Cette étude ne lit aucun tick et ne produit ni entrée, ni transaction, ni gain ou perte.
Ce n'est ni une validation de performance, ni une autorisation de trading.

## 1. Objet

Décrire, séance par séance, ce que DAY_02 voit **sur les bougies seules**, jusqu'à la sortie du
drapeau incluse : recherches, M15 examinées, impulsions reconnues, extensions, drapeaux formés,
fins de configuration et sorties confirmées (instants `D`). Deux trajectoires de lecture :

- **référence** : H1 → M15 → M5 (`Day02Params()`) ;
- **comparaison préenregistrée** : H1 → M15 (`Day02Params(trigger=Trigger.M15)`).

L'impulsion et la formation du drapeau se lisent sur M15 dans les deux ; seules la sortie du
drapeau, la profondeur après `F` et l'extrême du drapeau diffèrent.

## 2. Règles, paramètres et données

- **Règles et paramètres** : ceux de la fiche figée, **sans modification**, via `Day02Params()` et
  `Day02Params(trigger=Trigger.M15)`. Aucune grille, aucun réglage : les distributions rapportées
  ne servent à modifier aucun paramètre.
- **Bougies M5 et M15** : lot `data/bars/dukascopy/EURUSD/intraday_2015_2021_day01_5min/`,
  convention à 5 minutes étendue à DAY_02 (ADR-026 : silence > 5 min, M5 sans tick et M15 à
  sous-créneau vide non `OK`). Empreintes vérifiées **avant lecture** : `5m` `94387741…fb82`,
  `15m` `64b30520…9db2` (bilan des données §8.1). Toute différence arrête l'étude.
- **H1 et trous** : `data/bars/dukascopy/EURUSD/1h.parquet` et trous du rapport de qualité
  `data/reports/quality_dukascopy_EURUSD.json` (`load_gaps`), qui influencent les états H1 et l'ATR.
- **Empreintes des entrées** (corrections du 2026-11-07, ADR-032), comparées **en entier** avant
  toute lecture, puis enregistrées avant et après le passage :

  | Entrée | Référence | Provenance de la référence |
  |---|---|---|
  | `5m.parquet` du lot à 5 min | `9438774154972aafa2cc924cf6042e6ae2b3c97de23328644b7d54f3af50fb82` | sortie de l'audit à 5 min (`intraday_dukascopy_EURUSD_2015_2021_day01_5min.json`, `outputs_sha256`) |
  | `15m.parquet` du lot à 5 min | `64b305201c2f8e48afd257048e07800cea1778e17228673b4c4af7c6a86a9db2` | idem |
  | `1h.parquet` | `a7c7f8b82ac55828bbbc25b8fd87c64cac99efb5a977187c47b381480802c585` | `existing_bars_sha256`, avant et après, des deux audits intraday : `intraday_dukascopy_EURUSD_2015_2021.json` (commit `36daea1`, arbre propre) et sa reprise à 5 min (commit `c0272cc`, arbre avec modifications non commitées) ; préfixe publié dans le bilan des données |
  | `quality_dukascopy_EURUSD.json` | **aucune référence historique** : aucun audit n'a enregistré son empreinte | empreinte enregistrée avant et après le passage seulement ; contenu ancré par le nombre de trous chargés jusqu'au 2022-01-01, **383**, celui des passages DAY_01 (bilan de performance DAY_01), sur la fenêtre officielle seulement |

  Une empreinte calculée le 2026-11-07 pour le rapport de qualité (`0cdcebee…6b9`) n'est **pas** une
  référence d'audit ; elle n'est pas utilisée comme telle. Les états H1
  gardent la convention H1 du projet (seuil `ResearchConfig.gap_threshold`, 10 min), **inchangée** ;
  ATR Wilder 14 H1 avec continuité des H1 prévues.
- **Aucun tick lu.** Les contrôles à `D` (marché, cotation, stop admissible, cible encore devant,
  taille) et tout ce qui suit relèvent du passage de performance.
- **Fenêtres** :
  - **séances** : jours ouvrés de Londres dont 07:00 Londres tombe dans [2015-01-01, 2022-01-01),
    hors 25 décembre et 1er janvier (fiche §5) ;
  - **fenêtre propre de DAY_02** : M15 commençant de 07:00 à 14:45 Londres (impulsion,
    formation) ; M5 (référence) ou M15 (comparaison) de `F` jusqu'à 15:00 au plus (sortie) ;
  - **H1** : lues depuis le 2015-01-01, premier jour des données ; **l'amorçage de l'ATR est compté
    dans la période** (aucune H1 antérieure n'existe). Les premières séances de janvier 2015 peuvent
    donc donner « ATR H1 non calculable » : comptées par cause, jamais comblées ;
  - lecture bornée par `require_development_window` : **2022-2025 reste en réserve**.
- **Calendrier** (précision 1) : l'outil construit les dates **depuis les règles du calendrier**
  (jours ouvrés de Londres dont la fenêtre 07:00-17:00 tombe dans la période, puis exclusions du
  25 décembre et du 1er janvier), indépendamment de la sélection du moteur, et rapproche les deux
  listes. Sur la **fenêtre officielle complète** seulement, l'ancrage est celui d'un comptage
  indépendant : **1 827 jours ouvrés, 11 exclusions, 1 816 séances**. Une fenêtre partielle n'a
  pas d'ancrage ; le total DAY_01 n'est pas repris.

## 3. Méthode : « parcours sans position »

- **Fonction commune** : l'outil appelle `day02.configuration_from`, la fonction sur bougies du
  moteur, avec l'ATR H1 calculé par `Day02Backtest.atr_at` sur un moteur sans tick. Ce partage
  garantit que l'étude, le moteur et le futur contrôle par configuration lisent **la même règle**.
  Il **ne vérifie pas cette règle** : une erreur de `configuration_from` serait reproduite à
  l'identique partout. La vérification indépendante repose sur les tests synthétiques à valeurs
  explicites (PR #24) et sur le recalcul distinct du contrôle C6.
- **Convention** (fiche §10.1), identique pour M5 et M15 :
  - chaque séance commence par une recherche depuis 07:00 Londres (`début de séance`) ;
  - chaque configuration est suivie jusqu'à sa fin ;
  - une **sortie confirmée** à `D` est comptée comme telle (**pas comme une entrée**) et met fin à
    la configuration ;
  - la recherche reprend avec les M15 qui commencent **à l'instant de fin ou après** : `D` pour une
    sortie confirmée, l'instant de fin pour un abandon, une invalidation ou une expiration ;
  - la séance s'achève quand une recherche ne reconnaît plus d'impulsion jusqu'à 14:15.
- **Aucune position fictive** : l'étude ne suppose ni durée de position, ni entrée, ni refus à `D`.
  Dans le passage de performance, la recherche est suspendue pendant une entrée en attente ou une
  position, puis reprend après sa clôture : la suite des configurations y **dépend des
  exécutions** (§7).

## 4. Conventions de comptage et dénominateurs

### 4.1 Unités

| Unité | Définition | Dénominateur de |
|---|---|---|
| **Séance** | date de Londres, jour ouvré hors 25/12 et 1/1 | recherches, configurations et sorties par séance |
| **Recherche** | une exécution de `configuration_from` depuis un état de reprise | M15 examinées ; configurations ouvertes |
| **M15 examinée** | une clôture `t_j` de 08:00 à 14:15 examinée sans configuration en cours | causes de non-reconnaissance ; impulsions |
| **Configuration** | une impulsion reconnue et son parcours | drapeaux, fins, sorties |
| **Drapeau formé** | une configuration ayant atteint `F` | fins après `F`, sorties confirmées |

Chaque pourcentage nomme son dénominateur. Comptes par année (date de Londres) et au total, par
trajectoire.

### 4.2 Parcours (issues exclusives)

| Étape | Issues terminales | Passe à |
|---|---|---|
| 1. Jours ouvrés de la fenêtre | `pas de séance` (25 décembre, 1er janvier) | séances |
| 2. Recherches d'une séance | une recherche se termine **sans configuration** (dernière de la séance) ou **ouvre une configuration** | configurations |
| 3. M15 examinées d'une recherche | une seule cause, dans l'ordre de la fiche §9 : fenêtre (M15 absente, non `OK` ou avant 07:00) ; ATR H1 non calculable ; puis, par sens, ordre des extrêmes (`o ≥ p`), sommet antérieur (`p < j`), amplitude insuffisante, clôture non forte ; cas ambigu ; **ou** impulsion reconnue (la dernière M15 examinée de la recherche) | impulsions |
| 4. Formation (M15) | données inutilisables pendant le drapeau ; repli trop profond ; impulsion prolongée sans pause ; fin de fenêtre (drapeau non formé à 14:45) | drapeaux formés |
| 5. Sortie (M5 ou M15) | données inutilisables ; repli trop profond (prioritaire sur une sortie de la même bougie) ; consolidation trop longue (expiration à `fin(p) + 90 min`) ; fin de fenêtre (expiration à 15:00) ; **ou sortie confirmée** | sorties confirmées (instants `D`) |

- Les causes « ordre », « sommet antérieur », « amplitude » et « clôture » sont rapportées **par
  sens** ; une M15 non reconnue a une cause pour la hausse et une pour la baisse.
- Une **sortie confirmée** est un instant `D` où le passage de performance évaluera une entrée,
  sous réserve de la suspension de la recherche (§7). Ce n'est ni une entrée décidée, ni une entrée
  exécutée.
- Les **extensions** (nombre par configuration) et la durée de l'impulsion (2 à 6 M15) sont
  décrites, sans être des issues.

### 4.3 Mesures

**Domaine et absences** (précision 4) : chaque mesure nomme les configurations sur lesquelles elle
est définie (configurations, drapeaux formés, sorties confirmées, ventes). Une configuration hors du
domaine (par exemple abandonnée avant `F`, ou formée sans sortie) est comptée **absente avec son
motif** (« configuration terminée avant la formation du drapeau », « pas de sortie confirmée ») :
aucune valeur n'est inventée, aucun cas n'est exclu en silence.

**Calculables sur les bougies seules (rapportées par l'étude)** :

| Mesure | Unité |
|---|---|
| Mesure | Unité | Définie sur |
|---|---|---|
| `A` (ATR H1) | pips | configurations |
| `I`, `I / A` ; durée de l'impulsion à la reconnaissance et finale ; nombre d'extensions | pips, multiples de `A`, M15 | configurations |
| pente du drapeau | multiples de `A` | drapeaux formés |
| **profondeur structurelle sur le bid** : achat `(E − plus bas bid_low) / I`, vente `(plus haut bid_high − E) / I`, sur les pauses et les bougies de sortie lues | fraction de `I` | drapeaux formés |
| **extrême ask du stop à la vente** : plus haut `ask_high` du drapeau, distinct de la profondeur sur le bid | prix | sorties confirmées à la vente |
| délai `D − F`, `D − fin(p)`, heure de `D` à Londres | bougies de l'unité, minutes | sorties confirmées |
| niveaux `S` (bid à l'achat, `ask_high` à la vente) et `T` ; distances structurelles `E − S` et `T − E` (achat ; symétriques à la vente) | pips, multiples de `A` | sorties confirmées |
| **indicateurs approchés, étiquetés comme tels** : `bid_close − S` et `T − bid_close` de la bougie de sortie (achat ; symétriques), « clôture de sortie au-delà de `T` » | pips, compte | sorties confirmées |

**Non calculables ici (passage de performance seulement)** : `P_D` et prix de sortie courant ;
admissibilité du stop ; `P_D − S`, `T − P_D` ; rapports des distances estimés et nets à `D` ; « cible
déjà dépassée à `D` » au sens de la fiche ; taille et refus de taille ; part des coûts fixes ; rapport
obtenu à l'exécution ; issues des entrées et des positions ; résultats.

La clôture d'une bougie est la cotation de son dernier tick valide ; elle devrait correspondre à la
cotation retenue à `D`. **Cette correspondance n'est pas supposée** : le passage de performance
mesurera l'écart entre les indicateurs approchés et les valeurs à `D`.

### 4.4 Descriptions (sans filtre ni réglage)

- par année ; par sens ; en heure d'hiver (GMT), d'été (BST) et pendant les semaines de décalage ;
- configurations et sorties confirmées par séance (0, 1, 2, …) ;
- M15 examinées par heure de `t_j` ; sorties confirmées par heure de `D` ;
- **couverture** (précision 2), en deux parties, à titre descriptif, sans changer le seuil :
  - **nécessaire** à la reconnaissance et à la sortie, de 07:00 à 15:00 : M15 et M5 non `OK` par
    cause (absente, sans tick, ticks invalides seulement, silence de plus de 5 min, sous-créneau M5
    vide, jour férié probable) ;
  - **descriptive de la fenêtre complète** DAY_02, de 07:00 à 17:00 (fiche §4.1) : mêmes comptes,
    plus les silences de plus de 5 min qui la recoupent (nombre, minutes d'ouverture prévue dans la
    fenêtre, séances touchées) ;
  - **source des silences**, sans lire les ticks : les M5 du lot audité à 5 min, dont chaque bougie
    porte l'horodatage de son premier et de son dernier tick valides. Un silence de plus de 5 min ne
    peut pas tenir dans une seule M5 : il sépare toujours le dernier tick valide d'une M5 du premier
    tick valide d'une M5 ultérieure, et se lit donc exactement entre bougies consécutives ayant un
    tick valide. Il est classé comme par le moteur (`classify_silence`, durée exacte puis temps
    d'ouverture prévue ; la fermeture hebdomadaire n'en est pas un). Le rapport historique à 10 min
    ne suffirait pas (silences de 5 à 10 min absents) ; il n'est pas utilisé pour cette mesure.
    Aucune nouvelle lecture n'est nécessaire ;
  - **ATR H1 indisponible** (rétabli le 2026-11-07) : chaque M15 examinée dont l'ATR est
    indisponible reçoit une cause, lue dans l'historique H1 et les états connaissables à `t_j`
    seulement, par un diagnostic qui ne modifie pas le calcul de l'ATR : **amorçage initial**
    (historique trop court depuis le début des données), **H1 prévue absente**, **H1 inutilisable**
    (y compris la dernière H1 connue elle-même inutilisable), ou **non déterminée**, explicite. Aucune
    H1 postérieure à la dernière H1 terminée avant la fenêtre n'est lue.
  - **Compteurs de silences** : `silences distincts` compte chaque silence une seule fois, quel que
    soit le nombre de fenêtres qu'il traverse ; `intersections silence–séance` compte les couples
    (silence, fenêtre de séance) ; s'y ajoutent les minutes d'ouverture prévue dans les fenêtres et
    les séances touchées. Un silence traversant deux fenêtres est **un** silence et **deux**
    intersections.

## 5. Contrôles bloquants

Un écart inexpliqué **arrête l'étude** : résultats masqués (ni comptes, ni distributions, ni détail
écrit), seulement les contrôles, code de sortie 2. L'écart est présenté à l'opérateur avant toute
correction ou relance.

| # | Contrôle | Attendu |
|---|---|---|
| C1 | Séances | jours ouvrés = `pas de séance` + séances ; **1 816** séances, les mêmes jours fériés probables que le bilan DAY_01 (11 jours ouvrés) |
| C2 | Conservation | à chaque étape du §4.2 : entrées = issues terminales + passages, par année et au total ; chaque M15 examinée a une seule cause ; chaque configuration une seule fin ; chaque recherche ouvre au plus une configuration, et seule la dernière d'une séance n'en ouvre pas |
| C3 | **Événements autorisant chaque reprise** | première recherche d'une séance : reprise à 07:00 Londres, motif `début de séance` ; chaque recherche suivante : instant de reprise = instant de fin de la configuration précédente (`D` pour une sortie confirmée) et motif = sa cause de fin ; aucune autre reprise |
| C4 | **Bornes temporelles** (précision 3) | sur les configurations **valides**, distinguées des événements qui les terminent : `t_j` sur la grille M15, dans [08:00, 14:15] Londres, `t_j ≥` reprise arrondie à la M15 supérieure + 60 min ; `o < p = j` à la reconnaissance, relu sur les M15 de la fenêtre ; origine dans la fenêtre ; impulsion d'au plus 6 M15, **sauf** fin « impulsion prolongée sans pause », qui est une issue, jamais un échec : l'abandon a lieu à la **clôture de la première extension** qui porte l'impulsion au-delà de 6 M15, qui peut alors en compter plus de 7 si des pauses ont précédé cette extension ; fin au plus tard à 15:00 ; fin de fenêtre avant `F` à 14:45. **Seulement si `F` existe** : pauses = les deux M15 suivant le dernier sommet, `F` ≤ 14:45, `Δ = min(fin(p) + 90 min, 15:00)`, aucune bougie lue se terminant après `Δ`, expiration exactement à `Δ`. **Seulement si `D` existe** : `F < D ≤ Δ`, `D` sur la grille de l'unité, stop et cible présents |
| C5 | **Aucune bougie réutilisée** | dans une séance et une trajectoire, les M15 de deux configurations (fenêtre d'impulsion, extensions, pauses, et M15 de sortie en comparaison) sont disjointes ; toute M15 d'une fenêtre commence à l'instant de reprise ou après |
| C6 | **Recalcul distinct** | pour la **première configuration de chaque séance**, **séances sans configuration comprises** (les deux doivent n'en trouver aucune) : reconnaissance (`t_j`, sens, `O`, `o`) et formation (`F` avec `E` et `p` finaux, ou cause et instant de la fin avant `F`, impulsion prolongée comprise) recalculées par une implémentation distincte de `configuration_from`, écrite pour ce contrôle sur les M15 lues : 0 différence. Aucun champ postérieur à `F` n'est comparé. Portée : recalcul distinct **de la reconnaissance et de la formation**, avec **ATR H1 partagé** (celui du moteur) ; ce n'est pas une vérification indépendante de l'ATR. Il est distinct du code, pas de la lecture de la fiche par son auteur, et complète les tests synthétiques sans les remplacer |
| C7 | Étapes communes M5 / M15 | pour chaque séance, **sans configuration comprise** : M15 examinées de la première recherche, puis reconnaissance et formation de la première configuration (mêmes champs que C6), identiques entre les deux trajectoires. Les champs fixés après `F` (sortie, `D`, `FL`, stop, cible) sont **exclus** de l'égalité |
| C8 | ATR H1 | `A` lu sur la dernière H1 terminée au plus tard au début de la fenêtre d'impulsion, états connaissables à `t_j` ; aucune H1 de la fenêtre lue |
| C9 | Anti-fuite, entrées et paramètres | 0 tick lu ; aucune bougie lue après le 2022-01-01 ; empreintes **complètes** de M5, M15 et H1 égales aux références du §2 **avant toute lecture** ; empreintes de M5, M15, H1 et du rapport de qualité identiques avant et après ; sur la fenêtre officielle, 383 trous chargés ; paramètres enregistrés dans chaque rapport : `Day02Params()` et `Day02Params(trigger=Trigger.M15)`, seul `trigger` diffère |
| C10 | Provenance | commit et état de l'arbre capturés **au lancement**, arbre propre exigé ; commande enregistrée ; changements pendant le passage contrôlés à part, à la fin : bloquants s'ils touchent le code (`src/`, `pyproject.toml`, `uv.lock`) ou le commit, rapportés sinon |

Aucun nombre de configurations ni de sorties confirmées n'est fixé à l'avance : il n'existe pas de
référence antérieure. Les ancrages sont ceux des contrôles C1 et C9.

## 6. Sorties

- **Hors Git** (`data/`, ADR-014) : rapport agrégé JSON et Markdown, et détail JSONL avec une ligne
  par séance et par trajectoire (recherches, reprises et leurs motifs, M15 examinées par cause,
  configurations : `t_j`, sens, `A`, `O`, `E`, `I`, `o`, `p`, extensions, pauses, `F`, `Δ`, fin et
  instant, `FL`, `S`, `T`, pente, indicateurs approchés), sous
  `data/reports/backtests/day02_availability_2015_2021_<commit>.*`. Le détail n'est écrit que si les
  contrôles passent.
- **Dans Git**, après le passage et sa revue : bilan agrégé
  `docs/experiments/DAY02_AVAILABILITY_2015_2021_BILAN.md`, sans détail par séance au-delà des
  séances citées par les contrôles, avec une méthode de reproduction depuis le détail local.

## 7. Limites du futur rapprochement avec la performance

- **Aucune égalité globale n'est attendue** entre l'étude et le passage de performance, ni pour
  les configurations, ni pour les sorties confirmées, ni pour leurs comptes par cause : une
  configuration de l'étude peut tomber pendant une position du passage de performance ; après la
  clôture de cette position, le passage de performance peut trouver une configuration que l'étude
  n'a pas, parce que l'étude a consommé d'autres bougies. **Aucune inclusion n'est attendue non
  plus.**
- **Comparable à l'identique** : toute configuration qui part d'un même état de reprise, en
  particulier la **première configuration de chaque séance**, sauf si une position d'une séance
  précédente subsiste dans le passage de performance (séances listées).
- **Contrôle prévu dans le passage de performance** (à figer dans son protocole) : chaque
  configuration recalculée sur les bougies depuis l'état de reprise fourni ; ce contrôle ne vérifie
  pas l'instant de reprise, qui sera rapproché séparément de l'événement qui l'autorise (fin de
  configuration, refus à `D`, issue d'une entrée non exécutée, clôture de position au vrai instant
  du tick de sortie).
- Les deux séries seront présentées côte à côte, avec la part des séances concernées, **sans les
  présenter comme un rapprochement exact**.

## 8. Ordre de travail

1. Protocole proposé (ce document), soumis à revue.
2. Outil d'étude (`backtest/day02_availability.py`, commande `forex-day02-availability`) et tests
   synthétiques (`tests/test_day02_availability.py`), dont des parcours faussés volontairement pour
   chaque contrôle : fait, sans passage historique ni lecture des données de recherche.
3. Passage 2015-2021, **sur autorisation explicite**, depuis un arbre propre au commit de l'outil ;
   bilan agrégé soumis à revue :

   ```
   uv run forex-day02-availability \
       --out data/reports/backtests/day02_availability_2015_2021_<commit>.json \
       --details-out data/reports/backtests/day02_availability_2015_2021_<commit>_details.jsonl
   ```

## 9. Limites

- Sans tick, aucune entrée n'est décidée : refus à `D`, expirations, annulations, sorties et
  liquidations ne sont pas comptés ; la suspension de la recherche pendant une position n'est pas
  simulée.
- Les jours fériés probables suivent la convention du calendrier, non confirmée.
- Aucun calendrier d'annonces : la part des impulsions liées à une publication n'est pas mesurable
  (fiche §3.4).
- Les descriptions n'autorisent aucun réglage ; aucune donnée 2022-2025 ; aucun backtest de
  performance ; aucun entraînement ; aucun ordre.
