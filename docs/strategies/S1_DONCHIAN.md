# Fiche exécutable S1 — Cassure de canal Donchian (swing)

> Identifiant code : `SWING_01`. Statut : **spécifiée (brouillon)**, non implémentée, non évaluée.
> Tous les paramètres chiffrés sont des **PROPOSITIONS** non approuvées. Aucune performance n'est
> revendiquée ; aucune optimisation n'a été faite. Le sélecteur IA n'est pas concerné.

## 1. Hypothèse et références

- Hypothèse : après la clôture d'une bougie au-delà de l'extrême des N bougies précédentes, le
  prix tend à poursuivre dans le sens de la cassure assez souvent pour couvrir les pertes des
  faux départs et les coûts.
- Appui : « Time Series Momentum » (Moskowitz, Ooi, Pedersen ; AQR) pour la famille du suivi de
  tendance, **sans validation directe** de cette variante H4 sur EUR/USD (cahier des charges §6.2).
- Faiblesse attendue : faux départs répétés en marché latéral ; gaps de week-end.

## 2. Instrument, données et unités de temps

| Élément | Valeur | Statut |
|---|---|---|
| Instrument | EUR/USD ; cible d'exécution future IG `CS.D.EURUSD.CEFM.IP` | décidé (V1) |
| Données de recherche | Dukascopy, bid et ask séparés (`docs/DATA.md`) ; ≠ prix exécutables IG | candidate |
| Contexte | D1, ancrage clôture New York (17:00) | PROPOSITION |
| Signal | H4, même ancrage | PROPOSITION (cahier §6.2 : D1 → H4) |
| Variante de comparaison | Sans filtre D1 (H4 seul) | requise par §6.5 |
| Série de calcul du signal | **bid** (OHLC bid) pour les deux sens | PROPOSITION — décision ouverte (bid / mid) |

## 3. Construction des indicateurs (à la clôture de la bougie H4 `t`)

- Canal d'entrée : `HH_N(t) = max(bid_high[t-N .. t-1])`, `LL_N(t) = min(bid_low[t-N .. t-1])`.
  **La bougie `t` qui déclenche la cassure est exclue du canal.** N = 20 (PROPOSITION).
- Canal de sortie : `LL_M(t)`, `HH_M(t)` sur les M bougies précédentes, signal exclu. M = 10
  (PROPOSITION).
- ATR : moyenne de Wilder sur 14 bougies H4 (PROPOSITION) du true range bid, calculée jusqu'à `t`
  inclus.
- Contexte D1 : dernière bougie D1 **clôturée** au moment de la décision (`end_utc ≤ fin de t`) ;
  haussier si `bid_close_D1 > milieu du canal D1 sur 55 jours`, baissier si inférieur
  (PROPOSITION ; 55 jours, milieu du canal).

## 4. Règles d'entrée

À la clôture de la bougie H4 `t` (et seulement si toutes les conditions de données du §9 sont
remplies) :
- **Achat** si `bid_close[t] > HH_N(t)` et contexte D1 haussier (ou variante sans filtre).
- **Vente** si `bid_close[t] < LL_N(t)` et contexte D1 baissier (ou variante sans filtre).
- Pas de nouvelle entrée si une position S1 est déjà ouverte sur EUR/USD ; pas de position opposée
  (cahier §7 : pas de couverture implicite).
- Signal émis sur la dernière bougie H4 avant la fermeture hebdomadaire (vendredi 13:00-17:00 New
  York) : **expire** sans exécution (PROPOSITION ; décision ouverte, voir §12).

## 5. Chronologie du signal et de l'exécution

```
bougie t : [start_utc(t), end_utc(t))   -> clôturée à end_utc(t)
décision : à end_utc(t), avec uniquement les bougies dont end_utc <= end_utc(t)
exécution: premier prix admissible APRÈS end_utc(t) :
           achat au premier ask, vente au premier bid (cahier §9)
           jamais à un prix de la bougie t (pas d'exécution rétroactive)
```
En simulation par bougies sans ticks : `ask_open[t+1]` (achat) ou `bid_open[t+1]` (vente), avec
latence simulée à définir. Si `t+1` commence après une fermeture, le prix d'exécution est celui
de la réouverture (gap inclus).

## 6. Stop initial, sorties et invalidation

**Stop technique (stratégie)**, fixé à la décision et jamais élargi :
- Achat : `stop = bid_close[t] − k × ATR(t)` (niveau bid, côté de sortie) ; vente :
  `stop = ask_close[t] + k × ATR(t)` (niveau offer, côté de sortie). k = 2 (PROPOSITION).
- La distance effective est recalculée au prix d'exécution estimé (entrée à l'ask pour un achat).

**Sorties** (règle figée, une seule active par variante) :
- Base : sortie au marché au premier prix admissible après la clôture d'une bougie H4 où
  `bid_close < LL_M` (achat) ou `bid_close > HH_M` (vente).
