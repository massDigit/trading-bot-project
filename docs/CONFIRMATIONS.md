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
| **DÉCL** | Communication officielle IG relayée par l'opérateur, non vérifiée par l'agent | Celle indiquée par l'opérateur |
| **OBS-R** | Valeur lue par l'agent dans la plateforme web du compte CFD **réel**, en lecture seule (aucun ordre saisi ni validé) | Réel, cet instrument, à l'instant indiqué ; **ni règle générale ni valeur historique** |
| **PUB** | Texte publié sur le site public d'IG France, consulté à la date indiquée | Celle du texte ; date de publication non indiquée sauf mention contraire ; non contractuel |
| **SUP** | Question posée au support IG, réponse attendue | Aucune valeur retenue tant que la réponse n'est pas reçue |

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

## 5. Compte RÉEL cible : contraintes déclarées par l'opérateur

Source : courriel officiel d'activation IG reçu par l'opérateur, rapporté le 2026-10-27. Le
numéro de compte, les liens personnalisés et le courriel lui-même ne sont pas conservés dans le
dépôt. Nature : **DÉCL** (communication officielle IG relayée par l'opérateur, non vérifiée par
l'agent).

| Contrainte | Contenu | Périmètre |
|---|---|---|
| Type de compte | CFD **à risque limité** | Compte réel de l'opérateur uniquement |
| Stop garanti | **Obligatoire sur chaque position** | idem |
| Modification du stop | Peut être rapproché ; **ne peut pas être éloigné** de son niveau initial | idem |
| Prime | Facturée **si le stop garanti est déclenché** | idem (cohérent avec la clause 13(6) de S4/S5, sous réserve de l'entité) |

Conséquences pour le projet :
- Pour le compte réel cible, tout dimensionnement doit utiliser les contraintes du **stop
  garanti** : distance minimale `minControlledRiskStopDistance` et prime `limitedRiskPremium`
  **du compte réel**. Au 2026-10-27, seules les valeurs démo étaient connues (5.0 et 1.2 POINTS,
  non transposables) ; des relevés du compte réel des 2026-11-08 et 2026-11-09 figurent au §6,
  avec leurs limites.
- Un stop technique plus proche que le minimum garanti applicable entraîne le **refus du
  signal** ; le stop n'est jamais élargi ni déplacé silencieusement.
- La règle « rapprocher sans éloigner » est compatible avec le cahier des charges (§7 : pas
  d'élargissement libre du stop).
- **La démo n'est pas présumée soumise aux mêmes restrictions** : elle est observée séparément.
- Le code actuel accepte `guaranteed_stop` comme paramètre ; le rendre obligatoire pour le
  compte réel est une tâche distincte, non réalisée (aucun contrôle d'exécution modifié).

## 6. Compte RÉEL : relevés de novembre 2026 (EUR/USD standard et Mini)

Relevés faits **en lecture seule** : aucun ordre saisi, validé ou modifié, aucun paramètre du
compte changé. Le numéro de compte, les jetons, les requêtes brutes et les conversations avec le
support ne sont pas conservés dans le dépôt. Aucune de ces valeurs n'entre dans `BrokerConventions`,
dans les paramètres de recherche ou dans les coûts simulés : leur usage relève d'une décision
distincte (décision sur les conditions IG, ouverte).

### 6.1 Observé dans la plateforme

| Réf. | Date et heure | Environnement | Source | Relevé par |
|---|---|---|---|---|
| R1 | 2026-11-08, **heure et fuseau non enregistrés** | Compte CFD réel, plateforme web | Fiche de marché EUR/USD Mini, marché fermé (dimanche) | Opérateur (DÉCL) |
| R2 | 2026-11-09, 09:24:46 à 09:25:05 UTC | Compte CFD réel, plateforme web | Onglet « Info » de la fiche EUR/USD, marché ouvert | Agent (OBS-R) |
| R3 | 2026-11-09, 09:27:23 UTC | idem | Onglet « Info » de la fiche EUR/USD Mini, marché ouvert | Agent (OBS-R) |
| R4 | 2026-11-09, 09:27:39 UTC | idem | Onglet « Ordre » (ticket) de la fiche EUR/USD Mini, affiché sans saisie | Agent (OBS-R) |
| R5 | 2026-11-09, entre 09:24 et 09:27 UTC | idem | EPIC lus dans les adresses des requêtes de la page ouvrant chaque fiche (aucune requête brute conservée) | Agent (OBS-R) |

Heures de R2 à R5 : horodatage UTC des instantanés locaux de la page, pris au moment de chaque
lecture (soit 10:24 à 10:27 à Paris, UTC+1). L'heure de R1 n'a pas été enregistrée ; elle
n'est pas reconstituée.

| Information | EUR/USD standard | EUR/USD Mini | Réf. |
|---|---|---|---|
| EPIC | `CS.D.EURUSD.CEF.IP` | `CS.D.EURUSD.CEFM.IP` | R5 |
| Valeur du contrat | EUR 100 000 | EUR 10 000 | R2, R3 |
| « Un point représente » | 0.0001 USD/EUR | 0.0001 USD/EUR | R2, R3 |
| Valeur d'un point | USD 10 | USD 1 ; ticket : « 1 contrat = 1,00 $US par point » | R2, R3, R4 |
| Quantité minimum | 0.01 | 0.01 ; ticket : « min : 0.01 » contrats | R2, R3, R4 |
| Distance minimum du stop (normal) | 2 | 2 | R2, R3 |
| Distance minimum du stop garanti | 5 | 5 ; ticket : « min : 5 », champ « distance en pts » | R2, R3, R4 |
| Type de stop proposé par défaut sur le ticket | non relevé | « Garanti » | R4 |
| Facteur de slippage | 50.0 % (sens non documenté) | 50.0 % (sens non documenté) | R2, R3 |
| Couverture | 3,33 % sur les paliers 1 à 3, 6 % au-delà de 462,4 (colonne « Valeur de la position (Contracts - USD) », unité ambiguë) | non relevé | R2 |
| Spread affiché | non relevé | 1,3 à l'instant de R4 (valeur instantanée) | R4 |
| Swap indicatif | 0 / -0, « pas mis à jour en temps réel » | non relevé | R2 |
| Relevé du dimanche (marché fermé) | non relevé | Quantité minimum 0,01 ; stop garanti minimum **5 % du cours** ; stop normal minimum 10 points ; prime 1,2 | R1 |

**Limites.**
- Les fiches R2 et R3 n'affichent pas d'unité pour les distances. Seul le ticket Mini (R4)
  indique « distance en pts » pour le stop garanti. L'unité du stop normal et celle de la fiche
  standard ne sont pas affichées.
- Le dimanche (R1) et le lundi (R2 à R4) donnent 5 % puis 5 points pour le stop garanti, et 10
  puis 2 points pour le stop normal. Deux relevés **ne suffisent pas à établir la règle** de
  changement de valeur ou d'unité, ni ses conditions (fermeture, week-end, volatilité) : la
  question est posée au support (§6.3).
- Un minimum de 5 points **ne démontre pas l'absence de blocage** pour nos stratégies. Certains
  stops techniques peuvent être plus proches que ce minimum, et le prix depuis lequel IG mesure
  la distance reste à confirmer (§2, ambiguïté « Référence des distances minimales »).
- La quantité minimum de 0,01 Mini (réel) diffère de `minDealSize` = 0,1 observé en démo le
  2026-10-27 (O1). Elle **ne confirme ni le pas de taille** au-delà du minimum, **ni la cause
  de l'écart** avec la démo (compte, date, réglage ou autre).
- La correspondance EPIC / fiche est établie par les requêtes émises à l'ouverture de chaque
  fiche, et par le nom « EUR/USD Mini » affiché sur la seconde. Elle n'est pas confirmée par un
  champ de la fiche.
- Chaque valeur vaut pour l'instant du relevé. Aucune n'est transposée à la démo, à une autre
  date ou à 2015-2021.

### 6.2 Publié par IG (site public, consulté le 2026-11-08 entre 11:04 et 11:05 UTC)

Ces textes sont généraux et non contractuels ; ils ne remplacent pas S4 ou S5.

**Dates affichées.** Complément du 2026-11-09, de 12:14:58 à 12:15:13 UTC, nouvelle lecture des
cinq pages :
- **P2, P3, P4, P5** affichent « 20 septembre 2026 » (élément de date placé sous le titre de
  l'article). La même date figurait déjà dans les instantanés de la consultation initiale du
  2026-11-08. Elle n'est **pas assimilée** à une date de publication, de mise à jour ou d'entrée
  en vigueur : la page ne dit pas ce qu'elle représente.
- **P1** n'affiche pas de date propre. Elle cite une période pour ses spreads moyens (12
  semaines jusqu'au 29 mai 2020) et la date d'entrée en vigueur de MiFID II (3 janvier 2018) ;
  aucune des deux ne date les frais publiés.

| Réf. | Page |
|---|---|
| P1 | « Frais et commissions » — https://www.ig.com/fr/frais-et-commissions |
| P2 | « Pourquoi dois-je ajouter un stop garanti à chacune de mes positions ? » — https://www.ig.com/fr/portail-d-aide/articles/839593-pourquoi-dois-je-ajouter-un-stop-garanti-a-chacune-de-mes-positions |
| P3 | « Combien coûte un stop garanti ? » — https://www.ig.com/fr/portail-d-aide/articles/839598-combien-coute-un-stop-garanti |
| P4 | « Pourquoi ma position a-t-elle été clôturée ? » — https://www.ig.com/fr/portail-d-aide/articles/839588-pourquoi-ma-position-a-t-elle-ete-cloturee |
| P5 | « Comment sont calculés les coûts associés à l'ouverture d'un contrat sur forex ? » — https://www.ig.com/fr/portail-d-aide/articles/839581-comment-sont-calcules-les-couts-associes-a-l-ouverture-d-un-contrat-sur-forex |

| Sujet | Contenu publié | Réf. |
|---|---|---|
| Compte à risque limité | « Par défaut, tout nouveau client IG dispose d'un compte risque limité », chaque position « devant obligatoirement disposer d'un stop garanti » | P2 |
| Prime du stop garanti | Débitée « que si votre stop est déclenché » ; coût affiché sur le ticket ; « susceptible d'évoluer, particulièrement à l'approche du weekend et lorsque les conditions de marché sont volatiles » | P3, P1 |
| Exécution des stops | Stop normal : ordre au marché, slippage négatif possible ; stop garanti : clôture au niveau du stop | P4 |
| Conversion | Instantanée par défaut, ou quotidienne, hebdomadaire ou mensuelle au choix ; « Le coût de conversion standard est de 0,8% » ; le résultat est converti après prise en compte des frais de financement, commissions et dividendes | P1 |
| Financement forex | « nombre de nuits x (taux tom-next + frais administratifs annuels) x taille de l'ordre » ; frais administratifs « actuellement » de 1 % ; facturé après la fermeture de session, « ordinairement 23h00 heure de Paris » | P1 |
| Financement forex (aide) | « Taille x (taux tom-next + charge administrative) », taille = nombre de lots × valeur d'un lot ; charge administrative « ne dépasse pas 0,0022% par jour » ; « trois jours les mercredis » | P5 |

P1 (1 % par an) et P5 (au plus 0,0022 % par jour, soit environ 0,80 % sur 365 jours) ne donnent
pas la même valeur : l'écart n'est pas tranché (question au §6.3).

### 6.3 En attente du support (SUP)

Questions envoyées par le chat le 2026-11-09 vers 09:28 UTC, transmises à un conseiller ; aucune
réponse reçue à la rédaction. Le 2026-11-08, l'agent automatique du chat a seulement estimé que
les 5 % reflétaient « probablement » le marché fermé, et indiqué que ses sources ne précisaient ni
le pas de taille ni le côté de déclenchement : ce n'est pas une confirmation.

| Question | État |
|---|---|
| Pas de taille au-delà de 0,01 contrat (Mini et standard), identique ou non en réel et en démo | SUP |
| Règle du minimum du stop garanti : valeur, unité (points ou %), conditions de passage en % | SUP |
| Côté de déclenchement des stops (bid / ask) sur le compte réel | SUP ; documenté par S4/S5 sous réserve de l'entité (§4) |
| Prix depuis lequel les distances minimales sont mesurées | SUP |
| Minimums et prime applicables entre 2015 et 2021 | SUP |
| Taux de conversion appliqué (cours, côté) et assiette exacte des 0,8 % | Non encore posée |
| Frais administratifs du financement forex : 1 % par an (P1) ou au plus 0,0022 % par jour (P5), base de calcul (jours par an) et unités du tom-next, de la taille et des frais | Non encore posée |
| Heure effective du financement pendant les semaines où les changements d'heure européen et américain ne coïncident pas (« ordinairement 23h00 heure de Paris », P1) | Non encore posée |

### 6.4 Supposé pour 2015-2021

Aucune valeur de ce paragraphe n'a été observée ni publiée pour 2015-2021. Les études
historiques restent fondées sur les hypothèses du projet : taille minimale et incrément de 0,1
(ASSUMP-004/005), aucune distance minimale de stop du courtier appliquée en backtest, coûts du
scénario `RESEARCH_COSTS` (ASSUMP-006), déclenchement selon ASSUMP-008. Une valeur relevée ou
publiée en 2026 **n'est pas appliquée rétroactivement** à 2015-2021 sans décision explicite.

## 7. Rapprochement des coûts simulés avec les sources IG (aucun paramètre modifié)

Scénario simulé : `RESEARCH_COSTS` (`backtest/explore.py`), appliqué à la clôture par
`_settle` (`backtest/engine.py`). Sources IG : P1 et P5 (§6.2), consultées le 2026-11-08 et
relues le 2026-11-09 (P1 sans date propre ; P5 affiche « 20 septembre 2026 », non assimilée à
une date de publication ou d'entrée en vigueur).

### 7.1 Conversion

| Élément | Simulé | Publié par IG | Écart ou inconnue |
|---|---|---|---|
| Taux | 0,5 % (ASSUMED) | « coût de conversion standard » 0,8 % | Écart de 0,3 point |
| Assiette | Valeur absolue du résultat net de la transaction en EUR, après glissement, commission, financement et prime | Résultat de l'opération, converti après prise en compte du financement, des commissions et des dividendes | Proche ; nature exacte des 0,8 % (pourcentage du montant ou majoration du cours) non précisée |
| Sens | Gains et pertes | Non précisé | À confirmer |
| Cours | 1/bid pour un résultat négatif, 1/ask pour un résultat positif (convention défavorable du projet) | Non précisé | À confirmer |
| Moment | À chaque clôture | Instantané par défaut ; quotidien, hebdomadaire ou mensuel au choix | Cohérent avec le réglage par défaut |

### 7.2 Financement overnight

| Élément | Simulé | Publié par IG | Écart ou inconnue |
|---|---|---|---|
| Formule | 1 USD × contrats Mini × nuits, toujours un coût (ASSUMED) | Transcription des sources, **pas encore une formule implémentable** : « nombre de nuits x (taux tom-next + frais administratifs annuels) x taille de l'ordre » (P1) ; « Taille x (taux tom-next + charge administrative) » (P5) | Les unités du tom-next (points, taux ou montant), de la taille et des frais administratifs (annuels ou journaliers) doivent être rendues compatibles avant tout calcul ; non confirmées |
| Taux | Forfait de 1 USD par contrat Mini et par nuit | Tom-next (selon le marché, crédit ou débit selon le sens) + frais administratifs de 1 % par an (P1) ou au plus 0,0022 % par jour (P5) | Différence certaine : forfait fixe simulé contre taux variables ; tom-next 2015-2021 inconnu |
| Dépendance à la taille | Proportionnel au nombre de contrats | Proportionnel à la « taille » (P5 : nombre de lots × valeur d'un lot) | Les deux calculs dépendent de la taille de position ; la conversion exacte entre contrats, valeur d'un lot et devise du montant reste à confirmer |
| Sens | Toujours débité | Tom-next : débit ou crédit selon le sens ; frais administratifs : débit | Le crédit n'est pas simulé |
| Heure | Changement de journée de négociation à 17:00 New York (`trading_day`) | Après la fermeture de session, « ordinairement 23h00 heure de Paris » | Calcul des fuseaux : 17:00 New York correspond à 23:00 Paris, et à 22:00 Paris pendant les semaines où les changements d'heure européen et américain ne coïncident pas. « Ordinairement » ne suffit pas à établir la règle effective d'IG pendant ces semaines (question au §6.3) |
| Jours | Une nuit par journée de négociation franchie ; un passage du vendredi au lundi compte 3 nuits | Une nuit par jour, **triple le mercredi** | Calendriers différents, notamment pour une position présente le mercredi soir ou détenue pendant le week-end. Au mieux, pour une position constante sur une semaine ordinaire, les deux conventions peuvent couvrir le même nombre de jours de financement, selon le calendrier applicable (jours fériés compris) ; cela ne démontre **aucune égalité des montants**, le forfait simulé restant différent du tom-next et des frais administratifs |

**Ordre de grandeur, à titre indicatif (CALC, non appliqué).** Calcul illustratif qui suppose,
sans confirmation d'IG, que la « taille » est la valeur notionnelle en USD et que le taux annuel
se répartit sur une **base de 365 jours** (choix de l'illustration, pas une convention IG
confirmée). Pour 1 contrat Mini à un cours de 1,12 (notionnel d'environ 11 200 USD), les frais
administratifs seuls représentent alors environ 0,31 USD par nuit à 1 % par an (11 200 × 1 % /
365), et au plus 0,25 USD à 0,0022 % par jour. S'y ajoute le tom-next, de signe et de montant
inconnus pour 2015-2021. Ce calcul ne dit donc pas si le forfait de 1 USD majore ou minore le coût
réel.

**Portée.** Le rapprochement décrit des formules ; il ne modifie ni le moteur, ni les paramètres,
ni les coûts. Les valeurs publiées en 2026 ne sont pas appliquées à 2015-2021 sans décision
explicite. Le choix des hypothèses de l'étude attend la réponse du support et la décision sur les
conditions IG.

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
- Profil « compte réel à risque limité » : stop garanti obligatoire, interdiction d'éloigner le
  stop, prime au déclenchement ; contraintes du compte réel à observer séparément de la démo.
