# CONFIRMATIONS.md - Registre des conventions courtier

> Chaque ligne indique le contrat concerné, son statut, sa source et sa date.
> Une valeur ne peut entrer dans `BrokerConventions` (`src/forex_bot/instruments.py`) que sous la
> forme d'une `Confirmation(value, source, confirmed_on, epic)`, et seulement si elle est `CONFIRMÉ`.

Statuts :
- **CONFIRMÉ** : affirmé par une source IG identifiée (documentation officielle, réponse écrite du support).
- **OBSERVÉ** : valeur renvoyée par l'API démo ; c'est un fait sur la réponse, pas sur sa signification.
- **DÉDUIT** : conclusion du projet à partir d'observations ; jamais traitée comme confirmée.
- **NON CONFIRMÉ** : inconnu ; le code bloque.

Contrat : `CS.D.EURUSD.CEFM.IP` (EUR/USD Mini), compte CFD démo, sauf mention contraire.

| Sujet | Statut | Valeur | Source | Date |
|---|---|---|---|---|
| Taille de contrat | OBSERVÉ | 10 000 EUR (`contractSize`) | `GET /markets/{epic}` v3, démo | 2026-10-27 |
| Pip | OBSERVÉ | 0,0001 (`onePipMeans` = "0.0001 USD/EUR") | idem | 2026-10-27 |
| Valeur du pip pour 1 contrat | OBSERVÉ | 1,00 USD (`valueOfOnePip`), cohérent avec 0,0001 × 10 000 | idem | 2026-10-27 |
| Distance min. stop normal | OBSERVÉ | 2.0 POINTS (`minNormalStopOrLimitDistance`) | idem | 2026-10-27 |
| Distance min. stop garanti | OBSERVÉ | 5.0 POINTS (`minControlledRiskStopDistance`) | idem | 2026-10-27 |
| Rapport point IG / pip | NON CONFIRMÉ | — | question 1 du support | — |
| Rapport unité de taille / contrat | NON CONFIRMÉ | — | question 2 du support | — |
| Taille minimale | NON CONFIRMÉ | `minDealSize` = 0.1 « POINTS » observé, unité non comprise | question 3 du support | — |
| Incrément de taille | NON CONFIRMÉ | aucun champ dédié ; `minStepDistance` non interprété | question 3 du support | — |
| Côté de déclenchement des stops | NON CONFIRMÉ | hypothèse ASSUMP-008 : bid (achat) / offer (vente) | question 4 du support | — |
| Référence distance min. stop normal | NON CONFIRMÉ | hypothèse ASSUMP-008 : prix de sortie courant | question 5 du support | — |
| Référence distance min. stop garanti | NON CONFIRMÉ | — | question 5 du support | — |
| Flux `PRICE` : `TIMESTAMP` | CONFIRMÉ (définition) | « Update time in UTC milliseconds » | IG Labs, Streaming API Reference | 2026-10-27 |
| Flux `PRICE` : `TIMESTAMP` reçu sur la démo | OBSERVÉ | présent à chaque mise à jour (sonde `ig-price-probe`) | sonde démo | 2026-10-27 |
| Flux `PRICE` : `DLG_FLAG` | OBSERVÉ | `"DEAL"` suivi d'espaces ; signification non définie (ASSUMP-012) | sonde démo ; question 6 | 2026-10-27 |
| Flux `PRICE` : `DELAY` | OBSERVÉ | jamais renseigné sur la démo (ASSUMP-013) | sonde démo ; question 6 | 2026-10-27 |
| Abonnement `MARKET` | CONFIRMÉ | fin de vie annoncée par IG ; non utilisé | IG Labs, Streaming API Reference | 2026-10-27 |
| `reroutingEnvironment` | OBSERVÉ | champ présent mais vide sur la démo | `POST /session` v2, démo | 2026-10-27 |

Aucune convention n'est confirmée pour le compte réel.
