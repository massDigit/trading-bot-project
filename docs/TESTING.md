# TESTING.md - Stratégie de Tests

## 🧪 Niveaux de Test

- **Tests unitaires hors ligne** (`tests/`) : l'API IG est simulée par `httpx.MockTransport`.
  Ils vérifient le scénario complet, l'absence de toute valeur secrète dans la sortie, le refus
  des endpoints de trading et de l'URL réelle, la configuration et la bascule de compte.
- **Diagnostic réel démo** (manuel) : `uv run ig-demo-diagnostic` avec un `.env.demo` local.
- **Sonde du flux PRICE démo** (manuel, lecture seule) : `uv run ig-price-probe --seconds 20`.
- **Historique** : `tests/test_history.py` (fichiers CSV synthétiques, calculs faits à la main) ; aucune donnée réelle dans les tests. Le source Java de l'adaptateur JForex est contrôlé statiquement (lecture seule, démo, période autorisée) ; l'adaptateur lui-même n'est pas testé hors ligne.
  Non exécuté par les agents IA (identifiants détenus uniquement par l'opérateur).
- Couverture cible du cahier des charges (§14) à mettre en place avec le moteur de simulation.
