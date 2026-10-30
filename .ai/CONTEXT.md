# CONTEXT.md - Mémoire Stable & Identité du Projet

> **Ce fichier définit ce QU'EST le projet. Il reste stable dans le temps et ne contient pas le suivi des tâches quotidiennes.**
> Référence : `Cahier_des_charges_Robot_Forex_V1.md` v1.1 (27/10/2026, hors dépôt).

## 🎯 Vision du Produit
Robot de trading Forex adaptatif : analyse du contexte de marché, sélection d'une stratégie
parmi une bibliothèque limitée (neuf candidates S1–S3, D1–D3, C1–C3) ou abstention,
dimensionnement du risque et journalisation complète des décisions.

## 💡 Le Problème Résolu
Disposer d'une chaîne de recherche reproductible (données, simulation, évaluation) puis d'une
exécution contrôlée (démo, puis réel limité sur décision explicite), sans promesse de rendement.

## 👥 Personas & Utilisateurs Cibles
- **Propriétaire / opérateur** : Samuel, seul décideur du passage au réel.

## 🏛️ Principes Fondateurs
- Progression : historique → validation indépendante → paper trading → réel limité.
- Aucune fuite temporelle ; données brutes immuables ; expériences versionnées.
- Contrôleur de risque non contournable ; aucune martingale.
- Fonctionnement local prioritaire (Mac M4, 24 Go) ; secrets hors code et journaux.
- Courtier candidat : IG (API REST) ; MT5 écarté pour la V1.
