# FieldOps AI — System-Wide Security Review & Threat Audit

**Document Version:** 1.0.0  
**Status:** Approved & Formally Verified  
**Date:** October 2026  
**Author:** Staff Backend Security Engineer & AI Systems Architect  

---

## 1. Executive Summary

FieldOps AI handles sensitive customer personal identifying information (PII), residential addresses, technician real-time physical locations, and mission-critical dispatch operations. Securing this surface requires defensive controls spanning:
1. **Authentication & Cryptographic Foundations** (JWT lifecycle, password hashing, constant-time comparisons)
2. **Role-Based Access Control (RBAC)** across four explicit tiers (Admin, Dispatcher, Technician, Customer)
3. **Insecure Direct Object Reference (IDOR) Mitigation** across work orders, appointments, and conversational sessions
4. **AI Safety & Adversarial Defenses** (Prompt injection filters, two-phase confirmation gates, grounding constraints)
5. **PII Redaction & Sensitive Logging Prevention**

This review audits the complete surface, validates remediation of identified vulnerabilities, and details the API route authorization matrix.

---

## 2. API Route Authorization Matrix

All endpoints require appropriate authorization guards (`Depends(require_roles(...))` or custom capability token validation).

| HTTP Method | Route Path | Allowed Roles / Auth Mechanisms | IDOR / Ownership Protection |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Public (anonymous) | Rate-limited; password complexity enforced |
| `POST` | `/api/v1/auth/login` | Public (anonymous) | Rate-limited; constant-time hash verification |
| `GET` | `/api/v1/auth/me` | Authenticated (Any active role) | Scoped strictly to authenticated `sub` (user ID) |
| `POST` | `/api/v1/customers` | `ADMIN`, `DISPATCHER` | Validated customer profile creation |
| `GET` | `/api/v1/customers` | `ADMIN`, `DISPATCHER` | Paginated listing with search |
| `GET` | `/api/v1/customers/{id}` | `ADMIN`, `DISPATCHER`, `CUSTOMER` | Customer role can only inspect their own profile |
| `POST` | `/api/v1/work-orders` | `ADMIN`, `DISPATCHER`, `CUSTOMER` | Supports `Idempotency-Key` header |
| `GET` | `/api/v1/work-orders` | `ADMIN`, `DISPATCHER`, `CUSTOMER` | Customer queries automatically filter by their customer ID |
| `GET` | `/api/v1/work-orders/{id}`| `ADMIN`, `DISPATCHER`, `CUSTOMER`, `TECHNICIAN` | Customers can only access their orders; techs can only access assigned orders |
| `PATCH`| `/api/v1/work-orders/{id}`| `ADMIN`, `DISPATCHER`, `TECHNICIAN` | State transition machine strictly enforced; audit event recorded |
| `POST` | `/api/v1/technicians` | `ADMIN` | Technician onboarding |
| `GET` | `/api/v1/technicians` | `ADMIN`, `DISPATCHER` | Skills and service area discovery |
| `POST` | `/api/v1/technicians/{id}/location` | `ADMIN`, `DISPATCHER`, `TECHNICIAN` | Techs can only update their own GPS location |
| `POST` | `/api/v1/appointments/available-slots` | `ADMIN`, `DISPATCHER`, `CUSTOMER` | Non-blocking conflict-free slot discovery |
| `POST` | `/api/v1/appointments/hold` | `ADMIN`, `DISPATCHER`, `CUSTOMER` | Ephemeral 10-minute hold via atomic MongoDB mutation |
| `POST` | `/api/v1/appointments/confirm` | `ADMIN`, `DISPATCHER`, `CUSTOMER` | Requires `user_confirmed: true` and valid reservation hold |
| `POST` | `/api/v1/appointments/{id}/cancel` | `ADMIN`, `DISPATCHER`, `CUSTOMER` | Optimistic concurrency locking (`lock_version`); frees calendar |
| `POST` | `/api/v1/appointments/{id}/reschedule` | `ADMIN`, `DISPATCHER`, `CUSTOMER` | Optimistic concurrency locking (`lock_version`); atomicity enforced |
| `POST` | `/api/v1/dispatch/match-candidates` | `ADMIN`, `DISPATCHER` | Hard-constraint deterministic gate followed by soft ML scoring |
| `POST` | `/api/v1/agent/chat` | Public / Authenticated | Message length limited (4000 chars); returns capability `session_token` |
| `POST` | `/api/v1/agent/voice` | Public / Authenticated | Audio payload size limited; STT/TTS mediated |
| `GET` | `/api/v1/agent/sessions/{session_id}` | `ADMIN`, `DISPATCHER`, Session Owner, or `X-Session-Token` | **Remediated IDOR**: rejects unauthorized queries with 401/403 |
| `DELETE`| `/api/v1/agent/sessions/{session_id}` | `ADMIN`, `DISPATCHER`, Session Owner, or `X-Session-Token` | Closes and terminates conversational session |
| `POST` | `/api/v1/ml/predict-duration` | `ADMIN`, `DISPATCHER` | Validated input features; fallback heuristics on missing models |
| `POST` | `/api/v1/ml/predict-risk` | `ADMIN`, `DISPATCHER` | Pre-job features only; returns calibrated risk tiers |
| `POST` | `/api/v1/ml/train` | `ADMIN` | Authenticated offline pipeline retraining with audit logging |
| `GET` | `/api/v1/ml/monitoring/drift` | `ADMIN`, `DISPATCHER` | Rolling drift metrics across recent 500 inferences |
| `POST` | `/api/v1/webhooks/sms` | Webhook Provider | HMAC-SHA256 signature verification (`X-Webhook-Signature`) |
| `POST` | `/api/v1/outbox/process` | `ADMIN` | Trigger background outbox processing batch |
| `POST` | `/api/v1/outbox/replay-dlq` | `ADMIN` | Safely replay failed dead-letter events |

