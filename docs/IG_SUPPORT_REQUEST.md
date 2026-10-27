# IG_SUPPORT_REQUEST.md - Demande au support IG (brouillon, NON ENVOYÉE)

> Brouillon préparé le 2026-10-27. À relire et envoyer par l'opérateur depuis son espace client.
> Ne contient ni identifiant, ni numéro de compte, ni jeton : à compléter au moment de l'envoi.
> Les réponses alimentent `docs/CONFIRMATIONS.md`, puis seulement `BrokerConventions` dans le code.

---

**Objet** : API IG — conventions d'unités, de taille et de stops pour CS.D.EURUSD.CEFM.IP (compte CFD démo)

Bonjour,

Je développe une application qui utilise l'API REST et le flux Lightstreamer d'IG, actuellement en
lecture seule sur un compte CFD de démonstration. Avant toute utilisation, je souhaite confirmer les
conventions suivantes pour le marché **EUR/USD Mini, epic `CS.D.EURUSD.CEFM.IP`**.

Valeurs renvoyées par `GET /markets/CS.D.EURUSD.CEFM.IP` (version 3) le 2026-10-27, sur la démo :

- `instrument.contractSize` = 10000 ; `instrument.onePipMeans` = "0.0001 USD/EUR" ;
  `instrument.valueOfOnePip` = "1.00" ; `instrument.unit` = "CONTRACTS" ; `instrument.lotSize` = 1.0
- `dealingRules.minDealSize` = {unit: "POINTS", value: 0.1}
- `dealingRules.minStepDistance` = {unit: "POINTS", value: 5.0}
- `dealingRules.minNormalStopOrLimitDistance` = {unit: "POINTS", value: 2.0}
- `dealingRules.minControlledRiskStopDistance` = {unit: "POINTS", value: 5.0}
- `dealingRules.controlledRiskSpacing` = {unit: "POINTS", value: 20.0}

**1. Point IG et pip**
Pour ce marché, combien de pips représente 1 « point » dans les distances de `dealingRules` ?
Autrement dit, une distance minimale de 2.0 POINTS correspond-elle à 2 pips (0,0002), à 0,2 pip
ou à une autre valeur ?

**2. Unité de taille et contrat**
La taille d'une position (`size`) est-elle exprimée en nombre de contrats de 10 000 EUR ?
Pourquoi `minDealSize` est-il exprimé avec l'unité « POINTS » ?

**3. Taille minimale et incrément**
Quelle est la taille minimale autorisée et quel est l'incrément de taille autorisé (par exemple
0,1 ; 0,01) ? `minStepDistance` (5.0 POINTS) concerne-t-il la taille ou une distance de prix ?

**4. Côté de déclenchement des stops**
Pour une position acheteuse, un stop normal est-il déclenché par le prix vendeur (bid) ?
Pour une position vendeuse, par le prix acheteur (offer) ? En est-il de même pour un stop garanti ?

**5. Référence des distances minimales**
Depuis quel prix la distance minimale est-elle mesurée lors de l'ouverture d'une position :
- pour un stop **normal** (`minNormalStopOrLimitDistance`) : bid, offer, prix moyen ou niveau
  d'exécution ?
- pour un stop **garanti** (`minControlledRiskStopDistance`) : même question.
Que représente `controlledRiskSpacing` ?

**6. Flux `PRICE` (Lightstreamer)**
- Sur la démo, le champ `DELAY` de l'abonnement `PRICE:{compte}:CS.D.EURUSD.CEFM.IP` n'est jamais
  renseigné. Est-ce normal, et comment savoir si un prix est différé ?
- Quelles valeurs de `DLG_FLAG` signifient qu'une nouvelle position peut être ouverte
  (`DEAL` uniquement, ou aussi `DEALNOEDIT`) ?
- `TIMESTAMP` est-il l'heure de la cotation chez IG, ou l'heure de publication du message ?

Pour chaque réponse, pourriez-vous indiquer si elle s'applique aussi au compte réel, et citer la
page de documentation correspondante si elle existe ?

Merci d'avance.

---

## Après réception

1. Reporter chaque réponse dans `docs/CONFIRMATIONS.md` : valeur, source (référence du ticket ou
   URL), date, epic, compte démo et/ou réel.
2. Une réponse ambiguë reste `NON CONFIRMÉ`. Ce que nous en déduisons est noté `DÉDUIT`, pas `CONFIRMÉ`.
3. Seules les lignes `CONFIRMÉ` peuvent devenir une `Confirmation(...)` dans
   `EURUSD_MINI_CONVENTIONS` (`src/forex_bot/instruments.py`), dans une PR dédiée et validée.
