# Fiche S3 — Cassure après compression de volatilité (swing)

> Identifiant code : `SWING_03`. Statut : **spécifiée, proposée** (cahier des charges §6.2, §6.6) ;
> ni implémentée, ni évaluée. Règles et valeurs numériques **proposées** (ASSUMP-026), en attente
> de la décision de l'opérateur. Valeurs choisies a priori, sans lecture de données ni
> optimisation ; aucune donnée 2022-2025. Ni validation de performance ni autorisation de trading.

**Libellés.** Comme dans la fiche S2, **H4 et D1 désignent toujours des unités de temps**. Les
scénarios de stop non observable sont nommés **A** (observé seulement) et **B** (stop d'abord),
comme les scénarios H0 et H1 des rapports S1.

**Points demandés par l'opérateur le 2026-11-04** :
- reconnaissance de la compression avant la cassure : §3 et §4.1 ;
- bornes de consolidation et moment où elles sont figées : §4.1 et §4.2 ;
- confirmation de la direction : §4.3 ;
- sortie d'une fausse cassure : §5 ;
- apport par rapport à S1 : §2 et §9.

## 1. Hypothèse de marché et références

- **Hypothèse** : la volatilité se regroupe par périodes, et une période calme est plus souvent
  suivie d'une période agitée que d'une période encore plus calme. Une consolidation étroite,
  reconnue **avant** sa rupture, délimite un niveau où l'expansion qui suit a le plus de chances de
  se décider.
  - La compression ne dit **rien du sens** : la direction est donnée par la clôture qui sort de la
    consolidation, avec une expansion de volatilité mesurée, et par le contexte D1.
- **Appui** :
  - méthodes de cassure de volatilité de John Bollinger [R3] (largeur de bande faible par rapport
    à son propre historique, la « Squeeze », puis clôture hors des bandes) ;
  - règles de Bollinger [R7] : un simple contact avec une bande ne constitue pas un signal ; d'où
    la clôture hors de la consolidation **et** hors de la bande, avec une largeur en hausse (§4.3) ;
  - regroupement de la volatilité, propriété largement documentée des rendements de change.
  - Portée : ce sont des méthodes et des propriétés générales. Elles ne prouvent pas que **cette**
    variante H4 sur EUR/USD couvre ses coûts. L'adaptation au Forex est à tester (cahier §6.2).
- **Faiblesses attendues** (cahier §6.2) :
  - **fausse première cassure** : la clôture sort, puis le prix revient dans la consolidation
    (« head fake » chez Bollinger) ;
  - **compression persistante** : pas de rupture, ou plusieurs consolidations successives sans
    expansion ;
  - cassure sur une annonce : écart de prix au-delà du stop (§6.4).

## 2. En quoi S3 diffère de S1

S1 et S3 entrent toutes deux sur la clôture d'une H4 au-delà d'un extrême récent, dans le sens du
contexte D1. Le cahier note qu'elles **peuvent partager des risques** (§6.6). S3 n'apporte quelque
chose que si ses trois différences changent les transactions prises ou leur issue :

| | S1 — cassure Donchian | S3 — cassure après compression |
|---|---|---|
| Condition avant la cassure | aucune : toute clôture au-delà de l'extrême des 20 H4 | **état de volatilité mesuré** : largeur de bande dans les 20 % les plus basses de ses 360 dernières valeurs, sur 6 H4 consécutives, et consolidation d'au plus 3 × `A` |
| Niveau franchi | extrême glissant des 20 H4 précédentes, recalculé à chaque bougie | **bornes figées** d'une consolidation de 6 H4, connues avant la cassure (§4.1) |
| Confirmation | clôture au-delà du canal | clôture hors de la consolidation **et** hors de la bande de Bollinger, **avec** une largeur de bande en hausse (§4.3) |
| Nombre de tentatives | tant que les clôtures franchissent le canal | **une seule cassure par consolidation** (la première clôture hors de la boîte la consomme) |
| Stop | 2 × ATR H4 depuis la clôture du signal | **structurel** : au-delà de la borne opposée de la consolidation, plus 0,25 × `A` |
| Sortie d'une fausse cassure | aucune règle propre : stop ou canal opposé de 10 H4 | **réintégration** : première clôture H4 revenue dans la consolidation (§5) |
| Sortie d'une cassure qui tient | canal opposé de 10 H4 | **suiveuse** : clôture H4 de l'autre côté de la moyenne de Bollinger (20 H4) |
| Profil attendu (non mesuré) | beaucoup de faux départs en marché latéral, gains longs | moins d'entrées ; faux départs coupés plus tôt ; gains longs si l'expansion dure |

**Ce que S3 doit démontrer**, mesuré à l'étape 4 (§9) :
1. que ses entrées ne sont pas pour l'essentiel les mêmes que celles de S1 (même H4, même sens) ;
2. que la sortie sur réintégration coupe les fausses cassures pour une perte inférieure au stop ;
3. que les deux stratégies ne perdent pas en même temps.

Si les entrées coïncident largement et que les pertes sont simultanées, S3 est **redondante**
avec S1, même si son net est positif. S3 est évaluée **seule** ; le chevauchement avec S1 est
mesuré, sans portefeuille combiné (comme S2).

Le stop de S3 **n'est pas forcément plus proche** que celui de S1. La distance va de la clôture de
cassure à la borne opposée de la boîte, plus la marge, soit au moins la hauteur de la boîte plus
0,25 × `A`, et elle peut dépasser 2 × `A`. La taille s'y ajuste (§6.2).

## 3. Données, unités et définitions

Mêmes données, ancrage New York 17:00, états de bougie, règles de disponibilité, d'exécution et de
fermeture que S1 et S2 (`S1_DONCHIAN.md` §5, §10, §11 ; ADR-006, ADR-009 ; `S2_PULLBACK.md` §3).
Série de calcul : **bid**. Latence de publication `L = 0`.

**Fréquence des décisions** : à la disponibilité de chaque H4. Comme S1, les H4 et D1 qui se
terminent au même instant sont utilisables ensemble, puis indicateurs mis à jour, puis sortie,
puis entrée (S1 §5).

**H4 utilisable** : `OK` ou `FERMETURE_DOCUMENTÉE` (S1 §10.1). **Continuité** : une suite de `n`
H4 « consécutives » désigne `n` H4 **prévues** successives du calendrier de cotation, toutes
présentes et utilisables. La fermeture hebdomadaire ne rompt pas la continuité, puisqu'aucune H4
n'y est prévue ; une H4 prévue mais absente ou inutilisable la rompt (règle de continuité de S2).

**Bandes de Bollinger** à la disponibilité de la H4 `t`, sur les 20 dernières H4 consécutives
`t − 19 … t` (la bougie `t` incluse : sa clôture est connue à cet instant) :
- moyenne `M(t)` = moyenne arithmétique des 20 `bid_close` ;
- écart type `σ(t)` = écart type **de population** (division par 20) de ces clôtures ;
- bande haute `U(t) = M(t) + 2σ(t)`, bande basse `B(t) = M(t) − 2σ(t)` ;
- **largeur relative** `W(t) = (U(t) − B(t)) / M(t) = 4σ(t) / M(t)`.

`M`, `U`, `B` et `W` ne sont **pas calculables** si l'une des 20 H4 n'est pas utilisable ou si la
suite n'est pas continue. Après une rupture, il faut 20 nouvelles H4 consécutives.

**Compression de la H4 `t`** (relative à son propre historique, cahier §6.2) :
- **historique de référence** `R(t)` : les valeurs `W` calculables des **360 H4 prévues qui
  précèdent `t`** (`t` exclue), soit environ 12 semaines de cotation ;
- calculable seulement si `W(t)` l'est et si `R(t)` contient **au moins 240 valeurs** ;
- seuil `Q(t)` : **20e centile au rang le plus proche**, c'est-à-dire la `⌈0,20 × N⌉`-ième plus
  petite valeur de `R(t)`, où `N` est le nombre de valeurs de `R(t)` ;
- la H4 `t` est **comprimée** si `W(t) ≤ Q(t)`.

La H4 `t` est comparée à son passé seulement : aucune valeur future n'entre dans `Q(t)`.

**ATR (`A`)** : Wilder 14 sur les H4, true range bid, avec la continuité des H4 prévues (lecture
de S2). Une seule valeur, fixée à la reconnaissance de la consolidation `F` (§4.1) : l'ATR de la
dernière H4 disponible à `F`. Elle sert à la hauteur maximale et à la marge du stop.

**Contexte D1** : celui de S1, inchangé (S1 §3, §10.4). La dernière D1 disponible est haussière si
`bid_close` est au-dessus du milieu du canal des 55 D1, baissière si elle est au-dessous ; égalité
ou D1 non utilisable : pas de contexte.

**Amorçage** : il faut 20 H4 pour une première largeur et 240 largeurs pour un premier seuil, soit
environ 9 semaines de cotation. Le canal D1 demande 55 D1. Avec un historique qui commence le
2015-01-01, aucune entrée n'est possible avant la mi-mars 2015 environ ; ces décisions sont
journalisées comme non évaluables.

## 4. Consolidation et entrée

Règles écrites pour un achat ; la vente est donnée au §4.4.

### 4.1 Reconnaissance de la consolidation (instant `F`)

À la disponibilité de la H4 `t`, une **consolidation** (« boîte ») est reconnue si toutes les
conditions suivantes sont réunies :
1. aucune boîte n'est active ;
2. les **6 H4 consécutives** `t − 5 … t` sont toutes **comprimées**, chacune selon son propre seuil
   calculé à sa propre disponibilité ;
3. ces 6 H4 commencent toutes **à la fin de la boîte précédente ou après** : une bougie ne sert
   jamais à deux boîtes ;
4. `A` est disponible à `F` ;
5. **hauteur** `BH − BL ≤ 3 × A`, avec `BH = max bid_high[t − 5 … t]` et `BL = min bid_low[t − 5 … t]`.

`F` est la disponibilité de la H4 `t`. Si la condition 5 échoue, aucune boîte n'est créée (motif
« consolidation trop large ») et la fenêtre de 6 H4 glisse à la H4 suivante.

