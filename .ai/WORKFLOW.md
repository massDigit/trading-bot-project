# WORKFLOW.md - Procédures de Validation & Dev Loop

## 🔁 Boucle de Développer-Tester-Valider

Avant de déclarer une tâche terminée, l'agent doit exécuter (stack Python, voir `docs/STACK.md`) :

```bash
# 0. Environnement synchronisé avec uv.lock
uv sync

# 1. Typecheck
uv run mypy src tests

# 2. Linter et format
uv run ruff check src tests
uv run ruff format --check src tests

# 3. Tests unitaires (hors ligne)
uv run pytest

# 4. Tests d'intégration : diagnostic démo IG, exécuté par l'opérateur avec son .env.demo
uv run ig-demo-diagnostic
uv run ig-price-probe --seconds 20   # PRICE stream probe, read-only
```

Pas d'étape de build de production à ce stade (projet de recherche local).

Si l'une de ces commandes échoue, l'agent doit immédiatement traiter l'erreur avant de poursuivre.

## ✋ Validation Opérateur

Une fois les vérifications passées, présenter le résultat à l'opérateur. Aucun commit ni push sans sa validation explicite (`.ai/RULES.md`, règle 7).
