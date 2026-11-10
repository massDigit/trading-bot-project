# Campagne exploratoire DAY_02 : H1, H2, H3 seules et combinées (2015-2021, déclenchement M5)

**Statut** : campagne **exploratoire** autorisée par l'opérateur le 2026-11-09, **terminée le
2026-11-10 : recommandation « abandonner » (§7)**. Ce n'est pas une
validation. Les définitions ci-dessous ont été fixées et enregistrées (commit de lancement) **avant
la lecture de tout résultat des variantes**. La référence DAY_02 (fiche figée, ADR-028, protocole
`DAY02_REFERENCE_2015_2021.md`, ADR-035) reste inchangée, reproductible, et son résultat négatif est
conservé. Les années 2015-2021 ont déjà été examinées : aucun résultat de cette campagne n'est une
validation indépendante, et aucune variante n'est présentée comme validée pour le réel. Aucune
donnée 2022-2025, aucun ordre (réel ou démo), aucune fusion ni remplacement de la référence sans
accord de l'opérateur.

## 1. Objet

Chercher un meilleur compromis entre **fréquence et régularité** des occasions, **espérance nette
après coûts** et **risque**. Une hausse du nombre de transactions, ou un résultat seulement moins
négatif, ne suffit pas. L'objectif de fréquence du robot sera fixé par l'opérateur ; la campagne le
mesure sans l'imposer.

Coûts, capital et risque : ceux de l'ADR-035 (`RESEARCH_COSTS`, `ASSUMED` ; 2 000 EUR ; 0,25 % ;
minimum et pas 0,1 ; stop garanti simulé sans minimum courtier).

## 2. Causalité (contrainte impérative)

À chaque instant T, une décision n'utilise que ce qui est disponible à T : ticks déjà reçus, bougies
clôturées (`end_utc ≤ T`, latence nulle), indicateurs calculés sur le passé, positions évaluées aux
prix alors connus. Aucun indicateur centré, aucune normalisation ni aucun seuil calculé sur la
période, aucune sélection de variante à une date d'après ses résultats ultérieurs, aucune
reconnaissance tardive donnant une décision ou une exécution antidatée. Les données postérieures ne
servent qu'à mesurer après coup le résultat d'une décision (bilan), jamais à la prendre.

Vérifications (§5) : tests synthétiques de troncature et d'altération après T (bougies, ticks, H4),
contrôle bloquant « aucun événement antérieur à la reconnaissance », et rejeu tronqué sur les données
réelles.

## 3. Définitions (une par hypothèse, fixées avant les résultats)

Toutes les autres valeurs sont celles de la référence (`Day02Params()`), contrôlées par le passage
(`variant_params`, code `backtest/day02_variants.py`). Les variantes sont nommées `REF`, `H1`, `H2`,
`H3`, `H1H2`, `H1H3`, `H2H3`, `H1H2H3`.

### 3.1 H1 : reconnaissance différée

- **Règle levée** : `p = j` (fiche §5.1 point 6), restriction de construction sans justification
  économique. L'ordre `o < p` reste exigé.
- **Définition** : à la disponibilité `t_j` de chaque M15, la fenêtre de 4 M15 donne `O`, `o`, `E`,
  `p` comme dans la référence ; `p` peut être antérieur à `j`.
  - **Amplitude et clôture forte restent lues sur la clôture de `j`**, la dernière bougie close à
    `t_j` : `bid_close_j − O ≥ 1,5 × A` et `bid_close_j ≥ E − 0,25 × I`. Elles décrivent l'état connu
    à la reconnaissance : le prix tient encore l'impulsion. Dans la référence, `j = p`, c'est la même
    condition.
  - **Bougies de `p + 1` à `j`**, déjà closes : ce sont des bougies de pause (aucune n'atteint `E`,
    `p` étant la dernière qui l'atteint). Chacune doit respecter la profondeur de la variante (bas,
    ou clôture sous H2), avec `E` et `I` de la fenêtre ; sinon, pas de reconnaissance à `t_j`
    (« repli trop profond avant la reconnaissance »), l'examen continue à la M15 suivante.
  - Ces bougies **comptent** dans le drapeau. S'il y en a deux, le drapeau est formé à
    `F = t_j` (fin de la seconde, instant où elle est connue) ; sinon la formation continue avec les
    M15 suivantes, comme dans la référence.
  - Échéance inchangée : `Δ = min(fin(p) + 90 min, 15:00)`, depuis le sommet réel. Une
    reconnaissance tardive dispose donc de moins de temps.
