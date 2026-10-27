# API.md - Contrats d'API & Endpoints

> ⚠️ **Exemple du template** : contenu illustratif, à remplacer par la spécification réelle (skill `project-bootstrap`). Ne pas le considérer comme une source de vérité.

## 🌐 Endpoints REST / GraphQL

### `GET /api/v1/health`
- **Description** : Vérification du statut de l'application
- **Réponse 200** :
  ```json
  { "status": "ok", "uptime": 1234 }
  ```
