# STACK.md - Technologies & Dépendances

## 💻 Stack (socle V1)

- **Langage** : Python 3.12 (CPython arm64, installé et épinglé par `uv` via `.python-version`)
- **Gestion d'environnement / dépendances** : `uv` (`.venv/` local, versions verrouillées dans `uv.lock`)
- **HTTP** : `httpx` 0.28 (timeouts explicites, redirections désactivées)
- **Configuration locale** : `python-dotenv` (lecture de `.env`, jamais commité)
- **Qualité** : `ruff` (lint + format), `mypy --strict`, `pytest`
- **Courtier (candidat)** : IG, API REST, environnement **démo uniquement** en V1

- **Données historiques** : `pyarrow` (Parquet), `duckdb` (agrégations) — voir `docs/DATA.md`
- **Acquisition Dukascopy** : Java 21 (OpenJDK Homebrew, arm64), Maven, SDK `DDS2-jClient-JForex` 3.6.51 (`tools/jforex-ticks`, isolé du robot Python)
- **Flux de prix** : `lightstreamer-client-lib` (client officiel Lightstreamer)

Prévus par le cahier des charges, non installés à ce stade : LightGBM, MLX-LM (Qwen3-8B).
Le choix de Python 3.12 (plutôt que 3.14) vise la disponibilité des roues arm64 de ces bibliothèques
— voir `ASSUMP-001` dans `.ai/ASSUMPTIONS.md`.