- **Jamais rétroactif** : `F ≥ t_j`, `D > t_j` ; la sortie du drapeau n'est lue que sur les bougies
  de déclenchement qui commencent à `F` ou après ; l'exécution reste au premier tick postérieur à
  `D`. Aucune bougie de déclenchement antérieure à `t_j` ne peut confirmer : elles ne peuvent
  d'ailleurs pas dépasser `E` (plus hauts inférieurs à `E`).
- **Alternative écartée avant tout résultat** : lire amplitude et clôture forte sur la clôture de
  `p`. Analyse structurelle : la fenêtre examinée à `t_p` contient la même origine (une origine
  postérieure à `p` violerait `o < p`) et la même clôture ; une reconnaissance plus tardive
  n'ajouterait donc presque que des impulsions dont la fenêtre à `t_p` était bornée (07:00, reprise,
  données, ATR). **Correction de mon diagnostic précédent** : les 10 425 refus « sommet antérieur »
  de l'étude ne mesurent pas le potentiel de H1 ; la plupart de ces fenêtres avaient déjà été
  examinées à `t_p`.
- **Mécanisme attendu** : reconnaître une impulsion dont la bougie de sommet a clôturé faiblement
  (mèche) mais que la bougie suivante confirme, et réduire le temps mort après 07:00 et après chaque
  reprise. **Infirmée si** les transactions ajoutées ont une espérance nette inférieure à celle de
  la référence, ou si la fréquence n'augmente pas sensiblement.

### 3.2 H2 : invalidation de profondeur sur clôture

- **Définition** : le seuil `E − 0,5 × I` (vente `E + 0,5 × I`), comparé à l'ancien `E` et à l'ancien
  `I` comme dans la référence, invalide sur la **clôture bid** de la bougie, plus sur son extrême.
  - **Formation (M15)** : invalidation si `bid_close < seuil` (vente `>`), prioritaire ; sinon
    extension si `bid_high > E` (vente `bid_low < E`) ; sinon pause. Une bougie qui fait un nouveau
    sommet avec une mèche sous le seuil mais une clôture au-dessus est donc une **extension**.
  - **Bougies de déclenchement après F** : invalidation si la clôture franchit le seuil, prioritaire
    sur la sortie (exclusives de fait : la sortie exige une clôture au-delà de `E + 0,1 × A`).
  - **Pauses antérieures à `t_j`** (avec H1) : même lecture sur la clôture.
- **Stop inchangé** : `FL − 0,25 × A`, `FL` restant le plus bas `bid_low` (vente : plus haut
  `ask_high`) des pauses et des bougies de déclenchement, **mèches comprises**. Le risque n'est pas
  sous-estimé ; les stops sont plus larges, donc les tailles plus petites.
- Série bid conservée pour la vente, comme la référence.
- **Mécanisme attendu** : une mèche réintégrée est un passage de liquidité, pas un renversement.
  **Infirmée si** les drapeaux supplémentaires touchent plus souvent le stop, ou si leur espérance
  nette est inférieure à celle de la référence.

### 3.3 H3 : contexte directionnel H4

- **Définition** : une impulsion trouvée n'ouvre une configuration que si elle va dans le sens de la
  **pente de la moyenne simple des 20 dernières clôtures bid H4** : signe de
  `SMA20(k) − SMA20(k − 1) = (close(k) − close(k − 20)) / 20`, où `k` est la **dernière H4 terminée au
  plus tard au début de la fenêtre d'impulsion** (même borne que `A`). Hausse admise si le signe est
  `+1`, baisse si `−1`. Pente nulle : aucune.
  - Les 21 H4 `k − 20 … k` doivent être contiguës dans le calendrier prévu et utilisables (états
    connus à `t_j`) ; sinon « contexte H4 non calculable », pas de reconnaissance à `t_j`.
  - Le contexte n'est lu qu'une fois une impulsion trouvée, après le cas ambigu ; un refus pour
    contexte est une cause d'examen (« contexte H4 contraire ou neutre ») et l'examen continue.
