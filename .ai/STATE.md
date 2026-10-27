# STATE.md - Photo Instantanée du Projet

> **Ce fichier donne à l'agent une image précise de l'état du projet en temps réel à chaque début de session.**

**Dernière mise à jour** : 2026-10-27
**Version** : 0.2.0 (template) — socle Python non encore publié

## 🚀 Phase Actuelle
Lot 0/5 préparatoire : socle Python et vérification de l'accès à l'API IG démo en lecture seule.

## 🎯 Focus Courant
Contrat EUR/USD Mini et garde de dimensionnement (branche `feat/eurusd-mini-risk-guard`, basée sur PR #1).

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

## 🔄 En Cours
- [ ] PR #2 brouillon `feat/eurusd-mini-risk-guard` (dépend de la PR #1), en revue
- [ ] Demande au support IG préparée, non envoyée (`docs/IG_SUPPORT_REQUEST.md`)

## ⚠️ Problèmes Connus / Points de Vigilance
- Unités IG non confirmées (point/pip, unité de taille/contrat, minimum, incrément) : ASSUMP-005.
- Coûts IG inconnus (commission, conversion, financement, stop garanti) : ASSUMP-006.
- Pas encore de suivi des fonds propres du robot ; flux `PRICE` validé par sonde seulement (pas de service permanent avec reconnexion et réauthentification).
- Conventions de stop (côté de déclenchement, référence des distances) non confirmées : ASSUMP-008.
- Incrément de taille : pas de champ dédié documenté par IG (`ASSUMP-004`).
- Mot de passe chiffré non géré si IG l'exige.

## 🏁 Prochaine Étape / Milestone
Résultat réel du diagnostic → confirmer epic EUR/USD, taille minimale et distances de stop,
puis vérifier la compatibilité avec un risque de 5 € par opération (cahier des charges §8).
