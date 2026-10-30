# WORKFLOW.md - Procédures de Validation & Dev Loop

## 🔁 Boucle de Développer-Tester-Valider

Avant de déclarer une tâche terminée, l'agent exécute les vérifications **correspondant au type de
changement** (stack : `docs/STACK.md`). Un changement qui touche plusieurs types cumule leurs
vérifications. Toutes sont hors ligne, sauf l'intégration réseau.

### Code Python (`src/`, `tests/`)

```bash
uv sync                              # environnement synchronisé avec uv.lock
uv run mypy src tests                # typage strict, tests compris
uv run ruff check src tests          # linter
uv run ruff format --check src tests # format
uv run pytest                        # tests hors ligne
```

### Adaptateur Java (`tools/jforex-ticks/`)

```bash
cd tools/jforex-ticks && JAVA_HOME=/opt/homebrew/opt/openjdk@21 mvn -q -B compile
uv run pytest -k java_adapter        # garde statique : lecture seule, démo, période autorisée
```

Ne lance **aucun** téléchargement : un essai réel du SDK exige l'accord de l'opérateur.

### Documentation seule (`docs/`, `.ai/`, `README.md`, `CHANGELOG.md`)

- Cohérence des références : identifiants `ASSUMP-` et `ADR-`, sections citées, chemins de fichiers.
- Cohérence des statuts : une décision n'apparaît dans `.ai/DECISIONS.md` que si l'opérateur l'a
  prise (date, portée, source) ; un fait extérieur n'est confirmé que par une preuve consignée dans
  `docs/CONFIRMATIONS.md`.
- Langue : français pour `.ai/` et `docs/`, anglais pour `README.md`, `AGENTS.md` et les skills.

### Données historiques (`data/`, hors Git)

```bash
uv run forex-history build           # bougies et rapport qualité, si le code de construction change
```

Comparer les sorties avant et après (colonnes existantes, rapport) et signaler toute différence.

### Intégration réseau (seulement si le changement le justifie)

Exécutée par l'opérateur avec son `.env.demo`, uniquement pour un changement du client IG, de la
sonde du flux ou de l'adaptateur JForex :

```bash
uv run ig-demo-diagnostic
uv run ig-price-probe --seconds 20   # PRICE stream probe, read-only
```

Un travail hors ligne n'est jamais bloqué par une session démo expirée.

Pas d'étape de build de production à ce stade (projet de recherche local).

Si l'une des commandes requises échoue, l'agent traite l'erreur avant de poursuivre.

## ✋ Validation Opérateur

Une fois les vérifications passées, présenter le résultat et le diff à l'opérateur. Aucun commit ni
push sans sa validation explicite (`.ai/RULES.md`, règle 7).