La reconnaissance ne dépend **ni du contexte D1, ni d'une position ouverte** : à `F`, le sens est
inconnu.

**Bornes figées à `F`** : `BH` (borne haute), `BL` (borne basse), ainsi que
`AH = max ask_high[t − 5 … t]`, qui sert au stop d'une vente. Elles ne sont **jamais mises à jour**
ensuite : une mèche au-delà d'une borne, ou de nouvelles H4 comprimées, ne les déplacent pas.

### 4.2 Vie de la boîte

À chaque H4 disponible après `F` :
- **clôture dans la boîte** (`BL ≤ bid_close ≤ BH`) : la boîte reste active, même si le
  `bid_high` ou le `bid_low` dépasse une borne ;
- **première clôture strictement hors de la boîte** : c'est la **cassure** (§4.3). La boîte est
  **consommée**, que l'entrée soit décidée ou refusée ; elle ne produit **qu'une seule cassure**.
  - Une fausse cassure suivie d'une rupture de l'autre côté ne donne donc pas de seconde entrée
    sur la même boîte. C'est un choix prudent, qui exclut d'exploiter le « head fake ».
- **H4 prévue absente ou inutilisable** après `F` : sa clôture est inconnue. La boîte est
  **abandonnée** (`DONNÉES_BOÎTE_INCOMPLÈTES`) ; une absence de données ne prolonge jamais la
  boîte.
