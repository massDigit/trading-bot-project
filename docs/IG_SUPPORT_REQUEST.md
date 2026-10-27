# IG_SUPPORT_REQUEST.md - Demande au support IG (brouillon, NON ENVOYÉE)

> Brouillon mis à jour le 2026-10-27, après la recherche documentaire consignée dans
> `docs/CONFIRMATIONS.md`. Il ne contient que les questions que la documentation officielle ne
> tranche pas. À relire et envoyer par l'opérateur depuis son espace client, sans identifiant,
> numéro de compte ni jeton (à ajouter par l'opérateur si le support les demande).
>
> **Avant l'envoi** : vérifier dans les documents contractuels de l'espace client l'entité qui
> tient le compte. Si c'est IG Europe GmbH, la question 4 peut être retirée : les clauses 12(1)(a)
> et 13(3) des conditions CFD d'IG Europe GmbH y répondent.

---

**Objet** : API IG — dealing rules et flux PRICE pour CS.D.EURUSD.CEFM.IP (compte CFD démo)

Bonjour,

J'utilise l'API REST (`GET /markets/{epic}`, version 3) et le flux Lightstreamer (`PRICE`) en
lecture seule sur un compte CFD de démonstration. J'ai consulté la référence IG Labs et vos
conditions générales ; il me reste les questions ci-dessous sur le marché **EUR/USD Mini, epic
`CS.D.EURUSD.CEFM.IP`**.

Valeurs renvoyées par `GET /markets/CS.D.EURUSD.CEFM.IP` (v3) sur la démo le 2026-10-27 :
`instrument.unit` = CONTRACTS, `contractSize` = 10000, `onePipMeans` = "0.0001 USD/EUR",
`valueOfOnePip` = "1.00", `lotSize` = 1.0, `snapshot.scalingFactor` = 10000,
`limitedRiskPremium` = {POINTS, 1.2}, et `dealingRules` :
`minDealSize` {POINTS, 0.1}, `minStepDistance` {POINTS, 5.0},
`minNormalStopOrLimitDistance` {POINTS, 2.0}, `minControlledRiskStopDistance` {POINTS, 5.0},
`controlledRiskSpacing` {POINTS, 20.0}.

Ce que je comprends déjà : la taille d'une position est qualifiée en contrats
(`instrument.unit`). La référence IG Labs décrit `contractSize` uniquement comme « Contract size »
et les champs de `dealingRules` uniquement comme « Dealing rule ».

**1. Contrat, taille minimale et incrément**
- `contractSize` = 10000 est-il exprimé en unités de la devise de base (EUR) ? Cela serait
  cohérent avec 0,0001 USD/EUR × 10000 = 1 USD = `valueOfOnePip`.
- `minDealSize` vaut 0.1 avec l'unité « POINTS ». Faut-il comprendre une taille minimale de
  0,1 contrat ? Quel est l'incrément de taille autorisé (par exemple 0,1 ou 0,01 contrat) ?

**2. Point IG et pip**
Pour ce marché, que vaut 1 « point » dans les `dealingRules` et dans `limitedRiskPremium`, en
prix ? `scalingFactor` = 10000 suggère 1 point = 0,0001 (1 pip) : est-ce exact ?

**3. Référence des distances minimales**
À l'ouverture d'une position, depuis quel prix la distance minimale est-elle mesurée :
- pour un stop normal (`minNormalStopOrLimitDistance`) : bid, offer, prix moyen ou niveau d'exécution ?
- pour un stop garanti (`minControlledRiskStopDistance`) : même question.

Que représentent `minStepDistance` et `controlledRiskSpacing` ?

**4. Côté de déclenchement des stops** *(à retirer si le compte relève d'IG Europe GmbH)*
Pour mon compte, un stop d'une position acheteuse est-il déclenché par le bid et celui d'une
position vendeuse par l'offer, pour les stops normaux comme pour les stops garantis ?

**5. Flux `PRICE`**
- `DELAY` (« Delayed price flag (0=false, 1=true) ») n'est jamais renseigné sur la démo pour
  cet item. Que signifie son absence ? `snapshot.delayTime` = 0 (REST) s'applique-t-il au flux ?
- `TIMESTAMP` (« The timestamp in UTC millis ») horodate-t-il la production du prix par IG ou la
  publication du message ?
- Quelles valeurs de `DLG_FLAG` permettent d'ouvrir une position (`DEAL` seulement, ou aussi
  `DEALNOEDIT`) ?

Pour chaque réponse, pourriez-vous préciser si elle vaut aussi pour le compte réel, et indiquer
la documentation correspondante si elle existe ?

Merci d'avance.

---

## Après réception

1. Reporter chaque réponse dans `docs/CONFIRMATIONS.md` (nature DOC, source, date, version d'API,
   périmètre : démo ou réel, epic).
2. Une réponse ambiguë reste HYP. Ce que nous en déduisons reste HYP ou CALC, jamais DOC.
3. Toute levée de blocage est proposée séparément, avec sa justification, dans une PR dédiée.