- **Motivation** : le point commun des praticiens (Raschke, Brooks) est de ne traiter un repli que
  dans le sens d'une tendance établie ; 20 périodes est la moyenne usuelle de ces méthodes. H4 sur
  20 bougies couvre environ 3,3 jours de cotation, une échelle supérieure à la figure (quelques
  heures) et distincte du filtre D1 de S1. Une seule définition, sans seuil ni autre période.
- **Limites** : le choix de H4 et de 20 n'est pas démontré ; la pente sur 20 H4 est un moment
  (variation sur 20 bougies), sensible aux deux extrémités ; les premières séances de l'historique
  n'ont pas de contexte (21 H4 nécessaires) ; H4 du projet, empreinte
  `081989d4f626585a38e2fb8c0d619237a27e603cdf87e352babcc1aa8fc07989`.
- **Mécanisme attendu** : améliorer l'espérance brute en écartant les impulsions à contre-tendance.
  **Infirmée si** le brut des transactions retenues ne dépasse pas celui de la référence, ou si la
  perte de fréquence n'est pas compensée par l'espérance nette.

### 3.4 Combinaisons

`H1H2`, `H1H3`, `H2H3`, `H1H2H3` : les définitions ci-dessus, appliquées ensemble sans autre
changement. Elles sont lancées **même si les variantes isolées ne sont pas meilleures**. Interactions
attendues : H1 et H2 ajoutent des configurations (fréquence), H3 en retire (qualité recherchée) ;
H2 élargit les stops ; avec une position à la fois, une transaction de plus suspend aussi la
recherche.

## 4. Plan d'exécution

Une seule branche de recherche (`research/day02-h1-h3`), configurations explicites (`--variant`),
arbre propre au commit de lancement, provenance enregistrée au lancement et à la fin.

1. **Études de disponibilité** (sans ticks ni positions) des 8 configurations, M5 et M15 comme
   l'outil les produit : `forex-day02-availability --variant <V>`. Contrôles C1 à C10 de l'étude,
   adaptés aux règles modifiées (C4 : `p = j` exigé seulement sans H1 ; `F` et toute fin jamais
   antérieurs à `t_j` ; `F = max(t_j, fin de la 2e pause)` ; C6 : recalcul distinct réécrit pour
   H1, H2, H3, contexte partagé comme l'ATR). **Reproductibilité** : l'étude `REF` doit redonner le
   détail de l'étude `eb48d6c` octet pour octet (SHA-256
   `775e4bba4a6492af4f054a415ff75cb3c125c5aa1fd9f46ee33dfd0efba69ddc`).
2. **Passages de performance M5, scénario A**, des 8 configurations :
   `forex-day02-backtest --variant <V> --trigger M5 --scenario A`, chacun rapproché de l'étude de
   **sa** variante (champ par champ là où l'état de reprise est le même ; l'ancrage d'empreinte reste
   celui de la référence). **Reproductibilité** : `REF` doit redonner les transactions, le solde et
   le détail par séance du passage de référence `day02_ref_2015_2021_m5_a`.
3. **Scénarios conditionnels** de chaque variante, d'après **son** passage A : B et C s'il contient
   au moins une transaction indéterminée ; rejet à l'exécution s'il contient au moins un stop dépassé
   à l'exécution. C publié seulement s'il diffère de A.
4. **Causalité sur données réelles** : pour chaque variante, étude de disponibilité tronquée au
   2018-01-01, comparée à l'étude complète sur toutes les séances antérieures (identité exigée) ; pour
   `H1H2H3`, passage tronqué 2015-01-01 → 2015-04-01 comparé au passage 2015-01-01 → 2015-07-01 sur
   tout ce qui précède le 2015-04-01 (journal, tentatives, transactions closes).
