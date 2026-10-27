---
name: architecture-review
description: Procedure for auditing project structure against architectural rules
---

# Architecture Review Procedure

## 1. Boundary & Dependency Audit
- Check imports in `src/` to ensure layering constraints are respected (e.g. UI layers do not directly query DB).
- Verify no circular dependencies exist.

## 2. ADR Conformance
- Read `.ai/DECISIONS.md`.
- Ensure new code conforms to previously recorded architectural decisions.

## 3. Documentation Alignment
- Compare actual file organization with `docs/ARCHITECTURE.md`.
- Flag any undocumented components.
