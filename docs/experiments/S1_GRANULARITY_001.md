# Protocole — Granularité de taille 0,01 contrat, S1 seule, 2015-2021

**Statut** : figé le 2026-11-03, avant le lancement de la variante. Décision de l'opérateur du
2026-11-03 (ADR-011). Hypothèse de recherche : une taille de 0,01 contrat **n'est pas confirmée**
chez IG. Ni validation de performance, ni autorisation de trading.

## 1. Question

Le minimum de 0,1 contrat a-t-il écarté des occasions rentables, ou a-t-il protégé le compte ?
Dans la référence (`S1_REFERENCE_2015_2021.md`, rapport `s1_ref_2015_2021_h0.json`), 215
signaux sont refusés parce que la taille minimale dépasse le budget : 215 sur 1 024 cassures
détectées (21,0 %), ou 215 sur 268 signaux arrivés au dimensionnement (80,2 %).

## 2. Seule différence avec la référence

| Élément | Référence | Variante |
|---|---|---|
| Taille minimale | 0,1 contrat | **0,01 contrat** |
| Incrément de taille | 0,1 contrat | **0,01 contrat** |

Tout le reste est identique : moteur vérifié (`d52f24f`, inchangé), données EUR/USD locales,
lecteur en flux, trajectoire continue du 2015-01-01 inclus au 2022-01-01 exclu, canaux H4 20/10,
ATR 14, stop à 2 ATR, filtre D1 strict de 55 jours, stop garanti simulé, 2 000 EUR, 0,25 % de
risque par opération, coûts par contrat de `RESEARCH_COSTS`, H0, « exécutée puis liquidée ».
H1 ou rejet à l'exécution seulement si la variante en présente des cas (même règle que la
référence). Aucune autre taille ni aucun autre budget ne sera testé après les résultats.

## 3. Commande

```
uv run forex-backtest-explore --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 \
  --min-size 0.01 --size-increment 0.01 \
  --decisions-out data/reports/backtests/s1_gran001_2015_2021_h0_decisions.jsonl \
  --out data/reports/backtests/s1_gran001_2015_2021_h0.json
```

Fichiers distincts de la référence, hors Git, avec copie du protocole et du diff de lancement.

## 4. Réponses attendues

1. **Devenir des 215 refus de taille** : pour chaque instant de décision concerné dans la
   référence, action de la variante au même instant : entrée décidée (exécutée ou non), toujours
   refusée (motif), non évaluée parce qu'une position est ouverte, ou autre action parce que la
   trajectoire a changé.
2. **Origine de l'écart de résultat** : transactions rapprochées par instant de décision et par
   sens. Communes (même décision, même sens) : effet du changement de taille sur leur résultat ;
   propres à la référence ; propres à la variante. Écart net = somme des trois contributions.
3. **Effet pour le compte** : nombre de transactions, brut, coûts, net, drawdown maximal
   observable au tick, dépassements du budget, net par année ; conclusion limitée à 2015-2021 et
   à ces hypothèses.

## 5. Résultats (2026-11-03)

