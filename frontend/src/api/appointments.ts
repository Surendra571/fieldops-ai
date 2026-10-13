import { request } from './client';
import {
  Appointment,
  AppointmentCreateRequest,
  AvailableSlotsResponse,
} from '../types/appointment';

export interface AppointmentFilterParams {
  skip?: number;
  limit?: number;
  status?: string;
  technician_id?: string;
  work_order_id?: string;
  start_date?: string;
  end_date?: string;
}

export async function getAppointments(params: AppointmentFilterParams = {}): Promise<Appointment[]> {
  const searchParams = new URLSearchParams();
  if (params.skip !== undefined) searchParams.set('skip', params.skip.toString());
  if (params.limit !== undefined) searchParams.set('limit', params.limit.toString());
  if (params.status) searchParams.set('status', params.status);
  if (params.technician_id) searchParams.set('technician_id', params.technician_id);
  if (params.work_order_id) searchParams.set('work_order_id', params.work_order_id);
  if (params.start_date) searchParams.set('start_date', params.start_date);
  if (params.end_date) searchParams.set('end_date', params.end_date);

  const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
  const data = await request<any>(`/appointments${query}`, { method: 'GET' });
  if (data && Array.isArray(data.items)) {
    return data.items;
  }
  if (Array.isArray(data)) {
    return data;
  }
  return [];
}

export async function getAppointmentById(id: string): Promise<Appointment> {
  return request<Appointment>(`/appointments/${id}`, { method: 'GET' });
}

export async function createAppointment(
  data: AppointmentCreateRequest,
  idempotencyKey?: string
): Promise<Appointment> {
  return request<Appointment>('/appointments', {
    method: 'POST',
    body: JSON.stringify(data),
    idempotencyKey,
  });
}

export async function updateAppointmentStatus(
  id: string,
  newStatus: string,
  reason?: string
): Promise<Appointment> {
  return request<Appointment>(`/appointments/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ new_status: newStatus, reason }),
  });
}

export async function rescheduleAppointment(
  id: string,
  newStart: string,
  newEnd: string,
  reason?: string
): Promise<Appointment> {
  return request<Appointment>(`/appointments/${id}/reschedule`, {
    method: 'POST',
    body: JSON.stringify({
      scheduled_start: newStart,
      scheduled_end: newEnd,
      reason,
    }),
  });
}

export async function getAvailableSlots(params: {
  target_date: string;
  technician_id?: string;
  work_order_id?: string;
  duration_minutes?: number;
  buffer_minutes?: number;
  timezone?: string;
}): Promise<AvailableSlotsResponse> {
  return request<AvailableSlotsResponse>('/appointments/available-slots', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

