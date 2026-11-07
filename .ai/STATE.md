# STATE.md - Photo Instantanée du Projet

> **Ce fichier donne à l'agent une image précise de l'état du projet en temps réel à chaque début de session.**

**Dernière mise à jour** : 2026-11-07
**Version de l'application** : 0.1.0 (`pyproject.toml`), non publiée
**Modèle de dépôt IA** : v0.2.0 (`massDigit/ai-project-template`, structure `AGENTS.md`, `.ai/`, `.agents/`)

## 🚀 Phase Actuelle
Historique de recherche EUR/USD acquis (2015-2023, avec exceptions connues) ; règles de données
de S1 validées comme référence expérimentale ; moteur de backtest S1 hors ligne **implémenté**,
validé comme moteur de recherche hors ligne et fusionné (PR #4, `d52f24f`) ; référence S1 seule
2015-2021 mesurée (ADR-010), variantes de granularité 0,01 contrat (ADR-011) et de risque 1 %
(ADR-013) mesurées, sans valeur de validation de performance.

## 🎯 Focus Courant
Quatre candidates de la bibliothèque (cahier v1.2 §6) ont été **étudiées** sur EUR/USD, partition
de développement 2015-2021, avec paramètres et coûts de recherche figés :
- **S1** Donchian D1 → H4 : référence de développement (ADR-010, ADR-011, ADR-014) ;
- **S2** reprise après repli H1 : étudiée, résultats insuffisants pour conclure (ADR-016) ;
- **S3** cassure après compression D1 → H4 : étudiée, effectif insuffisant pour conclure sur sa
  rentabilité (ADR-020) ;
- **DAY_01** cassure du range précédant Londres et retest, M5 (référence) et M15 (comparaison) :
  étudiée, résultats défavorables dans les conditions testées, **non retenue pour le paper
  trading** (ADR-024, PR #21 fusionnée, `8bc08b9`).

Suite de la bibliothèque (ADR-025) : ordre **D2 avant D3** confirmé ; fiche **DAY_02**
(continuation après impulsion et drapeau, `docs/strategies/DAY_02_FLAG_CONTINUATION.md`,
ASSUMP-029) rédigée en PR #23 ; base de rédaction et extension de la convention de qualité à 5 min retenues (ADR-026), corrections intégrées (ordre des extrêmes, extension / profondeur / échéances, étude de disponibilité sans position, limite de perte journalière, horaires), chronologie, valeurs de référence et dérogation sur les limites journalière et hebdomadaire retenues (ADR-027) ; **fiche figée le 2026-11-07, ASSUMP-029 `APPROVED` pour la recherche hors ligne seulement (ADR-028)** ; réutilisation validée et implémentation autorisée (ADR-029) : moteur `backtest/day02_engine.py` (`Day02Backtest` sur `S1Backtest`, sans héritage de DAY_01), règles sur bougies `backtest/day02.py`, 45 tests synthétiques `tests/test_day02.py` ; lot moteur **clos**, PR #24 fusionnée (`653cdac`, ADR-030) ; aucun module existant modifié ; 506 tests réussis. Protocole de disponibilité `docs/experiments/DAY02_AVAILABILITY_2015_2021.md` approuvé dans son principe, précisions intégrées (ADR-031) ; outil `forex-day02-availability` (`backtest/day02_availability.py`) et 20 tests synthétiques en PR brouillon #25, corrections après revue intégrées (ADR-032), **soumis à revue** ; aucun passage historique, aucune lecture des données de recherche.
**Aucune expérience n'est autorisée** : ni moteur, ni analyse historique, ni backtest, ni
entraînement, ni ordre ; 2022-2025 reste en réserve. Conditions IG : point ouvert distinct (fiche
§8), à trancher avant tout passage de performance.

## 🧾 Synthèse vérifiée (2026-11-03)
- PR #1 à #4 fusionnées dans `main` par commits de fusion, sur autorisation de l'opérateur
  (`main` = `d52f24f`). Une branche depuis `main`, une PR vers `main`.
- **PR #4 fusionnée** (`d52f24f`, 2026-11-03) après revue d'Astra sur `4c6f01a` : moteur S1 (`9b38118`),
  revues d'Astra corrigées (`b8506b0`, `cf4d0b4`) ; ASSUMP-024 validée (ADR-009) ; lecteur en
  flux et passage exploratoire (`8681a6e`) vérifiés par Astra. Journal des décisions et drawdown
  au tick (`4c6f01a`). Branche `feat/s1-reference-2015-2021` : bilan annuel (`7414378`), comparaison de passages, non commitée ; 216 tests réussis ; `ruff check`, `ruff format --check` et `uv run mypy src tests` sans erreur.
- Comparaison sur l'échantillon réel 2019-04-01 → 2019-07-01 (7 707 234 ticks, 91 fichiers) :
  lecteurs en mémoire et en flux **identiques** (transactions, coûts, journal, fonds propres, fin).
  Passage en flux seul : 164 s, pic de mémoire 195 Mio (Mac M4) ; avec la référence en mémoire : 3,7 Gio.
- Passage H0 2019-04-01 → 2019-07-01 : aucun franchissement de stop non observable (aucun passage
  H1 nécessaire pour cette fenêtre). Rejeu avec observation : 6 transactions identiques au JSON de
  référence ; 390 lignes de décision pour 390 décisions H4 ; drawdown au tick 13,77 € (échantillonné
  11,79 €) ; 190 s, pic 188 Mio.
- Référence S1 seule 2015-2021, H0 (ADR-010) : 10 912 décisions H4, 53 transactions (19 achats,
  34 ventes ; 18 gagnantes), brut +46,95 €, coûts 29,31 €, net +17,63 € ; fonds propres finaux
  2 017,63 €, aucune position ouverte ; drawdown au tick 46,34 € (échantillonné 44,85 €) ; aucun
  franchissement non observable, aucun stop dépassé à l'exécution, aucun dépassement du budget ;
  refus de taille (minimum 0,1 contrat au-dessus du budget de 0,25 %) : 215 sur 1 024 cassures
  détectées (21,0 %), ou 215 sur 268 signaux arrivés au dimensionnement (80,2 %) ; filtre D1 :
  33 refus pour historique D1 initial insuffisant, distincts des 445 refus pour canal D1 inutilisable.
  Indicateurs tous calculables à partir du 2015-03-19 21:00 UTC. 4 848 s, pic 307 Mio.
  Journal : 10 912 lignes valides, distinctes, chronologiques. Empreinte de provenance du rapport
  (`0231c857…`) différente du diff de lancement (`1515cac3…`) : calculée à l'écriture du rapport,
  après des modifications de STATE, TASKS et CHANGELOG pendant le passage (arbre de fin reconstitué
  = `0231c857…`) ; partie code (`src`, `tests`) identique au lancement et à la fin. Provenance
  désormais relevée au lancement.
- Granularité 0,01 contrat (ADR-011), même trajectoire 2015-2021 : 1 franchissement non observable,
  donc H0 et H1 (H1 : une seule transaction diffère, +0,15 €). H0 : 132 transactions (39 gagnantes),
  brut −45,62 €, coûts 60,26 €, net **−105,88 €** (H1 −105,73 €), drawdown au tick 136,64 €,
  1 dépassement du budget (0,008 €). Des 215 refus de taille : 84 exécutés (−147,09 € nets, déjà
  −117,61 € bruts), 131 non évalués (position ouverte par l'une de ces entrées), 0 toujours refusé.
  Écart −123,51 € = −147,09 (propres à la variante) + 24,69 (5 pertes de la référence évitées)
  − 1,10 (48 communes : 40 de taille différente, 8 de taille identique). Sur 2015-2021 et sous ces hypothèses, le minimum de
  0,1 contrat a protégé le compte. 4 790 s / 321 Mio (H0), 4 859 s / 313 Mio (H1).
- Risque 1 % (ADR-013), minimum et pas de 0,1 contrat, même trajectoire 2015-2021 : 1 franchissement
  non observable, donc H0 et H1 (H1 : une seule transaction diffère, +0,30 €). Mêmes transactions
  que la variante 0,01 contrat, à tailles plus élevées. H0 : 132 transactions, brut −160,99 €, coûts
  197,73 €, net **−358,71 €** (H1 −358,42 €) ; drawdown au tick 448,02 € = 21,74 % du sommet (référence
  46,34 € = 2,25 %) ; 1 dépassement du budget (0,02 €). Des 215 refus : 84 deviennent des entrées
  (−495,03 €), 131 non évalués, 0 toujours refusé. Écart −376,35 € = +94,00 (48 communes, tailles
  plus élevées) − 495,03 (84 ajoutées) + 24,69 (5 évitées). Plus gros gain : vente du 2018-04-20 ;
  sans elle, la référence passe de +17,63 € à −12,98 €, la variante de −358,71 € à −450,54 €. Sur
  2015-2021 et sous ces hypothèses, 1 % n'améliore pas S1. 4 849 s / 321 Mio (H0), 4 891 s / 311 Mio (H1). Expérience close (ADR-014).
- Branches fusionnées `feat/ig-demo-diagnostic`, `feat/eurusd-mini-risk-guard`,
  `feat/eurusd-history-s1` supprimées (locales et GitHub) après vérification.

## ✅ Réalisé
- [x] Structure IA-Native (modèle de dépôt v0.2.0)
- [x] Projet Python 3.12 / uv, dépendances verrouillées (`uv.lock`)
- [x] `.env.example` fictif, `.gitignore` (secrets, `.venv`, journaux, `data/`)
- [x] Client IG lecture seule verrouillé sur la démo, masquage des secrets ; diagnostic réel démo exécuté le 2026-10-27 (code 0)
- [x] Contrat Mini explicite + vérification + garde de dimensionnement (PR #2) ; flux `PRICE` observé sur la démo le 2026-10-27 (`TIMESTAMP` reçu, `DLG_FLAG` = DEAL avec espaces, `DELAY` jamais renseigné)
- [x] Importeur historique reproductible (brut immuable, manifeste, empreinte, reprise, idempotence), bougies H1/H4/D1 bid/ask, rapport qualité
- [x] Adaptateur JForex SDK (Java, démo, lecture seule)
- [x] Acquisition 2015-2023 **terminée avec exceptions connues** (ADR-004, ADR-005) : 3 287 jours sur 3 287, 260 051 730 ticks ; 3 heures absentes à la source acceptées sans comblement (2016-09-02 18h, 2019-05-26 21h-22h UTC) : ces journées restent incomplètes
- [x] Bougies et rapport qualité 2015-2023. Bougies incomplètes, **audit rétrospectif** (`complete`) : H1 89, H4 46, D1 33 ; **état connaissable à la clôture** (`complete_at_close`, seul utilisable pour une décision) : H1 87, H4 45, D1 32
- [x] Vérifications ciblées (`docs/DATA.md` §6.1) : comptes Java / CSV / Parquet identiques, conversion décimale exacte, aucune heure dupliquée ; **5 journées** re-téléchargées dans un cache isolé, identiques octet pour octet
- [x] Classement des interruptions corrigé ; purge limitée au squelette du dossier JForex créé par nos lancements
- [x] Règles de données de S1 validées comme référence expérimentale (ADR-006) ; fiche S1 harmonisée
- [x] Choix du projet ASSUMP-001 à 022 approuvés dans leur portée (ADR-008) ; faits extérieurs ouverts : ASSUMP-005, 008, 018, 019 et parts extérieures des entrées mixtes
- [x] ADR-002 : conteneurisation Docker différée jusqu'au besoin d'exécution continue
- [x] Moteur S1 hors ligne implémenté (`src/forex_bot/backtest/`) ; conventions ASSUMP-024 validées (ADR-009)
- [x] Lecture bornée de l'historique : lecteur en flux (un fichier journalier à la fois) et référence en mémoire, fenêtre limitée à 2015-2021
- [x] Passage exploratoire S1 sur 2019-04-01 → 2019-07-01 (initialisation depuis 2019-01-01), dates fixées avant résultats (ADR-009)

## 📊 Résultat du diagnostic démo (2026-10-27, observations démo uniquement)
- 2 comptes CFD en EUR (« CFD » actif/par défaut, « Barrières et Options ») ; solde fictif 10 000 €.
- EUR/USD : `CS.D.EURUSD.CEF.IP` (contrat 100 000, 10 USD/pip/contrat) et `CS.D.EURUSD.CEFM.IP`
  Mini (contrat 10 000, 1 USD/pip/contrat) ; `minDealSize` 0,1 ; stop normal min 2 points ;
  stop garanti min 5 points ; marge 3,33 %. Le marché « Weekend EUR/USD » ressort aussi du filtre.
  Ces valeurs ne sont pas transposées au compte réel.

## 🔄 En Cours
- [x] S3 étape 1 : moteur hors ligne (`backtest/s3.py`, `s3_engine.py`, S1 et S2 inchangés) et 28 tests synthétiques, dont l'exemple du §7, ses deux suites et l'abandon de la sortie suiveuse quand le stop est atteint avant son exécution ; validée par l'opérateur (PR #13). Aucun passage historique
- [x] S3 étape 2 (2026-11-04) : rejeu S1 H0 du 2019-04-01 au 2019-07-01 sur `main` = `51f1507` (après fusion du moteur S3), identique à la référence `s1_2019Q2_stream.json` : 6 transactions identiques champ par champ, solde 1 992,04 €, journal des 390 décisions identique octet pour octet ; 190 s, 187 Mio. Sorties hors Git. Étude de disponibilité et backtest de performance S3 non lancés
- [x] S3 étape 3 (2026-11-04, `1be93fd`, `docs/experiments/S3_AVAILABILITY_2015_2021.md`, close, PR #15) : 10 896 créneaux H4 attendus, 0 absent ; compression non calculable sur 575 (5,277 %) : 259 d'initialisation, 316 décisions bloquées par 28 H4 `INTERRUPTION_INEXPLIQUÉE` (12 sur calendrier, 16 hors calendrier, 16 épisodes) ; 2 244 H4 comprimées en 270 séquences ; 160 boîtes, 41 refus trop large (23 séquences), 0 expirée, 0 abandonnée, 160 consommées par une cassure non évaluée
- [x] S3 étape 4 (2026-11-04, `15d2c83`, PR #16, bilan validé, ADR-020) : protocole `docs/experiments/S3_REFERENCE_2015_2021.md` figé avec l'outil `forex-s3-backtest` ; passages A D1 → H4 et H4 seule lancés, contrôles réussis (160 boîtes identiques à l'étape 3, 160 cassures rapprochées, aucun doublon), B et rejet sans objet (0 franchissement non observable, 0 stop dépassé à l'exécution). Référence : 5 transactions, net +5,62 € (−8,82 € sans la meilleure), drawdown 0,774 %, 4 pertes sur 4 simultanées à une perte S1 ; H4 seule : 7 transactions, +5,37 €. Bilan agrégé `docs/experiments/S3_REFERENCE_2015_2021_BILAN.md`. S3 étudiée, effectif insuffisant pour conclure, faible apport par rapport à S1 ; aucun paramètre modifié, aucune nouvelle expérience
- [ ] Recherche d'une source applicable pour les fermetures particulières (non bloquante)
- [ ] Demande au support IG préparée, non envoyée (`docs/IG_SUPPORT_REQUEST.md`)

## ⚠️ Problèmes Connus / Points de Vigilance
- Unités IG non confirmées (point/pip, unité de taille/contrat, minimum, incrément) : ASSUMP-004, ASSUMP-005.
- Coûts IG inconnus (commission, conversion, financement, prime de stop garanti) : ASSUMP-006. Ils bloquent une conclusion réaliste sur IG, pas le moteur hors ligne.
- Déclenchement des stops et référence des distances minimales non confirmés : ASSUMP-008.
- Compte réel cible à risque limité : stop garanti obligatoire, rapprochable mais jamais éloigné, prime au déclenchement (`docs/CONFIRMATIONS.md` §5, DÉCL) ; ses valeurs ne sont pas observées.
- Pas encore de suivi des fonds propres du robot en fonctionnement (le moteur de recherche les valorise, ASSUMP-024) ; flux `PRICE` validé par sonde seulement.
- ATR de Wilder du moteur S1 (`WilderAtr`) : il enchaîne les true ranges d'une H4 présente à la suivante sans vérifier qu'aucune H4 attendue ne manque entre elles. S2 utilise une lecture qui respecte la continuité (`ContinuousWilderAtr`) ; S1 et sa référence 2015-2021 sont inchangés. Limite héritée, à revoir lors d'une future revue de la référence S1 (nombre de H4 absentes dans 2015-2021 non mesuré).
- Moteur S1 : la taille est fixée avant l'exécution simulée ; l'entrée exécutée peut dépasser le budget de risque, dépassement enregistré et jamais supprimé. Drawdown mesuré au tick (depuis `4c6f01a`) et sur les échantillons (décisions H4 et sorties).
- Mot de passe chiffré non géré si IG l'exige.
- Dukascopy : ambiguïté de licence **non résolue** (ASSUMP-018) ; acquisition par décision de l'opérateur (ADR-004), arrêt et purge en cas d'avertissement ; convention temporelle non documentée, cohérente sur 2015-2023 (ASSUMP-019).
- SDK JForex : une réponse HTTP 503 devient une heure vide mise en cache, sans erreur ; traitée comme acquisition incomplète (ASSUMP-022). Compte démo valable 14 jours.
- 18 interruptions de 10 à 26 min commencent 0 à 45 min après 17:00 New York (15 en semaine, 3 réouvertures du dimanche ; 11 en 2023) : **inexpliquées**, jamais traitées comme des fermetures connues. Le re-téléchargement isolé n'a vérifié que **5 journées** à trous, dont 3 de ce groupe (2021-04-20, 2023-03-15, 2023-06-15) ; la conclusion « présentes dans les données servies par Dukascopy » ne vaut que pour ces journées.
- Jours fériés probables non documentés : classés interruption inexpliquée pour S1 ; 40,6 % des décisions H4 2015-2021 bloquées (variante avec filtre D1, état connaissable à la clôture, sans position simulée).
- Spreads Dukascopy nettement plus larges entre 21h et 24h UTC (95e centile pondéré par la durée : 2,7 pips) ; les spreads IG restent à mesurer.
- Ancrage des bougies IG à revérifier sur `snapshotTimeUTC` ; l'ancrage New York est la convention proposée du robot (ASSUMP-015).
- Données Dukascopy (environ 28 Go) uniquement sur le poste de l'opérateur, hors Git, sans copie de sauvegarde.
- Authentification SSH vers GitHub intermittente le 2026-10-30 (clé enregistrée et chargée) ; une nouvelle tentative a suffi.

## 🏁 Prochaine Étape / Milestone
1. S1, S2 et S3 étudiées sur 2015-2021 (ADR-016, ADR-020), sans conclusion de rentabilité. Suite (stratégie, paramètres, capital ou risque, modèle de sélection) sur décision de l'opérateur seulement ; aucune expérience en cours.
   Première vague (cahier v1.2 §6.6, §15 lot 3A) : fiche DAY_01 figée (ADR-022) ; lot de données M5/M15 2015-2021 clôturé (ADR-021, convention DAY_01 : silence > 5 min) ; moteur DAY_01 hors ligne (référence M5 et variante M15) et tests synthétiques fusionnés (PR #19, ADR-023) ; étude de disponibilité 2015-2021 **close** (PR #20 fusionnée, `ef41596`) : passage du 2026-11-06 sur `1c1ed0f`, C1 à C10 conformes, bilan agrégé `docs/experiments/DAY01_AVAILABILITY_2015_2021_BILAN.md` validé ; 1 816 séances attendues, 1 204 cassures, 831 confirmations M5 et 736 M15 (instants d'évaluation, pas des entrées). Protocole de performance `docs/experiments/DAY01_REFERENCE_2015_2021.md` approuvé dans son principe (2026-11-07, `03c6643`), trois précisions intégrées (parcours jusqu'à `D` séparé de la décision, issues exclusives et annotations, liquidation en attente à la fin) ; outil `forex-day01-backtest` et `forex-day01-compare` avec tests synthétiques, figé à `3d38ad5`. Passages A M5 et M15 autorisés et faits le 2026-11-07 sur `3d38ad5`, contrôles conformes, aucun passage B, C ni rejet requis ; bilan agrégé `docs/experiments/DAY01_REFERENCE_2015_2021_BILAN.md` validé, étape **close** (PR #21 fusionnée, ADR-024) : net −586,71 € en M5 (831 transactions, sept années déficitaires, drawdown relatif maximal 31,1 %), −289,12 € en M15 (736 transactions). **DAY_01 étudiée, résultats défavorables dans les conditions testées ; aucune trajectoire retenue pour le paper trading** ; aucune sélection de M15 après coup, aucun changement de paramètre, aucun filtre tiré des sous-groupes positifs. Suite de la bibliothèque : décision séparée à venir.
2. En parallèle : fermetures particulières et confirmations IG.
3. Garder 2022-2023 pour l'évaluation des variantes figées, puis 2024-2025 pour le test final (ADR-007).
