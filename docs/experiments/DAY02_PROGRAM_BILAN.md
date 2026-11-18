# DAY_02 : bilan d'ensemble des essais d'amélioration (EUR/USD, 2015-2021, M5)

**Statut** : synthèse exploratoire du 2026-11-18. Elle ne remplace aucun bilan de campagne et ne prend
aucune décision. Elle rassemble les chiffres des passages déjà faits, sans nouvelle simulation.
Aucune donnée 2022-2025 n'a été lue, aucun ordre n'a été passé et aucune configuration n'est validée.

Conventions communes : capital 2 000 €, risque 0,25 % par transaction, une position à la fois, coûts
ADR-035 (glissement 0,5 pip, prime de stop garanti 1,2 USD par contrat, conversion 0,5 %), scénario A.
Une « séance » est une séance de Londres admissible (1 816 sur 2015-2021, 259 ou 260 par an).
R = net / perte estimée au stop ; ± = erreur type ; DD = drawdown relatif au tick.

## 1. Les campagnes et leurs documents

| Campagne | ADR | Document | Configurations | Lecture enregistrée |
|---|---|---|---|---|
| Référence | ADR-034, ADR-035 | `DAY02_REFERENCE_2015_2021.md` | REF | net −70,66 € |
| H1-H3 | ADR-036 | `DAY02_IMPROVEMENT_CAMPAIGN.md` | H1, H2, H3 et 4 combinaisons | toutes abandonnées |
| Sorties tardives | ADR-037 | `DAY02_LATE_EXIT_CAMPAIGN.md` | LATE | piste à poursuivre ; nouvelle base |
| Sorties partielles | ADR-038 | `DAY02_PARTIAL_EXITS_CAMPAIGN.md` | PROT, PART, FULL | aucune retenue |
| Criblage des guides | — (exploratoire, hors moteur) | `day02_research_annexes/guides_screening/` | 12 filtres, 2 décalages d'entrée | G1a, G5b, E3 prometteurs |
| Fréquence, guides, SMT | ADR-039 | `DAY02_FREQUENCY_CAMPAIGN.md` §7 bis-§8 | G1A, G5B, G1A5B, E3, F2R, RSC, M5S, SMTF, SMTT | voir §3 |
| Mesures hors DAY_02 | — | `day02_research_annexes/` (cost_wall, atlas, morning_short_*) | mur des coûts, atlas, ventes de matinée | voir §5 |

## 2. Transactions par séance, par année

| | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | Moyenne |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| REF | 0,166 | 0,135 | 0,181 | 0,174 | 0,158 | 0,169 | 0,165 | 0,164 |
| H1 | 0,166 | 0,154 | 0,185 | 0,197 | 0,174 | 0,173 | 0,169 | 0,174 |
| H2 | 0,189 | 0,173 | 0,201 | 0,197 | 0,205 | 0,223 | 0,192 | 0,197 |
| H3 | 0,097 | 0,073 | 0,089 | 0,085 | 0,089 | 0,092 | 0,088 | 0,088 |
| H1H2 | 0,197 | 0,196 | 0,216 | 0,220 | 0,216 | 0,235 | 0,200 | 0,211 |
| H1H3 | 0,097 | 0,085 | 0,089 | 0,097 | 0,104 | 0,104 | 0,096 | 0,096 |
| H2H3 | 0,108 | 0,085 | 0,112 | 0,104 | 0,112 | 0,119 | 0,112 | 0,107 |
| H1H2H3 | 0,116 | 0,104 | 0,116 | 0,120 | 0,124 | 0,138 | 0,115 | 0,119 |
| **LATE** | 0,166 | 0,131 | 0,181 | 0,174 | 0,158 | 0,169 | 0,162 | **0,163** |
| PROT | 0,166 | 0,131 | 0,181 | 0,174 | 0,158 | 0,169 | 0,162 | 0,163 |
| PART, FULL | 0,166 | 0,131 | 0,178 | 0,174 | 0,158 | 0,169 | 0,162 | 0,162 |
| G1A | 0,147 | 0,119 | 0,170 | 0,158 | 0,143 | 0,158 | 0,142 | 0,148 |
| G5B | 0,135 | 0,115 | 0,154 | 0,151 | 0,131 | 0,123 | 0,138 | 0,135 |
| G1A5B | 0,124 | 0,108 | 0,143 | 0,135 | 0,120 | 0,112 | 0,127 | 0,124 |
| E3 | 0,135 | 0,092 | 0,154 | 0,100 | 0,108 | 0,092 | 0,115 | 0,114 |
| F2R | 0,409 | 0,338 | 0,402 | 0,402 | 0,359 | 0,388 | 0,377 | 0,382 |
| RSC | 0,193 | 0,158 | 0,205 | 0,212 | 0,193 | 0,204 | 0,188 | 0,193 |
| M5S | 0,498 | 0,488 | 0,490 | 0,498 | 0,459 | 0,515 | 0,473 | 0,489 |
| SMTF | 0,081 | 0,042 | 0,073 | 0,100 | 0,073 | 0,096 | 0,096 | 0,080 |
| SMTT | 0,317 | 0,312 | 0,386 | 0,336 | 0,301 | 0,312 | 0,327 | 0,327 |
| Ventes de matinée | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 |

