# ASSUMPTIONS.md - Hypothèses & Propositions à Valider

> **Ce fichier isole les hypothèses techniques et propositions émises par l'IA en attente de confirmation explicite par l'utilisateur.**

---

## ⚠️ Classification & Règles

Tout élément figurant ici est une **PROPOSITION** et ne doit pas être considéré comme une contrainte d'architecture définitive tant qu'il n'a pas été validé par l'utilisateur.

### Format d'une hypothèse / proposition :
- **ID** : `ASSUMP-001`
- **Sujet** : [ex: Choix du SGBD / Stratégie d'authentification]
- **Proposition** : [ex: PostgreSQL + Prisma ORM]
- **Raisonnement** : [Pourquoi cette solution est suggérée]
- **Statut** : `PROPOSED` | `UNDER_REVIEW` | `APPROVED` | `REJECTED`

---

## 📋 Hypothèses et Propositions Actives

- **ID** : `ASSUMP-001`
- **Sujet** : Version de Python et outil d'environnement
- **Proposition** : Python 3.12 arm64 géré par `uv` (`.python-version`, `uv.lock`), au lieu du Python 3.14 Homebrew.
- **Raisonnement** : environnement isolé et reproductible ; 3.12 maximise la disponibilité des roues arm64 de LightGBM, MLX et DuckDB prévues ensuite.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-002`
- **Sujet** : Client HTTP et authentification IG
- **Proposition** : `httpx` ; `POST /session` version 2 (jetons `CST` / `X-SECURITY-TOKEN`) plutôt que v3 (OAuth, jeton d'accès de courte durée).
- **Raisonnement** : la v2 renvoie directement comptes et compte actif ; jetons valides 6 h, suffisant pour un diagnostic. La v3 pourra être reconsidérée pour le paper trading continu.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-003`
- **Sujet** : Sélection du marché EUR/USD
- **Proposition** : retenir les résultats `instrumentType = CURRENCIES` sans échéance (`expiry = "-"`) et détailler chacun (max 5) plutôt que figer un epic dans le code.
- **Raisonnement** : IG propose plusieurs contrats EUR/USD (tailles différentes) ; le choix définitif dépend des minimums observés et du budget de risque.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-004`
- **Sujet** : Incrément de taille des positions
- **Proposition** : ne pas assimiler `dealingRules.minStepDistance` à l'incrément de taille tant que ce n'est pas confirmé (support IG ou essai contrôlé en démo, à autoriser séparément).
- **Raisonnement** : la référence IG ne documente aucun champ d'incrément de taille et décrit `minStepDistance` seulement comme « Dealing rule ».
- **Observation 2026-10-27 (démo)** : sur `CS.D.EURUSD.CEF.IP` et `CS.D.EURUSD.CEFM.IP`, `minDealSize` = 0,1 et `minStepDistance` = 5,0. Un pas de 5 avec un minimum de 0,1 est incohérent pour une taille : `minStepDistance` n'est donc vraisemblablement pas l'incrément de taille. Incrément toujours inconnu.
- **Statut** : `PROPOSED`
