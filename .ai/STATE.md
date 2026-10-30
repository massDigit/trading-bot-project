# STATE.md - Photo Instantanée du Projet

> **Ce fichier donne à l'agent une image précise de l'état du projet en temps réel à chaque début de session.**

**Dernière mise à jour** : 2026-10-30
**Version** : 0.2.0 (template) — socle Python non encore publié

## 🚀 Phase Actuelle
Historique de recherche EUR/USD acquis (2015-2023) ; préparation du moteur de backtest S1.

## 🎯 Focus Courant
Revue externe (Astra) du rapport sur l'historique : corrections, vérifications ciblées et règles de
données de S1 proposées (branche `feat/eurusd-history-s1`, PR #3 brouillon, worktree séparé).
Aucune PR ne sera fusionnée avant la fin des retours de la revue (décision de l'opérateur).

## ✅ Réalisé
- [x] Structure IA-Native (template v0.2.0)
- [x] Projet Python 3.12 / uv, dépendances verrouillées (`uv.lock`)
- [x] `.env.example` fictif, `.gitignore` (secrets, `.venv`, journaux)
- [x] Client IG lecture seule verrouillé sur la démo, masquage des secrets
- [x] Script de diagnostic + 15 tests hors ligne (ruff, mypy strict, pytest OK)

- [x] Diagnostic réel démo exécuté le 2026-10-27 : code 0, aucune donnée sensible affichée

## 📊 Résultat du diagnostic démo (2026-10-27)
- 2 comptes CFD en EUR (« CFD » actif/par défaut, « Barrières et Options ») ; solde fictif 10 000 €.
- EUR/USD : `CS.D.EURUSD.CEF.IP` (contrat 100 000, 10 USD/pip/contrat) et `CS.D.EURUSD.CEFM.IP`
  Mini (contrat 10 000, 1 USD/pip/contrat) ; `minDealSize` 0,1 ; stop normal min 2 points ;
  stop garanti min 5 points ; marge 3,33 %. Le marché « Weekend EUR/USD » ressort aussi du filtre.

- [x] PR #1 (`feat/ig-demo-diagnostic`) ouverte, non fusionnée
- [x] Contrat Mini explicite + vérification + garde de dimensionnement (branche `feat/eurusd-mini-risk-guard`), diagnostic réel OK

- [x] Corrections de revue du commit cedbfb5 (stop garanti, convention de déclenchement, horodatage des fonds propres, état du marché) + 111 tests
- [x] Flux `PRICE` vérifié sur la démo le 2026-10-27 : `TIMESTAMP` reçu, `DLG_FLAG` = DEAL (avec espaces), `DELAY` jamais renseigné

- [x] Importeur historique reproductible (brut immuable, manifeste, empreinte, reprise, idempotence), bougies H1/H4/D1 bid/ask, rapport qualité, tests synthétiques
- [x] Fiche exécutable S1 (brouillon, paramètres proposés)
- [x] Adaptateur JForex SDK (Java, démo, lecture seule) ; échantillon 2019-03 acquis : 530 478 ticks, aucune anomalie, 97 H1 complètes (2026-10-28)
- [x] Acquisition complète 2015-2023 terminée le 2026-10-30 **avec exceptions connues** : 3 287 jours sur 3 287, 260 051 730 ticks ; 3 heures absentes à la source (2016-09-02 18h, 2019-05-26 21h-22h UTC) acceptées par l'opérateur sans comblement (ces journées restent incomplètes)
- [x] Bougies H1/H4/D1 et rapport qualité sur 2015-2023 (construction en mémoire bornée, 87 s) ; 26 trous pendant l'ouverture prévue, bougies incomplètes marquées (H1 89, H4 46, D1 33)
- [x] Vérifications ciblées (2026-10-30) : comptes Java / CSV / Parquet identiques, conversion décimale exacte, aucune heure dupliquée, 5 jours re-téléchargés dans un cache isolé identiques octet pour octet (`docs/DATA.md` §6.1)
- [x] Classement des interruptions corrigé (jour férié détecté à l'intérieur de l'interruption ; une réouverture tardive n'est plus masquée) ; purge limitée au squelette du dossier JForex créé par nos lancements
- [x] ADR-002 : conteneurisation Docker différée jusqu'au besoin d'exécution continue

## 🔄 En Cours
- [ ] PR #1 ouverte, PR #2 brouillon (dépend de #1), PR #3 brouillon (dépend de #2) ; aucune fusion avant les retours de la revue externe
- [ ] Règles de données de S1 proposées (ASSUMP-023, fiche S1 §10) : canal D1 **strict** retenu par l'opérateur comme référence le 2026-10-30 ; états de bougie, ATR, positions pendant une interruption à valider
- [ ] Demande au support IG préparée, non envoyée (`docs/IG_SUPPORT_REQUEST.md`)

## ⚠️ Problèmes Connus / Points de Vigilance
- Unités IG non confirmées (point/pip, unité de taille/contrat, minimum, incrément) : ASSUMP-005.
- Coûts IG inconnus (commission, conversion, financement, stop garanti) : ASSUMP-006.
- Pas encore de suivi des fonds propres du robot ; flux `PRICE` validé par sonde seulement (pas de service permanent avec reconnexion et réauthentification).
- Conventions de stop (côté de déclenchement, référence des distances) non confirmées : ASSUMP-008.
- Incrément de taille : pas de champ dédié documenté par IG (`ASSUMP-004`).
- Mot de passe chiffré non géré si IG l'exige.
- Dukascopy : licence ambiguë pour la conservation locale et la conversion ; l'opérateur a décidé d'acquérir quand même (usage personnel, arrêt en cas d'avertissement) ; convention temporelle non documentée, cohérente sur l'échantillon (ASSUMP-018, ASSUMP-019).
- SDK JForex : une réponse HTTP 503 devient une heure vide mise en cache, sans erreur ; détecté et relancé par l'adaptateur (ASSUMP-022). Compte démo valable 14 jours.
- 18 interruptions de 10 à 26 min commencent 0 à 45 min après 17:00 New York (15 en semaine, 3 réouvertures du dimanche ; 11 en 2023) : **inexpliquées**, reproduites à l'identique par un re-téléchargement isolé ; jamais traitées comme des fermetures connues.
- Spreads Dukascopy nettement plus larges entre 21h et 24h UTC (95e centile pondéré par la durée : 2,7 pips) ; les spreads IG restent à mesurer.
- Ancrage des bougies IG non vérifié (`snapshotTime` local / `snapshotTimeUTC`) ; l'ancrage New York est conservé pour la recherche et le fonctionnement (ASSUMP-015).
- Données Dukascopy (environ 28 Go) uniquement sur le poste de l'opérateur, hors Git, sans copie de sauvegarde.

## 🏁 Prochaine Étape / Milestone
1. Valider les règles de données de S1 (ASSUMP-023) ; chercher une source documentée des fermetures particulières (sans elle, chaque jour férié probable bloque environ 55 jours d'entrées filtrées : 40,6 % des décisions H4 bloquées sur 2015-2021).
2. Implémenter le moteur S1 avec ces règles et un journal détaillé (pas avant la validation).
3. Premier backtest exploratoire sur 2015-2021 uniquement, coûts paramétrés explicitement.
4. Comparer ensuite prix, bougies, signaux et coûts avec IG (calibrage ; ouverture de 2026 dans
   l'adaptateur à décider par l'opérateur).
Côté IG (inchangé) : confirmer unités, taille minimale, distances de stop et coûts (ASSUMP-004 à 008).
