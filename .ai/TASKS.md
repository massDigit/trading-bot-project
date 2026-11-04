# TASKS.md - Suivi des Tâches & Roadmap Active

## 🎯 Backlog Prioritaire

### 🏃 En Cours
- [ ] Moteur de backtest S1 hors ligne (ADR-006), PR #4 en brouillon vers `main` :
  - [x] moteur et tests synthétiques (branche `feat/s1-backtest-engine`, 2026-10-30) : chronologie et disponibilité des bougies, exécution bid/ask au premier tick après la décision, stops (observé, non observable, garanti, normal), dimensionnement, propagation des scénarios H0 / H1 aux fonds propres et aux décisions suivantes
  - [x] corrections de la revue d'Astra (2026-10-31) : stop prioritaire sur une sortie au canal en attente, solde / latent / fonds propres, risque au prix exécuté et dépassement conservé, taille d'un retournement ; 6 tests ciblés (ASSUMP-024, validée par ADR-009)
  - [x] seconde revue (2026-11-03) : fin d'étude et courbe chronologique, état strictement avant `D`, règle explicite pour une entrée au-delà du stop ; 4 tests ciblés
  - [x] journal d'une ligne par décision H4 (connu à la décision / action, résultats reliés à part) et drawdown observable au tick (2026-11-03)
  - [x] lecteur de ticks en flux (un fichier journalier à la fois, Parquet) et référence en mémoire (DuckDB) ; équivalence vérifiée sur données synthétiques et sur l'échantillon réel (2026-11-03)
  - [x] premier passage exploratoire 2019-04-01 → 2019-07-01, dates fixées avant résultats, paramètres fixes, coûts de recherche explicites (ADR-009)
  - [x] revue du passage exploratoire et fusion de la PR #4 (2026-11-03)
