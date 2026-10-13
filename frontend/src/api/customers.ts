import { request } from './client';
import { Customer, CustomerCreateRequest } from '../types/customer';

export async function getCustomers(params: { page?: number; skip?: number; limit?: number; search?: string } = {}): Promise<Customer[]> {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) {
    searchParams.set('page', params.page.toString());
  } else if (params.skip !== undefined && params.limit !== undefined) {
    const page = Math.floor(params.skip / params.limit) + 1;
    searchParams.set('page', page.toString());
  }
  if (params.limit !== undefined) searchParams.set('limit', params.limit.toString());
  if (params.search) searchParams.set('search', params.search);
  const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
  const data = await request<any>(`/customers${query}`, { method: 'GET' });
  if (data && Array.isArray(data.items)) {
    return data.items;
  }
  if (Array.isArray(data)) {
    return data;
  }
  return [];
}

export async function getCustomerById(id: string): Promise<Customer> {
  return request<Customer>(`/customers/${id}`, { method: 'GET' });
}

export async function createCustomer(data: CustomerCreateRequest): Promise<Customer> {
  return request<Customer>('/customers', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

