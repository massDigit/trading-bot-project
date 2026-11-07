# DAY_01 — disponibilité des données (rapport agrégé)

Fenêtre : 2015-01-01T00:00:00+00:00 → 2022-01-01T00:00:00+00:00. Aucun tick lu, aucune exécution.

| Contrôle | Conforme | Écarts |
|---|---|---:|
| C1 | oui | 0 |
| C2 | oui | 0 |
| C3 | oui | 0 |
| C4 | oui | 0 |
| C5 | oui | 0 |
| C6 | oui | 0 |
| C7 | oui | 0 |
| C8 | oui | 0 |
| C9 | oui | 0 |
| C10 | oui | 0 |

## Entonnoir M5 (total)

| Étape | Entrées (dénominateur) | Issue | Nombre | % des entrées |
|---|---:|---|---:|---:|
| jours_ouvrés | 1827 | PAS_DE_SÉANCE | 11 | 0,602 % |
| séances_attendues | 1816 | RANGE_INCOMPLET | 3 | 0,165 % |
| ranges_complets | 1813 | ATR_NON_CALCULABLE | 49 | 2,703 % |
| ranges_avec_atr | 1764 | RANGE_TROP_ÉTROIT | 36 | 2,041 % |
| ranges_avec_atr | 1764 | RANGE_TROP_LARGE | 31 | 1,757 % |
| ranges_admissibles | 1697 | DONNÉES_CASSURE | 0 | 0,000 % |
| ranges_admissibles | 1697 | AUCUNE_CASSURE | 493 | 29,051 % |
| cassures | 1204 | DONNÉES_RETEST | 0 | 0,000 % |
| cassures | 1204 | INVALIDATION_AVANT_CONTACT | 19 | 1,578 % |
| cassures | 1204 | INVALIDATION_APRÈS_CONTACT | 39 | 3,239 % |
| cassures | 1204 | DÉLAI_SANS_CONTACT | 314 | 26,080 % |
| cassures | 1204 | DÉLAI_CONTACT_SANS_CONFIRMATION | 1 | 0,083 % |
| confirmations | 831 | CONFIRMATION | 831 | |

## Entonnoir M15 (total)

| Étape | Entrées (dénominateur) | Issue | Nombre | % des entrées |
|---|---:|---|---:|---:|
| jours_ouvrés | 1827 | PAS_DE_SÉANCE | 11 | 0,602 % |
| séances_attendues | 1816 | RANGE_INCOMPLET | 3 | 0,165 % |
| ranges_complets | 1813 | ATR_NON_CALCULABLE | 49 | 2,703 % |
| ranges_avec_atr | 1764 | RANGE_TROP_ÉTROIT | 36 | 2,041 % |
| ranges_avec_atr | 1764 | RANGE_TROP_LARGE | 31 | 1,757 % |
| ranges_admissibles | 1697 | DONNÉES_CASSURE | 0 | 0,000 % |
| ranges_admissibles | 1697 | AUCUNE_CASSURE | 493 | 29,051 % |
| cassures | 1204 | DONNÉES_RETEST | 0 | 0,000 % |
| cassures | 1204 | INVALIDATION_AVANT_CONTACT | 81 | 6,728 % |
| cassures | 1204 | INVALIDATION_APRÈS_CONTACT | 67 | 5,565 % |
| cassures | 1204 | DÉLAI_SANS_CONTACT | 314 | 26,080 % |
| cassures | 1204 | DÉLAI_CONTACT_SANS_CONFIRMATION | 6 | 0,498 % |
| confirmations | 736 | CONFIRMATION | 736 | |

une confirmation est un instant D où une entrée sera évaluée, pas une entrée