5. **Bilan** (§6), puis recommandation : poursuivre, reformuler ou abandonner.

Un défaut d'implémentation reproductible est corrigé, testé, et les essais affectés relancés, les
sorties invalidées restant tracées au registre. Une modification de règle suggérée par un résultat
n'est **pas** une correction : elle relève d'un lot suivant.

## 5. Mesures et lecture (fixées avant les résultats)

Pour chaque configuration, sur 2015-2021 et par période **2015-2018 / 2019-2021** (découpage
exploratoire, années déjà examinées) :
- **activité** : transactions, par an ; séances actives (part) ; semaines actives (part) ; écart
  médian et maximal entre séances actives ; mois sans transaction ;
- **résultat** : brut, coûts, net ; espérance nette et brute en R avec erreur type ; profit factor ;
  net par année ;
- **risque** : drawdown au tick (EUR) et relatif ; plus longue série de pertes ; distance médiane du
  stop ; net sans la meilleure transaction ;
- **parcours** : configurations, drapeaux, sorties confirmées, entrées, issues.

**Appariement entre trajectoires** : les trajectoires divergent dès qu'une transaction diffère
(une position à la fois). Les transactions sont rapprochées par instant de décision `D` et sens :
« communes », « propres à la variante », « propres à la référence ». C'est une **description**, pas
une mesure causale de l'effet d'une règle : une transaction propre à une variante peut déplacer les
suivantes.

**Lecture enregistrée à l'avance** (exploratoire, aucune n'est une validation) :
- **piste à poursuivre** : net positif sur 2015-2021 **et** dans chacune des deux périodes, espérance
  nette positive, drawdown relatif sous 6 %, activité au moins égale à la référence (semaines
  actives) ou baisse justifiée par l'espérance ;
- **à reformuler** : espérance brute améliorée de plus d'une erreur type dans les deux périodes,
  mais net encore négatif ou fréquence insuffisante ;
- **à abandonner** : ni l'un ni l'autre.

Une variante retenue ne serait éprouvée que par un protocole distinct, gelé avant la lecture de
2022-2023, sur autorisation de l'opérateur.

## 6. Registre des essais

Tous les essais sont conservés, y compris défavorables ou invalidés. Sorties sous
`data/reports/backtests/day02_campaign/` (hors Git). Tous les passages ont été lancés sur `a827964`,
arbre propre, et terminés sans changement de commit ni de fichier suivi (provenance vérifiée en fin
de passage). Aucun essai n'a été invalidé ; aucune correction de bug n'a été nécessaire.

| # | Essai | Configuration | Commit | Résultat | Incident |
|---|---|---|---|---|---|
| — | définitions, code et tests | §3 | a827964 | 574 tests | — |
| 1-8 | études de disponibilité 2015-2021 | REF, H1, H2, H3, H1H2, H1H3, H2H3, H1H2H3 | a827964 | C1-C10 réussis pour les 8 ; REF identique octet pour octet à l'étude de référence | — |
| 9-16 | passages de performance M5, scénario A | les 8 | a827964 | contrôles réussis ; aucun scénario B/C ni rejet requis ; REF identique à `day02_ref_2015_2021_m5_a` (rapport et détail des séances) | — |
| 17-24 | disponibilité tronquée au 2018-01-01 | les 8 | a827964 | chaque séance antérieure à 2018 identique à l'étude complète (778 séances × 8) | — |
| 25-26 | performance H1H2H3 tronquée (→2015-04-01, →2015-07-01) | H1H2H3 | a827964 | les 63 séances avant 2015-04-01 (tentatives, journal, transactions) identiques entre les deux troncatures et le passage complet ; 7 transactions identiques | — |

## 7. Bilan (exploratoire)

### 7.1 Tableau 2015-2021 (M5, scénario A, coûts et risque ADR-035)

Risque par transaction 5 EUR (0,25 % de 2 000 EUR) ; R = résultat / risque à l'exécution ; ± = erreur
type. Drawdown relatif au tick ; « max sans » = plus longue suite de séances sans transaction.

