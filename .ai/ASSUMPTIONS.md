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
- **Garde dans le code** : `BrokerConventions.stop_trigger_side`, `normal_stop_distance_reference` et `guaranteed_stop_distance_reference` sont vides ; le dimensionnement est bloqué tant qu'ils ne portent pas une `Confirmation` (source, date, epic). Une confirmation différente de la convention implémentée bloque aussi.
- **Statut** : `PROPOSED` — question posée dans `docs/IG_SUPPORT_REQUEST.md`

- **ID** : `ASSUMP-009`
- **Sujet** : Âge maximal d'une cotation pour une entrée
- **Proposition** : 10 secondes, mesuré sur le champ `TIMESTAMP` (UTC, millisecondes) du flux `PRICE`, jamais sur l'heure de réception locale. **Paramètre expérimental**, pas une exigence IG.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-010`
- **Sujet** : Âge maximal des fonds propres du robot
- **Proposition** : 5 minutes. **Paramètre expérimental**, pas une exigence IG. Tout événement de position, de frais ou de flux non intégré invalide les fonds propres, quelle que soit leur date. Le suivi des fonds propres reste à construire.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-011`
- **Sujet** : Âge maximal de la vérification du contrat
- **Proposition** : 60 secondes, mesuré sur l'heure de réception locale de `GET /markets/{epic}` v3 (aucun horodatage IG exploitable). Paramètre expérimental. Toute contradiction entre l'état du contrat (REST) et l'état de la cotation (flux `PRICE`) bloque l'entrée ; aucune source ne l'emporte : il faut une nouvelle vérification récente concordante.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-012`
- **Sujet** : Interprétation de `DLG_FLAG` (flux `PRICE`)
- **Proposition** : seule la valeur `DEAL` est considérée comme négociable ; toutes les autres (`CLOSED`, `CALL`, `EDIT`, `CLOSINGSONLY`, `DEALNOEDIT`, `AUCTION`, `AUCTIONNOEDIT`, `SUSPEND`) bloquent. Les espaces finaux (présents dans la liste documentée par IG et observés sur la démo) sont ignorés.
- **Raisonnement** : la référence IG liste les valeurs sans les définir. Choix restrictif, à confirmer.
- **Statut** : `PROPOSED` — question posée dans `docs/IG_SUPPORT_REQUEST.md`

- **ID** : `ASSUMP-013`
- **Sujet** : Champ `DELAY` absent sur la démo
- **Proposition** : `DELAY` a été demandé mais n'a jamais été reçu avec une valeur sur la démo (2026-10-27). Une valeur absente ou inconnue bloque l'entrée (« indicateur de cotation différée inconnu »), elle n'est pas lue comme « non différé ».
- **Statut** : `PROPOSED` — question posée dans `docs/IG_SUPPORT_REQUEST.md`

- **ID** : `ASSUMP-014`
- **Sujet** : Verrouillage du flux sur la démo
- **Proposition** : `reroutingEnvironment` est renvoyé vide par la démo ; la sonde refuse toute valeur autre que vide ou `DEMO` et exige un hôte Lightstreamer de la liste démo (`demo-apd.marketdatasystems.com`, observé le 2026-10-27). Un nouvel hôte arrête la sonde jusqu'à revue (la documentation IG indique que l'adresse peut changer).
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-015`
- **Sujet** : Ancrage des bougies H4 et D1
- **Proposition** : clôture de New York (journée 17:00 → 17:00 America/New_York ; H4 à 17, 21, 01, 05, 09, 13 h New York) ; H1 sur l'heure UTC. Le dimanche soir appartient au lundi.
- **Raisonnement** : convention Forex courante ; 5 bougies D1 par semaine ; les changements d'heure américains tombent pendant la fermeture. L'ancrage des graphiques IG reste à comparer avant le direct.
- **Statut** : `PROPOSED` (configuration de travail)

- **ID** : `ASSUMP-016`
- **Sujet** : Horaire de fermeture hebdomadaire et jours fériés
- **Proposition** : fermeture du vendredi 17:00 au dimanche 17:00 New York ; 25 décembre et 1er janvier marqués « jour férié probable » (bougies incomplètes), jamais classés silencieusement comme fermeture normale.
- **Statut** : `PROPOSED` — à confronter à l'échantillon et aux horaires IG

- **ID** : `ASSUMP-017`
- **Sujet** : Seuil de trou de cotation
- **Proposition** : un intervalle sans tick valide de plus de 10 minutes pendant l'ouverture prévue rend les bougies concernées incomplètes. Paramètre propre au projet.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-018`
- **Sujet** : Canal et conditions d'accès aux données Dukascopy
- **Proposition** : canal privilégié : JForex SDK (`IHistory`), sous la licence de l'API JForex (usage personnel, non commercial). Aucune acquisition tant que restent ambigus : conservation persistante hors cache (« temporary use »), conversion en Parquet et bougies (« adapt, modify »), usage pour un compte chez un autre courtier, apprentissage, conditions du compte démo. Question préparée : `docs/DUKASCOPY_REQUEST.md` (non envoyée). Pas de téléchargement automatisé depuis le site (CGU du site, section 3).
- **Statut** : `PROPOSED` — l'opérateur a décidé le 2026-10-28 d'acquérir par le SDK malgré les ambiguïtés, pour un usage personnel non commercial, sans envoyer la question, avec arrêt et purge en cas d'avertissement de Dukascopy (`docs/DATA.md` §1.3)

