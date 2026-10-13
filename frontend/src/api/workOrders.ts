import { request } from './client';
import { WorkOrder, WorkOrderCreateRequest } from '../types/workOrder';

export interface WorkOrderFilterParams {
  skip?: number;
  limit?: number;
  status?: string;
  priority?: string;
  category?: string;
  customer_id?: string;
}

export async function getWorkOrders(params: WorkOrderFilterParams = {}): Promise<WorkOrder[]> {
  const searchParams = new URLSearchParams();
  if (params.skip !== undefined) searchParams.set('skip', params.skip.toString());
  if (params.limit !== undefined) searchParams.set('limit', params.limit.toString());
  if (params.status) searchParams.set('status', params.status);
  if (params.priority) searchParams.set('priority', params.priority);
  if (params.category) searchParams.set('category', params.category);
  if (params.customer_id) searchParams.set('customer_id', params.customer_id);

  const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
  const data = await request<any>(`/work-orders${query}`, { method: 'GET' });
  if (data && Array.isArray(data.items)) {
    return data.items;
  }
  if (Array.isArray(data)) {
    return data;
  }
  return [];
}

export async function getWorkOrderById(id: string): Promise<WorkOrder> {
  return request<WorkOrder>(`/work-orders/${id}`, { method: 'GET' });
}

export async function createWorkOrder(
  data: WorkOrderCreateRequest,
  idempotencyKey?: string
): Promise<WorkOrder> {
  return request<WorkOrder>('/work-orders', {
    method: 'POST',
    body: JSON.stringify(data),
    idempotencyKey,
  });
}

export async function updateWorkOrderStatus(
  id: string,
  newStatus: string,
  reason?: string
): Promise<WorkOrder> {
  return request<WorkOrder>(`/work-orders/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ new_status: newStatus, reason }),
  });
}

