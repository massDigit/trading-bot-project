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
