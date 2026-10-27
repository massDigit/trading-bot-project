---
name: bug-investigation
description: Structured workflow for investigating and resolving bugs without symptom patching
---

# Bug Investigation Procedure

## 1. Reproduce
- Never modify code before reproducing or observing the issue through logs or failing tests.
- Capture exact error trace, line numbers, and input parameters.

## 2. Locate
Identify:
- Entry point of the request/data
- Full execution path
- Failing component or boundary

## 3. Root Cause Analysis
Separate:
- Symptom (e.g. `TypeError: Cannot read property 'id' of null`)
- Root Cause (e.g. upstream API returning null due to missing auth header)

*Never patch only the symptom with empty try/catch or fallback defaults.*

## 4. Architectural Fix
- Implement the cleanest fix respecting `.ai/RULES.md` and `.ai/CODING_STANDARDS.md`.
- Verify signature compatibility across all call sites.

## 5. Regression Guard
- Add a unit or integration test reproducing the original bug to prevent regressions.

## 6. Verification
- Run tests and checks defined in `.ai/WORKFLOW.md`.

## 7. Documentation
- If the bug revealed an architectural limitation or flaw, propose it in `.ai/ASSUMPTIONS.md` (`PROPOSED`) and move it to `.ai/DECISIONS.md` only after explicit user approval (`.ai/RULES.md`, rule 6).
