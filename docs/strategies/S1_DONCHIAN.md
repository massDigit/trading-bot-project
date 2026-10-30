# Fiche exécutable S1 — Cassure de canal Donchian (swing)

> Identifiant code : `SWING_01`. Statut : **implémentée hors ligne** (`src/forex_bot/backtest/`,
> tests synthétiques), **non évaluée** : aucun passage sur données réelles. Les règles
> de données et de chronologie (§5, §10) sont validées comme **référence expérimentale** (ADR-006,
> 2026-10-30) : ni validation de performance ni autorisation de trading.
> Les paramètres chiffrés sont une **configuration initiale expérimentale** approuvée (ASSUMP-020,
> ADR-008) : une référence à tester, pas des paramètres démontrés rentables. Aucune performance n'est
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
| Contexte | D1, ancrage clôture New York (17:00) | convention du robot (ASSUMP-015) |
| Signal | H4, même ancrage | convention du robot (ASSUMP-015 ; cahier §6.2 : D1 → H4) |
| Variante de comparaison | Sans filtre D1 (H4 seul) | requise par §6.5 |
| Série de calcul du signal | **bid** (OHLC bid) pour les deux sens | EXPÉRIMENTAL (ASSUMP-020) ; variante mid possible |

## 3. Construction des indicateurs (à la clôture de la bougie H4 `t`)

- Canal d'entrée : `HH_N(t) = max(bid_high[t-N .. t-1])`, `LL_N(t) = min(bid_low[t-N .. t-1])`.
  **La bougie `t` qui déclenche la cassure est exclue du canal.** N = 20 (EXPÉRIMENTAL, ASSUMP-020).
- Canal de sortie : `LL_M(t)`, `HH_M(t)` sur les M bougies précédentes, signal exclu. M = 10
  (EXPÉRIMENTAL, ASSUMP-020).
- ATR : moyenne de Wilder sur 14 bougies H4 (EXPÉRIMENTAL, ASSUMP-020) du true range bid, calculée jusqu'à `t`
  inclus ; disponibilité et réamorçage après une bougie non utilisable : §10.3.
- Contexte D1 : dernière bougie D1 **disponible** au moment de la décision (`available_at_utc ≤
  D(t)`, §5) ; haussier si `bid_close_D1 > milieu du canal D1 sur 55 jours`, baissier si inférieur.
  Le canal D1 couvre les 55 D1 qui se terminent par la D1 de contexte (EXPÉRIMENTAL, ASSUMP-020 ;
  55 jours, milieu du canal). Jamais de jointure par date civile : elle peut introduire la clôture
  du soir dans une décision du matin.

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
bougie t : [start_utc(t), end_utc(t))      -> clôturée à end_utc(t)
           disponible à available_at_utc(t) = end_utc(t) + L
décision : à D(t) = available_at_utc(t), avec uniquement les bougies
           dont available_at_utc <= D(t)
