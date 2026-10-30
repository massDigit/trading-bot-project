# CODING_STANDARDS.md - Normes de Code & Style

## 📐 Standards de Code

- **Python (stack du projet)** : PEP 8 via `ruff` (lignes de 120), annotations de type complètes, `mypy --strict`. Nommage `snake_case` (fonctions, variables, modules), `PascalCase` (classes), `UPPER_CASE` (constantes). Docstrings sur les modules et fonctions publiques. Erreurs explicites ; jamais de secret dans un message d'exception.
- **TypeScript (si interface Next.js ultérieure)** : typage strict obligatoire (`noImplicitAny`).
- **Nommage** :
  - Variables & Fonctions : `camelCase`
  - Types, Interfaces & Composants : `PascalCase`
  - Fichiers : `kebab-case` ou `PascalCase` selon le framework
- **Documentation** : Conserver la JSDoc / TSDoc existante sur les fonctions exportées.
- **Langue de la documentation** :
  - Anglais : `README.md`, `AGENTS.md`, points d'entrée agents (`CLAUDE.md`, `GEMINI.md`) et skills (`.agents/skills/`).
  - Français : mémoire projet (`.ai/`) et documentation métier (`docs/`).
- **Gestion des erreurs** : Traitement explicite de toutes les promesses et erreurs potentiellement nulles.
