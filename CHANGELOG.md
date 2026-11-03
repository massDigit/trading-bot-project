# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le projet respecte le [Semantic Versioning](https://semver.org/lang/fr/).

## [Unreleased]

### Added
- Moteur S2 hors ligne, reprise de tendance après repli (`backtest/s2.py`, `backtest/s2_engine.py` ; fiche `docs/strategies/S2_PULLBACK.md`, ASSUMP-025, ADR-015), construit sur le moteur S1 sans le modifier : pivots stricts connus à `i + p`, tendance D1, configuration (identification, contact par recoupement de la zone, abandon pour données du repli incomplètes, repli trop profond, reprise sans entrée, expiration, remplacement), séquence contact → pivot de reprise → confirmation → première cassure, seuil consommé, stop structurel (bid à l'achat, `ask_high` à la vente), rapport gain net / perte estimée, cible à la première cotation exécutable, sortie temporelle, trous de cotation en scénarios A, B et C, déclenchement H1 (référence) ou H4 (comparaison), drawdown relatif maximal au tick avec premier franchissement de 6 %, bougie absente du calendrier (H1 ou H4) traitée comme inutilisable ; 20 tests synthétiques, dont l'exemple horodaté de la fiche reproduit de bout en bout avec les paramètres approuvés. Aucun passage sur données réelles.
- Projet Python 3.12 géré par `uv` (`pyproject.toml`, `uv.lock`, `.python-version`), paquet `forex_bot`.
- Client IG REST lecture seule verrouillé sur `https://demo-api.ig.com/gateway/deal` (liste blanche d'endpoints).
- Script `ig-demo-diagnostic` : authentification, comptes, solde, recherche EUR/USD, contraintes de marché.
- Masquage des secrets, jetons et identifiants de compte dans toutes les sorties.
- Tests hors ligne (`pytest`, API IG simulée), `ruff`, `mypy --strict`.
- Sélection explicite du contrat EUR/USD Mini `CS.D.EURUSD.CEFM.IP`, exclusion du marché Weekend, vérification des caractéristiques et de l'état du contrat (`instruments.py`).
- Estimation de la perte au stop (`risk.py`) : convention de prix explicite (spread compté une fois), conversion USD→EUR, coûts `CONFIRMED` / `ASSUMED` / `UNKNOWN` (un coût inconnu bloque, jamais compté zéro), financement swing, frais de conversion et prime de stop garanti.
- Dimensionnement sur les fonds propres actualisés du robot, distincts de l'allocation initiale de 2 000 EUR ; stop jamais modifié ; résultat présenté comme une estimation, pas une garantie.
- Blocage des entrées (`market.py`, `risk.py`) : marché fermé, cotation périmée ou sans horodatage, contrat non vérifié, fonds propres indisponibles, unités non confirmées, coûts inconnus.
- Contraintes distinctes stop normal / stop garanti ; conventions courtier sous forme de `Confirmation` (source, date, epic) ; blocage explicite tant que le côté de déclenchement et la référence des distances minimales ne sont pas confirmés.
- Fonds propres : refus des dates sans fuseau ou dans le futur, invalidation par tout événement de position, de frais ou de flux non intégré.
- État du marché : provenance et fraîcheur de la vérification du contrat ; contradiction contrat / cotation bloquante.
- Suivi du flux IG `PRICE` (`streaming.py`) : `TIMESTAMP` UTC, messages partiels, hors ordre, reconnexion, mises à jour perdues, `DLG_FLAG`, `DELAY`.
- Sonde `ig-price-probe` (lecture seule, démo) ; dépendance `lightstreamer-client-lib`.
- `docs/IG_SUPPORT_REQUEST.md` (brouillon non envoyé) et `docs/CONFIRMATIONS.md` (registre source/date/contrat).

- Importeur historique (`forex_bot.history`, commande `forex-history`) : fichiers exportés manuellement, copie brute immuable, manifeste et empreinte SHA-256, reprise après interruption, import idempotent, Parquet UTC, bid et ask séparés.
- Bougies H1/H4/D1 bid/ask (ancrage clôture New York), rapport qualité (trous, fermetures, ticks simultanés, contrôle du fuseau), sans comblement.
- `docs/DATA.md` (étude Dukascopy par canal d'accès : export web, JForex SDK ; conditions d'utilisation, schéma, conventions), `docs/DUKASCOPY_REQUEST.md` (brouillon non envoyé) et fiche exécutable `docs/strategies/S1_DONCHIAN.md`.
- Règle de découpage des requêtes JForex (bornes inclusives, sans doublon ni perte aux frontières).
- Adaptateur Java `tools/jforex-ticks` (SDK JForex, serveur démo, lecture seule, période 2015-2023 seulement) : un CSV par jour UTC, reprise, relance des heures vides dues aux réponses 503 du SDK, masquage des identifiants.
- Format `jforex-sdk-ticks-csv-v1` et commande `forex-history ingest-jforex`.
- Moteur de backtest S1 hors ligne (`src/forex_bot/backtest/`, ADR-006) : décision à `fin + L` sur les seules bougies disponibles, états de bougie réévalués avec l'information disponible à l'instant de décision, ATR indisponible puis réamorcé, exécution au premier tick strictement postérieur (achat à l'ask, vente au bid), stops observés / après fermeture connue / après interruption inexpliquée / non observables (politiques H0 et H1 en trajectoires distinctes), stop garanti et stop normal séparés, coûts comptés à part, dimensionnement sur les fonds propres actualisés (coût inconnu = abstention) ; 22 tests synthétiques. Non exécuté sur données réelles.
- Moteur S1, revue d'Astra (ASSUMP-024) : solde réalisé, résultat latent et fonds propres distincts, courbe échantillonnée à chaque décision H4 et à chaque sortie, position ouverte en fin d'étude valorisée ; risque au prix exécuté et dépassement du budget enregistrés sans supprimer l'exécution ; taille d'un retournement calculée sur les fonds propres incluant le latent de la position sortante ; 6 tests ciblés.
- Expérience de risque 1 % par opération (ADR-013, protocole `docs/experiments/S1_RISK_1PCT_001.md`) : option `--risk-fraction` de `forex-backtest-explore` (0,25 % par défaut) ; `forex-backtest-compare` donne aussi brut et coûts par groupe de transactions, drawdown au tick en pourcentage du sommet qui le précède, montant des dépassements et contribution du plus gros gain ; 1 test.
- Expérience de granularité 0,01 contrat (ADR-011, protocole `docs/experiments/S1_GRANULARITY_001.md`) : options `--min-size` et `--size-increment` de `forex-backtest-explore` (scénarios de recherche, 0,1 par défaut) ; commande `forex-backtest-compare` (devenir des refus de taille de la référence, transactions rapprochées par instant de décision et sens, effet pour le compte) ; 2 tests.
- Référence S1 seule 2015-2021 (ADR-010) : protocole figé `docs/experiments/S1_REFERENCE_2015_2021.md` ; `forex-backtest-explore` donne un bilan par année civile (entrées, transactions clôturées brut / coûts / net, décisions et motifs d'abstention, drawdown au tick par année, fonds propres de fin d'année), la première décision où tous les indicateurs sont calculables et la provenance du passage (commit, empreinte du diff, commande) ; 3 tests.
- Moteur S1, observation (sans effet sur les décisions) : journal d'une ligne par décision H4 de la période d'étude (informations connues à la décision, action sur la position, action d'entrée : aucun signal, évaluation impossible, signal refusé, entrée décidée ; sortie et entrée décidées ensemble conservées), résultats ultérieurs reliés à part ; drawdown maximal observable au tick depuis les fonds propres initiaux (sommet, creux et instants, sans valeur stockée par tick) ; 8 tests.
- Lecture bornée de l'historique local (`backtest/data.py`) : lecteur de ticks en flux (un fichier journalier à la fois) et lecteur de référence en mémoire (DuckDB), fenêtre limitée à 2015-2021 ; moteur alimenté par un itérateur, fenêtre d'étude `[start, end)` avec période d'initialisation ; commande `forex-backtest-explore` (scénario de coûts de recherche explicite, comparaison mémoire / flux, temps et pic de mémoire) ; 5 tests d'équivalence et de bornage (ADR-009).
- Moteur S1 : perte estimée au stop après exécution distincte de la perte simulée comptabilisée ; cas de stop déjà dépassé à l'exécution comptés dans les deux scénarios (ASSUMP-024 validée, ADR-009).
- Moteur S1, seconde revue d'Astra : fin d'étude explicite (`end_utc`), décision sur l'état strictement antérieur à `D`, règle explicite `StopAtExecution` pour une entrée dont le premier tick d'exécution dépasse déjà le stop (exécutée puis liquidée par défaut, rejet modélisé en variante) ; 4 tests ciblés.
- Mémoire `.ai/` remise en ordre : suppositions classées par nature (choix du projet, fait extérieur, observation), décisions de l'opérateur consignées (ADR-003 à ADR-008, dont la validation expérimentale des règles de S1 et l'approbation des choix du projet ASSUMP-001 à 022), tâches et état actualisés, vérifications adaptées au type de changement, normes par langage, PR empilées ; fiche S1 harmonisée (état `OK` sur `complete_at_close`, chronologie avec latence, sortie stratégique distincte d'une liquidation de sécurité, prime du stop garanti comptée à part).
- Bougies : état de qualité connaissable à la clôture (`complete_at_close`, `flags_at_close`, construit sans ticks postérieurs) distinct de l'audit rétrospectif (`complete`, `flags`) ; un tick invalide exclu rend la bougie incomplète ; `overlaps_gap(..., known_until=)` pour l'information disponible à un instant donné ; tests sur l'invariance aux ticks futurs.
- Rapport qualité : classement des interruptions corrigé (jour férié détecté à l'intérieur de l'interruption, réouverture tardive après un jour férié classée en trou), totaux par classe en durée brute et en minutes d'ouverture prévue, rapprochement des clôtures hebdomadaires, état du marché à la réouverture attendue ; bougies inchangées.
- Purge Dukascopy : le dossier `~/Library/Application Support/JForex` n'est supprimé que s'il se réduit au squelette créé par nos lancements du SDK ; sinon il est laissé en place et signalé.
- Fiche S1 : règles de données proposées après revue externe (états de bougie, ATR indisponible puis réamorcé sur 14 true ranges valides, canal D1 strict retenu par l'opérateur, positions pendant une interruption en scénarios propagés, disponibilité des bougies et ordre de traitement).
- Adaptateur JForex : liste fermée d'heures acceptées vides sur décision de l'opérateur (2016-09-02 18h, 2019-05-26 21h-22h UTC, 503 persistants à la source) ; jours écrits sans combler ces heures, signalées dans le JSON compagnon et le rapport qualité.
- Construction des bougies et du rapport qualité en mémoire bornée (DuckDB, 6 Go, débordement sur disque dans `data/tmp`) : trous, ticks en fermeture et transitions hebdomadaires calculés en SQL ; résultats identiques sur 2015-2020, 47 s au lieu de 22 min.
- Commande `forex-history purge-dukascopy` : liste puis, avec `--confirm`, supprime toutes les données dérivées de Dukascopy, le cache du SDK et `~/Library/Application Support/JForex`.

### Changed
- `.env.example` (valeurs fictives IG), `.gitignore` (environnement Python, journaux), `.editorconfig` (Python).
- Documentation adaptée au projet Robot Forex : `README.md`, `docs/`, `.ai/`.

### Fixed
- PR #5 : les sorties de passage publiées par `d316d31` (journaux de décisions, rapports et comparaisons contenant des bougies, cotations et prix dérivés de Dukascopy) sont retirées de la branche et de son historique avant fusion (ADR-014) ; elles restent locales, hors Git.
- `forex-backtest-explore` : la provenance (commit, empreinte du diff, commande) était calculée à l'écriture du rapport, donc après les modifications faites pendant le passage ; elle est désormais relevée au lancement. Pour la référence 2015-2021, l'empreinte du rapport correspond à l'arbre de fin de passage (reconstitué) ; le code exécuté est identique au commit `7414378`.
- Moteur S1 : un stop franchi sur le tick qui exécutait une sortie au canal en attente était ignoré au profit de la sortie au canal (stop garanti sans prime) ; le stop est désormais prioritaire.
- Moteur S1 : la courbe de fonds propres pouvait revenir en arrière à la fin (point au dernier tick ajouté après la dernière décision) ; les ticks horodatés exactement à `D` entraient dans le solde lu par la décision mais pas dans la cotation de dimensionnement ; une entrée dont le premier tick d'exécution dépassait le stop était annulée au vu de ce prix futur.

## [0.2.0] - 2026-10-05

### Added
- `project-bootstrap` : étape 6 de configuration GitHub du nouveau dépôt (protection de `main`, fusion squash, suppression des branches fusionnées).

### Changed
- `release-check` : étape 8 de création de la GitHub Release à partir du `CHANGELOG.md`.
- `release-check` : les commits `docs:`, `chore:`, `refactor:`, `test:`… seuls n'entraînent aucune montée de version (correctif uniquement si une release est demandée).

### Fixed
- `README.md` : création de projet via `gh repo create --template`, `degit` en `--mode=git` pour un template privé, suppression d'une phrase obsolète.

## [0.1.1] - 2026-10-05

### Added
- Lien symbolique `.claude/skills` pour exposer les skills à Claude Code.
- `.editorconfig`, `.gitattributes` et `.env.example`.
- Règle de branches (`feat/…`, `fix/…`, `chore/…`) et passage obligatoire par Pull Request (`RULES.md`).
- Convention de langue de la documentation (`CODING_STANDARDS.md`).

### Changed
- `WORKFLOW.md` : ajout des tests d'intégration, du build de production et de l'étape de validation opérateur.
- Liste de lecture au démarrage harmonisée entre `AGENTS.md`, `CLAUDE.md` et `GEMINI.md`.
- Statuts des ADR harmonisés (`ACCEPTED` | `SUPERSEDED` | `DEPRECATED`).
- `release-check` : la release passe par une branche `chore/release-vX.Y.Z` et une PR, le tag est posé après fusion.
- Skill `tests` traduit en anglais (convention de langue).
- Contenus d'exemple de `docs/DATABASE.md` et `docs/API.md` signalés comme tels.

### Fixed
- Les skills `new-feature`, `bug-investigation` et `db-migration` passent par `ASSUMPTIONS.md` au lieu d'écrire directement dans `DECISIONS.md` (règle 6).
- Liens `file://` remplacés par des liens relatifs.
- Skill `tests` : suppression de la dépendance à l'outil `run_command`.

## [0.1.0] - 2026-10-05

### Added
- Structure IA-Native : `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, mémoire `.ai/` et documentation `docs/`.
- Skills d'agent dans `.agents/skills/` (dont `project-bootstrap` et `release-check`).
- `.ai/ASSUMPTIONS.md` et règle de classification des décisions (non-usurpation d'ADR).
- Règle Git & Versioning : validation opérateur obligatoire avant tout commit/push, Conventional Commits, SemVer.
- Fichiers `VERSION` et `CHANGELOG.md`.

[Unreleased]: https://github.com/massDigit/ai-project-template/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/massDigit/ai-project-template/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/massDigit/ai-project-template/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/massDigit/ai-project-template/releases/tag/v0.1.0