La fréquence est stable d'une année à l'autre pour toutes les configurations. Objectif de l'opérateur :
4 à 5 par séance ; le maximum DAY_02 atteint est 0,49 (M5S), avec une espérance négative.

## 3. Résultats 2015-2021

| | Trans. | Net € | R net ± ET | PF | DD | Net 15-18 | Net 19-21 | Lecture |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| REF | 298 | −70,66 | −0,064 ± 0,044 | 0,82 | 5,66 % | −61,13 | −9,53 | référence |
| H1 | 316 | −67,98 | −0,061 ± 0,043 | 0,84 | 5,24 % | −50,14 | −17,84 | abandonnée |
| H2 | 358 | −62,98 | −0,055 ± 0,039 | 0,87 | 5,08 % | −44,98 | −18,00 | abandonnée |
| H3 | 159 | −20,15 | −0,033 ± 0,065 | 0,91 | 2,53 % | −0,08 | −20,07 | abandonnée |
| H1H2 | 384 | −65,40 | −0,052 ± 0,038 | 0,87 | 4,61 % | −33,34 | −32,06 | abandonnée |
| H1H3 | 174 | −22,96 | −0,036 ± 0,062 | 0,91 | 2,92 % | +3,87 | −26,83 | abandonnée |
| H2H3 | 195 | −1,98 | −0,013 ± 0,056 | 0,99 | 2,43 % | +14,19 | −16,17 | abandonnée |
| H1H2H3 | 216 | −14,28 | −0,025 ± 0,054 | 0,95 | 3,38 % | +20,08 | −34,36 | abandonnée |
| **LATE** | 296 | **+36,32** | +0,029 ± 0,064 | 1,06 | 2,55 % | +5,29 | +31,03 | piste ; base des lots suivants |
| PROT | 296 | +24,35 | +0,010 ± 0,063 | — | 3,33 % | −12,39 | +36,74 | non retenue |
| PART | 295 | +0,82 | −0,007 ± 0,059 | — | 3,13 % | −10,20 | +11,03 | non retenue |
| FULL | 295 | −31,28 | −0,035 ± 0,056 | — | 3,78 % | −40,28 | +9,00 | non retenue |
| G1A | 269 | +82,37 | +0,077 ± 0,067 | 1,16 | 2,53 % | +16,26 | +66,11 | confirmée en trajectoire |
| G5B | 246 | +99,12 | +0,095 ± 0,071 | 1,21 | 1,94 % | +40,64 | +58,48 | confirmée en trajectoire |
| **G1A5B** | 225 | **+127,07** | **+0,131 ± 0,074** | 1,30 | 1,87 % | +45,75 | +81,32 | confirmée en trajectoire |
| E3 | 207 | +89,28 | +0,091 ± 0,094 | 1,18 | 2,80 % | +48,94 | +40,33 | confirmée en trajectoire |
| F2R | 694 | −83,86 | −0,022 ± 0,068 | 0,96 | 7,06 % | −14,41 | −69,45 | rejetée |
| RSC | 351 | −0,56 | −0,014 ± 0,058 | 1,00 | 3,34 % | −4,64 | +4,07 | rejetée |
| M5S | 888 | −337,29 | −0,099 ± 0,035 | 0,83 | 18,92 % | −157,78 | −179,51 | rejetée |
| SMTF | 146 | +54,29 | +0,082 ± 0,094 | 1,19 | 2,10 % | +5,30 | +48,99 | confirmée de justesse |
| SMTT | 594 | −262,61 | −0,103 ± 0,074 | 0,85 | 15,69 % | −225,02 | −37,59 | rejetée |

Net par année (€) depuis LATE :

| | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 |
|---|---:|---:|---:|---:|---:|---:|---:|
| LATE | −19,7 | −13,0 | +28,6 | +9,4 | +4,1 | +10,4 | +16,6 |
| PROT | −26,3 | −22,2 | +22,0 | +14,1 | −0,4 | +12,0 | +25,2 |
| PART | −16,9 | −26,2 | +29,0 | +3,9 | +0,7 | −9,2 | +19,5 |
| FULL | −21,2 | −34,9 | +18,3 | −2,4 | −2,6 | −2,8 | +14,4 |
| G1A | −4,7 | −7,7 | +21,9 | +6,8 | +4,0 | +25,0 | +37,2 |
| G5B | −10,8 | −4,6 | +30,5 | +25,5 | +26,4 | +12,3 | +19,7 |
| G1A5B | −1,6 | −1,0 | +25,4 | +22,9 | +21,7 | +26,6 | +33,0 |
| E3 | −15,1 | −15,5 | +49,0 | +30,5 | −2,7 | −10,2 | +53,2 |
| F2R | −61,3 | +7,8 | +25,8 | +13,2 | −54,7 | +36,3 | −51,1 |
| RSC | −38,4 | −15,4 | +31,0 | +18,2 | −6,5 | +11,8 | −1,2 |
| M5S | −28,8 | −76,3 | −67,3 | +14,6 | −2,2 | −101,7 | −75,6 |
| SMTF | −19,5 | −7,9 | +12,4 | +20,2 | +4,2 | +13,0 | +31,8 |
| SMTT | −35,9 | −96,6 | −116,3 | +23,8 | −25,0 | +68,2 | −80,8 |

