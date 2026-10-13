import { request } from './client';
import { Technician, TechnicianCreateRequest } from '../types/technician';

export async function getTechnicians(params: { page?: number; skip?: number; limit?: number; status?: string; skills?: string[] } = {}): Promise<Technician[]> {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) {
    searchParams.set('page', params.page.toString());
  } else if (params.skip !== undefined && params.limit !== undefined) {
    const page = Math.floor(params.skip / params.limit) + 1;
    searchParams.set('page', page.toString());
  }
  if (params.limit !== undefined) searchParams.set('limit', params.limit.toString());
  if (params.status) searchParams.set('status', params.status);
  if (params.skills && params.skills.length > 0) {
    params.skills.forEach(s => searchParams.append('skills', s));
  }
  const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
  const data = await request<any>(`/technicians${query}`, { method: 'GET' });
  if (data && Array.isArray(data.items)) {
    return data.items;
  }
  if (Array.isArray(data)) {
    return data;
  }
  return [];
}

export async function getTechnicianById(id: string): Promise<Technician> {
  return request<Technician>(`/technicians/${id}`, { method: 'GET' });
}

export async function createTechnician(data: TechnicianCreateRequest): Promise<Technician> {
  return request<Technician>('/technicians', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateTechnician(
  id: string,
  data: Partial<TechnicianCreateRequest>
): Promise<Technician> {
  return request<Technician>(`/technicians/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function updateTechnicianLocation(
  id: string,
  coordinates: [number, number]
): Promise<Technician> {
  return request<Technician>(`/technicians/${id}/location`, {
    method: 'POST',
    body: JSON.stringify({ coordinates }),
  });
}

