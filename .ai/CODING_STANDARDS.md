# CODING_STANDARDS.md - Normes de Code & Style

## 📐 Standards de Code

- **Langage & Typage** : TypeScript / Modern JavaScript. Typage strict obligatoire (`noImplicitAny`).
- **Nommage** :
  - Variables & Fonctions : `camelCase`
  - Types, Interfaces & Composants : `PascalCase`
  - Fichiers : `kebab-case` ou `PascalCase` selon le framework
- **Documentation** : Conserver la JSDoc / TSDoc existante sur les fonctions exportées.
- **Langue de la documentation** :
  - Anglais : `README.md`, `AGENTS.md`, points d'entrée agents (`CLAUDE.md`, `GEMINI.md`) et skills (`.agents/skills/`).
  - Français : mémoire projet (`.ai/`) et documentation métier (`docs/`).
- **Gestion des erreurs** : Traitement explicite de toutes les promesses et erreurs potentiellement nulles.