Les sections 1 à 4 sont restées inchangées après le lancement. Fichiers locaux, hors Git (publiés
temporairement dans la PR #5, puis retirés de son historique avant fusion, ADR-014), dans
`data/reports/backtests/` : `s1_gran001_2015_2021_h0*` et `_h1*` (rapport, journal des décisions,
journal d'exécution, diff de lancement), `s1_gran001_vs_ref.json` et `s1_gran001_h1_vs_ref.json`
(comparaisons).

### 5.1 Contrôles

- H0 : 4 790 s, pic de mémoire 321 Mio. H1 : 4 859 s, 313 Mio (Mac M4).
- Journal des décisions de la variante : 10 912 lignes valides, distinctes et chronologiques, aux
  mêmes instants que la référence.
- Provenance relevée au lancement. L'empreinte du diff de lancement, calculée par la même méthode,
  concorde avec celle des rapports : H0 `da592e51…`, H1 concordante.
- H0 de la variante : 1 franchissement de stop possible mais non observable (vente de 0,05 contrat
  décidée le 2016-12-15 14:00 UTC), donc un passage H1 (`--policy ALL_TRIGGERED`). Aucun stop
  dépassé au premier tick d'exécution, donc aucun passage de rejet.
- H1 ne diffère de H0 que par cette transaction : stop de scénario le 2016-12-26 à −5,31 €, au lieu
  d'un stop observé le 2016-12-29 à −5,45 €, soit +0,15 €. Toutes les autres transactions sont
  identiques. Les chiffres ci-dessous sont ceux de H0 ; H1 est indiqué entre crochets quand il
  diffère.

### 5.2 Devenir des 215 refus de taille

| Action de la variante au même instant | Nombre |
|---|---|
| Entrée exécutée | 84 |
| Toujours refusée | 0 |
| Non évaluée : position déjà ouverte | 131 |
| Autre action (trajectoire modifiée) | 0 |

Les 84 entrées sont toutes clôturées : 21 gagnantes ; 48 sorties au canal et 36 stops ; tailles de
0,04 à 0,09 contrat. Ensemble, elles font −147,09 € nets [H1 −146,95 €], dont −117,61 € bruts et
29,48 € de coûts. Les 131 signaux non évalués tombent tous pendant une position ouverte issue de
l'une de ces 84 entrées.

### 5.3 Origine de l'écart de résultat net (−123,51 € [H1 −123,36 €])

| Transactions rapprochées (instant de décision et sens) | Nombre | Contribution à l'écart |
|---|---|---|
| Propres à la variante | 84 (les 84 entrées du §5.2) | −147,09 € [H1 −146,95 €] |
| Propres à la référence (absentes de la variante) | 5 | +24,69 € |
| Communes, effet du changement de taille | 48 | −1,10 € |
| **Total** | | **−123,51 €** [H1 −123,36 €] |

- Les 5 transactions propres à la référence se sont toutes terminées au stop (−24,69 € en tout).
  Dans la variante, une position ouverte par l'une des 84 entrées propres à la variante empêchait
  de les évaluer.
- Les 48 transactions communes ont la même sortie, au même instant et pour le même motif. 8 gardent
  la taille de 0,1 contrat, les autres passent de 0,09 à 0,16 contrat. Le dimensionnement plus fin
  pèse −1,10 € au total.

### 5.4 Effet pour le compte (2 000 € initiaux)

| | Référence (min. 0,1) | Variante (min. 0,01) H0 | Variante H1 |
|---|---|---|---|
| Transactions clôturées (gagnantes) | 53 (18) | 132 (39) | 132 (39) |
| Achats / ventes | 19 / 34 | 54 / 78 | 54 / 78 |
| Brut | +46,95 € | −45,62 € | −45,66 € |
| Coûts | 29,31 € | 60,26 € | 60,07 € |
| Net | **+17,63 €** | **−105,88 €** | **−105,73 €** |
| Fonds propres finaux | 2 017,63 € | 1 894,12 € | 1 894,27 € |
| Drawdown maximal au tick | 46,34 € (2018-08-15 → 2020-11-30) | 136,64 € (2015-05-01 → 2020-07-16) | 136,49 € |
| Dépassements du budget | 0 | 1 (0,008 €, entrée du 2021-11-05) | 1 |

Net par année de sortie (EUR) et drawdown au tick par année :

| Année | Réf. net | Var. net | Réf. drawdown | Var. drawdown |
|---|---|---|---|---|
| 2015 | 0,00 | −44,53 | 0,00 | 60,08 |
| 2016 | −3,71 | −24,89 [H1 −24,74] | 10,48 | 41,92 [H1 41,77] |
| 2017 | +10,59 | +4,18 | 29,13 | 39,83 |
| 2018 | +26,37 | −12,35 | 25,81 | 40,12 |
| 2019 | −20,75 | −28,79 | 26,23 | 40,43 |
| 2020 | +12,72 | +17,22 | 11,38 | 27,71 |
| 2021 | −7,58 | −16,73 | 23,29 | 28,45 |

Les transactions propres à la variante se concentrent sur 2015-2018 : 70 sur 84, pour −135,64 €.

### 5.5 Conclusion (2015-2021, ces hypothèses seulement)

Sur cette période et sous ces hypothèses (0,01 contrat non confirmé chez IG, coûts de recherche
par contrat, H0 / H1, « exécutée puis liquidée »), le minimum de 0,1 contrat **a protégé le compte**
plutôt qu'il n'a écarté des occasions rentables. Les signaux qu'il refusait perdent déjà avant
coûts (−117,61 € bruts sur 84 transactions). En les prenant, la variante occupe aussi la position
et perd 5 transactions de la référence, toutes perdantes, ce qui compense en partie. Le résultat
passe de +17,63 € à −105,88 €, et le drawdown au tick de 46 € à 137 €.

Ce résultat ne valide aucune règle et ne dit rien de 2022-2025, jamais lus. Il repose sur un seul
passage par hypothèse, sans test de significativité. Conformément au protocole, aucune autre
taille ni aucun autre budget n'est testé.
