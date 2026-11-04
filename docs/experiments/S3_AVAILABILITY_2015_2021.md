# S3 — Étape 3 : disponibilité des données, développement 2015-2021

**Statut** : passage du 2026-11-04, autorisé par l'opérateur (fiche S3 §9, étape 3). Aucun tick
lu : aucune transaction, aucun gain ou perte, aucun drawdown. Ni validation de performance, ni
autorisation de trading. Bilan soumis à revue ; l'étape 4 n'est pas lancée.

## 1. Commande et provenance

```
uv run forex-s3-availability --init-start 2015-01-01 --start 2015-01-01 --end 2022-01-01 \
    --out data/reports/backtests/s3_availability_2015_2021_1be93fd.json \
    --details-out data/reports/backtests/s3_availability_2015_2021_1be93fd_details.jsonl
```

- **Code qui a produit les chiffres** : commit `1be93fda189b123cadb65f8ac1c6fd548eea3f27`
  (branche `feat/s3-data-availability`), arbre propre (aucun diff non commité).
- Entrées : 10 912 H4, 1 822 D1, 383 trous du rapport de qualité, 0 tick. 60 s, pic de mémoire
  142 Mio. Sorties détaillées hors Git (`data/`, ADR-014).
- Règles et paramètres S3 approuvés (ASSUMP-026, ADR-017, ADR-018), sans modification : bandes
  20 H4 et 2σ de population, référence de 360 H4 prévues avec au moins 240 largeurs, 20e centile
  au rang le plus proche, 6 H4 comprimées, hauteur au plus 3 × A, ATR Wilder 14, vie de 30 H4.
  Latence 0, aucune fermeture particulière documentée (comme les références S1 et S2).
- L'historique commence le 2015-01-01 : l'amorçage est compté dans la période (fiche §3).

## 2. Méthode

- **Créneaux H4 attendus** : calculés à partir du calendrier, comme pour S2. Un créneau H4 est
  attendu si son début est un début de H4 (ancrage 17 h New York) et si le marché est censé être
  ouvert à cet instant. Sont exclues la fermeture hebdomadaire et, par **convention de calcul**
  du moteur, les journées de cotation du 25 décembre et du 1er janvier (jours fériés probables,
  non confirmés). Un créneau appartient à l'année de sa disponibilité (fin de la H4, latence 0),
  dans [2015-01-01, 2022-01-01).
- Chaque créneau attendu est dans une seule classe : **absent** (aucune H4) ; **présent,
  compression calculable** ; **présent, compression non calculable**, avec sa première cause.
  La calculabilité est mesurée pour chaque H4 présente, quelle que soit la situation de la boîte
  à cet instant. Les H4 présentes hors calendrier prévu sont comptées à part.
- **Causes**, dans cet ordre :
  1. la H4 elle-même est inutilisable à sa disponibilité ;
  2. bandes non calculables, par **initialisation** (moins de 20 H4 depuis le début de
     l'historique) ou par **interruption** (une H4 prévue absente, ou une H4 inutilisable, parmi
     les 20) ;
  3. moins de 240 largeurs dans la référence, par **initialisation** (moins de 240 largeurs
     possibles depuis la première largeur de l'historique) ou par **interruption** (H4 prévues
     absentes ou inutilisables parmi les 360).
- **H4 comprimées** et **séquences** : une séquence est une suite maximale de H4 comprimées
  consécutives (continuité des H4 prévues). Plusieurs bougies comprimées appartiennent ainsi à
  une même consolidation, et une longue séquence peut donner plusieurs boîtes successives.
- **Boîtes** : règles approuvées (§4.1, §4.2), rapportées à l'année de `F`. Une
  **consolidation trop large** est refusée à chaque H4 où la fenêtre glissante de 6 H4 est
  examinée : le nombre de refus compte des décisions, pas des consolidations.
- **Convention de l'étude** (le moteur de performance S3 n'est pas modifié) : une cassure
  consomme sa boîte et n'est pas évaluée (ni expansion, ni contexte D1, ni taille, ni ordre).
  La reconnaissance d'une boîte ne dépend ni d'une position ni de l'évaluation de la cassure
  (§4.1, §4.2) : les boîtes comptées ici sont celles que verra le moteur de performance.

## 3. Créneaux H4 et calculabilité de la compression

Dénominateur des pourcentages : **créneaux H4 attendus** de l'année (ou du total).

