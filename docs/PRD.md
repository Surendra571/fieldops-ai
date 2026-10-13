# FieldOps AI — Product Requirements Document (PRD)

**Document Version:** 1.0.0  
**Status:** Approved for Architecture & Implementation  
**Target Milestone:** Production MVP  
**Authors:** Senior Software Architect & Staff Backend Engineer  

---

## 1. Executive Summary & Product Vision

**FieldOps AI** is an intelligent, voice-first field service management (FSM) platform designed for home and commercial repair and maintenance service providers (HVAC, plumbing, electrical, appliance repair, roofing). 

Traditional FSM platforms suffer from significant friction:
- Customer intake requires prolonged interactive voice response (IVR) phone trees or rigid web forms.
- Dispatchers manually triage ambiguous problem descriptions and juggle technician schedules across fragmented spreadsheets or legacy ERPs.
- Scheduling errors cause double bookings, missed appointments, and suboptimal driving routes.
- Customers experience frustrating communication blackouts between intake and arrival.

FieldOps AI replaces this broken workflow with an autonomous, highly reliable, voice- and text-driven service platform. Customers speak or text naturally about their service issues. An AI intake agent conversationalist extracts structured repair parameters, validates service feasibility, checks real-time technician availability, and books guaranteed appointments after explicit customer confirmation. Behind the scenes, an intelligent multi-factor dispatch engine matches the best-fit technician using skills, location, drive time, urgency, and machine-learning predictions for job duration and no-show risk.

---

## 2. Target Personas

| Persona | Role & Context | Primary Goals | Key Pain Points |
| :--- | :--- | :--- | :--- |
| **Residential / Commercial Customer** | Homeowner, tenant, or property manager experiencing an urgent or routine equipment malfunction. | Fast problem resolution, immediate appointment confirmation, zero waiting on hold, proactive arrival alerts. | Clunky web forms, vague arrival windows ("between 8 AM and 5 PM"), lack of live updates. |
| **AI Intake Voice/Chat Agent** | Autonomous system interface handling incoming calls and chat requests. | Extract accurate fault diagnostics, identify customer location/urgency, safely invoke backend tools, secure customer confirmation. | Ambiguous caller descriptions, audio dropouts, hallucinations, accidental double-bookings. |
| **Field Dispatcher** | Operations coordinator overseeing a geographic zone with 5–50 field technicians. | Maximize daily completed jobs, minimize drive time, handle emergency escalations, prevent technician burnout. | Schedule conflicts, emergency reprioritization chaos, lack of visibility into actual job progress. |
| **Field Technician** | Certified HVAC, plumbing, or electrical specialist operating in a service van. | Clear job briefings, reliable navigation, accurate time estimates, effortless status logging (en route, on site, complete). | Inaccurate parts information, unexpected job scope creep, difficult mobile data entry while working. |
| **Operations Administrator** | Service business owner or IT manager tracking SLA metrics, revenue, and system reliability. | High system uptime, accurate ML job forecasting, zero lost customer leads, verifiable audit logs. | Compliance, PII leakage, vendor lock-in with voice/LLM providers, system outages. |

---

## 3. Core Problem Statement & Value Proposition

```mermaid
flowchart LR
    A[Inbound Call / Text] --> B[AI Voice/Text Intake Agent]
    B -->|Structured Work Order & Slot Hold| C[Validation & Guardrail Engine]
    C -->|Explicit Customer Confirmation| D[Atomic Reservation & Booking]
    D --> E[Multi-Factor Dispatch Matching]
    E --> F[ML Duration & Risk Predictors]
    F --> G[Dispatcher Console & Technician Dispatch]
    G --> H[Automated Customer SMS/Voice Updates]
```

- **Zero-Wait Customer Intake:** Inbound voice calls and SMS are answered instantly by an agent capable of natural conversational clarification.
- **Strict Guardrails & Determinism:** The AI agent never performs consequential bookings without human confirmation; tool calls are validated against rigorous Pydantic schemas.
- **Intelligent Dispatch Optimization:** Technicians are matched not just by proximity, but through a composite score of skills, drive times, urgency, and ML-predicted job durations.
- **Proactive Risk Mitigation:** Machine learning flags high-risk appointments for no-shows or scope overruns before they disrupt the daily schedule.
- **Real-Time Operational Transparency:** WebSocket-powered dispatcher dashboards and technician portals keep all stakeholders in continuous sync.

