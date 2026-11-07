# DAY_02 — Disponibilité des données, développement 2015-2021 (protocole)

**Statut** : protocole **proposé** le 2026-11-07, documentation seulement (ADR-030). Fiche figée
`docs/strategies/DAY_02_FLAG_CONTINUATION.md` (ADR-028), §10.1. Ni outil, ni passage : l'outil
d'étude et ses tests seront écrits après approbation, puis le passage lancé sur autorisation
explicite. Cette étude ne lit aucun tick et ne produit ni entrée, ni transaction, ni gain ou perte.
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
- **H1 et trous** : `data/bars/dukascopy/EURUSD/1h.parquet`, empreinte vérifiée avant lecture
  (`a7c7f8b8…`, bilan des données), et trous du rapport de qualité (`load_gaps`). Les états H1
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

**Calculables sur les bougies seules (rapportées par l'étude)** :

| Mesure | Unité |
|---|---|
| `A` (ATR H1) | pips |
| `I`, `I / A` ; durée de l'impulsion ; nombre d'extensions | pips, multiples de `A`, M15 |
| nombre de bougies de pause, pente du drapeau | M15, multiples de `A` |
| profondeur `(E − FL) / I` (achat ; symétrique à la vente) | fraction de `I` |
| délai `D − F`, `D − fin(p)`, heure de `D` à Londres | bougies de l'unité, minutes |
| niveaux `S` (bid à l'achat, `ask_high` à la vente) et `T` | prix |
| distances structurelles `E − S` et `T − E` (achat ; symétriques à la vente) | pips, multiples de `A` |
| **indicateurs approchés, étiquetés comme tels** : `bid_close − S` et `T − bid_close` de la bougie de sortie (achat ; symétriques), « clôture de sortie au-delà de `T` » | pips, multiples de `A`, compte |

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
- **couverture de la fenêtre propre** : part des M15 de 07:00 à 15:00 et des M5 de 08:00 à 15:00
  non `OK`, par cause (absente, silence, sous-créneau vide), et silences de plus de 5 min dans cette
  fenêtre, à titre descriptif, sans changer le seuil (fiche §4.1) ; H1 non utilisables et ATR
  indisponibles, par cause (amorçage, H1 prévue absente, H1 inutilisable).

## 5. Contrôles bloquants

Un écart inexpliqué **arrête l'étude** : résultats masqués (ni comptes, ni distributions, ni détail
écrit), seulement les contrôles, code de sortie 2. L'écart est présenté à l'opérateur avant toute
correction ou relance.

| # | Contrôle | Attendu |
|---|---|---|
| C1 | Séances | jours ouvrés = `pas de séance` + séances ; **1 816** séances, les mêmes jours fériés probables que le bilan DAY_01 (11 jours ouvrés) |
| C2 | Conservation | à chaque étape du §4.2 : entrées = issues terminales + passages, par année et au total ; chaque M15 examinée a une seule cause ; chaque configuration une seule fin ; chaque recherche ouvre au plus une configuration, et seule la dernière d'une séance n'en ouvre pas |
| C3 | **Événements autorisant chaque reprise** | première recherche d'une séance : reprise à 07:00 Londres, motif `début de séance` ; chaque recherche suivante : instant de reprise = instant de fin de la configuration précédente (`D` pour une sortie confirmée) et motif = sa cause de fin ; aucune autre reprise |
| C4 | **Bornes temporelles** | `t_j` sur la grille M15, dans [08:00, 14:15] Londres, `t_j ≥` reprise arrondie à la M15 supérieure + 60 min ; `o < p = j` à la reconnaissance ; impulsion de 2 à 4 M15 à la reconnaissance, au plus 6 ; `F` = fin de la 2e bougie de pause après le dernier sommet, `F ≤ 14:45` ; `Δ = min(fin(p) + 90 min, 15:00)` ; `F < D ≤ Δ`, `D` sur la grille de l'unité ; expiration exactement à `Δ` ; aucune bougie lue se terminant après `Δ` |
| C5 | **Aucune bougie réutilisée** | dans une séance et une trajectoire, les M15 de deux configurations (fenêtre d'impulsion, extensions, pauses, et M15 de sortie en comparaison) sont disjointes ; toute M15 d'une fenêtre commence à l'instant de reprise ou après |
| C6 | **Recalcul distinct** | pour la **première configuration de chaque séance**, la reconnaissance (`t_j`, sens, `O`, `E`, `o`, `p`) et la formation (`F` ou cause de fin) recalculées par une implémentation distincte de `configuration_from`, écrite pour ce contrôle directement sur les tables parquet : 0 différence. Ce recalcul est distinct du code, pas de la lecture de la fiche par son auteur ; il complète les tests synthétiques sans les remplacer |
| C7 | Étapes communes M5 / M15 | pour la première configuration de chaque séance : recherche, M15 examinées, reconnaissance et formation identiques champ par champ entre les deux trajectoires (elles ne divergent qu'à partir de `F`) |
| C8 | ATR H1 | `A` lu sur la dernière H1 terminée au plus tard au début de la fenêtre d'impulsion, états connaissables à `t_j` ; aucune H1 de la fenêtre lue |
| C9 | Anti-fuite, entrées et paramètres | 0 tick lu ; aucune bougie lue après le 2022-01-01 ; empreintes M5, M15 et H1 égales à celles de l'audit **avant toute lecture**, identiques avant et après ; paramètres enregistrés dans chaque rapport : `Day02Params()` et `Day02Params(trigger=Trigger.M15)`, seul `trigger` diffère |
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
2. Après approbation : outil d'étude (`backtest/day02_availability.py`, commande à nommer) et tests
   synthétiques, dont les contrôles C1 à C10 faussés volontairement, sans passage historique.
3. Passage 2015-2021, **sur autorisation explicite**, depuis un arbre propre au commit de l'outil ;
   bilan agrégé soumis à revue.

## 9. Limites

- Sans tick, aucune entrée n'est décidée : refus à `D`, expirations, annulations, sorties et
  liquidations ne sont pas comptés ; la suspension de la recherche pendant une position n'est pas
  simulée.
- Les jours fériés probables suivent la convention du calendrier, non confirmée.
- Aucun calendrier d'annonces : la part des impulsions liées à une publication n'est pas mesurable
  (fiche §3.4).
- Les descriptions n'autorisent aucun réglage ; aucune donnée 2022-2025 ; aucun backtest de
  performance ; aucun entraînement ; aucun ordre.
