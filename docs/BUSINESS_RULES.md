# BUSINESS_RULES.md - Règles de Gestion Métier

> **Toutes les règles répertoriées ci-dessous sont absolues et doivent être garanties par le code.**
> Source : cahier des charges v1.1 (§8, §11) et exigences de l'opérateur du 2026-10-27.

## 📌 Règle 1 : Aucun ordre à ce stade
- Aucun passage d'ordre, aucune modification de position, aucun accès au réel.
- Garantie : liste blanche d'endpoints du client IG (`src/forex_bot/ig_client.py`), URL démo verrouillée.

## 📌 Règle 2 : Contrat explicitement sélectionné
- Contrat unique : IG EUR/USD Mini `CS.D.EURUSD.CEFM.IP`, désigné par son epic, jamais choisi dans
  un résultat de recherche.
- Le marché « Weekend EUR/USD » (`IX.D.SUNEURUSD.CEF.IP`, et tout nom contenant « weekend ») est exclu.
- Avant toute utilisation, les caractéristiques du contrat (type, échéance, taille de contrat,
  pip, devise de cotation, taille minimale, stop minimal, stops autorisés) sont comparées à la
  référence observée le 2026-10-27, ainsi que son état (`TRADEABLE`) et la cohérence bid/offer.
  Tout écart bloque l'usage jusqu'à revue humaine.
- Garantie : `src/forex_bot/instruments.py` (`verify_contract`).

## 📌 Règle 3 : Allocation initiale ≠ fonds propres actualisés
- **Allocation initiale** : 2 000 EUR, capital de départ affecté au robot, distinct du solde du
  compte démo (10 000 EUR).
- **Base du budget** : les **fonds propres actualisés du portefeuille du robot** (allocation
  + réalisé + latent − frais, corrigés des apports/retraits), jamais l'allocation initiale ni le
  solde du courtier. Risque par opération : 0,25 % (proposition §8, non approuvée pour le réel).
- Tant que ce suivi n'existe pas (ou si la valeur est périmée, nulle ou dans une autre devise),
  le dimensionnement est **bloqué**. Le budget sur l'allocation initiale (5 EUR) n'est affiché
  qu'à titre d'information.
- La fonction de dimensionnement ne reçoit pas le solde du courtier.

## 📌 Règle 4 : Convention de prix — le spread n'est compté qu'une fois
- `bid` = prix de vente, `offer` = prix d'achat.
- Achat : entrée estimée à l'**offer** ; stop exprimé en prix **bid** (on vend pour sortir).
  Perte de prix = offer − stop (+ glissement provisionné).
- Vente : entrée estimée au **bid** ; stop exprimé en prix **offer** (on rachète pour sortir).
  Perte de prix = stop − bid (+ glissement provisionné).
- Le spread est inclus une seule fois, par l'entrée du côté défavorable ; aucun terme de spread
  n'est ajouté en plus. Un stop d'achat doit être strictement sous le bid courant, un stop de
  vente strictement au-dessus de l'offer courant.
- Conversion USD → EUR au taux 1 / bid EUR/USD (côté qui maximise la perte en EUR).

Exemples (bid 1,11498 / offer 1,11508, glissement 0,5 pip) :

| | Achat, stop 1,11200 | Vente, stop 1,11800 |
|---|---|---|
| Entrée estimée | 1,11508 (offer) | 1,11498 (bid) |
| Perte de prix | 1,11508 − 1,11200 + 0,00005 = 0,00313 | 1,11800 − 1,11498 + 0,00005 = 0,00307 |
| Par contrat (× 10 000) | 31,30 USD | 30,70 USD |
| En EUR (÷ 1,11498) | 28,07 EUR | 27,53 EUR |

## 📌 Règle 5 : Unités
- Confirmées par des champs de l'API : pip = 0,0001 (`onePipMeans`) ; contrat = 10 000 EUR
  (`contractSize`) ; 1 pip × 1 contrat = 1 USD, cohérent avec `valueOfOnePip` (vérifié).
- **Non confirmées** (valeur vide, jamais remplacée par défaut) : rapport point IG / pip
  (distances `POINTS` des `dealingRules`), rapport unité de taille / contrat (`minDealSize` en
  « POINTS »), taille minimale et incrément. Toute vérification qui en dépend reste bloquée.