exécution: premier prix admissible strictement APRÈS D(t) :
           achat au premier ask, vente au premier bid (cahier §9)
           jamais à un prix de la bougie t (pas d'exécution rétroactive)
```
En simulation par bougies sans ticks : `ask_open[t+1]` (achat) ou `bid_open[t+1]` (vente), avec
latence simulée à définir. Si `t+1` commence après une fermeture, le prix d'exécution est celui
de la réouverture (gap inclus).

**Disponibilité des bougies (référence expérimentale, ADR-006).** Chaque bougie porte
`start_utc`, `end_utc` et `available_at_utc`. En recherche, `available_at_utc = end_utc + L`, avec
une latence de publication `L` paramétrée (0 par défaut, puisque les bougies sont reconstruites
à partir des ticks) ; en fonctionnement, l'instant où la bougie est effectivement finalisée.
Une bougie n'est lisible que si `available_at_utc ≤ instant de décision`. La décision liée à la
bougie `t` est prise à `D(t) = available_at_utc(t)`, jamais à `end_utc(t)` lorsque `L > 0` : à
cet instant, la bougie du signal n'est pas encore disponible. Le prix de clôture n'est jamais une
exécution obtenue.

**Ordre déterministe à un instant de décision `E` (par exemple la frontière commune H1/H4/D1 de
17:00 New York, plus `L`).**
1. Rendre disponibles toutes les bougies dont `available_at_utc ≤ E` : H1, puis H4, puis D1. Une
   D1 et une H4 qui se terminent au même instant ont la même disponibilité : la D1 est donc
   lisible pour la décision H4 correspondante.
2. Mettre à jour les indicateurs (canaux, ATR, contexte D1) et l'état de qualité des données.
3. Évaluer d'abord la sortie de la position ouverte, puis une éventuelle entrée.
4. Exécuter au premier tick strictement postérieur à `E` (`ts > E`) : achat à l'ask, vente au
   bid. Une sortie et une nouvelle entrée au même instant sont deux exécutions distinctes.

Une décision prise à `E` n'est jamais réécrite, même si une information apparue après `E`
montre qu'une bougie qu'elle a lue était dégradée.

**Priorité des événements sur un même tick (ASSUMP-024, proposée).** 1) silence précédant le
tick (§10.5) ; 2) stop de la position ouverte ; 3) sortie au canal en attente ; 4) entrée en
attente. Si le premier tick après `E` franchit déjà le stop, le stop l'emporte (ordre déjà en
place) : stop garanti exécuté au niveau `S` avec sa prime, stop normal au prix observé ; la
sortie au canal est abandonnée et journalisée (`SORTIE_CANAL_ABANDONNÉE`). Une entrée en attente
(retournement) est ensuite exécutée sur ce même tick.

## 6. Stop initial, sorties et invalidation

**Stop technique (stratégie)**, fixé à la décision et jamais élargi :
- Achat : `stop = bid_close[t] − k × ATR(t)` (niveau bid, côté de sortie) ; vente :
  `stop = ask_close[t] + k × ATR(t)` (niveau offer, côté de sortie). k = 2 (EXPÉRIMENTAL, ASSUMP-020).
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

**Moteur hors ligne (ASSUMP-024, proposée).**
- *Fonds propres* = solde réalisé + résultat latent. Le latent est la valeur de liquidation de la
  position au dernier tick connu (prix côté sortie, coûts de sortie accumulés, conversion du côté
  défavorable, sans prime). Courbe échantillonnée à chaque décision H4 et à chaque sortie ; une
  position ouverte en fin d'étude est valorisée, pas clôturée.
- *Taille* fixée à `D`, avant l'envoi simulé, sur les fonds propres estimés au dernier tick
  strictement antérieur à `D` ; lors d'un retournement, ils incluent le latent de la position en
  cours de sortie, dont la sortie n'est pas encore comptabilisée.
- *Écart entre entrée estimée et exécutée* : la taille n'est pas recalculée après l'exécution et
  l'entrée n'est jamais supprimée au vu de son prix. Le risque au prix exécuté et le dépassement
  du budget sont enregistrés (`DÉPASSEMENT_RISQUE`). Un refus sur écart d'exécution exigerait un
  ordre conditionnel modélisé explicitement (non implémenté).

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

## 10. Qualité des données, bougies non utilisables et positions pendant une interruption

> Règles de référence expérimentales, validées par l'opérateur le 2026-10-30 (ADR-006) après la
> revue externe. Elles s'appuient sur l'état connaissable à la clôture (`complete_at_close`,
> `flags_at_close`) et sur l'information disponible à chaque instant de décision ; aucune bougie
> n'est supprimée, comblée ou retirée pour « compresser » le temps.

### 10.1 État de qualité d'une bougie

Les états sont dérivés de l'**état connaissable à la clôture** (`complete_at_close`,
`flags_at_close`), jamais de l'audit rétrospectif (`complete`, `flags`), qui peut utiliser des
ticks postérieurs à la clôture (`docs/DATA.md` §5). L'état à la clôture est le point de départ ;
à chaque nouvelle décision, une bougie passée est réévaluée avec l'information disponible à cet
instant (par exemple un trou commencé avant sa clôture et devenu supérieur à 10 min depuis), jamais
au-delà ; une décision déjà prise n'est pas réécrite.

| État | Définition | Utilisable |
|---|---|---|
| `OK` | `complete_at_close = true`, et aucune information disponible à l'instant de décision ne la dégrade depuis | oui |
| `FERMETURE_DOCUMENTÉE` | incomplète **uniquement** à cause d'une fermeture particulière **établie par une source documentée et citée** pour cette date (calendrier publié du courtier ou du fournisseur). Un « jour férié probable » de notre calendrier de travail ne suffit pas. **Aucune bougie n'est dans cet état aujourd'hui** : aucune source de ce type n'est encore enregistrée | oui, sauf comme bougie de signal |
| `COUVERTURE_PARTIELLE` | la bougie dépasse la couverture déclarée des données (début ou fin de l'historique) : cause connue, contenu partiel | non |
| `INTERRUPTION_INEXPLIQUÉE` | trou de plus de 10 min pendant l'ouverture prévue, heures manquantes (y compris les heures absentes à la source acceptées par l'opérateur), ticks pendant la fermeture prévue, ticks invalides exclus, **jour férié probable non documenté** : le parcours du prix est inconnu sur une partie de la bougie, son extrême, sa clôture ou son true range peuvent être faux | non |

Une interruption inexpliquée n'est jamais traitée comme une fermeture connue. La fermeture
hebdomadaire (vendredi 17:00 - dimanche 17:00 New York) ne rend aucune bougie incomplète : les
bougies H4 et D1 ne la chevauchent pas.

### 10.2 Nouvelles entrées

Une entrée à la clôture de la bougie H4 `t` n'est permise que si :
1. la bougie de signal `t` est `OK` ;
2. les bougies des canaux d'entrée (`t-N .. t-1`) et de sortie (`t-M .. t-1`) sont toutes
   utilisables (`OK` ou `FERMETURE_DOCUMENTÉE`) ;
3. l'ATR est **disponible** (§10.3) ;
4. la D1 de contexte, dernière disponible au sens du §5, est utilisable ;
5. le canal D1 de 55 jours satisfait la règle stricte (§10.4).

Chaque abstention est journalisée avec la première règle qui l'a provoquée.

### 10.3 ATR de Wilder : disponibilité et réamorçage

- True range de la bougie `t` (série bid) : `TR(t) = max(H(t) − L(t), |H(t) − C(t−1)|,
  |L(t) − C(t−1)|)`. `TR(t)` est **valide** seulement si `t` **et** `t−1` sont utilisables : la
  clôture précédente doit être utilisable. Entre la dernière H4 du vendredi et la première du
  dimanche, la clôture du vendredi est utilisable (fermeture hebdomadaire prévue, écart inclus).
- L'état de l'ATR est **INDISPONIBLE** (et non nul) au début de l'historique et après toute
  bougie non utilisable `d`.
- Réamorçage : `TR(d)` et `TR(d+1)` sont invalides (`d+1` n'a pas de clôture précédente
  utilisable) ; le premier true range valide est `TR(d+2)`. L'ATR redevient disponible à la
  clôture de `d+15`, amorcé par la moyenne simple des 14 true ranges valides `TR(d+2) ..
  TR(d+15)`, puis suit la récurrence de Wilder `ATR(t) = (13 × ATR(t−1) + TR(t)) / 14`.
  Toute bougie non utilisable pendant le réamorçage le recommence.
- **Nombre de bougies réellement nécessaire** : 15 bougies utilisables consécutives après la
  dernière bougie non utilisable (`d+1 .. d+15`) ; en début d'historique, l'ATR est disponible à
  la clôture de la 15e bougie. Le canal d'entrée est plus exigeant (20 bougies utilisables puis
  une bougie de signal `OK`) : après une bougie non utilisable `d`, la première entrée possible
  est à la clôture de `d+21`.
- Le stop d'une position ouverte est fixé à l'entrée et n'est jamais recalculé : l'indisponibilité
  de l'ATR ne modifie pas une position en cours.

### 10.4 Canal D1 de 55 jours

- **Référence (retenue par l'opérateur le 2026-10-30)** : règle **stricte**. Les 55 D1 de la
  fenêtre utilisée par le filtre, et la D1 de contexte, sont toutes utilisables. Une seule D1 non
  utilisable dans la fenêtre bloque les entrées filtrées.
- Règle « ciblée » (ne bloquer que si la D1 dégradée porte l'extrême observé) : **écartée comme
  référence**. Une journée dégradée qui ne détient pas l'extrême observé peut avoir contenu un
  extrême manquant ; la baisse du taux de blocage ne prouve pas sa validité.
- Mesure de disponibilité des données (aucun calcul de stratégie). **Portée** : décisions H4 de
  la partition de développement 2015-2021 uniquement, variante **avec** filtre D1, règles 1 à 5
  du §10.2, jours fériés probables non documentés classés `INTERRUPTION_INEXPLIQUÉE`, aucune
  position ouverte supposée (une position S1 en cours, qui interdit une nouvelle entrée, n'est
  pas simulée). Avec l'**état à la clôture** : 10 912 décisions H4 ; 6 485 permises ;
  **40,6 % bloquées** (40,57 %), dont 34,4 % par le seul canal D1 (chaque 25 décembre et
  1er janvier non documenté gèle environ 55 jours de trading), 3,1 % par les canaux H4, 2,8 %
  faute d'historique D1 suffisant au début, 0,3 % sur la bougie de signal. La première mesure
  publiée (40,58 %, 6 484 permises) utilisait par erreur l'audit rétrospectif ; l'écart est d'une
  décision.
  Documenter ces fermetures par une source citée réduirait ce taux ; cela reste à faire et
  n'est pas présumé.
- La **variante sans filtre D1** (§2) est une expérience distincte, enregistrée à l'avance ; elle
  n'est soumise ni au canal D1 ni à la D1 de contexte. Aucune sélection entre les deux variantes
  n'est faite sur 2022-2023 à ce stade.

### 10.5 Position ouverte pendant une interruption

**Définitions.**
- *Franchissement observé* : une cotation du côté de déclenchement (bid pour le stop d'un achat,
  ask pour celui d'une vente ; convention du courtier à confirmer, ASSUMP-008) au niveau du stop
  ou au-delà, à un instant connu.
- *Franchissement possible mais non observable* : la position est ouverte pendant une interruption
  inexpliquée, et les cotations qui l'encadrent restent du bon côté du stop ; le parcours du prix
  pendant l'interruption est inconnu.
- *Prix de déclenchement* : le niveau du stop `S`. Ce n'est pas un prix d'exécution.
- *Prix d'exécution simulé* : le prix retenu par la simulation pour la sortie ; il dépend du type
  de stop et d'hypothèses explicites. Un coût (prime, glissement) est comptabilisé séparément du
  prix : il n'est jamais fondu dans le prix d'exécution.

**Type de stop et coûts.** Les deux hypothèses sont simulées séparément, chacune avec ses coûts :
- *stop garanti* (obligatoire sur le compte réel cible) : exécution au niveau `S` ; la prime de
  stop garanti, due lorsqu'il est déclenché, est **comptabilisée séparément** comme coût (inconnue
  pour le compte réel : paramètre de scénario, jamais zéro) ;
- *stop normal* (comparaison de recherche) : exécution au premier prix observable du côté de
  sortie au moment du déclenchement ou après ; glissement éventuel paramétré.

**Cas.**

| Cas | Constat | Stop garanti | Stop normal |
|---|---|---|---|
| A. Fermeture connue (fermeture hebdomadaire, `FERMETURE_DOCUMENTÉE`) | à la réouverture, la première cotation franchit le stop : franchissement observé | exécution à `S` ; prime comptabilisée séparément | première cotation après la réouverture (écart inclus) |
| B. Interruption inexpliquée, première cotation après l'interruption au-delà du stop | déclenchement **certain**, instant inconnu (pendant l'interruption ou à sa fin) | exécution à `S` ; prime comptabilisée séparément | **hypothèse** : première cotation observée après l'interruption ; le déclenchement a pu avoir lieu plus tôt à un autre prix ; transaction marquée |
| C. Interruption inexpliquée, cotations encadrantes du bon côté du stop | franchissement **possible mais non observable** : transaction **INDÉTERMINÉE** | scénarios H0 / H1 ci-dessous | scénarios H0 / H1 ci-dessous |

**Scénarios d'une transaction INDÉTERMINÉE.**
- H0 : le stop n'a pas été déclenché ; la position continue.
- H1 : le stop a été déclenché pendant l'interruption ; sortie enregistrée à la fin de
  l'interruption, au prix d'exécution simulé : `S` pour un stop garanti, la prime étant
  comptabilisée séparément ; pour un stop normal, `S` dégradé d'un glissement paramétré, lui
  aussi comptabilisé séparément (hypothèse, pas une observation).
- Aucun des deux n'est qualifié d'office de « prudent » : une sortie au stop peut être plus
  favorable que la suite réelle de la position, et inversement.

**Propagation.** Chaque scénario est une trajectoire distincte et complète de simulation : fonds
propres, dimensionnement, positions et décisions suivantes en découlent. La première version
publie deux politiques appliquées à tous les événements indéterminés : « aucun déclenchement non
observable » et « tous déclenchés ». L'énumération des `2^k` combinaisons, potentiellement
énorme, n'est **pas** requise ; elle pourra être ajoutée plus tard pour un petit nombre de cas.
Ces scénarios restent des hypothèses : ils ne sont **pas** présentés comme des bornes garanties
du résultat réel, faute de démonstration (dépendance au chemin). Aucune transaction indéterminée n'est supprimée :
chacune est listée avec l'interruption, les cotations qui l'encadrent, leur distance au stop et
le résultat de chaque scénario.

**Sortie stratégique et liquidation de sécurité.** Deux mécanismes distincts, chacun avec son motif
et son prix simulé explicites :
- *Sortie stratégique* (motif `SORTIE_CANAL`) : calculée seulement si la bougie de décision et les
  `M` bougies du canal de sortie sont utilisables à l'instant de décision. Exécution au premier
  prix du côté de sortie strictement postérieur à cet instant (bid pour une position acheteuse,
  ask pour une position vendeuse). Une sortie réduit l'exposition, mais cela ne rend pas fiable
  un signal calculé sur des données dégradées : sur données non utilisables, la sortie
  stratégique n'est **pas** calculée.
- *Sortie non calculable* (motif `SORTIE_NON_CALCULABLE`, journalisé) : la position reste
  protégée par son stop, inchangé ; la sortie stratégique est réévaluée à la prochaine décision
  où elle est calculable.
- *Liquidation de sécurité* (motif `LIQUIDATION_SÉCURITÉ`) : règle séparée, qui ne prétend pas
  être un signal de la stratégie. **Désactivée dans la configuration de référence** ; une variante
  paramétrée (par exemple après `P` décisions H4 consécutives sans sortie calculable) reste une
  décision ouverte. Si elle est activée : exécution au premier prix du côté de sortie strictement
  postérieur à l'instant de décision, coûts comptabilisés séparément.

## 11. Prévention des fuites temporelles

- Seules les bougies disponibles (`available_at_utc ≤ instant de décision`) sont lues ; la bougie
  D1 en cours n'est jamais utilisée ; l'audit rétrospectif (`complete`) n'est jamais lu.
- Canal calculé sur `t-N .. t-1` : la bougie du signal est exclue.
- Exécution strictement après `end_utc(t)`.
- Réglages uniquement sur 2015-2021 ; 2022-2023 pour la validation sans réglage ; 2024-2025 non
  ouvert (l'importeur le refuse).
- Les essais et variantes sont enregistrés avant évaluation (cahier §6.6, §9), y compris la
  variante sans filtre D1.
- Règles et paramètres **figés et versionnés avant** la première évaluation sur 2022-2023 :
  consulter la qualité technique de cette période ne la contamine pas, mais ajuster la stratégie
  après avoir vu ses résultats la transforme en période de développement.
- Un modèle de coûts calibré en 2026 appliqué au passé est présenté comme une **réévaluation avec
  un modèle de coûts récent**, distincte d'une simulation n'utilisant que l'information
  disponible à l'époque.
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

Règles du §10 : validées le 2026-10-30 comme référence expérimentale (ADR-006).

Décisions ouvertes : source documentée des fermetures particulières (jours fériés) ; variante de
liquidation de sécurité (désactivée dans la référence) ; énumération des scénarios H0 / H1
au-delà des deux politiques globales ; glissement du stop normal ; latence de publication `L` (§5) ; série bid ou mid ; traitement du signal du vendredi soir ; sortie temporelle ;
latence simulée ; ancrage H4/D1 (clôture New York, à comparer à l'ancrage des graphiques IG) ;
scénarios de coûts tant que les coûts IG sont inconnus ; contraintes du compte réel (distance
minimale, prime, référence de mesure).