| Année | Attendus | Absents | Présents, compression calculable | Présents, compression non calculable | Présentes hors calendrier |
|---|---:|---:|---:|---:|---:|
| 2015 | 1 554 | 0 (0,000 %) | 1 255 (80,759 %) | 299 (19,241 %) | 3 |
| 2016 | 1 560 | 0 (0,000 %) | 1 520 (97,436 %) | 40 (2,564 %) | 0 |
| 2017 | 1 554 | 0 (0,000 %) | 1 534 (98,713 %) | 20 (1,287 %) | 3 |
| 2018 | 1 554 | 0 (0,000 %) | 1 535 (98,777 %) | 19 (1,223 %) | 3 |
| 2019 | 1 554 | 0 (0,000 %) | 1 496 (96,268 %) | 58 (3,732 %) | 4 |
| 2020 | 1 560 | 0 (0,000 %) | 1 501 (96,218 %) | 59 (3,782 %) | 3 |
| 2021 | 1 560 | 0 (0,000 %) | 1 480 (94,872 %) | 80 (5,128 %) | 0 |
| **Total** | **10 896** | **0 (0,000 %)** | **10 321 (94,723 %)** | **575 (5,277 %)** | **16** |

Réconciliation des 10 912 H4 lues : 10 896 créneaux attendus, tous présents, + 16 H4 hors
calendrier prévu = 10 912. Les 16 H4 hors calendrier sont celles des journées de la convention
(24-25 décembre de 2015, 2017, 2018, 2019 et 2020 ; 31 décembre 2018 au soir). Aucun créneau H4
attendu n'est absent : les 3 H1 absentes relevées pour S2 tombent dans des H4 présentes, mais
inutilisables.

**Causes des 575 compressions non calculables** (première cause) ; dernière colonne :
pourcentage des **10 896 créneaux attendus**.

| Cause | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | Total | % des attendus |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Interruption : H4 inutilisable parmi les 20 H4 des bandes | 38 | 38 | 19 | 19 | 57 | 57 | 76 | 304 | 2,790 % |
| Initialisation : moins de 240 largeurs possibles | 240 | 0 | 0 | 0 | 0 | 0 | 0 | 240 | 2,203 % |
| Initialisation : moins de 20 H4 | 19 | 0 | 0 | 0 | 0 | 0 | 0 | 19 | 0,174 % |
| H4 elle-même inutilisable (`INTERRUPTION_INEXPLIQUÉE`) | 2 | 2 | 1 | 0 | 1 | 2 | 4 | 12 | 0,110 % |
| Interruption : H4 prévue absente (bandes ou référence) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0,000 % |
| Interruption : moins de 240 largeurs dans la référence | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0,000 % |

- **Initialisation** : 259 H4 (2,377 % des attendus), toutes en 2015. La compression est
  calculable à partir de la H4 qui commence le 2015-03-04 à 02:00 UTC, conformément à
  l'amorçage prévu par la fiche (§3).
- **Interruptions** : 316 H4 (2,900 % des attendus). Elles viennent de **16 H4 inutilisables**,
  toutes `INTERRUPTION_INEXPLIQUÉE` : chacune rend la compression non calculable pour elle-même
  et pour les 19 H4 suivantes (304 = 16 × 19).
  - 11 sont sur un créneau attendu : 2015-05-06 (13:00 ; la H4 de 09:00, également
    inutilisable, est dans la même fenêtre), 2016-09-02, 2016-12-26, 2017-12-25 22:00, 2019-05-26,
    2020-02-11, 2020-09-09, 2021-02-08, 2021-04-20, 2021-04-26 et 2021-05-03.
  - 5 sont des H4 hors calendrier des journées de la convention (25 décembre 2015, 2018, 2019
    et 2020 ; 31 décembre 2018). Présentes mais inutilisables, elles rompent la continuité. Les
    12 H4 non calculables « par elles-mêmes » sont les 12 H4 inutilisables sur un créneau attendu.
- La référence de 360 H4 n'est jamais descendue sous 240 largeurs après l'initialisation : une
  interruption isolée retire au plus 20 largeurs.

## 4. H4 comprimées, séquences et boîtes

Dénominateurs : H4 comprimées en % des **H4 présentes à compression calculable** ; boîtes
expirées et abandonnées en % des **boîtes reconnues**. Les séquences et les boîtes ne sont pas
des bougies.

