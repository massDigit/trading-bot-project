# TASKS.md - Suivi des Tâches & Roadmap Active

## 🎯 Backlog Prioritaire

### 🏃 En Cours
- [ ] Validation de `feat/eurusd-mini-risk-guard`
- [ ] Confirmer unité de taille, taille minimale et incrément IG (support IG ou essai démo autorisé séparément)

### 📋 A Faire
- [ ] Valider ou rejeter ASSUMP-001 à ASSUMP-004
- [ ] Vérifier la grille de coûts IG (commission, conversion, financement, stop garanti) — ASSUMP-006
- [ ] Construire le suivi des fonds propres du portefeuille du robot — ASSUMP-010
- [ ] Envoyer `docs/IG_SUPPORT_REQUEST.md` (opérateur) et reporter les réponses dans `docs/CONFIRMATIONS.md`
- [ ] Valider ASSUMP-011 à ASSUMP-014 (vérification contrat 60 s, `DLG_FLAG`, `DELAY`, hôte démo)
- [ ] Service de flux `PRICE` permanent (fil dédié, reconnexion, réauthentification) — futur lot
- [ ] Acquisition complète EUR/USD 2015-01-01 → 2024-01-01 par le SDK JForex, traitement des jours incomplets, import, rapport qualité — ASSUMP-022
- [ ] Mention « Powered by Dukascopy » si les données sont intégrées à une interface (licence, section 8)
- [ ] Revoir la fiche S1 et ses décisions ouvertes ; fiches S2 et D1 (première vague)
- [ ] Comparer l'ancrage H4/D1 proposé à celui des graphiques IG — ASSUMP-015

### ✅ Terminé
- [x] Commande `forex-history purge-dukascopy` (liste, puis suppression avec `--confirm`) (2026-10-29)
- [x] Adaptateur Java JForex en lecture seule, démo (`tools/jforex-ticks`) et échantillon 2019-03-07 → 2019-03-13 acquis, importé et contrôlé (2026-10-28)
- [x] Création de l'arborescence standardisée IA (`AGENTS.md`, `.ai/`, `.agents/`)
- [x] Socle Python + client IG démo lecture seule + script de diagnostic (PR #1)
