# FieldOps AI — API Specification Document

**Document Version:** 1.0.0  
**Status:** Approved for Architecture & Implementation  
**Base URL:** `http://localhost:8000/api/v1`  
**Protocol:** HTTP/1.1 & HTTP/2, WebSockets (`ws://`, `wss://`)  
**Security:** Bearer JWT, Role-Based Access Control, `Idempotency-Key` Headers  

---

## 1. Global API Standards & Conventions

### 1.1. Data Representation
- Payloads are strictly formatted in UTF-8 JSON.
- Field names use standard `snake_case`.
- Timestamps are formatted in ISO-8601 UTC with explicit timezone offset: `YYYY-MM-DDTHH:MM:SSZ`.
- Geographic coordinates follow GeoJSON standards: `[longitude, latitude]`.

### 1.2. Standard Error Envelope
All error responses adhere to a consistent RFC 7807-inspired JSON structure:

```json
{
  "error": {
    "code": "SLOT_CONFLICT",
    "message": "The requested appointment slot is no longer available.",
    "details": {
      "technician_id": "tech_01h8y99",
      "requested_start": "2026-10-11T14:00:00Z"
    },
    "request_id": "req_88f912c4-9a10-449e-8c3e",
    "timestamp": "2026-10-10T10:04:12Z"
  }
}
```

### 1.3. Standard HTTP Status Codes
- `200 OK`: Successful read or update mutation.
- `201 Created`: Resource successfully created.
- `400 Bad Request`: Validation failure on input schema.
- `401 Unauthorized`: Missing or expired JWT token.
- `403 Forbidden`: Insufficient role permissions.
- `404 Not Found`: Target resource does not exist.
- `409 Conflict`: Concurrency version mismatch, state machine invalid transition, or duplicate hold.
- `422 Unprocessable Entity`: Semantic validation failure (e.g., end time before start time).
- `500 Internal Server Error`: Unhandled application exception.

---

## 2. Authentication & Authorization

All protected routes require an HTTP Authorization header: `Authorization: Bearer <JWT_TOKEN>`.

### 2.1. Role-Based Access Control (RBAC) Matrix
- `CUSTOMER`: Ingestion sessions, own work orders, self-service reschedule.
- `TECHNICIAN`: View assigned jobs, update location, transition appointment status (`EN_ROUTE`, `ON_SITE`, `COMPLETED`).
- `DISPATCHER`: Full access to dispatching, scheduling, triage, technician directory, overrides.
- `ADMIN`: User management, ML model retraining triggers, system configuration.
- `AI_AGENT`: Internal service token authorizing invocation of safe backend tools.

---

## 3. Ingestion & Conversational AI Endpoints

### 3.1. `POST /intake/conversations`
Initialize a new customer intake session (chat or transcribed voice).
- **Auth:** Public / Anonymous with rate limiting.
- **Request Body:**
  ```json
  {
    "channel": "VOICE", // "VOICE" | "CHAT" | "SMS"
    "caller_phone": "+14045550183",
    "customer_id": "cust_01h8x..." // Optional if existing customer known
  }
  ```
- **Response `201 Created`:**
  ```json
  {
    "session_id": "sess_intake_00912",
    "status": "IN_PROGRESS",
    "created_at": "2026-10-10T10:00:00Z",
    "initial_greeting": "Thank you for calling Metro Field Services! How can we assist you with your home today?"
  }
  ```

### 3.2. `POST /intake/conversations/{session_id}/messages`
Process customer utterance, extract slots, execute safe tools, and return the agent's conversational response.
- **Auth:** Public or Session Token.
- **Request Body:**
  ```json
  {
    "message": "My central air conditioner is making a loud buzzing noise and only blowing warm air. Can someone come out tomorrow afternoon?",
    "audio_metadata": null
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "session_id": "sess_intake_00912",
    "agent_response": "I'm sorry to hear that your AC is blowing warm air. We have a certified HVAC specialist available tomorrow at 2:00 PM who can inspect the system. Would you like me to reserve that appointment for you?",
    "extracted_slots": {
      "category": "HVAC",
      "symptoms": ["WARM_AIR", "BUZZING_NOISE"],
      "urgency": "HIGH",
      "preferred_time_window": "TOMORROW_AFTERNOON"
    },
    "tentative_reservation": {
      "reservation_token": "res_token_88ab7c",
      "technician_name": "Marcus Brody",
      "start_time": "2026-10-11T14:00:00Z",
      "end_time": "2026-10-11T15:30:00Z",
      "expires_at": "2026-10-10T10:15:00Z"
    },
    "requires_confirmation": true
  }
  ```