---

## 4. Functional Requirements

### 4.1. Conversational Voice & Text Intake
- **Multi-Modal Ingestion:** Accept voice streams (telephony via WebSockets/SIP or web voice) and asynchronous text messages.
- **Natural Language Slot Filling:** Extract key work order attributes from unstructured dialogue:
  - Equipment category (e.g., Central AC, Tankless Water Heater, Main Breaker Panel).
  - Issue description & symptoms (e.g., "compressor humming but fan not spinning", "leaking water under sink").
  - Service address & access notes (e.g., gate code, dog on property).
  - Customer contact details (name, phone, callback preference).
  - Urgency level (`EMERGENCY`, `HIGH`, `MEDIUM`, `ROUTINE`).
- **Conversational Repair Clarification:** If critical slots are ambiguous or missing, the agent asks targeted follow-up questions before attempting to schedule.
- **Consequential Booking Confirmation Boundary:** Before finalizing any reservation or modifying an existing appointment, the agent must present the exact slot, address, and summary, and receive an explicit verbal or textual affirmative confirmation (`YES`, `CONFIRMED`).

### 4.2. Work Order Lifecycle Management
- **Structured Representation:** Work orders must contain standardized categorization, required technician skill tags, estimated duration, urgency score, customer metadata, and full conversational transcripts.
- **Idempotent Ingestion:** Every work order submission must support an `Idempotency-Key` header to eliminate duplicate ticket creation resulting from network retries or repeated caller clicks.
- **State Machine Enforcement:** Work orders must strictly follow an auditable state transition lifecycle:
  `DRAFT` $\rightarrow$ `SUBMITTED` $\rightarrow$ `TRIAGED` $\rightarrow$ `SCHEDULED` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED` (or `CANCELLED` / `FAILED`).

### 4.3. Intelligent Dispatch & Candidate Matching
- **Multi-Factor Scoring Engine:** Match qualified technicians to work orders using a deterministic composite utility function:
  $$\text{Score} = w_1 \cdot \text{SkillMatch} + w_2 \cdot \text{ProximityScore} + w_3 \cdot \text{AvailabilityFit} + w_4 \cdot \text{UrgencyWeight} - w_5 \cdot \text{RiskPenalty}$$
  - **Skill Verification:** Hard filter; technicians must hold all required skill tags (e.g., `HVAC_EPA_CERTIFIED`, `HIGH_VOLTAGE`).
  - **Geospatial Distance & Drive Time:** Calculate travel time between technician's current or previous job location and target service address using provider-independent map adapters.
  - **Availability Windows:** Check technician shift calendars, existing bookings, and buffer times.
- **Dispatch Modes:**
  - *Automated Dispatch:* Instant assignment for emergency work orders or high-confidence slot selections.
  - *Assisted Dispatch:* Recommended candidate ranked list presented to the human dispatcher for single-click assignment.

### 4.4. Scheduling & Atomic Concurrency-Safe Booking
- **Two-Phase Slot Booking:**
  1. *Phase 1 (Ephemeral Hold):* When a customer explores an available appointment window, the slot is held for 10 minutes (`TENTATIVE_HOLD`) with an expiring reservation token.
  2. *Phase 2 (Atomic Confirmation):* Upon customer confirmation, the hold transitions to `CONFIRMED`.
- **Concurrency Guarantee:** Prevent overlapping bookings for the same technician. Enforced via MongoDB atomic conditional updates (`find_one_and_update`) and unique compound index constraints on non-cancelled appointments.

### 4.5. Customer Engagement & Lifecycle Notifications
- **Automated Omnichannel Messaging:**
  - Instant confirmation message (SMS/Email/WhatsApp) with calendar attachment (`.ics`) and one-click rescheduling link.
  - 24-hour and 2-hour pre-appointment reminders.
  - "Technician En Route" alert with live ETA and technician photo/name.
  - "Job Completed" summary with digital invoice receipt and satisfaction rating prompt.
- **Provider-Independent Notification Delivery:** Pluggable adapters for Twilio, SendGrid, AWS SES/SNS, and mock implementations for local testing.

### 4.6. Predictive Machine Learning Models
- **Model 1: Job Duration Predictor (`DurationRegressor`):**
  - Predicts realistic on-site service duration in minutes based on equipment category, age, reported symptoms, property type, and technician experience.
  - Prevents under-scheduling and calendar cascades.
- **Model 2: Missed-Appointment Risk Classifier (`NoShowClassifier`):**
  - Estimates the probability ($0.0 \dots 1.0$) of a customer cancellation or no-show based on lead time, customer history, time of day, urgency, and day of week.
  - Flags high-risk bookings ($\ge 0.45$) for proactive automated SMS verification or dispatcher review.

### 4.7. Dispatcher Operational Console
- **Unified Real-Time Dashboard:**
  - **Kanban Board:** Work orders organized by state (`Unassigned`, `Scheduled`, `In Progress`, `Review Required`).
  - **Schedule Timeline (Gantt):** Daily timeline of technician routes, active jobs, travel buffers, and unassigned slots.
  - **Live Map View:** Real-time technician GPS locations, pending job pins, and active routes.
  - **Manual Override Controls:** Drag-and-drop rescheduling, emergency reassignment, and manual slot release.

### 4.8. Technician Field Interface
- **Mobile-Responsive Progressive Web App:**
  - Daily assigned job manifest with turn-by-turn navigation deep links.
  - Work order briefing: AI-summarized customer problem description, equipment history, gate codes, access notes.
  - Single-tap status progression: `Accept` $\rightarrow$ `En Route` $\rightarrow$ `Arrived / On Site` $\rightarrow$ `Complete`.
  - Field notes, photos, and parts-used logging.

---

## 5. Non-Functional Requirements (NFRs)

| Dimension | Specification | Verification Method |
| :--- | :--- | :--- |
| **Voice / Chat Latency** | Time-to-first-token < 600ms; Voice turnaround < 900ms end-to-end. | Synthetic streaming benchmarks, synthetic WebSocket testing. |
| **API Performance** | P95 response time < 200ms for read endpoints; P95 < 350ms for write/booking endpoints. | Locust / HTTPX load tests against FastAPI endpoints. |
| **System Availability** | 99.9% uptime for core booking and dispatcher APIs. | Health checks, Docker container restart policies, circuit breakers. |
| **Data Integrity** | Zero double bookings permitted under concurrent loads; 100% idempotent retry safety. | Concurrent race-condition test suite simulating simultaneous bookings. |
| **Security & Privacy** | Strict PII redaction in application logs; JWT-based RBAC; TLS 1.3 in transit. | Log audit verification tests; automated secret scanning in CI. |
| **Extensibility & Decoupling** | Clean architectural boundaries; provider-agnostic adapters for all third-party services. | Contract unit tests verifying mock and live adapter parity. |
| **Portability** | Single command local setup via `docker compose up --build`. | Fresh environment smoke test running backend, workers, Mongo, Redis, frontend. |

---

## 6. Synthetic Seed Data Specification (Demo & Testing)

To allow comprehensive demonstration, automated testing, and developer evaluation without production external dependencies, the platform includes a deterministic synthetic seed data generator (`app/scripts/seed_data.py`):
- **10 Technicians:** Distributed across Metro Atlanta (or similar configured metro), varying skills (HVAC Master, Journeyman Plumber, Appliance Specialist), working hours, and GPS coordinates.
- **50 Customers:** Realistic addresses within service zones, phone numbers, contact preferences, and historical service records.
- **100 Historical Work Orders:** Diverse trade categories, urgency levels, symptom notes, and resolved statuses for ML training data generation.
- **20 Active Work Orders & Appointments:** Distributed across states (`SUBMITTED`, `SCHEDULED`, `EN_ROUTE`, `ON_SITE`) to populate the dispatcher Gantt and Kanban boards immediately upon startup.

