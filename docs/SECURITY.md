# SECURITY.md - Consignes de Sécurité

## 🔒 Principes de Sécurité

1. **Variables Sensibles** : Ne jamais commiter de fichiers `.env` ou de clés d'API.
2. **Sanitisation** : Assainir toutes les entrées utilisateurs contre les injections XSS et SQL.
3. **Authentication & CORS** : Restreindre les origines CORS autorisées en production.
