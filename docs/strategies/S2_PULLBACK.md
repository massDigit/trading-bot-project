# Fiche S2 — Reprise de tendance après repli (swing)

> Identifiant code : `SWING_02`. Statut : **candidate en cours de spécification** (cahier des
> charges §6.2, §6.6). Principe approuvé par l'opérateur le 2026-11-03 ; règles et valeurs
> numériques **proposées** (ASSUMP-025, statut `PROPOSED` jusqu'à la revue de la fiche complète).
> Documentation seulement : **aucun code, aucun backtest, aucun entraînement, aucune donnée
> 2022-2025**. Les valeurs sont choisies a priori et ne seront pas optimisées.

**Libellés.** Dans cette fiche, **H1, H4 et D1 désignent toujours des unités de temps** (bougies
d'une heure, de quatre heures, d'un jour). Les deux scénarios de stop non observable du moteur
(appelés H0 et H1 dans les rapports S1) sont nommés ici **scénario A** et **scénario B** (§7).

**Points demandés par l'opérateur le 2026-11-03** : chronologie du signal → §4 et §5 ; définition et
durée de la configuration → §3 et §4 ; exécution et risque → §6 et §7 ; lecture des résultats → §9.

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

## 4. Configuration et entrée (achat ; la vente est symétrique)

### 4.1 Tendance D1

À l'instant considéré, sur les pivots D1 connus : les deux derniers sommets sont croissants, les
deux derniers creux sont croissants, et la clôture de la dernière D1 disponible est au-dessus du
dernier creux confirmé. Vérifiée à l'identification `I` **et** à la décision d'entrée `D`.

### 4.2 Identification de la configuration (instant `I`)

- **`E`** : sommet H4 qui vient d'être confirmé. `I` = sa date de confirmation (disponibilité de
  la H4 `E + 3`).
- **`K`** : le sommet H4 confirmé le plus récent, antérieur à `E` et strictement inférieur à `E`
  (ancienne résistance que la jambe vers `E` a franchie). Sans `K` : pas de configuration.
- **Zone admissible** : `[K − z × A ; K + z × A]`, avec `z = 0,5`. Sa **borne basse** est le
  niveau d'invalidation.
- La configuration n'est créée que si la tendance D1 est haussière à `I`, si `A` est disponible et
  si aucune H4 clôturée entre la fin de `E` et `I` n'a de `bid_close` sous la borne basse.

### 4.3 Vie de la configuration

- **Contact** : une bougie H1 qui **commence à `I` ou après** et dont `bid_low ≤ K + z × A`. Un
  contact antérieur à `I` ne compte pas.
- **Creux du repli `PL`** : plus bas `bid_low` des H1 disponibles depuis la fin de la bougie `E`
  (y compris avant `I`).
- **Invalidation (repli trop profond)** : la première H4 dont la **clôture bid est strictement
  sous la borne basse `K − z × A`** (et non sous `K`) abandonne la configuration.
- **Reprise sans entrée** : si une H1 atteint `bid_high > E` avant l'entrée, la configuration est
  abandonnée.
- **Nouveau sommet H4** confirmé avant l'entrée : s'il est **supérieur à `E`**, il remplace la
  configuration (nouvel `E`, nouveau `K`, nouvel `I`, nouvel `A`, compteurs remis à zéro) ; s'il est
  inférieur ou égal à `E`, c'est un sommet de la correction : il est ignoré par la configuration.
- **Durée maximale (`T_max = 30` H4)** : le compteur part de la **première H4 qui suit la bougie
  `E`**. La configuration expire à la disponibilité de la 30e H4 : une entrée décidée à cet instant
  est encore permise, aucune après. Les trois H4 de confirmation font partie des 30 (il en reste
  27 après `I`). Le week-end ne compte pas : seules les H4 cotées sont comptées.
- Une configuration ne produit **qu'une entrée**.

### 4.4 Déclenchement et décision d'entrée (instant `D`)

