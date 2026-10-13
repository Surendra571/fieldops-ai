export type AppointmentStatus =
  | 'TENTATIVE_HOLD'
  | 'CONFIRMED'
  | 'EN_ROUTE'
  | 'ON_SITE'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'RESCHEDULED'
  | 'CANCELLED'
  | 'NO_SHOW';

export interface Appointment {
  id: string;
  appointment_number: string;
  work_order_id: string;
  technician_id: string;
  customer_id: string;
  status: AppointmentStatus;
  scheduled_start: string;
  scheduled_end: string;
  actual_start?: string;
  actual_end?: string;
  lock_version: number;
  reservation_token?: string;
  customer_notes?: string;
  technician_notes?: string;
  missed_appointment_risk_score?: number;
  created_at: string;
  updated_at: string;
}

export interface SlotOption {
  start_time: string;
  end_time: string;
  technician_id: string;
  technician_name: string;
  formatted_time_window: string;
}

export interface AvailableSlotsResponse {
  target_date: string;
  timezone: string;
  slots: SlotOption[];
}

export interface AppointmentCreateRequest {
  work_order_id: string;
  technician_id: string;
  customer_id: string;
  scheduled_start: string;
  scheduled_end: string;
  reservation_token?: string;
  status?: AppointmentStatus;
  customer_notes?: string;
  technician_notes?: string;
}

