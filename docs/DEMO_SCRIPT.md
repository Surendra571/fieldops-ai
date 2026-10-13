# FieldOps AI — Live Demonstration Script & Walkthrough

**Demonstration Goal:** Showcase how FieldOps AI modernizes field service operations through voice-based customer intake, transparent multi-factor technician dispatch, atomic conflict prevention, and predictive ML insights.

**Audience:** Technical Evaluators, Operations Leaders, Field Service Directors  
**Prerequisites:** Backend running on `http://localhost:8000`, Frontend running on `http://localhost:5173` (or Docker on `http://localhost:3000`).

---

## Act 1: Authentication & Role-Based Entry

### 1.1 Objective
Demonstrate secure authentication and rapid switching between roles without manual password typing.

### 1.2 Steps
1. Navigate to the Login screen at `http://localhost:5173/login`.
2. Observe the **Quick Demo Accounts** panel featuring four pre-configured roles:
   - **System Administrator** (`admin@fieldops.ai`)
   - **Dispatcher** (`dispatcher@fieldops.ai`)
   - **Lead HVAC Technician** (`marcus.brody@fieldops.ai`)
   - **Customer** (`customer@fieldops.ai`)
3. Click the **"Dispatcher"** quick-login button.
4. The application authenticates via JWT and navigates directly to the Dispatcher Dashboard.

*Talking Point:* "Authentication uses cryptographically salted bcrypt hashes and signed JWT tokens. Passwords and tokens are automatically redacted in server logs by our PII scrubbers."

---

## Act 2: Dispatcher Dashboard & Real-Time Operational Overview

### 2.1 Objective
Show operational situational awareness across work orders, urgent calls, appointments, and background outbox notifications.

### 2.2 Steps
1. Observe the top KPI metric cards:
   - **Open Work Orders:** Total active jobs across HVAC, plumbing, electrical, and appliance trades.
   - **Urgent / Emergency Requests:** Highlighted in red badge for immediate priority triage.
   - **Today's Scheduled Appointments:** Confirmed bookings for the active calendar date.
   - **Unassigned Jobs:** Requests awaiting technician assignment.
   - **Outbox Queue:** Real-time counter of staged and delivered transactional notifications.
2. Click on the **"Urgent Requests"** card to filter the dashboard agenda directly to high-priority tickets.

*Talking Point:* "The dispatcher has immediate, unified visibility into SLA risks, unassigned jobs, and background messaging pipelines without context switching."

---

## Act 3: Voice & Conversational AI Customer Intake

### 3.1 Objective
Demonstrate the AI intake agent extracting structured work orders, asking focused follow-ups for missing information, and supporting voice interaction.

### 3.2 Scenario A: Missing Address Clarification Gate
1. Navigate to **Customer Intake** (`/intake`).
2. Type or paste the following customer message into the chat:
   > *"Hi, my name is Arthur Pendelton, phone 404-555-0299. My air conditioner is leaking water all over the floor."*
3. Click **Send** (`Enter`).
4. **Agent Response:** Observe the agent acknowledge the leak and politely ask for the exact service street address.
5. **Live Draft Inspector (Right Panel):**
   - Customer Name: `Arthur Pendelton` (`VERIFIED` green badge)
   - Phone: `404-555-0299` (`VERIFIED` green badge)
   - Category: `HVAC` (`VERIFIED` green badge)
   - Service Address: `MISSING` (yellow alert)
   - Completeness Score: `75%`
   - Dispatch Warning: *"Missing required fields: Service Address"*

*Talking Point:* "The agent strictly adheres to a zero-hallucination policy. It will never invent or guess a service location; it must confirm critical details before dispatch."

### 3.3 Scenario B: Completing the Request via Speech
1. In the chat input, send:
   > *"The address is 742 Evergreen Terrace, Atlanta, GA 30306."*
2. Observe the Live Draft Inspector update to **100% Completeness** (`is_ready_for_dispatch: true`).
3. Click the **"Simulate Voice Mode"** toggle button:
   - Audio waveform animation activates.
   - Synthetic speech output plays the audio reply.
4. Click **"Convert to Work Order"**:
   - A structured work order is committed to MongoDB with an auto-generated work order number (e.g., `WO-2026-1048`).

---

## Act 4: Intelligent Dispatch Board & Conflict-Free Booking

### 4.1 Objective
Demonstrate hard-constraint filtering, multi-factor ranking with transparent explanations, atomic slot reservation, and the explicit confirmation gate.

### 4.2 Steps
1. Navigate to the **Dispatch Board** (`/dispatch`).
2. Select the newly created work order from the dropdown (or select an unassigned emergency HVAC ticket).
3. Click **"Find & Rank Matching Technicians"**:
   - Hard constraints execute first: filters for `HVAC_EPA_CERTIFIED` skill, active operating shifts, and Atlanta service radius.
   - Observe candidate ranking cards with composite match scores (e.g. `Score: 0.92`).
