# DAY_01 — Disponibilité des données, développement 2015-2021 (protocole)

**Statut** : protocole **approuvé dans son principe** par l'opérateur le 2026-11-06, avec deux
précisions intégrées (§3, C9) ; outil et tests synthétiques prêts, **aucun lancement historique**
(fiche `docs/strategies/DAY_01_LONDON_RANGE.md` §9, étape 4). Ni outil lancé, ni donnée lue à ce
stade. Cette étude ne produit ni transaction, ni gain ou perte, ni drawdown. Ce n'est ni une
validation de performance, ni une autorisation de trading.

## 1. Objet

Compter, séance par séance, ce que DAY_01 voit **jusqu'à la confirmation incluse**, sans exécution :
séances attendues, ranges complets, ranges admissibles, cassures, retests et confirmations. Deux
trajectoires de lecture :

- **référence** : H4 → M15 → M5 (`Trigger.M5`) ;
- **comparaison préenregistrée** : « H4 → M15, retest et confirmation sur M15 » (`Trigger.M15`).

Les étapes jusqu'à la cassure sont communes aux deux ; seuls le retest, l'invalidation et la
confirmation diffèrent.

## 2. Règles, paramètres et données

- **Règles et paramètres** : ceux de la fiche figée (ADR-022), des conventions de données de
  l'ADR-021 et des libellés de l'ADR-023, **sans modification** (`Day01Params()` par défaut :
  range [01:00, 08:00) Londres, gel à 08:00, cassures de 08:15 à 11:00, marges `0,1 × A`, largeur
  `0,5 ≤ H / A ≤ 2`, délai de retest 60 min, ATR Wilder 14 H4). Aucune grille, aucun réglage :
  les distributions décrites ici ne servent à modifier aucun paramètre.
- **Bougies M5 et M15** : `data/bars/dukascopy/EURUSD/intraday_2015_2021_day01_5min/`,
  convention DAY_01 (silence > 5 min, M5 sans tick et M15 à sous-créneau vide non `OK`). Empreintes
  vérifiées **avant lecture** : `5m` `94387741…`, `15m` `64b30520…` (bilan des données §8.1). Toute
  différence arrête l'étude.
- **H4 et trous** : bougies H4 locales et trous du rapport de qualité, chargés comme pour S2 et S3
  (`load_bars`, `load_gaps`). L'état des H4 et l'ATR gardent leurs propres règles (seuil
  `ResearchConfig`, continuité des H4 prévues, ADR-021). Empreinte H4 enregistrée.
- **Aucun tick lu.** Les contrôles à `D` (position ouverte, marché, cotation, stop admissible,
  cible, taille) et tout ce qui suit relèvent de l'étape de performance.
- **Fenêtre** : séances dont le début du range tombe dans [2015-01-01, 2022-01-01) ; H4 lues
  depuis le 2015-01-01 (l'amorçage de l'ATR est compté dans la période). La fenêtre est contrôlée
  par `require_development_window` : **2022-2025 reste en réserve**, aucune lecture.

## 3. Méthode : le moteur, arrêté à la confirmation

- **Moteur réutilisé** : l'outil (`backtest/day01_availability.py`, `forex-day01-availability`)
  exécute `Day01Backtest` avec un flux de ticks vide. Une sous-classe d'étude remplace seulement la
  décision d'entrée : à la confirmation, elle enregistre l'instant `D` et n'évalue rien d'autre
  (ni position, ni cotation, ni stop, ni cible, ni taille, ni entrée en attente). Comme pour S2 et
  S3, les séances comptées sont exactement celles que verra le moteur de performance.
- **Observation du retest dans le moteur** (ajout du 2026-11-06, approuvé par l'opérateur) : le
  moteur renseigne `Session.retest` **dès le début du retest** et le met à jour à chaque bougie lue,
  au lieu de ne l'écrire qu'à la fin. Il conserve ainsi, quelle que soit l'issue (données
  inutilisables, invalidation, délai dépassé, confirmation) :
  - l'unité de déclenchement et la zone ;
  - l'instant du contact, s'il a eu lieu, et l'extrême du retest depuis ce contact ;
  - le début de la dernière bougie examinée (`last_examined_utc`).

  Ce sont des métadonnées d'observation : elles ne modifient ni les décisions ni les règles. Les
  tests du moteur existants passent sans modification. L'ordre existant est conservé : sur une
  bougie, l'invalidation est examinée **avant** la reconnaissance d'un nouveau contact. Une bougie
  qui recoupe la zone mais clôture au-delà de `Z_b` (achat) est donc une **invalidation avant
  contact**.
