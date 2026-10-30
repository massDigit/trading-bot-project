# CODING_STANDARDS.md - Normes de Code & Style

## 📐 Standards de Code

Les règles sont propres à chaque langage.

### Python (stack principale)
- PEP 8 via `ruff` (lignes de 120), format `ruff format`.
- Annotations de type complètes, `mypy --strict` sur `src` et `tests`.
- Nommage : `snake_case` (fonctions, variables, modules et fichiers), `PascalCase` (classes),
  `UPPER_CASE` (constantes).
- Docstrings sur les modules et les fonctions publiques.
- Erreurs explicites ; jamais de secret dans un message d'exception ni dans un journal.
- Requêtes SQL (DuckDB) paramétrées (`$1`), jamais construites par formatage de chaîne.
- Prix en `Decimal` ou `decimal128` ; jamais de flottant pour un prix stocké.

### Java (adaptateur `tools/jforex-ticks`)
- Java 21, dépendances fixées dans `pom.xml`.
- Nommage : `camelCase` (méthodes, variables), `PascalCase` (classes), `UPPER_CASE` (constantes),
  paquet en minuscules (`forexbot.jforex`).
- Javadoc sur les classes et méthodes non triviales.
- Lecture seule : aucun appel au moteur d'ordres (`getEngine`, `IEngine`, `IOrder`, `submitOrder`,
  `closeOrders`) ; serveur démo figé ; test statique `test_java_adapter_is_read_only_and_demo_only`.
- Identifiants lus dans le fichier d'environnement passé en argument, masqués dans toutes les
  sorties ; écritures atomiques.

### TypeScript (seulement si une interface Next.js est ajoutée)
- Typage strict (`noImplicitAny`) ; `camelCase` pour variables et fonctions, `PascalCase` pour
  types et composants ; TSDoc sur les fonctions exportées ; promesses toujours traitées.

## 🌐 Langue de la documentation
- Anglais : `README.md`, `AGENTS.md`, points d'entrée agents (`CLAUDE.md`, `GEMINI.md`) et skills
  (`.agents/skills/`), commentaires et docstrings du code.
- Français : mémoire projet (`.ai/`) et documentation métier (`docs/`), messages affichés à
  l'opérateur.
