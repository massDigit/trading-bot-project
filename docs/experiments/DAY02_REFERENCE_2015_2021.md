# Protocole — DAY_02, premier passage de performance 2015-2021 (référence M5, comparaison M15)

**Statut** : base **approuvée** par l'opérateur le 2026-11-07, trois précisions intégrées (reprises
§5.2, entonnoir §6, comparaisons entre scénarios §8) et deux choix retenus (franchissements
journaliers et hebdomadaires non décrits, §7 ; recalcul distinct C6 sur toutes les tentatives, §5.1)
(ADR-034). Outil `forex-day02-backtest` et `forex-day02-compare` et tests synthétiques écrits ;
revue de f705858 : deux corrections intégrées (écart entre indicateur approché et valeur à `D`,
§7 ; rattachement des détails par séance à leur rapport, §8) ; **figé au commit de ces
corrections**, soumis à revue. Aucun passage historique. Étape 6 de la fiche figée `docs/strategies/DAY_02_FLAG_CONTINUATION.md` (§10,
ADR-028), après la clôture de l'étude de disponibilité (étape 5, PR #25, bilan
`DAY02_AVAILABILITY_2015_2021_BILAN.md`, ADR-033). Ni validation de performance, ni autorisation de
trading. **Les passages restent subordonnés à la décision de l'opérateur sur les conditions IG
(§10)**. Aucun paramètre ne sera modifié après lecture des résultats ; un résultat défavorable est
rapporté tel quel.

## 1. Code et données

- **Moteur** : `Day02Backtest` (`backtest/day02_engine.py`, règles `backtest/day02.py`), fusionné
  (PR #24), **inchangé**. Il est construit sur le moteur S1 sans le modifier : le rejeu de
  non-régression S1 n'est refait que si un moteur partagé est modifié.
- **Outil de passage** : `forex-day02-backtest` (`backtest/day02_explore.py`) et
  `forex-day02-compare` (§8), sur le modèle de `forex-day01-backtest`, tests synthétiques
  `tests/test_day02_explore.py`. Il n'ajoute que de l'observation : il lit les tentatives
  (`Attempt`), clôtures (`Closing`), transactions et annotations enregistrées par le moteur, sans
  réévaluer de règle, sauf le recalcul de contrôle du §5 sur les seules bougies. Un test vérifie que
  transactions, solde, journal, courbe, tentatives et clôtures sont ceux du moteur seul. Le recalcul
  distinct C6 de l'étude (`independent_first`) reçoit un instant de reprise facultatif, qui vaut
  07:00 par défaut : le comportement de l'étude est inchangé (ses tests passent sans modification). Provenance au lancement (commit, état de l'arbre, commande) et changements
  pendant le passage contrôlés à la fin (règle C10 de l'étude de disponibilité). Les passages
  partent d'un arbre propre au commit qui fige ce protocole et l'outil.
- **Données**, locales, sans téléchargement, fenêtre bornée ; 2022-2025 jamais lus (refus du
  lecteur hors 2015-2021) :
  - ticks Dukascopy EUR/USD, lecteur en flux ;
  - bougies M5 et M15 du lot clôturé (ADR-021) et H1 pour l'ATR seulement ; empreintes complètes de
    l'étude de disponibilité (5m `9438774154972aafa2cc924cf6042e6ae2b3c97de23328644b7d54f3af50fb82`,
    15m `64b305201c2f8e48afd257048e07800cea1778e17228673b4c4af7c6a86a9db2`, 1h
    `a7c7f8b82ac55828bbbc25b8fd87c64cac99efb5a977187c47b381480802c585`), vérifiées avant et après
    chaque passage ;
  - rapport de qualité (trous) : empreinte enregistrée avant et après, sans référence historique ;
    ancrage par le nombre, 383 trous jusqu'au 2022-01-01 (contrôle de nombre, pas preuve
    d'identité, comme au bilan de disponibilité §1).
