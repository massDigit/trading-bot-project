# WORKFLOW.md - Procédures de Validation & Dev Loop

## 🔁 Boucle de Développer-Tester-Valider

Avant de déclarer une tâche terminée, l'agent doit exécuter :

```bash
# 1. Verification TypeScript / Typecheck
npm run typecheck

# 2. Linter
npm run lint

# 3. Tests Unitaires
npm test

# 4. Tests d'Intégration
npm run test:integration

# 5. Build de Production
npm run build
```

> Les commandes ci-dessus sont des valeurs par défaut pour une stack Node.js. Les adapter à la stack réelle définie dans `docs/STACK.md`.

Si l'une de ces commandes échoue, l'agent doit immédiatement traiter l'erreur avant de poursuivre.

## ✋ Validation Opérateur

Une fois les vérifications passées, présenter le résultat à l'opérateur. Aucun commit ni push sans sa validation explicite (`.ai/RULES.md`, règle 7).
