# SECURITY.md - Consignes de Sécurité

## 🔒 Principes de Sécurité

1. **Variables sensibles** : un fichier de secrets par environnement — `.env.demo` en V1
   (`chmod 600`), futur `.env.live` distinct et jamais lu par la V1. Jamais commités (`.env*`
   exclu sauf `.env.example`), jamais transmis dans un chat. `.env.example` ne contient que des
   valeurs fictives. Les agents IA sont privés d'accès à ces fichiers par
   `.claude/settings.local.json` (local, non commité).
2. **Environnement verrouillé** : V1 limitée à `https://demo-api.ig.com/gateway/deal`, constante
   dans `src/forex_bot/config.py`. Les variables `IG_BASE_URL`, `IG_API_URL`, `IG_ENVIRONMENT`,
   `IG_ACC_TYPE` sont refusées. Le client refuse toute autre URL de base.
3. **Lecture seule** : liste blanche méthode/chemin dans `src/forex_bot/ig_client.py`
   (`/session`, `/accounts`, `/markets`, `/markets/{epic}`). Les endpoints de positions, ordres
   et ordres en attente sont inaccessibles ; un test vérifie ce refus.
4. **Masquage** : clé API, identifiant, mot de passe, CST, X-SECURITY-TOKEN, `accountId` et
   `clientId` sont remplacés par `[MASQUÉ:…]` dans toute sortie et tout message d'erreur.
   Les en-têtes HTTP ne sont jamais affichés. Les redirections HTTP sont désactivées pour ne
   pas transmettre les en-têtes d'authentification à un autre hôte.
5. **Journaux** : aucun fichier de journal n'est écrit à ce stade ; `logs/`, `reports/` et `*.log`
   sont exclus du Git par précaution.
6. **Réel** : aucun accès au réel tant que les conditions du cahier des charges (§11, §14) ne sont
   pas remplies et qu'une décision explicite du propriétaire n'a pas été prise.