- **Lus seulement, jamais recalculés** :
  - étude de disponibilité : `data/reports/backtests/day02_availability_2015_2021_eb48d6c_details.jsonl`
    (3 632 lignes, SHA-256 `775e4bba4a6492af4f054a415ff75cb3c125c5aa1fd9f46ee33dfd0efba69ddc`,
    commit `eb48d6c`), empreinte vérifiée avant usage ;
  - références des autres stratégies, pour le chevauchement (§8) : S1 `s1_ref_2015_2021_h0.json`,
    S2 `s2_ref_2015_2021_h1_a.json`, S3 `s3_ref_2015_2021_d1h4_a.json`, DAY_01 M5
    `day01_ref_2015_2021_m5_a.json`, sous `data/reports/backtests/`.

## 2. Fenêtre

Trajectoire **continue** du 2015-01-01T00:00Z inclus au 2022-01-01T00:00Z exclu, sans remise à
zéro annuelle du capital, pour chaque passage. L'ATR H1 s'amorce sur le début de l'historique (une
séance touchée, le 2015-01-02, déjà comptée par l'étude). Séances attendues : 1 816 (1 827 jours
ouvrés, 11 exclusions). Une position encore ouverte à la fin est valorisée au dernier tick, sans
sortie inventée, et présentée à part, avec sa clôture non exécutée et le silence en cours s'il y en
a un.

## 3. Configuration

| Élément | Valeur |
|---|---|
| Paramètres DAY_02 (ADR-028) | `Day02Params()` pour la référence M5, `Day02Params(trigger=Trigger.M15)` pour la comparaison M15 ; aucun autre écart (contrôlé comme C9) |
| Impulsion, drapeau, sortie | fiche §5 : ATR Wilder 14 H1, impulsion de 4 M15 glissantes depuis 07:00, `o < p = j`, `bid_close − O ≥ 1,5 × A`, clôture forte ; reconnaissance de 08:00 à 14:15 ; profondeur `E − 0,5 × I` prioritaire ; 2 pauses, `F ≤ 14:45` ; sortie au-delà de `E + 0,1 × A`, échéance `Δ = min(fin(p) + 90 min, 15:00)` incluse |
| Décision à `D` | fiche §5.6 : cotation à `D`, stop admissible, cible du bon côté, taille ; aucun blocage journalier ou hebdomadaire (ADR-027) |
| Entrée | au premier tick admissible de `]D, D + 5 min]` ; sinon `ENTRÉE_EXPIRÉE` ; annulation sur interruption connue (`ENTRÉE_ANNULÉE_INTERRUPTION`) ; aucune exécution après 15:05 |
| Stop | `FL − 0,25 × A` (vente : `FH_ask + 0,25 × A`), **garanti simulé** avec prime, sans distance minimale IG (ASSUMP-008, §10) |
| Cible | `T = E + I` (vente : `E − I`), première cotation exécutable qui l'atteint |
| Sorties temporelles | `SORTIE_TEMPORELLE` à `X + 2 h` ; `LIQUIDATION_17H` à 17:00 Londres ; une seule clôture, celle de la première échéance, `LIQUIDATION_17H` en cas d'égalité ; premier tick strictement postérieur |
| Seuil d'interruption | strictement plus de 5 min d'ouverture prévue (ADR-021, extension DAY_02) |
| Capital, risque, taille | 2 000 EUR ; 0,25 % des fonds propres estimés à `D` ; minimum 0,1 contrat, incrément 0,1 |
| Coûts (`RESEARCH_COSTS`, `ASSUMED`) | glissement 0,5 pip ; commission 0 ; conversion 0,5 % ; prime de stop garanti 1,2 USD par contrat ; financement 1 USD par contrat et par nuit, seulement pour une `NUIT_NON_PRÉVUE` |
| Latence de publication | 0 |
| Fermetures particulières documentées | aucune |
| Stop dépassé au premier tick d'exécution | exécutée puis liquidée (référence) ; rejet seulement selon §4 |
| Limites de perte 1 % / 2 % | non appliquées (dérogation ADR-027) ; 6 % reste un seuil de revue |
| Annonces économiques | aucun filtre (fiche §3.4) |

## 4. Passages et conditions de déclenchement (fixées à l'avance)

