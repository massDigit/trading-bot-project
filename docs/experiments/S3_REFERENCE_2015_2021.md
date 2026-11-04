# Protocole — S3 cassure après compression, premier passage de performance 2015-2021

**Statut** : figé le 2026-11-04 avec l'outil de passage, **avant tout lancement** sur cette
période ; aucun passage lancé. Étape 4 de la fiche `docs/strategies/S3_SQUEEZE.md` (§9), après
validation de l'étape 3 (PR #15) ; protocole validé par l'opérateur (PR #16), précisé sur le
déclenchement de B (§4) et le décompte des cassures (§6). Ni validation
de performance, ni autorisation de trading. Aucun paramètre ne sera modifié après lecture des
résultats ; un résultat défavorable est rapporté tel quel.

## 1. Code et données

- Moteur : `S3Backtest` (`backtest/s3_engine.py`), fusionné dans `main` (PR #13), **inchangé**.
  Le rejeu de non-régression S1 (étape 2) est clos ; il ne sera refait que si un moteur partagé
  est modifié.
- Outil de passage : `forex-s3-backtest` (`backtest/s3_explore.py`), sur le modèle de
  `forex-s2-backtest`. Il n'ajoute que de l'observation (parcours, rapprochement des boîtes,
  retours vers la boîte, drawdown, récupération, cotations autour des trous, comparaison à S1),
  couverte par des tests synthétiques (`tests/test_s3_explore.py`) ; un test vérifie que les
  transactions et le solde sont ceux du moteur seul.
  Chaque rapport enregistre le commit, l'empreinte du diff non commité et la ligne de commande ;
  les passages partent d'un arbre propre au commit qui fige ce protocole.
- Données : historique Dukascopy EUR/USD local, lecteur en flux, fenêtre bornée ; aucun
  téléchargement ; 2022-2025 jamais lus (refus du lecteur hors 2015-2021).
- Lus seulement, jamais recalculés :
  - étape 3 : `data/reports/backtests/s3_availability_2015_2021_1be93fd_details.jsonl`
    (160 boîtes, commit `1be93fd`) ;
  - référence S1 : `data/reports/backtests/s1_ref_2015_2021_h0.json` (53 transactions, commit
    `d52f24f`) et son journal `s1_ref_2015_2021_h0_decisions.jsonl` (signaux par H4).

## 2. Fenêtre

Trajectoire **continue** du 2015-01-01T00:00Z inclus au 2022-01-01T00:00Z exclu, sans remise à
zéro annuelle du capital. L'historique commence le 2015-01-01 : pendant l'amorçage (bandes,
référence de compression, canal D1 de 55 jours), les décisions sont non évaluables. Une position
encore ouverte à la fin est valorisée, sans clôture fictive, et présentée à part.

## 3. Configuration

| Élément | Valeur |
|---|---|
| Paramètres S3 (ASSUMP-026, ADR-017, ADR-018, fiche §10) | bandes 20 H4, 2σ de population ; référence de 360 H4 prévues, au moins 240 largeurs, 20e centile au rang le plus proche ; 6 H4 comprimées ; hauteur ≤ 3 × A ; ATR Wilder 14 H4 figé à `F` ; vie de 30 H4 ; stop à 0,25 × A au-delà de la borne opposée ; contexte D1 de S1 (milieu du canal de 55 D1, règle stricte) |
| Sortie | une seule sortie de stratégie : clôture H4 de l'autre côté de la moyenne `M` ; stop garanti ; ni cible ni sortie temporelle ; première clôture de retour vers la boîte journalisée, sans sortie |
| Capital initial | 2 000 EUR ; risque 0,25 % des fonds propres estimés à la décision |
| Taille | minimum 0,1 contrat, incrément 0,1 (scénario de la référence S1) |
| Stop | garanti simulé (prime à son déclenchement) |
| Latence de publication | 0 |
| Coûts (`RESEARCH_COSTS`, scénario non confirmé chez IG) | glissement 0,5 pip ; commission 0 ; financement 1 USD par contrat et par nuit ; conversion 0,5 % ; prime de stop garanti 1,2 USD par contrat |
| Fermetures particulières documentées | aucune (comme les références S1 et S2) |
| Stop dépassé au premier tick d'exécution | exécutée puis liquidée (référence) ; rejet seulement selon §4 |

## 4. Passages et conditions de déclenchement

Deux réglages, enregistrés à l'avance :
- **Référence : D1 → H4** (contexte D1 exigé, fiche §4.3) ;
- **Comparaison secondaire : H4 seule, sans contexte D1** (fiche §9, cahier §6.5). Elle ne
  remplace pas la référence, même si son résultat est meilleur.

Pour chaque réglage, dans cet ordre :
1. **A — observé seulement** (`NONE_TRIGGERED`), toujours lancé.
2. **B — stop d'abord** (`ALL_TRIGGERED`) : lancé seulement si le passage A du même réglage
   contient **au moins un franchissement possible mais non observable** enregistré par le moteur
   (`unobservable_crossings` d'une transaction, **y compris une position encore ouverte à la
   fin** ; rapport : `scenario_triggers.scenario_b_required`). Un trou de cotation suivi d'un prix
   **déjà au-delà du stop** n'en est pas un : le moteur clôture alors la position au stop
   (`STOP_APRÈS_INTERRUPTION`, franchissement observé), ce qui ne déclenche pas B à lui seul.
3. **Rejet à l'exécution** (`REJECT`, scénario A) : lancé seulement si le passage A du même
   réglage contient **au moins une exécution dont le stop est déjà dépassé au premier tick**
   (`STOP_DÉPASSÉ_À_L'EXÉCUTION` ; rapport : `scenario_triggers.reject_required`).

S3 n'ayant pas de cible, il n'y a pas de scénario C. Chaque passage est une trajectoire rejouée en
entier. Aucune autre variante n'est lancée (ni sortie à la réintégration, ni sensibilité : fiche
§11, protocoles distincts).

## 5. Rapprochement des boîtes avec l'étape 3 (contrôle avant lecture)

Avant toute lecture des résultats, l'outil rapproche les boîtes de **chaque passage** des 160
boîtes de l'étape 3 :
- clé : instant de formation `F` ; comparés à l'égalité exacte : `BH`, `BL`, `AH`, `A` ; puis
  devenir (consommée par une cassure, avec son instant et son sens ; expirée ; abandonnée ;
  active à la fin) ;
- rapporté : boîtes identiques, boîtes seulement dans le passage, seulement à l'étape 3, et
  boîtes appariées avec des bornes ou un devenir différents.

La reconnaissance ne dépend ni du contexte D1, ni d'une position, ni de l'évaluation de la
cassure (fiche §4.1, §4.2) : le résultat attendu est **160 boîtes identiques dans chaque
passage**, référence et comparaison. **Tout écart est une anomalie** : le passage est signalé,
ses résultats ne sont pas présentés, et l'écart est soumis à l'opérateur avant toute correction
ou nouveau lancement.

Mise en œuvre : le rapport contient `boxes_check` (identiques, seulement dans le passage,
seulement à l'étape 3, et pour chaque boîte différente son `F` et chaque champ avec ses deux
valeurs). En cas d'écart, il ne contient **aucun résultat de performance** (ni transactions, ni
parcours, ni journal des décisions écrit), et la commande s'arrête avec le code 2.

