# STATE.md - Photo Instantanée du Projet

> **Ce fichier donne à l'agent une image précise de l'état du projet en temps réel à chaque début de session.**

**Dernière mise à jour** : 2026-10-05
**Version** : 0.2.0

## 🚀 Phase Actuelle
Bootstrap & Définition de la Spécification Produit.

## 🎯 Focus Courant
Initialisation de l'architecture IA-Native et rédaction des spécifications dans `docs/`.

## ✅ Réalisé
- [x] Arborescence standardisée IA (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`)
- [x] Structure de mémoire `.ai/` (`CONTEXT.md`, `STATE.md`, `TASKS.md`, `RULES.md`, `DECISIONS.md`, `ASSUMPTIONS.md`)
- [x] Skill universal `project-bootstrap` (`.agents/skills/project-bootstrap/SKILL.md`)
- [x] Règle stricte de classification des décisions & non-usurpation d'ADR (`AGENTS.md`, `RULES.md`)
- [x] Documentation d'accueil universelle générique (`README.md`)
- [x] Règle Git & Versioning (`RULES.md`), `VERSION`, `CHANGELOG.md`, procédure de release (`release-check`)
- [x] Cohérence des règles & skills, règle branches/PR, protection de `main` (v0.1.1)
- [x] Dépôt GitHub template privé, configuration GitHub dans `project-bootstrap`, GitHub Releases dans `release-check` (v0.2.0)

## 🔄 En Cours
- [ ] Test d'initialisation de projet réel via le skill `project-bootstrap` (projet LeCubeDeVie, créé depuis le template v0.2.0)

## ⚠️ Problèmes Connus / Points de Vigilance
- Template universel vierge d'application source (`src/`).

## 🏁 Prochaine Étape / Milestone
Tester le workflow de bootstrap sur un nouveau projet réel (LeCubeDeVie) pour vérifier la génération complète de la documentation sans toucher au code source.

