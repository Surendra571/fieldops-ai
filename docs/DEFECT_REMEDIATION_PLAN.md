# FieldOps AI — Defect Remediation & Production Hardening Plan

**Version:** 1.0.0  
**Date:** October 2026  
**Roles:** Staff Software Engineer, Backend Security Engineer, AI Systems Engineer, ML Engineer  
**Baseline Test Status:** 56/56 passing (19.22s) | Ruff: 100% clean (120 files)  

---

## 1. Executive Summary & Objective

This plan outlines the engineering diagnosis, root cause analysis, architecture design, and step-by-step remediation roadmap for all outstanding production-readiness issues in **FieldOps AI**. 

Our engineering objectives:
1. **Crash-Safe & Idempotent Appointment Confirmation:** Eliminate TOCTOU and crash divergence across reservation holds, appointment creation, technician calendar updates, work order status, and outbox event staging using an atomic claim lease protocol with transaction support and automatic reconciliation.
2. **Intake Session Security & IDOR Prevention:** Replace unauthenticated, guessable session access with high-entropy cryptographic tokens, capability authorization, strict customer ownership checks, telephony webhook signature validation, rate limiting, and PII log redaction.
3. **Rigorous & Reproducible ML Evaluation:** Empirically reproduce Model A (duration regression) and Model B (missed-appointment risk classification) metrics using strict chronological splitting and leakage-free pipelines, formally correcting previously overstated metrics.
4. **Integration Verification & Resilient Outbox:** Clearly classify provider adapters, verify timeouts, jittered backoff, idempotent webhook processing, and safe dead-letter replay.
5. **System-Wide Authorization & Security Boundary:** Enforce role-based access control (RBAC) and resource ownership validation across all API routes.
6. **AI Agent Reliability & Guardrails:** Enforce strict Pydantic parameter grounding, two-phase confirmation gates, and prompt injection defenses.

---

## 2. Priority 1 — Crash-Safe, Idempotent Appointment Confirmation & State Invariants

### 2.1 Problem Analysis & Root Cause
- **Vulnerability:** In `appointment_service.py`, `confirm_booking` consumed the reservation token via `find_one_and_delete` before writing the appointment. A crash or network timeout between token consumption and appointment insertion leaves the hold deleted without an appointment record, while the technician's calendar remains blocked in `TENTATIVE_HOLD`. Furthermore, non-transactional writes across 4 collections (`slot_reservations`, `appointments`, `technicians`, `work_orders`, `outbox_events`) can silently diverge on failure.
- **Invariants Defined:**
  1. *Reservation Token Invariant:* Exactly one confirmed appointment may ever be created from a single reservation token.
  2. *Technician Booking Invariant:* A technician can never have overlapping active bookings (`CONFIRMED`, `TENTATIVE_HOLD`, `EN_ROUTE`, `ON_SITE`).
  3. *Work Order Status Invariant:* When an appointment is confirmed, the corresponding work order must transition to `SCHEDULED` with `active_appointment_id` linked.
  4. *Outbox Delivery Invariant:* For every confirmed booking, exactly one `NOTIFICATION_BOOKING_CONFIRMED` outbox event must be staged.

### 2.2 Remediation Design
- **Two-Tier Architecture:**
  - **Tier 1 (MongoDB Transactions):** Where supported (replica set deployment), execute confirmation across `slot_reservations`, `appointments`, `technicians`, `work_orders`, and `outbox_events` within a client session transaction (`start_transaction()`).
  - **Tier 2 (Recoverable Lease State Machine):** For standalone MongoDB deployments where multi-document transactions are unavailable:
    1. **Idempotent Pre-Check:** Check if an appointment with `reservation_token` already exists. If found, return the existing appointment immediately (handling retries after timeout).
    2. **Atomic Lease Claim:** Transition `slot_reservations` from `status: "HELD"` to `status: "CONFIRMING"` using `find_one_and_update` with a 30-second lease timestamp (`claim_expires_at`).
    3. **Unique Sparse Index:** Add unique index on `appointments.reservation_token` to guarantee at the database storage engine that no two appointments can share a token.
    4. **Atomic Step Progression:** Insert appointment, update technician active booking, update work order status, and stage outbox event.
    5. **Finalize Token:** Update `slot_reservations` to `status: "CONSUMED"` or delete.
  - **Background Reconciliation:** Add `reconcile_inconsistent_bookings(db)` to detect orphaned holds or incomplete confirmations (e.g. lease expired in `CONFIRMING`) and either automatically complete sync or roll back the tentative hold.