| Année | H4 comprimées | % des calculables | Séquences | < 6 H4 | ≥ 1 boîte | Toutes trop larges | Autre motif | Boîtes reconnues | H4 dans les boîtes | Refus « trop large » (décisions) | Expirées | Abandonnées (données) | Consommées par une cassure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 280 | 22,311 % | 35 | 18 | 13 | 3 | 1 | 18 | 108 | 4 | 0 | 0 | 18 |
| 2016 | 333 | 21,908 % | 37 | 16 | 18 | 1 | 2 | 23 | 138 | 7 | 0 | 0 | 23 |
| 2017 | 355 | 23,142 % | 50 | 26 | 22 | 1 | 1 | 27 | 162 | 4 | 0 | 0 | 27 |
| 2018 | 280 | 18,241 % | 37 | 18 | 17 | 2 | 0 | 24 | 144 | 6 | 0 | 0 | 24 |
| 2019 | 376 | 25,134 % | 38 | 16 | 20 | 1 | 1 | 26 | 156 | 4 | 0 | 0 | 26 |
| 2020 | 313 | 20,853 % | 34 | 16 | 18 | 0 | 0 | 24 | 144 | 10 | 0 | 0 | 24 |
| 2021 | 307 | 20,743 % | 39 | 23 | 16 | 0 | 0 | 18 | 108 | 6 | 0 | 0 | 18 |
| **Total** | **2 244** | **21,742 %** | **270** | **133** | **124** | **8** | **5** | **160** | **960** | **41** | **0 (0,000 %)** | **0 (0,000 %)** | **160** |

- **Bougies et consolidations** : 2 244 H4 comprimées forment **270 séquences** (longueur
  médiane 6, maximum 49). 133 séquences ont moins de 6 H4 et ne peuvent pas donner de boîte.
  Les **160 boîtes** occupent 960 H4 comprimées (6 chacune) ; les 1 284 autres sont des séquences
  courtes, des fenêtres refusées, ou des H4 comprimées pendant la vie d'une boîte.
- Les 124 séquences qui ont donné au moins une boîte en ont donné 160 : 91 séquences une boîte,
  31 deux, une trois et une quatre (séquences longues : une nouvelle boîte peut suivre la
  cassure de la précédente, sur des bougies nouvelles).
- **Consolidations trop larges** : 41 refus (décisions), répartis sur **23 séquences**. 8 de
  ces séquences n'ont donné aucune boîte (toutes leurs fenêtres trop larges) ; dans les 15
  autres, une fenêtre ultérieure de la même séquence a été reconnue (26 refus).
- **Autre motif** : 5 séquences d'au moins 6 H4 sans boîte ni refus, parce que leurs bougies
  commençaient avant la fin de la boîte précédente (§4.1, condition 3). Aucun refus pour ATR
  indisponible.
- **Boîtes expirées : 0. Boîtes abandonnées pour données manquantes : 0.** Les 160 boîtes ont
  toutes été consommées par une cassure, 24 H4 au plus après `F` : 1 H4 pour 38 boîtes,
  médiane 3, troisième quartile 6, maximum 24. Aucune des 16 H4 inutilisables n'est tombée
  pendant la vie d'une boîte. Aucune boîte n'était active à la fin de l'étude.
- Les cassures (160) ne sont **pas évaluées** à cette étape : leur nombre n'est ni un nombre
  d'entrées, ni un résultat.

## 5. Lecture

- **Données** : la compression est calculable sur 94,7 % des créneaux attendus. Hors amorçage
  de 2015, la perte vient seulement des 16 H4 `INTERRUPTION_INEXPLIQUÉE` (2,9 % des créneaux),
  dont 5 sont des H4 partielles des journées fériées de la convention.
- **Effectif** : 160 boîtes sur sept ans, entre 18 et 27 par an. Ce sera le maximum des
  cassures évaluées à l'étape 4, avant les refus (expansion, contexte D1, marché, taille,
  position ouverte).
- **Vie des boîtes** : la limite de 30 H4 n'a jamais servi sur cette période, et la règle
  d'abandon pour données non plus. Ce constat ne change aucun paramètre.
- Les H4 comprimées représentent 21,7 % des H4 calculables, un peu plus que le seuil de 20 % :
  le seuil compare chaque H4 aux 360 précédentes, au rang le plus proche avec égalité incluse.

## 6. Limites

- Sans tick, aucune position ni aucun refus de cassure n'existe ; ils n'ont aucun effet sur les
  boîtes (§2). Les nombres de boîtes de l'étape 4 doivent donc être identiques, sur la même
  fenêtre et les mêmes données.
- Les jours de la convention (25 décembre, 1er janvier) restent hors calendrier, mais leurs H4
  partielles rompent la continuité : c'est l'application des règles approuvées, pas un choix de
  cette étude.
- Aucune donnée 2022-2025 lue ; aucun backtest de performance ; aucun entraînement ; aucun
  ordre.