- **Durée maximale** `T_box = 30` H4 prévues après `F`, soit environ 5 jours de cotation :
  - sans cassure, la boîte **expire** à la fin de la 30e ;
  - une cassure à cette 30e H4 est encore admise.
  - C'est la réponse à la **compression persistante** : une nouvelle boîte exige 6 nouvelles H4
    comprimées, commencées après la fin de celle-ci.

Une boîte peut être reconnue et consommée pendant qu'une position S3 est ouverte. Sa cassure est
alors journalisée, non évaluée (comme S2).

### 4.3 Cassure, direction et décision d'entrée (instant `D`)

La **cassure haussière** est la première H4 `h` après `F` telle que `bid_close[h] > BH`. `D` est
la disponibilité de `h`.

La direction est **celle de la clôture** ; elle n'est jamais déduite de la compression. À `D`,
l'entrée est décidée si, en plus :
1. **expansion de volatilité** : `bid_close[h] > U(h)` (clôture au-dessus de la bande haute) **et**
   `W(h) > W(h − 1)` (bande qui s'élargit) ; les deux valeurs doivent être calculables ;
2. **contexte D1 haussier** à `D` (S1) ;
3. aucune position S3 ouverte ; marché ouvert à `D` ;
4. taille admise et distance du stop au moins égale au minimum du courtier (S1 §7, §8).

Sinon la cassure est **refusée**, avec la première cause (§8) ; la boîte reste consommée.

Exécution : ordre au marché au premier tick strictement postérieur à `D`, achat à l'ask (S1 §5).

Il n'y a **pas de rapport gain/risque** : S3 n'a pas de cible (§5). Le refus pour taille joue le
rôle du contrôle de risque.

### 4.4 Vente (règle symétrique)

| Élément | Achat | Vente |
|---|---|---|
| Boîte, hauteur, compression | identiques | identiques |
| Cassure | première `bid_close > BH` | première `bid_close < BL` |
| Expansion | `bid_close[h] > U(h)` et `W(h) > W(h − 1)` | `bid_close[h] < B(h)` et `W(h) > W(h − 1)` |
| Contexte D1 | haussier | baissier |
| Stop | `BL − 0,25 × A` (niveau bid) | `AH + 0,25 × A` (niveau ask) |
| Réintégration | clôture H4 `bid_close ≤ BH` | clôture H4 `bid_close ≥ BL` |
| Sortie suiveuse | clôture H4 `bid_close < M(t)` | clôture H4 `bid_close > M(t)` |
| Exécution d'entrée | ask du premier tick après `D` | bid du premier tick après `D` |

Asymétrie assumée, comme dans S2 (ADR-015) : la structure est mesurée sur la série bid ; le stop
d'une vente est placé au-dessus de l'extrême `ask_high` de la boîte (côté de sortie).

## 5. Stop et sorties

- **Stop initial** (structurel, derrière la consolidation) :
  - achat : `BL − b × A` ; vente : `AH + b × A` ; `b = 0,25` ;
  - stop garanti simulé, prime à son déclenchement (S1 §6, §10.5) ;
  - jamais élargi ni déplacé.
- **Sortie sur réintégration** (fausse cassure) : à la disponibilité de toute H4 postérieure à
  l'exécution dont `bid_close ≤ BH` (achat), la position est clôturée au marché au premier tick
  strictement postérieur. Revenir dans la boîte, ou sur sa borne, invalide la cassure.
  - La perte est alors en général inférieure à celle du stop : on sort près de `BH`, alors que le
    stop est sous `BL`.
  - Ce n'est pas garanti : une seule H4 peut traverser toute la boîte.
- **Sortie suiveuse** (cassure qui tient) : à la disponibilité de toute H4 postérieure à
  l'exécution dont `bid_close < M(t)` (achat), sortie au marché au premier tick strictement
  postérieur.
  - Juste après la cassure, `M` est en général à l'intérieur de la boîte, et la réintégration
    joue avant.
  - Quand l'expansion dure, `M` monte au-dessus de `BH` et devient la sortie active.
- Les deux règles sont évaluées à chaque H4. Si les deux sont vraies, le motif journalisé est
  `RÉINTÉGRATION`. Le stop garanti reste en place jusqu'à l'exécution de la sortie.
- **Pas de cible, pas de sortie temporelle** : la sortie suiveuse limite la durée.
- **Conservation nocturne et week-end** : une position passe les nuits (swing) et paie le
  financement de recherche. Elle est aussi conservée pendant la fermeture hebdomadaire, comme dans
  S1, avec son stop garanti : l'écart de réouverture est un risque assumé et mesuré (§6.3, §6.4).
  La politique de conservation pendant les nuits et le week-end reste une décision ouverte du
  cahier (§16.3) ; la fiche n'en préjuge pas pour l'exploitation.
- **Sortie non calculable** :
  - H4 non utilisable : la position est maintenue avec son stop (S1 §10), et la sortie est
    évaluée à la H4 utilisable suivante ;
  - H4 utilisable mais `M(t)` non calculable (continuité rompue) : la réintégration est évaluée,
    la sortie suiveuse non, et la ligne le journalise.

## 6. Exécution et risque

### 6.1 Chronologie

Celle de S1 (§5) : décision à la disponibilité de la H4, état lu strictement avant `D`,
exécution au premier tick strictement postérieur. Priorité sur un même tick : silence, stop,
sortie en attente, entrée en attente (ASSUMP-024).

### 6.2 Taille

Contrôleur de risque inchangé :
- budget = 0,25 % des fonds propres estimés à `D` ;
- perte estimée au stop = (ask − stop + glissement) × 10 000 + prime de stop garanti + financement
  d'une nuit, convertie en EUR au taux 1/bid, majorée de 0,5 % ;
- taille arrondie vers le bas au pas de 0,1 ; refus si 0,1 contrat dépasse le budget.

Coûts de recherche de la référence S1 (`RESEARCH_COSTS`, non confirmés chez IG).

### 6.3 Premier prix au-delà du stop

Si le premier tick après `D` est déjà au-delà du stop, la convention de la référence S1
s'applique : exécutée puis liquidée, comptée (`STOP_DÉPASSÉ_À_L'EXÉCUTION`). Un passage de rejet
n'est fait que si de tels cas existent.

### 6.4 Trous de cotation

S3 n'a qu'une borne de prix, le stop : les sorties de réintégration et suiveuse se décident sur
des clôtures. Pendant une interruption inexpliquée (S1 §10.5), seul un franchissement du stop
peut être non observable.
- **Scénario A** (observé seulement) : la position continue, sauf si la première cotation après le
  trou est au-delà du stop.
- **Scénario B** (stop d'abord) : sortie au niveau du stop garanti, à la fin du trou.

Chaque transaction concernée est marquée **INDÉTERMINÉE**. B est rejoué en entier seulement s'il en
existe une.

**Annonces** : aucun calendrier d'annonces n'est disponible ni validé dans le projet. Aucune
annonce n'est donc filtrée dans la version de référence. Une compression précède souvent une
annonce, et sa cassure peut sauter le stop. Ce risque est couvert par le stop garanti simulé et
mesuré par les dépassements au premier tick ; il n'est pas modélisé autrement.

## 7. Exemple horodaté (achat, données inventées)

> Prix **fictifs** ; aucune donnée n'a été lue. Hiver : H4 à 22:00, 02:00, 06:00, 10:00, 14:00 et
> 18:00 UTC. `A` = 12 pips.

| Instant (UTC) | Événement | Règle |
|---|---|---|
| lun. 11 févr. 22:00 → mar. 12 févr. 22:00 | 6 H4 consécutives, chacune comprimée : par exemple, la H4 18-22 a `W` = 0,0016, sous son seuil `Q` = 0,0019 calculé sur 360 H4 précédentes (352 largeurs calculables) | §3 |
| mar. 12 févr. 22:00 | **`F`**. `BH` = 1,1350, `BL` = 1,1322, hauteur 28 pips ≤ 3 × `A` = 36 : **boîte reconnue et figée**. `AH` = 1,1352. Expiration à la fin de la 30e H4 suivante, mar. 19 févr. 22:00 | §4.1, §4.2 |
| mer. 13 févr. 02:00 | H4 22-02 : `bid_high` 1,1356 au-dessus de `BH`, mais clôture 1,1347 : **pas de cassure**, bornes inchangées | §4.2 |
| mer. 13 févr. 10:00 | H4 06-10 clôture à 1,1366 > `BH` : **cassure**, la boîte est consommée. `U` = 1,1358 et `W` passe de 0,0016 à 0,0021 : **expansion**. D1 du 12 févr. clôture à 1,1340, au-dessus du milieu de son canal de 55 D1 (1,1290) : contexte haussier. **Décision `D` = 10:00** | §4.3 |
| mer. 13 févr. 10:00 | Dernier tick avant `D` : bid 1,1366, ask 1,1367. Stop = 1,1322 − 0,25 × 0,0012 = **1,1319**. Perte estimée = (1,1367 − 1,1319 + 0,00005) × 10 000 + 1,2 + 1,0 = 50,70 USD par contrat, soit 50,70 / 1,1366 × 1,005 = 44,83 €. Budget 5,00 € → **0,1 contrat** (4,48 €) | §6.2 |
| mer. 13 févr. 10:00:00,2 | Premier tick après `D` : **achat à l'ask 1,1368** | §6.1 |
| *Suite 1, fausse cassure* : mer. 13 févr. 14:00 | H4 10-14 clôture à 1,1349 ≤ `BH` : **réintégration**. Sortie au premier tick après 14:00, bid 1,1348. Environ −20 pips de prix, contre −49 pips au stop | §5 |
| *Suite 2, cassure qui tient* | Les clôtures restent au-dessus de `BH` et de `M` ; `M` dépasse `BH` le 15 févr. La première H4 qui clôture sous `M` déclenche la **sortie suiveuse** | §5 |

## 8. Abstentions (première cause journalisée)

Ordre d'évaluation à chaque décision H4 sans entrée :
1. **données** :
   - H4 de décision non utilisable ;
   - D1 de contexte non utilisable ;
   - largeur ou seuil de compression non calculable ;
   - `A` indisponible à `F` ;
   - boîte abandonnée (`DONNÉES_BOÎTE_INCOMPLÈTES`) ;
2. **position déjà ouverte** (cassure non évaluée, boîte consommée) ;
3. **pas de boîte** : pas de compression, moins de 6 H4 comprimées consécutives, ou consolidation
   trop large ;
4. **boîte expirée** ;
5. **pas de cassure** : clôture dans la boîte ;
6. **pas d'expansion** : clôture dans la bande, ou largeur de bande qui ne s'élargit pas ;
7. **contexte D1 contraire ou absent** ;
8. **marché fermé** à `D` ;
9. **taille** : 0,1 contrat au-dessus du budget, ou distance du stop sous le minimum du courtier.

Le journal garde une ligne par décision H4, avec seulement ce qui était connu à cet instant :
- largeur, seuil et nombre de valeurs de référence ;
- H4 comprimées consécutives ;
- boîte (`F`, `BH`, `BL`, `AH`, `A`, H4 restantes) ;
- bandes, contexte D1, cotation, compte, position ;
- l'action décidée, sans résultat ultérieur (comme S1 et S2).

## 9. Protocole de test et lecture des résultats

**Étape 0 — fiche figée** : décision de l'opérateur sur ASSUMP-026.

**Étape 1 — implémentation hors ligne et tests synthétiques uniquement** (aucune donnée réelle) :
- largeur de bande avec écart type de population ;
- 20e centile au rang le plus proche, H4 courante exclue ; minimum de 240 valeurs ;
- continuité et rupture après une H4 absente ; amorçage ;
- reconnaissance après 6 H4 comprimées, refus d'une consolidation trop large ;
- bornes figées malgré une mèche ; bougies jamais partagées entre deux boîtes ;
- abandon pour H4 manquante ; expiration à la 30e H4 ;
- une cassure par boîte ; refus sans expansion ; refus sur contexte D1 contraire ;
- cassure pendant une position ;
- stop structurel ; sorties sur réintégration et suiveuse, avec priorité du motif ;
- sortie non calculable ; vente symétrique ;
- exemple du §7 reproduit ;
- premier prix au-delà du stop ; scénarios A et B.

**Étape 2 — non-régression de S1** : si le moteur S1 est partagé ou modifié, rejeu de la référence
S1 sur avril-juin 2019, qui doit rester identique (comme S2).

**Étape 3 — disponibilité des données** (aucun résultat de stratégie), sur 2015-2021 :
- part des décisions H4 où la compression n'est pas calculable, par cause ;
- boîtes abandonnées pour données ;
- H4 comprimées, boîtes reconnues, consolidations trop larges, boîtes expirées.

**Étape 4 — passages pré-enregistrés** sur 2015-2021, avec les paramètres de la référence S1 :
trajectoire continue, 2 000 €, 0,25 %, minimum et pas de 0,1, mêmes coûts.
- **Référence S3 : D1 → H4** (§4), scénario A, puis B seulement s'il existe une transaction
  indéterminée, et rejet à l'exécution seulement si un stop est déjà dépassé au premier tick.
- **Comparaison secondaire enregistrée à l'avance : H4 seule, sans contexte D1**. C'est la
  variante plus simple demandée par le cahier (§6.5). Elle ne remplace pas la référence, même si
  son résultat est meilleur.
- Protocole figé avant lancement ; journaux et sorties détaillées hors Git ; bilan agrégé dans
  `docs/experiments/`.

**Rapporté pour chaque passage** :
- **parcours** : H4 comprimées → boîtes reconnues (refusées trop larges, abandonnées pour données,
  expirées sans cassure) → cassures → refus (position ouverte, expansion, contexte D1, marché,
  taille) → entrées décidées → positions effectivement ouvertes ;
- transactions ; brut, coûts, net ; sorties par motif (stop, réintégration, suiveuse) ;
  globalement et par année ;
- **part des fausses cassures** (sorties sur réintégration) et leur perte moyenne en multiples du
  risque, comparée à celle des stops ;
- drawdown au tick en euros, **véritable drawdown relatif maximal**, premier franchissement de 6 %,
  durée de récupération ;
- net sans la meilleure transaction ; transactions indéterminées ; dépassements du budget ;
- mesures du cahier (§9) : espérance nette en unités de risque, profit factor, gain et perte
  moyens, durée d'exposition, mois sans opération et mois déficitaires conservés.

**Comparaison à la référence S1**, ce qui mesure l'apport de S3 (§2) :
- **coïncidence des entrées** : part des entrées S3 décidées sur la même H4 et dans le même sens
  qu'un signal de la référence S1, entrée S1 décidée ou non ;
- chevauchement des positions dans le temps (même sens, sens opposé) ;
- **pertes simultanées** : transactions S3 perdantes qui chevauchent une transaction S1
  perdante ;
- nets annuels côte à côte.

**Lecture des résultats** (règles de S2 §9, ADR-015) :
1. **Net** : un net strictement positif dans chaque scénario publié est un résultat favorable
   sur la période de développement, sans plus. Un signe différent entre A et B signifie que le
   résultat dépend des trous de cotation.
2. **Concentration** : le net sans la meilleure transaction est un indicateur, pas un motif
   automatique de rejet. 6 % de drawdown relatif est un seuil de revue ; la trajectoire continue.
3. **Redondance avec S1** : si la plupart des entrées S3 coïncident avec des signaux S1, ou si les
   pertes S3 sont surtout simultanées à des pertes S1, la conclusion est que S3 apporte peu par
   rapport à S1, quel que soit son net. Ce constat est rapporté ; aucun seuil automatique n'est
   fixé.
4. **Effectif** : avec peu de transactions, aucune conclusion statistique (constat de S2).

Un résultat défavorable est rapporté tel quel ; aucun paramètre n'est ajusté.

**Interdits** : aucune donnée 2022-2025 ; aucun réglage après lecture des résultats ; aucun
entraînement ; aucun ordre ; le sélecteur IA n'est pas concerné.

## 10. Paramètres proposés (ASSUMP-026)

| Paramètre | Valeur | Rôle |
|---|---|---|
| Bandes de Bollinger | 20 H4, 2 écarts types de population, `bid_close` | largeur `W`, bandes `U` / `B`, moyenne `M` |
| Historique de compression | 360 H4 prévues précédentes, au moins 240 largeurs calculables | « propre historique » de la largeur |
| Seuil de compression | 20e centile (rang le plus proche) | H4 comprimée si `W ≤ Q` |
| Durée de compression | 6 H4 consécutives comprimées | reconnaissance de la boîte |
| Hauteur maximale | 3 × `A` | consolidation délimitée |
| ATR (`A`) | Wilder 14 H4, continuité S2, fixé à `F` | hauteur, marge du stop |
| `T_box` | 30 H4 prévues après `F` | durée de vie de la boîte |
| Expansion | clôture hors bande et `W(h) > W(h − 1)` | confirmation de la cassure |
| Contexte D1 | milieu du canal de 55 D1 (S1) | sens admis |
| `b` | 0,25 × `A` | marge du stop au-delà de la borne opposée |
| Sorties | réintégration (`bid_close ≤ BH`), suiveuse (`bid_close < M`) | fausse cassure, cassure qui tient |

**Raisons des valeurs** (a priori, aucune mesurée) :
- **Bandes** : 20 périodes et 2 écarts types sont les réglages usuels de Bollinger.
- **Historique** : environ 12 semaines couvrent plusieurs régimes de volatilité sans remonter trop
  loin.
- **Seuil et durée** :
  - le 20e centile est une compression nette, sans être rare au point de ne jamais se produire ;
  - 6 H4 consécutives font un jour de cotation, assez pour une consolidation et non pour une
    simple pause.
- **Hauteur et marge** :
  - 3 × `A` exclut les dérives lentes qui comprimeraient les bandes sans former de consolidation ;
  - 0,25 × `A` est la marge de S2.
- **Durée de vie** : 30 H4 font environ une semaine de cotation, comme le `T_max` de S2.

**Domaine de recherche** (cahier §6.6) : **aucun** dans ce lot. Une seule valeur par paramètre,
sans grille ni optimisation. Le test de sensibilité autour des valeurs choisies, prévu par le
cahier (§9), n'est pas inclus ; il demanderait un protocole et une décision distincts (§11).

## 11. Points soumis à la décision de l'opérateur

1. Valeurs du §10 (ASSUMP-026).
2. **Contexte D1 dans la référence** et H4 seule en comparaison secondaire. L'ordre inverse est
   possible, mais la référence suivrait alors l'unité unique, alors que le cahier prévoit D1 → H4.
3. **Une seule cassure par boîte**, sans seconde entrée de l'autre côté après une fausse cassure.
4. **Ni cible, ni sortie temporelle** : la sortie suiveuse limite la durée.
5. **Aucun filtre d'annonces** tant qu'aucun calendrier n'est validé (§6.4).
6. Réintégration jugée sur la **clôture** H4, pas sur un prix intra-bougie : la sortie attend la
   fin de la H4, et le stop reste la seule protection en cours de bougie.
7. **Deux sorties dans une même version.** Le cahier (§6.2) prévoit une « sortie suiveuse ou
   sortie sur réintégration selon la version testée », donc plutôt deux versions. Pour une seule
   version de référence, la fiche les combine : la réintégration traite la fausse cassure, la
   suiveuse la cassure qui tient. Leur apport respectif ne sera donc pas mesuré séparément. Les
   séparer demanderait deux versions pré-enregistrées.
8. **Sensibilité aux paramètres** (cahier §9) : non incluse dans la référence ; à décider plus
   tard, avec son propre protocole, sans réglage d'après les résultats.

Hors de cette version : sortie à objectif (projection de la hauteur), filtre de volume (pas de
volume fiable sur le Forex de gré à gré), seconde entrée après une fausse cassure, déclenchement
sur une unité plus fine.
