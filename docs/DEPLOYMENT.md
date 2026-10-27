# DEPLOYMENT.md - Procédure de Déploiement

## 🚀 CI/CD Pipeline

- **Environnement de Staging** : Auto-deploy sur chaque Pull Request validée.
- **Environnement de Production** : Déploiement manuel/tag Git.

## 🏷️ Versioning & Releases

- **Schéma** : [Semantic Versioning](https://semver.org/lang/fr/) `MAJOR.MINOR.PATCH`. Version courante dans le fichier `VERSION`.
- **Tags** : Tags Git annotés au format `vX.Y.Z` ; un tag déclenche le déploiement en production.
- **Changelog** : Chaque release est documentée dans `CHANGELOG.md` (format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/)).
- **Procédure** : Skill `.agents/skills/release-check/SKILL.md`.
