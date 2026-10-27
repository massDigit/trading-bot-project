---
name: db-migration
description: Procedure for creating, validating, and applying database migrations safely
---

# Database Migration Procedure

## 1. Schema Design
- Inspect `docs/DATABASE.md`.
- Ensure new entities/columns match data types, nullability, foreign keys, and indexes.

## 2. Migration Generation
- Generate migration script using project's ORM or migration CLI.
- Inspect raw SQL to ensure non-destructive changes or proper rollback steps.

## 3. Migration Test
- Run migration forward and backward in test environment.
- Verify zero data loss or breaking changes to existing models.

## 4. Documentation Update
- Update `docs/DATABASE.md` with new ERD or schema definition.
- If the schema change impacts architecture, propose it in `.ai/ASSUMPTIONS.md` (`PROPOSED`) and move it to `.ai/DECISIONS.md` only after explicit user approval (`.ai/RULES.md`, rule 6).
