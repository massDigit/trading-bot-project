# Protocole — Risque de 1 % par opération, S1 seule, 2015-2021

**Statut** : figé le 2026-11-03, avant le lancement de la variante. Décision de l'opérateur du
2026-11-03 (ADR-013), après la revue par Astra du commit `d316d31`. Backtest seulement. Ni
validation de performance, ni autorisation de trading.

## 1. Question

Avec le minimum et le pas de 0,1 contrat de la référence, un risque de 1 % des fonds propres par
opération, au lieu de 0,25 %, améliore-t-il le résultat ? Si oui, cette amélioration dépend-elle
d'une seule transaction ?

## 2. Seule différence avec la référence

| Élément | Référence | Variante |
|---|---|---|
| Fraction de risque | 0,25 % des fonds propres à la décision | **1 %** |
| Budget initial (2 000 €) | 5 € | **20 €** |

Le budget reste recalculé sur les fonds propres estimés à chaque décision. Tout le reste est
identique à la référence (`S1_REFERENCE_2015_2021.md`, rapport `s1_ref_2015_2021_h0.json`) :
- moteur vérifié (`d52f24f`, inchangé) ;
- S1 Donchian (canaux H4 20/10, ATR 14, stop à 2 ATR), filtre D1 strict de 55 jours ;
- stop garanti simulé, coûts de recherche `RESEARCH_COSTS` ;
- minimum et pas de 0,1 contrat ;
- données EUR/USD locales, lecteur en flux ;
- trajectoire continue du 2015-01-01 inclus au 2022-01-01 exclu, 2 000 € au départ ;
- H0 et « exécutée puis liquidée ».

H1 seulement si la variante compte un franchissement de stop non observable ; rejet à l'exécution
seulement si elle compte un stop déjà dépassé au premier tick d'entrée (mêmes règles que la
référence). Pas de combinaison 1 % / 0,01 contrat, aucun autre paramètre ajusté après lecture des
résultats, aucune donnée 2022-2025.

## 3. Commande

```
uv run forex-backtest-explore --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 \
  --risk-fraction 0.01 \
  --decisions-out data/reports/backtests/s1_risk1pct_2015_2021_h0_decisions.jsonl \
  --out data/reports/backtests/s1_risk1pct_2015_2021_h0.json
```

Fichiers nouveaux, distincts de la référence, avec copie du protocole et du diff de lancement. Les
journaux détaillés restent locaux (hors Git) ; la revue s'appuie sur un bilan agrégé.

## 4. Réponses attendues

1. **Anciens refus de taille** : combien des 215 refus de la référence deviennent des entrées, et
   ce que deviennent les autres.
2. **Origine de l'écart** : transactions rapprochées par instant de décision et sens ; effet des
   tailles plus élevées sur les transactions communes, distinct de l'effet des transactions
   ajoutées (propres à la variante) ou évitées (propres à la référence).
3. **Effet pour le compte** : résultat brut et net, coûts, drawdown maximal au tick en euros et en
   pourcentage du sommet qui le précède, dépassements du budget, bilan annuel.
4. **Dépendance au plus gros gain** : transaction la plus gagnante de chaque passage, sa part du
   résultat net et le résultat net sans elle.

## 5. Résultats (2026-11-03)

Les sections 1 à 4 sont restées inchangées après le lancement. Fichiers locaux, hors Git, dans
`data/reports/backtests/` :
- `s1_risk1pct_2015_2021_h0*` et `s1_risk1pct_2015_2021_h1*` : rapport, journal des décisions,
  journal d'exécution, diff de lancement ;
- `s1_risk1pct_2015_2021_protocol.md` : copie du protocole ;
- `s1_risk1pct_vs_ref.json` et `s1_risk1pct_h1_vs_ref.json` : comparaisons.

### 5.1 Contrôles

| | H0 | H1 |
|---|---|---|
| Durée / pic de mémoire (Mac M4) | 4 849 s / 321 Mio | 4 891 s / 311 Mio |
| Empreinte du diff de lancement | concordante | concordante |
| Configuration | `risk_fraction` 0,01, minimum et pas de 0,1 | idem |

- Les journaux des décisions comptent 10 912 lignes valides, distinctes et chronologiques, aux
  mêmes instants que la référence.
- H0 compte 1 franchissement de stop possible mais non observable (vente décidée le
  2016-12-15 14:00 UTC), donc un passage H1 a été fait.
- Aucun stop n'était dépassé au premier tick d'exécution : aucun passage de rejet.
- H1 ne diffère de H0 que par cette transaction : stop de scénario le 2016-12-26 à −10,61 €, au
  lieu d'un stop observé le 2016-12-29 à −10,91 €, soit +0,30 €.

Les chiffres ci-dessous sont ceux de H0 ; H1 est indiqué entre crochets quand il diffère.

### 5.2 Les 215 anciens refus de taille

| Action de la variante au même instant | Nombre |
|---|---|
| Entrée exécutée | **84** |
| Toujours refusée | 0 |
| Non évaluée : position déjà ouverte | 131 |
| Autre action | 0 |

