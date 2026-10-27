---
name: new-feature
description: Procedure for designing, implementing, and documenting a new feature
---

# New Feature Development Procedure

## 1. Scope & Spec Alignment
- Read `.ai/CONTEXT.md` and `docs/BUSINESS_RULES.md`.
- Ensure feature goals are aligned with current phase in `.ai/STATE.md`.

## 2. Architectural Design
- Check `docs/ARCHITECTURE.md` and `docs/DATABASE.md`.
- If new tables, models, or API endpoints are needed, update specification docs first.
- If making a major architectural choice, propose it in `.ai/ASSUMPTIONS.md` (`PROPOSED`) and move it to `.ai/DECISIONS.md` only after explicit user approval (`.ai/RULES.md`, rule 6).

## 3. Implementation
- Follow `.ai/CODING_STANDARDS.md` and `.ai/RULES.md`.
- Write modular, decoupled code in `src/`.

## 4. Testing & Verification
- Write unit and integration tests covering positive, negative, and edge cases.
- Run validation commands specified in `.ai/WORKFLOW.md`.

## 5. State & Documentation Update
- Update `docs/FEATURES.md` (mark feature as completed).
- Update `.ai/STATE.md` (update current focus and completed list).
- Update `.ai/TASKS.md`.
