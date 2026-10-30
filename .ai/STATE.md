# STATE.md - Photo Instantanée du Projet

> **Ce fichier donne à l'agent une image précise de l'état du projet en temps réel à chaque début de session.**

**Dernière mise à jour** : 2026-10-31
**Version de l'application** : 0.1.0 (`pyproject.toml`), non publiée
**Modèle de dépôt IA** : v0.2.0 (`massDigit/ai-project-template`, structure `AGENTS.md`, `.ai/`, `.agents/`)

## 🚀 Phase Actuelle
Historique de recherche EUR/USD acquis (2015-2023, avec exceptions connues) ; règles de données
de S1 validées comme référence expérimentale ; moteur de backtest S1 hors ligne **implémenté**
(tests synthétiques), **en revue** (PR #4) ; **aucun passage sur données historiques réalisé**.

## 🎯 Focus Courant
Corrections de la revue d'Astra du moteur S1 (branche `feat/s1-backtest-engine`, PR #4 en
brouillon vers `main`) : priorité du stop sur une sortie au canal, fonds propres valorisés,
risque au prix exécuté, taille d'un retournement. Ensuite : lecteur de ticks en flux et petit
passage exploratoire sur 2015-2021.

## 🧾 Synthèse vérifiée (2026-10-31)
- PR #1, #2 et #3 fusionnées dans `main` par commits de fusion, sur autorisation de l'opérateur
  (`main` = `aa69503`). Une branche depuis `main`, une PR vers `main`.
- **PR #4 ouverte en brouillon** (`feat/s1-backtest-engine` → `main`) : moteur S1 au commit
  `9b38118`, revu par Astra le 2026-10-31 (deux défauts reproduits, non couverts par les tests) ;
  corrections et 6 tests ciblés dans l'arbre de travail, non commités. 194 tests réussis ;
  `ruff check`, `ruff format --check` et `uv run mypy src tests` sans erreur.