| Variante | Trans. | /an | Sem. actives | Max sans | Mois sans | Brut € | Coûts € | Net € | R net | R brut | PF | DD rel. | Série pertes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| REF | 298 | 42,6 | 58,7 % | 26 | 2 | −17,91 | 52,75 | −70,66 | −0,064 ± 0,044 | −0,020 ± 0,043 | 0,82 | 5,66 % | 10 |
| H1 | 316 | 45,1 | 60,9 % | 25 | 1 | −12,40 | 55,58 | −67,98 | −0,061 ± 0,043 | −0,018 ± 0,042 | 0,84 | 5,24 % | 10 |
| H2 | 358 | 51,1 | 65,6 % | 26 | 2 | −1,96 | 61,02 | −62,98 | −0,055 ± 0,039 | −0,013 ± 0,038 | 0,87 | 5,08 % | 10 |
| H3 | 159 | 22,7 | 36,9 % | 71 | 10 | +10,19 | 30,34 | −20,15 | −0,033 ± 0,065 | +0,013 ± 0,064 | 0,91 | 2,53 % | 7 |
| H1H2 | 384 | 54,9 | 69,1 % | 25 | 1 | −0,75 | 64,64 | −65,40 | −0,052 ± 0,038 | −0,011 ± 0,037 | 0,87 | 4,61 % | 10 |
| H1H3 | 174 | 24,9 | 40,4 % | 63 | 8 | +9,43 | 32,39 | −22,96 | −0,036 ± 0,062 | +0,009 ± 0,060 | 0,91 | 2,92 % | 7 |
| H2H3 | 195 | 27,9 | 42,1 % | 46 | 7 | +32,40 | 34,38 | −1,98 | −0,013 ± 0,056 | +0,030 ± 0,055 | 0,99 | 2,43 % | 7 |
| H1H2H3 | 216 | 30,9 | 45,9 % | 46 | 4 | +23,15 | 37,43 | −14,28 | −0,025 ± 0,054 | +0,017 ± 0,053 | 0,95 | 3,38 % | 6 |

Le coût moyen reste d'environ 0,17-0,19 EUR par transaction (≈ 0,035-0,04 R) pour toutes les
variantes ; aucune ne change la structure de coût. La distance médiane du stop reste de 18-19 pips.

### 7.2 Par période (exploratoire, années déjà examinées)

| Variante | 2015-2018 : n | net € | R brut | 2019-2021 : n | net € | R brut |
|---|---:|---:|---:|---:|---:|---:|
| REF | 170 | −61,13 | −0,066 ± 0,059 | 128 | −9,53 | +0,041 ± 0,062 |
| H1 | 182 | −50,14 | −0,051 ± 0,058 | 134 | −17,84 | +0,028 ± 0,060 |
| H2 | 197 | −44,98 | −0,043 ± 0,054 | 161 | −18,00 | +0,024 ± 0,054 |
| H3 | 89 | −0,08 | +0,021 ± 0,089 | 70 | −20,07 | +0,002 ± 0,092 |
| H1H2 | 215 | −33,34 | −0,022 ± 0,053 | 169 | −32,06 | +0,002 ± 0,051 |
| H1H3 | 95 | +3,87 | +0,029 ± 0,087 | 79 | −26,83 | −0,015 ± 0,083 |
| H2H3 | 106 | +14,19 | +0,049 ± 0,077 | 89 | −16,17 | +0,008 ± 0,078 |
| H1H2H3 | 118 | +20,08 | +0,059 ± 0,075 | 98 | −34,36 | −0,034 ± 0,073 |

Toutes les variantes améliorent 2015-2018 et **toutes dégradent 2019-2021** par rapport à la
référence, en net comme en R brut. L'écart se creuse avec le nombre de règles combinées :
H1H2H3 gagne +0,125 R brut sur 2015-2018 et en perd 0,074 sur 2019-2021.

### 7.3 Lecture enregistrée (§5)

