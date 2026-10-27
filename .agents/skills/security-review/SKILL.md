---
name: security-review
description: Procedure for conducting automated and manual security audits
---

# Security Review Procedure

## 1. Secrets Audit
- Search codebase for hardcoded API keys, tokens, passwords, or private keys.
- Ensure `.env` is ignored by Git.

## 2. Input Sanitization & Injection Defense
- Check SQL queries for parameterization.
- Check HTML rendering for XSS prevention.
- Check API routes for input schema validation (Zod, Joi, etc.).

## 3. Auth & Authorization Audit
- Check endpoint protection rules against `docs/SECURITY.md`.
- Verify role-based access control (RBAC) on sensitive operations.

## 4. Report & Remediation
- Log any vulnerabilities found and apply required fixes.
