# Fiche S2 — Reprise de tendance après repli (swing)

> Identifiant code : `SWING_02`. Statut : **spécifiée** (cahier des charges §6.2, §6.6). Règles et
> valeurs numériques **approuvées pour la recherche hors ligne** (ASSUMP-025, ADR-015, 2026-11-03),
> au commit `a10a779` complété des décisions du §11. Ni validation de performance ni autorisation
> de trading. Valeurs choisies a priori, jamais optimisées ; aucune donnée 2022-2025.

**Libellés.** Dans cette fiche, **H1, H4 et D1 désignent toujours des unités de temps** (bougies
d'une heure, de quatre heures, d'un jour). Les deux scénarios de stop non observable du moteur
(appelés H0 et H1 dans les rapports S1) sont nommés ici **scénario A** et **scénario B** ; s'y ajoute
un **scénario C** propre à S2 (§7).

**Points demandés par l'opérateur le 2026-11-03** : chronologie du signal → §4.4 et §5 ; définition et
durée de la configuration → §3, §4.2 et §4.3 ; vente → §4.5 ; comparaison H4 → §4.6 ; exécution et
risque → §6 et §7 ; lecture des résultats → §9.

## 1. Hypothèse de marché et références

- **Hypothèse** : dans une tendance de fond intacte, une correction qui revient vers un niveau déjà
  connu (ancienne résistance devenue support, ou l'inverse) se termine plus souvent par une reprise
  dans le sens de la tendance que par un retournement. Entrer quand la structure de la correction
  casse sur l'unité inférieure place le stop au-delà du niveau qui invaliderait la reprise, avec une
  cible naturelle : l'extrême précédent.
- **Appui** : configurations de continuation décrites par CME [R2] (cahier §6.2) ; documentation
  technique, pas une preuve statistique de ce système.
- **Faiblesses attendues** : correction qui devient un retournement (stop) ; tendance qui repart
  sans repli suffisant (pas d'entrée) ; cible proche de l'entrée une fois les coûts comptés.

## 2. En quoi S2 diffère de S1

| | S1 — cassure Donchian | S2 — reprise après repli |
|---|---|---|
| Moment d'entrée | force : clôture au-delà de l'extrême des 20 H4 | faiblesse dans la tendance : après une correction |
| Tendance | milieu du canal D1 de 55 jours | sommets et creux D1 confirmés (pivots) |
| Unités | D1 → H4 | D1 → H4 → H1 (déclenchement) |
| Stop | 2 × ATR H4 depuis la clôture du signal | structurel : au-delà du creux du repli |
| Sortie | suiveuse : canal opposé de 10 H4 | cible à l'extrême précédent, stop, sortie temporelle |
| Profil attendu (non mesuré) | peu de gagnants, gains longs | plus de gagnants, gains bornés par la cible |

S1 et S2 partagent le risque d'une fin de tendance (cahier §6.6). S2 est évaluée **seule** ; le
chevauchement avec S1 est mesuré, sans portefeuille combiné.

## 3. Données, unités et définitions

Mêmes données, ancrage New York 17:00, états de bougie, règles de disponibilité et d'exécution que
S1 (`S1_DONCHIAN.md` §5, §10, §11 ; ADR-006, ADR-009). Série de calcul : **bid**. Latence de
publication `L = 0` : une bougie est disponible à sa clôture.

**Pivots.** Bougie `i` d'une unité donnée, ordre `p` :
- **sommet** si `bid_high[i]` est **strictement** supérieur au `bid_high` de chacune des `p`
  bougies qui précèdent et des `p` bougies qui suivent ;
- **creux** si `bid_low[i]` est strictement inférieur au `bid_low` de chacune de ces bougies ;
- **égalité** avec l'une de ces bougies : la bougie `i` n'est pas un pivot. Deux sommets égaux
  voisins ne forment donc aucun sommet (choix prudent : pas de pivot ambigu) ;
- les `2p + 1` bougies doivent être utilisables (`OK` ou `FERMETURE_DOCUMENTÉE`), sinon pas de
  pivot ;
- le pivot est **connu à la disponibilité de la bougie `i + p`**, jamais avant ; cet instant est
  sa date de confirmation.

| Unité | Ordre `p` | Bougies nécessaires | Délai de confirmation après la clôture du pivot |
|---|---|---|---|
| D1 | 2 | 5 D1 | 2 jours de cotation |
| H4 | 3 | 7 H4 | 12 heures de cotation |
| H1 | 2 | 5 H1 | 2 heures de cotation |

**ATR.** Wilder 14 sur les H4, true range bid, règles de disponibilité et de réamorçage de S1
(§10.3). La configuration utilise **une seule valeur, `A`**, fixée à l'instant d'identification
`I` (§4) : l'ATR de la dernière H4 disponible à `I`. Zone, invalidation et marge du stop utilisent
cette même valeur jusqu'à la fin de la configuration. ATR indisponible à `I` : pas de
configuration.

**Fréquence des décisions.** Une décision S2 a lieu à la disponibilité de chaque bougie H1. Aux
instants où plusieurs unités clôturent ensemble (toutes les 4 heures pour H1 et H4 ; à 17:00 New
York pour H1, H4 et D1), **les trois bougies qui se terminent à cet instant sont utilisables par
cette décision** : elles sont rendues disponibles dans l'ordre H1, H4, D1, puis les indicateurs et
pivots sont mis à jour, puis la sortie est évaluée, puis l'entrée (S1 §5). Un pivot confirmé par
une bougie qui se termine à cet instant est donc connu de la décision.

## 4. Configuration et entrée

Les règles sont écrites pour un achat (§4.1 à §4.4) ; la vente est donnée au §4.5. Toutes les
comparaisons de structure utilisent la série bid ; stop et cible sont comparés au côté de sortie
(§6.4).

### 4.1 Tendance D1

À l'instant considéré, sur les pivots D1 connus : les deux derniers sommets sont croissants, les
deux derniers creux sont croissants, et la clôture de la dernière D1 disponible est au-dessus du
dernier creux confirmé. Vérifiée à l'identification `I` **et** à la décision d'entrée `D`.

### 4.2 Identification de la configuration (instant `I`)

- **`E`** : sommet H4 qui vient d'être confirmé. `I` = sa date de confirmation (disponibilité de
  la H4 `E + 3`).
- **`K`** : le sommet H4 confirmé le plus récent, antérieur à `E` et strictement inférieur à `E`
  (ancienne résistance que la jambe vers `E` a franchie). Sans `K` : pas de configuration.
- **Zone admissible** : `[K − z × A ; K + z × A]`, avec `z = 0,5`. **Borne basse** `K − z × A`,
  **borne haute** `K + z × A`.
- La configuration n'est créée que si la tendance D1 est haussière à `I`, si `A` est disponible, si
  les bougies de la période de repli déjà écoulée sont utilisables (§4.3) et si aucune H4 clôturée
  entre la fin de `E` et `I` n'a de `bid_close` sous la borne basse.

### 4.3 Vie de la configuration

- **Contact** : une bougie H1 qui **commence à `I` ou après** et dont l'intervalle recoupe la zone :
  `bid_low ≤ borne haute` **et** `bid_high ≥ borne basse`. Une bougie entièrement sous la zone (par
  exemple de 1,1430 à 1,1435 pour une zone 1,1440-1,1460) ou entièrement au-dessus n'est pas un
  contact. Un contact antérieur à `I` ne compte pas. Le contact est **mesuré sur les extrêmes de la
  bougie** : il ne prouve pas qu'une cotation a eu lieu dans la zone (le prix a pu la traverser par
  un saut).