- [x] Référence S1 seule 2015-2021 (ADR-010, protocole `docs/experiments/S1_REFERENCE_2015_2021.md`) : H0 ; ni H1 ni rejet nécessaires ; retenue comme référence de développement (2026-11-03)
- [x] Granularité 0,01 contrat (ADR-011, protocole `docs/experiments/S1_GRANULARITY_001.md`) : H0 et H1 ; minimum de 0,1 contrat protecteur sur 2015-2021 ; conclusion retenue après revue d'Astra (2026-11-03)
- [x] Risque 1 % (ADR-013, protocole `docs/experiments/S1_RISK_1PCT_001.md`) : H0 et H1 ; 1 % n'améliore pas S1 sur 2015-2021 ; expérience close, S1 à 0,25 % reste la référence (ADR-014, 2026-11-03)
- [x] Protocole S2 (reprise de tendance après repli) : fiche `docs/strategies/S2_PULLBACK.md`, ASSUMP-025 approuvée pour la recherche hors ligne (ADR-015, 2026-11-03)
- [x] S2 étape 1 : implémentation hors ligne et 27 tests synthétiques (PR #7)
- [x] S2 étape 2 : rejeu de non-régression S1 sur avril-juin 2019 sur `7b9a1f1` : transactions, solde (1 992,04 €) et journal identiques à la référence (2026-11-03)
- [x] S2 étape 3 : disponibilité des données 2015-2021 (`docs/experiments/S2_AVAILABILITY_2015_2021.md`, 2026-11-04)
- [ ] S2 étape 4 : passages pré-enregistrés 2015-2021 (autorisée 2026-11-04 ; protocole `docs/experiments/S2_REFERENCE_2015_2021.md` figé avant lancement)
- [ ] Fermetures particulières (jours fériés, fermetures anticipées) : rechercher une source applicable, en parallèle ; sans preuve, le classement actuel est conservé (ASSUMP-016)

### 📋 A Faire
- [ ] Revue future de la référence S1 : continuité des H4 prévues dans l'ATR (`WilderAtr` enchaîne les true ranges à travers une H4 absente) ; mesurer d'abord les H4 absentes de 2015-2021, sans changer S1 avant décision
- [ ] Critères de passage du développement (2015-2021) à la validation (2022-2023) : règles et paramètres figés et versionnés, variantes enregistrées, journal complet, aucune donnée 2022-2023 consultée pour régler (ADR-007)
- [ ] Sauvegarde des données Dukascopy (environ 28 Go, uniquement sur le poste de l'opérateur) : support à choisir par l'opérateur ; la purge devra aussi couvrir la copie
- [ ] Confirmer unité de taille, taille minimale et incrément IG (ASSUMP-004, ASSUMP-005)
- [ ] Vérifier la grille de coûts IG (commission, conversion, financement, prime de stop garanti) — ASSUMP-006
- [ ] Confirmer le déclenchement des stops et la référence des distances minimales — ASSUMP-008
- [ ] Observer séparément les contraintes du compte réel à risque limité (distance minimale et prime du stop garanti) ; rendre le stop garanti obligatoire pour ce profil (`docs/CONFIRMATIONS.md` §5)
- [ ] Envoyer `docs/IG_SUPPORT_REQUEST.md` (opérateur) et reporter les réponses dans `docs/CONFIRMATIONS.md`
- [ ] Construire le suivi des fonds propres du portefeuille du robot — ASSUMP-010
- [ ] Service de flux `PRICE` permanent (fil dédié, reconnexion, réauthentification) — futur lot d'exécution continue (ADR-002)
- [ ] Revérifier l'ancrage des bougies IG sur `snapshotTimeUTC` (convention du robot : New York, ASSUMP-015)
- [ ] Calibrage Dukascopy / IG sur une période commune : prix et bougies, signaux, coûts et conditions d'exécution, séparément (ouverture de 2026 dans l'adaptateur : décision de l'opérateur)
- [ ] Mention « Powered by Dukascopy » si les données sont intégrées à une interface (licence, section 8)
- [ ] Fiches S2 et D1 (première vague)

### ✅ Terminé
- [x] Revue externe du rapport historique et revue du code : classement des interruptions, purge limitée, vérifications ciblées, état connaissable à la clôture séparé de l'audit, ticks invalides, tests anti-fuite sur de vraies clôtures H1/H4/D1 (2026-10-30, PR #3)
- [x] Règles de données de S1 validées comme référence expérimentale (ADR-006, 2026-10-30)
- [x] Choix du projet ASSUMP-001 à 022 approuvés dans leur portée (ADR-008, 2026-10-30)
- [x] Branche de la PR #3 synchronisée avec la PR #2 (`b28daa6`, registre des confirmations) (2026-10-30)
- [x] Acquisition EUR/USD 2015-01-01 → 2024-01-01 par le SDK JForex : **terminée avec exceptions connues** — 3 287 jours sur 3 287, 3 heures absentes à la source acceptées sans comblement (ADR-005), 26 trous pendant l'ouverture prévue, tous conservés et marqués ; ce ne sont pas des données parfaites (2026-10-30)
- [x] Import, bougies H1/H4/D1 et rapport qualité 2015-2023 (construction en mémoire bornée) (2026-10-30)
- [x] ADR-002 : conteneurisation Docker différée (2026-10-29)
- [x] Commande `forex-history purge-dukascopy` (liste, puis suppression avec `--confirm`) (2026-10-29)
- [x] Adaptateur Java JForex en lecture seule, démo (`tools/jforex-ticks`) et échantillon 2019-03-07 → 2019-03-13 acquis, importé et contrôlé (2026-10-28)
- [x] Contrat Mini, garde de dimensionnement et sonde du flux `PRICE` (PR #2, brouillon)
- [x] Création de l'arborescence standardisée IA (`AGENTS.md`, `.ai/`, `.agents/`)
- [x] Socle Python + client IG démo lecture seule + script de diagnostic (PR #1)