- **Aucune copie des règles du retest** dans l'outil : il lit l'abstention du moteur et
  `Session.retest` pour classer chaque séance (§4.2). Seuls le range et la cassure sont
  **recalculés indépendamment** (contrôle C6), et les invariants du retest sont vérifiés (C7, C8).
- **Indépendance vis-à-vis des ticks et des positions** : jusqu'à `D`, le parcours d'une séance ne
  lit que les bougies M15/M5 et l'ATR H4 ; il est consommé par la première cassure, quelle que soit
  l'issue (une tentative par séance, §4.6). Une position de la veille n'intervient qu'à `D`
  (§4.7) : elle n'a donc aucun effet sur ces comptes.
- **Deux trajectoires**, sur les mêmes entrées et le même commit : `Day01Params()` (référence M5) et
  `Day01Params(trigger=Trigger.M15)` (comparaison M15).
- **Cause de l'ATR non calculable** : « amorçage » tant qu'aucune séance antérieure de l'étude n'a
  eu d'ATR, « interruption » de la continuité des H4 ensuite.
- **Résultats masqués** sur tout contrôle en échec : le rapport ne garde que les contrôles et la
  provenance, sans entonnoir, descriptions ni détail ; code de sortie 2.

## 4. Conventions de comptage

### 4.1 Unité et dénominateurs

- **Unité** : la **séance** (date de Londres, jour ouvré). Chaque séance a **une seule issue
  terminale** par trajectoire, la première raison bloquante dans l'ordre de la fiche §8.
- Chaque pourcentage nomme son dénominateur : séances attendues, ranges complets, ranges
  admissibles, cassures. Les comptes sont donnés **par année** (année de la date de Londres) et au
  total.

### 4.2 Entonnoir (issues exclusives, dans l'ordre)

| Étape | Issues terminales | Passe à l'étape suivante |
|---|---|---|
| 1. Jours ouvrés de la fenêtre | `pas de séance` (marché non ouvert sur toute la fenêtre du range : jour férié probable ou fermeture) | séances attendues |
| 2. Range | `range incomplet` (première M15 non `OK`, avec sa cause : absente, silence, sous-créneau vide, les deux) | ranges complets |
| 3. ATR au gel | `ATR H4 non calculable`, avec sa cause (amorçage, ou interruption de la continuité des H4) | ranges avec ATR |
| 4. Largeur | `range hors largeur admissible`, **séparé en trop étroit** (`H / A < 0,5`) **et trop large** (`H / A > 2`) | ranges admissibles |
| 5. Cassure | `données inutilisables pendant la recherche de cassure` (M15 en cause) ; `aucune cassure confirmée à 11:00` | cassures (achat, vente) |
| 6. Retest, par trajectoire | `données inutilisables pendant le retest` ; `invalidation`, séparée **avant contact** et **après contact** ; `délai de retest dépassé`, séparé **sans contact** et **contact sans confirmation** | **confirmations** |

- Les étapes 1 à 5 sont **identiques** pour les deux trajectoires (contrôle C5).
- Une **confirmation** est un instant `D` où le moteur de performance évaluera une entrée. Ce
  n'est ni une entrée exécutée, ni une décision acceptée : les refus à `D` (position ouverte,
  cotation, stop, taille) et les issues de l'entrée en attente ne sont pas évalués ici.

### 4.3 Descriptions rapportées (sans filtre ni réglage)

- **Séances** : par année ; par heure d'hiver (GMT) ou d'été (BST) ; et pendant les semaines de
  décalage entre Londres et New York (mars, octobre-novembre).
- **Ranges** : distribution de `H / A` (quartiles, minimum, maximum) des ranges avec ATR, et de `A`
  en pips.
- **Cassures** : par sens ; par M15 de cassure (12 créneaux, `K` de 08:15 à 11:00 Londres).
- **Retests et confirmations**, par trajectoire et par sens :
  - délai `D − K`, en nombre de bougies (M5 : 1 à 12 ; M15 : 1 à 4) ;
  - confirmation sur la bougie du contact ou sur une bougie postérieure ;
  - heure de `D` à Londres (au plus 12:00) ;
  - écart entre l'extrême du retest et la borne cassée, en unités de `A` (descriptif du futur stop,
    sans prix d'entrée ni taille).

## 5. Rapprochements prévus (bloquants)

Un écart inexpliqué à l'un de ces contrôles **arrête l'étude** : résultats masqués, code de sortie
2, écart rapporté sans interprétation.

