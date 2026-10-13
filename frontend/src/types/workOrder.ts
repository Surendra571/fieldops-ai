export type WorkOrderCategory = 'HVAC' | 'PLUMBING' | 'ELECTRICAL' | 'APPLIANCE' | 'ROOFING';
export type WorkOrderPriority = 'EMERGENCY' | 'HIGH' | 'MEDIUM' | 'ROUTINE';
export type WorkOrderStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'TRIAGED'
  | 'SCHEDULED'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'FAILED';

export type WorkOrderSource = 'VOICE' | 'CHAT' | 'WEB' | 'MANUAL';
export type TimeOfDayPreference = 'MORNING' | 'AFTERNOON' | 'EVENING' | 'ANYTIME';

export interface ServiceAddress {
  street: string;
  unit?: string;
  city: string;
  state: string;
  postal_code: string;
  location?: {
    type: string;
    coordinates: [number, number]; // [lng, lat]
  };
  access_notes?: string;
  is_primary?: boolean;
}

export interface PreferredTimeWindow {
  preferred_date?: string;
  time_of_day: TimeOfDayPreference;
  specific_start?: string;
  specific_end?: string;
}

export interface AuditTransition {
  transition_id: string;
  from_status: string;
  to_status: string;
  actor: string;
  timestamp: string;
  reason?: string;
}

export interface WorkOrder {
  id: string;
  work_order_number: string;
  customer_id: string;
  category: WorkOrderCategory;
  priority: WorkOrderPriority;
  urgency?: WorkOrderPriority;
  description: string;
  symptoms: string[];
  required_skills: string[];
  service_address: ServiceAddress;
  preferred_time_window?: PreferredTimeWindow;
  source: WorkOrderSource;
  status: WorkOrderStatus;
  idempotency_key?: string;
  estimated_duration_minutes: number;
  predicted_by_ml: boolean;
  assigned_technician_id?: string;
  active_appointment_id?: string;
  ai_confidence_score?: number;
  audit_trail: AuditTransition[];
  created_at: string;
  updated_at?: string;
}

export interface WorkOrderCreateRequest {
  customer_id: string;
  category: WorkOrderCategory;
  priority: WorkOrderPriority;
  description: string;
  symptoms?: string[];
  required_skills?: string[];
  service_address: ServiceAddress;
  preferred_time_window?: PreferredTimeWindow;
  estimated_duration_minutes?: number;
}

