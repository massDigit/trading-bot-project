# RULES.md - Règles d'Ingénierie Stricte

> **Ces règles sont NON NÉGOCIABLES pour tout assistant IA ou développeur travaillant sur la codebase.**

1. **Aucun patch superficiel** : Toujours corriger la cause racine au lieu de contourner les exceptions.
2. **Découplage & Modularité** : Séparer strictement la logique métier des couches d'affichage et d'infrastructure.
3. **Contrat d'API strict** : Ne jamais altérer une signature de fonction ou de type sans mettre à jour tous ses appels.
4. **Ne jamais deviner les schemas** : Toujours lire la définition exacte des entités dans `docs/DATABASE.md` ou le code source avant consommation.
5. **Gestion propre du state** : Ne pas muter directement l'état global avec des objets partiels ou incomplets.
6. **Classification des décisions & non-usurpation d'ADR** : Ne jamais inscrire une proposition technique de l'agent dans `.ai/DECISIONS.md` sans validation explicite de l'utilisateur. Toute hypothèse non confirmée doit figurer dans `.ai/ASSUMPTIONS.md`.
7. **Git & Versioning** :
   - **Validation opérateur obligatoire** : Aucun `git commit` ni `git push` ne doit être exécuté sans que l'opérateur humain ait explicitement validé, testé et jugé la fonctionnalité conforme. Les vérifications automatiques de `.ai/WORKFLOW.md` sont nécessaires mais ne remplacent pas cette validation. Une validation ne vaut que pour la modification concernée, pas pour les suivantes.
   - **Conventional Commits** : Messages au format `type(scope): description` (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`…), un commit = un changement cohérent.
   - **Branches & Pull Requests** : Aucun commit direct sur `main`. Tout changement passe par une branche nommée selon son type — `feat/<description>`, `fix/<description>`, `chore/<description>` (en `kebab-case`) — puis par une Pull Request vers `main`, fusionnée après validation de l'opérateur.
   - **PR empilées** : une PR qui dépend d'une autre non fusionnée cible volontairement la branche de celle-ci (exemple : #2 → `feat/ig-demo-diagnostic`, #3 → `feat/eurusd-mini-risk-guard`). Sa description indique la dépendance et l'ordre de fusion ; elle est reciblée vers `main` lors de l'intégration. Une mise à jour de la branche parente est intégrée par une fusion (pas de réécriture de l'historique déjà poussé). L'agent ne fusionne jamais une PR.
   - **Semantic Versioning** : Versions `MAJOR.MINOR.PATCH`, tags Git au format `vX.Y.Z`, chaque release documentée dans `CHANGELOG.md`.