- **Creux du repli `PL`** : plus bas `bid_low` des H1 depuis la fin de la bougie `E` jusqu'à la
  dernière H1 disponible (y compris avant `I`).
- **Données manquantes pendant le repli** : si une H1 de cette période (de la fin de `E` à la
  décision) est absente ou inutilisable, son vrai plus bas est inconnu et `PL` pourrait être trop
  haut ; de même, si une H4 de cette période est absente ou inutilisable, l'invalidation ne peut pas
  être vérifiée. Dans les deux cas, la configuration est **abandonnée** avec un motif explicite
  (`DONNÉES_REPLI_INCOMPLÈTES`). Une absence de données ne resserre jamais le stop et ne prolonge
  jamais le délai. (H1 et H4 prévues pendant la fermeture hebdomadaire : aucune n'est attendue.)
- **Invalidation (repli trop profond)** : la première H4 dont la **clôture bid est strictement
  sous la borne basse `K − z × A`** (et non sous `K`) abandonne la configuration.
- **Reprise sans entrée** : si une H1 atteint `bid_high > E` avant l'entrée, la configuration est
  abandonnée.
- **Nouveau sommet H4** confirmé avant l'entrée : s'il est **supérieur à `E`**, il remplace la
  configuration (nouvel `E`, nouveau `K`, nouvel `I`, nouvel `A`, compteurs remis à zéro) ; s'il est
  inférieur ou égal à `E`, c'est un sommet de la correction : il ne change pas la configuration.
- **Durée maximale (`T_max = 30` H4)** : le compteur part de la **première H4 prévue après la
  bougie `E`** ; il compte les H4 du calendrier de cotation, qu'elles soient complètes ou non (une
  bougie manquante ne prolonge pas le délai ; elle abandonne d'ailleurs la configuration). La
  configuration expire à la fin de la 30e H4 : une entrée décidée à cet instant est encore
  permise, aucune après. Les trois H4 de confirmation font partie des 30. Le week-end ne compte pas.
- Une configuration ne produit **qu'une entrée**.

### 4.4 Séquence obligatoire et décision d'entrée (instant `D`)

L'entrée exige la séquence suivante, dans cet ordre, chaque étape sur une bougie ultérieure à la
précédente :

1. **configuration identifiée** à `I` (§4.2) ;
2. **contact** sur une H1 `c` qui commence à `I` ou après (§4.3) ;
3. **pivot de reprise** : un sommet H1 (ordre 2) formé sur une bougie `r` postérieure à `c` ;
4. **confirmation** de ce sommet, à la fin de la bougie `r + 2` : son niveau devient le **seuil** ;
5. **clôture de cassure** : la première H1 `h` qui commence à la confirmation ou après et dont
   `bid_close[h]` est strictement supérieur au seuil.

**Bornes temporelles** (mêmes conventions en H1 et en H4) :
- `début(c) ≥ I` ;
- `début(r) ≥ fin(c)` : la bougie de contact ne peut pas être le pivot, la bougie qui la suit
  immédiatement peut l'être ;
- `confirmation(seuil) = fin(r + p) ≤ début(h)` : le seuil est connu au début de la bougie de
  cassure ;
- après une cassure refusée à l'instant `D_refus` : `début(r') ≥ D_refus` pour tout nouveau pivot
  de reprise `r'`, qui doit ensuite être confirmé avant sa propre bougie de cassure.

