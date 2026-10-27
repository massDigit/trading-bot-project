# CONFIRMATIONS.md - Registre des conventions courtier

> Contrat concerné : `CS.D.EURUSD.CEFM.IP` (EUR/USD Mini), sauf mention contraire.
> Une valeur n'entre dans `BrokerConventions` (`src/forex_bot/instruments.py`) que sous la forme
> d'une `Confirmation(value, source, confirmed_on, epic)`, après validation de l'opérateur dans une
> PR dédiée. Ce registre ne modifie aucun contrôle d'exécution.

## Nature des informations

| Code | Nature | Portée |
|---|---|---|
| **DOC** | Définition documentée par une source officielle IG | Celle de la source (API, entité, produit) |
| **OBS** | Valeur observée sur notre compte CFD démo | Démo uniquement, à la date indiquée ; **jamais généralisée au réel** |
| **CALC** | Calcul de cohérence entre valeurs observées | Ne prouve pas la signification d'un champ |
| **HYP** | Hypothèse ou ambiguïté non levée | Le code bloque ce qui en dépend |

Une documentation officielle explicite et applicable à notre compte suffit à confirmer une
convention ; une réponse du support n'est nécessaire que pour les ambiguïtés restantes.

## Sources consultées le 2026-10-27

| Réf. | Source | Version / date | Périmètre |
|---|---|---|---|
| S1 | IG Labs, `GET /markets/{epic}` — https://labs.ig.com/reference/markets-epic.html | API v3 (utilisée par le projet) ; v4 existe | API REST IG, toutes entités |
| S2 | IG Labs, Streaming API Reference — https://labs.ig.com/streaming-api-reference.html | non datée | Flux Lightstreamer IG |
| S3 | IG Labs, `POST /positions/otc` — https://labs.ig.com/reference/positions-otc.html | API v2 | API REST IG (lu, jamais appelé) |
| S4 | IG Europe GmbH, *Conditions Générales de Vente et de Fonctionnement des Comptes CFD* (FR) | juin 2026 | Comptes CFD d'IG Europe GmbH (y compris IG Europe France) |
| S5 | IG Europe GmbH, *Margin Trading Customer Agreement* (EN) | février 2025 | Comptes CFD d'IG Europe GmbH |
| S6 | tastyfx LLC (ex-IG US), *Customer Agreement* — lien `igCompany=igus` | août 2026 | **Autre entité (États-Unis), FX au comptant** : non applicable à notre compte |
| O1 | Réponse `GET /markets/CS.D.EURUSD.CEFM.IP` v3 sur notre démo | 2026-10-27 | Démo, ce contrat |
| O2 | Sonde `ig-price-probe` (flux `PRICE`) sur notre démo | 2026-10-27, 4 exécutions | Démo, ce contrat |
| O3 | Réponse `POST /session` v2 sur notre démo | 2026-10-27 | Démo |

**Entité de notre compte : NON DÉTERMINÉE.** L'API ne l'indique pas, et elle n'est pas déduite de
la langue du site. S4 et S5 ne s'appliquent que si l'opérateur constate, dans les documents
contractuels de son espace client, que son compte relève d'IG Europe GmbH. Les conditions d'un
compte démo peuvent par ailleurs différer de celles du compte réel.

## 1. Unité de taille et contrat

| Information | Nature | Contenu | Source |
|---|---|---|---|
| `instrument.unit` | DOC | « Unit used to qualify the size of a trade » ; valeurs `AMOUNT`, `CONTRACTS`, `SHARES` | S1 (v3) |
| `instrument.unit` | OBS | `CONTRACTS` | O1 |
| `instrument.contractSize` | DOC | « Contract size » (sans unité ni devise précisées) | S1 (v3) |
| `instrument.contractSize` | OBS | `"10000"` | O1 |
| `instrument.lotSize` | DOC / OBS | « Lot size » / `1.0` (rôle non décrit) | S1 / O1 |
| `instrument.onePipMeans` | DOC / OBS | « Meaning of one pip » / `"0.0001 USD/EUR"` | S1 / O1 |
| `instrument.valueOfOnePip` | DOC / OBS | « Value of one pip » / `"1.00"` (devise non précisée par le champ) | S1 / O1 |
| Valeur du pip par contrat | CALC | 10 000 EUR × 0,0001 USD/EUR = 1 USD = `valueOfOnePip` : cohérent si `contractSize` est exprimé en EUR (devise de base) et `valueOfOnePip` en USD | O1 |
| `size` d'une position | DOC | « Deal size », au plus 12 décimales ; aucune unité indiquée | S3 (v2) |
| Unité de `contractSize` | HYP | Interprétation : 10000 unités de la devise de base (EUR). Appuyée par le CALC ci-dessus et par `onePipMeans` exprimé en USD/EUR ; **aucune source IG ne définit l'unité de `contractSize`** (S1 : « Contract size »). | CALC sur O1 ; question 1 du support |