- **Piste à poursuivre** : aucune variante (net négatif sur 2015-2021 pour les huit).
- **À reformuler** : aucune. Le critère exige une espérance brute améliorée de plus d'une erreur type
  dans les deux périodes ; sur 2019-2021, toutes les variantes ont une espérance brute inférieure à la
  référence. Sur 2015-2018, seules H1H3, H2H3 et H1H2H3 dépassent une erreur type.
- **À abandonner** : H1, H2, H3 et leurs quatre combinaisons, selon la grille fixée avant les
  résultats.

### 7.4 Interactions

- **H1 et H2 (parcours)** : effets faibles et à peine additifs. H1 ajoute 18 transactions (+2,7 EUR
  net), H2 en ajoute 60 (+7,7 EUR), H1H2 en ajoute 86 (+5,3 EUR). Les transactions ajoutées ont une
  espérance brute proche de zéro (+0,05 à +0,12 R), ce qui ne couvre pas les coûts ; les quelques
  transactions de la référence perdues en route étaient meilleures (+0,23 à +0,45 R brut, sur 5 à 17
  transactions). Elles augmentent la régularité (semaines actives 61-69 % contre 59 %) sans améliorer
  l'espérance.
- **H3 (filtre)** : l'essentiel du gain net vient du retrait de transactions. Les 161 transactions de
  la référence que H3 écarte ont une espérance nette de −0,105 R (−62 EUR), mais l'espérance brute de
  H3 (+0,013 R) ne s'écarte de celle de la référence que d'environ une demi-erreur type. Le filtre
  divise l'activité par deux (37 % de semaines actives, jusqu'à 71 séances sans transaction,
  10 mois sans transaction), contraire à l'objectif de régularité. Son effet s'inverse entre
  périodes (+61 EUR sur 2015-2018, −10,5 EUR sur 2019-2021).
- **H2 avec H3** : la meilleure combinaison (H2H3, −1,98 EUR, +18 EUR par rapport à H3 seule, avec
  36 transactions de plus). Ajouter H1 (H1H2H3) dégrade le net de 12 EUR : pas d'additivité.

### 7.5 Limites

- **Appariement** : les trajectoires divergent dès la première transaction différente (une position
  à la fois). Le rapprochement par `D` et sens décrit les différences ; il n'attribue pas un effet
  causal à une règle. Le retrait d'une transaction peut libérer une occasion plus tardive.
- **Erreurs types** : calculées sur chaque échantillon séparément ; les échantillons se recouvrent
  largement, donc les écarts ne sont pas indépendants. Aucun écart n'atteint deux erreurs types.
- **Périodes** : découpage exploratoire sur des années déjà examinées ; 2022-2025 non lus.
- **Comparaisons multiples** : 7 variantes contre une référence ; le meilleur résultat (H2H3) est
  attendu meilleur que la référence par simple sélection.
- **Hypothèses de coût** : ADR-035 (ASSUMED), inchangées.

### 7.6 Causalité sur données réelles

Rejeu tronqué sur les données réelles (en plus des tests synthétiques) :
- études de disponibilité arrêtées au 2018-01-01 : pour les huit configurations, les 778 séances
  antérieures sont identiques, champ pour champ, à celles de l'étude complète ;
- passage H1H2H3 (les trois règles, contexte H4 compris) arrêté au 2015-04-01 puis au 2015-07-01 :
  les 63 séances antérieures au 2015-04-01 (tentatives, causes, journal) et les 7 transactions
  closes sont identiques entre les deux troncatures et le passage complet.

Les données postérieures à T ne modifient donc aucune décision antérieure à T.

### 7.7 Recommandation

**Abandonner H1, H2 et H3 sous leur forme actuelle.** Aucune ne passe la grille enregistrée.
L'amélioration observée sur 2015-2018 ne se reproduit pas sur 2019-2021 et s'inverse d'autant plus
que les règles sont combinées, signe d'un ajustement à la première période plutôt que d'un effet
stable. H3 réduit surtout l'exposition, au prix de la régularité. H1 et H2 augmentent la fréquence
sans apporter d'espérance.

La référence DAY_02 reste inchangée et reproductible. Les nouvelles idées relèvent d'un lot
ultérieur, sur autorisation de l'opérateur.