Deux déclenchements, enregistrés à l'avance :
- **Référence : H1 → M15 → M5** (`Trigger.M5`) ;
- **Comparaison : H1 → M15** (`Trigger.M15`). Elle ne remplace pas la référence, même si son
  résultat est meilleur.

Pour **chaque déclenchement**, dans cet ordre, chaque condition étant lue dans le rapport de **son
propre** passage A (`scenario_triggers`) :

1. **A — observé seulement** (`GapScenario.OBSERVED_ONLY`) : toujours lancé.
2. **B — stop d'abord** (`GapScenario.STOP_FIRST`) : lancé si le passage A contient **au moins une
   transaction indéterminée**, c'est-à-dire au moins une interruption (silence strictement
   supérieur à 5 min d'ouverture prévue) pendant une position, enregistrée par le moteur
   (`unobservable_crossings`), **y compris** pendant une sortie temporelle ou une liquidation de
   17:00 en attente, et pour une position encore ouverte à la fin.
   - Ne déclenchent pas B à eux seuls : une fermeture connue ; une entrée en attente annulée pour
     interruption (aucune position) ; un silence d'exactement 5 min.
3. **C — cible d'abord** (`GapScenario.TARGET_FIRST`) : lancé à la **même condition** que B.
   **Publié seulement s'il diffère de A** (transactions ou solde) ; sinon rapporté comme identique.
4. **Rejet à l'exécution** (`StopAtExecution.REJECT`, scénario A) : lancé seulement si le passage A
   contient **au moins une** `STOP_DÉPASSÉ_À_L'EXÉCUTION`.

Chaque passage est une trajectoire rejouée en entier. **Particularité de DAY_02** : la suite des
configurations dépend des positions (fiche §5.7) ; B, C et le rejet peuvent donc produire d'autres
tentatives que A, pas seulement d'autres issues. Chacun est contrôlé selon les §5 et §6 pour lui-même,
jamais par égalité de ses tentatives avec celles de A. Les conditions de M5 et de M15 sont lues
séparément. Aucune autre variante : ni autre cible ou sortie, ni autre durée de sortie temporelle,
ni autre heure de liquidation, ni blocage journalier ou hebdomadaire, ni filtre d'annonces, ni
sensibilité.

## 5. Contrôle des configurations depuis leur véritable état de reprise (avant lecture)

Contrairement à DAY_01, le parcours jusqu'à `D` d'une configuration DAY_02 dépend de son instant
de reprise, qui dépend des positions. Le passage n'est donc **pas** rapproché de l'étude de
disponibilité par des totaux : **aucune égalité globale avec les 307 et 272 sorties confirmées de
l'étude n'est exigée**, ni sur les configurations, les causes ou les comptes par séance et par
année. Le contrôle porte sur chaque tentative, depuis l'état de reprise que le passage a réellement
vécu. Tout écart est une anomalie : résultats masqués, code 2, présentation avant toute correction.

**5.1 Configuration recalculée depuis son état de reprise.** Pour chaque tentative (`Attempt`) :
- recalcul par `configuration_from(resume_utc, …)` sur les seules bougies (aucun tick, aucune
  position), avec les paramètres du passage ; égalité champ par champ avec la recherche enregistrée
  par le moteur : M15 examinées et causes, sens, `A`, `O`, `E`, bougies `o` et `p`, extensions,
  pauses, `F`, `Δ`, issue, fin, extrême du drapeau, `S`, `T`, `D` ;
- recalcul distinct (fonctions de contrôle C6 de l'étude, généralisées à un instant de reprise
  quelconque) de la reconnaissance et de la formation, ATR H1 partagé ; même portée qu'en C6 ;
- bornes (C4) et non-réutilisation des M15 (C5) appliquées aux tentatives du passage : aucune M15
  commençant avant la reprise, aucune M15 servant deux configurations.

**5.2 Événement qui autorise chaque reprise.** Ce recalcul ne prouve pas que l'instant de reprise
est le bon ; chaque `resume_utc` est donc rapproché de l'événement qui l'autorise (fiche §5.7),
lu dans les enregistrements du moteur (précisions du 2026-11-07, ADR-034) :

