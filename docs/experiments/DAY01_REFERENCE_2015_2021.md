# Protocole — DAY_01, premier passage de performance 2015-2021 (référence M5, comparaison M15)

**Statut** : principe **approuvé** par l'opérateur le 2026-11-07 (commit `03c6643`), avec trois
précisions intégrées (§5, §6) ; outil `forex-day01-backtest` et tests synthétiques écrits ; **figé
au commit de l'outil** (`3d38ad5`), avant tout lancement. Passages A M5 et M15 faits le 2026-11-07
sur `3d38ad5`, contrôles conformes, aucun passage conditionnel requis ; bilan
`DAY01_REFERENCE_2015_2021_BILAN.md` validé, étape **close** (résultats défavorables, aucune
trajectoire retenue). Les règles ci-dessous restent celles figées avant les passages. Étape 5 de la fiche `docs/strategies/DAY_01_LONDON_RANGE.md`
(§9), après la clôture de l'étude de disponibilité (étape 4, PR #20, bilan
`DAY01_AVAILABILITY_2015_2021_BILAN.md`). Ni validation de performance, ni autorisation de
trading. Aucun paramètre ne sera modifié après lecture des résultats ; un résultat défavorable est
rapporté tel quel.

## 1. Code et données

- **Moteur** : `Day01Backtest` (`backtest/day01_engine.py`, règles `backtest/day01.py`), fusionné
  (PR #19), **inchangé**. Il est construit sur le moteur S1 sans le modifier : le rejeu de
  non-régression S1 n'est refait que si un moteur partagé est modifié.
- **Outil de passage** : `forex-day01-backtest` (`backtest/day01_explore.py`), sur le modèle de
  `forex-s3-backtest`, et `forex-day01-compare` pour la comparaison M5 / M15 (§8). Il n'ajoute que
  de l'observation (parcours, rapprochements, liquidations, drawdown, comparaisons), couverte par des
  tests synthétiques (`tests/test_day01_explore.py`) ; un test vérifie que les transactions, le
  solde, le journal, la courbe et les séances sont ceux du moteur seul. Il ne réévalue aucune règle :
  il lit ce que le moteur a enregistré. La ligne de détail de l'étude de disponibilité est produite
  par une seule fonction (`detail_line`), que les tests utilisent pour le rapprochement. Chaque rapport enregistre la provenance **au lancement**
  (commit, état de l'arbre, commande) ; les changements survenus pendant le passage sont contrôlés
  à part, à la fin (règle C10 de l'étude de disponibilité). Les passages partent d'un arbre propre
  au commit qui fige ce protocole et l'outil.
- **Données**, locales, sans téléchargement, fenêtre bornée ; 2022-2025 jamais lus (refus du
  lecteur hors 2015-2021) :
  - ticks Dukascopy EUR/USD, lecteur en flux ;
  - bougies M5 et M15 du lot clôturé (ADR-021), empreintes SHA-256 de l'étude de disponibilité
    (5m `94387741…fb82`, 15m `64b30520…9db2`), vérifiées avant et après chaque passage ;
  - H4 (`4h.parquet`, `081989d4…7989`) pour l'ATR seulement.
- **Lus seulement, jamais recalculés** :
  - étude de disponibilité : `data/reports/backtests/day01_availability_2015_2021_1c1ed0f_details.jsonl`
    (3 654 lignes, SHA-256 `24111a1d…77c3`, commit `1c1ed0f`) ;
  - références des autres stratégies, pour le chevauchement (§8) : S1
    `s1_ref_2015_2021_h0.json`, S2 `s2_ref_2015_2021_h1_a.json`, S3 `s3_ref_2015_2021_d1h4_a.json`,
    sous `data/reports/backtests/`.

## 2. Fenêtre

Trajectoire **continue** du 2015-01-01T00:00Z inclus au 2022-01-01T00:00Z exclu, sans remise à
zéro annuelle du capital, pour chaque passage. L'ATR H4 s'amorce sur le début de l'historique
(3 séances sans ATR au début de janvier 2015, déjà comptées par l'étude de disponibilité). Une
position encore ouverte à la fin est valorisée au dernier tick, sans sortie inventée, et présentée
à part, avec sa liquidation non exécutée et le silence en cours s'il y en a un (ADR-023).

## 3. Configuration

| Élément | Valeur |
|---|---|
| Paramètres DAY_01 (ADR-022) | `Day01Params()` pour la référence M5, `Day01Params(trigger=Trigger.M15)` pour la comparaison M15 ; aucun autre écart (contrôlé comme C9) |
| Range, cassure, retest | fiche §4 : range [01:00, 08:00) Londres, largeur `0,5 × A ≤ H ≤ 2 × A`, cassure M15 au-delà de `0,1 × A` de 08:15 à 11:00, zone `± 0,1 × A`, délai 60 min, une tentative par séance |
| Entrée | à `D`, au premier tick admissible de `]D, D + 5 min]` ; sinon `ENTRÉE_EXPIRÉE` ; annulation sur interruption connue avant l'exécution |
| Stop | extrême du retest `± 0,25 × A`, **garanti simulé** avec prime, sans distance minimale IG (ASSUMP-008, exécutabilité non validée) |
| Cible | `k = 1,5` depuis `P_D`, sans filtre sur le rapport net ; sortie à la première cotation exécutable qui l'atteint |
| Liquidation | 16:00 Londres, premier tick strictement postérieur ; délai, silence clos et motif rapportés à part (ADR-023) |
| Seuil d'interruption | strictement plus de 5 min d'ouverture prévue, pour les entrées en attente et les positions (ADR-021) ; l'ATR H4 garde ses propres règles |
| Capital initial | 2 000 EUR ; risque 0,25 % des fonds propres estimés à `D` |
| Taille | minimum 0,1 contrat, incrément 0,1 (comme S1 à S3) |
| Coûts (`RESEARCH_COSTS`, scénario non confirmé chez IG) | glissement 0,5 pip ; commission 0 ; conversion 0,5 % ; prime de stop garanti 1,2 USD par contrat ; financement 1 USD par contrat et par nuit, **compté seulement pour une nuit effectivement passée** (`NUIT_NON_PRÉVUE`), estimation de taille intrajournalière sans nuit |
| Latence de publication | 0 |
| Fermetures particulières documentées | aucune (comme S1 à S3) |
| Stop dépassé au premier tick d'exécution | exécutée puis liquidée (référence) ; rejet seulement selon §4 |
| Annonces économiques | aucun filtre (limite de la fiche §3.4) |

## 4. Passages et conditions de déclenchement (fixées à l'avance)

Deux déclenchements, enregistrés à l'avance :
- **Référence : H4 → M15 → M5** (`Trigger.M5`) ;
- **Comparaison : H4 → M15, retest et confirmation sur M15** (`Trigger.M15`). Elle ne remplace pas
  la référence, même si son résultat est meilleur.

Pour **chaque déclenchement**, dans cet ordre, chaque condition étant lue dans le rapport de **son
propre** passage A (`scenario_triggers`) :

1. **A — observé seulement** (`GapScenario.OBSERVED_ONLY`) : toujours lancé.
2. **B — stop d'abord** (`GapScenario.STOP_FIRST`) : lancé si le passage A contient **au moins une
   transaction indéterminée**, c'est-à-dire au moins une interruption inexpliquée (silence
   strictement supérieur à 5 min d'ouverture prévue) pendant une position, enregistrée par le
   moteur (`unobservable_crossings`), **y compris** une position encore ouverte à la fin et une
   liquidation de 16:00 en attente pendant ce silence (fiche §5, point 3). Rapport :
   `scenario_triggers.scenario_b_required`.
   - Ne déclenchent pas B à eux seuls : une fermeture connue (la première cotation après s'applique
     comme une cotation observée) ; une entrée en attente annulée pour interruption
     (`ENTRÉE_ANNULÉE_INTERRUPTION`, aucune position) ; un silence d'exactement 5 min.
3. **C — cible d'abord** (`GapScenario.TARGET_FIRST`) : lancé à la **même condition** que B ; une
   atteinte de la cible y est toujours possible. **Publié seulement s'il diffère de A**
   (transactions ou solde) ; s'il est identique, il est rapporté comme tel, sans être publié comme
   trajectoire distincte (règle de S2).
4. **Rejet à l'exécution** (`StopAtExecution.REJECT`, scénario A) : lancé seulement si le passage A
   contient **au moins une exécution dont le stop est déjà dépassé au premier tick**
   (`STOP_DÉPASSÉ_À_L'EXÉCUTION`). Rapport : `scenario_triggers.reject_required`.

Chaque passage est une trajectoire rejouée en entier. Les conditions de M5 et de M15 sont lues
séparément : un déclenchement de B en M5 ne lance pas B en M15. Aucune autre variante n'est lancée :
ni cible sur niveau prédéfini `RH + H` / `RL − H`, ni deux tentatives, ni filtre d'annonces, ni
autre heure de liquidation, ni sensibilité (fiche §11, protocoles distincts).

## 5. Rapprochement avec l'étude de disponibilité (contrôle avant lecture)

Jusqu'à `D`, le parcours d'une séance ne dépend ni des ticks, ni des positions, ni du scénario
(protocole de disponibilité §3) : une position de la veille n'intervient qu'à `D`. Chaque passage
est donc rapproché, **avant toute lecture des résultats**, de la trajectoire de même
déclenchement de l'étude de disponibilité (JSONL `1c1ed0f`).

**Parcours jusqu'à `D`, séparé de la décision** (précision du 2026-11-07). Le rapprochement porte
sur l'état jusqu'à la confirmation **incluse**. Une confirmation reste classée `CONFIRMATION` pour
ce contrôle même si le moteur refuse ensuite l'entrée à `D` (le moteur remplace alors son
abstention par le motif du refus, pas la confirmation : `D` reste enregistré dans
`Session.retest`). Le refus à `D` et l'issue de l'entrée en attente sont conservés **à part**
(champ `at_d` de chaque séance, §6). Aucune règle n'est réévaluée : les causes avant `D` sont lues
par la classification de l'étude elle-même.

- **Clé** : date de séance de Londres (`day`). Chaque côté doit contenir **exactement 1 827 dates
  distinctes**, une seule ligne par couple (`day`, `trigger`) : un doublon est refusé avant toute
  comparaison.
- **Comparés à l'égalité exacte**, pour chaque date : issue jusqu'à la confirmation (abstention et
  cause, ou confirmation), `RH`, `RL`, `A`, `K`, sens, zone, contact, extrême du retest, dernière
  bougie examinée et `D` (`confirmation_utc`).
- **Attendu** :

  | Déclenchement | Séances attendues | Cassures | Confirmations (`D`) |
  |---|---:|---:|---:|
  | M5 | 1 816 | 1 204 | 831 |
  | M15 | 1 816 | 1 204 | 736 |

  et les mêmes abstentions par cause que le bilan de disponibilité (49 ATR non calculables, 3 ranges
  incomplets, 0 issue de données, 67 largeurs, 493 sans cassure, invalidations et délais du §3 du
  bilan).
- **Tout écart est une anomalie** : le passage est signalé, ses résultats ne sont pas présentés
  (ni transactions, ni parcours, ni journal écrit), seulement les contrôles, et la commande
  s'arrête avec le code 2. L'écart est soumis à l'opérateur avant toute correction ou relance.

Le rapprochement porte sur la même chaîne de code que l'étude (moteur inchangé depuis `1c1ed0f`) :
un changement de moteur entre les deux rendrait le rapprochement non concluant et exigerait une
nouvelle étude de disponibilité, sur autorisation.

## 6. Parcours : des confirmations aux transactions

Pour chaque passage, globalement et par année. **Une confirmation n'est pas une entrée** : chaque
confirmation (831 en M5, 736 en M15) est classée **une seule fois**, d'après la décision et les
événements du moteur ; aucune règle n'est réévaluée par l'outil.

| Étape (dénominateur) | Issue exclusive |
|---|---|
| Confirmations | refus à `D` : position DAY_01 déjà ouverte ; marché fermé à `D` ; absence de cotation à `D` ; stop non admissible ; taille minimale supérieure au budget ; **ou** entrée décidée |
| Entrées décidées | `EXÉCUTÉE` ; `STOP_DÉPASSÉ_À_L'EXÉCUTION` ; `CIBLE_ATTEINTE_À_L'EXÉCUTION` ; `ENTRÉE_REJETÉE` (passage de rejet seulement) ; `ENTRÉE_EXPIRÉE` ; `ENTRÉE_ANNULÉE_INTERRUPTION` |
| Entrées exécutées (`EXÉCUTÉE`, `STOP_DÉPASSÉ_À_L'EXÉCUTION`, `CIBLE_ATTEINTE_À_L'EXÉCUTION`) | sortie liée au stop ; clôturée à la cible ; clôturée par liquidation (`LIQUIDATION_16H`) ; encore ouverte à la fin de l'étude |

**Issues exclusives et annotations** (précision du 2026-11-07) :
- Une entrée **décidée** n'est pas une entrée **exécutée** : `ENTRÉE_REJETÉE`, `ENTRÉE_EXPIRÉE` et
  `ENTRÉE_ANNULÉE_INTERRUPTION` sont décidées, sans transaction. Une entrée exécutée puis sortie sur
  le même tick **reste exécutée**.
- Chaque entrée exécutée a **une seule** issue parmi les quatre ci-dessus, lue dans le motif de
  clôture du moteur, qui est conservé tel quel comme sous-motif. Les sorties immédiates gardent leur
  motif précis et sont comptées une fois :
  - `STOP_FRANCHI_À_L'EXÉCUTION` est rangé dans la famille **« sortie liée au stop »** (libellé
    validé le 2026-11-07, au lieu de « clôturée au stop »), avec son sous-motif distinct. C'est une
    entrée **exécutée puis liquidée au prix observé** du premier tick, le stop étant déjà dépassé :
    **sans garantie de sortie au niveau du stop**, ni prime. Aucun changement d'exécution ;
  - `CIBLE_ATTEINTE_À_L'EXÉCUTION` sous « clôturée à la cible ».

  Les autres motifs du moteur se rangent ainsi : sortie liée au stop pour le stop observé, après
  fermeture connue, après interruption, scénario B ; clôturée à la cible pour la cible, après
  fermeture connue, après interruption, scénario C. Un motif non prévu fait échouer le contrôle.
- **Annotations**, qui recoupent ces issues et ne sont **jamais additionnées** comme des sorties
  distinctes : indéterminée, `NUIT_NON_PRÉVUE`, `LIQUIDATION_APRÈS_INTERRUPTION`, liquidation en
  attente à la fin.

**Contrôles bloquants** (même règle d'arrêt qu'au §5) :
- confirmations = refus à `D` + entrées décidées ; entrées décidées = somme des issues ;
- une seule entrée décidée par séance ; au plus une transaction par entrée décidée ; toute
  transaction issue d'une entrée décidée ; une entrée exécutée a exactement une transaction (y
  compris une entrée exécutée puis sortie sur le même tick) ;
- chaque entrée décidée attestée par un événement du moteur ; sinon anomalie, jamais une
  non-exécution supposée ;
- toute liquidation de 16:00 **résolue** a ses trois grandeurs (délai, silence clos, motif) et la
  transaction qu'elle clôt ; `LIQUIDATION_APRÈS_INTERRUPTION` et `NUIT_NON_PRÉVUE` concordent avec
  le journal du moteur ;
- **liquidation encore en attente à la fin** (précision du 2026-11-07) : situation autorisée, qui
  ne fait pas échouer les contrôles. Sont rapportés l'heure de décision, la durée d'attente jusqu'à
  la borne finale, la position ouverte et le silence en cours ; ni instant de clôture, ni motif de
  sortie, ni cotation ne sont fabriqués. Elle reste prise en compte au §4 : si le silence en cours
  dépasse 5 min d'ouverture prévue, la transaction est indéterminée et déclenche B et C ;
- au plus une position DAY_01 ouverte à tout instant ;
- aucune exécution après 12:05:00 Londres ; aucune décision hors `[K + unité, K + 60 min]` ;
- 0 tick lu hors de la fenêtre ; empreintes des bougies inchangées ; paramètres attendus (C9) ;
  provenance au lancement et changements pendant le passage (C10).

## 7. Rapporté pour chaque passage

- Transactions ; brut, coûts (par poste : glissement, conversion, prime de stop garanti,
  financement d'une nuit non prévue), net ; sorties par motif ; globalement et par année (par
  année de sortie) ; position ouverte à la fin, à part.
- **Liquidations de 16:00** : nombre ; délai après 16:00 (distribution) ; silence clos (durée,
  nature) ; motif de clôture ; liquidations après interruption ; nuits non prévues ; liquidation
  non exécutée à la fin de l'étude.
- **Entrées non exécutées** : expirées, annulées pour interruption (avec la durée du silence),
  rejetées (passage de rejet).
- **Mesures par entrée**, dans le détail local par séance (hors Git, champ `measures`), et en
  distribution dans le rapport agrégé ; aucune ne sert de filtre :
  - les **trois rapports côte à côte** : distances estimées à `D` (`k = 1,5` par construction),
    net estimé à `D` (formule de S2, sans nuit : gain net à la cible depuis la cotation de `D`,
    glissement, commission et conversion compris, divisé par la perte estimée au stop par contrat
    de l'ordre), obtenu à l'exécution (`(T − prix exécuté) / (prix exécuté − S)` à l'achat) ;
  - la **distance du stop** `|P_D − S|`, en pips et en multiples de `A` (ATR H4 figé) ;
  - la **part des coûts fixes dans le risque** : (glissement + commission + prime de stop garanti)
    par contrat, en USD, divisés par la perte estimée au stop par contrat en USD à la cotation de
    dimensionnement (écart, glissement, commission et prime compris ; conversion exclue, car
    proportionnelle).

  Les deux rapports estimés portent sur les entrées décidées ; le rapport obtenu et la part des
  coûts fixes sur les entrées exécutées. Une mesure non définissable est **absente, avec son
  motif** (par exemple : entrée non exécutée ; stop déjà dépassé au prix exécuté, risque non
  positif), jamais remplacée ; le rapport agrégé compte les absences par motif.
- **Répartitions** : par jour de la semaine ; par heure d'entrée (Londres) ; en heure d'hiver
  (GMT), d'été (BST) et pendant les semaines de décalage ; par sens.
- Drawdown au tick en euros : **global, continu** depuis 2 000 € ; **par année**, sommet
  initialisé aux fonds propres du premier tick de l'année ; drawdown relatif maximal au tick ;
  premier franchissement éventuel de 6 % (seuil de revue, la trajectoire continue) ; durée de
  récupération.
- Net sans la meilleure transaction ; transactions indéterminées (trou, cotations qui
  l'encadrent, distance au stop et à la cible) ; dépassements du budget.
- Mesures du cahier (§9) : espérance nette en multiples du risque, profit factor, gain et perte
  moyens, durée d'exposition, mois sans opération et mois déficitaires.

## 8. Comparaisons

**M5 / M15**, rapprochées par date de séance de Londres (`forex-day01-compare`, depuis les deux
détails locaux d'un même scénario ; doublons refusés, mêmes dates exigées). Une ligne par date,
dans la sortie locale (hors Git) : issue de chaque trajectoire, confirmée ou non, exécutée ou non,
et, pour les séances exécutées dans les deux, les écarts M15 − M5 d'instant d'entrée, de stop, de
taille et de résultat. Toutes les synthèses sont calculées depuis ces lignes : confirmations
communes et propres à chaque trajectoire (attendu, d'après le bilan de disponibilité : 724
communes, 107 propres à M5, 12 propres à M15), exécutions communes et propres, différences de
parcours, distribution des écarts d'entrée, stops et tailles identiques, nets des séances communes
clôturées. Parcours, transactions, net et drawdown sont aussi présentés côte à côte. La comparaison
ne remplace pas la référence.

**Avec S1, S2 et S3** (références lues au §1), description seulement :
- chevauchement des positions dans le temps (même sens, sens opposé) ;
- **pertes simultanées** : transactions DAY_01 perdantes qui chevauchent une transaction perdante
  d'une autre référence ;
- nets annuels réalisés côte à côte, pour les sept années 2015 à 2021 (net de 0 € une année sans
  clôture).

Ces chevauchements décrivent des trajectoires **indépendantes**, chacune avec son propre capital.
Ils ne constituent pas l'évaluation d'un portefeuille partagé : celui-ci devrait simuler
conjointement les décisions, le capital et le risque global, ce qui n'est pas fait ici.

## 9. Lecture des résultats (fiche §9, règles de S2 et S3)

1. Un net strictement positif dans chaque scénario publié est un résultat favorable sur la
   période de développement, sans plus. Un signe différent entre A et B (ou A et C) signifie que
   le résultat dépend des trous de cotation.
2. Le net sans la meilleure transaction est un indicateur, pas un motif automatique de rejet ;
   6 % de drawdown relatif est un seuil de revue.
3. Si les pertes DAY_01 sont surtout simultanées à des pertes S1, S2 ou S3, la conclusion est que
   DAY_01 diversifie peu, quel que soit son net. Aucun seuil automatique n'est fixé.
4. Avec peu de transactions, aucune conclusion statistique.
5. Les stops courts sont simulés comme garantis sans minimum IG confirmé : un résultat favorable
   ne dit rien de leur exécutabilité (ASSUMP-008), à traiter avant tout paper trading.
6. Aucun filtre d'annonces : la part des séances touchées par une annonce n'est pas mesurable sans
   calendrier historique (fiche §3.4) ; c'est une limite, pas une mesure.

## 10. Commandes (figées ; exécutées le 2026-11-07, voir le bilan §1)

Préfixe des sorties : `data/reports/backtests/day01_ref_2015_2021_<déclenchement>_<passage>` (hors
Git), avec `<déclenchement>` = `m5` ou `m15` et `<passage>` = `a`, `b`, `c` ou `a_reject`.

```
uv run forex-day01-backtest --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 \
  --trigger M5 --scenario A \
  --availability data/reports/backtests/day01_availability_2015_2021_1c1ed0f_details.jsonl \
  --s1-reference data/reports/backtests/s1_ref_2015_2021_h0.json \
  --s2-reference data/reports/backtests/s2_ref_2015_2021_h1_a.json \
  --s3-reference data/reports/backtests/s3_ref_2015_2021_d1h4_a.json \
  --out data/reports/backtests/day01_ref_2015_2021_m5_a.json \
  --sessions-out data/reports/backtests/day01_ref_2015_2021_m5_a_sessions.jsonl
```

La fenêtre officielle (`--init-start`, `--start` 2015-01-01, `--end` 2022-01-01) est la valeur par
défaut ; elle active les ancrages du §5 (3 654 lignes, 1 827 dates, 831 et 736 confirmations). Le
rapport JSON a un résumé Markdown (même nom, `.md`) ; le détail par séance n'est écrit que si les
contrôles passent.

Ordre prévu :
1. `m5_a` (ci-dessus) ;
2. `m15_a` : même commande avec `--trigger M15`, sorties `day01_ref_2015_2021_m15_a*` ;
3. pour chaque déclenchement, selon `scenario_triggers` de son passage A : `--scenario B` puis
   `--scenario C` (sorties `*_b*`, `*_c*`) si `scenario_b_required` ; puis
   `--stop-at-execution REJECT` (sorties `*_a_reject*`) si `reject_required` ;
4. comparaison M5 / M15 de chaque scénario publié, depuis les deux détails locaux :
   `uv run forex-day01-compare --m5 <..._m5_a_sessions.jsonl> --m15 <..._m15_a_sessions.jsonl> --out <...>`.

Chaque commande part d'un arbre propre au commit qui fige ce protocole et l'outil ; un passage dont
un contrôle échoue (code 2) arrête la suite et est présenté avant toute correction.

Bilan agrégé : `DAY01_REFERENCE_2015_2021_BILAN.md` dans ce dossier (passages A M5 et M15 seuls,
B, C et rejet non requis) ; journaux et détails par séance hors Git.

## 11. Ordre de travail

1. Protocole soumis à l'opérateur ; principe approuvé le 2026-11-07 (`03c6643`).
2. Outil `forex-day01-backtest` et tests synthétiques, sans passage historique : fait ; protocole
   figé au commit de l'outil.
3. Passages 2015-2021, **sur autorisation explicite** (2026-11-07), dans l'ordre du §10 : fait ;
   bilan agrégé revu et validé, décision consignée au §13 du bilan.

## 12. Interdits

Aucune donnée 2022-2025 ; aucun réglage après lecture des résultats ; aucune variante non
enregistrée ici ; aucun entraînement ; aucun ordre, même en démo ; le sélecteur IA n'est pas
concerné ; aucun détail par séance publié.
