# TESTING.md - Stratégie de Tests

## 🧪 Niveaux de Test

- **Tests unitaires hors ligne** (`tests/`) : l'API IG est simulée par `httpx.MockTransport`.
  Ils vérifient le scénario complet, l'absence de toute valeur secrète dans la sortie, le refus
  des endpoints de trading et de l'URL réelle, la configuration et la bascule de compte.
- **Diagnostic réel démo** (manuel) : `uv run ig-demo-diagnostic` avec un `.env.demo` local.
- **Sonde du flux PRICE démo** (manuel, lecture seule) : `uv run ig-price-probe --seconds 20`.
  Non exécuté par les agents IA (identifiants détenus uniquement par l'opérateur).
- Couverture cible du cahier des charges (§14) à mettre en place avec le moteur de simulation.