## 📌 Règle 6 : Coûts
- Chaque coût est `CONFIRMED`, `ASSUMED` ou `UNKNOWN`. Un coût inconnu n'est **jamais** compté
  comme zéro : il est listé comme exclu de l'estimation et bloque le dimensionnement exécutable.
- Coûts pris en compte : spread (via la convention de prix), glissement, commission, frais de
  conversion de devise, financement overnight (positions swing, par nuit), prime de stop garanti
  (si utilisé).

## 📌 Règle 7 : Le stop technique n'est jamais modifié
- Si la position ne tient pas dans le budget : taille réduite (arrondi **vers le bas** à
  l'incrément) ou signal **refusé**. Le stop n'est jamais rapproché pour faire entrer la position.
- Stop plus proche que le minimum courtier : signal refusé (le stop n'est pas non plus élargi).
- Le minimum dépend du type de stop : `minNormalStopOrLimitDistance` (2 points) pour un stop
  normal, `minControlledRiskStopDistance` (5 points) pour un stop garanti. Il est mesuré depuis le
  prix de référence **confirmé** pour ce type de stop. Si le rapport point/pip, la référence ou le
  côté de déclenchement ne sont pas confirmés, le dimensionnement est **bloqué** (ASSUMP-008).
- Une convention n'est utilisée que sous forme de `Confirmation` (source, date, epic) ; une
  confirmation pour un autre epic est ignorée (`docs/CONFIRMATIONS.md`).

## 📌 Règle 8 : Une estimation, pas une garantie
- Le résultat est une **perte estimée au stop**. Gaps, glissement supérieur à la provision, rejet
  ou panne peuvent la dépasser : ce n'est jamais une perte maximale garantie (cahier des charges §8).

## 📌 Règle 9 : Blocage des entrées
- Toute future entrée est bloquée si le marché n'est pas `TRADEABLE`, si la cotation est
  incohérente, périmée, différée, sans horodatage ou sans fuseau, si le contrat n'est pas vérifié,
  si les fonds propres sont indisponibles, si une convention n'est pas confirmée ou si un coût
  applicable est inconnu.
- **Fonds propres** : date sans fuseau ou dans le futur (au-delà de 2 s de tolérance) → bloqué ;
  tout événement de position, de frais ou de flux non encore intégré → bloqué, même si la date
  des fonds propres est récente. L'horloge locale sans fuseau bloque aussi (jamais de `TypeError`).
- **État du marché** : la vérification du contrat (`GET /markets/{epic}` v3, datée à la réception
  locale, valable 60 s — ASSUMP-011) et la cotation (flux `PRICE`, datée par `TIMESTAMP` IG)
  doivent toutes deux indiquer un marché négociable. Une contradiction bloque ; aucune source ne
  l'emporte : il faut une nouvelle vérification récente et concordante.
- L'horodatage `updateTime` de `GET /markets/{epic}` v3 (heure sans date ni fuseau documenté)
  n'est pas converti : la cotation correspondante est considérée sans horodatage.
- Garantie : `src/forex_bot/market.py` (`quote_blockers`), `src/forex_bot/risk.py`
  (`entry_blockers`, `size_position`).

## 📌 Règle 10 : Cotations horodatées (flux `PRICE`)
- Trois informations distinctes : heure de la cotation chez IG (`TIMESTAMP`, UTC), heure de
  réception locale, état de la connexion. La fraîcheur se mesure **uniquement** sur `TIMESTAMP`.
- Messages partiels (`MERGE`) fusionnés ; cotation absente tant qu'un champ requis manque.
- Message plus ancien que la dernière cotation acceptée : rejeté (hors ordre). Ce plancher survit
  aux reconnexions : un instantané de reconnexion ne peut ni ramener une cotation plus ancienne
  ni rajeunir une cotation existante.
- Déconnexion ou flux bloqué : état fusionné effacé, entrée bloquée. Mises à jour perdues :
  bloqué jusqu'à une cotation plus récente.
- `DLG_FLAG` autre que `DEAL` → non négociable (ASSUMP-012) ; `DELAY` = 1, absent ou inconnu →
  bloqué (ASSUMP-013).
- Les seuils de 10 s (cotation), 60 s (vérification du contrat) et 5 min (fonds propres) sont des
  **paramètres expérimentaux**, pas des exigences IG.
- Garantie : `src/forex_bot/streaming.py` (`PriceTracker`), `src/forex_bot/market.py`.