## 4. Avantages et inconvénients

| Configuration | Avantages | Inconvénients |
|---|---|---|
| LATE | premier net positif ; effet apparié contre REF +0,092 ± 0,047 R dans les deux périodes ; DD 2,55 % | R non distinguable de zéro ; 2015-2018 nulle ; net négatif si glissement et prime doublés ; écarts IG de fin de journée non modélisés |
| PROT | même fréquence ; meilleure que LATE sur 2019-2021 | coupe plus de continuations qu'elle n'évite de pertes ; −0,020 R apparié |
| PART | même fréquence | gains raccourcis, pertes inchangées ; TP3 atteint 12 % ; −0,040 R apparié |
| FULL | — | cumule les deux défauts ; −0,068 R apparié (plus de trois ET) |
| G1A | +82 € ; retire 28 transactions de LATE à −42,74 € ; fréquence −9 % ; positif avec coûts doublés | R à un peu plus d'une ET ; règle issue du criblage des mêmes années |
| G5B | +99 € ; DD 1,94 % ; positive 2017-2021 ; positive avec coûts doublés | filtre horaire, sans calendrier d'annonces ; −17 % de fréquence, jusqu'à 55 jours sans transaction |
| G1A5B | meilleur net, R, PF et DD ; positive 2017-2021 ; +75 € avec coûts doublés | 0,124 par séance, 50 % de semaines actives ; deux règles sélectionnées sur les mêmes années ; environ 1,8 ET |
| E3 | meilleur prix sur les entrées exécutées (+68 € à taille LATE) | 90 entrées manquées, les meilleures de LATE (+116,94 €) ; 2019-2020 négatives ; exécution de l'ordre limite optimiste |
| F2R | 0,38 par séance, 88 % de semaines actives | coûts > brut ; 519 ajoutées à −98,64 € ; 28 % de gagnantes ; DD 7,06 % |
| RSC | +19 % de fréquence ; communes améliorées | 67 ajoutées à −55,15 € ; net nul |
| M5S | 0,49 par séance, 94 % de semaines actives | brut 24 € contre 361 € de coûts ; R −0,099 ± 0,035 ; DD 18,9 % |
| SMTF | +54 € ; DD 2,1 % | 0,080 par séance, jusqu'à 83 jours sans transaction ; 2015-2018 au centime de LATE ; deuxième paire nécessaire |
| SMTT | 0,33 par séance | sorties « SMT » −269 € (85 % au stop) ; DD 15,7 % |

## 5. Hors DAY_02

- **Mur des coûts** (`cost_wall/`) : entrées au hasard avec stop et cible ; mesure l'avantage qu'une
  stratégie doit dépasser selon la taille du stop. Plus le stop est court, plus les coûts fixes pèsent
  (stop 5 pips, cible 1:1 : R net −0,22 au hasard sur 2015-2019).
- **Atlas EUR/USD 2015-2019** (`atlas/`) : 48 tests, un seul phénomène retenu, la baisse de l'euro de
  09:00 à 13:00 Londres (−3,46 pips en moyenne, 5 années sur 5).
- **Vente de matinée EUR/USD** (`morning_short_eurusd/`), une transaction par jour : S30 principale ;
  2015-2019 R +0,054 ± 0,021 ; vérification 2020-2021 R +0,017 ± 0,029, **inconclusive** (2020 négative,
  ne survit pas à un glissement doublé).
- **Vente de matinée GBP/USD** (`morning_short_gbpusd/`) : S30 R −0,049 ± 0,024 sur 2015-2021, net
  −252,19 €, **non confirmée** ; corrélation jour par jour avec EUR/USD 0,33.

## 6. Constats

1. Les configurations qui améliorent le net sont des filtres et réduisent la fréquence (G1A, G5B, G1A5B,
   E3, SMTF, et avant elles H3) ; celles qui augmentent la fréquence perdent (F2R, RSC, M5S, SMTT, H1, H2).
2. Aucune espérance nette ne dépasse deux erreurs types ; les années 2015-2021 ont servi à de nombreux
   essais et plusieurs règles en sont issues (criblage) : un optimisme de sélection est attendu.
3. Seule une épreuve sur des années non lues (2022-2023, réservées), sous protocole gelé avant lecture et
   sur autorisation de l'opérateur, pourrait distinguer un effet réel d'un ajustement.