- **Affected Files:**
  - `app/services/appointment_service.py`
  - `app/repositories/appointment_repo.py`
  - `app/scripts/init_db.py`
  - `tests/integration/test_phase2_dispatch_and_scheduling.py`
- **Regression Tests:**
  - Concurrent confirmations for same reservation token.
  - Client retry after timeout returning existing booking.
  - Crash simulation after reservation claim.
  - Crash simulation after appointment creation before work order update.
  - Expired reservation hold rejection.
  - Concurrent bookings on overlapping technician slots.
  - Cancellation and rescheduling concurrency.

---

## 3. Priority 2 — Secure Intake Sessions & IDOR Prevention

### 3.1 Problem Analysis & Root Cause
- **Vulnerability:** `GET /agent/sessions/{session_id}` allowed unauthenticated inspection of customer transcripts and extracted work-order drafts. Arbitrary session IDs could be supplied to `POST /agent/chat`, allowing cross-user conversation hijacking.
- **Remediation Design:**
  1. **High-Entropy Identifiers:** Generate `session_id` using `secrets.token_urlsafe(24)` and an unguessable capability secret `session_token = secrets.token_urlsafe(32)`.
  2. **Dual-Mode Authorization:**
     - *Authenticated Users:* If caller is logged in, attach `customer_id = current_user.id`. Enforce that customers can only read/update their own sessions. Dispatchers and Admins can view all sessions.
     - *Anonymous Web/Voice Callers:* Require the session capability token (`X-Session-Token` header or query param) matching the session's stored token.
  3. **Session Expiration & Retention:** Add `expires_at` (configurable, default 24 hours). Add a secure cleanup/deletion endpoint `DELETE /agent/sessions/{session_id}`.
  4. **Telephony Webhook Verification:** Validate provider signatures (`X-Twilio-Signature` or `X-Signature-SHA256`) with 300s replay tolerance windows.
  5. **Payload Size & Rate Limits:** Enforce maximum message length (4,000 characters) and per-IP/per-session rate limiting.
  6. **PII Sanitization:** Ensure request body streaming is non-destructively intercepted for logging sanitization.
- **Affected Files:**
  - `app/api/v1/agent.py`
  - `app/services/agent_service.py`
  - `app/repositories/conversation_repo.py`
  - `app/schemas/agent.py`
  - `tests/integration/test_phase4_voice_agent.py`

---

## 4. Priority 3 — Independent Reproduction of ML Evaluation Results

### 4.1 Problem Analysis & Root Cause
- **Discrepancy:** The previous summary report claimed a "193.9% PR-AUC improvement" for Model B, whereas the codebase's actual generated evaluation report cited +91.7% (from baseline 0.133 to 0.255). This must be systematically verified, recalculated from raw code, and documented with complete transparency.
- **Remediation Design:**
  1. **Raw Metric Verification:** Execute `python -m app.ml.trainer` with seed=42 and N=3,000 samples.
  2. **Leakage & Feature Store Audit:** Formally verify that no post-outcome features (`actual_duration_minutes`, `completed_at`, `status`, `cancellation_reason`) exist in pre-job feature matrices.
  3. **Evaluation Protocol:**
     - Model A: Report MAE, RMSE, R² against `HistoricalCategoryAverageBaseline`.
     - Model B: Report PR-AUC, ROC-AUC, Precision, Recall, F1, Brier score against `PriorFrequencyRiskBaseline`.
     - Report Confusion Matrix and probability calibration.
  4. **Document Findings:** Publish verified numbers in `docs/ML_EVALUATION_REPORT.md` and explicitly note synthetic data limitations.