| Reprise (`resume_after`) | Instant attendu |
|---|---|
| `début de séance` (première tentative d'une séance) | 07:00 de la séance, aucune position ni entrée en attente à 07:00 ; **y compris après une clôture la veille** : la recherche du lendemain repart à 07:00, pas à l'heure de cette clôture |
| `clôture de la position` (première tentative d'une séance) | position héritée encore ouverte à 07:00 : `max(07:00, tick de sortie)` de cette position ; égal à la fin enregistrée de sa tentative |
| fin de configuration sans entrée (abandon, invalidation, expiration) | fin enregistrée de la configuration précédente |
| abstention à `D` (cinq causes possibles) | `D` de la configuration précédente |
| `ENTRÉE_EXPIRÉE`, `ENTRÉE_ANNULÉE_INTERRUPTION`, `ENTRÉE_REJETÉE` (passage de rejet) | instant enregistré de l'issue de l'entrée (`entry_outcome_utc`) |
| `clôture de la position` (dans la séance) | instant du **tick de sortie** de la transaction de la tentative précédente ; égal à `ended_utc` de cette tentative |

Contrôles associés :
- **fin de chaque tentative** : `ended_utc` et `ended_by` égaux à l'événement du tableau, lu
  séparément (fin de configuration, `D` et refus, issue de l'entrée, tick de sortie de sa
  transaction). **Une recherche qui se termine sans reconnaître de configuration n'a ni `ended_utc`
  ni `ended_by`** : c'est une fin normale de recherche, ni une position ouverte, ni une anomalie ;
  elle est comptée (`sans configuration jusqu'à la fin de fenêtre`) et ne peut être que la dernière
  de sa séance. Seule une position encore ouverte à la fin de l'étude laisse aussi une tentative
  sans fin ;
- **enchaînement dans une séance** : chaque tentative reprend exactement à la fin de la précédente.
  La dernière tentative d'une séance est une recherche sans configuration, ou une position fermée
  au plus tôt à 14:15 (dernière reconnaissance), ou encore ouverte à la fin de l'étude ;
- **première tentative d'une séance** : `début de séance` à 07:00 si rien n'est tenu à 07:00 ;
  `clôture de la position` à la clôture effective d'une position tenue à 07:00 (séance **listée**
  comme retardée) ; toute autre cause est une anomalie ;
- **séance sans recherche** : justifiée seulement par une position encore ouverte à 14:15 (ou à la
  fin de l'étude) et marquée par le moteur (`skipped_days`) ; séance **listée** ;
- aucune reprise pendant une position (de `D` au tick de sortie) ; aucune abstention « position
  déjà ouverte » à `D` (impossible par construction : 0 attendu).

Tests synthétiques de ces situations : recherche terminée sans configuration ; clôture la veille
suivie d'une reprise à 07:00 ; position tenue à 07:00 retardant la reprise ; position tenue au-delà
de 14:15 empêchant toute recherche ; rejet à l'exécution ; reprise volontairement mal datée
(bloquante).

**5.3 Rapprochement partiel avec l'étude de disponibilité.** Seulement là où l'état de reprise est
le même, configuration par configuration :
- **première recherche de séance** : pour toute séance dont la première reprise du passage est
  `début de séance` à 07:00, la configuration est égale champ par champ à la première recherche de
  la même date et du même déclenchement dans le JSONL de l'étude (exactement une ligne par date et
  par déclenchement, doublons refusés). Les séances retardées ou empêchées par une position héritée
  (§5.2) sont exclues de ce contrôle et comptées ;
- **toute autre tentative** dont l'instant de reprise coïncide avec celui d'une recherche de
  l'étude pour la même séance (par exemple une reprise à `D` après une abstention) : même égalité.
  Les autres tentatives ne sont rapprochées que par le §5.1 ;
- rapporté côte à côte, sans égalité exigée : configurations et sorties confirmées de l'étude et du
  passage, au total et par année, et nombre de séances dont la suite des instants de reprise
  diffère de celle de l'étude.

## 6. Parcours : des confirmations aux transactions

Pour chaque passage, globalement et par année. **Une sortie confirmée n'est pas une entrée** :
chaque confirmation (configuration d'issue `sortie confirmée`, instant `D`) est classée **une seule
fois**, d'après les enregistrements du moteur (`at_d`, `entry_outcome`, transaction, `Closing`).

| Étape (dénominateur) | Issue exclusive |
|---|---|
| Recherches (tentatives) | sans configuration jusqu'à la fin de fenêtre ; configuration |
| Configurations | données inutilisables ; impulsion prolongée ; repli trop profond avant `F` ; fin de fenêtre avant `F` ; **drapeau formé** |
| Drapeaux formés | **données inutilisables pendant la recherche de sortie** ; repli trop profond après `F` ; consolidation trop longue ; fin de fenêtre ; **sortie confirmée** |
| Sorties confirmées | refus à `D` : marché fermé ; absence de cotation ; stop non admissible ; cible déjà dépassée ; taille minimale supérieure au budget ; **ou** entrée décidée |
| Entrées décidées | `EXÉCUTÉE` ; `STOP_DÉPASSÉ_À_L'EXÉCUTION` ; `CIBLE_ATTEINTE_À_L'EXÉCUTION` ; `ENTRÉE_REJETÉE` (passage de rejet seulement) ; `ENTRÉE_EXPIRÉE` ; `ENTRÉE_ANNULÉE_INTERRUPTION` |
| Entrées exécutées | sortie liée au stop ; clôturée à la cible ; `SORTIE_TEMPORELLE` ; `LIQUIDATION_17H` ; encore ouverte à la fin de l'étude |

La fin pour données inutilisables **après la formation du drapeau** (bougie de déclenchement
absente ou non `OK` pendant la recherche de sortie) est une issue des drapeaux formés, distincte de
la même cause avant `F`. Elle reste dans le classement même si l'étude de disponibilité n'en compte
aucune ; sa conservation dans les comptes est testée.

**Issues exclusives et annotations** (règles validées pour DAY_01, reprises) :
- une entrée **décidée** n'est pas **exécutée** : rejet, expiration et annulation sont décidés sans
  transaction ; une entrée exécutée puis sortie sur le même tick reste exécutée ;
- chaque entrée exécutée a **une seule** issue, lue dans le motif de clôture du moteur, conservé comme
  sous-motif. `STOP_FRANCHI_À_L'EXÉCUTION` est rangé dans « sortie liée au stop » (exécutée puis
  liquidée au prix observé, sans garantie de sortie au niveau du stop) ; `CIBLE_ATTEINTE_À_L'EXÉCUTION`
  dans « clôturée à la cible ». Une `SORTIE_TEMPORELLE` ou une `LIQUIDATION_17H` dont le tick de
  clôture franchit d'abord le stop ou la cible est rangée selon le motif effectif du moteur
  (`Closing.close_reason`), l'ordre de clôture restant rapporté à part. Un motif non prévu fait
  échouer le contrôle ;
- **annotations**, jamais additionnées comme des sorties : indéterminée ; `NUIT_NON_PRÉVUE` ;
  clôture après interruption ; coïncidence des échéances (sortie temporelle à 17:00) ; clôture en
  attente à la fin.

**Contrôles bloquants** (même règle d'arrêt qu'au §5) :
- conservation à chaque étape ; une configuration au plus par tentative ; une décision au plus par
  configuration ; au plus une transaction par entrée décidée ; toute transaction issue d'une entrée
  décidée ; une entrée exécutée a exactement une transaction ;
- chaque entrée décidée attestée par une transaction ou un événement de non-exécution ;
- au plus une position DAY_02 ou entrée en attente à tout instant ;
- `D ≤ 15:00`, aucune exécution après 15:05 Londres, exécution dans `]D, D + 5 min]` ;
- chaque position fermée par au plus une clôture (`Closing`) : échéance = première de `X + 2 h` et
  17:00, `LIQUIDATION_17H` en cas d'égalité ; délai, silence clos et motif présents ; concordance
  des `NUIT_NON_PRÉVUE` avec le journal ;
- clôture encore en attente à la fin : autorisée ; heure de décision, durée d'attente, position et
  silence en cours rapportés, sans clôture fabriquée ; si ce silence dépasse 5 min d'ouverture
  prévue, la transaction est indéterminée (§4) ;
- 0 tick lu hors de la fenêtre ; empreintes inchangées ; paramètres attendus (C9) ; provenance
  (C10).

## 7. Rapporté pour chaque passage

- Transactions ; brut, coûts par poste (glissement, conversion, prime de stop garanti, financement
  d'une nuit non prévue), net ; issues ; globalement et par année de sortie ; position ouverte à la
  fin, à part.
- **Configurations, entrées et pertes par séance** (fiche §10.2) ; séances à plusieurs entrées.
- **Sorties temporelles et liquidations de 17:00** : nombre ; délai après l'échéance ; silence clos ;
  motif de clôture ; coïncidences ; positions subsistant après 17:00 ; nuits non prévues ; clôture
  non exécutée à la fin.
- **Entrées non exécutées** : expirées, annulées pour interruption (silence décrit par l'événement
  du moteur, conservé dans le détail local), rejetées.
- **Portée de deux descriptions** (retenue après la revue de f705858) : une annulation pour
  interruption est décrite **par l'événement enregistré par le moteur**, sans durée de silence
  recalculée ; une transaction indéterminée l'est **par les trous enregistrés par le moteur**, sans
  nouvelle lecture des ticks. Ni l'une ni l'autre ne mesure davantage que ce que le moteur a
  enregistré.
- **Mesures par entrée** (détail local hors Git, distributions dans l'agrégé ; aucune ne sert de
  filtre ; une mesure non définissable est absente avec son motif) : distance du stop `P_D − S` en
  pips et en multiples de `A` ; rapports des distances estimé à `D`, net estimé à `D` et obtenu à
  l'exécution, côte à côte ; part des coûts fixes dans le risque (définition de DAY_01) ; **écart
  entre les indicateurs approchés de l'étude** (depuis la clôture de la bougie de sortie) **et les
  valeurs à `D`**, sur les sorties confirmées rapprochées au §5.3 : distance au stop à `D`
  `|P_D − S|` moins l'indicateur approché `|clôture bid − S|`, en pips. `P_D` étant l'ask à `D` à
  l'achat et le bid à `D` à la vente, l'écart vaut `(ask à D − clôture bid) / pip` à l'achat et
  `(clôture bid − bid à D) / pip` à la vente ; le stop s'élimine ; pente du drapeau des entrées décidées (descriptif ; le
  nombre de pauses vaut 2 par construction).
- **Répartitions** : par jour de la semaine ; par heure de décision (Londres) ; GMT, BST et semaines
  de décalage ; par sens.
- Drawdown au tick en euros, global continu et par année ; drawdown relatif maximal ; premier
  franchissement de 6 % (seuil de revue, la trajectoire continue) ; durée de récupération.
- Net sans la meilleure transaction ; transactions indéterminées (trous enregistrés par le moteur,
  position ouverte à la fin) ; dépassements du budget.
- Mesures du cahier (§9) : espérance nette en multiples du risque, profit factor, gain et perte
  moyens, durée d'exposition, mois sans opération et mois déficitaires.
- **Limites de perte journalière et hebdomadaire** : **non décrites** dans ce premier passage
  (choix retenu par l'opérateur le 2026-11-07, la fiche §7.1 les rendant facultatives) ; le premier
  franchissement de 6 % reste rapporté.

## 8. Comparaisons

**Existence des deux passages** (précision du 2026-11-07). B, C et le rejet sont déclenchés
séparément pour M5 et M15 (§4). Une comparaison entre les deux trajectoires d'un même scénario n'est
produite **que si les deux passages existent** et ont passé leurs contrôles : `forex-day02-compare`
exige les deux rapports (même scénario, même règle d'exécution, même fenêtre, déclenchements M5 et
M15) et refuse sinon (code 2, aucune sortie).

**Rattachement des détails à leur rapport** (correction du 2026-11-07). Chaque rapport enregistre
l'empreinte SHA-256 et le nombre de lignes du détail par séance qu'il a écrit (`sessions_file`) ;
chaque ligne du détail nomme le passage qui l'a produite : déclenchement, scénario, règle
d'exécution, passage (`A`, `B`, `C` ou `A_rejet`, ce dernier pour la règle de rejet) et fenêtre.
Avant toute comparaison, `forex-day02-compare` vérifie pour chaque côté que l'empreinte du détail
fourni est celle enregistrée par son rapport, puis que chaque ligne porte le déclenchement, le
scénario, la règle d'exécution, le passage et la fenêtre de ce rapport. Un détail d'un autre
passage (par exemple les détails B fournis avec les rapports A, ou un détail substitué entre A et
A avec rejet) est refusé : code 2, aucune comparaison écrite. Le plan (`--plan`) n'accepte que les
deux rapports du passage `A`, pas ceux du passage `A_rejet`. Le plan des comparaisons est établi depuis les deux passages A
(`--plan`) : un scénario requis d'un seul côté est **rapporté comme tel**, sans comparaison, et
l'autre côté **n'est pas lancé** pour compléter le tableau.

**M5 / M15**, par date de séance de Londres (`forex-day02-compare`, depuis les deux détails
locaux d'un même scénario ; exactement une ligne par date et par trajectoire, doublons refusés,
mêmes dates exigées). Une ligne par date dans la sortie locale : tentatives, sorties confirmées,
entrées décidées et exécutées de chaque trajectoire. Les appariements entrée par entrée ne portent
que sur la **première configuration de séance à même état de reprise** dans les deux trajectoires
(écarts d'instant d'entrée, de stop, de taille et de résultat) ; au-delà, seuls des comptes par
séance sont comparés, sans appariement. Parcours, transactions, net et drawdown côte à côte. La
comparaison ne remplace pas la référence.

**Avec S1, S2, S3 et DAY_01 M5** (références du §1), description seulement : chevauchement des
positions dans le temps (même sens, sens opposé), **pertes simultanées** (transactions DAY_02
perdantes qui chevauchent une perte de chaque référence), présentées par référence puis en union
sans doublon des transactions DAY_02 concernées ; nets annuels côte à côte. Trajectoires
indépendantes, chacune avec son capital : **ce n'est pas une simulation de portefeuille partagé**.

## 9. Lecture des résultats (règles de S2, S3 et DAY_01)

1. Un net strictement positif dans chaque scénario publié est un résultat favorable sur la période
   de développement, sans plus. Un signe différent entre A et B (ou A et C) signifie que le résultat
   dépend des trous de cotation.
2. Le net sans la meilleure transaction est un indicateur, pas un motif automatique de rejet ; 6 %
   de drawdown relatif est un seuil de revue.
3. Si les pertes DAY_02 sont surtout simultanées à celles d'autres références, DAY_02 diversifie
   peu, quel que soit son net. Aucun seuil automatique.
4. Avec peu de transactions, aucune conclusion statistique.
5. Stops garantis simulés sans minimum IG confirmé : un résultat favorable ne dit rien de leur
   exécutabilité (ASSUMP-008).
6. Les limites 1 % et 2 % ne sont pas appliquées (ADR-027) : le résultat n'est pas celui d'un compte
   qui les applique.
7. Aucun filtre d'annonces : la part des configurations touchées n'est pas mesurable.

## 10. Conditions IG : décision encore nécessaire avant les passages

La fiche (§8) liste les informations IG manquantes et les hypothèses de recherche qui les
remplacent : distance minimale et prime du stop garanti, côté de déclenchement des stops,
disponibilité d'un stop normal, taille minimale et incrément, glissement, commission, conversion,
financement, exécution d'un ordre limite à la cible, écart Dukascopy / IG, horaires et fermetures.
Pour DAY_02, la distance minimale du stop garanti est la plus sensible : les stops dépendent de la
profondeur du drapeau et de `A` H1, et leur distribution à `D` n'est pas connue avant le passage.

**Avant tout passage de performance, l'opérateur décide** l'une des options suivantes, consignée
dans une ADR :
- **(a)** confirmer d'abord tout ou partie de ces conditions auprès d'IG, par l'opérateur lui-même
  (demande préparée `docs/IG_SUPPORT_REQUEST.md`, non envoyée ; aucun contact par l'agent) ; les
  valeurs confirmées seraient intégrées à ce protocole avant le gel ;
- **(b)** mener le passage sous les hypothèses explicites actuelles (`RESEARCH_COSTS`, `ASSUMED`,
  aucune distance minimale), comme S1 à DAY_01, avec les limites du §9 points 5 et 6 rappelées
  dans le bilan.

Aucune variante de sensibilité aux conditions IG n'est prévue par ce protocole. L'outil a été
écrit et testé sur données synthétiques avant cette décision (autorisation du 2026-11-07) ; la
décision reste **ouverte** et aucun passage historique n'est autorisé.

## 11. Commandes (figées avec l'outil)

Préfixe des sorties : `data/reports/backtests/day02_ref_2015_2021_<déclenchement>_<passage>` (hors
Git), avec `<déclenchement>` = `m5` ou `m15` et `<passage>` = `a`, `b`, `c` ou `a_reject`.

```
uv run forex-day02-backtest --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 \
  --trigger M5 --scenario A \
  --availability data/reports/backtests/day02_availability_2015_2021_eb48d6c_details.jsonl \
  --s1-reference data/reports/backtests/s1_ref_2015_2021_h0.json \
  --s2-reference data/reports/backtests/s2_ref_2015_2021_h1_a.json \
  --s3-reference data/reports/backtests/s3_ref_2015_2021_d1h4_a.json \
  --day01-reference data/reports/backtests/day01_ref_2015_2021_m5_a.json \
  --out data/reports/backtests/day02_ref_2015_2021_m5_a.json \
  --sessions-out data/reports/backtests/day02_ref_2015_2021_m5_a_sessions.jsonl
```

La fenêtre officielle (valeur par défaut) active les ancrages : empreinte complète du JSONL de
l'étude, 3 632 lignes et 1 816 dates, 383 trous. Le rapport JSON a un résumé Markdown (même nom,
`.md`) ; le détail par séance n'est écrit que si les contrôles passent, et son empreinte est alors
enregistrée dans le rapport (§8).

Ordre prévu :
1. `m5_a` (ci-dessus) ; `m15_a` : même commande avec `--trigger M15`, sorties `*_m15_a*` ;
2. plan des comparaisons depuis les deux passages A :
   `uv run forex-day02-compare --plan --m5-report <..._m5_a.json> --m15-report <..._m15_a.json> --out <...>` ;
3. pour chaque déclenchement, selon `scenario_triggers` de **son** passage A : `--scenario B` puis
   `--scenario C` si `scenario_b_required` ; puis `--stop-at-execution REJECT` si `reject_required` ;
4. comparaison M5 / M15 de chaque scénario dont les deux passages existent :
   `uv run forex-day02-compare --m5-report <...> --m15-report <...> --m5 <..._sessions.jsonl> --m15 <..._sessions.jsonl> --out <...>`.

 Chaque commande part d'un arbre propre
au commit qui fige ce protocole et l'outil ; un contrôle en échec (code 2) arrête la suite et est
présenté avant toute correction. Bilan agrégé : `DAY02_REFERENCE_2015_2021_BILAN.md` ; journaux et
détails hors Git.

## 12. Ordre de travail

1. Protocole soumis à l'opérateur ; base approuvée le 2026-11-07, précisions intégrées (ADR-034).
2. Outil `forex-day02-backtest`, `forex-day02-compare` et tests synthétiques (dont des tentatives
   faussées pour les contrôles des §5 et §6), sans passage historique : fait ; revue de f705858,
   deux corrections (§7, §8) ; protocole figé au commit de ces corrections, soumis à revue.
3. Décision de l'opérateur sur les conditions IG (§10) : **ouverte**.
4. Passages 2015-2021, **sur autorisation explicite**, dans l'ordre du §11.

## 13. Interdits

Aucune donnée 2022-2025 ; aucun réglage après lecture des résultats ; aucune variante non
enregistrée ici ; aucune égalité imposée avec les totaux de l'étude de disponibilité ; aucun
entraînement ; aucun ordre, même en démo ; aucun contact avec IG par l'agent ; aucun détail par
séance publié.
