# Protocole — S2 reprise de tendance après repli, premier passage de performance 2015-2021

**Statut** : figé le 2026-11-04, **avant tout lancement** sur cette période. Étape 4 de la fiche
`docs/strategies/S2_PULLBACK.md` (§9), autorisée par l'opérateur le 2026-11-04 après validation de
l'étape 3 (PR #8). Ni validation de performance, ni autorisation de trading. Aucun paramètre ne
sera modifié après lecture des résultats ; un résultat défavorable est rapporté tel quel.

## 1. Code et données

- Moteur : `S2Backtest` (`backtest/s2_engine.py`), fusionné dans `main` (PR #7 et #8) ; le passage
  utilise `forex-s2-backtest` (`backtest/s2_explore.py`), qui n'ajoute que de l'observation :
  drawdown au tick par année, cotations encadrant chaque trou de cotation pendant une position,
  rapport. Chaque rapport enregistre le commit, l'empreinte du diff non commité et la ligne de
  commande (`provenance`) ; les passages partent d'un arbre propre au commit qui fige ce protocole.
- Données : historique Dukascopy EUR/USD local, lecteur en flux, fenêtre bornée ; aucun
  téléchargement ; 2022-2025 jamais lus (refus du lecteur hors 2015-2021).
- Référence S1 pour le chevauchement : `data/reports/backtests/s1_ref_2015_2021_h0.json`
  (commit `d52f24f`, 53 transactions), lue seulement.

## 2. Fenêtre

Trajectoire **continue** du 2015-01-01T00:00Z inclus au 2022-01-01T00:00Z exclu, sans remise à zéro
annuelle du capital. Initialisation sur les premières bougies de la fenêtre (l'historique commence
le 2015-01-01), pendant laquelle les règles de données refusent toute entrée.

## 3. Configuration

| Élément | Valeur |
|---|---|
| Paramètres S2 (ASSUMP-025, fiche §10) | `p_D1` 2, `p_H4` 3, `p_H1` 2, ATR Wilder 14 H4 figé à `I`, `z` 0,5 A, `T_max` 30 H4, `b` 0,25 A, `R_min` 1,0, `H_max` 60 H4 |
| Déclenchement | **H1 = référence** ; **H4 = comparaison secondaire enregistrée à l'avance** (§4.6), qui ne remplace pas la référence même si son résultat est meilleur |
| Capital initial | 2 000 EUR ; risque 0,25 % des fonds propres estimés à la décision |
| Taille | minimum 0,1 contrat, incrément 0,1 (scénario de la référence S1) |
| Stop | garanti simulé (prime à son déclenchement) |
| Latence de publication | 0 |
| Coûts (`RESEARCH_COSTS`, scénario non confirmé chez IG) | glissement 0,5 pip ; commission 0 ; financement 1 USD par contrat et par nuit ; conversion 0,5 % ; prime de stop garanti 1,2 USD par contrat |
| Fermetures particulières documentées | aucune (comme la référence S1) |
| Stop dépassé au premier tick d'exécution | exécutée puis liquidée (référence) ; rejet seulement selon §4 |

## 4. Passages et conditions de déclenchement des scénarios

Pour chaque déclenchement (H1, puis H4), dans cet ordre :

1. **A — observé seulement**, toujours lancé.
2. **B — stop d'abord** : lancé si le passage A du même déclenchement contient **au moins une
   transaction indéterminée** (trou de cotation inexpliqué pendant une position : un
   franchissement du stop y est toujours possible).
3. **C — cible d'abord** : lancé à la même condition (une atteinte de la cible y est toujours
   possible) ; **publié seulement s'il diffère de A** (transactions ou solde). S'il est identique,
   il est rapporté comme tel, sans être publié comme trajectoire distincte.
4. **Rejet à l'exécution** (`REJECT`, scénario A) : lancé seulement si le passage A du même
   déclenchement contient **au moins une exécution dont le stop est déjà dépassé au premier tick**
   (`STOP_DÉPASSÉ_À_L'EXÉCUTION`).

Chaque scénario est une trajectoire rejouée en entier. Aucune autre variante n'est lancée.

## 5. Commandes

Préfixe des sorties : `data/reports/backtests/s2_ref_2015_2021_<déclenchement>_<passage>` (hors Git),
avec `<déclenchement>` = `h1` ou `h4` et `<passage>` = `a`, `b`, `c` ou `a_reject`.

```
uv run forex-s2-backtest --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 \
  --trigger H1 --scenario A \
  --s1-reference data/reports/backtests/s1_ref_2015_2021_h0.json \
  --out data/reports/backtests/s2_ref_2015_2021_h1_a.json \
  --decisions-out data/reports/backtests/s2_ref_2015_2021_h1_a_decisions.jsonl
```

Les autres passages changent seulement `--trigger` (`H4`), `--scenario` (`B`, `C`) et, pour le
rejet, ajoutent `--stop-at-execution REJECT` ; les noms de sortie suivent le préfixe ci-dessus.

## 6. Rapporté pour chaque passage

- Du signal à la position : cassures détectées → refus (données, position déjà ouverte, tendance
  D1 perdue, rapport gain/risque, marché fermé, taille minimale, autre) → entrées décidées →
  positions effectivement ouvertes (dont exécutées puis liquidées, cible atteinte au premier tick,
  non exécutées) ; configurations créées et leur devenir (entrée, abandon par motif, active).
- Transactions ; brut, coûts, net ; sorties par motif (cible, stop, temps, autres) ; globalement et
  par année (transactions par année de sortie).
- Drawdown au tick en euros (global et par année) ; **véritable drawdown relatif maximal au tick**
  et **premier franchissement éventuel de 6 %** (seuil de revue, la trajectoire continue).
- Net sans la meilleure transaction ; dépassements du budget ; résultats en multiples du risque
  estimé à la décision.
- Transactions indéterminées : trou, cotations qui l'encadrent, distances au stop et à la cible,
  issue en pips si stop, si cible, et observée.
- Comparaison à la référence S1 : chevauchement des positions dans le temps (même sens, sens
  opposé) et nets annuels côte à côte.
- Écarts avec l'étape 3 (sans chercher à les reproduire) : cycle de vie des configurations avec
  positions ouvertes et refus économiques.

Bilan agrégé dans ce dossier après les passages ; journaux et rapports détaillés hors Git.