**Portée de la conclusion.** Pour ce contrat, sur notre démo et en API v3, la taille d'une
transaction est qualifiée en **contrats** (`unit = CONTRACTS`, définition S1).
`contractSize` observé = 10000 ; son interprétation en EUR de base est explicitée et sourcée
séparément (ligne « Unité de `contractSize` », statut HYP). Cela ne vaut pas pour le réel ni
pour un autre epic sans nouvelle observation, et cela ne dit rien de la taille minimale ni de
l'incrément.

> Le calcul de la perte (`risk.py`) utilise déjà `contract_size` = 10000 comme nombre d'unités de
> devise de base par contrat. Ce choix repose sur l'interprétation HYP ci-dessus ;
> `verify_contract` en contrôle la cohérence (pip × `contractSize` = `valueOfOnePip`), sans la
> prouver.

| Ambiguïté | Nature | Détail |
|---|---|---|
| Étiquette `POINTS` de `minDealSize` | HYP | `minDealSize` = {unit `POINTS`, value 0.1} (O1) ; S1 ne décrit le champ que comme « Dealing rule » et l'unité `POINTS` que comme « dimension for a dealing rule value ». `instrument.unit` ne suffit pas à l'expliquer. |

## 2. Taille minimale, incrément, distances

| Information | Nature | Contenu | Source |
|---|---|---|---|
| `minDealSize` | OBS | {unit `POINTS`, value 0.1} | O1 |
| `minStepDistance` | DOC / OBS | « Dealing rule » / {`POINTS`, 5.0} | S1 / O1 |
| `minNormalStopOrLimitDistance` | DOC / OBS | « Dealing rule » / {`POINTS`, 2.0} | S1 / O1 |
| `minControlledRiskStopDistance` | DOC / OBS | « Dealing rule » / {`POINTS`, 5.0} | S1 / O1 |
| `controlledRiskSpacing` | DOC / OBS | « Dealing rule » / {`POINTS`, 20.0} | S1 / O1 |
| `maxStopOrLimitDistance` | DOC / OBS | « Dealing rule » / {`PERCENTAGE`, 75.0} | S1 / O1 |
| `snapshot.scalingFactor` | DOC | « Multiplying factor to determine actual pip value for the levels used by the instrument » | S1 (v3 et v4) |
| `snapshot.scalingFactor` | OBS | `10000` ; `decimalPlacesFactor` = 5 | O1 |
| Rapport `scalingFactor` / pip | CALC | 1 / 10 000 = 0,0001 = taille du pip (`onePipMeans`) | O1 |
| `instrument.controlledRiskAllowed` | DOC / OBS | « True if controlled risk trades are allowed » / `true` | S1 (v3, absent en v4) / O1 |
| `instrument.limitedRiskPremium` | DOC / OBS | « The limited risk premium » / {`POINTS`, 1.2} | S1 / O1 |
| Prime de stop garanti | DOC | « Limited Risk Premium […] as set out in the Product Details » (clause 13(6)) | S5 (FR : S4, 13(6), « Coût du Stop garanti ») |
| `trailingStopIncrement` | DOC | « increment step in pips for the trailing stop » (seule mention d'une unité de distance) | S3 |

| Ambiguïté | Nature | Détail |
|---|---|---|
| Interprétation de `minDealSize` = 0.1 « POINTS » | HYP | 0,1 contrat ? Unité non documentée. |
| Incrément de taille autorisé | HYP | Aucun champ dédié. `minStepDistance` **n'est pas** considéré comme un incrément de taille : S1 ne dit rien de son objet. |
| Rapport point IG / pip | HYP | Le CALC sur `scalingFactor` est compatible avec 1 point = 1 pip pour ce contrat, mais aucune source ne définit le point des `dealingRules` : ce n'est pas une confirmation. |
| Référence des distances minimales (stop normal, stop garanti) | HYP | Ni S1, ni S4, ni S5 n'indiquent depuis quel prix la distance est mesurée. |
| Sens de `minStepDistance` et `controlledRiskSpacing` | HYP | Décrits seulement comme « Dealing rule ». |
| Montant de la prime de stop garanti | HYP | 1.2 « POINTS » observé ; sa valeur monétaire dépend du rapport point/pip et des « Product Details ». |

## 3. Flux `PRICE`

| Information | Nature | Contenu | Source |
|---|---|---|---|
| `TIMESTAMP` | DOC | « The timestamp in UTC millis » | S2 |
| `DELAY` | DOC | « Delayed price flag (0=false, 1=true) » | S2 |
| `DLG_FLAG` | DOC | `"CLOSED "`, `"CALL "`, `"DEAL "`, `"EDIT "`, `"CLOSINGSONLY "`, `"DEALNOEDIT "`, `"AUCTION "`, `"AUCTIONNOEDIT"`, `"SUSPEND "` : valeurs listées avec espaces finaux, sans définition | S2 |
| `MARKET:{epic}` | DOC | Fin de vie annoncée ; non utilisé | S2 |
| `TIMESTAMP` | OBS | Présent dans chaque mise à jour ; aucune hors ordre | O2 |
| `DLG_FLAG` | OBS | `"DEAL"` complété d'espaces, comme dans la liste documentée | O2 |
| `DELAY` | OBS | Demandé, jamais reçu avec une valeur | O2 |
| `snapshot.delayTime` (REST) | DOC / OBS | « Price delay » / `0` | S1 / O1 |
| `reroutingEnvironment` | OBS | Présent mais vide | O3 |

| Ambiguïté | Nature | Détail |
|---|---|---|
| Absence de `DELAY` | HYP | S2 ne dit pas ce qu'elle signifie. `snapshot.delayTime = 0` (REST) ne s'applique pas explicitement au flux. **Le blocage est maintenu** (ASSUMP-013). |
| Événement horodaté par `TIMESTAMP` | HYP | « The timestamp in UTC millis » : production du prix ou publication du message ? |
| Opérations permises par chaque `DLG_FLAG` | HYP | Seul `DEAL` est traité comme négociable (ASSUMP-012), y compris face à `DEALNOEDIT`. |

## 4. Déclenchement des stops

| Information | Nature | Contenu | Source |
|---|---|---|---|
| Ordre stop | DOC | « Your Stop Order will be triggered if our bid price (in the case of an Order to Sell) or our offer price (in the case of an Order to Buy) moves against you to a point that is at or beyond the level specified by you » (clause 12(1)(a)) | S5 ; S4 12(1)(a) en français |
| Stop garanti | DOC | « Your agreed stop level will be triggered when our bid price (in the case of an order to Sell) or our offer price (in the case of an order to Buy) moves against you » (clause 13(3)) | S5 ; S4 13(3) |
| Cours de clôture | DOC | Clôture d'un Achat au « chiffre le plus bas », d'une Vente au « chiffre le plus élevé » (clause 7(2)) | S4 |
| Règle équivalente IG US | DOC | Clause 9(1)(a) : bid pour un ordre de vente, ask pour un ordre d'achat | S6, **non applicable** (autre entité, autre produit) |
| Traduction française | Note | S4 traduit *bid price* par « cours vendeur » et *offer price* par « cours acheteur » ; la version anglaise S5 et la clause 7(2) lèvent l'ambiguïté du vocabulaire. | S4 / S5 |

**Portée.** Si notre compte relève d'IG Europe GmbH, la convention implémentée par le projet
(stop d'une position acheteuse déclenché par le bid, d'une position vendeuse par l'offer) est
documentée pour les stops normaux et garantis, sous réserve des exceptions des clauses 12 et 13
(réglementation, actions du carnet d'ordres, périodes d'enchères). L'entité n'est pas déterminée
(voir plus haut), et rien n'est confirmé pour le réel tant que les documents acceptés par
l'opérateur ne sont pas identifiés.

## Propositions de levée de blocage (non activées)

Aucune n'est appliquée dans le code. Chacune exige une décision explicite de l'opérateur et une PR
dédiée.

| Convention | Proposition | Justification documentaire | Limites | Statut |
|---|---|---|---|---|
| `stop_trigger_side` | `EXIT_SIDE` | S4/S5, clauses 12(1)(a) et 13(3) d'IG Europe GmbH | Applicable seulement si l'entité du compte et la version des conditions sont vérifiées par l'opérateur | **Non confirmé pour notre compte** — en attente de cette vérification |
| `contracts_per_size_unit` | 1 | S1 (v3) : `instrument.unit` qualifie la taille ; O1 : `CONTRACTS` | Définition sommaire ; démo et ce contrat uniquement ; ne lève ni la taille minimale ni l'incrément | Proposée, **non activée** |

## Tâches distinctes (hors de ce lot documentaire)

- Renforcer `verify_contract` pour contrôler aussi `instrument.unit = CONTRACTS`,
  `snapshot.scalingFactor` (10000) et `instrument.controlledRiskAllowed` (`true`) : contrôles
  supplémentaires uniquement, sans levée de blocage, dans une modification de code séparée.
