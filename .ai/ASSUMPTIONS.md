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

- **ID** : `ASSUMP-005`
- **Sujet** : Unités IG pour EUR/USD Mini
- **Proposition** : à confirmer — rapport point IG / pip, rapport unité de taille / contrat, taille minimale et incrément.
- **Raisonnement** : `minDealSize` et les distances de `dealingRules` sont renvoyés en « POINTS », ce qui ne permet pas de conclure. Ces valeurs restent vides dans `EURUSD_MINI_CONVENTIONS` ; aucune n'est supposée implicitement (pas de 1 point = 1 pip, pas de 1 unité = 1 contrat). Les vérifications qui en dépendent sont bloquées.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-006`
- **Sujet** : Statut des coûts
- **Proposition** : glissement `ASSUMED` à 0,5 pip ; commission, frais de conversion, financement overnight et prime de stop garanti `UNKNOWN` jusqu'à vérification sur la grille IG. Un coût inconnu bloque le dimensionnement et n'est jamais compté comme zéro.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-007`
- **Sujet** : Taux de conversion USD → EUR
- **Proposition** : 1 / bid EUR/USD au moment du calcul (côté qui maximise la perte en EUR). Les frais de conversion IG sont traités séparément (ASSUMP-006).
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-008`
- **Sujet** : Côté de déclenchement des stops et référence de la distance minimale
- **Proposition** : un stop d'achat est un niveau bid, un stop de vente un niveau offer ; la distance minimale du courtier se mesure depuis le prix de sortie courant (bid pour un achat, offer pour une vente).
- **Raisonnement** : convention usuelle des CFD, non confirmée dans la référence IG consultée. Elle détermine que le spread est compté une seule fois, via l'entrée.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-009`
- **Sujet** : Âge maximal d'une cotation pour une entrée
- **Proposition** : 10 secondes, mesuré sur l'horodatage du courtier (UTC). Source d'horodatage fiable à choisir (flux Lightstreamer ou `snapshot.updateTimestampUTC` de `GET /markets/{epic}` v4).
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-010`
- **Sujet** : Âge maximal des fonds propres du robot
- **Proposition** : 5 minutes. Le suivi des fonds propres (réalisé, latent, frais, flux) reste à construire.
- **Statut** : `PROPOSED`
