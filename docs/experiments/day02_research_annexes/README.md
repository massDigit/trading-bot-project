# Annexes de recherche DAY_02 (2015-2021)

Copies archivées, versionnées pour relecture et analyse, de fichiers produits hors Git sous
`data/reports/` (dossier exclu par `.gitignore`). Synthèse : `../DAY02_PROGRAM_BILAN.md`.

## Contenu

| Dossier | Origine | Contenu |
|---|---|---|
| `trades/` | rapports de passage `perf_*_m5_a.json` et CSV des ventes de matinée | une ligne par transaction : instants, sens, taille, motif de sortie, net €, risque €, R ; **sans prix de marché** |
| `frequency_lot/` | `data/reports/backtests/day02_frequency/` | scripts de lancement et de lecture du lot ADR-039 (`bilan.py`, `e3_decomp.py`, `trunc_check.py`, `align_gbp.py`, `*.sh`) et leurs sorties (`bilan.json`, `e3_decomp.json`, `gbp_alignment.json`) |
| `guides_screening/` | `data/reports/backtests/day02_guides/` | criblage des guides FX Replay sur les entrées LATE : pré-enregistrement, bilan, effets des filtres, scripts |
| `cost_wall/` | `data/reports/research/cost_wall/` | mesure descriptive du « mur des coûts » : protocole, script, résultats |
| `atlas/` | `data/reports/research/atlas/` | atlas des régularités horaires EUR/USD 2015-2019 : protocole, résultats, script |
| `morning_short_eurusd/` | `data/reports/research/morning_short/` | vente de matinée EUR/USD : protocole, variante principale fixée avant vérification, résultats, script |
| `morning_short_gbpusd/` | `data/reports/research/morning_short_gbpusd/` | même règle sur GBP/USD : protocole, résultats, script |
| `export_trades.py` | — | régénère `trades/` depuis les rapports locaux |

Chaque fichier `day02_<CONFIG>.csv` contient les transactions d'une configuration : `REF`, `H1` à
`H1H2H3`, `LATE`, `PROT`, `PART`, `FULL`, `G1A`, `G5B`, `G1A5B`, `E3`, `F2R`, `RSC`, `M5S`, `SMTF`, `SMTT`.
`R` = `net_eur / risk_eur`, où `risk_eur` est la perte estimée au stop à la décision.
`MS_<PAIRE>_S<stop>.csv` : ventes de matinée, une transaction par jour ouvré.

## Limites

- **Données de marché non incluses** : ticks et bougies Dukascopy (licence non résolue, ASSUMP-018), et
  rapports détaillés par séance (plusieurs centaines de Mo). Les scripts ne peuvent donc être
  relancés qu'avec ces données sur le poste de l'opérateur.
- Les scripts sont des **copies** : leurs chemins sont ceux de leur emplacement d'origine sous
  `data/reports/` (les chemins absolus du poste ont été remplacés par la racine du dépôt). Ils ne sont
  ni testés ni vérifiés par `ruff` ou `mypy`, qui ne couvrent que `src/` et `tests/`.
- Tout est exploratoire, sur des années déjà examinées ; 2022-2025 non lues ; rien n'est validé.