Précisions :
- s'il existe plusieurs pivots de reprise confirmés, le seuil est le **dernier** confirmé avant le
  début de `h` ;
- **un seuil ne produit qu'une cassure** : la première clôture au-dessus **consomme** le seuil,
  même si l'entrée est refusée (cible trop proche, taille, marché fermé). Une clôture qui reste
  ensuite au-dessus d'un seuil déjà franchi n'est pas une nouvelle cassure. Une nouvelle tentative
  exige un nouveau pivot de reprise **formé puis confirmé après ce refus** ;
- un pivot formé avant le contact, ou sur la bougie de contact, ne sert jamais de seuil.

À `D` = fin de `h`, l'entrée est décidée si, en plus :
- la configuration est vivante (ni abandonnée, ni expirée, ni remplacée) ;
- la tendance D1 est toujours haussière ;
- le rapport de risque est suffisant (§6.1) ;
- aucune position S2 n'est ouverte, le marché est ouvert à `D` et la taille est admise (§6.2).

Exécution : ordre au marché au premier tick strictement postérieur à `D` (achat à l'ask).

### 4.5 Vente (règle symétrique)

| Élément | Achat | Vente |
|---|---|---|
| Tendance D1 | 2 sommets et 2 creux croissants, clôture au-dessus du dernier creux | 2 sommets et 2 creux décroissants, clôture sous le dernier sommet |
| `E` | dernier sommet H4 confirmé | dernier **creux** H4 confirmé |
| `K` | sommet H4 antérieur, strictement **inférieur** à `E` | creux H4 antérieur, strictement **supérieur** à `E` |
| Zone | `K ± z × A` | `K ± z × A` |
| Contact | intervalle bid de la H1 recoupant la zone | idem |
| Extrême du repli | `PL` = plus bas `bid_low` depuis `E` | `PH` = plus haut **`ask_high`** depuis `E` (côté de sortie d'une vente) |
| Invalidation | clôture H4 bid **sous la borne basse** | clôture H4 bid **au-dessus de la borne haute** |
| Reprise sans entrée | une H1 avec `bid_high > E` | une H1 avec `bid_low < E` |
| Remplacement | nouveau sommet H4 **supérieur** à `E` | nouveau creux H4 **inférieur** à `E` |
| Pivot de reprise | **sommet** H1 formé après le contact | **creux** H1 formé après le contact |
| Cassure | première `bid_close` **au-dessus** du seuil | première `bid_close` **sous** le seuil |
| Stop | `PL − b × A` (niveau bid) | `PH + b × A` (niveau ask) |
| Cible | `E`, atteinte quand le **bid** ≥ `E` | `E`, atteinte quand l'**ask** ≤ `E` |
| Exécution d'entrée | ask du premier tick après `D` | bid du premier tick après `D` |

Asymétrie assumée (approuvée, ADR-015) : la structure et `E` sont calculés sur la série bid ; le
stop d'une vente utilise l'extrême `ask_high` du repli et sa cible est atteinte quand ask ≤ `E`.
Une vente doit donc dépasser `E` du spread observé pour atteindre sa cible ; **aucune correction
forfaitaire du spread** n'est ajoutée. C'est la convention de côté de sortie des stops de S1.

### 4.6 Comparaison enregistrée : déclenchement H4

Même configuration (`E`, `K`, `A`, zone, invalidation, délai, données), même stop et mêmes sorties.
La comparaison change **l'unité du contact, du pivot de reprise et de la cassure** : toute la
séquence du §4.4 est appliquée aux bougies **H4**, avec les mêmes bornes temporelles (contact sur une
H4 commençant à `I` ou après ; pivot de reprise H4 d'ordre 3 avec `début(r) ≥ fin(c)` ;
confirmation à `fin(r + 3) ≤ début(h)` ; première clôture H4 au-delà du seuil). Elle compare donc
**deux séquences complètes**, pas seulement deux heures d'entrée. Un sommet H4 inférieur ou égal à
`E` peut servir de seuil dans cette comparaison sans changer la configuration (§4.3). Les décisions
de cette comparaison ont lieu à la disponibilité de chaque H4.

## 5. Exemple horodaté (achat, données inventées)

> Prix **fictifs**, choisis pour illustrer les règles ; aucune donnée n'a été lue. Hiver (heure
> normale de New York) : 17:00 New York = 22:00 UTC ; bornes H4 à 22:00, 02:00, 06:00, 10:00,
> 14:00 et 18:00 UTC. `A` = 20 pips.

| Instant (UTC) | Événement | Règle |
|---|---|---|
| lun. 14 janv. 10:00-14:00 | H4 de sommet `bid_high` 1,1450 | futur `K` |
| mar. 15 janv. 02:00 | Sommet 1,1450 confirmé (fin de la 3e H4 suivante) | §3 |
| mar. 15 janv. 14:00-18:00 | H4 de sommet `bid_high` 1,1530 | futur `E` |
| mer. 16 janv. 06:00 | `E` confirmé par les H4 18-22, 22-02 et 02-06, toutes plus basses. **`I` = 06:00.** Tendance D1 haussière (D1 close le 15 janv. à 22:00). `A` = 0,0020. Zone `[1,1440 ; 1,1460]`, invalidation sous 1,1440. Compteur `T_max` : il part de la H4 18-22 du 15 janv. ; expiration à la fin de la 30e H4, mar. 22 janv. 18:00 | §4.2, §4.3 |
| mer. 16 janv. 04:00-05:00 | Une H1 de 1,1459 à 1,1474 recoupe la zone mais **ne compte pas** comme contact (avant `I`) ; `PL` = 1,1459 | §4.3 |
| mer. 16 janv. 13:00-14:00 | H1 de 1,1455 à 1,1471 : recoupe la zone, **contact** (bougie `c`, commence après `I`) ; `PL` = 1,1455 | §4.3 |
| mer. 16 janv. 15:00-16:00 | H1 de sommet `bid_high` 1,1478, formé après la bougie de contact : **pivot de reprise** `r` | §4.4 |
| mer. 16 janv. 18:00 | Sommet H1 1,1478 confirmé (fin de la H1 17-18). La H1 17-18 a un `bid_low` de 1,1451 : `PL` = 1,1451. La H4 14-18 clôture à 1,1463 ≥ 1,1440 : pas d'invalidation | §3, §4.3 |
| mer. 16 janv. 18:00-19:00 | H1 clôture à 1,1476 : sous le seuil, pas de cassure | §4.4 |
| mer. 16 janv. 19:00-20:00 | H1 `h` clôture à 1,1481 > 1,1478 : **première** clôture au-dessus du seuil depuis sa confirmation (18:00), connu au début de `h` (19:00). Toutes les H1 et H4 depuis la fin de `E` sont utilisables | §4.3, §4.4 |
| mer. 16 janv. 20:00:00 | **Décision `D`.** Dernier tick avant `D` : bid 1,1481, ask 1,1482. Stop = `PL − 0,25 × A` = 1,1451 − 0,0005 = **1,1446**. Cible `E` = **1,1530**. Rapport net 1,19 ≥ 1 (§6.1). Taille 0,1 contrat | §4.4, §6 |
| mer. 16 janv. 20:00:00,180 | Premier tick strictement après `D` : bid 1,1483, ask 1,1484. **Exécution à 1,1484** (ask observé), pas à 1,1482 (estimation) | §6.3 |
| à partir de l'entrée | Compteur `H_max` : il part de la première H4 qui commence après l'exécution (20:00-22:00 n'en est pas une ; la première est 22:00-02:00). Sortie temporelle à la disponibilité de la 60e | §6.4 |

## 6. Exécution et risque

### 6.1 Rapport « gain potentiel net / perte estimée au stop ≥ 1 » (`R_min = 1`)

Calculé à `D`, par contrat (10 000 EUR ; 1 pip = 1 USD), avec le **dernier tick strictement
antérieur à `D`** et les coûts de recherche de la référence S1 (`RESEARCH_COSTS`, hypothèses non
confirmées chez IG) :
- **perte estimée au stop** = (ask − stop + glissement) × 10 000 + prime de stop garanti +
  financement d'une nuit, convertie en EUR au taux 1/bid, majorée de 0,5 % de frais de conversion
  (formule du contrôleur de risque, `risk.py`) ;
- **gain potentiel net** = (cible − ask − glissement) × 10 000 − financement d'une nuit, converti en
  EUR au taux 1/ask (convention du moteur pour un gain), diminué de 0,5 % de frais de conversion ;
  pas de prime (le stop n'est pas déclenché).

Exemple du §5 (bid 1,1481, ask 1,1482, stop 1,1446, glissement 0,5 pip, prime 1,2 USD, financement
1 USD par nuit, une nuit provisionnée) :

| | Calcul (USD par contrat) | EUR par contrat |
|---|---|---|
| Perte estimée au stop | (1,1482 − 1,1446 + 0,00005) × 10 000 + 1,2 + 1,0 = 38,70 | 38,70 / 1,1481 × 1,005 = **33,88** |
| Gain potentiel net, cible 1,1530 | (1,1530 − 1,1482 − 0,00005) × 10 000 − 1,0 = 46,50 | 46,50 / 1,1482 × 0,995 = **40,30** |
| Rapport | | 40,30 / 33,88 = **1,19 ≥ 1 : entrée** |
| Contre-exemple, cible 1,1520 | 36,50 | 31,63 → rapport **0,93 < 1 : abstention** |

Le contre-exemple montre que le seul écart de prix (38 pips de gain contre 36 pips de perte) ne
suffit pas : les coûts font passer le rapport sous 1.

### 6.2 Taille

Contrôleur de risque inchangé : budget = 0,25 % des fonds propres estimés à `D` ; taille = budget /
perte estimée par contrat, arrondie vers le bas au pas de 0,1 ; refus si 0,1 contrat dépasse le
budget. Exemple : 5,00 / 33,88 = 0,147 → **0,1 contrat**, perte estimée 3,39 €.

### 6.3 Prix estimé et premier prix observable

Le prix estimé (ask avant `D`) sert au rapport et à la taille ; il n'est **jamais** une exécution.
L'entrée se fait au premier tick strictement postérieur à `D`. La taille n'est pas recalculée ; la
perte estimée au stop après exécution et un éventuel dépassement du budget sont enregistrés, sans
supprimer l'entrée (ASSUMP-024, ADR-009). Le rapport du §6.1 n'est pas recalculé au prix exécuté.

Premier prix déjà au-delà d'une borne (achat) :
- **bid ≤ stop** au premier tick : convention de la référence, « exécutée puis liquidée » sur ce
  même tick, comptée (`STOP_DÉPASSÉ_À_L'EXÉCUTION`). Un passage de rejet à l'exécution n'est fait
  que si de tels cas existent (comme S1) ;
- **bid ≥ cible** au premier tick : exécutée à l'ask, puis **sortie sur ce même tick au bid**,
  comptée (`CIBLE_ATTEINTE_À_L'EXÉCUTION`). L'entrée n'est pas annulée au vu de ce prix futur (même
  principe qu'ADR-009). **« Cible atteinte » ne signifie pas « transaction gagnante »** : l'achat se
  fait à l'ask et la revente au bid.

Exemple (données inventées, cible `E` = 1,1530, taille 0,1 contrat) : premier tick après `D`, bid
1,1531, ask 1,1532. Achat à 1,1532, revente à 1,1531 sur le même tick. Résultat de prix : −1 pip, soit
−1,00 USD par contrat ; glissement 0,5 pip, soit −0,50 USD ; pas de nuit ni de prime. Total
−1,50 USD par contrat, −0,15 USD pour 0,1 contrat, soit **−0,13 €** après conversion (taux 1/bid,
frais de 0,5 %). La transaction sort « à la cible » et perd.

### 6.4 Sorties

- **Stop** : stop garanti simulé à son niveau, prime comptée à part (S1 §6, §10.5). Jamais élargi
  ni rapproché du seul fait de l'entrée H1.
- **Cible — convention de simulation** : sortie à la **première cotation exécutable observée** qui
  atteint la cible, au prix de cette cotation : le bid pour clôturer un achat (bid ≥ `E`), l'ask
  pour clôturer une vente (ask ≤ `E`). Un écart favorable observé est conservé. Ce n'est pas le
  comportement confirmé d'un ordre limite IG (ASSUMP-008).
- **Sortie temporelle (`H_max = 60` H4)** : le compteur part de la **première H4 qui commence après
  le tick d'exécution** ; à la disponibilité de la 60e, si la position est encore ouverte, sortie au
  marché au premier tick suivant. Environ 10 jours de cotation.
- Pour un achat, stop et cible sont de part et d'autre du prix : un même tick ne peut pas franchir
  les deux. La priorité « stop, puis cible, puis sortie temporelle » ne départage que la sortie
  temporelle et une borne franchie au même instant ; elle ne sert pas à reconstituer un trou (§7).

## 7. Trous de cotation : franchissements non observables

Pendant une **interruption inexpliquée** (S1 §10.5), le parcours du prix est inconnu. Avec deux
bornes, aucune règle de priorité ne reconstitue l'ordre réel.

| Cotation après le trou (achat) | Ce qui est certain | Ce qui reste inconnu |
|---|---|---|
| entre stop et cible, comme avant le trou | rien n'est observé | stop, cible, ou les deux, ont pu être touchés pendant le trou |
| au-delà de la cible | la cible a été atteinte | le stop a pu être touché avant |
| au-delà du stop | le stop a été franchi | la cible a pu être atteinte avant |

Chaque transaction concernée est marquée **INDÉTERMINÉE** et listée avec le trou, les cotations
qui l'encadrent, leur distance au stop et à la cible, et le résultat de chaque issue possible.

Trajectoires publiées, chacune **rejouée en entier** (une sortie pendant le trou libère la position
plus tôt et peut changer les entrées suivantes, les fonds propres et les tailles) :

| Scénario | Règle pour une transaction indéterminée | Prix de sortie |
|---|---|---|
| **A — observé seulement** (`NONE_TRIGGERED`) | seule la première cotation après le trou compte ; au-delà d'une borne, cette borne s'exécute ; sinon la position continue | stop : niveau garanti ; cible : cotation observée |
| **B — stop d'abord** (`ALL_TRIGGERED`) | tout franchissement du stop possible pendant le trou a eu lieu, avant la cible | niveau du stop garanti, à la fin du trou |
| **C — cible d'abord** | toute atteinte de la cible possible pendant le trou a eu lieu, avant le stop | **niveau `E`**, comptabilisé au premier tick qui clôt le trou, sans amélioration de prix invisible |

Scénario C (ADR-015) : la sortie est comptabilisée au niveau `E` au **premier tick qui clôt le
trou**. Le journal enregistre séparément l'intervalle du trou et l'instant de comptabilisation :
l'heure réelle du franchissement reste inconnue. Le capital n'est **pas libéré rétroactivement**
pour une décision antérieure à cette comptabilisation (une décision prise pendant le trou voit
encore la position ouverte). Même règle pour B.

C est publié seulement si au moins une transaction indéterminée admet une atteinte possible de la
cible et si C diffère alors de A. B est publié seulement si au moins une transaction admet un
franchissement possible du stop. **Aucun de ces scénarios n'est une borne garantie** du résultat
réel (dépendance au chemin).

Le contact (§4.3) et les pivots sont mesurés sur les extrêmes des bougies : pendant un trou, ils ne
prouvent pas qu'une cotation a eu lieu ; les règles de données (§4.3) abandonnent d'ailleurs une
configuration dont le repli contient une bougie inutilisable.

## 8. Abstentions (première cause journalisée)

Ordre d'évaluation à chaque décision H1 sans entrée :
1. **données** : H1 de cassure non `OK` ; bougie d'un pivot utilisé non utilisable ; `A`
   indisponible ; D1 de contexte non utilisable ;
2. **position déjà ouverte** (non évaluée) ;
3. **pas de tendance D1** ;
4. **pas de configuration** : pas de `E` confirmé ou pas de `K` ;
5. **configuration abandonnée**, avec son motif : données du repli incomplètes
   (`DONNÉES_REPLI_INCOMPLÈTES`), repli trop profond, reprise sans entrée, expirée, déjà utilisée ;
6. **pas de contact** depuis `I` ;
7. **pas de cassure** : pas de pivot de reprise confirmé après le contact, clôture sous le seuil, ou
   seuil déjà consommé ;
8. **cible trop proche** (`R_min`) ;
9. **marché fermé** à `D` (signal expiré, y compris la dernière H1 avant la fermeture hebdomadaire) ;
10. **taille** : 0,1 contrat au-dessus du budget ; distance de stop sous le minimum du courtier.

Le journal garde une ligne par décision H1 : ce qui était connu (pivots, `E`, `K`, `A`, `PL`,
contact, seuil, tendance, cotation, compte, position) et l'action, sans résultat ultérieur (comme
S1).

## 9. Protocole de test et lecture des résultats

**Périmètre de l'expérience.** Aucun filtre horaire nouveau, aucune variante de sortie. Cotations
bid / ask observées, règles existantes sur les fermetures et coûts de recherche de la référence S1
(`RESEARCH_COSTS`).

**Étape 0 — fiche figée** : ASSUMP-025 approuvée pour la recherche hors ligne (ADR-015,
2026-11-03).

**Étape 1 — implémentation hors ligne et tests synthétiques uniquement** (aucune donnée réelle) :
pivots connus seulement à `i + p` et égalités sans pivot ; ordre H1 / H4 / D1 aux clôtures communes ;
contact par recoupement de la zone, contact avant `I` ignoré, bougie entièrement hors de la zone
refusée ; séquence contact → pivot de reprise → confirmation → cassure, pivot antérieur au contact
refusé, une cassure par seuil ; abandon pour données du repli incomplètes ; invalidation sous la
borne basse ; remplacement par un sommet supérieur ; compteurs `T_max` et `H_max` ; règles de vente
symétriques ; exemples des §5 et §6.3 reproduits tels quels ; premier prix au-delà du stop ou de la
cible ; trous de cotation et scénarios A, B et C (§7) ; une entrée par configuration ; conventions du
moteur S1 conservées.

**Étape 2 — rejeu historique de non-régression de S1**, distinct de l'étape 1 : la référence S1
rejouée sur avril-juin 2019 doit donner des transactions identiques avec le moteur modifié.

**Étape 3 — disponibilité des données** (aucun résultat de stratégie) : part des décisions H1
2015-2021 bloquées par les règles de données, et des configurations abandonnées pour données du
repli incomplètes, par cause (comme S1 §10.4).

**Étape 4 — passages pré-enregistrés** sur 2015-2021, trajectoire continue, 2 000 €, coûts, risque
(0,25 %) et taille (minimum et pas de 0,1) de la référence S1 :
- **référence S2 : déclenchement H1** ; scénario A, puis B et C selon les conditions du §7 ; rejet à
  l'exécution seulement si un stop est déjà dépassé au premier tick ;
- **comparaison secondaire enregistrée à l'avance : déclenchement H4** (§4.6). Elle mesure l'apport
  de l'unité H1 (cahier §6.5) ; elle ne remplace pas la référence, même si son résultat est
  meilleur ;
- protocole et diff de lancement copiés avec les sorties ; journaux et rapports locaux, hors Git ;
  bilan agrégé dans `docs/experiments/`.

**Rapporté pour chaque passage** : nombre de transactions ; net après coûts, avec brut et coûts ;
résultats annuels ; drawdown maximal au tick en euros et **maximum relatif au tick** ; dépassements
du budget ; net sans la meilleure transaction. Propre à S2 : configurations créées, abandonnées par
motif, déclenchées, refusées (cible, taille, stop) ; sorties par motif (cible, stop, temps) ; entrées
au-delà d'une borne au premier tick ; transactions indéterminées et issues possibles ; résultats en
multiples du risque. Comparaison à la référence S1 : chevauchement des positions dans le temps et
résultats annuels côte à côte.

**Lecture des résultats.**
1. **Net après coûts** : un net **strictement positif dans chaque scénario publié** (A, et B ou C
   s'ils existent) est un résultat favorable sur la période de développement, sans plus. Si le signe
   change entre A, B et C, la conclusion est que **le résultat dépend du traitement des trous**.
   Tous les résultats sont publiés.
2. **Net sans la meilleure transaction** : indicateur de **concentration des gains**, rapporté et
   commenté, **pas un motif automatique de rejet**. Le seuil de 6 % ci-dessous est un **seuil de
   revue**, pas un critère d'exclusion.
3. **Seuil de revue de 6 % du drawdown relatif au tick.**
   - *Origine* : seuil de « baisse depuis le sommet entraînant une revue » du cahier des charges (§8).
   - *Définition exacte* : fonds propres au tick `F(t)` = solde réalisé + valeur de liquidation de
     la position (ASSUMP-024) ; sommet `S(t)` = maximum de `F` depuis le début de la trajectoire
     (2 000 € au départ) jusqu'à `t` inclus ; drawdown relatif = **véritable maximum sur `t` de
     `(S(t) − F(t)) / S(t)`**, sur toute la trajectoire continue 2015-2021, dans chaque scénario
     publié. Les creux pendant les trous de cotation restent inconnus.
   - *En backtest de recherche* : le **premier franchissement** éventuel (instant, sommet, fonds
     propres, transaction ouverte) est rapporté et **la trajectoire continue** sans interruption.
   - *En exploitation* (cahier §8, distinct de ce backtest) : le franchissement bloquerait les
     nouvelles entrées jusqu'à une revue et une reprise explicites. Ce blocage n'est pas simulé ;
     les seuils de perte journalière et hebdomadaire non plus.
   - *Implémentation requise* : le moteur suit aujourd'hui l'épisode de plus forte baisse en euros ;
     le maximum relatif devra être suivi séparément.
   - *Comparaison avec S1* : les 2,25 % de la référence S1 sont son pire recul **en euros** rapporté
     au sommet de cet épisode, pas son maximum relatif ; ils ne sont **pas directement
     comparables** au chiffre de S2.

Un résultat défavorable est rapporté tel quel ; aucun paramètre n'est ajusté.

**Interdits.** Aucune donnée 2022-2025 ; aucun réglage après lecture des résultats ; aucun
entraînement ; aucun ordre ; le sélecteur IA n'est pas concerné.

## 10. Paramètres approuvés pour la recherche hors ligne (ASSUMP-025)

| Paramètre | Valeur | Rôle |
|---|---|---|
| `p_D1` | 2 | ordre des pivots D1 (tendance) |
| `p_H4` | 3 | ordre des pivots H4 (`E`, `K`) |
| `p_H1` | 2 | ordre des pivots H1 (seuil de déclenchement) |
| ATR (`A`) | Wilder 14 H4, fixé à `I` | zone, invalidation, marge du stop |
| `z` | 0,5 × `A` | demi-largeur de la zone autour de `K` |
| `T_max` | 30 H4 après la bougie `E` | durée maximale de la configuration |
| `b` | 0,25 × `A` | marge du stop sous le creux du repli |
| `R_min` | 1,0 | gain potentiel net / perte estimée au stop |
| `H_max` | 60 H4 après l'exécution | sortie temporelle |

## 11. Décisions de l'opérateur (2026-11-03)

Revue du commit `647d709` : valeurs numériques proposées, contact sur H1, pivots stricts sans
égalité, ATR figé à l'identification, déclenchement H4 comme comparaison secondaire, sortie à la
cible à la première cotation exécutable, scénarios A, B et C, seuil de revue de 6 %. Hors de cette
expérience : filtre horaire, sortie sur perte de la tendance D1, filtre de moyenne mobile,
continuation suiveuse.

Revue du commit `a10a779` (ADR-015) :
1. **Seuil consommé** : la première cassure consomme le seuil, même si l'entrée est refusée ; une
   nouvelle tentative exige un nouveau pivot formé puis confirmé après ce refus (§4.4).
2. **Vente** : structure et `E` sur le bid ; stop sur l'extrême `ask_high` du repli ; cible atteinte
   quand ask ≤ `E` ; aucune correction forfaitaire du spread (§4.5).
3. **Scénario C** : sortie au niveau `E` comptabilisée au premier tick qui clôt le trou ; intervalle
   du trou et instant de comptabilisation journalisés séparément ; aucun capital libéré
   rétroactivement (§7).
4. **Lecture** : net strictement positif dans chaque scénario publié = résultat favorable sur la
   période de développement ; signe différent entre A, B et C = résultat dépendant du traitement
   des trous ; tous les résultats publiés ; net sans la meilleure transaction = indicateur de
   concentration ; 6 % = seuil de revue (§9).
5. **Bornes temporelles** : `début(pivot) ≥ fin(contact)` et `confirmation(seuil) ≤
   début(bougie de cassure)`, en H1 et en H4 ; la comparaison H4 compare deux séquences complètes
   (§4.4, §4.6).