- **ID** : `ASSUMP-019`
- **Sujet** : Format et convention temporelle des données Dukascopy
- **Proposition** : export CSV : en-tête `Gmt time,Ask,Bid,AskVolume,BidVolume`, date `dd.MM.yyyy HH:mm:ss.SSS`, 5 décimales, temps **déclaré** GMT/UTC (non documenté). JForex : `getTime()` sans unité ni fuseau documentés (millisecondes GMT selon le forum seulement). La fermeture et la réouverture hebdomadaires ne sont que des contrôles de cohérence.
- **Statut** : `PROPOSED` — JForex : lecture en millisecondes UTC cohérente sur l'échantillon 2019-03 (clôture et réouverture à moins de 0,1 min de l'horaire attendu) ; toujours non documentée

- **ID** : `ASSUMP-020`
- **Sujet** : Paramètres de la fiche S1
- **Proposition** : N = 20, M = 10, ATR 14, k = 2, filtre D1 au milieu du canal 55 jours, signal sur la série bid (voir `docs/strategies/S1_DONCHIAN.md`). Aucun réglage ni résultat.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-021`
- **Sujet** : Découpage des requêtes JForex
- **Proposition** : fenêtres d'une heure ; demander `[début − 1 ms, fin − 1 ms]` puis garder `début ≤ t < fin`, filtrage sur le temps uniquement. Aucun tick dupliqué ni supprimé aux frontières ; ticks simultanés conservés (`src/forex_bot/history/jforex.py`). Sources : le wiki officiel (« History ticks ») indique que `from` et `to` sont **tous deux inclusifs** ; la Javadoc ne le précise que pour `to`. La règle reste correcte dans les deux cas.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-022`
- **Sujet** : Heures vides renvoyées par le SDK JForex
- **Proposition** : une heure sans tick alors que le marché est attendu ouvert est traitée comme un échec de téléchargement, pas comme une absence de cotation : suppression du fichier de cache de 0 octet de cette heure, jusqu'à 5 tentatives, puis jour non écrit (`<jour>.incomplete.json`). Fondé sur l'observation du 2026-10-28 (réponse HTTP 503 transformée en liste vide et mise en cache). La structure du cache est observée, non documentée. Les heures des jours fériés probables (25 décembre, 1er janvier, ASSUMP-016) ne sont pas relancées.
- **Statut** : `PROPOSED`

- **ID** : `ASSUMP-023`
- **Sujet** : Règles de données de S1 (bougies non utilisables, ATR, canal D1, positions pendant une interruption, disponibilité des bougies)
- **Proposition** : `docs/strategies/S1_DONCHIAN.md` §5 et §10. États `OK` / `FERMETURE_DOCUMENTÉE` (fermeture particulière établie par une source citée ; un jour férié probable ne suffit pas ; aucune bougie dans cet état aujourd'hui) / `COUVERTURE_PARTIELLE` / `INTERRUPTION_INEXPLIQUÉE`. Pas d'entrée si le signal n'est pas `OK`, si une bougie des canaux H4 n'est pas utilisable, si l'ATR est indisponible ou si la règle D1 stricte échoue. ATR **indisponible** (pas nul) après une bougie non utilisable, réamorcé par 14 true ranges valides (clôture précédente utilisable) : 15 bougies utilisables nécessaires, 21 pour une entrée compte tenu du canal. Positions pendant une interruption : franchissement observé, franchissement possible non observable, prix de déclenchement et prix d'exécution simulé distingués ; stop garanti et stop normal simulés séparément avec leurs coûts ; transactions INDÉTERMINÉES suivies en scénarios propagés aux fonds propres et aux décisions suivantes, jamais supprimées, jamais présentés comme des bornes garanties. Bougies lues selon `available_at_utc` ; ordre déterministe clôture → indicateurs → sortie → entrée → exécution au premier tick suivant.
- **Statut** : `PROPOSED` — canal D1 : règle **stricte** retenue par l'opérateur comme référence le 2026-10-30 (règle ciblée écartée) ; variante sans filtre D1 conservée comme expérience distincte, sans sélection sur 2022-2023 ; le reste est à valider avant l'écriture du moteur
