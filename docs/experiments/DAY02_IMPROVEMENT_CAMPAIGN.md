# Campagne exploratoire DAY_02 : H1, H2, H3 seules et combinées (2015-2021, déclenchement M5)

**Statut** : campagne **exploratoire** autorisée par l'opérateur le 2026-11-09. Ce n'est pas une
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
`data/reports/backtests/day02_campaign/` (hors Git).

| # | Essai | Configuration | Commit | Résultat | Incident |
|---|---|---|---|---|---|
| — | définitions, code et tests | §3 | (ce commit) | 574 tests | — |