## 6. Parcours : cassures, refus, entrées

Pour chaque passage, globalement et par année. Une **cassure détectée** est une décision où le
moteur a enregistré un signal (première clôture hors d'une boîte active ; 160 attendues). Sa
catégorie reprend **l'action et le dernier motif enregistrés par le moteur** à cette décision ;
aucune règle n'est réévaluée. Chaque cassure est dans **une seule** catégorie :

| Action du moteur | Catégorie |
|---|---|
| `ÉVALUATION_IMPOSSIBLE` | données : bougie de cassure non `OK` ; données : bandes non calculables (à la cassure ou à la H4 précédente) ; **données D1 : insuffisantes** (moins de 55 D1 disponibles) ; **données D1 : inutilisables** (D1 de contexte, ou une D1 du canal, non utilisable). Référence seulement : sans filtre D1, l'état du D1 n'est pas lu |
| `NON_ÉVALUÉE` | non évaluée : position S3 déjà ouverte (boîte consommée) |
| `SIGNAL_REFUSÉ` | refus : pas d'expansion ; **refus : contexte D1 calculable, neutre ou contraire** (référence seulement) ; refus : marché fermé à `D` ; refus taille : **aucune cotation connue** ; refus taille : **estimation impossible** ; refus taille : **coût inconnu** ; refus taille : **taille minimale** |
| `ENTRÉE_DÉCIDÉE` | entrée décidée |

Un motif non prévu est rangé à part (« autre », avec le motif) et fait échouer le contrôle.

Chaque **entrée décidée** est ensuite comptée une seule fois comme **exécutée** (position
ouverte, ou exécutée puis liquidée au premier tick si le stop est déjà dépassé) ou **non
exécutée** (rejet à l'exécution, position déjà ouverte, aucun tick avant la fin de la fenêtre).

Contrôles écrits dans le rapport (`funnel.checks`) : une catégorie par cassure ; aucun motif non
classé ; entrées décidées = exécutées + non exécutées. Un contrôle en échec est rapporté avant
toute lecture des résultats.

## 7. Rapporté pour chaque passage

- Transactions ; brut, coûts, net ; sorties par motif (stop, sortie suiveuse, autres) ;
  globalement et par année (transactions par année de sortie) ; position ouverte à la fin, à
  part.
- **Retours vers la boîte** (description seulement) : positions avec une réintégration, avec une
  traversée, sans retour ; délai en H4 depuis l'exécution ; sortie qui a suivi (suiveuse ou
  stop) et résultat en multiples du risque, à côté des positions sans réintégration. Aucune
  sortie à la réintégration n'est simulée.
- Drawdown au tick en euros (global et par année) ; **véritable drawdown relatif maximal au
  tick** ; premier franchissement éventuel de 6 % (seuil de revue, la trajectoire continue) ;
  durée de récupération.
- Net sans la meilleure transaction ; transactions indéterminées (trou, cotations qui l'encadrent,
  distance au stop) ; dépassements du budget.
- Mesures du cahier (§9) : espérance nette en multiples du risque, profit factor, gain et perte
  moyens, durée d'exposition, mois sans opération et mois déficitaires conservés.

## 8. Comparaison à la référence S1

Lue dans les sorties de la référence S1, pour chaque passage S3 :
- **coïncidence des entrées** : part des entrées S3 décidées sur la même H4 (même instant de
  décision) et dans le même sens qu'un **signal** de la référence S1, entrée S1 décidée ou non ;
- chevauchement des positions dans le temps (même sens, sens opposé) ;
- **pertes simultanées** : transactions S3 perdantes qui chevauchent une transaction S1
  perdante ;
- nets annuels S1 et S3 côte à côte.

La référence D1 → H4 et la comparaison H4 seule sont aussi présentées côte à côte (parcours,
transactions, net, drawdown), sans que la comparaison remplace la référence.

## 9. Lecture des résultats (fiche §9, règles de S2 et ADR-015)

1. Un net strictement positif dans chaque scénario publié est un résultat favorable sur la
   période de développement, sans plus. Un signe différent entre A et B signifie que le résultat
   dépend des trous de cotation.
2. Le net sans la meilleure transaction est un indicateur, pas un motif automatique de rejet ;
   6 % de drawdown relatif est un seuil de revue.
3. Si la plupart des entrées S3 coïncident avec des signaux S1, ou si les pertes S3 sont surtout
   simultanées à des pertes S1, la conclusion est que S3 apporte peu par rapport à S1, quel que
   soit son net. Aucun seuil automatique n'est fixé.
4. Avec peu de transactions, aucune conclusion statistique.

## 10. Commandes (aucune lancée à ce jour)

Préfixe des sorties : `data/reports/backtests/s3_ref_2015_2021_<réglage>_<passage>` (hors Git),
avec `<réglage>` = `d1h4` (référence) ou `h4` (comparaison) et `<passage>` = `a`, `b` ou
`a_reject`.

```
uv run forex-s3-backtest --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 \
  --d1-filter on --scenario A \
  --step3 data/reports/backtests/s3_availability_2015_2021_1be93fd_details.jsonl \
  --s1-reference data/reports/backtests/s1_ref_2015_2021_h0.json \
  --s1-decisions data/reports/backtests/s1_ref_2015_2021_h0_decisions.jsonl \
  --out data/reports/backtests/s3_ref_2015_2021_d1h4_a.json \
  --decisions-out data/reports/backtests/s3_ref_2015_2021_d1h4_a_decisions.jsonl
```

Ordre prévu :
1. `d1h4_a` (ci-dessus) ;
2. `h4_a` : même commande avec `--d1-filter off`, sorties `s3_ref_2015_2021_h4_a*` ;
3. pour chaque réglage, selon `scenario_triggers` de son passage A : `--scenario B` (sorties
   `*_b*`) si `scenario_b_required`, puis `--stop-at-execution REJECT` (sorties `*_a_reject*`)
   si `reject_required`.

Chaque commande part d'un arbre propre au commit qui fige ce protocole ; un passage dont le
contrôle des boîtes échoue (code 2) arrête la suite.

Bilan agrégé dans ce dossier après les passages ; journaux et rapports détaillés hors Git.

## 11. Interdits

Aucune donnée 2022-2025 ; aucun réglage après lecture des résultats ; aucune variante non
enregistrée ici ; aucun entraînement ; aucun ordre ; le sélecteur IA n'est pas concerné.