## ✅ Réalisé
- [x] Structure IA-Native (modèle de dépôt v0.2.0)
- [x] Projet Python 3.12 / uv, dépendances verrouillées (`uv.lock`)
- [x] `.env.example` fictif, `.gitignore` (secrets, `.venv`, journaux, `data/`)
- [x] Client IG lecture seule verrouillé sur la démo, masquage des secrets ; diagnostic réel démo exécuté le 2026-10-27 (code 0)
- [x] Contrat Mini explicite + vérification + garde de dimensionnement (PR #2) ; flux `PRICE` observé sur la démo le 2026-10-27 (`TIMESTAMP` reçu, `DLG_FLAG` = DEAL avec espaces, `DELAY` jamais renseigné)
- [x] Importeur historique reproductible (brut immuable, manifeste, empreinte, reprise, idempotence), bougies H1/H4/D1 bid/ask, rapport qualité
- [x] Adaptateur JForex SDK (Java, démo, lecture seule)
- [x] Acquisition 2015-2023 **terminée avec exceptions connues** (ADR-004, ADR-005) : 3 287 jours sur 3 287, 260 051 730 ticks ; 3 heures absentes à la source acceptées sans comblement (2016-09-02 18h, 2019-05-26 21h-22h UTC) : ces journées restent incomplètes
- [x] Bougies et rapport qualité 2015-2023. Bougies incomplètes, **audit rétrospectif** (`complete`) : H1 89, H4 46, D1 33 ; **état connaissable à la clôture** (`complete_at_close`, seul utilisable pour une décision) : H1 87, H4 45, D1 32
- [x] Vérifications ciblées (`docs/DATA.md` §6.1) : comptes Java / CSV / Parquet identiques, conversion décimale exacte, aucune heure dupliquée ; **5 journées** re-téléchargées dans un cache isolé, identiques octet pour octet
- [x] Classement des interruptions corrigé ; purge limitée au squelette du dossier JForex créé par nos lancements
- [x] Règles de données de S1 validées comme référence expérimentale (ADR-006) ; fiche S1 harmonisée
- [x] Choix du projet ASSUMP-001 à 022 approuvés dans leur portée (ADR-008) ; faits extérieurs ouverts : ASSUMP-005, 008, 018, 019 et parts extérieures des entrées mixtes
- [x] ADR-002 : conteneurisation Docker différée jusqu'au besoin d'exécution continue
- [x] Moteur S1 hors ligne implémenté (`src/forex_bot/backtest/`), tests synthétiques uniquement ; jamais exécuté sur l'historique

## 📊 Résultat du diagnostic démo (2026-10-27, observations démo uniquement)
- 2 comptes CFD en EUR (« CFD » actif/par défaut, « Barrières et Options ») ; solde fictif 10 000 €.
- EUR/USD : `CS.D.EURUSD.CEF.IP` (contrat 100 000, 10 USD/pip/contrat) et `CS.D.EURUSD.CEFM.IP`
  Mini (contrat 10 000, 1 USD/pip/contrat) ; `minDealSize` 0,1 ; stop normal min 2 points ;
  stop garanti min 5 points ; marge 3,33 %. Le marché « Weekend EUR/USD » ressort aussi du filtre.
  Ces valeurs ne sont pas transposées au compte réel.

## 🔄 En Cours
- [ ] Revue du moteur S1 (PR #4) : corrections d'Astra appliquées, conventions ASSUMP-024 proposées à l'opérateur
- [ ] Lecteur de ticks en flux (DuckDB) puis premier passage exploratoire 2015-2021 : **non réalisé**
- [ ] Recherche d'une source applicable pour les fermetures particulières (non bloquante)
- [ ] Demande au support IG préparée, non envoyée (`docs/IG_SUPPORT_REQUEST.md`)

## ⚠️ Problèmes Connus / Points de Vigilance
- Unités IG non confirmées (point/pip, unité de taille/contrat, minimum, incrément) : ASSUMP-004, ASSUMP-005.
- Coûts IG inconnus (commission, conversion, financement, prime de stop garanti) : ASSUMP-006. Ils bloquent une conclusion réaliste sur IG, pas le moteur hors ligne.
- Déclenchement des stops et référence des distances minimales non confirmés : ASSUMP-008.
- Compte réel cible à risque limité : stop garanti obligatoire, rapprochable mais jamais éloigné, prime au déclenchement (`docs/CONFIRMATIONS.md` §5, DÉCL) ; ses valeurs ne sont pas observées.
- Pas encore de suivi des fonds propres du robot en fonctionnement (le moteur de recherche les valorise, ASSUMP-024) ; flux `PRICE` validé par sonde seulement.
- Moteur S1 : la taille est fixée avant l'exécution simulée ; l'entrée exécutée peut dépasser le budget de risque, dépassement enregistré et jamais supprimé. Drawdown mesuré sur des échantillons (décisions H4 et sorties), pas tick par tick.
- Mot de passe chiffré non géré si IG l'exige.
- Dukascopy : ambiguïté de licence **non résolue** (ASSUMP-018) ; acquisition par décision de l'opérateur (ADR-004), arrêt et purge en cas d'avertissement ; convention temporelle non documentée, cohérente sur 2015-2023 (ASSUMP-019).
- SDK JForex : une réponse HTTP 503 devient une heure vide mise en cache, sans erreur ; traitée comme acquisition incomplète (ASSUMP-022). Compte démo valable 14 jours.
- 18 interruptions de 10 à 26 min commencent 0 à 45 min après 17:00 New York (15 en semaine, 3 réouvertures du dimanche ; 11 en 2023) : **inexpliquées**, jamais traitées comme des fermetures connues. Le re-téléchargement isolé n'a vérifié que **5 journées** à trous, dont 3 de ce groupe (2021-04-20, 2023-03-15, 2023-06-15) ; la conclusion « présentes dans les données servies par Dukascopy » ne vaut que pour ces journées.
- Jours fériés probables non documentés : classés interruption inexpliquée pour S1 ; 40,6 % des décisions H4 2015-2021 bloquées (variante avec filtre D1, état connaissable à la clôture, sans position simulée).
- Spreads Dukascopy nettement plus larges entre 21h et 24h UTC (95e centile pondéré par la durée : 2,7 pips) ; les spreads IG restent à mesurer.
- Ancrage des bougies IG à revérifier sur `snapshotTimeUTC` ; l'ancrage New York est la convention proposée du robot (ASSUMP-015).
- Données Dukascopy (environ 28 Go) uniquement sur le poste de l'opérateur, hors Git, sans copie de sauvegarde.
- Authentification SSH vers GitHub intermittente le 2026-10-30 (clé enregistrée et chargée) ; une nouvelle tentative a suffi.

## 🏁 Prochaine Étape / Milestone
1. Valider les corrections de la PR #4, puis lecteur de ticks en flux et petit passage sur 2015-2021 uniquement, coûts paramétrés (non confirmés chez IG), sans optimisation.
2. En parallèle : fermetures particulières et confirmations IG.
3. Garder 2022-2023 pour l'évaluation des variantes figées, puis 2024-2025 pour le test final (ADR-007).
