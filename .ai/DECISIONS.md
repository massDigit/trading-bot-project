# DECISIONS.md - Architecture Decision Records (ADR)

> **Registre chronologique des choix techniques et d'architecture.**
>
> Statuts : `ACCEPTED` | `SUPERSEDED` | `DEPRECATED`. Une proposition `APPROVED` dans `.ai/ASSUMPTIONS.md` devient un ADR `ACCEPTED` ici.

---

### ADR-001 : Initialisation du socle IA-Native
- **Date** : 2026-08-08
- **Statut** : `ACCEPTED`
- **Contexte** : Nécessité de structurer le projet pour une collaboration homme-IA optimale et interopérable.
- **Décision** : Adoption de l'architecture standardisée avec routage master `AGENTS.md`, `.ai/` et `.agents/skills/`.
- **Conséquences** : Tout agent IA doit respecter le parcours de lecture obligatoire.
