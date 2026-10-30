# TASKS.md - Suivi des Tâches & Roadmap Active

## 🎯 Backlog Prioritaire

### 🏃 En Cours
- [ ] Moteur de backtest S1 hors ligne (ADR-006), PR #4 en brouillon vers `main` :
  - [x] moteur et tests synthétiques (branche `feat/s1-backtest-engine`, 2026-10-30) : chronologie et disponibilité des bougies, exécution bid/ask au premier tick après la décision, stops (observé, non observable, garanti, normal), dimensionnement, propagation des scénarios H0 / H1 aux fonds propres et aux décisions suivantes
  - [x] corrections de la revue d'Astra (2026-10-31) : stop prioritaire sur une sortie au canal en attente, solde / latent / fonds propres, risque au prix exécuté et dépassement conservé, taille d'un retournement ; 6 tests ciblés (ASSUMP-024 proposée)
  - [ ] journal détaillé de chaque décision, abstention et transaction (motifs, données lues, scénarios)
  - [ ] lecteur de ticks en flux (DuckDB) pour l'historique réel : impossible de charger 190 millions de ticks en mémoire
  - [ ] premier passage exploratoire sur 2015-2021 uniquement, coûts paramétrés explicitement, sans optimisation
- [ ] Fermetures particulières (jours fériés, fermetures anticipées) : rechercher une source applicable, en parallèle ; sans preuve, le classement actuel est conservé (ASSUMP-016)

### 📋 A Faire
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