| # | Contrôle | Attendu |
|---|---|---|
| C1 | Jours ouvrés = `pas de séance` + séances attendues | séances attendues = **1 816** (bilan des données §8.3) ; les jours sans séance sont les jours fériés probables de la convention (25 décembre, 1er janvier) |
| C2 | Ranges incomplets | **3** séances : 2015-11-10 (silence et sous-créneau vide), 2017-01-02 et 2021-10-12 (silence seul), conformes au bilan §8.3 |
| C3 | Conservation de l'entonnoir | à chaque étape, entrées = issues terminales + passages, par année et au total ; chaque séance a exactement une issue par trajectoire |
| C4 | Données inutilisables pendant la cassure et le retest | **0** dans les deux trajectoires : aucune M5 ni M15 non `OK` en 08-12 (bilan §8.2, §8.3) |
| C5 | Étapes communes | M5 et M15 identiques séance par séance, champ par champ : issue des étapes 1 à 5, `RH`, `RL`, `A`, `H / A`, `K`, sens |
| C6 | Recalcul indépendant du range et de la cassure | `RH`, `RL` (28 M15) et première clôture de cassure recalculés directement sur les fichiers parquet, par une requête distincte du moteur : 0 différence |
| C7 | Bornes temporelles | gel à 08:00 UTC en GMT et 07:00 UTC en BST ; `K` sur la grille M15 dans [08:15, 11:00] Londres ; `D − K` multiple de l'unité, dans [5, 60] min (M5) ou [15, 60] min (M15) ; `D` ≤ 12:00 Londres |
| C8 | Cohérence du retest | contact au plus tard sur la bougie de confirmation ; extrême lu sur les bougies du contact à la confirmation incluses ; aucune bougie lue au-delà de `K + 60 min` |
| C9 | Anti-fuite, entrées et paramètres | 0 tick lu ; aucune bougie lue après le 2022-01-01 ; empreintes M5 et M15 égales à celles de l'audit **avant toute lecture**, et M5, M15 et H4 identiques avant et après ; paramètres enregistrés dans chaque rapport : référence M5 = `Day01Params()`, comparaison M15 = `Day01Params(trigger=Trigger.M15)`, **tous les autres paramètres identiques** entre les deux |
| C10 | Provenance | commit et état de l'arbre capturés **au lancement**, arbre propre exigé ; changements survenus pendant le passage contrôlés à part, à la fin : bloquants s'ils touchent le code (`src/`, `pyproject.toml`, `uv.lock`) ou le commit, rapportés sinon |

**Rapprochement avec l'étape de performance** (à reprendre dans son protocole, comme pour S3) : sur
la même fenêtre et les mêmes données, le moteur de performance devra reproduire, séance par séance,
les issues des étapes 1 à 6 et les mêmes instants `D`. Le nombre de confirmations sera le maximum
des entrées évaluées, avant les refus à `D`.

## 6. Sorties

- **Hors Git** (`data/`, ADR-014) : rapport agrégé JSON et Markdown, et détail JSONL avec une ligne
  par séance et par trajectoire (issue, cause, `RH`, `RL`, `A`, `K`, contact, `D`, extrême), sous
  `data/reports/backtests/day01_availability_2015_2021_<commit>.*`.
- **Dans Git**, après le passage et sa revue : bilan agrégé
  `docs/experiments/DAY01_AVAILABILITY_2015_2021_BILAN.md`, sans détail par séance au-delà des
  séances citées par les contrôles.

## 7. Ordre de travail

1. Protocole approuvé dans son principe (2026-11-06), précisions intégrées.
2. Outil d'étude (`backtest/day01_availability.py`, commande `forex-day01-availability`) et tests
   synthétiques (`tests/test_day01_availability.py`, observation du retest dans
   `tests/test_day01.py`) : fait, sans passage historique.
3. Passage 2015-2021, **sur autorisation explicite**, puis bilan agrégé soumis à revue :

   ```
   uv run forex-day01-availability \
       --out data/reports/backtests/day01_availability_2015_2021_<commit>.json \
       --details-out data/reports/backtests/day01_availability_2015_2021_<commit>_details.jsonl
   ```

## 8. Limites

- Sans tick, aucune entrée n'est décidée : les refus à `D`, les expirations, les annulations pour
  interruption et les liquidations ne sont pas comptés.
- Les jours fériés probables (25 décembre, 1er janvier) suivent la convention du calendrier, non
  confirmée.
- Les descriptions du §4.3 n'autorisent aucun réglage : les paramètres restent ceux de la fiche
  figée.
- Aucune donnée 2022-2025 lue ; aucun backtest de performance ; aucun entraînement ; aucun ordre.
