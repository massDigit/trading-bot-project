# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le projet respecte le [Semantic Versioning](https://semver.org/lang/fr/).

## [Unreleased]

## [0.2.0] - 2026-10-05

### Added
- `project-bootstrap` : étape 6 de configuration GitHub du nouveau dépôt (protection de `main`, fusion squash, suppression des branches fusionnées).

### Changed
- `release-check` : étape 8 de création de la GitHub Release à partir du `CHANGELOG.md`.
- `release-check` : les commits `docs:`, `chore:`, `refactor:`, `test:`… seuls n'entraînent aucune montée de version (correctif uniquement si une release est demandée).

### Fixed
- `README.md` : création de projet via `gh repo create --template`, `degit` en `--mode=git` pour un template privé, suppression d'une phrase obsolète.

## [0.1.1] - 2026-10-05

### Added
- Lien symbolique `.claude/skills` pour exposer les skills à Claude Code.
- `.editorconfig`, `.gitattributes` et `.env.example`.
- Règle de branches (`feat/…`, `fix/…`, `chore/…`) et passage obligatoire par Pull Request (`RULES.md`).
- Convention de langue de la documentation (`CODING_STANDARDS.md`).

### Changed
- `WORKFLOW.md` : ajout des tests d'intégration, du build de production et de l'étape de validation opérateur.
- Liste de lecture au démarrage harmonisée entre `AGENTS.md`, `CLAUDE.md` et `GEMINI.md`.
- Statuts des ADR harmonisés (`ACCEPTED` | `SUPERSEDED` | `DEPRECATED`).
- `release-check` : la release passe par une branche `chore/release-vX.Y.Z` et une PR, le tag est posé après fusion.
- Skill `tests` traduit en anglais (convention de langue).
- Contenus d'exemple de `docs/DATABASE.md` et `docs/API.md` signalés comme tels.

### Fixed
- Les skills `new-feature`, `bug-investigation` et `db-migration` passent par `ASSUMPTIONS.md` au lieu d'écrire directement dans `DECISIONS.md` (règle 6).
- Liens `file://` remplacés par des liens relatifs.
- Skill `tests` : suppression de la dépendance à l'outil `run_command`.

## [0.1.0] - 2026-10-05

### Added
- Structure IA-Native : `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, mémoire `.ai/` et documentation `docs/`.
- Skills d'agent dans `.agents/skills/` (dont `project-bootstrap` et `release-check`).
- `.ai/ASSUMPTIONS.md` et règle de classification des décisions (non-usurpation d'ADR).
- Règle Git & Versioning : validation opérateur obligatoire avant tout commit/push, Conventional Commits, SemVer.
- Fichiers `VERSION` et `CHANGELOG.md`.

[Unreleased]: https://github.com/massDigit/ai-project-template/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/massDigit/ai-project-template/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/massDigit/ai-project-template/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/massDigit/ai-project-template/releases/tag/v0.1.0