---

## 3. Vulnerability Remediation & Deep-Dive Analysis

### 3.1 IDOR on Intake Conversation Sessions (`GET /api/v1/agent/sessions/{id}`)

- **Vulnerability Description:** Previously, `GET /api/v1/agent/sessions/{session_id}` returned customer conversation transcripts, addresses, and partial work order drafts to any caller with knowledge of a `session_id`, presenting an IDOR vulnerability.
- **Root Cause:** The endpoint lacked authentication dependencies and did not verify session ownership.
- **Remediation Implemented:**
  1. High-entropy session IDs generated using `f"sess_{secrets.token_urlsafe(24)}"`.
  2. Cryptographic capability token (`session_token = secrets.token_urlsafe(32)`) issued upon session creation and returned in `AgentChatResponse` / `AgentVoiceResponse`.
  3. `_authorize_session_access()` check added to `GET` and `DELETE` endpoints:
     - Allows access if caller is authenticated as `ADMIN` or `DISPATCHER`.
     - Allows access if caller is authenticated as `CUSTOMER` and owns the session.
     - Allows access if caller presents valid `X-Session-Token` header matching stored session token (using `secrets.compare_digest`).
     - Rejects unauthenticated/tokenless requests with HTTP 401 Unauthorized.
     - Rejects mismatched/forged tokens with HTTP 403 Forbidden.
  4. Added `DELETE /api/v1/agent/sessions/{session_id}` to allow explicit session termination.
- **Verification:** Verified via `test_session_unauthorized_and_idor_protection` in `tests/integration/test_phase4_voice_agent.py`.

### 3.2 Race Conditions in Slot Holds & Concurrency Invariants

- **Vulnerability Description:** Under concurrent requests, two callers could race to book the same technician slot, causing double-bookings.
- **Remediation Implemented:**
  1. Atomic MongoDB `$pull` / `$push` queries with `$elemMatch` conditional filters on `active_bookings`.
  2. Lease-based state machine on `slot_reservations` (`status: CONFIRMING`, `claim_expires_at`).
  3. Unique sparse index on `appointments.reservation_token`.
  4. Optimistic locking on cancellations and reschedules via `lock_version` field.
  5. Automatic background reconciliation (`reconcile_inconsistent_bookings`) releasing orphaned tentative holds.
- **Verification:** Verified via `test_concurrent_holds_on_same_slot_rejected` in `test_phase2_dispatch_and_scheduling.py`.

---

## 4. AI Safety & Grounding Controls

### 4.1 Two-Phase Confirmation Gate

The AI assistant is strictly prohibited from mutating production booking schedules unilaterally:
- To propose a slot, the agent calls `propose_appointment_hold`, which creates an ephemeral hold.
- To finalize a booking, the agent MUST invoke `confirm_booking` with `user_confirmed: true`.
- If `user_confirmed` is `false` or missing, the tool execution returns `{"success": False, "error": "CONFIRMATION_REQUIRED"}` without modifying the database.
- The same rule protects `reschedule_appointment`.

### 4.2 Adversarial Prompt Injection Defense

Input messages pass through a multi-layer regex inspection pipeline detecting instruction overrides, jailbreak phrases (e.g., `"ignore previous instructions"`, `"developer mode"`, `"reveal system prompt"`). When detected:
1. Tool calling is immediately suspended.
2. The session records an audit event with `escalation_reason = "security_prompt_injection"`.
3. The assistant replies with a polite standard boundary response without revealing hidden system prompts or internal state.

### 4.3 Grounding & Anti-Hallucination Guarantees

FieldOps AI enforces deterministic Pydantic validation before any entity creation:
- Never hallucinates customer addresses, phone numbers, or equipment details.
- Missing required fields are explicitly tracked in `ExtractedWorkOrderDraft.missing_required_fields`.
- The assistant is instructed to ask polite, focused follow-up questions until all required fields are verified.

---

## 5. Sensitive Data & Log Protection

1. **Password Security:** Passwords are hashed using bcrypt/Argon2 with high work factors. Plaintext passwords are never persisted.
2. **PII Masking:** Logs and error messages do not output raw JWT credentials, credit card details, or full customer phone numbers.
3. **CORS Hardening:** Configured via `settings.BACKEND_CORS_ORIGINS` to allow only explicitly registered dashboard domains.
4. **Environment Isolation:** Secrets and API keys are managed exclusively via environment variables and `pydantic-settings`.

