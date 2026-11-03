# Protocole — Référence S1 Donchian seule, développement 2015-2021

**Statut** : figé le 2026-11-03, avant tout lancement sur cette période. Décision de l'opérateur
du 2026-11-03 (ADR-010). Ni validation de performance, ni autorisation de trading.

## 1. But

Obtenir une référence reproductible de S1 seule sur toute la partition de développement, à
laquelle un futur modèle (prendre le signal ou s'abstenir) sera comparé. Aucun paramètre n'est
optimisé, aucun modèle n'est entraîné. Une perte est rapportée telle quelle.

## 2. Code et données

- Moteur vérifié : `main` au commit `d52f24f` (fusion de la PR #4, revue d'Astra sur `4c6f01a`).
  `engine.py`, `s1.py`, `feed.py`, `data.py` et `bar_state.py` y sont inchangés.
- Ajout d'observation sur la branche `feat/s1-reference-2015-2021` (`explore.py` seulement) :
  bilan par année et drawdown observable au tick par année. Il ne modifie aucune décision ; chaque
  rapport enregistre le commit, l'empreinte SHA-256 du diff non commité et la ligne de commande
  (`provenance`).
- Données : historique Dukascopy EUR/USD local (`data/`), lecteur en flux, fenêtre bornée ; aucun
  téléchargement ; 2022-2025 jamais lus (refus du lecteur hors 2015-2021).

## 3. Fenêtre

- Trajectoire **continue** du 2015-01-01T00:00Z inclus au 2022-01-01T00:00Z exclu, sans remise à
  zéro annuelle du capital.
- Initialisation : l'historique commence le 2015-01-01 ; les indicateurs se construisent sur les
  premières bougies de la fenêtre, pendant lesquelles les règles de données refusent toute
  entrée (« évaluation impossible »). La première décision où canaux H4 20/10, ATR 14 et canal
  D1 de 55 jours sont tous calculables est rapportée (`first_fully_usable_decision`).

## 4. Configuration (identique au passage d'avril-juin 2019)

| Élément | Valeur |
|---|---|
| Canaux H4 | entrée 20, sortie 10 |
| ATR | 14 (Wilder), stop à 2 ATR |
| Filtre D1 | milieu du canal de 55 jours incluant la D1 de contexte, règle stricte |
| Stop | garanti simulé (prime à son déclenchement) |
| Capital initial | 2 000 EUR ; risque 0,25 % des fonds propres estimés à la décision |
| Taille | minimum 0,1 contrat, incrément 0,1 (scénario) |
| Latence de publication | 0 |
| Coûts (`RESEARCH_COSTS`, scénario non confirmé chez IG) | glissement 0,5 pip ; commission 0 ; financement 1 USD par contrat et par nuit ; conversion 0,5 % ; prime de stop garanti 1,2 USD par contrat |
| Interruption inexpliquée | H0 (aucun déclenchement non observable) |
| Stop dépassé au premier tick d'exécution | exécutée puis liquidée (ADR-009) |

## 5. Passages

1. **H0** (toujours) :

   ```
   uv run forex-backtest-explore --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 \
     --decisions-out data/reports/backtests/s1_ref_2015_2021_h0_decisions.jsonl \
     --out data/reports/backtests/s1_ref_2015_2021_h0.json
   ```

2. **H1**, seulement si le passage H0 compte au moins un franchissement de stop possible mais non
   observable pendant une position ouverte (`unobservable_crossings_h0` > 0) : même commande avec
   `--policy ALL_TRIGGERED`, sorties `s1_ref_2015_2021_h1*`. Les deux trajectoires sont
   présentées.
3. **Rejet à l'exécution**, seulement si H0 compte au moins un stop déjà dépassé au premier tick
   d'entrée (`stop_beyond_at_execution` > 0) : même commande avec
   `--stop-at-execution REJECT`, sorties `s1_ref_2015_2021_reject*`. Les deux conventions sont
   comparées.

Aucun scénario n'est choisi pour sa rentabilité ; H0 et « exécutée puis liquidée » restent la
convention de référence fixée avant le lancement.

## 6. Mesures

Global et par année civile UTC : achats et ventes (date d'entrée) ; transactions clôturées,
résultat brut, coûts et résultat net en EUR (date de sortie) ; drawdown maximal observable au
tick (global depuis 2 000 EUR ; par année depuis les fonds propres au premier tick de l'année) ;
dépassements du budget de risque ; motifs d'abstention ; décisions par action ; solde, latent et
fonds propres en fin d'année. Une position ouverte à la fin est valorisée et présentée à part.
Temps d'exécution et pic de mémoire (Mac M4).

Distinction demandée : années avec **peu d'occasions** (peu de cassures ou de nombreux refus de
données) et années où les **transactions perdent**.

## 7. Sorties (hors Git)

`data/reports/backtests/s1_ref_2015_2021_*.json` (rapport, résultats reliés à part dans
`outcomes_after_decision`), `*_decisions.jsonl` (une ligne par décision H4 : connu à la décision
et action, aucun résultat ultérieur), `*.log` (temps et mémoire mesurés par `/usr/bin/time -l`).