### 3.3. `POST /intake/conversations/{session_id}/confirm-and-book`
Explicit customer confirmation to convert a tentative hold into a finalized work order and appointment.
- **Headers:** `Idempotency-Key: <UUID>`
- **Request Body:**
  ```json
  {
    "reservation_token": "res_token_88ab7c",
    "customer_name": "Eleanor Vance",
    "customer_phone": "+14045550183",
    "service_address": {
      "street": "1428 Elm Street",
      "city": "Atlanta",
      "state": "GA",
      "postal_code": "30309"
    },
    "user_confirmed": true
  }
  ```
- **Response `201 Created`:**
  ```json
  {
    "work_order_id": "wo_01h8z...",
    "work_order_number": "WO-2026-10084",
    "appointment_id": "appt_01h9a...",
    "appointment_number": "APT-2026-5541",
    "technician_name": "Marcus Brody",
    "scheduled_start": "2026-10-11T14:00:00Z",
    "status": "CONFIRMED",
    "confirmation_message": "Appointment confirmed for tomorrow at 2:00 PM. An SMS confirmation with calendar details has been sent to +14045550183."
  }
  ```

### 3.4. `WebSocket /voice/ws/{session_id}`
Real-time bi-directional audio/event stream for telephony integration (Twilio MediaStream or web browser voice).
- **Client Frame:** Inbound binary PCM/mulaw audio chunks or JSON control events (`speech_started`, `speech_ended`).
- **Server Frame:** Outbound synthesized TTS audio chunks, transcript deltas, and session state changes.

---

## 4. Work Order Management Endpoints

### 4.1. `POST /work-orders`
Manually create or submit a work order (e.g., dispatcher entry or API integration).
- **Auth:** `DISPATCHER`, `ADMIN`
- **Headers:** `Idempotency-Key: <UUID>` (Mandatory)
- **Request Body:**
  ```json
  {
    "customer_id": "cust_01h8x...",
    "source": "MANUAL",
    "category": "PLUMBING",
    "priority": "HIGH",
    "description": "Main line backup in basement; standing water reported.",
    "symptoms": ["BACKUP", "STANDING_WATER"],
    "required_skills": ["MASTER_PLUMBER"],
    "service_address": {
      "street": "742 Evergreen Terrace",
      "city": "Atlanta",
      "state": "GA",
      "postal_code": "30310",
      "location": { "type": "Point", "coordinates": [-84.4000, 33.7400] }
    }
  }
  ```
- **Response `201 Created`:** Work order document with generated `work_order_number` and status `SUBMITTED`.

### 4.2. `GET /work-orders`
List and filter work orders for the dispatcher console.
- **Auth:** `DISPATCHER`, `ADMIN`
- **Query Parameters:**
  - `status`: Filter by state (`SUBMITTED`, `TRIAGED`, `SCHEDULED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`).
  - `priority`: Filter by priority (`EMERGENCY`, `HIGH`, `MEDIUM`, `ROUTINE`).
  - `category`: Filter by trade category.
  - `search`: Full-text search on description or customer name.
  - `page`: Default 1.
  - `limit`: Default 50, max 100.
- **Response `200 OK`:**
  ```json
  {
    "items": [ /* array of WorkOrder schemas */ ],
    "total": 142,
    "page": 1,
    "limit": 50,
    "total_pages": 3
  }
  ```

### 4.3. `PATCH /work-orders/{id}/status`
Transition work order status through the domain state machine.
- **Auth:** `DISPATCHER`, `TECHNICIAN`, `ADMIN`
- **Request Body:**
  ```json
  {
    "new_status": "IN_PROGRESS",
    "reason": "Technician checked in on site and began diagnostics",
    "actor_id": "tech_01h8y..."
  }
  ```
- **Response `200 OK`:** Updated work order object with appended audit trail entry.

---

## 5. Technician & Fleet Management Endpoints

### 5.1. `GET /technicians`
Query technicians with optional skill filtering and live status.
- **Auth:** `DISPATCHER`, `ADMIN`
- **Query Parameters:** `status=ACTIVE`, `skills=HVAC_EPA_CERTIFIED`
- **Response `200 OK`:** Array of technician objects.

### 5.2. `POST /technicians/{id}/location`
Update live GPS coordinates from technician mobile application.
- **Auth:** `TECHNICIAN`, `ADMIN`
- **Request Body:**
  ```json
  {
    "coordinates": [-84.3850, 33.7550], // [lon, lat]
    "heading": 180.0,
    "speed_kph": 45.2,
    "battery_level": 0.88,
    "timestamp": "2026-10-10T10:05:00Z"
  }
  ```
- **Response `200 OK`:** Location acknowledged; triggers geofence proximity evaluation if technician is `EN_ROUTE`.

---

## 6. Dispatch & Candidate Matching Endpoints