4. Expand the **Transparent Explanation**:
   - *"Primary match (score 0.92). Has all 1 required skills (HVAC_EPA_CERTIFIED). Estimated 14 min drive (8.2 km). Balanced workload with 1 assigned jobs."*
5. Select technician **Marcus Brody** and click **"Discover Available Slots"**:
   - The system queries working shifts and existing bookings, offering non-overlapping 90-minute slots.
6. Click an available morning slot (e.g., `Tomorrow 10:00 AM – 11:30 AM`).
   - The system acquires an ephemeral 10-minute hold token (`TENTATIVE_HOLD`).
7. **Explicit Confirmation Gate Modal:**
   - A confirmation dialog appears asking the dispatcher or customer to review the booking details.
   - Click **"Confirm & Finalize Booking"** (`user_confirmed: true`).
   - The booking transitions to `CONFIRMED`.
   - A `BOOKING_CONFIRMATION` event is atomically staged into `outbox_events`.

*Talking Point:* "Our database-enforced atomic update with conditional element matching guarantees that concurrent bookings for the same technician never result in double-booking."

---

## Act 5: Mobile Technician Field Portal

### 5.1 Objective
Show how field technicians view assigned routes and update job progress in real time.

### 5.2 Steps
1. Click **Log Out** in the top right.
2. On the login screen, click **"Technician"** quick-login (`marcus.brody@fieldops.ai`).
3. The app redirects to the **Technician Portal** (`/portal`):
   - Displays the day's route agenda with customer location, issue category, and symptoms.
4. Click **"En Route"**:
   - Appointment status updates to `EN_ROUTE`. Outbox stages an ETA notification.
5. Click **"Start Job"**:
   - Status updates to `IN_PROGRESS`.
6. Click **"Complete Work Order"**:
   - Modal prompts for resolution notes (e.g., *"Replaced faulty capacitor and cleared condensate line. Tested cooling delta at 18 degrees."*).
   - Work order transitions to `COMPLETED`. An automated customer review link notification is staged.

---

## Act 6: Machine Learning Insights & Runtime Telemetry

### 6.1 Objective
Demonstrate how predictive models assist dispatchers and how the system monitors data drift and provides fallbacks.

### 6.2 Steps
1. Log in as **Dispatcher** and navigate to **ML Insights** (`/ml-insights`).
2. **Model A: Job-Duration Regression Playground:**
   - Select Category: `HVAC`, Equipment Age: `8.5 years`, Urgency: `HIGH`.
   - Click **"Predict Duration"**:
   - Output: `Predicted: 88.4 min`, 95% Confidence Interval: `[71.3 min – 105.5 min]`, Baseline: `80.0 min`.
3. **Model B: Missed-Appointment Risk Calculator:**
   - Set Customer No-Show History: `1`, Scheduled Hour: `17` (5:00 PM peak traffic), Distance: `28.5 km`.
   - Click **"Evaluate Risk"**:
   - Output: `Risk: 38% (MEDIUM RISK)`.
   - Contributing Factors:
     - *"Customer has 1 previous missed appointment."*
     - *"Late afternoon window with 28.5 km transit increases delay risk."*
4. **Runtime Feature Drift Monitor:**
   - View the drift telemetry table monitoring sliding-window distributions (equipment age, distance, workload) against training baselines.
   - Point out the active fallback warning badge: if model files are missing, the system gracefully defaults to category averages with zero downtime.

---

## Act 7: Settings & Operational Outbox Drainage

### 7.1 Objective
Demonstrate administrative configuration, weight tuning, and outbox operations.

### 7.2 Steps
1. Navigate to **Settings** (`/settings`) (accessible to Administrators).
2. Review the **Dispatch Composite Weights** sliders:
   - Travel Distance Weight (`0.30`)
   - Workload Balance Weight (`0.25`)
   - Skill Proficiency Weight (`0.25`)
   - Urgency Fit Weight (`0.20`)
3. Review the **Transactional Outbox Pipeline** panel:
   - Displays count of pending, in-flight, sent, and dead-letter events.
   - Click **"Drain / Process Outbox Now"** to trigger immediate batch delivery.
4. Under **Model Maintenance**, click **"Retrain ML Models"**:
   - Executes a reproducible pipeline retraining cycle with fixed random seed `42` across 3,000 synthetic Atlanta records, logging updated evaluation metrics.

---

## Key Architectural Proof Points to Emphasize

1. **Modular Monolith Integrity:** Clean separation of domain logic, state machines, repositories, API routers, and background queues.
2. **Double-Booking Elimination:** Atomic MongoDB document locking prevents race conditions under high concurrency.
3. **Transactional Outbox Reliability:** Dual-write failures are eliminated; committed jobs always receive customer notifications.
4. **Zero-Hallucination AI:** Deterministic verification gates prevent dispatching incomplete requests.
5. **PII Protection:** Strict redaction across logs and masked display across UI views.