À la disponibilité de la bougie H1 `h` (instant `D` = fin de `h`), une entrée est décidée si :
1. la configuration est vivante (ni abandonnée, ni expirée, ni remplacée) ;
2. un contact a eu lieu, dans une H1 qui commence à `I` ou après et qui n'est pas postérieure à
   `h` (la bougie `h` elle-même peut être la bougie de contact) ;
3. **seuil** : le dernier sommet H1 confirmé dont la bougie commence après la fin de `E`, et dont
   la date de confirmation est **antérieure ou égale au début de `h`**. Le seuil est donc connu
   avant la bougie qui le franchit ;
4. `bid_close[h]` est strictement supérieur au seuil ;
5. la tendance D1 est toujours haussière à `D` ;
6. le rapport de risque est suffisant (§6.1) ;
7. aucune position S2 ouverte, marché ouvert à `D`, taille admise (§6.2).

Exécution : ordre au marché au premier tick strictement postérieur à `D` (achat à l'ask).

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
| mer. 16 janv. 04:00-05:00 | Une H1 descend à 1,1459 : **ne compte pas** comme contact (avant `I`) ; `PL` = 1,1459 | §4.3 |
| mer. 16 janv. 13:00-14:00 | H1 `bid_low` 1,1455 : **contact** (≥ `I`) ; `PL` = 1,1455 | §4.3 |
| mer. 16 janv. 15:00-16:00 | H1 de sommet `bid_high` 1,1478 | futur seuil |
| mer. 16 janv. 18:00 | Sommet H1 1,1478 confirmé (fin de la H1 17-18). La H1 17-18 a un `bid_low` de 1,1451 : `PL` = 1,1451. La H4 14-18 clôture à 1,1463 ≥ 1,1440 : pas d'invalidation | §3, §4.3 |
| mer. 16 janv. 18:00-19:00 | H1 clôture à 1,1476 : sous le seuil, pas d'entrée | §4.4 |
| mer. 16 janv. 19:00-20:00 | H1 `h` clôture à 1,1481 > 1,1478. Seuil confirmé à 18:00 ≤ début de `h` (19:00) | §4.4 |
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
- **bid ≥ cible** au premier tick : exécutée puis **sortie à la cible sur ce même tick**, au bid
  observé, comptée (`CIBLE_ATTEINTE_À_L'EXÉCUTION`). L'entrée n'est pas annulée au vu de ce prix
  futur (même principe qu'ADR-009). Le nombre de cas est rapporté.

### 6.4 Sorties

- **Stop** : stop garanti simulé à son niveau, prime comptée à part (S1 §6, §10.5). Jamais élargi
  ni rapproché du seul fait de l'entrée H1.
- **Cible** : premier tick où le bid atteint `E` ou plus, exécuté à ce bid (un écart favorable est
  conservé ; le comportement d'un ordre limite IG n'est pas confirmé, ASSUMP-008).
- **Sortie temporelle (`H_max = 60` H4)** : le compteur part de la **première H4 qui commence après
  le tick d'exécution** ; à la disponibilité de la 60e, si la position est encore ouverte, sortie au
  marché au premier tick suivant. Environ 10 jours de cotation.
- Pour un achat, stop et cible sont de part et d'autre du prix : un même tick ne peut pas franchir
  les deux. La priorité « stop, puis cible, puis sortie temporelle » ne départage que la sortie
  temporelle et un tick qui franchit une borne au même instant.

## 7. Trous de cotation : franchissements non observables

Pendant une **interruption inexpliquée** (S1 §10.5), le parcours du prix est inconnu. Avec deux
bornes, plusieurs cas sont possibles ; aucune règle de priorité ne reconstitue l'ordre réel.

| Cotation après le trou (achat) | Ce qui est certain | Ce qui reste inconnu |
|---|---|---|
| entre stop et cible, comme avant le trou | rien n'est observé | stop, cible, ou les deux, ont pu être touchés pendant le trou |
| au-delà de la cible | la cible a été atteinte | le stop a pu être touché avant |
| au-delà du stop | le stop a été franchi | la cible a pu être atteinte avant |

Chaque transaction concernée est marquée **INDÉTERMINÉE** et listée avec le trou, les cotations
qui l'encadrent, leur distance au stop et à la cible, et le résultat de chaque issue possible
(stop, cible, poursuite). Deux trajectoires complètes sont publiées, comme pour S1 :
- **scénario A** (« aucun franchissement non observé », politique `NONE_TRIGGERED` du moteur) :
  seule la première cotation après le trou compte ; au-delà d'une borne, cette borne est exécutée
  (stop au niveau garanti, cible au bid observé) ; sinon la position continue ;
- **scénario B** (« stop d'abord », politique `ALL_TRIGGERED`) : tout franchissement du stop
  possible pendant le trou est supposé avoir eu lieu, avant la cible ; sortie au stop à la fin du
  trou.

Ni A ni B n'est présenté comme une borne du résultat réel (dépendance au chemin). Une trajectoire
« cible d'abord » n'est pas publiée dans la base (arbitrage ouvert, §11).

## 8. Abstentions (première cause journalisée)

Ordre d'évaluation à chaque décision H1 sans entrée :
1. **données** : H1 de déclenchement non `OK` ; bougie d'un pivot utilisé non utilisable ; `A`
   indisponible ; D1 de contexte non utilisable ;
2. **position déjà ouverte** (non évaluée) ;
3. **pas de tendance D1** ;
4. **pas de configuration** : pas de `E` confirmé ou pas de `K` ;
5. **configuration abandonnée** : repli trop profond, reprise sans entrée, expirée, déjà utilisée ;
6. **pas de contact** depuis `I` ;
7. **pas de déclenchement** : pas de seuil H1 connu, ou clôture sous le seuil ;
8. **cible trop proche** (`R_min`) ;
9. **marché fermé** à `D` (signal expiré, y compris la dernière H1 avant la fermeture hebdomadaire) ;
10. **taille** : 0,1 contrat au-dessus du budget ; distance de stop sous le minimum du courtier.

Le journal garde une ligne par décision H1 : ce qui était connu (pivots, `E`, `K`, `A`, `PL`,
seuil, tendance, cotation, compte, position) et l'action, sans résultat ultérieur (comme S1).

## 9. Protocole de test et lecture des résultats

**Étape 0 — figer la fiche.** L'opérateur relit la fiche complète et approuve ASSUMP-025, ou la
modifie, **avant** toute implémentation.

**Étape 1 — implémentation hors ligne et tests synthétiques**, sans données réelles : pivots connus
seulement à `i + p` et égalités sans pivot ; ordre H1 / H4 / D1 aux clôtures communes ; contact
avant `I` ignoré ; seuil connu avant la bougie qui le franchit ; invalidation sous la borne basse ;
remplacement par un sommet supérieur ; compteurs `T_max` et `H_max` ; exemple du §5 reproduit tel
quel ; premier prix au-delà du stop ou de la cible ; trous de cotation (§7) ; une entrée par
configuration ; conventions du moteur S1 conservées et S1 inchangée (référence rejouée sur
avril-juin 2019, transactions identiques).

**Étape 2 — disponibilité des données** (aucun résultat de stratégie) : part des décisions H1
2015-2021 bloquées par les règles de données, par cause (comme S1 §10.4).

**Étape 3 — passages pré-enregistrés** sur 2015-2021, trajectoire continue, 2 000 €, coûts, risque
(0,25 %) et taille (minimum et pas de 0,1) de la référence S1 :
- **référence S2 : déclenchement H1** ; scénario A, puis scénario B seulement si une transaction
  indéterminée apparaît ; rejet à l'exécution seulement si un stop est déjà dépassé au premier tick ;
- **comparaison enregistrée à l'avance : déclenchement H4** (clôture H4 au-dessus du dernier sommet
  H4 confirmé après `E`, connu avant cette H4), mêmes `E`, `K`, `A`, stop, cible et sorties. Elle
  sert à mesurer l'apport de l'unité H1 (cahier §6.5) ; elle ne remplace pas la référence, même si
  son résultat est meilleur ;
- protocole et diff de lancement copiés avec les sorties ; journaux et rapports locaux, hors Git ;
  bilan agrégé dans `docs/experiments/`.

**Rapporté pour chaque passage** : nombre de transactions ; net après coûts, avec brut et coûts ;
résultats annuels ; drawdown maximal au tick en euros et en pourcentage du sommet ; dépassements
du budget ; **net sans la meilleure transaction**, qui mesure la concentration des gains.
Propre à S2 : configurations créées, abandonnées par motif, déclenchées, refusées (cible, taille,
stop) ; sorties par motif (cible, stop, temps) ; entrées au-delà d'une borne au premier tick ;
transactions indéterminées ; résultats en multiples du risque. Comparaison à la référence S1 :
chevauchement des positions dans le temps et résultats annuels côte à côte.

**Critères de lecture proposés, à approuver avant tout lancement :**
1. net après coûts positif dans chaque scénario publié (A et, s'il existe, B) ;
2. net sans la meilleure transaction encore positif ;
3. **drawdown au tick inférieur à 6 % du sommet**.
   - *Valeur* : 6 %.
   - *Justification* : c'est le seuil de « baisse depuis le sommet entraînant une revue » du cahier
     des charges (§8). Une trajectoire qui le franchit aurait, en fonctionnement, arrêté les
     nouvelles entrées pour revue ; elle ne peut pas être présentée comme admissible sans ce constat.
     La référence S1 est à 2,25 %.
   - *Définition exacte* : fonds propres au tick `F(t)` = solde réalisé + valeur de liquidation de
     la position (ASSUMP-024) ; sommet `S(t)` = maximum de `F` depuis le début de la trajectoire
     (2 000 € au départ) jusqu'à `t` inclus ; drawdown relatif = `max sur t de (S(t) − F(t)) / S(t)`,
     sur toute la trajectoire continue 2015-2021, dans chaque scénario publié, pour le
     déclenchement H1. Les creux pendant les trous de cotation restent inconnus.
   - *Implémentation requise* : le moteur suit aujourd'hui l'épisode de plus forte baisse **en
     euros** ; le maximum **en pourcentage** devra être suivi séparément.

Un résultat qui ne remplit pas ces critères est rapporté tel quel ; aucun paramètre n'est ajusté
pour les remplir. Les seuils de perte journalière et hebdomadaire du cahier (§8) ne sont pas
simulés, comme pour S1.

**Interdits.** Aucune donnée 2022-2025 ; aucun réglage après lecture des résultats ; aucun
entraînement ; aucun ordre ; le sélecteur IA n'est pas concerné.

## 10. Paramètres proposés (ASSUMP-025)

| Paramètre | Proposition | Rôle |
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

## 11. Arbitrages encore ouverts

1. Trajectoire « cible d'abord » pour les transactions indéterminées : publiée en plus de A et B,
   ou seulement listée transaction par transaction (proposition : listée seulement).
2. Contact détecté sur H1 (proposé) plutôt que sur H4 : plus précoce, et cohérent avec le
   déclenchement.
3. Égalités sans pivot (proposé) : prudent, mais un double sommet exact ne crée aucun `E`.
4. Exécution de la cible au bid observé (écart favorable conservé) plutôt qu'au niveau `E`.
5. Critères de lecture du §9, dont le plafond de 6 %.
6. Variantes non enregistrées pour l'instant : sortie sur perte de la tendance D1, filtre de
   moyenne mobile (« si utile », cahier §6.2), continuation suiveuse au lieu de la cible.
7. Décisions aux heures de spread élargi (21 h-24 h UTC) ; fermetures particulières (comme S1).