### 6.1. `POST /dispatch/match-candidates`
Compute scored candidate rankings for a given work order.
- **Auth:** `DISPATCHER`, `ADMIN`, `AI_AGENT`
- **Request Body:**
  ```json
  {
    "work_order_id": "wo_01h8z...",
    "target_date": "2026-10-11",
    "max_candidates": 5
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "work_order_id": "wo_01h8z...",
    "candidates": [
      {
        "technician_id": "tech_01h8y...",
        "name": "Marcus Brody",
        "composite_score": 0.92,
        "skill_match_score": 1.0,
        "proximity_score": 0.89,
        "estimated_drive_time_minutes": 18,
        "available_slots": [
          {
            "start_time": "2026-10-11T14:00:00Z",
            "end_time": "2026-10-11T15:30:00Z"
          }
        ],
        "no_show_risk_score": 0.15
      }
    ]
  }
  ```

### 6.2. `POST /dispatch/manual-assign`
Assign a specific technician and time slot to a work order.
- **Auth:** `DISPATCHER`, `ADMIN`
- **Headers:** `Idempotency-Key: <UUID>`
- **Request Body:**
  ```json
  {
    "work_order_id": "wo_01h8z...",
    "technician_id": "tech_01h8y...",
    "scheduled_start": "2026-10-11T14:00:00Z",
    "scheduled_end": "2026-10-11T15:30:00Z",
    "dispatcher_notes": "Customer requested technician call ahead"
  }
  ```
- **Response `201 Created`:** Confirmed appointment and updated work order.

---

## 7. Appointment Lifecycle Endpoints

### 7.1. `POST /appointments/hold`
Create an ephemeral 10-minute hold for an appointment slot.
- **Auth:** `AI_AGENT`, `DISPATCHER`, `CUSTOMER`
- **Request Body:**
  ```json
  {
    "technician_id": "tech_01h8y...",
    "scheduled_start": "2026-10-11T14:00:00Z",
    "scheduled_end": "2026-10-11T15:30:00Z",
    "customer_id": "cust_01h8x..."
  }
  ```
- **Response `201 Created`:**
  ```json
  {
    "reservation_token": "res_token_88ab7c",
    "expires_at": "2026-10-10T10:15:00Z",
    "status": "TENTATIVE_HOLD"
  }
  ```

### 7.2. `POST /appointments/{id}/reschedule`
Reschedule an existing confirmed appointment to a new slot.
- **Auth:** `DISPATCHER`, `CUSTOMER`, `ADMIN`
- **Headers:** `Idempotency-Key: <UUID>`
- **Request Body:**
  ```json
  {
    "new_start": "2026-10-12T09:00:00Z",
    "new_end": "2026-10-12T10:30:00Z",
    "reason": "Customer out of town on original date"
  }
  ```
- **Response `200 OK`:** Updated appointment details.

---

## 8. AI Agent Tool Execution Endpoints (Internal / Secured)

These endpoints represent the strictly bounded tools exposed to the LLM agent during conversational intake. Each tool enforces strict Pydantic validation:

| Tool Endpoint | Scope | Purpose | Side Effect? |
| :--- | :--- | :--- | :--- |
| `POST /agent/tools/lookup-customer` | Read | Look up customer details by phone number. | No |
| `POST /agent/tools/check-availability` | Read | Find available technician slots given skills and postal code. | No |
| `POST /agent/tools/hold-slot` | Write | Place an ephemeral 10-minute hold on a candidate slot. | Yes (Ephemeral) |
| `POST /agent/tools/confirm-booking` | Write | Commit a tentative hold into a finalized appointment. | **Yes (Consequential - Requires Confirmation)** |

---

## 9. Machine Learning Endpoints

### 9.1. `POST /ml/predict-duration`
- **Request Body:**
  ```json
  {
    "category": "HVAC",
    "symptoms": ["COMPRESSOR_SILENT", "WARM_AIR"],
    "property_type": "RESIDENTIAL",
    "equipment_age_years": 8,
    "technician_experience_years": 4
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "predicted_duration_minutes": 85,
    "confidence_interval_95": [70, 100],
    "model_version": "duration_v1.0.0"
  }
  ```

### 9.2. `POST /ml/predict-no-show-risk`
- **Request Body:**
  ```json
  {
    "lead_time_hours": 28.5,
    "urgency": "HIGH",
    "day_of_week": "MONDAY",
    "hour_of_day": 14,
    "customer_historical_no_shows": 0,
    "channel": "VOICE"
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "no_show_risk_probability": 0.14,
    "risk_level": "LOW",
    "recommended_action": "STANDARD_REMINDER",
    "model_version": "noshow_risk_v1.0.0"
  }
  ```

