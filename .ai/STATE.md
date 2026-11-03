# STATE.md - Photo Instantanée du Projet

> **Ce fichier donne à l'agent une image précise de l'état du projet en temps réel à chaque début de session.**

**Dernière mise à jour** : 2026-11-03
**Version de l'application** : 0.1.0 (`pyproject.toml`), non publiée
**Modèle de dépôt IA** : v0.2.0 (`massDigit/ai-project-template`, structure `AGENTS.md`, `.ai/`, `.agents/`)

## 🚀 Phase Actuelle
Historique de recherche EUR/USD acquis (2015-2023, avec exceptions connues) ; règles de données
de S1 validées comme référence expérimentale ; moteur de backtest S1 hors ligne **implémenté**,
validé comme moteur de recherche hors ligne et fusionné (PR #4, `d52f24f`) ; référence S1 seule
2015-2021 mesurée (ADR-010), variantes de granularité 0,01 contrat (ADR-011) et de risque 1 %
(ADR-013) mesurées, sans valeur de validation de performance.

## 🎯 Focus Courant
Référence S1 seule sur la période de développement 2015-2021 (branche
`feat/s1-reference-2015-2021`, PR #5 en brouillon, depuis `main` = `d52f24f`) : référence commitée
(`7414378`) ; granularité 0,01 contrat commitée (`3477689`, `d316d31`), conclusion retenue par
l'opérateur après revue d'Astra ; risque 1 % (`docs/experiments/S1_RISK_1PCT_001.md`) terminé, à
présenter avant commit. Fusion de la PR #5 réservée à l'opérateur.

## 🧾 Synthèse vérifiée (2026-11-03)
- PR #1 à #4 fusionnées dans `main` par commits de fusion, sur autorisation de l'opérateur
  (`main` = `d52f24f`). Une branche depuis `main`, une PR vers `main`.
- **PR #4 fusionnée** (`d52f24f`, 2026-11-03) après revue d'Astra sur `4c6f01a` : moteur S1 (`9b38118`),
  revues d'Astra corrigées (`b8506b0`, `cf4d0b4`) ; ASSUMP-024 validée (ADR-009) ; lecteur en
  flux et passage exploratoire (`8681a6e`) vérifiés par Astra. Journal des décisions et drawdown
  au tick (`4c6f01a`). Branche `feat/s1-reference-2015-2021` : bilan annuel (`7414378`), comparaison de passages, non commitée ; 216 tests réussis ; `ruff check`, `ruff format --check` et `uv run mypy src tests` sans erreur.
- Comparaison sur l'échantillon réel 2019-04-01 → 2019-07-01 (7 707 234 ticks, 91 fichiers) :
  lecteurs en mémoire et en flux **identiques** (transactions, coûts, journal, fonds propres, fin).
  Passage en flux seul : 164 s, pic de mémoire 195 Mio (Mac M4) ; avec la référence en mémoire : 3,7 Gio.
- Passage H0 2019-04-01 → 2019-07-01 : aucun franchissement de stop non observable (aucun passage
  H1 nécessaire pour cette fenêtre). Rejeu avec observation : 6 transactions identiques au JSON de
  référence ; 390 lignes de décision pour 390 décisions H4 ; drawdown au tick 13,77 € (échantillonné
  11,79 €) ; 190 s, pic 188 Mio.
- Référence S1 seule 2015-2021, H0 (ADR-010) : 10 912 décisions H4, 53 transactions (19 achats,
  34 ventes ; 18 gagnantes), brut +46,95 €, coûts 29,31 €, net +17,63 € ; fonds propres finaux
  2 017,63 €, aucune position ouverte ; drawdown au tick 46,34 € (échantillonné 44,85 €) ; aucun
  franchissement non observable, aucun stop dépassé à l'exécution, aucun dépassement du budget ;
  refus de taille (minimum 0,1 contrat au-dessus du budget de 0,25 %) : 215 sur 1 024 cassures
  détectées (21,0 %), ou 215 sur 268 signaux arrivés au dimensionnement (80,2 %) ; filtre D1 :
  33 refus pour historique D1 initial insuffisant, distincts des 445 refus pour canal D1 inutilisable.
  Indicateurs tous calculables à partir du 2015-03-19 21:00 UTC. 4 848 s, pic 307 Mio.
  Journal : 10 912 lignes valides, distinctes, chronologiques. Empreinte de provenance du rapport
  (`0231c857…`) différente du diff de lancement (`1515cac3…`) : calculée à l'écriture du rapport,
  après des modifications de STATE, TASKS et CHANGELOG pendant le passage (arbre de fin reconstitué
  = `0231c857…`) ; partie code (`src`, `tests`) identique au lancement et à la fin. Provenance
  désormais relevée au lancement.
- Granularité 0,01 contrat (ADR-011), même trajectoire 2015-2021 : 1 franchissement non observable,
  donc H0 et H1 (H1 : une seule transaction diffère, +0,15 €). H0 : 132 transactions (39 gagnantes),
  brut −45,62 €, coûts 60,26 €, net **−105,88 €** (H1 −105,73 €), drawdown au tick 136,64 €,
  1 dépassement du budget (0,008 €). Des 215 refus de taille : 84 exécutés (−147,09 € nets, déjà
  −117,61 € bruts), 131 non évalués (position ouverte par l'une de ces entrées), 0 toujours refusé.
  Écart −123,51 € = −147,09 (propres à la variante) + 24,69 (5 pertes de la référence évitées)
  − 1,10 (48 communes : 40 de taille différente, 8 de taille identique). Sur 2015-2021 et sous ces hypothèses, le minimum de
  0,1 contrat a protégé le compte. 4 790 s / 321 Mio (H0), 4 859 s / 313 Mio (H1).
- Risque 1 % (ADR-013), minimum et pas de 0,1 contrat, même trajectoire 2015-2021 : 1 franchissement
  non observable, donc H0 et H1 (H1 : une seule transaction diffère, +0,30 €). Mêmes transactions
  que la variante 0,01 contrat, à tailles plus élevées. H0 : 132 transactions, brut −160,99 €, coûts
  197,73 €, net **−358,71 €** (H1 −358,42 €) ; drawdown au tick 448,02 € = 21,74 % du sommet (référence
  46,34 € = 2,25 %) ; 1 dépassement du budget (0,02 €). Des 215 refus : 84 deviennent des entrées
  (−495,03 €), 131 non évalués, 0 toujours refusé. Écart −376,35 € = +94,00 (48 communes, tailles
  plus élevées) − 495,03 (84 ajoutées) + 24,69 (5 évitées). Plus gros gain : vente du 2018-04-20 ;
  sans elle, la référence passe de +17,63 € à −12,98 €, la variante de −358,71 € à −450,54 €. Sur
  2015-2021 et sous ces hypothèses, 1 % n'améliore pas S1. 4 849 s / 321 Mio (H0), 4 891 s / 311 Mio (H1).
- Branches fusionnées `feat/ig-demo-diagnostic`, `feat/eurusd-mini-risk-guard`,
  `feat/eurusd-history-s1` supprimées (locales et GitHub) après vérification.

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
- [x] Moteur S1 hors ligne implémenté (`src/forex_bot/backtest/`) ; conventions ASSUMP-024 validées (ADR-009)
- [x] Lecture bornée de l'historique : lecteur en flux (un fichier journalier à la fois) et référence en mémoire, fenêtre limitée à 2015-2021
- [x] Passage exploratoire S1 sur 2019-04-01 → 2019-07-01 (initialisation depuis 2019-01-01), dates fixées avant résultats (ADR-009)

## 📊 Résultat du diagnostic démo (2026-10-27, observations démo uniquement)
- 2 comptes CFD en EUR (« CFD » actif/par défaut, « Barrières et Options ») ; solde fictif 10 000 €.
- EUR/USD : `CS.D.EURUSD.CEF.IP` (contrat 100 000, 10 USD/pip/contrat) et `CS.D.EURUSD.CEFM.IP`
  Mini (contrat 10 000, 1 USD/pip/contrat) ; `minDealSize` 0,1 ; stop normal min 2 points ;
  stop garanti min 5 points ; marge 3,33 %. Le marché « Weekend EUR/USD » ressort aussi du filtre.
  Ces valeurs ne sont pas transposées au compte réel.

## 🔄 En Cours
- [ ] Risque 1 % (ADR-013) : H0 et H1 terminés, comparaison faite ; lot à présenter, non commité
- [ ] Recherche d'une source applicable pour les fermetures particulières (non bloquante)
- [ ] Demande au support IG préparée, non envoyée (`docs/IG_SUPPORT_REQUEST.md`)

## ⚠️ Problèmes Connus / Points de Vigilance
- Unités IG non confirmées (point/pip, unité de taille/contrat, minimum, incrément) : ASSUMP-004, ASSUMP-005.
- Coûts IG inconnus (commission, conversion, financement, prime de stop garanti) : ASSUMP-006. Ils bloquent une conclusion réaliste sur IG, pas le moteur hors ligne.
- Déclenchement des stops et référence des distances minimales non confirmés : ASSUMP-008.
- Compte réel cible à risque limité : stop garanti obligatoire, rapprochable mais jamais éloigné, prime au déclenchement (`docs/CONFIRMATIONS.md` §5, DÉCL) ; ses valeurs ne sont pas observées.
- Pas encore de suivi des fonds propres du robot en fonctionnement (le moteur de recherche les valorise, ASSUMP-024) ; flux `PRICE` validé par sonde seulement.
- Moteur S1 : la taille est fixée avant l'exécution simulée ; l'entrée exécutée peut dépasser le budget de risque, dépassement enregistré et jamais supprimé. Drawdown mesuré au tick (depuis `4c6f01a`) et sur les échantillons (décisions H4 et sorties).
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
1. Revue de la PR #5 (référence S1 2015-2021 et granularité) par l'opérateur ; ensuite seulement, sur décision, un modèle de sélection des signaux comparé à cette référence (aucun entraînement avant).
2. En parallèle : fermetures particulières et confirmations IG.
3. Garder 2022-2023 pour l'évaluation des variantes figées, puis 2024-2025 pour le test final (ADR-007).