- **Affected Files:**
  - `app/ml/trainer.py`
  - `app/ml/dataset.py`
  - `app/ml/duration_model.py`
  - `app/ml/risk_model.py`
  - `docs/ML_EVALUATION_REPORT.md`

---

## 5. Priority 4 — External Integrations Verification

### 5.1 Remediation Design
- **Adapter Classification Table:**
  | Adapter | Protocol | Supported Mode | Fallback / Mock Behavior |
  |---|---|---|---|
  | `TwilioSendGridNotificationAdapter` | SMS & Email | Live (Env Vars) / Mock Fallback | Emits mock delivery ID if creds absent |
  | `GoogleCalendarAdapter` | Calendar Sync | Simulator / Mock | Simulates OAuth2 sync |
  | `HubSpotCRMAdapter` | CRM Contacts/Deals | Simulator / Mock | Simulates REST webhook sync |
  | `OpenAILLMAdapter` | LLM Tool Calling | Live (API Key) / Deterministic Mock | Fallback to MockLLMAdapter |
  | `WhisperVoiceAdapter` | Audio STT/TTS | Live (API Key) / Audio Mock | Fallback to MockSTT / MockTTS |
- **Resilience Guarantees:**
  - Strict timeout budgets: 5s for SMS/Email, 10s for CRM/Calendar, 15s for LLM/STT.
  - Exponential backoff with jitter on outbox delivery: $T = \min(M, B \times 2^{\text{attempt}}) \times \text{uniform}(0.5, 1.5)$.
  - Idempotent consumer verification via `event_id` and webhook deduplication via `(webhook_id, provider)`.
  - Dead-letter management with admin-only replay and rate limits.
- **Affected Files:**
  - `app/integrations/`
  - `app/services/outbox_service.py`
  - `app/api/v1/integrations.py`
  - `docs/INTEGRATION_VERIFICATION.md`

---

## 6. Priority 5 — System-Wide Authorization & Security Boundary

### 6.1 Remediation Design
- Audit all API routes across `/auth`, `/users`, `/customers`, `/technicians`, `/work-orders`, `/appointments`, `/agent`, `/ml`, `/integrations`, `/webhooks`.
- Enforce:
  - Role-based dependencies (`require_roles(...)`) on administrative and staff endpoints.
  - Resource ownership checks: Customers can only access their own profile, appointments, and work orders; technicians can only access assigned jobs.
  - Rate limiting with client IP and API key tracking.
- **Affected Files:**
  - `app/api/v1/*.py`
  - `app/api/deps.py`
  - `docs/SECURITY_REVIEW.md`

---

## 7. Priority 6 — AI Agent Safeguards & Guardrails

### 7.1 Remediation Design
- **Missing Field Grounding:** If required fields (`service_address`, `issue_description`) are absent, agent must return clarification prompts and NEVER fabricate synthetic values.
- **Two-Phase Confirmation Gate:** Slot hold (`propose_appointment_hold`) must precede booking; final booking requires explicit customer affirmative message.
- **Prompt Injection Scanners:** Reject adversarial jailbreak instructions (`ignore previous instructions`, `maintenance mode`).
- **Bounded Context Memory:** Keep cumulative draft state in MongoDB while truncating raw dialogue tokens to the last 6 turns.
- **Evaluation Benchmark:** Execute `tests/evaluation/run_eval.py` to assert 100% pass rate across all 11 canonical dialogue scenarios.

---

## 8. Priority 7 — Verification & Documentation Deliverables

1. `docs/DEFECT_REMEDIATION_PLAN.md` (This document)
2. `docs/DEFECT_REMEDIATION_REPORT.md` (Post-fix evidence and diffs)
3. `docs/SECURITY_REVIEW.md` (Threat model and RBAC matrix)
4. `docs/ML_EVALUATION_REPORT.md` (Reproduced metrics and leakage analysis)
5. `docs/INTEGRATION_VERIFICATION.md` (Provider modes and resilience tests)
6. `docs/PRODUCTION_READINESS.md` (Final sign-off)

