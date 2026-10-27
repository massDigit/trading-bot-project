# API.md - API externes consommées

## IG REST Trading API — démo, lecture seule

Source : référence officielle IG Labs, consultée le 2026-10-27
(https://labs.ig.com/rest-trading-api-reference.html, https://labs.ig.com/rest-trading-api-guide.html).

Base : `https://demo-api.ig.com/gateway/deal` (verrouillée). En-têtes : `X-IG-API-KEY`,
`Version`, `Content-Type`/`Accept: application/json; charset=UTF-8`, puis `CST` et
`X-SECURITY-TOKEN` après connexion (valides 6 h, prolongés jusqu'à 72 h à l'usage).

| Méthode | Chemin | Version | Usage | Champs exploités |
|---|---|---|---|---|
| POST | `/session` | 2 | Connexion | corps : `identifier`, `password`, `encryptedPassword` ; en-têtes réponse `CST`, `X-SECURITY-TOKEN` ; `currentAccountId`, `clientId`, `accounts`, `currencyIsoCode`, `dealingEnabled` |
| PUT | `/session` | 1 | Bascule de compte si `IG_ACCOUNT_ID` ≠ compte actif (`defaultAccount` non envoyé : compte par défaut inchangé) | `accountId` |
| DELETE | `/session` | 1 | Déconnexion | — |
| GET | `/accounts` | 1 | Comptes et soldes | `accountId`, `accountName`, `accountType`, `currency`, `status`, `preferred`, `balance.{balance, available, deposit, profitLoss}` |
| GET | `/markets?searchTerm=` | 1 | Recherche EUR/USD | `epic`, `instrumentName`, `instrumentType`, `expiry`, `marketStatus`, `bid`, `offer` |
| GET | `/markets/{epic}` | 3 | Contraintes du marché | `dealingRules.{minDealSize, minStepDistance, minNormalStopOrLimitDistance, minControlledRiskStopDistance, maxStopOrLimitDistance, controlledRiskSpacing}` (`unit`, `value`), `marketOrderPreference`, `trailingStopsPreference` ; `instrument.{lotSize, contractSize, onePipMeans, valueOfOnePip, currencies, marginFactor, marginFactorUnit, stopsLimitsAllowed, forceOpenAllowed}` ; `snapshot.{marketStatus, bid, offer}` |

### Points d'attention documentés

- **Incrément de taille** : aucun champ dédié dans `/markets/{epic}`. `minStepDistance` est
  décrit uniquement comme « Dealing rule » ; son interprétation est à confirmer (voir `ASSUMP-004`).
- **Sélection EUR/USD** : marchés `instrumentType = CURRENCIES` sans échéance (`expiry = "-"`).
  Plusieurs epics peuvent coexister (tailles de contrat différentes) ; tous sont détaillés (max 5).
- **Quotas par défaut (FAQ IG)** : 60 req/min non-trading par application, 30 req/min
  non-trading par compte, 10 000 points d'historique par semaine. Le diagnostic émet ~6 à 10 requêtes.
- **Mot de passe chiffré** : si IG renvoie `error.public-api.failure.encryption.required`,
  il faudra implémenter `GET /session/encryptionKey` (non fait à ce stade).

## IG Streaming API (Lightstreamer) — démo, lecture seule

Sources consultées le 2026-10-27 : IG Labs Streaming API Reference et Streaming API Guide
(https://labs.ig.com/streaming-api-reference.html, https://labs.ig.com/streaming-api-guide.html),
`POST /session` (https://labs.ig.com/reference/session.html) et la page IG « How to use IG API »
(https://www.ig.com/en/trading-platforms/trading-apis/how-to-use-ig-api), qui recommande le client
Lightstreamer et renvoie aux pages IG Labs pour le détail.

- Point d'accès : `lightstreamerEndpoint` de `POST /session` (« ne doit pas être codé en dur ») ;
  observé `https://demo-apd.marketdatasystems.com` sur la démo.
- Identifiant : compte actif (`currentAccountId`) ; mot de passe : `CST-<CST>|XST-<X-SECURITY-TOKEN>`.
  Bibliothèque : client officiel `lightstreamer-client-lib` (2.2.3). La page IG de téléchargement
  ne précise pas de version recommandée.
- Abonnement utilisé : `PRICE:{compte}:CS.D.EURUSD.CEFM.IP`, mode `MERGE`, adaptateur `Pricing`,
  champs `BIDPRICE1`, `ASKPRICE1`, `TIMESTAMP` (« The timestamp in UTC millis »), `DLG_FLAG`
  (CLOSED, CALL, DEAL, EDIT, CLOSINGSONLY, DEALNOEDIT, AUCTION, AUCTIONNOEDIT, SUSPEND), `DELAY` (0/1).
- `MARKET:{epic}` (heure `UPDATE_TIME` en heure locale UK) : fin de vie annoncée par IG, **non utilisé**.
- Limite : 40 abonnements simultanés par connexion ; ouvrir des connexions supplémentaires pour
  la contourner est contraire aux conditions IG.
- Le guide recommande une connexion dans un fil dédié, une reconnexion automatique et une
  réauthentification si les jetons ont expiré : à faire dans le futur service de flux (la sonde
  actuelle est ponctuelle).

- Échanges réseau de la sonde : `POST /session` et `DELETE /session` (REST) ; côté Lightstreamer,
  les requêtes de contrôle de la bibliothèque (ouverture de session, abonnement, désabonnement,
  déconnexion). `sendMessage` n'est jamais appelé.

Observé sur la démo le 2026-10-27 (sonde `ig-price-probe`, 3 exécutions de 15 à 20 s) : connexion
`CONNECTED:WS-STREAMING` ; 52, 43 puis 20 mises à jour, dont un instantané par exécution, aucune
hors ordre ni malformée ; `TIMESTAMP`, `BIDPRICE1`, `ASKPRICE1`, `DLG_FLAG` reçus ; `DLG_FLAG` =
`"DEAL"` complété d'espaces (valeurs documentées elles aussi avec des espaces finaux) ; `DELAY` jamais renseigné. `reroutingEnvironment` présent mais vide
dans `POST /session`.

Écart apparent « réception locale − `TIMESTAMP` » : médiane +0,005 à +0,010 s, maximum +1,3 à
+1,8 s. **Ce n'est pas une mesure de latence** : il additionne le délai de publication IG, le
transport, le traitement par la bibliothèque et le décalage entre l'horloge locale et celle d'IG,
qui n'a pas été mesuré. L'origine des maxima n'a pas été établie. Seul `TIMESTAMP` sert à juger la
fraîcheur.