- Variante : rapprocher le stop au niveau du canal de sortie (jamais l'éloigner).
- Stop touché : sortie au niveau du stop pour un stop garanti ; en simulation, un gap au-delà du
  stop est exécuté au premier prix admissible, sauf garantie applicable (cahier §9).
- Stop et sortie dans la même bougie : résolution plus fine (H1, puis ticks) ; si l'ordre reste
  inconnu, convention prudente (stop d'abord) et mesure de sensibilité.

**Invalidation** de l'hypothèse : stop touché ou règle de sortie. Sortie temporelle : aucune dans
la base (décision ouverte).

## 7. Contraintes du compte IG cible (distinctes de la stratégie)

Source : courriel officiel d'activation IG relayé par l'opérateur (statut DÉCL), compte **réel**
CFD à risque limité. La démo n'est pas présumée soumise aux mêmes règles.

| Contrainte | Effet sur S1 |
|---|---|
| Stop garanti **obligatoire** sur chaque position | Chaque entrée porte un stop garanti au niveau du stop technique |
| Distance minimale du stop garanti (compte réel : **inconnue** ; démo : 5.0 « POINTS », unité non confirmée) | Si la distance du stop technique est **inférieure** au minimum : **signal refusé**. Le stop n'est ni élargi ni déplacé |
| Stop rapprochable, **jamais éloigné** | Aucune règle S1 ne peut élargir le stop ; la variante « rapprocher » est compatible |
| Prime facturée si le stop garanti est déclenché (compte réel : **inconnue** ; démo : 1.2 « POINTS ») | Incluse dans la perte estimée au stop ; tant qu'inconnue : dimensionnement **bloqué** |
| Référence de mesure des distances minimales : **inconnue** | Dimensionnement **bloqué** (ASSUMP-008) |

Un stop technique incompatible avec ces contraintes entraîne le **refus** du signal, journalisé
avec son motif ; il n'est jamais modifié silencieusement.

## 8. Dimensionnement

Règles du contrôleur de risque existant (`risk.py`, `docs/BUSINESS_RULES.md`) :
- budget = 0,25 % des fonds propres actualisés du robot (PROPOSITION §8), pas de l'allocation
  initiale ;
- perte estimée par contrat = (entrée ask − stop bid + glissement) × taille de contrat, convertie
  en EUR, plus les coûts applicables ; taille = budget / perte, arrondie **vers le bas** à
  l'incrément ; refus si la taille minimale dépasse le budget ;
- résultat présenté comme une perte **estimée**, jamais garantie (sauf effet propre du stop garanti,
  à confirmer pour le compte réel).

## 9. Coûts nécessaires

| Coût | Statut | Traitement |
|---|---|---|
| Spread | Historique Dukascopy (bid/ask) ; spread IG **inconnu** et différent | entrée ask / sortie bid ; scénarios de spread IG dégradé |
| Glissement | ASSUMED 0,5 pip (ASSUMP-006) | provision ; sensibilité |
| Financement overnight (swing, par nuit) | **UNKNOWN** | bloque le dimensionnement ; en recherche, scénarios explicites, jamais zéro |
| Conversion USD→EUR | **UNKNOWN** | idem |
| Commission | **UNKNOWN** | idem |
| Prime de stop garanti | **UNKNOWN** (réel) | idem |

Tant qu'un coût est inconnu, aucun résultat « net » n'est revendiqué ; les résultats de
recherche indiquent les scénarios de coûts utilisés.

## 10. Données manquantes

- Abstention (journalisée) si la bougie `t`, l'une des N bougies du canal, l'une des bougies de la
  fenêtre ATR ou la bougie D1 de contexte est **incomplète** (`complete = false`).
- Aucune bougie manquante n'est interpolée ; une fenêtre qui en contient une n'est pas « raccourcie ».
- Trou de données pendant une position : la position reste gérée par son stop ; la sortie au canal
  attend la prochaine bougie complète.

## 11. Prévention des fuites temporelles

- Seules les bougies clôturées (`end_utc ≤ instant de décision`) sont lues ; la bougie D1 en cours
  n'est jamais utilisée.
- Canal calculé sur `t-N .. t-1` : la bougie du signal est exclue.
- Exécution strictement après `end_utc(t)`.
- Réglages uniquement sur 2015-2021 ; 2022-2023 pour la validation sans réglage ; 2024-2025 non
  ouvert (l'importeur le refuse).
- Les essais et variantes sont enregistrés avant évaluation (cahier §6.6, §9).
- Le direct devra construire ses bougies avec le même ancrage, à partir du flux IG `PRICE`.

## 12. Paramètres et décisions ouvertes

| Paramètre | Proposition | Domaine de recherche envisagé (à pré-enregistrer) |
|---|---|---|
| N (canal d'entrée H4) | 20 | 10-60 |
| M (canal de sortie H4) | 10 | 5-30, M < N |
| ATR | 14 bougies H4 | 10-30 |
| k (stop) | 2 × ATR | 1,5-4 |
| Filtre D1 | milieu du canal 55 jours | avec / sans filtre |
| Série du signal | bid | bid / mid (à décider) |

Décisions ouvertes : série bid ou mid ; traitement du signal du vendredi soir ; sortie temporelle ;
latence simulée ; ancrage H4/D1 (clôture New York, à comparer à l'ancrage des graphiques IG) ;
scénarios de coûts tant que les coûts IG sont inconnus ; contraintes du compte réel (distance
minimale, prime, référence de mesure).