Les 84 entrées se font à 0,1–0,3 contrat. Elles sont toutes clôturées : 21 gagnantes, 48 sorties
au canal et 36 stops, pour −495,03 € nets [H1 −494,73 €]. Les 131 signaux non évalués tombent
tous pendant une position ouverte par l'une de ces 84 entrées.

Ces transactions sont exactement celles de la variante à 0,01 contrat (`S1_GRANULARITY_001.md`) :
mêmes instants de décision, mêmes sens, mêmes sorties. Seules les tailles diffèrent. Les deux
variantes lèvent la même barrière : un budget inférieur au risque de la taille minimale.

### 5.3 Origine de l'écart de résultat net (−376,35 € [H1 −376,05 €])

| Transactions rapprochées (instant de décision et sens) | Nombre | Brut | Coûts | Contribution |
|---|---|---|---|---|
| Communes : effet des tailles plus élevées | 48 | 70,33 → 237,09 € | 28,02 → 100,77 € | **+94,00 €** |
| Ajoutées (propres à la variante) | 84 | −398,08 € | 96,96 € | **−495,03 €** [H1 −494,73 €] |
| Évitées (propres à la référence) | 5 | −23,39 € | 1,30 € | **+24,69 €** |
| **Total** | | | | **−376,35 €** [H1 −376,05 €] |

- Transactions communes : mêmes sorties, au même instant et pour le même motif. Toutes changent
  de taille, de 0,1 contrat à 0,3 (22), 0,4 (20) ou 0,5 (6).
- Transactions évitées : les 5 se terminent au stop dans la référence. Dans la variante, une
  position ouverte par l'une des 84 entrées ajoutées empêchait de les évaluer.

### 5.4 Effet pour le compte (2 000 € au départ)

| | Référence 0,25 % | Variante 1 % H0 | Variante 1 % H1 |
|---|---|---|---|
| Transactions clôturées (gagnantes) | 53 (18) | 132 (39) | 132 (39) |
| Brut | +46,95 € | −160,99 € | −161,06 € |
| Coûts | 29,31 € | 197,73 € | 197,36 € |
| **Net** | **+17,63 €** | **−358,71 €** | **−358,42 €** |
| Fonds propres finaux | 2 017,63 € | 1 641,29 € | 1 641,58 € |
| Drawdown max au tick | 46,34 € | 448,02 € | 447,72 € |
| … en % du sommet qui le précède | 2,25 % (sommet 2 055,73 €) | 21,74 % (sommet 2 060,73 €) | 21,73 % |
| … période | 2018-08-15 → 2020-11-30 | 2015-05-01 → 2020-07-16 | idem |
| Dépassements du budget | 0 | 1 (0,02 €, entrée du 2016-07-19) | 1 |

Le pourcentage porte sur l'épisode de plus forte baisse en euros. L'épisode de plus forte baisse
en pourcentage n'est pas suivi séparément.

Bilan annuel (net par année de sortie et drawdown au tick par année, en EUR) :

| Année | Réf. net | Var. net | Réf. drawdown | Var. drawdown |
|---|---|---|---|---|
| 2015 | 0,00 | −152,76 | 0,00 | 213,65 |
| 2016 | −3,71 | −70,34 [H1 −70,04] | 10,48 | 133,87 [H1 133,58] |
| 2017 | +10,59 | +17,91 | 29,13 | 137,06 |
| 2018 | +26,37 | −47,33 | 25,81 | 127,93 |
| 2019 | −20,75 | −92,80 | 26,23 | 132,82 |
| 2020 | +12,72 | +39,77 | 11,38 | 77,35 |
| 2021 | −7,58 | −53,17 | 23,29 | 91,60 |

### 5.5 Dépendance au plus gros gain

| | Plus gros gain | Net total | Net sans ce gain |
|---|---|---|---|
| Référence | vente du 2018-04-20, 0,1 contrat : +30,61 € (174 % du net) | +17,63 € | **−12,98 €** |
| Variante 1 % | même transaction, 0,3 contrat : +91,82 € | −358,71 € | **−450,54 €** |

Le résultat positif de la référence dépend d'une seule transaction. La variante n'apporte pas
d'amélioration ; la question de la dépendance d'une amélioration à un seul trade ne se pose donc
pas pour elle.

### 5.6 Conclusion (2015-2021, ces hypothèses seulement)

Sur cette période et sous ces hypothèses (coûts de recherche par contrat, minimum de 0,1 contrat
non confirmé chez IG, H0 / H1, « exécutée puis liquidée »), un risque de 1 % par opération
**n'améliore pas** S1 :
- le résultat net passe de +17,63 € à −358,71 € ;
- le drawdown au tick passe de 2,25 % à 21,74 % du sommet.

Les tailles plus élevées rapportent +94 € sur les transactions communes. Les 84 signaux que le
budget plus large laisse passer coûtent −495 €, et ils perdent déjà avant coûts.

Le petit résultat positif de la référence repose lui-même sur une seule transaction : sans elle,
S1 seule est négative sur 2015-2021.

Ce résultat ne valide aucune règle et ne dit rien de 2022-2025, jamais lus. Un seul passage par
hypothèse, sans test de significativité. Conformément au protocole, ni combinaison 1 % / 0,01, ni
autre paramètre n'est testé.
