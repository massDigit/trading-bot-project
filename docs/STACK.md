# STACK.md - Technologies & Dépendances

## 💻 Stack (socle V1)

- **Langage** : Python 3.12 (CPython arm64, installé et épinglé par `uv` via `.python-version`)
- **Gestion d'environnement / dépendances** : `uv` (`.venv/` local, versions verrouillées dans `uv.lock`)
- **HTTP** : `httpx` 0.28 (timeouts explicites, redirections désactivées)
- **Configuration locale** : `python-dotenv` (lecture de `.env`, jamais commité)
- **Qualité** : `ruff` (lint + format), `mypy --strict`, `pytest`
- **Courtier (candidat)** : IG, API REST, environnement **démo uniquement** en V1

Prévus par le cahier des charges, non installés à ce stade : Parquet/DuckDB, LightGBM, MLX-LM (Qwen3-8B).
Le choix de Python 3.12 (plutôt que 3.14) vise la disponibilité des roues arm64 de ces bibliothèques
— voir `ASSUMP-001` dans `.ai/ASSUMPTIONS.md`.
