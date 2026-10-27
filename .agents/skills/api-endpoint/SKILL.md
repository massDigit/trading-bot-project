---
name: api-endpoint
description: Procedure for designing, creating, and documenting API endpoints
---

# API Endpoint Procedure

## 1. Contract Specification
- Read `docs/API.md` and `docs/SECURITY.md`.
- Define path, HTTP method, query/body schemas, and response status codes.

## 2. Security & Auth Check
- Verify authentication requirements (JWT, Session, API key).
- Ensure input validation / payload sanitization.

## 3. Implementation
- Define request/response DTOs or TypeScript types.
- Implement controller / route handler and service layer logic.

## 4. Testing & Verification
- Add integration tests verifying valid payloads, bad payloads (400), unauthorized calls (401/403), and server errors (500).
- Run `.ai/WORKFLOW.md`.

## 5. Documentation
- Update `docs/API.md` with the new endpoint spec.
